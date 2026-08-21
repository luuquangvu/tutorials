"""Home Assistant Blueprint & Jinja2 Syntax Validator.

Directly leverages Home Assistant Core's native validation engines:
1. Native YAML loader (`homeassistant.util.yaml.loader.load_yaml`) for custom tags.
2. Official domain schemas (`AUTOMATION_BLUEPRINT_SCHEMA`, `TEMPLATE_BLUEPRINT_SCHEMA`, `BLUEPRINT_SCHEMA`).
3. Official selector validation (`homeassistant.helpers.selector.validate_selector`).
4. Official template engine (`homeassistant.helpers.template.TemplateEnvironment`) for all HA filters/tests.
5. Input reference cross-validation against defined blueprint inputs.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import jinja2
import voluptuous as vol
from homeassistant.components.automation.config import AUTOMATION_BLUEPRINT_SCHEMA
from homeassistant.components.blueprint.errors import InvalidBlueprint
from homeassistant.components.blueprint.models import Blueprint
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.helpers.selector import validate_selector
from homeassistant.helpers.template import TemplateEnvironment
from homeassistant.util.yaml.loader import load_yaml
from homeassistant.util.yaml.objects import Input

try:
    from homeassistant.components.template.config import TEMPLATE_BLUEPRINT_SCHEMA
except ImportError:
    TEMPLATE_BLUEPRINT_SCHEMA = None


def get_blueprint_schema(domain: str) -> vol.Schema | vol.All:
    """Return the appropriate Home Assistant blueprint schema for a given domain."""
    if domain == "automation":
        return AUTOMATION_BLUEPRINT_SCHEMA
    if domain == "template":
        if isinstance(TEMPLATE_BLUEPRINT_SCHEMA, vol.Schema):
            return TEMPLATE_BLUEPRINT_SCHEMA
        return BLUEPRINT_SCHEMA
    return BLUEPRINT_SCHEMA


def extract_defined_inputs(input_dict: Any) -> set[str]:
    """Extract all input keys defined in blueprint.input (including nested sections)."""
    keys: set[str] = set()
    if not isinstance(input_dict, Mapping):
        return keys

    for k, v in input_dict.items():
        if isinstance(k, str):
            keys.add(k)
        if isinstance(v, Mapping) and "input" in v and isinstance(v["input"], Mapping):
            keys.update(extract_defined_inputs(v["input"]))
    return keys


def validate_selectors_in_inputs(input_dict: Any, path: str = "blueprint.input") -> list[str]:
    """Validate all selector definitions within blueprint inputs."""
    errors: list[str] = []
    if not isinstance(input_dict, Mapping):
        return errors

    for k, v in input_dict.items():
        curr_path = f"{path}.{k}"
        if isinstance(v, Mapping):
            if "input" in v and isinstance(v["input"], Mapping):
                errors.extend(validate_selectors_in_inputs(v["input"], curr_path))
            elif "selector" in v:
                sel = v.get("selector")
                if isinstance(sel, dict) and sel:
                    try:
                        validate_selector(sel)
                    except vol.Invalid as e:
                        errors.append(f"Invalid selector at '{curr_path}.selector': {e}")
                    except Exception as e:
                        errors.append(f"Selector validation error at '{curr_path}.selector': {e}")
    return errors


def extract_used_inputs(obj: Any) -> list[str]:
    """Recursively find all !input references in the parsed structure."""
    used: list[str] = []
    if isinstance(obj, Input):
        used.append(obj.name)
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            if isinstance(k, Input):
                used.append(k.name)
            elif not isinstance(k, (str, bytes, bytearray)):
                used.extend(extract_used_inputs(k))
            used.extend(extract_used_inputs(v))
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for item in obj:
            used.extend(extract_used_inputs(item))
    return used


def validate_jinja_in_obj(
    obj: Any,
    env: TemplateEnvironment,
    path: str = "root",
    *,
    skip_blueprint_metadata: bool = False,
) -> list[str]:
    """Recursively inspect and parse all Jinja2 template expressions using Home Assistant's TemplateEnvironment."""
    errors: list[str] = []

    if isinstance(obj, str):
        if "{{" in obj or "{%" in obj or "{#" in obj:
            try:
                env.parse(obj)
            except jinja2.TemplateSyntaxError as e:
                errors.append(f"Jinja2 syntax error in '{path}' at line {e.lineno}: {e.message}")
            except Exception as e:
                errors.append(f"Jinja2 parse error in '{path}': {e}")
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            if skip_blueprint_metadata and k == "blueprint":
                continue
            child_path = f"{path}.{k}" if path != "root" else str(k)
            if isinstance(k, str) and ("{{" in k or "{%" in k or "{#" in k):
                try:
                    env.parse(k)
                except jinja2.TemplateSyntaxError as e:
                    errors.append(f"Jinja2 syntax error in key '{child_path}' at line {e.lineno}: {e.message}")
                except Exception as e:
                    errors.append(f"Jinja2 parse error in key '{child_path}': {e}")
            errors.extend(validate_jinja_in_obj(v, env, child_path))
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for idx, item in enumerate(obj):
            errors.extend(validate_jinja_in_obj(item, env, f"{path}[{idx}]"))

    return errors


def validate_blueprint_file(
    file_path: Path, jinja_env: TemplateEnvironment, verbose: bool = False
) -> tuple[bool, list[str], list[str]]:
    """Validate a single blueprint file using Home Assistant Core schemas and template environment."""
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Native Home Assistant YAML Loading
    try:
        data = load_yaml(str(file_path))
    except Exception as e:
        return False, [f"YAML loading error: {e}"], []

    if not isinstance(data, dict):
        return False, ["Invalid blueprint: root must be a YAML mapping (dictionary)"], []

    # Check if this file is a blueprint
    if "blueprint" not in data:
        warnings.append("Not a blueprint (missing 'blueprint:' key)")
        return True, errors, warnings

    blueprint_meta = data.get("blueprint")
    if not isinstance(blueprint_meta, dict):
        errors.append("Invalid blueprint metadata: 'blueprint:' must be a dictionary")
        return False, errors, warnings

    domain = blueprint_meta.get("domain", "automation")
    schema = get_blueprint_schema(domain)

    # 2. Official Home Assistant Blueprint Schema & Model Validation
    try:
        bp = Blueprint(data, expected_domain=domain, schema=schema)
        if bp_errors := bp.validate():
            errors.extend([f"Blueprint validation error: {err}" for err in bp_errors])
    except InvalidBlueprint as e:
        errors.append(f"Invalid blueprint: {e}")
    except Exception as e:
        errors.append(f"Home Assistant Blueprint schema error: {e}")

    # 3. Input Reference Validation
    defined_inputs = extract_defined_inputs(blueprint_meta.get("input", {}))
    used_inputs = extract_used_inputs(data)
    errors.extend(f"Undefined input referenced: '!input {used}'" for used in used_inputs if used not in defined_inputs)
    # 4. Selector Configuration Validation
    selector_errors = validate_selectors_in_inputs(blueprint_meta.get("input", {}))
    errors.extend(selector_errors)

    # 5. Official Home Assistant Jinja2 Syntax Validation
    jinja_errors = validate_jinja_in_obj(data, jinja_env, skip_blueprint_metadata=True)
    errors.extend(jinja_errors)

    # 6. Structure Validation based on domain
    if domain == "automation":
        if "trigger" not in data and "triggers" not in data:
            warnings.append("Automation blueprint has no 'trigger' or 'triggers' section")
        if "action" not in data and "actions" not in data and "sequence" not in data:
            warnings.append("Automation blueprint has no 'action', 'actions', or 'sequence' section")
    elif domain == "script":
        if "sequence" not in data:
            errors.append("Script blueprint is missing required 'sequence:' section")

    is_valid = not errors
    return is_valid, errors, warnings


def main() -> int:
    """CLI entrypoint for blueprint validator."""
    parser = argparse.ArgumentParser(description="Verify Home Assistant Blueprint and Jinja2 syntax across YAML files.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[],
        help="Specific blueprint files or directories to validate. If omitted, scans root directory.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()
    jinja_env = TemplateEnvironment(None)

    root_dir = Path(__file__).resolve().parent.parent
    target_files: list[Path] = []
    if args.paths:
        for p in args.paths:
            if p.is_dir():
                for ext in ("*.yaml", "*.yml"):
                    target_files.extend(
                        candidate
                        for candidate in p.rglob(ext)
                        if not any(part.startswith(".") for part in candidate.relative_to(p).parts[:-1])
                    )
            elif p.is_file():
                target_files.append(p)
            else:
                print(f"Error: Path '{p}' not found.")
                return 1
    else:
        for ext in ("*.yaml", "*.yml"):
            target_files.extend(
                candidate
                for candidate in root_dir.rglob(ext)
                if not any(part.startswith(".") for part in candidate.relative_to(root_dir).parts[:-1])
            )
    target_files = sorted(set(target_files))

    if not target_files:
        print("No YAML files found to validate.")
        return 0

    print("=======================================================")
    print("   Home Assistant Blueprint & Jinja2 Syntax Validator   ")
    print("=======================================================")
    print(f"Scanning {len(target_files)} YAML files...\n")

    total_valid = 0
    total_invalid = 0
    total_skipped = 0

    for file_path in target_files:
        rel_path = file_path.relative_to(root_dir) if file_path.is_relative_to(root_dir) else file_path
        is_valid, errors, warnings = validate_blueprint_file(file_path, jinja_env, args.verbose)

        if "Not a blueprint (missing 'blueprint:' key)" in warnings:
            if args.verbose:
                print(f"  [SKIP] {rel_path} (not a blueprint)")
            total_skipped += 1
            continue

        if is_valid:
            total_valid += 1
            print(f"  [PASS] {rel_path}")
            if warnings and args.verbose:
                for w in warnings:
                    print(f"         Warning: {w}")
        else:
            total_invalid += 1
            print(f"  [FAIL] {rel_path}")
            for err in errors:
                print(f"         [ERROR] {err}")
            for w in warnings:
                print(f"         [WARN]  {w}")

    print("\n-------------------------------------------------------")
    print(f"Results: {total_valid} passed, {total_invalid} failed, {total_skipped} skipped")
    print("-------------------------------------------------------\n")

    return 0 if total_invalid == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

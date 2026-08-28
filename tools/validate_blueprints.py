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
from homeassistant.components.template.config import TEMPLATE_BLUEPRINT_SCHEMA
from homeassistant.helpers.selector import validate_selector
from homeassistant.helpers.template import TemplateEnvironment
from homeassistant.util.yaml.loader import load_yaml
from homeassistant.util.yaml.objects import Input


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


def _is_jinja_template(text: str) -> bool:
    """Check if a string contains Jinja2 template markers."""
    return "{{" in text or "{%" in text or "{#" in text


def _validate_jinja_string(
    text: str,
    env: TemplateEnvironment,
    path: str,
    *,
    is_key: bool = False,
) -> list[str]:
    """Validate a single Jinja2 template string."""
    if not _is_jinja_template(text):
        return []

    target = f"key '{path}'" if is_key else f"'{path}'"
    try:
        env.parse(text)
    except jinja2.TemplateSyntaxError as e:
        return [f"Jinja2 syntax error in {target} at line {e.lineno}: {e.message}"]
    except Exception as e:
        return [f"Jinja2 parse error in {target}: {e}"]
    return []


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
        errors.extend(_validate_jinja_string(obj, env, path))
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            if skip_blueprint_metadata and k == "blueprint":
                continue
            child_path = f"{path}.{k}" if path != "root" else str(k)
            if isinstance(k, str):
                errors.extend(_validate_jinja_string(k, env, child_path, is_key=True))
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


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
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
    return parser.parse_args(argv)


_BLUEPRINT_EXTENSIONS = ("*.yaml", "*.yml")


def _find_yaml_files(directory: Path) -> list[Path]:
    """Find YAML files in a directory, ignoring hidden directories."""
    files: list[Path] = []
    for ext in _BLUEPRINT_EXTENSIONS:
        files.extend(
            candidate
            for candidate in directory.rglob(ext)
            if not any(part.startswith(".") for part in candidate.relative_to(directory).parts[:-1])
        )
    return files


def _collect_target_files(paths: Sequence[Path], root_dir: Path) -> list[Path] | None:
    """Resolve target YAML files from provided paths or default root directory."""
    if not paths:
        return sorted(set(_find_yaml_files(root_dir)))

    target_files: list[Path] = []
    for path in paths:
        if path.is_dir():
            target_files.extend(_find_yaml_files(path))
        elif path.is_file():
            target_files.append(path)
        else:
            print(f"Error: Path '{path}' not found.")
            return None
    return sorted(set(target_files))


_HEADER_WIDTH = 55
_BANNER_TITLE = "Home Assistant Blueprint & Jinja2 Syntax Validator"


def _report_file_result(
    rel_path: Path,
    is_valid: bool,
    errors: list[str],
    warnings: list[str],
    *,
    verbose: bool,
) -> None:
    """Print the validation outcome for a single blueprint file."""
    if is_valid:
        print(f"[PASS] {rel_path}")
        if warnings and verbose:
            for w in warnings:
                print(f"  Warning: {w}")
    else:
        print(f"[FAIL] {rel_path}")
        for err in errors:
            print(f"  [ERROR] {err}")
        for w in warnings:
            print(f"  [WARN]  {w}")


def _validate_all_files(
    target_files: Sequence[Path],
    root_dir: Path,
    jinja_env: TemplateEnvironment,
    *,
    verbose: bool,
) -> tuple[int, int, int]:
    """Validate all target files and print their progress, returning (valid, invalid, skipped) counts."""
    total_valid = 0
    total_invalid = 0
    total_skipped = 0

    for file_path in target_files:
        rel_path = file_path.relative_to(root_dir) if file_path.is_relative_to(root_dir) else file_path
        is_valid, errors, warnings = validate_blueprint_file(file_path, jinja_env, verbose)

        if "Not a blueprint (missing 'blueprint:' key)" in warnings:
            if verbose:
                print(f"[SKIP] {rel_path} (not a blueprint)")
            total_skipped += 1
            continue

        if is_valid:
            total_valid += 1
        else:
            total_invalid += 1

        _report_file_result(rel_path, is_valid, errors, warnings, verbose=verbose)

    return total_valid, total_invalid, total_skipped


def _print_summary(total_valid: int, total_invalid: int, total_skipped: int) -> None:
    """Print the overall validation summary."""
    print(f"\n{'-' * _HEADER_WIDTH}")
    print(f"Results: {total_valid} passed, {total_invalid} failed, {total_skipped} skipped")
    print(f"{'-' * _HEADER_WIDTH}\n")


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for blueprint validator."""
    args = _parse_args(argv)
    root_dir = Path(__file__).resolve().parent.parent

    target_files = _collect_target_files(args.paths, root_dir)
    if target_files is None:
        return 1

    if not target_files:
        print("No YAML files found to validate.")
        return 0

    print("=" * _HEADER_WIDTH)
    print(_BANNER_TITLE.center(_HEADER_WIDTH))
    print("=" * _HEADER_WIDTH)
    print(f"Scanning {len(target_files)} YAML files...\n")

    jinja_env = TemplateEnvironment(None)
    total_valid, total_invalid, total_skipped = _validate_all_files(
        target_files, root_dir, jinja_env, verbose=args.verbose
    )
    _print_summary(total_valid, total_invalid, total_skipped)

    return 0 if total_invalid == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

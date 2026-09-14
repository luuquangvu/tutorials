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
import asyncio
import contextlib
import copy
import math
import os
import re
import sys
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final

import jinja2
from jinja2 import nodes
from jinja2.sandbox import ImmutableSandboxedEnvironment

if TYPE_CHECKING:
    import voluptuous as vol
else:
    try:
        import probatio as vol
    except ImportError:
        import voluptuous as vol

import homeassistant.components.template.config as template_config
from homeassistant.components.automation.config import (
    AUTOMATION_BLUEPRINT_SCHEMA,
    PLATFORM_SCHEMA,
)
from homeassistant.components.automation.const import CONF_TRIGGER_VARIABLES
from homeassistant.components.blueprint.const import (
    CONF_BLUEPRINT,
    CONF_INPUT,
    CONF_USE_BLUEPRINT,
)
from homeassistant.components.blueprint.errors import InvalidBlueprint
from homeassistant.components.blueprint.models import Blueprint, BlueprintInputs
from homeassistant.components.blueprint.schemas import BLUEPRINT_SCHEMA
from homeassistant.components.script.config import SCRIPT_ENTITY_SCHEMA
from homeassistant.components.template.config import (
    CONFIG_SECTION_SCHEMA,
)
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ACTION,
    CONF_ACTIONS,
    CONF_CONDITION,
    CONF_CONDITIONS,
    CONF_DEFAULT,
    CONF_DOMAIN,
    CONF_IF,
    CONF_SEQUENCE,
    CONF_SERVICE,
    CONF_TARGET,
    CONF_TRIGGER,
    CONF_TRIGGERS,
    CONF_UNTIL,
    CONF_VARIABLES,
    CONF_WAIT_FOR_TRIGGER,
    CONF_WHILE,
)

if TYPE_CHECKING:
    from homeassistant.const import ATTR_CONFIG_ENTRY_ID
else:
    try:
        from homeassistant.const import ATTR_CONFIG_ENTRY_ID
    except ImportError:
        ATTR_CONFIG_ENTRY_ID = "config_entry_id"

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector as ha_selector
from homeassistant.helpers.config_validation import comp_entity_ids_or_uuids
from homeassistant.helpers.selector import validate_selector
from homeassistant.helpers.template import (
    MAX_CUSTOM_TEMPLATE_SIZE,
    TemplateEnvironment,
    is_template_string,
)
from homeassistant.util.yaml.loader import load_yaml
from homeassistant.util.yaml.objects import Input

_raw_template_schema: object = getattr(
    template_config, "BLUEPRINT_SCHEMA", getattr(template_config, "TEMPLATE_BLUEPRINT_SCHEMA", None)
)
TEMPLATE_BLUEPRINT_SCHEMA: vol.Schema | None = (
    _raw_template_schema if isinstance(_raw_template_schema, vol.Schema) else None
)


class SelectorType(StrEnum):
    """Home Assistant Core selector type identifiers."""

    ACTION = "action"
    ADDON = "addon"
    APP = "app"
    AREA = "area"
    ASSIST_PIPELINE = "assist_pipeline"
    ATTRIBUTE = "attribute"
    AUTOMATION_BEHAVIOR = "automation_behavior"
    BACKUP_LOCATION = "backup_location"
    BOOLEAN = "boolean"
    CHOOSE = "choose"
    COLOR_RGB = "color_rgb"
    COLOR_TEMP = "color_temp"
    CONDITION = "condition"
    CONFIG_ENTRY = "config_entry"
    CONSTANT = "constant"
    CONVERSATION_AGENT = "conversation_agent"
    COUNTRY = "country"
    DATE = "date"
    DATETIME = "datetime"
    DEVICE = "device"
    DEVICE_CLASS = "device_class"
    DURATION = "duration"
    ENTITY = "entity"
    FILE = "file"
    FILTER = "filter"
    FLOOR = "floor"
    ICON = "icon"
    LABEL = "label"
    LANGUAGE = "language"
    LOCATION = "location"
    MEDIA = "media"
    NUMBER = "number"
    NUMERIC_THRESHOLD = "numeric_threshold"
    OBJECT = "object"
    QR_CODE = "qr_code"
    SELECT = "select"
    SERIAL_PORT = "serial_port"
    STATE = "state"
    STATISTIC = "statistic"
    TARGET = "target"
    TEMPLATE = "template"
    TEXT = "text"
    THEME = "theme"
    TIME = "time"
    TRIGGER = "trigger"


_KNOWN_SELECTOR_TYPES: Final[frozenset[str]] = frozenset(s.value for s in SelectorType)

_MATH_MODULE: Final[str] = "math"
_MATH_UNAVAILABLE_MSG: Final[str] = f"'{_MATH_MODULE}' is not available in Home Assistant templates."
_AST_CTX_LOAD: Final[str] = "load"
_ALLOWED_TEMPLATE_EXTENSION: Final[str] = ".jinja"
_CUSTOM_TEMPLATES_FOLDER: Final[str] = "custom_templates"
_DEFAULT_DUMMY_VALUE: Final[str] = "test.dummy"
_DEFAULT_SELECT_OPTION: Final[str] = "dummy_opt"
_CONF_SELECTOR: Final[str] = "selector"
_ROOT_PATH: Final[str] = "root"


def _get_ha_target_field_keys() -> frozenset[str]:
    """Dynamically extract valid target keys from Home Assistant Core with hardcoded fallback.

    Returns:
        Frozenset of field names recognized as target inputs.
    """
    cv_target = getattr(cv, "TARGET_SERVICE_FIELDS", None)
    if isinstance(cv_target, (set, frozenset, list, tuple)):
        return frozenset(str(k) for k in cv_target)
    if isinstance(cv_target, Mapping):
        return frozenset(str(k) for k in cv_target)

    target_sel = getattr(ha_selector, "TargetSelector", None)
    cfg_schema = getattr(target_sel, "CONFIG_SCHEMA", None)
    if isinstance(cfg_schema, vol.Schema) and isinstance(cfg_schema.schema, Mapping):
        keys: set[str] = set()
        for k in cfg_schema.schema:
            k_name = getattr(k, "schema", k)
            if isinstance(k_name, str):
                keys.add(k_name)
        if keys:
            return frozenset(keys)

    return frozenset(
        {
            ATTR_ENTITY_ID,
            ATTR_DEVICE_ID,
            ATTR_AREA_ID,
            ATTR_FLOOR_ID,
            ATTR_LABEL_ID,
        }
    )


_HA_TARGET_FIELD_KEYS: Final[frozenset[str]] = _get_ha_target_field_keys()
_HA_SERVICE_ACTION_KEYS: Final[frozenset[str]] = frozenset({CONF_ACTION, CONF_SERVICE})
_HA_VARIABLE_BLOCK_KEYS: Final[frozenset[str]] = frozenset({CONF_VARIABLES, CONF_TRIGGER_VARIABLES})
_TRIGGER_PATH_SEGMENTS: Final[frozenset[str]] = frozenset({CONF_TRIGGER, CONF_TRIGGERS, CONF_WAIT_FOR_TRIGGER})
_CONDITION_PATH_SEGMENTS: Final[frozenset[str]] = frozenset(
    {CONF_CONDITION, CONF_CONDITIONS, CONF_IF, CONF_WHILE, CONF_UNTIL}
)


def _get_ha_mutable_method_names() -> frozenset[str]:
    """Dynamically determine mutating collection methods blocked by Home Assistant's sandbox.

    Returns:
        Frozenset of blocked mutating method names.
    """
    blocked_names: set[str] = set()
    env = ImmutableSandboxedEnvironment()

    test_targets: list[object] = [[], {}, set()]
    for target in test_targets:
        for attr in dir(target):
            if attr.startswith("_"):
                continue
            val = getattr(target, attr, None)
            if not callable(val):
                continue
            try:
                if not env.is_safe_attribute(target, attr, val):
                    blocked_names.add(attr)
            except Exception:
                blocked_names.add(attr)

    blocked_names.update({"append", "extend", "insert", "pop", "remove", "clear", "update"})
    return frozenset(blocked_names)


_HA_MUTABLE_METHOD_NAMES: Final[frozenset[str]] = _get_ha_mutable_method_names()
_PYTHON_MATH_NAMES: Final[frozenset[str]] = frozenset(
    name for name in dir(math) if not name.startswith("_") and callable(getattr(math, name, None))
)


def _multi_or_single(sub_cfg: object, dummy: str) -> list[str] | str:
    """Generate list of dummy strings or single string based on 'multiple' flag.

    Args:
        sub_cfg: Selector configuration mapping.
        dummy: Dummy string value.

    Returns:
        List containing dummy string if multiple=True, otherwise dummy string.
    """
    if isinstance(sub_cfg, Mapping) and sub_cfg.get("multiple"):
        return [dummy]
    return dummy


_ID_DUMMY_DEFAULTS: Final[dict[str, str]] = {
    SelectorType.DEVICE: f"dummy_{ATTR_DEVICE_ID}",
    SelectorType.AREA: f"dummy_{ATTR_AREA_ID}",
    SelectorType.FLOOR: f"dummy_{ATTR_FLOOR_ID}",
    SelectorType.LABEL: f"dummy_{ATTR_LABEL_ID}",
    SelectorType.CONFIG_ENTRY: f"dummy_{ATTR_CONFIG_ENTRY_ID}",
}

_SIMPLE_DUMMY_SELECTORS: Final[dict[str, object]] = {
    SelectorType.ACTION: [],
    SelectorType.ADDON: "core_ssh",
    SelectorType.APP: "dummy",
    SelectorType.ASSIST_PIPELINE: "preferred",
    SelectorType.ATTRIBUTE: "state",
    SelectorType.AUTOMATION_BEHAVIOR: "all",
    SelectorType.BACKUP_LOCATION: "/backup",
    SelectorType.BOOLEAN: False,
    SelectorType.COLOR_RGB: [255, 255, 255],
    SelectorType.CONDITION: [{CONF_CONDITION: "state", ATTR_ENTITY_ID: _DEFAULT_DUMMY_VALUE, "state": "on"}],
    SelectorType.CONVERSATION_AGENT: "homeassistant",
    SelectorType.DATE: "2026-01-01",
    SelectorType.DATETIME: "2026-01-01 00:00:00",
    SelectorType.DURATION: {"hours": 0, "minutes": 0, "seconds": 0},
    SelectorType.FILE: "00000000-0000-0000-0000-000000000000",
    SelectorType.ICON: "mdi:home",
    SelectorType.LOCATION: {"latitude": 0.0, "longitude": 0.0},
    SelectorType.NUMERIC_THRESHOLD: {"type": "above", "value": {"number": 0.0}},
    SelectorType.QR_CODE: "dummy",
    SelectorType.SERIAL_PORT: "/dev/ttyUSB0",
    SelectorType.STATE: "on",
    SelectorType.STATISTIC: "sensor.dummy",
    SelectorType.TEMPLATE: "",
    SelectorType.TEXT: "",
    SelectorType.THEME: "default",
    SelectorType.TIME: "00:00:00",
    SelectorType.TRIGGER: [{CONF_TRIGGER: "state", ATTR_ENTITY_ID: _DEFAULT_DUMMY_VALUE}],
}


def _dummy_choose_value(sub_cfg: object) -> object:
    """Derive dummy value for a choose selector from its configured choices.

    Args:
        sub_cfg: Choose selector configuration mapping.

    Returns:
        Mapping or value satisfying the choose selector schema.
    """
    if isinstance(sub_cfg, Mapping):
        choices = sub_cfg.get("choices")
        if isinstance(choices, Mapping) and choices:
            first_key = next(iter(choices.keys()))
            first_choice = choices[first_key]
            if isinstance(first_choice, Mapping):
                sub_sel = first_choice.get(_CONF_SELECTOR)
                if isinstance(sub_sel, Mapping):
                    sub_dummy = generate_dummy_input_value(sub_sel)
                    return {"active_choice": first_key, first_key: sub_dummy}
    return {}


def _dummy_device_class_value(sub_cfg: object) -> object:
    """Derive dummy value for a device_class selector honoring domain and multiple flag.

    Args:
        sub_cfg: Device class selector configuration mapping.

    Returns:
        Device class string or list of strings satisfying schema constraints.
    """
    dummy = "battery"
    if isinstance(sub_cfg, Mapping):
        domain = sub_cfg.get("domain")
        if domain == "switch":
            dummy = "switch"
        elif domain == "cover":
            dummy = "door"
        elif domain == "valve":
            dummy = "water"
        elif domain == "update":
            dummy = "firmware"
    return _multi_or_single(sub_cfg, dummy)


def _dummy_object_value(sub_cfg: object) -> object:
    """Derive dummy value for an object selector honoring configured fields and multiple flag.

    Args:
        sub_cfg: Object selector configuration mapping.

    Returns:
        Dictionary or list of dictionaries satisfying schema constraints.
    """
    obj: dict[str, object] = {}
    if isinstance(sub_cfg, Mapping):
        fields = sub_cfg.get("fields")
        if isinstance(fields, Mapping):
            for field_name, field_info in fields.items():
                if isinstance(field_info, Mapping) and field_info.get("required"):
                    field_sel = field_info.get(_CONF_SELECTOR)
                    if isinstance(field_sel, Mapping):
                        obj[str(field_name)] = generate_dummy_input_value(field_sel)
                    else:
                        obj[str(field_name)] = "dummy"
        if sub_cfg.get("multiple"):
            return [obj]
    return obj


def _dummy_number_value(sub_cfg: object) -> float | int:
    """Derive dummy value for a number selector honoring bounds.

    Args:
        sub_cfg: Number selector configuration mapping.

    Returns:
        Numeric dummy value satisfying schema constraints.
    """
    if not isinstance(sub_cfg, Mapping):
        return 0

    if "min" in sub_cfg:
        try:
            return float(sub_cfg["min"])
        except (ValueError, TypeError):
            return 0
    if "max" in sub_cfg:
        try:
            max_val = float(sub_cfg["max"])
            return min(max_val, 0)
        except (ValueError, TypeError):
            return 0
    return 0


def _dummy_select_value(sub_cfg: object) -> object:
    """Derive dummy value for a select selector from its option configuration.

    Args:
        sub_cfg: Select selector configuration mapping.

    Returns:
        Selected dummy option scalar or list.
    """
    if isinstance(sub_cfg, Mapping):
        options = sub_cfg.get("options")
        if isinstance(options, Sequence) and not isinstance(options, (str, bytes, bytearray)) and options:
            first = options[0]
            val = first.get("value", first) if isinstance(first, Mapping) else first
            return [val] if sub_cfg.get("multiple") else val
    return _multi_or_single(sub_cfg, _DEFAULT_SELECT_OPTION)


def _dummy_color_temp_value(sub_cfg: object) -> int:
    """Derive dummy value for a color_temp selector honoring unit and bounds.

    Args:
        sub_cfg: Color temp selector configuration mapping.

    Returns:
        Integer color temperature in mireds or Kelvin satisfying schema constraints.
    """
    if not isinstance(sub_cfg, Mapping):
        return 300

    is_kelvin = sub_cfg.get("unit") == "kelvin"
    default_val = 3000 if is_kelvin else 300
    min_val = sub_cfg.get("min")
    max_val = sub_cfg.get("max")
    if min_val is not None:
        with contextlib.suppress(ValueError, TypeError):
            default_val = max(default_val, int(min_val))
    if max_val is not None:
        with contextlib.suppress(ValueError, TypeError):
            default_val = min(default_val, int(max_val))
    return default_val


def _dummy_country_value(sub_cfg: object) -> list[str] | str:
    """Derive dummy value for a country selector honoring options and multiple flag.

    Args:
        sub_cfg: Country selector configuration mapping.

    Returns:
        Two-letter country code string or list of codes satisfying schema constraints.
    """
    country = "US"
    if isinstance(sub_cfg, Mapping):
        countries = sub_cfg.get("countries")
        if isinstance(countries, Sequence) and not isinstance(countries, (str, bytes, bytearray)) and countries:
            first = countries[0]
            if isinstance(first, str) and len(first) == 2:
                country = first.upper()
    return _multi_or_single(sub_cfg, country)


def _dummy_language_value(sub_cfg: object) -> list[str] | str:
    """Derive dummy value for a language selector honoring options and multiple flag.

    Args:
        sub_cfg: Language selector configuration mapping.

    Returns:
        Language code string or list of language codes satisfying schema constraints.
    """
    lang = "en"
    if isinstance(sub_cfg, Mapping):
        languages = sub_cfg.get("languages")
        if isinstance(languages, Sequence) and not isinstance(languages, (str, bytes, bytearray)) and languages:
            first = languages[0]
            if isinstance(first, str):
                lang = first
    return _multi_or_single(sub_cfg, lang)


def _dummy_media_value(sub_cfg: object) -> object:
    """Derive dummy value for a media selector honoring accept and multiple constraints.

    Args:
        sub_cfg: Media selector configuration mapping.

    Returns:
        Dictionary or list of dictionaries satisfying media selector schema.
    """
    has_accept = isinstance(sub_cfg, Mapping) and "accept" in sub_cfg
    dummy_item: dict[str, str] = {
        "media_content_id": "dummy",
        "media_content_type": "dummy",
    }
    if not has_accept:
        dummy_item["entity_id"] = "media_player.dummy"

    if isinstance(sub_cfg, Mapping) and sub_cfg.get("multiple"):
        return [dummy_item]
    return dummy_item


def _dummy_entity_value(sub_cfg: object) -> list[str] | str:
    """Derive dummy entity ID honoring domain filter and multiple flag.

    Args:
        sub_cfg: Entity selector configuration mapping.

    Returns:
        Entity ID string or list of entity ID strings satisfying schema constraints.
    """
    domain = "test"
    if isinstance(sub_cfg, Mapping):
        domain_cfg = sub_cfg.get("domain")
        if isinstance(domain_cfg, str) and domain_cfg:
            domain = domain_cfg
        elif isinstance(domain_cfg, Sequence) and not isinstance(domain_cfg, (str, bytes, bytearray)) and domain_cfg:
            first = domain_cfg[0]
            if isinstance(first, str) and first:
                domain = first

    dummy_entity = f"{domain}.dummy"
    return _multi_or_single(sub_cfg, dummy_entity)


def _dummy_target_value(sub_cfg: object) -> dict[str, str]:
    """Derive dummy target mapping honoring entity domain filter.

    Args:
        sub_cfg: Target selector configuration mapping.

    Returns:
        Dictionary satisfying target selector schema.
    """
    domain = "test"
    if isinstance(sub_cfg, Mapping):
        entity_cfg = sub_cfg.get("entity")
        if isinstance(entity_cfg, Mapping):
            domain_cfg = entity_cfg.get("domain")
            if isinstance(domain_cfg, str) and domain_cfg:
                domain = domain_cfg
            elif (
                isinstance(domain_cfg, Sequence) and not isinstance(domain_cfg, (str, bytes, bytearray)) and domain_cfg
            ):
                first = domain_cfg[0]
                if isinstance(first, str) and first:
                    domain = first

    return {ATTR_ENTITY_ID: f"{domain}.dummy"}


def get_ha_live_selectors() -> Mapping[str, type]:
    """Retrieve the live selector registry from Home Assistant Core.

    Returns:
        Mapping of selector type names to selector classes, or empty dict if unavailable.
    """
    selectors = getattr(ha_selector, "SELECTORS", None)
    return selectors if isinstance(selectors, Mapping) else {}


_CANDIDATE_DYNAMIC_DUMMIES: Final[tuple[object, ...]] = (
    _DEFAULT_DUMMY_VALUE,
    "",
    "dummy",
    0,
    False,
    {},
    [],
)


def _is_dummy_value_valid_for_selector(sel_cfg: Mapping[str, object], dummy: object) -> bool:
    """Verify if the generated dummy value satisfies the Home Assistant selector schema.

    Args:
        sel_cfg: Selector configuration mapping.
        dummy: Generated candidate dummy value.

    Returns:
        True if the dummy value satisfies selector schema or if selector cannot be resolved,
        False if the selector schema explicitly rejects the dummy value.
    """
    if not isinstance(sel_cfg, Mapping) or not sel_cfg:
        return False

    sel_type = next(iter(sel_cfg.keys()), None)
    if not isinstance(sel_type, str):
        return False

    registry = getattr(ha_selector, "SELECTORS", None)
    if registry is not None and sel_type not in registry:
        return sel_type in _KNOWN_SELECTOR_TYPES

    try:
        raw_selector: object = ha_selector.selector(dict(sel_cfg))
        if callable(raw_selector):
            raw_selector(dummy)
        return True
    except Exception as err:
        return "outside the event loop" in str(err)


def generate_dummy_input_value(sel_cfg: object) -> object:
    """Generate a minimal valid mock value for a given Home Assistant selector config.

    Args:
        sel_cfg: Selector mapping from blueprint input definition.

    Returns:
        Dummy value appropriate for passing Home Assistant schema validation.
    """
    if not isinstance(sel_cfg, Mapping):
        return _DEFAULT_DUMMY_VALUE

    for sel_type, sub_cfg in sel_cfg.items():
        if sel_type in _ID_DUMMY_DEFAULTS:
            return _multi_or_single(sub_cfg, _ID_DUMMY_DEFAULTS[sel_type])
        if sel_type == SelectorType.ENTITY:
            return _dummy_entity_value(sub_cfg)
        if sel_type == SelectorType.TARGET:
            return _dummy_target_value(sub_cfg)
        if sel_type in _SIMPLE_DUMMY_SELECTORS:
            return copy.deepcopy(_SIMPLE_DUMMY_SELECTORS[sel_type])
        if sel_type == SelectorType.CONSTANT and isinstance(sub_cfg, Mapping) and "value" in sub_cfg:
            return copy.deepcopy(sub_cfg["value"])
        if sel_type == SelectorType.NUMBER:
            return _dummy_number_value(sub_cfg)
        if sel_type == SelectorType.SELECT:
            return _dummy_select_value(sub_cfg)
        if sel_type == SelectorType.COLOR_TEMP:
            return _dummy_color_temp_value(sub_cfg)
        if sel_type == SelectorType.COUNTRY:
            return _dummy_country_value(sub_cfg)
        if sel_type == SelectorType.LANGUAGE:
            return _dummy_language_value(sub_cfg)
        if sel_type == SelectorType.MEDIA:
            return _dummy_media_value(sub_cfg)
        if sel_type == SelectorType.CHOOSE:
            return _dummy_choose_value(sub_cfg)
        if sel_type == SelectorType.DEVICE_CLASS:
            return _dummy_device_class_value(sub_cfg)
        if sel_type == SelectorType.OBJECT:
            return _dummy_object_value(sub_cfg)

    # For any selector not explicitly handled, dynamically probe against HA live selector schemas
    for candidate in _CANDIDATE_DYNAMIC_DUMMIES:
        if _is_dummy_value_valid_for_selector(sel_cfg, candidate):
            return copy.deepcopy(candidate)

    return _DEFAULT_DUMMY_VALUE


_generate_dummy_input_value = generate_dummy_input_value

_TARGET_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)(?:target|data\.target)$")
_ENTITY_ID_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)entity_id(?:\[\d+\])?$")
_DEVICE_ID_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)device_id(?:\[\d+\])?$")
_AREA_ID_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)area_id(?:\[\d+\])?$")
_FLOOR_ID_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)floor_id(?:\[\d+\])?$")
_LABEL_ID_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)label_id(?:\[\d+\])?$")
_ACTION_ITEM_PATH_RE: Final[re.Pattern[str]] = re.compile(
    r"(?:^|\.)(?:action|actions|sequence|then|else|default)\[\d+\]$"
)
_ACTION_BLOCK_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)(?:action|actions|sequence|then|else|default)$")
_TRIGGER_ITEM_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)(?:trigger|triggers)\[\d+\]$")
_TRIGGER_BLOCK_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)(?:trigger|triggers)$")
_CONDITION_ITEM_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)(?:condition|conditions)\[\d+\]$")
_CONDITION_BLOCK_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)(?:condition|conditions)$")
_VARIABLES_BLOCK_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)(?:variables|trigger_variables)$")
_VARIABLE_CHILD_PATH_RE: Final[re.Pattern[str]] = re.compile(r"(?:^|\.)(?:variables|trigger_variables)\.")


def _derive_value_for_path(path: str) -> object | None:
    """Derive compatible dummy value for a single observed blueprint usage path.

    Args:
        path: Dot-notation or bracket-notation structural path.

    Returns:
        Derived dummy value, or None if the path shape cannot be determined.
    """
    if _TARGET_PATH_RE.search(path):
        return {ATTR_ENTITY_ID: _DEFAULT_DUMMY_VALUE}
    if _ENTITY_ID_PATH_RE.search(path):
        return _DEFAULT_DUMMY_VALUE
    if _DEVICE_ID_PATH_RE.search(path):
        return f"dummy_{ATTR_DEVICE_ID}"
    if _AREA_ID_PATH_RE.search(path):
        return f"dummy_{ATTR_AREA_ID}"
    if _FLOOR_ID_PATH_RE.search(path):
        return f"dummy_{ATTR_FLOOR_ID}"
    if _LABEL_ID_PATH_RE.search(path):
        return f"dummy_{ATTR_LABEL_ID}"
    if _ACTION_ITEM_PATH_RE.search(path):
        return {
            CONF_ACTION: "homeassistant.update_entity",
            CONF_TARGET: {ATTR_ENTITY_ID: _DEFAULT_DUMMY_VALUE},
        }
    if _ACTION_BLOCK_PATH_RE.search(path):
        return []
    if _TRIGGER_ITEM_PATH_RE.search(path):
        return {CONF_TRIGGER: "state", ATTR_ENTITY_ID: _DEFAULT_DUMMY_VALUE}
    if _TRIGGER_BLOCK_PATH_RE.search(path):
        return [{CONF_TRIGGER: "state", ATTR_ENTITY_ID: _DEFAULT_DUMMY_VALUE}]
    if _CONDITION_ITEM_PATH_RE.search(path):
        return {CONF_CONDITION: "state", ATTR_ENTITY_ID: _DEFAULT_DUMMY_VALUE, "state": "on"}
    if _CONDITION_BLOCK_PATH_RE.search(path):
        return [{CONF_CONDITION: "state", ATTR_ENTITY_ID: _DEFAULT_DUMMY_VALUE, "state": "on"}]
    if _VARIABLES_BLOCK_PATH_RE.search(path):
        return {}
    return _DEFAULT_DUMMY_VALUE if _VARIABLE_CHILD_PATH_RE.search(path) else None


def derive_dummy_input_value(
    input_name: str,
    input_cfg: Mapping[str, object],
    blueprint_dict: Mapping[str, object],
) -> object | None:
    """Derive a valid dummy value for an input from its selector or observed usage.

    Args:
        input_name: Input key name.
        input_cfg: Input definition configuration dictionary.
        blueprint_dict: Parsed blueprint dictionary.

    Returns:
        A mock value compatible with schema validation, or None if the shape cannot be determined.
    """
    sel = input_cfg.get(_CONF_SELECTOR)
    if isinstance(sel, Mapping) and sel:
        dummy = generate_dummy_input_value(sel)
        return dummy if _is_dummy_value_valid_for_selector(sel, dummy) else None
    usages = [path for inp, path in _iter_input_nodes(blueprint_dict, "") if inp.name == input_name]

    if not usages:
        return _DEFAULT_DUMMY_VALUE

    derived_values: list[object] = []
    for path in usages:
        val = _derive_value_for_path(path)
        if val is None:
            return None
        derived_values.append(val)

    first = derived_values[0]
    return None if any(v != first for v in derived_values[1:]) else first


_EMPTY_UNSAFE_SELECTORS: Final[frozenset[str]] = frozenset(
    {
        SelectorType.ENTITY,
        SelectorType.DEVICE,
        SelectorType.AREA,
        SelectorType.FLOOR,
        SelectorType.LABEL,
    }
)


def is_invalid_for_input_default(value: object, cfg: Mapping[str, object]) -> bool:
    """Check if a default value is null or empty for selectors requiring non-empty values.

    Args:
        value: Default value defined in the input metadata.
        cfg: Input configuration dictionary.

    Returns:
        True if the default value is unsafe/empty when substituted.
    """
    if value in ("", None):
        return True

    sel = cfg.get(_CONF_SELECTOR)
    if isinstance(sel, Mapping) and sel:
        # In Home Assistant blueprints, TargetSelector defaults to {} for optional targets.
        if SelectorType.TARGET in sel:
            return not isinstance(value, Mapping)
        if any(k in sel for k in _EMPTY_UNSAFE_SELECTORS):
            return value in ("", {}, [])
        return value != [] if SelectorType.ACTION in sel else False
    if value in ("", {}, []):
        return True

    try:
        comp_entity_ids_or_uuids(value)
        return False
    except (vol.Invalid, Exception):
        return True


_is_invalid_for_input_default = is_invalid_for_input_default


def _iter_input_nodes(value: object, path: str) -> list[tuple[Input, str]]:
    """Recursively collect all !input nodes and their structural YAML paths.

    Args:
        value: Arbitrary structure parsed from YAML.
        path: Dot-delimited path of the current element.

    Returns:
        List of tuples of (Input, path).
    """
    results: list[tuple[Input, str]] = []
    if isinstance(value, Input):
        results.append((value, path))
    elif isinstance(value, Mapping):
        for k, v in value.items():
            child_path = f"{path}.{k}" if path else str(k)
            results.extend(_iter_input_nodes(v, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for i, elem in enumerate(value):
            child_path = f"{path}[{i}]"
            results.extend(_iter_input_nodes(elem, child_path))
    return results


def _get_path_segments(path: str) -> set[str]:
    """Extract individual key segments from a dot/bracket notation path.

    Args:
        path: Path string with dot or bracket notation.

    Returns:
        Set of segment names.
    """
    return {seg.split("[")[0] for seg in path.split(".") if seg}


def _check_target_inputs(value: object, path: str, empty_default_inputs: Mapping[str, object]) -> list[str]:
    """Validate that target and entity fields do not reference empty-default inputs.

    Args:
        value: Node value to check.
        path: Path string of the node.
        empty_default_inputs: Mapping of input name to default value for invalid-default inputs.

    Returns:
        List of error strings.
    """
    errors: list[str] = []
    for inp, item_path in _iter_input_nodes(value, path):
        if inp.name in empty_default_inputs:
            default_repr = repr(empty_default_inputs[inp.name])
            segments = _get_path_segments(item_path)
            if _TRIGGER_PATH_SEGMENTS & segments:
                errors.append(
                    f"Unsafe '!input {inp.name}' at '{item_path}': trigger entity/device cannot "
                    f"default to an invalid value ({default_repr}). Provide a non-empty default "
                    "or make the input mandatory."
                )
            elif _CONDITION_PATH_SEGMENTS & segments:
                errors.append(
                    f"Unsafe '!input {inp.name}' at '{item_path}': condition entity/device cannot "
                    f"default to an invalid value ({default_repr}). Provide a non-empty default "
                    "or make the input mandatory."
                )
            else:
                errors.append(
                    f"Unsafe '!input {inp.name}' at '{item_path}': input defaults to an invalid "
                    f"target value ({default_repr}). Home Assistant requires a valid "
                    "entity/device ID or template. Use a Jinja template "
                    f"'{{{{ {inp.name} }}}}' referencing an automation variable instead, "
                    "or provide a non-empty default."
                )
    return errors


def _check_service_action_inputs(value: object, path: str, empty_default_inputs: Mapping[str, object]) -> list[str]:
    """Validate that action or service names do not reference empty-default inputs.

    Args:
        value: Node value to check.
        path: Path string of the node.
        empty_default_inputs: Mapping of input name to default value for invalid-default inputs.

    Returns:
        List of error strings.
    """
    errors: list[str] = []
    for inp, item_path in _iter_input_nodes(value, path):
        if inp.name in empty_default_inputs:
            default_repr = repr(empty_default_inputs[inp.name])
            errors.append(
                f"Unsafe '!input {inp.name}' at '{item_path}': service/action name cannot "
                f"default to an empty value ({default_repr})."
            )
    return errors


def validate_safe_input_usages(
    obj: object,
    empty_default_inputs: Mapping[str, object] | None = None,
    path: str = _ROOT_PATH,
) -> list[str]:
    """Check for unsafe !input usages where the input defaults to empty/null in targets/actions.

    Args:
        obj: Blueprint data tree to traverse.
        empty_default_inputs: Optional mapping of input name to invalid default value.
        path: Current traversal path.

    Returns:
        List of error strings for unsafe usages.
    """
    if empty_default_inputs is None:
        if not isinstance(obj, Mapping):
            return []
        blueprint_meta = obj.get(CONF_BLUEPRINT)
        raw_inputs = blueprint_meta.get(CONF_INPUT) if isinstance(blueprint_meta, Mapping) else None
        input_configs = extract_input_configs(raw_inputs)
        empty_default_inputs = {
            k: v[CONF_DEFAULT]
            for k, v in input_configs.items()
            if CONF_DEFAULT in v and is_invalid_for_input_default(v[CONF_DEFAULT], v)
        }

    if not empty_default_inputs:
        return []

    errors: list[str] = []

    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if k in _HA_VARIABLE_BLOCK_KEYS:
                continue

            child_path = f"{path}.{k}" if path != _ROOT_PATH else str(k)

            if k in _HA_TARGET_FIELD_KEYS or k == CONF_TARGET:
                errors.extend(_check_target_inputs(v, child_path, empty_default_inputs))

            if k in _HA_SERVICE_ACTION_KEYS and not isinstance(v, (list, tuple, Mapping)):
                errors.extend(_check_service_action_inputs(v, child_path, empty_default_inputs))

            errors.extend(validate_safe_input_usages(v, empty_default_inputs, child_path))
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for idx, item in enumerate(obj):
            errors.extend(validate_safe_input_usages(item, empty_default_inputs, f"{path}[{idx}]"))

    return errors


def _extract_target_names(target: nodes.Node, names: set[str]) -> None:
    """Recursively extract variable names from an assignment target node.

    Args:
        target: Target Jinja AST node.
        names: Set to collect target names into.
    """
    if isinstance(target, nodes.Name):
        names.add(target.name)
    elif isinstance(target, (nodes.Tuple, nodes.List)):
        for item in target.items:
            _extract_target_names(item, names)


def _check_math_getattr_usage(
    node: nodes.Getattr,
    env: TemplateEnvironment,
    math_globals_desc: str,
) -> str:
    """Format an error message for an invalid math.<attr> expression.

    Args:
        node: Getattr AST node.
        env: Template environment.
        math_globals_desc: Description string of available math globals.

    Returns:
        Formatted error message.
    """
    attr_name = node.attr
    if attr_name in env.globals:
        return (
            f"line {node.lineno}: {_MATH_UNAVAILABLE_MSG} "
            f"'{attr_name}' is directly available as a global: use '{attr_name}' instead of "
            f"'{_MATH_MODULE}.{attr_name}'."
        )
    if attr_name in env.filters:
        return (
            f"line {node.lineno}: {_MATH_UNAVAILABLE_MSG} "
            f"'{attr_name}' is available as a filter: use '| {attr_name}' instead of "
            f"'{_MATH_MODULE}.{attr_name}'."
        )
    return f"line {node.lineno}: {_MATH_UNAVAILABLE_MSG} Use direct math globals/filters instead{math_globals_desc}."


class _ScopedMathInspector:
    """Jinja AST inspector for undeclared math usages honoring local scopes and shadowing."""

    def __init__(self, env: TemplateEnvironment) -> None:
        """Initialize inspector with template environment.

        Args:
            env: Template environment.
        """
        self._env = env
        ha_math_globals = sorted(_PYTHON_MATH_NAMES & set(env.globals.keys()))
        self._math_globals_desc = f" (available globals: {', '.join(ha_math_globals)})" if ha_math_globals else ""
        self.errors: list[str] = []
        self.reported_math_lines: set[int] = set()

    def inspect(self, ast: nodes.Node) -> list[str]:
        """Inspect the AST and return collected error messages.

        Args:
            ast: Root Jinja AST node.

        Returns:
            List of compatibility error strings.
        """
        self._visit(ast, set())
        return self.errors

    def _check_math_getattr(self, node: nodes.Getattr, scope: set[str]) -> bool:
        """Check for math attribute access when math is not in scope.

        Args:
            node: Getattr node to check.
            scope: Currently active variable scope.

        Returns:
            True if an undeclared math attribute usage was reported.
        """
        if (
            isinstance(node.node, nodes.Name)
            and node.node.ctx == _AST_CTX_LOAD
            and node.node.name == _MATH_MODULE
            and _MATH_MODULE not in scope
            and _MATH_MODULE not in self._env.globals
        ):
            self.reported_math_lines.add(node.lineno)
            self.errors.append(_check_math_getattr_usage(node, self._env, self._math_globals_desc))
            return True
        return False

    def _check_math_call(self, node: nodes.Call, scope: set[str]) -> None:
        """Check for direct call of unsupported Python math functions.

        Args:
            node: Call node to check.
            scope: Currently active variable scope.
        """
        func_node = node.node
        if (
            isinstance(func_node, nodes.Name)
            and func_node.ctx == _AST_CTX_LOAD
            and func_node.name in _PYTHON_MATH_NAMES
            and func_node.name not in self._env.globals
            and func_node.name not in scope
        ):
            if func_node.name in self._env.filters:
                hint = f"'{func_node.name}' is registered as a filter: use '| {func_node.name}' instead"
            else:
                hint = f"'{func_node.name}()' is not registered as a global function"
            self.errors.append(
                f"line {func_node.lineno}: '{func_node.name}()' is not available in Home Assistant ({hint})."
            )

    def _check_math_name(self, node: nodes.Name, scope: set[str]) -> None:
        """Check for bare math module usage.

        Args:
            node: Name node to check.
            scope: Currently active variable scope.
        """
        if (
            node.ctx == _AST_CTX_LOAD
            and node.name == _MATH_MODULE
            and _MATH_MODULE not in scope
            and _MATH_MODULE not in self._env.globals
            and node.lineno not in self.reported_math_lines
        ):
            self.errors.append(
                f"line {node.lineno}: {_MATH_UNAVAILABLE_MSG} "
                f"Use direct math globals/filters instead{self._math_globals_desc}."
            )
            self.reported_math_lines.add(node.lineno)

    def _visit_for(self, node: nodes.For, scope: set[str]) -> None:
        """Visit for-loop honoring target variable scope.

        Args:
            node: For node to inspect.
            scope: Currently active variable scope.
        """
        self._visit(node.iter, scope)
        child_scope = set(scope)
        _extract_target_names(node.target, child_scope)
        for child in node.body:
            self._visit(child, child_scope)
        for child in node.else_:
            self._visit(child, scope)

    def _visit_macro(self, node: nodes.Macro, scope: set[str]) -> None:
        """Visit macro definition honoring argument variable scope.

        Args:
            node: Macro node to inspect.
            scope: Currently active variable scope.
        """
        scope.add(node.name)
        child_scope = set(scope)
        for arg in node.args:
            if isinstance(arg, nodes.Name):
                child_scope.add(arg.name)
        for default in node.defaults:
            self._visit(default, scope)
        for child in node.body:
            self._visit(child, child_scope)

    def _visit_with(self, node: nodes.With, scope: set[str]) -> None:
        """Visit with statement honoring bound variable scope.

        Args:
            node: With node to inspect.
            scope: Currently active variable scope.
        """
        for val in getattr(node, "values", ()):
            self._visit(val, scope)
        child_scope = set(scope)
        for target in getattr(node, "targets", ()):
            _extract_target_names(target, child_scope)
        for child in node.body:
            self._visit(child, child_scope)

    def _visit_assign(self, node: nodes.Assign, scope: set[str]) -> None:
        """Visit assignment statement updating current scope.

        Args:
            node: Assign node to inspect.
            scope: Currently active variable scope.
        """
        self._visit(node.node, scope)
        _extract_target_names(node.target, scope)

    def _visit_assign_block(self, node: nodes.AssignBlock, scope: set[str]) -> None:
        """Visit assignment block updating current scope.

        Args:
            node: AssignBlock node to inspect.
            scope: Currently active variable scope.
        """
        for child in node.body:
            self._visit(child, scope)
        _extract_target_names(node.target, scope)

    def _visit_import(self, node: nodes.Import, scope: set[str]) -> None:
        """Register imported module alias in current scope.

        Args:
            node: Import node to inspect.
            scope: Currently active variable scope.
        """
        if isinstance(node.target, str):
            scope.add(node.target)

    def _visit_from_import(self, node: nodes.FromImport, scope: set[str]) -> None:
        """Register imported names and aliases in current scope.

        Args:
            node: FromImport node to inspect.
            scope: Currently active variable scope.
        """
        for item in getattr(node, "names", ()):
            if isinstance(item, tuple) and len(item) == 2:
                scope.add(str(item[1]))
            elif isinstance(item, str):
                scope.add(item)

    def _visit_children(self, node: nodes.Node, scope: set[str]) -> None:
        """Recursively visit all child fields of an unhandled node.

        Args:
            node: AST node to inspect.
            scope: Currently active variable scope.
        """
        for _, field_val in node.iter_fields():
            if isinstance(field_val, list):
                for item in field_val:
                    self._visit(item, scope)
            elif isinstance(field_val, nodes.Node):
                self._visit(field_val, scope)

    def _visit(self, node: object, scope: set[str]) -> None:
        """Recursively inspect node for math usages honoring local scopes and shadowing.

        Args:
            node: Jinja AST node or object.
            scope: Set of variable names currently in scope.
        """
        if not isinstance(node, nodes.Node):
            return

        if isinstance(node, nodes.Getattr) and self._check_math_getattr(node, scope):
            return

        if isinstance(node, nodes.Call):
            self._check_math_call(node, scope)

        if isinstance(node, nodes.Name):
            self._check_math_name(node, scope)

        if isinstance(node, nodes.For):
            self._visit_for(node, scope)
        elif isinstance(node, nodes.Macro):
            self._visit_macro(node, scope)
        elif isinstance(node, nodes.With):
            self._visit_with(node, scope)
        elif isinstance(node, nodes.Assign):
            self._visit_assign(node, scope)
        elif isinstance(node, nodes.AssignBlock):
            self._visit_assign_block(node, scope)
        elif isinstance(node, nodes.Import):
            self._visit_import(node, scope)
        elif isinstance(node, nodes.FromImport):
            self._visit_from_import(node, scope)
        else:
            self._visit_children(node, scope)


def _check_math_module_usages(ast: nodes.Node, env: TemplateEnvironment) -> list[str]:
    """Flag undeclared 'math' module usage honoring local scopes, shadowing, and aliases.

    Args:
        ast: Root Jinja AST node.
        env: Template environment.

    Returns:
        List of error strings.
    """
    return [] if _MATH_MODULE in env.globals else _ScopedMathInspector(env).inspect(ast)


def _check_mutating_method_calls(ast: nodes.Node) -> list[str]:
    """Flag mutating collection methods blocked by Home Assistant's sandboxed environment.

    Args:
        ast: Root Jinja AST node.

    Returns:
        List of error strings.
    """
    errors: list[str] = []
    for node in ast.find_all(nodes.Call):
        func_node = node.node
        if isinstance(func_node, nodes.Getattr) and func_node.attr in _HA_MUTABLE_METHOD_NAMES:
            errors.append(
                f"line {func_node.lineno}: calling mutating method '.{func_node.attr}()' is not "
                "allowed in Home Assistant templates."
            )
    return errors


def _is_jinja_template_name(tmpl_name: str) -> bool:
    """Check if an imported name targets a Jinja template rather than a Python module.

    Args:
        tmpl_name: The imported template name.

    Returns:
        True if the name has a .jinja extension, False otherwise.
    """
    return tmpl_name.endswith(_ALLOWED_TEMPLATE_EXTENSION) and tmpl_name != _ALLOWED_TEMPLATE_EXTENSION


def _extract_custom_template_paths(env: TemplateEnvironment | None) -> set[str] | None:
    """Extract valid custom template paths recognized by Home Assistant.

    Args:
        env: The template environment.

    Returns:
        A set of valid relative template paths, or None if context is unavailable.
    """
    if env is None:
        return None

    loader = getattr(env, "loader", None)
    if loader is not None:
        sources = getattr(loader, "sources", None)
        if isinstance(sources, Mapping) and len(sources) > 0:
            return set(sources)
        mapping = getattr(loader, "mapping", None)
        if isinstance(mapping, Mapping) and len(mapping) > 0:
            return set(mapping)

    hass = getattr(env, "hass", None)
    if hass is not None and hasattr(hass, "config") and hasattr(hass.config, "path"):
        jinja_path = hass.config.path(_CUSTOM_TEMPLATES_FOLDER)
        if os.path.isdir(jinja_path):
            jinja_root = Path(jinja_path)
            return {
                item.relative_to(jinja_root).as_posix()
                for item in jinja_root.rglob(f"*{_ALLOWED_TEMPLATE_EXTENSION}")
                if item.is_file() and item.stat().st_size <= MAX_CUSTOM_TEMPLATE_SIZE
            }

    workspace_custom_templates = Path(__file__).resolve().parent.parent / _CUSTOM_TEMPLATES_FOLDER
    if workspace_custom_templates.is_dir():
        return {
            item.relative_to(workspace_custom_templates).as_posix()
            for item in workspace_custom_templates.rglob(f"*{_ALLOWED_TEMPLATE_EXTENSION}")
            if item.is_file() and item.stat().st_size <= MAX_CUSTOM_TEMPLATE_SIZE
        }

    return None


def _is_custom_template_present(
    tmpl_name: str,
    env: TemplateEnvironment | None,
    available_paths: set[str] | None = None,
) -> bool:
    """Check if an imported custom template exists in the loader or on disk.

    Args:
        tmpl_name: The imported template filename or relative path.
        env: The template environment.
        available_paths: Optional pre-extracted set of available custom template paths.

    Returns:
        True if the template exists or context is unavailable; False if known not to exist.
    """
    paths = available_paths if available_paths is not None else _extract_custom_template_paths(env)
    if paths is not None:
        return tmpl_name in paths

    pure_path = PurePosixPath(tmpl_name)
    return not (
        pure_path.is_absolute()
        or tmpl_name.startswith(("/", f"{_CUSTOM_TEMPLATES_FOLDER}/"))
        or ".." in pure_path.parts
    )


def _check_template_imports(
    ast: nodes.Node,
    env: TemplateEnvironment | None = None,
) -> list[str]:
    """Flag invalid template imports and verify custom template existence.

    Args:
        ast: Root Jinja AST node.
        env: Optional template environment.

    Returns:
        List of error strings.
    """
    errors: list[str] = []
    available_paths = _extract_custom_template_paths(env)

    for node in ast.find_all((nodes.Import, nodes.FromImport)):
        template_node = getattr(node, "template", None)
        if isinstance(template_node, nodes.Const) and isinstance(template_node.value, str):
            tmpl_name = template_node.value
        elif isinstance(template_node, nodes.Name):
            tmpl_name = template_node.name
        else:
            tmpl_name = str(getattr(template_node, "value", getattr(template_node, "name", template_node or "")))

        if not _is_jinja_template_name(tmpl_name):
            errors.append(
                f"line {node.lineno}: cannot import Python modules via '{tmpl_name}'; "
                f"only custom templates in '{_CUSTOM_TEMPLATES_FOLDER}' are supported."
            )
            continue

        if not _is_custom_template_present(tmpl_name, env, available_paths):
            errors.append(
                f"line {node.lineno}: custom template '{tmpl_name}' does not exist in '{_CUSTOM_TEMPLATES_FOLDER}'."
            )

    return errors


def check_ha_template_ast_compatibility(
    ast: nodes.Node,
    env: TemplateEnvironment,
) -> list[str]:
    """Inspect Jinja2 AST for structures and math expressions incompatible with Home Assistant.

    Args:
        ast: Root Jinja AST node.
        env: Template environment.

    Returns:
        List of compatibility error strings.
    """
    errors: list[str] = []
    errors.extend(_check_math_module_usages(ast, env))
    errors.extend(_check_mutating_method_calls(ast))
    errors.extend(_check_template_imports(ast, env))
    return errors


_check_ha_template_ast_compatibility = check_ha_template_ast_compatibility


def _validate_jinja_string(
    text: str,
    env: TemplateEnvironment,
    path: str,
    *,
    is_key: bool = False,
) -> list[str]:
    """Validate a single Jinja2 template string against Home Assistant's template environment.

    Args:
        text: Template string to validate.
        env: Home Assistant TemplateEnvironment.
        path: Path identifier of the template.
        is_key: Whether the template appears in a dictionary key.

    Returns:
        List of error strings found.
    """
    if not is_template_string(text):
        return []

    target = f"key '{path}'" if is_key else f"'{path}'"
    errors: list[str] = []

    # 1. Parse AST to verify syntax
    try:
        ast = env.parse(text)
    except jinja2.TemplateSyntaxError as e:
        return [f"Jinja2 syntax error in {target} at line {e.lineno}: {e.message}"]
    except Exception as e:
        return [f"Jinja2 parse error in {target}: {e}"]

    # 2. Compile AST using Home Assistant's TemplateEnvironment to validate filters and tests
    try:
        env.compile(ast)
    except jinja2.TemplateAssertionError as e:
        errors.append(f"Home Assistant template error in {target} at line {e.lineno}: {e.message}")
    except jinja2.TemplateError as e:
        errors.append(f"Home Assistant template compilation error in {target}: {e}")
    except Exception as e:
        errors.append(f"Home Assistant template error in {target}: {e}")

    # 3. Inspect AST for Home Assistant specific compatibility
    errors.extend(
        f"Home Assistant template error in {target} at {err}" for err in check_ha_template_ast_compatibility(ast, env)
    )
    return errors


def validate_jinja_in_obj(
    obj: object,
    env: TemplateEnvironment,
    path: str = _ROOT_PATH,
    *,
    skip_blueprint_metadata: bool = False,
) -> list[str]:
    """Recursively inspect and parse all Jinja2 template expressions using TemplateEnvironment.

    Args:
        obj: Object structure to traverse.
        env: Home Assistant TemplateEnvironment.
        path: Current traversal path.
        skip_blueprint_metadata: Whether to skip blueprint metadata key.

    Returns:
        List of validation error strings.
    """
    errors: list[str] = []

    if isinstance(obj, str):
        errors.extend(_validate_jinja_string(obj, env, path))
    elif isinstance(obj, Mapping):
        for k, v in obj.items():
            if skip_blueprint_metadata and k == CONF_BLUEPRINT:
                continue
            child_path = f"{path}.{k}" if path != _ROOT_PATH else str(k)
            if isinstance(k, str):
                errors.extend(_validate_jinja_string(k, env, child_path, is_key=True))
            errors.extend(validate_jinja_in_obj(v, env, child_path))
    elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
        for idx, item in enumerate(obj):
            errors.extend(validate_jinja_in_obj(item, env, f"{path}[{idx}]"))

    return errors


def extract_defined_inputs(input_dict: object) -> set[str]:
    """Extract all input keys defined in blueprint.input (including nested sections).

    Args:
        input_dict: Raw input dictionary from blueprint metadata.

    Returns:
        Set of all defined input keys.
    """
    keys: set[str] = set()
    if not isinstance(input_dict, Mapping):
        return keys

    for k, v in input_dict.items():
        if isinstance(v, Mapping) and CONF_INPUT in v and isinstance(v[CONF_INPUT], Mapping):
            keys.update(extract_defined_inputs(v[CONF_INPUT]))
        elif isinstance(k, str):
            keys.add(k)
    return keys


def extract_input_configs(input_dict: object) -> dict[str, dict[str, object]]:
    """Extract input definitions mapping input_name -> config dict.

    Args:
        input_dict: Input mapping from blueprint metadata.

    Returns:
        Dictionary mapping input names to configuration dicts.
    """
    configs: dict[str, dict[str, object]] = {}
    if not isinstance(input_dict, Mapping):
        return configs

    for k, v in input_dict.items():
        if isinstance(v, Mapping):
            if CONF_INPUT in v and isinstance(v[CONF_INPUT], Mapping):
                configs |= extract_input_configs(v[CONF_INPUT])
            elif isinstance(k, str):
                configs[k] = dict(v)
        elif isinstance(k, str):
            configs[k] = {}
    return configs


def extract_used_inputs(obj: object) -> list[str]:
    """Recursively find all !input references in the parsed structure.

    Args:
        obj: Object structure to search.

    Returns:
        List of input names referenced via !input tags.
    """
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


def validate_input_references(data: dict[str, object]) -> str | None:
    """Verify that all !input tags reference defined blueprint inputs.

    Args:
        data: Parsed YAML dictionary of the blueprint.

    Returns:
        An error message if undefined inputs are referenced, or None if valid.
    """
    blueprint_meta = data.get(CONF_BLUEPRINT)
    if not isinstance(blueprint_meta, Mapping):
        return None

    defined = extract_defined_inputs(blueprint_meta.get(CONF_INPUT))
    used = extract_used_inputs(data)

    if undefined := sorted({name for name in used if name not in defined}):
        if len(undefined) == 1:
            return f"Undefined input referenced: '!input {undefined[0]}'"
        formatted = ", ".join(f"'!input {name}'" for name in undefined)
        return f"Undefined inputs referenced: {formatted}"

    return None


def validate_selectors_in_inputs(input_dict: object, path: str = "blueprint.input") -> list[str]:
    """Validate all selector definitions within blueprint inputs.

    Args:
        input_dict: Input mapping to validate selectors in.
        path: Dot-delimited path of current traversal.

    Returns:
        List of selector validation error strings.
    """
    errors: list[str] = []
    if not isinstance(input_dict, Mapping):
        return errors

    for k, v in input_dict.items():
        curr_path = f"{path}.{k}"
        if isinstance(v, Mapping):
            if CONF_INPUT in v and isinstance(v[CONF_INPUT], Mapping):
                errors.extend(validate_selectors_in_inputs(v[CONF_INPUT], curr_path))
            elif _CONF_SELECTOR in v:
                sel = v.get(_CONF_SELECTOR)
                if isinstance(sel, dict) and sel:
                    try:
                        validate_selector(sel)
                    except vol.Invalid as e:
                        errors.append(f"Invalid selector at '{curr_path}.selector': {e}")
                    except Exception as e:
                        errors.append(f"Selector validation error at '{curr_path}.selector': {e}")
    return errors


def get_blueprint_schema(domain: str) -> vol.Schema | vol.All:
    """Return the appropriate Home Assistant blueprint schema for a given domain.

    Args:
        domain: Domain of the blueprint.

    Returns:
        The corresponding voluptuous Schema.
    """
    if domain == "automation":
        return AUTOMATION_BLUEPRINT_SCHEMA
    if domain == "template":
        if isinstance(TEMPLATE_BLUEPRINT_SCHEMA, vol.Schema):
            return TEMPLATE_BLUEPRINT_SCHEMA
        return BLUEPRINT_SCHEMA
    return BLUEPRINT_SCHEMA


def validate_substituted_ha_domain_config(
    bp: Blueprint,
    blueprint_data: Mapping[str, object],
    file_path: Path,
    domain: str,
) -> list[str]:
    """Proactively validate substituted blueprint config against Home Assistant Core domain schemas.

    Args:
        bp: Blueprint instance.
        blueprint_data: Raw parsed blueprint mapping.
        file_path: Path to blueprint file.
        domain: Blueprint domain.

    Returns:
        List of validation error strings.
    """
    errors: list[str] = []
    blueprint_meta = blueprint_data.get(CONF_BLUEPRINT, {})
    raw_inputs = blueprint_meta.get(CONF_INPUT, {}) if isinstance(blueprint_meta, Mapping) else {}
    input_configs = extract_input_configs(raw_inputs)
    all_inputs = {**bp.inputs, **input_configs}

    dummy_inputs: dict[str, object] = {}
    for inp_name, inp_cfg in all_inputs.items():
        if isinstance(inp_cfg, Mapping) and CONF_DEFAULT not in inp_cfg:
            dummy_val = derive_dummy_input_value(inp_name, inp_cfg, blueprint_data)
            if dummy_val is None:
                sel_cfg = inp_cfg.get(_CONF_SELECTOR)
                dummy_val = generate_dummy_input_value(sel_cfg if isinstance(sel_cfg, Mapping) else {})
            dummy_inputs[inp_name] = dummy_val

    try:
        inputs = BlueprintInputs(
            bp,
            {CONF_USE_BLUEPRINT: {"path": file_path.name, CONF_INPUT: dummy_inputs}},
        )
        sub_config = inputs.async_substitute()
    except Exception as err:
        return [f"Failed to substitute blueprint defaults: {err}"]

    try:
        if domain == "automation":
            PLATFORM_SCHEMA(sub_config)
        elif domain == "script":
            SCRIPT_ENTITY_SCHEMA(sub_config)
        elif domain == "template":
            CONFIG_SECTION_SCHEMA(sub_config)
    except vol.Invalid as err:
        errors.append(f"Home Assistant Core domain validation error in substituted config: {err}")
    except Exception as err:
        errors.append(f"Unexpected error validating substituted config against HA Core: {err}")

    return errors


def validate_blueprint_file(
    file_path: Path, jinja_env: TemplateEnvironment, verbose: bool = False
) -> tuple[bool, list[str], list[str]]:
    """Validate a single blueprint file using Home Assistant Core schemas and template environment.

    Args:
        file_path: Path to blueprint YAML file.
        jinja_env: Home Assistant TemplateEnvironment.
        verbose: Whether verbose output is enabled.

    Returns:
        Tuple of (is_valid, errors, warnings).
    """
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
    if CONF_BLUEPRINT not in data:
        warnings.append("Not a blueprint (missing 'blueprint:' key)")
        return True, errors, warnings

    blueprint_meta = data.get(CONF_BLUEPRINT)
    if not isinstance(blueprint_meta, dict):
        errors.append("Invalid blueprint metadata: 'blueprint:' must be a dictionary")
        return False, errors, warnings

    domain = blueprint_meta.get(CONF_DOMAIN, "automation")
    schema = get_blueprint_schema(domain)

    # 2. Official Home Assistant Blueprint Schema and Model Validation
    try:
        bp = Blueprint(data, expected_domain=domain, schema=schema)
        if bp_errors := bp.validate():
            errors.extend([f"Blueprint validation error: {err}" for err in bp_errors])
    except InvalidBlueprint as e:
        errors.append(f"Invalid blueprint: {e}")
    except Exception as e:
        errors.append(f"Home Assistant Blueprint schema error: {e}")
        return False, errors, warnings

    # 3. Input Reference Validation
    if input_ref_error := validate_input_references(data):
        errors.append(input_ref_error)

    # 4. Selector Configuration Validation
    selector_errors = validate_selectors_in_inputs(blueprint_meta.get(CONF_INPUT, {}))
    errors.extend(selector_errors)

    # 5. Safe Input Usages Validation (prevent empty default inputs in action targets)
    unsafe_input_errors = validate_safe_input_usages(data)
    errors.extend(unsafe_input_errors)

    # 6. Proactive Substituted Config Validation via Home Assistant Core Domain Schemas
    ha_domain_errors = validate_substituted_ha_domain_config(bp, data, file_path, domain)
    errors.extend(ha_domain_errors)

    # 7. Official Home Assistant Jinja2 Syntax Validation
    jinja_errors = validate_jinja_in_obj(data, jinja_env, skip_blueprint_metadata=True)
    errors.extend(jinja_errors)

    # 8. Structure Validation based on domain
    if domain == "automation":
        if CONF_TRIGGER not in data and CONF_TRIGGERS not in data:
            warnings.append(f"Automation blueprint has no '{CONF_TRIGGER}' or '{CONF_TRIGGERS}' section")
        if CONF_ACTION not in data and CONF_ACTIONS not in data and CONF_SEQUENCE not in data:
            warnings.append(
                f"Automation blueprint has no '{CONF_ACTION}', '{CONF_ACTIONS}', or '{CONF_SEQUENCE}' section"
            )
    elif domain == "script":
        if CONF_SEQUENCE not in data:
            errors.append(f"Script blueprint is missing required '{CONF_SEQUENCE}:' section")

    is_valid = not errors
    return is_valid, errors, warnings


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Command-line arguments sequence.

    Returns:
        Parsed arguments namespace.
    """
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


_BLUEPRINT_EXTENSIONS: Final[tuple[str, ...]] = ("*.yaml", "*.yml")


def _find_yaml_files(directory: Path) -> list[Path]:
    """Find YAML files in a directory, ignoring hidden directories.

    Args:
        directory: Directory path to scan.

    Returns:
        List of matching YAML file paths.
    """
    files: list[Path] = []
    for ext in _BLUEPRINT_EXTENSIONS:
        files.extend(
            candidate
            for candidate in directory.rglob(ext)
            if not any(part.startswith(".") for part in candidate.relative_to(directory).parts[:-1])
        )
    return files


def _collect_target_files(paths: Sequence[Path], root_dir: Path) -> list[Path] | None:
    """Resolve target YAML files from provided paths or default root directory.

    Args:
        paths: Explicit paths provided via CLI.
        root_dir: Workspace root directory.

    Returns:
        Sorted list of candidate paths, or None if an invalid path was provided.
    """
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


_HEADER_WIDTH: Final[int] = 55
_BANNER_TITLE: Final[str] = "Home Assistant Blueprint & Jinja2 Syntax Validator"


def _report_file_result(
    rel_path: Path,
    is_valid: bool,
    errors: list[str],
    warnings: list[str],
    *,
    verbose: bool,
) -> None:
    """Print the validation outcome for a single blueprint file.

    Args:
        rel_path: Relative file path for display.
        is_valid: Whether file validation passed.
        errors: List of error strings.
        warnings: List of warning strings.
        verbose: Verbose output flag.
    """
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
    """Validate all target files and print their progress.

    Args:
        target_files: Files to validate.
        root_dir: Workspace root directory.
        jinja_env: Home Assistant TemplateEnvironment.
        verbose: Verbose flag.

    Returns:
        Tuple of (total_valid, total_invalid, total_skipped).
    """
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
    """Print the overall validation summary.

    Args:
        total_valid: Number of passed blueprints.
        total_invalid: Number of failed blueprints.
        total_skipped: Number of skipped files.
    """
    print(f"\n{'-' * _HEADER_WIDTH}")
    print(f"Results: {total_valid} passed, {total_invalid} failed, {total_skipped} skipped")
    print(f"{'-' * _HEADER_WIDTH}\n")


async def _async_main(argv: Sequence[str] | None = None) -> int:
    """Async entrypoint initializing HomeAssistant instance and validating all blueprints.

    Args:
        argv: Command-line arguments.

    Returns:
        Exit code: 0 if all valid, 1 otherwise.
    """
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

    hass = HomeAssistant("")
    jinja_env = TemplateEnvironment(hass)
    total_valid, total_invalid, total_skipped = _validate_all_files(
        target_files, root_dir, jinja_env, verbose=args.verbose
    )
    _print_summary(total_valid, total_invalid, total_skipped)

    return 0 if total_invalid == 0 else 1


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for blueprint validator.

    Args:
        argv: Command-line arguments.

    Returns:
        Exit code.
    """
    return asyncio.run(_async_main(argv))


if __name__ == "__main__":
    sys.exit(main())

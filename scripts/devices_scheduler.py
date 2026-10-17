"""Device schedule and timer management engine for Home Assistant Pyscript automations.

Provides persistent timer management, dynamic condition evaluations at expiration,
restart recovery, and native action execution without relying on complex YAML loops.
"""

from __future__ import annotations

import asyncio
import difflib
import sqlite3
import threading
import time
from contextlib import closing, suppress
from pathlib import Path
from typing import Any

import orjson
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify


def _resolve_db_path() -> Path:
    """Resolve database path portably for standard or custom HA environments.

    Returns:
        Resolved Path object for the SQLite database.
    """
    if Path("/config").exists():
        return Path("/config/devices_schedules.db")
    with suppress(Exception):
        if "hass" in globals() and hasattr(hass, "config"):  # noqa: F821  # ty:ignore[unresolved-reference]
            return Path(hass.config.path("devices_schedules.db"))  # noqa: F821  # ty:ignore[unresolved-reference]
    return Path("devices_schedules.db")


DB_PATH = _resolve_db_path()
SCHEDULER_SENSOR_ENTITY = "sensor.devices_scheduler"
SCHEDULER_SENSOR_FRIENDLY_NAME = "Devices Scheduler"
SCHEDULER_SENSOR_UNIT_OF_MEASUREMENT = "timers"
_SUN_ENTITY = "sun.sun"
_ZONE_PREFIX = "zone."
_NOBODY_TERMS = frozenset({"nobody", "no_one", "empty", "0", "false", "off", "away"})
_NUMERIC_UNITS = (
    "°c",
    "°f",
    "kwh",
    "kw",
    "ppm",
    "ppb",
    "min",
    "c",
    "f",
    "%",
    "w",
    "lx",
    "v",
    "a",
    "s",
    "h",
)
_ATTRIBUTE_SYNONYMS: dict[str, str] = {
    "temp": "temperature",
    "hum": "humidity",
    "bri": "brightness",
    "vol": "volume",
    "batt": "battery",
    "pos": "position",
    "pwr": "power",
}
_REVERSE_ATTRIBUTE_SYNONYMS: dict[str, str] = {v: k for k, v in _ATTRIBUTE_SYNONYMS.items()}

_DB_READY = False
_DB_READY_LOCK = threading.Lock()
_ACTIVE_TASKS: dict[str, asyncio.Task[None]] = {}
_ACTIVE_TASKS_LOCK = asyncio.Lock()


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _get_db_connection() -> sqlite3.Connection:
    """Create a configured SQLite connection with optimized PRAGMAs.

    Returns:
        Configured sqlite3.Connection object.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA busy_timeout=3000;")
    return conn


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _ensure_db() -> None:
    """Initialize the timer database schema and directory."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(_get_db_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduled_timers (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                end_timestamp REAL NOT NULL,
                remaining REAL NOT NULL,
                duration_seconds REAL NOT NULL,
                condition_spec TEXT,
                actions TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timers_status ON scheduled_timers(status);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_timers_entity ON scheduled_timers(entity_id);")
        conn.commit()


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _ensure_db_once(force: bool = False) -> None:
    """Ensure the database schema exists, optionally forcing a rebuild.

    Args:
        force: If True, forces re-checking of the database schema.
    """
    global _DB_READY
    if force:
        _DB_READY = False
    if _DB_READY and DB_PATH.exists():
        return
    with _DB_READY_LOCK:
        if force:
            _DB_READY = False
        if not _DB_READY or not DB_PATH.exists():
            _ensure_db()
            _DB_READY = True


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _db_save_timer(
    timer_id: str,
    entity_id: str,
    status: str,
    created_at: str,
    end_timestamp: float,
    remaining: float,
    duration_seconds: float,
    condition_spec_json: str,
    actions_json: str,
) -> bool:
    """Insert or update a timer record in SQLite.

    Args:
        timer_id: Unique identifier for the timer.
        entity_id: Target Home Assistant entity ID.
        status: Current status (running, paused, canceled, completed, etc.).
        created_at: ISO timestamp of creation.
        end_timestamp: Target completion epoch timestamp.
        remaining: Remaining duration in seconds.
        duration_seconds: Total duration in seconds.
        condition_spec_json: Serialized JSON specification for expiration condition.
        actions_json: Serialized JSON list of actions to execute.

    Returns:
        True if the write succeeded, False otherwise.
    """
    _ensure_db_once()
    now_iso = dt_util.now().isoformat()
    with closing(_get_db_connection()) as conn:
        conn.execute(
            """
            INSERT INTO scheduled_timers (
                id, entity_id, status, created_at, end_timestamp,
                remaining, duration_seconds, condition_spec, actions, last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status = excluded.status,
                end_timestamp = excluded.end_timestamp,
                remaining = excluded.remaining,
                duration_seconds = excluded.duration_seconds,
                condition_spec = excluded.condition_spec,
                actions = excluded.actions,
                last_updated = excluded.last_updated
            """,
            (
                timer_id,
                entity_id,
                status,
                created_at,
                end_timestamp,
                remaining,
                duration_seconds,
                condition_spec_json,
                actions_json,
                now_iso,
            ),
        )
        conn.commit()
    return True


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _db_get_timer(timer_id: str) -> dict[str, Any] | None:
    """Fetch a single timer by ID.

    Args:
        timer_id: Unique timer identifier.

    Returns:
        Dictionary representation of the timer record or None if absent.
    """
    _ensure_db_once()
    with closing(_get_db_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM scheduled_timers WHERE id = ?",
            (timer_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _db_get_active_timers(entity_id: str | None = None) -> list[dict[str, Any]]:
    """Retrieve all active running or paused timers, optionally filtered by entity.

    Args:
        entity_id: Optional entity ID filter.

    Returns:
        List of matching timer record dictionaries.
    """
    _ensure_db_once()
    with closing(_get_db_connection()) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if entity_id:
            cur.execute(
                """
                SELECT * FROM scheduled_timers
                WHERE status IN ('running', 'paused') AND entity_id = ?
                ORDER BY created_at DESC
                """,
                (entity_id.strip().lower(),),
            )
        else:
            cur.execute(
                """
                SELECT * FROM scheduled_timers
                WHERE status IN ('running', 'paused')
                ORDER BY created_at DESC
                """
            )
        return [dict(row) for row in cur.fetchall()]


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _db_update_timer_status(timer_id: str, status: str, remaining: float = 0.0) -> bool:
    """Update status and remaining seconds for a timer.

    Args:
        timer_id: Identifier of the timer.
        status: Target status string.
        remaining: Updated remaining duration in seconds.

    Returns:
        True if updated successfully.
    """
    _ensure_db_once()
    now_iso = dt_util.now().isoformat()
    with closing(_get_db_connection()) as conn:
        conn.execute(
            """
            UPDATE scheduled_timers
            SET status = ?, remaining = ?, last_updated = ?
            WHERE id = ?
            """,
            (status, max(remaining, 0.0), now_iso, timer_id),
        )
        conn.commit()
    return True


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _db_prune_old_timers(retention_seconds: int = 604800) -> int:
    """Prune inactive timers older than the retention threshold (default 7 days).

    Args:
        retention_seconds: Retention limit in seconds.

    Returns:
        Count of deleted timer records.
    """
    _ensure_db_once()
    cutoff = time.time() - retention_seconds
    with closing(_get_db_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM scheduled_timers
            WHERE status NOT IN ('running', 'paused')
              AND end_timestamp < ?
            """,
            (cutoff,),
        )
        deleted = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
    return max(deleted, 0)


def _normalize_text(val: Any, casefold: bool = True) -> str:
    """Normalize raw string input by stripping whitespace and optionally casefolding.

    Args:
        val: Raw input value.
        casefold: Whether to casefold string for caseless comparison (default True).

    Returns:
        Stripped string, optionally casefolded, or empty string if None.
    """
    if val is None:
        return ""
    text = str(val).strip()
    return text.casefold() if casefold else text


def _canonical_attr(token: str) -> str:
    """Resolve an attribute property alias to its canonical full name.

    Args:
        token: Attribute property name or token.

    Returns:
        Canonical attribute name string.
    """
    return _ATTRIBUTE_SYNONYMS.get(token, token)


def _normalize_entity_id(val: Any) -> str:
    """Normalize entity ID by stripping whitespace and converting to lowercase.

    Args:
        val: Raw entity identifier.

    Returns:
        Normalized lowercase entity ID string.
    """
    return _normalize_text(val)


def _normalize_slug(val: Any) -> str:
    """Normalize a keyword or identifier into a canonical lowercase underscored slug using HA slugify.

    Args:
        val: Raw keyword or property string.

    Returns:
        Cleaned lowercase slug with multiple separators collapsed, or empty string.
    """
    text = _normalize_text(val)
    if not text:
        return ""
    slug = slugify(text)
    return "" if slug == "unknown" and text != "unknown" else slug


def _split_slug_tokens(val: Any) -> set[str]:
    """Split a delimited string into a set of normalized slug tokens.

    Args:
        val: Raw string or value with comma or semicolon delimiters.

    Returns:
        Set of non-empty normalized slug tokens.
    """
    if not val:
        return set()
    text = str(val).replace(";", ",")
    return {slug for item in text.split(",") if (slug := _normalize_slug(item))}


def _clean_numeric_string(raw_val: str) -> str:
    """Strip common metric units and symbols from a numeric string.

    Args:
        raw_val: Target string potentially containing units (e.g., '22°C', '80%').

    Returns:
        Cleaned numeric string representation.
    """
    cleaned = _normalize_text(raw_val)
    for unit in _NUMERIC_UNITS:
        if cleaned.endswith(unit):
            candidate = cleaned.removesuffix(unit).strip()
            if candidate and candidate.replace(".", "", 1).replace("-", "", 1).replace("+", "", 1).isdigit():
                return candidate
    return cleaned


def _is_nobody_term(val: str) -> bool:
    """Check if a string represents an empty or unoccupied state.

    Args:
        val: Normalized input string to check.

    Returns:
        True if the term corresponds to nobody/empty, False otherwise.
    """
    return _normalize_slug(val) in _NOBODY_TERMS


def _generate_timer_id(entity_norm: str, custom_id: str | None = None) -> str:
    """Generate a unique timer identifier or sanitize a custom identifier.

    Args:
        entity_norm: Normalized target entity ID.
        custom_id: Optional custom identifier.

    Returns:
        Sanitized unique timer ID string.
    """
    if cid := _normalize_text(custom_id):
        return cid
    slug = _normalize_slug(entity_norm) if entity_norm else "timer"
    ts = dt_util.now().strftime("%Y%m%d%H%M%S%f")
    return f"{slug}__{ts}"


def _calculate_remaining_seconds(item: dict[str, Any], now_ts: float | None = None) -> int:
    """Calculate remaining seconds for a timer record based on its current status.

    Args:
        item: Timer dictionary from the database.
        now_ts: Current epoch timestamp (defaults to time.time()).

    Returns:
        Integer remaining seconds (minimum 0).
    """
    st = item.get("status", "")
    ts = now_ts if now_ts is not None else time.time()
    if st == "running":
        end_ts = item.get("end_timestamp", 0.0)
        return max(round(end_ts - ts), 0)
    rem = item.get("remaining", 0.0)
    return max(round(rem), 0)


def _format_timestamp(ts: float) -> str:
    """Format epoch timestamp into a timezone-aware ISO string.

    Args:
        ts: Epoch timestamp in seconds.

    Returns:
        ISO formatted string or empty string if timestamp <= 0.
    """
    return dt_util.as_local(dt_util.utc_from_timestamp(ts)).isoformat() if ts > 0 else ""


def _parse_condition_spec(cond_raw: Any) -> dict[str, Any] | None:
    """Parse raw condition specification from DB or input into a dictionary.

    Args:
        cond_raw: Raw condition spec (dict, JSON string, or None).

    Returns:
        Parsed dictionary or None if empty or invalid.
    """
    if not cond_raw:
        return None
    if isinstance(cond_raw, dict):
        return cond_raw
    if isinstance(cond_raw, str):
        trimmed = cond_raw.strip()
        if not trimmed or trimmed in ("null", "{}"):
            return None
        with suppress(Exception):
            parsed = orjson.loads(trimmed)
            if isinstance(parsed, dict):
                return parsed
    return None


def _is_effective_condition(cond_spec: dict[str, Any] | None) -> bool:
    """Check if condition specification contains an effective condition.

    Args:
        cond_spec: Parsed condition specification dictionary.

    Returns:
        True if an active condition exists, False otherwise.
    """
    if not cond_spec or not isinstance(cond_spec, dict):
        return False
    cond_type = _normalize_slug(cond_spec.get("type", ""))
    if cond_type == "none":
        return False
    if cond_type:
        return True
    return bool(cond_spec.get("entity_id") or cond_spec.get("value"))


def _describe_condition(cond_spec: dict[str, Any]) -> str:
    """Generate a human-readable summary of a condition specification.

    Args:
        cond_spec: Structured dictionary specifying condition rules.

    Returns:
        Human-readable summary string (e.g. 'zone.home == nobody').
    """
    cond_type = _normalize_slug(cond_spec.get("type", ""))
    entity_id = _normalize_text(cond_spec.get("entity_id", ""), casefold=False)
    prop = _normalize_text(cond_spec.get("property", ""), casefold=False)
    op = _normalize_text(cond_spec.get("operator", "=="), casefold=False) or "=="
    val = _normalize_text(cond_spec.get("value", ""), casefold=False)

    if cond_type == "day_of_week":
        return f"day_of_week == {val}" if val else "day_of_week"

    target = ".".join([p for p in (entity_id, prop) if p])

    if target and val:
        return f"{target} {op} {val}"
    if target:
        return target
    return f"{cond_type} {op} {val}" if val else cond_type or "active_condition"


def _parse_actions(actions_raw: Any) -> list[dict[str, Any]]:
    """Parse raw actions from DB or input into a list of action dictionaries.

    Args:
        actions_raw: Raw actions (list, JSON string, or None).

    Returns:
        List of action dictionaries.
    """
    if not actions_raw:
        return []
    if isinstance(actions_raw, list):
        return actions_raw
    if isinstance(actions_raw, str):
        trimmed = actions_raw.strip()
        if not trimmed or trimmed in ("null", "[]"):
            return []
        with suppress(Exception):
            parsed = orjson.loads(trimmed)
            if isinstance(parsed, list):
                return parsed
    return []


def _format_timer_record(item: dict[str, Any], now_ts: float | None = None) -> dict[str, Any]:
    """Format a database timer record into an API and sensor-friendly dictionary.

    Args:
        item: Raw timer dictionary from the database.
        now_ts: Current epoch timestamp.

    Returns:
        Formatted dictionary containing normalized timer information.
    """
    ts = now_ts if now_ts is not None else time.time()
    st = item.get("status", "")
    end_ts = item.get("end_timestamp", 0.0)
    remaining = _calculate_remaining_seconds(item, ts)
    end_iso = _format_timestamp(end_ts) if (end_ts > 0 and st == "running") else ""

    cond_spec = _parse_condition_spec(item.get("condition_spec"))
    has_cond = _is_effective_condition(cond_spec)
    cond_summary = _describe_condition(cond_spec) if (has_cond and cond_spec) else None
    actions = _parse_actions(item.get("actions"))

    return {
        "id": item.get("id", ""),
        "entity_id": item.get("entity_id", ""),
        "status": st,
        "created_at": item.get("created_at", ""),
        "end": end_iso,
        "remaining": remaining,
        "duration_seconds": item.get("duration_seconds", 0.0),
        "has_condition": has_cond,
        "condition": cond_spec if has_cond else None,
        "condition_summary": cond_summary,
        "actions": actions,
    }


async def _cancel_active_task(timer_id: str) -> bool:
    """Cancel and remove an active in-memory timer task if present.

    Args:
        timer_id: Unique timer identifier.

    Returns:
        True if an active task was found and cancelled, False otherwise.
    """
    async with _ACTIVE_TASKS_LOCK:
        task_obj = _ACTIVE_TASKS.pop(timer_id, None)

    if task_obj is not None:
        with suppress(Exception):
            task.cancel(task_obj)  # noqa: F821  # ty:ignore[unresolved-reference]
        return True

    with suppress(Exception):
        if tid := task.name2id(f"devices_scheduler_{timer_id}"):  # noqa: F821  # ty:ignore[unresolved-reference]
            task.cancel(tid)  # noqa: F821  # ty:ignore[unresolved-reference]
            return True

    return False


async def _resolve_target_timer(
    timer_id: str | None,
    target_entity: str | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve target timer identifier and record by ID or entity.

    Args:
        timer_id: Optional explicit timer identifier.
        target_entity: Optional target entity identifier to query active timers.

    Returns:
        Tuple of (resolved_timer_id, timer_record) or (None, None) if not found.
    """
    tid = _normalize_text(timer_id)
    entity_norm = _normalize_entity_id(target_entity)

    if not tid and entity_norm:
        actives = await asyncio.to_thread(_db_get_active_timers, entity_norm)
        return (actives[0]["id"], actives[0]) if actives else (None, None)

    if not tid:
        return None, None

    timer = await asyncio.to_thread(_db_get_timer, tid)
    return tid, timer


async def _update_scheduler_sensor() -> None:
    """Update Home Assistant sensor.devices_scheduler with active timers and metrics."""
    try:
        active_timers = await asyncio.to_thread(_db_get_active_timers, None)
        now_ts = time.time()
        formatted = [_format_timer_record(t, now_ts) for t in active_timers]

        running = [t for t in formatted if t["status"] == "running"]
        paused = [t for t in formatted if t["status"] == "paused"]

        running_sorted = sorted(running, key=lambda x: x["remaining"])
        next_expiring = running_sorted[0] if running_sorted else None

        total_count = len(formatted)
        running_count = len(running)
        paused_count = len(paused)
        active_entities = sorted({t["entity_id"] for t in formatted if t.get("entity_id")})
        active_conditions = [
            t["condition_summary"] for t in formatted if t.get("has_condition") and t.get("condition_summary")
        ]

        attrs = {
            "friendly_name": SCHEDULER_SENSOR_FRIENDLY_NAME,
            "icon": "mdi:timer-outline",
            "unit_of_measurement": SCHEDULER_SENSOR_UNIT_OF_MEASUREMENT,
            "state_class": "measurement",
            "total_active_count": total_count,
            "running_count": running_count,
            "paused_count": paused_count,
            "active_entities": active_entities,
            "active_conditions": active_conditions,
            "all_timers": formatted,
            "running_timers": running,
            "paused_timers": paused,
            "next_expiring": next_expiring,
            "last_updated": dt_util.now().isoformat(),
        }

        state.set(  # noqa: F821  # ty:ignore[unresolved-reference]
            SCHEDULER_SENSOR_ENTITY,
            total_count,
            attrs,
        )
    except Exception as error:
        log.error(f"{__name__}: Failed to update scheduler sensor: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]


def _evaluate_numeric_comparison(current_num: float, op: str, target_num: float) -> bool:
    """Evaluate numeric operators between two floats.

    Args:
        current_num: The observed live sensor value.
        op: Comparison operator ('>', '<', '>=', '<=', '!=', '==').
        target_num: The threshold value.

    Returns:
        True if comparison passes, False otherwise.
    """
    if op == ">":
        return current_num > target_num
    if op == "<":
        return current_num < target_num
    if op == ">=":
        return current_num >= target_num
    if op == "<=":
        return current_num <= target_num
    if op in {"!=", "is_not"}:
        return round(current_num, 2) != round(target_num, 2)
    return round(current_num, 2) == round(target_num, 2)


def _check_weather_condition(op: str, target_val: str, prop: str = "", entity_id: str = "") -> bool:
    """Evaluate current weather conditions dynamically against all available weather entities.

    Args:
        op: Comparison operator.
        target_val: Target condition value (e.g. 'clear', 'rain', 'sunny', 'cloudy', '25').
        prop: Optional specific property/attribute to inspect.
        entity_id: Optional specific weather entity ID to inspect first.

    Returns:
        True if any weather entity satisfies the condition, False otherwise.
    """
    clean_val = _normalize_slug(target_val)
    if (
        entity_id
        and entity_id.startswith("weather.")
        and (we := hass.states.get(entity_id))  # noqa: F821  # ty:ignore[unresolved-reference]
        and _compare_values(_extract_entity_property(we, prop) if prop else we.state, op, clean_val)
    ):
        return True

    weather_entities = [
        s
        for s in hass.states.all()  # noqa: F821  # ty:ignore[unresolved-reference]
        if s.entity_id.startswith("weather.")
    ]

    for we in weather_entities:
        obs = _extract_entity_property(we, prop) if prop else we.state
        if _compare_values(obs, op, clean_val):
            return True

    # If checking for rain and weather states didn't trigger, also inspect moisture sensors
    if not prop and "rain" in clean_val:
        moisture_sensors = [
            s
            for s in hass.states.all()  # noqa: F821  # ty:ignore[unresolved-reference]
            if s.entity_id.startswith("binary_sensor.") and s.attributes.get("device_class") == "moisture"
        ]
        if any(s.state == "on" for s in moisture_sensors):
            return op not in {"!=", "is_not"}

    return False


def _check_zone_occupancy(require_nobody: bool, zone_name: str = "home") -> bool:
    """Check occupancy for a specific zone or home based on zone and person entities.

    Args:
        require_nobody: If True, checks that nobody is in the zone; if False, checks that someone is in the zone.
        zone_name: Target zone entity ID or friendly name (defaults to 'home').

    Returns:
        True if the occupancy requirement is met, False otherwise.
    """
    clean_target = _normalize_slug(zone_name or "home").removeprefix("zone_").removeprefix(_ZONE_PREFIX)
    target_zone = "home" if clean_target in {"", "house"} else clean_target

    zone_eid = f"{_ZONE_PREFIX}{target_zone}"
    if z := hass.states.get(zone_eid):  # noqa: F821  # ty:ignore[unresolved-reference]
        with suppress(ValueError, TypeError):
            is_nobody = int(z.state) == 0
            return is_nobody if require_nobody else not is_nobody

    zone_entities = [
        s
        for s in hass.states.all()  # noqa: F821  # ty:ignore[unresolved-reference]
        if s.entity_id.startswith(_ZONE_PREFIX)
    ]
    for z in zone_entities:
        z_id = z.entity_id.replace(_ZONE_PREFIX, "").lower()
        z_name = str(z.attributes.get("friendly_name", "")).lower()
        if target_zone in {z_id, z_name}:
            with suppress(ValueError, TypeError):
                is_nobody = int(z.state) == 0
                return is_nobody if require_nobody else not is_nobody

    if persons := [
        s
        for s in hass.states.all()  # noqa: F821  # ty:ignore[unresolved-reference]
        if s.entity_id.startswith("person.")
    ]:
        matching = [
            p
            for p in persons
            if (target_zone == "home" and p.state.lower() == "home")
            or (_normalize_slug(p.state) == target_zone)
            or (p.state.lower() == target_zone)
        ]
        is_nobody = not matching
        return is_nobody if require_nobody else not is_nobody

    return require_nobody


def _check_day_of_week(target_val: str) -> bool:
    """Evaluate day of week conditions.

    Args:
        target_val: String target specifying day criteria (e.g. 'weekday', 'weekend', 'monday').

    Returns:
        True if current day matches the target requirement.
    """
    val = _normalize_slug(target_val)
    weekday = dt_util.now().weekday()
    if val in {"weekend", "weekends"}:
        return weekday in {5, 6}
    if val in {"weekday", "weekdays"}:
        return weekday < 5
    day_map = {
        "monday": 0,
        "mon": 0,
        "tuesday": 1,
        "tue": 1,
        "wednesday": 2,
        "wed": 2,
        "thursday": 3,
        "thu": 3,
        "friday": 4,
        "fri": 4,
        "saturday": 5,
        "sat": 5,
        "sunday": 6,
        "sun": 6,
    }
    return weekday == day_map[val] if val in day_map else False


def _matches_sun_daylight(val: str, elevation: float, st: str) -> bool | None:
    """Evaluate day and night solar terms.

    Args:
        val: Normalized target condition term.
        elevation: Live solar elevation in degrees.
        st: Live main state of sun.sun.

    Returns:
        Boolean outcome if val is a daylight term, None otherwise.
    """
    if val in {"day", "daytime", "above_horizon", "light"}:
        return elevation > 0 or st == "above_horizon"
    if val in {"night", "below_horizon", "dark"}:
        return elevation <= 0 or st == "below_horizon"
    return None


def _matches_sun_twilight(val: str, elevation: float, rising: bool) -> bool | None:
    """Evaluate sunrise, sunset, dawn, and dusk solar terms.

    Args:
        val: Normalized target condition term.
        elevation: Live solar elevation in degrees.
        rising: True if sun is currently rising.

    Returns:
        Boolean outcome if val is a twilight term, None otherwise.
    """
    if val == "sunrise":
        return -4.0 <= elevation <= 4.0 and rising
    if val == "sunset":
        return -4.0 <= elevation <= 4.0 and not rising
    if val == "after_sunset":
        return (-4.0 <= elevation <= 4.0 and not rising) or elevation < 0
    if val == "dawn":
        return -18.0 <= elevation <= 0.0 and rising
    return (-18.0 <= elevation <= 0.0 and not rising) if val == "dusk" else None


def _matches_sun_time(val: str, elevation: float) -> bool | None:
    """Evaluate noon and midnight solar terms.

    Args:
        val: Normalized target condition term.
        elevation: Live solar elevation in degrees.

    Returns:
        Boolean outcome if val is a noon/midnight term, None otherwise.
    """
    hour = dt_util.now().hour
    if val in {"noon", "midday"}:
        return hour == 12 or (elevation > 0 and 11 <= hour <= 13)
    return (hour in {23, 0}) if val == "midnight" else None


def _matches_sun_state(observed_sun: Any, target_val: str) -> bool:
    """Check if live sun state satisfies natural solar condition terms.

    Args:
        observed_sun: Home Assistant sun.sun state object.
        target_val: Target solar term (e.g. 'night', 'day', 'sunrise', 'sunset', 'midnight', 'noon', 'dawn', 'dusk').

    Returns:
        True if the solar condition is satisfied, False otherwise.
    """
    if not observed_sun or observed_sun.state in {"unknown", "unavailable"}:
        return False

    val = _normalize_slug(target_val)
    st = str(observed_sun.state).lower()
    attrs = getattr(observed_sun, "attributes", {}) or {}

    elevation = float(attrs.get("elevation", 0.0))
    rising = bool(attrs.get("rising", False))

    if (day_res := _matches_sun_daylight(val, elevation, st)) is not None:
        return day_res
    if (twi_res := _matches_sun_twilight(val, elevation, rising)) is not None:
        return twi_res
    if (time_res := _matches_sun_time(val, elevation)) is not None:
        return time_res

    return st == val


def _evaluate_sun_condition(cond_type: str, op: str, val: str, prop: str) -> bool:
    """Evaluate solar elevation, azimuth, and sun conditions (day, night, sunrise, sunset, midnight, noon, dawn, dusk).

    Args:
        cond_type: Condition type ('sun', 'after_sunset', 'night', 'during_daytime', 'day').
        op: Comparison operator.
        val: Target value string.
        prop: Optional attribute name.

    Returns:
        True if the sun condition requirement is met.
    """
    sun = hass.states.get(_SUN_ENTITY)  # noqa: F821  # ty:ignore[unresolved-reference]
    if not sun:
        return False
    if prop:
        obs = _extract_entity_property(sun, prop)
        return _compare_values(obs, op, val)

    target_term = val or cond_type
    return _matches_sun_state(sun, target_term)


def _evaluate_ambient_condition(
    cond_type: str,
    op: str,
    val: str,
    prop: str,
    entity_id: str = "",
) -> bool | None:
    """Evaluate ambient or contextual conditions such as weather, occupancy, and sun.

    Args:
        cond_type: Canonical string condition type.
        op: Comparison operator.
        val: Target value string.
        prop: Property or attribute name.
        entity_id: Optional entity ID for targeted ambient evaluation.

    Returns:
        Boolean outcome if cond_type is recognized as ambient, None otherwise.
    """
    if cond_type in {"weather", "outside"}:
        return _check_weather_condition(op, val, prop=prop, entity_id=entity_id)
    if cond_type in {"outside_is_raining", "outside_is_not_raining"}:
        is_raining = _check_weather_condition("==", "rain", entity_id=entity_id)
        return is_raining if cond_type == "outside_is_raining" else not is_raining
    if cond_type in {"occupancy", "nobody_home", "someone_home"}:
        is_nobody = (cond_type == "nobody_home") or _is_nobody_term(val)
        target_zone = entity_id or prop or "home"
        return _check_zone_occupancy(require_nobody=is_nobody, zone_name=target_zone)
    if cond_type in {"sun", "after_sunset", "night", "during_daytime", "day"}:
        return _evaluate_sun_condition(cond_type, op, val, prop)
    if cond_type == "day_of_week":
        return _check_day_of_week(val)
    if cond_type in {"is_weekday", "is_weekend"}:
        return (dt_util.now().weekday() < 5) if cond_type == "is_weekday" else (dt_util.now().weekday() in {5, 6})
    return None


def _token_jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Calculate token Jaccard similarity coefficient between two token sets.

    Args:
        set_a: First set of string tokens.
        set_b: Second set of string tokens.

    Returns:
        Float similarity score in [0.0, 1.0].
    """
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _ngram_jaccard(str_a: str, str_b: str, n: int = 2) -> float:
    """Calculate character n-gram Jaccard similarity between two strings.

    Args:
        str_a: First string to compare.
        str_b: Second string to compare.
        n: N-gram length (default 2 for bigrams).

    Returns:
        Float similarity score in [0.0, 1.0].
    """
    if not str_a or not str_b:
        return 0.0
    if str_a == str_b:
        return 1.0
    if len(str_a) < n or len(str_b) < n:
        return 0.0

    ngrams_a = {str_a[i : i + n] for i in range(len(str_a) - n + 1)}
    ngrams_b = {str_b[i : i + n] for i in range(len(str_b) - n + 1)}

    intersection = len(ngrams_a & ngrams_b)
    union = len(ngrams_a | ngrams_b)
    return intersection / union if union > 0 else 0.0


def _fuzzy_ratio(str_a: str, str_b: str) -> float:
    """Calculate Ratcliff-Obershelp fuzzy string similarity ratio using difflib.

    Args:
        str_a: First string to compare.
        str_b: Second string to compare.

    Returns:
        Float similarity ratio in [0.0, 1.0].
    """
    if not str_a or not str_b:
        return 0.0
    if str_a == str_b:
        return 1.0
    return difflib.SequenceMatcher(None, str_a, str_b).ratio()


def _score_attribute_key(k_lower: str, prop_norm: str, value: Any = None) -> int:
    """Score attribute key similarity against requested property intelligently using Jaccard and fuzzy similarity.

    Args:
        k_lower: Lowercase attribute key candidate.
        prop_norm: Normalized requested property name.
        value: Optional attribute value to penalize non-scalar capability lists.

    Returns:
        Integer score representing match quality (-1 if no match).
    """
    canon_prop = _canonical_attr(prop_norm)
    canon_k = _canonical_attr(k_lower)

    if canon_prop in {"temperature", "humidity"}:
        if k_lower == f"current_{canon_prop}":
            return 100
        if canon_k == canon_prop:
            return 90
    elif canon_k == canon_prop:
        return 100

    k_base = k_lower.removeprefix("current_")
    if k_lower.startswith("current_") and _canonical_attr(k_base) == canon_prop:
        return 95

    k_tokens = {_canonical_attr(t) for t in k_lower.split("_") if t}
    prop_tokens = {canon_prop}

    has_token_overlap = bool(prop_tokens & k_tokens)
    token_sim = _token_jaccard(prop_tokens, k_tokens)
    overlap = len(prop_tokens & k_tokens) / len(prop_tokens) if prop_tokens else 0.0
    fuzzy_sim = max(_fuzzy_ratio(prop_norm, k_lower), _fuzzy_ratio(canon_prop, k_lower))
    ngram_sim = max(_ngram_jaccard(prop_norm, k_lower), _ngram_jaccard(canon_prop, k_lower))

    # Reject early if no token match and low fuzzy/ngram similarity
    if not has_token_overlap and fuzzy_sim < 0.65 and ngram_sim < 0.5:
        return -1

    # Weighted combination of token Jaccard, token overlap, ngram Jaccard, and fuzzy matching
    similarity = (0.35 * token_sim) + (0.35 * overlap) + (0.15 * ngram_sim) + (0.15 * fuzzy_sim)
    score = round(similarity * 80)

    if k_lower.startswith("current_"):
        score += 10
    if _canonical_attr(k_lower.split("_")[-1]) == canon_prop:
        score += 5

    # Penalize non-scalar capability lists, steps, and limits
    if k_lower.endswith(("_list", "_modes", "_options")) or isinstance(value, (list, set, tuple)):
        score -= 30
    if any(k_lower.startswith(p) for p in ("min_", "max_", "target_")):
        score -= 10
    if any(k_lower.endswith(s) for s in ("_step", "_factor", "_unit")):
        score -= 15

    return max(score, 0)


def _extract_entity_property(state_obj: Any, prop: str) -> Any:
    """Extract an attribute or main state from a Home Assistant state object dynamically.

    Args:
        state_obj: Home Assistant state object.
        prop: Requested property name or empty string.

    Returns:
        The extracted attribute value or main state.
    """
    if not prop or state_obj is None:
        return state_obj.state if state_obj else None

    prop_norm = _normalize_slug(prop)
    if not prop_norm:
        return state_obj.state

    attrs = getattr(state_obj, "attributes", {}) or {}
    best_key: str | None = None
    best_score = -1

    for k, v in attrs.items():
        score = _score_attribute_key(k.lower(), prop_norm, value=v)
        if score > best_score:
            best_score = score
            best_key = k

    if best_key is not None and best_score > 0:
        val = attrs[best_key]
        return (
            round((float(val) / 255.0) * 100)
            if best_key.lower() == "brightness" and isinstance(val, (int, float))
            else val
        )

    return state_obj.state


def _matches_binary_sensor(observed_str: str, target_str: str) -> bool:
    """Check binary sensor equivalence against natural language states across all HA device classes.

    Args:
        observed_str: Observed state ('on' or 'off').
        target_str: Target condition value.

    Returns:
        True if the state matches natural equivalent terms.
    """
    if observed_str == "on":
        return target_str in {
            "on",
            "true",
            "yes",
            "1",
            "open",
            "opened",
            "opening",
            "motion",
            "detected",
            "active",
            "wet",
            "moisture",
            "occupied",
            "occupancy",
            "connected",
            "connecting",
            "online",
            "unlocked",
            "unlocking",
            "running",
            "charging",
            "plugged",
            "plugged_in",
            "moving",
            "hot",
            "cold",
            "low",
            "problem",
            "unsafe",
            "tampered",
        }
    if observed_str == "off":
        return target_str in {
            "off",
            "false",
            "no",
            "0",
            "closed",
            "closing",
            "clear",
            "inactive",
            "dry",
            "empty",
            "vacant",
            "disconnected",
            "offline",
            "unreachable",
            "locked",
            "locking",
            "stopped",
            "idle",
            "unplugged",
            "discharging",
            "not_charging",
            "normal",
            "ok",
            "safe",
            "secure",
        }
    return False


def _matches_string_state(observed_str: str, target_str: str, is_binary: bool = False) -> bool:
    """Check if an observed state string matches the target specification.

    Args:
        observed_str: Live entity state string.
        target_str: Target condition value string.
        is_binary: Whether the entity is a binary sensor.

    Returns:
        True if the observed state matches the target specification.
    """
    if observed_str == target_str:
        return True
    if is_binary and _matches_binary_sensor(observed_str, target_str):
        return True

    # Solar terms check if observed state is above/below horizon
    if observed_str in {"above_horizon", "below_horizon"}:
        sun = hass.states.get(_SUN_ENTITY)  # noqa: F821  # ty:ignore[unresolved-reference]
        if sun and _matches_sun_state(sun, target_str):
            return True

    obs_slug = _normalize_slug(observed_str)
    tgt_slug = _normalize_slug(target_str)
    if obs_slug == tgt_slug:
        return True

    # Guard against antonym and negation collisions (e.g. locked vs unlocked, plugged vs unplugged)
    neg_prefixes = ("un", "dis", "non", "not_")
    obs_is_neg = obs_slug.startswith(neg_prefixes)
    tgt_is_neg = tgt_slug.startswith(neg_prefixes)
    if obs_is_neg != tgt_is_neg:
        return False

    # Guard discrete short states from substring matches (e.g. off vs offline, on vs online)
    discrete_exact = {"on", "off", "open", "closed", "locked", "unlocked", "heat", "cool", "auto"}
    if obs_slug in discrete_exact or tgt_slug in discrete_exact:
        stem_groups = [
            {"lock", "locked"},
            {"unlock", "unlocked"},
            {"open", "opened", "opening"},
            {"close", "closed", "closing"},
            {"heat", "heating"},
            {"cool", "cooling"},
        ]
        return any(obs_slug in group and tgt_slug in group for group in stem_groups)

    if tgt_slug and (tgt_slug in obs_slug or obs_slug in tgt_slug):
        return True

    if tgt_slug in {"clear", "sunny"} and obs_slug in {"clear", "sunny", "clear_night", "clear-night"}:
        return True

    return tgt_slug == "rain" and "pour" in obs_slug


def _matches_containment(observed_str: str, target_str: str, op: str) -> bool:
    """Evaluate containment or set membership between observed and target string values.

    Args:
        observed_str: Live entity state string.
        target_str: Target specification or delimited values string.
        op: Comparison operator ('in', 'contains', 'not_in', 'not in').

    Returns:
        True if containment criteria are met, False otherwise.
    """
    obs_slug = _normalize_slug(observed_str)
    tgt_slug = _normalize_slug(target_str)
    if not obs_slug or not tgt_slug:
        return op in {"not_in", "not in"}
    tgt_tokens = _split_slug_tokens(target_str)
    obs_tokens = _split_slug_tokens(observed_str)
    is_in = obs_slug in tgt_tokens or bool(obs_tokens & tgt_tokens) or tgt_slug in obs_slug or tgt_slug == obs_slug
    return is_in if op in {"in", "contains"} else not is_in


def _compare_values(observed_val: Any, op: str, clean_val: str, is_binary: bool = False) -> bool:
    """Evaluate comparison between live observed value and target string.

    Args:
        observed_val: Observed live entity state or attribute.
        op: Comparison operator.
        clean_val: Clean target value string.
        is_binary: Whether the entity is a binary sensor.

    Returns:
        True if comparison passes, False otherwise.
    """
    # 1. Numeric comparison if both sides are numeric
    if observed_val is not None:
        with suppress(ValueError, TypeError):
            current_num = float(observed_val)
            clean_num_str = _clean_numeric_string(clean_val)
            target_num = float(clean_num_str)
            return _evaluate_numeric_comparison(current_num, op, target_num)

    # 2. String comparison
    observed_str = _normalize_entity_id(observed_val)
    target_str = _normalize_text(clean_val)

    if op in {"!=", "is_not"}:
        return not _matches_string_state(observed_str, target_str, is_binary=is_binary)
    if op in {"in", "contains", "not_in", "not in"}:
        return _matches_containment(observed_str, target_str, op)
    return _matches_string_state(observed_str, target_str, is_binary=is_binary)


def _evaluate_condition(condition_spec: dict[str, Any] | None) -> bool:
    """Evaluate condition specification against live Home Assistant state.

    Args:
        condition_spec: Structured dictionary specifying the condition to evaluate.

    Returns:
        True if the condition is satisfied or empty, False otherwise.
    """
    if not condition_spec or not isinstance(condition_spec, dict):
        return True

    cond_type = _normalize_slug(condition_spec.get("type", ""))
    if cond_type in {"", "none"}:
        return True

    prop = _normalize_slug(condition_spec.get("property", ""))
    raw_val = _normalize_text(condition_spec.get("value", ""))
    op = _normalize_text(condition_spec.get("operator", "==")) or "=="
    entity_id = _normalize_entity_id(condition_spec.get("entity_id", ""))

    # 1. Ambient / Contextual evaluations
    ambient_result = _evaluate_ambient_condition(cond_type, op, raw_val, prop, entity_id=entity_id)
    if ambient_result is not None:
        return ambient_result

    # 2. Entity / Property Evaluation
    if not entity_id:
        return _check_weather_condition(op, raw_val, prop=prop) if raw_val else True

    if entity_id in {"outside", "weather"}:
        return _check_weather_condition(op, raw_val, prop=prop, entity_id=entity_id)

    if entity_id in {"sun", _SUN_ENTITY}:
        return _evaluate_sun_condition("sun", op, raw_val, prop)

    if entity_id.startswith(_ZONE_PREFIX) or entity_id in {"home", "house"}:
        is_nobody = _is_nobody_term(raw_val)
        return _check_zone_occupancy(require_nobody=is_nobody, zone_name=entity_id)

    state_obj = hass.states.get(entity_id)  # noqa: F821  # ty:ignore[unresolved-reference]
    if not state_obj or state_obj.state in {"unknown", "unavailable"}:
        return False

    is_binary = entity_id.startswith("binary_sensor.")
    observed_val = _extract_entity_property(state_obj, prop)
    return _compare_values(observed_val, op, raw_val, is_binary=is_binary)


async def _execute_actions(actions: list[dict[str, Any]]) -> None:
    """Dispatch action sequence via Home Assistant service calls.

    Args:
        actions: List of action dictionaries containing action, target, data.
    """
    for item in actions:
        if not isinstance(item, dict):
            continue
        service_call = item.get("action", "")
        if "." not in service_call:
            continue
        domain, service_name = service_call.split(".", 1)
        target = item.get("target") or {}
        data = item.get("data") or {}
        try:
            await hass.services.async_call(domain, service_name, data, target=target)  # noqa: F821  # ty:ignore[unresolved-reference]
        except Exception as error:
            log.error(f"{__name__}: Action execution failed for {service_call}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]


async def _run_timer_task(timer_id: str, end_timestamp: float) -> None:
    """Async countdown worker task for an active timer.

    Args:
        timer_id: Identifier of the running timer.
        end_timestamp: Target completion epoch timestamp.
    """
    try:
        task.unique(f"devices_scheduler_{timer_id}")  # noqa: F821  # ty:ignore[unresolved-reference]
        now_ts = time.time()
        remaining = end_timestamp - now_ts
        if remaining > 0:
            task.sleep(remaining)  # noqa: F821  # ty:ignore[unresolved-reference]

        timer = await asyncio.to_thread(_db_get_timer, timer_id)
        if not timer or timer.get("status") != "running":
            return

        cond_json = timer.get("condition_spec")
        condition_spec = _parse_condition_spec(cond_json)
        actions = _parse_actions(timer.get("actions"))

        if _evaluate_condition(condition_spec):
            await _execute_actions(actions)
            await asyncio.to_thread(_db_update_timer_status, timer_id, "completed", 0.0)
        else:
            await asyncio.to_thread(_db_update_timer_status, timer_id, "skipped_condition_unmet", 0.0)
        await _update_scheduler_sensor()

    except asyncio.CancelledError:
        raise
    except Exception as error:
        log.error(f"{__name__}: Timer {timer_id} encountered unexpected error: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
    finally:
        async with _ACTIVE_TASKS_LOCK:
            _ACTIVE_TASKS.pop(timer_id, None)


async def _register_active_task(timer_id: str, end_timestamp: float) -> None:
    """Create and register an in-memory background timer task.

    Args:
        timer_id: Unique timer identifier.
        end_timestamp: Target completion epoch timestamp.
    """
    task_obj = task.create(_run_timer_task, timer_id, end_timestamp)  # noqa: F821  # ty:ignore[unresolved-reference]
    async with _ACTIVE_TASKS_LOCK:
        _ACTIVE_TASKS[timer_id] = task_obj


async def _recover_single_timer(timer: dict[str, Any], now_ts: float) -> None:
    """Recover or execute a single in-flight timer during startup.

    Args:
        timer: Raw timer record dictionary.
        now_ts: Current epoch timestamp.
    """
    timer_id = timer["id"]
    if timer.get("status") != "running":
        return

    end_ts = float(timer.get("end_timestamp", 0.0))
    if end_ts > now_ts:
        await _register_active_task(timer_id, end_ts)
        return

    cond_json = timer.get("condition_spec")
    condition_spec = _parse_condition_spec(cond_json)
    actions = _parse_actions(timer.get("actions"))

    if _evaluate_condition(condition_spec):
        await _execute_actions(actions)
        await asyncio.to_thread(_db_update_timer_status, timer_id, "completed_offline", 0.0)
    else:
        await asyncio.to_thread(_db_update_timer_status, timer_id, "skipped_condition_unmet", 0.0)


@time_trigger("startup")  # noqa: F821  # ty:ignore[unresolved-reference]
async def initialize_scheduler() -> None:
    """Initialize SQLite database and recover in-flight timers on Home Assistant startup."""
    await asyncio.to_thread(_ensure_db_once, True)
    # Delay briefly to allow entities to establish initial states
    task.sleep(5)  # noqa: F821  # ty:ignore[unresolved-reference]

    now_ts = time.time()
    active_timers = await asyncio.to_thread(_db_get_active_timers, None)

    for timer in active_timers:
        try:
            await _recover_single_timer(timer, now_ts)
        except Exception as error:
            log.error(f"{__name__}: Failed to restore timer {timer.get('id')}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]

    await _update_scheduler_sensor()
    log.info(f"Pyscript {__name__} is ready. Restored {len(active_timers)} timer(s).")  # noqa: F821  # ty:ignore[unresolved-reference]


@time_trigger("cron(0 * * * *)")  # noqa: F821  # ty:ignore[unresolved-reference]
async def prune_old_schedules() -> None:
    """Hourly housekeeping job pruning stale inactive timers from database."""
    deleted = await asyncio.to_thread(_db_prune_old_timers, 604800)
    if deleted > 0:
        log.info(f"Pyscript {__name__}: Pruned {deleted} expired timer record(s).")  # noqa: F821  # ty:ignore[unresolved-reference]
        await _update_scheduler_sensor()


@time_trigger("period(now, 10s)")  # noqa: F821  # ty:ignore[unresolved-reference]
async def refresh_active_schedules_sensor() -> None:
    """Periodically refresh sensor.devices_scheduler every 10 seconds when a timer is active."""
    if not _ACTIVE_TASKS:
        return
    await _update_scheduler_sensor()


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def devices_schedules_start(
    target_entity: str,
    duration_seconds: float,
    actions: list[dict[str, Any]],
    condition_spec: dict[str, Any] | None = None,
    timer_id: str | None = None,
    dedupe_mode: str = "cancel_existing",
) -> dict[str, Any]:
    """
    yaml
    name: Devices Schedules Start
    description: Start a scheduled timer with on-completion actions and conditional evaluation.
    fields:
      target_entity:
        name: Target Entity
        description: Home Assistant entity ID controlled by the timer.
        required: true
        selector:
          text:
      duration_seconds:
        name: Duration Seconds
        description: Seconds to wait before executing actions.
        required: true
        selector:
          number:
            min: 1
            max: 604800
            mode: box
      actions:
        name: Actions
        description: List of action dictionaries to execute upon expiration.
        required: true
        selector:
          object:
      condition_spec:
        name: Condition Specification
        description: Optional condition evaluated prior to action execution.
        selector:
          object:
      timer_id:
        name: Timer ID
        description: Optional custom timer identifier.
        selector:
          text:
      dedupe_mode:
        name: Deduplication Mode
        description: Policy when timer for entity exists (cancel_existing, reuse_existing, error, none).
        selector:
          select:
            options: [cancel_existing, reuse_existing, error, none]
    """
    entity_norm = _normalize_entity_id(target_entity)
    dur = duration_seconds
    if dur <= 0:
        return {"status": "error", "error": "Duration must be greater than zero."}

    # Handle deduplication
    existing = await asyncio.to_thread(_db_get_active_timers, entity_norm)
    if existing and dedupe_mode == "reuse_existing":
        return {
            "status": "reuse_existing",
            "timer_id": existing[0]["id"],
            "entity": entity_norm,
        }
    if existing and dedupe_mode == "error":
        return {
            "status": "error",
            "error": f"Timer already active for {entity_norm}",
        }
    if existing and dedupe_mode == "cancel_existing":
        for old in existing:
            old_id = old["id"]
            await _cancel_active_task(old_id)
            await asyncio.to_thread(_db_update_timer_status, old_id, "canceled", 0.0)

    # Generate timer ID
    tid = _generate_timer_id(entity_norm, timer_id)

    now_ts = time.time()
    end_ts = now_ts + dur
    created_iso = dt_util.now().isoformat()
    cond_json = orjson.dumps(condition_spec).decode("utf-8") if condition_spec else ""
    actions_json = orjson.dumps(actions).decode("utf-8")

    await asyncio.to_thread(
        _db_save_timer,
        tid,
        entity_norm,
        "running",
        created_iso,
        end_ts,
        dur,
        dur,
        cond_json,
        actions_json,
    )

    await _register_active_task(tid, end_ts)
    await _update_scheduler_sensor()

    return {
        "status": "scheduled",
        "timer_id": tid,
        "entity": entity_norm,
        "duration_seconds": dur,
        "end_time": _format_timestamp(end_ts),
    }


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def devices_schedules_cancel(
    timer_id: str | None = None,
    target_entity: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Devices Schedules Cancel
    description: Cancel an active timer by ID or target entity.
    fields:
      timer_id:
        name: Timer ID
        selector:
          text:
      target_entity:
        name: Target Entity
        selector:
          text:
    """
    tid, timer = await _resolve_target_timer(timer_id, target_entity)
    if not tid or not timer:
        return {"status": "not_found", "message": "No matching active timer found."}

    await _cancel_active_task(tid)
    remaining = _calculate_remaining_seconds(timer) if timer.get("status") == "running" else 0.0

    await asyncio.to_thread(_db_update_timer_status, tid, "canceled", remaining)
    await _update_scheduler_sensor()

    return {
        "status": "success",
        "timer_id": tid,
        "entity": timer.get("entity_id", _normalize_entity_id(target_entity)),
        "seconds_remaining": round(remaining),
    }


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def devices_schedules_cancel_all(
    target_entity: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Devices Schedules Cancel All
    description: Cancel all running timers, optionally filtered by target entity.
    fields:
      target_entity:
        name: Target Entity
        selector:
          text:
    """
    entity_norm = _normalize_entity_id(target_entity) if target_entity else None
    actives = await asyncio.to_thread(_db_get_active_timers, entity_norm)
    canceled_list: list[dict[str, Any]] = []

    for item in actives:
        tid = item["id"]
        await _cancel_active_task(tid)
        remaining = _calculate_remaining_seconds(item)
        await asyncio.to_thread(_db_update_timer_status, tid, "canceled", remaining)
        canceled_list.append(
            {
                "id": tid,
                "entity_id": item.get("entity_id", ""),
                "seconds_remaining": remaining,
            }
        )

    await _update_scheduler_sensor()
    return {
        "status": "success",
        "count": len(canceled_list),
        "canceled": canceled_list,
    }


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def devices_schedules_extend(
    extend_seconds: float,
    timer_id: str | None = None,
    target_entity: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Devices Schedules Extend
    description: Add seconds to an active or paused timer.
    fields:
      extend_seconds:
        name: Additional Seconds
        required: true
        selector:
          number:
            min: 1
            max: 604800
            mode: box
      timer_id:
        name: Timer ID
        selector:
          text:
      target_entity:
        name: Target Entity
        selector:
          text:
    """
    tid, timer = await _resolve_target_timer(timer_id, target_entity)
    if not tid or not timer:
        return {"status": "not_found", "message": "No matching active timer found."}

    status = timer.get("status")
    if status not in ("running", "paused"):
        return {"status": "invalid_state", "timer_id": tid}

    ext = extend_seconds
    now_ts = time.time()
    if status == "running":
        new_end = float(timer.get("end_timestamp", now_ts)) + ext
        new_remaining = max(new_end - now_ts, 0.0)
        await _cancel_active_task(tid)
        await _register_active_task(tid, new_end)
    else:
        new_remaining = float(timer.get("remaining", 0.0)) + ext
        new_end = now_ts + new_remaining

    await asyncio.to_thread(
        _db_save_timer,
        tid,
        timer.get("entity_id", ""),
        status,
        timer.get("created_at", ""),
        new_end,
        new_remaining,
        float(timer.get("duration_seconds", 0.0)) + ext,
        timer.get("condition_spec") or "",
        timer.get("actions", "[]"),
    )

    await _update_scheduler_sensor()
    return {
        "status": "success",
        "timer_id": tid,
        "extended_seconds": ext,
        "new_remaining_seconds": round(new_remaining),
        "new_end_time": _format_timestamp(new_end) if status == "running" else "",
    }


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def devices_schedules_pause(
    timer_id: str | None = None,
    target_entity: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Devices Schedules Pause
    description: Pause a running timer.
    fields:
      timer_id:
        name: Timer ID
        selector:
          text:
      target_entity:
        name: Target Entity
        selector:
          text:
    """
    tid, timer = await _resolve_target_timer(timer_id, target_entity)
    if not tid or not timer:
        return {"status": "not_found", "message": "No matching active timer found."}

    if timer.get("status") != "running":
        return {"status": "invalid_state", "timer_id": tid}

    await _cancel_active_task(tid)
    remaining = _calculate_remaining_seconds(timer)
    await asyncio.to_thread(_db_update_timer_status, tid, "paused", remaining)
    await _update_scheduler_sensor()

    return {
        "status": "success",
        "timer_id": tid,
        "remaining_seconds": remaining,
    }


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def devices_schedules_resume(
    timer_id: str | None = None,
    target_entity: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Devices Schedules Resume
    description: Resume a paused timer.
    fields:
      timer_id:
        name: Timer ID
        selector:
          text:
      target_entity:
        name: Target Entity
        selector:
          text:
    """
    tid, timer = await _resolve_target_timer(timer_id, target_entity)
    if not tid or not timer:
        return {"status": "not_found", "message": "No matching active timer found."}

    if timer.get("status") != "paused":
        return {"status": "invalid_state", "timer_id": tid}

    remaining = float(timer.get("remaining", 0.0))
    if remaining <= 0:
        return {"status": "invalid_state", "timer_id": tid, "error": "No remaining time."}

    now_ts = time.time()
    new_end = now_ts + remaining

    await asyncio.to_thread(
        _db_save_timer,
        tid,
        timer.get("entity_id", ""),
        "running",
        timer.get("created_at", ""),
        new_end,
        remaining,
        float(timer.get("duration_seconds", 0.0)),
        timer.get("condition_spec") or "",
        timer.get("actions", "[]"),
    )

    await _register_active_task(tid, new_end)
    await _update_scheduler_sensor()

    return {
        "status": "success",
        "timer_id": tid,
        "resumed_at": dt_util.now().isoformat(),
        "remaining_seconds": round(remaining),
        "new_end_time": _format_timestamp(new_end),
    }


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def devices_schedules_list(
    entity_filter: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Devices Schedules List
    description: List active running and paused timers with calculated remaining durations.
    fields:
      entity_filter:
        name: Entity Filter
        selector:
          text:
    """
    filter_norm = _normalize_entity_id(entity_filter) if entity_filter else None
    actives = await asyncio.to_thread(_db_get_active_timers, filter_norm)
    now_ts = time.time()
    formatted_timers = [_format_timer_record(item, now_ts) for item in actives]

    count = len(formatted_timers)
    summary = (
        f"There {'is' if count == 1 else 'are'} {count} active timer{'s' if count != 1 else ''}."
        if count > 0
        else "No active timers right now."
    )

    return {
        "status": "ok",
        "count": count,
        "summary": summary,
        "timers": formatted_timers,
    }

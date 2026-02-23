import asyncio
import random
import re
import sqlite3
import threading
import time
import urllib.parse
from contextlib import closing
from pathlib import Path
from typing import Any

import orjson
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

TTL = 30  # Cache retention period (1-30 days)
RETRY_LIMIT = 3
BASE_URL = "https://www.csgt.vn"
LOOKUP_URL = f"{BASE_URL}/tra-cuu-phat-nguoi"
POST_URL = f"{BASE_URL}/tra-cuu-vi-pham-qua-hinh-anh"
RECAPTCHA_SITEKEY = "6Le8H9ArAAAAAOWw8BZe4rg5mgbagZtxG1dVxv4i"
RECAPTCHA_CO = "aHR0cHM6Ly93d3cuY3NndC52bjo0NDM."

VEHICLE_TYPES = {"car", "motorbike", "electricbike"}

DB_PATH = Path("/config/cache.db")

if TTL < 1 or TTL > 30:
    raise ValueError("TTL must be between 1 and 30")

_CACHE_READY = False
_CACHE_READY_LOCK = threading.Lock()

CACHE_MAX_AGE = TTL * 24 * 60 * 60
# Update cache in background if data is older than 4 hours
CACHE_REFRESH_PERIOD = 4 * 60 * 60
CACHE_REFRESH_THRESHOLD = CACHE_MAX_AGE - CACHE_REFRESH_PERIOD


@pyscript_compile  # noqa: F821
def _connect_db() -> sqlite3.Connection:
    """Create a configured SQLite connection with necessary PRAGMAs."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA busy_timeout=3000;")
    except Exception:
        conn.close()
        raise
    return conn


@pyscript_compile  # noqa: F821
def _ensure_cache_db() -> None:
    """Create the cache database directory, SQLite file, and schema if they do not already exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect_db()) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache_entries
            (
                key        TEXT PRIMARY KEY,
                value      TEXT    NOT NULL,
                expires_at INTEGER NOT NULL
            )
            """
        )
        conn.commit()


@pyscript_compile  # noqa: F821
def _ensure_cache_db_once(force: bool = False) -> None:
    """Ensure the cache database exists, optionally forcing a rebuild."""
    global _CACHE_READY
    if force:
        _CACHE_READY = False
    if _CACHE_READY and DB_PATH.exists():
        return
    with _CACHE_READY_LOCK:
        if force:
            _CACHE_READY = False
        if not _CACHE_READY or not DB_PATH.exists():
            _ensure_cache_db()
            _CACHE_READY = True


def _reset_cache_ready() -> None:
    """Mark the cache database schema as stale so it will be recreated."""
    global _CACHE_READY
    with _CACHE_READY_LOCK:
        _CACHE_READY = False


async def _cache_prepare_db(force: bool = False) -> bool:
    """Ensure the cache database is ready for use."""
    await asyncio.to_thread(_ensure_cache_db_once, force)
    return True


@pyscript_compile  # noqa: F821
def _cache_get_sync(key: str) -> tuple[str | None, int | None]:
    """Fetch a cache record synchronously if it exists and has not expired."""
    for attempt in range(2):
        try:
            _ensure_cache_db_once(force=attempt == 1)
            now = int(time.time())
            with closing(_connect_db()) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT value, expires_at
                    FROM cache_entries
                    WHERE key = ?
                      AND expires_at > ?
                    """,
                    (key, now),
                )
                row = cur.fetchone()
            if not row:
                return None, None
            ttl_remaining = max(int(row["expires_at"]) - now, 0)
            return row["value"], ttl_remaining
        except sqlite3.OperationalError:
            _reset_cache_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return None, None


async def _cache_get(key: str) -> tuple[str | None, int | None]:
    """Return the cached JSON payload for a key and its remaining TTL in seconds."""
    return await asyncio.to_thread(_cache_get_sync, key)


@pyscript_compile  # noqa: F821
def _cache_set_sync(key: str, value: str, ttl_seconds: int) -> bool:
    """Store or update a cache record synchronously with retry on schema loss."""
    for attempt in range(2):
        try:
            _ensure_cache_db_once(force=attempt == 1)
            now = int(time.time())
            expires_at = now + ttl_seconds
            with closing(_connect_db()) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO cache_entries (key, value, expires_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value      = excluded.value,
                                                   expires_at = excluded.expires_at
                    """,
                    (key, value, expires_at),
                )
                conn.commit()
            return True
        except sqlite3.OperationalError:
            _reset_cache_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return False


async def _cache_set(key: str, value: str, ttl_seconds: int) -> bool:
    """Persist a cache entry with the provided TTL and prune expired records."""
    return await asyncio.to_thread(_cache_set_sync, key, value, ttl_seconds)


@pyscript_compile  # noqa: F821
def _cache_delete_sync(key: str) -> int:
    """Remove a cache record synchronously and return the rowcount."""
    for attempt in range(2):
        try:
            _ensure_cache_db_once(force=attempt == 1)
            with closing(_connect_db()) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                deleted = cur.rowcount if cur.rowcount is not None else 0
                conn.commit()
            return max(deleted, 0)
        except sqlite3.OperationalError:
            _reset_cache_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return 0


async def _cache_delete(key: str) -> int:
    """Remove the cache entry identified by key if it exists."""
    return await asyncio.to_thread(_cache_delete_sync, key)


@pyscript_compile  # noqa: F821
def _prune_expired_sync() -> int:
    """Prune expired entries from the cache database."""
    for attempt in range(2):
        try:
            _ensure_cache_db_once()
            now = int(time.time())
            with closing(_connect_db()) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM cache_entries WHERE expires_at <= ?", (now,))
                rowcount = getattr(cur, "rowcount", -1)
                removed = rowcount if rowcount and rowcount > 0 else 0
                conn.commit()
            return removed
        except sqlite3.OperationalError:
            _reset_cache_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return 0


async def _prune_expired() -> int:
    """Async wrapper for pruning expired entries."""
    return await asyncio.to_thread(_prune_expired_sync)


@time_trigger("cron(15 3 * * *)")  # noqa: F821
async def prune_cache_db() -> None:
    """Regularly prune expired entries from the cache database."""
    await _prune_expired()


async def _get_recaptcha_version(ss: AsyncSession) -> str | None:
    """Fetch the current reCAPTCHA JS version from Google's API.

    The version string changes with each Google release. It is extracted from
    the releases URL embedded in ``api.js``.

    Args:
        ss: An active AsyncSession.

    Returns:
        Version string or None on failure.
    """
    try:
        api_url = f"https://www.google.com/recaptcha/api.js?render={RECAPTCHA_SITEKEY}"
        resp = await ss.get(api_url, timeout=60)
        resp.raise_for_status()
        match = re.search(r"/recaptcha/releases/([^/]+)/", resp.text)
        return match.group(1) if match else None
    except Exception:
        return None


async def _get_recaptcha_token(ss: AsyncSession) -> tuple[str, None] | tuple[None, str]:
    """Obtain a reCAPTCHA v3 token via the anchor+reload API flow.

    Uses curl_cffi's Chrome impersonation to get a valid token from Google's
    reCAPTCHA API without running JavaScript. The token is obtained by:
    1. Fetching ``api.js`` to get the current release version
    2. Fetching the anchor page to get an initial token
    3. Posting to the reload endpoint to get the full response token

    Args:
        ss: An active AsyncSession with Chrome impersonation.

    Returns:
        (token, None) on success or (None, error_message) on failure.
    """
    try:
        version = await _get_recaptcha_version(ss)
        if not version:
            return None, "Failed to fetch reCAPTCHA version from api.js"

        anchor_url = (
            f"https://www.google.com/recaptcha/api2/anchor?"
            f"ar=1&k={RECAPTCHA_SITEKEY}"
            f"&co={RECAPTCHA_CO}"
            f"&hl=en&v={version}"
            f"&size=invisible&cb={int(time.time() * 1000)}"
        )

        resp_anchor = await ss.get(anchor_url, timeout=60)
        resp_anchor.raise_for_status()

        match = re.search(r'id="recaptcha-token"\s+value="([^"]+)"', resp_anchor.text)
        if not match:
            return None, "Failed to extract anchor token from reCAPTCHA"

        anchor_token = match.group(1)

        reload_url = (
            f"https://www.google.com/recaptcha/api2/reload?k={RECAPTCHA_SITEKEY}"
        )
        reload_data = {
            "v": version,
            "reason": "q",
            "c": anchor_token,
            "k": RECAPTCHA_SITEKEY,
            "co": RECAPTCHA_CO,
            "hl": "en",
            "size": "invisible",
        }
        reload_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": anchor_url,
        }

        resp_reload = await ss.post(
            reload_url, data=reload_data, headers=reload_headers, timeout=60
        )
        resp_reload.raise_for_status()

        rresp_match = re.search(r'"rresp","([^"]+)"', resp_reload.text)
        if not rresp_match:
            return None, "Failed to extract response token from reCAPTCHA reload"

        return rresp_match.group(1), None

    except Exception as error:
        return None, f"reCAPTCHA token retrieval failed: {error}"


@pyscript_compile  # noqa: F821
def _extract_violations_from_html(result_html: str) -> dict[str, Any]:
    """Parse violations from the resultHtml returned by the new csgt.vn API.

    The new HTML structure uses Bootstrap cards with the following layout:
    - Each violation is inside a ``div.violation-card``
    - Status in ``span.status-badge``
    - Info items in ``div.info-item`` containing ``span.label`` and ``span.value``

    Args:
        result_html: The HTML string from the ``resultHtml`` field in the JSON response.

    Returns:
        A dict with status (success/error), message, and violation details.
    """
    soup = BeautifulSoup(result_html, "html.parser")
    violation_cards = soup.find_all("div", class_="violation-card")

    if not violation_cards:
        # Check if the page returns a "no violations" message
        text_content = soup.get_text(strip=True)
        if text_content:
            return {
                "status": "success",
                "message": "Không có vi phạm giao thông",
                "detail": "",
            }
        return {
            "status": "error",
            "message": "Không tìm thấy dữ liệu vi phạm",
            "detail": "",
        }

    violations = []
    for card in violation_cards:
        violation = {}

        # Extract plate number from violation title
        title_div = card.find("div", class_="violation-title")
        if title_div:
            violation["Biển kiểm soát"] = title_div.get_text(strip=True)

        # Extract status
        status_span = card.find("span", class_="status-badge")
        if status_span:
            violation["Trạng thái"] = status_span.get_text(strip=True)

        # Extract info by section to handle duplicate "Địa chỉ" labels
        info_groups = card.find_all("div", class_="info-group")
        for group in info_groups:
            title_el = group.find("h6", class_="info-title")
            section = title_el.get_text(strip=True) if title_el else ""

            if section == "Thông tin xử lý":
                # This section has two col-md-6 columns, each with "Đơn vị" + "Địa chỉ"
                columns = group.find_all("div", class_="col-md-6")
                resolution_items = []
                for col in columns:
                    col_data = {}
                    for item in col.find_all("div", class_="info-item"):
                        label_span = item.find("span", class_="label")
                        value_span = item.find("span", class_="value")
                        if label_span and value_span:
                            key = label_span.get_text(strip=True).rstrip(":")
                            col_data[key] = value_span.get_text(strip=True)
                    if col_data:
                        resolution_items.append(col_data)

                for col_data in resolution_items:
                    # Prefix duplicate keys with their context label
                    unit_key = next(
                        (k for k in col_data if k.startswith("Đơn vị")), None
                    )
                    if unit_key:
                        violation[unit_key] = col_data[unit_key]
                        addr = col_data.get("Địa chỉ")
                        if addr:
                            violation[f"Địa chỉ ({unit_key})"] = addr
                    else:
                        violation.update(col_data)
            else:
                for item in group.find_all("div", class_="info-item"):
                    label_span = item.find("span", class_="label")
                    value_span = item.find("span", class_="value")
                    if label_span and value_span:
                        key = label_span.get_text(strip=True).rstrip(":")
                        violation[key] = value_span.get_text(strip=True)

        if violation:
            violations.append(violation)

    if not violations:
        return {
            "status": "success",
            "message": "Không có vi phạm giao thông",
            "detail": "",
        }

    return {
        "status": "success",
        "message": f"Có {len(violations)} vi phạm giao thông",
        "detail": violations,
    }


async def _check_license_plate(
    license_plate: str, vehicle_type: str, retry_count: int = 0
) -> dict[str, Any]:
    """End-to-end lookup flow against csgt.vn with retries.

    Performs: visit homepage → visit lookup page (get CSRF token + cookies) →
    obtain reCAPTCHA v3 token → submit form → parse resultHtml.

    Args:
        license_plate: VN plate number (uppercase, validated by caller).
        vehicle_type: One of ``car``, ``motorbike``, ``electricbike``.
        retry_count: Current retry attempt (0-based, max ``RETRY_LIMIT`` retries).

    Returns:
        Parsed response dict with status and details, or error.
    """
    async with AsyncSession(impersonate="chrome") as ss:
        try:
            # Step 1: Visit homepage to establish session cookies
            await ss.get(BASE_URL, timeout=60)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Step 2: Visit lookup page to get CSRF token and session cookies
            resp_page = await ss.get(LOOKUP_URL, timeout=60)
            resp_page.raise_for_status()

            token_match = re.search(r'name="_token"\s+value="([^"]+)"', resp_page.text)
            if not token_match:
                return {"error": "Failed to extract CSRF token from lookup page"}

            csrf_token = token_match.group(1)

            # Step 3: Obtain reCAPTCHA token
            await asyncio.sleep(random.uniform(1.0, 2.0))
            recaptcha_token, error = await _get_recaptcha_token(ss)
            if not recaptcha_token:
                if retry_count < RETRY_LIMIT:
                    print(
                        f"reCAPTCHA failed (Retry {retry_count + 1}/{RETRY_LIMIT}): {error}"
                    )
                    await asyncio.sleep(30)
                    return await _check_license_plate(
                        license_plate, vehicle_type, retry_count + 1
                    )
                return {"error": f"reCAPTCHA token retrieval failed: {error}"}

            # Step 4: Submit the lookup form
            xsrf_token = urllib.parse.unquote(dict(ss.cookies).get("XSRF-TOKEN", ""))
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": BASE_URL,
                "Referer": LOOKUP_URL,
                "X-Requested-With": "XMLHttpRequest",
                "X-XSRF-TOKEN": xsrf_token,
            }
            form_data = urllib.parse.urlencode(
                {
                    "_token": csrf_token,
                    "g-recaptcha-response": recaptcha_token,
                    "vehicle_type": vehicle_type,
                    "plate_number": license_plate,
                }
            )

            resp = await ss.post(POST_URL, data=form_data, headers=headers, timeout=60)

            if resp.status_code == 429:
                if retry_count < RETRY_LIMIT:
                    print(f"Rate limited (Retry {retry_count + 1}/{RETRY_LIMIT})")
                    await asyncio.sleep(60)
                    return await _check_license_plate(
                        license_plate, vehicle_type, retry_count + 1
                    )
                return {"error": f"Rate limited after {RETRY_LIMIT} retries"}

            if resp.status_code == 422:
                response_data = orjson.loads(resp.content)
                if retry_count < RETRY_LIMIT:
                    msg = response_data.get("message", "Verification failed")
                    print(
                        f"Verification failed (Retry {retry_count + 1}/{RETRY_LIMIT}): {msg}"
                    )
                    await asyncio.sleep(30)
                    return await _check_license_plate(
                        license_plate, vehicle_type, retry_count + 1
                    )
                return {
                    "error": f"Verification failed after {RETRY_LIMIT} retries: "
                    + response_data.get("message", "Verification failed")
                }

            resp.raise_for_status()

            # Step 5: Parse the response
            response_data = orjson.loads(resp.content)
            result_html = response_data.get("resultHtml", "")

            if not result_html:
                return {
                    "status": "success",
                    "message": "Không có vi phạm giao thông",
                    "detail": "",
                }

            return _extract_violations_from_html(result_html)

        except Exception as error:
            if retry_count < RETRY_LIMIT:
                print(f"Error (Retry {retry_count + 1}/{RETRY_LIMIT}): {error}")
                await asyncio.sleep(30)
                return await _check_license_plate(
                    license_plate, vehicle_type, retry_count + 1
                )
            return {"error": f"Failed after {RETRY_LIMIT} retries: {error}"}


@time_trigger("startup")  # noqa: F821
async def build_cached_ctx() -> None:
    """Run once at HA startup / Pyscript reload."""
    await _cache_prepare_db(force=True)
    await _prune_expired()


@service(supports_response="only")  # noqa: F821
async def traffic_fine_lookup_tool(
    license_plate: str, vehicle_type: str, bypass_caching: bool = False
) -> dict[str, Any]:
    """
    yaml
    name: Traffic Fine Lookup Tool
    description: Check Vietnam traffic fine status on csgt.vn and return parsed results.
    fields:
      license_plate:
        name: License Plate
        description: Vietnam license plate without spaces or dashes.
        example: 29A99999
        required: true
        selector:
          text:
      vehicle_type:
        name: Vehicle Type
        description: Vehicle classification expected by csgt.vn.
        example: car
        required: true
        selector:
          select:
            options:
              - label: Car
                value: car
              - label: Motorbike
                value: motorbike
              - label: Electric Bike
                value: electricbike
        default: car
      bypass_caching:
        name: Bypass Caching
        description: Ignore cached data and fetch fresh results (useful for debugging).
        example: false
        selector:
          boolean:
    """
    try:
        license_plate = str(license_plate).upper()
        license_plate = re.sub(r"[^A-Z0-9]", "", license_plate)
        vehicle_type = str(vehicle_type).lower()

        if vehicle_type not in VEHICLE_TYPES:
            return {"error": "The type of vehicle is invalid"}

        if vehicle_type == "car":
            pattern = r"^\d{2}[A-Z]{1,2}\d{4,5}$"
        else:
            pattern = r"^\d{2}[A-Z1-9]{2}\d{4,5}$"
        if not (license_plate and re.match(pattern, license_plate)):
            return {"error": "The license plate number is invalid"}

        cache_key = f"{license_plate}-{vehicle_type}"
        if bool(bypass_caching):
            await _cache_delete(cache_key)
            response = await _check_license_plate(license_plate, vehicle_type)
            if response and response.get("status") == "success":
                await _cache_set(
                    cache_key,
                    orjson.dumps(response).decode("utf-8"),
                    CACHE_MAX_AGE,
                )
            return response

        cached_value, ttl = await _cache_get(cache_key)
        if cached_value is not None:
            if ttl is not None and ttl < CACHE_REFRESH_THRESHOLD:
                task.create(_check_license_plate, license_plate, vehicle_type)  # noqa: F821
            return orjson.loads(cached_value)

        response = await _check_license_plate(license_plate, vehicle_type)
        if response and response.get("status") == "success":
            await _cache_set(
                cache_key,
                orjson.dumps(response).decode("utf-8"),
                CACHE_MAX_AGE,
            )
        return response
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}

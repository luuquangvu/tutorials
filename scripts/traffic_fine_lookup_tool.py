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
from curl_cffi.requests import AsyncSession, RequestsError

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
    """Create a configured SQLite connection with optimized PRAGMAs."""
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA busy_timeout=3000;")
    except sqlite3.Error:
        conn.close()
        raise
    return conn


@pyscript_compile  # noqa: F821
def _ensure_cache_db() -> None:
    """Initialize the cache database schema and directory."""
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
    """Mark the cache database schema as stale."""
    global _CACHE_READY
    with _CACHE_READY_LOCK:
        _CACHE_READY = False


async def _cache_prepare_db(force: bool = False) -> bool:
    """Async wrapper to ensure the cache database is ready."""
    await asyncio.to_thread(_ensure_cache_db_once, force)
    return True


@pyscript_compile  # noqa: F821
def _cache_get_sync(key: str) -> tuple[str | None, int | None]:
    """Fetch a cache record synchronously (returns value and remaining TTL)."""
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
    """Fetch cached JSON payload and its remaining TTL in seconds."""
    return await asyncio.to_thread(_cache_get_sync, key)


@pyscript_compile  # noqa: F821
def _cache_set_sync(key: str, value: str, ttl_seconds: int) -> bool:
    """Store or update a cache record synchronously."""
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
    """Persist a cache entry with the provided TTL."""
    return await asyncio.to_thread(_cache_set_sync, key, value, ttl_seconds)


@pyscript_compile  # noqa: F821
def _cache_delete_sync(key: str) -> int:
    """Remove a cache record synchronously."""
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
    """Remove a cache entry by key."""
    return await asyncio.to_thread(_cache_delete_sync, key)


@pyscript_compile  # noqa: F821
def _prune_expired_sync() -> int:
    """Remove expired entries from the cache database."""
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
    """Async wrapper for pruning expired cache entries."""
    return await asyncio.to_thread(_prune_expired_sync)


@time_trigger("cron(15 3 * * *)")  # noqa: F821
async def prune_cache_db() -> None:
    """Daily cleanup of expired cache entries."""
    await _prune_expired()


async def _get_recaptcha_version(ss: AsyncSession) -> str | None:
    """Fetch the current reCAPTCHA JS version from Google's API."""
    try:
        api_url = f"https://www.google.com/recaptcha/api.js?render={RECAPTCHA_SITEKEY}"
        resp = await ss.get(api_url, timeout=60)
        resp.raise_for_status()
        match = re.search(r"/recaptcha/releases/([^/]+)/", resp.text)
        return match.group(1) if match else None
    except RequestsError:
        return None


async def _get_recaptcha_token(ss: AsyncSession) -> tuple[str, None] | tuple[None, str]:
    """Obtain a reCAPTCHA v3 token via the anchor+reload API flow."""
    try:
        version = await _get_recaptcha_version(ss)
        if not version:
            return None, "Failed to fetch reCAPTCHA version"

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
            return None, "Failed to extract anchor token"

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
            return None, "Failed to extract response token"

        return rresp_match.group(1), None

    except RequestsError as error:
        return None, f"reCAPTCHA retrieval failed: {error}"


@pyscript_compile  # noqa: F821
def _extract_violations_from_html(result_html: str) -> dict[str, Any]:
    """Parse traffic violations from csgt.vn result HTML."""
    soup = BeautifulSoup(result_html, "html.parser")
    violation_cards = soup.find_all("div", class_="violation-card")

    if not violation_cards:
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

        title_div = card.find("div", class_="violation-title")
        if title_div:
            violation["Biển kiểm soát"] = title_div.get_text(strip=True)

        status_span = card.find("span", class_="status-badge")
        if status_span:
            violation["Trạng thái"] = status_span.get_text(strip=True)

        info_groups = card.find_all("div", class_="info-group")
        for group in info_groups:
            title_el = group.find("h6", class_="info-title")
            section = title_el.get_text(strip=True) if title_el else ""

            if section == "Thông tin xử lý":
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
    """Execute the end-to-end lookup flow against csgt.vn with retries."""
    async with AsyncSession(impersonate="chrome") as ss:
        try:
            await ss.get(BASE_URL, timeout=60)
            await asyncio.sleep(random.uniform(0.5, 1.5))

            resp_page = await ss.get(LOOKUP_URL, timeout=60)
            resp_page.raise_for_status()

            token_match = re.search(r'name="_token"\s+value="([^"]+)"', resp_page.text)
            if not token_match:
                log.error(f"CSRF token extraction failed for {license_plate}")  # noqa: F821
                return {"error": "Failed to extract CSRF token"}

            csrf_token = token_match.group(1)

            await asyncio.sleep(random.uniform(1.0, 2.0))
            recaptcha_token, error = await _get_recaptcha_token(ss)
            if not recaptcha_token:
                if retry_count < RETRY_LIMIT:
                    log.warning(  # noqa: F821
                        f"reCAPTCHA failed (Retry {retry_count + 1}/{RETRY_LIMIT}): {error}"
                    )
                    await asyncio.sleep(30)
                    return await _check_license_plate(
                        license_plate, vehicle_type, retry_count + 1
                    )
                log.error(f"reCAPTCHA failed for {license_plate}: {error}")  # noqa: F821
                return {"error": f"reCAPTCHA retrieval failed: {error}"}

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
                try:
                    msg = orjson.loads(resp.content).get("message", "")
                except orjson.JSONDecodeError:
                    msg = ""

                if "Bạn đã vượt quá số lần tra cứu" in msg:
                    log.error(f"Daily limit reached for {license_plate}: {msg}")  # noqa: F821
                    return {"error": msg}

                if retry_count < RETRY_LIMIT:
                    log.warning(  # noqa: F821
                        f"Rate limited (Retry {retry_count + 1}/{RETRY_LIMIT}): {msg}"
                    )
                    await asyncio.sleep(60)
                    return await _check_license_plate(
                        license_plate, vehicle_type, retry_count + 1
                    )
                return {"error": msg or f"Rate limited after {RETRY_LIMIT} retries"}

            if resp.status_code == 422:
                response_data = orjson.loads(resp.content)
                if retry_count < RETRY_LIMIT:
                    msg = response_data.get("message", "Verification failed")
                    log.warning(  # noqa: F821
                        f"Verification failed (Retry {retry_count + 1}/{RETRY_LIMIT}): {msg}"
                    )
                    await asyncio.sleep(30)
                    return await _check_license_plate(
                        license_plate, vehicle_type, retry_count + 1
                    )
                return {
                    "error": "Verification failed: "
                    + response_data.get("message", "Verification failed")
                }

            resp.raise_for_status()

            response_data = orjson.loads(resp.content)
            result_html = response_data.get("resultHtml", "")

            if not result_html:
                return {
                    "status": "success",
                    "message": "Không có vi phạm giao thông",
                    "detail": "",
                }

            return _extract_violations_from_html(result_html)

        except (RequestsError, orjson.JSONDecodeError) as error:
            if retry_count < RETRY_LIMIT:
                log.warning(f"Error (Retry {retry_count + 1}/{RETRY_LIMIT}): {error}")  # noqa: F821
                await asyncio.sleep(30)
                return await _check_license_plate(
                    license_plate, vehicle_type, retry_count + 1
                )
            log.error(  # noqa: F821
                f"Lookup failed for {license_plate} after {RETRY_LIMIT} retries: {error}"
            )
            return {"error": f"Failed after {RETRY_LIMIT} retries: {error}"}


@time_trigger("startup")  # noqa: F821
async def build_cached_ctx() -> None:
    """Initialize cache and prune expired entries on startup."""
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
        log.error(f"Unexpected error for {license_plate}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}

import asyncio
import contextlib
import mimetypes
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any

import httpx
import orjson
from homeassistant.helpers import network

DIRECTORY = "/media/telegram"
TOKEN = pyscript.config.get("telegram_bot_token")  # noqa: F821  # ty:ignore[unresolved-reference]
if TOKEN:
    TOKEN = TOKEN.strip()

_session: httpx.AsyncClient | None = None
_session_lock = asyncio.Lock()


if not TOKEN:
    raise ValueError("Telegram bot token is missing")

ACTIONS_CHAT: tuple[str, ...] = (
    "typing",
    "upload_photo",
    "record_video",
    "upload_video",
    "record_voice",
    "upload_voice",
    "upload_document",
    "choose_sticker",
    "find_location",
    "record_video_note",
    "upload_video_note",
)

PARSE_MODES: tuple[str, ...] = (
    "HTML",
    "MarkdownV2",
    "Markdown",
)


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _create_session() -> httpx.AsyncClient:
    """Create the HTTPX client in native Python for executor-safe SSL setup."""
    return httpx.AsyncClient(http2=True, timeout=httpx.Timeout(300))


_COORDINATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"@\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))"),
    re.compile(r"!3d\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+)).*?!4d\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))"),
    re.compile(r"(?:[?&](?:q|query|ll)=)\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))"),
    re.compile(r"(?<![\d.])([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))"),
)


def _to_media_path(path: str) -> str:
    """Normalize and validate a Home Assistant media path to start with /media/."""
    if path.startswith("local/"):
        path = "/media/" + path.removeprefix("local/")

    p = Path(path)
    if not p.is_absolute():
        p = Path("/media") / p

    try:
        resolved_path = p.resolve()
    except OSError:
        resolved_path = Path(os.path.abspath(str(p)))

    media_root = Path("/media").resolve()
    if media_root not in resolved_path.parents and resolved_path != media_root:
        raise ValueError(
            f"Security Error: Access to '{path}' (resolved to '{resolved_path}') is denied. Path must be inside /media."
        )

    return str(resolved_path)


def _to_relative_path(path: str) -> str:
    """Convert an absolute /media/ path to a relative local/ media source path."""
    if path.startswith("/media/"):
        return "local/" + path.removeprefix("/media/")
    return path


async def _ensure_session() -> httpx.AsyncClient:
    """Create or return a shared httpx AsyncClient with HTTP/2."""
    global _session
    if _session is None or _session.is_closed:
        async with _session_lock:
            if _session is None or _session.is_closed:
                _session = await asyncio.to_thread(_create_session)
    return _session


async def _ensure_dir(path: str) -> None:
    """Ensure a directory exists, creating it if necessary."""
    await asyncio.to_thread(os.makedirs, path, exist_ok=True)


async def _get_file(client: httpx.AsyncClient, file_id: str) -> str | None:
    """Resolve a Telegram file identifier to its server path."""
    url = f"https://api.telegram.org/bot{TOKEN}/getFile"
    payload = {"file_id": file_id}
    data = orjson.dumps(payload).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    result = orjson.loads(resp.content)
    return result.get("result", {}).get("file_path")


async def _download_file(client: httpx.AsyncClient, file_id: str) -> tuple[str, None] | tuple[None, str]:
    """Download a file from Telegram and save it locally."""
    try:
        online_file_path = await _get_file(client, file_id)
        if not online_file_path:
            return None, "Unable to retrieve the file_path from Telegram."

        url = f"https://api.telegram.org/file/bot{TOKEN}/{online_file_path}"

        file_name = os.path.basename(online_file_path)
        base, ext = os.path.splitext(file_name)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        file_name = f"{base}_{timestamp}_{secrets.token_hex(4)}{ext}"

        file_path = os.path.join(DIRECTORY, file_name)

        await asyncio.to_thread(_download_file_chunks, url, file_path)

        return file_path, None
    except Exception as error:
        return None, f"Download failed: {error}"


async def _send_message(
    client: httpx.AsyncClient,
    chat_id: int | str,
    message: str,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Send a text message via the Telegram API."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    text = message
    if len(text) > 4096:
        text = f"{text[:4093]}..."
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_message_id is not None:
        payload["reply_parameters"] = {"message_id": reply_to_message_id}
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id
    if parse_mode:
        if parse_mode not in PARSE_MODES:
            raise ValueError(f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}")
        payload["parse_mode"] = parse_mode
    data = orjson.dumps(payload).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _send_location(
    client: httpx.AsyncClient,
    chat_id: int | str,
    latitude: float,
    longitude: float,
    horizontal_accuracy: float | None = None,
    live_period: int | None = None,
    heading: int | None = None,
    proximity_alert_radius: int | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
) -> dict[str, Any]:
    """Send a map location via the Telegram API."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "latitude": latitude,
        "longitude": longitude,
    }
    optional_fields = {
        "horizontal_accuracy": horizontal_accuracy,
        "live_period": live_period,
        "heading": heading,
        "proximity_alert_radius": proximity_alert_radius,
        "message_thread_id": message_thread_id,
        "business_connection_id": business_connection_id,
        "direct_messages_topic_id": direct_messages_topic_id,
        "receiver_user_id": receiver_user_id,
        "callback_query_id": callback_query_id,
        "disable_notification": disable_notification,
        "protect_content": protect_content,
        "allow_paid_broadcast": allow_paid_broadcast,
        "message_effect_id": message_effect_id,
    }
    payload |= {name: value for name, value in optional_fields.items() if value is not None and value != ""}
    if reply_to_message_id is not None:
        payload["reply_parameters"] = {"message_id": reply_to_message_id}

    url = f"https://api.telegram.org/bot{TOKEN}/sendLocation"
    data = orjson.dumps(payload).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _send_photo(
    client: httpx.AsyncClient,
    chat_id: int | str,
    file_path: str,
    caption: str | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Upload and send a photo via the Telegram API."""
    file_path = _to_media_path(file_path)

    file_exists = await asyncio.to_thread(os.path.isfile, file_path)
    if not file_exists:
        raise FileNotFoundError(f"File not found: {file_path}")

    filename = os.path.basename(file_path)
    mime_type, _ = mimetypes.guess_file_type(filename)
    content_type = mime_type or "application/octet-stream"

    form_data: dict[str, Any] = {
        "chat_id": str(chat_id),
    }
    if caption:
        form_data["caption"] = caption[:1024]
    if parse_mode:
        if parse_mode not in PARSE_MODES:
            raise ValueError(f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}")
        form_data["parse_mode"] = parse_mode
    if reply_to_message_id is not None:
        form_data["reply_parameters"] = orjson.dumps({"message_id": reply_to_message_id}).decode("utf-8")
    if message_thread_id:
        form_data["message_thread_id"] = str(message_thread_id)

    f = await asyncio.to_thread(_open_file, file_path, "rb")
    try:
        files = {"photo": (filename, f, content_type)}
        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        resp = await client.post(url, data=form_data, files=files)
        resp.raise_for_status()
        return orjson.loads(resp.content)
    finally:
        await asyncio.to_thread(f.close)


async def _send_media_file(
    client: httpx.AsyncClient,
    chat_id: int | str,
    file_path: str,
    endpoint: str,
    field_name: str,
    caption: str | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
    fields: dict[str, Any] | None = None,
    attachments: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Upload and send a local media file through a Telegram multipart endpoint."""
    file_path = _to_media_path(file_path)

    file_exists = await asyncio.to_thread(os.path.isfile, file_path)
    if not file_exists:
        raise FileNotFoundError(f"File not found: {file_path}")

    form_data: dict[str, Any] = {"chat_id": str(chat_id)}
    if caption:
        form_data["caption"] = caption[:1024]
    if parse_mode:
        if parse_mode not in PARSE_MODES:
            raise ValueError(f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}")
        form_data["parse_mode"] = parse_mode
    if reply_to_message_id is not None:
        form_data["reply_parameters"] = orjson.dumps({"message_id": reply_to_message_id}).decode("utf-8")
    if message_thread_id is not None:
        form_data["message_thread_id"] = str(message_thread_id)
    if fields:
        for name, value in fields.items():
            if value is not None:
                form_data[name] = str(value).lower() if isinstance(value, bool) else str(value)

    paths = {field_name: file_path, **(attachments or {})}
    opened_files: dict[str, Any] = {}
    try:
        files: dict[str, tuple[str, Any, str]] = {}
        for field, path in paths.items():
            normalized_path = _to_media_path(path)
            if not await asyncio.to_thread(os.path.isfile, normalized_path):
                raise FileNotFoundError(f"File not found: {normalized_path}")
            attachment_name = os.path.basename(normalized_path)
            attachment_type, _ = mimetypes.guess_file_type(attachment_name)
            attachment_file = await asyncio.to_thread(_open_file, normalized_path, "rb")
            opened_files[field] = attachment_file
            files[field] = (attachment_name, attachment_file, attachment_type or "application/octet-stream")

        url = f"https://api.telegram.org/bot{TOKEN}/{endpoint}"
        resp = await client.post(url, data=form_data, files=files)
        resp.raise_for_status()
        return orjson.loads(resp.content)
    finally:
        for attachment_file in opened_files.values():
            await asyncio.to_thread(attachment_file.close)


def _common_media_fields(
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
) -> dict[str, Any]:
    """Return common optional fields supported by Telegram send-media methods."""
    return {
        "business_connection_id": business_connection_id,
        "direct_messages_topic_id": direct_messages_topic_id,
        "receiver_user_id": receiver_user_id,
        "callback_query_id": callback_query_id,
        "disable_notification": disable_notification,
        "protect_content": protect_content,
        "allow_paid_broadcast": allow_paid_broadcast,
        "message_effect_id": message_effect_id,
    }


def _parse_coordinates(value: Any) -> tuple[float, float] | None:
    """Extract latitude and longitude from text, a coordinate pair, or a Google Maps URL."""
    if isinstance(value, str):
        decoded = value.replace("%2C", ",").replace("%2c", ",")
    else:
        try:
            values = tuple(value)
        except TypeError:
            decoded = str(value)
        else:
            if len(values) == 2:
                with contextlib.suppress(TypeError, ValueError):
                    return float(values[0]), float(values[1])
            decoded = str(value)

        decoded = decoded.replace("%2C", ",").replace("%2c", ",")
    for pattern in _COORDINATE_PATTERNS:
        if match := pattern.search(decoded):
            return float(match.group(1)), float(match.group(2))
    return None


async def _send_audio(
    client: httpx.AsyncClient,
    chat_id: int | str,
    file_path: str,
    caption: str | None = None,
    duration: int | None = None,
    performer: str | None = None,
    title: str | None = None,
    thumbnail_path: str | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Upload and send an audio file via the Telegram API."""
    return await _send_media_file(
        client,
        chat_id,
        file_path,
        endpoint="sendAudio",
        field_name="audio",
        caption=caption,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=message_thread_id,
        parse_mode=parse_mode,
        fields={
            "duration": duration,
            "performer": performer,
            "title": title,
            **_common_media_fields(
                business_connection_id,
                direct_messages_topic_id,
                receiver_user_id,
                callback_query_id,
                disable_notification,
                protect_content,
                allow_paid_broadcast,
                message_effect_id,
            ),
        },
        attachments={"thumbnail": thumbnail_path} if thumbnail_path else None,
    )


async def _send_document(
    client: httpx.AsyncClient,
    chat_id: int | str,
    file_path: str,
    caption: str | None = None,
    disable_content_type_detection: bool | None = None,
    thumbnail_path: str | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Upload and send a document file via the Telegram API."""
    return await _send_media_file(
        client,
        chat_id,
        file_path,
        endpoint="sendDocument",
        field_name="document",
        caption=caption,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=message_thread_id,
        parse_mode=parse_mode,
        fields={
            "disable_content_type_detection": disable_content_type_detection,
            **_common_media_fields(
                business_connection_id,
                direct_messages_topic_id,
                receiver_user_id,
                callback_query_id,
                disable_notification,
                protect_content,
                allow_paid_broadcast,
                message_effect_id,
            ),
        },
        attachments={"thumbnail": thumbnail_path} if thumbnail_path else None,
    )


async def _send_video(
    client: httpx.AsyncClient,
    chat_id: int | str,
    file_path: str,
    caption: str | None = None,
    duration: int | None = None,
    width: int | None = None,
    height: int | None = None,
    supports_streaming: bool | None = None,
    has_spoiler: bool | None = None,
    thumbnail_path: str | None = None,
    cover_path: str | None = None,
    start_timestamp: int | None = None,
    show_caption_above_media: bool | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Upload and send a video file via the Telegram API."""
    return await _send_media_file(
        client,
        chat_id,
        file_path,
        endpoint="sendVideo",
        field_name="video",
        caption=caption,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=message_thread_id,
        parse_mode=parse_mode,
        fields={
            "duration": duration,
            "width": width,
            "height": height,
            "supports_streaming": supports_streaming,
            "has_spoiler": has_spoiler,
            "start_timestamp": start_timestamp,
            "show_caption_above_media": show_caption_above_media,
            **_common_media_fields(
                business_connection_id,
                direct_messages_topic_id,
                receiver_user_id,
                callback_query_id,
                disable_notification,
                protect_content,
                allow_paid_broadcast,
                message_effect_id,
            ),
        },
        attachments=({"thumbnail": thumbnail_path} if thumbnail_path else {})
        | ({"cover": cover_path} if cover_path else {})
        or None,
    )


async def _send_voice(
    client: httpx.AsyncClient,
    chat_id: int | str,
    file_path: str,
    caption: str | None = None,
    duration: int | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """Upload and send a voice message via the Telegram API."""
    return await _send_media_file(
        client,
        chat_id,
        file_path,
        endpoint="sendVoice",
        field_name="voice",
        caption=caption,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=message_thread_id,
        parse_mode=parse_mode,
        fields={
            "duration": duration,
            **_common_media_fields(
                business_connection_id,
                direct_messages_topic_id,
                receiver_user_id,
                callback_query_id,
                disable_notification,
                protect_content,
                allow_paid_broadcast,
                message_effect_id,
            ),
        },
    )


async def _get_webhook_info(client: httpx.AsyncClient) -> dict[str, Any]:
    """Retrieve current Telegram webhook status."""
    url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
    resp = await client.get(url)
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _set_webhook(
    client: httpx.AsyncClient,
    base_url: str,
    webhook_id: str,
    secret_token: str,
) -> dict[str, Any]:
    """Configure the Telegram webhook URL."""
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    params = {
        "url": f"{base_url}/api/webhook/{webhook_id}",
        "drop_pending_updates": True,
        "secret_token": secret_token,
    }
    data = orjson.dumps(params).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _delete_webhook(client: httpx.AsyncClient) -> dict[str, Any]:
    """Remove the Telegram webhook configuration."""
    url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    params = {"drop_pending_updates": True}
    data = orjson.dumps(params).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _get_updates(
    client: httpx.AsyncClient,
    timeout: int = 30,
    offset: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Fetch updates from Telegram using long polling."""
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params: dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    if limit is not None:
        params["limit"] = limit
    data = orjson.dumps(params).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _get_me(client: httpx.AsyncClient) -> dict[str, Any]:
    """Retrieve basic bot account information."""
    url = f"https://api.telegram.org/bot{TOKEN}/getMe"
    resp = await client.get(url)
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _send_chat_action(
    client: httpx.AsyncClient,
    chat_id: int | str,
    message_thread_id: int | None = None,
    action: str = "typing",
) -> dict[str, Any]:
    """Broadcast a chat action status to a conversation."""
    if action not in ACTIONS_CHAT:
        raise ValueError(f"Unsupported chat action: {action}. Allowed: {', '.join(ACTIONS_CHAT)}")
    url = f"https://api.telegram.org/bot{TOKEN}/sendChatAction"
    params = {
        "chat_id": chat_id,
        "action": action,
    }
    if message_thread_id:
        params["message_thread_id"] = message_thread_id
    data = orjson.dumps(params).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


def _internal_url() -> str | None:
    """Return the internal Home Assistant base URL."""
    try:
        return network.get_url(hass, allow_external=False)  # noqa: F821  # ty:ignore[unresolved-reference]
    except network.NoURLAvailableError:
        return None


def _external_url() -> str | None:
    """Return the external HTTPS Home Assistant base URL."""
    try:
        return network.get_url(
            hass,  # noqa: F821  # ty:ignore[unresolved-reference]
            allow_internal=False,
            allow_ip=False,
            require_ssl=True,
            require_standard_port=True,
        )
    except network.NoURLAvailableError:
        return None


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _open_file(path: str, mode: str):
    """Safely open a file using native Python."""
    return open(path, mode)


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _download_file_chunks(url: str, file_path: str) -> None:
    """Download a URL in chunks using httpx to save memory."""
    with httpx.Client(timeout=300) as client, client.stream("GET", url) as resp, open(file_path, "wb") as f:
        resp.raise_for_status()
        for chunk in resp.iter_bytes(65536):
            f.write(chunk)
        f.flush()
        with contextlib.suppress(OSError):
            os.fsync(f.fileno())


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _cleanup_disk_sync(directory: str, cutoff: float) -> None:
    """Remove files from a directory older than a specified cutoff time."""
    path = Path(directory)
    if not path.exists():
        return

    for entry in path.iterdir():
        with contextlib.suppress(OSError):
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink()


async def _cleanup_old_files(directory: str, days: int = 30) -> None:
    """Delete local files older than the specified number of days."""
    now = time.time()
    cutoff = now - (days * 86400)
    await asyncio.to_thread(_cleanup_disk_sync, directory, cutoff)


@time_trigger("shutdown")  # noqa: F821  # ty:ignore[unresolved-reference]
async def _close_session() -> None:
    """Close the shared AsyncClient on service shutdown."""
    global _session
    if _session and not _session.is_closed:
        await _session.aclose()
        _session = None


@time_trigger("cron(0 0 * * *)")  # noqa: F821  # ty:ignore[unresolved-reference]
async def _daily_cleanup() -> None:
    """Perform daily cleanup of archived media files."""
    await _cleanup_old_files(DIRECTORY, days=30)


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_telegram_message(
    chat_id: str,
    message: str,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Telegram Message
    description: Send a plain text message to a Telegram chat.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
      message:
        name: Message
        description: Message text.
        example: Hello from Home Assistant
        required: true
        selector:
          text:
      reply_to_message_id:
        name: Reply To Message ID
        description: Message ID to reply to.
        selector:
          number:
            min: 1
            step: 1
      message_thread_id:
        name: Message Thread ID
        description: Topic/thread ID (forum topics in supergroups).
        selector:
          number:
            min: 1
            step: 1
      parse_mode:
        name: Parse Mode
        description: Format entities in the message using the selected parse mode.
        selector:
          select:
            mode: dropdown
            options:
              - HTML
              - MarkdownV2
              - Markdown
    """
    if not all([chat_id, message]):
        return {"error": "Missing one or more required arguments: chat_id, message"}
    if parse_mode and parse_mode not in PARSE_MODES:
        return {"error": f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}"}
    try:
        client = await _ensure_session()
        response = await _send_message(
            client,
            chat_id,
            message,
            reply_to_message_id=reply_to_message_id,
            message_thread_id=message_thread_id,
            parse_mode=parse_mode,
        )
        return response or {"error": "Failed to send message"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def get_telegram_file(file_id: str) -> dict[str, Any]:
    """
    yaml
    name: Get Telegram File
    description: Download a file by Telegram file_id; saves under media and returns a local path and type.
    fields:
      file_id:
        name: File ID
        description: Telegram file_id of the media to download.
        required: true
        selector:
          text:
    """
    if not file_id:
        return {"error": "Missing a required argument: file_id"}
    try:
        client = await _ensure_session()
        await _ensure_dir(DIRECTORY)

        file_path, error = await _download_file(client, file_id)
        if not file_path:
            return {"error": f"Unable to download the file from Telegram. {error}"}

        mimetypes.add_type("text/plain", ".yaml")
        mime_type, _ = mimetypes.guess_file_type(file_path)
        file_path = _to_relative_path(file_path)
        support_file_types = (
            "image/",
            "video/",
            "audio/",
            "text/",
            "application/pdf",
            "application/rtf",
            "application/msword",
            "application/vnd.ms-excel",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        response: dict[str, Any] = {
            "file_path": file_path,
            "mime_type": mime_type,
            "supported": bool(mime_type and mime_type.lower().startswith(support_file_types)),
        }
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def get_telegram_webhook() -> dict[str, Any]:
    """
    yaml
    name: Get Telegram Bot Webhook
    description: Retrieve current webhook configuration and status.
    """
    try:
        client = await _ensure_session()
        return await _get_webhook_info(client)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def set_telegram_webhook(webhook_id: str | None = None) -> dict[str, Any]:
    """
    yaml
    name: Set Telegram Bot Webhook
    description: Configure the HTTPS webhook endpoint for your Telegram bot.
    fields:
      webhook_id:
        name: Webhook ID
        description: Optional custom path suffix for /api/webhook; leave empty to auto-generate.
        selector:
          text:
    """
    try:
        if not webhook_id:
            webhook_id: str = secrets.token_urlsafe(32)
        external_url = _external_url()
        if not external_url:
            return {"error": "The external Home Assistant URL is not found or incorrect."}
        secret_token = secrets.token_urlsafe(32)
        client = await _ensure_session()
        response = await _set_webhook(client, external_url, webhook_id, secret_token)
        if isinstance(response, dict) and response.get("ok"):
            response["webhook_id"] = webhook_id
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def delete_telegram_webhook() -> dict[str, Any]:
    """
    yaml
    name: Delete Telegram Bot Webhook
    description: Remove the webhook configuration and stop webhook delivery.
    """
    try:
        client = await _ensure_session()
        return await _delete_webhook(client)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def get_telegram_updates(
    timeout: int = 30, offset: int | None = None, limit: int | None = None
) -> dict[str, Any]:
    """
    yaml
    name: Get Telegram Updates
    description: Tool for getting Telegram message updates.
    fields:
      timeout:
        name: Timeout
        description: Time to wait for a response from the Telegram.
        selector:
          number:
            min: 30
            max: 120
            step: 1
        default: 30
      offset:
        name: Offset
        description: Identifier of the first update to be returned.
        selector:
          number:
            min: 0
            step: 1
      limit:
        name: Limit
        description: Limits the number of updates to be retrieved. Values between 1-100.
        selector:
          number:
            min: 1
            max: 100
            step: 1
    """
    try:
        client = await _ensure_session()
        response = await _get_updates(client, timeout=timeout, offset=offset, limit=limit)
        if not response:
            return {
                "ok": True,
                "result": [],
                "description": "No updates found. Please send a message to "
                "the bot first to ensure there is data to retrieve.",
            }
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def get_telegram_bot_info() -> dict[str, Any]:
    """
    yaml
    name: Get Telegram Bot Information
    description: Tool for getting Telegram bot basic information.
    """
    try:
        client = await _ensure_session()
        return await _get_me(client)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_telegram_chat_action(
    chat_id: str,
    message_thread_id: int | None = None,
    action: str = "typing",
) -> dict[str, Any]:
    """
    yaml
    name: Send Telegram Chat Action
    description: Send a chat action to a Telegram chat (e.g., typing, upload_photo).
    fields:
      chat_id:
        name: Chat ID
        description: The unique identifier of the target chat where the chat action will be sent.
        required: true
        selector:
          text:
      message_thread_id:
        name: Message Thread ID
        description: The unique identifier of the specific message thread (topic) where the chat action will be sent.
        selector:
          number:
            min: 1
            step: 1
      action:
        name: Action
        description: Chat action to broadcast.
        selector:
          select:
            mode: dropdown
            options:
              - typing
              - upload_photo
              - record_video
              - upload_video
              - record_voice
              - upload_voice
              - upload_document
              - choose_sticker
              - find_location
              - record_video_note
              - upload_video_note
        default: typing
    """
    if not chat_id:
        return {"error": "Missing a required argument: chat_id"}
    if action not in ACTIONS_CHAT:
        return {"error": f"Unsupported chat action: {action}. Allowed: {', '.join(ACTIONS_CHAT)}"}
    try:
        client = await _ensure_session()
        response = await _send_chat_action(
            client,
            chat_id,
            message_thread_id,
            action=action,
        )
        return response or {"error": "Failed to send message"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_telegram_location(
    chat_id: str,
    location: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    horizontal_accuracy: float | None = None,
    live_period: int | None = None,
    heading: int | None = None,
    proximity_alert_radius: int | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Telegram Location
    description: Send a Telegram map pin from latitude/longitude or a Google Maps URL containing coordinates.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
      location:
        name: Location
        description: Coordinates as latitude,longitude or a Google Maps URL containing coordinates.
        selector:
          text:
      latitude:
        name: Latitude
        description: Latitude in degrees from -90 to 90. Overrides the value parsed from location.
        selector:
          number:
            min: -90
            max: 90
            step: 0.000001
      longitude:
        name: Longitude
        description: Longitude in degrees from -180 to 180. Overrides the value parsed from location.
        selector:
          number:
            min: -180
            max: 180
            step: 0.000001
      horizontal_accuracy:
        name: Horizontal Accuracy
        description: Optional radius of uncertainty in meters, from 0 to 1500.
        selector:
          number:
            min: 0
            max: 1500
            step: 0.1
      live_period:
        name: Live Period
        description: "Optional live-location period in seconds: 60-86400 or 2147483647."
        selector:
          number:
            min: 60
            max: 2147483647
            step: 1
      heading:
        name: Heading
        description: Optional direction of movement for a live location, from 1 to 360 degrees.
        selector:
          number:
            min: 1
            max: 360
            step: 1
      proximity_alert_radius:
        name: Proximity Alert Radius
        description: Optional proximity alert radius in meters for a live location.
        selector:
          number:
            min: 1
            step: 1
      reply_to_message_id:
        name: Reply To Message ID
        description: Optional message ID to reply to.
        selector:
          number:
            min: 1
            step: 1
      message_thread_id:
        name: Message Thread ID
        description: Optional forum topic/thread ID.
        selector:
          number:
            min: 1
            step: 1
      disable_notification:
        name: Disable Notification
        description: Send the location silently.
        selector:
          boolean:
      protect_content:
        name: Protect Content
        description: Prevent forwarding and saving.
        selector:
          boolean:
      allow_paid_broadcast:
        name: Allow Paid Broadcast
        description: Allow paid high-rate broadcasting.
        selector:
          boolean:
    """
    if not chat_id:
        return {"error": "Missing a required argument: chat_id"}

    if latitude is None or longitude is None:
        if not location:
            return {"error": "Provide latitude and longitude, or a Google Maps URL containing coordinates"}
        coordinates = _parse_coordinates(location)
        if not coordinates:
            return {"error": "Unable to find coordinates in location; provide latitude and longitude explicitly"}
    if latitude is None:
        latitude = coordinates[0]
    if longitude is None:
        longitude = coordinates[1]

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return {"error": "Latitude and longitude must be valid numbers"}

    if not -90 <= latitude <= 90:
        return {"error": "Latitude must be between -90 and 90"}
    if not -180 <= longitude <= 180:
        return {"error": "Longitude must be between -180 and 180"}
    try:
        if horizontal_accuracy is not None:
            horizontal_accuracy = float(horizontal_accuracy)
        if live_period is not None:
            live_period = int(live_period)
        if heading is not None:
            heading = int(heading)
        if proximity_alert_radius is not None:
            proximity_alert_radius = int(proximity_alert_radius)
    except (TypeError, ValueError):
        return {"error": "Location optional parameters must be valid numbers"}

    if horizontal_accuracy is not None and not 0 <= horizontal_accuracy <= 1500:
        return {"error": "Horizontal accuracy must be between 0 and 1500 meters"}
    if live_period is not None and live_period not in range(60, 86401) and live_period != 2147483647:
        return {"error": "Live period must be between 60 and 86400 seconds, or 2147483647"}
    if heading is not None and not 1 <= heading <= 360:
        return {"error": "Heading must be between 1 and 360 degrees"}
    if proximity_alert_radius is not None and proximity_alert_radius < 1:
        return {"error": "Proximity alert radius must be at least 1 meter"}

    try:
        client = await _ensure_session()
        response = await _send_location(
            client,
            chat_id,
            latitude,
            longitude,
            horizontal_accuracy=horizontal_accuracy,
            live_period=live_period,
            heading=heading,
            proximity_alert_radius=proximity_alert_radius,
            reply_to_message_id=reply_to_message_id,
            message_thread_id=message_thread_id,
            business_connection_id=business_connection_id,
            direct_messages_topic_id=direct_messages_topic_id,
            receiver_user_id=receiver_user_id,
            callback_query_id=callback_query_id,
            disable_notification=disable_notification,
            protect_content=protect_content,
            allow_paid_broadcast=allow_paid_broadcast,
            message_effect_id=message_effect_id,
        )
        return response or {"error": "Failed to send location"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_telegram_photo(
    chat_id: str,
    file_path: str,
    caption: str | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Telegram Photo
    description: Send a local image by uploading via multipart/form-data.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
      file_path:
        name: File Path
        description: Local image path under /media or local/.
        required: true
        selector:
          text:
      caption:
        name: Caption
        description: Optional text shown under the photo.
        selector:
          text:
      parse_mode:
        name: Parse Mode
        description: Format entities in the caption using the selected parse mode.
        selector:
          select:
            mode: dropdown
            options:
              - HTML
              - MarkdownV2
              - Markdown
      reply_to_message_id:
        name: Reply To Message ID
        description: The unique identifier of the original message you want to reply to.
        selector:
          number:
            min: 1
            step: 1
      message_thread_id:
        name: Message Thread ID
        description: The unique identifier of the specific message thread (topic) where the photo will be sent.
        selector:
          number:
            min: 1
            step: 1
    """
    if not all([chat_id, file_path]):
        return {"error": "Missing one or more required arguments: chat_id, file_path"}
    if parse_mode and parse_mode not in PARSE_MODES:
        return {"error": f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}"}
    try:
        client = await _ensure_session()
        response = await _send_photo(
            client,
            chat_id,
            file_path,
            caption=caption,
            reply_to_message_id=reply_to_message_id,
            message_thread_id=message_thread_id,
            parse_mode=parse_mode,
        )
        return response or {"error": "Failed to send photo"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


async def _send_telegram_media_action(
    sender: Any,
    media_name: str,
    chat_id: str,
    file_path: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Validate and execute a media-send Home Assistant action."""
    if not all([chat_id, file_path]):
        return {"error": "Missing one or more required arguments: chat_id, file_path"}
    if kwargs.get("parse_mode") and kwargs["parse_mode"] not in PARSE_MODES:
        return {"error": f"Unsupported parse_mode: {kwargs['parse_mode']}. Allowed: {', '.join(PARSE_MODES)}"}
    try:
        client = await _ensure_session()
        response = await sender(client, chat_id, file_path, **kwargs)
        return response or {"error": f"Failed to send {media_name}"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_telegram_audio(
    chat_id: str,
    file_path: str,
    caption: str | None = None,
    duration: int | None = None,
    performer: str | None = None,
    title: str | None = None,
    thumbnail_path: str | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Telegram Audio
    description: Send a local MP3 or M4A audio file via Telegram multipart/form-data.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
      file_path:
        name: File Path
        description: Local audio path under /media or local/.
        required: true
        selector:
          text:
      caption:
        name: Caption
        description: Optional audio caption, up to 1024 characters.
        selector:
          text:
      duration:
        name: Duration
        description: Optional duration of the audio in seconds.
        selector:
          number:
            min: 0
            step: 1
      performer:
        name: Performer
        description: Optional performer name.
        selector:
          text:
      title:
        name: Title
        description: Optional track title.
        selector:
          text:
      thumbnail_path:
        name: Thumbnail Path
        description: Optional JPEG thumbnail under /media or local/ (max 200 kB and 320 px).
        selector:
          text:
      reply_to_message_id:
        name: Reply To Message ID
        description: Optional message ID to reply to.
        selector:
          number:
            min: 1
            step: 1
      message_thread_id:
        name: Message Thread ID
        description: Optional forum topic/thread ID.
        selector:
          number:
            min: 1
            step: 1
      parse_mode:
        name: Parse Mode
        description: Format entities in the caption.
        selector:
          select:
            mode: dropdown
            options:
              - HTML
              - MarkdownV2
              - Markdown
      disable_notification:
        name: Disable Notification
        description: Send the audio silently.
        selector:
          boolean:
      protect_content:
        name: Protect Content
        description: Prevent forwarding and saving.
        selector:
          boolean:
      allow_paid_broadcast:
        name: Allow Paid Broadcast
        description: Allow paid high-rate broadcasting.
        selector:
          boolean:
    """
    return await _send_telegram_media_action(
        _send_audio,
        "audio",
        chat_id,
        file_path,
        caption=caption,
        duration=duration,
        performer=performer,
        title=title,
        thumbnail_path=thumbnail_path,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=message_thread_id,
        parse_mode=parse_mode,
        business_connection_id=business_connection_id,
        direct_messages_topic_id=direct_messages_topic_id,
        receiver_user_id=receiver_user_id,
        callback_query_id=callback_query_id,
        disable_notification=disable_notification,
        protect_content=protect_content,
        allow_paid_broadcast=allow_paid_broadcast,
        message_effect_id=message_effect_id,
    )


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_telegram_document(
    chat_id: str,
    file_path: str,
    caption: str | None = None,
    thumbnail_path: str | None = None,
    disable_content_type_detection: bool | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Telegram Document
    description: Send a local file as a Telegram document via multipart/form-data.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
      file_path:
        name: File Path
        description: Local document path under /media or local/.
        required: true
        selector:
          text:
      caption:
        name: Caption
        description: Optional document caption, up to 1024 characters.
        selector:
          text:
      thumbnail_path:
        name: Thumbnail Path
        description: Optional JPEG thumbnail under /media or local/ (max 200 kB and 320 px).
        selector:
          text:
      disable_content_type_detection:
        name: Disable Content Type Detection
        description: Disable automatic content type detection for the uploaded file.
        selector:
          boolean:
      reply_to_message_id:
        name: Reply To Message ID
        description: Optional message ID to reply to.
        selector:
          number:
            min: 1
            step: 1
      message_thread_id:
        name: Message Thread ID
        description: Optional forum topic/thread ID.
        selector:
          number:
            min: 1
            step: 1
      parse_mode:
        name: Parse Mode
        description: Format entities in the caption.
        selector:
          select:
            mode: dropdown
            options:
              - HTML
              - MarkdownV2
              - Markdown
      disable_notification:
        name: Disable Notification
        description: Send the document silently.
        selector:
          boolean:
      protect_content:
        name: Protect Content
        description: Prevent forwarding and saving.
        selector:
          boolean:
      allow_paid_broadcast:
        name: Allow Paid Broadcast
        description: Allow paid high-rate broadcasting.
        selector:
          boolean:
    """
    return await _send_telegram_media_action(
        _send_document,
        "document",
        chat_id,
        file_path,
        caption=caption,
        thumbnail_path=thumbnail_path,
        disable_content_type_detection=disable_content_type_detection,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=message_thread_id,
        parse_mode=parse_mode,
        business_connection_id=business_connection_id,
        direct_messages_topic_id=direct_messages_topic_id,
        receiver_user_id=receiver_user_id,
        callback_query_id=callback_query_id,
        disable_notification=disable_notification,
        protect_content=protect_content,
        allow_paid_broadcast=allow_paid_broadcast,
        message_effect_id=message_effect_id,
    )


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_telegram_video(
    chat_id: str,
    file_path: str,
    caption: str | None = None,
    duration: int | None = None,
    width: int | None = None,
    height: int | None = None,
    thumbnail_path: str | None = None,
    cover_path: str | None = None,
    start_timestamp: int | None = None,
    show_caption_above_media: bool | None = None,
    has_spoiler: bool | None = None,
    supports_streaming: bool | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Telegram Video
    description: Send a local MPEG-4 video via Telegram multipart/form-data.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
      file_path:
        name: File Path
        description: Local video path under /media or local/.
        required: true
        selector:
          text:
      caption:
        name: Caption
        description: Optional video caption, up to 1024 characters.
        selector:
          text:
      duration:
        name: Duration
        description: Optional duration in seconds.
        selector:
          number:
            min: 0
            step: 1
      width:
        name: Width
        description: Optional video width in pixels.
        selector:
          number:
            min: 0
            step: 1
      height:
        name: Height
        description: Optional video height in pixels.
        selector:
          number:
            min: 0
            step: 1
      thumbnail_path:
        name: Thumbnail Path
        description: Optional JPEG thumbnail under /media or local/ (max 200 kB and 320 px).
        selector:
          text:
      cover_path:
        name: Cover Path
        description: Optional video cover under /media or local/.
        selector:
          text:
      start_timestamp:
        name: Start Timestamp
        description: Optional start timestamp in seconds.
        selector:
          number:
            min: 0
            step: 1
      show_caption_above_media:
        name: Show Caption Above Media
        description: Show the caption above the video.
        selector:
          boolean:
      has_spoiler:
        name: Has Spoiler
        description: Cover the video with a spoiler animation.
        selector:
          boolean:
      supports_streaming:
        name: Supports Streaming
        description: Mark the uploaded video as suitable for streaming.
        selector:
          boolean:
      reply_to_message_id:
        name: Reply To Message ID
        description: Optional message ID to reply to.
        selector:
          number:
            min: 1
            step: 1
      message_thread_id:
        name: Message Thread ID
        description: Optional forum topic/thread ID.
        selector:
          number:
            min: 1
            step: 1
      parse_mode:
        name: Parse Mode
        description: Format entities in the caption.
        selector:
          select:
            mode: dropdown
            options:
              - HTML
              - MarkdownV2
              - Markdown
      disable_notification:
        name: Disable Notification
        description: Send the video silently.
        selector:
          boolean:
      protect_content:
        name: Protect Content
        description: Prevent forwarding and saving.
        selector:
          boolean:
      allow_paid_broadcast:
        name: Allow Paid Broadcast
        description: Allow paid high-rate broadcasting.
        selector:
          boolean:
    """
    return await _send_telegram_media_action(
        _send_video,
        "video",
        chat_id,
        file_path,
        caption=caption,
        duration=duration,
        width=width,
        height=height,
        thumbnail_path=thumbnail_path,
        cover_path=cover_path,
        start_timestamp=start_timestamp,
        show_caption_above_media=show_caption_above_media,
        has_spoiler=has_spoiler,
        supports_streaming=supports_streaming,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=message_thread_id,
        parse_mode=parse_mode,
        business_connection_id=business_connection_id,
        direct_messages_topic_id=direct_messages_topic_id,
        receiver_user_id=receiver_user_id,
        callback_query_id=callback_query_id,
        disable_notification=disable_notification,
        protect_content=protect_content,
        allow_paid_broadcast=allow_paid_broadcast,
        message_effect_id=message_effect_id,
    )


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_telegram_voice(
    chat_id: str,
    file_path: str,
    caption: str | None = None,
    duration: int | None = None,
    reply_to_message_id: int | None = None,
    message_thread_id: int | None = None,
    parse_mode: str | None = None,
    business_connection_id: str | None = None,
    direct_messages_topic_id: int | None = None,
    receiver_user_id: int | None = None,
    callback_query_id: str | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Telegram Voice
    description: Send a local OGG/Opus, MP3, or M4A voice message via Telegram multipart/form-data.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
      file_path:
        name: File Path
        description: Local voice path under /media or local/.
        required: true
        selector:
          text:
      caption:
        name: Caption
        description: Optional voice caption, up to 1024 characters.
        selector:
          text:
      duration:
        name: Duration
        description: Optional duration in seconds.
        selector:
          number:
            min: 0
            step: 1
      reply_to_message_id:
        name: Reply To Message ID
        description: Optional message ID to reply to.
        selector:
          number:
            min: 1
            step: 1
      message_thread_id:
        name: Message Thread ID
        description: Optional forum topic/thread ID.
        selector:
          number:
            min: 1
            step: 1
      parse_mode:
        name: Parse Mode
        description: Format entities in the caption.
        selector:
          select:
            mode: dropdown
            options:
              - HTML
              - MarkdownV2
              - Markdown
      disable_notification:
        name: Disable Notification
        description: Send the voice message silently.
        selector:
          boolean:
      protect_content:
        name: Protect Content
        description: Prevent forwarding and saving.
        selector:
          boolean:
      allow_paid_broadcast:
        name: Allow Paid Broadcast
        description: Allow paid high-rate broadcasting.
        selector:
          boolean:
    """
    return await _send_telegram_media_action(
        _send_voice,
        "voice message",
        chat_id,
        file_path,
        caption=caption,
        duration=duration,
        reply_to_message_id=reply_to_message_id,
        message_thread_id=message_thread_id,
        parse_mode=parse_mode,
        business_connection_id=business_connection_id,
        direct_messages_topic_id=direct_messages_topic_id,
        receiver_user_id=receiver_user_id,
        callback_query_id=callback_query_id,
        disable_notification=disable_notification,
        protect_content=protect_content,
        allow_paid_broadcast=allow_paid_broadcast,
        message_effect_id=message_effect_id,
    )

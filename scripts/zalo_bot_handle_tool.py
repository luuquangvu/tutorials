import asyncio
import contextlib
import mimetypes
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
import orjson
from homeassistant.helpers import network

DIRECTORY = "/media/zalo"
WWW_DIRECTORY = "/config/www/zalo"
TOKEN = pyscript.config.get("zalo_bot_token")  # noqa: F821
if TOKEN:
    TOKEN = TOKEN.strip()

_session: aiohttp.ClientSession | None = None


if not TOKEN:
    raise ValueError("Zalo bot token is missing")


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


async def _ensure_session() -> aiohttp.ClientSession:
    """Create or return a shared aiohttp ClientSession."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300))
    return _session


async def _ensure_dir(path: str) -> None:
    """Ensure a directory exists, creating it if necessary."""
    await asyncio.to_thread(os.makedirs, path, exist_ok=True)


@pyscript_compile  # noqa: F821
def _open_file(path: str, mode: str):
    """Safely open a file using native Python."""
    return open(path, mode)


@pyscript_compile  # noqa: F821
def _cleanup_disk_sync(directory: str, cutoff: float) -> None:
    """Remove files from a directory older than a specified cutoff time."""
    path = Path(directory)
    if not path.exists():
        return

    for entry in path.iterdir():
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink()
        except OSError:
            pass


async def _cleanup_old_files(directory: str, days: int = 30) -> None:
    """Delete local files older than the specified number of days."""
    now = time.time()
    cutoff = now - (days * 86400)
    await asyncio.to_thread(_cleanup_disk_sync, directory, cutoff)


async def _download_file(
    session: aiohttp.ClientSession, url: str
) -> tuple[str, None] | tuple[None, str]:
    """Download a file from a URL and save it locally."""
    try:
        resp = await session.get(url)
        async with resp:
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "")
            ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""

            parsed_url = urlparse(url)
            original_name = Path(parsed_url.path).name
            if not Path(original_name).suffix and ext:
                original_name += ext

            base, extension = os.path.splitext(original_name)
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            file_name = f"{base}_{timestamp}_{secrets.token_hex(4)}{extension}"

            file_path = os.path.join(DIRECTORY, file_name)

            f = await asyncio.to_thread(_open_file, file_path, "wb")
            try:
                while True:
                    chunk = await resp.content.read(65536)
                    if not chunk:
                        break
                    await asyncio.to_thread(f.write, chunk)
                await asyncio.to_thread(f.flush)
                await asyncio.to_thread(os.fsync, f.fileno())
            finally:
                await asyncio.to_thread(f.close)

            return file_path, None
    except (aiohttp.ClientError, OSError) as error:
        return None, f"Download failed: {error}"


async def _send_message(
    session: aiohttp.ClientSession, chat_id: str, message: str
) -> dict[str, Any]:
    """Send a text message via the Zalo Bot API."""
    url = f"https://bot-api.zapps.me/bot{TOKEN}/sendMessage"
    text = message
    if len(text) > 2000:
        text = text[:1997] + "..."
    payload = {"chat_id": chat_id, "text": text}
    data = orjson.dumps(payload).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(content_type=None, loads=orjson.loads)


async def _send_photo(
    session: aiohttp.ClientSession,
    chat_id: str,
    photo_url: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """Send a photo to a Zalo chat using a public URL."""
    url = f"https://bot-api.zapps.me/bot{TOKEN}/sendPhoto"
    payload: dict[str, Any] = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        payload["caption"] = caption
    data = orjson.dumps(payload).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(content_type=None, loads=orjson.loads)


async def _get_webhook_info(session: aiohttp.ClientSession) -> dict[str, Any]:
    """Retrieve current Zalo webhook status."""
    url = f"https://bot-api.zapps.me/bot{TOKEN}/getWebhookInfo"
    resp = await session.get(url)
    async with resp:
        resp.raise_for_status()
        return await resp.json(content_type=None, loads=orjson.loads)


async def _set_webhook(
    session: aiohttp.ClientSession, base_url: str, webhook_id: str
) -> dict[str, Any]:
    """Configure the Zalo bot webhook URL."""
    url = f"https://bot-api.zapps.me/bot{TOKEN}/setWebhook"
    params = {
        "url": f"{base_url}/api/webhook/{webhook_id}",
        "secret_token": secrets.token_urlsafe(),
    }
    data = orjson.dumps(params).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(content_type=None, loads=orjson.loads)


async def _delete_webhook(session: aiohttp.ClientSession) -> dict[str, Any]:
    """Remove the Zalo bot webhook configuration."""
    url = f"https://bot-api.zapps.me/bot{TOKEN}/deleteWebhook"
    resp = await session.get(url)
    async with resp:
        resp.raise_for_status()
        return await resp.json(content_type=None, loads=orjson.loads)


async def _get_updates(
    session: aiohttp.ClientSession, timeout: int = 30
) -> dict[str, Any]:
    """Fetch updates from Zalo using long polling."""
    url = f"https://bot-api.zapps.me/bot{TOKEN}/getUpdates"
    payload = {"timeout": timeout}
    data = orjson.dumps(payload).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(content_type=None, loads=orjson.loads)


async def _get_me(session: aiohttp.ClientSession) -> dict[str, Any]:
    """Retrieve basic Zalo bot account information."""
    url = f"https://bot-api.zapps.me/bot{TOKEN}/getMe"
    resp = await session.get(url)
    async with resp:
        resp.raise_for_status()
        return await resp.json(content_type=None, loads=orjson.loads)


async def _send_chat_action(
    session: aiohttp.ClientSession, chat_id: str, action: str = "typing"
) -> dict[str, Any]:
    """Broadcast a chat action status to a Zalo conversation."""
    url = f"https://bot-api.zapps.me/bot{TOKEN}/sendChatAction"
    params = {"chat_id": chat_id, "action": action}
    data = orjson.dumps(params).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(content_type=None, loads=orjson.loads)


async def _copy_to_www(file_path: str) -> tuple[str, str]:
    """Temporarily copy a media file to the public www directory."""
    normalized = _to_media_path(file_path)
    file_exists = await asyncio.to_thread(os.path.isfile, normalized)
    if not file_exists:
        raise FileNotFoundError(f"File not found: {normalized}")
    external = _external_url()
    if not external:
        raise ValueError("The external Home Assistant URL is not found or incorrect.")
    await _ensure_dir(WWW_DIRECTORY)

    name = f"{secrets.token_urlsafe(16)}-{Path(normalized).name}"
    dest_path = os.path.join(WWW_DIRECTORY, name)

    await asyncio.to_thread(shutil.copyfile, normalized, dest_path)

    public_url = f"{external}/local/zalo/{name}"
    return public_url, dest_path


async def _remove_file(path: str) -> None:
    """Safely delete a file if it exists."""
    with contextlib.suppress(FileNotFoundError):
        await asyncio.to_thread(os.remove, path)


async def _delayed_remove(path: str, delay_seconds: int = 30) -> None:
    """Schedule a file for deletion after a specified delay."""
    await asyncio.sleep(delay_seconds)
    await _remove_file(path)


def _internal_url() -> str | None:
    """Return the internal Home Assistant base URL."""
    try:
        return network.get_url(hass, allow_external=False)  # noqa: F821
    except network.NoURLAvailableError:
        return None


def _external_url() -> str | None:
    """Return the external HTTPS Home Assistant base URL."""
    try:
        return network.get_url(
            hass,  # noqa: F821
            allow_internal=False,
            allow_ip=False,
            require_ssl=True,
            require_standard_port=True,
        )
    except network.NoURLAvailableError:
        return None


@time_trigger("shutdown")  # noqa: F821
async def _close_session() -> None:
    """Close the shared ClientSession on service shutdown."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


@time_trigger("cron(0 0 * * *)")  # noqa: F821
async def _daily_cleanup() -> None:
    """Perform daily cleanup of archived media and public files."""
    await _cleanup_old_files(DIRECTORY, days=30)
    await _cleanup_old_files(WWW_DIRECTORY, days=1)


@service(supports_response="only")  # noqa: F821
async def send_zalo_message(chat_id: str, message: str) -> dict[str, Any]:
    """
    yaml
    name: Send Zalo Message
    description: Send a plain text message to a Zalo chat via your bot.
    fields:
      chat_id:
        name: Chat ID
        description: Target chat ID.
        required: true
        selector:
          text:
      message:
        name: Message
        description: Message text (up to ~2000 chars).
        example: Hello from Home Assistant
        required: true
        selector:
          text:
    """
    if not all([chat_id, message]):
        return {"error": "Missing one or more required arguments: chat_id, message"}
    try:
        session = await _ensure_session()
        response = await _send_message(session, chat_id, message)
        if not response:
            return {"error": "Failed to send message"}
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def get_zalo_file(url: str) -> dict[str, Any]:
    """
    yaml
    name: Get Zalo File
    description: Download a file by direct URL and save it under Home Assistant media; returns a local path and file type.
    fields:
      url:
        name: URL
        description: Direct file URL (e.g., from a Zalo attachment).
        required: true
        selector:
          text:
    """
    if not url:
        return {"error": "Missing a required argument: url"}
    try:
        session = await _ensure_session()
        await _ensure_dir(DIRECTORY)

        file_path, error = await _download_file(session, url)
        if not file_path:
            return {"error": f"Unable to download the file from Zalo. {error}"}

        mimetypes.add_type("text/plain", ".yaml")
        mime_type, _ = mimetypes.guess_file_type(file_path)
        file_path = _to_relative_path(file_path)
        response: dict[str, Any] = {"file_path": file_path, "mime_type": mime_type}
        support_file_types = (
            "image/",
            "video/",
            "audio/",
            "text/",
            "application/pdf",
        )
        if mime_type and mime_type.startswith(support_file_types):
            response["supported"] = True
        else:
            response["supported"] = False
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def get_zalo_webhook() -> dict[str, Any]:
    """
    yaml
    name: Get Zalo Bot Webhook
    description: Retrieve current webhook configuration and status.
    """
    try:
        session = await _ensure_session()
        return await _get_webhook_info(session)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def set_zalo_webhook(webhook_id: str | None = None) -> dict[str, Any]:
    """
    yaml
    name: Set Zalo Bot Webhook
    description: Configure the HTTPS webhook endpoint for your Zalo bot.
    fields:
      webhook_id:
        name: Webhook ID
        description: Optional custom path suffix for /api/webhook; leave empty to auto-generate.
        selector:
          text:
    """
    try:
        if not webhook_id:
            webhook_id = secrets.token_urlsafe()
        external_url = _external_url()
        if not external_url:
            return {
                "error": "The external Home Assistant URL is not found or incorrect."
            }
        session = await _ensure_session()
        response = await _set_webhook(session, external_url, webhook_id)
        if isinstance(response, dict) and response.get("ok"):
            response["webhook_id"] = webhook_id
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def delete_zalo_webhook() -> dict[str, Any]:
    """
    yaml
    name: Delete Zalo Bot Webhook
    description: Remove the webhook configuration and stop webhook delivery.
    """
    try:
        session = await _ensure_session()
        return await _delete_webhook(session)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def get_zalo_updates(timeout: int = 30) -> dict[str, Any]:
    """
    yaml
    name: Get Zalo Updates
    description: Fetch new messages via long polling (use when no webhook).
    fields:
      timeout:
        name: Timeout
        description: Server wait time before responding.
        selector:
          number:
            min: 30
            max: 120
            step: 1
        default: 30
    """
    try:
        session = await _ensure_session()
        response = await _get_updates(session, timeout=timeout)
        if not response:
            return {
                "ok": True,
                "result": [],
                "description": "No updates found. Please send a message to the bot first to ensure there is data to retrieve.",
            }
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def get_zalo_bot_info() -> dict[str, Any]:
    """
    yaml
    name: Get Zalo Bot Information
    description: Get basic bot profile and status.
    """
    try:
        session = await _ensure_session()
        return await _get_me(session)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def send_zalo_chat_action(chat_id: str) -> dict[str, Any]:
    """
    yaml
    name: Send Zalo Chat Action
    description: Show a 'typing' indicator in the chat.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
    """
    if not chat_id:
        return {"error": "Missing a required argument: chat_id"}
    try:
        session = await _ensure_session()
        response = await _send_chat_action(session, chat_id)
        if not response:
            return {"error": "Failed to send message"}
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def send_zalo_photo(
    chat_id: str,
    file_path: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Zalo Photo
    description: Send a local image by temporarily publishing it to /local/zalo and posting its URL to Zalo; the published file is deleted after a successful send.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the conversation (user or group).
        required: true
        selector:
          text:
      file_path:
        name: File Path
        description: Local image path under /media or local/; the file is copied to /config/www/zalo temporarily.
        required: true
        selector:
          text:
      caption:
        name: Caption
        description: Optional text shown under the photo.
        selector:
          text:
    """
    if not all([chat_id, file_path]):
        return {"error": "Missing one or more required arguments: chat_id, file_path"}
    published_path = None
    try:
        session = await _ensure_session()
        public_url, published_path = await _copy_to_www(file_path)
        response = await _send_photo(session, chat_id, public_url, caption=caption)
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}
    finally:
        if published_path:
            task.create(_delayed_remove, published_path, 30)  # noqa: F821

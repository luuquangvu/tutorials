import asyncio
import contextlib
import ipaddress
import mimetypes
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import orjson
from homeassistant.helpers import network

DIRECTORY = "/media/zalo"
WWW_DIRECTORY = "/config/www/zalo"
TOKEN = pyscript.config.get("zalo_bot_token")  # noqa: F821  # ty:ignore[unresolved-reference]
if TOKEN:
    TOKEN = TOKEN.strip()

_session: httpx.AsyncClient | None = None
_session_lock = asyncio.Lock()


if not TOKEN:
    raise ValueError("Zalo bot token is missing")

ZALO_API_BASE_URL = f"https://bot-api.zaloplatforms.com/bot{TOKEN}"


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _create_session() -> httpx.AsyncClient:
    """Create the HTTPX client in native Python for executor-safe SSL setup."""
    return httpx.AsyncClient(http2=True, timeout=httpx.Timeout(300))


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


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _validate_download_url(url: str) -> str:
    """Allow HTTPS downloads while rejecting obvious local/private targets."""
    parsed_url = urlparse(url.strip())
    hostname = parsed_url.hostname
    if parsed_url.scheme.lower() != "https" or not hostname:
        raise ValueError("Only HTTPS URLs with a hostname are allowed")
    if parsed_url.username or parsed_url.password:
        raise ValueError("URLs containing credentials are not allowed")
    normalized_hostname = hostname.lower().rstrip(".")
    if normalized_hostname in {"localhost", "localhost.localdomain"} or normalized_hostname.endswith(
        (".local", ".localhost", ".internal")
    ):
        raise ValueError("Local and internal hostnames are not allowed")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Private and reserved IP addresses are not allowed")
    try:
        parsed_port = parsed_url.port
    except ValueError as error:
        raise ValueError("Invalid URL port") from error
    if parsed_port == 0:
        raise ValueError("Port 0 is not allowed")
    return url.strip()


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _open_file(path: str, mode: str):
    """Safely open a file using native Python."""
    return open(path, mode)


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _download_file_chunks_with_headers(url: str, original_name: str, directory: str) -> str:
    """Download a file in chunks using httpx.Client, guess the extension, and write to disk."""
    with httpx.Client(timeout=300) as client, client.stream("GET", url) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "") or ""
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""

        name = original_name
        if not Path(name).suffix and ext:
            name += ext

        base, extension = os.path.splitext(name)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        file_name = f"{base}_{timestamp}_{secrets.token_hex(4)}{extension}"
        file_path = os.path.join(directory, file_name)

        with open(file_path, "wb") as f:
            for chunk in resp.iter_bytes(65536):
                f.write(chunk)
            f.flush()
            with contextlib.suppress(OSError):
                os.fsync(f.fileno())

        return file_path


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


async def _download_file(client: httpx.AsyncClient, url: str) -> tuple[str, None] | tuple[None, str]:
    """Download a file from a URL and save it locally."""
    try:
        safe_url = _validate_download_url(url)
        parsed_url = urlparse(safe_url)
        original_name = Path(parsed_url.path).name or "zalo_file"

        file_path = await asyncio.to_thread(
            _download_file_chunks_with_headers,
            safe_url,
            original_name,
            DIRECTORY,
        )

        return file_path, None
    except Exception as error:
        return None, f"Download failed: {error}"


async def _send_message(client: httpx.AsyncClient, chat_id: str, message: str) -> dict[str, Any]:
    """Send a text message via the Zalo Bot API."""
    url = f"{ZALO_API_BASE_URL}/sendMessage"
    text = message
    if len(text) > 2000:
        text = f"{text[:1997]}..."
    payload = {"chat_id": chat_id, "text": text}
    data = orjson.dumps(payload).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _send_photo(
    client: httpx.AsyncClient,
    chat_id: str,
    photo_url: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """Send a photo to a Zalo chat using a public URL."""
    url = f"{ZALO_API_BASE_URL}/sendPhoto"
    payload: dict[str, Any] = {"chat_id": chat_id, "photo": photo_url}
    if caption:
        payload["caption"] = caption
    data = orjson.dumps(payload).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _send_sticker(
    client: httpx.AsyncClient,
    chat_id: str,
    sticker: str,
) -> dict[str, Any]:
    """Send a sticker to a Zalo chat using its sticker ID."""
    url = f"{ZALO_API_BASE_URL}/sendSticker"
    payload = {"chat_id": chat_id, "sticker": sticker}
    data = orjson.dumps(payload).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


def _validate_voice_url(url: str) -> str:
    """Validate a public AAC voice URL accepted by the Zalo Bot API."""
    safe_url = _validate_download_url(url)
    if Path(urlparse(safe_url).path).suffix.lower() != ".aac":
        raise ValueError("voice_url must reference a file with the .aac extension")
    return safe_url


async def _send_voice(
    client: httpx.AsyncClient,
    chat_id: str,
    voice_url: str,
) -> dict[str, Any]:
    """Send an AAC voice message to a one-to-one Zalo chat."""
    url = f"{ZALO_API_BASE_URL}/sendVoice"
    payload = {"chat_id": chat_id, "voice_url": voice_url}
    data = orjson.dumps(payload).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _get_webhook_info(client: httpx.AsyncClient) -> dict[str, Any]:
    """Retrieve current Zalo webhook status."""
    url = f"{ZALO_API_BASE_URL}/getWebhookInfo"
    resp = await client.post(url, json={})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _set_webhook(
    client: httpx.AsyncClient,
    base_url: str,
    webhook_id: str,
    secret_token: str,
) -> dict[str, Any]:
    """Configure the Zalo bot webhook URL."""
    url = f"{ZALO_API_BASE_URL}/setWebhook"
    params = {
        "url": f"{base_url}/api/webhook/{webhook_id}",
        "secret_token": secret_token,
    }
    data = orjson.dumps(params).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _test_webhook(client: httpx.AsyncClient) -> dict[str, Any]:
    """Test whether the configured Zalo webhook can receive a request."""
    url = f"{ZALO_API_BASE_URL}/testWebhook"
    resp = await client.post(url, json={})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _delete_webhook(client: httpx.AsyncClient) -> dict[str, Any]:
    """Remove the Zalo bot webhook configuration."""
    url = f"{ZALO_API_BASE_URL}/deleteWebhook"
    resp = await client.post(url, json={})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _get_updates(client: httpx.AsyncClient, timeout: int = 30) -> dict[str, Any]:
    """Fetch updates from Zalo using long polling."""
    url = f"{ZALO_API_BASE_URL}/getUpdates"
    payload = {"timeout": timeout}
    data = orjson.dumps(payload).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _get_me(client: httpx.AsyncClient) -> dict[str, Any]:
    """Retrieve basic Zalo bot account information."""
    url = f"{ZALO_API_BASE_URL}/getMe"
    resp = await client.post(url, json={})
    resp.raise_for_status()
    return orjson.loads(resp.content)


async def _send_chat_action(client: httpx.AsyncClient, chat_id: str, action: str = "typing") -> dict[str, Any]:
    """Broadcast a chat action status to a Zalo conversation."""
    url = f"{ZALO_API_BASE_URL}/sendChatAction"
    params = {"chat_id": chat_id, "action": action}
    data = orjson.dumps(params).decode("utf-8")
    resp = await client.post(url, content=data, headers={"Content-Type": "application/json"})
    resp.raise_for_status()
    return orjson.loads(resp.content)


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


@time_trigger("shutdown")  # noqa: F821  # ty:ignore[unresolved-reference]
async def _close_session() -> None:
    """Close the shared AsyncClient on service shutdown."""
    global _session
    if _session and not _session.is_closed:
        await _session.aclose()
        _session = None


@time_trigger("cron(0 0 * * *)")  # noqa: F821  # ty:ignore[unresolved-reference]
async def _daily_cleanup() -> None:
    """Perform daily cleanup of archived media and public files."""
    await _cleanup_old_files(DIRECTORY, days=30)
    await _cleanup_old_files(WWW_DIRECTORY, days=1)


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
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
        client = await _ensure_session()
        response = await _send_message(client, chat_id, message)
        return response or {"error": "Failed to send message"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def get_zalo_file(url: str) -> dict[str, Any]:
    """
    yaml
    name: Get Zalo File
    description: >-
      Download a file by direct URL and save it under Home Assistant media; returns a local path and file type.
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
        client = await _ensure_session()
        await _ensure_dir(DIRECTORY)

        file_path, error = await _download_file(client, url)
        if not file_path:
            return {"error": f"Unable to download the file from Zalo. {error}"}

        mimetypes.add_type("text/plain", ".yaml")
        mime_type, _ = mimetypes.guess_file_type(file_path)
        file_path = _to_relative_path(file_path)
        support_file_types = (
            "image/",
            "video/",
            "audio/",
            "text/",
            "application/pdf",
        )
        response: dict[str, Any] = {
            "file_path": file_path,
            "mime_type": mime_type,
            "supported": bool(mime_type and mime_type.startswith(support_file_types)),
        }
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def get_zalo_webhook() -> dict[str, Any]:
    """
    yaml
    name: Get Zalo Bot Webhook
    description: Retrieve current webhook configuration and status.
    """
    try:
        client = await _ensure_session()
        return await _get_webhook_info(client)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def test_zalo_webhook() -> dict[str, Any]:
    """
    yaml
    name: Test Zalo Bot Webhook
    description: >-
      Immediately test whether the configured Zalo webhook responds successfully.
      Check result.ok in the response; the outer ok only indicates that the API call succeeded.
    """
    try:
        client = await _ensure_session()
        return await _test_webhook(client)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
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
            webhook_id: str = secrets.token_urlsafe(32)
        external_url = _external_url()
        if not external_url:
            return {"error": "The external Home Assistant URL is not found or incorrect."}
        selected_secret = secrets.token_urlsafe(32)
        client = await _ensure_session()
        response = await _set_webhook(client, external_url, webhook_id, selected_secret)
        if isinstance(response, dict) and response.get("ok"):
            response["webhook_id"] = webhook_id
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def delete_zalo_webhook() -> dict[str, Any]:
    """
    yaml
    name: Delete Zalo Bot Webhook
    description: Remove the webhook configuration and stop webhook delivery.
    """
    try:
        client = await _ensure_session()
        return await _delete_webhook(client)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
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
        client = await _ensure_session()
        response = await _get_updates(client, timeout=timeout)
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
async def get_zalo_bot_info() -> dict[str, Any]:
    """
    yaml
    name: Get Zalo Bot Information
    description: Get basic bot profile and status.
    """
    try:
        client = await _ensure_session()
        return await _get_me(client)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
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
        client = await _ensure_session()
        response = await _send_chat_action(client, chat_id)
        return response or {"error": "Failed to send message"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_zalo_photo(
    chat_id: str,
    file_path: str,
    caption: str | None = None,
) -> dict[str, Any]:
    """
    yaml
    name: Send Zalo Photo
    description: >-
      Send a local image by temporarily publishing it to /local/zalo and posting its URL to Zalo;
      the published file is deleted after a successful send.
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
        client = await _ensure_session()
        public_url, published_path = await _copy_to_www(file_path)
        return await _send_photo(client, chat_id, public_url, caption=caption)
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}
    finally:
        if published_path:
            task.create(_delayed_remove, published_path, 30)  # noqa: F821  # ty:ignore[unresolved-reference]


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_zalo_sticker(chat_id: str, sticker: str) -> dict[str, Any]:
    """
    yaml
    name: Send Zalo Sticker
    description: Send a sticker to a Zalo user or conversation by sticker ID.
    fields:
      chat_id:
        name: Chat ID
        description: ID of the recipient or conversation.
        required: true
        selector:
          text:
      sticker:
        name: Sticker ID
        description: Sticker ID obtained from stickers.zaloapp.com.
        required: true
        selector:
          text:
    """
    if not all([chat_id, sticker]):
        return {"error": "Missing one or more required arguments: chat_id, sticker"}
    try:
        client = await _ensure_session()
        response = await _send_sticker(client, chat_id, sticker)
        return response or {"error": "Failed to send sticker"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821  # ty:ignore[unresolved-reference]
async def send_zalo_voice(chat_id: str, voice_url: str) -> dict[str, Any]:
    """
    yaml
    name: Send Zalo Voice
    description: >-
      Send an AAC voice message from a public HTTPS URL to a one-to-one Zalo chat.
      Group chats are not supported by the Zalo API.
    fields:
      chat_id:
        name: Chat ID
        description: One-to-one recipient ID; group chats are not supported.
        required: true
        selector:
          text:
      voice_url:
        name: Voice URL
        description: Public HTTPS URL for an AAC audio file with a .aac extension.
        required: true
        selector:
          text:
    """
    if not all([chat_id, voice_url]):
        return {"error": "Missing one or more required arguments: chat_id, voice_url"}
    try:
        safe_voice_url = _validate_voice_url(voice_url)
    except ValueError as error:
        return {"error": f"Invalid voice_url: {error}"}
    try:
        client = await _ensure_session()
        response = await _send_voice(client, chat_id, safe_voice_url)
        return response or {"error": "Failed to send voice message"}
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}

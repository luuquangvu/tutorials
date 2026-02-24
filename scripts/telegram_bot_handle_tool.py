import asyncio
import mimetypes
import os
import secrets
import time
from pathlib import Path
from typing import Any

import aiohttp
import orjson
from homeassistant.helpers import network

DIRECTORY = "/media/telegram"
TOKEN = pyscript.config.get("telegram_bot_token")  # noqa: F821
if TOKEN:
    TOKEN = TOKEN.strip()

_session: aiohttp.ClientSession | None = None


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


async def _get_file(session: aiohttp.ClientSession, file_id: str) -> str | None:
    """Resolve a Telegram file identifier to its server path."""
    url = f"https://api.telegram.org/bot{TOKEN}/getFile"
    payload = {"file_id": file_id}
    data = orjson.dumps(payload).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        data = await resp.json(loads=orjson.loads)
    return data.get("result", {}).get("file_path")


async def _download_file(
    session: aiohttp.ClientSession, file_id: str
) -> tuple[str, None] | tuple[None, str]:
    """Download a file from Telegram and save it locally."""
    try:
        online_file_path = await _get_file(session, file_id)
        if not online_file_path:
            return None, "Unable to retrieve the file_path from Telegram."

        url = f"https://api.telegram.org/file/bot{TOKEN}/{online_file_path}"
        resp = await session.get(url)
        async with resp:
            resp.raise_for_status()

            file_name = os.path.basename(online_file_path)
            base, ext = os.path.splitext(file_name)
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            file_name = f"{base}_{timestamp}_{secrets.token_hex(4)}{ext}"

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
    session: aiohttp.ClientSession,
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
        text = text[:4093] + "..."
    payload = {"chat_id": chat_id, "text": text}
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    if message_thread_id:
        payload["message_thread_id"] = message_thread_id
    if parse_mode:
        if parse_mode not in PARSE_MODES:
            raise ValueError(
                f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}"
            )
        payload["parse_mode"] = parse_mode
    data = orjson.dumps(payload).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(loads=orjson.loads)


async def _send_photo(
    session: aiohttp.ClientSession,
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

    form = aiohttp.FormData()
    form.add_field("chat_id", str(chat_id))
    if caption:
        form.add_field("caption", caption[:1024])
    if parse_mode:
        if parse_mode not in PARSE_MODES:
            raise ValueError(
                f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}"
            )
        form.add_field("parse_mode", parse_mode)
    if reply_to_message_id:
        form.add_field("reply_to_message_id", str(reply_to_message_id))
    if message_thread_id:
        form.add_field("message_thread_id", str(message_thread_id))

    f = await asyncio.to_thread(_open_file, file_path, "rb")
    try:
        form.add_field(
            name="photo",
            value=f,
            filename=filename,
            content_type=content_type,
        )

        url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        resp = await session.post(url, data=form)
        async with resp:
            resp.raise_for_status()
            return await resp.json(loads=orjson.loads)
    finally:
        await asyncio.to_thread(f.close)


async def _get_webhook_info(session: aiohttp.ClientSession) -> dict[str, Any]:
    """Retrieve current Telegram webhook status."""
    url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
    resp = await session.get(url)
    async with resp:
        resp.raise_for_status()
        return await resp.json(loads=orjson.loads)


async def _set_webhook(
    session: aiohttp.ClientSession, base_url: str, webhook_id: str
) -> dict[str, Any]:
    """Configure the Telegram webhook URL."""
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    params = {
        "url": f"{base_url}/api/webhook/{webhook_id}",
        "drop_pending_updates": True,
    }
    data = orjson.dumps(params).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(loads=orjson.loads)


async def _delete_webhook(session: aiohttp.ClientSession) -> dict[str, Any]:
    """Remove the Telegram webhook configuration."""
    url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    params = {"drop_pending_updates": True}
    data = orjson.dumps(params).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(loads=orjson.loads)


async def _get_updates(
    session: aiohttp.ClientSession,
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
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(loads=orjson.loads)


async def _get_me(session: aiohttp.ClientSession) -> dict[str, Any]:
    """Retrieve basic bot account information."""
    url = f"https://api.telegram.org/bot{TOKEN}/getMe"
    resp = await session.get(url)
    async with resp:
        resp.raise_for_status()
        return await resp.json(loads=orjson.loads)


async def _send_chat_action(
    session: aiohttp.ClientSession,
    chat_id: int | str,
    message_thread_id: int | None = None,
    action: str = "typing",
) -> dict[str, Any]:
    """Broadcast a chat action status to a conversation."""
    if action not in ACTIONS_CHAT:
        raise ValueError(
            f"Unsupported chat action: {action}. Allowed: {', '.join(ACTIONS_CHAT)}"
        )
    url = f"https://api.telegram.org/bot{TOKEN}/sendChatAction"
    params = {
        "chat_id": chat_id,
        "action": action,
    }
    if message_thread_id:
        params["message_thread_id"] = message_thread_id
    data = orjson.dumps(params).decode("utf-8")
    resp = await session.post(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    async with resp:
        resp.raise_for_status()
        return await resp.json(loads=orjson.loads)


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


@time_trigger("shutdown")  # noqa: F821
async def _close_session() -> None:
    """Close the shared ClientSession on service shutdown."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None


@time_trigger("cron(0 0 * * *)")  # noqa: F821
async def _daily_cleanup() -> None:
    """Perform daily cleanup of archived media files."""
    await _cleanup_old_files(DIRECTORY, days=30)


@service(supports_response="only")  # noqa: F821
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
        return {
            "error": f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}"
        }
    try:
        session = await _ensure_session()
        response = await _send_message(
            session,
            chat_id,
            message,
            reply_to_message_id=reply_to_message_id,
            message_thread_id=message_thread_id,
            parse_mode=parse_mode,
        )
        if not response:
            return {"error": "Failed to send message"}
        return response
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
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
        session = await _ensure_session()
        await _ensure_dir(DIRECTORY)

        file_path, error = await _download_file(session, file_id)
        if not file_path:
            return {"error": f"Unable to download the file from Telegram. {error}"}

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
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def get_telegram_webhook() -> dict[str, Any]:
    """
    yaml
    name: Get Telegram Bot Webhook
    description: Retrieve current webhook configuration and status.
    """
    try:
        session = await _ensure_session()
        return await _get_webhook_info(session)
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
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
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def delete_telegram_webhook() -> dict[str, Any]:
    """
    yaml
    name: Delete Telegram Bot Webhook
    description: Remove the webhook configuration and stop webhook delivery.
    """
    try:
        session = await _ensure_session()
        return await _delete_webhook(session)
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
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
        session = await _ensure_session()
        response = await _get_updates(
            session, timeout=timeout, offset=offset, limit=limit
        )
        if not response:
            return {
                "ok": True,
                "result": [],
                "description": "No updates found. Please send a message to the bot first to ensure there is data to retrieve.",
            }
        return response
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
async def get_telegram_bot_info() -> dict[str, Any]:
    """
    yaml
    name: Get Telegram Bot Information
    description: Tool for getting Telegram bot basic information.
    """
    try:
        session = await _ensure_session()
        return await _get_me(session)
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
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
        return {
            "error": f"Unsupported chat action: {action}. Allowed: {', '.join(ACTIONS_CHAT)}"
        }
    try:
        session = await _ensure_session()
        response = await _send_chat_action(
            session,
            chat_id,
            message_thread_id,
            action=action,
        )
        if not response:
            return {"error": "Failed to send message"}
        return response
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}


@service(supports_response="only")  # noqa: F821
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
        return {
            "error": f"Unsupported parse_mode: {parse_mode}. Allowed: {', '.join(PARSE_MODES)}"
        }
    try:
        session = await _ensure_session()
        response = await _send_photo(
            session,
            chat_id,
            file_path,
            caption=caption,
            reply_to_message_id=reply_to_message_id,
            message_thread_id=message_thread_id,
            parse_mode=parse_mode,
        )
        if not response:
            return {"error": "Failed to send photo"}
        return response
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}

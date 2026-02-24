import asyncio
import mimetypes
import os
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
from homeassistant.helpers import network

DIRECTORY = "/media/zalo"

_session: aiohttp.ClientSession | None = None


def _to_relative_path(path: str) -> str:
    """Convert an absolute /media/ path to a relative local/ media source path."""
    if path.startswith("/media/"):
        return "local/" + path.removeprefix("/media/")
    return path


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
async def get_zalo_file_custom_bot(url: str) -> dict[str, Any]:
    """
    yaml
    name: Get Zalo File (Custom Bot)
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
async def generate_webhook_id() -> dict[str, Any]:
    """
    yaml
    name: Generate Webhook ID
    description: Generate a unique URL-safe webhook ID and sample URLs.
    """
    try:
        webhook_id = secrets.token_urlsafe()
        internal_url = _internal_url()
        external_url = _external_url()
        response = {"webhook_id": webhook_id}
        if internal_url:
            response["sample_internal_url"] = f"{internal_url}/api/webhook/{webhook_id}"
        else:
            response["sample_internal_url"] = (
                "The internal Home Assistant URL is not found."
            )
        if external_url:
            response["sample_external_url"] = f"{external_url}/api/webhook/{webhook_id}"
        else:
            response["sample_external_url"] = (
                "The external Home Assistant URL is not found or incorrect."
            )
        return response
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821
        return {"error": f"An unexpected error occurred during processing: {error}"}

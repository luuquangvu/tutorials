import asyncio
import contextlib
import mimetypes
import os
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from homeassistant.helpers import network

DIRECTORY = "/media/zalo"

_session: httpx.AsyncClient | None = None
_session_lock = asyncio.Lock()


@pyscript_compile  # noqa: F821  # ty:ignore[unresolved-reference]
def _create_session() -> httpx.AsyncClient:
    """Create the HTTPX client in native Python for executor-safe SSL setup."""
    return httpx.AsyncClient(http2=True, timeout=httpx.Timeout(300))


def _to_relative_path(path: str) -> str:
    """Convert an absolute /media/ path to a relative local/ media source path."""
    if path.startswith("/media/"):
        return "local/" + path.removeprefix("/media/")
    return path


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
        parsed_url = urlparse(url)
        original_name = Path(parsed_url.path).name

        file_path = await asyncio.to_thread(
            _download_file_chunks_with_headers,
            url,
            original_name,
            DIRECTORY,
        )

        return file_path, None
    except Exception as error:
        return None, f"Download failed: {error}"


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
async def get_zalo_file_custom_bot(url: str) -> dict[str, Any]:
    """
    yaml
    name: Get Zalo File (Custom Bot)
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
        return {
            "webhook_id": webhook_id,
            "sample_internal_url": (
                f"{internal_url}/api/webhook/{webhook_id}"
                if internal_url
                else "The internal Home Assistant URL is not found."
            ),
            "sample_external_url": (
                f"{external_url}/api/webhook/{webhook_id}"
                if external_url
                else "The external Home Assistant URL is not found or incorrect."
            ),
        }
    except Exception as error:
        log.error(f"{__name__}: {error}")  # noqa: F821  # ty:ignore[unresolved-reference]
        return {"error": f"An unexpected error occurred during processing: {error}"}

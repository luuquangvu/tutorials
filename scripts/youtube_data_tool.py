import asyncio
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

YOUTUBE_API_KEY = pyscript.config.get("youtube_api_key")  # noqa: F821
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

YOUTUBE_CLIENT: Any = None
_YOUTUBE_LOCK = asyncio.Lock()

if not YOUTUBE_API_KEY:
    raise ValueError("You need to configure your YouTube API key")


@pyscript_compile  # noqa: F821
def _build_youtube_client() -> Any:
    """Initialize the Google API client for YouTube v3."""
    return build(
        YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY
    )


async def _ensure_youtube_client() -> None:
    """Ensure the YouTube client is initialized once using a thread lock."""
    global YOUTUBE_CLIENT
    if YOUTUBE_CLIENT is None:
        async with _YOUTUBE_LOCK:
            if YOUTUBE_CLIENT is None:
                YOUTUBE_CLIENT = await asyncio.to_thread(_build_youtube_client)


@pyscript_compile  # noqa: F821
def youtube_search(
    client: Any,
    query: str,
    results: int = 5,
    search_type: str = "video,channel,playlist",
    page_token: str = "",
) -> dict[str, Any]:
    """Execute a search query against the YouTube API."""
    search_response = (
        client.search()
        .list(
            q=query,
            part="id,snippet",
            maxResults=results,
            type=search_type,
            pageToken=page_token,
        )
        .execute()
    )

    return search_response


@service(supports_response="only")  # noqa: F821
async def youtube_search_tool(query: str, **kwargs) -> dict[str, Any]:
    """
    yaml
    name: YouTube Search Tool
    description: Search YouTube for videos, channels, and playlists.
    fields:
      query:
        name: Query
        description: Search keywords or phrase.
        example: Nikola Tesla
        required: true
        selector:
          text:
      search_type:
        name: Search Type
        description: Content types to include.
        example: video
        required: true
        selector:
          select:
            options:
              - video
              - channel
              - playlist
            multiple: true
        default:
          - video
      results:
        name: Results
        description: Maximum number of items to return (1-50).
        selector:
          number:
            min: 1
            max: 50
        default: 5
      page_token:
        name: Page Token
        description: Token for the next page of results.
        selector:
          text:
    """
    if not query:
        return {"error": "Missing a required argument: query"}

    def _coerce_results(value: Any) -> int:
        try:
            coerced = int(value)
        except (TypeError, ValueError) as err:
            raise ValueError(
                "The results value must be an integer between 1 and 50"
            ) from err
        if not 1 <= coerced <= 50:
            raise ValueError("The results value must be between 1 and 50")
        return coerced

    def _coerce_search_types(value: Any) -> list[str]:
        valid_types = {"video", "channel", "playlist"}
        if value is None:
            items: list[str] = []
        elif isinstance(value, str):
            items = [value]
        elif isinstance(value, (list, tuple, set)):
            items = [str(item) for item in value if str(item).strip()]
        else:
            raise ValueError(
                "The search_type value must be a string or list of strings"
            )

        cleaned: list[str] = []
        for item in items:
            item = item.strip().lower()  # Normalize to lowercase
            if item in valid_types and item not in cleaned:
                cleaned.append(item)

        if not cleaned:
            cleaned = ["video"]
        return cleaned

    try:
        await _ensure_youtube_client()
        results = _coerce_results(kwargs.get("results", 5))
        search_types = _coerce_search_types(kwargs.get("search_type", ["video"]))
        page_token = kwargs.get("page_token", "") or ""

        response = await asyncio.to_thread(
            youtube_search,
            YOUTUBE_CLIENT,
            query,
            results=results,
            search_type=",".join(search_types),
            page_token=page_token,
        )
        if not isinstance(response, dict):
            return {
                "error": "Unexpected response from YouTube API",
                "detail": f"Expected dict, received {type(response).__name__}",
            }
        return response
    except HttpError as error:
        return {
            "error": "YouTube API Error",
            "detail": str(error),
        }
    except Exception as error:
        return {"error": f"An unexpected error occurred during processing: {error}"}

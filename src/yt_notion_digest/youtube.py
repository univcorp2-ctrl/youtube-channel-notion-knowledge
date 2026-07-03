from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import requests

from yt_notion_digest.models import Channel, Video

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeApiError(RuntimeError):
    """Raised when the YouTube Data API returns an unusable response."""


def parse_playlist_id(source_url: str) -> str | None:
    """Extract a YouTube playlist ID from a playlist or watch URL."""
    parsed = urlparse(source_url)
    query = parse_qs(parsed.query)
    values = query.get("list")
    if values and values[0].strip():
        return values[0].strip()
    return None


def parse_channel_identity(channel_url: str) -> tuple[str, str]:
    parsed = urlparse(channel_url)
    path = parsed.path.strip("/")
    if not path and parsed.netloc in {"youtu.be", "www.youtu.be"}:
        return "unknown", channel_url

    if path.startswith("@"):  # handle URL
        return "handle", path.split("/")[0]

    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "channel":
        return "id", parts[1]
    if len(parts) >= 2 and parts[0] == "user":
        return "username", parts[1]
    if len(parts) >= 2 and parts[0] == "c":
        return "search", parts[1]
    if len(parts) == 1 and re.match(r"^UC[0-9A-Za-z_-]{20,}$", parts[0]):
        return "id", parts[0]

    query = parse_qs(parsed.query)
    if "channel_id" in query and query["channel_id"]:
        return "id", query["channel_id"][0]

    return "search", parts[-1] if parts else channel_url


class YouTubeDataClient:
    def __init__(self, api_key: str, session: requests.Session | None = None) -> None:
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is required to enumerate every public upload or playlist item.")
        self.api_key = api_key
        self.session = session or requests.Session()

    def _get(self, path: str, params: dict[str, object]) -> dict[str, object]:
        request_params = dict(params)
        request_params["key"] = self.api_key
        response = self.session.get(f"{YOUTUBE_API_BASE}{path}", params=request_params, timeout=30)
        if response.status_code >= 400:
            raise YouTubeApiError(
                f"YouTube API request failed: HTTP {response.status_code}: {response.text[:500]}"
            )
        data = response.json()
        if "error" in data:
            raise YouTubeApiError(f"YouTube API error: {data['error']}")
        return data

    def resolve_channel(self, channel_url: str) -> Channel:
        """Resolve either a channel URL or playlist URL to a collection container.

        For a playlist URL, uploads_playlist_id stores the requested playlist ID so the
        existing exhaustive playlist pagination path can be reused.
        """
        playlist_id = parse_playlist_id(channel_url)
        if playlist_id:
            return self.resolve_playlist(channel_url, playlist_id)

        kind, value = parse_channel_identity(channel_url)
        part = "snippet,contentDetails,statistics"

        if kind == "id":
            data = self._get("/channels", {"part": part, "id": value})
        elif kind == "handle":
            data = self._get("/channels", {"part": part, "forHandle": value})
        elif kind == "username":
            data = self._get("/channels", {"part": part, "forUsername": value})
        else:
            search = self._get(
                "/search", {"part": "snippet", "q": value, "type": "channel", "maxResults": 1}
            )
            items = search.get("items", [])
            if not items:
                raise YouTubeApiError(f"Could not resolve channel from URL or query: {channel_url}")
            channel_id = items[0]["snippet"]["channelId"]
            data = self._get("/channels", {"part": part, "id": channel_id})

        items = data.get("items", [])
        if not items:
            raise YouTubeApiError(f"No channel matched: {channel_url}")

        item = items[0]
        snippet = item.get("snippet", {})
        content_details = item.get("contentDetails", {})
        statistics = item.get("statistics", {})
        uploads = content_details.get("relatedPlaylists", {}).get("uploads")
        if not uploads:
            raise YouTubeApiError("Channel response did not include an uploads playlist ID.")

        return Channel(
            id=item["id"],
            title=snippet.get("title", "Untitled channel"),
            url=f"https://www.youtube.com/channel/{item['id']}",
            uploads_playlist_id=uploads,
            description=snippet.get("description", ""),
            subscriber_count=_optional_int(statistics.get("subscriberCount")),
            video_count=_optional_int(statistics.get("videoCount")),
        )

    def resolve_playlist(self, source_url: str, playlist_id: str) -> Channel:
        data = self._get(
            "/playlists",
            {"part": "snippet,contentDetails", "id": playlist_id, "maxResults": 1},
        )
        items = data.get("items", [])
        if not items:
            raise YouTubeApiError(f"No public playlist matched ID: {playlist_id}")

        item = items[0]
        snippet = item.get("snippet", {})
        details = item.get("contentDetails", {})
        owner_channel_id = snippet.get("channelId") or f"PLAYLIST:{playlist_id}"
        playlist_title = snippet.get("title", "Untitled playlist")
        return Channel(
            id=owner_channel_id,
            title=f"Playlist: {playlist_title}",
            url=source_url,
            uploads_playlist_id=playlist_id,
            description=snippet.get("description", ""),
            video_count=_optional_int(details.get("itemCount")),
        )

    def list_uploads(self, channel: Channel, max_videos: int = 0) -> list[Video]:
        videos: list[Video] = []
        page_token: str | None = None

        while True:
            params: dict[str, object] = {
                "part": "snippet,contentDetails",
                "playlistId": channel.uploads_playlist_id,
                "maxResults": 50,
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("/playlistItems", params)

            for raw in data.get("items", []):
                snippet = raw.get("snippet", {})
                resource = snippet.get("resourceId", {})
                content_details = raw.get("contentDetails", {})
                video_id = resource.get("videoId") or content_details.get("videoId")
                if not video_id:
                    continue
                videos.append(
                    Video(
                        id=video_id,
                        title=snippet.get("title", "Untitled video"),
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        published_at=content_details.get("videoPublishedAt") or snippet.get("publishedAt"),
                        description=snippet.get("description", ""),
                        channel_id=snippet.get("videoOwnerChannelId") or channel.id,
                        channel_title=snippet.get("videoOwnerChannelTitle") or channel.title,
                        position=snippet.get("position"),
                    )
                )
                if max_videos and len(videos) >= max_videos:
                    return self.enrich_videos(videos[:max_videos])

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return self.enrich_videos(videos)

    def enrich_videos(self, videos: list[Video]) -> list[Video]:
        if not videos:
            return []

        enriched_by_id: dict[str, Video] = {video.id: video for video in videos}
        for index in range(0, len(videos), 50):
            batch = videos[index : index + 50]
            data = self._get(
                "/videos",
                {
                    "part": "contentDetails,statistics,snippet",
                    "id": ",".join(video.id for video in batch),
                    "maxResults": 50,
                },
            )
            for item in data.get("items", []):
                video_id = item.get("id")
                original = enriched_by_id.get(video_id)
                if original is None:
                    continue
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})
                details = item.get("contentDetails", {})
                enriched_by_id[video_id] = replace(
                    original,
                    title=snippet.get("title", original.title),
                    description=snippet.get("description", original.description),
                    published_at=snippet.get("publishedAt", original.published_at),
                    channel_id=snippet.get("channelId", original.channel_id),
                    channel_title=snippet.get("channelTitle", original.channel_title),
                    duration=details.get("duration"),
                    view_count=_optional_int(stats.get("viewCount")),
                    like_count=_optional_int(stats.get("likeCount")),
                )

        return [enriched_by_id[video.id] for video in videos]


def _optional_int(raw: object) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# yt-dlp backend (no API key required)
# ---------------------------------------------------------------------------

def _ytdlp_date_to_iso(date_str: str | None) -> str | None:
    """Convert YYYYMMDD to ISO 8601 datetime string."""
    if not date_str or len(date_str) != 8:
        return None
    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T00:00:00Z"


def _seconds_to_iso8601_duration(seconds: int | None) -> str | None:
    """Convert integer seconds to ISO 8601 duration string (e.g. PT1H30M5S)."""
    if seconds is None:
        return None
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    result = "PT"
    if h:
        result += f"{h}H"
    if m:
        result += f"{m}M"
    result += f"{s}S"
    return result


class YtDlpClient:
    """YouTube client using yt-dlp instead of the YouTube Data API.

    No API key required. Works for any public channel, playlist, or video URL.
    Provides the same interface as YouTubeDataClient.
    """

    def __init__(self, quiet: bool = True) -> None:
        self.quiet = quiet
        self._info_cache: dict[str, dict] = {}

    def _extract_info(self, url: str, flat: bool = True, max_videos: int = 0) -> dict:
        import yt_dlp  # optional dependency

        ydl_opts: dict = {
            "quiet": self.quiet,
            "no_warnings": self.quiet,
            "extract_flat": "in_playlist" if flat else False,
            "ignoreerrors": True,
        }
        if max_videos:
            ydl_opts["playlistend"] = max_videos

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False) or {}

    @staticmethod
    def _videos_url(channel_url: str) -> str:
        """Return the /videos tab URL for a channel, preserving playlist URLs."""
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(channel_url)
        if parse_qs(parsed.query).get("list"):
            return channel_url  # playlist URL — don't modify
        url = channel_url.rstrip("/")
        if not url.endswith("/videos"):
            url += "/videos"
        return url

    def resolve_channel(self, channel_url: str) -> Channel:
        videos_url = self._videos_url(channel_url)
        info = self._extract_info(videos_url, flat=True, max_videos=1)

        channel_id = (
            info.get("channel_id")
            or info.get("uploader_id")
            or info.get("id")
            or "unknown"
        )
        channel_title = (
            info.get("channel")
            or info.get("uploader")
            or info.get("title")
            or "Unknown Channel"
        )
        # Canonical channel URL (without /videos suffix)
        canonical_url = info.get("webpage_url") or channel_url
        if canonical_url.endswith("/videos"):
            canonical_url = canonical_url[: -len("/videos")]

        return Channel(
            id=channel_id,
            title=channel_title,
            url=canonical_url,
            uploads_playlist_id=channel_id,  # placeholder; not used by YtDlpClient.list_uploads
            description=info.get("description") or "",
            subscriber_count=_optional_int(info.get("channel_follower_count")),
            video_count=_optional_int(info.get("playlist_count")),
        )

    def list_uploads(self, channel: Channel, max_videos: int = 0) -> list[Video]:
        # Always use the /videos tab to get individual video entries
        videos_url = self._videos_url(channel.url)
        cache_key = channel.url
        if cache_key in self._info_cache and max_videos == 0:
            info = self._info_cache[cache_key]
        else:
            info = self._extract_info(videos_url, flat=True, max_videos=max_videos)

        entries = info.get("entries") or []
        videos: list[Video] = []

        for i, entry in enumerate(entries):
            if not entry:
                continue
            video_id = entry.get("id") or ""
            if not video_id:
                continue

            raw_duration = entry.get("duration")
            duration_iso = _seconds_to_iso8601_duration(
                int(raw_duration) if raw_duration is not None else None
            )
            videos.append(
                Video(
                    id=video_id,
                    title=entry.get("title") or "Untitled video",
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    published_at=_ytdlp_date_to_iso(entry.get("upload_date")),
                    description=entry.get("description") or "",
                    channel_id=entry.get("channel_id") or channel.id,
                    channel_title=entry.get("channel") or channel.title,
                    duration=duration_iso,
                    view_count=_optional_int(entry.get("view_count")),
                    like_count=_optional_int(entry.get("like_count")),
                    position=i,
                )
            )
            if max_videos and len(videos) >= max_videos:
                break

        return videos


def get_youtube_client(api_key: str | None) -> "YouTubeDataClient | YtDlpClient":
    """Factory: returns YouTubeDataClient if api_key is set, otherwise YtDlpClient."""
    if api_key and api_key.strip():
        return YouTubeDataClient(api_key.strip())
    return YtDlpClient()


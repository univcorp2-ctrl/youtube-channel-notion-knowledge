from __future__ import annotations

import re
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import requests

from yt_notion_digest.models import Channel, Video

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeApiError(RuntimeError):
    """Raised when the YouTube Data API returns an unusable response."""


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
            raise ValueError("YOUTUBE_API_KEY is required to enumerate every public upload.")
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
                        published_at=snippet.get("publishedAt") or content_details.get("videoPublishedAt"),
                        description=snippet.get("description", ""),
                        channel_id=channel.id,
                        channel_title=channel.title,
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

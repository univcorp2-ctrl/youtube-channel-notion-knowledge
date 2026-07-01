from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from yt_notion_digest.models import Channel, TranscriptResult, Video, VideoSummary

NOTION_API_BASE = "https://api.notion.com/v1"
MAX_RICH_TEXT = 1900
MAX_BLOCKS_PER_REQUEST = 100


class NotionError(RuntimeError):
    """Raised when Notion rejects a request."""


class NotionClient:
    def __init__(
        self,
        token: str,
        database_id: str | None = None,
        version: str = "2022-06-28",
        session: requests.Session | None = None,
    ) -> None:
        if not token:
            raise ValueError("NOTION_TOKEN is required for Notion sync.")
        self.token = token
        self.database_id = database_id
        self.version = version
        self.session = session or requests.Session()

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.request(
            method,
            f"{NOTION_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Notion-Version": self.version,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        if response.status_code >= 400:
            raise NotionError(f"Notion API failed: HTTP {response.status_code}: {response.text[:800]}")
        return response.json()

    def create_database(self, parent_page_id: str, title: str) -> str:
        payload = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": {
                "Name": {"title": {}},
                "Video ID": {"rich_text": {}},
                "Video URL": {"url": {}},
                "Channel": {"rich_text": {}},
                "Published": {"date": {}},
                "Status": {
                    "select": {
                        "options": [
                            {"name": "done", "color": "green"},
                            {"name": "missing_transcript", "color": "yellow"},
                            {"name": "error", "color": "red"},
                            {"name": "channel_summary", "color": "blue"},
                        ]
                    }
                },
                "Word Count": {"number": {"format": "number"}},
                "Summary Model": {"rich_text": {}},
                "Synced At": {"date": {}},
            },
        }
        created = self._request("POST", "/databases", payload)
        self.database_id = created["id"]
        return self.database_id

    def ensure_database(self, parent_page_id: str | None, title: str) -> str | None:
        if self.database_id:
            return self.database_id
        if parent_page_id:
            return self.create_database(parent_page_id, title)
        return None

    def find_page_by_video_id(self, video_id: str) -> str | None:
        if not self.database_id:
            return None
        payload = {
            "filter": {"property": "Video ID", "rich_text": {"equals": video_id}},
            "page_size": 1,
        }
        try:
            data = self._request("POST", f"/databases/{self.database_id}/query", payload)
        except NotionError:
            return None
        results = data.get("results") or []
        return results[0].get("id") if results else None

    def upsert_markdown_page(
        self,
        video_id: str,
        properties: dict[str, Any],
        markdown: str,
    ) -> str:
        if not self.database_id:
            raise NotionError("No Notion database ID is configured.")

        blocks = markdown_to_blocks(markdown)
        existing_page_id = self.find_page_by_video_id(video_id)
        if existing_page_id:
            self._request("PATCH", f"/pages/{existing_page_id}", {"properties": properties})
            update_block = paragraph_block(
                f"Synced again at {datetime.now(timezone.utc).isoformat()}. Existing content was kept; new content appended below."
            )
            self.append_children(existing_page_id, [update_block, *blocks])
            return existing_page_id

        payload = {
            "parent": {"database_id": self.database_id},
            "properties": properties,
            "children": blocks[:MAX_BLOCKS_PER_REQUEST],
        }
        created = self._request("POST", "/pages", payload)
        page_id = created["id"]
        remaining = blocks[MAX_BLOCKS_PER_REQUEST:]
        if remaining:
            self.append_children(page_id, remaining)
        return page_id

    def append_children(self, block_id: str, blocks: list[dict[str, Any]]) -> None:
        for start in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
            batch = blocks[start : start + MAX_BLOCKS_PER_REQUEST]
            if batch:
                self._request("PATCH", f"/blocks/{block_id}/children", {"children": batch})

    def sync_video(
        self,
        channel: Channel,
        video: Video,
        transcript: TranscriptResult,
        summary: VideoSummary,
        include_transcript: bool = True,
    ) -> str:
        status = "done" if transcript.status == "ok" else "missing_transcript"
        properties = {
            "Name": title_prop(video.title),
            "Video ID": rich_text_prop(video.id),
            "Video URL": {"url": video.url},
            "Channel": rich_text_prop(channel.title),
            "Published": date_prop(video.published_at),
            "Status": {"select": {"name": status}},
            "Word Count": {"number": transcript.word_count},
            "Summary Model": rich_text_prop(summary.model),
            "Synced At": date_prop(datetime.now(timezone.utc).isoformat()),
        }
        markdown = video_markdown(channel, video, transcript, summary, include_transcript)
        return self.upsert_markdown_page(video.id, properties, markdown)

    def sync_channel_summary(self, channel: Channel, summary_markdown: str) -> str:
        video_id = f"CHANNEL_SUMMARY:{channel.id}"
        properties = {
            "Name": title_prop(f"{channel.title} - チャンネル総合サマリー"),
            "Video ID": rich_text_prop(video_id),
            "Video URL": {"url": channel.url},
            "Channel": rich_text_prop(channel.title),
            "Published": {"date": None},
            "Status": {"select": {"name": "channel_summary"}},
            "Word Count": {"number": len(summary_markdown.split())},
            "Summary Model": rich_text_prop("channel-synthesis"),
            "Synced At": date_prop(datetime.now(timezone.utc).isoformat()),
        }
        return self.upsert_markdown_page(video_id, properties, summary_markdown)


def title_prop(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:MAX_RICH_TEXT]}}]}


def rich_text_prop(value: str) -> dict[str, Any]:
    return {"rich_text": [{"type": "text", "text": {"content": value[:MAX_RICH_TEXT]}}]}


def date_prop(value: str | None) -> dict[str, Any]:
    if not value:
        return {"date": None}
    return {"date": {"start": value}}


def text_object(value: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": value[:MAX_RICH_TEXT]}}]


def paragraph_block(value: str) -> dict[str, Any]:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": text_object(value)}}


def heading_block(level: int, value: str) -> dict[str, Any]:
    block_type = f"heading_{level}"
    return {"object": "block", "type": block_type, block_type: {"rich_text": text_object(value)}}


def bullet_block(value: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": text_object(value)},
    }


def markdown_to_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        for chunk in chunk_text(line, MAX_RICH_TEXT):
            stripped = chunk.strip()
            if stripped.startswith("### "):
                blocks.append(heading_block(3, stripped[4:]))
            elif stripped.startswith("## "):
                blocks.append(heading_block(2, stripped[3:]))
            elif stripped.startswith("# "):
                blocks.append(heading_block(1, stripped[2:]))
            elif stripped.startswith("- "):
                blocks.append(bullet_block(stripped[2:]))
            else:
                blocks.append(paragraph_block(stripped))
    return blocks or [paragraph_block("No content.")]


def chunk_text(text: str, max_length: int) -> list[str]:
    if len(text) <= max_length:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + max_length])
        start += max_length
    return chunks


def video_markdown(
    channel: Channel,
    video: Video,
    transcript: TranscriptResult,
    summary: VideoSummary,
    include_transcript: bool,
) -> str:
    lines = [
        f"# {video.title}",
        "",
        "## メタデータ",
        f"- Channel: {channel.title}",
        f"- Video ID: {video.id}",
        f"- URL: {video.url}",
        f"- Published: {video.published_at or 'unknown'}",
        f"- Duration: {video.duration or 'unknown'}",
        f"- Views: {video.view_count if video.view_count is not None else 'unknown'}",
        f"- Transcript status: {transcript.status}",
        f"- Transcript language: {transcript.language_code or 'unknown'}",
        f"- Summary model: {summary.model}",
        "",
        "## 詳細サマリー",
        summary.summary_markdown,
    ]
    if include_transcript:
        lines.extend(
            [
                "",
                "## フル文字起こし",
                transcript.text or f"取得不可: {transcript.error or 'unknown error'}",
            ]
        )
    return "\n".join(lines)

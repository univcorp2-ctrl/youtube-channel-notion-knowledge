from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class Channel:
    id: str
    title: str
    url: str
    uploads_playlist_id: str
    description: str = ""
    subscriber_count: int | None = None
    video_count: int | None = None


@dataclass(slots=True)
class Video:
    id: str
    title: str
    url: str
    published_at: str | None = None
    description: str = ""
    channel_id: str | None = None
    channel_title: str | None = None
    duration: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    position: int | None = None


@dataclass(slots=True)
class TranscriptResult:
    video_id: str
    status: str
    text: str = ""
    language_code: str | None = None
    is_generated: bool | None = None
    segment_count: int = 0
    error: str | None = None

    @property
    def word_count(self) -> int:
        return len(self.text.split()) if self.text else 0


@dataclass(slots=True)
class VideoSummary:
    video_id: str
    title: str
    summary_markdown: str
    model: str
    chunk_count: int
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(slots=True)
class PipelineResult:
    channel: Channel
    videos_found: int
    videos_processed: int
    output_dir: str
    notion_database_id: str | None = None
    channel_summary_path: str | None = None
    manifest_path: str | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

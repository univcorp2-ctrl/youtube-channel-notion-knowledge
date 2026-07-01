from __future__ import annotations

import html
import time
from typing import Any

from yt_notion_digest.models import TranscriptResult


def seconds_to_timestamp(seconds: float) -> str:
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class TranscriptClient:
    def __init__(
        self,
        languages: list[str] | None = None,
        translate_to: str | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.languages = languages or ["ja", "en"]
        self.translate_to = translate_to
        self.delay_seconds = delay_seconds

    def fetch(self, video_id: str) -> TranscriptResult:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
            if self.translate_to:
                transcript = api.list(video_id).find_transcript(self.languages)
                fetched = transcript.translate(self.translate_to).fetch()
            else:
                fetched = api.fetch(video_id, languages=self.languages, preserve_formatting=False)

            raw_segments = _to_raw_segments(fetched)
            lines = []
            for segment in raw_segments:
                text = html.unescape(str(segment.get("text", ""))).replace("\n", " ").strip()
                if not text:
                    continue
                start = float(segment.get("start", 0.0) or 0.0)
                lines.append(f"[{seconds_to_timestamp(start)}] {text}")

            if self.delay_seconds:
                time.sleep(self.delay_seconds)

            return TranscriptResult(
                video_id=video_id,
                status="ok",
                text="\n".join(lines),
                language_code=getattr(fetched, "language_code", self.translate_to or self.languages[0]),
                is_generated=getattr(fetched, "is_generated", None),
                segment_count=len(raw_segments),
            )
        except Exception as exc:  # noqa: BLE001
            if self.delay_seconds:
                time.sleep(self.delay_seconds)
            return TranscriptResult(
                video_id=video_id,
                status="missing",
                text="",
                segment_count=0,
                error=f"{type(exc).__name__}: {exc}",
            )


def _to_raw_segments(fetched: Any) -> list[dict[str, Any]]:
    if hasattr(fetched, "to_raw_data"):
        return [dict(item) for item in fetched.to_raw_data()]

    raw_segments: list[dict[str, Any]] = []
    for item in fetched:
        if isinstance(item, dict):
            raw_segments.append(dict(item))
        else:
            raw_segments.append(
                {
                    "text": getattr(item, "text", ""),
                    "start": getattr(item, "start", 0.0),
                    "duration": getattr(item, "duration", 0.0),
                }
            )
    return raw_segments

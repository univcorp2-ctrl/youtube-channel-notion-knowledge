from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict
from pathlib import Path

from yt_notion_digest.models import Channel, PipelineResult, TranscriptResult, Video, VideoSummary


def safe_filename(value: str, max_length: int = 80) -> str:
    value = re.sub(r"[^0-9A-Za-zぁ-んァ-ン一-龥_-]+", "-", value).strip("-")
    if not value:
        value = "untitled"
    return value[:max_length]


class RunStore:
    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)
        self.videos_dir = self.output_dir / "videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.videos_dir.mkdir(parents=True, exist_ok=True)

    def save_video_bundle(
        self, video: Video, transcript: TranscriptResult, summary: VideoSummary
    ) -> Path:
        date_prefix = (video.published_at or "unknown")[:10]
        folder = self.videos_dir / f"{date_prefix}_{video.id}_{safe_filename(video.title)}"
        folder.mkdir(parents=True, exist_ok=True)

        (folder / "transcript.txt").write_text(transcript.text, encoding="utf-8")
        (folder / "summary.md").write_text(summary.summary_markdown, encoding="utf-8")
        (folder / "metadata.json").write_text(
            json.dumps(
                {
                    "video": asdict(video),
                    "transcript": asdict(transcript),
                    "summary": asdict(summary),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return folder

    def save_channel_summary(self, channel: Channel, summary_markdown: str) -> Path:
        path = self.output_dir / "channel_summary.md"
        header = f"# {channel.title}\n\nChannel ID: `{channel.id}`\n\n"
        path.write_text(header + summary_markdown, encoding="utf-8")
        return path

    def save_manifest(
        self,
        channel: Channel,
        videos: list[Video],
        transcripts: list[TranscriptResult],
        summaries: list[VideoSummary],
        errors: list[str],
    ) -> tuple[Path, Path]:
        transcript_by_id = {item.video_id: item for item in transcripts}
        summary_by_id = {item.video_id: item for item in summaries}
        rows = []
        for video in videos:
            transcript = transcript_by_id.get(video.id)
            summary = summary_by_id.get(video.id)
            rows.append(
                {
                    "video_id": video.id,
                    "title": video.title,
                    "url": video.url,
                    "published_at": video.published_at,
                    "duration": video.duration,
                    "view_count": video.view_count,
                    "transcript_status": transcript.status if transcript else "not_processed",
                    "transcript_error": transcript.error if transcript else "",
                    "word_count": transcript.word_count if transcript else 0,
                    "summary_model": summary.model if summary else "",
                }
            )

        json_path = self.output_dir / "manifest.json"
        json_path.write_text(
            json.dumps({"channel": asdict(channel), "videos": rows, "errors": errors}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        csv_path = self.output_dir / "manifest.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["video_id"])
            writer.writeheader()
            writer.writerows(rows)

        return json_path, csv_path

    def save_result(self, result: PipelineResult) -> Path:
        path = self.output_dir / "result.json"
        path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from yt_notion_digest.config import AppConfig
from yt_notion_digest.models import Channel, PipelineResult, TranscriptResult, Video, VideoSummary
from yt_notion_digest.notion import NotionClient
from yt_notion_digest.storage import RunStore
from yt_notion_digest.summarizer import Summarizer
from yt_notion_digest.transcripts import TranscriptClient
from yt_notion_digest.youtube import YouTubeDataClient, YtDlpClient, get_youtube_client  # noqa: F401


class YouTubeClientProtocol(Protocol):
    def resolve_channel(self, channel_url: str) -> Channel:
        ...

    def list_uploads(self, channel: Channel, max_videos: int = 0) -> list[Video]:
        ...


class TranscriptClientProtocol(Protocol):
    def fetch(self, video_id: str) -> TranscriptResult:
        ...


class SummarizerProtocol(Protocol):
    def summarize_video(self, video: Video, transcript: TranscriptResult) -> VideoSummary:
        ...

    def summarize_channel(self, channel: Channel, summaries: list[VideoSummary]) -> str:
        ...


@dataclass(slots=True)
class PipelineOptions:
    channel_url: str
    output_dir: Path
    max_videos: int = 0
    languages: list[str] | None = None
    translate_to: str | None = None
    sync_notion: bool = True
    include_transcript_in_notion: bool = True


class YouTubeToNotionPipeline:
    def __init__(
        self,
        config: AppConfig,
        youtube_client: YouTubeClientProtocol | None = None,
        transcript_client: TranscriptClientProtocol | None = None,
        summarizer: SummarizerProtocol | None = None,
        notion_client: NotionClient | None = None,
    ) -> None:
        self.config = config
        self.youtube_client = youtube_client or get_youtube_client(config.youtube_api_key)
        self.transcript_client = transcript_client or TranscriptClient(
            languages=config.languages,
            translate_to=config.translate_to,
            delay_seconds=float(os.environ.get("TRANSCRIPT_DELAY_SECONDS", "2.0")),
        )
        self.summarizer = summarizer or Summarizer(
            api_key=config.openai_api_key,
            model=config.openai_model,
            max_output_tokens=config.openai_max_output_tokens,
        )
        self.notion_client = notion_client
        if self.notion_client is None and config.notion_token:
            self.notion_client = NotionClient(
                token=config.notion_token,
                database_id=config.notion_database_id,
                version=config.notion_version,
            )

    def run(self, options: PipelineOptions) -> PipelineResult:
        store = RunStore(options.output_dir)
        errors: list[str] = []
        transcripts: list[TranscriptResult] = []
        summaries: list[VideoSummary] = []

        channel = self.youtube_client.resolve_channel(options.channel_url)
        videos = self.youtube_client.list_uploads(channel, max_videos=options.max_videos)

        notion_database_id: str | None = None
        if options.sync_notion and self.notion_client:
            try:
                notion_database_id = self.notion_client.ensure_database(
                    self.config.notion_parent_page_id, self.config.notion_database_title
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"Notion database setup failed: {type(exc).__name__}: {exc}")
        elif options.sync_notion:
            errors.append("Notion sync requested but NOTION_TOKEN is not configured.")

        for index, video in enumerate(videos, start=1):
            try:
                print(f"[{index}/{len(videos)}] transcript: {video.title}")
                transcript = self.transcript_client.fetch(video.id)
                transcripts.append(transcript)

                print(f"[{index}/{len(videos)}] summarize: {video.title}")
                summary = self.summarizer.summarize_video(video, transcript)
                summaries.append(summary)
                store.save_video_bundle(video, transcript, summary)

                if options.sync_notion and self.notion_client and notion_database_id:
                    print(f"[{index}/{len(videos)}] notion sync: {video.title}")
                    self.notion_client.sync_video(
                        channel,
                        video,
                        transcript,
                        summary,
                        include_transcript=options.include_transcript_in_notion,
                    )
            except Exception as exc:  # noqa: BLE001
                message = f"Video {video.id} failed: {type(exc).__name__}: {exc}"
                print(message)
                errors.append(message)

        channel_summary_path: str | None = None
        try:
            channel_summary = self.summarizer.summarize_channel(channel, summaries)
            channel_summary_path = str(store.save_channel_summary(channel, channel_summary))
            if options.sync_notion and self.notion_client and notion_database_id:
                self.notion_client.sync_channel_summary(channel, channel_summary)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Channel summary failed: {type(exc).__name__}: {exc}")

        manifest_json, _manifest_csv = store.save_manifest(channel, videos, transcripts, summaries, errors)
        result = PipelineResult(
            channel=channel,
            videos_found=len(videos),
            videos_processed=len(summaries),
            output_dir=str(options.output_dir),
            notion_database_id=notion_database_id,
            channel_summary_path=channel_summary_path,
            manifest_path=str(manifest_json),
            errors=errors,
        )
        store.save_result(result)
        return result

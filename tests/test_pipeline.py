from pathlib import Path

from yt_notion_digest.config import AppConfig
from yt_notion_digest.models import Channel, TranscriptResult, Video, VideoSummary
from yt_notion_digest.pipeline import PipelineOptions, YouTubeToNotionPipeline


class FakeYouTubeClient:
    def resolve_channel(self, channel_url: str) -> Channel:
        return Channel(
            id="UC1",
            title="Fake Channel",
            url=channel_url,
            uploads_playlist_id="UU1",
            video_count=1,
        )

    def list_uploads(self, channel: Channel, max_videos: int = 0) -> list[Video]:
        return [Video(id="v1", title="Video One", url="https://youtu.be/v1", channel_id=channel.id)]


class FakeTranscriptClient:
    def fetch(self, video_id: str) -> TranscriptResult:
        return TranscriptResult(video_id=video_id, status="ok", text="[00:00] Hello world.")


class FakeSummarizer:
    def summarize_video(self, video: Video, transcript: TranscriptResult) -> VideoSummary:
        return VideoSummary(
            video_id=video.id,
            title=video.title,
            summary_markdown="# Summary\nDetailed note.",
            model="fake",
            chunk_count=1,
        )

    def summarize_channel(self, channel: Channel, summaries: list[VideoSummary]) -> str:
        return "# Channel Summary\nAll videos covered."


def test_pipeline_writes_outputs(tmp_path: Path) -> None:
    config = AppConfig(
        youtube_api_key=None,
        openai_api_key=None,
        openai_model="fake",
        openai_max_output_tokens=1000,
        notion_token=None,
        notion_database_id=None,
        notion_parent_page_id=None,
        notion_database_title="DB",
        notion_version="2022-06-28",
        notion_include_transcript=True,
        channel_url=None,
        languages=["ja", "en"],
        translate_to=None,
        max_videos=0,
        output_dir=tmp_path,
    )
    pipeline = YouTubeToNotionPipeline(
        config,
        youtube_client=FakeYouTubeClient(),
        transcript_client=FakeTranscriptClient(),
        summarizer=FakeSummarizer(),
    )
    result = pipeline.run(
        PipelineOptions(channel_url="https://youtube.com/@fake", output_dir=tmp_path, sync_notion=False)
    )
    assert result.videos_found == 1
    assert result.videos_processed == 1
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "channel_summary.md").exists()

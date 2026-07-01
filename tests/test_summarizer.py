from yt_notion_digest.models import TranscriptResult, Video
from yt_notion_digest.summarizer import Summarizer, split_text_by_chars


def test_split_text_by_chars_keeps_all_text() -> None:
    text = "abc\n" * 100
    chunks = split_text_by_chars(text, 50)
    assert "".join(chunks).replace("\n", "") == text.strip().replace("\n", "")
    assert len(chunks) > 1


def test_local_fallback_summary_mentions_openai_key() -> None:
    video = Video(id="v1", title="Title", url="https://youtu.be/v1")
    transcript = TranscriptResult(video_id="v1", status="ok", text="最初の説明です。 次の説明です。")
    summary = Summarizer(api_key=None).summarize_video(video, transcript)
    assert summary.model == "local-extractive-fallback"
    assert "OPENAI_API_KEY" in summary.summary_markdown
    assert "最初の説明" in summary.summary_markdown

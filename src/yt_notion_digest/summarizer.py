from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

import requests

from yt_notion_digest.models import Channel, TranscriptResult, Video, VideoSummary

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class SummaryError(RuntimeError):
    """Raised when a remote summarization request fails."""


def split_text_by_chars(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            newline = text.rfind("\n", start + int(max_chars * 0.65), end)
            if newline != -1:
                end = newline + 1
        chunks.append(text[start:end].strip())
        start = end
    return [chunk for chunk in chunks if chunk]


class Summarizer:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-5.4-mini",
        max_output_tokens: int = 6000,
        max_chunk_chars: int = 24_000,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.max_chunk_chars = max_chunk_chars
        self.session = session or requests.Session()

    @property
    def uses_openai(self) -> bool:
        return bool(self.api_key)

    def summarize_video(self, video: Video, transcript: TranscriptResult) -> VideoSummary:
        if transcript.status != "ok" or not transcript.text.strip():
            return VideoSummary(
                video_id=video.id,
                title=video.title,
                summary_markdown=self._missing_transcript_summary(video, transcript),
                model="no-transcript",
                chunk_count=0,
            )

        chunks = split_text_by_chars(transcript.text, self.max_chunk_chars)
        if not self.uses_openai:
            return VideoSummary(
                video_id=video.id,
                title=video.title,
                summary_markdown=self._extractive_video_summary(video, transcript),
                model="local-extractive-fallback",
                chunk_count=len(chunks),
            )

        chunk_summaries = []
        for index, chunk in enumerate(chunks, start=1):
            prompt = self._video_chunk_prompt(video, transcript, chunk, index, len(chunks))
            chunk_summaries.append(self._call_openai(prompt, max_output_tokens=self.max_output_tokens))

        synthesis_prompt = self._video_synthesis_prompt(video, transcript, chunk_summaries)
        final_summary = self._call_openai(synthesis_prompt, max_output_tokens=self.max_output_tokens)
        return VideoSummary(
            video_id=video.id,
            title=video.title,
            summary_markdown=final_summary,
            model=self.model,
            chunk_count=len(chunks),
        )

    def summarize_channel(self, channel: Channel, summaries: list[VideoSummary]) -> str:
        if not summaries:
            return f"# {channel.title}\n\n動画が見つかりませんでした。"

        combined = "\n\n".join(
            f"## {idx}. {summary.title}\nVideo ID: {summary.video_id}\n\n{summary.summary_markdown}"
            for idx, summary in enumerate(summaries, start=1)
        )
        chunks = split_text_by_chars(combined, self.max_chunk_chars)

        if not self.uses_openai:
            titles = "\n".join(f"- {summary.title}" for summary in summaries)
            return (
                f"# {channel.title} チャンネル総合サマリー\n\n"
                "OPENAI_API_KEY が未設定のため、統合要約は動画タイトル一覧と各動画サマリーの結合です。\n\n"
                f"## 収集動画\n{titles}\n\n## 各動画サマリー\n{combined}"
            )

        chunk_summaries = []
        for index, chunk in enumerate(chunks, start=1):
            prompt = (
                "あなたはYouTubeチャンネル全体を知識ベース化する編集者です。"
                "以下は各動画サマリーの一部です。欠落を作らず、論点・固有名詞・手順・数字・注意点を保持して、"
                "後で全体統合できる詳細な中間ノートにしてください。\n\n"
                f"チャンネル: {channel.title}\n"
                f"分割: {index}/{len(chunks)}\n\n{chunk}"
            )
            chunk_summaries.append(self._call_openai(prompt, max_output_tokens=self.max_output_tokens))

        final_prompt = (
            "以下の中間ノートを統合し、チャンネル全動画を横断したNotebookLM風のナレッジベースをMarkdownで作ってください。\n"
            "重要条件:\n"
            "- 代表動画だけに寄せず、全動画の内容を回収する。\n"
            "- 情報量を落としすぎず、動画ごとの差分・共通テーマ・手順・ツール・注意点を残す。\n"
            "- 見出しは、全体像、主要テーマ、動画別詳細ノート、実践手順、用語集、未確認/字幕欠落、次に見る順番。\n"
            "- 動画タイトルとVideo IDをできるだけ残す。\n\n"
            f"チャンネルメタデータ: {asdict(channel)}\n\n"
            f"中間ノート:\n{chr(10).join(chunk_summaries)}"
        )
        return self._call_openai(final_prompt, max_output_tokens=self.max_output_tokens)

    def _call_openai(self, prompt: str, max_output_tokens: int) -> str:
        if not self.api_key:
            raise SummaryError("OPENAI_API_KEY is not configured.")

        response = self.session.post(
            OPENAI_RESPONSES_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": prompt,
                "max_output_tokens": max_output_tokens,
            },
            timeout=180,
        )
        if response.status_code >= 400:
            raise SummaryError(
                f"OpenAI request failed: HTTP {response.status_code}: {response.text[:800]}"
            )
        data = response.json()
        return _extract_response_text(data).strip()

    def _video_chunk_prompt(
        self,
        video: Video,
        transcript: TranscriptResult,
        chunk: str,
        index: int,
        total: int,
    ) -> str:
        return (
            "あなたは日本語で詳細な動画ノートを作る専門家です。"
            "以下は1本のYouTube動画の文字起こしの一部です。"
            "省略しすぎず、後から全体統合しても情報が落ちないように詳細にまとめてください。\n\n"
            "出力形式:\n"
            "1. この分割の要旨\n"
            "2. 時系列の詳細ノート\n"
            "3. 固有名詞・サービス・ツール・数字\n"
            "4. 手順・ノウハウ・判断基準\n"
            "5. 注意点・例外・未解決点\n\n"
            f"動画メタデータ: {asdict(video)}\n"
            f"字幕メタデータ: {asdict(transcript)}\n"
            f"分割: {index}/{total}\n\n"
            f"文字起こし:\n{chunk}"
        )

    def _video_synthesis_prompt(
        self, video: Video, transcript: TranscriptResult, chunk_summaries: list[str]
    ) -> str:
        return (
            "以下は1本の動画を分割して要約した中間ノートです。"
            "重複だけ整理し、情報量を落とさず、Notionに保存する完成版の詳細サマリーをMarkdownで作ってください。\n\n"
            "必須見出し:\n"
            "# 動画サマリー\n"
            "## 一言でいうと\n"
            "## 詳細ノート\n"
            "## 時系列・構成\n"
            "## 具体的な手順・Tips\n"
            "## 固有名詞・ツール・数値\n"
            "## 注意点・未確認事項\n"
            "## この動画からNotionに残すべき検索タグ\n\n"
            f"動画メタデータ: {asdict(video)}\n"
            f"字幕メタデータ: {asdict(transcript)}\n\n"
            f"中間ノート:\n{chr(10).join(chunk_summaries)}"
        )

    def _missing_transcript_summary(self, video: Video, transcript: TranscriptResult) -> str:
        return (
            f"# {video.title}\n\n"
            "## ステータス\n"
            "この動画は動画一覧には含めましたが、字幕/文字起こしを取得できませんでした。\n\n"
            f"- Video ID: {video.id}\n"
            f"- URL: {video.url}\n"
            f"- 公開日: {video.published_at or 'unknown'}\n"
            f"- エラー: {transcript.error or 'unknown'}\n\n"
            "## 次の対応\n"
            "YouTube側で字幕が存在しない、年齢制限、地域制限、IPブロック、または字幕取得APIの仕様変更が原因の可能性があります。"
            "動画自体はNotionとmanifestに残るため、抜け漏れ監査の対象として追跡できます。"
        )

    def _extractive_video_summary(self, video: Video, transcript: TranscriptResult) -> str:
        sentences = _split_sentences(transcript.text)
        selected = sentences[:40]
        bullet_lines = "\n".join(f"- {sentence}" for sentence in selected)
        return (
            f"# {video.title}\n\n"
            "## 注意\n"
            "OPENAI_API_KEY が未設定のため、これはローカル抽出型の暫定サマリーです。"
            "本番ではOPENAI_API_KEYを設定すると、分割要約と統合要約で詳細なノートを生成します。\n\n"
            "## 抽出ノート\n"
            f"{bullet_lines}\n\n"
            "## メタデータ\n"
            f"- Video ID: {video.id}\n- URL: {video.url}\n- 公開日: {video.published_at or 'unknown'}\n"
        )


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？.!?])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _extract_response_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]

    collected: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if isinstance(content.get("text"), str):
                collected.append(content["text"])
    if collected:
        return "\n".join(collected)

    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message", {})
        if isinstance(message.get("content"), str):
            return message["content"]

    raise SummaryError("Could not extract text from OpenAI response.")

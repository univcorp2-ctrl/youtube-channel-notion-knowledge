from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(slots=True)
class AppConfig:
    youtube_api_key: str | None
    openai_api_key: str | None
    openai_model: str
    openai_max_output_tokens: int
    notion_token: str | None
    notion_database_id: str | None
    notion_parent_page_id: str | None
    notion_database_title: str
    notion_version: str
    notion_include_transcript: bool
    channel_url: str | None
    languages: list[str]
    translate_to: str | None
    max_videos: int
    output_dir: Path

    @classmethod
    def from_env(cls, env_file: str | None = None) -> AppConfig:
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return cls(
            youtube_api_key=os.getenv("YOUTUBE_API_KEY") or None,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            openai_max_output_tokens=_env_int("OPENAI_MAX_OUTPUT_TOKENS", 6000),
            notion_token=os.getenv("NOTION_TOKEN") or None,
            notion_database_id=os.getenv("NOTION_DATABASE_ID") or None,
            notion_parent_page_id=os.getenv("NOTION_PARENT_PAGE_ID") or None,
            notion_database_title=os.getenv("NOTION_DATABASE_TITLE", "YouTube Channel Knowledge Base"),
            notion_version=os.getenv("NOTION_VERSION", "2022-06-28"),
            notion_include_transcript=_env_bool("NOTION_INCLUDE_TRANSCRIPT", True),
            channel_url=os.getenv("CHANNEL_URL") or None,
            languages=_csv_env("LANGUAGES", ["ja", "en"]),
            translate_to=os.getenv("TRANSLATE_TO") or None,
            max_videos=_env_int("MAX_VIDEOS", 0),
            output_dir=Path(os.getenv("OUTPUT_DIR", "data/runs/latest")),
        )

# Agent Notes

## Goal

Maintain a production-ready pipeline that converts every public upload of a YouTube channel into a Notion knowledge base.

## Commands

```bash
pip install -e '.[dev]'
ruff check .
pytest
yt-notion-digest run --channel-url "https://youtube.com/@macamp0817?si=U7FfYoWVQQLMvJf0" --max-videos 3 --no-notion
```

## Key files

- `src/yt_notion_digest/youtube.py`: channel resolution and upload enumeration
- `src/yt_notion_digest/transcripts.py`: subtitle retrieval
- `src/yt_notion_digest/summarizer.py`: video and channel summaries
- `src/yt_notion_digest/notion.py`: Notion database/page sync
- `src/yt_notion_digest/pipeline.py`: orchestration
- `.github/workflows/ci.yml`: tests and workflow_dispatch processing

## Safety and compliance

Do not commit API keys, Notion tokens, or generated transcript data. Respect YouTube, Notion, and OpenAI API terms, channel owner rights, and copyright requirements.

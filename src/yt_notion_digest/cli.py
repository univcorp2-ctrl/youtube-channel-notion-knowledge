from __future__ import annotations

import argparse
import json
from pathlib import Path

from yt_notion_digest.config import AppConfig
from yt_notion_digest.pipeline import PipelineOptions, YouTubeToNotionPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-notion-digest",
        description="Collect all public uploads from a YouTube channel, summarize transcripts, and sync to Notion.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the full channel-to-Notion pipeline.")
    run_parser.add_argument("--channel-url", default=None, help="YouTube channel URL or @handle URL.")
    run_parser.add_argument("--output-dir", default=None, help="Directory for local Markdown/TXT/JSON outputs.")
    run_parser.add_argument("--max-videos", type=int, default=None, help="0 means all uploads.")
    run_parser.add_argument("--languages", default=None, help="Comma-separated transcript language priority, e.g. ja,en.")
    run_parser.add_argument("--translate-to", default=None, help="Translate available captions to this language code.")
    run_parser.add_argument("--no-notion", action="store_true", help="Disable Notion sync for this run.")
    run_parser.add_argument("--env-file", default=None, help="Optional .env file path.")

    serve_parser = subparsers.add_parser("serve", help="Start the lightweight FastAPI web UI.")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8000)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("yt_notion_digest.web:app", host=args.host, port=args.port, reload=False)
        return

    config = AppConfig.from_env(args.env_file)
    channel_url = args.channel_url or config.channel_url
    if not channel_url:
        raise SystemExit("--channel-url or CHANNEL_URL is required")

    languages = config.languages
    if args.languages:
        languages = [item.strip() for item in args.languages.split(",") if item.strip()]

    options = PipelineOptions(
        channel_url=channel_url,
        output_dir=Path(args.output_dir) if args.output_dir else config.output_dir,
        max_videos=config.max_videos if args.max_videos is None else args.max_videos,
        languages=languages,
        translate_to=args.translate_to or config.translate_to,
        sync_notion=not args.no_notion,
        include_transcript_in_notion=config.notion_include_transcript,
    )

    if args.languages or args.translate_to:
        config.languages = languages
        config.translate_to = options.translate_to

    result = YouTubeToNotionPipeline(config).run(options)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

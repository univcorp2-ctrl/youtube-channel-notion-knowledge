#!/usr/bin/env python3
"""
retry_missing_transcripts.py
Notion DB の missing_transcript ページを取得し、字幕を再取得してページを更新する。

使い方:
    python scripts/retry_missing_transcripts.py
    python scripts/retry_missing_transcripts.py --delay 5.0  # 1動画ごとに5秒待機
    python scripts/retry_missing_transcripts.py --limit 10   # 最大10件のみ処理

実行セッション情報:
    Notion DB  : YouTube Channel Knowledge Base
    DB ID      : aa8e4d967b1f49a68e1ce512bf05bc28
    Repo       : C:\\Users\\t0015\\Documents\\AI_Agent_LOCAL\\youtube-channel-notion-knowledge
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from yt_notion_digest.notion import NotionClient, markdown_to_blocks


def get_missing_pages(db_id: str, token: str, limit: int = 0) -> list[dict]:
    """Notionから missing_transcript ページを全件取得"""
    pages = []
    cursor = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    while True:
        body = {
            "filter": {"property": "Status", "select": {"equals": "missing_transcript"}},
            "page_size": 100,
        }
        if cursor:
            body["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{db_id}/query",
            headers=headers,
            json=body,
        )
        data = r.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more") or (limit and len(pages) >= limit):
            break
        cursor = data.get("next_cursor")
    return pages[:limit] if limit else pages


def fetch_transcript(video_id: str, languages: list[str]) -> tuple[str, str]:
    """字幕テキストと言語コードを返す。失敗時は ("", "error") を返す"""
    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=languages)
        lines = []
        for seg in fetched:
            text = str(getattr(seg, "text", seg.get("text", "") if isinstance(seg, dict) else "")).replace("\n", " ").strip()
            start = float(getattr(seg, "start", seg.get("start", 0.0) if isinstance(seg, dict) else 0.0))
            m, s = divmod(int(start), 60)
            lines.append(f"[{m:02d}:{s:02d}] {text}")
        lang = getattr(fetched, "language_code", languages[0])
        return "\n".join(lines), lang
    except Exception as e:
        return "", f"error:{type(e).__name__}"


def update_notion_page(nc: NotionClient, page_id: str, transcript: str, video_id: str) -> bool:
    """NotionページのStatusとコンテンツを更新"""
    synced_at = datetime.now(timezone.utc).isoformat()
    word_count = len(transcript.split()) if transcript else 0
    properties = {
        "Status": {"select": {"name": "done" if transcript else "missing_transcript"}},
        "Word Count": {"number": word_count},
        "Synced At": {"date": {"start": synced_at}},
    }
    try:
        nc._request("PATCH", f"/pages/{page_id}", {"properties": properties})
        if transcript:
            blocks = markdown_to_blocks(transcript)
            nc.append_children(page_id, blocks[:50])  # 最初の50ブロックのみ
        return bool(transcript)
    except Exception as e:
        print(f"  Notion update error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Retry missing transcripts in Notion DB")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds to wait between videos (default: 3.0)")
    parser.add_argument("--limit", type=int, default=0, help="Max pages to process (0 = all)")
    parser.add_argument("--languages", default="ja,en", help="Language codes (default: ja,en)")
    args = parser.parse_args()

    db_id = os.getenv("NOTION_DATABASE_ID")
    token = os.getenv("NOTION_TOKEN")
    languages = [x.strip() for x in args.languages.split(",")]

    if not db_id or not token:
        print("ERROR: NOTION_DATABASE_ID and NOTION_TOKEN must be set in .env")
        sys.exit(1)

    nc = NotionClient(token=token, database_id=db_id)

    print("=" * 60)
    print("Retry Missing Transcripts")
    print(f"DB: {db_id}")
    print(f"Delay: {args.delay}s / Languages: {languages}")
    print(f"Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    pages = get_missing_pages(db_id, token, args.limit)
    print(f"Found {len(pages)} missing_transcript pages\n")

    success = 0
    fail = 0

    for i, page in enumerate(pages, 1):
        props = page.get("properties", {})
        name_arr = props.get("Name", {}).get("title", [])
        title = name_arr[0].get("plain_text", "?")[:55] if name_arr else "?"
        vid_arr = props.get("Video ID", {}).get("rich_text", [])
        video_id = vid_arr[0].get("plain_text", "") if vid_arr else ""
        page_id = page["id"]

        if not video_id:
            print(f"[{i}/{len(pages)}] SKIP (no video_id): {title}")
            continue

        print(f"[{i}/{len(pages)}] {title}")
        print(f"  video_id: {video_id}")

        transcript, lang = fetch_transcript(video_id, languages)

        if transcript:
            ok = update_notion_page(nc, page_id, transcript, video_id)
            if ok:
                print(f"  -> OK ({lang}, {len(transcript.split())} words)")
                success += 1
            else:
                print("  -> Notion update failed")
                fail += 1
        else:
            print(f"  -> No transcript ({lang})")
            fail += 1

        if i < len(pages):
            time.sleep(args.delay)

    print()
    print("=" * 60)
    print(f"Done: success={success}, fail={fail}, total={len(pages)}")
    print(f"End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()

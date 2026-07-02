---
name: youtube-to-notion
description: >-
  YouTubeチャンネルの全動画情報（タイトル・文字起こし・サマリー）をNotionデータベースに保存し、
  NotebookLMのナレッジソースとして活用するパイプライン運用スキル。
  以下のとき必ず使う：「YouTubeチャンネルをNotionに保存して」「動画の文字起こしをNotionに入れて」
  「NotebookLM用にYouTubeを整理して」「yt-notion-digestを実行して」「チャンネルの動画をまとめて」
  「Notion動画DBが更新されない」「文字起こしが取れない」「YouTubeチャンネルURL」が含まれた依頼。
  yt-dlp（APIキー不要）でチャンネルをスクレイプ、youtube-transcript-apiで字幕取得、
  Notion APIでDBへupsertする。GitHub: univcorp2-ctrl/youtube-channel-notion-knowledge
---

# youtube-to-notion 運用スキル

YouTubeチャンネルURLを受け取り、全動画の文字起こし・サマリーをNotionナレッジベースDBに保存する。
NotebookLMのソースとして読み込むことで、チャンネル全体をAIが参照できる状態にする。

## 構成（前提知識）

- **リポジトリ**: `C:\Users\t0015\Documents\AI_Agent_LOCAL\youtube-channel-notion-knowledge`
- **実行コマンド**: `yt-notion-digest run --channel-url <URL> [--max-videos N]`
- **YouTube取得**: `yt-dlp`（APIキー不要。APIキーあれば YouTube Data API v3 を自動使用）
- **文字起こし**: `youtube-transcript-api`（自動生成字幕を優先: `ja,en`の順）
- **サマリー**: OpenAI GPT（`OPENAI_API_KEY`設定時）または extractive fallback（キー未設定時）
- **Notion sync**: Notion API v1（`ntn_E43853346674...` トークン）
- **対象DB**: `YouTube Channel Knowledge Base`（ID: `aa8e4d967b1f49a68e1ce512bf05bc28`）
- **.envファイル**: プロジェクトルートの `.env`（`NOTION_TOKEN`, `NOTION_DATABASE_ID` 必須）

## DBスキーマ（Notion）

| プロパティ | 型 | 内容 |
|---|---|---|
| Name | title | 動画タイトル |
| Video ID | rich_text | YouTube video_id（重複防止キー） |
| Video URL | url | `https://www.youtube.com/watch?v=...` |
| Channel | rich_text | チャンネル名 |
| Published | date | 公開日 |
| Status | select | done / missing_transcript / error / channel_summary |
| Word Count | number | サマリーの単語数 |
| Summary Model | rich_text | extractive / gpt-4o-mini / local-extractive-fallback 等 |
| Synced At | date | 最終同期日時 |

## 鉄則

1. **yt-dlpはチャンネルURLに `/videos` を付けて実行**。ルートURLだとタブ一覧が返り動画が取れない。
2. **`NOTION_DATABASE_ID`は`.env`から読む**。直接コードに埋めない。
3. **Codex integration がDB に接続されていること**。Notion側で「Connections → Codex」を追加する。
4. **upsertで重複防止**。`Video ID`プロパティで既存ページを検索→あればPATCH、なければPOST。
5. **OpenAIキーが無くても動く**。`OPENAI_API_KEY`未設定なら extractive fallback でサマリー生成。

## よくある依頼と対応手順

### A. 「チャンネルを新規登録してNotionに保存したい」

```powershell
cd "C:\Users\t0015\Documents\AI_Agent_LOCAL\youtube-channel-notion-knowledge"

# まず5件でテスト
yt-notion-digest run --channel-url "https://www.youtube.com/@CHANNEL_HANDLE" --max-videos 5

# 全件（バックグラウンド推奨）
$job = Start-Job {
  cd "C:\Users\t0015\Documents\AI_Agent_LOCAL\youtube-channel-notion-knowledge"
  yt-notion-digest run --channel-url "https://www.youtube.com/@CHANNEL_HANDLE"
}
Receive-Job $job
```

処理時間の目安：1動画あたり約30〜60秒（文字起こし取得込み）。

### B. 「Notionへの同期なし・ローカル保存のみ」

```powershell
yt-notion-digest run --channel-url "https://www.youtube.com/@lexfridman" --max-videos 5 --output-dir "data/test-run" --no-notion
```

`data/test-run/videos/` にMarkdownファイルが保存される。

### C. 「Notion syncだけ単独テスト」

```python
import sys, os; sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv(r'C:\Users\t0015\Documents\AI_Agent_LOCAL\youtube-channel-notion-knowledge\.env', override=True)
from yt_notion_digest.notion import NotionClient
nc = NotionClient(token=os.getenv('NOTION_TOKEN'), database_id=os.getenv('NOTION_DATABASE_ID'))
print('DB:', nc.database_id)
```

### D. 「Notion APIが `object_not_found` を返す」

Codex integrationがDBに接続されていない。
1. Notion DBページ → `...` → `Connections` → 検索で「Codex」→「Add to page」をクリック。
2. `.env`の`NOTION_DATABASE_ID`が正しいか確認（`aa8e4d967b1f49a68e1ce512bf05bc28`）。

### E. 「yt-dlpが動画を取得できない（タブ一覧が返る）」

`src/yt_notion_digest/youtube.py`の`YtDlpClient._videos_url()`が `/videos` サフィックスを付けているか確認:

```python
def _videos_url(channel_url: str) -> str:
    url = channel_url.rstrip("/")
    if not url.endswith("/videos"):
        url += "/videos"
    return url
```

### F. 「NotebookLMにソースとして追加したい」

1. `data/runs/latest/videos/*.md` ファイルをNotebookLMに直接アップロード、または
2. Notion DBページを共有設定で公開 → NotebookLM `Add source → Website` にURLを追加

## セットアップ（初回のみ）

```powershell
cd "C:\Users\t0015\Documents\AI_Agent_LOCAL\youtube-channel-notion-knowledge"

# 依存パッケージインストール
pip install yt-dlp youtube-transcript-api notion-client python-dotenv

# パッケージをeditable modeでインストール
pip install -e .

# .env設定
Copy-Item .env.example .env
# .envを編集してNOTION_TOKEN, NOTION_DATABASE_IDを記入
```

### 必須環境変数（`.env`）

```
NOTION_TOKEN=ntn_E43853346674S2T0YcUYVUCOGCQaOU4v7ZTyflXB8Sx5JL
NOTION_DATABASE_ID=aa8e4d967b1f49a68e1ce512bf05bc28
NOTION_INCLUDE_TRANSCRIPT=true
LANGUAGES=ja,en
MAX_VIDEOS=0
OUTPUT_DIR=data/runs/latest

# オプション（未設定でもextractiveサマリーで動作）
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
YOUTUBE_API_KEY=
```

## トークン予算への配慮

- 全動画取得は時間がかかるため、まず `--max-videos 5` でテスト
- `--no-notion` フラグで Notion API コールを省略しローカルのみ保存可能
- PowerShellから `Start-Job` でバックグラウンド実行推奨（タイムアウト回避）

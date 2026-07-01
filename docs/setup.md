# Setup Guide

## 目的

YouTubeチャンネルURLを渡すだけで、全公開アップロード動画を収集し、文字起こしと詳細サマリーをNotionへ保存できる状態にします。

## 1. YouTube Data API Key

1. Google Cloud Consoleでプロジェクトを作成します。
2. APIs & Servicesで YouTube Data API v3 を有効化します。
3. CredentialsでAPI keyを作成します。
4. GitHub Actions Secretsまたは `.env` に `YOUTUBE_API_KEY` として保存します。

このキーはチャンネルの公開アップロード一覧を網羅的に取得するために必要です。

## 2. Notion Integration

1. Notionの開発者ページでInternal Integrationを作成します。
2. Integration tokenをコピーします。
3. 保存先にしたいNotionページまたはデータベースに、そのIntegrationを招待します。
4. 既存DBを使う場合はDB IDを `NOTION_DATABASE_ID` に設定します。
5. 新規DBを自動作成する場合は、親ページIDを `NOTION_PARENT_PAGE_ID` に設定します。

既存DBを使う場合はREADMEのプロパティ表に合わせてください。初心者向けには `NOTION_PARENT_PAGE_ID` による自動DB作成が簡単です。

## 3. OpenAI API Key

`OPENAI_API_KEY` を設定すると、長い文字起こしを分割要約し、動画単位・チャンネル単位の詳細ノートへ統合します。未設定でも処理自体は動きますが、ローカル抽出型サマリーになります。

推奨環境変数:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.4-mini
OPENAI_MAX_OUTPUT_TOKENS=6000
```

高品質・長文処理を優先する場合は `OPENAI_MODEL` をより高性能なモデルに変更できます。

## 4. GitHub Actions Secrets

Repository Settings → Secrets and variables → Actions で以下を入れます。

Secrets:

- `YOUTUBE_API_KEY`
- `OPENAI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID` または `NOTION_PARENT_PAGE_ID`

Variables:

- `OPENAI_MODEL`
- `LANGUAGES`
- `NOTION_INCLUDE_TRANSCRIPT`
- `NOTION_DATABASE_TITLE`

## 5. 実行

Actions → CI → Run workflow を押し、次を入力します。

- `channel_url`: `https://youtube.com/@macamp0817?si=U7FfYoWVQQLMvJf0`
- `max_videos`: 初回は `3`、本番は `0`
- `sync_notion`: `true`

完了後、ActionsのArtifact `youtube-channel-knowledge-outputs` からローカル成果物も取得できます。

## 6. トラブルシュート

### 字幕が取れない動画がある

Notionとmanifestで `missing_transcript` になります。動画が非公開、限定公開、メンバー限定、年齢/地域制限、字幕なし、またはYouTube側ブロックの可能性があります。

### Notionで保存に失敗する

Integrationが対象ページ/DBに招待されているか確認してください。既存DBを使う場合は、READMEのプロパティ名と型が一致している必要があります。

### 全件実行が長い

チャンネルの動画数、字幕量、OpenAIモデル、Notion保存量に比例します。初回は `max_videos=3` で接続確認し、その後 `0` で全件実行してください。

### 費用が心配

OpenAI APIは文字起こしの長さと出力の長さに比例します。まず少数件で概算を確認してください。Notionにフル文字起こしを保存しない場合は `NOTION_INCLUDE_TRANSCRIPT=false` にできます。

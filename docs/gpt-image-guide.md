# GPT Image Guide Prompts

このリポジトリの運用手順を初心者向けの1枚画像にするためのプロンプト集です。READMEのMermaid図が技術者向けの全体像で、ここでは非エンジニア向けの視覚ガイドを作ります。

利用モデル例: `gpt-image-2`

## 1. 全体アーキテクチャ画像

```text
日本語の初心者向けインフォグラフィックを作成してください。テーマは「YouTubeチャンネルURLからNotionナレッジベースを自動作成する流れ」です。横長16:9。左から右へ、1) ユーザーがYouTubeチャンネルURLを入力、2) GitHub ActionsまたはWeb UIが起動、3) YouTube Data APIで全アップロード動画を取得、4) 各動画の字幕を取得、5) OpenAIで詳細サマリー化、6) Notionに動画ごとのページとチャンネル総合ページを保存、7) ArtifactとしてMarkdown/TXT/CSVを保存、という流れをアイコン付きで示してください。色は白背景、黒文字、アクセントは青と緑。専門用語には短い説明を添えてください。
```

## 2. Notion Integration設定画像

```text
日本語のステップバイステップ画像を作成してください。テーマは「Notion Integrationを作り、このアプリに接続する方法」です。縦長。Step 1 Notion DevelopersでInternal Integrationを作る、Step 2 Tokenをコピーする、Step 3 保存先ページにIntegrationを招待する、Step 4 NOTION_TOKENとNOTION_PARENT_PAGE_IDをGitHub Secretsに保存する、Step 5 GitHub Actionsを実行する。初心者でも迷わないよう、注意点として「TokenはChat欄やREADMEに貼らない」「Integrationをページに招待しないと保存できない」を強調してください。
```

## 3. GitHub Actions実行画像

```text
日本語の操作ガイド画像を作成してください。テーマは「GitHub ActionsでYouTubeチャンネル要約を実行する」です。横長16:9。GitHubの画面を抽象化したUIで、Actionsタブ、CI workflow、Run workflow、channel_url入力、max_videos入力、Runボタン、Artifactダウンロードの順番を矢印で示してください。初心者向けに、初回はmax_videos=3、本番はmax_videos=0と注記してください。
```

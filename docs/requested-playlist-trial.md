# Requested Playlist Notion Trial

## 対象

`https://youtube.com/playlist?list=PL0pHg9WQBbWZqnTu9vqMUdwsxRaZIB0Ja&si=robybr6RzkwhvWuk`

## 実装状態

プレイリストURL対応は実装済みです。`list=PL0pHg9WQBbWZqnTu9vqMUdwsxRaZIB0Ja` を抽出し、YouTube Data APIのplaylistItemsを全ページ走査して、字幕取得、動画単位の詳細要約、全体統合、Notion保存を実行します。

## 2026-07-02の試行結果

GitHub Actions workflow `Requested Playlist Notion Trial` を自動実行しました。依存関係インストールまでは成功しましたが、`Validate required secrets` で停止しました。

未設定だったSecrets:

- `YOUTUBE_API_KEY`
- `OPENAI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_DATABASE_ID` または `NOTION_PARENT_PAGE_ID`

秘密値はリポジトリやドキュメントへ直接書かず、Repository Settings → Secrets and variables → Actions → Repository secrets に保存してください。

## 再実行

Secrets設定後、GitHub Actionsの `Requested Playlist Notion Trial` を開き、`Run workflow` を実行します。対象プレイリストURLはworkflowに設定済みで、追加入力は不要です。

workflowは処理後に `result.json` を検査し、次の条件をすべて満たさなければ失敗扱いにします。

- Notion database IDが解決されている
- pipeline errorsが空
- `videos_processed` と `videos_found` が一致する

成功時はNotionへの全件同期が完了し、`requested-playlist-notion-trial-outputs` ArtifactにもMarkdown、TXT、JSON、CSVが保存されます。

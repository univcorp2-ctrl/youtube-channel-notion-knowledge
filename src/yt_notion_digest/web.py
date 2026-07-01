from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from yt_notion_digest.config import AppConfig
from yt_notion_digest.pipeline import PipelineOptions, YouTubeToNotionPipeline

app = FastAPI(title="YouTube Channel Notion Knowledge Base", version="0.1.0")


class RunRequest(BaseModel):
    channel_url: str = Field(..., description="YouTube channel URL, e.g. https://youtube.com/@handle")
    max_videos: int = Field(0, ge=0, description="0 means all public uploads")
    output_dir: str = "data/runs/web"
    sync_notion: bool = True


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>YouTube Channel → Notion Knowledge Base</title>
  <style>
    body { font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 920px; margin: 40px auto; padding: 0 20px; line-height: 1.7; }
    input, button { font-size: 16px; padding: 10px; width: 100%; box-sizing: border-box; margin: 8px 0; }
    button { cursor: pointer; background: #111827; color: white; border: 0; border-radius: 8px; }
    pre { background: #f3f4f6; padding: 16px; overflow: auto; border-radius: 8px; }
    label { font-weight: 700; }
  </style>
</head>
<body>
  <h1>YouTube Channel → Notion Knowledge Base</h1>
  <p>チャンネルURLを入力すると、公開アップロード一覧を取得し、字幕取得・詳細サマリー化・Notion同期を実行します。長いチャンネルはCLIまたはGitHub Actionsでの実行を推奨します。</p>
  <label>Channel URL</label>
  <input id="channelUrl" value="https://youtube.com/@macamp0817?si=U7FfYoWVQQLMvJf0" />
  <label>Max videos（0 = 全件）</label>
  <input id="maxVideos" type="number" min="0" value="3" />
  <button onclick="run()">Run</button>
  <pre id="output">Ready.</pre>
<script>
async function run() {
  const output = document.getElementById('output');
  output.textContent = 'Running. Large channels can take a long time. For production, use GitHub Actions workflow_dispatch.';
  try {
    const res = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        channel_url: document.getElementById('channelUrl').value,
        max_videos: Number(document.getElementById('maxVideos').value),
        output_dir: 'data/runs/web',
        sync_notion: true
      })
    });
    const json = await res.json();
    output.textContent = JSON.stringify(json, null, 2);
  } catch (err) {
    output.textContent = String(err);
  }
}
</script>
</body>
</html>
"""


@app.post("/api/run")
def run_pipeline(request: RunRequest) -> dict[str, object]:
    config = AppConfig.from_env()
    options = PipelineOptions(
        channel_url=request.channel_url,
        output_dir=Path(request.output_dir),
        max_videos=request.max_videos,
        languages=config.languages,
        translate_to=config.translate_to,
        sync_notion=request.sync_notion,
        include_transcript_in_notion=config.notion_include_transcript,
    )
    try:
        result = YouTubeToNotionPipeline(config).run(options)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
    return result.to_dict()

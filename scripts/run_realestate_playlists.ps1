# ============================================================
# run_realestate_playlists.ps1
# 不動産YouTubeプレイリスト → Notion DB 一括同期スクリプト
#
# 実行セッション情報:
#   Notion DB  : YouTube Channel Knowledge Base
#   DB ID      : aa8e4d967b1f49a68e1ce512bf05bc28
#   DB URL     : https://app.notion.com/p/aa8e4d967b1f49a68e1ce512bf05bc28
#   Token      : ntn_E43853346674S2T0... (Codex integration)
#   Repo       : C:\Users\t0015\Documents\AI_Agent_LOCAL\youtube-channel-notion-knowledge
#   Script     : scripts\run_realestate_playlists.ps1
# ============================================================

$REPO = "C:\Users\t0015\Documents\AI_Agent_LOCAL\youtube-channel-notion-knowledge"
$ENV_FILE = "$REPO\.env"
$LOG_DIR = "$REPO\logs"
New-Item -ItemType Directory -Force -Path $LOG_DIR | Out-Null

$playlists = @(
    @{ name="01_基礎セミナー";              url="https://www.youtube.com/playlist?list=PL0pHg9WQBbWZqnTu9vqMUdwsxRaZIB0Ja" },
    @{ name="02_実践編まとめ";              url="https://www.youtube.com/playlist?list=PL0pHg9WQBbWY6avImP3hocBBv9JK6Ocfh" },
    @{ name="03_ボリューム検討会_質問会";   url="https://www.youtube.com/playlist?list=PL0pHg9WQBbWYex7WXtCaCvaMMT7KJcx2G" },
    @{ name="04_バランス大家さん_土地から新築"; url="https://www.youtube.com/playlist?list=PL0pHg9WQBbWbpr_6xLe58MF2lk4onn3Gt" },
    @{ name="05_セミナーアーカイブまとめ";  url="https://www.youtube.com/playlist?list=PL0pHg9WQBbWZq0NaahmY4WilqjuBRlglZ" }
)

Write-Output "========================================================"
Write-Output "不動産YouTube -> Notion 一括同期"
Write-Output "開始: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output "Notion DB: https://app.notion.com/p/aa8e4d967b1f49a68e1ce512bf05bc28"
Write-Output "========================================================"

$jobs = @()
foreach ($pl in $playlists) {
    $logFile = "$LOG_DIR\$($pl.name).log"
    Write-Output "[$($pl.name)] 開始 URL: $($pl.url)"

    $job = Start-Job -Name $pl.name -ScriptBlock {
        param($repo, $envFile, $url, $name, $logFile)
        Set-Location $repo
        "START $(Get-Date): $name" | Out-File $logFile -Encoding UTF8
        "URL: $url" | Out-File $logFile -Append -Encoding UTF8
        & yt-notion-digest run --channel-url $url --env-file $envFile --output-dir "data/playlists/$name" 2>&1 |
            Out-File $logFile -Append -Encoding UTF8
        "END $(Get-Date) exit:$LASTEXITCODE" | Out-File $logFile -Append -Encoding UTF8
    } -ArgumentList $REPO, $ENV_FILE, $pl.url, $pl.name, $logFile

    $jobs += $job
    Write-Output "  -> Job #$($job.Id)"
    Start-Sleep -Seconds 3
}

Write-Output "========================================================"
Write-Output "[$($jobs.Count) jobs running in background]"
Write-Output "Log dir: $LOG_DIR"
Write-Output "Status:  Get-Job | ft Id,Name,State"
Write-Output "Logs:    Get-Content (Get-ChildItem logs\*.log)[0] -Tail 10"
Write-Output "========================================================"

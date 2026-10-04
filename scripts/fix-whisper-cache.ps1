# Fix broken faster-whisper HuggingFace cache on Windows (WinError 1314 symlinks).
$ErrorActionPreference = "Stop"

$env:HF_HUB_DISABLE_SYMLINKS = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

$cacheRoot = Join-Path $env:USERPROFILE ".cache\huggingface\hub"
$broken = @(
    "models--Systran--faster-whisper-small",
    "models--Systran--faster-whisper-base",
    "models--Systran--faster-whisper-medium"
)

Write-Host "HF_HUB_DISABLE_SYMLINKS=1 (copy mode, no symlinks)" -ForegroundColor Cyan

foreach ($name in $broken) {
    $path = Join-Path $cacheRoot $name
    if (Test-Path $path) {
        Write-Host "Removing broken cache: $path"
        Remove-Item -Recurse -Force $path
    }
}

$localCache = Join-Path (Split-Path -Parent $PSScriptRoot) "models\voice\hf-cache"
if (Test-Path $localCache) {
    Write-Host "Removing local hf-cache: $localCache"
    Remove-Item -Recurse -Force $localCache
}

Write-Host @"

Done. Re-run voice wake — Whisper will re-download using copies (no symlinks).

  .\.venv\Scripts\Activate.ps1
  emily voice wake --once

Optional: enable Windows Developer Mode to allow HF symlinks (Settings > System > For developers).
"@ -ForegroundColor Green

# Full multilingual voice stack: Kokoro + IndicF5 + Chatterbox + faster-whisper-small
# Chatterbox requires Python 3.11 (upstream). Main project venv may be 3.12.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$env:HF_HUB_DISABLE_SYMLINKS = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host "=== Emily full voice install (Python 3.11 venv) ===" -ForegroundColor Cyan

$py311 = Get-Command py -ErrorAction SilentlyContinue
if (-not $py311) {
    Write-Error "Python launcher 'py' not found. Install Python 3.11 from python.org"
}

& py -3.11 -c "import sys; print(sys.version)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python 3.11 not installed. Run: py install 3.11"
}

if (-not (Test-Path ".venv311")) {
    Write-Host "Creating .venv311 ..."
    & py -3.11 -m venv .venv311
}

Write-Host "Activating .venv311 ..."
& .\.venv311\Scripts\Activate.ps1

python -m pip install -U pip setuptools wheel
python -m pip install numpy

$packages = @(
  "packages/emily-core",
  "packages/emily-events",
  "packages/emily-config",
  "packages/emily-observability",
  "packages/emily-kernel",
  "packages/emily-providers",
  "packages/emily-voice",
  "apps/emily-cli"
)
foreach ($pkg in $packages) {
  Write-Host "Installing $pkg ..."
  python -m pip install -e $pkg
}

Write-Host "Installing voice extras (kokoro, asr, audio, indicf5, chatterbox) ..."
python -m pip install -e "packages/emily-voice[kokoro,asr,audio,indicf5,chatterbox]"

Write-Host "Installing IndicF5 + pinned transformers ..."
python -m pip install "transformers==4.49.0"
python -m pip install "git+https://github.com/ai4bharat/IndicF5.git"

Write-Host "Installing Chatterbox TTS ..."
python -m pip install chatterbox-tts

Write-Host @"

=== Full voice venv ready ===

Activate before voice commands:
  .\.venv311\Scripts\Activate.ps1

In .env set:
  TTS_ENABLE_CHATTERBOX=true
  TTS_ENABLE_INDICF5=true

IndicF5 (gated — login + accept license):
  hf auth login
  emily voice models --name indicf5-ref --download
  emily voice models --name indicf5 --download

Fix Windows Whisper cache if needed:
  powershell -File scripts/fix-whisper-cache.ps1

Test:
  emily voice wake --once
  python scripts/smoke_m8_voice_live.py
"@ -ForegroundColor Green

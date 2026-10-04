# Install Emily OS (dev) on Windows
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$packages = @(
  "packages/emily-core",
  "packages/emily-events",
  "packages/emily-config",
  "packages/emily-observability",
  "packages/emily-kernel",
  "packages/emily-providers",
  "packages/emily-missions",
  "packages/emily-agents",
  "packages/emily-memory",
  "packages/emily-tools",
  "packages/emily-desktop",
  "packages/emily-browser",
  "packages/emily-voice",
  "apps/emily-cli"
)

foreach ($pkg in $packages) {
  Write-Host "Installing $pkg ..."
  python -m pip install -e $pkg
}

Write-Host "Installing root + dev extras ..."
python -m pip install -e ".[dev]"

Write-Host "Installing emily-voice runtime extras (kokoro, asr, audio) ..."
python -m pip install -e "packages/emily-voice[kokoro,asr,audio]"

Write-Host @"
Done. Try: emily version
Optional large TTS (needs free disk + HF access):
  pip install chatterbox-tts
  pip install `"git+https://github.com/ai4bharat/IndicF5.git`"
Voice smoke:
  python scripts/smoke_m8_voice.py
  python scripts/smoke_m8_voice_live.py
"@

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
  "apps/emily-cli"
)

foreach ($pkg in $packages) {
  Write-Host "Installing $pkg ..."
  python -m pip install -e $pkg
}

Write-Host "Installing root + dev extras ..."
python -m pip install -e ".[dev]"

Write-Host "Done. Try: emily version"

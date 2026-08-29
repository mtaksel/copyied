$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python -m pip install -r requirements.txt pyinstaller
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name Copyied `
    --distpath (Join-Path $PSScriptRoot "dist") `
    --workpath (Join-Path $PSScriptRoot "build") `
    (Join-Path $PSScriptRoot "app.py")

Write-Host "Created: $PSScriptRoot\dist\Copyied.exe"

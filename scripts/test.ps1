$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & "$projectRoot\.venv\Scripts\python.exe" -m pytest -q
    exit $LASTEXITCODE
} finally { Pop-Location }

param([int]$Port = 8770)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & "$projectRoot\.venv\Scripts\python.exe" -m fabscope serve --port $Port
    exit $LASTEXITCODE
} finally { Pop-Location }

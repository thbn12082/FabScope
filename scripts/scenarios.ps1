param([string]$Id = 'all')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot
try {
    & "$projectRoot\.venv\Scripts\python.exe" -m fabscope scenarios --id $Id
    exit $LASTEXITCODE
} finally { Pop-Location }

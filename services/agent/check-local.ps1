param(
    [switch]$Install,
    [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$venvPython = Join-Path $here '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host 'Creating local agent virtual environment...'
    python -m venv (Join-Path $here '.venv')
}

if ($Install) {
    Write-Host 'Installing local agent dependencies...'
    & $venvPython -m pip install -r (Join-Path $here 'requirements.txt')
}

if (-not $SkipTests) {
    Write-Host 'Running local agent tests...'
    & $venvPython -m pytest tests -v
}

Write-Host 'Running local datastore smoke check...'
& $venvPython -m app.data_store

Write-Host ''
if (Test-Path (Join-Path $here 'app\main.py')) {
    Write-Host 'FastAPI app is present. Start it with:'
    Write-Host '  .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8100'
} else {
    Write-Host 'FastAPI app is not implemented yet. Current local layer provides seeded/runtime datastore for the next agent API task.'
}

param(
    [int]$ApiPort = 8000
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "Starting backend API on port $ApiPort ..."
& "$root\.venv\Scripts\python.exe" "$root\app-api\run.py"

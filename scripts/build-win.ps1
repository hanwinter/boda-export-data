$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = "$root\.venv\Scripts\python.exe"

Write-Host "[1/4] Build backend executable (PyInstaller)..."
Push-Location "$root\app-api"
& $python -m pip install -r "$root\app-api\requirements.txt"
& $python -m pip install pyinstaller
& $python -m PyInstaller --noconfirm --clean --onefile --name boda-api --paths "$root\app-api" --collect-all passlib --collect-all pymysql --collect-all pymssql --collect-all pyodbc --hidden-import sqlalchemy.dialects.mysql.pymysql --hidden-import sqlalchemy.dialects.mssql.pymssql --hidden-import sqlalchemy.dialects.mssql.pyodbc --hidden-import pyodbc "$root\app-api\desktop_server.py"
Pop-Location

Write-Host "[2/4] Build frontend..."
Push-Location "$root\app-web"
npm install
npm run build
Pop-Location

Write-Host "[3/4] Install desktop dependencies..."
Push-Location "$root\app-desktop"
npm install

Write-Host "[4/4] Build Windows installer..."
npm run build
Pop-Location

Write-Host "Done. Installer is under app-desktop\\dist"

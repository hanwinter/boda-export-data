# boda-export-data

Windows single-machine C/S application for:

1. Connecting to existing SQLServer/MySQL.
2. Reading org/person/exam data.
3. Showing data in frontend.
4. Exporting to Excel with abnormal values marked in red.

## Structure

- `app-api`: FastAPI backend.
- `app-web`: React frontend.
- `app-desktop`: Electron desktop app.
- `config`: app/db/export/view/dict settings.
- `scripts`: helper scripts.

## Run (Web + API)

```powershell
cd "D:\project\boda-export-data"
.\.venv\Scripts\Activate.ps1
python .\app-api\run.py

cd "D:\project\boda-export-data\app-web"
npm install
npm run dev
```

## Desktop (Installer)

Build installer:

```powershell
cd "D:\project\boda-export-data"
.\scripts\build-win.ps1
```

Run desktop in dev mode:

```powershell
cd "D:\project\boda-export-data\app-desktop"
npm install
npm run dev
```

## Export Path Selection

- In desktop mode, export dialog supports native "选择目录" button.
- In browser mode, enter path manually.

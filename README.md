# boda-export-data

Windows single-machine C/S application skeleton for:

1. Connecting to existing MySQL.
2. Reading org/person/exam/abnormal data.
3. Showing data in frontend.
4. Exporting to Excel with abnormal values marked in red.

## Structure

- `app-api`: FastAPI backend.
- `app-web`: frontend placeholder.
- `app-desktop`: Electron packaging placeholder.
- `config`: app/db/export settings.
- `scripts`: start/build helper scripts.
- `设计记录.md`: discussion and architecture notes.

## Quick Start (Backend)

```powershell
cd "D:\project\boda-export-data"
.\.venv\Scripts\Activate.ps1
pip install -r .\app-api\requirements.txt
python .\app-api\run.py
```

Open:

- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/health`

## Next

1. Replace mock repository with MySQL table mapping.
2. Implement React page in `app-web`.
3. Integrate Electron one-click startup in `app-desktop`.

# boda-export-data

Windows single-machine C/S application skeleton for:

1. Connecting to existing MySQL.
2. Reading org/person/exam/abnormal data.
3. Showing data in frontend.
4. Exporting to Excel with abnormal values marked in red.

## Structure

- `app-api`: FastAPI backend.
- `app-web`: React frontend.
- `app-desktop`: Electron packaging placeholder.
- `config`: app/db/export/view/dict settings.
- `scripts`: start/build helper scripts.
- `设计记录.md`: discussion and architecture notes.

## Quick Start

```powershell
cd "D:\project\boda-export-data"
.\.venv\Scripts\Activate.ps1
pip install -r .\app-api\requirements.txt
cd .\app-web && npm install
```

Run backend:

```powershell
cd "D:\project\boda-export-data"
python .\app-api\run.py
```

Run frontend:

```powershell
cd "D:\project\boda-export-data\app-web"
npm run dev
```

## MySQL View Integration

1. Edit `config/db.yaml`
- set `enabled: true`
- fill host/port/user/password/database/view_name

2. Edit `config/view_mapping.yaml`
- map standard fields to your view columns

3. Edit `config/dict_mapping.yaml`
- map source enum values to frontend standard values

4. Restart backend and test `/api/records`.

If db config is incomplete or unavailable, backend automatically falls back to mock data.

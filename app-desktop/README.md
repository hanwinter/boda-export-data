# app-desktop

Electron desktop shell for local install and run.

## Features

1. Package frontend as desktop app.
2. Export directory chooser via native OS dialog.
3. Build Windows installer (NSIS).

## Dev Run

```powershell
cd "D:\project\boda-export-data\app-desktop"
npm install
npm run dev
```

## Build Installer

```powershell
cd "D:\project\boda-export-data"
.\scripts\build-win.ps1
```

Output directory:

- `app-desktop\dist`

Note:

- Desktop app loads frontend only. Backend API should be running at `http://127.0.0.1:8000`.

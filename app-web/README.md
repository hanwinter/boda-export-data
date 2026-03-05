# app-web

React frontend for browsing and exporting medical exam records.

## Features

1. Login with username/password (JWT auth).
2. Admin user management: list, create, enable/disable, reset password.
3. Filter by org, keyword, exam no, status, summary date, final date, and abnormal-only flag.
4. Show records table with expandable project-group and item details.
5. Export with optional output directory and selected project groups.

## Demo Accounts

- `admin / admin123`
- `viewer / viewer123`

## Run

```powershell
cd "D:\project\boda-export-data\app-web"
npm install
npm run dev
```

Default URL: `http://127.0.0.1:5173`

Backend API base URL is configured in `src/api.js`:

- `http://127.0.0.1:8000`

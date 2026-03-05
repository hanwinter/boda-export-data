from __future__ import annotations

from datetime import date

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.models import ExportRequest, ExportResponse, RecordsResponse
from app.services.data_service import list_orgs, list_records, list_records_for_export
from app.services.export_service import export_records

app = FastAPI(title="Boda Export Data API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/orgs")
def get_orgs():
    return list_orgs()


@app.get("/api/records", response_model=RecordsResponse)
def get_records(
    org_id: str | None = None,
    keyword: str | None = None,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    only_abnormal: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
):
    total, items = list_records(org_id, keyword, start_date, end_date, only_abnormal, page, page_size)
    return RecordsResponse(total=total, page=page, page_size=page_size, items=items)


@app.post("/api/export", response_model=ExportResponse)
def post_export(payload: ExportRequest):
    records = list_records_for_export(
        payload.org_id,
        payload.keyword,
        payload.start_date,
        payload.end_date,
        payload.only_abnormal,
    )
    file_name, file_path = export_records(records)
    return ExportResponse(file_name=file_name, file_path=file_path)

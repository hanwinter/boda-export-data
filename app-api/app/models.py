from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class Org(BaseModel):
    org_id: str
    org_name: str


class ExamRecord(BaseModel):
    record_id: str
    org_id: str
    org_name: str
    person_id: str
    person_name: str
    gender: str | None = None
    id_no: str | None = None
    exam_date: date
    item_code: str
    item_name: str
    result_value: str
    unit: str | None = None
    ref_range: str | None = None
    is_abnormal: bool
    abnormal_flag: str | None = None


class RecordsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ExamRecord]


class ExportRequest(BaseModel):
    org_id: str | None = None
    keyword: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    only_abnormal: bool = False


class ExportResponse(BaseModel):
    file_name: str
    file_path: str

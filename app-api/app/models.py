from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class Org(BaseModel):
    org_id: str
    org_name: str


class UserInfo(BaseModel):
    username: str
    role: str


class UserManageItem(BaseModel):
    username: str
    role: str
    is_active: bool


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    role: str = Field(default="viewer")


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class ResetPasswordRequest(BaseModel):
    new_password: str | None = Field(default=None, min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class ExamItem(BaseModel):
    item_name: str
    result_value: str
    unit: str | None = None
    ref_range: str | None = None
    is_abnormal: bool
    abnormal_flag: str | None = None


class ExamProjectGroup(BaseModel):
    group_name: str
    group_is_abnormal: bool
    abnormal_count: int
    items: list[ExamItem]


class ExamSummaryRecord(BaseModel):
    record_id: str
    org_id: str
    org_name: str
    person_id: str
    person_name: str
    gender: str | None = None
    id_no: str | None = None
    phone: str | None = None
    exam_no: str
    summary_date: date | None = None
    final_date: date | None = None
    exam_status: str
    has_abnormal: bool
    project_groups: list[ExamProjectGroup]


class RecordsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ExamSummaryRecord]


class ExportRequest(BaseModel):
    org_id: str | None = None
    keyword: str | None = None
    exam_no: str | None = None
    exam_status: str | None = None
    summary_start_date: date | None = None
    summary_end_date: date | None = None
    final_start_date: date | None = None
    final_end_date: date | None = None
    only_abnormal: bool = False
    export_dir: str | None = None
    selected_groups: list[str] | None = None


class ExportResponse(BaseModel):
    file_name: str
    file_path: str

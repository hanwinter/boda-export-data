from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from app.core.dependencies import get_current_user, require_admin
from app.core.security import create_access_token
from app.models import (
    CreateUserRequest,
    ExportRequest,
    ExportResponse,
    LoginRequest,
    LoginResponse,
    RecordsResponse,
    ResetPasswordRequest,
    UpdateUserStatusRequest,
    UserInfo,
    UserManageItem,
)
from app.services.auth_service import (
    authenticate_user,
    create_user,
    list_users,
    reset_password,
    set_user_active,
)
from app.services.data_service import list_orgs, list_project_groups, list_records, list_records_for_export
from app.services.export_service import export_records

app = FastAPI(title="Boda Export Data API", version="0.4.0")

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


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    token = create_access_token(user.username)
    return LoginResponse(access_token=token, user=UserInfo(username=user.username, role=user.role))


@app.get("/api/auth/me", response_model=UserInfo)
def me(current_user: UserInfo = Depends(get_current_user)):
    return current_user


@app.get("/api/users", response_model=list[UserManageItem])
def get_users(_: UserInfo = Depends(require_admin)):
    return [UserManageItem(username=u.username, role=u.role, is_active=u.is_active) for u in list_users()]


@app.post("/api/users", response_model=UserManageItem)
def post_user(payload: CreateUserRequest, _: UserInfo = Depends(require_admin)):
    try:
        user = create_user(payload.username.strip(), payload.password, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return UserManageItem(username=user.username, role=user.role, is_active=user.is_active)


@app.patch("/api/users/{username}/status", response_model=UserManageItem)
def patch_user_status(
    username: str,
    payload: UpdateUserStatusRequest,
    current_user: UserInfo = Depends(require_admin),
):
    if username == current_user.username and not payload.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能禁用当前登录管理员")
    try:
        user = set_user_active(username, payload.is_active)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UserManageItem(username=user.username, role=user.role, is_active=user.is_active)


@app.post("/api/users/{username}/reset-password", response_model=UserManageItem)
def post_reset_password(
    username: str,
    payload: ResetPasswordRequest,
    _: UserInfo = Depends(require_admin),
):
    new_password = payload.new_password or "123456"
    try:
        user = reset_password(username, new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UserManageItem(username=user.username, role=user.role, is_active=user.is_active)


@app.get("/api/orgs")
def get_orgs(_: UserInfo = Depends(get_current_user)):
    return list_orgs()


@app.get("/api/project-groups")
def get_project_groups(_: UserInfo = Depends(get_current_user)):
    return list_project_groups()


@app.get("/api/records", response_model=RecordsResponse)
def get_records(
    org_id: str | None = None,
    keyword: str | None = None,
    exam_no: str | None = None,
    exam_status: str | None = None,
    summary_start_date: date | None = Query(default=None),
    summary_end_date: date | None = Query(default=None),
    final_start_date: date | None = Query(default=None),
    final_end_date: date | None = Query(default=None),
    only_abnormal: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    _: UserInfo = Depends(get_current_user),
):
    total, items = list_records(
        org_id,
        keyword,
        exam_no,
        exam_status,
        summary_start_date,
        summary_end_date,
        final_start_date,
        final_end_date,
        only_abnormal,
        page,
        page_size,
    )
    return RecordsResponse(total=total, page=page, page_size=page_size, items=items)


@app.post("/api/export", response_model=ExportResponse)
def post_export(payload: ExportRequest, _: UserInfo = Depends(get_current_user)):
    records = list_records_for_export(
        payload.org_id,
        payload.keyword,
        payload.exam_no,
        payload.exam_status,
        payload.summary_start_date,
        payload.summary_end_date,
        payload.final_start_date,
        payload.final_end_date,
        payload.only_abnormal,
    )
    file_name, file_path = export_records(records, payload.export_dir, payload.selected_groups)
    return ExportResponse(file_name=file_name, file_path=file_path)

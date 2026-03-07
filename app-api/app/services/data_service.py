from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text

from app.core.settings import load_app_config, load_db_config, load_dict_mapping, load_view_mapping
from app.models import ExamItem, ExamProjectGroup, ExamSummaryRecord, Org


ORGS = [
    Org(org_id="org-001", org_name="Org A"),
    Org(org_id="org-002", org_name="Org B"),
]


MOCK_RECORDS = [
    ExamSummaryRecord(
        record_id="rec-1001",
        org_id="org-001",
        org_name="Org A",
        person_id="p-001",
        person_name="Test User",
        gender="M",
        id_no="320101199001011234",
        phone="13800001111",
        exam_no="TJ20260001",
        summary_date=date(2026, 2, 17),
        final_date=date(2026, 2, 18),
        exam_status="DONE",
        has_abnormal=True,
        project_groups=[
            ExamProjectGroup(
                group_name="CBC",
                group_is_abnormal=True,
                abnormal_count=1,
                items=[
                    ExamItem(
                        item_name="RBC",
                        result_value="3.92",
                        unit="10^12/L",
                        ref_range="4.30-5.80",
                        is_abnormal=True,
                        abnormal_flag="L",
                    ),
                    ExamItem(
                        item_name="WBC",
                        result_value="6.2",
                        unit="10^9/L",
                        ref_range="3.5-9.5",
                        is_abnormal=False,
                        abnormal_flag="N",
                    ),
                ],
            )
        ],
    )
]


SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_$.]+$")

_META_CACHE: dict[str, tuple[float, Any]] = {}
_TOTAL_CACHE: dict[str, tuple[float, int]] = {}
logger = logging.getLogger(__name__)


class DataSourceError(RuntimeError):
    pass


def _cache_get(cache: dict[str, tuple[float, Any]], key: str):
    now = time.time()
    item = cache.get(key)
    if not item:
        return None
    exp, value = item
    if exp < now:
        cache.pop(key, None)
        return None
    return value


def _cache_set(cache: dict[str, tuple[float, Any]], key: str, value: Any, ttl: int) -> None:
    cache[key] = (time.time() + max(ttl, 1), value)


def _normalize_date_filters(
    summary_start_date: date | None,
    summary_end_date: date | None,
    final_start_date: date | None,
    final_end_date: date | None,
) -> tuple[date | None, date | None, date | None, date | None]:
    if summary_start_date or summary_end_date or final_start_date or final_end_date:
        return summary_start_date, summary_end_date, final_start_date, final_end_date

    days = max(load_app_config().default_query_days, 1)
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    return start_date, end_date, final_start_date, final_end_date


def _make_total_cache_key(view_name: str, where_sql: str, params: dict[str, Any]) -> str:
    normalized = {}
    for k, v in sorted(params.items()):
        if isinstance(v, (date, datetime)):
            normalized[k] = v.isoformat()
        else:
            normalized[k] = str(v)
    raw = json.dumps({"view": view_name, "where": where_sql, "params": normalized}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _safe_id(name: str) -> str:
    if not name or not SAFE_ID_RE.match(name):
        raise ValueError("invalid identifier")
    return name


def _build_engine():
    cfg = load_db_config()
    if not cfg.enabled or not cfg.host or not cfg.database or not cfg.user:
        return None

    if cfg.db_type == "sqlserver":
        preferred_driver = os.getenv("BODA_SQLSERVER_ODBC_DRIVER", "").strip()
        driver_candidates = [preferred_driver] if preferred_driver else [
            "ODBC Driver 18 for SQL Server",
            "ODBC Driver 17 for SQL Server",
            "SQL Server",
        ]

        available: list[str] = []
        selected_driver = driver_candidates[0]
        pyodbc_error: str | None = None

        try:
            import pyodbc  # type: ignore

            available = [d.strip() for d in pyodbc.drivers() if d.strip()]
            for drv in driver_candidates:
                if drv in available:
                    selected_driver = drv
                    break

            odbc_connect = (
                f"DRIVER={{{selected_driver}}};"
                f"SERVER={cfg.host},{cfg.port};"
                f"DATABASE={cfg.database};"
                f"UID={cfg.user};"
                f"PWD={cfg.password};"
                "Encrypt=no;"
                "TrustServerCertificate=yes;"
            )
            pyodbc_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_connect)}"
            logger.info("SQLServer engine using pyodbc driver: %s", selected_driver)
            return create_engine(pyodbc_url, pool_pre_ping=True)
        except Exception as exc:
            pyodbc_error = (
                "SQLServer pyodbc init failed; "
                f"driver={selected_driver}; available_drivers={available}; error={exc}"
            )
            logger.warning(pyodbc_error)

        try:
            user = quote_plus(cfg.user)
            password = quote_plus(cfg.password)
            pymssql_url = f"mssql+pymssql://{user}:{password}@{cfg.host}:{cfg.port}/{cfg.database}"
            logger.info("SQLServer engine fallback to pymssql")
            return create_engine(pymssql_url, pool_pre_ping=True)
        except Exception as exc:
            raise RuntimeError(
                "SQLServer connection init failed for both pyodbc and pymssql; "
                f"pyodbc_error={pyodbc_error}; pymssql_error={exc}"
            ) from exc

    password = quote_plus(cfg.password)
    url = f"mysql+pymysql://{cfg.user}:{password}@{cfg.host}:{cfg.port}/{cfg.database}?charset=utf8mb4"
    return create_engine(url, pool_pre_ping=True)


def _get_mapping() -> dict[str, str]:
    return (load_view_mapping().get("fields", {}) or {}).copy()


def _get_source_field(std_field: str, mapping: dict[str, str]) -> str | None:
    val = mapping.get(std_field)
    return _safe_id(val) if val else None


def _get_view_name() -> str | None:
    cfg = load_db_config()
    view_name = cfg.view_name or (load_view_mapping().get("view", {}) or {}).get("source_name", "")
    return _safe_id(view_name) if view_name else None


def _fmt(value: Any) -> str:
    if value is None:
        return ""

    text_value: str
    if isinstance(value, (bytes, bytearray)):
        for enc in ("utf-8", "gbk", "gb18030", "latin-1"):
            try:
                text_value = value.decode(enc)
                break
            except Exception:
                continue
        else:
            text_value = str(value)
    else:
        text_value = str(value)

    # Fix common SQLServer mojibake like '??' -> '?', '??' -> '?'
    if text_value and all(ord(ch) <= 0x00FF for ch in text_value):
        try:
            recovered = text_value.encode("latin-1").decode("gbk")
            if recovered:
                return recovered
        except Exception:
            pass

    return text_value


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return None


def _parse_float_safe(text_value: str) -> float | None:
    value = text_value.strip()
    value = value.replace("?", ",").replace("?", "-").replace("?", "-")
    if not value:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _is_numeric_result_out_of_range(result_value: str, ref_range: str) -> bool:
    result_num = _parse_float_safe(result_value)
    if result_num is None:
        return False

    rr = ref_range.strip().replace(" ", "")
    if not rr:
        return False

    # a-b or a~b
    if "-" in rr or "~" in rr:
        splitter = "-" if "-" in rr else "~"
        parts = rr.split(splitter)
        if len(parts) == 2:
            lo = _parse_float_safe(parts[0])
            hi = _parse_float_safe(parts[1])
            if lo is not None and hi is not None:
                return result_num < lo or result_num > hi

    # <=x, <x, >=x, >x
    for op in ("<=", ">=", "<", ">"):
        if rr.startswith(op):
            bound = _parse_float_safe(rr[len(op):])
            if bound is None:
                return False
            if op == "<=":
                return result_num > bound
            if op == "<":
                return result_num >= bound
            if op == ">=":
                return result_num < bound
            if op == ">":
                return result_num <= bound

    return False


def _read_cell(row: dict[str, Any], field: str | None) -> Any:
    if not field:
        return None
    if field in row:
        return row[field]
    lower_field = field.lower()
    for key in row.keys():
        if str(key).lower() == lower_field:
            return row[key]
    return None


def _build_filters_sql(
    mapping: dict[str, str],
    org_id: str | None,
    keyword: str | None,
    exam_no: str | None,
    exam_status: str | None,
    summary_start_date: date | None,
    summary_end_date: date | None,
    final_start_date: date | None,
    final_end_date: date | None,
    only_abnormal: bool,
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    clauses = ["1=1"]

    org_field = _get_source_field("org_name", mapping)
    name_field = _get_source_field("person_name", mapping)
    phone_field = _get_source_field("phone", mapping)
    exam_no_field = _get_source_field("exam_no", mapping)
    exam_status_field = _get_source_field("exam_status", mapping)
    summary_date_field = _get_source_field("summary_date", mapping)
    final_date_field = _get_source_field("final_date", mapping)
    abnormal_flag_field = _get_source_field("abnormal_flag", mapping)

    if org_id and org_field:
        clauses.append(f"{org_field} = :org_id")
        params["org_id"] = org_id

    if keyword:
        kw = f"%{keyword.strip()}%"
        sub = []
        if name_field:
            sub.append(f"{name_field} LIKE :kw")
        if phone_field:
            sub.append(f"{phone_field} LIKE :kw")
        if sub:
            clauses.append("(" + " OR ".join(sub) + ")")
            params["kw"] = kw

    if exam_no and exam_no_field:
        clauses.append(f"{exam_no_field} LIKE :exam_no")
        params["exam_no"] = f"%{exam_no.strip()}%"

    if exam_status and exam_status_field:
        status_map = load_dict_mapping().get("exam_status", {})
        reverse_map = {v: k for k, v in status_map.items()}
        raw_status = reverse_map.get(exam_status, exam_status)
        clauses.append(f"{exam_status_field} = :exam_status")
        params["exam_status"] = raw_status

    if summary_start_date and summary_date_field:
        clauses.append(f"{summary_date_field} >= :summary_start")
        params["summary_start"] = summary_start_date
    if summary_end_date and summary_date_field:
        clauses.append(f"{summary_date_field} < :summary_end_next")
        params["summary_end_next"] = summary_end_date + timedelta(days=1)

    if final_start_date and final_date_field:
        clauses.append(f"{final_date_field} >= :final_start")
        params["final_start"] = final_start_date
    if final_end_date and final_date_field:
        clauses.append(f"{final_date_field} < :final_end_next")
        params["final_end_next"] = final_end_date + timedelta(days=1)

    if only_abnormal and abnormal_flag_field:
        normal_values = [k.lower() for k in load_dict_mapping().get("abnormal_flag_normal_values", {}).keys()]
        clauses.append(f"{abnormal_flag_field} IS NOT NULL")
        clauses.append(f"LTRIM(RTRIM(CONCAT('', {abnormal_flag_field}))) <> ''")
        if normal_values:
            ph = []
            for idx, value in enumerate(normal_values):
                key = f"abn_normal_{idx}"
                params[key] = value
                ph.append(f":{key}")
            clauses.append(f"LOWER(CONCAT('', {abnormal_flag_field})) NOT IN ({', '.join(ph)})")

    return " AND ".join(clauses), params


def _build_records_from_rows(rows: list[dict[str, Any]]) -> list[ExamSummaryRecord]:
    mapping = _get_mapping()
    dicts = load_dict_mapping()
    gender_map = dicts.get("gender", {})
    exam_status_map = dicts.get("exam_status", {})
    normal_abnormal_values = {k.lower() for k in dicts.get("abnormal_flag_normal_values", {}).keys()}

    grouped: dict[str, dict[str, Any]] = {}

    for row in rows:
        org_name = _fmt(_read_cell(row, _get_source_field("org_name", mapping)))
        exam_no = _fmt(_read_cell(row, _get_source_field("exam_no", mapping)))
        person_name = _fmt(_read_cell(row, _get_source_field("person_name", mapping)))
        gender_raw = _fmt(_read_cell(row, _get_source_field("gender", mapping)))
        phone = _fmt(_read_cell(row, _get_source_field("phone", mapping)))

        summary_date = _to_date(_read_cell(row, _get_source_field("summary_date", mapping)))
        final_date = _to_date(_read_cell(row, _get_source_field("final_date", mapping)))

        exam_status_raw = _fmt(_read_cell(row, _get_source_field("exam_status", mapping)))
        exam_status = exam_status_map.get(exam_status_raw, exam_status_raw)

        key = exam_no or f"{org_name}|{person_name}|{summary_date}"
        if key not in grouped:
            grouped[key] = {
                "record_id": key,
                "org_id": org_name,
                "org_name": org_name,
                "person_id": key,
                "person_name": person_name,
                "gender": gender_map.get(gender_raw, gender_raw),
                "phone": phone,
                "exam_no": exam_no,
                "summary_date": summary_date,
                "final_date": final_date,
                "exam_status": exam_status,
                "groups": {},
            }

        group_name = _fmt(_read_cell(row, _get_source_field("group_name", mapping))) or "Ungrouped"
        item_name = _fmt(_read_cell(row, _get_source_field("item_name", mapping)))
        result_value = _fmt(_read_cell(row, _get_source_field("result_value", mapping)))
        unit = _fmt(_read_cell(row, _get_source_field("unit", mapping)))
        ref_range = _fmt(_read_cell(row, _get_source_field("ref_range", mapping)))
        abnormal_flag = _fmt(_read_cell(row, _get_source_field("abnormal_flag", mapping)))

        by_flag = bool(abnormal_flag.strip()) and abnormal_flag.strip().lower() not in normal_abnormal_values
        by_range = _is_numeric_result_out_of_range(result_value, ref_range)
        is_abnormal = by_flag or by_range

        groups = grouped[key]["groups"]
        if group_name not in groups:
            groups[group_name] = {
                "group_name": group_name,
                "group_is_abnormal": False,
                "abnormal_count": 0,
                "items": [],
            }

        groups[group_name]["items"].append(
            ExamItem(
                item_name=item_name,
                result_value=result_value,
                unit=unit or None,
                ref_range=ref_range or None,
                is_abnormal=is_abnormal,
                abnormal_flag=abnormal_flag or None,
            )
        )

        if is_abnormal:
            groups[group_name]["group_is_abnormal"] = True
            groups[group_name]["abnormal_count"] += 1

    records: list[ExamSummaryRecord] = []
    for payload in grouped.values():
        group_models = [
            ExamProjectGroup(
                group_name=g["group_name"],
                group_is_abnormal=g["group_is_abnormal"],
                abnormal_count=g["abnormal_count"],
                items=g["items"],
            )
            for g in payload["groups"].values()
        ]
        records.append(
            ExamSummaryRecord(
                record_id=payload["record_id"],
                org_id=payload["org_id"],
                org_name=payload["org_name"],
                person_id=payload["person_id"],
                person_name=payload["person_name"],
                gender=payload["gender"] or None,
                id_no=None,
                phone=payload["phone"] or None,
                exam_no=payload["exam_no"],
                summary_date=payload["summary_date"],
                final_date=payload["final_date"],
                exam_status=payload["exam_status"],
                has_abnormal=any(g.group_is_abnormal for g in group_models),
                project_groups=group_models,
            )
        )
    return records


def _fetch_records_db_paged(
    org_id: str | None,
    keyword: str | None,
    exam_no: str | None,
    exam_status: str | None,
    summary_start_date: date | None,
    summary_end_date: date | None,
    final_start_date: date | None,
    final_end_date: date | None,
    only_abnormal: bool,
    page: int,
    page_size: int,
) -> tuple[int, list[ExamSummaryRecord]]:
    engine = _build_engine()
    if engine is None:
        raise RuntimeError("db disabled")

    cfg = load_db_config()
    mapping = _get_mapping()
    view_name = _get_view_name()
    if not view_name:
        raise RuntimeError("view name missing")

    exam_no_field = _get_source_field("exam_no", mapping)
    if not exam_no_field:
        raise RuntimeError("exam_no mapping missing")

    where_sql, params = _build_filters_sql(
        mapping,
        org_id,
        keyword,
        exam_no,
        exam_status,
        summary_start_date,
        summary_end_date,
        final_start_date,
        final_end_date,
        only_abnormal,
    )

    with engine.connect() as conn:
        total_key = _make_total_cache_key(view_name, where_sql, params)
        total_cached = _cache_get(_TOTAL_CACHE, total_key)
        if total_cached is None:
            count_sql = text(f"SELECT COUNT(DISTINCT {exam_no_field}) AS total FROM {view_name} WHERE {where_sql}")
            total = int(conn.execute(count_sql, params).scalar() or 0)
            _cache_set(_TOTAL_CACHE, total_key, total, load_app_config().cache_ttl_total_seconds)
        else:
            total = int(total_cached)

        if total == 0:
            return 0, []

        offset = max(page - 1, 0) * page_size
        key_params = dict(params)
        key_params["_offset"] = offset
        key_params["_limit"] = page_size

        final_date_field = _get_source_field("final_date", mapping)
        summary_date_field = _get_source_field("summary_date", mapping)
        sort_final = final_date_field or summary_date_field or exam_no_field
        sort_summary = summary_date_field or exam_no_field

        if cfg.db_type == "sqlserver":
            page_sql_str = (
                f"SELECT {exam_no_field} AS exam_no_key, "
                f"MAX({sort_final}) AS sort_final, MAX({sort_summary}) AS sort_summary "
                f"FROM {view_name} WHERE {where_sql} "
                f"GROUP BY {exam_no_field} "
                f"ORDER BY sort_final DESC, sort_summary DESC, exam_no_key DESC "
                f"OFFSET :_offset ROWS FETCH NEXT :_limit ROWS ONLY"
            )
        else:
            page_sql_str = (
                f"SELECT {exam_no_field} AS exam_no_key, "
                f"MAX({sort_final}) AS sort_final, MAX({sort_summary}) AS sort_summary "
                f"FROM {view_name} WHERE {where_sql} "
                f"GROUP BY {exam_no_field} "
                f"ORDER BY sort_final DESC, sort_summary DESC, exam_no_key DESC "
                f"LIMIT :_limit OFFSET :_offset"
            )

        key_rows = conn.execute(text(page_sql_str), key_params).mappings().all()
        page_exam_nos = [str(r["exam_no_key"]) for r in key_rows if r.get("exam_no_key") is not None]
        if not page_exam_nos:
            return total, []

        in_params = dict(params)
        placeholders = []
        for i, no in enumerate(page_exam_nos):
            key = f"_exam_no_{i}"
            in_params[key] = no
            placeholders.append(f":{key}")

        group_field = _get_source_field("group_name", mapping)
        item_field = _get_source_field("item_name", mapping)
        final_date_field = _get_source_field("final_date", mapping)
        summary_date_field = _get_source_field("summary_date", mapping)
        order_parts = [p for p in [final_date_field, summary_date_field, exam_no_field, group_field, item_field] if p]

        detail_sql = text(
            f"SELECT * FROM {view_name} WHERE {where_sql} "
            f"AND {exam_no_field} IN ({', '.join(placeholders)}) "
            f"ORDER BY {', '.join(order_parts)}"
        )
        detail_rows = [dict(r) for r in conn.execute(detail_sql, in_params).mappings().all()]

    records = _build_records_from_rows(detail_rows)
    order_index = {no: idx for idx, no in enumerate(page_exam_nos)}
    records.sort(
        key=lambda r: (
            order_index.get(r.exam_no, 10**9),
            -(r.final_date.toordinal() if r.final_date else 0),
            -(r.summary_date.toordinal() if r.summary_date else 0),
            r.exam_no,
        )
    )
    return total, records


def _fetch_rows_for_export_db(
    org_id: str | None,
    keyword: str | None,
    exam_no: str | None,
    exam_status: str | None,
    summary_start_date: date | None,
    summary_end_date: date | None,
    final_start_date: date | None,
    final_end_date: date | None,
    only_abnormal: bool,
) -> list[ExamSummaryRecord]:
    engine = _build_engine()
    if engine is None:
        raise RuntimeError("db disabled")

    mapping = _get_mapping()
    view_name = _get_view_name()
    if not view_name:
        raise RuntimeError("view name missing")

    where_sql, params = _build_filters_sql(
        mapping,
        org_id,
        keyword,
        exam_no,
        exam_status,
        summary_start_date,
        summary_end_date,
        final_start_date,
        final_end_date,
        only_abnormal,
    )

    exam_no_field = _get_source_field("exam_no", mapping)
    group_field = _get_source_field("group_name", mapping)
    item_field = _get_source_field("item_name", mapping)
    order_parts = [p for p in [exam_no_field, group_field, item_field] if p]

    with engine.connect() as conn:
        sql = text(
            f"SELECT * FROM {view_name} WHERE {where_sql}"
            + (f" ORDER BY {', '.join(order_parts)}" if order_parts else "")
        )
        rows = [dict(r) for r in conn.execute(sql, params).mappings().all()]
    return _build_records_from_rows(rows)


def _fetch_distinct_field_db(std_field: str) -> list[str]:
    engine = _build_engine()
    if engine is None:
        return []
    mapping = _get_mapping()
    view_name = _get_view_name()
    source_field = _get_source_field(std_field, mapping)
    if not view_name or not source_field:
        return []

    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT DISTINCT {source_field} AS v FROM {view_name}"), {}).mappings().all()
    values = [str(r["v"]).strip() for r in rows if r.get("v") is not None and str(r["v"]).strip()]
    values.sort()
    return values


def _db_enabled() -> bool:
    return load_db_config().enabled


def _match_date(value: date | None, start: date | None, end: date | None) -> bool:
    if value is None:
        return start is None and end is None
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


def _filter_records_mock(
    org_id: str | None,
    keyword: str | None,
    exam_no: str | None,
    exam_status: str | None,
    summary_start_date: date | None,
    summary_end_date: date | None,
    final_start_date: date | None,
    final_end_date: date | None,
    only_abnormal: bool,
) -> list[ExamSummaryRecord]:
    records = MOCK_RECORDS
    if org_id:
        records = [record for record in records if record.org_id == org_id]
    if keyword:
        key = keyword.strip().lower()
        records = [record for record in records if key in record.person_name.lower()]
    if exam_no:
        key = exam_no.strip().lower()
        records = [record for record in records if key in record.exam_no.lower()]
    if exam_status:
        records = [record for record in records if record.exam_status == exam_status]
    if summary_start_date or summary_end_date:
        records = [record for record in records if _match_date(record.summary_date, summary_start_date, summary_end_date)]
    if final_start_date or final_end_date:
        records = [record for record in records if _match_date(record.final_date, final_start_date, final_end_date)]
    if only_abnormal:
        records = [record for record in records if record.has_abnormal]
    records.sort(
        key=lambda r: (
            -(r.final_date.toordinal() if r.final_date else 0),
            -(r.summary_date.toordinal() if r.summary_date else 0),
            r.exam_no,
        )
    )
    return records


def list_orgs() -> list[Org]:
    if _db_enabled():
        cache_key = "orgs"
        cached = _cache_get(_META_CACHE, cache_key)
        if cached is not None:
            return cached
        try:
            names = _fetch_distinct_field_db("org_name")
            result = [Org(org_id=name, org_name=name) for name in names]
            _cache_set(_META_CACHE, cache_key, result, load_app_config().cache_ttl_orgs_seconds)
            return result
        except Exception as exc:
            logger.exception("Failed to load orgs from database")
            raise DataSourceError(f"Database query failed (orgs): {exc}") from exc
    return ORGS


def list_project_groups() -> list[str]:
    if _db_enabled():
        cache_key = "project_groups"
        cached = _cache_get(_META_CACHE, cache_key)
        if cached is not None:
            return cached
        try:
            names = _fetch_distinct_field_db("group_name")
            _cache_set(_META_CACHE, cache_key, names, load_app_config().cache_ttl_groups_seconds)
            return names
        except Exception as exc:
            logger.exception("Failed to load project groups from database")
            raise DataSourceError(f"Database query failed (project-groups): {exc}") from exc
    return sorted({group.group_name for record in MOCK_RECORDS for group in record.project_groups})


def list_records(
    org_id: str | None,
    keyword: str | None,
    exam_no: str | None,
    exam_status: str | None,
    summary_start_date: date | None,
    summary_end_date: date | None,
    final_start_date: date | None,
    final_end_date: date | None,
    only_abnormal: bool,
    page: int,
    page_size: int,
) -> tuple[int, list[ExamSummaryRecord]]:
    summary_start_date, summary_end_date, final_start_date, final_end_date = _normalize_date_filters(
        summary_start_date,
        summary_end_date,
        final_start_date,
        final_end_date,
    )

    if _db_enabled():
        try:
            return _fetch_records_db_paged(
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
        except Exception as exc:
            logger.exception("Failed to load records from database")
            raise DataSourceError(f"Database query failed (records): {exc}") from exc

    filtered = _filter_records_mock(
        org_id,
        keyword,
        exam_no,
        exam_status,
        summary_start_date,
        summary_end_date,
        final_start_date,
        final_end_date,
        only_abnormal,
    )
    total = len(filtered)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return total, filtered[start:end]


def list_records_for_export(
    org_id: str | None,
    keyword: str | None,
    exam_no: str | None,
    exam_status: str | None,
    summary_start_date: date | None,
    summary_end_date: date | None,
    final_start_date: date | None,
    final_end_date: date | None,
    only_abnormal: bool,
) -> list[ExamSummaryRecord]:
    if _db_enabled():
        try:
            return _fetch_rows_for_export_db(
                org_id,
                keyword,
                exam_no,
                exam_status,
                summary_start_date,
                summary_end_date,
                final_start_date,
                final_end_date,
                only_abnormal,
            )
        except Exception as exc:
            logger.exception("Failed to load records for export from database")
            raise DataSourceError(f"Database query failed (export): {exc}") from exc

    return _filter_records_mock(
        org_id,
        keyword,
        exam_no,
        exam_status,
        summary_start_date,
        summary_end_date,
        final_start_date,
        final_end_date,
        only_abnormal,
    )

from __future__ import annotations

from datetime import date
from typing import Iterable

from app.models import ExamRecord, Org


ORGS = [
    Org(org_id="org-001", org_name="第一单位"),
    Org(org_id="org-002", org_name="第二单位"),
]

MOCK_RECORDS = [
    ExamRecord(
        record_id="rec-001",
        org_id="org-001",
        org_name="第一单位",
        person_id="p-001",
        person_name="张三",
        gender="男",
        id_no="320101199001011234",
        exam_date=date(2026, 2, 16),
        item_code="HB",
        item_name="血红蛋白",
        result_value="117",
        unit="g/L",
        ref_range="130-175",
        is_abnormal=True,
        abnormal_flag="L",
    ),
    ExamRecord(
        record_id="rec-002",
        org_id="org-001",
        org_name="第一单位",
        person_id="p-001",
        person_name="张三",
        gender="男",
        id_no="320101199001011234",
        exam_date=date(2026, 2, 16),
        item_code="GLU",
        item_name="葡萄糖",
        result_value="5.2",
        unit="mmol/L",
        ref_range="3.9-6.1",
        is_abnormal=False,
        abnormal_flag="N",
    ),
    ExamRecord(
        record_id="rec-003",
        org_id="org-002",
        org_name="第二单位",
        person_id="p-002",
        person_name="李四",
        gender="女",
        id_no="320101199502023456",
        exam_date=date(2026, 2, 18),
        item_code="WBC",
        item_name="白细胞",
        result_value="12.6",
        unit="10^9/L",
        ref_range="3.5-9.5",
        is_abnormal=True,
        abnormal_flag="H",
    ),
]


def list_orgs() -> list[Org]:
    return ORGS


def _filter_records(
    org_id: str | None,
    keyword: str | None,
    start_date: date | None,
    end_date: date | None,
    only_abnormal: bool,
) -> Iterable[ExamRecord]:
    records = MOCK_RECORDS
    if org_id:
        records = [record for record in records if record.org_id == org_id]
    if keyword:
        key = keyword.strip().lower()
        records = [
            record
            for record in records
            if key in record.person_name.lower() or (record.id_no and key in record.id_no.lower())
        ]
    if start_date:
        records = [record for record in records if record.exam_date >= start_date]
    if end_date:
        records = [record for record in records if record.exam_date <= end_date]
    if only_abnormal:
        records = [record for record in records if record.is_abnormal]
    return records


def list_records(
    org_id: str | None,
    keyword: str | None,
    start_date: date | None,
    end_date: date | None,
    only_abnormal: bool,
    page: int,
    page_size: int,
) -> tuple[int, list[ExamRecord]]:
    filtered = list(_filter_records(org_id, keyword, start_date, end_date, only_abnormal))
    total = len(filtered)
    start = max(page - 1, 0) * page_size
    end = start + page_size
    return total, filtered[start:end]


def list_records_for_export(
    org_id: str | None,
    keyword: str | None,
    start_date: date | None,
    end_date: date | None,
    only_abnormal: bool,
) -> list[ExamRecord]:
    return list(_filter_records(org_id, keyword, start_date, end_date, only_abnormal))

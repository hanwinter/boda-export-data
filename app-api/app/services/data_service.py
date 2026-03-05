from __future__ import annotations

from datetime import date

from app.models import ExamItem, ExamProjectGroup, ExamSummaryRecord, Org


ORGS = [
    Org(org_id="org-001", org_name="第一单位"),
    Org(org_id="org-002", org_name="第二单位"),
]


MOCK_RECORDS = [
    ExamSummaryRecord(
        record_id="rec-1001",
        org_id="org-001",
        org_name="第一单位",
        person_id="p-001",
        person_name="张三",
        gender="男",
        id_no="320101199001011234",
        phone="13800001111",
        exam_no="TJ20260001",
        summary_date=date(2026, 2, 17),
        final_date=date(2026, 2, 18),
        exam_status="已终检",
        has_abnormal=True,
        project_groups=[
            ExamProjectGroup(
                group_name="血常规",
                group_is_abnormal=True,
                abnormal_count=1,
                items=[
                    ExamItem(
                        item_name="红细胞",
                        result_value="3.92",
                        unit="10^12/L",
                        ref_range="4.30-5.80",
                        is_abnormal=True,
                        abnormal_flag="L",
                    ),
                    ExamItem(
                        item_name="白细胞",
                        result_value="6.2",
                        unit="10^9/L",
                        ref_range="3.5-9.5",
                        is_abnormal=False,
                        abnormal_flag="N",
                    ),
                ],
            ),
            ExamProjectGroup(
                group_name="尿常规",
                group_is_abnormal=False,
                abnormal_count=0,
                items=[
                    ExamItem(
                        item_name="尿蛋白",
                        result_value="阴性",
                        unit=None,
                        ref_range="阴性",
                        is_abnormal=False,
                        abnormal_flag="N",
                    )
                ],
            ),
        ],
    ),
    ExamSummaryRecord(
        record_id="rec-2001",
        org_id="org-002",
        org_name="第二单位",
        person_id="p-002",
        person_name="李四",
        gender="女",
        id_no="320101199502023456",
        phone="13900002222",
        exam_no="TJ20260088",
        summary_date=date(2026, 2, 20),
        final_date=None,
        exam_status="已总检",
        has_abnormal=True,
        project_groups=[
            ExamProjectGroup(
                group_name="彩超",
                group_is_abnormal=True,
                abnormal_count=1,
                items=[
                    ExamItem(
                        item_name="甲状腺结节",
                        result_value="TI-RADS 4a",
                        unit=None,
                        ref_range="无明显异常",
                        is_abnormal=True,
                        abnormal_flag="H",
                    )
                ],
            ),
            ExamProjectGroup(
                group_name="肝功能",
                group_is_abnormal=False,
                abnormal_count=0,
                items=[
                    ExamItem(
                        item_name="谷丙转氨酶",
                        result_value="26",
                        unit="U/L",
                        ref_range="0-40",
                        is_abnormal=False,
                        abnormal_flag="N",
                    )
                ],
            ),
        ],
    ),
]


def list_orgs() -> list[Org]:
    return ORGS


def list_project_groups() -> list[str]:
    names = {group.group_name for record in MOCK_RECORDS for group in record.project_groups}
    return sorted(names)


def _match_date(value: date | None, start: date | None, end: date | None) -> bool:
    if value is None:
        return start is None and end is None
    if start and value < start:
        return False
    if end and value > end:
        return False
    return True


def _filter_records(
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
        records = [
            record
            for record in records
            if key in record.person_name.lower() or (record.id_no and key in record.id_no.lower())
        ]
    if exam_no:
        key = exam_no.strip().lower()
        records = [record for record in records if key in record.exam_no.lower()]
    if exam_status:
        records = [record for record in records if record.exam_status == exam_status]
    if summary_start_date or summary_end_date:
        records = [
            record
            for record in records
            if _match_date(record.summary_date, summary_start_date, summary_end_date)
        ]
    if final_start_date or final_end_date:
        records = [
            record for record in records if _match_date(record.final_date, final_start_date, final_end_date)
        ]
    if only_abnormal:
        records = [record for record in records if record.has_abnormal]
    return records


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
    filtered = _filter_records(
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
    return _filter_records(
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

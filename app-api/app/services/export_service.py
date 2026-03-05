from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from app.core.settings import ROOT_DIR, load_app_config, load_export_columns
from app.models import ExamRecord


RED_FONT = Font(color="FF0000", bold=True)


DEFAULT_COLUMNS = [
    {"field": "org_name", "title": "单位"},
    {"field": "person_name", "title": "姓名"},
    {"field": "gender", "title": "性别"},
    {"field": "id_no", "title": "证件号"},
    {"field": "exam_date", "title": "体检日期"},
    {"field": "item_code", "title": "项目编码"},
    {"field": "item_name", "title": "项目名称"},
    {"field": "result_value", "title": "结果值"},
    {"field": "unit", "title": "单位"},
    {"field": "ref_range", "title": "参考范围"},
    {"field": "abnormal_flag", "title": "异常标记"},
]


def _get_columns() -> list[dict[str, str]]:
    configured = load_export_columns()
    return configured if configured else DEFAULT_COLUMNS


def export_records(records: list[ExamRecord]) -> tuple[str, str]:
    app_cfg = load_app_config()
    export_dir = Path(app_cfg.export_dir)
    if not export_dir.is_absolute():
        export_dir = ROOT_DIR / export_dir
    export_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"体检导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    file_path = export_dir / file_name

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "体检数据"

    columns = _get_columns()
    headers = [column["title"] for column in columns]
    sheet.append(headers)

    for index, title in enumerate(headers, start=1):
        sheet.cell(row=1, column=index).font = Font(bold=True)
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = max(len(title) * 2, 12)

    for record in records:
        row = []
        for column in columns:
            value = getattr(record, column["field"], "")
            row.append(str(value) if value is not None else "")
        sheet.append(row)

        row_index = sheet.max_row
        if record.is_abnormal:
            for column_index, column in enumerate(columns, start=1):
                if column["field"] in {"result_value", "abnormal_flag"}:
                    sheet.cell(row=row_index, column=column_index).font = RED_FONT

    workbook.save(file_path)
    return file_name, str(file_path)

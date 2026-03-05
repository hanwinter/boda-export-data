from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from app.core.settings import ROOT_DIR, load_app_config
from app.models import ExamSummaryRecord


RED_FONT = Font(color="FF0000", bold=True)
BOLD_FONT = Font(bold=True)
GROUP_FILL = PatternFill(fill_type="solid", fgColor="DDEBF7")


BASE_COLUMNS = [
    ("org_name", "单位"),
    ("person_name", "姓名"),
    ("gender", "性别"),
    ("id_no", "证件号"),
    ("phone", "电话"),
    ("exam_no", "体检编号"),
    ("summary_date", "汇总日期"),
    ("final_date", "终检日期"),
    ("exam_status", "体检状态"),
]


def _resolve_export_dir(requested_export_dir: str | None) -> Path:
    app_cfg = load_app_config()
    if requested_export_dir and requested_export_dir.strip():
        target = Path(requested_export_dir.strip())
    else:
        target = Path(app_cfg.export_dir)

    if not target.is_absolute():
        target = ROOT_DIR / target
    target.mkdir(parents=True, exist_ok=True)
    return target


def _allow_group(group_name: str, selected_groups: set[str] | None) -> bool:
    if not selected_groups:
        return True
    return group_name in selected_groups


def _build_group_items(
    records: list[ExamSummaryRecord],
    selected_group_set: set[str] | None,
) -> list[tuple[str, list[str]]]:
    group_items: dict[str, list[str]] = {}
    group_order: list[str] = []

    for record in records:
        for group in record.project_groups:
            if not _allow_group(group.group_name, selected_group_set):
                continue
            if group.group_name not in group_items:
                group_items[group.group_name] = []
                group_order.append(group.group_name)
            for item in group.items:
                if item.item_name not in group_items[group.group_name]:
                    group_items[group.group_name].append(item.item_name)

    return [(name, group_items[name]) for name in group_order]


def _fmt(value) -> str:
    if value is None:
        return ""
    return str(value)


def export_records(
    records: list[ExamSummaryRecord],
    export_dir: str | None = None,
    selected_groups: list[str] | None = None,
) -> tuple[str, str]:
    target_dir = _resolve_export_dir(export_dir)
    selected_group_set = set(selected_groups) if selected_groups else None

    file_name = f"体检导出_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    file_path = target_dir / file_name

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "体检数据"

    group_items_layout = _build_group_items(records, selected_group_set)

    headers: list[str] = [title for _, title in BASE_COLUMNS]
    group_col_indexes: list[int] = []
    item_col_index: dict[tuple[str, str], int] = {}

    for group_name, item_names in group_items_layout:
        headers.append(f"{group_name}·组合结果")
        group_col_indexes.append(len(headers))
        for item_name in item_names:
            headers.append(item_name)
            item_col_index[(group_name, item_name)] = len(headers)

    sheet.append(headers)

    for idx, title in enumerate(headers, start=1):
        cell = sheet.cell(row=1, column=idx)
        cell.font = BOLD_FONT
        if idx in group_col_indexes:
            cell.fill = GROUP_FILL
        sheet.column_dimensions[cell.column_letter].width = max(min(len(title) * 2, 32), 12)

    for record in records:
        group_result_map: dict[str, str] = {}
        item_value_map: dict[tuple[str, str], tuple[str, bool]] = {}

        for group in record.project_groups:
            if not _allow_group(group.group_name, selected_group_set):
                continue
            status_text = "异常" if group.group_is_abnormal else "正常"
            group_result_map[group.group_name] = f"{group.group_name}({status_text})"
            for item in group.items:
                item_value_map[(group.group_name, item.item_name)] = (_fmt(item.result_value), item.is_abnormal)

        row_values = [_fmt(getattr(record, field, "")) for field, _ in BASE_COLUMNS]
        abnormal_cols: list[int] = []

        for group_name, item_names in group_items_layout:
            row_values.append(group_result_map.get(group_name, ""))
            for item_name in item_names:
                value, is_abnormal = item_value_map.get((group_name, item_name), ("", False))
                row_values.append(value)
                if is_abnormal:
                    abnormal_cols.append(item_col_index[(group_name, item_name)])

        sheet.append(row_values)
        row_idx = sheet.max_row

        for col_idx in group_col_indexes:
            sheet.cell(row=row_idx, column=col_idx).fill = GROUP_FILL

        for col_idx in abnormal_cols:
            sheet.cell(row=row_idx, column=col_idx).font = RED_FONT

    sheet.freeze_panes = "A2"
    workbook.save(file_path)
    return file_name, str(file_path)

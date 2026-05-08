from __future__ import annotations

import importlib
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation

REPO_ROOT = Path(__file__).resolve().parents[1]

PROCESS_TEMPLATE_FILES = (
    "工种配置.xlsx",
    "供应商配置.xlsx",
    "零件工艺路线.xlsx",
    "零件工序工时.xlsx",
)

PAGE_MANUAL_TEMPLATE_COLUMN_CONTRACTS = {
    "excel_personnel": "人员基本信息.xlsx",
    "excel_personnel_link": "人员设备关联.xlsx",
    "excel_personnel_calendar": "人员专属工作日历.xlsx",
    "excel_equipment": "设备信息.xlsx",
    "excel_equipment_link": "设备人员关联.xlsx",
    "excel_op_types": "工种配置.xlsx",
    "excel_suppliers": "供应商配置.xlsx",
    "excel_routes": "零件工艺路线.xlsx",
    "excel_part_op_hours": "零件工序工时.xlsx",
    "excel_batches": "批次信息.xlsx",
    "excel_calendar": "工作日历.xlsx",
}

DROPDOWN_MANUAL_CONTRACTS: Mapping[str, Mapping[str, Any]] = {
    "工种配置.xlsx": {
        "manual_id": "excel_op_types",
        "manual_heading": "#### 1.5.1 工种配置",
        "dropdowns": {"归属": ["自制", "外协"]},
        "compatible_values": {"归属": ["内部", "外部"]},
        "page_phrases": ["归属可填：自制 / 外协", "新文件请只填这两个中文选项"],
        "manual_phrases": ["填 `自制` 或 `外协`", "新文件请只填这两个中文值"],
        "forbidden_page_phrases": ["内部/外部", "内部 / 外部", "内部、外部", "内部，外部"],
        "forbidden_manual_phrases": ["`内部`", "`外部`", "内部/外部", "内部 / 外部", "内部、外部", "内部，外部"],
    },
    "供应商配置.xlsx": {
        "manual_id": "excel_suppliers",
        "manual_heading": "#### 1.5.2 供应商配置",
        "dropdowns": {"状态": ["启用", "停用"]},
        "compatible_values": {"状态": ["在用", "正常", "禁用"]},
        "page_phrases": ["启用/停用", "对应工种", "状态和备注"],
        "manual_phrases": ["`启用`/`停用`", "`在用`/`正常`/`禁用`", "状态", "备注"],
        "forbidden_page_phrases": ["新填数据请使用自制/外协", "新填数据请使用 `自制`/`外协`"],
        "forbidden_manual_phrases": [],
    },
    "人员基本信息.xlsx": {
        "manual_id": "excel_personnel",
        "manual_heading": "#### 1.5.5 人员基本信息",
        "dropdowns": {"状态": ["在岗", "停用"]},
        "compatible_values": {"状态": ["启用", "可用", "正常", "休假", "离岗"]},
        "page_phrases": ["状态", "在岗", "停用"],
        "manual_phrases": ["`在岗` 或 `停用`"],
        "forbidden_page_phrases": [],
        "forbidden_manual_phrases": [],
    },
    "设备信息.xlsx": {
        "manual_id": "excel_equipment",
        "manual_heading": "#### 1.5.6 设备信息",
        "dropdowns": {"状态": ["可用", "停用", "维修"]},
        "compatible_values": {"状态": ["启用", "正常", "禁用", "不可用", "维护", "维护中", "维修中", "保养"]},
        "page_phrases": ["状态", "可用", "停用", "维修"],
        "manual_phrases": ["`可用`、`停用`、`维修`"],
        "forbidden_page_phrases": [],
        "forbidden_manual_phrases": [],
    },
    "批次信息.xlsx": {
        "manual_id": "excel_batches",
        "manual_heading": "#### 1.5.10 批次信息（排产核心）",
        "dropdowns": {"优先级": ["普通", "急件", "特急"], "齐套": ["齐套", "未齐套", "部分齐套"]},
        "compatible_values": {"优先级": ["急"], "齐套": ["是", "否"]},
        "page_phrases": ["优先级", "普通", "急件", "特急", "齐套", "未齐套", "部分齐套"],
        "manual_phrases": ["`普通`、`急件`、`特急`", "`齐套`、`未齐套`、`部分齐套`"],
        "forbidden_page_phrases": [],
        "forbidden_manual_phrases": [],
    },
    "工作日历.xlsx": {
        "manual_id": "excel_calendar",
        "manual_heading": "#### 1.5.8 工作日历",
        "dropdowns": {"类型": ["工作日", "假期"], "允许普通件": ["是", "否"], "允许急件": ["是", "否"]},
        "compatible_values": {"类型": ["周末", "节假日"]},
        "page_phrases": ["类型", "工作日", "假期", "允许普通件", "允许急件", "是", "否"],
        "manual_phrases": ["`工作日`", "`假期`", "`是` 或 `否`"],
        "forbidden_page_phrases": [],
        "forbidden_manual_phrases": [],
    },
}


def _ensure_repo_on_path() -> None:
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


def _template_definition(filename: str) -> Mapping[str, Any]:
    _ensure_repo_on_path()
    excel_templates = importlib.import_module("core.services.common.excel_templates")
    return excel_templates.get_template_definition(filename)


def _read_static_manual() -> str:
    return (REPO_ROOT / "static" / "docs" / "scheduler_manual.md").read_text(encoding="utf-8")


def _manual_payload_text(payload: Mapping[str, Any]) -> str:
    parts = [str(payload.get("title") or ""), str(payload.get("summary") or "")]
    help_card = payload.get("help_card") or {}
    parts.append(str(help_card.get("title") or ""))
    parts.extend(str(item or "") for item in (help_card.get("items") or []))
    for section in payload.get("sections") or []:
        parts.append(str(section.get("title") or ""))
        parts.append(str(section.get("body_md") or ""))
    return "\n".join(part for part in parts if part)


def _extract_markdown_section(markdown_text: str, heading: str) -> str:
    start = markdown_text.find(heading)
    if start < 0 and heading.startswith("#### "):
        heading_title = re.sub(r"^####\s+\d+(?:\.\d+)*\s+", "", heading).strip()
        pattern = rf"^####\s+\d+(?:\.\d+)*\s+{re.escape(heading_title)}\s*$"
        m = re.search(pattern, markdown_text, flags=re.M)
        if m:
            start = m.start()
            heading = m.group(0)
    assert start >= 0, f"总说明书缺少章节标题：{heading}"
    rest = markdown_text[start + len(heading) :]
    next_heading = re.search(r"^####\s+\d+(?:\.\d+)*\s+", rest, flags=re.M)
    end = start + len(heading) + next_heading.start() if next_heading else len(markdown_text)
    return markdown_text[start:end]


def _is_allowed_legacy_op_type_note(section_text: str, phrase: str) -> bool:
    return (
        phrase == "内部/外部"
        and "旧模板中已有数据行不会被系统擅自改写" in section_text
        and "新填数据请使用 `自制`/`外协`" in section_text
    )


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _value_has_compatibility_context(text: str, value: str) -> bool:
    markers = ("旧文件", "旧模板", "以前", "兼容", "也能识别", "尽量读懂", "也可以填", "按假期")
    for match in re.finditer(re.escape(value), text):
        start = max(0, match.start() - 50)
        end = min(len(text), match.end() + 50)
        context = text[start:end]
        if any(marker in context for marker in markers):
            return True
    return False


def _assert_dropdown_copy_distinguishes_recommended_and_compatible(
    text: str,
    *,
    label: str,
    dropdowns: Mapping[str, Sequence[str]],
    compatible_values: Mapping[str, Sequence[str]],
) -> None:
    compact = _compact_text(text)
    for column_name, recommended_values in dropdowns.items():
        assert column_name in text, f"{label} 缺少下拉字段名：{column_name}"
        for value in recommended_values:
            assert value in text, f"{label} 缺少模板推荐下拉值：{column_name}={value}"
        joined = "/".join(str(value) for value in recommended_values)
        assert joined in compact or any(marker in text for marker in ("新文件", "新表", "新填数据", "推荐填", "建议填")), (
            f"{label} 应把 {column_name} 的推荐值和兼容旧写法分开说明：{joined}"
        )

    for column_name, values in compatible_values.items():
        for value in values:
            if value not in text:
                continue
            assert _value_has_compatibility_context(text, value), (
                f"{label} 里的兼容写法没有标清是旧写法或兼容写法：{column_name}={value}"
            )


def _definition_enum_values_by_header(definition: Mapping[str, Any]) -> dict[str, list[str]]:
    headers = [str(item) for item in (definition.get("headers") or [])]
    enum_cols = ((definition.get("format_spec") or {}).get("enum_cols") or {})
    out: dict[str, list[str]] = {}
    for raw_col_idx, values in enum_cols.items():
        col_idx = int(raw_col_idx)
        header = headers[col_idx]
        out[header] = [str(item).strip() for item in (values or []) if str(item).strip()]
    return out


def _inline_validation_values(formula1: Any) -> list[str]:
    raw = str(formula1 or "").strip()
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    return [item.strip() for item in raw.split(",") if item.strip()]


def _validation_values_for_column(ws: Any, one_based_col_idx: int) -> list[str]:
    for data_validation in ws.data_validations.dataValidation:
        if data_validation.type != "list":
            continue
        for cell_range in data_validation.sqref.ranges:
            if (
                cell_range.min_col <= one_based_col_idx <= cell_range.max_col
                and cell_range.min_row <= 2 <= cell_range.max_row
            ):
                return _inline_validation_values(data_validation.formula1)
    return []


def _actual_enum_values_by_header(ws: Any, headers: Sequence[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for one_based_col_idx, header in enumerate(headers, start=1):
        values = _validation_values_for_column(ws, one_based_col_idx)
        if values:
            out[str(header)] = values
    return out


def _normalize_help_column_label(raw: str) -> str:
    text = re.sub(r"[`*]", "", str(raw or "")).strip().rstrip("。.")

    def _replace_note(match: re.Match[str]) -> str:
        inner = str(match.group(1) or match.group(2) or "").strip()
        return "(h)" if inner.lower() == "h" else ""

    text = re.sub(r"（([^）]*)）|\(([^)]*)\)", _replace_note, text)
    text = re.split(r"[；;]", text, maxsplit=1)[0]
    return text.strip()


def _split_help_columns(column_text: str) -> list[str]:
    columns: list[str] = []
    current: list[str] = []
    depth = 0
    for char in column_text:
        if char in "（(":
            depth += 1
        elif char in "）)" and depth > 0:
            depth -= 1
        if char in "、,，" and depth == 0:
            columns.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    if current:
        columns.append("".join(current).strip())
    return columns


def _extract_help_card_columns(payload: Mapping[str, Any]) -> list[str]:
    help_card = payload.get("help_card") or {}
    for item in help_card.get("items") or []:
        text = str(item or "").strip()
        if text.startswith("列："):
            column_text = text[len("列：") :].strip()
        elif text.startswith("模板列："):
            column_text = text[len("模板列：") :].strip()
        else:
            continue
        column_text = re.split(r"[。]", column_text, maxsplit=1)[0].strip()
        raw_columns = _split_help_columns(column_text)
        return [_normalize_help_column_label(column) for column in raw_columns if _normalize_help_column_label(column)]
    raise AssertionError(f"{payload.get('title')} 页面帮助卡缺少“列：...”说明")


def _read_sample_rows(ws: Any, *, width: int, count: int) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for row_idx in range(2, 2 + count):
        rows.append([ws.cell(row_idx, col_idx).value for col_idx in range(1, width + 1)])
    return rows


def _read_template_snapshot(template_path: Path, definition: Mapping[str, Any]) -> tuple[list[Any], list[list[Any]], dict[str, list[str]]]:
    expected_headers = [str(item) for item in definition.get("headers") or []]
    expected_sample_rows = list(definition.get("sample_rows") or [])
    workbook = load_workbook(template_path, data_only=True)
    try:
        ws = workbook.active
        actual_headers = [ws.cell(1, col_idx).value for col_idx in range(1, len(expected_headers) + 1)]
        actual_sample_rows = _read_sample_rows(
            ws,
            width=len(expected_headers),
            count=len(expected_sample_rows),
        )
        actual_enums = _actual_enum_values_by_header(ws, expected_headers)
    finally:
        workbook.close()
    return actual_headers, actual_sample_rows, actual_enums


def _write_legacy_op_type_template(
    template_path: Path,
    *,
    sample_rows: Sequence[Sequence[Any]],
    dropdown_values: Sequence[str],
) -> None:
    definition = _template_definition("工种配置.xlsx")
    workbook = Workbook()
    try:
        ws = workbook.active
        ws.append(list(definition.get("headers") or []))
        for row in sample_rows:
            ws.append(list(row))
        if dropdown_values:
            validation = DataValidation(type="list", formula1=f"\"{','.join(dropdown_values)}\"", allow_blank=True)
            validation.add("C2:C500")
            ws.add_data_validation(validation)
        template_path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(template_path)
    finally:
        workbook.close()


def _assert_op_type_template_current(template_path: Path) -> None:
    definition = _template_definition("工种配置.xlsx")
    expected_headers = [str(item) for item in definition.get("headers") or []]
    expected_sample_rows = list(definition.get("sample_rows") or [])
    expected_enums = _definition_enum_values_by_header(definition)

    actual_headers, actual_sample_rows, actual_enums = _read_template_snapshot(template_path, definition)
    assert actual_headers == expected_headers, "工种配置旧模板刷新后表头不正确"
    assert actual_sample_rows == expected_sample_rows, "工种配置旧模板刷新后示例行不正确"
    assert actual_enums == expected_enums, "工种配置旧模板刷新后下拉值不正确"


def _assert_legacy_op_type_template_refreshes() -> None:
    _ensure_repo_on_path()
    excel_templates = importlib.import_module("core.services.common.excel_templates")

    scenarios = (
        (
            "旧示例行仍写内部/外部",
            [["OT001", "数车", "内部"], ["OT002", "标印", "外部"]],
            ["自制", "外协"],
        ),
        (
            "旧下拉仍写内部/外部",
            [["OT001", "数车", "自制"], ["OT002", "标印", "外协"]],
            ["内部", "外部"],
        ),
    )

    for label, sample_rows, dropdown_values in scenarios:
        with tempfile.TemporaryDirectory(prefix="aps_excel_template_contract_") as tmpdir:
            template_path = Path(tmpdir) / "工种配置.xlsx"
            _write_legacy_op_type_template(
                template_path,
                sample_rows=sample_rows,
                dropdown_values=dropdown_values,
            )

            result = excel_templates.ensure_excel_templates(tmpdir)
            assert "工种配置.xlsx" in result.get("created", []), f"{label} 时，旧模板没有触发自动刷新"
            _assert_op_type_template_current(template_path)


def _assert_legacy_op_type_template_with_extra_rows_repairs_dropdown_without_overwriting_data() -> None:
    _ensure_repo_on_path()
    excel_templates = importlib.import_module("core.services.common.excel_templates")

    original_rows = [
        ["OT001", "数车", "内部"],
        ["OT002", "标印", "外部"],
        ["OT003", "喷涂", "内部"],
    ]

    with tempfile.TemporaryDirectory(prefix="aps_excel_template_contract_") as tmpdir:
        template_path = Path(tmpdir) / "工种配置.xlsx"
        _write_legacy_op_type_template(
            template_path,
            sample_rows=original_rows,
            dropdown_values=["内部", "外部"],
        )

        result = excel_templates.ensure_excel_templates(tmpdir)
        assert "工种配置.xlsx" in result.get("created", []), "旧工种模板有额外数据行时，仍应触发下拉刷新"

        definition = _template_definition("工种配置.xlsx")
        expected_headers = [str(item) for item in definition.get("headers") or []]
        expected_enums = _definition_enum_values_by_header(definition)
        workbook = load_workbook(template_path, data_only=True)
        try:
            ws = workbook.active
            actual_headers = [ws.cell(1, col_idx).value for col_idx in range(1, len(expected_headers) + 1)]
            actual_rows = _read_sample_rows(ws, width=len(expected_headers), count=len(original_rows))
            actual_enums = _actual_enum_values_by_header(ws, expected_headers)
        finally:
            workbook.close()

        assert actual_headers == expected_headers, "旧工种模板有额外数据行时，表头应刷新为当前表头"
        assert actual_rows == original_rows, "旧工种模板有额外数据行时，用户数据行不能被覆盖"
        assert actual_enums == expected_enums, "旧工种模板有额外数据行时，归属下拉应刷新为自制/外协"


def _assert_process_excel_template_files_match_registered_definitions() -> None:
    for filename in PROCESS_TEMPLATE_FILES:
        template_path = REPO_ROOT / "templates_excel" / filename
        assert template_path.exists(), f"缺少工艺 Excel 模板文件：{template_path}"

        definition = _template_definition(filename)
        expected_headers = [str(item) for item in definition.get("headers") or []]
        expected_sample_rows = list(definition.get("sample_rows") or [])
        expected_enums = _definition_enum_values_by_header(definition)
        actual_headers, actual_sample_rows, actual_enums = _read_template_snapshot(template_path, definition)

        assert actual_headers == expected_headers, f"{filename} 表头和模板定义不一致"
        assert actual_sample_rows == expected_sample_rows, f"{filename} 示例行和模板定义不一致"
        assert actual_enums == expected_enums, f"{filename} 下拉值和模板定义不一致"


def _assert_process_excel_dropdown_values_match_page_and_full_manuals() -> None:
    _ensure_repo_on_path()
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")
    static_manual_text = _read_static_manual()

    for filename, contract in DROPDOWN_MANUAL_CONTRACTS.items():
        definition = _template_definition(filename)
        expected_enums = _definition_enum_values_by_header(definition)
        template_path = REPO_ROOT / "templates_excel" / filename
        workbook = load_workbook(template_path, data_only=True)
        try:
            ws = workbook.active
            headers = [str(item) for item in definition.get("headers") or []]
            actual_enums = _actual_enum_values_by_header(ws, headers)
        finally:
            workbook.close()

        for column_name, expected_values in (contract["dropdowns"] or {}).items():
            expected_values = list(expected_values)
            assert expected_enums.get(column_name) == expected_values, f"{filename} 模板定义中的 {column_name} 下拉值不正确"
            assert actual_enums.get(column_name) == expected_values, (
                f"{filename} 文件里的 {column_name} 下拉值不正确；"
                f"期望 {expected_values}，实际 {actual_enums.get(column_name)}"
            )

        payload = page_manuals.build_manual_payload(str(contract["manual_id"]), include_sections=True)
        assert payload is not None, f"{contract['manual_id']} 无法构建页面说明"
        page_text = _manual_payload_text(payload)
        full_manual_section = _extract_markdown_section(static_manual_text, str(contract["manual_heading"]))

        for phrase in contract["page_phrases"]:
            assert phrase in page_text, f"{contract['manual_id']} 页面说明缺少推荐值：{phrase}"
        for phrase in contract["manual_phrases"]:
            assert phrase in full_manual_section, f"{contract['manual_heading']} 说明书章节缺少推荐值：{phrase}"
        _assert_dropdown_copy_distinguishes_recommended_and_compatible(
            page_text,
            label=f"{contract['manual_id']} 页面说明",
            dropdowns=contract["dropdowns"],
            compatible_values=contract.get("compatible_values", {}),
        )
        _assert_dropdown_copy_distinguishes_recommended_and_compatible(
            full_manual_section,
            label=f"{contract['manual_heading']} 说明书章节",
            dropdowns=contract["dropdowns"],
            compatible_values=contract.get("compatible_values", {}),
        )
        for phrase in contract["forbidden_page_phrases"]:
            assert phrase not in page_text, f"{contract['manual_id']} 页面说明仍包含旧说法：{phrase}"
        for phrase in contract["forbidden_manual_phrases"]:
            if _is_allowed_legacy_op_type_note(full_manual_section, phrase):
                continue
            assert phrase not in full_manual_section, f"{contract['manual_heading']} 说明书章节仍包含旧说法：{phrase}"


def _assert_page_manual_help_columns_match_template_headers() -> None:
    _ensure_repo_on_path()
    page_manuals = importlib.import_module("web.viewmodels.page_manuals")

    for manual_id, filename in PAGE_MANUAL_TEMPLATE_COLUMN_CONTRACTS.items():
        definition = _template_definition(filename)
        expected_headers = [str(item) for item in definition.get("headers") or []]
        payload = page_manuals.build_manual_payload(manual_id, include_sections=True)
        assert payload is not None, f"{manual_id} 无法构建页面说明"
        actual_columns = _extract_help_card_columns(payload)
        assert actual_columns == expected_headers, (
            f"{manual_id} 帮助卡列顺序必须和 {filename} 模板表头一致；"
            f"期望 {expected_headers}，实际 {actual_columns}"
        )


def main() -> None:
    _assert_process_excel_template_files_match_registered_definitions()
    _assert_process_excel_dropdown_values_match_page_and_full_manuals()
    _assert_page_manual_help_columns_match_template_headers()
    _assert_legacy_op_type_template_refreshes()
    _assert_legacy_op_type_template_with_extra_rows_repairs_dropdown_without_overwriting_data()
    print("OK")


if __name__ == "__main__":
    main()

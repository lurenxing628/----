from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_PATH = REPO_ROOT / "docs" / "frontend_manual_audit_and_rewrite_blueprint.md"


def _read_blueprint() -> str:
    return BLUEPRINT_PATH.read_text(encoding="utf-8")


def _compact(text: str) -> str:
    return "".join(str(text).split())


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _table_after_heading(text: str, heading: str) -> list[dict[str, str]]:
    start = text.find(heading)
    assert start >= 0, f"蓝本缺少章节：{heading}"
    lines = text[start:].splitlines()
    table_start = next((idx for idx, line in enumerate(lines) if line.startswith("| ")), None)
    assert table_start is not None, f"{heading} 后缺少 Markdown 表格"
    headers = _split_markdown_row(lines[table_start])
    rows: list[dict[str, str]] = []
    for line in lines[table_start + 2 :]:
        if not line.startswith("|"):
            break
        cells = _split_markdown_row(line)
        rows.append(dict(zip(headers, cells)))
    return rows


def _row_by_first_cell(rows: list[dict[str, str]], first_header: str, value: str) -> dict[str, str]:
    for row in rows:
        if row.get(first_header) == value:
            return row
    raise AssertionError(f"表格缺少 {first_header}={value} 的行")


def test_blueprint_declares_internal_scope_and_current_baseline() -> None:
    text = _read_blueprint()

    assert "内部改稿蓝本和验收清单" in text
    assert "不是直接给计划调度员或工艺员看的最终用户说明书" in text
    assert "当前说明体系已经完成一轮补强" in text
    assert "不能再把旧缺口当作当前事实" in text
    assert "552b2916573fd1cefe00c429f488bb63fb1af9ab" in text


def test_blueprint_uses_auditable_status_buckets() -> None:
    text = _read_blueprint()

    for heading in ("### 1.1 已覆盖", "### 1.2 仍需补强", "### 1.3 需修正", "### 1.4 需核实"):
        assert heading in text

    assert "不再把首页路线或统计卡解释写成当前待办" in text
    assert "不再写成“结果页从零缺说明”" in text
    assert "不再笼统写“工艺说明明显偏短”" in text

    forbidden_current_gaps = (
        "首页缺少完整排产路线",
        "排产输出页控件很多，但说明没有逐个解释",
        "工艺主数据页面说明明显偏短。",
    )
    for phrase in forbidden_current_gaps:
        assert phrase not in text, f"蓝本不应继续把旧诊断当当前缺口：{phrase}"


def test_blueprint_contains_red_line_boundary_table() -> None:
    text = _read_blueprint()

    assert "## 2. 说明口径红线表" in text

    rows = _table_after_heading(text, "## 2. 说明口径红线表")
    expected_pairs = {
        "系统自动考虑所有限制并保证全局最优": "不保证唯一最优",
        "未齐套批次一定不参与排产": "只有本次启用齐套检查时",
        "系统会自动跳过缺料批次继续排其它批次": "本次排产会报错并停止",
        "物料库存会自动扣减": "判断齐套状态",
        "供应商产能会参与排产": "外协主要按周期天数处理",
        "备份文件由用户按日期和用途命名": "备份文件名由系统生成",
        "停机时间可以直接缩短或延长": "取消后重建",
        "历史页可以导出或恢复版本": "恢复走备份",
        "模拟排产结果可以直接发现场执行": "正式执行排产后的版本才建议发现场",
    }
    for forbidden_wording, recommended_wording in expected_pairs.items():
        row = _row_by_first_cell(rows, "不要这样写", forbidden_wording)
        assert recommended_wording in row["推荐这样写"], f"{forbidden_wording} 的推荐写法没有绑在同一行"


def test_excel_values_are_split_between_recommended_compatible_and_internal() -> None:
    text = _read_blueprint()

    assert "## 3. Excel 推荐值、兼容旧写法和内部口径" in text
    assert "新模板推荐值" in text
    assert "兼容旧写法" in text
    assert "仅内部知道" in text

    rows = _table_after_heading(text, "### 3.2 字段口径表")
    expected_rows = (
        ("人员状态", "`在岗`、`停用`", "`休假`、`离岗`", "`active`、`inactive`"),
        ("工种归属", "`自制`、`外协`", "`内部`、`外部`", "`internal`、`external`"),
        ("批次优先级", "`普通`、`急件`、`特急`", "`急`", "`normal`、`urgent`、`critical`"),
        ("批次齐套", "`齐套`、`未齐套`、`部分齐套`", "`是` 按齐套", "`yes`、`no`、`partial`"),
        ("工作日历类型", "`工作日`、`假期`", "`周末`、`节假日`", "`workday`、`holiday`、`weekend`"),
    )
    for label, recommended, compatible, internal in expected_rows:
        row = _row_by_first_cell(rows, "字段", label)
        assert _compact(recommended) in _compact(row["新模板推荐值"])
        assert _compact(compatible) in _compact(row["兼容旧写法"])
        assert _compact(internal) in _compact(row["仅内部知道"])


def test_page_level_checklist_has_required_columns_and_p0_fixes() -> None:
    text = _read_blueprint()

    assert "## 4. 页面级验收清单" in text
    assert "| 页面 | 当前已覆盖 | 后续可打磨 | 需修正 | 证据位置 | 下一步动作 |" in text

    required_phrases = (
        "设备详情",
        "取消后重建",
        "人员 Excel",
        "`在岗 / 停用`",
        "备份/恢复",
        "系统生成文件名",
        "排产历史",
        "不写“关键词搜索”",
        "齐套检查",
        "不会自动跳过",
    )
    for phrase in required_phrases:
        assert phrase in text


def test_blueprint_marks_uncertain_items_as_need_verification() -> None:
    text = _read_blueprint()

    assert "### 1.4 需核实" in text
    for phrase in (
        "版本下拉是否只列最近 30 个版本",
        "黄色提醒“更多提醒”统一去历史或分析页看",
        "只填一边日期是否会自动推断另一边",
        "证据不够完整",
    ):
        assert phrase in text


def test_blueprint_keeps_testing_contract_and_quality_commands() -> None:
    text = _read_blueprint()

    assert "tests/regression_frontend_manual_blueprint_contract.py" in text
    assert "tests/regression_excel_template_contracts.py" in text
    assert "tests/regression_frontend_ui_language_polish.py" in text
    assert "tests/regression_page_manual_registry.py" in text
    assert "tests/regression_config_manual_markdown.py" in text
    assert "tests/regression_manual_entry_scope.py" in text
    assert "git diff --check" in text
    assert "scripts/run_quality_gate.py --require-clean-worktree" in text

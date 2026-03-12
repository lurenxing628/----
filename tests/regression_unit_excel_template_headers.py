from __future__ import annotations

from collections import Counter, defaultdict

from core.services.process.unit_excel.template_builder import ConvertedTemplates, UnitTemplateBuilder


def test_unit_template_output_specs_include_team_headers() -> None:
    specs = {filename: headers for filename, headers, _ in ConvertedTemplates.output_specs()}

    assert specs["人员基本信息.xlsx"] == ["工号", "姓名", "状态", "班组", "备注"]
    assert specs["设备信息.xlsx"] == ["设备编号", "设备名称", "工种", "班组", "状态"]


def test_unit_template_builder_rows_include_team_columns() -> None:
    builder = UnitTemplateBuilder()
    _, operators_rows = builder._build_operator_rows({"张三"})
    machines_rows = builder._build_machines_rows(
        used_machine_ids={"MC001"},
        machine_label_map={"MC001": "数控车床1"},
        machine_internal_counter=defaultdict(Counter),
    )

    assert operators_rows[0]["班组"] is None
    assert machines_rows[0]["班组"] is None

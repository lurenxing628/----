"""回归测试：ConvertedTemplates.output_specs() 给人员/设备/人员设备关联/工种/供应商各模板输出的表头列序固定（含「班组」列），且 UnitTemplateBuilder 生成的人员行与设备行默认带「班组」键（值为 None）。"""

from __future__ import annotations

from collections import Counter, defaultdict

from core.services.process.unit_excel.template_builder import ConvertedTemplates, UnitTemplateBuilder


def test_unit_template_output_specs_include_team_headers() -> None:
    specs = {filename: headers for filename, headers, _ in ConvertedTemplates.output_specs()}

    assert specs["人员基本信息.xlsx"] == ["工号", "姓名", "状态", "班组", "备注"]
    assert specs["设备信息.xlsx"] == ["设备编号", "设备名称", "工种", "班组", "状态"]
    assert specs["人员设备关联.xlsx"] == ["工号", "设备编号", "技能等级", "主操设备"]
    assert specs["工种配置.xlsx"] == ["工种编号", "工种名称", "归属"]
    assert specs["供应商配置.xlsx"] == ["供应商编号", "名称", "对应工种", "默认周期", "状态", "备注"]


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

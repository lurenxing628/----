"""单元测试：web.routes.enum_display 各枚举中文化包装的输出口径（R41/O26 收口后）——machine/operator/day_type/priority/ready 五族已收口到 enum_normalizers 标准标签（未知坏值一律 loud 透传原值或显示「未知」，禁改回静默贴确定态/「-」占位）；两处 O26 业务补丁钉死：operator inactive（含中文别名「休假」）保留「停用/休假」双标签、ready 空值/None 钉「未齐套」（绝不让标准版默认「齐套」放行——未齐套冒充齐套会让调度员误放行，RK20）；batch_status 无 canonical 收口点保留私有旧口径；process_bp 的 _source_zh 已收口 source_type_label（中文别名「外协」不再误判「自制」）。"""

from __future__ import annotations


def test_enum_display_wrappers_expected_outputs() -> None:
    from web.routes.enum_display import (
        batch_status_zh,
        day_type_zh,
        machine_status_zh,
        operator_status_zh,
        priority_zh,
        ready_zh,
    )

    assert machine_status_zh("  active  ") == "可用"
    assert machine_status_zh("weird") == "weird", "未知值必须 loud 透传，禁静默贴占位符"
    assert machine_status_zh("") == "未知"
    assert machine_status_zh(None) == "未知"

    assert operator_status_zh("  inactive ") == "停用/休假", "O26 补丁：inactive 保留双标签，禁收窄成「停用」"
    assert operator_status_zh("休假") == "停用/休假", "中文别名经 normalize 归 inactive，同样保留双标签"
    assert operator_status_zh("weird") == "weird"
    assert operator_status_zh("") == "未知"
    assert operator_status_zh(None) == "未知"

    assert day_type_zh("  weekend  ") == "假期"
    assert day_type_zh("WorkdayX") == "WorkdayX"
    assert day_type_zh("") == "工作日", "空值走标准版默认 workday（O26 接受的口径变化）"
    assert day_type_zh(None) == "工作日"

    # batch_status 无 canonical 收口点，保留私有旧口径（O26 裁定）。
    assert batch_status_zh("  pending  ") == "待排"
    assert batch_status_zh("weird") == "weird"
    assert batch_status_zh("") == "-"
    assert batch_status_zh(None) == "-"

    assert priority_zh("  urgent  ") == "急件"
    assert priority_zh("weird") == "weird", "未知值由旧「未知」改 loud 透传原值（标准版 passthrough）"
    assert priority_zh("") == "普通"
    assert priority_zh(None) == "普通"

    assert ready_zh("  yes  ") == "齐套"
    assert ready_zh("no") == "未齐套"
    assert ready_zh("partial") == "部分齐套"
    assert ready_zh("weird") == "weird", "未知坏值 loud 透传，禁静默贴「未齐套」确定态"
    # O26/RK20 专项：空值反转防回退——标准版 ready_status_label("") 默认「齐套」，包装层补丁
    # 必须钉「未齐套」，绝不让未齐套冒充齐套放行；此断言禁贴回收口输出复活静默。
    assert ready_zh("") == "未齐套"
    assert ready_zh(None) == "未齐套"


def test_source_zh_no_longer_misjudges_external_aliases() -> None:
    from web.routes.process_bp import _source_zh

    assert _source_zh("external") == "外协"
    assert _source_zh("外协") == "外协", "R41 修复：中文别名「外协」旧实现误判「自制」"
    assert _source_zh("外") == "外协"
    assert _source_zh("internal") == "自制"
    assert _source_zh("自制") == "自制"
    assert _source_zh("") == "自制", "空值走标准版默认 internal（既有 Excel 导入口径）"
    assert _source_zh("weird") == "未知", "未知值显示「未知」，不再误贴「自制」确定态"

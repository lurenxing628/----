"""回归测试：core.shared.value_policies 字段策略矩阵契约——覆盖 default_days/ext_days/各权重/freeze_window_days/graph_* 等字段无缺项无重复，并逐字段校验 write_mode(REQUIRED)、read_mode(COMPAT)、strict/compat/blank 原因码、has_compat_default 及兼容回退值（如 default_days/ext_days=1.0、freeze_window_days=0、priority_weight/graph 权重不写死运行时默认）。import 直指承重点 core.shared（R33 已删 core.services.common.value_policies 壳；due_date/start_time/end_time 死切片随 R30 退场）。"""


def test_value_policies_matrix_contract() -> None:

    from core.shared.value_policies import (
        READ_COMPAT,
        WRITE_REQUIRED,
        get_field_policy,
        list_field_policies,
    )

    policies = list_field_policies()
    fields = {policy.field for policy in policies}
    expected_fields = {
        "default_days",
        "ext_days",
        "setup_hours",
        "unit_hours",
        "priority_weight",
        "due_weight",
        "ready_weight",
        "holiday_default_efficiency",
        "freeze_window_days",
        "ortools_time_limit_seconds",
        "graph_critical_weight",
        "graph_impact_weight",
        "time_budget_seconds",
    }

    missing = expected_fields - fields
    assert not missing, f"字段策略矩阵缺项：{sorted(missing)!r}"
    assert len(policies) == len(fields), "字段策略矩阵存在重复 field"

    default_days = get_field_policy("default_days")
    assert default_days.write_mode == WRITE_REQUIRED, f"default_days 写入语义异常：{default_days.write_mode!r}"
    assert default_days.read_mode == READ_COMPAT, f"default_days 读取语义异常：{default_days.read_mode!r}"
    assert default_days.strict_reason_code == "invalid_number", f"default_days strict 原因码异常：{default_days.strict_reason_code!r}"
    assert default_days.compat_reason_code == "invalid_number", f"default_days compat 原因码异常：{default_days.compat_reason_code!r}"
    assert default_days.blank_reason_code == "blank_required", f"default_days 空白原因码异常：{default_days.blank_reason_code!r}"
    assert default_days.has_compat_default is True, "default_days 应声明兼容回退值"
    assert abs(float(default_days.compat_default) - 1.0) < 1e-9, f"default_days compat 回退值异常：{default_days.compat_default!r}"

    ext_days = get_field_policy("ext_days")
    assert ext_days.compat_reason_code == "legacy_external_days_defaulted", f"ext_days compat 原因码异常：{ext_days.compat_reason_code!r}"
    assert ext_days.has_compat_default is True and abs(float(ext_days.compat_default) - 1.0) < 1e-9, (
        f"ext_days compat 回退值异常：{ext_days.compat_default!r}"
    )

    priority_weight = get_field_policy("priority_weight")
    assert priority_weight.read_mode == READ_COMPAT, f"priority_weight 读取语义异常：{priority_weight.read_mode!r}"
    assert priority_weight.has_compat_default is False, "priority_weight 不应在矩阵中写死运行时默认值"

    freeze_window_days = get_field_policy("freeze_window_days")
    assert freeze_window_days.compat_reason_code == "freeze_seed_unavailable", (
        f"freeze_window_days compat 原因码异常：{freeze_window_days.compat_reason_code!r}"
    )
    assert freeze_window_days.has_compat_default is True and int(freeze_window_days.compat_default) == 0, (
        f"freeze_window_days compat 回退值异常：{freeze_window_days.compat_default!r}"
    )

    graph_critical_weight = get_field_policy("graph_critical_weight")
    graph_impact_weight = get_field_policy("graph_impact_weight")
    assert graph_critical_weight.read_mode == READ_COMPAT, (
        f"graph_critical_weight 读取语义异常：{graph_critical_weight.read_mode!r}"
    )
    assert graph_critical_weight.has_compat_default is False, "graph_critical_weight 不应在矩阵中写死运行时默认值"
    assert graph_impact_weight.has_compat_default is False, "graph_impact_weight 不应在矩阵中写死运行时默认值"

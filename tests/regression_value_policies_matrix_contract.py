import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.common.value_policies import (
        READ_COMPAT,
        READ_FILTER_ONLY,
        WRITE_OPTIONAL,
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
        "time_budget_seconds",
        "due_date",
        "start_time",
        "end_time",
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

    due_date = get_field_policy("due_date")
    assert due_date.write_mode == WRITE_OPTIONAL, f"due_date 写入语义异常：{due_date.write_mode!r}"
    assert due_date.compat_reason_code == "invalid_due_date", f"due_date compat 原因码异常：{due_date.compat_reason_code!r}"
    assert due_date.has_compat_default is True and due_date.compat_default is None, "due_date 兼容回退应明确为空值"

    start_time = get_field_policy("start_time")
    end_time = get_field_policy("end_time")
    assert start_time.read_mode == READ_FILTER_ONLY, f"start_time 读取语义异常：{start_time.read_mode!r}"
    assert end_time.read_mode == READ_FILTER_ONLY, f"end_time 读取语义异常：{end_time.read_mode!r}"

    print("OK")


if __name__ == "__main__":
    main()

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

    assert machine_status_zh("active") == "可用"
    assert machine_status_zh("maintain") == "维修"
    assert machine_status_zh("inactive") == "停用"
    assert machine_status_zh("  active  ") == "可用"
    assert machine_status_zh("weird") == "weird"
    assert machine_status_zh("") == "-"
    assert machine_status_zh(None) == "-"

    assert operator_status_zh("active") == "在岗"
    assert operator_status_zh("inactive") == "停用/休假"
    assert operator_status_zh("  inactive ") == "停用/休假"
    assert operator_status_zh("weird") == "weird"
    assert operator_status_zh("") == "-"
    assert operator_status_zh(None) == "-"

    assert day_type_zh("workday") == "工作日"
    assert day_type_zh("holiday") == "假期"
    assert day_type_zh("weekend") == "假期"
    assert day_type_zh("  weekend  ") == "假期"
    assert day_type_zh("WorkdayX") == "WorkdayX"
    assert day_type_zh("") == "-"
    assert day_type_zh(None) == "-"

    assert batch_status_zh("pending") == "待排"
    assert batch_status_zh("scheduled") == "已排"
    assert batch_status_zh("processing") == "加工中"
    assert batch_status_zh("completed") == "已完成"
    assert batch_status_zh("cancelled") == "已取消"
    assert batch_status_zh("  pending  ") == "待排"
    assert batch_status_zh("weird") == "weird"
    assert batch_status_zh("") == "-"
    assert batch_status_zh(None) == "-"

    assert priority_zh("critical") == "特急"
    assert priority_zh("urgent") == "急件"
    assert priority_zh("normal") == "普通"
    assert priority_zh("  urgent  ") == "急件"
    assert priority_zh("weird") == "普通"
    assert priority_zh("") == "普通"
    assert priority_zh(None) == "普通"

    assert ready_zh("yes") == "齐套"
    assert ready_zh("partial") == "部分齐套"
    assert ready_zh("no") == "未齐套"
    assert ready_zh("  yes  ") == "齐套"
    assert ready_zh("weird") == "未齐套"
    assert ready_zh("") == "未齐套"
    assert ready_zh(None) == "未齐套"


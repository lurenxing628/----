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

    from core.services.common.compat_parse import parse_compat_date, parse_compat_float
    from core.services.common.degradation import DegradationCollector

    collector = DegradationCollector()

    default_days = parse_compat_float("abc", field="default_days", scope="supplier_history", collector=collector)
    assert abs(float(default_days or 0.0) - 1.0) < 1e-9, f"default_days compat 回退异常：{default_days!r}"

    ext_days = parse_compat_float("bad", field="ext_days", scope="schedule_input", collector=collector)
    assert abs(float(ext_days or 0.0) - 1.0) < 1e-9, f"ext_days compat 回退异常：{ext_days!r}"

    priority_weight = parse_compat_float(
        "   ",
        field="priority_weight",
        scope="config",
        collector=collector,
        fallback=0.4,
        min_value=0.0,
    )
    assert abs(float(priority_weight or 0.0) - 0.4) < 1e-9, f"priority_weight compat 回退异常：{priority_weight!r}"

    due_date = parse_compat_date("2026-02-31", field="due_date", scope="schedule_history", collector=collector)
    assert due_date is None, f"due_date compat 回退异常：{due_date!r}"

    events = collector.to_list()
    codes = [event.code for event in events]
    assert codes == [
        "invalid_number",
        "legacy_external_days_defaulted",
        "blank_required",
        "invalid_due_date",
    ], f"退化原因码异常：{codes!r}"
    assert all("兼容读取" in event.message for event in events), f"退化文案异常：{events!r}"
    assert all(event.sample is not None for event in events), "兼容读取事件应保留样本值"

    counters = collector.to_counters()
    assert counters["invalid_number"] == 1, f"invalid_number 计数异常：{counters!r}"
    assert counters["legacy_external_days_defaulted"] == 1, f"legacy_external_days_defaulted 计数异常：{counters!r}"
    assert counters["blank_required"] == 1, f"blank_required 计数异常：{counters!r}"
    assert counters["invalid_due_date"] == 1, f"invalid_due_date 计数异常：{counters!r}"

    print("OK")


if __name__ == "__main__":
    main()

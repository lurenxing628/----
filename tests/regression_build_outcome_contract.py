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

    from core.services.common.build_outcome import BuildOutcome
    from core.services.common.degradation import DegradationCollector

    collector = DegradationCollector()
    collector.add(
        code="invalid_number",
        scope="config",
        field="priority_weight",
        message="字段“priority_weight”历史数值无效，已按兼容读取回退为 0.4。",
        count=2,
    )
    collector.add(
        code="invalid_due_date",
        scope="gantt",
        field="due_date",
        message="字段“due_date”历史日期无效，已按兼容读取回退为 空值。",
    )

    outcome = BuildOutcome.from_collector(
        value=[{"id": 1, "name": "示例"}],
        collector=collector,
        counters={"manual_filtered": 3},
        empty_reason="compat_filtered",
    )
    assert outcome.value == [{"id": 1, "name": "示例"}], f"BuildOutcome.value 异常：{outcome.value!r}"
    assert outcome.empty_reason == "compat_filtered", f"BuildOutcome.empty_reason 异常：{outcome.empty_reason!r}"
    assert outcome.has_events is True, "BuildOutcome.has_events 应为 True"
    assert len(outcome.events) == 2, f"BuildOutcome.events 数量异常：{outcome.events!r}"
    assert outcome.counters["invalid_number"] == 2, f"BuildOutcome.invalid_number 计数异常：{outcome.counters!r}"
    assert outcome.counters["invalid_due_date"] == 1, f"BuildOutcome.invalid_due_date 计数异常：{outcome.counters!r}"
    assert outcome.counters["manual_filtered"] == 3, f"BuildOutcome 自定义计数异常：{outcome.counters!r}"

    duplicated = BuildOutcome(value=[], events=collector.to_list() + collector.to_list(), empty_reason="empty_after_filter")
    assert len(duplicated.events) == 2, f"BuildOutcome 应自动合并重复事件：{duplicated.events!r}"
    assert duplicated.counters["invalid_number"] == 4, f"BuildOutcome 重复事件计数异常：{duplicated.counters!r}"
    assert duplicated.empty_reason == "empty_after_filter", f"BuildOutcome empty_reason 保留异常：{duplicated.empty_reason!r}"

    print("OK")


if __name__ == "__main__":
    main()

"""回归测试（R55）：关键链 makespan 口径必须对外可辨——计划明细筛选路径
（critical_chain_for_plan_detail_filter，周窗口+资源/批次子集喂整版算法）产出标
scope=filtered；整版口径（provider/候选/空版本）经 _public_critical_chain 缺省落 full。
钉死"对外永远有 scope 标记"，杜绝筛选口径 makespan 被当整版误读。严禁裸删过滤。"""

from __future__ import annotations

from core.services.scheduler.gantt_contract import _public_critical_chain
from core.services.scheduler.gantt_service_support import critical_chain_for_plan_detail_filter


def test_detail_filter_path_marks_scope_filtered() -> None:
    result = critical_chain_for_plan_detail_filter([], {"batch_id": "B1"})
    assert result is not None, "filters 非空时应产出筛选口径结果，而非 None"
    assert result.get("scope") == "filtered", f"筛选口径须标 scope=filtered，实际 {result!r}"


def test_no_filter_returns_none_unchanged() -> None:
    # 无筛选 → 交回 None，由调用方落整版 provider；该路径不在 support 层标 scope。
    assert critical_chain_for_plan_detail_filter([], {}) is None


def test_public_contract_defaults_scope_full_when_absent() -> None:
    out = _public_critical_chain({"available": True, "ids": [], "edges": [], "makespan_end": None})
    assert out.get("scope") == "full", f"未标 scope 的整版口径对外须缺省 full，实际 {out!r}"


def test_public_contract_carries_filtered_scope() -> None:
    out = _public_critical_chain({"available": True, "ids": [], "edges": [], "scope": "filtered"})
    assert out.get("scope") == "filtered", f"筛选口径须透传到对外契约，实际 {out!r}"


def test_public_contract_unavailable_still_has_scope() -> None:
    out_full = _public_critical_chain({"available": False, "reason_code": "rows_exception"})
    assert out_full.get("scope") == "full", f"不可用整版口径仍须带 scope=full，实际 {out_full!r}"
    out_filtered = _public_critical_chain({"available": False, "reason_code": "rows_exception", "scope": "filtered"})
    assert out_filtered.get("scope") == "filtered", f"不可用筛选口径须保留 scope=filtered，实际 {out_filtered!r}"

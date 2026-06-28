"""回归测试:public / 内部 id 脱敏单一真相源契约(core/models/public_identifier_redaction)。

守护 roadmap scheduler-global-optimizer 4.8 的 public / diagnostics 边界(各 public 出口统一引用本模块):
- contains_internal_identifier:内部标识(字段名 / op: / OPnn / graph_w 指纹 / 调试容器名)命中即真;
  正常业务文本与裸 "baseline"(候选标签里的"原算法方案"来源)放行;
- is_forbidden_internal_key:并集禁用 key + token 形态 key 一律拦截,空 key 也拦截,正常 public key 放行;
- redact_internal_text:token / key:value 串脱敏成占位,正常中文不动,空串返回空串;
- 并集不可缩小:FORBIDDEN_INTERNAL_KEYS 必须覆盖历史各 public 出口(optimizer / graph / excel /
  operation_log)的全部内部 key——防止将来缩并集导致某一处脱敏被悄悄放松。
"""

from __future__ import annotations

from core.models.public_identifier_redaction import (
    FORBIDDEN_INTERNAL_KEYS,
    REDACTED_INTERNAL_TEXT,
    contains_internal_identifier,
    is_forbidden_internal_key,
    redact_internal_text,
)


def test_contains_internal_identifier_hits_internal_passes_normal() -> None:
    for hit in (
        "op_id",
        "candidate_key",
        "decision_fingerprint",
        "output_fingerprint",
        "graph_w1_of_3",
        "a op:batch:5 b",
        "OP123",
        "node_metrics_sample",
    ):
        assert contains_internal_identifier(hit) is True, hit
    for ok in ("edd", "批次顺序优化", "多起点方案", "baseline", ""):
        assert contains_internal_identifier(ok) is False, ok


def test_is_forbidden_internal_key_blocks_internal_passes_public() -> None:
    for forbidden in (
        "op_id",
        "candidate_key",
        "decision_fingerprint",
        "node_metrics_sample",
        "output_fingerprint",
        "unmatched_operation_ids_sample",
        "scenario_id",
        "op:1",
        "OP12",
        "graph_w2_of_5",
        "",
    ):
        assert is_forbidden_internal_key(forbidden) is True, forbidden
    for public in ("status", "node_count", "reason", "overdue_count", "makespan_hours"):
        assert is_forbidden_internal_key(public) is False, public


def test_redact_internal_text() -> None:
    r1 = redact_internal_text("op:123 hi")
    assert REDACTED_INTERNAL_TEXT in r1 and "hi" in r1 and "op:123" not in r1
    r2 = redact_internal_text("candidate_key: graph_w1_of_3")
    assert "candidate_key" not in r2 and "graph_w1_of_3" not in r2
    assert redact_internal_text("正常中文说明") == "正常中文说明"
    assert redact_internal_text("") == ""
    assert REDACTED_INTERNAL_TEXT in redact_internal_text("OP12")


def test_forbidden_keys_union_is_not_narrowed() -> None:
    """并集不可缩小:历史各 public 出口的内部 key 必须全部在并集内。"""
    required = {
        # optimizer / 候选
        "adopted_candidate_key",
        "baseline_best_candidate_key",
        "candidate_key",
        "candidate_id",
        "critical_best_candidate_key",
        "raw_score_best_candidate_key",
        "selected_candidate_key",
        "candidate_fingerprint",
        "decision_fingerprint",
        "output_fingerprint",
        "parent_fingerprint",
        "attempts",
        "attempts_public",
        # 图 / 节点
        "node_id",
        "op_id",
        "op_code",
        "from_node_id",
        "to_node_id",
        # 内部样本
        "critical_path_sample",
        "node_metrics_sample",
        "unmatched_operation_ids_sample",
        "bottleneck_machine_ids_sample",
        "warnings_sample",
        "graph_score_sample",
        "cycle_edges_sample",
        "matches_sample",
        "topological_order_sample",
        # 计划身份
        "schedule_id",
        "scenario_id",
        "source_table",
        "target_id",
    }
    missing = required - set(FORBIDDEN_INTERNAL_KEYS)
    assert not missing, f"并集缺失内部 key(脱敏被放松):{sorted(missing)}"

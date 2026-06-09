"""plan_role 性质测试 —— 锁住“看哪套方案”的语义，打在真收口点上。

真收口点(已核验)：core/models/schedule_plan_role.py
  PLAN_ROLE_LABELS / plan_role_label / VALID_PLAN_ROLES / is_comparison_role
刻意不新建 resolve_plan_role 之类的新模块(那会变成 P5 第N套私有实现)。
"""
from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from core.models import schedule_plan_role as pr

VALID_LABELS = {
    "adopted": "正式采用方案",
    "baseline_best": "原算法代表方案",
    "critical_best": "重点工序优先代表方案",
}


def test_valid_set_matches_registry():
    # 概念账本 allowed_values 必须和模型层 VALID_PLAN_ROLES 一致。
    assert set(pr.VALID_PLAN_ROLES) == set(VALID_LABELS)


@given(st.sampled_from(sorted(VALID_LABELS)))
def test_valid_roles_have_stable_labels(role):
    assert pr.plan_role_label(role) == VALID_LABELS[role]


@given(st.sampled_from(sorted(VALID_LABELS)))
def test_user_visible_label_does_not_leak_internal_token(role):
    # 用户可见标签不得回泄内部 token(ARCHITECTURE.md:65)。
    label = pr.plan_role_label(role)
    for leaked in (role, "candidate_id", "source_table", "plan_role", "scenario_id"):
        assert leaked not in label


@given(st.one_of(st.none(), st.just(""), st.just("   ")))
def test_missing_role_normalizes_to_adopted_label(value):
    # 模型层对缺失/空值容忍并回落正式采用方案标签。
    assert pr.plan_role_label(value) == VALID_LABELS["adopted"]


def test_unknown_role_uses_unknown_label():
    assert pr.plan_role_label("future_role") == "未知方案身份"


@given(st.sampled_from(["baseline_best", "critical_best"]))
def test_comparison_roles_flagged(role):
    assert pr.is_comparison_role(role) is True


def test_adopted_is_not_comparison():
    assert pr.is_comparison_role("adopted") is False

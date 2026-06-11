#!/usr/bin/env python
"""校验 concept-registry.yaml 与真代码一致 —— 防账本自身腐烂。

可用交付 .venv(3.8)或 .venv-semantic(3.14)跑,只 import 项目代码 + PyYAML。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from core.models import schedule_plan_role as pr  # noqa: E402
from core.services.scheduler.config import config_field_spec as cfs  # noqa: E402


def main() -> int:
    reg = yaml.safe_load((ROOT / ".codestable" / "semantics" / "concept-registry.yaml").read_text("utf-8"))
    errs = []
    by_id = {c["id"]: c for c in reg["concepts"]}

    # plan_role: allowed_values 必须 == VALID_PLAN_ROLES,且标签匹配
    pr_c = by_id["plan_role"]
    reg_roles = set(pr_c["allowed_values"])
    if reg_roles != set(pr.VALID_PLAN_ROLES):
        errs.append(f"plan_role 值集漂移: 账本{reg_roles} vs 代码{set(pr.VALID_PLAN_ROLES)}")
    for role, meta in pr_c["allowed_values"].items():
        want = meta.get("user_label")
        got = pr.PLAN_ROLE_LABELS.get(role)
        if want != got:
            errs.append(f"plan_role[{role}] 标签漂移: 账本'{want}' vs 代码'{got}'")

    # graph_analysis_mode: 默认值/choices 必须匹配
    gm_c = by_id["graph_analysis_mode"]
    spec = cfs.get_field_spec("graph_analysis_mode")
    if set(gm_c["allowed_values"]) != set(spec.choices):
        errs.append(f"graph_analysis_mode choices 漂移: 账本{set(gm_c['allowed_values'])} vs 代码{set(spec.choices)}")

    # schedule_result_status: 枚举值集==allowed_values，别名表一致，标签匹配
    from core.services.scheduler.summary.schedule_summary_types import ScheduleResultStatus  # noqa: E402
    from web.viewmodels import scheduler_summary_result_state as rs  # noqa: E402

    st_c = by_id["schedule_result_status"]
    enum_values = {m.value for m in ScheduleResultStatus}
    if set(st_c["allowed_values"]) != enum_values:
        errs.append(f"result_status 值集漂移: 账本{set(st_c['allowed_values'])} vs 枚举{enum_values}")
    labels = rs.result_status_display_labels()
    for value, meta in st_c["allowed_values"].items():
        if meta.get("user_label") != labels.get(value):
            errs.append(f"result_status[{value}] 标签漂移: 账本'{meta.get('user_label')}' vs 代码'{labels.get(value)}'")
    if st_c["input_aliases"] != rs._LEGACY_RESULT_STATUS_ALIASES:
        errs.append(f"result_status 别名漂移: 账本{st_c['input_aliases']} vs 代码{rs._LEGACY_RESULT_STATUS_ALIASES}")

    # schedule_strategy: 合法值==config choices；合法∪兼容==展示字典 7 键
    from web.viewmodels.scheduler_history_summary import _STRATEGY_LABELS  # noqa: E402

    sg_c = by_id["schedule_strategy"]
    cfg_choices = set(cfs.get_field_spec("sort_strategy").choices)
    if set(sg_c["allowed_values"]) != cfg_choices:
        errs.append(f"strategy 合法值漂移: 账本{set(sg_c['allowed_values'])} vs 配置{cfg_choices}")
    union = set(sg_c["allowed_values"]) | set(sg_c["display_compat_values"])
    if union != set(_STRATEGY_LABELS):
        errs.append(f"strategy 标签键集漂移: 账本∪{union} vs 代码{set(_STRATEGY_LABELS)}")
    for value, meta in {**sg_c["allowed_values"], **sg_c["display_compat_values"]}.items():
        if meta.get("user_label") != _STRATEGY_LABELS.get(value):
            errs.append(f"strategy[{value}] 标签漂移: 账本'{meta.get('user_label')}' vs 代码'{_STRATEGY_LABELS.get(value)}'")

    if errs:
        print("❌ concept-registry 与代码不一致:")
        for e in errs:
            print("  -", e)
        return 1
    print("✅ concept-registry.yaml 与真代码一致(plan_role + graph_analysis_mode + result_status + strategy)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

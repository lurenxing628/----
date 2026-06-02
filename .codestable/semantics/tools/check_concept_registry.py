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

    if errs:
        print("❌ concept-registry 与代码不一致:")
        for e in errs:
            print("  -", e)
        return 1
    print("✅ concept-registry.yaml 与真代码一致(plan_role 值集/标签 + graph_analysis_mode choices)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

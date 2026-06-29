"""Reference diagnostics for optimizer benchmark comparisons.

This module is benchmark scaffolding, not production scheduling logic.  It keeps
the GraphReady v2 comparison matrix honest by separating references that are
objective-comparable from references that are useful only as diagnostics.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.algorithms.objective_specs import objective_metric_keys
from core.services.scheduler.run.optimizer_proof_contracts import assert_public_payload_safe
from core.services.scheduler.run.optimizer_proof_harness import run_optimizer_proof_harness

REFERENCE_DIAGNOSTICS_SCHEMA_VERSION = 1
DEFAULT_REFERENCE_DIAGNOSTICS_OUTPUT = Path("evidence/QualityGate/long_gate/optimizer_benchmark/reference_diagnostics.json")

CHANGEOVER_BASELINE_SPECS = (
    {
        "case_slug": "wtsds-loader-contract",
        "label": "WTSDS",
        "not_comparable_reason": "WTSDS 是序列相关准备时间数据集；本仓库当前没有装载 tracked 数据，不能拿它证明 APS 当前目标更优。",
    },
    {
        "case_slug": "cicirello-sdst-loader-contract",
        "label": "Cicirello SDST",
        "not_comparable_reason": "Cicirello SDST 基准只作为换型基准准备项；当前不下载、不提交 tracked 外部数据。",
    },
    {
        "case_slug": "sdst-fjsp-loader-contract",
        "label": "SDST FJSP",
        "not_comparable_reason": "SDST FJSP 同时改变作业车间模型和换型口径；当前只能定义装载和脱敏规则，不能进入 APS min_overdue gap。",
    },
)


def build_reference_diagnostics(*, objective_name: str = "min_overdue") -> Dict[str, Any]:
    metric_keys = list(objective_metric_keys(objective_name))
    proof_payload = run_optimizer_proof_harness(require_optimal=True)
    rows = [_row_from_tiny_reference(ref) for ref in proof_payload.get("references") or []]
    rows.append(_jackson_preemptive_reference_row(objective_name=objective_name, metric_keys=metric_keys))
    rows.extend(_changeover_baseline_rows(objective_name=objective_name, metric_keys=metric_keys))
    payload = {
        "schema_version": REFERENCE_DIAGNOSTICS_SCHEMA_VERSION,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "status": "passed" if rows and proof_payload.get("status") == "passed" else "failed",
        "objective_name": objective_name,
        "objective_metric_keys": metric_keys,
        "case_count": len(rows),
        "references": rows,
        "summary": _summary(rows),
        "tracked_external_data_written": False,
    }
    assert_public_payload_safe(_public_projection(payload))
    return payload


def load_reference_diagnostics(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_reference_diagnostics(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _row_from_tiny_reference(ref: Dict[str, Any]) -> Dict[str, Any]:
    comparable = bool(ref.get("bound_is_objective_comparable"))
    return {
        "schema_version": REFERENCE_DIAGNOSTICS_SCHEMA_VERSION,
        "case_group": "tiny",
        "case_slug": str(ref.get("case_slug") or ""),
        "reference_type": str(ref.get("reference_type") or ""),
        "bound_metric": str(ref.get("bound_metric") or ""),
        "objective_name": str(ref.get("objective_name") or ""),
        "objective_metric_keys": list(ref.get("objective_metric_keys") or []),
        "comparison_scope": str(ref.get("bound_scope") or "same_model"),
        "bound_is_objective_comparable": comparable,
        "not_comparable_reason": None if comparable else "该 reference 不是同目标 objective_score 证明，只能作诊断。",
        "changeover_baseline_status": "not_applicable",
        "diagnostics_ref": ref.get("diagnostics_ref"),
        "oracle_status": str(ref.get("oracle_status") or ""),
        "gap_to_oracle_pct": ref.get("gap_to_oracle_pct"),
        "gap_to_bound_pct": ref.get("gap_to_bound_pct"),
    }


def _jackson_preemptive_reference_row(*, objective_name: str, metric_keys: List[str]) -> Dict[str, Any]:
    comparable = False
    return {
        "schema_version": REFERENCE_DIAGNOSTICS_SCHEMA_VERSION,
        "case_group": "reference",
        "case_slug": "jackson-single-machine-preemptive",
        "reference_type": "lower_bound",
        "bound_metric": "max_lateness_hours",
        "objective_name": objective_name,
        "objective_metric_keys": list(metric_keys),
        "comparison_scope": "single_machine_preemptive_reference",
        "bound_is_objective_comparable": comparable,
        "not_comparable_reason": "Jackson 单机抢占参考量尺优化的是最大迟延，不是 APS 完整 objective_score，不能进入 gap 计算。",
        "changeover_baseline_status": "not_applicable",
        "diagnostics_ref": "optimizer_reference_diagnostics:jackson-single-machine-preemptive",
        "oracle_status": "not_run",
        "gap_to_oracle_pct": None,
        "gap_to_bound_pct": None,
    }


def _changeover_baseline_rows(*, objective_name: str, metric_keys: List[str]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for spec in CHANGEOVER_BASELINE_SPECS:
        slug = str(spec["case_slug"])
        rows.append(
            {
                "schema_version": REFERENCE_DIAGNOSTICS_SCHEMA_VERSION,
                "case_group": "changeover_reference",
                "case_slug": slug,
                "reference_type": "folded_not_comparable",
                "bound_metric": "changeover_count",
                "objective_name": objective_name,
                "objective_metric_keys": list(metric_keys),
                "comparison_scope": "external_changeover_baseline_preparation",
                "bound_is_objective_comparable": False,
                "not_comparable_reason": str(spec["not_comparable_reason"]),
                "changeover_baseline_status": "not_available",
                "changeover_baseline_label": str(spec["label"]),
                "diagnostics_ref": f"optimizer_reference_diagnostics:changeover:{slug}",
                "oracle_status": "not_run",
                "gap_to_oracle_pct": None,
                "gap_to_bound_pct": None,
                "loader_contract": {
                    "load": "defined",
                    "score": "defined",
                    "redact": "defined",
                    "default_output": "stdout_or_ignored",
                    "tracked_data": "not_written",
                    "ignored_rule": "external_data_absent",
                },
            }
        )
    return rows


def _summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    comparable = [row for row in rows if row.get("bound_is_objective_comparable")]
    not_comparable = [row for row in rows if not row.get("bound_is_objective_comparable")]
    return {
        "comparable_reference_count": len(comparable),
        "not_comparable_reference_count": len(not_comparable),
        "changeover_loaded_count": len([row for row in rows if row.get("changeover_baseline_status") == "loaded"]),
        "changeover_not_available_count": len(
            [row for row in rows if row.get("changeover_baseline_status") == "not_available"]
        ),
    }


def _public_projection(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "schema_version": payload.get("schema_version"),
        "status": payload.get("status"),
        "objective_name": payload.get("objective_name"),
        "case_count": payload.get("case_count"),
        "summary": payload.get("summary"),
        "references": [
            {
                "case_group": row.get("case_group"),
                "case_slug": row.get("case_slug"),
                "reference_type": row.get("reference_type"),
                "bound_metric": row.get("bound_metric"),
                "comparison_scope": row.get("comparison_scope"),
                "bound_is_objective_comparable": row.get("bound_is_objective_comparable"),
                "not_comparable_reason": row.get("not_comparable_reason"),
                "changeover_baseline_status": row.get("changeover_baseline_status"),
            }
            for row in payload.get("references") or []
        ],
    }


__all__ = [
    "DEFAULT_REFERENCE_DIAGNOSTICS_OUTPUT",
    "REFERENCE_DIAGNOSTICS_SCHEMA_VERSION",
    "build_reference_diagnostics",
    "load_reference_diagnostics",
    "write_reference_diagnostics",
]

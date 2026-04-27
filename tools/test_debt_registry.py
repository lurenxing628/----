from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, cast

from .quality_gate_ledger import sort_ledger, validate_ledger
from .quality_gate_shared import (
    LEDGER_SCHEMA_VERSION,
    QualityGateError,
    extract_json_code_block,
    now_shanghai_iso,
)

BASELINE_BEGIN = "<!-- APS-FULL-PYTEST-BASELINE:BEGIN -->"
BASELINE_END = "<!-- APS-FULL-PYTEST-BASELINE:END -->"
TEST_DEBT_FAMILY = "operator_machine_normalization_contract_drift"

P0_TEST_DEBT_SEED_METADATA: Dict[str, Dict[str, Any]] = {
    "tests/test_operator_machine_exception_paths.py::test_list_by_operator_propagates_unexpected_readside_normalization_errors": {
        "debt_id": "test-debt:operator-machine-list-by-operator-stale-patch",
        "reason": "测试仍在 patch 已不存在的技能等级归一化旧入口，无法验证 list_by_operator 的异常传播合同。",
        "domain": "personnel.operator_machine",
        "style": "stale_patch_target",
        "root": {
            "module": "core.services.personnel.operator_machine_service",
            "function": "list_by_operator",
        },
        "owner": "personnel.operator_machine",
        "exit_condition": "更新读侧异常传播测试的旧 patch 目标，让该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。",
    },
    "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_optional_only_converts_value_error": {
        "debt_id": "test-debt:operator-machine-normalize-skill-level-optional-stale-patch",
        "reason": "测试仍在 patch 已不存在的 normalize_skill_level 旧入口，无法验证可选技能等级归一化合同。",
        "domain": "personnel.operator_machine",
        "style": "stale_patch_target",
        "root": {
            "module": "core.services.personnel.operator_machine_normalizers",
            "function": "normalize_skill_level_optional",
        },
        "owner": "personnel.operator_machine",
        "exit_condition": "更新测试 patch 目标或改成公开入口验证，让该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。",
    },
    "tests/test_operator_machine_exception_paths.py::test_normalize_skill_level_stored_only_falls_back_for_value_error": {
        "debt_id": "test-debt:operator-machine-normalize-skill-level-stored-stale-patch",
        "reason": "测试仍在 patch 已不存在的 normalize_skill_level 旧入口，无法验证落库存储技能等级归一化合同。",
        "domain": "personnel.operator_machine",
        "style": "stale_patch_target",
        "root": {
            "module": "core.services.personnel.operator_machine_normalizers",
            "function": "normalize_skill_level_stored",
        },
        "owner": "personnel.operator_machine",
        "exit_condition": "更新测试 patch 目标或改成公开入口验证，让该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。",
    },
    "tests/test_operator_machine_exception_paths.py::test_resolve_write_values_only_converts_validation_error": {
        "debt_id": "test-debt:operator-machine-resolve-write-values-return-contract",
        "reason": "测试仍期待写入解析错误时返回 None，但当前合同是返回旧值和错误消息、调用方跳过写入。",
        "domain": "personnel.operator_machine",
        "style": "return_contract_drift",
        "root": {
            "module": "core.services.personnel.operator_machine_service",
            "function": "_resolve_write_values",
        },
        "owner": "personnel.operator_machine",
        "exit_condition": "按当前“返回旧值和错误消息、调用方跳过写入”的合同更新测试，或先改实现再同步测试；该 nodeid 定向 pytest 普通通过后，从正式 full pytest 债务基线移除。",
    },
    "tests/test_query_services.py::test_operator_machine_query_service_lists_with_names_and_linkage_rows": {
        "debt_id": "test-debt:operator-machine-query-service-dirty-fields-contract",
        "reason": "测试仍按普通字段精确相等，未覆盖查询服务当前返回 dirty_fields/dirty_reasons 的读侧归一化合同。",
        "domain": "personnel.operator_machine",
        "style": "readside_normalization_contract_drift",
        "root": {
            "module": "core.services.personnel.operator_machine_query_service",
            "function": "OperatorMachineQueryService._normalize_row",
        },
        "owner": "personnel.operator_machine",
        "exit_condition": "更新测试，明确断言归一化后的 skill_level/is_primary 以及 dirty_fields/dirty_reasons；该 nodeid 定向 pytest 普通通过后，从正式 full pytest 债务基线移除。",
    },
}


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityGateError(f"{field_name} 必须是非空字符串")
    text = value.strip()
    if text.lower() == "untriaged":
        raise QualityGateError(f"{field_name} 不允许写 untriaged 占位")
    return text


def _classification_list(payload: Dict[str, Any], key: str) -> List[str]:
    classifications = cast(Dict[str, Any], payload.get("classifications") or {})
    return [str(nodeid) for nodeid in list(classifications.get(key) or [])]


def baseline_candidate_nodeids(payload: Dict[str, Any]) -> List[str]:
    return sorted(_classification_list(payload, "candidate_test_debt"))


def _count_or_actual_blocker(payload: Dict[str, Any], counts: Dict[str, Any], key: str) -> Optional[str]:
    if _classification_list(payload, key) or int(counts.get(key) or 0) != 0:
        return key
    return None


def _collection_error_blocker(payload: Dict[str, Any], summary: Dict[str, Any]) -> Optional[str]:
    if list(payload.get("collection_errors") or []) or int(summary.get("collection_error_count") or 0) != 0:
        return "collection_error_count"
    return None


def _baseline_blockers(payload: Dict[str, Any], *, require_importable: bool) -> List[str]:
    summary = dict(payload.get("summary") or {})
    counts = dict(summary.get("classification_counts") or {})
    blockers = []
    if str(payload.get("baseline_kind") or "") != "after_main_style_isolation":
        blockers.append("baseline_kind")
    if require_importable and bool(payload.get("importable")) is not True:
        blockers.append("importable")
    if int(payload.get("exitstatus") or 0) not in {0, 1}:
        blockers.append("pytest_exitstatus")
    for key in ["required_or_quality_gate_self_failure", "main_style_isolation_candidate"]:
        blocker = _count_or_actual_blocker(payload, counts, key)
        if blocker:
            blockers.append(blocker)
    collection_blocker = _collection_error_blocker(payload, summary)
    if collection_blocker:
        blockers.append(collection_blocker)
    return blockers


def load_full_test_debt_baseline(path: str) -> Dict[str, Any]:
    baseline_path = Path(path)
    if not baseline_path.exists():
        raise QualityGateError(f"测试债务 baseline 不存在：{path}")
    payload = extract_json_code_block(
        baseline_path.read_text(encoding="utf-8"),
        BASELINE_BEGIN,
        BASELINE_END,
        "full pytest 测试债务 baseline",
    )
    validate_importable_baseline(payload)
    return payload


def validate_importable_baseline(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise QualityGateError("测试债务 baseline 顶层必须是对象")
    blockers = _baseline_blockers(payload, require_importable=True)
    if blockers:
        raise QualityGateError("测试债务 baseline 不能导入，存在禁入项：" + ", ".join(blockers))
    _validate_candidate_nodeids(payload, expected_nodeids=sorted(P0_TEST_DEBT_SEED_METADATA))


def validate_current_candidate_payload(payload: Dict[str, Any], *, expected_nodeids: Sequence[str]) -> None:
    if not isinstance(payload, dict):
        raise QualityGateError("当前 full pytest dry-run 顶层必须是对象")
    blockers = _baseline_blockers(payload, require_importable=False)
    if blockers:
        raise QualityGateError("当前 full pytest dry-run 不能承接导入，存在禁入项：" + ", ".join(blockers))
    _validate_candidate_nodeids(payload, expected_nodeids=sorted(str(nodeid) for nodeid in expected_nodeids))


def _validate_candidate_nodeids(payload: Dict[str, Any], *, expected_nodeids: Sequence[str]) -> None:
    candidate_nodeids = baseline_candidate_nodeids(payload)
    expected = sorted(str(nodeid) for nodeid in expected_nodeids)
    if candidate_nodeids != expected:
        raise QualityGateError("candidate_test_debt 与任务 5 已核实的 5 条 nodeid 不一致")
    summary = dict(payload.get("summary") or {})
    counts = dict(summary.get("classification_counts") or {})
    if int(counts.get("candidate_test_debt") or 0) != len(expected):
        raise QualityGateError("candidate_test_debt 数量与任务 5 已核实数量不一致")
    if int(summary.get("failed_nodeid_count") or 0) != len(expected):
        raise QualityGateError("failed_nodeid_count 与任务 5 已核实数量不一致")


def build_test_debt_entries(payload: Dict[str, Any], *, last_verified_at: str) -> List[Dict[str, Any]]:
    validate_importable_baseline(payload)
    nodeids = sorted(
        str(nodeid)
        for nodeid in cast(Dict[str, Any], payload.get("classifications") or {}).get("candidate_test_debt") or []
    )
    entries: List[Dict[str, Any]] = []
    for nodeid in nodeids:
        seed = copy.deepcopy(P0_TEST_DEBT_SEED_METADATA[nodeid])
        entry = {
            "debt_id": seed["debt_id"],
            "nodeid": nodeid,
            "mode": "xfail",
            "reason": seed["reason"],
            "domain": seed["domain"],
            "style": seed["style"],
            "root": seed["root"],
            "owner": seed["owner"],
            "exit_condition": seed["exit_condition"],
            "last_verified_at": last_verified_at,
            "debt_family": TEST_DEBT_FAMILY,
        }
        validate_test_debt_entry(entry)
        entries.append(entry)
    return entries


def validate_test_debt_entry(entry: Dict[str, Any]) -> None:
    for field_name in [
        "debt_id",
        "nodeid",
        "mode",
        "reason",
        "domain",
        "style",
        "owner",
        "exit_condition",
        "last_verified_at",
        "debt_family",
    ]:
        _require_text(entry.get(field_name), field_name)
    if str(entry.get("mode")) not in {"xfail", "fixed"}:
        raise QualityGateError(f"mode 非法：{entry.get('mode')}")
    root = entry.get("root")
    if not isinstance(root, dict):
        raise QualityGateError("root 必须是对象")
    _require_text(root.get("module"), "root.module")
    _require_text(root.get("function"), "root.function")


def build_test_debt_ledger_from_baseline(
    ledger: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    verified_head_sha: str,
    last_verified_at: str = "",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    verified_at = last_verified_at or now_shanghai_iso()
    entries = build_test_debt_entries(payload, last_verified_at=verified_at)
    next_ledger = copy.deepcopy(ledger)
    existing_test_debt = next_ledger.get("test_debt")
    if isinstance(existing_test_debt, dict) and existing_test_debt.get("entries"):
        raise QualityGateError("治理台账已存在 test_debt.entries，导入命令不得覆盖已有测试债务登记")
    next_ledger["schema_version"] = LEDGER_SCHEMA_VERSION
    next_ledger["updated_at"] = verified_at
    next_ledger["test_debt"] = {
        "ratchet": {"max_registered_xfail": len([entry for entry in entries if entry["mode"] == "xfail"])},
        "entries": entries,
    }
    sorted_ledger = sort_ledger(next_ledger)
    validate_ledger(sorted_ledger)
    summary = {
        "baseline_head_sha": str(payload.get("head_sha") or ""),
        "verified_head_sha": verified_head_sha,
        "imported_count": len(entries),
        "nodeids": [entry["nodeid"] for entry in entries],
        "max_registered_xfail": sorted_ledger["test_debt"]["ratchet"]["max_registered_xfail"],
        "updated_at": sorted_ledger.get("updated_at"),
    }
    return sorted_ledger, summary


def registered_test_debt_entries(ledger: Dict[str, Any]) -> List[Dict[str, Any]]:
    validate_ledger(ledger)
    return [
        dict(entry)
        for entry in cast(List[Dict[str, Any]], cast(Dict[str, Any], ledger.get("test_debt") or {}).get("entries") or [])
    ]


def active_xfail_nodeids(ledger: Dict[str, Any]) -> Set[str]:
    return {
        str(entry["nodeid"])
        for entry in registered_test_debt_entries(ledger)
        if str(entry.get("mode") or "") == "xfail"
    }


__all__ = [
    "P0_TEST_DEBT_SEED_METADATA",
    "TEST_DEBT_FAMILY",
    "active_xfail_nodeids",
    "baseline_candidate_nodeids",
    "build_test_debt_entries",
    "build_test_debt_ledger_from_baseline",
    "load_full_test_debt_baseline",
    "registered_test_debt_entries",
    "validate_current_candidate_payload",
    "validate_importable_baseline",
    "validate_test_debt_entry",
]

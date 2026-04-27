from __future__ import annotations

import copy
import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _import_checker():
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("tools.check_full_test_debt", None)
    return importlib.import_module("tools.check_full_test_debt")


def _entry(
    nodeid: str = "tests/test_registered.py::test_known_debt",
    *,
    mode: str = "xfail",
    debt_id: str = "test-debt:sample",
    reason: str = "旧测试合同尚未更新",
) -> Dict[str, Any]:
    return {
        "debt_id": debt_id,
        "nodeid": nodeid,
        "mode": mode,
        "reason": reason,
        "domain": "personnel.operator_machine",
        "style": "stale_patch_target",
        "root": {
            "module": "core.services.personnel.operator_machine_normalizers",
            "function": "normalize_skill_level_optional",
        },
        "owner": "personnel.operator_machine",
        "exit_condition": "该 nodeid 定向 pytest 普通通过，并从正式 full pytest 债务基线移除。",
        "last_verified_at": "2026-04-27T08:00:00+08:00",
        "debt_family": "operator_machine_normalization_contract_drift",
    }


def _ledger(*entries: Dict[str, Any], max_registered_xfail: int = 1) -> Dict[str, Any]:
    from tools.quality_gate_shared import LEDGER_IDENTITY_STRATEGY, LEDGER_SCHEMA_VERSION, STARTUP_SCOPE_PATTERNS

    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "identity_strategy": LEDGER_IDENTITY_STRATEGY,
        "updated_at": "2026-04-27T08:00:00+08:00",
        "oversize_allowlist": [],
        "complexity_allowlist": [],
        "silent_fallback": {"scope": list(STARTUP_SCOPE_PATTERNS), "entries": []},
        "test_debt": {
            "ratchet": {"max_registered_xfail": max_registered_xfail},
            "entries": list(entries),
        },
        "accepted_risks": [],
    }


def _report(
    nodeid: str,
    *,
    outcome: str = "skipped",
    wasxfail_reason: str = "test-debt:sample: 旧测试合同尚未更新",
    xfail_marker_present: bool = True,
    xfail_marker_reason: str = "test-debt:sample: 旧测试合同尚未更新",
    xfail_marker_strict: bool = True,
    strict_xpass: bool = False,
) -> Dict[str, Any]:
    return {
        "nodeid": nodeid,
        "when": "call",
        "outcome": outcome,
        "duration": 0.0,
        "longrepr": "",
        "xfail_marker_present": xfail_marker_present,
        "xfail_marker_reason": xfail_marker_reason,
        "xfail_marker_strict": xfail_marker_strict,
        "wasxfail_reason": wasxfail_reason,
        "strict_xpass": strict_xpass,
    }


def _payload(
    *,
    collected_nodeids: List[str],
    reports: List[Dict[str, Any]],
    candidate_test_debt: Optional[List[str]] = None,
    required_or_quality_gate_self_failure: Optional[List[str]] = None,
    main_style_isolation_candidate: Optional[List[str]] = None,
    collection_errors: Optional[List[Dict[str, Any]]] = None,
    exitstatus: int = 0,
) -> Dict[str, Any]:
    candidate = list(candidate_test_debt or [])
    required = list(required_or_quality_gate_self_failure or [])
    main_style = list(main_style_isolation_candidate or [])
    errors = list(collection_errors or [])
    classifications = {
        "candidate_test_debt": candidate,
        "main_style_isolation_candidate": main_style,
        "required_or_quality_gate_self_failure": required,
    }
    failed_nodeids = set(candidate + required + main_style)
    return {
        "schema_version": 2,
        "baseline_kind": "after_main_style_isolation",
        "importable": False,
        "importable_blockers": [],
        "generated_at": "2026-04-27T08:00:00+08:00",
        "head_sha": "deadbeef",
        "collector_argv": ["--baseline-kind", "after_main_style_isolation", "--", "tests"],
        "git_status_short_before": None,
        "worktree_clean_before": None,
        "python_executable": sys.executable,
        "python_version": sys.version.splitlines()[0],
        "pytest_version": "8.0.0",
        "pytest_args": ["tests", "-q", "--tb=short", "-ra", "-p", "no:cacheprovider"],
        "exitstatus": exitstatus,
        "collected_nodeids": list(collected_nodeids),
        "collection_errors": errors,
        "reports": list(reports),
        "summary": {
            "collected_count": len(collected_nodeids),
            "failed_nodeid_count": len(failed_nodeids),
            "collection_error_count": len(errors),
            "outcome_counts": {},
            "classification_counts": {key: len(value) for key, value in classifications.items()},
        },
        "classifications": classifications,
    }


def test_check_full_test_debt_accepts_registered_xfails_and_stable_summary() -> None:
    checker = _import_checker()
    nodeid = "tests/test_registered.py::test_known_debt"
    entry = _entry(nodeid)
    payload = _payload(collected_nodeids=[nodeid], reports=[_report(nodeid)])

    summary = checker.build_full_test_debt_summary(payload, ledger=_ledger(entry))

    assert summary == {
        "schema_version": 1,
        "status": "passed",
        "active_xfail_count": 1,
        "collected_count": 1,
        "collection_error_count": 0,
        "fixed_count": 0,
        "max_registered_xfail": 1,
        "unexpected_failure_count": 0,
        "active_xfail_entries": [
            {
                "debt_id": "test-debt:sample",
                "nodeid": nodeid,
                "reason": "旧测试合同尚未更新",
            }
        ],
    }


@pytest.mark.parametrize(
    ("payload_update", "message"),
    [
        (lambda nodeid: {"candidate_test_debt": ["tests/test_new_failure.py::test_new_failure"], "exitstatus": 1}, "candidate_test_debt"),
        (lambda nodeid: {"exitstatus": 1}, "exitstatus"),
        (lambda nodeid: {"collected_nodeids": [], "reports": []}, "collected_nodeids"),
        (lambda nodeid: {"reports": [_report(nodeid, wasxfail_reason="test-debt:sample: wrong")]}, "xfail reason"),
        (lambda nodeid: {"reports": [_report(nodeid, xfail_marker_strict=False)]}, "strict"),
        (lambda nodeid: {"reports": [_report(nodeid, outcome="failed", wasxfail_reason="", strict_xpass=True)]}, "XPASS"),
    ],
)
def test_check_full_test_debt_rejects_invalid_current_proof(payload_update, message: str) -> None:
    checker = _import_checker()
    nodeid = "tests/test_registered.py::test_known_debt"
    entry = _entry(nodeid)
    data = {
        "collected_nodeids": [nodeid],
        "reports": [_report(nodeid)],
        "exitstatus": 0,
    }
    data.update(payload_update(nodeid))
    payload = _payload(**data)

    with pytest.raises(checker.QualityGateError, match=message):
        checker.build_full_test_debt_summary(payload, ledger=_ledger(entry))


def test_check_full_test_debt_rejects_fixed_entry_still_marked_xfail() -> None:
    checker = _import_checker()
    nodeid = "tests/test_registered.py::test_fixed"
    entry = _entry(nodeid, mode="fixed")
    payload = _payload(collected_nodeids=[nodeid], reports=[_report(nodeid)])

    with pytest.raises(checker.QualityGateError, match="fixed"):
        checker.build_full_test_debt_summary(payload, ledger=_ledger(entry, max_registered_xfail=0))


def test_check_full_test_debt_accepts_fixed_entry_when_collected_and_passed() -> None:
    checker = _import_checker()
    nodeid = "tests/test_registered.py::test_fixed"
    entry = _entry(nodeid, mode="fixed")
    payload = _payload(
        collected_nodeids=[nodeid],
        reports=[
            _report(
                nodeid,
                outcome="passed",
                wasxfail_reason="",
                xfail_marker_present=False,
                xfail_marker_reason="",
                xfail_marker_strict=False,
            )
        ],
    )

    summary = checker.build_full_test_debt_summary(payload, ledger=_ledger(entry, max_registered_xfail=0))

    assert summary["active_xfail_count"] == 0
    assert summary["fixed_count"] == 1
    assert summary["max_registered_xfail"] == 0


@pytest.mark.parametrize(
    ("collected_nodeids", "reports", "message"),
    [
        ([], [], "collect"),
        (
            ["tests/test_registered.py::test_fixed"],
            [
                _report(
                    "tests/test_registered.py::test_fixed",
                    outcome="failed",
                    wasxfail_reason="",
                    xfail_marker_present=False,
                    xfail_marker_reason="",
                    xfail_marker_strict=False,
                )
            ],
            "普通通过",
        ),
        (
            ["tests/test_registered.py::test_fixed"],
            [
                _report(
                    "tests/test_registered.py::test_fixed",
                    outcome="passed",
                    wasxfail_reason="",
                    xfail_marker_present=True,
                    xfail_marker_reason="",
                    xfail_marker_strict=False,
                )
            ],
            "xfail",
        ),
    ],
)
def test_check_full_test_debt_rejects_invalid_fixed_proof(
    collected_nodeids: List[str], reports: List[Dict[str, Any]], message: str
) -> None:
    checker = _import_checker()
    nodeid = "tests/test_registered.py::test_fixed"
    entry = _entry(nodeid, mode="fixed")
    payload = _payload(collected_nodeids=collected_nodeids, reports=reports)

    with pytest.raises(checker.QualityGateError, match=message):
        checker.build_full_test_debt_summary(payload, ledger=_ledger(entry, max_registered_xfail=0))


def test_check_full_test_debt_rejects_ratchet_overflow() -> None:
    checker = _import_checker()
    nodeid = "tests/test_registered.py::test_known_debt"
    entry = _entry(nodeid)
    payload = _payload(collected_nodeids=[nodeid], reports=[_report(nodeid)])

    with pytest.raises(checker.QualityGateError, match="max_registered_xfail"):
        checker.build_full_test_debt_summary(payload, ledger=_ledger(entry, max_registered_xfail=0))


def test_check_full_test_debt_rejects_ratchet_slack() -> None:
    checker = _import_checker()
    nodeid = "tests/test_registered.py::test_known_debt"
    entry = _entry(nodeid)
    payload = _payload(collected_nodeids=[nodeid], reports=[_report(nodeid)])

    with pytest.raises(checker.QualityGateError, match="max_registered_xfail"):
        checker.build_full_test_debt_summary(payload, ledger=_ledger(entry, max_registered_xfail=2))


def test_check_full_test_debt_rejects_bad_collector_json() -> None:
    checker = _import_checker()

    with pytest.raises(checker.QualityGateError, match="JSON"):
        checker.parse_collector_payload("not json")


def test_check_full_test_debt_rejects_required_test_active_xfail() -> None:
    checker = _import_checker()
    from tools.quality_gate_shared import QUALITY_GATE_SELFTEST_PATH

    nodeid = f"{QUALITY_GATE_SELFTEST_PATH}::test_required"
    entry = _entry(nodeid)
    payload = _payload(collected_nodeids=[nodeid], reports=[_report(nodeid)])

    with pytest.raises(checker.QualityGateError, match="required/proof"):
        checker.build_full_test_debt_summary(payload, ledger=_ledger(entry))


def test_check_full_test_debt_rejects_report_missing_xfail_machine_fields() -> None:
    checker = _import_checker()
    nodeid = "tests/test_registered.py::test_known_debt"
    entry = _entry(nodeid)
    report = copy.deepcopy(_report(nodeid))
    report.pop("wasxfail_reason")
    payload = _payload(collected_nodeids=[nodeid], reports=[report])

    with pytest.raises(checker.QualityGateError, match="wasxfail_reason"):
        checker.build_full_test_debt_summary(payload, ledger=_ledger(entry))

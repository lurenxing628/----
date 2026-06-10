"""回归测试：verify_required_regressions_from_full_test_debt 从 full-test-debt payload 核销必跑回归（P2 证明捆绑已退役）——main 是纯只读 CLI，核销通过只打印摘要、不写任何文件；当某必跑文件未被 payload 覆盖、存在非通过 report、或阻断分类（candidate_test_debt 等）非空时抛 RequiredRegressionProofError（required ⊄ debt 语义）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from tools import verify_required_regressions_from_full_test_debt as verifier


def _report(nodeid: str, *, outcome: str = "passed", when: str = "call", xfail: bool = False) -> Dict[str, Any]:
    return {
        "nodeid": nodeid,
        "when": when,
        "outcome": outcome,
        "duration": 0.0,
        "longrepr": "",
        "xfail_marker_present": xfail,
        "xfail_marker_reason": "test-debt:sample" if xfail else "",
        "xfail_marker_strict": False,
        "xfail_marker_run": False,
        "wasxfail_reason": "",
        "strict_xpass": False,
    }


def _payload(
    *,
    nodeids: List[str],
    reports: List[Dict[str, Any]],
    candidate_test_debt: Optional[List[str]] = None,
    required_or_quality_gate_self_failure: Optional[List[str]] = None,
    main_style_isolation_candidate: Optional[List[str]] = None,
) -> Dict[str, Any]:
    classifications = {
        "candidate_test_debt": list(candidate_test_debt or []),
        "main_style_isolation_candidate": list(main_style_isolation_candidate or []),
        "required_or_quality_gate_self_failure": list(required_or_quality_gate_self_failure or []),
    }
    return {
        "schema_version": 2,
        "generated_at": "2026-05-16T08:00:00",
        "head_sha": "deadbeef",
        "exitstatus": 0,
        "collected_nodeids": list(nodeids),
        "collection_errors": [],
        "reports": list(reports),
        "summary": {
            "collected_count": len(nodeids),
            "collection_error_count": 0,
            "classification_counts": {key: len(value) for key, value in classifications.items()},
        },
        "classifications": classifications,
    }


def test_main_verifies_required_regressions_without_writing_files(monkeypatch, tmp_path: Path, capsys) -> None:
    required = ["tests/test_required_a.py", "tests/regression_required_b.py"]
    nodeids = [
        "tests/test_required_a.py::test_a",
        "tests/regression_required_b.py::regression_b",
        "tests/test_other.py::test_other",
    ]
    payload_path = tmp_path / "current_full_test_debt.json"
    output_path = tmp_path / "required_regressions.json"
    payload_path.write_text(
        json.dumps(
            _payload(
                nodeids=nodeids,
                reports=[
                    _report("tests/test_required_a.py::test_a", when="setup"),
                    _report("tests/test_required_a.py::test_a", when="call"),
                    _report("tests/test_required_a.py::test_a", when="teardown"),
                    _report("tests/regression_required_b.py::regression_b", when="setup"),
                    _report("tests/regression_required_b.py::regression_b", when="call"),
                    _report("tests/regression_required_b.py::regression_b", when="teardown"),
                    _report("tests/test_other.py::test_other"),
                ],
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier.quality_gate_shared, "iter_quality_gate_required_tests", lambda: list(required))
    monkeypatch.setattr(
        verifier.quality_gate_support,
        "iter_required_regression_groups",
        lambda groups=None: [
            {
                "group_id": "quality_gate",
                "label": "Quality gate",
                "target_paths": [required[0]],
                "input_file_scopes": [],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
                "env_keys": [],
            },
            {
                "group_id": "scheduler",
                "label": "Scheduler",
                "target_paths": [required[1]],
                "input_file_scopes": [],
                "config_file_scopes": [],
                "tool_file_scopes": [],
                "dependency_file_scopes": [],
                "env_keys": [],
            },
        ],
    )

    assert verifier.main(["--payload", str(payload_path)]) == 0

    # P2 证明捆绑已退役：核销器是纯只读 CLI，不再写父证明/子证明文件
    assert not output_path.exists()
    assert not (output_path.parent / output_path.stem).exists()

    verification = verifier.verify_required_regressions_from_payload(
        json.loads(payload_path.read_text(encoding="utf-8"))
    )
    assert verification["required_target_paths"] == required
    assert verification["required_nodeids"] == [
        "tests/regression_required_b.py::regression_b",
        "tests/test_required_a.py::test_a",
    ]
    assert verification["required_nodeid_count_by_path"] == {required[0]: 1, required[1]: 1}
    assert verification["group_coverage"]["missing"] == []
    assert verification["group_coverage"]["unknown"] == []
    assert verification["collected_count"] == 3
    assert verification["report_count"] == 7


def test_verify_rejects_missing_required_file() -> None:
    payload = _payload(
        nodeids=["tests/test_required_a.py::test_a"],
        reports=[_report("tests/test_required_a.py::test_a")],
    )

    with pytest.raises(verifier.RequiredRegressionProofError, match="没有被 full-test-debt 覆盖"):
        verifier.verify_required_regressions_from_payload(
            payload,
            required_tests=["tests/test_required_a.py", "tests/test_missing_required.py"],
        )


def test_verify_rejects_failed_required_report() -> None:
    payload = _payload(
        nodeids=["tests/test_required_a.py::test_a"],
        reports=[_report("tests/test_required_a.py::test_a", outcome="failed")],
    )

    with pytest.raises(verifier.RequiredRegressionProofError, match="非通过 reports"):
        verifier.verify_required_regressions_from_payload(payload, required_tests=["tests/test_required_a.py"])


def test_verify_tolerates_allowlisted_skipped_required_report() -> None:
    # 白名单内 nodeid 的 skipped（平台合法 skip，如含换行符文件名在 Windows 非法）不算非通过。
    allowed_nodeid = verifier.quality_gate_shared.REQUIRED_REGRESSION_ALLOWED_SKIPPED_NODEIDS[0]
    required_path = allowed_nodeid.split("::", 1)[0]
    payload = _payload(
        nodeids=[allowed_nodeid],
        reports=[_report(allowed_nodeid, outcome="skipped", when="setup")],
    )

    verification = verifier.verify_required_regressions_from_payload(payload, required_tests=[required_path])
    assert allowed_nodeid in verification["required_nodeids"]


def test_verify_rejects_non_allowlisted_skipped_required_report() -> None:
    # 未登记白名单的 required nodeid 一旦 skipped 仍判非通过，守卫不放水。
    payload = _payload(
        nodeids=["tests/test_required_a.py::test_a"],
        reports=[_report("tests/test_required_a.py::test_a", outcome="skipped", when="setup")],
    )

    with pytest.raises(verifier.RequiredRegressionProofError, match="非通过 reports"):
        verifier.verify_required_regressions_from_payload(payload, required_tests=["tests/test_required_a.py"])


def test_verify_rejects_non_empty_blocking_classification() -> None:
    payload = _payload(
        nodeids=["tests/test_required_a.py::test_a"],
        reports=[_report("tests/test_required_a.py::test_a")],
        candidate_test_debt=["tests/test_new_failure.py::test_new_failure"],
    )

    with pytest.raises(verifier.RequiredRegressionProofError, match="classifications.candidate_test_debt 非空"):
        verifier.verify_required_regressions_from_payload(payload, required_tests=["tests/test_required_a.py"])

from __future__ import annotations

from pathlib import Path


def test_current_evidence_entrypoint_exists() -> None:
    text = Path("evidence/current/README.md").read_text(encoding="utf-8")

    assert "python scripts/run_quality_gate.py --require-clean-worktree" in text
    assert "不代表当前通过状态" in text


def test_evidence_readme_points_to_current_entrypoint() -> None:
    text = Path("evidence/README.md").read_text(encoding="utf-8")

    assert "current/" in text
    assert "failures/" in text
    assert "archive/" in text
    assert "当前状态判断规则" in text


def test_audit_readme_points_to_latest_month() -> None:
    text = Path("audit/README.md").read_text(encoding="utf-8")

    assert "2026-05" in text
    assert "2026-04-25" in text


def test_phase6_audit_entrypoint_records_scope() -> None:
    text = Path("audit/2026-05/README.md").read_text(encoding="utf-8")

    assert "result_summary" in text
    assert "scheduler 路由导入即注册" in text
    assert "python scripts/run_quality_gate.py --require-clean-worktree" in text

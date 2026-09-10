"""Completion scope survives public projection without exposing operation identities."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithms.evaluation import compute_metrics
from core.services.scheduler.contracts.optimizer_public_safety import project_attempt_metrics, project_public_metrics
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary


def _partial_metrics():
    start = datetime(2026, 1, 1, 8)
    operations = [SimpleNamespace(id=i, batch_id="B1") for i in (1, 2)]
    result = SimpleNamespace(op_id=1, batch_id="B1", start_time=start, end_time=start + timedelta(hours=1),
                             source="external", machine_id=None, operator_id=None)
    return compute_metrics([result], {"B1": SimpleNamespace(due_date="2026-01-01", priority="normal")},
                           expected_operations=operations).to_dict()


@pytest.mark.parametrize("project", [project_attempt_metrics, project_public_metrics])
def test_partial_scope_is_preserved_without_identifier_samples(project):
    original = _partial_metrics()
    projected = project(original)
    completion = projected["completion"]
    assert completion["objective_defined"] is False
    assert completion["objective_score_policy"] == "unknown_all_components"
    assert completion["due_metrics_scope"] == "completed_batches_only"
    assert completion["missing_operation_count"] == 1
    assert completion["incomplete_batch_count"] == completion["partial_batch_count"] == 1
    assert "B1" not in json.dumps(projected)
    assert "unknown_objective_value" not in completion
    assert original["completion"]["incomplete_batch_ids_sample"] == ["B1"]


def test_algo_metrics_and_attempts_both_keep_completion_scope():
    metrics = _partial_metrics()
    public, _ = project_public_algo_summary({
        "metrics": metrics,
        "attempts": [{"tag": "start:priority_first|sgs:slack", "failed_ops": 1,
                      "dispatch_mode": "sgs", "dispatch_rule": "slack", "metrics": metrics}],
    })
    assert public["metrics"]["completion"]["objective_defined"] is False
    assert public["attempts"][0]["metrics"]["completion"] == public["metrics"]["completion"]


@pytest.mark.parametrize("project", [project_attempt_metrics, project_public_metrics])
def test_projection_does_not_coerce_malformed_flags_or_publish_unknown_fields(project):
    raw = {"completion": {"objective_defined": "false", "missing_operation_count": True,
                           "incomplete_batch_count": -1, "partial_batch_count": "2",
                           "objective_score_policy": "op:SECRET", "private": "OP-SECRET",
                           "incomplete_batch_ids_sample": ["B1"]}}
    assert project(raw) == {}


@pytest.mark.parametrize("project", [project_attempt_metrics, project_public_metrics])
def test_legacy_metrics_without_completion_keep_their_contract(project):
    assert project({"overdue_count": 1}) == {"overdue_count": 1}

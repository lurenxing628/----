"""Trial predecessor render/callback contracts; real browser geometry belongs to EQ."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tests/workbench/trial_predecessor_labels_probe.cjs"


def task(ref, piece_id, sequence, predecessors=()):
    return {
        "task_ref": ref, "piece_id": piece_id, "sequence": sequence,
        "batch_id": "B1", "process_label": "Turning", "part_no": "P1",
        "part_name": "Part", "source": "internal", "quantity": 1,
        "batch_quantity": 3, "priority": "normal", "due_date": None,
        "machine_ref": None, "operator_ref": None,
        "start": "2026-09-10T08:00:00", "end": "2026-09-10T08:15:00",
        "original": {"machine_ref": None, "operator_ref": None,
                     "start": "2026-09-10T08:00:00", "end": "2026-09-10T08:15:00"},
        "hours": {"setup_hours": 0, "unit_hours": 0.25, "total_hours": 0.25,
                  "basis": "effective_processing_hours"},
        "predecessor_refs": list(predecessors), "predecessor_operation_refs": [],
        "issues": [], "data_gaps": [], "execution": None, "execution_at_creation": None,
        "edit_context": {"can_change": False, "blocked_reasons": []},
    }


def probe(tasks, selected, labels, follow_labels=None):
    node = os.environ.get("WORKBENCH_NODE") or shutil.which("node")
    assert node, "Node is required for the local TrialDetails source probe"
    value = {"data": {"tasks": tasks, "resources": {"machines": [], "operators": []}},
             "selected": selected, "labels": labels, "follow_labels": follow_labels}
    result = subprocess.run([node, str(PROBE)], input=json.dumps(value), cwd=str(ROOT),
                            text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["source_unchanged"] and report["real_button"]
    assert report["browser_geometry_verified"] is False
    return report


def test_join_links_identify_three_original_pieces_and_keep_ref_navigation():
    common = task("origin-z", None, 10)
    pieces = [task("opaque-" + ref, "item-" + piece, 30, [common["task_ref"]])
              for ref, piece in [("9", "A"), ("1", "B"), ("7", "C")]]
    ordered = [pieces[1], pieces[2], pieces[0]]
    join = task("join", None, 40, [row["task_ref"] for row in ordered])
    report = probe([pieces[2], join, pieces[0], common, pieces[1]], "join",
                   ["前序 分件 " + row["piece_id"] + " · Turning 30" for row in ordered],
                   [["前序 共同工序 · Turning 10"]] * 3)
    assert report["navigation"] == join["predecessor_refs"]
    assert len(set(report["labels"])) == 3


@pytest.mark.parametrize("piece_id", ["长中文原始分件编号" * 32, "OriginalPiece" * 40])
def test_long_original_piece_labels_are_complete_and_allow_wrapping(piece_id):
    previous = task("opaque-not-the-piece", piece_id, 30)
    previous["process_label"] = "长中文精加工工序名称"
    current = task("current", None, 40, [previous["task_ref"]])
    report = probe([current, previous], "current",
                   ["前序 分件 " + piece_id + " · 长中文精加工工序名称 30"])
    assert report["wrap_contracts"] == 1


@pytest.mark.parametrize("identity", ["missing", "empty", "blank", "gap"])
def test_missing_identity_does_not_invent_piece_from_sequence_or_ref(identity):
    previous = task("ref-item-FAKE-999", None, 999)
    if identity == "missing":
        del previous["piece_id"]
    elif identity == "gap":
        previous["data_gaps"] = [{"field": "piece_id", "message": "Not recorded"}]
    else:
        previous["piece_id"] = "" if identity == "empty" else "   "
    current = task("current", None, 40, [previous["task_ref"]])
    report = probe([current, previous], "current", ["前序 分件未记录 · Turning 999"])
    assert "FAKE" not in report["labels"][0]


def test_common_predecessor_and_no_predecessors_remain_explicit():
    common = task("common", None, 10)
    current = task("current", "item-A", 20, ["common"])
    probe([current, common], "current", ["前序 共同工序 · Turning 10"], [[]])
    assert probe([common], "common", [])["navigation"] == []

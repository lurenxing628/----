"""Acceptance bookkeeping cannot turn a family pass into atomic proof."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / ".codestable/roadmap/workbench-prototype-migration/acceptance-master"


def test_frozen_denominator_and_explicit_action_ids():
    ledger = json.loads((FOLDER / "actions.json").read_text(encoding="utf-8"))
    raw = (ROOT / ledger["planning_path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ledger["planning_sha256"]
    planning = json.loads(raw)
    expected = {row["id"] for row in planning["capabilities"] if row["workstream"] in ("master-data", "batches")}
    assert len(expected) == 58
    assert {row["family_id"] for row in ledger["families"]} == expected
    assert sum(row["workstream"] == "master-data" for row in ledger["families"]) == 41
    assert sum(row["workstream"] == "batches" for row in ledger["families"]) == 17
    ids = []
    for family in ledger["families"]:
        for action in family["actions"]:
            assert action["action_id"].startswith(family["family_id"] + "-A")
            assert action["description"]
            assert set(action["gates"]) == {"B", "K", "V", "P"}
            for gate, state in action["gates"].items():
                assert state in ("pending", "pending_main_review", "passed", "failed", "not_applicable", "reused")
                if state in ("passed", "reused", "not_applicable"):
                    evidence = [row for row in action["evidence"] if row.get("gate") == gate]
                    assert evidence, (action["action_id"], gate)
                    assert all(row.get("reason") for row in evidence)
                    if state in ("passed", "reused"):
                        assert all(row.get("source_sha256") for row in evidence)
                    if gate == "V" and state == "passed":
                        assert all(row.get("reviewer") == "Main" for row in evidence)
            ids.append(action["action_id"])
    assert len(ids) == len(set(ids)) == ledger["atomic_actions"] == 599

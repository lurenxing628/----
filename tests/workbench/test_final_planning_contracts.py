"""The frozen 37-family denominator cannot be replaced by passed prototypes."""

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROADMAP = REPO / ".codestable/roadmap/workbench-prototype-migration"


def test_planning_action_denominator_keeps_every_frozen_family():
    frozen_bytes = (ROADMAP / "workbench-capabilities.json").read_bytes()
    assert hashlib.sha256(frozen_bytes).hexdigest() == "0cad8e05a5adbadacf0c2ecef1e56f38bb4c97e6948c1dc5a2fc847bcec1ffb2"
    frozen = json.loads(frozen_bytes)
    planned = json.loads((ROADMAP / "acceptance-planning/action-inventory.json").read_text(encoding="utf-8"))
    families = {row["id"] for row in frozen["capabilities"] if row["workstream"] in ("scheduling", "trial")}
    assert len(families) == planned["capability_count"] == 37
    assert {row["capability_id"] for row in planned["capabilities"]} == families
    actions = [action for row in planned["capabilities"] for action in row["actions"]]
    ids = {row["action_id"] for row in actions}
    assert len(ids) == len(actions) == planned["action_count"] == 146
    assert all(row["status"] == "not_run" for row in actions)
    assert all(row["implementation_status"] == "not_started" for row in frozen["capabilities"])


def test_probe_ids_must_exist_in_action_inventory():
    planned = json.loads((ROADMAP / "acceptance-planning/action-inventory.json").read_text(encoding="utf-8"))
    declared = {action["action_id"] for row in planned["capabilities"] for action in row["actions"]}
    used = set()
    for path in Path(__file__).parent.glob("final_planning*.cjs"):
        used.update(re.findall(r"WBP-[A-Z]+-\d{3}\.[a-z-]+", path.read_text(encoding="utf-8")))
    assert used
    assert not used - declared

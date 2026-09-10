"""True process death and cold startup, not merely another SQLite connection."""

import json
import subprocess
import sys
from pathlib import Path

from tests.workbench.trial_adoption_support import INTENT, KEY, preview, saved_scenario, service
from tests.workbench.trial_adoption_support import trial_case as trial_case
from tests.workbench.trial_support import snapshot


def cold(case, mode, saved, *args):
    return subprocess.run([sys.executable, "-m", "tests.workbench.trial_adoption_restart_support", mode,
                           str(case.path), saved["scenario_ref"], KEY, *args],
                          cwd=str(Path(__file__).resolve().parents[2]), capture_output=True, text=True, timeout=20)


def test_cold_process_recovers_original_committed_receipt_readonly(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    result = service(case.conn).adopt(saved["scenario_ref"], preview(case, saved), KEY, INTENT)
    before = snapshot(case.conn)
    child = cold(case, "lookup", saved)
    assert child.returncode == 0, child.stderr
    value = json.loads(child.stdout)
    assert value["changes"] == 0 and value["in_transaction"] is False
    assert value["result"]["receipt_ref"] == result["receipt_ref"] and value["result"]["replayed"]
    assert snapshot(case.conn) == before


def test_process_death_before_commit_leaves_no_partial_plan_or_receipt(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    before = snapshot(case.conn)
    child = cold(case, "crash", saved)
    assert child.returncode == 73, child.stderr
    assert snapshot(case.conn) == before
    recovered = cold(case, "lookup", saved)
    assert recovered.returncode == 0, recovered.stderr
    assert json.loads(recovered.stdout) == {"result": None, "changes": 0, "in_transaction": False}
    result = service(case.conn).adopt(saved["scenario_ref"], preview(case, saved), KEY, INTENT)
    assert result["result"] == "committed" and not result["replayed"]


def test_old_process_write_token_is_not_a_restart_authorization(trial_case):
    case = trial_case
    saved = saved_scenario(case)
    token = preview(case, saved)
    before = snapshot(case.conn)
    child = cold(case, "stale", saved, token)
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == {"result": {"code": "stale_write"}, "changes": 0, "in_transaction": False}
    assert snapshot(case.conn) == before


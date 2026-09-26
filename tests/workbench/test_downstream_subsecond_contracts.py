"""Real read DTOs retain subsecond official plans through browser validation."""

import json
import os
import shutil
import subprocess
from pathlib import Path

from tests.workbench.actual_gantt_support import BASE, prepare
from tests.workbench.field_workspace_support import make_app
from tests.workbench.plan_read_support import add_tasks
from tests.workbench.run_candidate_baseline_support import api, original_plan
from tests.workbench.run_candidate_support import candidate_case as candidate_case
from tests.workbench.run_candidate_support import compute, read


def probe(tmp_path, mode, payload):
    source = tmp_path / (mode + ".json")
    source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    script = Path(__file__).with_suffix(".cjs")
    result = subprocess.run(
        [os.environ.get("WORKBENCH_NODE") or shutil.which("node"), str(script), mode, str(source)],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_real_field_and_actual_gantt_accept_microsecond_task_and_exact_gap(tmp_path):
    actual = prepare(tmp_path / "actual.db", reports=False)
    with actual.db() as conn:
        conn.execute("UPDATE Schedule SET start_time='2026-09-09 08:00:00',"
                     "end_time='2026-09-09 08:00:00.000001' WHERE version=3")
        add_tasks(conn, 1, start="2026-09-09 08:01:00", end="2026-09-09 08:01:00.000001")
        conn.execute("UPDATE Schedule SET machine_id='PRIVATE-M1',operator_id='PRIVATE-O1' WHERE version=3")
    query = {"plan_ref": actual.ref()}
    response = actual.client.get(BASE, query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    field = make_app(actual.path).test_client().get("/api/workbench/v1/execution/tasks", query_string=query)
    assert field.status_code == 200, field.get_data(as_text=True)
    result = probe(tmp_path, "actual", {"actual": response.get_json(), "field": field.get_json()})
    assert result == {"tasks": 2, "exact_gap_verified": True}


def test_real_admission_baseline_keeps_positive_microsecond_interval(candidate_case, tmp_path):
    case = candidate_case
    original_plan(case, start="2026-09-09 08:00:00.123456", end="2026-09-09 08:00:00.123457")
    case.conn.execute("UPDATE BatchOperations SET unit_hours=0.001 WHERE id=?", (case.op_id,))
    case.conn.commit()
    _, refs = compute(case)
    client, _ = api(case)
    workspace = read(client, "/candidates/" + refs[0] + "/workspace")
    baseline = read(client, "/candidates/" + refs[0] + "/baseline")
    assert probe(tmp_path, "baseline", {"workspace": workspace, "baseline": baseline}) == {
        "microsecond_baseline_comparable": True}

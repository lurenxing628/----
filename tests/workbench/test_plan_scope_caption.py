"""FA caption checks using EA engine adoption, real HTTP and the shipped UI."""

import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.workbench.ea_zero_duration_support import adopt, point_candidate
from tests.workbench.point_downstream_support import app_for, read, serve
from tests.workbench.test_run_candidate_support import retained
from tests.workbench.trial_support import trial_case as trial_case  # noqa: F401

HERE = Path(__file__).resolve().parent
MODULES = "/Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
BROWSER = "/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium"


def invoke(script, value):
    node = shutil.which("node")
    assert node, "Node is required for the real caption browser probe"
    result = subprocess.run([node, str(HERE / script)], input=json.dumps(value),
        text=True, capture_output=True, timeout=180,
        env=dict(os.environ, NODE_PATH=MODULES, WORKBENCH_BROWSER=BROWSER))
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.fixture(scope="module")
def caption_assets(tmp_path_factory):
    output = tmp_path_factory.mktemp("fa-plan-scope-caption")
    invoke("point_downstream_browser_build_support.cjs", {"output": str(output)})
    return output


@pytest.mark.parametrize("kind,risk", [("point-only", "on_time"), ("mixed-last-point", "overdue"),
                                     ("mixed-first-point", "unknown"), ("ordinary", "on_time")])
def test_plan_scope_caption_real_adoption(trial_case, caption_assets, tmp_path, kind, risk):
    case = trial_case
    if kind.startswith("mixed"):
        case.operation(seq=2, setup_hours=0, unit_hours=0 if kind == "mixed-last-point" else 0.25)
    candidate = point_candidate(case, unit=0.25 if kind in ("ordinary", "mixed-last-point") else 0)
    plan = adopt(case, candidate, key="fa-scope-caption-adopt-01")
    if risk != "on_time":
        case.conn.execute("UPDATE Batches SET due_date=? WHERE batch_id='B1'",
                          (None if risk == "unknown" else "2026-09-08",))
        case.conn.commit()
    app = app_for(case, caption_assets)
    client = app.test_client()
    path = "/api/workbench/v1/plans/" + plan["plan_ref"] + "/workspace"
    with retained(case.conn):
        whole = read(client, path)["data"]
        span = whole["plan_span"]
        inclusive = kind in ("point-only", "mixed-last-point")
        assert whole["plan"]["is_current_official"] is True
        assert whole["scope"]["range_start"] is None
        assert [row["risk"] for row in whole["projections"]["delivery_risks"]["items"]] == [risk]
        assert span.get("end_inclusive", False) is inclusive
        assert (span["start"] == span["end"]) is (kind == "point-only")
        points = [row for row in whole["tasks"] if row.get("event_kind") == "point"]
        assert len(points) == (0 if kind == "ordinary" else 1)
        assert all(row["start"] == row["end"] and row["duration_seconds"] == 0
                   and row["occupies_resources"] is False for row in points)
        if kind.startswith("mixed"):
            assert any(row["start"] < row["end"] for row in whole["tasks"])
        def label(value):
            return value.replace("T", " ")

        prefix = "计划时间范围：" + label(span["start"]) + " → " + label(span["end"])
        caption = "计划时间点：" + label(span["start"]) if kind == "point-only" else (
            prefix + ("（包含末端计划点）" if inclusive else "（不含结束时刻）"))
        fixtures = [{"name": "whole", "scope": {}, "caption": caption, "payload": read(client, path)}]
        boundary = points[0]["start"] if points else span["end"]
        low = (datetime.fromisoformat(span["start"]) - timedelta(seconds=1)).isoformat()
        high = (datetime.fromisoformat(boundary) + timedelta(seconds=1)).isoformat()
        for name, start, end in [("end-excludes", low, boundary), ("start-includes", boundary, high)]:
            scope = {"range_start": start, "range_end": end}
            payload = read(client, path, **scope)
            refs = {row["task_ref"] for row in payload["data"]["tasks"]}
            for point in points:
                assert (point["task_ref"] in refs) is (name == "start-includes")
            caption = "计划时间范围：" + label(start) + " → " + label(end) + "（不含结束时刻）"
            fixtures.append({"name": name, "scope": scope, "caption": caption, "payload": payload})
        with serve(app) as base:
            assert not base.endswith(":53144")
            print(invoke("plan_scope_caption_probe.cjs", {"base": base, "plan_ref": plan["plan_ref"],
                "fixtures": fixtures, "output": str(tmp_path)}), flush=True)
    print("FA_CAPTION_EVIDENCE " + str(tmp_path), flush=True)

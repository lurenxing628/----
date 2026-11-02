from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict

import pytest

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / ".limcode"
    / "skills"
    / "aps-start-and-rerun-route"
    / "scripts"
    / "run_start_and_rerun_route.py"
)


def _load_route_script_module():
    spec = importlib.util.spec_from_file_location("run_start_and_rerun_route_test_mod", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install_workbench_stub(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    *,
    version: int = 7,
    plan_ref: str = "plan-official-7",
    workspace_plan: Dict[str, Any] | None = None,
    tasks: Any = None,
    task_count: Any = 3,
    tasks_complete: Any = True,
) -> None:
    resolved_tasks = [{"task_id": idx} for idx in range(3)] if tasks is None else tasks
    resolved_workspace_plan = (
        {"plan_ref": plan_ref, "version": version, "kind": "official"}
        if workspace_plan is None
        else workspace_plan
    )

    def fake_read_json(url: str) -> Dict[str, Any]:
        if url == "http://127.0.0.1:5000/api/workbench/v1/plans?collection=history&size=1":
            return {
                "plans": [
                    {
                        "plan_ref": plan_ref,
                        "version": version,
                        "kind": "official",
                        "capabilities": {"view": True},
                    }
                ]
            }
        if url == f"http://127.0.0.1:5000/api/workbench/v1/plans/{plan_ref}/workspace":
            return {
                "plan": resolved_workspace_plan,
                "tasks": resolved_tasks,
                "task_count": task_count,
                "tasks_complete": tasks_complete,
            }
        raise AssertionError(f"Unexpected workbench URL: {url}")

    monkeypatch.setattr(module, "_read_json", fake_read_json)


@pytest.mark.parametrize(
    ("task_count", "sliced_len", "tasks_complete"),
    [
        (3, 3, True),
        (5000, 5000, True),
        (5001, 5000, False),
        (10000, 5000, False),
    ],
)
def test_read_existing_plan_accepts_complete_and_first_page_sliced_tasks(
    monkeypatch: pytest.MonkeyPatch,
    task_count: int,
    sliced_len: int,
    tasks_complete: bool,
) -> None:
    module = _load_route_script_module()
    _install_workbench_stub(
        monkeypatch,
        module,
        tasks=[{"task_id": i} for i in range(sliced_len)],
        task_count=task_count,
        tasks_complete=tasks_complete,
    )

    result = module._read_existing_plan("http://127.0.0.1:5000")
    assert result["version"] == 7
    assert result["plan_ref"] == "plan-official-7"
    assert result["task_count"] == task_count
    assert "view=gantt" in result["url"]
    assert "plan-official-7" in result["url"]


@pytest.mark.parametrize(
    ("tasks", "task_count", "tasks_complete"),
    [
        ([{"task_id": 1}], 3, True),
        ([], 5001, False),
        ([{"task_id": i} for i in range(5000)], 5000, False),
        ([{"task_id": i} for i in range(5001)], 5000, False),
        ([], 0, True),
        ([{"task_id": 1}], True, True),
        ([{"task_id": 1}], 1, 1),
        (None, 1, True),
    ],
)
def test_read_existing_plan_rejects_inconsistent_or_empty_task_slice(
    monkeypatch: pytest.MonkeyPatch,
    tasks: Any,
    task_count: Any,
    tasks_complete: Any,
) -> None:
    module = _load_route_script_module()
    _install_workbench_stub(
        monkeypatch,
        module,
        tasks=tasks,
        task_count=task_count,
        tasks_complete=tasks_complete,
    )

    with pytest.raises(RuntimeError, match="工作台甘特接口返回的任务列表与计划任务总数不一致。"):
        module._read_existing_plan("http://127.0.0.1:5000")


def test_read_existing_plan_preserves_version_and_identity_guards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_route_script_module()
    _install_workbench_stub(
        monkeypatch,
        module,
        tasks=[{"task_id": i} for i in range(5000)],
        task_count=5001,
        tasks_complete=False,
    )
    with pytest.raises(RuntimeError, match="Latest service plan version does not match"):
        module._read_existing_plan("http://127.0.0.1:5000", expected_version=8)

    _install_workbench_stub(
        monkeypatch,
        module,
        workspace_plan={"plan_ref": "other-plan", "version": 7, "kind": "official"},
        tasks=[{"task_id": i} for i in range(5000)],
        task_count=5001,
        tasks_complete=False,
    )
    with pytest.raises(RuntimeError, match="Workbench returned a different plan identity"):
        module._read_existing_plan("http://127.0.0.1:5000")


def test_view_only_reports_authoritative_task_count_without_seeding_or_starting(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_route_script_module()
    _install_workbench_stub(
        monkeypatch,
        module,
        tasks=[{"task_id": i} for i in range(5000)],
        task_count=5001,
        tasks_complete=False,
    )
    monkeypatch.setattr(
        module,
        "_existing_server",
        lambda repo_root, db_path: {
            "host": "127.0.0.1",
            "port": 5000,
            "base_url": "http://127.0.0.1:5000",
            "started_now": False,
        },
    )

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("view-only must not start a server or seed/schedule sample data")

    monkeypatch.setattr(module, "_start_server_if_needed", forbidden)
    monkeypatch.setattr(module, "_seed_and_schedule", forbidden)

    rc = module.main(["view-only", "--no-open"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["ok"] is True
    assert payload["mode"] == "view-only"
    assert payload["server_started_now"] is False
    assert payload["version"] == 7
    assert payload["plan_ref"] == "plan-official-7"
    assert payload["task_count"] == 5001

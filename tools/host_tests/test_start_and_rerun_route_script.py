from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from core.infrastructure.safe_files import write_fixed_json, write_fixed_text
from web.bootstrap.launcher_health import HealthProbeResult

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = (
    _REPO_ROOT
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
    workspace_plan: Optional[Dict[str, Any]] = None,
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


def _write_runtime_files(
    repo_root: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 5055,
    db_path: str,
    instance_id: str = "inst-abc123",
    pid: int = 43210,
) -> None:
    logs_dir = repo_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    write_fixed_text(logs_dir / "aps_host.txt", host + "\n")
    write_fixed_text(logs_dir / "aps_port.txt", f"{port}\n")
    write_fixed_text(logs_dir / "aps_db_path.txt", db_path + "\n")
    write_fixed_json(
        logs_dir / "aps_runtime.json",
        {
            "contract_version": 1,
            "pid": pid,
            "host": host,
            "port": port,
            "runtime_dir": str(repo_root),
            "exe_path": str(repo_root / "app.py"),
            "owner": "tester",
            "instance_id": instance_id,
            "shutdown_path": "/system/runtime/shutdown",
            "shutdown_token": "tok-secret",
            "started_at": "2026-11-11T00:00:00Z",
            "db_path": db_path,
            "chrome_profile_dir": str(repo_root / "chrome"),
            "data_dirs": {
                "log_dir": str(logs_dir),
                "backup_dir": str(repo_root / "backups"),
                "excel_template_dir": str(repo_root / "templates_excel"),
            },
        },
    )


def test_verify_live_repo_instance_cross_checks_health_and_contract_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_route_script_module()
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    target_db = str((tmp_path / "isolated.db").resolve())

    assert module._verify_live_repo_instance(fake_repo, target_db) is None

    _write_runtime_files(fake_repo, db_path=target_db, instance_id="inst-good", pid=24680)
    health_payload: Dict[str, Any] = {
        "app": "aps",
        "status": "ok",
        "contract_version": 1,
        "pid": 24680,
        "instance_id": "inst-good",
        "db_path": target_db,
    }

    monkeypatch.setattr(
        module,
        "probe_runtime_health_result",
        lambda base_url, timeout_s=2.0: HealthProbeResult(
            ok=True,
            url=base_url + "/system/health",
            status=200,
            payload=dict(health_payload),
        ),
    )

    verified = module._verify_live_repo_instance(fake_repo, target_db)
    assert verified == {
        "host": "127.0.0.1",
        "port": 5055,
        "base_url": "http://127.0.0.1:5055",
        "instance_id": "inst-good",
    }

    health_payload["instance_id"] = "inst-other"
    with pytest.raises(RuntimeError, match="instance_id or pid does not match"):
        module._verify_live_repo_instance(fake_repo, target_db)

    health_payload["instance_id"] = "inst-good"
    health_payload["pid"] = 99999
    with pytest.raises(RuntimeError, match="instance_id or pid does not match"):
        module._verify_live_repo_instance(fake_repo, target_db)

    health_payload["pid"] = 24680
    health_payload["db_path"] = str((tmp_path / "other.db").resolve())
    with pytest.raises(RuntimeError, match="health db_path"):
        module._verify_live_repo_instance(fake_repo, target_db)

    health_payload["db_path"] = target_db
    write_fixed_text(fake_repo / "logs" / "aps_db_path.txt", str((tmp_path / "stale.db").resolve()) + "\n")
    with pytest.raises(RuntimeError, match="runtime DB file points to"):
        module._verify_live_repo_instance(fake_repo, target_db)

    _write_runtime_files(fake_repo, db_path=str((tmp_path / "wrong_contract.db").resolve()), instance_id="inst-good", pid=24680)
    write_fixed_text(fake_repo / "logs" / "aps_db_path.txt", target_db + "\n")
    with pytest.raises(RuntimeError, match=r"aps_runtime\.json db_path"):
        module._verify_live_repo_instance(fake_repo, target_db)


def test_verify_live_repo_instance_recovers_from_startup_publication_window_and_rejects_persistent_missing_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_route_script_module()
    fake_repo = tmp_path / "race_repo"
    logs_dir = fake_repo / "logs"
    logs_dir.mkdir(parents=True)
    target_db = str((tmp_path / "race_isolated.db").resolve())

    # Simulate publication window: triplet files written first, aps_runtime.json not written yet.
    write_fixed_text(logs_dir / "aps_host.txt", "127.0.0.1\n")
    write_fixed_text(logs_dir / "aps_port.txt", "5066\n")
    write_fixed_text(logs_dir / "aps_db_path.txt", target_db + "\n")

    publish_on_probe = {"enabled": True, "calls": 0}

    def fake_probe(base_url: str, timeout_s: float = 2.0) -> HealthProbeResult:
        publish_on_probe["calls"] += 1
        if publish_on_probe["enabled"] and not (logs_dir / "aps_runtime.json").exists():
            _write_runtime_files(
                fake_repo,
                host="127.0.0.1",
                port=5066,
                db_path=target_db,
                instance_id="inst-race-ok",
                pid=13579,
            )
        return HealthProbeResult(
            ok=True,
            url=base_url + "/system/health",
            status=200,
            payload={
                "app": "aps",
                "status": "ok",
                "contract_version": 1,
                "pid": 13579,
                "instance_id": "inst-race-ok",
                "db_path": target_db,
            },
        )

    monkeypatch.setattr(module, "probe_runtime_health_result", fake_probe)
    verified = module._verify_live_repo_instance(fake_repo, target_db)
    assert verified == {
        "host": "127.0.0.1",
        "port": 5066,
        "base_url": "http://127.0.0.1:5066",
        "instance_id": "inst-race-ok",
    }
    assert publish_on_probe["calls"] == 2

    # When aps_runtime.json stays missing after reread while endpoint is healthy, must fail closed.
    (logs_dir / "aps_runtime.json").unlink()
    publish_on_probe["enabled"] = False
    with pytest.raises(RuntimeError, match="missing or corrupted; refusing to reuse an unverified instance"):
        module._verify_live_repo_instance(fake_repo, target_db)


def test_assert_isolated_empty_demo_db_accepts_empty_and_rejects_business_rows(tmp_path: Path) -> None:
    module = _load_route_script_module()
    missing_db = tmp_path / "not_created_yet.db"
    module._assert_isolated_empty_demo_db(missing_db, before_server_start=True)
    assert not missing_db.exists()

    with pytest.raises(RuntimeError, match="file does not exist"):
        module._assert_isolated_empty_demo_db(missing_db, before_server_start=False)

    schema_sql = (_REPO_ROOT / "schema.sql").read_text(encoding="utf-8")
    empty_db = tmp_path / "empty_demo.db"
    with sqlite3.connect(str(empty_db)) as conn:
        conn.executescript(schema_sql)
        conn.execute(
            "INSERT INTO ScheduleConfig (config_key, config_value, description) "
            "VALUES ('algo_mode', 'fast', 'test')"
        )
        conn.execute(
            "INSERT INTO OperationLogs (log_level, module, action, target_type, target_id, detail, operator) "
            "VALUES ('INFO', 'system', 'startup', 'system', 'init', 'boot', 'system')"
        )
        conn.execute(
            "INSERT INTO SystemJobState (job_key, last_run_time, last_run_detail) "
            "VALUES ('auto_backup', '2026-11-11 00:00:00', 'ok')"
        )

    module._assert_isolated_empty_demo_db(empty_db, before_server_start=True)
    module._assert_isolated_empty_demo_db(empty_db, before_server_start=False)

    batches_db = tmp_path / "has_batches.db"
    with sqlite3.connect(str(batches_db)) as conn:
        conn.executescript(schema_sql)
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES ('P1', 'Part 1', 'no')")
        conn.execute(
            "INSERT INTO Batches (batch_id, part_no, quantity, due_date, priority, ready_status, status) "
            "VALUES ('B1', 'P1', 5, '2026-12-01', 'normal', 'yes', 'pending')"
        )
    with pytest.raises(RuntimeError, match=r"Refusing rerun on non-empty database .* table '(Batches|Parts)'"):
        module._assert_isolated_empty_demo_db(batches_db, before_server_start=True)

    hash_db = tmp_path / "isolated#prod.db"
    truncated_side_effect = tmp_path / "isolated"
    with sqlite3.connect(str(hash_db)) as conn:
        conn.executescript(schema_sql)
        conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES ('P1', 'Part 1', 'no')")
    with pytest.raises(RuntimeError, match=r"Refusing rerun on non-empty database .* table 'Parts'"):
        module._assert_isolated_empty_demo_db(hash_db, before_server_start=True)
    assert not truncated_side_effect.exists()

    reports_db = tmp_path / "has_reports.db"
    with sqlite3.connect(str(reports_db)) as conn:
        conn.executescript(schema_sql)
        op_ref, task_ref, plan_ref = "b" * 48, "c" * 48, "d" * 48
        conn.execute(
            "INSERT INTO WorkbenchPlanSourceRefs (ref, kind, source_key) VALUES (?, 'operation', 'op-1'), (?, 'official', '1')",
            (op_ref, plan_ref),
        )
        conn.execute(
            "INSERT INTO WorkbenchTaskRefs (ref, plan_ref, row_ref) VALUES (?, ?, 'row-1')",
            (task_ref, plan_ref),
        )
        conn.execute(
            "INSERT INTO WorkbenchProductionReports ("
            "report_ref, report_no, operation_ref, recorded_against_task_ref, "
            "recorded_against_plan_ref, source, recorded_at"
            ") VALUES (?, 'RPT-001', ?, ?, ?, 'manual', '2026-11-11T09:00:00')",
            ("a" * 48, op_ref, task_ref, plan_ref),
        )
    with pytest.raises(RuntimeError, match=r"Refusing rerun on non-empty database .* table 'Workbench.*' already contains data"):
        module._assert_isolated_empty_demo_db(reports_db, before_server_start=False)


def test_cli_rerun_requires_explicit_db_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_route_script_module()
    monkeypatch.setenv("APS_DB_PATH", "/tmp/should-not-be-used.db")
    with pytest.raises(SystemExit) as exc_info:
        module.main(["rerun", "--no-open"])
    assert exc_info.value.code == 2
    assert "rerun requires an explicit --db-path" in capsys.readouterr().err


def test_start_server_if_needed_preserves_live_locked_contracts_and_cleans_dead_lock_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_route_script_module()
    fake_repo = tmp_path / "start_repo"
    fake_repo.mkdir()
    target_db = str((tmp_path / "start_isolated.db").resolve())
    _write_runtime_files(fake_repo, host="127.0.0.1", port=5077, db_path=target_db, instance_id="inst-busy", pid=os.getpid())
    logs_dir = fake_repo / "logs"
    write_fixed_text(logs_dir / "aps_launch_error.txt", "stale error\n")
    contract_files = [
        logs_dir / "aps_host.txt",
        logs_dir / "aps_port.txt",
        logs_dir / "aps_db_path.txt",
        logs_dir / "aps_runtime.json",
    ]
    original_snapshots = {path.name: path.read_text(encoding="utf-8") for path in contract_files}

    health_ready = {"ok": False}

    def fake_probe(base_url: str, timeout_s: float = 2.0) -> HealthProbeResult:
        if not health_ready["ok"]:
            return HealthProbeResult(
                ok=False,
                url=base_url + "/system/health",
                status=None,
                payload=None,
                error="timed out",
            )
        return HealthProbeResult(
            ok=True,
            url=base_url + "/system/health",
            status=200,
            payload={
                "app": "aps",
                "status": "ok",
                "contract_version": 1,
                "pid": os.getpid(),
                "instance_id": "inst-fresh",
                "db_path": target_db,
            },
        )

    monkeypatch.setattr(module, "probe_runtime_health_result", fake_probe)
    monkeypatch.setattr(module, "_resolve_project_python", lambda _repo_root: Path(sys.executable))

    popen_calls = []

    class DummyProc:
        def poll(self) -> Optional[int]:
            return None

    def fake_popen(cmd: Any, **_kwargs: Any) -> DummyProc:
        popen_calls.append(cmd)
        for path in (*contract_files, logs_dir / "aps_launch_error.txt"):
            assert not path.exists(), f"expected stale file {path.name} to be removed before Popen"
        _write_runtime_files(
            fake_repo,
            host="127.0.0.1",
            port=5077,
            db_path=target_db,
            instance_id="inst-fresh",
            pid=os.getpid(),
        )
        health_ready["ok"] = True
        return DummyProc()

    monkeypatch.setattr(module.subprocess, "Popen", fake_popen)

    # 1. Live runtime lock (health probe timed out, but lock owner PID is alive): must refuse cleanup & spawn.
    write_fixed_text(
        logs_dir / "aps_runtime.lock",
        f"pid={os.getpid()}\nowner=tester\nexe_path={sys.executable}\ndb_path={target_db}\n",
    )
    with pytest.raises(RuntimeError, match="active or ambiguous APS runtime lock"):
        module._start_server_if_needed(fake_repo, "127.0.0.1", 5077, 5, target_db)
    assert popen_calls == []
    assert {path.name: path.read_text(encoding="utf-8") for path in contract_files} == original_snapshots

    # 2. Malformed/ambiguous runtime lock: also refuses cleanup & spawn.
    write_fixed_text(logs_dir / "aps_runtime.lock", "corrupted-lock-without-equals\n")
    with pytest.raises(RuntimeError, match="active or ambiguous APS runtime lock"):
        module._start_server_if_needed(fake_repo, "127.0.0.1", 5077, 5, target_db)
    assert popen_calls == []
    assert {path.name: path.read_text(encoding="utf-8") for path in contract_files} == original_snapshots

    # 3. Dead PID in runtime lock: cleans stale state files under mutation guard and starts new instance.
    dead_pid = next(
        pid for pid in (999999, 888888, 777777, 654321) if not module.is_runtime_lock_active({"pid": pid})
    )
    write_fixed_text(
        logs_dir / "aps_runtime.lock",
        f"pid={dead_pid}\nowner=tester\ndb_path={target_db}\n",
    )
    started = module._start_server_if_needed(fake_repo, "127.0.0.1", 5077, 5, target_db)
    assert len(popen_calls) == 1
    assert started == {
        "host": "127.0.0.1",
        "port": 5077,
        "base_url": "http://127.0.0.1:5077",
        "instance_id": "inst-fresh",
        "started_now": True,
    }

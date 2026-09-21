"""Runner mode safety and current workbench reads, without a real server or DB."""

import importlib.util
import io
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from tests._support.paths import REPO_ROOT_STR


@pytest.fixture
def runner(tmp_path, monkeypatch):
    path = Path(REPO_ROOT_STR) / "scripts/run_start_and_rerun_route.py"
    spec = importlib.util.spec_from_file_location("route_runner_modes", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "_find_repo_root", lambda: tmp_path)
    monkeypatch.delenv("APS_DB_PATH", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected server startup, DB mutation, browser or network access")

    monkeypatch.setattr(mod.subprocess, "Popen", forbidden)
    monkeypatch.setattr(mod, "_seed_and_schedule", forbidden)
    monkeypatch.setattr(mod, "_open_url", forbidden)
    monkeypatch.setattr(mod.urllib.request, "urlopen", forbidden)
    return mod


def _endpoint():
    return {"host": "127.0.0.1", "port": 5721, "base_url": "http://127.0.0.1:5721", "started_now": False}


def _probe(runner, tmp_path, monkeypatch, endpoint=None, mismatch=None):
    class Probe:
        def resolve_healthy_endpoint(self, runtime_dir, timeout):
            return endpoint

        def read_runtime_host_port(self, runtime_dir):
            return ("127.0.0.1", 9999 if mismatch == "endpoint" else 5721)

        def read_runtime_db_path(self, runtime_dir):
            return str(tmp_path / ("other.db" if mismatch == "db" else "db/aps.db"))

        def build_base_url(self, host, port):
            return f"http://{host}:{port}"

    monkeypatch.setattr(runner, "_runtime_probe", lambda root: Probe())


def _responses(runner, monkeypatch, plans=None, workspace_changes=None):
    official = {"version": 17, "kind": "official", "plan_ref": "plan-existing",
                "capabilities": {"view": True}}
    workspace = {"plan": dict(official), "tasks": [{"task_ref": "existing-task"}],
                 "task_count": 1, "tasks_complete": True}
    workspace.update(workspace_changes or {})
    catalog = {"plans": [official] if plans is None else plans}
    responses = [catalog, workspace]
    calls = []

    def urlopen(url, timeout):
        calls.append(url)
        assert timeout == 10
        return io.BytesIO(json.dumps({"ok": True, "data": responses[len(calls) - 1]}).encode())

    monkeypatch.setattr(runner.urllib.request, "urlopen", urlopen)
    return calls


def test_omitted_command_only_starts(runner, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(runner, "_start_server_if_needed", lambda **kwargs: calls.append(kwargs) or _endpoint())
    assert runner.main(["--no-open"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "start-only"
    assert result["url"] == "http://127.0.0.1:5721/"
    assert len(calls) == 1


@pytest.mark.parametrize("args", [["rerun"], ["rerun", "--db-path", "   "]])
@pytest.mark.parametrize("use_env", [False, True])
def test_rerun_requires_explicit_target_before_any_side_effect(runner, monkeypatch, args, use_env):
    if use_env:
        monkeypatch.setenv("APS_DB_PATH", "/must-not-be-used.db")
    monkeypatch.setattr(runner, "_find_repo_root", lambda: pytest.fail("Must reject before resolving the repo"))
    with pytest.raises(SystemExit) as exc:
        runner.main(args)
    assert exc.value.code == 2


def test_view_only_reads_existing_plan_and_actual_endpoint(runner, tmp_path, monkeypatch, capsys):
    _probe(runner, tmp_path, monkeypatch, endpoint=_endpoint())
    calls = _responses(runner, monkeypatch)
    assert runner.main(["view-only", "--host", "wrong-host", "--port", "9999", "--no-open"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["mode"] == "view-only"
    assert result["server_started_now"] is False
    assert (result["version"], result["plan_ref"], result["task_count"]) == (17, "plan-existing", 1)
    assert calls == ["http://127.0.0.1:5721/api/workbench/v1/plans?collection=history&size=1",
                     "http://127.0.0.1:5721/api/workbench/v1/plans/plan-existing/workspace"]
    url = urlsplit(result["url"])
    assert url.netloc == "127.0.0.1:5721" and url.path == "/workbench"
    assert json.loads(parse_qs(url.query)["nav"][0]) == {
        "version": 1, "view": "gantt", "context": {"plan_ref": "plan-existing"}}


def test_view_only_without_service_does_not_start(runner, tmp_path, monkeypatch):
    _probe(runner, tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="No healthy APS instance"):
        runner.main(["view-only", "--no-open"])


@pytest.mark.parametrize("mismatch", ["db", "endpoint"])
def test_view_only_refuses_unmatched_instance(runner, tmp_path, monkeypatch, mismatch):
    _probe(runner, tmp_path, monkeypatch, endpoint=_endpoint(), mismatch=mismatch)
    with pytest.raises(RuntimeError, match="refusing to reuse"):
        runner.main(["view-only", "--no-open"])


@pytest.mark.parametrize("plans", [[], [{"kind": "candidate", "version": 17}],
                                  [{"kind": "official", "version": 17, "capabilities": {"view": False}}]])
def test_empty_or_unavailable_official_plan_never_substitutes(runner, monkeypatch, plans):
    calls = _responses(runner, monkeypatch, plans=plans)
    with pytest.raises(RuntimeError):
        runner._read_existing_plan("http://example.test")
    assert len(calls) == 1


def test_rerun_does_not_verify_a_different_latest_version(runner, monkeypatch):
    calls = _responses(runner, monkeypatch)
    with pytest.raises(RuntimeError, match="version does not match"):
        runner._read_existing_plan("http://example.test", expected_version=16)
    assert len(calls) == 1


@pytest.mark.parametrize("changes", [{"plan": {"version": 17, "plan_ref": "wrong-plan", "kind": "official"}},
                                     {"tasks_complete": False}, {"task_count": 2}])
def test_workspace_identity_or_incomplete_tasks_fail(runner, monkeypatch, changes):
    _responses(runner, monkeypatch, workspace_changes=changes)
    with pytest.raises(RuntimeError):
        runner._read_existing_plan("http://example.test", expected_version=17)


def test_cleanup_matches_literal_prefix_and_schedule_relationship(runner):
    # Real SQLite executes every cleanup statement; no seed/server/DB mocks.
    names = ("ROUTEDEMO_REAL", "ROUTEDEMOX_REAL", "ROUTEDEMO", "routedemo_REAL", "BUSINESS_REAL")
    survivors = set(names[1:])
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        for table, column in (("Batches", "batch_id"), ("Parts", "part_no"),
                              ("Operators", "operator_id"), ("Machines", "machine_id"),
                              ("Suppliers", "supplier_id"), ("OpTypes", "op_type_id")):
            conn.execute(f"CREATE TABLE {table} ({column} TEXT PRIMARY KEY)")
            conn.executemany(f"INSERT INTO {table} VALUES (?)", [(name,) for name in names])
        conn.executescript("""
            CREATE TABLE BatchOperations (id INTEGER PRIMARY KEY, batch_id TEXT REFERENCES Batches(batch_id));
            CREATE TABLE Schedule (id INTEGER PRIMARY KEY, op_id INTEGER REFERENCES BatchOperations(id));
            CREATE TABLE ExternalGroups (group_id TEXT, part_no TEXT REFERENCES Parts(part_no));
            CREATE TABLE PartOperations (id INTEGER, part_no TEXT REFERENCES Parts(part_no));
            CREATE TABLE OperatorMachine (operator_id TEXT REFERENCES Operators(operator_id),
                                          machine_id TEXT REFERENCES Machines(machine_id));
        """)
        for index, name in enumerate(names, 1):
            conn.execute("INSERT INTO BatchOperations VALUES (?, ?)", (index, name))
            conn.execute("INSERT INTO Schedule VALUES (?, ?)", (index, index))
            conn.execute("INSERT INTO ExternalGroups VALUES (?, ?)", (f"GROUP_{index}", name))
            conn.execute("INSERT INTO PartOperations VALUES (?, ?)", (index, name))
            conn.execute("INSERT INTO OperatorMachine VALUES (?, ?)", (name, name))
        # A second schedule row for a demo operation must also be removed.
        conn.execute("INSERT INTO Schedule VALUES (99, 1)")
        # Both sides of resource links obey the literal prefix rule.
        conn.execute("INSERT INTO OperatorMachine VALUES (?, ?)", (names[0], names[4]))
        conn.execute("INSERT INTO OperatorMachine VALUES (?, ?)", (names[4], names[0]))
        conn.execute("INSERT INTO OperatorMachine VALUES (?, ?)", (names[1], names[4]))
        conn.execute("INSERT INTO OperatorMachine VALUES (?, ?)", (names[4], names[1]))
        conn.commit()

        runner._clear_route_demo_rows(conn)

        for table, column in (("Batches", "batch_id"), ("BatchOperations", "batch_id"),
                              ("Parts", "part_no"), ("ExternalGroups", "part_no"), ("PartOperations", "part_no"),
                              ("Operators", "operator_id"), ("Machines", "machine_id"),
                              ("Suppliers", "supplier_id"), ("OpTypes", "op_type_id")):
            assert {row[0] for row in conn.execute(f"SELECT {column} FROM {table}")} == survivors, table
        assert set(conn.execute("SELECT id, op_id FROM Schedule")) == {(2, 2), (3, 3), (4, 4), (5, 5)}
        assert set(conn.execute("SELECT operator_id, machine_id FROM OperatorMachine")) == (
            {(name, name) for name in survivors} | {(names[1], names[4]), (names[4], names[1])})
        assert not list(conn.execute("PRAGMA foreign_key_check"))
        # A repeated cleanup is still confined to the same now-empty scope.
        changes = conn.total_changes
        runner._clear_route_demo_rows(conn)
        assert conn.total_changes == changes

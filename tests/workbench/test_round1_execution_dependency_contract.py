"""R1-D: one neutral projection owner and live scheduler/workbench boundaries."""

import json
import subprocess
import sys

import pytest

from core.services.execution import legacy as legacy_owner
from core.services.execution import projection as projection_owner
from core.services.execution import quality as quality_owner
from core.services.execution import totals as totals_owner
from core.services.execution.ledger_reader import ExecutionLedgerReader
from core.services.scheduler.execution.execution_ledger_adapter import ledger_read_snapshot
from core.services.scheduler.execution.execution_plan_identity import current_execution_plan
from core.services.workbench import execution_ledger_legacy as legacy_adapter
from core.services.workbench import execution_ledger_projection as projection_adapter
from core.services.workbench import execution_ledger_quality as quality_adapter
from core.services.workbench import execution_ledger_totals as totals_adapter
from core.services.workbench.execution_ledger import ExecutionLedgerService
from tests._support.dependency_boundaries import assert_no_import_prefixes
from tests._support.paths import REPO_ROOT
from tests.workbench.test_execution_ledger_support import NOW, all_rows
from tests.workbench.test_execution_ledger_support import ledger_case as ledger_fixture
from tests.workbench.test_scheduler_execution_ledger_support import read_facts


@pytest.mark.parametrize("old,owner,symbols", [
    (projection_adapter, projection_owner, ("project_execution", "report_dto")),
    (legacy_adapter, legacy_owner, ("LegacyEvidence", "legacy_evidence")),
    (quality_adapter, quality_owner, ("INVALID_CODES", "classify_quality", "gap", "operation_target")),
    (totals_adapter, totals_owner, ("ReportTotals", "merge_legacy_totals", "quantity_consistency", "report_totals")),
])
def test_old_helper_paths_reexport_identical_neutral_objects(old, owner, symbols):
    for symbol in symbols:
        assert getattr(old, symbol) is getattr(owner, symbol)


def test_workbench_inherits_the_same_fact_and_snapshot_methods():
    assert issubclass(ExecutionLedgerService, ExecutionLedgerReader)
    for method in ("load", "read_snapshot", "_current_plan", "project_operations"):
        assert getattr(ExecutionLedgerService, method) is getattr(ExecutionLedgerReader, method)


@pytest.mark.parametrize("module,banned", [
    ("core.services.execution.ledger_reader", ("core.services.scheduler", "core.services.workbench", "core.services.report")),
    ("core.services.scheduler.execution.execution_ledger_adapter", ("core.services.workbench", "core.services.report")),
])
def test_cold_runtime_imports_do_not_load_reverse_service_dependencies(module, banned):
    script = f"import importlib, sys\nimportlib.import_module({module!r})\n"
    script += f"banned = {banned!r}\n"
    script += "loaded = [name for name in sys.modules if any(name == p or name.startswith(p + '.') for p in banned)]\n"
    script += "assert not loaded, loaded\n"
    completed = subprocess.run([sys.executable, "-c", script], cwd=str(REPO_ROOT),
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_neutral_source_has_no_reverse_imports_even_inside_functions():
    paths = sorted((REPO_ROOT / "core/services/execution").glob("*.py"))
    assert len(paths) == 6
    for path in paths:
        assert_no_import_prefixes(path, ("core.services.scheduler", "core.services.workbench", "core.services.report"))
        source = path.read_text(encoding="utf-8")
        assert "TYPE_CHECKING" not in source and "import_module" not in source and "__import__" not in source


@pytest.mark.parametrize("provider", [None, False, ""])
def test_neutral_reader_rejects_invalid_plan_provider(provider):
    with pytest.raises(TypeError, match="current-plan provider must be callable"):
        ExecutionLedgerReader(None, current_plan_provider=provider)


@pytest.mark.parametrize("mode", ["empty", "legacy_unknown", "partial", "complete", "corrected"])
def test_neutral_and_original_workbench_consumers_return_identical_stored_facts(ledger_case, mode):
    case = ledger_case
    if mode == "legacy_unknown":
        case.event(case.op_id, "start")
        case.event(case.op_id, "finish")
    case.install()
    task = case.task(1, case.op_id)
    if mode in ("partial", "complete", "corrected"):
        quantity = 4 if mode == "partial" else 10
        row = case.command("create", task, case.values(quantity))["data"]["rows"][0]
        if mode == "corrected":
            case.command("correct", row["report_ref"], {"completed_quantity": 3,
                "original_revision_ref": row["revision_ref"], "reason": "Verified count"})
    operation_ref = case.ledger.get_task(task).operation_ref
    before = all_rows(case.conn)
    case.conn.execute("PRAGMA query_only=ON")
    calls = []

    def plan_provider(conn):
        assert conn is case.conn and conn.in_transaction
        calls.append(conn)
        return current_execution_plan(conn)

    reader = ExecutionLedgerReader(case.conn, current_plan_provider=plan_provider, clock=lambda: NOW)
    actual = reader.project_operations([operation_ref], comparison_plan_ref=case.plan_ref(1))
    expected = case.ledger.project_operations([operation_ref], comparison_plan_ref=case.plan_ref(1))
    assert actual == expected
    assert calls == [case.conn]
    assert actual[0].target_quantity == 10 and actual[0].target_basis == "batch"
    if mode == "legacy_unknown":
        assert actual[0].completion_basis == "legacy_finish_event"
        assert actual[0].remaining_quantity is None and actual[0].unknown_record_count == 1
    assert all_rows(case.conn) == before


def test_scheduler_constructs_only_neutral_reader_and_preserves_all_tables(ledger_case, monkeypatch):
    case = ledger_case
    case.install()
    case.command("create", case.task(1, case.op_id), case.values(4))
    before = all_rows(case.conn)

    def forbidden(*args, **kwargs):
        raise AssertionError("Scheduler must not construct a workbench service")

    monkeypatch.setattr(ExecutionLedgerService, "__init__", forbidden)
    case.conn.execute("PRAGMA query_only=ON")
    with ledger_read_snapshot(case.conn) as reader:
        assert type(reader) is ExecutionLedgerReader
        assert reader.current_plan_provider is current_execution_plan
    fact = read_facts(case.conn)[case.op_id]
    assert fact.ledger_execution_state == "partial" and fact.remaining_quantity == 6
    assert "execution_ledger_remaining_plan_unavailable" in fact.execution_protection_reasons
    assert all_rows(case.conn) == before


def test_workbench_alone_issues_write_contexts(ledger_case):
    case = ledger_case
    case.install()
    task = case.task(1, case.op_id)
    case.command("create", task, case.values(4))
    operation_ref = case.ledger.get_task(task).operation_ref
    issued = []

    def issue(ref, actions, snapshot):
        issued.append((ref, actions, snapshot))
        return {"write_token": "bound-context", "capabilities": actions}

    service = ExecutionLedgerService(case.conn, clock=lambda: NOW, context_factory=issue)
    before = all_rows(case.conn)
    with service.read_snapshot():
        facts = service.load([operation_ref])
        closed = service.project_loaded(facts, contexts=False)
        assert not issued
        opened = service.project_loaded(facts)
    assert len(issued) == 2
    assert opened[0].write_context["capabilities"] == ["create"]
    assert opened[0].reports[0].write_context["capabilities"] == ["supplement", "correct"]
    assert closed[0].write_context["capabilities"] == []
    assert closed[0].reports[0].write_context["capabilities"] == []
    assert all_rows(case.conn) == before


def test_real_import_graph_has_no_execution_service_cycle():
    completed = subprocess.run([sys.executable, "-m", "tools.scan_import_cycles", "--include-tests", "--json"],
                               cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert not report["parse_errors"]
    owned = {"core/services/execution", "core/services/workbench", "core/services/scheduler", "core/services/report"}
    for key in ("hard_dir_cycles", "delayed_dir_cycles"):
        cycles = [row for row in report[key] if owned & set(row["members"])]
        assert not cycles, cycles
    prefixes = ("core.services.execution.", "core.services.workbench.execution_ledger",
                "core.services.scheduler.execution.execution_ledger")
    assert not [row for row in report["hard_file_cycles"] if any(name.startswith(prefixes) for name in row)]

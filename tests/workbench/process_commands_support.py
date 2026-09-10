"""Real SQLite workflow/receipt fixtures, independent full-row preservation oracles."""

from __future__ import annotations

import cProfile
import hashlib
import io
import json
import pstats
import sqlite3
import time
from collections import Counter
from pathlib import Path

import pytest

from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_process_workflow_schema import install_process_workflow
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process_mutations import WorkbenchProcessMutationService
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from tests.workbench.process_query_support import ref_for, seed_process
from tests.workbench.process_route_support import all_table_snapshot

PART = "PROC-001"
KEY = "process-command-00000001"


@pytest.fixture(name="stage_conn")
def stage_database(schema_conn):
    with TransactionManager(schema_conn).transaction(begin_immediate=True):
        install_process_workflow(schema_conn)
    seed_process(schema_conn)
    schema_conn.execute("ALTER TABLE PartOperations ADD COLUMN private_legacy TEXT")
    schema_conn.execute("UPDATE PartOperations SET private_legacy=' keep hidden ',created_at='2000-01-01 00:00:00'")
    schema_conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES ('PROC-S2','second',NULL,4.5)")
    schema_conn.execute("INSERT INTO WorkbenchSupplierOpTypes VALUES ('PROC-S2','PROC-EX')")
    schema_conn.execute("""INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,setup_hours,unit_hours)
        VALUES ('STAGE-OLD','PROC-B',10,'historical','internal',7,8)""")
    key = schema_conn.execute("SELECT id FROM BatchOperations WHERE op_code='STAGE-OLD'").fetchone()[0]
    schema_conn.execute("INSERT INTO Schedule(op_id,start_time,end_time) VALUES (?,?,?)", (key, "2026-10-01 08:00:00", "2026-10-01 09:00:00"))
    schema_conn.commit()
    return schema_conn


def identity_for(conn, part_no=PART):
    return WorkbenchIdentityRepository(conn).find_active("part", part_no)


def op_rows(conn, part_no=PART):
    return {row["seq"]: dict(row) for row in conn.execute("SELECT * FROM PartOperations WHERE part_no=? ORDER BY seq", (part_no,))}


def group_rows(conn, part_no=PART):
    return {row["group_id"]: dict(row) for row in conn.execute("SELECT * FROM ExternalGroups WHERE part_no=? ORDER BY group_id", (part_no,))}


def op_ref(conn, seq=10, part_no=PART):
    row = conn.execute("SELECT id FROM PartOperations WHERE part_no=? AND seq=?", (part_no, seq)).fetchone()
    assert row is not None
    return ref_for(conn, "template_operation", str(row[0]))


def route_input(conn, text=None, part_no=PART):
    raw = conn.execute("SELECT route_raw FROM Parts WHERE part_no=?", (part_no,)).fetchone()[0] if text is None else text
    return {"route": {"mode": "text", "route_raw": raw}, "discard_group_refs": []}


def source_input(conn, part_no=PART):
    rows = active_rows_with_refs(conn, part_no)
    types = _fixture_refs(conn, "op_type", [row["op_type_id"] for row in rows if row["op_type_id"]])
    suppliers = _fixture_refs(conn, "supplier", [row["supplier_id"] for row in rows if row["supplier_id"]])
    return {"operations": [{"ref": row["ref"], "source": row["source"],
                            "op_type_ref": types[row["op_type_id"]] if row["op_type_id"] else None,
                            "supplier_ref": suppliers[row["supplier_id"]] if row["supplier_id"] else None,
                            "confirmed": True} for row in rows],
            "discard_group_refs": []}


def hours_input(conn, part_no=PART):
    operations, active_groups = [], set()
    for row in active_rows_with_refs(conn, part_no):
        fields = {"setup_hours": row["setup_hours"], "unit_hours": row["unit_hours"]} if row["source"] == "internal" else {"external_days": row["ext_days"]}
        operations.append({"ref": row["ref"], **fields})
        active_groups.add(row["ext_group_id"])
    rows = {key: row for key, row in group_rows(conn, part_no).items() if key in active_groups and row["merge_mode"] == "merged"}
    refs = _fixture_refs(conn, "template_external_group", rows)
    groups = [{"ref": refs[key], "total_days": row["total_days"]} for key, row in rows.items()]
    return {"operations": operations, "groups": groups, "confirm_zero_unit_hours": True}


def active_rows_with_refs(conn, part_no):
    rows = conn.execute("""SELECT o.*,r.ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
        ON r.kind='template_operation' AND r.active=1 AND r.entity_key=CAST(o.id AS TEXT)
        WHERE o.part_no=? AND o.status='active' ORDER BY o.seq""", (part_no,)).fetchall()
    assert all(row["ref"] is not None for row in rows)
    return rows


def _fixture_refs(conn, kind, keys):
    keys = set(keys)
    refs = WorkbenchIdentityRepository(conn).active_map(kind, keys)
    assert set(refs) == keys
    return {key: value.ref for key, value in refs.items()}


def run_stage(conn, action, payload, *, key=KEY, identity=None, command=None, guard=None):
    service = WorkbenchProcessMutationService(conn)
    identity = identity_for(conn) if identity is None else identity
    return (command or WorkbenchCommandService(conn)).execute(
        request_key=key, action="process." + action, context_ref=identity.ref,
        normalized_input=service.normalize(action, payload), guard=guard or (lambda: identity),
        mutate=lambda checked: service.apply(action, payload, checked))


def prepare_stages(conn, *, source=True):
    run_stage(conn, "route_confirm", route_input(conn), key=KEY + "-route")
    if source:
        run_stage(conn, "source_confirm", source_input(conn), key=KEY + "-source")


def storage(conn):
    return all_table_snapshot(conn)


def downstream(conn):
    return {table: tuple(tuple(row) for row in conn.execute('SELECT * FROM "' + table + '" ORDER BY rowid'))
            for table in ("Batches", "BatchOperations", "Schedule")}


class ProcessProfileConnection(sqlite3.Connection):
    """Count submitted statements separately from SQLite's executed VM steps."""

    sql_counts = None

    def execute(self, sql, parameters=()):
        if self.sql_counts is not None:
            self.sql_counts[sql] += 1
        return super().execute(sql, parameters)

    def executemany(self, sql, parameters):
        def counted():
            for row in parameters:
                if self.sql_counts is not None:
                    self.sql_counts[sql] += 1
                yield row
        return super().executemany(sql, counted())


def profile_phase(conn, output, name, callback):
    """Return the real result plus reproducible query/VM/profile evidence."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    profiler, ticks = cProfile.Profile(), [0]

    def progress():
        ticks[0] += 1
        return 0

    conn.sql_counts = Counter()
    conn.set_progress_handler(progress, 1000)
    before = conn.total_changes
    start = time.perf_counter()
    profiler.enable()
    try:
        result = callback()
    finally:
        profiler.disable()
        elapsed = time.perf_counter() - start
        conn.set_progress_handler(None, 0)
        statements = conn.sql_counts
        conn.sql_counts = None
        profiler.dump_stats(str(output / (name + ".prof")))
        text = io.StringIO()
        pstats.Stats(profiler, stream=text).sort_stats("cumulative").print_stats(45)
        (output / (name + ".txt")).write_text(text.getvalue(), encoding="utf-8")
        record = {"phase": name, "seconds": elapsed, "sqlite_vm_steps_lower_bound": ticks[0] * 1000,
                  "sqlite_vm_step_quantum": 1000, "submitted_statements": sum(statements.values()),
                  "total_changes": conn.total_changes - before,
                  "sql": [{"sql": sql, "calls": count} for sql, count in statements.most_common()]}
        (output / (name + ".json")).write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({key: value for key, value in record.items() if key != "sql"}), flush=True)
    return result, record


def seed_stage_scale(conn, count):
    conn.execute("INSERT INTO Parts(part_no,part_name,route_raw,route_parsed) VALUES ('SCALE','scale','existing route','yes')")
    conn.executemany("""INSERT INTO PartOperations(part_no,seq,op_type_name,op_type_id,source,setup_hours,unit_hours)
        VALUES ('SCALE',?,'车削','PROC-IN','internal',0,1)""", [(seq,) for seq in range(1, count + 1)])
    conn.commit()


def scale_inputs(conn):
    """Match the original 10000-row test's payload without using op_ref in a loop."""
    refs = [row[0] for row in conn.execute("""SELECT r.ref FROM PartOperations o JOIN WorkbenchEntityRefs r
        ON r.kind='template_operation' AND r.active=1 AND r.entity_key=CAST(o.id AS TEXT)
        WHERE o.part_no='SCALE' ORDER BY o.seq""")]
    type_ref = ref_for(conn, "op_type", "PROC-IN")
    source = {"operations": [{"ref": ref, "source": "internal", "op_type_ref": type_ref,
                              "supplier_ref": None, "confirmed": True} for ref in refs]}
    hours = {"operations": [{"ref": ref, "setup_hours": 0, "unit_hours": 2} for ref in refs],
             "groups": [], "confirm_zero_unit_hours": False}
    return source, hours


def profile_input_helpers(count, output):
    """Frozen old helper algorithm vs bulk helpers on the exact same live fixture."""
    conn = sqlite3.connect(":memory:", factory=ProcessProfileConnection)
    conn.row_factory = sqlite3.Row
    conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
    stage_database.__wrapped__(conn)
    seed_stage_scale(conn, count)

    def legacy_source():
        result = []
        for seq, row in op_rows(conn, "SCALE").items():
            key = op_rows(conn, "SCALE")[seq]["id"]
            result.append({"ref": ref_for(conn, "template_operation", str(key)), "source": row["source"],
                           "op_type_ref": ref_for(conn, "op_type", row["op_type_id"]), "supplier_ref": None, "confirmed": True})
        return {"operations": result, "discard_group_refs": []}

    def legacy_hours():
        result = []
        for seq, row in op_rows(conn, "SCALE").items():
            key = op_rows(conn, "SCALE")[seq]["id"]
            result.append({"ref": ref_for(conn, "template_operation", str(key)), "setup_hours": row["setup_hours"], "unit_hours": row["unit_hours"]})
        return {"operations": result, "groups": [], "confirm_zero_unit_hours": True}

    records, expected = [], {}
    for name, callback in (("legacy_source", legacy_source), ("bulk_source", lambda: source_input(conn, "SCALE")),
                           ("legacy_hours", legacy_hours), ("bulk_hours", lambda: hours_input(conn, "SCALE"))):
        result, record = profile_phase(conn, output, name, callback)
        stage = name.split("_")[1]
        if stage in expected:
            assert result == expected[stage]
        expected[stage] = result
        records.append(record)
    conn.close()
    return {"count": count, "complete_payloads_equal": True, "phases": records}


def _profile_command(conn, action, normalized, suffix=""):
    service = WorkbenchProcessMutationService(conn)
    identity = identity_for(conn, "SCALE")
    return WorkbenchCommandService(conn).execute(
        request_key=KEY + "-" + action + suffix, action="process." + action, context_ref=identity.ref,
        normalized_input=normalized, guard=lambda: identity,
        mutate=lambda checked: service.apply(action, normalized, checked))


def _profile_route(conn, output, count, measure):
    from core.services.process.workflow_state import record_confirmation

    if count <= 2000:
        payload = {"route": {"mode": "rows", "rows": [{"seq": seq, "op_type_name": "车削"} for seq in range(1, count + 1)]}}
        normalized = measure("normalize_route", lambda: WorkbenchProcessMutationService.normalize("route_confirm", payload))
        measure("route_transaction", lambda: _profile_command(conn, "route_confirm", normalized))
    else:
        # The route API still rejects >2000 inputs. Do not fabricate a route API timing.
        def existing_route():
            with TransactionManager(conn).transaction(begin_immediate=True):
                return record_confirmation(conn, "SCALE", "route")
        measure("fixture_existing_route_confirmation", existing_route)


def profile_stage_scale(count, output):
    from core.infrastructure.migration_state import CURRENT_SCHEMA_VERSION, ensure_schema_version, get_schema_version
    from core.infrastructure.workbench_plan_identity_schema import workbench_plan_identity_contract_issues
    from core.infrastructure.workbench_process_schema import workbench_process_contract_issues
    from core.services.process.workflow_state import read_workflow

    conn = sqlite3.connect(":memory:", factory=ProcessProfileConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    records = []

    def measure(name, callback):
        result, record = profile_phase(conn, output, name, callback)
        if isinstance(result, dict) and "result" in result:
            record["result"] = result["result"]
        records.append(record)
        return result

    def initialize_version():
        with TransactionManager(conn).transaction(begin_immediate=True):
            ensure_schema_version(conn)
            assert get_schema_version(conn) == CURRENT_SCHEMA_VERSION
        return get_schema_version(conn)

    try:
        schema = (Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8")
        measure("schema_setup", lambda: conn.executescript(schema))
        version = measure("schema_version_bootstrap", initialize_version)
        measure("fixture_base", lambda: stage_database.__wrapped__(conn))
        assert workbench_process_contract_issues(conn) == []
        assert workbench_plan_identity_contract_issues(conn) == []
        triggers = {row[0]: {"sql": row[1], "sha256": hashlib.sha256(row[1].encode("utf-8")).hexdigest()}
                    for row in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND name GLOB 'wb_ref_template_*' ORDER BY name")}
        manifest = Path(output) / "installed_process_triggers.json"
        manifest.write_text(json.dumps(triggers, indent=2), encoding="utf-8")
        measure("fixture_scale_seed", lambda: seed_stage_scale(conn, count))
        source, hours = measure("fixture_payload", lambda: scale_inputs(conn))
        _profile_route(conn, output, count, measure)
        normalized_source = measure("normalize_source", lambda: WorkbenchProcessMutationService.normalize("source_confirm", source))
        measure("source_preview", lambda: WorkbenchProcessMutationService(conn).affected_groups("source_confirm", normalized_source, identity_for(conn, "SCALE")))
        measure("source_transaction", lambda: _profile_command(conn, "source_confirm", normalized_source))
        measure("source_unchanged_transaction", lambda: _profile_command(conn, "source_confirm", normalized_source, "-unchanged"))
        normalized_hours = measure("normalize_hours", lambda: WorkbenchProcessMutationService.normalize("hours_confirm", hours))
        measure("hours_transaction", lambda: _profile_command(conn, "hours_confirm", normalized_hours))
        measure("hours_unchanged_transaction", lambda: _profile_command(conn, "hours_confirm", normalized_hours, "-unchanged"))
        assert conn.execute("SELECT COUNT(*) FROM PartOperations WHERE part_no='SCALE' AND unit_hours=2").fetchone()[0] == count
        assert read_workflow(conn, "SCALE")["ready"]
        return {"count": count, "schema_version": version, "plan_identity_contract_valid": True,
                "process_trigger_contract_valid": True,
                "trigger_manifest": str(manifest.resolve()), "phases": records}
    finally:
        conn.close()


def profile_source_hashes():
    root = Path(__file__).resolve().parents[2]
    files = [Path(__file__), root / "schema.sql", root / "core/infrastructure/workbench_metadata_schema.py",
             root / "core/infrastructure/workbench_process_schema.py", root / "core/services/process/workflow_state.py",
             root / "core/models/workbench_process_commands.py", root / "core/infrastructure/migration_state.py",
             root / "core/infrastructure/migrations/__init__.py", root / "core/infrastructure/migrations/v24.py",
             root / "core/infrastructure/workbench_plan_identity_schema.py"]
    files.extend((root / "core/services/workbench").glob("process*.py"))
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def profile_noop_confirmations(count, output):
    """Same-connection ABBA of the old unconditional confirmation tail and no-op."""
    from core.services.process.workflow_state import record_confirmation

    conn = sqlite3.connect(":memory:", factory=ProcessProfileConnection)
    conn.row_factory = sqlite3.Row
    conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
    stage_database.__wrapped__(conn)
    seed_stage_scale(conn, count)
    with TransactionManager(conn).transaction(begin_immediate=True):
        record_confirmation(conn, "SCALE", "route")
    source, hours = scale_inputs(conn)
    _profile_command(conn, "source_confirm", source)
    _profile_command(conn, "hours_confirm", hours)
    service = WorkbenchProcessMutationService(conn)
    identity = identity_for(conn, "SCALE")

    def state():
        _, tables = all_table_snapshot(conn)
        tables.pop("WorkbenchCommandReceipts")
        return hashlib.sha256(json.dumps(tables, sort_keys=True).encode("utf-8")).hexdigest()

    before, phases = state(), []
    for action, payload in (("source_confirm", source), ("hours_confirm", hours)):
        normalized = service.normalize(action, payload)
        for index, legacy in enumerate((True, False, False, True)):
            def mutate(checked):
                outcome = service.apply(action, normalized, checked)
                assert outcome.result == "unchanged"
                if legacy:
                    # Reproduce only the removed tail, using the real confirmation service.
                    record_confirmation(conn, "SCALE", action[:-len("_confirm")])
                return outcome

            name = action + "_" + str(index) + ("_legacy_tail" if legacy else "_noop")

            def execute():
                return WorkbenchCommandService(conn).execute(
                    request_key=KEY + "-" + name, action="process." + action, context_ref=identity.ref,
                    normalized_input=normalized, guard=lambda: identity, mutate=mutate)

            result, record = profile_phase(conn, output, name, execute)
            record["result"] = result["result"]
            assert state() == before
            phases.append(record)
    conn.close()
    return {"count": count, "all_nonreceipt_rows_unchanged": True, "state_sha256": before, "phases": phases}


def profile_identity_predicates(count, output):
    """Compare equivalent predicate statements in one isolated metadata database.

    This does not replace any installed trigger or bypass workflow schema checks.
    """
    conn = sqlite3.connect(":memory:", factory=ProcessProfileConnection)
    conn.row_factory = sqlite3.Row
    conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
    conn.executemany("INSERT INTO WorkbenchEntityRefs(ref,kind,entity_key,alternate_key) VALUES (?,'template_operation',?,?)",
                     [(format(index, "048x"), str(index), "SCALE:" + str(index)) for index in range(1, count + 1)])
    conn.commit()
    prefix = "UPDATE WorkbenchEntityRefs SET active=0,revision=revision+1 WHERE kind='template_operation' AND active=1 AND entity_key<>?"
    original = prefix + " AND (entity_key=? OR alternate_key=?)"
    by_key, by_alternate = prefix + " AND entity_key=?", prefix + " AND alternate_key=?"

    def run(split, args):
        old, new, alternate = args
        if split:
            conn.execute(by_key, (old, new))
            conn.execute(by_alternate, (old, alternate))
        else:
            conn.execute(original, args)

    def rows():
        return [tuple(row) for row in conn.execute("SELECT * FROM WorkbenchEntityRefs ORDER BY ref")]

    proofs = []
    for case in [("1", "1", "SCALE:1"), ("-1", "1", "absent"), ("-1", "-2", "SCALE:1"),
                 ("-1", "1", "SCALE:1"), ("-1", "1", "SCALE:2")]:
        observed = []
        for split in (False, True):
            conn.execute("SAVEPOINT comparison")
            run(split, case)
            observed.append(rows())
            conn.execute("ROLLBACK TO comparison")
            conn.execute("RELEASE comparison")
        assert observed[0] == observed[1]
        proofs.append({"parameters": case, "all_identity_fields_equal": True})
    plans = [{"sql": sql, "plan": [tuple(row) for row in conn.execute("EXPLAIN QUERY PLAN " + sql, params)]}
             for sql, params in ((original, ("1", "1", "SCALE:1")), (by_key, ("1", "1")), (by_alternate, ("1", "SCALE:1")))]
    phases = []
    # Reversed order in the second pair reduces systematic warm-cache timing bias.
    for index, split in enumerate((False, True, True, False)):
        def probe():
            for _ in range(100):
                run(split, ("1", "1", "SCALE:1"))
        _, result = profile_phase(conn, output, "predicate_" + str(index) + ("_split" if split else "_or"), probe)
        phases.append(result)
    conn.close()
    report = {"count": count, "repetitions": 100, "equivalence": proofs, "query_plans": plans, "phases": phases}
    (Path(output) / "predicate_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _profile_main():
    import argparse

    parser = argparse.ArgumentParser(description="Isolated process-stage profiles; never opens an application database.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--counts", nargs="+", type=int, default=[1000, 2000, 10000])
    parser.add_argument("--identity-predicates", action="store_true")
    parser.add_argument("--input-helpers", action="store_true")
    parser.add_argument("--noop-confirmations", action="store_true")
    args = parser.parse_args()
    if any(not 1 <= count <= 10000 for count in args.counts):
        parser.error("profile counts must be between 1 and 10000")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    hashes = profile_source_hashes()
    profile = profile_identity_predicates if args.identity_predicates else profile_input_helpers if args.input_helpers else profile_stage_scale
    if args.noop_confirmations:
        profile = profile_noop_confirmations
    runs = [profile(count, output / str(count)) for count in args.counts]
    report = {"python_sqlite_version": sqlite3.sqlite_version, "source_hashes_before": hashes,
              "source_hashes_after": profile_source_hashes(), "runs": runs}
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    _profile_main()

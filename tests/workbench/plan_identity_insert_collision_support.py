"""BW-only deterministic probes; the saved BP failure remains unresolved.

Overrides and observer triggers live on disposable test connections only. A
forced duplicate proves rollback behavior, not the cause of the historical run.
"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.infrastructure.workbench_plan_identity_schema import plan_identity_objects
from tests.workbench.identity_metadata_support import insert_row

REF_TABLES = ("WorkbenchEntityRefs", "WorkbenchPlanSourceRefs", "WorkbenchTaskRefs")
EVIDENCE_DATABASE = "failed-after-fixture-teardown.sqlite"


class RefProbe:
    """Record attempted refs outside SQL rollback; never retry a duplicate."""

    def __init__(self, conn, outputs=None, *, observe=True, native_random=False):
        self.draws = []
        self.attempts = []
        self.outputs = iter(outputs) if outputs is not None else None
        if native_random:
            assert outputs is None
        else:
            conn.create_function("randomblob", 1, self.draw, deterministic=False)
        conn.create_function("bw_observe_ref", 2, self.observe)
        columns = dict.fromkeys(REF_TABLES, "ref")
        present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table, column in (("WorkbenchDashboardItems", "item_ref"), ("WorkbenchDashboardDowntimeRefs", "ref")):
            if table in present:
                columns[table] = column
        for table, column in columns.items() if observe else ():
            conn.execute('CREATE TEMP TRIGGER "bw_observe_' + table + '" BEFORE INSERT ON main."' +
                         table + '" BEGIN SELECT bw_observe_ref(\'' + table + "', NEW." + column + "); END")

    def draw(self, size):
        assert size == 24
        # Little-endian counters are injective and exercise non-monotone PK order.
        value = next(self.outputs) if self.outputs is not None else (len(self.draws) + 1).to_bytes(size, "little")
        assert len(value) == size
        self.draws.append(value.hex())
        return value

    def observe(self, table, ref):
        self.attempts.append((table, ref))
        return 0

    def assert_one_draw_per_attempt(self):
        assert sorted(self.draws) == sorted(ref for _, ref in self.attempts)
        assert len(self.draws) == len(set(self.draws))
        # Task INSERT SELECT materializes its refs before nested map triggers run.
        # Preserve the original identity order and check every mapping draw too.
        for mapping in (False, True):
            attempts = [ref for table, ref in self.attempts if (table not in REF_TABLES) == mapping]
            selected = set(attempts)
            assert [ref for ref in self.draws if ref in selected] == attempts


def seed_parents(conn):
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('CAP-051','P1',3)")
    conn.commit()


def operation(conn, seq, *, batch="CAP-051", verb="INSERT", machine="M1", operator="O1"):
    insert_row(conn, "BatchOperations", dict(op_code=f"{batch}-{seq}", batch_id=batch,
        seq=seq, op_type_id="T1", op_type_name="Turning", source="internal", setup_hours=0,
        unit_hours=0.001, machine_id=machine, operator_id=operator, status="pending"), verb=verb)


def source_refs(conn):
    return [tuple(row) for row in conn.execute(
        "SELECT source_key,ref,active FROM WorkbenchPlanSourceRefs WHERE kind='operation' ORDER BY rowid")]


def insert_many_operations(conn, count):
    conn.execute("""WITH RECURSIVE rows(seq) AS (VALUES(1) UNION ALL
        SELECT seq+1 FROM rows WHERE seq < ?)
        INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name)
        SELECT 'CAP-051-' || seq,'CAP-051',seq,'Turning' FROM rows""", (count,))


def inspect_saved_failure(directory):
    """Read only the preserved evidence bundle, including earlier run snapshots."""
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "failure-evidence.json").read_text(encoding="utf-8"))
    path = directory / EVIDENCE_DATABASE
    assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["database_sha256"]
    for source in manifest["sources"]:
        saved = directory / "source-after-failure" / source["path"]
        assert hashlib.sha256(saved.read_bytes()).hexdigest() == source["sha256"]
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        actual = dict(conn.execute("SELECT name,sql FROM sqlite_master"))
        identity = {name: sql for name, sql in actual.items() if name.startswith("wb_plan_")}
        snapshots = []
        for ref, raw in conn.execute("SELECT run_ref,facts_json FROM WorkbenchRunJobs"):
            saved = {row[1]: row[3] for row in json.loads(raw)["schema"]
                     if row[0] == "trigger" and row[1].startswith("wb_plan_")}
            snapshots.append({"run_ref": ref, "trigger_count": len(saved), "matches_saved_db": saved == identity})
        return {"status": "unresolved", "evidence_hashes_verified": True,
                "sqlite_runtime": sqlite3.sqlite_version,
                "integrity_check": [row[0] for row in conn.execute("PRAGMA integrity_check")],
                "operation_refs": source_refs(conn),
                "clock": list(conn.execute("SELECT singleton,revision FROM WorkbenchPlanIdentityClock")),
                "identity_ddl_mismatches": [name for name, sql in plan_identity_objects().items()
                    if _canonical_sql(actual.get(name) or "") != _canonical_sql(sql)],
                "pre_capacity_snapshots": snapshots, "limitations": manifest["limitations"]}


def replay_saved_capacity(directory):
    """One deterministic seed-only replay on an in-memory backup; no worker/UI."""
    report = inspect_saved_failure(directory)
    path = (Path(directory).resolve() / EVIDENCE_DATABASE).as_uri() + "?mode=ro"
    with closing(sqlite3.connect(path, uri=True)) as saved, closing(sqlite3.connect(":memory:")) as conn:
        saved.execute("PRAGMA query_only=ON")
        saved.backup(conn)
        conn.execute("PRAGMA foreign_keys=ON")
        before = source_refs(conn)
        probe = RefProbe(conn)
        conn.execute("UPDATE BatchOperations SET unit_hours=0.001")
        for index in range(100):
            batch = "B1" if index == 0 else f"CAP-{index:03d}"
            machine, operator = "M1", "O1"
            if index:
                machine, operator = f"CM{index:03d}", f"CO{index:03d}"
                conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES (?,'P1',3)", (batch,))
                conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES (?,?,'T1')", (machine, machine))
                conn.execute("INSERT INTO Operators(operator_id,name) VALUES (?,?)", (operator, operator))
                conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES (?,?)", (operator, machine))
            for seq in range(4 if index == 0 else 1, 51):
                operation(conn, seq, batch=batch, machine=machine, operator=operator)
        probe.assert_one_draw_per_attempt()
        assert source_refs(conn)[:len(before)] == before
        assert conn.execute("SELECT count(*) FROM BatchOperations WHERE op_code='CAP-051-15'").fetchone()[0] == 1
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        report["deterministic_replay"] = {"operation_count": len(source_refs(conn)),
            "draws": len(probe.draws), "attempts": len(probe.attempts),
            "original_refs_retained": True, "CAP-051-15_inserted": True,
            "historical_failure_reproduced": False,
            "scope": "seed only; connection-local numbered randomblob; no scheduler or browser"}
    return report

"""Bound new tracking rows to the actual AN-only operations that created them."""

import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path

TABLES = frozenset(("WorkbenchDashboardItems", "WorkbenchOutsourcingOperationOrigins",
                    "WorkbenchTemplateLineageOrigins", "WorkbenchTemplateLineageEvents"))
REF = re.compile(r"[0-9a-f]{48}\Z")


def row_id(row):
    keys = {"__oracle_rowid__", "__rowid__"} & row.keys()
    assert len(keys) == 1
    key = next(iter(keys))
    return row[key]


def normalized_row(row):
    return {"__rowid__": row_id(row), **{key: value for key, value in row.items() if key not in ("__rowid__", "__oracle_rowid__")}}


def changes_between(before, after):
    result = []
    assert before["schema"] == after["schema"]
    for table, rows in before["tables"].items():
        old = {row_id(row): row for row in rows}
        new = {row_id(row): row for row in after["tables"][table]}
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                result.append({"table": table, "before": old.get(key), "after": new.get(key)})
    return result


def typed_events(rows, root):
    if not rows:
        return {}
    assert root is not None, "Typed lineage evidence requires its real private database"
    root = Path(root).resolve()
    db = (root / "db/aps-live.db").resolve()
    db.relative_to(root)
    expected = {row["event_id"]: normalized_row(row) for row in rows}
    assert len(expected) == len(rows), "Duplicate lineage event identity"
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        actual = {row["event_id"]: dict(row) for row in conn.execute(
            'SELECT rowid AS __rowid__, * FROM WorkbenchTemplateLineageEvents WHERE event_id <= ? ORDER BY event_id',
            (max(expected),))}
    assert actual == expected, "Saved event values or history differ from the immutable SQLite evidence"
    history = defaultdict(list)
    for row in actual.values():
        history[row["operation_ref"]].append(row)
    return history


def validate_metadata(changes, after, policy, root=None):
    assert policy in ("read", "write", "noop")
    items = [row for row in changes if row["table"] in TABLES]
    if items:
        assert policy == "write", "Read/cancel/noop cannot append tracking records"
    tables = after["tables"]
    batches = {row["ref"]: row for row in tables["WorkbenchEntityRefs"] if row["kind"] == "batch"}
    operations = {row["ref"]: row for row in tables["WorkbenchPlanSourceRefs"] if row["kind"] == "operation"}
    new_batches = {row["after"]["ref"] for row in changes if row["table"] == "WorkbenchEntityRefs"
                   and row.get("before") is None and row.get("after") and row["after"]["kind"] == "batch"}
    new_operations = {row["after"]["ref"] for row in changes if row["table"] == "WorkbenchPlanSourceRefs"
                      and row.get("before") is None and row.get("after") and row["after"]["kind"] == "operation"}
    events = defaultdict(list)
    for row in tables["WorkbenchTemplateLineageEvents"]:
        events[row["operation_ref"]].append(row)
    for rows in events.values():
        rows.sort(key=lambda row: row["event_id"])
    dashboard, outsourcing, origins, touched = defaultdict(list), set(), set(), set()
    exact_events = None

    def batch_owner(ref):
        owner = batches[ref]
        assert REF.fullmatch(ref) and owner["entity_key"].startswith("AN-"), "Tracking row targets an original protected batch"
        return owner

    def operation_owner(ref):
        owner = operations[ref]
        history = events[ref]
        assert REF.fullmatch(ref) and owner["alternate_key"].startswith("AN-B-"), "Tracking row targets an out-of-scope operation"
        assert history and history[0]["event_type"] == "created"
        birth = history[0]
        assert str(birth["id"]) == owner["source_key"] and birth["op_code"] == owner["alternate_key"]
        batch = batch_owner(birth["batch_ref"])
        assert batch["entity_key"] == birth["batch_id"]
        return birth

    for change in items:
        table, row = change["table"], change.get("after")
        assert change.get("before") is None and row is not None, "Old tracking rows cannot be updated or removed"
        assert any(normalized_row(row) == normalized_row(item) for item in tables[table])
        assert type(row_id(row)) is int and row_id(row) > 0
        columns = {key for key in row if key not in ("__rowid__", "__oracle_rowid__")}
        if table == "WorkbenchDashboardItems":
            assert columns == {"item_ref", "category", "batch_ref", "task_ref"}
            assert REF.fullmatch(row["item_ref"]) and row["category"] in ("delivery", "material") and row["task_ref"] is None
            assert row["batch_ref"] in new_batches, "Dashboard rows must belong to a batch identity created in this action"
            batch_owner(row["batch_ref"])
            dashboard[row["batch_ref"]].append(row["category"])
        elif table == "WorkbenchOutsourcingOperationOrigins":
            assert columns == {"operation_ref", "batch_ref"}
            assert row["operation_ref"] in new_operations and row["operation_ref"] not in outsourcing
            assert operation_owner(row["operation_ref"])["batch_ref"] == row["batch_ref"]
            outsourcing.add(row["operation_ref"])
        elif table == "WorkbenchTemplateLineageOrigins":
            from core.services.scheduler.template_lineage_query import validate_origin

            assert row["operation_ref"] in new_operations and row["operation_ref"] not in origins
            operation_owner(row["operation_ref"])
            # JavaScript JSON loses SQLite REAL 0.0 versus INTEGER 0. Preserve
            # storage types from the immutable event rows, after exact value checks.
            if exact_events is None:
                exact_events = typed_events(tables["WorkbenchTemplateLineageEvents"], root)
            template, instance = validate_origin(row, exact_events[row["operation_ref"]])
            assert instance["batch_ref"] in batches and batch_owner(instance["batch_ref"])["entity_key"] == instance["batch_id"]
            assert instance["op_code"] == operations[row["operation_ref"]]["alternate_key"]
            assert template["part_no"] == "PROC-001"
            origins.add(row["operation_ref"])
            touched.add(row["operation_ref"])
        else:
            birth = operation_owner(row["operation_ref"])
            assert row["batch_ref"] == birth["batch_ref"] and row["batch_id"] == birth["batch_id"]
            assert str(row["id"]) == operations[row["operation_ref"]]["source_key"]
            assert row["op_code"] == operations[row["operation_ref"]]["alternate_key"]
            assert row["event_type"] in ("created", "updated", "retired", "batch_changed")
            touched.add(row["operation_ref"])
    assert set(dashboard) == new_batches, "Every new batch requires its exact two dashboard identities"
    assert all(sorted(values) == ["delivery", "material"] for values in dashboard.values())
    assert outsourcing == new_operations, "Every new operation requires one original-batch binding"
    assert origins == new_operations, "Every operation in these template-copy scenarios requires its lineage origin"
    lineage = {"checked": 0}
    if touched:
        from core.services.scheduler.template_lineage_query import TemplateLineageQuery

        assert root is not None, "Lineage validation requires the real private database, not a skipped check"
        root = Path(root).resolve()
        db = (root / "db/aps-live.db").resolve()
        db.relative_to(root)
        with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            result = TemplateLineageQuery(conn).read(sorted(touched))
            assert result["available"] and touched <= set(result["origins"])
            lineage = {"checked": len(touched), "problems": result["problems"]}
    return {"passed": True, "accepted_append_only_tables": dict(Counter(row["table"] for row in items)),
            "new_batch_pairs": len(dashboard), "new_operation_origins": len(new_operations), "lineage": lineage,
            "policy": "Exact new AN batch/operation identities only; old rows immutable; paired indexes and real lineage validation"}


def main():
    value = json.load(sys.stdin)
    try:
        result = validate_metadata(value["changes"], value["after"], value["policy"], value.get("root"))
    finally:
        if os.environ.get("FINAL_OPERATIONS_SOURCE_MANIFEST"):
            from tests.workbench.final_operations_source_binding import source_binding
            from tests.workbench.live_environment import write_json

            binding = source_binding()
            assert binding is not None and not binding["violations"]
            write_json(Path(value["root"]) / ("final-master-lineage-imports-" + str(os.getpid()) + ".json"), binding)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

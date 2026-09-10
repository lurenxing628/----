"""Permanent instance refs and task membership, maintained only on source writes.

Source refs retain tombstones. Row snapshots keep the original operation/parent
instance, so an orphan cannot attach itself to a later same-number replacement.
An official plan is a history *version*, not an individual history summary row.
Version refs survive summary removal/restoration; resolution requires a live head.
The existing ScheduleVersionSeq allocator never reuses a published version number.
Task refs are random persisted pairs of plan instance and arrangement instance.
Installation is caller-transactional; none of these statements updates sources.
Fresh bootstrap executes objects(), then plan_identity_initialization_sql()
before schema-version detection. The empty-DB detector may ignore ONLY the
validated initial Clock(1, 1) row, not either reference table or a used clock.
Existing databases must enter install() BEFORE any CREATE IF NOT EXISTS repair.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .workbench_metadata_schema import _canonical_sql, entity_key_sql

_REF = "TEXT PRIMARY KEY NOT NULL CHECK(length(ref) = 48 AND ref NOT GLOB '*[^0-9a-f]*')"
_RANDOM = "lower(hex(randomblob(24)))"
_COLUMNS = ("kind", "source_key", "alternate_key", "extra_key", "version", "plan_role",
            "source_table", "owner_key", "operation_id", "operation_ref", "parent_ref")
# kind: table, primary key, unique alternates, identity-changing columns.
_SOURCES: Dict[str, Tuple[str, str, Tuple[Tuple[str, ...], ...], Tuple[str, ...]]] = {
    "operation": ("BatchOperations", "id", (("op_code",), ("batch_id", "seq", "piece_id")), ()),
    "candidate": ("ScheduleCandidate", "id", (("version", "candidate_key"),), ("id", "version", "candidate_key")),
    "selection": ("ScheduleCandidateSelection", "id", (("version", "role"),), ("id", "version", "role", "candidate_id", "source_table")),
    "scenario": ("ScheduleAdjustmentScenario", "scenario_id", (("source_draft_id",),),
                 ("scenario_id", "source_draft_id", "base_version", "base_plan_role", "base_source_table", "base_candidate_id", "base_candidate_key")),
    "schedule_row": ("Schedule", "id", (), ("version", "op_id")),
    "candidate_row": ("ScheduleCandidateRows", "id", (("candidate_id", "op_id"),), ("version", "candidate_id", "op_id")),
    "scenario_row": ("ScheduleAdjustmentScenarioRow", "id", (("scenario_id", "op_id"),), ("scenario_id", "op_id")),
}
_INITIALIZATION_TABLES = ("WorkbenchPlanSourceRefs", "WorkbenchTaskRefs", "ScheduleHistory") + tuple(
    source[0] for source in _SOURCES.values())
_TABLES = {
    "WorkbenchPlanSourceRefs": f"""CREATE TABLE IF NOT EXISTS WorkbenchPlanSourceRefs (
        ref {_REF}, kind TEXT NOT NULL, source_key TEXT NOT NULL,
        alternate_key TEXT, extra_key TEXT, version INTEGER, plan_role TEXT,
        source_table TEXT, owner_key TEXT, operation_id INTEGER,
        operation_ref TEXT, parent_ref TEXT,
        active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1))
    )""",
    "WorkbenchTaskRefs": f"""CREATE TABLE IF NOT EXISTS WorkbenchTaskRefs (
        ref {_REF}, plan_ref TEXT NOT NULL, row_ref TEXT NOT NULL,
        UNIQUE(plan_ref, row_ref)
    )""",
    "WorkbenchPlanIdentityClock": """CREATE TABLE IF NOT EXISTS WorkbenchPlanIdentityClock (
        singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
        revision INTEGER NOT NULL CHECK(typeof(revision) = 'integer' AND revision > 0)
    )""",
}
_INDEXES = {
    "idx_wb_plan_source_key": "CREATE UNIQUE INDEX IF NOT EXISTS idx_wb_plan_source_key ON WorkbenchPlanSourceRefs(kind, source_key) WHERE active = 1",
    "idx_wb_plan_source_alternate": "CREATE INDEX IF NOT EXISTS idx_wb_plan_source_alternate ON WorkbenchPlanSourceRefs(kind, alternate_key) WHERE active = 1",
    "idx_wb_plan_source_extra": "CREATE INDEX IF NOT EXISTS idx_wb_plan_source_extra ON WorkbenchPlanSourceRefs(kind, extra_key) WHERE active = 1",
    "idx_wb_plan_source_version": "CREATE INDEX IF NOT EXISTS idx_wb_plan_source_version ON WorkbenchPlanSourceRefs(kind, version, plan_role) WHERE active = 1",
    "idx_wb_plan_source_parent": "CREATE INDEX IF NOT EXISTS idx_wb_plan_source_parent ON WorkbenchPlanSourceRefs(kind, parent_ref) WHERE active = 1",
    "idx_wb_plan_task_row": "CREATE INDEX IF NOT EXISTS idx_wb_plan_task_row ON WorkbenchTaskRefs(row_ref)",
    "idx_wb_plan_history_head": "CREATE INDEX IF NOT EXISTS idx_wb_plan_history_head ON ScheduleHistory(version, schedule_time DESC, id DESC)",
}


def _lookup(kind: str, key: str) -> str:
    return ("(SELECT ref FROM WorkbenchPlanSourceRefs WHERE kind = '" + kind +
            "' AND source_key = CAST(" + key + " AS TEXT) AND active = 1)")


def _base_ref(prefix: str) -> str:
    return f"""CASE WHEN {prefix}.base_plan_role = 'adopted'
        THEN {_lookup('official', prefix + '.base_version')}
        ELSE (SELECT ref FROM WorkbenchPlanSourceRefs WHERE active = 1 AND kind = 'selection'
            AND version = {prefix}.base_version AND plan_role = {prefix}.base_plan_role) END"""


def _values(kind: str, prefix: str) -> Dict[str, str]:
    _, primary, alternates, _ = _SOURCES[kind]
    values: Dict[str, str] = dict.fromkeys(_COLUMNS, "NULL")
    values.update(kind="'" + kind + "'", source_key=entity_key_sql((primary,), prefix))
    for field, columns in zip(("alternate_key", "extra_key"), alternates):
        values[field] = entity_key_sql(columns, prefix)
    if kind in ("candidate", "selection", "schedule_row", "candidate_row"):
        values["version"] = prefix + ".version"
    if kind == "selection":
        values.update(plan_role=prefix + ".role", source_table=prefix + ".source_table",
                      owner_key=f"CAST({prefix}.candidate_id AS TEXT)",
                      parent_ref=_lookup("candidate", prefix + ".candidate_id"))
    if kind == "scenario":
        values.update(version=prefix + ".base_version", plan_role=prefix + ".base_plan_role",
                      source_table="'adjustment_scenario_rows'", parent_ref=_base_ref(prefix))
    if kind.endswith("_row"):
        source = {"schedule_row": "schedule", "candidate_row": "candidate_rows",
                  "scenario_row": "adjustment_scenario_rows"}[kind]
        owner = {"schedule_row": "version", "candidate_row": "candidate_id", "scenario_row": "scenario_id"}[kind]
        values.update(source_table="'" + source + "'", owner_key=f"CAST({prefix}.{owner} AS TEXT)",
                      operation_id=prefix + ".op_id", operation_ref=_lookup("operation", prefix + ".op_id"))
        if kind != "schedule_row":
            values["parent_ref"] = _lookup("candidate" if kind == "candidate_row" else "scenario", prefix + "." + owner)
    return values


def _insert(values: Dict[str, str], condition: str = "1") -> str:
    return ("INSERT INTO WorkbenchPlanSourceRefs(ref, " + ", ".join(_COLUMNS) + ") SELECT " +
            _RANDOM + ", " + ", ".join(values[column] for column in _COLUMNS) + " WHERE " + condition + ";")


def _history_triggers() -> Dict[str, str]:
    insert = f"""INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, version, plan_role, source_table)
        SELECT {_RANDOM}, 'official', CAST(NEW.version AS TEXT), NEW.version, 'adopted', 'schedule'
        WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanSourceRefs WHERE kind = 'official'
            AND source_key = CAST(NEW.version AS TEXT) AND active = 1);"""
    result = {}
    for event in ("insert", "update", "delete"):
        name = "wb_plan_history_" + event
        body = "" if event == "delete" else insert
        result[name] = (f"CREATE TRIGGER IF NOT EXISTS {name} AFTER {event.upper()} ON ScheduleHistory BEGIN " +
                        body + "UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END")
    return result


def _source_triggers(kind: str) -> Dict[str, str]:
    table, primary, _, rotate_columns = _SOURCES[kind]
    values = _values(kind, "NEW")
    old_key = entity_key_sql((primary,), "OLD")
    conflicts = [column + " = " + values[column] for column in
                 ("source_key", "alternate_key", "extra_key") if values[column] != "NULL"]
    where = f"kind = '{kind}' AND active = 1"
    changed = " OR ".join(f"OLD.{column} IS NOT NEW.{column}" for column in rotate_columns) or "0"
    # Separate indexed seeks: an OR here makes SQLite scan every same-kind ref.
    retire = "".join(f"UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE {where} AND {conflict};"
                     for conflict in conflicts)
    update_retire = "".join(f"UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE {where} "
                            f"AND {conflict} AND source_key != {old_key};" for conflict in conflicts)
    update_retire += (f"UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE {where} "
                      f"AND source_key = {old_key} AND ({changed});")
    # Only identity changes capture fresh parent/operation refs. Ordinary updates
    # must never reconnect an orphaned arrangement to a same-number new instance.
    assignments = ", ".join(column + " = " + values[column] for column in _COLUMNS
                            if column not in ("operation_ref", "parent_ref"))
    bodies = {
        "insert": retire + _insert(values),
        "update": update_retire + f"UPDATE WorkbenchPlanSourceRefs SET {assignments} WHERE {where} AND source_key = {old_key};" + _insert(values, changed),
        "delete": f"UPDATE WorkbenchPlanSourceRefs SET active = 0 WHERE {where} AND source_key = {old_key};",
    }
    result = {}
    for event, body in bodies.items():
        name = "wb_plan_" + kind + "_" + event
        result[name] = (f'CREATE TRIGGER IF NOT EXISTS {name} AFTER {event.upper()} ON "{table}" BEGIN ' +
                        body + "UPDATE WorkbenchPlanIdentityClock SET revision = revision + 1 WHERE singleton = 1; END")
    return result


def _task_pairs(plan_condition: str = "1", row_condition: str = "1") -> str:
    common = f"p.active = 1 AND r.active = 1 AND ({plan_condition}) AND ({row_condition})"
    matches = (
        "p.kind = 'official' AND r.kind = 'schedule_row' AND r.version = p.version",
        "p.kind = 'selection' AND p.plan_role != 'adopted' AND p.source_table = 'schedule' "
        "AND r.kind = 'schedule_row' AND r.version = p.version",
        "p.kind = 'selection' AND p.plan_role != 'adopted' AND p.source_table = 'candidate_rows' "
        "AND r.kind = 'candidate_row' AND r.version = p.version AND r.parent_ref = p.parent_ref",
        "p.kind = 'scenario' AND r.kind = 'scenario_row' AND r.parent_ref = p.ref",
    )
    return " UNION ALL ".join(
        "SELECT p.ref AS plan_ref, r.ref AS row_ref FROM WorkbenchPlanSourceRefs p "
        "JOIN WorkbenchPlanSourceRefs r ON " + match + " WHERE " + common for match in matches)


def _task_insert(plan_condition: str = "1", row_condition: str = "1") -> str:
    return f"""INSERT INTO WorkbenchTaskRefs(ref, plan_ref, row_ref)
        SELECT {_RANDOM}, pairs.plan_ref, pairs.row_ref FROM ({_task_pairs(plan_condition, row_condition)}) pairs
        WHERE NOT EXISTS (SELECT 1 FROM WorkbenchTaskRefs t
            WHERE t.plan_ref = pairs.plan_ref AND t.row_ref = pairs.row_ref);"""


def plan_identity_objects() -> Dict[str, str]:
    objects = dict(_TABLES)
    objects.update(_INDEXES)
    objects.update(_history_triggers())
    for kind in _SOURCES:
        objects.update(_source_triggers(kind))
    for side, condition in (("plan", "NEW.kind IN ('official', 'selection', 'scenario')"),
                            ("row", "NEW.kind IN ('schedule_row', 'candidate_row', 'scenario_row')")):
        name = "wb_plan_task_" + side + "_insert"
        body = _task_insert("p.ref = NEW.ref" if side == "plan" else "1",
                            "r.ref = NEW.ref" if side == "row" else "1")
        objects[name] = (f"CREATE TRIGGER IF NOT EXISTS {name} AFTER INSERT ON WorkbenchPlanSourceRefs "
                         f"WHEN {condition} BEGIN {body} END")
    return objects


def _source_issues(conn) -> List[str]:
    issues = []
    extras = {"history": ("schedule_time", "version"), "scenario_row": ("op_id",),
              "schedule_row": ("id", "version", "op_id")}
    sources = dict(_SOURCES, history=("ScheduleHistory", "id", (), ()))
    for kind, (table, primary, alternates, rotate_columns) in sources.items():
        info = conn.execute("SELECT name, pk FROM pragma_table_info(?)", (table,)).fetchall()
        names = {row[0] for row in info}
        required = {primary, *rotate_columns, *extras.get(kind, ())}
        required.update(column for columns in alternates for column in columns)
        issues.extend("missing_workbench_plan_source: " + table + "." + column
                      for column in sorted(required - names))
        if tuple(row[0] for row in sorted(info, key=lambda row: row[1]) if row[1]) != (primary,):
            issues.append("bad_workbench_plan_source_primary: " + table)
    return issues


def _structure_issues(conn) -> List[str]:
    actual = {row[0]: row[1] for row in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type IN ('table', 'index', 'trigger')").fetchall()}
    issues = _source_issues(conn)
    for name, sql in plan_identity_objects().items():
        if name not in actual:
            issues.append("missing_workbench_plan_identity: " + name)
        elif _canonical_sql(actual[name] or "") != _canonical_sql(sql):
            issues.append("bad_workbench_plan_identity: " + name)
    return issues


def _clock_issues(conn) -> List[str]:
    rows = conn.execute("SELECT singleton, revision FROM WorkbenchPlanIdentityClock LIMIT 2").fetchall()
    if not rows:
        return ["missing_workbench_plan_clock_state"]
    if len(rows) != 1 or rows[0][0] != 1 or type(rows[0][1]) is not int or rows[0][1] <= 0:
        return ["bad_workbench_plan_clock_state"]
    return []


def workbench_plan_identity_contract_issues(conn) -> List[str]:
    """SELECT-only structure and required clock check, not business completeness."""
    issues = _structure_issues(conn)
    return issues if issues else _clock_issues(conn)


def plan_identity_initialization_sql() -> str:
    """Seed for the end of a NEW database's DDL script, never a repair script.

The revision CHECK deliberately aborts a missing-clock initialization when any
source/identity data exists. Do not replace it with INSERT OR IGNORE. Python
callers use initialize_plan_identity() to validate the complete DDL first.
"""
    empty = " AND ".join(f'NOT EXISTS (SELECT 1 FROM "{table}" LIMIT 1)' for table in _INITIALIZATION_TABLES)
    return ("INSERT INTO WorkbenchPlanIdentityClock(singleton, revision) "
            f"SELECT 1, CASE WHEN {empty} THEN 1 ELSE 0 END "
            "WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanIdentityClock);")


def initialize_plan_identity(conn) -> None:
    """Initialize a complete, empty schema once; never recreate refs or a used clock."""
    issues = _structure_issues(conn)
    if issues:
        raise RuntimeError("Cannot initialize workbench plan identities: " + "; ".join(issues))
    clock_issues = _clock_issues(conn)
    if clock_issues == ["missing_workbench_plan_clock_state"]:
        if any(conn.execute(f'SELECT 1 FROM "{table}" LIMIT 1').fetchone() for table in _INITIALIZATION_TABLES):
            raise RuntimeError("Cannot initialize a missing plan clock over existing source or identity data.")
        conn.execute(plan_identity_initialization_sql())
    elif clock_issues:
        raise RuntimeError("Cannot initialize workbench plan identities: " + "; ".join(clock_issues))


def _existing_identity_issues(conn) -> List[str]:
    """Installation-only coverage check; no all-history scan in GET requests."""
    issues = []
    sources = [(kind, table, entity_key_sql((primary,), "s"))
               for kind, (table, primary, _, _) in _SOURCES.items()]
    sources.append(("official", "ScheduleHistory", "CAST(s.version AS TEXT)"))
    for kind, table, key in sources:
        missing = conn.execute(f'SELECT 1 FROM "{table}" s WHERE NOT EXISTS ('
                               "SELECT 1 FROM WorkbenchPlanSourceRefs r WHERE r.kind = ? "
                               f"AND r.source_key = {key} AND r.active = 1) LIMIT 1", (kind,)).fetchone()
        if missing:
            issues.append("missing_workbench_plan_source_identity: " + kind)
    if conn.execute(f"SELECT 1 FROM ({_task_pairs()}) pairs WHERE NOT EXISTS ("
                    "SELECT 1 FROM WorkbenchTaskRefs t WHERE t.plan_ref = pairs.plan_ref "
                    "AND t.row_ref = pairs.row_ref) LIMIT 1").fetchone():
        issues.append("missing_workbench_plan_task_identity")
    return issues


def _is_first_install(conn) -> bool:
    expected = set(plan_identity_objects())
    actual = {row[0] for row in conn.execute("SELECT name FROM sqlite_master").fetchall()}
    present = expected & actual
    if present and present != expected:
        raise RuntimeError("Partial workbench plan identity schema; refusing to recreate permanent identities: " +
                           ", ".join(sorted(expected - present)))
    issues = _structure_issues(conn) if present else _source_issues(conn)
    if issues:
        raise RuntimeError("Cannot install workbench plan identities: " + "; ".join(issues))
    if not present and "SchemaVersion" in actual:
        row = conn.execute("SELECT version FROM SchemaVersion WHERE id = 1").fetchone()
        if row is not None and row[0] >= 24:
            raise RuntimeError("Plan identity schema is missing from an already migrated database.")
    return not present


def _backfill_source(conn, kind: str) -> None:
    table, _, _, _ = _SOURCES[kind]
    values = _values(kind, "s")
    key = values["source_key"]
    if conn.execute(f'SELECT 1 FROM "{table}" s WHERE {key} IS NULL LIMIT 1').fetchone():
        raise RuntimeError("Cannot backfill identity for a missing source key: " + table)
    conn.execute("INSERT INTO WorkbenchPlanSourceRefs(ref, " + ", ".join(_COLUMNS) + ") SELECT " +
                 _RANDOM + ", " + ", ".join(values[column] for column in _COLUMNS) +
                 f' FROM "{table}" s WHERE NOT EXISTS (SELECT 1 FROM WorkbenchPlanSourceRefs e '
                 f"WHERE e.kind = '{kind}' AND e.source_key = {key} AND e.active = 1)")


def install_plan_identity(conn) -> None:
    """First install backfills; a complete existing schema is checked, never repaired."""
    if not _is_first_install(conn):
        initialize_plan_identity(conn)
        issues = _existing_identity_issues(conn)
        if issues:
            raise RuntimeError("Lost permanent plan identities; restore a complete backup: " + "; ".join(issues))
        return
    for sql in plan_identity_objects().values():
        conn.execute(sql)
    # All metadata objects were absent before this transaction. Legacy sources
    # are allowed only on this first-install path, immediately followed by backfill.
    conn.execute("INSERT INTO WorkbenchPlanIdentityClock(singleton, revision) VALUES (1, 1)")
    conn.execute(f"""INSERT INTO WorkbenchPlanSourceRefs(ref, kind, source_key, version, plan_role, source_table)
        SELECT {_RANDOM}, 'official', CAST(h.version AS TEXT), h.version, 'adopted', 'schedule'
        FROM (SELECT DISTINCT version FROM ScheduleHistory) h WHERE NOT EXISTS
        (SELECT 1 FROM WorkbenchPlanSourceRefs e WHERE e.kind = 'official'
            AND e.source_key = CAST(h.version AS TEXT) AND e.active = 1)""")
    for kind in _SOURCES:
        _backfill_source(conn, kind)
    conn.execute(_task_insert())


# Small integration surface for the coordinator; no registration in this module.
objects = plan_identity_objects
install = install_plan_identity
contract_issues = workbench_plan_identity_contract_issues

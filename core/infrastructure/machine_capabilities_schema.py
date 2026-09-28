"""Additional machine work types; the legacy primary capability remains valid."""

from .workbench_metadata_schema import canonical_sql


def objects():
    result = {
        "MachineOpTypes": """CREATE TABLE MachineOpTypes (
            machine_id TEXT NOT NULL REFERENCES Machines(machine_id) ON DELETE CASCADE,
            op_type_id TEXT NOT NULL REFERENCES OpTypes(op_type_id),
            PRIMARY KEY(machine_id, op_type_id))""",
        "idx_machine_op_types_type": "CREATE INDEX idx_machine_op_types_type ON MachineOpTypes(op_type_id)",
    }
    for event in ("INSERT", "UPDATE", "DELETE"):
        aliases = ("OLD", "NEW") if event == "UPDATE" else (("OLD",) if event == "DELETE" else ("NEW",))
        predicates = [f"(kind='{kind}' AND entity_key={alias}.{key})" for kind, key in
                      (("machine", "machine_id"), ("op_type", "op_type_id")) for alias in aliases]
        name = "wb_machine_types_" + event.lower()
        result[name] = f"""CREATE TRIGGER {name} AFTER {event} ON MachineOpTypes BEGIN
            UPDATE WorkbenchEntityRefs SET revision=revision+1 WHERE active=1 AND ({' OR '.join(predicates)});
        END"""
    return result


def contract_issues(conn):
    actual = {row[0]: row[1] for row in conn.execute("SELECT name,sql FROM sqlite_master")}
    return [("missing_machine_capabilities:" if name not in actual else "invalid_machine_capabilities:") + name
            for name, sql in objects().items()
            if name not in actual or canonical_sql(sql) != canonical_sql(actual[name] or "")]


def install(conn):
    if not conn.in_transaction:
        raise RuntimeError("Machine capabilities require a migration transaction.")
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    if names & set(objects()):
        issues = contract_issues(conn)
        if issues:
            raise RuntimeError("Cannot repair partial machine capabilities: " + ";".join(issues))
        return
    for sql in objects().values():
        conn.execute(sql)

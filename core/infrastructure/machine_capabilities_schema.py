"""Additional machine work types; the legacy primary capability remains valid."""

from .schema_structure import SchemaStructure, schema_objects
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


def contract_issues(conn, *, structure=None):
    actual = schema_objects(conn, structure=structure)
    return [("missing_machine_capabilities:" if name not in actual else "invalid_machine_capabilities:") + name
            for name, sql in objects().items()
            if name not in actual or canonical_sql(sql) != canonical_sql(actual[name])]


def install(conn):
    if not conn.in_transaction:
        raise RuntimeError("Machine capabilities require a migration transaction.")
    structure = SchemaStructure(conn)
    definitions = objects()
    if structure.objects.keys() & definitions.keys():
        issues = contract_issues(conn, structure=structure)
        if issues:
            raise RuntimeError("Cannot repair partial machine capabilities: " + ";".join(issues))
        return
    for sql in definitions.values():
        conn.execute(sql)

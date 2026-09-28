"""New schemas preserve legacy facts and refuse incomplete installations."""

import pytest

from core.infrastructure.machine_capabilities_schema import contract_issues as machine_issues
from core.infrastructure.machine_capabilities_schema import objects as machine_objects
from core.infrastructure.material_stages_schema import contract_issues as material_issues
from core.infrastructure.material_stages_schema import objects as material_objects
from core.infrastructure.migrations.v35 import run as v35
from core.infrastructure.migrations.v36 import run as v36


@pytest.mark.parametrize("objects,run,check", [(machine_objects, v35, machine_issues), (material_objects, v36, material_issues)])
def test_install_idempotent_without_rewriting_legacy_rows(schema_conn, objects, run, check):
    conn = schema_conn
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T','车削')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M','设备','T')")
    before = tuple(conn.execute("SELECT * FROM Machines").fetchone())
    for name, sql in reversed(list(objects().items())):
        kind = "TRIGGER" if "CREATE TRIGGER" in sql else "INDEX" if "CREATE INDEX" in sql else "TABLE"
        conn.execute("DROP " + kind + " " + name)
    conn.commit()
    run(conn)
    assert not check(conn)
    assert tuple(conn.execute("SELECT * FROM Machines").fetchone()) == before
    snapshot = list(conn.iterdump())
    run(conn)
    assert list(conn.iterdump()) == snapshot


@pytest.mark.parametrize("table,run", [("idx_machine_op_types_type", v35), ("BatchMaterialStages", v36)])
def test_partial_schema_rejected(schema_conn, table, run):
    schema_conn.execute(("DROP INDEX " if table.startswith("idx_") else "DROP TABLE ") + table)
    schema_conn.commit()
    before = list(schema_conn.iterdump())
    with pytest.raises(RuntimeError, match="partial"):
        run(schema_conn)
    assert list(schema_conn.iterdump()) == before

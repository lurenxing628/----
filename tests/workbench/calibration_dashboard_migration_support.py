"""Historical v28 with real completed candidates, execution, lineage and a scenario."""

import hashlib
from pathlib import Path

from flask import Flask

from core.infrastructure.migration_state import set_schema_version
from core.infrastructure.migrations import v27, v28
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_metadata_schema import _canonical_sql
from core.services.workbench.template_lineage import TemplateLineageWriter
from tests.workbench.run_schema_migration_support import connect, source_ddl
from tests.workbench.test_run_jobs_support import JobCase
from tests.workbench.trial_lineage_migration_support import seed_v26
from tests.workbench.trial_support import create, service

FIXTURE_V28 = Path(__file__).parent / "fixtures" / "schema-v28.sql"
FIXTURE_V28_SHA = "2520295cebbe708270f93ed0aa5a6b18ea9b93ad3a1c77dd6c7a857fea44ad52"


def canonical_object(row):
    return row[:3], _canonical_sql(row[3] or "")


def seed_v28(path):
    conn = seed_v26(path)
    with TransactionManager(conn).transaction():
        v27.run(conn)
        set_schema_version(conn, 27)
        v28.run(conn)
        set_schema_version(conn, 28)
    template = conn.execute("INSERT INTO PartOperations(part_no,seq,op_type_name,source,setup_hours,unit_hours) "
                            "VALUES ('P1',1,'Turning','internal',0,1)").lastrowid
    case = JobCase(conn)
    case.batch("B3")
    case.op_id = TemplateLineageWriter(conn).copy_template("B3", template)
    conn.commit()
    case.plan(2, [case.op_id], start="2026-09-10T13:00:00", end="2026-09-10T16:00:00")
    with Flask(__name__).app_context():
        draft = create(case, {"base": {"plan_ref": case.plan_ref(2)}}, key="v28-retained-draft-0001")
        result = service(conn).save(draft["draft_ref"], {"name": "Retain pre-upgrade scene"},
                                    draft["write_context"]["write_token"], "v28-retained-scene-0001")
        assert result["ok"] is True
    assert hashlib.sha256(FIXTURE_V28.read_bytes()).hexdigest() == FIXTURE_V28_SHA
    with connect(":memory:") as expected:
        expected.executescript(FIXTURE_V28.read_text(encoding="utf-8"))
        assert list(map(canonical_object, source_ddl(conn))) == list(map(canonical_object, source_ddl(expected)))
    return conn

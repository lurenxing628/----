"""AV-owned, temporary file SQLite fixtures with actual AJ and AS inputs."""

import sqlite3
from datetime import datetime

import pytest
from flask import Flask

from core.infrastructure.workbench_execution_ledger_schema import install_execution_ledger
from core.infrastructure.workbench_metadata_schema import install_metadata
from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from core.infrastructure.workbench_run_schema import install_workbench_run_schema
from core.models.workbench_command import canonical_json
from core.services.scheduler.config.config_field_spec import default_snapshot_values
from core.services.workbench.preflight import PreflightService
from core.services.workbench.run_jobs import WorkbenchRunService
from tests.workbench.test_run_compute_support import RunCase
from web.public_token_registry import issue_public_token_with_expiry
from web.routes.workbench.preflight import INPUT_SCOPE, resolve_preflight_input
from web.routes.workbench.write_context import issue_write_context, validate_write_context


def connection(path):
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def service(conn, enabled=True):
    return WorkbenchRunService(conn, integration_enabled=enabled, input_resolver=resolve_preflight_input,
        context_factory=issue_write_context, context_validator=validate_write_context,
        clock=lambda: datetime(2026, 9, 10, 12))


class JobCase(RunCase):
    def preflight(self, settings=None, ttl=900):
        data, fingerprint = PreflightService(self.conn).evaluate(settings or self.settings())
        bound = {"input": data["normalized_input"], "scope": data["scope"], "fingerprint": fingerprint}
        return issue_public_token_with_expiry(INPUT_SCOPE, canonical_json(bound), ttl_seconds=ttl)[0]

    def intent(self, settings=None):
        ref = self.preflight(settings)
        preview = service(self.conn).preview(ref)
        assert preview["write_context"]["capabilities"]["scheduling.run"] is True
        return ref, preview["write_context"]["write_token"]

    def accept(self, key="run-request-00000001", settings=None):
        ref, token = self.intent(settings)
        return service(self.conn).accept(ref, token, key)


@pytest.fixture(name="job_case")
def job_case(schema_conn, tmp_path):
    path = tmp_path / "run-jobs.sqlite"
    conn = connection(path)
    schema_conn.backup(conn)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN IMMEDIATE")
    install_metadata(conn)
    install_plan_identity(conn)
    install_execution_ledger(conn)
    install_workbench_run_schema(conn)
    conn.commit()
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.path = path
    case.batch("B1")
    case.op_id = case.operation()
    case.config(algo_mode="greedy", graph_candidate_weight_count=3, time_budget_seconds=60,
                ortools_enabled="no", freeze_window_enabled="no")
    case.app = Flask(__name__)
    with case.app.app_context():
        yield case
    conn.close()

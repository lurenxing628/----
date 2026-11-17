"""AV-owned, temporary file SQLite fixtures with actual AJ and AS inputs."""

from datetime import date, datetime
from types import MappingProxyType

import pytest
from flask import Flask

from core.infrastructure.connection_guards import main_database_path
from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.services.workbench.facts.run_data_context import RunDataContext
from core.services.workbench.facts.system_journal import system_journal_directory
from core.services.workbench.run.jobs import WorkbenchRunService
from core.services.workbench.run.preflight import PreflightService
from core.shared.refs import new_ref
from tests._support.sqlite_connection import open_test_connection
from tests.workbench.run_compute_support import RunCase
from web.public_token_registry import issue_public_token_with_expiry
from web.routes.workbench.preflight import INPUT_SCOPE, evaluate_preflight_input_prepared
from web.routes.workbench.write_context import issue_write_context, validate_write_context
from web.runtime_host import install_wall_clock


def connection(path):
    return open_test_connection(path, timeout=15)


def data_context(conn):
    return RunDataContext(conn, system_journal_directory(main_database_path(conn)))


# 排产服务的应用钟；受理预览由路由在入口取一次时传入，测试直接调用时传同一个时刻。
RUN_NOW = datetime(2026, 9, 10, 12)


def service(conn, enabled=True, *, clock=lambda: RUN_NOW):
    return WorkbenchRunService(conn, integration_enabled=enabled, input_resolver=evaluate_preflight_input_prepared,
        context_factory=issue_write_context, context_validator=validate_write_context,
        clock=clock, data_context=data_context(conn))


class JobCase(RunCase):
    def preflight(self, settings=None, ttl=900):
        data, fingerprint = PreflightService(self.conn).evaluate(settings or self.settings(), material_day=date.today().isoformat())
        bound = {"input": data["normalized_input"], "scope": data["scope"], "fingerprint": fingerprint,
                 "check_ref": new_ref()}
        return issue_public_token_with_expiry(INPUT_SCOPE, MappingProxyType(bound), key=bound["check_ref"], group=fingerprint, ttl_seconds=ttl)[0]

    def intent(self, settings=None):
        ref = self.preflight(settings)
        preview = service(self.conn).preview(ref, now=RUN_NOW)
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
    # Existing candidate/locked-plan fixtures use an explicit 08:00-16:00 shift.
    conn.execute("INSERT INTO WorkbenchCalendarDefaults(singleton,periods_json) VALUES (1,?)",
                 ('[{"start":"08:00","end":"16:00","day_offset":0}]',))
    conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
    conn.execute("INSERT INTO Machines(machine_id,name) VALUES ('M1','Lathe')")
    conn.execute("INSERT INTO MachineOpTypes(machine_id,op_type_id) VALUES ('M1','T1')")
    conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
    conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
    for key, value in default_snapshot_values().items():
        conn.execute("INSERT OR REPLACE INTO ScheduleConfig(config_key,config_value) VALUES (?,?)", (key, str(value)))
    case = JobCase(conn)
    case.path = path
    case.batch("B1")
    case.op_id = case.operation()
    case.config(algo_mode="greedy", time_budget_seconds=60, freeze_window_enabled="no")
    case.app = Flask(__name__)
    install_wall_clock(case.app, datetime.now)
    case.app.config["WORKBENCH_SYSTEM_JOURNAL_DIR"] = system_journal_directory(str(path))
    with case.app.app_context():
        yield case
    conn.close()

"""Fresh application startup makes the first real run independent of old config pages."""

import pytest

from core.errors import ValidationError
from core.infrastructure.database import get_connection
from core.services.scheduler.config.config_service import ConfigService
from core.services.workbench.run.input_config import configuration_snapshot
from core.services.workbench.run.worker import WorkbenchRunWorker
from data.repositories.config_repo import ConfigRepository
from tests.workbench.run_jobs_support import JobCase


def create_application():
    from app import create_app

    return create_app()


def config_rows(conn):
    return [tuple(row) for row in conn.execute("SELECT * FROM ScheduleConfig ORDER BY config_key")]


def test_fresh_application_first_real_worker_run_needs_no_config_page(db_env):
    conn = get_connection(db_env)
    try:
        assert conn.execute("SELECT COUNT(*) FROM ScheduleConfig").fetchone()[0] == 0
        app = create_application()
        assert configuration_snapshot(conn).sort_strategy == ConfigService.DEFAULT_SORT_STRATEGY
        assert ConfigService(conn).get_active_preset() == ConfigService.BUILTIN_PRESET_DEFAULT
        initialized = config_rows(conn)
        conn.execute("INSERT INTO OpTypes(op_type_id,name) VALUES ('T1','Turning')")
        conn.execute("INSERT INTO Machines(machine_id,name,op_type_id) VALUES ('M1','Lathe','T1')")
        conn.execute("INSERT INTO Operators(operator_id,name) VALUES ('O1','Operator')")
        conn.execute("INSERT INTO OperatorMachine(operator_id,machine_id) VALUES ('O1','M1')")
        conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P1','Part')")
        case = JobCase(conn)
        case.batch("B1")
        case.operation()
        conn.commit()
        with app.app_context():
            accepted = case.accept(settings=case.settings(hold_window=None))
            outcome = WorkbenchRunWorker(conn).execute(accepted["run_ref"])
        assert outcome["state"] == "complete" and outcome["result_persisted"] is True
        assert outcome["candidates"]
        assert conn.execute("SELECT COUNT(*) FROM WorkbenchRunCandidateTasks").fetchone()[0] > 0
        assert config_rows(conn) == initialized
        create_application()
        assert config_rows(conn) == initialized
    finally:
        conn.close()


@pytest.mark.parametrize("damage", ["missing", "invalid"])
def test_restart_preserves_existing_missing_or_invalid_configuration(db_env, damage):
    create_application()
    conn = get_connection(db_env)
    try:
        if damage == "missing":
            conn.execute("DELETE FROM ScheduleConfig WHERE config_key='sort_strategy'")
        else:
            conn.execute("UPDATE ScheduleConfig SET config_value='bad-strategy' WHERE config_key='sort_strategy'")
        conn.commit()
        before = config_rows(conn)
        create_application()
        assert config_rows(conn) == before
        with pytest.raises(ValidationError) as exc:
            configuration_snapshot(conn)
        assert exc.value.field == "sort_strategy"
    finally:
        conn.close()


def test_failed_startup_bootstrap_rolls_back_defaults_and_provenance(db_env, monkeypatch):
    def fail_preset_write(*_args, **_kwargs):
        raise RuntimeError("startup preset write failed")

    monkeypatch.setattr(ConfigRepository, "set", fail_preset_write)
    with pytest.raises(RuntimeError, match="startup preset write failed"):
        create_application()
    conn = get_connection(db_env)
    try:
        assert config_rows(conn) == []
    finally:
        conn.close()

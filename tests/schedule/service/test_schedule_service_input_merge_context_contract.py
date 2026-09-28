"""A missing batch context blocks scheduling; public legacy event shapes remain sanitized."""

import pytest

from core.errors import ValidationError
from core.services.scheduler import ConfigService, ScheduleService
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary
from tests.workbench.process_query_support import seed_process


def test_schedule_service_stops_before_compute_or_persistence_when_context_missing(schema_conn, monkeypatch):
    import core.services.scheduler.schedule_service as module

    conn = schema_conn
    seed_process(conn)
    conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_name,source,ext_days) "
                 "VALUES('MISSING-CONTEXT','PROC-B',20,'热处理','external',2.5)")
    conn.execute("DELETE FROM BatchExternalContexts")
    conn.commit()
    ConfigService(conn).restore_default()

    def forbidden(*args, **kwargs):
        pytest.fail("Missing external facts must stop before computing or saving a plan")

    monkeypatch.setattr(module, "orchestrate_schedule_run", forbidden)
    monkeypatch.setattr(module, "persist_schedule", forbidden)
    with pytest.raises(ValidationError) as error:
        ScheduleService(conn).run_schedule(["PROC-B"], start_dt="2026-10-01 08:00:00",
                                          enforce_ready=False, strict_mode=False)
    assert error.value.field == "external_context"
    assert conn.execute("SELECT COUNT(*) FROM Schedule").fetchone()[0] == 0


def test_public_algo_summary_rejects_non_list_degradation_event_shapes() -> None:
    public_algo, diagnostics = project_public_algo_summary(
        {
            "input_contract": {
                "degraded": True,
                "degradation_events": {"code": "external_group_missing", "sample": "ext_group_id=SECRET"},
            },
            "merge_context_events": {"code": "external_group_missing", "sample": "ext_group_id=SECRET"},
        }
    )

    assert public_algo["input_contract"]["degradation_events"] == []
    assert public_algo["merge_context_events"] == []
    assert diagnostics == {}

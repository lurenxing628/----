"""无可重排 POST 保留错误 flash 和原数据；退役 GET 不得被当成排产成功。"""

from __future__ import annotations

from tests._support.gantt_retirement import _business_state
from tests._support.schedule_retirement import initialize_read_fixture


def test_scheduler_run_no_reschedulable_flash(app_client, monkeypatch) -> None:
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.schedule_service import ScheduleService

    calls = []

    def _fake_run_schedule(
        self,
        batch_ids,
        start_dt=None,
        end_date=None,
        created_by=None,
        simulate=False,
        enforce_ready=None,
        run_time_budget_seconds=None,
        strict_mode=False,
    ):
        calls.append((list(batch_ids), start_dt, simulate))
        raise ValidationError("所选批次没有可重排工序，本次未执行排产。", field="排产")

    monkeypatch.setattr(ScheduleService, "run_schedule", _fake_run_schedule)

    client = app_client
    initialize_read_fixture(client.application)
    before = _business_state(client)
    resp = client.post(
        "/scheduler/run",
        data={"batch_ids": ["B001"], "start_dt": "2026-01-01 08:00:00"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/scheduler/"
    assert calls == [(["B001"], "2026-01-01 08:00:00", False)]
    with client.session_transaction() as session:
        messages = list(session.get("_flashes", []))
    assert ("error", "所选批次没有可重排工序，本次未执行排产。") in messages
    assert not any("排产完成（版本" in message for _category, message in messages)
    landing = client.get(resp.headers["Location"])
    assert landing.status_code == 410
    landing_body = landing.get_data(as_text=True)
    assert "没有跳转，也没有丢掉任何条件" in landing_body
    assert "所选批次没有可重排工序，本次未执行排产。" in landing_body
    assert "排产完成（版本" not in landing_body
    assert "Location" not in landing.headers
    assert _business_state(client) == before

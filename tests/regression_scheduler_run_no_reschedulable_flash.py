"""回归测试：当 ScheduleService.run_schedule 抛 ValidationError(无可重排工序) 时，POST /scheduler/run 跟随重定向后应返回 200 并在正式排产页面回显该业务错误提示，绝不误报“排产完成（版本…”。"""

from __future__ import annotations


def test_scheduler_run_no_reschedulable_flash(app_client, monkeypatch) -> None:
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.schedule_service import ScheduleService

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
        raise ValidationError("所选批次没有可重排工序，本次未执行排产。", field="排产")

    monkeypatch.setattr(ScheduleService, "run_schedule", _fake_run_schedule)

    client = app_client
    resp = client.post(
        "/scheduler/run",
        data={"batch_ids": ["B001"], "start_dt": "2026-01-01 08:00:00"},
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200, f"/scheduler/run follow_redirects 后应返回 200：{resp.status_code}"
    assert "所选批次没有可重排工序，本次未执行排产。" in body, "正式排产页面未展示业务错误提示"
    assert "排产完成（版本" not in body, "正式排产页面不应误报成功"

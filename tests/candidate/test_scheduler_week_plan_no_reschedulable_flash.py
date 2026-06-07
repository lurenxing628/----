"""回归测试：当 ScheduleService.run_schedule 抛「所选批次没有可重排工序，本次未执行模拟排产。」的 ValidationError 时，POST /scheduler/simulate 重定向回批次页 /scheduler（不跳转 /scheduler/gantt），并在页面 flash 出该业务错误、不误报「模拟排产完成：生成版本」。"""

from __future__ import annotations


def test_scheduler_week_plan_no_reschedulable_flash(app_client, monkeypatch) -> None:
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
        raise ValidationError("所选批次没有可重排工序，本次未执行模拟排产。", field="排产")

    monkeypatch.setattr(ScheduleService, "run_schedule", _fake_run_schedule)

    client_redirect = app_client
    redirect_resp = client_redirect.post(
        "/scheduler/simulate",
        data={"batch_ids": ["B001"], "start_dt": "2026-01-01 08:00:00"},
        follow_redirects=False,
    )
    location = str(redirect_resp.headers.get("Location") or "")
    assert redirect_resp.status_code in (301, 302), f"模拟排产失败后应重定向：{redirect_resp.status_code}"
    assert "/scheduler/gantt" not in location, f"空执行失败后不应跳转到甘特图：{location!r}"

    client = app_client.application.test_client()
    resp = client.post(
        "/scheduler/simulate",
        data={"batch_ids": ["B001"], "start_dt": "2026-01-01 08:00:00"},
        follow_redirects=True,
    )
    body = resp.get_data(as_text=True)
    final_path = str(getattr(getattr(resp, "request", None), "path", "") or "")

    assert resp.status_code == 200, f"/scheduler/simulate follow_redirects 后应返回 200：{resp.status_code}"
    assert "所选批次没有可重排工序，本次未执行模拟排产。" in body, "模拟排产页面未展示业务错误提示"
    assert "模拟排产完成：生成版本" not in body, "模拟排产页面不应误报成功"
    if final_path:
        assert final_path.rstrip("/") == "/scheduler", f"空执行失败后应回到批次页：{final_path!r}"

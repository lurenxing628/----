"""回归测试：首页排产生成时间走公开口径 format_public_datetime——正常 DB 时间显示「X年X月X日 HH:MM」，脏 schedule_time 显示「时间记录异常」且裸串绝不泄漏到页面（dashboard 曾是全仓唯一裸渲染 schedule_time 的模板）。

fusion-dashboard-cockpit：「当前查看排产」卡退役后，排产生成时间统一由壳层「计划上下文胶囊」
的 generated_at_label 承载（latest_plan_context 喂 generated_at → format_public_datetime），
下列断言经胶囊命中——时间诚实降级口径不变。"""

from __future__ import annotations


def _assert_status(resp, name: str, expect: int = 200) -> None:
    if resp.status_code != expect:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"{name} 返回 {resp.status_code}，期望 {expect}，body={body[:500]}")


def _seed_history(db_path: str, schedule_time: str) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        # schedule_time 列平时靠 DB 默认值生成，这里显式给列才能播种坏值
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by, schedule_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "priority_first", 0, 0, "success", "{}", "reg", schedule_time),
        )
        conn.commit()
    finally:
        conn.close()


def test_dashboard_schedule_time_normal_value_uses_public_format(app_client, db_path) -> None:
    _seed_history(db_path, "2026-05-05 10:00:00")

    resp = app_client.get("/")
    _assert_status(resp, "GET /")

    html = resp.data.decode("utf-8", errors="ignore")
    if "2026年5月5日 10:00" not in html:
        raise RuntimeError("首页排产时间未走公开口径格式化")
    if "2026-05-05 10:00:00" in html:
        raise RuntimeError("首页泄漏了 DB 原始时间串")


def test_dashboard_schedule_time_dirty_value_shows_honest_error(app_client, db_path) -> None:
    _seed_history(db_path, "debug raw garbage")

    resp = app_client.get("/")
    _assert_status(resp, "GET /")

    html = resp.data.decode("utf-8", errors="ignore")
    if "Internal Server Error" in html or "Traceback" in html:
        raise RuntimeError("脏 schedule_time 导致首页报错而非诚实降级")
    if "debug raw garbage" in html:
        raise RuntimeError("脏 schedule_time 裸串泄漏到首页展示")
    if "时间记录异常" not in html:
        raise RuntimeError("脏 schedule_time 未显示「时间记录异常」诚实口径")

"""工作日历拒绝非有限效率。"""


def _expect_validation_error(fn, title: str) -> None:
    from core.errors import ValidationError

    ok = False
    try:
        fn()
    except ValidationError:
        ok = True
    assert ok, f"{title}：应抛出 ValidationError"


def test_scheduler_reject_nonfinite_and_invalid_status(db_path) -> None:
    from core.infrastructure.database import get_connection
    from core.services.scheduler.calendar.service import CalendarService

    conn = get_connection(db_path)
    try:
        cal_svc = CalendarService(conn, logger=None)
        _expect_validation_error(
            lambda: cal_svc._admin._build_work_calendar(
                date_value="2026-02-01",
                day_type="workday",
                shift_hours=8,
                efficiency="inf",
                allow_normal="yes",
                allow_urgent="yes",
            ),
            "CalendarAdmin._build_work_calendar(efficiency=inf)",
        )
    finally:
        conn.close()

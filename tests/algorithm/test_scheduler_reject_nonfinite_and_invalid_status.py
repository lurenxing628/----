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
    from core.services.scheduler.calendar.admin import CalendarAdmin

    conn = get_connection(db_path)
    try:
        admin = CalendarAdmin(conn, logger=None)
        _expect_validation_error(
            lambda: admin.build_work_calendar_from_payload(
                {
                    "date": "2026-01-02",
                    "day_type": "workday",
                    "periods": [{"start": "08:00", "end": "16:00", "day_offset": 0}],
                    "efficiency": float("inf"),
                    "allow_normal": "yes",
                    "allow_urgent": "yes",
                    "remark": None,
                },
                context=admin.normalization_context(),
            ),
            "CalendarAdmin.build_work_calendar_from_payload(efficiency=inf)",
        )
    finally:
        conn.close()

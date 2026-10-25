"""Bad-time samples retain public locations without exposing raw stored values."""

from core.services.scheduler._sched_display_utils import bad_time_row_sample


def test_bad_time_sample_keeps_public_location_and_hides_raw_time_and_internal_ids():
    row = {"schedule_id": 17, "op_id": 23, "op_code": "OP-B001-10", "batch_id": "B001",
           "start_time": "2026-03-02 99:00:00", "end_time": "2026-03-02 13:00:00"}
    sample = bad_time_row_sample(row)
    assert sample is not None
    assert "工序编码=OP-B001-10" in sample and "批次号=B001" in sample and "字段=开始时间" in sample
    assert all(value not in sample for value in ("排程记录编号=17", "工序编号=23", "99:00:00", "start_time", "end_time"))

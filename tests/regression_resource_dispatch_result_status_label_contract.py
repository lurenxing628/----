"""回归测试：当 ScheduleHistory.result_status 为 failed 或 simulated 时，资源派工的 plan_identity 不得被标成正式采用方案——label 为不可执行正式方案、kind_label 为只能查看的方案、can_dispatch 与 can_write_feedback 均为 False，且 guardrail_text 说明排产结果状态。"""

from __future__ import annotations

from pathlib import Path

from tests.regression_scheduler_dispatch_plan_identity_guardrails import VERSION, _dispatch_payload, _seed_db


def test_failed_or_simulated_official_result_is_not_labeled_current_official(tmp_path: Path) -> None:
    conn = _seed_db(tmp_path)
    try:
        for result_status in ("failed", "simulated"):
            conn.execute(
                "UPDATE ScheduleHistory SET result_status = ? WHERE version = ?",
                (result_status, VERSION),
            )
            conn.commit()

            identity = _dispatch_payload(conn, version=VERSION)["plan_identity"]

            assert identity["label"] == "不可执行正式方案"
            assert identity["kind_label"] == "只能查看的方案"
            assert identity["can_dispatch"] is False
            assert identity["can_write_feedback"] is False
            assert "排产结果状态" in identity["guardrail_text"]
            assert "正式采用方案" not in identity["label"]
            assert "正式采用方案" not in identity["kind_label"]
    finally:
        conn.close()

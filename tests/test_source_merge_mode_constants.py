from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.algorithms.value_domains import EXTERNAL, INTERNAL, MERGED, SEPARATE
from core.services.report.calculations import compute_downtime_impact, compute_utilization


def test_compute_utilization_only_counts_internal_source() -> None:
    schedule_rows = [
        {
            "source": INTERNAL,
            "start_time": "2026-03-01 08:00:00",
            "end_time": "2026-03-01 10:00:00",
            "machine_id": "MC1",
            "machine_name": "机床1",
            "operator_id": "OP1",
            "operator_name": "人员1",
        },
        {
            "source": EXTERNAL,
            "start_time": "2026-03-01 08:00:00",
            "end_time": "2026-03-01 12:00:00",
            "machine_id": "MC2",
            "machine_name": "机床2",
            "operator_id": "OP2",
            "operator_name": "人员2",
        },
    ]

    start_dt = datetime(2026, 3, 1, 0, 0, 0)
    end_dt_excl = datetime(2026, 3, 2, 0, 0, 0)

    by_machine, by_operator = compute_utilization(
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        cap_hours=24.0,
    )

    assert [r["machine_id"] for r in by_machine] == ["MC1"]
    assert [r["operator_id"] for r in by_operator] == ["OP1"]


def test_compute_downtime_impact_only_counts_internal_source() -> None:
    downtime_rows = [
        {
            "machine_id": "MC1",
            "machine_name": "机床1",
            "start_time": "2026-03-01 09:00:00",
            "end_time": "2026-03-01 11:00:00",
            "reason_code": "R1",
            "reason_detail": "test",
        }
    ]
    schedule_rows = [
        {
            "source": INTERNAL,
            "start_time": "2026-03-01 08:00:00",
            "end_time": "2026-03-01 10:00:00",
            "machine_id": "MC1",
        },
        {
            "source": EXTERNAL,
            "start_time": "2026-03-01 08:00:00",
            "end_time": "2026-03-01 12:00:00",
            "machine_id": "MC1",
        },
    ]

    start_dt = datetime(2026, 3, 1, 0, 0, 0)
    end_dt_excl = datetime(2026, 3, 2, 0, 0, 0)

    items = compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=schedule_rows,
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
    )

    assert len(items) == 1
    assert (items[0].get("machine_id") or "").strip() == "MC1"
    assert float(items[0].get("schedule_overlap_hours") or 0.0) > 0.0


def test_target_files_have_no_source_merge_mode_quoted_literals() -> None:
    """
    防漂移：这些文件里不应再出现 source/merge_mode 控制值的裸字符串字面量。
    （允许在错误提示文案中出现 internal/external 子串，因此只匹配带引号 token：'internal' / \"internal\"）
    """
    repo_root = Path(__file__).resolve().parents[1]
    targets = [
        repo_root / "core/services/scheduler/schedule_optimizer.py",
        repo_root / "core/services/scheduler/freeze_window.py",
        repo_root / "core/services/report/calculations.py",
        repo_root / "web/routes/process_parts.py",
        repo_root / "web/routes/process_excel_op_types.py",
    ]

    tokens = (INTERNAL, EXTERNAL, MERGED, SEPARATE)
    for p in targets:
        text = p.read_text(encoding="utf-8")
        for t in tokens:
            assert f"'{t}'" not in text, f"{p.as_posix()} 存在裸字符串 {t!r}"
            assert f'"{t}"' not in text, f"{p.as_posix()} 存在裸字符串 {t!r}"


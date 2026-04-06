import os
import sys
from datetime import datetime


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.services.report.calculations import compute_downtime_impact, compute_utilization

    upper_row = {
        "source": "INTERNAL",
        "machine_id": "M1",
        "machine_name": "机1",
        "operator_id": "O1",
        "operator_name": "人1",
        "start_time": "2026-01-01 08:00:00",
        "end_time": "2026-01-01 10:00:00",
    }
    lower_row = dict(upper_row, source="internal")
    start_dt = datetime(2026, 1, 1, 0, 0, 0)
    end_dt_excl = datetime(2026, 1, 2, 0, 0, 0)

    upper_machine, upper_operator = compute_utilization(
        schedule_rows=[upper_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        cap_hours=24.0,
    )
    lower_machine, lower_operator = compute_utilization(
        schedule_rows=[lower_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        cap_hours=24.0,
    )
    assert upper_machine == lower_machine, "compute_utilization 应对 source 大小写不敏感（machine）"
    assert upper_operator == lower_operator, "compute_utilization 应对 source 大小写不敏感（operator）"

    downtime_rows = [
        {
            "machine_id": "M1",
            "machine_name": "机1",
            "start_time": "2026-01-01 09:00:00",
            "end_time": "2026-01-01 11:00:00",
            "reason_code": "maint",
            "reason_detail": "保养",
        }
    ]
    upper_downtime = compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=[upper_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
    )
    lower_downtime = compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=[lower_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
    )
    assert upper_downtime == lower_downtime, "compute_downtime_impact 应对 source 大小写不敏感"

    print("OK")


if __name__ == "__main__":
    main()

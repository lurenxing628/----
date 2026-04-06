import os
import sqlite3
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    with open(os.path.join(repo_root, "schema.sql"), "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.algorithms.evaluation import ScheduleMetrics, objective_score
    from core.services.scheduler.config_service import ConfigService

    metrics_a = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=10.0,
        makespan_hours=100.0,
        changeover_count=1,
        weighted_tardiness_hours=30.0,
    )
    metrics_b = ScheduleMetrics(
        overdue_count=1,
        total_tardiness_hours=20.0,
        makespan_hours=100.0,
        changeover_count=1,
        weighted_tardiness_hours=20.0,
    )

    assert objective_score("min_tardiness", metrics_a) < objective_score(
        "min_tardiness", metrics_b
    ), "min_tardiness 应优先选择总拖期更小的方案"
    assert objective_score("min_weighted_tardiness", metrics_b) < objective_score(
        "min_weighted_tardiness", metrics_a
    ), "min_weighted_tardiness 应优先选择加权拖期更小的方案"

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)

    cfg = ConfigService(conn)
    cfg.ensure_defaults()
    cfg.set_objective("min_weighted_tardiness")
    snap = cfg.get_snapshot()
    assert snap.objective == "min_weighted_tardiness", f"配置快照未保留新 objective：{snap.objective!r}"
    raw = cfg.get("objective")
    assert raw == "min_weighted_tardiness", f"配置仓储未落库新 objective：{raw!r}"

    print("OK")


if __name__ == "__main__":
    main()

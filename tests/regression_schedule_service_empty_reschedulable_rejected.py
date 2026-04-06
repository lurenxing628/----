import os
import sqlite3
import sys
from types import SimpleNamespace


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def load_schema(conn: sqlite3.Connection, repo_root: str) -> None:
    schema_path = os.path.join(repo_root, "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def _make_conn(repo_root: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    load_schema(conn, repo_root)
    return conn


def _batch_stub(batch_id: str, status: str = "pending") -> SimpleNamespace:
    return SimpleNamespace(
        batch_id=batch_id,
        status=status,
        priority="normal",
        due_date=None,
        ready_status="yes",
        ready_date=None,
        created_at=None,
        quantity=1,
        part_no="P001",
        part_name="测试件",
    )


def _terminal_ops(batch_id: str):
    return [
        SimpleNamespace(
            id=1,
            op_code=f"{batch_id}_10",
            batch_id=batch_id,
            seq=10,
            source="internal",
            machine_id="",
            operator_id="",
            supplier_id=None,
            setup_hours=1.0,
            unit_hours=0.0,
            ext_days=None,
            status="completed",
            op_type_name="工序A",
        ),
        SimpleNamespace(
            id=2,
            op_code=f"{batch_id}_20",
            batch_id=batch_id,
            seq=20,
            source="external",
            machine_id=None,
            operator_id=None,
            supplier_id="SUP001",
            setup_hours=0.0,
            unit_hours=0.0,
            ext_days=2.0,
            status="skipped",
            op_type_name="外协B",
        ),
    ]


def _run_case(
    repo_root: str,
    ScheduleService,
    ValidationError,
    *,
    captured,
    operations,
    simulate: bool,
    expected_message: str,
) -> None:
    conn = _make_conn(repo_root)
    try:
        svc = ScheduleService(conn)
        svc._get_batch_or_raise = lambda bid: _batch_stub(bid, "pending")  # type: ignore[assignment]
        svc.op_repo = SimpleNamespace(list_by_batch=lambda _bid: list(operations))  # type: ignore[assignment]

        def _unexpected_allocate_next_version():
            captured["allocate_next_version_calls"] = captured.get("allocate_next_version_calls", 0) + 1
            raise AssertionError("空执行场景不应分配新版本号")

        svc.history_repo.allocate_next_version = _unexpected_allocate_next_version  # type: ignore[assignment]

        try:
            svc.run_schedule(
                batch_ids=["B_EMPTY"],
                start_dt="2026-01-01 08:00:00",
                simulate=simulate,
                enforce_ready=True,
            )
            raise RuntimeError("空执行场景应抛出 ValidationError")
        except ValidationError as exc:
            message = getattr(exc, "message", str(exc))
            assert expected_message in message, f"空执行提示异常：{message!r}"

        assert captured.get("build_algo_operations_calls", 0) == 0, f"空执行不应构建算法输入：{captured!r}"
        assert captured.get("optimize_schedule_calls", 0) == 0, f"空执行不应调用优化器：{captured!r}"
        assert captured.get("persist_schedule_calls", 0) == 0, f"空执行不应进入持久化：{captured!r}"
        assert captured.get("allocate_next_version_calls", 0) == 0, f"空执行不应分配版本号：{captured!r}"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import core.services.scheduler.schedule_service as schedule_service_mod
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.schedule_service import ScheduleService

    captured = {}
    original_build_algo_operations = schedule_service_mod.build_algo_operations
    original_optimize_schedule = schedule_service_mod.optimize_schedule
    original_persist_schedule = schedule_service_mod.persist_schedule

    def _unexpected_build_algo_operations(*_args, **_kwargs):
        captured["build_algo_operations_calls"] = captured.get("build_algo_operations_calls", 0) + 1
        raise AssertionError("空执行场景不应构建算法输入")

    def _unexpected_optimize_schedule(*_args, **_kwargs):
        captured["optimize_schedule_calls"] = captured.get("optimize_schedule_calls", 0) + 1
        raise AssertionError("空执行场景不应调用优化器")

    def _unexpected_persist_schedule(*_args, **_kwargs):
        captured["persist_schedule_calls"] = captured.get("persist_schedule_calls", 0) + 1
        raise AssertionError("空执行场景不应进入持久化")

    schedule_service_mod.build_algo_operations = _unexpected_build_algo_operations
    schedule_service_mod.optimize_schedule = _unexpected_optimize_schedule
    schedule_service_mod.persist_schedule = _unexpected_persist_schedule
    try:
        captured.clear()
        _run_case(
            repo_root,
            ScheduleService,
            ValidationError,
            captured=captured,
            operations=_terminal_ops("B_EMPTY"),
            simulate=False,
            expected_message="所选批次没有可重排工序，本次未执行排产。",
        )

        captured.clear()
        _run_case(
            repo_root,
            ScheduleService,
            ValidationError,
            captured=captured,
            operations=[],
            simulate=False,
            expected_message="所选批次没有可重排工序，本次未执行排产。",
        )

        captured.clear()
        _run_case(
            repo_root,
            ScheduleService,
            ValidationError,
            captured=captured,
            operations=[],
            simulate=True,
            expected_message="所选批次没有可重排工序，本次未执行模拟排产。",
        )
    finally:
        schedule_service_mod.build_algo_operations = original_build_algo_operations
        schedule_service_mod.optimize_schedule = original_optimize_schedule
        schedule_service_mod.persist_schedule = original_persist_schedule

    print("OK")


if __name__ == "__main__":
    main()

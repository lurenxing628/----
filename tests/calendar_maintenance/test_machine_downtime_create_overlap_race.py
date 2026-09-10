"""守护停机录入查后插竞态修复契约（B13 录入侧）：create / create_by_scope 的 has_overlap 重叠检测
必须与写入同处一个 BEGIN IMMEDIATE 事务（写者串行化）。修复前检查在事务外，threaded 双请求
（各自连接）能同时通过检查、双双插入重叠段。行为测试用双线程双连接实测只能成一条；
结构合同用 AST 锁住“has_overlap 调用位于 begin_immediate=True 事务块内”。"""

from __future__ import annotations

import ast
import sqlite3
import threading
from pathlib import Path

from core.infrastructure.errors import BusinessError
from core.services.equipment.machine_downtime_service import MachineDowntimeService

SERVICE_PATH = Path(__file__).resolve().parents[2] / "core" / "services" / "equipment" / "machine_downtime_service.py"


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def test_concurrent_create_same_window_only_one_row_inserted(db_path) -> None:
    setup = _connect(db_path)
    try:
        setup.execute("INSERT INTO Machines(machine_id, name) VALUES ('MC_RACE', '竞态测试机')")
        setup.commit()
    finally:
        setup.close()

    barrier = threading.Barrier(2)
    results = {}

    def worker(name: str) -> None:
        conn = _connect(db_path)
        try:
            service = MachineDowntimeService(conn)
            barrier.wait(timeout=10)
            try:
                service.create("MC_RACE", "2026-07-01 08:00", "2026-07-01 12:00", reason_code="maintenance")
                results[name] = "created"
            except BusinessError as exc:
                results[name] = f"conflict:{exc}"
        except Exception as exc:  # noqa: BLE001 - 竞态测试必须把线程内异常带回主线程断言
            results[name] = f"error:{type(exc).__name__}:{exc}"
        finally:
            conn.close()

    threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    verify = _connect(db_path)
    try:
        row_count = verify.execute(
            "SELECT COUNT(*) FROM MachineDowntimes WHERE machine_id = 'MC_RACE' AND status = 'active'"
        ).fetchone()[0]
    finally:
        verify.close()

    outcomes = sorted(results.values())
    assert len(outcomes) == 2, f"两个线程都必须有结局：{results}"
    assert row_count == 1, f"重叠窗口并发创建只能成一条，实际 {row_count} 条；结局={results}"
    assert sum(1 for o in outcomes if o == "created") == 1, f"必须恰好一个成功：{results}"
    assert sum(1 for o in outcomes if o.startswith("conflict:")) == 1, f"另一个必须以重叠冲突拒绝：{results}"


def _is_immediate_tx_call(expr: ast.AST) -> bool:
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    if not (isinstance(func, ast.Attribute) and func.attr == "transaction"):
        return False
    for keyword in expr.keywords:
        if keyword.arg == "begin_immediate" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
            return True
    return False


def _collect_has_overlap_flags(node: ast.AST, inside_immediate: bool, hits) -> None:
    if isinstance(node, ast.With):
        inside = inside_immediate or any(_is_immediate_tx_call(item.context_expr) for item in node.items)
        for item in node.items:
            _collect_has_overlap_flags(item.context_expr, inside_immediate, hits)
        for child in node.body:
            _collect_has_overlap_flags(child, inside, hits)
        return
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "has_overlap":
        hits.append(inside_immediate)
    for child in ast.iter_child_nodes(node):
        _collect_has_overlap_flags(child, inside_immediate, hits)


def test_overlap_check_sits_inside_begin_immediate_transaction_contract() -> None:
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"), filename=str(SERVICE_PATH))
    class_node = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MachineDowntimeService"
    )
    for func_name in ("create", "create_by_scope"):
        func_node = next(
            node
            for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == func_name
        )
        hits = []
        _collect_has_overlap_flags(func_node, False, hits)
        assert hits, f"{func_name} 必须保留 has_overlap 重叠检测"
        assert all(hits), (
            f"{func_name} 的 has_overlap 检测必须全部位于 tx_manager.transaction(begin_immediate=True) 事务块内，"
            "否则查后插竞态回归（B13）"
        )

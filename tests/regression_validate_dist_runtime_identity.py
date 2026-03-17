"""
回归测试：validate_dist_exe 运行时实例身份证明契约。

验证点：
1) 运行时契约必须同时包含 host / port / db_path 三个文件。
2) 启动前会清理陈旧 runtime 契约文件。
3) 仅有 host / port 时，不得被误判为可用实例。
4) 若进程在契约完整前或关键检查后提前退出，验收必须失败。
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import threading
import time
from pathlib import Path


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _load_module(repo_root: str):
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    sys.modules.pop("validate_dist_exe", None)
    return importlib.import_module("validate_dist_exe")


class _DummyProc:
    def __init__(self, exit_code=None) -> None:
        self.exit_code = exit_code

    def poll(self):
        return self.exit_code


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_contract(log_dir: Path, host: str, port: int, db_path: str) -> None:
    _write_text(log_dir / "aps_host.txt", host + "\n")
    _write_text(log_dir / "aps_port.txt", str(port) + "\n")
    _write_text(log_dir / "aps_db_path.txt", db_path + "\n")


def main() -> None:
    repo_root = find_repo_root()
    mod = _load_module(repo_root)

    runtime_dir = Path(tempfile.mkdtemp(prefix="aps_validate_identity_contract_"))
    log_dir = runtime_dir / "logs"
    db_path = runtime_dir / "aps.db"
    db_path.write_text("", encoding="utf-8")
    _write_contract(log_dir, "127.0.0.1", 5720, str(db_path))

    contract = mod._read_runtime_contract(str(log_dir))
    _assert(contract is not None, "完整的 host/port/db 契约应可被读取")
    _assert(contract[0] == "127.0.0.1", "读取到的 host 不正确")
    _assert(contract[1] == 5720, "读取到的 port 不正确")
    _assert(contract[2] == os.path.normcase(os.path.abspath(str(db_path))), "读取到的 db_path 未被规范化")

    mod._clear_runtime_contract_files(str(log_dir))
    _assert(not (log_dir / "aps_host.txt").exists(), "清理后不应残留 aps_host.txt")
    _assert(not (log_dir / "aps_port.txt").exists(), "清理后不应残留 aps_port.txt")
    _assert(not (log_dir / "aps_db_path.txt").exists(), "清理后不应残留 aps_db_path.txt")

    _write_text(log_dir / "aps_host.txt", "127.0.0.1\n")
    _write_text(log_dir / "aps_port.txt", "5721\n")
    _assert(mod._read_runtime_contract(str(log_dir)) is None, "缺少 db_path 时不应视为完整运行时契约")

    delayed_runtime_dir = Path(tempfile.mkdtemp(prefix="aps_validate_identity_wait_"))
    delayed_log_dir = delayed_runtime_dir / "logs"
    delayed_db_path = delayed_runtime_dir / "delayed.db"
    delayed_db_path.write_text("", encoding="utf-8")

    def _delayed_writer() -> None:
        _write_text(delayed_log_dir / "aps_host.txt", "127.0.0.1\n")
        _write_text(delayed_log_dir / "aps_port.txt", "5722\n")
        time.sleep(0.3)
        _write_text(delayed_log_dir / "aps_db_path.txt", str(delayed_db_path) + "\n")

    writer = threading.Thread(target=_delayed_writer, daemon=True)
    writer.start()
    t0 = time.time()
    waited_contract = mod._wait_for_runtime_contract(str(delayed_log_dir), _DummyProc(), timeout_s=1.5)
    waited_for_s = time.time() - t0
    writer.join(timeout=1.0)
    _assert(waited_for_s >= 0.2, "缺少 db_path 时应继续等待，不应只凭 host/port 提前通过")
    _assert(waited_contract[0] == "127.0.0.1", "等待得到的 host 不正确")
    _assert(waited_contract[1] == 5722, "等待得到的 port 不正确")
    _assert(waited_contract[2] == os.path.normcase(os.path.abspath(str(delayed_db_path))), "等待得到的 db_path 不正确")

    try:
        mod._wait_for_runtime_contract(str(Path(tempfile.mkdtemp(prefix="aps_validate_identity_exit_")) / "logs"), _DummyProc(exit_code=9), timeout_s=0.1)
        raise RuntimeError("进程提前退出时应拒绝等待结果")
    except RuntimeError as e:
        _assert("host/port/db 契约文件" in str(e), "进程提前退出时错误信息不正确")

    mod._assert_runtime_db_path(str(delayed_db_path))
    try:
        mod._assert_runtime_db_path(str(delayed_runtime_dir / "missing.db"))
        raise RuntimeError("不存在的 DB 路径应被拒绝")
    except RuntimeError as e:
        _assert("运行时 DB 文件不存在" in str(e), "缺失 DB 路径的错误信息不正确")

    try:
        mod._assert_process_running(_DummyProc(exit_code=3), "页面检查通过后进程已退出。")
        raise RuntimeError("进程提前退出时应被拒绝")
    except RuntimeError as e:
        _assert("页面检查通过后进程已退出" in str(e), "进程退出错误信息不正确")

    print("OK")


if __name__ == "__main__":
    main()

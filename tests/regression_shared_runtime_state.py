"""
回归测试：共享安装口径下的运行时状态目录与单活用户锁。

验证点：
1) 运行时 host/port/db/runtime.json 主写共享日志目录，而不是强依赖 runtime_dir/logs。
2) runtime_dir/logs 仍保留镜像文件，兼容旧工具链。
3) 同一路径下第二个 owner 会被 RuntimeLockError 阻止。
4) 释放运行时锁与删除契约文件后，状态目录可重新使用。
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
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


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    sys.modules.pop("web.bootstrap.launcher", None)
    launcher = importlib.import_module("web.bootstrap.launcher")

    runtime_dir = Path(tempfile.mkdtemp(prefix="aps_runtime_shared_runtime_"))
    shared_log_dir = Path(tempfile.mkdtemp(prefix="aps_runtime_shared_logs_"))
    db_path = runtime_dir / "db" / "aps.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.write_text("", encoding="utf-8")
    backup_dir = runtime_dir / "backups"
    excel_template_dir = runtime_dir / "templates_excel"

    lock_payload = launcher.acquire_runtime_lock(
        str(runtime_dir),
        str(shared_log_dir),
        owner="DOMAIN\\userA",
        exe_path=str(runtime_dir / "aps.exe"),
    )
    _assert(bool(lock_payload), "首次获取共享运行时锁应成功")
    _assert((shared_log_dir / "aps_runtime.lock").exists(), "共享日志目录应存在运行时锁文件")

    launcher.write_runtime_host_port_files(
        runtime_dir=str(runtime_dir),
        cfg_log_dir=str(shared_log_dir),
        host="0.0.0.0",
        port=5731,
        db_path=str(db_path),
    )
    launcher.write_runtime_contract_file(
        str(runtime_dir),
        "0.0.0.0",
        5731,
        db_path=str(db_path),
        shutdown_token="shared-runtime-token",
        ui_mode="default",
        log_dir=str(shared_log_dir),
        backup_dir=str(backup_dir),
        excel_template_dir=str(excel_template_dir),
        exe_path=str(runtime_dir / "aps.exe"),
        owner="DOMAIN\\userA",
    )

    _assert((shared_log_dir / "aps_host.txt").exists(), "共享日志目录应存在 aps_host.txt")
    _assert((shared_log_dir / "aps_port.txt").exists(), "共享日志目录应存在 aps_port.txt")
    _assert((shared_log_dir / "aps_db_path.txt").exists(), "共享日志目录应存在 aps_db_path.txt")
    _assert((shared_log_dir / "aps_runtime.json").exists(), "共享日志目录应存在 aps_runtime.json")

    runtime_log_dir = runtime_dir / "logs"
    _assert((runtime_log_dir / "aps_host.txt").exists(), "runtime_dir/logs 应保留 aps_host.txt 镜像")
    _assert((runtime_log_dir / "aps_port.txt").exists(), "runtime_dir/logs 应保留 aps_port.txt 镜像")
    _assert((runtime_log_dir / "aps_db_path.txt").exists(), "runtime_dir/logs 应保留 aps_db_path.txt 镜像")
    _assert((runtime_log_dir / "aps_runtime.json").exists(), "runtime_dir/logs 应保留 aps_runtime.json 镜像")

    contract = launcher.read_runtime_contract(str(shared_log_dir))
    _assert(contract is not None, "共享日志目录中的运行时契约应可被读取")
    _assert(str(contract.get("owner") or "") == "DOMAIN\\userA", "owner 应写入运行时契约")
    _assert(str(contract.get("runtime_dir") or "") == os.path.abspath(str(runtime_dir)), "runtime_dir 不正确")
    data_dirs = contract.get("data_dirs") or {}
    _assert(str(data_dirs.get("log_dir") or "") == os.path.abspath(str(shared_log_dir)), "log_dir 应指向共享日志目录")

    blocked = False
    try:
        launcher.acquire_runtime_lock(
            str(runtime_dir),
            str(shared_log_dir),
            owner="DOMAIN\\userB",
            exe_path=str(runtime_dir / "aps.exe"),
        )
    except launcher.RuntimeLockError:
        blocked = True
    _assert(blocked, "第二个 owner 应被共享运行时锁阻止")

    launcher.release_runtime_lock(str(shared_log_dir))
    launcher.delete_runtime_contract_files(str(shared_log_dir))

    _assert(not (shared_log_dir / "aps_runtime.lock").exists(), "释放后不应残留共享运行时锁文件")
    _assert(not (shared_log_dir / "aps_runtime.json").exists(), "清理后不应残留共享运行时契约")

    reacquired = launcher.acquire_runtime_lock(
        str(runtime_dir),
        str(shared_log_dir),
        owner="DOMAIN\\userB",
        exe_path=str(runtime_dir / "aps.exe"),
    )
    _assert(bool(reacquired), "清理后应允许重新获取运行时锁")
    launcher.release_runtime_lock(str(shared_log_dir))
    print("OK")


if __name__ == "__main__":
    main()

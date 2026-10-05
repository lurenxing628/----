"""运行时宿主接缝：bootstrap 把进程级能力装进 app.extensions，routes 只从这里读取。

方向约束：web/bootstrap → web/routes 只允许 factory 装配蓝图；routes 绝不 import web.bootstrap。
两边共用的键名、恢复宿主契约和读取函数都放在这个 web 根模块里，它不依赖 routes 也不依赖 bootstrap。
"""

from __future__ import annotations

import hashlib
import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

RUNTIME_HOST_EXTENSION = "aps.runtime_host"
RESTORE_HOST_EXTENSION = "workbench_system_restore_host"
RESTORE_HOST_GUARD = "workbench_system_restore_guard"


def runtime_identity(app) -> Dict[str, Any]:
    raw_path = str(app.config.get("DATABASE_PATH") or "").strip()
    db_path = os.path.normcase(os.path.abspath(raw_path)) if raw_path else ""
    token = str(app.config.get("APS_RUNTIME_SHUTDOWN_TOKEN") or "")
    return {
        "pid": os.getpid(),
        "owner": str(app.config.get("APS_RUNTIME_OWNER") or ""),
        "db_path_hash": hashlib.sha256(db_path.encode("utf-8")).hexdigest() if db_path else "",
        "instance_id": hashlib.sha256(token.encode("utf-8")).hexdigest() if token else "",
    }


class SystemRestoreHost(ABC):
    """系统恢复宿主的最小契约；唯一实现是 web/bootstrap/workbench_system_restore.WorkbenchSystemRestoreHost。"""

    @property
    @abstractmethod
    def status(self) -> Dict[str, Any]: ...

    @abstractmethod
    def execute(self, service, *, request_key, intent, guard, audit, restore_runner): ...

    @abstractmethod
    def execute_file(self, service, *, request_key, action, intent, guard, audit): ...

    @abstractmethod
    def capture_maintenance_records(self): ...

    @abstractmethod
    def automatic_maintenance(self): ...

    @abstractmethod
    def audit_restore_result(self, result): ...


def install_runtime_host(app, *, request_shutdown: Callable[..., bool]) -> None:
    """由 factory 在建 app 时调用一次；request_shutdown(logger=None) -> bool 请求运行时 Server 关停。"""
    app.extensions[RUNTIME_HOST_EXTENSION] = {"request_shutdown": request_shutdown}


def request_shutdown(app, logger=None) -> bool:
    host = app.extensions.get(RUNTIME_HOST_EXTENSION)
    if not isinstance(host, dict) or not callable(host.get("request_shutdown")):
        raise RuntimeError("runtime host is not installed on this app")
    return bool(host["request_shutdown"](logger=logger))


def restore_host(app) -> Optional[SystemRestoreHost]:
    """两把钥匙指向同一个恢复宿主实例时才返回它；否则返回 None，表示恢复能力不可用。"""
    host = app.extensions.get(RESTORE_HOST_EXTENSION)
    if not isinstance(host, SystemRestoreHost) or app.extensions.get(RESTORE_HOST_GUARD) is not host:
        return None
    return host

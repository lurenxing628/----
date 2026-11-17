"""运行时宿主接缝：bootstrap 把进程级能力装进 app.extensions，routes 只从这里读取。

方向约束：web/bootstrap → web/routes 只允许 factory 装配蓝图；routes 绝不 import web.bootstrap。
两边共用的键名、恢复宿主契约和读取函数都放在这个 web 根模块里，它不依赖 routes 也不依赖 bootstrap。
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

RUNTIME_HOST_EXTENSION = "aps.runtime_host"
RESTORE_HOST_EXTENSION = "workbench_system_restore_host"
RESTORE_HOST_GUARD = "workbench_system_restore_guard"
RUNTIME_IDENTITY_EXTENSION = "aps.runtime_identity"
WALL_CLOCK_EXTENSION = "aps.wall_clock"


def normalize_runtime_db_path(db_path: Optional[str]) -> str:
    raw = str(db_path or "").strip()
    return os.path.normcase(os.path.abspath(raw)) if raw else ""


def runtime_identity(app) -> Dict[str, Any]:
    db_path = normalize_runtime_db_path(app.config["DATABASE_PATH"])
    identity = app.extensions.get(RUNTIME_IDENTITY_EXTENSION)
    if identity is None:
        identity = app.extensions.setdefault(RUNTIME_IDENTITY_EXTENSION, {
            "instance_id": uuid.uuid4().hex,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    return {
        "pid": os.getpid(),
        "owner": str(app.config.get("APS_RUNTIME_OWNER") or ""),
        "db_path": db_path,
        "instance_id": identity["instance_id"],
        "started_at": identity["started_at"],
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


def install_wall_clock(app, clock: Callable[[], datetime]) -> None:
    """工作台请求与排产作业共用的工厂本地墙钟，由 factory 建 app 时装一次。

    装的是可调用对象，返回无时区的工厂本地时间，每次取时都是真实时刻；请求读快照时刻、命令落时和
    作业起止都从这里取，下游服务不再各自核对时区。测试应用照 factory 的做法装自己的钟，不另开注入口。
    """
    app.extensions[WALL_CLOCK_EXTENSION] = clock


def wall_clock(app) -> Callable[[], datetime]:
    return app.extensions[WALL_CLOCK_EXTENSION]


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

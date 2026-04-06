"""
设备管理模块（Equipment）。

说明：
- 服务层只依赖 repositories，不在路由里写复杂业务逻辑
- 用户可见 message 尽量中文（便于 Win7 单机用户排障）
"""

from __future__ import annotations

from .machine_downtime_service import MachineDowntimeService
from .machine_service import MachineService

__all__ = ["MachineService", "MachineDowntimeService"]


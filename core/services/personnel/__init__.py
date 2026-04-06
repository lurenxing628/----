"""
人员管理模块（Personnel）。

说明：
- 服务层只依赖 repositories，不直接在路由里写复杂业务逻辑
- 用户可见 message 尽量中文（便于 Win7 单机用户排障）
"""

from __future__ import annotations

from .operator_machine_service import OperatorMachineService
from .operator_service import OperatorService
from .resource_team_service import ResourceTeamService

__all__ = ["OperatorService", "OperatorMachineService", "ResourceTeamService"]

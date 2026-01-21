"""
人员管理模块（Personnel）。

说明：
- 服务层只依赖 repositories，不直接在路由里写复杂业务逻辑
- 用户可见 message 尽量中文（便于 Win7 单机用户排障）
"""

from .operator_service import OperatorService
from .operator_machine_service import OperatorMachineService

__all__ = ["OperatorService", "OperatorMachineService"]


"""PyInstaller 冻结导入锚：core.services.scheduler lazy 导出的静态镜像。

背景（2026-07-19 盲区扫描 B08）：
- core/services/scheduler/__init__.py 的 _EXPORTS 走 __getattr__ +
  import_module(变量实参) 做 lazy 导出，源码态运行正常，但 PyInstaller 4.10
  的静态分析看不到这些动态导入，冻结包会漏掉服务模块，exe 启动即死。
- 本模块把 _EXPORTS 全部子模块（含 config 子包的 lazy 导出）显式静态 import
  一遍，只作冻结收集锚点；由 web/bootstrap/factory.py 的
  _PYINSTALLER_IMPORT_ANCHORS 静态引用，保证 PyInstaller 从 app.py 可达。
- 源码态行为零变化：web 启动路径本来就会在 factory 导入
  web.bootstrap.request_services 时立即导入全部服务；非 web 消费方不导入
  本模块，包级 lazy 语义保持不变（lazy 化取舍见 41ad409c）。

同步契约：__init__._EXPORTS（含 config/__init__._EXPORTS）新增或删除条目时，
必须同步本文件的静态 import 清单；
tests/gate_meta/test_frozen_bundle_contract.py 会做对账，漂移即红。
"""

from __future__ import annotations

import core.services.scheduler.batch_service as _batch_service
import core.services.scheduler.calendar_service as _calendar_service
import core.services.scheduler.config.config_page_outcome as _config_page_outcome
import core.services.scheduler.config.config_service as _config_service
import core.services.scheduler.gantt_adjustment_draft_service as _gantt_adjustment_draft_service
import core.services.scheduler.gantt_adjustment_publish_service as _gantt_adjustment_publish_service
import core.services.scheduler.gantt_adjustment_scenario_service as _gantt_adjustment_scenario_service
import core.services.scheduler.gantt_adjustment_validation_service as _gantt_adjustment_validation_service
import core.services.scheduler.gantt_service as _gantt_service
import core.services.scheduler.operation_execution_feedback_service as _operation_execution_feedback_service
import core.services.scheduler.resource_dispatch_actual_record_service as _resource_dispatch_actual_record_service
import core.services.scheduler.resource_dispatch_execution_service as _resource_dispatch_execution_service
import core.services.scheduler.resource_dispatch_service as _resource_dispatch_service
import core.services.scheduler.schedule_service as _schedule_service

FROZEN_IMPORT_ANCHORS = (
    _batch_service,
    _calendar_service,
    _config_page_outcome,
    _config_service,
    _gantt_adjustment_draft_service,
    _gantt_adjustment_publish_service,
    _gantt_adjustment_scenario_service,
    _gantt_adjustment_validation_service,
    _gantt_service,
    _operation_execution_feedback_service,
    _resource_dispatch_actual_record_service,
    _resource_dispatch_execution_service,
    _resource_dispatch_service,
    _schedule_service,
)

__all__ = ["FROZEN_IMPORT_ANCHORS"]

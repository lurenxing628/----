# 15 条懒导出 Warning 的最小提案

- 状态：Main 后续明确批准，已完成两文件最小实施。下文保留提案原文；实际静态声明追加到模块末尾，运行时代码不移动，结果见 `H-lazy-exports-fix-note-20260910.md`。两处 root 路径已先通过阶段消息报 Main。
- 范围仅为 `/Users/lurenxing/GitHub/----/core/services/scheduler/__init__.py`、`/Users/lurenxing/GitHub/----/core/services/scheduler/schedule_orchestrator.py`。
- 不展开默认 Pyright 的 2011 条 tests 诊断，不改配置、warning 等级、阈值、baseline、DTO、factory/host、算法或运行逻辑。

## 根因与具体修改

13 条来自 scheduler 包的 `__all__`，2 条来自旧 orchestrator 兼容转口的 `__all__`；它们实际由 `__getattr__` 懒加载提供，但缺少静态类型声明。详见 `H-preparation-20260910.md:45` 的逐条目标核对。

当前已有同类实现：`core/services/scheduler/config/__init__.py:4-8` 在 `TYPE_CHECKING` 中声明类，运行时仍通过 `_EXPORTS`/`__getattr__` 取真实对象。本提案沿用该模式，不引入 `.pyi` 或新依赖。

### Scheduler 包

在现有 `from importlib import import_module` 后、`_EXPORTS` 前加入：

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .batch_service import BatchService
    from .calendar_service import CalendarService
    from .config.config_service import ConfigService
    from .gantt_adjustment_draft_service import GanttAdjustmentDraftService
    from .gantt_adjustment_scenario_service import GanttAdjustmentScenarioService
    from .gantt_adjustment_publish_service import GanttAdjustmentPublishService
    from .gantt_adjustment_validation_service import GanttAdjustmentValidationService
    from .gantt_service import GanttService
    from .operation_execution_feedback_service import OperationExecutionFeedbackService
    from .resource_dispatch_actual_record_service import ResourceDispatchActualRecordService
    from .resource_dispatch_execution_service import ResourceDispatchExecutionService
    from .resource_dispatch_service import ResourceDispatchService
    from .schedule_service import ScheduleService
```

实际写入时按既有 Ruff import 排序排列。完整保留 `_EXPORTS`、13 项 `__all__`、`__getattr__` 的未知名字拒绝与 `globals()[name]` 缓存；不要把这 13 个 import 移到运行时顶层。

### 旧 Orchestrator 转口

把类型导入改为 `from typing import TYPE_CHECKING, Any, List`，在 `__all__` 前加入：

```python
if TYPE_CHECKING:
    from .run.schedule_orchestrator import (
        ScheduleOrchestrationOutcome,
        orchestrate_schedule_run,
    )
```

保留 `_TARGET_MODULE`、`__all__`（含现有 noqa）、`__getattr__`、`__dir__` 函数逻辑。不要包装成新类/新函数，不使用 `Any` 别名或 `cast` 假装是目标定义。

## 不变合同与风险

- `TYPE_CHECKING` 在普通 Python 3.8 运行时为 false，新增目标导入只供类型检查；访问导出仍返回同一目标模块里的同一对象，而不是代理/拷贝。实施后仍须实测，不以代码推理替代测试。
- `from core.services.scheduler import Name`、旧 orchestrator 路径与新路径对象身份必须用 `is` 对照；未知业务名字仍抛 `AttributeError`。
- 包导入不得提前拉起这 13 个实现模块。新进程分别先导入包、再取导出、先导入叶模块再访问旧路径，核对 `sys.modules` 与对象身份，避免同进程已有缓存掩盖 eager 导入。
- 新增 `TYPE_CHECKING` 守卫名不进入 `__all__`；`dir()` 可能多出这个内部类型守卫名。提案承诺公开导出集合和对象身份不变，不承诺模块内部名字全集逐字不变。
- 不动 `_frozen_import_anchor.py`、PyInstaller 锚点或构建 bat；已提交冻结导入合同继续作为独立验证，不因类型消警删掉锚点。
- 是否确实归零必须以实施后的产品 Pyright 为准。未找到这 15 条 warning 已经造成产品运行失败的证据；它们不是当前 full gate 必然失败项。

## Main 实施时验证

1. 在私有 `CHECKUP_CALLGRAPH` 下先用 symbol_locator 定位两处 `__getattr__` 与目标导出的影响面，不写共享调用图。遇到静态工具未识别模块级懒导出，补 fresh-process 运行验证，不把零边当无调用。
2. 两文件 Ruff、`.venv/bin/python -B -m pyright -p pyrightconfig.gate.json --outputjson`；预期消除这 15 条对应诊断，不能忽略其它真实 errors。
3. 现有 `tests/gate_meta/test_sp05_path_topology_contract.py`、`tests/schedule/service/test_schedule_orchestrator_contract.py`、`tests/gate_meta/test_frozen_bundle_contract.py`，加上述精确懒导出/对象身份合同。新增测试按真实 owner 收入登记，不用动态总数代替归属。
4. 生产及含 tests 的 import-cycle `--fail-on-new-cycle`，既有 baseline 不变；新 `TYPE_CHECKING` 边须按现有扫描语义处理，不调整扫描器来配合提案。
5. Main 归档提交后，在最终 HEAD 的完整 gate 中复核；此提案不授权 H 在早期 `c0097278` 上全跑。

所有临时运行、日志、测试库与调用图使用私有路径，不操作原预览。以上均为待实施命令，不冒充已跑结果。

## 当前源绑定

| 文件 | 本次只读 SHA-256 |
| --- | --- |
| `core/services/scheduler/__init__.py` | `544891a2608c4af6a9ac25e1be8f27a3fc4cb418d150fc31deff1853d2c8c7d0` |
| `core/services/scheduler/schedule_orchestrator.py` | `0d45aac24ffb8f8e4513c17bbd3381bbeb8d7989dc56ce79b622847bcb8c7a92` |
| `core/services/scheduler/config/__init__.py`（参考，只读） | `79a3bfab59b4f7776cbf8e5301397ccde7d1b22e8585c6fa8df974be90ee298c` |

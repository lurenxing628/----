## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [ ] 任务 1：补充根 README 与文档导航入口（解决 E1）  `#T01`
- [ ] 任务 2：补充开发依赖工具链（解决 D3）  `#T02`
- [ ] 任务 3：文档归档清理与事实源标注（解决 E2/E3/E4）  `#T03`
- [ ] 任务 4：白名单转治理台账（解决 C7）  `#T04`
- [ ] 任务 5：证据留痕主索引建立（解决 E5）  `#T05`
- [ ] 任务 6：调度服务目录子包化（解决 A1）  `#T06`
- [ ] 任务 7：GreedyScheduler.schedule() 方法拆分（解决 A3）  `#T07`
- [ ] 任务 8：算法层类型约束引入（解决 A4）  `#T08`
- [ ] 任务 9：兼容桥接代码清理（解决 A6）  `#T09`
- [ ] 任务 10：调度配置规则收敛 — 单一事实来源（解决 A2）  `#T10`
- [ ] 任务 11：database.py 拆分（解决 B1）  `#T11`
- [ ] 任务 12：仓储层读模型分离（解决 B2）  `#T12`
- [ ] 任务 13：路由子包化（解决 C1）  `#T13`
- [ ] 任务 14：Excel 导入通用流程抽象（解决 C2）  `#T14`
- [ ] 任务 15：双模板树收敛决策与执行（解决 C5）  `#T15`
- [ ] 任务 16：前端脚本初始化协议统一（解决 C4）  `#T16`
- [ ] 任务 17：测试分层目录建立与回归测试逐步标准化（解决 D1/D2）  `#T17`
- [ ] 任务 18：基础 CI 建设（解决 D4）  `#T18`
<!-- LIMCODE_TODO_LIST_END -->

# APS 排产系统技术债务综合修复计划

> **执行方式**：优先使用 `subagent-driven-development`；如果当前环境不适合子代理或用户要求当前会话直接执行，则使用 `executing-plans`。

**目标**：系统性修复两份技术债务审查报告中核实确认的全部问题，降低改动成本与维护复杂度。

**总体做法**：按 5 个治理主题（调度核心、数据基础设施、Web 界面层、测试体系、文档留存）分批推进，每个主题内的任务按风险和收益排序。每个任务完成后运行定向验证 + 全量回归门禁。

**涉及技术 / 模块**：
- `core/services/scheduler/` — 调度服务子包化、配置规则收敛、编排收敛
- `core/algorithms/greedy/` — 算法方法拆分、类型约束
- `core/infrastructure/` — 数据库基础设施拆分
- `core/models/` — 模型映射统一
- `data/repositories/` — 仓储层读模型分离
- `web/routes/` — 路由子包化、Excel 流程抽象
- `web/viewmodels/` — 页面装配规范
- `static/js/` — 前端脚本模块化
- `templates/` + `web_new_test/templates/` — 双模板树收敛
- `tests/` — 测试分层目录、回归测试标准化
- `开发文档/` + `audit/` + `evidence/` — 文档归档、事实源收敛
- 根目录 — 补充 README、CI 基建

---

## 核实确认的问题清单（排除 Win7/Python 3.8 不可变项后）

以下问题来自两份审查报告去重合并，共 **28 项**，按治理主题分组：

### 主题 A：调度服务核心治理（7 项）

| 编号 | 严重级别 | 问题 | 来源 |
|---|---|---|---|
| A1 | 高 | 排产调度服务目录过度膨胀（45 文件扁平） | 两份报告共识 |
| A2 | 高 | 调度配置规则多点复制（6 处相近逻辑） | 报告 2 |
| A3 | 高 | GreedyScheduler.schedule() 过于庞大（332 行） | 报告 1 |
| A4 | 中 | 算法层关键参数缺乏类型约束（List[Any]） | 报告 1 |
| A5 | 中 | 调度输入收集与编排扇出过大 / ScheduleService 12 仓储依赖 | 两份报告共识 |
| A6 | 中 | 核心调度链路长期兼容旧形态（桥接代码） | 报告 2 |
| A7 | 中 | 严格模式与降级状态横向扩散 | 报告 2 |

### 主题 B：数据基础设施治理（4 项）

| 编号 | 严重级别 | 问题 | 来源 |
|---|---|---|---|
| B1 | 高 | 数据库基础设施热点膨胀（database.py 533 行 + backup.py 377 行） | 报告 2 |
| B2 | 中 | 仓储层混入页面读模型查询 | 报告 2 |
| B3 | 中 | 手写模型映射样板与静默解析扩散 | 报告 2 |
| B4 | 中 | 迁移脚本持续承接业务语义清洗 | 报告 2 |

### 主题 C：Web 界面层治理（7 项）

| 编号 | 严重级别 | 问题 | 来源 |
|---|---|---|---|
| C1 | 中 | 路由层文件数量过多（59 文件扁平）| 两份报告共识 |
| C2 | 中 | 路由拆分后仍以重复流程维持（Excel 导入） | 报告 2 |
| C3 | 中 | 页面装配边界不一致（route/viewmodel 职责混乱） | 报告 2 |
| C4 | 中 | 前端全局脚本与 DOM 契约碎片化 | 报告 2 |
| C5 | 中 | 双套模板体系迁移不完整 / 新旧模板树并行易漂移 | 两份报告共识 |
| C6 | 中 | 缺乏统一的依赖注入机制 | 报告 1 |
| C7 | 中 | 结构债以白名单方式长期挂账 | 报告 2 |

### 主题 D：测试体系治理（4 项）

| 编号 | 严重级别 | 问题 | 来源 |
|---|---|---|---|
| D1 | 高 | 回归测试数量过度膨胀且约定非标准（252 个脚本式） | 两份报告共识 |
| D2 | 中 | 测试缺乏分层目录结构 | 两份报告共识 |
| D3 | 低 | 开发依赖不完整，缺乏覆盖率工具 | 报告 1 |
| D4 | 中 | 缺乏自动化持续集成流水线 | 两份报告共识 |

### 主题 E：文档与留存治理（6 项）

| 编号 | 严重级别 | 问题 | 来源 |
|---|---|---|---|
| E1 | 低 | 仓库根入口文档缺失 | 两份报告共识 |
| E2 | 中 | 开发文档体量庞大且与实现存在偏差 | 两份报告共识 |
| E3 | 低 | 文档示例代码与实际实现偏差大 | 报告 1 |
| E4 | 中 | 文档事实源分散且版本叠层 | 报告 2 |
| E5 | 中 | 测试证据与审计留痕多轨并行 | 报告 2 |
| E6 | 低 | 前端静态资源缺乏构建流水线 | 报告 1 |

---

## 第一阶段：低成本高收益快速治理（可立即开始）

### 任务 1：补充根 README 与文档导航入口

**目标**
- 解决 E1：新维护者进入仓库的首个认知入口缺失。

**文件**
- 新建：`README.md`

- [ ] **步骤 1：创建根 README**

在仓库根目录创建 `README.md`，内容至少包含：
  - 项目名称与一句话定位（回转壳体单元智能排产系统）
  - 运行环境要求（Python 3.8、Win7 兼容、SQLite）
  - 启动方式：`python app.py`（默认界面）、`python app_new_ui.py`（新界面）
  - 测试入口：`python -m pytest tests/ -q`
  - 关键目录说明表（core/、data/、web/、templates/、static/、tests/、开发文档/、audit/、evidence/）
  - 文档导航：指向 `开发文档/系统速查表.md`（速查）、`开发文档/开发文档.md`（综合）、`AGENTS.md`（协作约定）
  - 打包部署：指向 `DELIVERY_WIN7.md` 和 `installer/README_WIN7_INSTALLER.md`

- [ ] **步骤 2：验证**

确认文件存在且 markdown 渲染正常：
```powershell
Test-Path README.md
Get-Content README.md | Select-Object -First 5
```

---

### 任务 2：补充开发依赖工具链

**目标**
- 解决 D3：为后续治理工作提供覆盖率报告和类型检查基础。

**文件**
- 修改：`requirements-dev.txt`

- [ ] **步骤 1：添加开发依赖**

在 `requirements-dev.txt` 中追加：
```
pytest-cov
ruff
```

注意：`ruff` 已在项目中实际使用但未声明；pyright/mypy 受 Python 3.8 限制暂不强制。

- [ ] **步骤 2：验证安装**

```powershell
pip install -r requirements-dev.txt
python -m pytest --co -q 2>&1 | Select-Object -First 5
```

---

### 任务 3：文档归档清理与事实源标注

**目标**
- 解决 E2、E3、E4：降低新开发者面对 38 个开发文档 + 44 个 audit 文件时的困惑。

**文件**
- 修改：`开发文档/开发文档.md`（头部加归档声明）
- 修改：`策划方案/初步策划方案.md`（头部加归档声明）
- 修改：`策划方案/初步策划方案v2.md`（头部加归档声明）
- 修改：`策划方案/初步策划方案修改意见.md`（头部加归档声明）
- 修改：`策划方案/初步策划方案修改意见v2.md`（头部加归档声明）
- 修改：`开发文档/V1.2/APS测试系统_排产优化完整方案_v1.2.9_archived.md`（确认归档标注）
- 新建：`开发文档/README.md`（文档角色索引）

- [ ] **步骤 1：在开发文档.md 头部添加归档声明**

在文件第 1 行前插入：
```markdown
> ⚠️ **归档声明**：本文档为项目开工时点的方案快照，内嵌的示例代码已与实际实现有明显差异。实际实现以代码为准，速查请用 `开发文档/系统速查表.md`。
```

- [ ] **步骤 2：在策划方案目录各文件头部添加归档声明**

在每个策划方案文件第 1 行前插入：
```markdown
> ⚠️ **已归档**：本文档为早期策划方案，与当前实现已有差异，仅保留作为项目决策历史记录。
```

- [ ] **步骤 3：创建开发文档索引 README**

在 `开发文档/README.md` 中列出文档角色表：

| 文档 | 角色 | 状态 |
|---|---|---|
| 系统速查表.md | 字段/接口速查（当前有效） | 活跃 |
| 开发文档.md | 方案综合快照 | 已归档 |
| 面板与接口清单.md | 路由与面板清单 | 活跃 |
| ADR/ | 架构决策记录 | 活跃 |
| V1.2/ | v1.2 版本方案 | 活跃（当前版本） |
| 阶段留痕与验收记录.md | 验收留痕 | 活跃 |
| 其余 | 拆分/审计专题 | 历史留档 |

- [ ] **步骤 4：验证**

```powershell
Select-String -Path "开发文档/开发文档.md" -Pattern "归档声明" | Select-Object -First 1
Test-Path "开发文档/README.md"
```

---

### 任务 4：白名单转治理台账

**目标**
- 解决 C7：将架构适应度测试中的超长文件白名单和高复杂度白名单转为带退出条件的正式台账。

**文件**
- 新建：`开发文档/技术债务治理台账.md`

- [ ] **步骤 1：提取白名单条目并建立台账**

从 `tests/test_architecture_fitness.py` 中提取 `_known_oversize_files` 和 `known_violations` 白名单，创建台账文件 `开发文档/技术债务治理台账.md`，格式如下：

```markdown
# 技术债务治理台账

## 超长文件白名单（500 行门禁豁免）

| 文件 | 当前行数 | 计划处理方式 | 退出条件 | 状态 |
|---|---|---|---|---|
| web/routes/scheduler_excel_calendar.py | ~430+ | 抽象 Excel 通用流程 | ≤500 行 | 待处理 |
| core/services/process/part_service.py | ~500+ | 拆分子模块 | ≤500 行 | 待处理 |
| core/services/process/unit_excel/template_builder.py | ~500+ | 拆分 | ≤500 行 | 待处理 |
| core/services/scheduler/config_service.py | 501 | 配置规则收敛后瘦身 | ≤500 行 | 待处理 |
| core/services/scheduler/schedule_optimizer.py | 560 | 拆分优化步骤 | ≤500 行 | 待处理 |
| core/services/personnel/operator_machine_service.py | ~500+ | 拆分 | ≤500 行 | 待处理 |
| core/infrastructure/database.py | 533 | 拆分连接/迁移/引导 | ≤500 行 | 待处理 |

## 高复杂度函数白名单（C 级/15 门禁豁免）

（从 `known_violations` 集合中逐条列出，附计划处理方式）
```

- [ ] **步骤 2：验证**

```powershell
Test-Path "开发文档/技术债务治理台账.md"
```

---

### 任务 5：证据留痕主索引建立

**目标**
- 解决 E5：将分散在 tests/、evidence/、audit/、开发文档/ 四条轨道的留痕建立单一主索引。

**文件**
- 修改：`evidence/README.md`（扩展为主索引）

- [ ] **步骤 1：扩展 evidence/README.md 为主索引**

在现有内容基础上增加：
- 指向 `audit/` 各月度审计摘要的链接
- 指向 `开发文档/阶段留痕与验收记录.md` 的链接
- 说明各轨道的定位：
  - `evidence/` — 测试脚本自动生成的报告
  - `audit/` — 人工审计结论
  - `开发文档/阶段留痕与验收记录.md` — 阶段验收签字
  - `tests/` — 测试代码（不再手工写报告到此目录）

- [ ] **步骤 2：验证**

```powershell
Select-String -Path "evidence/README.md" -Pattern "audit" | Measure-Object | Select-Object -ExpandProperty Count
```

---

## 第二阶段：调度核心治理

### 任务 6：调度服务目录子包化

**目标**
- 解决 A1：将 45 文件扁平目录拆为子包，降低浏览和定位成本。

**文件**
- 修改：`core/services/scheduler/` — 拆为以下子包结构
- 新建子包目录及 `__init__.py`：
  - `core/services/scheduler/gantt/` — gantt_contract.py, gantt_critical_chain.py, gantt_range.py, gantt_service.py, gantt_tasks.py, gantt_week_plan.py
  - `core/services/scheduler/dispatch/` — resource_dispatch_excel.py, resource_dispatch_range.py, resource_dispatch_rows.py, resource_dispatch_service.py, resource_dispatch_support.py, resource_pool_builder.py
  - `core/services/scheduler/config/` — config_presets.py, config_service.py, config_snapshot.py, config_validator.py, number_utils.py
  - `core/services/scheduler/batch/` — batch_copy.py, batch_excel_import.py, batch_query_service.py, batch_service.py, batch_template_ops.py, batch_write_rules.py
  - `core/services/scheduler/summary/` — schedule_summary.py, schedule_summary_assembly.py, schedule_summary_degradation.py, schedule_summary_freeze.py, schedule_summary_types.py
  - `core/services/scheduler/calendar/` — calendar_admin.py, calendar_engine.py, calendar_service.py
- 保留在 `core/services/scheduler/` 根目录：schedule_service.py, schedule_input_builder.py, schedule_input_collector.py, schedule_optimizer.py, schedule_optimizer_steps.py, schedule_orchestrator.py, schedule_persistence.py, schedule_template_lookup.py, freeze_window.py, operation_edit_service.py, schedule_history_query_service.py, _sched_display_utils.py, _sched_utils.py
- 修改：所有引用上述被移动模块的 import 语句

- [ ] **步骤 1：创建子包目录和 `__init__.py`**

每个子包的 `__init__.py` 需要重新导出原有的公开接口，确保外部 import 路径兼容。例如 `core/services/scheduler/gantt/__init__.py`：
```python
from .gantt_service import GanttService
from .gantt_contract import GanttContract
# ... 其他公开接口
```

- [ ] **步骤 2：移动文件到子包**

使用 git mv 确保版本历史保留。

- [ ] **步骤 3：全局 import 修复**

搜索所有 `from core.services.scheduler.gantt_` / `from .gantt_` 等导入，替换为新路径 `from core.services.scheduler.gantt.gantt_` 或通过子包 `__init__.py` 简化。

- [ ] **步骤 4：验证**

```powershell
python -m pytest tests/ -x -q --timeout=120
python -c "from core.services.scheduler.gantt import GanttService; print('OK')"
python -c "from core.services.scheduler.config import ConfigService; print('OK')"
python -c "from core.services.scheduler.batch import BatchService; print('OK')"
```

---

### 任务 7：GreedyScheduler.schedule() 方法拆分

**目标**
- 解决 A3：将 332 行的 schedule() 方法拆分为多个职责清晰的私有方法，降低圈复杂度。

**文件**
- 修改：`core/algorithms/greedy/scheduler.py`

- [ ] **步骤 1：分析当前 schedule() 方法的职责块**

当前 schedule() 方法（第 56-388 行）包含以下可辨识的职责块：
1. 参数解析与配置读取（第 78-106 行，约 28 行）
2. 批次 ID 规范化与排序（第 109-164 行，约 55 行）
3. 种子结果处理与去重（第 166-206 行，约 40 行）
4. 资源时间线初始化（第 215-240 行，约 25 行）
5. 主调度循环（第 242-372 行，约 130 行）
6. 结果汇总与统计（第 375-388 行，约 13 行）

- [ ] **步骤 2：抽取为私有方法**

抽取以下私有方法（方法名和签名）：
```python
def _resolve_params(self, strategy, strategy_params, start_dt, end_date, 
                    dispatch_mode, dispatch_rule, strict_mode):
    """解析配置参数，返回 (params, base_time, end_dt_exclusive, used_params, ...)"""

def _normalize_batch_ids(self, batches, batch_order_override):
    """ID 规范化与批次排序，返回 (batches_norm, batch_order)"""

def _prepare_seed_results(self, seed_results, operations, batches_norm):
    """种子结果处理与去重，返回 (normalized_seed, seed_warnings, seed_op_ids)"""

def _init_timelines(self, base_time, batches_norm, normalized_seed):
    """资源时间线与批次进度初始化，返回各 timeline dict"""

def _build_schedule_summary(self, results, warnings, errors, t0, ...):
    """结果汇总与统计，返回 ScheduleSummary"""
```

- [ ] **步骤 3：重构 schedule() 为编排方法**

schedule() 方法体缩减为调用上述私有方法的编排逻辑，仅保留主循环和结果组装，目标≤150 行。

- [ ] **步骤 4：运行定向验证**

```powershell
python -m pytest tests/regression_greedy_scheduler_algo_stats_auto_assign.py tests/regression_greedy_scheduler_algo_stats_seed_counts.py tests/regression_greedy_date_parsers.py -x -q
```

- [ ] **步骤 5：运行全量回归**

```powershell
python -m pytest tests/ -x -q --timeout=120
```

---

### 任务 8：算法层类型约束引入

**目标**
- 解决 A4：为算法层核心参数定义 Protocol 类型，替代 Any。

**文件**
- 修改：`core/algorithms/types.py`（追加 Protocol 定义）
- 修改：`core/algorithms/greedy/scheduler.py`（更新类型标注）

- [ ] **步骤 1：在 `core/algorithms/types.py` 中定义 Protocol**

```python
from typing import Any, Optional
from typing_extensions import Protocol, runtime_checkable

@runtime_checkable
class ScheduleOperationLike(Protocol):
    batch_id: str
    seq: int
    source: str
    machine_id: Optional[str]
    operator_id: Optional[str]
    status: str

@runtime_checkable
class ScheduleBatchLike(Protocol):
    batch_id: str
    due_date: Optional[str]
    ready_date: Optional[str]
```

注意：Python 3.8 需要 `typing_extensions`，确认 `requirements.txt` 已包含。

- [ ] **步骤 2：更新 scheduler.py 的类型标注**

将 `operations: List[Any]` 改为 `operations: List[ScheduleOperationLike]`，`batches: Dict[str, Any]` 改为 `batches: Dict[str, ScheduleBatchLike]`。

- [ ] **步骤 3：验证**

```powershell
python -c "from core.algorithms.types import ScheduleOperationLike; print('OK')"
python -m pytest tests/ -x -q --timeout=120
```

---

### 任务 9：兼容桥接代码清理

**目标**
- 解决 A6：删除 `_scheduler_accepts_strict_mode` 签名探测和 TypeError 后重试逻辑。

**文件**
- 修改：`core/services/scheduler/schedule_optimizer_steps.py`（删除 `_scheduler_accepts_strict_mode`、简化 `_schedule_with_optional_strict_mode`）
- 修改：`core/algorithms/greedy/config_adapter.py`（确认 cfg_get 已足够简洁，无需修改）

- [ ] **步骤 1：确认所有 scheduler 实现都已支持 strict_mode**

搜索所有实现了 `schedule()` 方法的类，确认它们的签名都包含 `strict_mode` 参数：
```powershell
Select-String -Path "core/algorithms" -Pattern "def schedule\(" -Recurse
```

- [ ] **步骤 2：简化 `_schedule_with_optional_strict_mode`**

如果步骤 1 确认所有实现都支持 strict_mode，则将该函数简化为直接调用：
```python
def _schedule_with_optional_strict_mode(scheduler, *, strict_mode=False, **kwargs):
    return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))
```

删除 `_scheduler_accepts_strict_mode` 函数和对 `inspect` 的导入。

- [ ] **步骤 3：验证**

```powershell
python -m pytest tests/regression_scheduler_strict_mode_dispatch_flags.py tests/regression_schedule_optimizer_cfg_float_strict_blank.py -x -q
python -m pytest tests/ -x -q --timeout=120
```

---

### 任务 10：调度配置规则收敛（单一事实来源）

**目标**
- 解决 A2：为调度配置建立单一事实来源，消除 6 处相近的校验/默认值/值域逻辑。

**文件**
- 新建：`core/services/scheduler/config/config_field_spec.py`（字段规范定义）
- 修改：`core/services/scheduler/config/config_snapshot.py`（消费规范）
- 修改：`core/services/scheduler/config/config_validator.py`（消费规范）
- 修改：`core/services/scheduler/config/config_service.py`（消费规范）
- 修改：`core/algorithms/greedy/schedule_params.py`（消费规范）
- 修改：`core/services/scheduler/schedule_optimizer_steps.py`（消费规范）

- [ ] **步骤 1：定义字段规范数据结构**

在 `config_field_spec.py` 中定义：
```python
@dataclass(frozen=True)
class ConfigFieldSpec:
    key: str
    field_type: str  # "float" | "int" | "str" | "yes_no"
    default: Any
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    valid_values: Optional[Tuple[str, ...]] = None
    strict_mode_required: bool = False

SCHEDULE_CONFIG_FIELDS: Dict[str, ConfigFieldSpec] = {
    "priority_weight": ConfigFieldSpec("priority_weight", "float", 1.0, min_value=0.0),
    "due_weight": ConfigFieldSpec("due_weight", "float", 1.0, min_value=0.0),
    "ready_weight": ConfigFieldSpec("ready_weight", "float", 0.3, min_value=0.0),
    # ... 全部字段
}
```

- [ ] **步骤 2：让 config_snapshot 消费规范**

`build_schedule_config_snapshot` 从 `SCHEDULE_CONFIG_FIELDS` 读取默认值和值域，而不是硬编码。

- [ ] **步骤 3：让 config_validator 消费规范**

`normalize_preset_snapshot` 从 `SCHEDULE_CONFIG_FIELDS` 读取合法值列表和数值范围。

- [ ] **步骤 4：让算法层消费规范**

`schedule_params.py` 和 `schedule_optimizer_steps.py` 中的 `_cfg_float`/`_cfg_int` 从规范中读取默认值和下限。

- [ ] **步骤 5：验证**

```powershell
python -m pytest tests/regression_config_snapshot_strict_numeric.py tests/regression_config_validator_preset_degradation.py tests/regression_config_service_active_preset_custom_sync.py tests/regresheduler_apply_preset_reject_invalid_numeric.py -x -q
python -m pytest tests/ -x -q --timeout=120
```

---

## 第三阶段：数据基础设施治理

### 任务 11：database.py 拆分

**目标**
- 解决 B1：将 533 行的 database.py 拆为职责清晰的模块。

**文件**
- 修改：`core/infrastructure/database.py`（瘦身为连接管理+入口函数）
- 新建：`core/infrastructure/schema_bootstrap.py`（Schema 引导与缺表补齐）
- 新建：`core/infrastructure/migration_runner.py`（迁移执行与预检）
- 新建：`core/infrastructure/db_file_utils.py`（文件级操作：sidecar 清理、文件恢复）

- [ ] **步骤 1：抽取文件级工具函数到 db_file_utils.py**

移动以下函数：
- `_cleanup_sqlite_sidecars`
- `_restore_db_file_from_backup`
- `_cleanup_probe_db`
- `_is_windows_lock_error`

- [ ] **步骤 2：抽取 Schema 引导到 schema_bootstrap.py**

移动以下函数：
- `_load_schema_sql`、`_build_schema_exec_script`
- `_declared_schema_tables`、`_schema_create_table_statements`、`_schema_index_statements`
- `_build_statement_script`、`_missing_schema_tables`、`_bootstrap_missing_tables_from_schema`
- `_build_contract_error`、`_ensure_schema_version`
- `_is_truly_empty_db`、`_list_user_tables`、`_has_no_user_tables`、`_detect_schema_is_current`
- `_get_schema_version`、`_set_schema_version`

- [ ] **步骤 3：抽取迁移运行到 migration_runner.py**

移动以下函数：
- `_preflight_migration_contract`
- `_migrate_with_backup`
- `_run_migration`

- [ ] **步骤 4：database.py 保留连接管理和 ensure_schema 入口**

database.py 只保留：
- `CURRENT_SCHEMA_VERSION` 常量
- `MigrationContractError` 异常
- `get_connection()` 函数
- `ensure_schema()` 入口函数（内部调用 schema_bootstrap 和 migration_runner）

- [ ] **步骤 5：修复所有导入**

搜索全项目中 `from core.infrastructure.database import` 的语句，确认所有公开接口仍可从 `database.py` 导入（通过 re-export）。

- [ ] **步骤 6：验证**

```powershell
python -c "from core.infrastructure.database import get_connection, ensure_schema, MigrationContractError; print('OK')"
python -m pytest tests/regression_ensure_schema_fastforward_empty_only.py tests/regression_migrate_backup_dir_none_creates_backup.py tests/regression_migration_failfast_no_backup_storm.py -x -q
python -m pytest tests/ -x -q --timeout=120
```

- [ ] **步骤 7：更新白名单**

如果 database.py 行数降到 500 以下，从 `tests/test_architecture_fitness.py` 的 `_known_oversize_files` 中移除该条目，并更新 `开发文档/技术债务治理台账.md`。

---

### 任务 12：仓储层读模型分离

**目标**
- 解决 B2：将 ScheduleRepository 中面向页面的复杂关联查询迁移到独立查询服务。

**文件**
- 新建：`core/services/scheduler/schedule_query_service.py`（承接页面/报表级查询）
- 修改：`data/repositories/schedule_repo.py`（移除页面级查询方法）
- 修改：引用被移动方法的路由文件

- [ ] **步骤 1：识别需要迁移的方法**

`schedule_repo.py` 中的 `list_by_version_with_details` 及类似多表关联查询方法应迁移到服务层。

- [ ] **步骤 2：创建 schedule_query_service.py**

将多表关联查询方法移到查询服务中，该服务接收 conn 和所需仓储实例。

- [ ] **步骤 3：修改路由层引用**

路由层改为调用 `ScheduleQueryService` 而非直接调用仓储。

- [ ] **步骤 4：验证**

```powershell
python -m pytest tests/ -x -q --timeout=120
```

---

## 第四阶段：Web 界面层治理

### 任务 13：路由子包化

**目标**
- 解决 C1：将 59 文件扁平路由目录按业务域拆为子包。

**文件**
- 重组 `web/routes/` 为：
  - `web/routes/scheduler/` — 16 个 scheduler_*.py
  - `web/routes/equipment/` — 6 个 equipment_*.py
  - `web/routes/personnel/` — 7 个 personnel_*.py
  - `web/routes/process/` — 7 个 process_*.py
  - `web/routes/system/` — 8 个 system_*.py
  - 保留在根目录：`__init__.py`、`dashboard.py`、`excel_demo.py`、`excel_utils.py`、`normalizers.py`、`pagination.py`、`reports.py`、`material.py`、`enum_display.py`

- [ ] **步骤 1：创建子包目录和 `__init__.py`**

每个子包的 `__init__.py` 导出蓝图对象，例如：
```python
# web/routes/scheduler/__init__.py
from .scheduler_bp import scheduler_bp
# side-effect imports for route registration
from . import scheduler_pages, scheduler_gantt, ...
```

- [ ] **步骤 2：移动文件**

使用 git mv 移动文件，保留版本历史。

- [ ] **步骤 3：修复全局 import**

修复 `web/bootstrap/factory.py` 和所有引用路由模块的地方。

- [ ] **步骤 4：验证**

```powershell
python -c "from web.routes.scheduler import scheduler_bp; print('OK')"
python -m pytest tests/ -x -q --timeout=120
```

---

### 任务 14：Excel 导入通用流程抽象

**目标**
- 解决 C2：将分散在多个路由中的"读取→规范化→预览→基线校验→确认→写库→留痕"流程抽象为通用控制器。

**文件**
- 新建：`web/routes/excel_import_controller.py`（通用 Excel 导入流程控制器）
- 修改：各 Excel 导入路由文件（改为消费通用控制器）

- [ ] **步骤 1：分析现有 Excel 导入路由的共同模式**

当前至少有以下 Excel 导入路由采用相同流程：
- `scheduler_excel_calendar.py`（预览 + 确认，各约 110-170 行）
- `scheduler_excel_batches.py`
- `process_excel_routes.py`
- `process_excel_part_operation_hours.py`（预览 + 确认，共约 135 行）
- `process_excel_op_types.py`
- `process_excel_suppliers.py`
- `personnel_excel_operators.py`
- `personnel_excel_links.py`
- `personnel_excel_operator_calendar.py`
- `equipment_excel_machines.py`
- `equipment_excel_links.py`

- [ ] **步骤 2：定义通用流程控制器**

```python
class ExcelImportController:
    """通用 Excel 导入流程：上传→解析→规范化→预览→基线校验→确认→写库→留痕"""
    
    def __init__(self, *, blueprint, url_prefix, template_name, 
                 parser_factory, validator_factory, applier_factory,
                 entity_label, ...):
        ...
    
    def register_routes(self):
        """注册 preview + confirm 两个路由"""
```

- [ ] **步骤 3：逐步迁移现有路由**

先选择一个最简单的导入页面（如供应商导入）作为试点迁移，验证通用控制器可行后再推广。

- [ ] **步骤 4：验证**

```powershell
python -m pytest tests/regression_excel_import_strict_reference_apply.py tests/regression_excel_preview_confirm_baseline_guard.py -x -q
python -m pytest tests/ -x -q --timeout=120
```

---

### 任务 15：双模板树收敛决策与执行

**目标**
- 解决 C5：明确 v2 模板的终态策略并开始收敛。

**文件**
- 修改：`开发文档/ADR/` — 新增 ADR 记录模板策略决策
- 修改：相关模板文件（根据决策）

- [ ] **步骤 1：新增 ADR 记录双模板终态决策**

创建 `开发文档/ADR/0012-双模板树收敛策略.md`，记录以下决策：
- **方案 A**（推荐）：冻结 v1 为只读，v2 接管全部新增页面，逐步将 v1 页面在 v2 基座上重写
- **方案 B**：放弃 v2 overlay，在 v1 模板上直接演进
- 记录选定方案和理由

- [ ] **步骤 2：如选择方案 A，建立 v2 迁移清单**

在 ADR 中列出所有未迁移到 v2 的模板页面（约 40+ 个），标注优先级。

- [ ] **步骤 3：如选择方案 B，标记 web_new_test 为归档**

在 `web_new_test/` 根目录添加 README 说明此目录已冻结。

---

### 任务 16：前端脚本初始化协议统一

**目标**
- 解决 C4：为页面脚本建立统一初始化协议，减少全局命名空间和 DOM id 的隐式耦合。

**文件**
- 新建：`static/js/page_init.js`（统一页面初始化协议）
- 修改：`templates/base.html`（加载 page_init.js）
- 修改：`static/js/gantt.js`、`static/js/resource_dispatch.js` 等（适配新协议）

- [ ] **步骤 1：定义页面初始化协议**

```javascript
// page_init.js
window.__APS_PAGES__ = window.__APS_PAGES__ || {};

window.__APS_PAGES__.register = function(pageName, initFn) {
    window.__APS_PAGES__[pageName] = initFn;
};

window.__APS_PAGES__.boot = function(pageName, config) {
    var fn = window.__APS_PAGES__[pageName];
    if (fn) fn(config);
};
```

- [ ] **步骤 2：改造甘特图页面为试点**

将现有 `window.__APS_GANTT__` 改为 `window.__APS_PAGES__.register('gantt', function(config) { ... })`。

- [ ] **步骤 3：验证**

手动打开甘特图页面确认功能正常，运行：
```powershell
python -m pytest tests/regression_gantt_contract_snapshot.py tests/regression_gantt_url_persistence.py -x -q
```

---

## 第五阶段：测试体系治理

### 任务 17：测试分层目录建立与回归测试逐步标准化

**目标**
- 解决 D1、D2：建立测试分层目录，开始将回归测试逐步转换为标准 pytest 格式。

**文件**
- 新建：`tests/unit/`、`tests/integration/`、`tests/e2e/` 目录
- 新建：`tests/unit/__init__.py`、`tests/integration/__init__.py`、`tests/e2e/__init__.py`
- 修改：`tests/conftest.py`（确保子目录也能正确收集）

- [ ] **步骤 1：创建分层目录结构**

```
tests/
  unit/           # 纯单元测试（无数据库、无网络）
    __init__.py
    scheduler/    # 按业务域分组
    equipment/
    process/
    ...
  integration/    # 需要数据库但不需要 Web 服务器
    __init__.py
  e2e/            # 端到端测试（含 Web 服务器启动）
    __init__.py
  # 现有文件暂时保留原位，逐步迁移
```

- [ ] **步骤 2：试点迁移 3 个回归测试**

选择 3 个相关的回归测试（如 `regression_config_snapshot_strict_numeric.py`、`regression_config_validator_preset_degradation.py`、`regression_config_service_active_preset_custom_sync.py`），将它们合并为一个标准 pytest 文件 `tests/unit/scheduler/test_config_contracts.py`，使用标准 pytest 断言和夹具。

- [ ] **步骤 3：验证**

```powershell
python -m pytest tests/unit/ -x -q
python -m pytest tests/ -x -q --timeout=120
```

- [ ] **步骤 4：记录迁移规范**

在 `tests/README.md`（新建）中记录：
- 新测试应写在 `tests/unit/` 或 `tests/integration/
- 使用标准 pytest 函数/类格式
- 命名约定：`test_<模块>_<行为>.py`

---

### 任务 18：基础 CI 建设

**目标**
- 解决 D4：建立最小可用的持续集成检查。

**文件**
- 新建：`.github/workflows/ci.yml`（如果使用 GitHub）或 `scripts/ci_check.ps1`（本地 CI）

- [ ] **步骤 1：创建本地 CI 检查脚本**

由于项目定位为 Win7 单机交付，优先建立本地 CI 脚本 `scripts/ci_check.ps1`：
```powershell
#!/usr/bin/env pwsh
Write-Host "=== Ruff 代码风格检查 ===" -ForegroundColor Cyan
python -m ruff check core/ data/ web/ --config pyproject.toml
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "=== pytest 快速套件 ===" -ForegroundColor Cyan
python -m pytest tests/ -x -q --timeout=120
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "=== 架构适应度门禁 ===" -ForegroundColor Cyan
python -m pytest tests/test_architecture_fitness.py -x -q
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "全部检查通过 ✓" -ForegroundColor Green
```

- [ ] **步骤 2：创建 pre-commit hook（可选）**

在 `.pre-commit-config.yaml` 中已有 ruff 配置，确认其可用性。考虑添加 pytest 快速套件为 pre-push hook。

- [ ] **步骤 3：验证**

```powershell
powershell -File scripts/ci_check.ps1
```

---

## 降级状态与编排扇出治理说明

以下问题（A5 编排扇出、A7 降级状态扩散、B3 模型映射样板、B4 迁移语义清洗、C3 页面装配规范、C6 依赖注入）属于**中长期架构演进**，需要在前述任务完成后才能有效推进：

- **A5 编排扇出**：依赖任务 6（子包化）完成后，ScheduleService 的仓储依赖可通过子包内 facade 收敛
- **A7 降级状态扩散**：依赖任务 10（配置规则收敛）完成后，可统一降级事件收集点
- **B3 模型映射样板**：属于模式统一工作，建议单独开 plan
- **B4 迁移语义清洗**：现有迁移脚本已运行稳定，拆分收益有限，标记为长期关注
- **C3 页面装配规范**：依赖任务 14（Excel 抽象）作为试点，逐步建立页面层约定
- **C6 依赖注入**：依赖任务 6 完成后，可在子包 facade 层引入轻量级服务容器
- **E6 前端构建流水线**：对单机离线应用影响最小，标记为最低优先级

这些问题已在任务 4 的技术债务治理台账中登记，不在本 plan 中设置具体步骤。

---

## 全局验证

每个任务完成后，除任务自身的定向验证外，必须运行：

```powershell
# 架构适应度门禁
python -m pytest tests/test_architecture_fitness.py -x -q

# 全量回归
python -m pytest tests/ -x -q --timeout=120
```

确认无新增失败后方可进入下一个任务。

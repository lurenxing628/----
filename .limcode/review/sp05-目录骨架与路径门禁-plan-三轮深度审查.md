# SP05 目录骨架与路径门禁 Plan 三轮深度审查
- 日期: 2026-04-12
- 概述: 对 SP05 子 plan 进行三轮深度审查：目标达成性、设计优雅性、逻辑严谨性与 BUG 检测
- 状态: 进行中
- 总体结论: 待定

## 评审范围

# SP05 目录骨架与路径门禁 — Plan 三轮深度审查

## 审查对象
- `.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md`

## 审查方法
三轮递进式深度审查：
1. **第一轮：目标达成性与完备性** — plan 能否达成目的
2. **第二轮：设计优雅性与过度工程检测** — 是否简洁、是否有过度兜底/静默回退
3. **第三轮：逻辑严谨性与 BUG 检测** — 深入引用链追踪，检查逻辑漏洞

## 审查范围
追踪了以下完整引用链：
- `schedule_service.py` 全部 15 条根层导入
- `scheduler.py` → `scheduler_pages.py` 副作用导入链
- `factory.py` 蓝图注册链
- `scheduler_bp.py` 的 `Blueprint("scheduler", __name__)` 语义
- `_safe_next_url` 全部 3 个消费者（`scheduler_config.py`、`scheduler_batches.py`、`system_ui_mode.py`）
- `LOCAL_PARSE_HELPER_ALLOWLIST` 全部 10 条路径条目
- `REQUEST_SERVICE_TARGET_FILES` 全部 11 条路径条目
- `REQUEST_SERVICE_TARGET_ALLOWED_HELPERS` 全部 2 条条目及 `line` 字段
- `_check_architecture_layers` 路由侧 `os.listdir` vs 服务侧 `os.walk` 不对称
- `test_source_merge_mode_constants.py` 的 `targets` 列表
- `regression_excel_routes_no_tx_surface_hidden.py` 的 `targets` 列表
- 全部 15 个路由文件的根层共享工具导入清单
- 全部 10 个按旧路径 `import web.routes.scheduler_*` 的测试文件
- 全部 7 个使用模块级替换/注入合同的回归测试

## 评审摘要

- 当前状态: 进行中
- 已审模块: SP05 plan 目标定义, SP05 plan 范围边界, SP05 plan 实施前确认, SP05 plan 执行编排, SP05 plan 兼容策略, SP05 plan 停点规则, SP05 plan 阶段 3 服务迁移, SP05 plan 阶段 4 路由迁移, SP05 plan 阶段 5 门禁同步, SP05 plan 完成判定与验证命令
- 当前进度: 已记录 3 个里程碑；最新：R3-logic-bugs
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 4
- 问题严重级别分布: 高 0 / 中 3 / 低 1
- 最新结论: ## 结论：逻辑严谨，无重大 BUG 深入追踪全部引用链后，plan 的逻辑整体严谨。发现 3 个中等问题和 2 个低等问题，均为**措辞精确性**问题而非**逻辑漏洞**。 ### 关键验证结果 **1. 15 个路由文件共享导入完整追踪** | 需要绝对导入改写的文件 | 共享工具 | |---|---| | `scheduler_bp.py` | `.enum_display` | | `scheduler_config.py` | `_safe_next_url` | | `scheduler_run.py` | `.excel_utils` | | `scheduler_batches.py` | `.excel_utils`、`.pagination`、`_safe_next_url` | | `scheduler_analysis.py` | `.normalizers` | | `scheduler_gantt.py` | `.normalizers` | | `scheduler_week_plan.py` | `.excel_utils`、`.normalizers` | | `scheduler_excel_calendar.py` | `.excel_utils` | | `scheduler_excel_batches.py` | `.excel_utils` | | `scheduler_utils.py` | `.excel_utils`、`.normalizers` | 不需要改写的 4 个文件：`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`——它们只引用同域文件或绝对路径。 **2. 10 个 `import web.routes.scheduler_*` 的测试全部通过薄门面兼容** 追踪确认这些测试通过模块级 `import ... as route_mod` + `monkeypatch.setattr(route_mod, ...)` 工作，在"同一模块对象"语义下无需修改。 **3. `_check_architecture_layers` 的非递归扫描是真实 BUG** `generate_conformance_report.py:427` 用 `os.listdir(route_dir)` 只扫顶层，而服务侧 `:448` 用 `os.walk`。迁移后路由消失于报告。plan 正确识别了这一问题。 **4. `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 的 glob 自动兼容** `web/routes/**/*.py` 中 `**` 匹配任意层目录，`domains/scheduler/*.py` 自动包含。无需修改。 **5. 无循环导入风险** `schedule_service.py` 迁移后对 `.run/.config/.summary` 的导入不会形成循环——子包中无文件反向导入 `schedule_service.py`。
- 下一步建议: 待定
- 总体结论: 待定

## 评审发现

### 兼容薄门面缺少推荐实现机制示例

- ID: F01
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2-elegance
- 说明:

  plan 禁止 `from 新路径 import *` 式重导出，要求“同一模块对象语义”，但未明确给出推荐的实现机制。正确的做法应是 `sys.modules[__name__] = importlib.import_module('new.real.path')`。建议在阶段 2 的兼容薄门面规则中增加一句“推荐使用 `sys.modules` 替换实现同一模块对象语义”的显式指导，避免执行者自行发明其他机制。
- 建议:

  在阶段 2 第 4 点补充推荐实现机制示例
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md:199-205`
  - `.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md`

### Blueprint __name__ 迁移影响分析不充分

- ID: F02
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R3-logic-bugs
- 说明:

  plan 阶段 4 第 4 点仅说“需做一次显式启动/页面验证”，但未分析影响机制。实际追踪：

  `scheduler_bp.py` 当前：`Blueprint("scheduler", __name__)` → `__name__ == "web.routes.scheduler_bp"`
  迁移后：`Blueprint("scheduler", __name__)` → `__name__ == "web.routes.domains.scheduler.scheduler_bp"`

  Flask 用 `import_name` 确定 Blueprint 的 `root_path`，影响 `static_folder`/`template_folder` 的相对路径解析。但该 Blueprint **未设置自身的 `static_folder`/`template_folder`**，模板和静态文件均由应用级配置管理。因此 `__name__` 变化对 `url_for`、模板渲染和静态文件解析**均无影响**。

  建议将此分析结论写入阶段 2（导入策略阶段），而非留到阶段 4 才验证。
- 建议:

  在阶段 2 明确写明 `Blueprint __name__` 变化安全性分析，不必延后验证
- 证据:
  - `web/routes/scheduler_bp.py:10-11#Blueprint("scheduler", __name__)`
  - `.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md:256`
  - `web/routes/scheduler_bp.py`
  - `.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md`

### 回归测试未区分“需修改”与“只需验证”两类

- ID: F03
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R3-logic-bugs
- 说明:

  plan 阶段 5 第 6 点将全部回归测试统一列为“必须同批更新”，但实际追踪发现存在两类测试：

  **类型 A：需要修改代码的测试**（按文件路径读源码/硬编码路径常量）：
  - `regression_excel_routes_no_tx_surface_hidden.py` — `targets` 列表硬编码 `web/routes/scheduler_excel_batches.py`
  - `test_source_merge_mode_constants.py` — `targets` 列表硬编码 `core/services/scheduler/schedule_optimizer.py`
  - `test_architecture_fitness.py` — `LOCAL_PARSE_HELPER_ALLOWLIST` 硬编码路径
  - `tools/quality_gate_shared.py` — `REQUEST_SERVICE_TARGET_FILES` 硬编码路径

  **类型 B：不需要修改代码的测试**（通过模块导入，兼容薄门面自动透明）：
  - `regression_schedule_service_facade_delegation.py` — `import core.services.scheduler.schedule_service as schedule_service_mod` + 模块级替换
  - `regression_dict_cfg_contract.py` — `import core.services.scheduler.schedule_optimizer as schedule_optimizer` + 模块级替换
  - `regression_optimizer_zero_weight_cfg_preserved.py` — 同上
  - `regression_scheduler_config_route_contract.py` — `import web.routes.scheduler_config as route_mod` + monkeypatch
  - 另 6 个 `import web.routes.scheduler_*` 的路由合同回归

  类型 B 测试在兼容薄门面正确实现后无需任何修改即可通过。plan 未区分这两类，可能导致执行者对类型 B 测试做不必要的代码修改，反而引入新问题。
- 建议:

  在阶段 5 第 6 点明确区分“需要修改代码”和“只需验证通过”两类测试
- 证据:
  - `tests/regression_schedule_service_facade_delegation.py:83-86#schedule_service_mod.模块级替换`
  - `tests/regression_scheduler_config_route_contract.py:33-35#import web.routes.scheduler_config as route_mod`
  - `tests/regression_excel_routes_no_tx_surface_hidden.py:27-32#硬编码路径 targets`
  - `tests/regression_scheduler_run_surfaces_resource_pool_warning.py:17#import web.routes.scheduler_run as route_mod`
  - `tests/regression_schedule_service_facade_delegation.py`
  - `tests/regression_scheduler_config_route_contract.py`
  - `tests/regression_excel_routes_no_tx_surface_hidden.py`
  - `tests/regression_scheduler_run_surfaces_resource_pool_warning.py`

### 共享导入改写清单“至少”措辞引起疑虑

- ID: F04
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R3-logic-bugs
- 说明:

  阶段 4 第 3 点的共享导入改写清单以“至少覆盖”开头，但实际追踪全部 15 个路由文件后发现，清单实际上已经 **完整**覆盖了所有需要改写的共享导入。未被列出的 4 个文件（`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`）确实不包含需要改写的根层共享工具导入。但“至少”措辞会给执行者造成不必要的疑虑。
- 建议:

  将“至少覆盖”改为“完整覆盖（以下 4 个文件无需改写：...）”
- 证据:
  - `web/routes/scheduler_batch_detail.py:1-11#无根层共享工具导入`
  - `web/routes/scheduler_ops.py:1-8#无根层共享工具导入`
  - `web/routes/scheduler_resource_dispatch.py:1-14#无根层共享工具导入`
  - `web/routes/scheduler_calendar_pages.py:1-11#无根层共享工具导入`
  - `web/routes/scheduler_batch_detail.py`
  - `web/routes/scheduler_ops.py`
  - `web/routes/scheduler_resource_dispatch.py`
  - `web/routes/scheduler_calendar_pages.py`

## 评审里程碑

### R1-goal-completeness · 第一轮：目标达成性与完备性审查

- 状态: 已完成
- 记录时间: 2026-04-12T06:08:18.261Z
- 已审模块: SP05 plan 目标定义, SP05 plan 范围边界, SP05 plan 实施前确认
- 摘要:

  ## 结论：plan 能够达成其核心目标

  plan 的核心目标是"给后续 SP06~SP10 建立统一路径口径"，而非"移动文件"。这一定位是正确的。

  ### 已验证的关键事实

  1. **`scheduler.py` ↔ `scheduler_pages.py` 聚合缺口已正确识别**：当前 `scheduler.py` 直接导入 4 个模块（`excel_batches`/`excel_calendar`/`gantt`/`week_plan`），而 `scheduler_pages.py` 不包含它们。plan 在阶段 4 第 2 点要求"补入副作用导入"，正确。

  2. **`_safe_next_url` 消费者清单完整**：搜索确认恰好 3 个消费者（`scheduler_config.py:27`、`scheduler_batches.py:23`、`system_ui_mode.py:9`），plan 全部覆盖。

  3. **`test_source_merge_mode_constants.py` 影响范围精确**：5 个 `targets` 中仅 `schedule_optimizer.py` 和 `freeze_window.py` 受 SP05 影响，plan 正确只改这两项。

  4. **12 条实施前确认全部有据**：逐条核实了蓝图注册链（`factory.py:373`）、`schedule_service.py` 的 15 条导入、`quality_gate_shared.py` 的门禁常量等，均与实际代码吻合。

  5. **"不做什么"边界清晰**：7 条禁止项有效防止了范围蠕变，特别是"不把目录迁移和行为改造混在一个提交里"与"不顺手回头改请求级装配"。
- 结论:

  ## 结论：plan 能够达成其核心目标 plan 的核心目标是"给后续 SP06~SP10 建立统一路径口径"，而非"移动文件"。这一定位是正确的。 ### 已验证的关键事实 1. **`scheduler.py` ↔ `scheduler_pages.py` 聚合缺口已正确识别**：当前 `scheduler.py` 直接导入 4 个模块（`excel_batches`/`excel_calendar`/`gantt`/`week_plan`），而 `scheduler_pages.py` 不包含它们。plan 在阶段 4 第 2 点要求"补入副作用导入"，正确。 2. **`_safe_next_url` 消费者清单完整**：搜索确认恰好 3 个消费者（`scheduler_config.py:27`、`scheduler_batches.py:23`、`system_ui_mode.py:9`），plan 全部覆盖。 3. **`test_source_merge_mode_constants.py` 影响范围精确**：5 个 `targets` 中仅 `schedule_optimizer.py` 和 `freeze_window.py` 受 SP05 影响，plan 正确只改这两项。 4. **12 条实施前确认全部有据**：逐条核实了蓝图注册链（`factory.py:373`）、`schedule_service.py` 的 15 条导入、`quality_gate_shared.py` 的门禁常量等，均与实际代码吻合。 5. **"不做什么"边界清晰**：7 条禁止项有效防止了范围蠕变，特别是"不把目录迁移和行为改造混在一个提交里"与"不顺手回头改请求级装配"。
- 证据:
  - `web/routes/scheduler.py:11-22#scheduler.py 当前导入链`
  - `web/routes/scheduler_pages.py:1-16#scheduler_pages.py 当前聚合范围`
  - `web/routes/system_utils.py:19-43#_safe_next_url 唯一定义`
  - `web/bootstrap/factory.py:31#factory.py 蓝图导入`
  - `web/bootstrap/factory.py:373#factory.py 蓝图注册`
  - `tests/test_source_merge_mode_constants.py:93-99#targets 列表`

### R2-elegance · 第二轮：设计优雅性与过度工程检测

- 状态: 已完成
- 记录时间: 2026-04-12T06:08:52.737Z
- 已审模块: SP05 plan 执行编排, SP05 plan 兼容策略, SP05 plan 停点规则
- 摘要:

  ## 结论：设计简洁、无过度工程

  ### 6 阶段编排：合理无冗余
  每个阶段都有明确的前置依赖和产物，无多余分解。Phase 3 拆为 3A/3B/3C 是因为 config/summary 与 run 有不同的边界清晰度，合理。

  ### "兼容薄门面"策略：标准做法
  这是 Python 大型项目包重构的标准手法（Django、SQLAlchemy 都用过）。plan 明确禁止了两种危险的兼容方式且理由充分：
  1. 禁止 `from 新路径 import *` — 会创建新名称绑定而非别名，破坏模块身份
  2. 禁止"新路径回指旧路径"完成态 — 会制造反向依赖

  ### 停点规则：6 条，全部必要
  分布在阶段 2（2条）、阶段 4（3条）、阶段 5（1条），针对"不先完成 X 就不允许做 Y"的真实风险，无多余停点。

  ### 无过度兜底/静默回退
  plan 全文未使用任何"try-except 吞异常"、"双路径猜测"、"签名探测重试"式设计。第 51 行明确禁止"不允许根层兼容入口做成签名探测、吞异常重试、双路径猜测或第二事实源"。

  ### 一个改进点
  plan 禁止了错误做法但未给出推荐的正确做法示例（见 F01）。
- 结论:

  ## 结论：设计简洁、无过度工程 ### 6 阶段编排：合理无冗余 每个阶段都有明确的前置依赖和产物，无多余分解。Phase 3 拆为 3A/3B/3C 是因为 config/summary 与 run 有不同的边界清晰度，合理。 ### "兼容薄门面"策略：标准做法 这是 Python 大型项目包重构的标准手法（Django、SQLAlchemy 都用过）。plan 明确禁止了两种危险的兼容方式且理由充分： 1. 禁止 `from 新路径 import *` — 会创建新名称绑定而非别名，破坏模块身份 2. 禁止"新路径回指旧路径"完成态 — 会制造反向依赖 ### 停点规则：6 条，全部必要 分布在阶段 2（2条）、阶段 4（3条）、阶段 5（1条），针对"不先完成 X 就不允许做 Y"的真实风险，无多余停点。 ### 无过度兜底/静默回退 plan 全文未使用任何"try-except 吞异常"、"双路径猜测"、"签名探测重试"式设计。第 51 行明确禁止"不允许根层兼容入口做成签名探测、吞异常重试、双路径猜测或第二事实源"。 ### 一个改进点 plan 禁止了错误做法但未给出推荐的正确做法示例（见 F01）。
- 问题:
  - [中] 可维护性: 兼容薄门面缺少推荐实现机制示例

### R3-logic-bugs · 第三轮：逻辑严谨性与 BUG 检测（深度追踪）

- 状态: 已完成
- 记录时间: 2026-04-12T06:10:36.228Z
- 已审模块: SP05 plan 阶段 3 服务迁移, SP05 plan 阶段 4 路由迁移, SP05 plan 阶段 5 门禁同步, SP05 plan 完成判定与验证命令
- 摘要:

  ## 结论：逻辑严谨，无重大 BUG

  深入追踪全部引用链后，plan 的逻辑整体严谨。发现 3 个中等问题和 2 个低等问题，均为**措辞精确性**问题而非**逻辑漏洞**。

  ### 关键验证结果

  **1. 15 个路由文件共享导入完整追踪**

  | 需要绝对导入改写的文件 | 共享工具 |
  |---|---|
  | `scheduler_bp.py` | `.enum_display` |
  | `scheduler_config.py` | `_safe_next_url` |
  | `scheduler_run.py` | `.excel_utils` |
  | `scheduler_batches.py` | `.excel_utils`、`.pagination`、`_safe_next_url` |
  | `scheduler_analysis.py` | `.normalizers` |
  | `scheduler_gantt.py` | `.normalizers` |
  | `scheduler_week_plan.py` | `.excel_utils`、`.normalizers` |
  | `scheduler_excel_calendar.py` | `.excel_utils` |
  | `scheduler_excel_batches.py` | `.excel_utils` |
  | `scheduler_utils.py` | `.excel_utils`、`.normalizers` |

  不需要改写的 4 个文件：`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`——它们只引用同域文件或绝对路径。

  **2. 10 个 `import web.routes.scheduler_*` 的测试全部通过薄门面兼容**

  追踪确认这些测试通过模块级 `import ... as route_mod` + `monkeypatch.setattr(route_mod, ...)` 工作，在"同一模块对象"语义下无需修改。

  **3. `_check_architecture_layers` 的非递归扫描是真实 BUG**

  `generate_conformance_report.py:427` 用 `os.listdir(route_dir)` 只扫顶层，而服务侧 `:448` 用 `os.walk`。迁移后路由消失于报告。plan 正确识别了这一问题。

  **4. `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 的 glob 自动兼容**

  `web/routes/**/*.py` 中 `**` 匹配任意层目录，`domains/scheduler/*.py` 自动包含。无需修改。

  **5. 无循环导入风险**

  `schedule_service.py` 迁移后对 `.run/.config/.summary` 的导入不会形成循环——子包中无文件反向导入 `schedule_service.py`。
- 结论:

  ## 结论：逻辑严谨，无重大 BUG 深入追踪全部引用链后，plan 的逻辑整体严谨。发现 3 个中等问题和 2 个低等问题，均为**措辞精确性**问题而非**逻辑漏洞**。 ### 关键验证结果 **1. 15 个路由文件共享导入完整追踪** | 需要绝对导入改写的文件 | 共享工具 | |---|---| | `scheduler_bp.py` | `.enum_display` | | `scheduler_config.py` | `_safe_next_url` | | `scheduler_run.py` | `.excel_utils` | | `scheduler_batches.py` | `.excel_utils`、`.pagination`、`_safe_next_url` | | `scheduler_analysis.py` | `.normalizers` | | `scheduler_gantt.py` | `.normalizers` | | `scheduler_week_plan.py` | `.excel_utils`、`.normalizers` | | `scheduler_excel_calendar.py` | `.excel_utils` | | `scheduler_excel_batches.py` | `.excel_utils` | | `scheduler_utils.py` | `.excel_utils`、`.normalizers` | 不需要改写的 4 个文件：`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`——它们只引用同域文件或绝对路径。 **2. 10 个 `import web.routes.scheduler_*` 的测试全部通过薄门面兼容** 追踪确认这些测试通过模块级 `import ... as route_mod` + `monkeypatch.setattr(route_mod, ...)` 工作，在"同一模块对象"语义下无需修改。 **3. `_check_architecture_layers` 的非递归扫描是真实 BUG** `generate_conformance_report.py:427` 用 `os.listdir(route_dir)` 只扫顶层，而服务侧 `:448` 用 `os.walk`。迁移后路由消失于报告。plan 正确识别了这一问题。 **4. `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 的 glob 自动兼容** `web/routes/**/*.py` 中 `**` 匹配任意层目录，`domains/scheduler/*.py` 自动包含。无需修改。 **5. 无循环导入风险** `schedule_service.py` 迁移后对 `.run/.config/.summary` 的导入不会形成循环——子包中无文件反向导入 `schedule_service.py`。
- 问题:
  - [中] 可维护性: Blueprint __name__ 迁移影响分析不充分
  - [中] 可维护性: 回归测试未区分“需修改”与“只需验证”两类
  - [低] 可维护性: 共享导入改写清单“至少”措辞引起疑虑

## 最终结论

## 结论：逻辑严谨，无重大 BUG 深入追踪全部引用链后，plan 的逻辑整体严谨。发现 3 个中等问题和 2 个低等问题，均为**措辞精确性**问题而非**逻辑漏洞**。 ### 关键验证结果 **1. 15 个路由文件共享导入完整追踪** | 需要绝对导入改写的文件 | 共享工具 | |---|---| | `scheduler_bp.py` | `.enum_display` | | `scheduler_config.py` | `_safe_next_url` | | `scheduler_run.py` | `.excel_utils` | | `scheduler_batches.py` | `.excel_utils`、`.pagination`、`_safe_next_url` | | `scheduler_analysis.py` | `.normalizers` | | `scheduler_gantt.py` | `.normalizers` | | `scheduler_week_plan.py` | `.excel_utils`、`.normalizers` | | `scheduler_excel_calendar.py` | `.excel_utils` | | `scheduler_excel_batches.py` | `.excel_utils` | | `scheduler_utils.py` | `.excel_utils`、`.normalizers` | 不需要改写的 4 个文件：`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`——它们只引用同域文件或绝对路径。 **2. 10 个 `import web.routes.scheduler_*` 的测试全部通过薄门面兼容** 追踪确认这些测试通过模块级 `import ... as route_mod` + `monkeypatch.setattr(route_mod, ...)` 工作，在"同一模块对象"语义下无需修改。 **3. `_check_architecture_layers` 的非递归扫描是真实 BUG** `generate_conformance_report.py:427` 用 `os.listdir(route_dir)` 只扫顶层，而服务侧 `:448` 用 `os.walk`。迁移后路由消失于报告。plan 正确识别了这一问题。 **4. `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 的 glob 自动兼容** `web/routes/**/*.py` 中 `**` 匹配任意层目录，`domains/scheduler/*.py` 自动包含。无需修改。 **5. 无循环导入风险** `schedule_service.py` 迁移后对 `.run/.config/.summary` 的导入不会形成循环——子包中无文件反向导入 `schedule_service.py`。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnvd404m-bpio8k",
  "createdAt": "2026-04-12T00:00:00.000Z",
  "updatedAt": "2026-04-12T06:10:36.228Z",
  "finalizedAt": null,
  "status": "in_progress",
  "overallDecision": null,
  "header": {
    "title": "SP05 目录骨架与路径门禁 Plan 三轮深度审查",
    "date": "2026-04-12",
    "overview": "对 SP05 子 plan 进行三轮深度审查：目标达成性、设计优雅性、逻辑严谨性与 BUG 检测"
  },
  "scope": {
    "markdown": "# SP05 目录骨架与路径门禁 — Plan 三轮深度审查\n\n## 审查对象\n- `.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md`\n\n## 审查方法\n三轮递进式深度审查：\n1. **第一轮：目标达成性与完备性** — plan 能否达成目的\n2. **第二轮：设计优雅性与过度工程检测** — 是否简洁、是否有过度兜底/静默回退\n3. **第三轮：逻辑严谨性与 BUG 检测** — 深入引用链追踪，检查逻辑漏洞\n\n## 审查范围\n追踪了以下完整引用链：\n- `schedule_service.py` 全部 15 条根层导入\n- `scheduler.py` → `scheduler_pages.py` 副作用导入链\n- `factory.py` 蓝图注册链\n- `scheduler_bp.py` 的 `Blueprint(\"scheduler\", __name__)` 语义\n- `_safe_next_url` 全部 3 个消费者（`scheduler_config.py`、`scheduler_batches.py`、`system_ui_mode.py`）\n- `LOCAL_PARSE_HELPER_ALLOWLIST` 全部 10 条路径条目\n- `REQUEST_SERVICE_TARGET_FILES` 全部 11 条路径条目\n- `REQUEST_SERVICE_TARGET_ALLOWED_HELPERS` 全部 2 条条目及 `line` 字段\n- `_check_architecture_layers` 路由侧 `os.listdir` vs 服务侧 `os.walk` 不对称\n- `test_source_merge_mode_constants.py` 的 `targets` 列表\n- `regression_excel_routes_no_tx_surface_hidden.py` 的 `targets` 列表\n- 全部 15 个路由文件的根层共享工具导入清单\n- 全部 10 个按旧路径 `import web.routes.scheduler_*` 的测试文件\n- 全部 7 个使用模块级替换/注入合同的回归测试"
  },
  "summary": {
    "latestConclusion": "## 结论：逻辑严谨，无重大 BUG 深入追踪全部引用链后，plan 的逻辑整体严谨。发现 3 个中等问题和 2 个低等问题，均为**措辞精确性**问题而非**逻辑漏洞**。 ### 关键验证结果 **1. 15 个路由文件共享导入完整追踪** | 需要绝对导入改写的文件 | 共享工具 | |---|---| | `scheduler_bp.py` | `.enum_display` | | `scheduler_config.py` | `_safe_next_url` | | `scheduler_run.py` | `.excel_utils` | | `scheduler_batches.py` | `.excel_utils`、`.pagination`、`_safe_next_url` | | `scheduler_analysis.py` | `.normalizers` | | `scheduler_gantt.py` | `.normalizers` | | `scheduler_week_plan.py` | `.excel_utils`、`.normalizers` | | `scheduler_excel_calendar.py` | `.excel_utils` | | `scheduler_excel_batches.py` | `.excel_utils` | | `scheduler_utils.py` | `.excel_utils`、`.normalizers` | 不需要改写的 4 个文件：`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`——它们只引用同域文件或绝对路径。 **2. 10 个 `import web.routes.scheduler_*` 的测试全部通过薄门面兼容** 追踪确认这些测试通过模块级 `import ... as route_mod` + `monkeypatch.setattr(route_mod, ...)` 工作，在\"同一模块对象\"语义下无需修改。 **3. `_check_architecture_layers` 的非递归扫描是真实 BUG** `generate_conformance_report.py:427` 用 `os.listdir(route_dir)` 只扫顶层，而服务侧 `:448` 用 `os.walk`。迁移后路由消失于报告。plan 正确识别了这一问题。 **4. `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 的 glob 自动兼容** `web/routes/**/*.py` 中 `**` 匹配任意层目录，`domains/scheduler/*.py` 自动包含。无需修改。 **5. 无循环导入风险** `schedule_service.py` 迁移后对 `.run/.config/.summary` 的导入不会形成循环——子包中无文件反向导入 `schedule_service.py`。",
    "recommendedNextAction": null,
    "reviewedModules": [
      "SP05 plan 目标定义",
      "SP05 plan 范围边界",
      "SP05 plan 实施前确认",
      "SP05 plan 执行编排",
      "SP05 plan 兼容策略",
      "SP05 plan 停点规则",
      "SP05 plan 阶段 3 服务迁移",
      "SP05 plan 阶段 4 路由迁移",
      "SP05 plan 阶段 5 门禁同步",
      "SP05 plan 完成判定与验证命令"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 4,
    "severity": {
      "high": 0,
      "medium": 3,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "R1-goal-completeness",
      "title": "第一轮：目标达成性与完备性审查",
      "status": "completed",
      "recordedAt": "2026-04-12T06:08:18.261Z",
      "summaryMarkdown": "## 结论：plan 能够达成其核心目标\n\nplan 的核心目标是\"给后续 SP06~SP10 建立统一路径口径\"，而非\"移动文件\"。这一定位是正确的。\n\n### 已验证的关键事实\n\n1. **`scheduler.py` ↔ `scheduler_pages.py` 聚合缺口已正确识别**：当前 `scheduler.py` 直接导入 4 个模块（`excel_batches`/`excel_calendar`/`gantt`/`week_plan`），而 `scheduler_pages.py` 不包含它们。plan 在阶段 4 第 2 点要求\"补入副作用导入\"，正确。\n\n2. **`_safe_next_url` 消费者清单完整**：搜索确认恰好 3 个消费者（`scheduler_config.py:27`、`scheduler_batches.py:23`、`system_ui_mode.py:9`），plan 全部覆盖。\n\n3. **`test_source_merge_mode_constants.py` 影响范围精确**：5 个 `targets` 中仅 `schedule_optimizer.py` 和 `freeze_window.py` 受 SP05 影响，plan 正确只改这两项。\n\n4. **12 条实施前确认全部有据**：逐条核实了蓝图注册链（`factory.py:373`）、`schedule_service.py` 的 15 条导入、`quality_gate_shared.py` 的门禁常量等，均与实际代码吻合。\n\n5. **\"不做什么\"边界清晰**：7 条禁止项有效防止了范围蠕变，特别是\"不把目录迁移和行为改造混在一个提交里\"与\"不顺手回头改请求级装配\"。",
      "conclusionMarkdown": "## 结论：plan 能够达成其核心目标 plan 的核心目标是\"给后续 SP06~SP10 建立统一路径口径\"，而非\"移动文件\"。这一定位是正确的。 ### 已验证的关键事实 1. **`scheduler.py` ↔ `scheduler_pages.py` 聚合缺口已正确识别**：当前 `scheduler.py` 直接导入 4 个模块（`excel_batches`/`excel_calendar`/`gantt`/`week_plan`），而 `scheduler_pages.py` 不包含它们。plan 在阶段 4 第 2 点要求\"补入副作用导入\"，正确。 2. **`_safe_next_url` 消费者清单完整**：搜索确认恰好 3 个消费者（`scheduler_config.py:27`、`scheduler_batches.py:23`、`system_ui_mode.py:9`），plan 全部覆盖。 3. **`test_source_merge_mode_constants.py` 影响范围精确**：5 个 `targets` 中仅 `schedule_optimizer.py` 和 `freeze_window.py` 受 SP05 影响，plan 正确只改这两项。 4. **12 条实施前确认全部有据**：逐条核实了蓝图注册链（`factory.py:373`）、`schedule_service.py` 的 15 条导入、`quality_gate_shared.py` 的门禁常量等，均与实际代码吻合。 5. **\"不做什么\"边界清晰**：7 条禁止项有效防止了范围蠕变，特别是\"不把目录迁移和行为改造混在一个提交里\"与\"不顺手回头改请求级装配\"。",
      "evidence": [
        {
          "path": "web/routes/scheduler.py",
          "lineStart": 11,
          "lineEnd": 22,
          "symbol": "scheduler.py 当前导入链"
        },
        {
          "path": "web/routes/scheduler_pages.py",
          "lineStart": 1,
          "lineEnd": 16,
          "symbol": "scheduler_pages.py 当前聚合范围"
        },
        {
          "path": "web/routes/system_utils.py",
          "lineStart": 19,
          "lineEnd": 43,
          "symbol": "_safe_next_url 唯一定义"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 31,
          "lineEnd": 31,
          "symbol": "factory.py 蓝图导入"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 373,
          "lineEnd": 373,
          "symbol": "factory.py 蓝图注册"
        },
        {
          "path": "tests/test_source_merge_mode_constants.py",
          "lineStart": 93,
          "lineEnd": 99,
          "symbol": "targets 列表"
        }
      ],
      "reviewedModules": [
        "SP05 plan 目标定义",
        "SP05 plan 范围边界",
        "SP05 plan 实施前确认"
      ],
      "recommendedNextAction": null,
      "findingIds": []
    },
    {
      "id": "R2-elegance",
      "title": "第二轮：设计优雅性与过度工程检测",
      "status": "completed",
      "recordedAt": "2026-04-12T06:08:52.737Z",
      "summaryMarkdown": "## 结论：设计简洁、无过度工程\n\n### 6 阶段编排：合理无冗余\n每个阶段都有明确的前置依赖和产物，无多余分解。Phase 3 拆为 3A/3B/3C 是因为 config/summary 与 run 有不同的边界清晰度，合理。\n\n### \"兼容薄门面\"策略：标准做法\n这是 Python 大型项目包重构的标准手法（Django、SQLAlchemy 都用过）。plan 明确禁止了两种危险的兼容方式且理由充分：\n1. 禁止 `from 新路径 import *` — 会创建新名称绑定而非别名，破坏模块身份\n2. 禁止\"新路径回指旧路径\"完成态 — 会制造反向依赖\n\n### 停点规则：6 条，全部必要\n分布在阶段 2（2条）、阶段 4（3条）、阶段 5（1条），针对\"不先完成 X 就不允许做 Y\"的真实风险，无多余停点。\n\n### 无过度兜底/静默回退\nplan 全文未使用任何\"try-except 吞异常\"、\"双路径猜测\"、\"签名探测重试\"式设计。第 51 行明确禁止\"不允许根层兼容入口做成签名探测、吞异常重试、双路径猜测或第二事实源\"。\n\n### 一个改进点\nplan 禁止了错误做法但未给出推荐的正确做法示例（见 F01）。",
      "conclusionMarkdown": "## 结论：设计简洁、无过度工程 ### 6 阶段编排：合理无冗余 每个阶段都有明确的前置依赖和产物，无多余分解。Phase 3 拆为 3A/3B/3C 是因为 config/summary 与 run 有不同的边界清晰度，合理。 ### \"兼容薄门面\"策略：标准做法 这是 Python 大型项目包重构的标准手法（Django、SQLAlchemy 都用过）。plan 明确禁止了两种危险的兼容方式且理由充分： 1. 禁止 `from 新路径 import *` — 会创建新名称绑定而非别名，破坏模块身份 2. 禁止\"新路径回指旧路径\"完成态 — 会制造反向依赖 ### 停点规则：6 条，全部必要 分布在阶段 2（2条）、阶段 4（3条）、阶段 5（1条），针对\"不先完成 X 就不允许做 Y\"的真实风险，无多余停点。 ### 无过度兜底/静默回退 plan 全文未使用任何\"try-except 吞异常\"、\"双路径猜测\"、\"签名探测重试\"式设计。第 51 行明确禁止\"不允许根层兼容入口做成签名探测、吞异常重试、双路径猜测或第二事实源\"。 ### 一个改进点 plan 禁止了错误做法但未给出推荐的正确做法示例（见 F01）。",
      "evidence": [],
      "reviewedModules": [
        "SP05 plan 执行编排",
        "SP05 plan 兼容策略",
        "SP05 plan 停点规则"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F01"
      ]
    },
    {
      "id": "R3-logic-bugs",
      "title": "第三轮：逻辑严谨性与 BUG 检测（深度追踪）",
      "status": "completed",
      "recordedAt": "2026-04-12T06:10:36.228Z",
      "summaryMarkdown": "## 结论：逻辑严谨，无重大 BUG\n\n深入追踪全部引用链后，plan 的逻辑整体严谨。发现 3 个中等问题和 2 个低等问题，均为**措辞精确性**问题而非**逻辑漏洞**。\n\n### 关键验证结果\n\n**1. 15 个路由文件共享导入完整追踪**\n\n| 需要绝对导入改写的文件 | 共享工具 |\n|---|---|\n| `scheduler_bp.py` | `.enum_display` |\n| `scheduler_config.py` | `_safe_next_url` |\n| `scheduler_run.py` | `.excel_utils` |\n| `scheduler_batches.py` | `.excel_utils`、`.pagination`、`_safe_next_url` |\n| `scheduler_analysis.py` | `.normalizers` |\n| `scheduler_gantt.py` | `.normalizers` |\n| `scheduler_week_plan.py` | `.excel_utils`、`.normalizers` |\n| `scheduler_excel_calendar.py` | `.excel_utils` |\n| `scheduler_excel_batches.py` | `.excel_utils` |\n| `scheduler_utils.py` | `.excel_utils`、`.normalizers` |\n\n不需要改写的 4 个文件：`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`——它们只引用同域文件或绝对路径。\n\n**2. 10 个 `import web.routes.scheduler_*` 的测试全部通过薄门面兼容**\n\n追踪确认这些测试通过模块级 `import ... as route_mod` + `monkeypatch.setattr(route_mod, ...)` 工作，在\"同一模块对象\"语义下无需修改。\n\n**3. `_check_architecture_layers` 的非递归扫描是真实 BUG**\n\n`generate_conformance_report.py:427` 用 `os.listdir(route_dir)` 只扫顶层，而服务侧 `:448` 用 `os.walk`。迁移后路由消失于报告。plan 正确识别了这一问题。\n\n**4. `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 的 glob 自动兼容**\n\n`web/routes/**/*.py` 中 `**` 匹配任意层目录，`domains/scheduler/*.py` 自动包含。无需修改。\n\n**5. 无循环导入风险**\n\n`schedule_service.py` 迁移后对 `.run/.config/.summary` 的导入不会形成循环——子包中无文件反向导入 `schedule_service.py`。",
      "conclusionMarkdown": "## 结论：逻辑严谨，无重大 BUG 深入追踪全部引用链后，plan 的逻辑整体严谨。发现 3 个中等问题和 2 个低等问题，均为**措辞精确性**问题而非**逻辑漏洞**。 ### 关键验证结果 **1. 15 个路由文件共享导入完整追踪** | 需要绝对导入改写的文件 | 共享工具 | |---|---| | `scheduler_bp.py` | `.enum_display` | | `scheduler_config.py` | `_safe_next_url` | | `scheduler_run.py` | `.excel_utils` | | `scheduler_batches.py` | `.excel_utils`、`.pagination`、`_safe_next_url` | | `scheduler_analysis.py` | `.normalizers` | | `scheduler_gantt.py` | `.normalizers` | | `scheduler_week_plan.py` | `.excel_utils`、`.normalizers` | | `scheduler_excel_calendar.py` | `.excel_utils` | | `scheduler_excel_batches.py` | `.excel_utils` | | `scheduler_utils.py` | `.excel_utils`、`.normalizers` | 不需要改写的 4 个文件：`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`——它们只引用同域文件或绝对路径。 **2. 10 个 `import web.routes.scheduler_*` 的测试全部通过薄门面兼容** 追踪确认这些测试通过模块级 `import ... as route_mod` + `monkeypatch.setattr(route_mod, ...)` 工作，在\"同一模块对象\"语义下无需修改。 **3. `_check_architecture_layers` 的非递归扫描是真实 BUG** `generate_conformance_report.py:427` 用 `os.listdir(route_dir)` 只扫顶层，而服务侧 `:448` 用 `os.walk`。迁移后路由消失于报告。plan 正确识别了这一问题。 **4. `REQUEST_SERVICE_SCAN_SCOPE_PATTERNS` 的 glob 自动兼容** `web/routes/**/*.py` 中 `**` 匹配任意层目录，`domains/scheduler/*.py` 自动包含。无需修改。 **5. 无循环导入风险** `schedule_service.py` 迁移后对 `.run/.config/.summary` 的导入不会形成循环——子包中无文件反向导入 `schedule_service.py`。",
      "evidence": [],
      "reviewedModules": [
        "SP05 plan 阶段 3 服务迁移",
        "SP05 plan 阶段 4 路由迁移",
        "SP05 plan 阶段 5 门禁同步",
        "SP05 plan 完成判定与验证命令"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F02",
        "F03",
        "F04"
      ]
    }
  ],
  "findings": [
    {
      "id": "F01",
      "severity": "medium",
      "category": "maintainability",
      "title": "兼容薄门面缺少推荐实现机制示例",
      "descriptionMarkdown": "plan 禁止 `from 新路径 import *` 式重导出，要求“同一模块对象语义”，但未明确给出推荐的实现机制。正确的做法应是 `sys.modules[__name__] = importlib.import_module('new.real.path')`。建议在阶段 2 的兼容薄门面规则中增加一句“推荐使用 `sys.modules` 替换实现同一模块对象语义”的显式指导，避免执行者自行发明其他机制。",
      "recommendationMarkdown": "在阶段 2 第 4 点补充推荐实现机制示例",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md",
          "lineStart": 199,
          "lineEnd": 205
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md"
        }
      ],
      "relatedMilestoneIds": [
        "R2-elegance"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F02",
      "severity": "medium",
      "category": "maintainability",
      "title": "Blueprint __name__ 迁移影响分析不充分",
      "descriptionMarkdown": "plan 阶段 4 第 4 点仅说“需做一次显式启动/页面验证”，但未分析影响机制。实际追踪：\n\n`scheduler_bp.py` 当前：`Blueprint(\"scheduler\", __name__)` → `__name__ == \"web.routes.scheduler_bp\"`\n迁移后：`Blueprint(\"scheduler\", __name__)` → `__name__ == \"web.routes.domains.scheduler.scheduler_bp\"`\n\nFlask 用 `import_name` 确定 Blueprint 的 `root_path`，影响 `static_folder`/`template_folder` 的相对路径解析。但该 Blueprint **未设置自身的 `static_folder`/`template_folder`**，模板和静态文件均由应用级配置管理。因此 `__name__` 变化对 `url_for`、模板渲染和静态文件解析**均无影响**。\n\n建议将此分析结论写入阶段 2（导入策略阶段），而非留到阶段 4 才验证。",
      "recommendationMarkdown": "在阶段 2 明确写明 `Blueprint __name__` 变化安全性分析，不必延后验证",
      "evidence": [
        {
          "path": "web/routes/scheduler_bp.py",
          "lineStart": 10,
          "lineEnd": 11,
          "symbol": "Blueprint(\"scheduler\", __name__)"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md",
          "lineStart": 256,
          "lineEnd": 256
        },
        {
          "path": "web/routes/scheduler_bp.py"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP05_目录骨架与路径门禁.md"
        }
      ],
      "relatedMilestoneIds": [
        "R3-logic-bugs"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F03",
      "severity": "medium",
      "category": "maintainability",
      "title": "回归测试未区分“需修改”与“只需验证”两类",
      "descriptionMarkdown": "plan 阶段 5 第 6 点将全部回归测试统一列为“必须同批更新”，但实际追踪发现存在两类测试：\n\n**类型 A：需要修改代码的测试**（按文件路径读源码/硬编码路径常量）：\n- `regression_excel_routes_no_tx_surface_hidden.py` — `targets` 列表硬编码 `web/routes/scheduler_excel_batches.py`\n- `test_source_merge_mode_constants.py` — `targets` 列表硬编码 `core/services/scheduler/schedule_optimizer.py`\n- `test_architecture_fitness.py` — `LOCAL_PARSE_HELPER_ALLOWLIST` 硬编码路径\n- `tools/quality_gate_shared.py` — `REQUEST_SERVICE_TARGET_FILES` 硬编码路径\n\n**类型 B：不需要修改代码的测试**（通过模块导入，兼容薄门面自动透明）：\n- `regression_schedule_service_facade_delegation.py` — `import core.services.scheduler.schedule_service as schedule_service_mod` + 模块级替换\n- `regression_dict_cfg_contract.py` — `import core.services.scheduler.schedule_optimizer as schedule_optimizer` + 模块级替换\n- `regression_optimizer_zero_weight_cfg_preserved.py` — 同上\n- `regression_scheduler_config_route_contract.py` — `import web.routes.scheduler_config as route_mod` + monkeypatch\n- 另 6 个 `import web.routes.scheduler_*` 的路由合同回归\n\n类型 B 测试在兼容薄门面正确实现后无需任何修改即可通过。plan 未区分这两类，可能导致执行者对类型 B 测试做不必要的代码修改，反而引入新问题。",
      "recommendationMarkdown": "在阶段 5 第 6 点明确区分“需要修改代码”和“只需验证通过”两类测试",
      "evidence": [
        {
          "path": "tests/regression_schedule_service_facade_delegation.py",
          "lineStart": 83,
          "lineEnd": 86,
          "symbol": "schedule_service_mod.模块级替换"
        },
        {
          "path": "tests/regression_scheduler_config_route_contract.py",
          "lineStart": 33,
          "lineEnd": 35,
          "symbol": "import web.routes.scheduler_config as route_mod"
        },
        {
          "path": "tests/regression_excel_routes_no_tx_surface_hidden.py",
          "lineStart": 27,
          "lineEnd": 32,
          "symbol": "硬编码路径 targets"
        },
        {
          "path": "tests/regression_scheduler_run_surfaces_resource_pool_warning.py",
          "lineStart": 17,
          "lineEnd": 17,
          "symbol": "import web.routes.scheduler_run as route_mod"
        },
        {
          "path": "tests/regression_schedule_service_facade_delegation.py"
        },
        {
          "path": "tests/regression_scheduler_config_route_contract.py"
        },
        {
          "path": "tests/regression_excel_routes_no_tx_surface_hidden.py"
        },
        {
          "path": "tests/regression_scheduler_run_surfaces_resource_pool_warning.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3-logic-bugs"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F04",
      "severity": "low",
      "category": "maintainability",
      "title": "共享导入改写清单“至少”措辞引起疑虑",
      "descriptionMarkdown": "阶段 4 第 3 点的共享导入改写清单以“至少覆盖”开头，但实际追踪全部 15 个路由文件后发现，清单实际上已经 **完整**覆盖了所有需要改写的共享导入。未被列出的 4 个文件（`scheduler_batch_detail.py`、`scheduler_ops.py`、`scheduler_resource_dispatch.py`、`scheduler_calendar_pages.py`）确实不包含需要改写的根层共享工具导入。但“至少”措辞会给执行者造成不必要的疑虑。",
      "recommendationMarkdown": "将“至少覆盖”改为“完整覆盖（以下 4 个文件无需改写：...）”",
      "evidence": [
        {
          "path": "web/routes/scheduler_batch_detail.py",
          "lineStart": 1,
          "lineEnd": 11,
          "symbol": "无根层共享工具导入"
        },
        {
          "path": "web/routes/scheduler_ops.py",
          "lineStart": 1,
          "lineEnd": 8,
          "symbol": "无根层共享工具导入"
        },
        {
          "path": "web/routes/scheduler_resource_dispatch.py",
          "lineStart": 1,
          "lineEnd": 14,
          "symbol": "无根层共享工具导入"
        },
        {
          "path": "web/routes/scheduler_calendar_pages.py",
          "lineStart": 1,
          "lineEnd": 11,
          "symbol": "无根层共享工具导入"
        },
        {
          "path": "web/routes/scheduler_batch_detail.py"
        },
        {
          "path": "web/routes/scheduler_ops.py"
        },
        {
          "path": "web/routes/scheduler_resource_dispatch.py"
        },
        {
          "path": "web/routes/scheduler_calendar_pages.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3-logic-bugs"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:9f9addcd670f3371e8023ba97bb07e1f725ae42283a2c4b672902a04f43d9041",
    "generatedAt": "2026-04-12T06:10:36.228Z",
    "locale": "zh-CN"
  }
}
```

# 20260405 技术债务双plan三轮深度review
- 日期: 2026-04-05
- 概述: 对两份技术债务 plan 做三轮深审，核对覆盖性、实现优雅性、反兜底约束、逻辑严谨性与可执行性，并据此输出合并方向。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 技术债务双plan三轮深度review

## 审查对象
- `.limcode/plans/20260405_技术债务修复总plan.md`
- `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`

## 审查目标
1. 判断两份 plan 是否能覆盖两份技术债务 review 已确认的问题。
2. 判断实施路径是否优雅、简洁，是否会引入新的过度兜底、静默回退或抽象过度。
3. 判断 plan 本身是否存在路径错误、顺序错误、验证命令错误或无法在当前仓库执行的 BUG。
4. 形成一份可直接执行的最终合并 plan。

## 审查方法
- 以两份 review 为事实源核对问题覆盖。
- 抽读关键实现文件，验证 plan 中的路径、依赖关系与拆分边界是否真实存在。
- 重点检查：调度主链、配置链、数据基础设施、路由与模板、前端脚本、测试门禁。

## 初步结论
- `20260405_技术债务修复总plan.md` 的**覆盖面更完整、批次顺序更合理、反静默回退约束更强**，适合作为最终 plan 的主骨架。
- `aps排产系统技术债务综合修复计划.plan.md` 的**任务颗粒度、验证意识、步骤化表达更强**，适合吸收进最终 plan 的实施细节。
- 两份 plan **都不能原样直接执行**：第一份存在目录/路径冲突与局部命名不一致，第二份存在覆盖缺口、占位符、验证命令错误与若干过度抽象风险。
- 结论：应以“第一份作主骨架 + 第二份作步骤化细化 + 修正两边 BUG/冲突”的方式重写最终合并 plan。

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/plans/20260405_技术债务修复总plan.md, .limcode/plans/aps排产系统技术债务综合修复计划.plan.md, core/services/common/degradation.py, core/services/scheduler/schedule_summary_degradation.py, web/routes/scheduler_excel_calendar.py, web/routes/process_excel_part_operation_hours.py, static/js/gantt.js, static/js/gantt_boot.js, static/js/resource_dispatch.js, core/algorithms/greedy/scheduler.py, core/services/scheduler/schedule_input_builder.py, core/services/scheduler/freeze_window.py, core/services/scheduler/schedule_optimizer_steps.py, tests/test_architecture_fitness.py, requirements-dev.txt, .limcode/plans/20260405_技术债务最终合并修复plan.md
- 当前进度: 已记录 3 个里程碑；最新：R3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 9
- 问题严重级别分布: 高 4 / 中 5 / 低 0
- 最新结论: 三轮 review 结论：两份原始 plan 都不适合原样执行，但可以条件性接受其组合思路。最终应以 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 作为唯一权威执行 plan：它保留了总plan的完整覆盖能力，吸收了综合修复计划的步骤化细节，并显式修复了覆盖缺口、route 路径冲突、错误文件路径、占位步骤、无效验证命令以及过度抽象风险。
- 下一步建议: 后续实施只以 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 为准，原两份 plan 仅保留为历史输入，不再直接执行。
- 总体结论: 有条件通过

## 评审发现

### 综合修复计划存在覆盖缺口

- ID: plan-coverage-gap
- 严重级别: 高
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R1
- 说明:

  `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md` 虽然在问题清单中列出了 A5/A7/B3/B4/C3/C6/E6，但在后文又把这些问题转为“中长期架构演进”并明确不在本 plan 中设置具体步骤。这与用户要求的“覆盖两份 plan 里验证正确的所有技术债务”直接冲突。
- 建议:

  最终合并 plan 必须把这些问题拉回到正式任务中，可分阶段、可降优先级，但不能脱离主 plan。
- 证据:
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:867-879`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `.limcode/review/20260405_技术债务全面梳理.md`
  - `.limcode/review/aps排产系统技术债务全面梳理.md`

### 总plan更适合作为主骨架

- ID: plan-main-skeleton-stronger
- 严重级别: 中
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R1
- 说明:

  总 plan 提供了完整的问题覆盖矩阵、接受风险边界、批次依赖关系和横向治理约束，尤其明确禁止新增临时兼容桥、静默回退、整页复制模板与根目录平铺测试文件，更符合本轮治理目标。
- 建议:

  以总 plan 为主骨架，吸收综合修复计划中更细的步骤与验证项。
- 证据:
  - `.limcode/plans/20260405_技术债务修复总plan.md:522-588`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `.limcode/review/20260405_技术债务全面梳理.md`
  - `.limcode/review/aps排产系统技术债务全面梳理.md`

### Excel 导入控制器存在过泛化风险

- ID: plan-excel-flow-overabstracted
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  综合修复计划建议建立 `ExcelImportController`，把多个 Excel 页面统一抽象为 `blueprint/url_prefix/template_name/parser_factory/validator_factory/applier_factory/entity_label` 的总控制器。但当前各页面在模式限制、额外基线状态、预览后行状态改写、导出链路和页面渲染上下文上差异明显，直接用一个总控制器容易形成回调拼装与分支爆炸，后续反而更难维护。
- 建议:

  改为 pageflow/钩子式流程：统一预览-确认骨架，但把数据规范化、额外状态、结果渲染和导出保留在领域适配层。
- 证据:
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:661-709`
  - `web/routes/scheduler_excel_calendar.py:146-259`
  - `web/routes/process_excel_part_operation_hours.py:239-260`
  - `core/services/common/degradation.py`
  - `core/services/scheduler/schedule_summary_degradation.py`
  - `web/routes/scheduler_excel_calendar.py`
  - `web/routes/process_excel_part_operation_hours.py`
  - `static/js/gantt.js`
  - `static/js/gantt_boot.js`
  - `static/js/resource_dispatch.js`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `web/routes/process_excel_suppliers.py`

### 前端初始化方案不应再造全局总命名空间

- ID: plan-front-init-global-registry-risk
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  当前前端已经依赖 `window.__APS_COMMON__` 与 `window.__APS_GANTT__`。若再新增 `window.__APS_PAGES__` 作为新的总注册表，只是把多个全局对象换成另一个更大的全局对象，并没有真正降低模板与脚本间的隐式耦合。
- 建议:

  采用单点 `page_boot` + DOM `data-page` / `data-*` 协议，页面脚本只暴露局部初始化函数，不再扩张新的 window 级命名空间。
- 证据:
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:739-774`
  - `static/js/gantt.js:1-254`
  - `static/js/gantt_boot.js:220-246`
  - `static/js/resource_dispatch.js:1-83`
  - `core/services/common/degradation.py`
  - `core/services/scheduler/schedule_summary_degradation.py`
  - `web/routes/scheduler_excel_calendar.py`
  - `web/routes/process_excel_part_operation_hours.py`
  - `static/js/gantt.js`
  - `static/js/gantt_boot.js`
  - `static/js/resource_dispatch.js`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`

### 降级收口不能再造第二套事实源

- ID: plan-degradation-double-source-risk
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2
- 说明:

  总 plan 提出新增 `degradation_report.py` 统一降级状态，这是正确方向；但当前仓库已经有 `core/services/common/degradation.py` 的稳定降级事件模型，以及 `schedule_summary_degradation.py` 的摘要汇总逻辑。如果直接新建平行对象而不复用现有模型，会把“降级事实源收口”做成“降级事实源再复制一次”。
- 建议:

  最终合并 plan 应明确：复用 `DegradationCollector` 与稳定事件码，只允许新增统一装配层，不允许新增平行事件模型。
- 证据:
  - `.limcode/plans/20260405_技术债务修复总plan.md:255-274`
  - `core/services/common/degradation.py:6-130`
  - `core/services/scheduler/schedule_summary_degradation.py:161-321`
  - `core/services/common/degradation.py`
  - `core/services/scheduler/schedule_summary_degradation.py`
  - `web/routes/scheduler_excel_calendar.py`
  - `web/routes/process_excel_part_operation_hours.py`
  - `static/js/gantt.js`
  - `static/js/gantt_boot.js`
  - `static/js/resource_dispatch.js`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`

### 总plan的 route 子包化存在路径冲突

- ID: plan-route-package-collision
- 严重级别: 高
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  总 plan 同时要求新建 `web/routes/scheduler/`、`web/routes/process/`、`web/routes/personnel/`、`web/routes/equipment/`、`web/routes/system/`，又要求保留现有 `web/routes/*.py` 顶层入口做薄兼容壳。当前仓库已经存在同名文件 `scheduler.py`、`process.py`、`personnel.py`、`equipment.py`、`system.py`，在 Windows 与常见文件系统上，文件与同名目录不能并存，因此该改造顺序按原文无法落地。
- 建议:

  最终合并 plan 应采用“文件转包”的确定顺序：先临时改名旧入口，再创建同名目录与 `__init__.py`，最后删除临时壳；不要要求同名文件与目录共存。
- 证据:
  - `.limcode/plans/20260405_技术债务修复总plan.md:185-192`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/freeze_window.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `tests/test_architecture_fitness.py`
  - `requirements-dev.txt`
  - `web/routes/scheduler.py`
  - `web/routes/process.py`
  - `web/routes/personnel.py`
  - `web/routes/equipment.py`
  - `web/routes/system.py`

### 总plan存在算法文件路径错误与目录归属不一致

- ID: plan-algorithm-path-bugs
- 严重级别: 高
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  总 plan 在算法任务中引用了 `core/algorithms/greedy/types.py`、`core/algorithms/greedy/evaluation.py`、`core/algorithms/greedy/dispatch_rules.py`，但当前仓库真实路径分别位于 `core/algorithms/types.py`、`core/algorithms/evaluation.py`、`core/algorithms/dispatch_rules.py`。同时它一边创建 `core/services/scheduler/config/` 与 `run/` 子目录，一边又把 `config_schema.py`、`run_command.py`、`run_context.py` 放在根层，目录归属前后不一致。
- 建议:

  最终合并 plan 只允许使用真实路径，并统一规则：若已决定子包化，新文件应优先进入对应子包，由根层仅保留有限门面。
- 证据:
  - `.limcode/plans/20260405_技术债务修复总plan.md:219-228`
  - `.limcode/plans/20260405_技术债务修复总plan.md:256-270`
  - `.limcode/plans/20260405_技术债务修复总plan.md:298-307`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/freeze_window.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `tests/test_architecture_fitness.py`
  - `requirements-dev.txt`
  - `core/algorithms/types.py`
  - `core/algorithms/evaluation.py`
  - `core/algorithms/dispatch_rules.py`

### 综合修复计划含占位符与验证命令 BUG

- ID: plan-step-placeholder-and-command-bugs
- 严重级别: 高
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  综合修复计划多处使用 `...` 作为步骤、函数签名或示例占位，降低可执行性；同时大量验证命令携带 `--timeout=120`，但当前 `requirements-dev.txt` 仅声明 `pytest`，未声明提供该参数的插件；另有测试文件名拼写错误 `regresheduler_apply_preset_reject_invalid_numeric.py`。这些问题会让执行者在真正落地时立即遇到命令失败。
- 建议:

  最终合并 plan 禁止使用占位符；验证命令只能使用当前仓库已声明依赖支持的参数；拼写错误必须在落盘前清零。
- 证据:
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:322-323`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:350-366`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:517-519`
  - `requirements-dev.txt:1-4`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/freeze_window.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `tests/test_architecture_fitness.py`
  - `requirements-dev.txt`

### 兼容桥清理应改成确定性收口步骤

- ID: plan-compat-cleanup-should-be-deterministic
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R3
- 说明:

  综合修复计划把 strict_mode 清理写成“先搜索确认所有 scheduler 实现都支持 strict_mode”。但当前代码中只有一个 `schedule()` 实现；`build_algo_operations()` 已支持 `strict_mode` 与 `return_outcome`，`build_freeze_window_seed()` 也已支持 `strict_mode` 与 `meta`。这意味着 `_scheduler_accepts_strict_mode`、`_schedule_with_optional_strict_mode`、`_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta` 已具备直接收口条件，不应继续写成开放式排查。
- 建议:

  最终合并 plan 应把这些兼容桥收口写成明确任务，并配套列出要删掉的函数名与回归用例。
- 证据:
  - `core/services/scheduler/schedule_optimizer_steps.py:85-115`
  - `core/services/scheduler/schedule_input_builder.py:243-253`
  - `core/services/scheduler/freeze_window.py:180-189`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/freeze_window.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `tests/test_architecture_fitness.py`
  - `requirements-dev.txt`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_input_collector.py`

## 评审里程碑

### R1 · 第一轮：范围覆盖与目标达成性审查

- 状态: 已完成
- 记录时间: 2026-04-05T15:30:06.590Z
- 已审模块: .limcode/plans/20260405_技术债务修复总plan.md, .limcode/plans/aps排产系统技术债务综合修复计划.plan.md
- 摘要:

  对照两份技术债务 review 的问题集合核对两份 plan 的覆盖范围、接受风险边界与治理顺序。结论：总 plan 的覆盖面完整，能把已确认且可整改的问题全部落入任务；综合修复计划虽然颗粒度更细，但把 A5/A7/B3/B4/C3/C6/E6 明确后移或单独开新 plan，无法单独满足“覆盖全部已验证技术债务”的目标。
- 结论:

  第一轮结论：最终合并 plan 必须以总 plan 的问题覆盖矩阵为基线，不能沿用综合修复计划对若干已确认债务的延期处理。
- 证据:
  - `.limcode/plans/20260405_技术债务修复总plan.md:522-558`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:48-104`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:867-879`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `.limcode/review/20260405_技术债务全面梳理.md`
  - `.limcode/review/aps排产系统技术债务全面梳理.md`
- 下一步建议:

  进入第二轮，审查两份 plan 的实现优雅性、抽象边界与反兜底约束。
- 问题:
  - [高] 文档: 综合修复计划存在覆盖缺口
  - [中] 文档: 总plan更适合作为主骨架

### R2 · 第二轮：实现优雅性、简洁性与反兜底约束审查

- 状态: 已完成
- 记录时间: 2026-04-05T15:30:37.984Z
- 已审模块: core/services/common/degradation.py, core/services/scheduler/schedule_summary_degradation.py, web/routes/scheduler_excel_calendar.py, web/routes/process_excel_part_operation_hours.py, static/js/gantt.js, static/js/gantt_boot.js, static/js/resource_dispatch.js
- 摘要:

  抽查调度主链、配置链、Excel 路由、前端脚本与降级事件实现后，重点评估两份 plan 是否会引入新的抽象过度、兜底扩散或事实源重复。结论：总 plan 在反静默回退约束上明显更强，但其 `degradation_report.py` 提案若直接落地，可能与现有 `DegradationCollector` / `schedule_summary_degradation.py` 形成双事实源；综合修复计划的 `ExcelImportController` 与 `window.__APS_PAGES__` 方案则有明显过泛化与再次制造全局命名空间的风险。
- 结论:

  第二轮结论：最终合并 plan 应保留总 plan 的反兜底治理约束，但在实现层面采用“最小新抽象”原则：复用既有降级事件模型，使用 pageflow/钩子式 Excel 流程，不再引入新的万能控制器或新的全局脚本总命名空间。
- 证据:
  - `core/services/common/degradation.py:6-130`
  - `core/services/scheduler/schedule_summary_degradation.py:161-321`
  - `web/routes/scheduler_excel_calendar.py:146-259`
  - `web/routes/process_excel_part_operation_hours.py:239-260`
  - `static/js/gantt.js:1-254`
  - `static/js/gantt_boot.js:220-246`
  - `.limcode/plans/20260405_技术债务修复总plan.md:420-426`
  - `.limcode/plans/20260405_技术债务修复总plan.md:255-274`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:661-709`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:739-774`
  - `core/services/common/degradation.py`
  - `core/services/scheduler/schedule_summary_degradation.py`
  - `web/routes/scheduler_excel_calendar.py`
  - `web/routes/process_excel_part_operation_hours.py`
  - `static/js/gantt.js`
  - `static/js/gantt_boot.js`
  - `static/js/resource_dispatch.js`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
- 下一步建议:

  进入第三轮，检查两份 plan 的路径正确性、顺序依赖、命令有效性与潜在 BUG。
- 问题:
  - [中] 可维护性: Excel 导入控制器存在过泛化风险
  - [中] JavaScript: 前端初始化方案不应再造全局总命名空间
  - [中] 可维护性: 降级收口不能再造第二套事实源

### R3 · 第三轮：逻辑严谨性、顺序依赖与潜在 BUG 审查

- 状态: 已完成
- 记录时间: 2026-04-05T15:31:15.200Z
- 已审模块: core/algorithms/greedy/scheduler.py, core/services/scheduler/schedule_input_builder.py, core/services/scheduler/freeze_window.py, core/services/scheduler/schedule_optimizer_steps.py, tests/test_architecture_fitness.py, requirements-dev.txt
- 摘要:

  逐项核对两份 plan 的文件路径、命令可执行性、目录改造顺序与代码现状是否匹配。结论：第一份 plan 存在 Windows/同路径命名冲突与若干错误文件路径；第二份 plan 虽然更细，但仍含占位符、拼写错误、依赖未声明的超时参数，以及若干本可直接收敛却写成条件式排查的步骤。
- 结论:

  第三轮结论：最终合并 plan 必须修掉路径与命令 BUG，统一真实文件路径，删除占位符与未声明依赖的验证参数，并把已由当前代码证明成立的兼容桥清理改成确定性步骤。
- 证据:
  - `.limcode/plans/20260405_技术债务修复总plan.md:185-192`
  - `.limcode/plans/20260405_技术债务修复总plan.md:219-228`
  - `.limcode/plans/20260405_技术债务修复总plan.md:256-270`
  - `.limcode/plans/20260405_技术债务修复总plan.md:298-307`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:322-323`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:350-366`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md:517-519`
  - `core/services/scheduler/schedule_optimizer_steps.py:85-115`
  - `core/services/scheduler/schedule_input_builder.py:243-253`
  - `core/services/scheduler/freeze_window.py:180-189`
  - `requirements-dev.txt:1-4`
  - `.limcode/plans/20260405_技术债务修复总plan.md`
  - `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`
  - `core/algorithms/greedy/scheduler.py`
  - `core/services/scheduler/schedule_input_builder.py`
  - `core/services/scheduler/freeze_window.py`
  - `core/services/scheduler/schedule_optimizer_steps.py`
  - `tests/test_architecture_fitness.py`
  - `requirements-dev.txt`
- 下一步建议:

  据三轮结论重写最终合并 plan，并以新的 review 文档作为其 source artifact。
- 问题:
  - [高] 文档: 总plan的 route 子包化存在路径冲突
  - [高] 文档: 总plan存在算法文件路径错误与目录归属不一致
  - [高] 文档: 综合修复计划含占位符与验证命令 BUG
  - [中] 可维护性: 兼容桥清理应改成确定性收口步骤

## 最终结论

三轮 review 结论：两份原始 plan 都不适合原样执行，但可以条件性接受其组合思路。最终应以 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 作为唯一权威执行 plan：它保留了总plan的完整覆盖能力，吸收了综合修复计划的步骤化细节，并显式修复了覆盖缺口、route 路径冲突、错误文件路径、占位步骤、无效验证命令以及过度抽象风险。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnlx3kx6-15wryi",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T15:37:08.474Z",
  "finalizedAt": "2026-04-05T15:37:08.474Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "20260405 技术债务双plan三轮深度review",
    "date": "2026-04-05",
    "overview": "对两份技术债务 plan 做三轮深审，核对覆盖性、实现优雅性、反兜底约束、逻辑严谨性与可执行性，并据此输出合并方向。"
  },
  "scope": {
    "markdown": "# 技术债务双plan三轮深度review\n\n## 审查对象\n- `.limcode/plans/20260405_技术债务修复总plan.md`\n- `.limcode/plans/aps排产系统技术债务综合修复计划.plan.md`\n\n## 审查目标\n1. 判断两份 plan 是否能覆盖两份技术债务 review 已确认的问题。\n2. 判断实施路径是否优雅、简洁，是否会引入新的过度兜底、静默回退或抽象过度。\n3. 判断 plan 本身是否存在路径错误、顺序错误、验证命令错误或无法在当前仓库执行的 BUG。\n4. 形成一份可直接执行的最终合并 plan。\n\n## 审查方法\n- 以两份 review 为事实源核对问题覆盖。\n- 抽读关键实现文件，验证 plan 中的路径、依赖关系与拆分边界是否真实存在。\n- 重点检查：调度主链、配置链、数据基础设施、路由与模板、前端脚本、测试门禁。\n\n## 初步结论\n- `20260405_技术债务修复总plan.md` 的**覆盖面更完整、批次顺序更合理、反静默回退约束更强**，适合作为最终 plan 的主骨架。\n- `aps排产系统技术债务综合修复计划.plan.md` 的**任务颗粒度、验证意识、步骤化表达更强**，适合吸收进最终 plan 的实施细节。\n- 两份 plan **都不能原样直接执行**：第一份存在目录/路径冲突与局部命名不一致，第二份存在覆盖缺口、占位符、验证命令错误与若干过度抽象风险。\n- 结论：应以“第一份作主骨架 + 第二份作步骤化细化 + 修正两边 BUG/冲突”的方式重写最终合并 plan。"
  },
  "summary": {
    "latestConclusion": "三轮 review 结论：两份原始 plan 都不适合原样执行，但可以条件性接受其组合思路。最终应以 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 作为唯一权威执行 plan：它保留了总plan的完整覆盖能力，吸收了综合修复计划的步骤化细节，并显式修复了覆盖缺口、route 路径冲突、错误文件路径、占位步骤、无效验证命令以及过度抽象风险。",
    "recommendedNextAction": "后续实施只以 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 为准，原两份 plan 仅保留为历史输入，不再直接执行。",
    "reviewedModules": [
      ".limcode/plans/20260405_技术债务修复总plan.md",
      ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
      "core/services/common/degradation.py",
      "core/services/scheduler/schedule_summary_degradation.py",
      "web/routes/scheduler_excel_calendar.py",
      "web/routes/process_excel_part_operation_hours.py",
      "static/js/gantt.js",
      "static/js/gantt_boot.js",
      "static/js/resource_dispatch.js",
      "core/algorithms/greedy/scheduler.py",
      "core/services/scheduler/schedule_input_builder.py",
      "core/services/scheduler/freeze_window.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "tests/test_architecture_fitness.py",
      "requirements-dev.txt",
      ".limcode/plans/20260405_技术债务最终合并修复plan.md"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 9,
    "severity": {
      "high": 4,
      "medium": 5,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "R1",
      "title": "第一轮：范围覆盖与目标达成性审查",
      "status": "completed",
      "recordedAt": "2026-04-05T15:30:06.590Z",
      "summaryMarkdown": "对照两份技术债务 review 的问题集合核对两份 plan 的覆盖范围、接受风险边界与治理顺序。结论：总 plan 的覆盖面完整，能把已确认且可整改的问题全部落入任务；综合修复计划虽然颗粒度更细，但把 A5/A7/B3/B4/C3/C6/E6 明确后移或单独开新 plan，无法单独满足“覆盖全部已验证技术债务”的目标。",
      "conclusionMarkdown": "第一轮结论：最终合并 plan 必须以总 plan 的问题覆盖矩阵为基线，不能沿用综合修复计划对若干已确认债务的延期处理。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 522,
          "lineEnd": 558,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 48,
          "lineEnd": 104,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 867,
          "lineEnd": 879,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": ".limcode/review/20260405_技术债务全面梳理.md"
        },
        {
          "path": ".limcode/review/aps排产系统技术债务全面梳理.md"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/20260405_技术债务修复总plan.md",
        ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
      ],
      "recommendedNextAction": "进入第二轮，审查两份 plan 的实现优雅性、抽象边界与反兜底约束。",
      "findingIds": [
        "plan-coverage-gap",
        "plan-main-skeleton-stronger"
      ]
    },
    {
      "id": "R2",
      "title": "第二轮：实现优雅性、简洁性与反兜底约束审查",
      "status": "completed",
      "recordedAt": "2026-04-05T15:30:37.984Z",
      "summaryMarkdown": "抽查调度主链、配置链、Excel 路由、前端脚本与降级事件实现后，重点评估两份 plan 是否会引入新的抽象过度、兜底扩散或事实源重复。结论：总 plan 在反静默回退约束上明显更强，但其 `degradation_report.py` 提案若直接落地，可能与现有 `DegradationCollector` / `schedule_summary_degradation.py` 形成双事实源；综合修复计划的 `ExcelImportController` 与 `window.__APS_PAGES__` 方案则有明显过泛化与再次制造全局命名空间的风险。",
      "conclusionMarkdown": "第二轮结论：最终合并 plan 应保留总 plan 的反兜底治理约束，但在实现层面采用“最小新抽象”原则：复用既有降级事件模型，使用 pageflow/钩子式 Excel 流程，不再引入新的万能控制器或新的全局脚本总命名空间。",
      "evidence": [
        {
          "path": "core/services/common/degradation.py",
          "lineStart": 6,
          "lineEnd": 130,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/scheduler/schedule_summary_degradation.py",
          "lineStart": 161,
          "lineEnd": 321,
          "excerptHash": "n/a"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py",
          "lineStart": 146,
          "lineEnd": 259,
          "excerptHash": "n/a"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py",
          "lineStart": 239,
          "lineEnd": 260,
          "excerptHash": "n/a"
        },
        {
          "path": "static/js/gantt.js",
          "lineStart": 1,
          "lineEnd": 254,
          "excerptHash": "n/a"
        },
        {
          "path": "static/js/gantt_boot.js",
          "lineStart": 220,
          "lineEnd": 246,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 420,
          "lineEnd": 426,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 255,
          "lineEnd": 274,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 661,
          "lineEnd": 709,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 739,
          "lineEnd": 774,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/common/degradation.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_degradation.py"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/resource_dispatch.js"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        }
      ],
      "reviewedModules": [
        "core/services/common/degradation.py",
        "core/services/scheduler/schedule_summary_degradation.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/process_excel_part_operation_hours.py",
        "static/js/gantt.js",
        "static/js/gantt_boot.js",
        "static/js/resource_dispatch.js"
      ],
      "recommendedNextAction": "进入第三轮，检查两份 plan 的路径正确性、顺序依赖、命令有效性与潜在 BUG。",
      "findingIds": [
        "plan-excel-flow-overabstracted",
        "plan-front-init-global-registry-risk",
        "plan-degradation-double-source-risk"
      ]
    },
    {
      "id": "R3",
      "title": "第三轮：逻辑严谨性、顺序依赖与潜在 BUG 审查",
      "status": "completed",
      "recordedAt": "2026-04-05T15:31:15.200Z",
      "summaryMarkdown": "逐项核对两份 plan 的文件路径、命令可执行性、目录改造顺序与代码现状是否匹配。结论：第一份 plan 存在 Windows/同路径命名冲突与若干错误文件路径；第二份 plan 虽然更细，但仍含占位符、拼写错误、依赖未声明的超时参数，以及若干本可直接收敛却写成条件式排查的步骤。",
      "conclusionMarkdown": "第三轮结论：最终合并 plan 必须修掉路径与命令 BUG，统一真实文件路径，删除占位符与未声明依赖的验证参数，并把已由当前代码证明成立的兼容桥清理改成确定性步骤。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 185,
          "lineEnd": 192,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 219,
          "lineEnd": 228,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 256,
          "lineEnd": 270,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 298,
          "lineEnd": 307,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 322,
          "lineEnd": 323,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 350,
          "lineEnd": 366,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 517,
          "lineEnd": 519,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 85,
          "lineEnd": 115,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py",
          "lineStart": 243,
          "lineEnd": 253,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/scheduler/freeze_window.py",
          "lineStart": 180,
          "lineEnd": 189,
          "excerptHash": "n/a"
        },
        {
          "path": "requirements-dev.txt",
          "lineStart": 1,
          "lineEnd": 4,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/services/scheduler/freeze_window.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "requirements-dev.txt"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/scheduler.py",
        "core/services/scheduler/schedule_input_builder.py",
        "core/services/scheduler/freeze_window.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "tests/test_architecture_fitness.py",
        "requirements-dev.txt"
      ],
      "recommendedNextAction": "据三轮结论重写最终合并 plan，并以新的 review 文档作为其 source artifact。",
      "findingIds": [
        "plan-route-package-collision",
        "plan-algorithm-path-bugs",
        "plan-step-placeholder-and-command-bugs",
        "plan-compat-cleanup-should-be-deterministic"
      ]
    }
  ],
  "findings": [
    {
      "id": "plan-coverage-gap",
      "severity": "high",
      "category": "docs",
      "title": "综合修复计划存在覆盖缺口",
      "descriptionMarkdown": "`.limcode/plans/aps排产系统技术债务综合修复计划.plan.md` 虽然在问题清单中列出了 A5/A7/B3/B4/C3/C6/E6，但在后文又把这些问题转为“中长期架构演进”并明确不在本 plan 中设置具体步骤。这与用户要求的“覆盖两份 plan 里验证正确的所有技术债务”直接冲突。",
      "recommendationMarkdown": "最终合并 plan 必须把这些问题拉回到正式任务中，可分阶段、可降优先级，但不能脱离主 plan。",
      "evidence": [
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 867,
          "lineEnd": 879,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": ".limcode/review/20260405_技术债务全面梳理.md"
        },
        {
          "path": ".limcode/review/aps排产系统技术债务全面梳理.md"
        }
      ],
      "relatedMilestoneIds": [
        "R1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-main-skeleton-stronger",
      "severity": "medium",
      "category": "docs",
      "title": "总plan更适合作为主骨架",
      "descriptionMarkdown": "总 plan 提供了完整的问题覆盖矩阵、接受风险边界、批次依赖关系和横向治理约束，尤其明确禁止新增临时兼容桥、静默回退、整页复制模板与根目录平铺测试文件，更符合本轮治理目标。",
      "recommendationMarkdown": "以总 plan 为主骨架，吸收综合修复计划中更细的步骤与验证项。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 522,
          "lineEnd": 588,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": ".limcode/review/20260405_技术债务全面梳理.md"
        },
        {
          "path": ".limcode/review/aps排产系统技术债务全面梳理.md"
        }
      ],
      "relatedMilestoneIds": [
        "R1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-excel-flow-overabstracted",
      "severity": "medium",
      "category": "maintainability",
      "title": "Excel 导入控制器存在过泛化风险",
      "descriptionMarkdown": "综合修复计划建议建立 `ExcelImportController`，把多个 Excel 页面统一抽象为 `blueprint/url_prefix/template_name/parser_factory/validator_factory/applier_factory/entity_label` 的总控制器。但当前各页面在模式限制、额外基线状态、预览后行状态改写、导出链路和页面渲染上下文上差异明显，直接用一个总控制器容易形成回调拼装与分支爆炸，后续反而更难维护。",
      "recommendationMarkdown": "改为 pageflow/钩子式流程：统一预览-确认骨架，但把数据规范化、额外状态、结果渲染和导出保留在领域适配层。",
      "evidence": [
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 661,
          "lineEnd": 709,
          "excerptHash": "n/a"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py",
          "lineStart": 146,
          "lineEnd": 259,
          "excerptHash": "n/a"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py",
          "lineStart": 239,
          "lineEnd": 260,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/common/degradation.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_degradation.py"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/resource_dispatch.js"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": "web/routes/process_excel_suppliers.py"
        }
      ],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-front-init-global-registry-risk",
      "severity": "medium",
      "category": "javascript",
      "title": "前端初始化方案不应再造全局总命名空间",
      "descriptionMarkdown": "当前前端已经依赖 `window.__APS_COMMON__` 与 `window.__APS_GANTT__`。若再新增 `window.__APS_PAGES__` 作为新的总注册表，只是把多个全局对象换成另一个更大的全局对象，并没有真正降低模板与脚本间的隐式耦合。",
      "recommendationMarkdown": "采用单点 `page_boot` + DOM `data-page` / `data-*` 协议，页面脚本只暴露局部初始化函数，不再扩张新的 window 级命名空间。",
      "evidence": [
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 739,
          "lineEnd": 774,
          "excerptHash": "n/a"
        },
        {
          "path": "static/js/gantt.js",
          "lineStart": 1,
          "lineEnd": 254,
          "excerptHash": "n/a"
        },
        {
          "path": "static/js/gantt_boot.js",
          "lineStart": 220,
          "lineEnd": 246,
          "excerptHash": "n/a"
        },
        {
          "path": "static/js/resource_dispatch.js",
          "lineStart": 1,
          "lineEnd": 83,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/common/degradation.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_degradation.py"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/resource_dispatch.js"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-degradation-double-source-risk",
      "severity": "medium",
      "category": "maintainability",
      "title": "降级收口不能再造第二套事实源",
      "descriptionMarkdown": "总 plan 提出新增 `degradation_report.py` 统一降级状态，这是正确方向；但当前仓库已经有 `core/services/common/degradation.py` 的稳定降级事件模型，以及 `schedule_summary_degradation.py` 的摘要汇总逻辑。如果直接新建平行对象而不复用现有模型，会把“降级事实源收口”做成“降级事实源再复制一次”。",
      "recommendationMarkdown": "最终合并 plan 应明确：复用 `DegradationCollector` 与稳定事件码，只允许新增统一装配层，不允许新增平行事件模型。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 255,
          "lineEnd": 274,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/common/degradation.py",
          "lineStart": 6,
          "lineEnd": 130,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/scheduler/schedule_summary_degradation.py",
          "lineStart": 161,
          "lineEnd": 321,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/common/degradation.py"
        },
        {
          "path": "core/services/scheduler/schedule_summary_degradation.py"
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py"
        },
        {
          "path": "web/routes/process_excel_part_operation_hours.py"
        },
        {
          "path": "static/js/gantt.js"
        },
        {
          "path": "static/js/gantt_boot.js"
        },
        {
          "path": "static/js/resource_dispatch.js"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        }
      ],
      "relatedMilestoneIds": [
        "R2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-route-package-collision",
      "severity": "high",
      "category": "docs",
      "title": "总plan的 route 子包化存在路径冲突",
      "descriptionMarkdown": "总 plan 同时要求新建 `web/routes/scheduler/`、`web/routes/process/`、`web/routes/personnel/`、`web/routes/equipment/`、`web/routes/system/`，又要求保留现有 `web/routes/*.py` 顶层入口做薄兼容壳。当前仓库已经存在同名文件 `scheduler.py`、`process.py`、`personnel.py`、`equipment.py`、`system.py`，在 Windows 与常见文件系统上，文件与同名目录不能并存，因此该改造顺序按原文无法落地。",
      "recommendationMarkdown": "最终合并 plan 应采用“文件转包”的确定顺序：先临时改名旧入口，再创建同名目录与 `__init__.py`，最后删除临时壳；不要要求同名文件与目录共存。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 185,
          "lineEnd": 192,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/services/scheduler/freeze_window.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "requirements-dev.txt"
        },
        {
          "path": "web/routes/scheduler.py"
        },
        {
          "path": "web/routes/process.py"
        },
        {
          "path": "web/routes/personnel.py"
        },
        {
          "path": "web/routes/equipment.py"
        },
        {
          "path": "web/routes/system.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-algorithm-path-bugs",
      "severity": "high",
      "category": "docs",
      "title": "总plan存在算法文件路径错误与目录归属不一致",
      "descriptionMarkdown": "总 plan 在算法任务中引用了 `core/algorithms/greedy/types.py`、`core/algorithms/greedy/evaluation.py`、`core/algorithms/greedy/dispatch_rules.py`，但当前仓库真实路径分别位于 `core/algorithms/types.py`、`core/algorithms/evaluation.py`、`core/algorithms/dispatch_rules.py`。同时它一边创建 `core/services/scheduler/config/` 与 `run/` 子目录，一边又把 `config_schema.py`、`run_command.py`、`run_context.py` 放在根层，目录归属前后不一致。",
      "recommendationMarkdown": "最终合并 plan 只允许使用真实路径，并统一规则：若已决定子包化，新文件应优先进入对应子包，由根层仅保留有限门面。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 219,
          "lineEnd": 228,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 256,
          "lineEnd": 270,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md",
          "lineStart": 298,
          "lineEnd": 307,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/services/scheduler/freeze_window.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "requirements-dev.txt"
        },
        {
          "path": "core/algorithms/types.py"
        },
        {
          "path": "core/algorithms/evaluation.py"
        },
        {
          "path": "core/algorithms/dispatch_rules.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-step-placeholder-and-command-bugs",
      "severity": "high",
      "category": "docs",
      "title": "综合修复计划含占位符与验证命令 BUG",
      "descriptionMarkdown": "综合修复计划多处使用 `...` 作为步骤、函数签名或示例占位，降低可执行性；同时大量验证命令携带 `--timeout=120`，但当前 `requirements-dev.txt` 仅声明 `pytest`，未声明提供该参数的插件；另有测试文件名拼写错误 `regresheduler_apply_preset_reject_invalid_numeric.py`。这些问题会让执行者在真正落地时立即遇到命令失败。",
      "recommendationMarkdown": "最终合并 plan 禁止使用占位符；验证命令只能使用当前仓库已声明依赖支持的参数；拼写错误必须在落盘前清零。",
      "evidence": [
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 322,
          "lineEnd": 323,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 350,
          "lineEnd": 366,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md",
          "lineStart": 517,
          "lineEnd": 519,
          "excerptHash": "n/a"
        },
        {
          "path": "requirements-dev.txt",
          "lineStart": 1,
          "lineEnd": 4,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/services/scheduler/freeze_window.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "requirements-dev.txt"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "plan-compat-cleanup-should-be-deterministic",
      "severity": "medium",
      "category": "maintainability",
      "title": "兼容桥清理应改成确定性收口步骤",
      "descriptionMarkdown": "综合修复计划把 strict_mode 清理写成“先搜索确认所有 scheduler 实现都支持 strict_mode”。但当前代码中只有一个 `schedule()` 实现；`build_algo_operations()` 已支持 `strict_mode` 与 `return_outcome`，`build_freeze_window_seed()` 也已支持 `strict_mode` 与 `meta`。这意味着 `_scheduler_accepts_strict_mode`、`_schedule_with_optional_strict_mode`、`_get_snapshot_with_optional_strict_mode`、`_build_algo_operations_with_optional_outcome`、`_build_freeze_window_seed_with_optional_meta` 已具备直接收口条件，不应继续写成开放式排查。",
      "recommendationMarkdown": "最终合并 plan 应把这些兼容桥收口写成明确任务，并配套列出要删掉的函数名与回归用例。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 85,
          "lineEnd": 115,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py",
          "lineStart": 243,
          "lineEnd": 253,
          "excerptHash": "n/a"
        },
        {
          "path": "core/services/scheduler/freeze_window.py",
          "lineStart": 180,
          "lineEnd": 189,
          "excerptHash": "n/a"
        },
        {
          "path": ".limcode/plans/20260405_技术债务修复总plan.md"
        },
        {
          "path": ".limcode/plans/aps排产系统技术债务综合修复计划.plan.md"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py"
        },
        {
          "path": "core/services/scheduler/freeze_window.py"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "requirements-dev.txt"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py"
        }
      ],
      "relatedMilestoneIds": [
        "R3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:db10872f2f2005807adc9682f2d06116830b9c713c9b2370056ef8902f2938f6",
    "generatedAt": "2026-04-05T15:37:08.474Z",
    "locale": "zh-CN"
  }
}
```

# 20260405 技术债务最终合并修复plan深度review
- 日期: 2026-04-05
- 概述: 对 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 做全链路深审：验证路径正确性、引用链一致性、仓储计数事实、兼容桥归属、目录迁移可行性、治理逻辑严谨性与潜在 BUG。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 技术债务最终合并修复 plan 深度 review

## 审查对象
- `.limcode/plans/20260405_技术债务最终合并修复plan.md`

## 审查目标
1. 验证 plan 中所有文件路径、函数名、数字是否与当前仓库真实状态一致。
2. 追踪关键引用链，检查兼容桥归属、仓储计数、目录结构描述是否准确。
3. 评估实施方案是否优雅简洁、逻辑严谨、无过度兜底与静默回退。
4. 发现潜在 BUG、隐患与执行障碍。

## 审查方法
- 读取 `ScheduleService.__init__` 验证仓储计数。
- 读取五个兼容桥函数验证定义位置。
- 读取根层路由门面验证当前角色。
- 读取 `factory.py` 验证 `g.db` 注入机制。
- 扫描 `web/routes/` 中 `Service(g.db` 模式验证装配现状。
- 验证 `config_service.py::get_snapshot` 是否已支持 `strict_mode`。
- 验证 `GreedyScheduler.schedule` 是否已支持 `strict_mode`。
- 验证 `data/queries/`、`web/pageflows/`、`scripts/run_quality_gate.py` 等目标目录/文件当前是否存在。

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/freeze_window.py, web/routes/scheduler.py, web/routes/process.py, web/routes/personnel.py, web/routes/equipment.py, web/routes/system.py, web/bootstrap/factory.py, core/services/scheduler/config_service.py, core/services/scheduler/config_validator.py, core/services/scheduler/config_snapshot.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/schedule_params.py, core/infrastructure/database.py, tests/test_architecture_fitness.py, web/routes/scheduler_run.py
- 当前进度: 已记录 2 个里程碑；最新：R2
- 里程碑总数: 2
- 已完成里程碑: 2
- 问题总数: 0
- 问题严重级别分布: 高 0 / 中 0 / 低 0
- 最新结论: ## 深审总结 plan 整体方向正确、覆盖面完整、批次顺序合理、反兜底约束到位，**有条件接受**。但在执行前必须修正以下事实性错误和设计隐患，否则执行者会在落地时遇到困惑和失败。 --- ### 必须修正（3 项高优先级 BUG） | # | 问题 | 位置 | 修正要求 | |---|------|------|----------| | 1 | **仓储数量写错** | 任务 2 多处 | 全文把"12 个仓储依赖""12 个仓储参数"改为"10 个仓储实例"；修正构造器描述从"构造器承载 12 个仓储依赖"改为"构造器内部创建 10 个仓储实例" | | 2 | **`_get_snapshot_with_optional_strict_mode` 归属错误** | 任务 5 兼容桥清单 | 从 `schedule_input_collector.py` 改为 `schedule_service.py`（第 49-59 行定义，第 273 行传参） | | 3 | **`_build_freeze_window_seed_with_optional_meta` 归属错误** | 任务 5 兼容桥清单 | 从 `freeze_window.py` 改为 `schedule_input_collector.py`（第 216-255 行） | ### 建议完善（4 项中等优先级设计隐患） | # | 问题 | 建议 | |---|------|------| | 4 | **仓储束方案描述与实际不匹配** | 任务 2 步骤 2 修正为："把 `__init__` 内部的仓储创建逻辑提取到 `RepositoryBundle`，让 `ScheduleService` 接收已构建好的束对象"而非"把 12 个参数收为 1 个" | | 5 | **`collect_schedule_run_input` 18 参数巨型签名未治理** | 任务 5 应明确：兼容桥删除后，该函数的 6 个函数依赖注入参数应同步消除，签名应精简为接收 `RunCommand` 对象 | | 6 | **路由 `domains/` 中间层价值需评估** | 当前五个根层文件已是薄门面，迁移到 `domains/` 的主要收益是降低文件平铺数量；但代价是 59 个文件全部物理迁移 + 相对导入修改。plan 应明确迁移后 `url_for` 端点名/蓝图注册/模板引用是否保持不变，并补充对应回归验证 | | 7 | **`ScheduleRunInput` 29 字段拆分后的归属未定义** | 任务 5 步骤 3 应明确：`persist_schedule()` 当前消费的 22 个命名参数，拆分后哪些来自 `RunCommand`、哪些来自 `RunContext`、哪些来自 `ScheduleOrchestrationOutcome` | ### 已验证通过的方面 - ✅ **配置规则分散确认**：`config_service.py`、`config_validator.py`、`config_snapshot.py`、`schedule_params.py`、`schedule_optimizer_steps.py` 确实存在重复的默认值/合法值/数值下限定义，任务 4 方向正确 - ✅ **五个兼容桥可直接删除确认**：`ConfigService.get_snapshot()` 已支持 `strict_mode`，`GreedyScheduler.schedule()` 已支持 `strict_mode`，`build_algo_operations()` 已支持 `return_outcome`，`build_freeze_window_seed()` 已支持 `meta` - ✅ **算法文件路径已修正**：plan 已正确使用 `core/algorithms/types.py`、`core/algorithms/evaluation.py`、`core/algorithms/dispatch_rules.py` - ✅ **路由子包化采用 `domains/` 策略避免了同名冲突**：已修正上轮 review 的路径冲突问题 - ✅ **全局禁止项完备**：禁止新增兼容桥、静默回退、整页复制模板、根目录平铺测试文件 - ✅ **调度服务文件计数大致准确**：46 个文件（含 `__init__.py`），路由 59 个文件 - ✅ **`GreedyScheduler.schedule()` 确实 332 行**，任务 6 拆分方向正确
- 下一步建议: 修正上述 3 项高优先级 BUG 后即可开始按批次执行。优先从批次 0（工程基线）起步。
- 总体结论: 有条件通过

## 评审发现

<!-- no findings -->

## 评审里程碑

### R1 · 第一轮：事实验证 — 路径、数字与函数归属核对

- 状态: 已完成
- 记录时间: 2026-04-05T15:58:12.029Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/freeze_window.py, web/routes/scheduler.py, web/routes/process.py, web/routes/personnel.py, web/routes/equipment.py, web/routes/system.py, web/bootstrap/factory.py
- 摘要:

  逐条核对 plan 中引用的文件路径、仓储计数、兼容桥函数定义位置和目录结构描述。发现 6 个事实性错误或不准确描述。

  **核对结果清单：**

  1. **仓储数量**：plan 多处说"12 个仓储依赖"，但 `ScheduleService.__init__` 实际只创建 **10 个**仓储实例（`batch_repo, op_repo, part_op_repo, group_repo, machine_repo, operator_repo, operator_machine_repo, supplier_repo, schedule_repo, history_repo`）。构造器签名是 `(conn, logger, op_logger)` 共 3 个参数，并非"构造器承载 12 个仓储依赖"。

  2. **`_get_snapshot_with_optional_strict_mode` 函数归属错误**：plan 任务 5 把此函数归到 `schedule_input_collector.py`，但它实际定义在 `schedule_service.py`（第 49–59 行）。

  3. **`_build_freeze_window_seed_with_optional_meta` 函数归属错误**：plan 任务 5 把此函数归到 `freeze_window.py`，但它实际定义在 `schedule_input_collector.py`（第 216–255 行）。

  4. **路由门面现状**：当前五个根层路由文件已经是薄门面。

  5. **`ScheduleService` 仓储并非"参数化注入"而是"内部创建"**：构造器 `(conn, logger, op_logger)` 只有 3 个参数。

  6. **文件数量大致准确**：46 vs 45，59 吻合。
- 结论:

  逐条核对 plan 中引用的文件路径、仓储计数、兼容桥函数定义位置和目录结构描述。发现 6 个事实性错误或不准确描述。 **核对结果清单：** 1. **仓储数量**：plan 多处说"12 个仓储依赖"，但 `ScheduleService.__init__` 实际只创建 **10 个**仓储实例（`batch_repo, op_repo, part_op_repo, group_repo, machine_repo, operator_repo, operator_machine_repo, supplier_repo, schedule_repo, history_repo`）。构造器签名是 `(conn, logger, op_logger)` 共 3 个参数，并非"构造器承载 12 个仓储依赖"。 2. **`_get_snapshot_with_optional_strict_mode` 函数归属错误**：plan 任务 5 把此函数归到 `schedule_input_collector.py`，但它实际定义在 `schedule_service.py`（第 49–59 行）。 3. **`_build_freeze_window_seed_with_optional_meta` 函数归属错误**：plan 任务 5 把此函数归到 `freeze_window.py`，但它实际定义在 `schedule_input_collector.py`（第 216–255 行）。 4. **路由门面现状**：当前五个根层路由文件已经是薄门面。 5. **`ScheduleService` 仓储并非"参数化注入"而是"内部创建"**：构造器 `(conn, logger, op_logger)` 只有 3 个参数。 6. **文件数量大致准确**：46 vs 45，59 吻合。
- 下一步建议:

  进入第二轮：评估实施方案的逻辑严谨性与潜在风险。

### R2 · 第二轮：实施逻辑严谨性、引用链一致性与设计隐患审查

- 状态: 已完成
- 记录时间: 2026-04-05T15:58:35.608Z
- 已审模块: core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_service.py, core/services/scheduler/config_service.py, core/services/scheduler/config_validator.py, core/services/scheduler/config_snapshot.py, core/algorithms/greedy/scheduler.py, core/algorithms/greedy/schedule_params.py, core/infrastructure/database.py, tests/test_architecture_fitness.py, web/routes/scheduler_run.py
- 摘要:

  深入审查 plan 的实施逻辑是否严谨、引用链是否完整追踪、设计方案是否存在隐患。发现 6 项需要关注的问题。

  **关键发现：**

  1. **仓储计数 12→10 (高)**：plan 多处称"12 个仓储依赖"，实际为 10 个内部创建的仓储实例。构造器签名 `(conn, logger, op_logger)` 只有 3 个参数。plan 的"仓储束"方案描述需修正。

  2. **兼容桥归属错误 ×2 (高)**：
     - `_get_snapshot_with_optional_strict_mode` 实际在 `schedule_service.py` 而非 `schedule_input_collector.py`
     - `_build_freeze_window_seed_with_optional_meta` 实际在 `schedule_input_collector.py` 而非 `freeze_window.py`

  3. **配置规则散布点核实 (中)**：plan 任务 4 说配置规则分散在 6 个文件中。实测验证：
     - `config_service.py` 有 59-63 行的 `VALID_*` 常量和 37-57 行的 `DEFAULT_*` 常量
     - `config_validator.py` 的 `normalize_preset_snapshot()` 在 17-21 行重新定义了同样的合法值集合
     - `config_snapshot.py` 有独立的 `ScheduleConfigSnapshot` 字段定义
     - `schedule_params.py` 的 `resolve_schedule_params()` 有独立的参数解析与默认值逻辑
     - `schedule_optimizer_steps.py` 的 `_cfg_float`/`_cfg_int` 有独立的数值解析与下限处理
     - **确认规则确实存在重复分散**，任务 4 的治理方向正确

  4. **`collect_schedule_run_input` 18 参数巨型签名未被治理 (中)**：该函数有 18 个参数，其中 6 个是函数依赖注入（兼容桥消费入口）。任务 5 虽然要删除兼容桥，但没有明确说这个函数签名如何精简。

  5. **路由门面已是薄壳 (中)**：plan 要建 `domains/` 中间层，但当前门面文件已经只做导入转发，迁移价值需评估。

  6. **`ScheduleRunInput` 大对象有 29 个字段 (中)**：plan 任务 5 要拆分这个大对象，方向正确。但 `_run_schedule_impl` 调用链中 `persist_schedule()` 需要的字段既来自 `schedule_input` 又来自 `orchestration`，拆分后的字段归属需要精确定义，否则容易出现字段遗漏或重复传递。
- 结论:

  深入审查 plan 的实施逻辑是否严谨、引用链是否完整追踪、设计方案是否存在隐患。发现 6 项需要关注的问题。 **关键发现：** 1. **仓储计数 12→10 (高)**：plan 多处称"12 个仓储依赖"，实际为 10 个内部创建的仓储实例。构造器签名 `(conn, logger, op_logger)` 只有 3 个参数。plan 的"仓储束"方案描述需修正。 2. **兼容桥归属错误 ×2 (高)**： - `_get_snapshot_with_optional_strict_mode` 实际在 `schedule_service.py` 而非 `schedule_input_collector.py` - `_build_freeze_window_seed_with_optional_meta` 实际在 `schedule_input_collector.py` 而非 `freeze_window.py` 3. **配置规则散布点核实 (中)**：plan 任务 4 说配置规则分散在 6 个文件中。实测验证： - `config_service.py` 有 59-63 行的 `VALID_*` 常量和 37-57 行的 `DEFAULT_*` 常量 - `config_validator.py` 的 `normalize_preset_snapshot()` 在 17-21 行重新定义了同样的合法值集合 - `config_snapshot.py` 有独立的 `ScheduleConfigSnapshot` 字段定义 - `schedule_params.py` 的 `resolve_schedule_params()` 有独立的参数解析与默认值逻辑 - `schedule_optimizer_steps.py` 的 `_cfg_float`/`_cfg_int` 有独立的数值解析与下限处理 - **确认规则确实存在重复分散**，任务 4 的治理方向正确 4. **`collect_schedule_run_input` 18 参数巨型签名未被治理 (中)**：该函数有 18 个参数，其中 6 个是函数依赖注入（兼容桥消费入口）。任务 5 虽然要删除兼容桥，但没有明确说这个函数签名如何精简。 5. **路由门面已是薄壳 (中)**：plan 要建 `domains/` 中间层，但当前门面文件已经只做导入转发，迁移价值需评估。 6. **`ScheduleRunInput` 大对象有 29 个字段 (中)**：plan 任务 5 要拆分这个大对象，方向正确。但 `_run_schedule_impl` 调用链中 `persist_schedule()` 需要的字段既来自 `schedule_input` 又来自 `orchestration`，拆分后的字段归属需要精确定义，否则容易出现字段遗漏或重复传递。
- 下一步建议:

  进入第三轮：汇总结论与行动项。

## 最终结论

## 深审总结

plan 整体方向正确、覆盖面完整、批次顺序合理、反兜底约束到位，**有条件接受**。但在执行前必须修正以下事实性错误和设计隐患，否则执行者会在落地时遇到困惑和失败。

---

### 必须修正（3 项高优先级 BUG）

| # | 问题 | 位置 | 修正要求 |
|---|------|------|----------|
| 1 | **仓储数量写错** | 任务 2 多处 | 全文把"12 个仓储依赖""12 个仓储参数"改为"10 个仓储实例"；修正构造器描述从"构造器承载 12 个仓储依赖"改为"构造器内部创建 10 个仓储实例" |
| 2 | **`_get_snapshot_with_optional_strict_mode` 归属错误** | 任务 5 兼容桥清单 | 从 `schedule_input_collector.py` 改为 `schedule_service.py`（第 49-59 行定义，第 273 行传参） |
| 3 | **`_build_freeze_window_seed_with_optional_meta` 归属错误** | 任务 5 兼容桥清单 | 从 `freeze_window.py` 改为 `schedule_input_collector.py`（第 216-255 行） |

### 建议完善（4 项中等优先级设计隐患）

| # | 问题 | 建议 |
|---|------|------|
| 4 | **仓储束方案描述与实际不匹配** | 任务 2 步骤 2 修正为："把 `__init__` 内部的仓储创建逻辑提取到 `RepositoryBundle`，让 `ScheduleService` 接收已构建好的束对象"而非"把 12 个参数收为 1 个" |
| 5 | **`collect_schedule_run_input` 18 参数巨型签名未治理** | 任务 5 应明确：兼容桥删除后，该函数的 6 个函数依赖注入参数应同步消除，签名应精简为接收 `RunCommand` 对象 |
| 6 | **路由 `domains/` 中间层价值需评估** | 当前五个根层文件已是薄门面，迁移到 `domains/` 的主要收益是降低文件平铺数量；但代价是 59 个文件全部物理迁移 + 相对导入修改。plan 应明确迁移后 `url_for` 端点名/蓝图注册/模板引用是否保持不变，并补充对应回归验证 |
| 7 | **`ScheduleRunInput` 29 字段拆分后的归属未定义** | 任务 5 步骤 3 应明确：`persist_schedule()` 当前消费的 22 个命名参数，拆分后哪些来自 `RunCommand`、哪些来自 `RunContext`、哪些来自 `ScheduleOrchestrationOutcome` |

### 已验证通过的方面

- ✅ **配置规则分散确认**：`config_service.py`、`config_validator.py`、`config_snapshot.py`、`schedule_params.py`、`schedule_optimizer_steps.py` 确实存在重复的默认值/合法值/数值下限定义，任务 4 方向正确
- ✅ **五个兼容桥可直接删除确认**：`ConfigService.get_snapshot()` 已支持 `strict_mode`，`GreedyScheduler.schedule()` 已支持 `strict_mode`，`build_algo_operations()` 已支持 `return_outcome`，`build_freeze_window_seed()` 已支持 `meta`
- ✅ **算法文件路径已修正**：plan 已正确使用 `core/algorithms/types.py`、`core/algorithms/evaluation.py`、`core/algorithms/dispatch_rules.py`
- ✅ **路由子包化采用 `domains/` 策略避免了同名冲突**：已修正上轮 review 的路径冲突问题
- ✅ **全局禁止项完备**：禁止新增兼容桥、静默回退、整页复制模板、根目录平铺测试文件
- ✅ **调度服务文件计数大致准确**：46 个文件（含 `__init__.py`），路由 59 个文件
- ✅ **`GreedyScheduler.schedule()` 确实 332 行**，任务 6 拆分方向正确

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnly2bdk-7ngv4a",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T15:59:09.839Z",
  "finalizedAt": "2026-04-05T15:59:09.839Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "20260405 技术债务最终合并修复plan深度review",
    "date": "2026-04-05",
    "overview": "对 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 做全链路深审：验证路径正确性、引用链一致性、仓储计数事实、兼容桥归属、目录迁移可行性、治理逻辑严谨性与潜在 BUG。"
  },
  "scope": {
    "markdown": "# 技术债务最终合并修复 plan 深度 review\n\n## 审查对象\n- `.limcode/plans/20260405_技术债务最终合并修复plan.md`\n\n## 审查目标\n1. 验证 plan 中所有文件路径、函数名、数字是否与当前仓库真实状态一致。\n2. 追踪关键引用链，检查兼容桥归属、仓储计数、目录结构描述是否准确。\n3. 评估实施方案是否优雅简洁、逻辑严谨、无过度兜底与静默回退。\n4. 发现潜在 BUG、隐患与执行障碍。\n\n## 审查方法\n- 读取 `ScheduleService.__init__` 验证仓储计数。\n- 读取五个兼容桥函数验证定义位置。\n- 读取根层路由门面验证当前角色。\n- 读取 `factory.py` 验证 `g.db` 注入机制。\n- 扫描 `web/routes/` 中 `Service(g.db` 模式验证装配现状。\n- 验证 `config_service.py::get_snapshot` 是否已支持 `strict_mode`。\n- 验证 `GreedyScheduler.schedule` 是否已支持 `strict_mode`。\n- 验证 `data/queries/`、`web/pageflows/`、`scripts/run_quality_gate.py` 等目标目录/文件当前是否存在。"
  },
  "summary": {
    "latestConclusion": "## 深审总结\n\nplan 整体方向正确、覆盖面完整、批次顺序合理、反兜底约束到位，**有条件接受**。但在执行前必须修正以下事实性错误和设计隐患，否则执行者会在落地时遇到困惑和失败。\n\n---\n\n### 必须修正（3 项高优先级 BUG）\n\n| # | 问题 | 位置 | 修正要求 |\n|---|------|------|----------|\n| 1 | **仓储数量写错** | 任务 2 多处 | 全文把\"12 个仓储依赖\"\"12 个仓储参数\"改为\"10 个仓储实例\"；修正构造器描述从\"构造器承载 12 个仓储依赖\"改为\"构造器内部创建 10 个仓储实例\" |\n| 2 | **`_get_snapshot_with_optional_strict_mode` 归属错误** | 任务 5 兼容桥清单 | 从 `schedule_input_collector.py` 改为 `schedule_service.py`（第 49-59 行定义，第 273 行传参） |\n| 3 | **`_build_freeze_window_seed_with_optional_meta` 归属错误** | 任务 5 兼容桥清单 | 从 `freeze_window.py` 改为 `schedule_input_collector.py`（第 216-255 行） |\n\n### 建议完善（4 项中等优先级设计隐患）\n\n| # | 问题 | 建议 |\n|---|------|------|\n| 4 | **仓储束方案描述与实际不匹配** | 任务 2 步骤 2 修正为：\"把 `__init__` 内部的仓储创建逻辑提取到 `RepositoryBundle`，让 `ScheduleService` 接收已构建好的束对象\"而非\"把 12 个参数收为 1 个\" |\n| 5 | **`collect_schedule_run_input` 18 参数巨型签名未治理** | 任务 5 应明确：兼容桥删除后，该函数的 6 个函数依赖注入参数应同步消除，签名应精简为接收 `RunCommand` 对象 |\n| 6 | **路由 `domains/` 中间层价值需评估** | 当前五个根层文件已是薄门面，迁移到 `domains/` 的主要收益是降低文件平铺数量；但代价是 59 个文件全部物理迁移 + 相对导入修改。plan 应明确迁移后 `url_for` 端点名/蓝图注册/模板引用是否保持不变，并补充对应回归验证 |\n| 7 | **`ScheduleRunInput` 29 字段拆分后的归属未定义** | 任务 5 步骤 3 应明确：`persist_schedule()` 当前消费的 22 个命名参数，拆分后哪些来自 `RunCommand`、哪些来自 `RunContext`、哪些来自 `ScheduleOrchestrationOutcome` |\n\n### 已验证通过的方面\n\n- ✅ **配置规则分散确认**：`config_service.py`、`config_validator.py`、`config_snapshot.py`、`schedule_params.py`、`schedule_optimizer_steps.py` 确实存在重复的默认值/合法值/数值下限定义，任务 4 方向正确\n- ✅ **五个兼容桥可直接删除确认**：`ConfigService.get_snapshot()` 已支持 `strict_mode`，`GreedyScheduler.schedule()` 已支持 `strict_mode`，`build_algo_operations()` 已支持 `return_outcome`，`build_freeze_window_seed()` 已支持 `meta`\n- ✅ **算法文件路径已修正**：plan 已正确使用 `core/algorithms/types.py`、`core/algorithms/evaluation.py`、`core/algorithms/dispatch_rules.py`\n- ✅ **路由子包化采用 `domains/` 策略避免了同名冲突**：已修正上轮 review 的路径冲突问题\n- ✅ **全局禁止项完备**：禁止新增兼容桥、静默回退、整页复制模板、根目录平铺测试文件\n- ✅ **调度服务文件计数大致准确**：46 个文件（含 `__init__.py`），路由 59 个文件\n- ✅ **`GreedyScheduler.schedule()` 确实 332 行**，任务 6 拆分方向正确",
    "recommendedNextAction": "修正上述 3 项高优先级 BUG 后即可开始按批次执行。优先从批次 0（工程基线）起步。",
    "reviewedModules": [
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/freeze_window.py",
      "web/routes/scheduler.py",
      "web/routes/process.py",
      "web/routes/personnel.py",
      "web/routes/equipment.py",
      "web/routes/system.py",
      "web/bootstrap/factory.py",
      "core/services/scheduler/config_service.py",
      "core/services/scheduler/config_validator.py",
      "core/services/scheduler/config_snapshot.py",
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/schedule_params.py",
      "core/infrastructure/database.py",
      "tests/test_architecture_fitness.py",
      "web/routes/scheduler_run.py"
    ]
  },
  "stats": {
    "totalMilestones": 2,
    "completedMilestones": 2,
    "totalFindings": 0,
    "severity": {
      "high": 0,
      "medium": 0,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "R1",
      "title": "第一轮：事实验证 — 路径、数字与函数归属核对",
      "status": "completed",
      "recordedAt": "2026-04-05T15:58:12.029Z",
      "summaryMarkdown": "逐条核对 plan 中引用的文件路径、仓储计数、兼容桥函数定义位置和目录结构描述。发现 6 个事实性错误或不准确描述。\n\n**核对结果清单：**\n\n1. **仓储数量**：plan 多处说\"12 个仓储依赖\"，但 `ScheduleService.__init__` 实际只创建 **10 个**仓储实例（`batch_repo, op_repo, part_op_repo, group_repo, machine_repo, operator_repo, operator_machine_repo, supplier_repo, schedule_repo, history_repo`）。构造器签名是 `(conn, logger, op_logger)` 共 3 个参数，并非\"构造器承载 12 个仓储依赖\"。\n\n2. **`_get_snapshot_with_optional_strict_mode` 函数归属错误**：plan 任务 5 把此函数归到 `schedule_input_collector.py`，但它实际定义在 `schedule_service.py`（第 49–59 行）。\n\n3. **`_build_freeze_window_seed_with_optional_meta` 函数归属错误**：plan 任务 5 把此函数归到 `freeze_window.py`，但它实际定义在 `schedule_input_collector.py`（第 216–255 行）。\n\n4. **路由门面现状**：当前五个根层路由文件已经是薄门面。\n\n5. **`ScheduleService` 仓储并非\"参数化注入\"而是\"内部创建\"**：构造器 `(conn, logger, op_logger)` 只有 3 个参数。\n\n6. **文件数量大致准确**：46 vs 45，59 吻合。",
      "conclusionMarkdown": "逐条核对 plan 中引用的文件路径、仓储计数、兼容桥函数定义位置和目录结构描述。发现 6 个事实性错误或不准确描述。 **核对结果清单：** 1. **仓储数量**：plan 多处说\"12 个仓储依赖\"，但 `ScheduleService.__init__` 实际只创建 **10 个**仓储实例（`batch_repo, op_repo, part_op_repo, group_repo, machine_repo, operator_repo, operator_machine_repo, supplier_repo, schedule_repo, history_repo`）。构造器签名是 `(conn, logger, op_logger)` 共 3 个参数，并非\"构造器承载 12 个仓储依赖\"。 2. **`_get_snapshot_with_optional_strict_mode` 函数归属错误**：plan 任务 5 把此函数归到 `schedule_input_collector.py`，但它实际定义在 `schedule_service.py`（第 49–59 行）。 3. **`_build_freeze_window_seed_with_optional_meta` 函数归属错误**：plan 任务 5 把此函数归到 `freeze_window.py`，但它实际定义在 `schedule_input_collector.py`（第 216–255 行）。 4. **路由门面现状**：当前五个根层路由文件已经是薄门面。 5. **`ScheduleService` 仓储并非\"参数化注入\"而是\"内部创建\"**：构造器 `(conn, logger, op_logger)` 只有 3 个参数。 6. **文件数量大致准确**：46 vs 45，59 吻合。",
      "evidence": [],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/freeze_window.py",
        "web/routes/scheduler.py",
        "web/routes/process.py",
        "web/routes/personnel.py",
        "web/routes/equipment.py",
        "web/routes/system.py",
        "web/bootstrap/factory.py"
      ],
      "recommendedNextAction": "进入第二轮：评估实施方案的逻辑严谨性与潜在风险。",
      "findingIds": []
    },
    {
      "id": "R2",
      "title": "第二轮：实施逻辑严谨性、引用链一致性与设计隐患审查",
      "status": "completed",
      "recordedAt": "2026-04-05T15:58:35.608Z",
      "summaryMarkdown": "深入审查 plan 的实施逻辑是否严谨、引用链是否完整追踪、设计方案是否存在隐患。发现 6 项需要关注的问题。\n\n**关键发现：**\n\n1. **仓储计数 12→10 (高)**：plan 多处称\"12 个仓储依赖\"，实际为 10 个内部创建的仓储实例。构造器签名 `(conn, logger, op_logger)` 只有 3 个参数。plan 的\"仓储束\"方案描述需修正。\n\n2. **兼容桥归属错误 ×2 (高)**：\n   - `_get_snapshot_with_optional_strict_mode` 实际在 `schedule_service.py` 而非 `schedule_input_collector.py`\n   - `_build_freeze_window_seed_with_optional_meta` 实际在 `schedule_input_collector.py` 而非 `freeze_window.py`\n\n3. **配置规则散布点核实 (中)**：plan 任务 4 说配置规则分散在 6 个文件中。实测验证：\n   - `config_service.py` 有 59-63 行的 `VALID_*` 常量和 37-57 行的 `DEFAULT_*` 常量\n   - `config_validator.py` 的 `normalize_preset_snapshot()` 在 17-21 行重新定义了同样的合法值集合\n   - `config_snapshot.py` 有独立的 `ScheduleConfigSnapshot` 字段定义\n   - `schedule_params.py` 的 `resolve_schedule_params()` 有独立的参数解析与默认值逻辑\n   - `schedule_optimizer_steps.py` 的 `_cfg_float`/`_cfg_int` 有独立的数值解析与下限处理\n   - **确认规则确实存在重复分散**，任务 4 的治理方向正确\n\n4. **`collect_schedule_run_input` 18 参数巨型签名未被治理 (中)**：该函数有 18 个参数，其中 6 个是函数依赖注入（兼容桥消费入口）。任务 5 虽然要删除兼容桥，但没有明确说这个函数签名如何精简。\n\n5. **路由门面已是薄壳 (中)**：plan 要建 `domains/` 中间层，但当前门面文件已经只做导入转发，迁移价值需评估。\n\n6. **`ScheduleRunInput` 大对象有 29 个字段 (中)**：plan 任务 5 要拆分这个大对象，方向正确。但 `_run_schedule_impl` 调用链中 `persist_schedule()` 需要的字段既来自 `schedule_input` 又来自 `orchestration`，拆分后的字段归属需要精确定义，否则容易出现字段遗漏或重复传递。",
      "conclusionMarkdown": "深入审查 plan 的实施逻辑是否严谨、引用链是否完整追踪、设计方案是否存在隐患。发现 6 项需要关注的问题。 **关键发现：** 1. **仓储计数 12→10 (高)**：plan 多处称\"12 个仓储依赖\"，实际为 10 个内部创建的仓储实例。构造器签名 `(conn, logger, op_logger)` 只有 3 个参数。plan 的\"仓储束\"方案描述需修正。 2. **兼容桥归属错误 ×2 (高)**： - `_get_snapshot_with_optional_strict_mode` 实际在 `schedule_service.py` 而非 `schedule_input_collector.py` - `_build_freeze_window_seed_with_optional_meta` 实际在 `schedule_input_collector.py` 而非 `freeze_window.py` 3. **配置规则散布点核实 (中)**：plan 任务 4 说配置规则分散在 6 个文件中。实测验证： - `config_service.py` 有 59-63 行的 `VALID_*` 常量和 37-57 行的 `DEFAULT_*` 常量 - `config_validator.py` 的 `normalize_preset_snapshot()` 在 17-21 行重新定义了同样的合法值集合 - `config_snapshot.py` 有独立的 `ScheduleConfigSnapshot` 字段定义 - `schedule_params.py` 的 `resolve_schedule_params()` 有独立的参数解析与默认值逻辑 - `schedule_optimizer_steps.py` 的 `_cfg_float`/`_cfg_int` 有独立的数值解析与下限处理 - **确认规则确实存在重复分散**，任务 4 的治理方向正确 4. **`collect_schedule_run_input` 18 参数巨型签名未被治理 (中)**：该函数有 18 个参数，其中 6 个是函数依赖注入（兼容桥消费入口）。任务 5 虽然要删除兼容桥，但没有明确说这个函数签名如何精简。 5. **路由门面已是薄壳 (中)**：plan 要建 `domains/` 中间层，但当前门面文件已经只做导入转发，迁移价值需评估。 6. **`ScheduleRunInput` 大对象有 29 个字段 (中)**：plan 任务 5 要拆分这个大对象，方向正确。但 `_run_schedule_impl` 调用链中 `persist_schedule()` 需要的字段既来自 `schedule_input` 又来自 `orchestration`，拆分后的字段归属需要精确定义，否则容易出现字段遗漏或重复传递。",
      "evidence": [],
      "reviewedModules": [
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/config_service.py",
        "core/services/scheduler/config_validator.py",
        "core/services/scheduler/config_snapshot.py",
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/schedule_params.py",
        "core/infrastructure/database.py",
        "tests/test_architecture_fitness.py",
        "web/routes/scheduler_run.py"
      ],
      "recommendedNextAction": "进入第三轮：汇总结论与行动项。",
      "findingIds": []
    }
  ],
  "findings": [],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:534da94f74dd699873c69280e3c1ca481e84f0f63573f908bad0442db6b6a869",
    "generatedAt": "2026-04-05T15:59:09.839Z",
    "locale": "zh-CN"
  }
}
```

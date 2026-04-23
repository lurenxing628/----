# 技术债务最终合并修复plan三轮深度审查
- 日期: 2026-04-06
- 概述: 对 20260405_技术债务最终合并修复plan.md 进行三轮深度审查，验证目标可达性、实施严谨性与代码事实一致性
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 技术债务最终合并修复 plan 三轮深度审查

**审查日期**：2026-04-06

**审查对象**：`.limcode/plans/20260405_技术债务最终合并修复plan.md`

**审查目标**：
1. 第一轮：验证 plan 中事实性声明与代码实际状态是否一致
2. 第二轮：审查实施逻辑严谨性、批次依赖链完整性、边界条件覆盖
3. 第三轮：评估整体目标可达性、优雅度、是否存在过度设计或遗漏

**审查方法**：逐任务对照代码事实进行验证，不修改任何业务代码

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_input_builder.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_persistence.py, core/services/scheduler/gantt_critical_chain.py, web/bootstrap/factory.py, web/bootstrap/static_versioning.py, web/ui_mode.py, core/algorithms/greedy/scheduler.py, pyproject.toml, .pre-commit-config.yaml, requirements-dev.txt, tests/test_architecture_fitness.py, tests/check_quickref_vs_routes.py, plan 整体结构与 10 个任务
- 当前进度: 已记录 3 个里程碑；最新：R3-overall-assessment
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 8
- 问题严重级别分布: 高 0 / 中 3 / 低 5
- 最新结论: ## 三轮深度审查最终结论 本次对《APS 技术债务最终合并修复 plan》进行了三轮深度审查，覆盖了 18 个核心源文件与配置文件的代码级对照验证。 ### 总体评价：有条件通过 **该 plan 是一份高质量、可执行的技术债务治理方案。** #### 事实准确性（第一轮）：✅ 优秀 - plan 中 22 项关键事实性声明（函数签名、参数计数、行号、命中数等）全部与代码实际状态精确匹配 - 未发现虚假数据、错误路径或拼写错误的测试文件名 - 所有引用的验证测试文件均真实存在 #### 逻辑严谨性（第二轮）：✅ 良好，有 5 处需补充 - 批次依赖链（0→1→2→3→4→5）逻辑自洽 - 批次间任务排序约束正确 - 验证命令语法正确且目标路径匹配 - 发现 3 处中等级别缺口需补充： - `web/ui_mode.py` 的直接装配点应显式纳入任务 2 或任务 8 范围 - `F401` 全局忽略移除前需先评估影响面 - 静默异常门禁扫描范围应显式覆盖 `web/ui_mode.py` - 发现 2 处低级别优化建议： - `CalendarService`/`ConfigService` 延迟导入可直接给出"上移"结论 - `pre-commit` 钩子应与门禁脚本统一调用方式 #### 目标可达性与优雅度（第三轮）：✅ 良好 - 6 个批次的目标均可达，批次 2（配置与主链收口）挑战最大但 plan 已通过充分的实施前确认降低了风险 - 结构决策简洁实用，未发现过度设计 - "非同名子包"策略、请求级服务容器、Excel 骨架+钩子模式、DOM 前端协议等核心设计决策均属克制且正确的选择 - plan 复杂度接近认知天花板但在可接受范围内 ### 需补充的 3 项修正 1. **任务 2 / 任务 8**：显式声明 `web/ui_mode.py:_read_ui_mode_from_db` 的 `SystemConfigService(conn, ...)` 装配需收口或登记 2. **任务 3 步骤 8.2**：增加前置步骤 `python -m ruff check --select F401` 评估影响面再移除全局忽略 3. **任务 1 步骤 6**：把 `web/ui_mode.py` 显式纳入静默异常门禁扫描范围 ### 无阻断性缺陷，建议在上述 3 项修正后启动实施。
- 下一步建议: 在 plan 中补充上述 3 项修正（ui_mode.py 装配收口声明、F401 影响面前置评估、ui_mode.py 纳入门禁扫描范围）后即可启动批次 0 实施
- 总体结论: 有条件通过

## 评审发现

### ui_mode.py 直接装配未纳入任务 2 收口范围

- ID: F-ui-mode-py-直接装配未纳入任务-2-收口范围
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2-logic-rigor
- 说明:

  web/ui_mode.py 第 221 行 `SystemConfigService(conn, ...)` 是一处直接装配，但任务 2 的搜索范围仅限 `web/routes/`。当请求级服务容器建立后，render_ui_template 执行时 g.services 已可用，该处应改为从容器取用或显式登记到治理台账。当前 plan 将 ui_mode.py 放在任务 8 治理，但未提及此处直接装配需同步处理或登记。
- 建议:

  在任务 2 步骤 7 的残余装配清点中显式覆盖 `web/ui_mode.py`，或在任务 8 步骤 7.5 中明确声明此处需改为从 g.services 取用（如果请求上下文此时已具备条件）。
- 证据:
  - `web/ui_mode.py:221#SystemConfigService(conn, ...)`
  - `web/ui_mode.py`

### CalendarService/ConfigService 延迟导入实际无循环依赖

- ID: F-maintainability-2
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2-logic-rigor
- 说明:

  plan 中任务 5 步骤 6 要求 "明确延迟导入最终命运"，但经代码验证，CalendarService (calendar_service.py) 和 ConfigService (config_service.py) 均未导入 schedule_service 或其模块间任何形成循环的路径。延迟导入纯属历史遗留防御性写法，不存在真实循环依赖。plan 对此留了一个开放决策点，但建议直接给出结论：应移至模块顶层。
- 建议:

  在 plan 中补充明确结论：CalendarService / ConfigService 已无循环依赖，任务 5 应直接移至模块顶层导入，不留开放决策。
- 证据:
  - `core/services/scheduler/schedule_service.py:259-260`
  - `core/services/scheduler/calendar_service.py:1-13`
  - `core/services/scheduler/config_service.py:1-15`
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/calendar_service.py`
  - `core/services/scheduler/config_service.py`

### F401 全局忽略移除需前置评估影响面

- ID: F-f401-全局忽略移除需前置评估影响面
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2-logic-rigor
- 说明:

  pyproject.toml 第 31 行将 F401 列入全局 ignore 列表。plan 任务 3 步骤 8.2 要求 "先移除全局 F401 忽略，再同步覆盖根层门面"，但未要求在移除前先全量搜索评估影响面。ruff 移除全局 F401 后，所有未标注 `# noqa: F401` 的文件都会立即报错，可能远超根层门面范围。plan 应要求 "移除前先执行一次 ruff check --select F401 并记录影响文件清单"。
- 建议:

  在任务 3 步骤 8.2 中增加前置步骤：先执行 `python -m ruff check --select F401` 记录当前影响文件清单，再按清单逐文件加内联 noqa 或 per-file-ignores，最后再移除全局忽略。
- 证据:
  - `pyproject.toml:31`
  - `pyproject.toml`

### 静默异常门禁扫描范围未覆盖 web/bootstrap/ 和 web/ui_mode.py

- ID: F-maintainability-4
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2-logic-rigor
- 说明:

  现有 test_no_silent_exception_swallow (test_architecture_fitness.py line 404) 的扫描范围由 CORE_DIRS 决定（web/routes, core/services, data/repositories, core/models, core/infrastructure, web/viewmodels），不包含 web/bootstrap/ 和 web/ui_mode.py。plan 任务 1 步骤 6 要求 "把 web/bootstrap/ 补入扫描范围"，但未显式提及 web/ui_mode.py。ui_mode.py 包含至少 15+ 处 except Exception 后静默回退（pass/return 空值/return 默认值），是当前仓库静默回退密度最高的单文件之一。
- 建议:

  在任务 1 步骤 6 中把 web/ui_mode.py 显式纳入静默异常门禁扫描范围，与 web/bootstrap/ 同批登记白名单。
- 证据:
  - `tests/test_architecture_fitness.py:21-22`
  - `web/ui_mode.py:1-421`
  - `tests/test_architecture_fitness.py`
  - `web/ui_mode.py`

### pre-commit 钩子使用裸 ruff 命令存在版本漂移

- ID: F-pre-commit-钩子使用裸-ruff-命令存在版本漂移
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: R2-logic-rigor
- 说明:

  当前 .pre-commit-config.yaml 第 9 行直接调用 `ruff check --fix --exit-non-zero-on-fix`，使用 system PATH 中的 ruff。plan 正确识别了这个风险并要求改成 `python -m ruff`，但实际实施中需注意 pre-commit 的 language: system 模式下 python -m ruff 可能依赖当前 shell 环境的 python 版本。plan 应考虑在 entry 中使用与 scripts/run_quality_gate.py 一致的调用方式。
- 建议:

  确保 .pre-commit-config.yaml 的 entry 与 scripts/run_quality_gate.py 使用完全一致的 ruff 调用方式和版本断言逻辑，避免本地钩子与门禁脚本产生不同结果。
- 证据:
  - `.pre-commit-config.yaml:9-10`
  - `.pre-commit-config.yaml`

### 计划复杂度接近认知天花板但可接受

- ID: F-计划复杂度接近认知天花板但可接受
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 接受风险
- 相关里程碑: R3-overall-assessment
- 说明:

  plan 总共 10 个任务，56 条已吸收修正、十多万字，复杂度已经接近实施执行人的认知天花板。部分任务的步骤拆分粒度过细（如任务 1 有7 个主步骤 + 3 个半步骤、任务 3 有11 个主步骤），实际执行时很难严格按顺序来。但从治理角度看，这种粒度确实减少了歧义空间，属于“宁偶不缺”的实践，是可接受的代价。

### ScheduleRunInput 字段归属尚不确定但 plan 已尽力明确

- ID: F-maintainability-7
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 接受风险
- 相关里程碑: R3-overall-assessment
- 说明:

  plan 任务 5 步骤 3.5 定义了 ScheduleRunInput 27 字段归属规则，但当前 run_command.py 、run_context.py 和 ScheduleOrchestrationOutcome 均为待建文件，字段模型的最终形态要到实施时才能确定。plan 写得足够详细以指导实施，但字段归属规则不宜被视为最终形态，应允许在实施时根据实测微调。

### 结构决策简洁实用无过度设计

- ID: F-结构决策简洁实用无过度设计
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 接受风险
- 相关里程碑: R3-overall-assessment
- 说明:

  plan 对 web/routes/domains/ 采用“非同名子包”策略避免 scheduler.py 与 scheduler/ 同名冲突，是简洁而正确的决策。调度服务采用子包化且根层只保留门面的做法也合理。number_utils.py 保留在根层共享位置而非强移入 config/ 子包，符合实际跨包依赖现状。前端采用 DOM 协议而非新全局注册表，也是克制的好决策。整体结构决策简洁实用，未发现过度设计。

## 评审里程碑

### R1-fact-check · 第一轮：关键事实核实与代码对照

- 状态: 已完成
- 记录时间: 2026-04-06T07:34:34.385Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_input_builder.py, core/services/scheduler/schedule_orchestrator.py, core/services/scheduler/schedule_persistence.py, core/services/scheduler/gantt_critical_chain.py, web/bootstrap/factory.py, web/bootstrap/static_versioning.py, web/ui_mode.py, core/algorithms/greedy/scheduler.py
- 摘要:

  逐项对照 plan 中的事实性声明与代码实际状态，覆盖任务 1-7 涉及的核心文件。

  **已验证通过的声明：**
  1. `ScheduleService.__init__` 签名 `(conn, logger=None, op_logger=None)` 3 参数，内部创建 10 个仓储实例 ✅ 与代码完全一致 (line 78-96)
  2. `_get_snapshot_with_optional_strict_mode` 位于 `schedule_service.py` 第 49-59 行 ✅
  3. `GreedyScheduler.schedule(...)` 332 行 (56-388)，plan 称"300 多行" ✅
  4. `_cfg_value` 在 `schedule_optimizer.py` 中 9 处命中（含 3 处数值 helper 传入点） ✅ 精确匹配
  5. `_norm_text` 5 处命中，4 处实际消费点 ✅
  6. `_schedule_with_optional_strict_mode` 在 `schedule_optimizer.py` 中 3 处引用（导入、常规调用、`if best is None` 兜底） ✅
  7. `schedule_optimizer_steps.py` 中 `_run_ortools_warmstart` (146-147) 与 `_run_multi_start` (296-297) 各有本地 `_cfg_value` 闭包 ✅
  8. `collect_schedule_run_input` 16 参数（含 6 函数注入 + 2 类注入） ✅
  9. `ScheduleRunInput` 27 字段 ✅ (line 19-45)
  10. `persist_schedule` 签名为 `svc` + 21 个关键字参数 ✅ (line 244-267)
  11. `_normalize_optimizer_outcome` 大量 `getattr` 探测 ✅ (line 53-68)
  12. `_merge_summary_warnings` 对摘要形态试探 ✅ (line 71-100)
  13. `_lookup_template_group_context` 中 `_get_template_and_group_for_op` 旧回退 ✅ (line 85-105)
  14. `gantt_critical_chain.py` 5 处 `except Exception` 准确落点 ✅ (日期解析/时间差/load_rows/工艺前驱边/资源前驱边)
  15. `factory.py:_open_db` 2 处无日志静默回退 + 1 处有日志 ✅
  16. `factory.py:_close_db` 1 处 `except Exception: pass` ✅
  17. `factory.py:_perf_headers` 2 处异常吞没 ✅ (line 322 + line 333)
  18. `static_versioning.py:_mtime_version` `except Exception: return ""` ✅ (line 68)
  19. `static_versioning.py:_versioned_url_for` `except Exception: pass` ✅ (line 84)
  20. `web/ui_mode.py` 存在大量静默回退（至少 15+ 处 `except Exception` 后 `pass`/返回空值/返回默认值） ✅
  21. `CalendarService` / `ConfigService` 延迟导入在 `_run_schedule_impl` line 259-260 ✅
  22. `_run_schedule_impl` 返回值构建块中 7 处防御性 `getattr(orchestration.summary, ...)` ✅ (line 323-329)

  **核实结论**：plan 中全部事实性声明与代码实际状态高度一致，未发现虚假数据或错误描述。
- 结论:

  逐项对照 plan 中的事实性声明与代码实际状态，覆盖任务 1-7 涉及的核心文件。 **已验证通过的声明：** 1. `ScheduleService.__init__` 签名 `(conn, logger=None, op_logger=None)` 3 参数，内部创建 10 个仓储实例 ✅ 与代码完全一致 (line 78-96) 2. `_get_snapshot_with_optional_strict_mode` 位于 `schedule_service.py` 第 49-59 行 ✅ 3. `GreedyScheduler.schedule(...)` 332 行 (56-388)，plan 称"300 多行" ✅ 4. `_cfg_value` 在 `schedule_optimizer.py` 中 9 处命中（含 3 处数值 helper 传入点） ✅ 精确匹配 5. `_norm_text` 5 处命中，4 处实际消费点 ✅ 6. `_schedule_with_optional_strict_mode` 在 `schedule_optimizer.py` 中 3 处引用（导入、常规调用、`if best is None` 兜底） ✅ 7. `schedule_optimizer_steps.py` 中 `_run_ortools_warmstart` (146-147) 与 `_run_multi_start` (296-297) 各有本地 `_cfg_value` 闭包 ✅ 8. `collect_schedule_run_input` 16 参数（含 6 函数注入 + 2 类注入） ✅ 9. `ScheduleRunInput` 27 字段 ✅ (line 19-45) 10. `persist_schedule` 签名为 `svc` + 21 个关键字参数 ✅ (line 244-267) 11. `_normalize_optimizer_outcome` 大量 `getattr` 探测 ✅ (line 53-68) 12. `_merge_summary_warnings` 对摘要形态试探 ✅ (line 71-100) 13. `_lookup_template_group_context` 中 `_get_template_and_group_for_op` 旧回退 ✅ (line 85-105) 14. `gantt_critical_chain.py` 5 处 `except Exception` 准确落点 ✅ (日期解析/时间差/load_rows/工艺前驱边/资源前驱边) 15. `factory.py:_open_db` 2 处无日志静默回退 + 1 处有日志 ✅ 16. `factory.py:_close_db` 1 处 `except Exception: pass` ✅ 17. `factory.py:_perf_headers` 2 处异常吞没 ✅ (line 322 + line 333) 18. `static_versioning.py:_mtime_version` `except Exception: return ""` ✅ (line 68) 19. `static_versioning.py:_versioned_url_for` `except Exception: pass` ✅ (line 84) 20. `web/ui_mode.py` 存在大量静默回退（至少 15+ 处 `except Exception` 后 `pass`/返回空值/返回默认值） ✅ 21. `CalendarService` / `ConfigService` 延迟导入在 `_run_schedule_impl` line 259-260 ✅ 22. `_run_schedule_impl` 返回值构建块中 7 处防御性 `getattr(orchestration.summary, ...)` ✅ (line 323-329) **核实结论**：plan 中全部事实性声明与代码实际状态高度一致，未发现虚假数据或错误描述。
- 证据:
  - `core/services/scheduler/schedule_service.py:78-96#ScheduleService.__init__`
  - `core/services/scheduler/schedule_optimizer.py:290-296#_cfg_value/_norm_text`
  - `core/services/scheduler/schedule_input_collector.py:17-45#ScheduleRunInput`
  - `core/services/scheduler/schedule_persistence.py:244-267#persist_schedule`
  - `core/services/scheduler/gantt_critical_chain.py:9-133`
  - `web/bootstrap/factory.py:262-304#_open_db/_close_db`
  - `web/bootstrap/static_versioning.py:59-89#_mtime_version/_versioned_url_for`
  - `web/ui_mode.py:1-421`

### R2-logic-rigor · 第二轮：实施逻辑严谨性与依赖链审查

- 状态: 已完成
- 记录时间: 2026-04-06T07:38:16.301Z
- 已审模块: pyproject.toml, .pre-commit-config.yaml, requirements-dev.txt, tests/test_architecture_fitness.py, tests/check_quickref_vs_routes.py
- 摘要:

  第二轮审查聚焦批次依赖链完整性、验证命令可用性、边界条件覆盖和潜在逻辑缺口。

  **批次依赖链验证：**
  - 批次 0→1→2→3→4→5 的前后依赖关系逻辑自洽，任务 2 先于任务 3 的约束正确
  - 任务 3 的延迟物理迁移策略（gantt/ 归任务 7，batch/dispatch/calendar 归任务 8）合理
  - `install_versioned_url_for` (line 209) → `init_ui_mode` (line 231) 的初始化顺序已正确记录

  **验证命令可用性：**
  - 全部被引用的验证测试文件均真实存在
  - `check_quickref_vs_routes.py` 使用 `python` 直接执行而非 `pytest` 是正确的
  - 验证命令中的结构门禁（python -c "..."）语法正确且目标路径与代码现实匹配

  **环境基础设施现状：**
  - `requirements-dev.txt` 仅声明 `pytest`，确实缺少 `pytest-cov`、`radon`、`ruff` 版本约束
  - `pyproject.toml` 无 `[tool.pytest.ini_options]`，无 `testpaths` 配置
  - `tests/*` 在 ruff per-file-ignores 中不保证递归匹配子目录，plan 的 `tests/**/*.py` 修正是必要的
  - `F401` 全局忽略使得 per-file-ignores 中的 F401 声明实质冗余

  **发现 5 个问题（详见结构化发现）：**
  1. ui_mode.py 直接装配未纳入任务 2 范围 [中]
  2. CalendarService/ConfigService 延迟导入无循环依赖证据 [低]
  3. F401 全局忽略移除需前置影响面评估 [中]
  4. 静默异常门禁扫描范围缺少 web/ui_mode.py [中]
  5. pre-commit 钩子版本漂移风险 [低]
- 结论:

  第二轮审查聚焦批次依赖链完整性、验证命令可用性、边界条件覆盖和潜在逻辑缺口。 **批次依赖链验证：** - 批次 0→1→2→3→4→5 的前后依赖关系逻辑自洽，任务 2 先于任务 3 的约束正确 - 任务 3 的延迟物理迁移策略（gantt/ 归任务 7，batch/dispatch/calendar 归任务 8）合理 - `install_versioned_url_for` (line 209) → `init_ui_mode` (line 231) 的初始化顺序已正确记录 **验证命令可用性：** - 全部被引用的验证测试文件均真实存在 - `check_quickref_vs_routes.py` 使用 `python` 直接执行而非 `pytest` 是正确的 - 验证命令中的结构门禁（python -c "..."）语法正确且目标路径与代码现实匹配 **环境基础设施现状：** - `requirements-dev.txt` 仅声明 `pytest`，确实缺少 `pytest-cov`、`radon`、`ruff` 版本约束 - `pyproject.toml` 无 `[tool.pytest.ini_options]`，无 `testpaths` 配置 - `tests/*` 在 ruff per-file-ignores 中不保证递归匹配子目录，plan 的 `tests/**/*.py` 修正是必要的 - `F401` 全局忽略使得 per-file-ignores 中的 F401 声明实质冗余 **发现 5 个问题（详见结构化发现）：** 1. ui_mode.py 直接装配未纳入任务 2 范围 [中] 2. CalendarService/ConfigService 延迟导入无循环依赖证据 [低] 3. F401 全局忽略移除需前置影响面评估 [中] 4. 静默异常门禁扫描范围缺少 web/ui_mode.py [中] 5. pre-commit 钩子版本漂移风险 [低]
- 证据:
  - `pyproject.toml:1-47`
  - `.pre-commit-config.yaml:1-12`
  - `requirements-dev.txt:1-4`
  - `tests/test_architecture_fitness.py:404-497#test_no_silent_exception_swallow`
  - `tests/test_architecture_fitness.py:44-55#_known_oversize_files`
  - `web/bootstrap/factory.py:209-231#install_versioned_url_for -> init_ui_mode ordering`
  - `web/ui_mode.py:215-221#_read_ui_mode_from_db`
- 问题:
  - [中] 可维护性: ui_mode.py 直接装配未纳入任务 2 收口范围
  - [低] 可维护性: CalendarService/ConfigService 延迟导入实际无循环依赖
  - [中] 可维护性: F401 全局忽略移除需前置评估影响面
  - [中] 可维护性: 静默异常门禁扫描范围未覆盖 web/bootstrap/ 和 web/ui_mode.py
  - [低] 可维护性: pre-commit 钩子使用裸 ruff 命令存在版本漂移

### R3-overall-assessment · 第三轮：目标可达性、优雅度与整体评估

- 状态: 已完成
- 记录时间: 2026-04-06T07:39:34.166Z
- 已审模块: plan 整体结构与 10 个任务
- 摘要:

  第三轮从全局视角评估 plan 的可达性、设计优雅度和可能的遗漏。

  ## 目标可达性评估

  **总体判断：目标可达，但需注意执行节奏。**

  1. **批次 0（工程基线与治理台账）**：完全可行，无代码行为改动，风险最低。
  2. **批次 1（装配收口与目录骨架）**：可行但有工作量风险。45 个文件的平铺目录需分组迁移，50+ 处相对导入需修正。plan 已通过"分批物理迁移"策略降低了风险。
  3. **批次 2（配置与主链收口）**：最具技术挑战性。`ScheduleRunInput` 27 字段拆分为 `RunCommand` / `RunContext` / `ScheduleOrchestrationOutcome`、`persist_schedule()` 21 参数收口为对象边界、多处兼容桥删除——这些都是有明确前后依赖的精细改动。plan 通过充分的实施前确认和结构门禁降低了风险。
  4. **批次 3（算法与数据）**：可行。`GreedyScheduler.schedule(...)` 拆分有明确的 6 段职责划分；`database.py` 与 `backup.py` 拆分边界清晰。
  5. **批次 4（界面与前端）**：可行但范围广。包含 Excel 页面流程骨架、双模板收敛、静态资源构建入口、行内脚本迁出等多个交叉改动。plan 通过试点→扩展的渐进策略控制了风险。
  6. **批次 5（测试与文档）**：低风险，主要是文件迁移与文档整理。

  ## 设计优雅度评估

  **优点：**
  - **"非同名子包"策略**避免了 `scheduler.py` 与 `scheduler/` 冲突，是简洁正确的决策
  - **调度服务子包化**且根层只保留门面，符合 Python 包设计惯例
  - **`number_utils.py` 保留在根层共享位置**而非强移入 `config/`，尊重实际跨包依赖
  - **前端采用 DOM 协议而非新全局注册表**，体现克制
  - **Excel 页面只抽骨架+钩子**而非宽泛 `ExcelImportController`，避免过度抽象
  - **请求级服务容器**是 Flask 生态下最自然的依赖注入方式
  - **治理台账使用受控 JSON 代码块**而非自由格式正文，机器可读门禁可靠

  **可改进点：**
  - plan 自身的 56 条修正记录体现了极其充分的迭代审查，但也说明文档本身已接近认知天花板
  - 部分任务步骤拆得过细（如任务 1 有 7+3 个步骤），实际执行中可能需要合并执行
  - ScheduleRunInput 27 字段归属规则写得很详尽但尚属纸面方案，最终形态要到实施时才能确定

  ## 遗漏检查

  **已确认的遗漏（本轮新发现，已记录为结构化发现）：**
  1. `web/ui_mode.py:_read_ui_mode_from_db` 的直接 `SystemConfigService(conn, ...)` 装配未在任务 2 或任务 8 显式声明
  2. 静默异常门禁扫描范围应把 `web/ui_mode.py` 与 `web/bootstrap/` 一起纳入
  3. F401 全局忽略移除前需先评估影响面

  **未发现的重大遗漏：**
  - 问题覆盖矩阵（第七章）将 A1-E6 + 补充发现全部映射到任务，无无主项
  - 固定边界（Win7 / Python 3.8 / Chrome109 / 数据库迁移链路）被明确标为接受风险
  - 禁止项（4 大类 + 6 小项）覆盖了最常见的技术债务扩散模式
  - 验收口径（第九章 5 条）可操作、可验证

  ## 是否存在过度设计

  **结论：不存在过度设计。**

  所有新增结构（`web/routes/domains/`、`core/services/scheduler/<子包>/`、`web/pageflows/`、`data/queries/`、`core/infrastructure/data_repairs/`、`tests/<分层>/`）都有明确的职责边界和真实的代码迁入对象，不是空架子。plan 明确禁止了"新总抽象""新全局注册表""第二套事实源"等过度设计模式。
- 结论:

  第三轮从全局视角评估 plan 的可达性、设计优雅度和可能的遗漏。 ## 目标可达性评估 **总体判断：目标可达，但需注意执行节奏。** 1. **批次 0（工程基线与治理台账）**：完全可行，无代码行为改动，风险最低。 2. **批次 1（装配收口与目录骨架）**：可行但有工作量风险。45 个文件的平铺目录需分组迁移，50+ 处相对导入需修正。plan 已通过"分批物理迁移"策略降低了风险。 3. **批次 2（配置与主链收口）**：最具技术挑战性。`ScheduleRunInput` 27 字段拆分为 `RunCommand` / `RunContext` / `ScheduleOrchestrationOutcome`、`persist_schedule()` 21 参数收口为对象边界、多处兼容桥删除——这些都是有明确前后依赖的精细改动。plan 通过充分的实施前确认和结构门禁降低了风险。 4. **批次 3（算法与数据）**：可行。`GreedyScheduler.schedule(...)` 拆分有明确的 6 段职责划分；`database.py` 与 `backup.py` 拆分边界清晰。 5. **批次 4（界面与前端）**：可行但范围广。包含 Excel 页面流程骨架、双模板收敛、静态资源构建入口、行内脚本迁出等多个交叉改动。plan 通过试点→扩展的渐进策略控制了风险。 6. **批次 5（测试与文档）**：低风险，主要是文件迁移与文档整理。 ## 设计优雅度评估 **优点：** - **"非同名子包"策略**避免了 `scheduler.py` 与 `scheduler/` 冲突，是简洁正确的决策 - **调度服务子包化**且根层只保留门面，符合 Python 包设计惯例 - **`number_utils.py` 保留在根层共享位置**而非强移入 `config/`，尊重实际跨包依赖 - **前端采用 DOM 协议而非新全局注册表**，体现克制 - **Excel 页面只抽骨架+钩子**而非宽泛 `ExcelImportController`，避免过度抽象 - **请求级服务容器**是 Flask 生态下最自然的依赖注入方式 - **治理台账使用受控 JSON 代码块**而非自由格式正文，机器可读门禁可靠 **可改进点：** - plan 自身的 56 条修正记录体现了极其充分的迭代审查，但也说明文档本身已接近认知天花板 - 部分任务步骤拆得过细（如任务 1 有 7+3 个步骤），实际执行中可能需要合并执行 - ScheduleRunInput 27 字段归属规则写得很详尽但尚属纸面方案，最终形态要到实施时才能确定 ## 遗漏检查 **已确认的遗漏（本轮新发现，已记录为结构化发现）：** 1. `web/ui_mode.py:_read_ui_mode_from_db` 的直接 `SystemConfigService(conn, ...)` 装配未在任务 2 或任务 8 显式声明 2. 静默异常门禁扫描范围应把 `web/ui_mode.py` 与 `web/bootstrap/` 一起纳入 3. F401 全局忽略移除前需先评估影响面 **未发现的重大遗漏：** - 问题覆盖矩阵（第七章）将 A1-E6 + 补充发现全部映射到任务，无无主项 - 固定边界（Win7 / Python 3.8 / Chrome109 / 数据库迁移链路）被明确标为接受风险 - 禁止项（4 大类 + 6 小项）覆盖了最常见的技术债务扩散模式 - 验收口径（第九章 5 条）可操作、可验证 ## 是否存在过度设计 **结论：不存在过度设计。** 所有新增结构（`web/routes/domains/`、`core/services/scheduler/<子包>/`、`web/pageflows/`、`data/queries/`、`core/infrastructure/data_repairs/`、`tests/<分层>/`）都有明确的职责边界和真实的代码迁入对象，不是空架子。plan 明确禁止了"新总抽象""新全局注册表""第二套事实源"等过度设计模式。
- 问题:
  - [低] 可维护性: 计划复杂度接近认知天花板但可接受
  - [低] 可维护性: ScheduleRunInput 字段归属尚不确定但 plan 已尽力明确
  - [低] 可维护性: 结构决策简洁实用无过度设计

## 最终结论

## 三轮深度审查最终结论

本次对《APS 技术债务最终合并修复 plan》进行了三轮深度审查，覆盖了 18 个核心源文件与配置文件的代码级对照验证。

### 总体评价：有条件通过

**该 plan 是一份高质量、可执行的技术债务治理方案。**

#### 事实准确性（第一轮）：✅ 优秀
- plan 中 22 项关键事实性声明（函数签名、参数计数、行号、命中数等）全部与代码实际状态精确匹配
- 未发现虚假数据、错误路径或拼写错误的测试文件名
- 所有引用的验证测试文件均真实存在

#### 逻辑严谨性（第二轮）：✅ 良好，有 5 处需补充
- 批次依赖链（0→1→2→3→4→5）逻辑自洽
- 批次间任务排序约束正确
- 验证命令语法正确且目标路径匹配
- 发现 3 处中等级别缺口需补充：
  - `web/ui_mode.py` 的直接装配点应显式纳入任务 2 或任务 8 范围
  - `F401` 全局忽略移除前需先评估影响面
  - 静默异常门禁扫描范围应显式覆盖 `web/ui_mode.py`
- 发现 2 处低级别优化建议：
  - `CalendarService`/`ConfigService` 延迟导入可直接给出"上移"结论
  - `pre-commit` 钩子应与门禁脚本统一调用方式

#### 目标可达性与优雅度（第三轮）：✅ 良好
- 6 个批次的目标均可达，批次 2（配置与主链收口）挑战最大但 plan 已通过充分的实施前确认降低了风险
- 结构决策简洁实用，未发现过度设计
- "非同名子包"策略、请求级服务容器、Excel 骨架+钩子模式、DOM 前端协议等核心设计决策均属克制且正确的选择
- plan 复杂度接近认知天花板但在可接受范围内

### 需补充的 3 项修正

1. **任务 2 / 任务 8**：显式声明 `web/ui_mode.py:_read_ui_mode_from_db` 的 `SystemConfigService(conn, ...)` 装配需收口或登记
2. **任务 3 步骤 8.2**：增加前置步骤 `python -m ruff check --select F401` 评估影响面再移除全局忽略
3. **任务 1 步骤 6**：把 `web/ui_mode.py` 显式纳入静默异常门禁扫描范围

### 无阻断性缺陷，建议在上述 3 项修正后启动实施。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnmvgo30-9ndyoj",
  "createdAt": "2026-04-06T00:00:00.000Z",
  "updatedAt": "2026-04-06T07:40:07.699Z",
  "finalizedAt": "2026-04-06T07:40:07.699Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "技术债务最终合并修复plan三轮深度审查",
    "date": "2026-04-06",
    "overview": "对 20260405_技术债务最终合并修复plan.md 进行三轮深度审查，验证目标可达性、实施严谨性与代码事实一致性"
  },
  "scope": {
    "markdown": "# 技术债务最终合并修复 plan 三轮深度审查\n\n**审查日期**：2026-04-06\n\n**审查对象**：`.limcode/plans/20260405_技术债务最终合并修复plan.md`\n\n**审查目标**：\n1. 第一轮：验证 plan 中事实性声明与代码实际状态是否一致\n2. 第二轮：审查实施逻辑严谨性、批次依赖链完整性、边界条件覆盖\n3. 第三轮：评估整体目标可达性、优雅度、是否存在过度设计或遗漏\n\n**审查方法**：逐任务对照代码事实进行验证，不修改任何业务代码"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查最终结论\n\n本次对《APS 技术债务最终合并修复 plan》进行了三轮深度审查，覆盖了 18 个核心源文件与配置文件的代码级对照验证。\n\n### 总体评价：有条件通过\n\n**该 plan 是一份高质量、可执行的技术债务治理方案。**\n\n#### 事实准确性（第一轮）：✅ 优秀\n- plan 中 22 项关键事实性声明（函数签名、参数计数、行号、命中数等）全部与代码实际状态精确匹配\n- 未发现虚假数据、错误路径或拼写错误的测试文件名\n- 所有引用的验证测试文件均真实存在\n\n#### 逻辑严谨性（第二轮）：✅ 良好，有 5 处需补充\n- 批次依赖链（0→1→2→3→4→5）逻辑自洽\n- 批次间任务排序约束正确\n- 验证命令语法正确且目标路径匹配\n- 发现 3 处中等级别缺口需补充：\n  - `web/ui_mode.py` 的直接装配点应显式纳入任务 2 或任务 8 范围\n  - `F401` 全局忽略移除前需先评估影响面\n  - 静默异常门禁扫描范围应显式覆盖 `web/ui_mode.py`\n- 发现 2 处低级别优化建议：\n  - `CalendarService`/`ConfigService` 延迟导入可直接给出\"上移\"结论\n  - `pre-commit` 钩子应与门禁脚本统一调用方式\n\n#### 目标可达性与优雅度（第三轮）：✅ 良好\n- 6 个批次的目标均可达，批次 2（配置与主链收口）挑战最大但 plan 已通过充分的实施前确认降低了风险\n- 结构决策简洁实用，未发现过度设计\n- \"非同名子包\"策略、请求级服务容器、Excel 骨架+钩子模式、DOM 前端协议等核心设计决策均属克制且正确的选择\n- plan 复杂度接近认知天花板但在可接受范围内\n\n### 需补充的 3 项修正\n\n1. **任务 2 / 任务 8**：显式声明 `web/ui_mode.py:_read_ui_mode_from_db` 的 `SystemConfigService(conn, ...)` 装配需收口或登记\n2. **任务 3 步骤 8.2**：增加前置步骤 `python -m ruff check --select F401` 评估影响面再移除全局忽略\n3. **任务 1 步骤 6**：把 `web/ui_mode.py` 显式纳入静默异常门禁扫描范围\n\n### 无阻断性缺陷，建议在上述 3 项修正后启动实施。",
    "recommendedNextAction": "在 plan 中补充上述 3 项修正（ui_mode.py 装配收口声明、F401 影响面前置评估、ui_mode.py 纳入门禁扫描范围）后即可启动批次 0 实施",
    "reviewedModules": [
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_input_builder.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "core/services/scheduler/schedule_persistence.py",
      "core/services/scheduler/gantt_critical_chain.py",
      "web/bootstrap/factory.py",
      "web/bootstrap/static_versioning.py",
      "web/ui_mode.py",
      "core/algorithms/greedy/scheduler.py",
      "pyproject.toml",
      ".pre-commit-config.yaml",
      "requirements-dev.txt",
      "tests/test_architecture_fitness.py",
      "tests/check_quickref_vs_routes.py",
      "plan 整体结构与 10 个任务"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 8,
    "severity": {
      "high": 0,
      "medium": 3,
      "low": 5
    }
  },
  "milestones": [
    {
      "id": "R1-fact-check",
      "title": "第一轮：关键事实核实与代码对照",
      "status": "completed",
      "recordedAt": "2026-04-06T07:34:34.385Z",
      "summaryMarkdown": "逐项对照 plan 中的事实性声明与代码实际状态，覆盖任务 1-7 涉及的核心文件。\n\n**已验证通过的声明：**\n1. `ScheduleService.__init__` 签名 `(conn, logger=None, op_logger=None)` 3 参数，内部创建 10 个仓储实例 ✅ 与代码完全一致 (line 78-96)\n2. `_get_snapshot_with_optional_strict_mode` 位于 `schedule_service.py` 第 49-59 行 ✅\n3. `GreedyScheduler.schedule(...)` 332 行 (56-388)，plan 称\"300 多行\" ✅\n4. `_cfg_value` 在 `schedule_optimizer.py` 中 9 处命中（含 3 处数值 helper 传入点） ✅ 精确匹配\n5. `_norm_text` 5 处命中，4 处实际消费点 ✅\n6. `_schedule_with_optional_strict_mode` 在 `schedule_optimizer.py` 中 3 处引用（导入、常规调用、`if best is None` 兜底） ✅\n7. `schedule_optimizer_steps.py` 中 `_run_ortools_warmstart` (146-147) 与 `_run_multi_start` (296-297) 各有本地 `_cfg_value` 闭包 ✅\n8. `collect_schedule_run_input` 16 参数（含 6 函数注入 + 2 类注入） ✅\n9. `ScheduleRunInput` 27 字段 ✅ (line 19-45)\n10. `persist_schedule` 签名为 `svc` + 21 个关键字参数 ✅ (line 244-267)\n11. `_normalize_optimizer_outcome` 大量 `getattr` 探测 ✅ (line 53-68)\n12. `_merge_summary_warnings` 对摘要形态试探 ✅ (line 71-100)\n13. `_lookup_template_group_context` 中 `_get_template_and_group_for_op` 旧回退 ✅ (line 85-105)\n14. `gantt_critical_chain.py` 5 处 `except Exception` 准确落点 ✅ (日期解析/时间差/load_rows/工艺前驱边/资源前驱边)\n15. `factory.py:_open_db` 2 处无日志静默回退 + 1 处有日志 ✅\n16. `factory.py:_close_db` 1 处 `except Exception: pass` ✅\n17. `factory.py:_perf_headers` 2 处异常吞没 ✅ (line 322 + line 333)\n18. `static_versioning.py:_mtime_version` `except Exception: return \"\"` ✅ (line 68)\n19. `static_versioning.py:_versioned_url_for` `except Exception: pass` ✅ (line 84)\n20. `web/ui_mode.py` 存在大量静默回退（至少 15+ 处 `except Exception` 后 `pass`/返回空值/返回默认值） ✅\n21. `CalendarService` / `ConfigService` 延迟导入在 `_run_schedule_impl` line 259-260 ✅\n22. `_run_schedule_impl` 返回值构建块中 7 处防御性 `getattr(orchestration.summary, ...)` ✅ (line 323-329)\n\n**核实结论**：plan 中全部事实性声明与代码实际状态高度一致，未发现虚假数据或错误描述。",
      "conclusionMarkdown": "逐项对照 plan 中的事实性声明与代码实际状态，覆盖任务 1-7 涉及的核心文件。 **已验证通过的声明：** 1. `ScheduleService.__init__` 签名 `(conn, logger=None, op_logger=None)` 3 参数，内部创建 10 个仓储实例 ✅ 与代码完全一致 (line 78-96) 2. `_get_snapshot_with_optional_strict_mode` 位于 `schedule_service.py` 第 49-59 行 ✅ 3. `GreedyScheduler.schedule(...)` 332 行 (56-388)，plan 称\"300 多行\" ✅ 4. `_cfg_value` 在 `schedule_optimizer.py` 中 9 处命中（含 3 处数值 helper 传入点） ✅ 精确匹配 5. `_norm_text` 5 处命中，4 处实际消费点 ✅ 6. `_schedule_with_optional_strict_mode` 在 `schedule_optimizer.py` 中 3 处引用（导入、常规调用、`if best is None` 兜底） ✅ 7. `schedule_optimizer_steps.py` 中 `_run_ortools_warmstart` (146-147) 与 `_run_multi_start` (296-297) 各有本地 `_cfg_value` 闭包 ✅ 8. `collect_schedule_run_input` 16 参数（含 6 函数注入 + 2 类注入） ✅ 9. `ScheduleRunInput` 27 字段 ✅ (line 19-45) 10. `persist_schedule` 签名为 `svc` + 21 个关键字参数 ✅ (line 244-267) 11. `_normalize_optimizer_outcome` 大量 `getattr` 探测 ✅ (line 53-68) 12. `_merge_summary_warnings` 对摘要形态试探 ✅ (line 71-100) 13. `_lookup_template_group_context` 中 `_get_template_and_group_for_op` 旧回退 ✅ (line 85-105) 14. `gantt_critical_chain.py` 5 处 `except Exception` 准确落点 ✅ (日期解析/时间差/load_rows/工艺前驱边/资源前驱边) 15. `factory.py:_open_db` 2 处无日志静默回退 + 1 处有日志 ✅ 16. `factory.py:_close_db` 1 处 `except Exception: pass` ✅ 17. `factory.py:_perf_headers` 2 处异常吞没 ✅ (line 322 + line 333) 18. `static_versioning.py:_mtime_version` `except Exception: return \"\"` ✅ (line 68) 19. `static_versioning.py:_versioned_url_for` `except Exception: pass` ✅ (line 84) 20. `web/ui_mode.py` 存在大量静默回退（至少 15+ 处 `except Exception` 后 `pass`/返回空值/返回默认值） ✅ 21. `CalendarService` / `ConfigService` 延迟导入在 `_run_schedule_impl` line 259-260 ✅ 22. `_run_schedule_impl` 返回值构建块中 7 处防御性 `getattr(orchestration.summary, ...)` ✅ (line 323-329) **核实结论**：plan 中全部事实性声明与代码实际状态高度一致，未发现虚假数据或错误描述。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 78,
          "lineEnd": 96,
          "symbol": "ScheduleService.__init__"
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 290,
          "lineEnd": 296,
          "symbol": "_cfg_value/_norm_text"
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py",
          "lineStart": 17,
          "lineEnd": 45,
          "symbol": "ScheduleRunInput"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py",
          "lineStart": 244,
          "lineEnd": 267,
          "symbol": "persist_schedule"
        },
        {
          "path": "core/services/scheduler/gantt_critical_chain.py",
          "lineStart": 9,
          "lineEnd": 133
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 262,
          "lineEnd": 304,
          "symbol": "_open_db/_close_db"
        },
        {
          "path": "web/bootstrap/static_versioning.py",
          "lineStart": 59,
          "lineEnd": 89,
          "symbol": "_mtime_version/_versioned_url_for"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 1,
          "lineEnd": 421
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_input_builder.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "core/services/scheduler/schedule_persistence.py",
        "core/services/scheduler/gantt_critical_chain.py",
        "web/bootstrap/factory.py",
        "web/bootstrap/static_versioning.py",
        "web/ui_mode.py",
        "core/algorithms/greedy/scheduler.py"
      ],
      "recommendedNextAction": null,
      "findingIds": []
    },
    {
      "id": "R2-logic-rigor",
      "title": "第二轮：实施逻辑严谨性与依赖链审查",
      "status": "completed",
      "recordedAt": "2026-04-06T07:38:16.301Z",
      "summaryMarkdown": "第二轮审查聚焦批次依赖链完整性、验证命令可用性、边界条件覆盖和潜在逻辑缺口。\n\n**批次依赖链验证：**\n- 批次 0→1→2→3→4→5 的前后依赖关系逻辑自洽，任务 2 先于任务 3 的约束正确\n- 任务 3 的延迟物理迁移策略（gantt/ 归任务 7，batch/dispatch/calendar 归任务 8）合理\n- `install_versioned_url_for` (line 209) → `init_ui_mode` (line 231) 的初始化顺序已正确记录\n\n**验证命令可用性：**\n- 全部被引用的验证测试文件均真实存在\n- `check_quickref_vs_routes.py` 使用 `python` 直接执行而非 `pytest` 是正确的\n- 验证命令中的结构门禁（python -c \"...\"）语法正确且目标路径与代码现实匹配\n\n**环境基础设施现状：**\n- `requirements-dev.txt` 仅声明 `pytest`，确实缺少 `pytest-cov`、`radon`、`ruff` 版本约束\n- `pyproject.toml` 无 `[tool.pytest.ini_options]`，无 `testpaths` 配置\n- `tests/*` 在 ruff per-file-ignores 中不保证递归匹配子目录，plan 的 `tests/**/*.py` 修正是必要的\n- `F401` 全局忽略使得 per-file-ignores 中的 F401 声明实质冗余\n\n**发现 5 个问题（详见结构化发现）：**\n1. ui_mode.py 直接装配未纳入任务 2 范围 [中]\n2. CalendarService/ConfigService 延迟导入无循环依赖证据 [低]\n3. F401 全局忽略移除需前置影响面评估 [中]\n4. 静默异常门禁扫描范围缺少 web/ui_mode.py [中]\n5. pre-commit 钩子版本漂移风险 [低]",
      "conclusionMarkdown": "第二轮审查聚焦批次依赖链完整性、验证命令可用性、边界条件覆盖和潜在逻辑缺口。 **批次依赖链验证：** - 批次 0→1→2→3→4→5 的前后依赖关系逻辑自洽，任务 2 先于任务 3 的约束正确 - 任务 3 的延迟物理迁移策略（gantt/ 归任务 7，batch/dispatch/calendar 归任务 8）合理 - `install_versioned_url_for` (line 209) → `init_ui_mode` (line 231) 的初始化顺序已正确记录 **验证命令可用性：** - 全部被引用的验证测试文件均真实存在 - `check_quickref_vs_routes.py` 使用 `python` 直接执行而非 `pytest` 是正确的 - 验证命令中的结构门禁（python -c \"...\"）语法正确且目标路径与代码现实匹配 **环境基础设施现状：** - `requirements-dev.txt` 仅声明 `pytest`，确实缺少 `pytest-cov`、`radon`、`ruff` 版本约束 - `pyproject.toml` 无 `[tool.pytest.ini_options]`，无 `testpaths` 配置 - `tests/*` 在 ruff per-file-ignores 中不保证递归匹配子目录，plan 的 `tests/**/*.py` 修正是必要的 - `F401` 全局忽略使得 per-file-ignores 中的 F401 声明实质冗余 **发现 5 个问题（详见结构化发现）：** 1. ui_mode.py 直接装配未纳入任务 2 范围 [中] 2. CalendarService/ConfigService 延迟导入无循环依赖证据 [低] 3. F401 全局忽略移除需前置影响面评估 [中] 4. 静默异常门禁扫描范围缺少 web/ui_mode.py [中] 5. pre-commit 钩子版本漂移风险 [低]",
      "evidence": [
        {
          "path": "pyproject.toml",
          "lineStart": 1,
          "lineEnd": 47
        },
        {
          "path": ".pre-commit-config.yaml",
          "lineStart": 1,
          "lineEnd": 12
        },
        {
          "path": "requirements-dev.txt",
          "lineStart": 1,
          "lineEnd": 4
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 404,
          "lineEnd": 497,
          "symbol": "test_no_silent_exception_swallow"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 44,
          "lineEnd": 55,
          "symbol": "_known_oversize_files"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 209,
          "lineEnd": 231,
          "symbol": "install_versioned_url_for -> init_ui_mode ordering"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 215,
          "lineEnd": 221,
          "symbol": "_read_ui_mode_from_db"
        }
      ],
      "reviewedModules": [
        "pyproject.toml",
        ".pre-commit-config.yaml",
        "requirements-dev.txt",
        "tests/test_architecture_fitness.py",
        "tests/check_quickref_vs_routes.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-ui-mode-py-直接装配未纳入任务-2-收口范围",
        "F-maintainability-2",
        "F-f401-全局忽略移除需前置评估影响面",
        "F-maintainability-4",
        "F-pre-commit-钩子使用裸-ruff-命令存在版本漂移"
      ]
    },
    {
      "id": "R3-overall-assessment",
      "title": "第三轮：目标可达性、优雅度与整体评估",
      "status": "completed",
      "recordedAt": "2026-04-06T07:39:34.166Z",
      "summaryMarkdown": "第三轮从全局视角评估 plan 的可达性、设计优雅度和可能的遗漏。\n\n## 目标可达性评估\n\n**总体判断：目标可达，但需注意执行节奏。**\n\n1. **批次 0（工程基线与治理台账）**：完全可行，无代码行为改动，风险最低。\n2. **批次 1（装配收口与目录骨架）**：可行但有工作量风险。45 个文件的平铺目录需分组迁移，50+ 处相对导入需修正。plan 已通过\"分批物理迁移\"策略降低了风险。\n3. **批次 2（配置与主链收口）**：最具技术挑战性。`ScheduleRunInput` 27 字段拆分为 `RunCommand` / `RunContext` / `ScheduleOrchestrationOutcome`、`persist_schedule()` 21 参数收口为对象边界、多处兼容桥删除——这些都是有明确前后依赖的精细改动。plan 通过充分的实施前确认和结构门禁降低了风险。\n4. **批次 3（算法与数据）**：可行。`GreedyScheduler.schedule(...)` 拆分有明确的 6 段职责划分；`database.py` 与 `backup.py` 拆分边界清晰。\n5. **批次 4（界面与前端）**：可行但范围广。包含 Excel 页面流程骨架、双模板收敛、静态资源构建入口、行内脚本迁出等多个交叉改动。plan 通过试点→扩展的渐进策略控制了风险。\n6. **批次 5（测试与文档）**：低风险，主要是文件迁移与文档整理。\n\n## 设计优雅度评估\n\n**优点：**\n- **\"非同名子包\"策略**避免了 `scheduler.py` 与 `scheduler/` 冲突，是简洁正确的决策\n- **调度服务子包化**且根层只保留门面，符合 Python 包设计惯例\n- **`number_utils.py` 保留在根层共享位置**而非强移入 `config/`，尊重实际跨包依赖\n- **前端采用 DOM 协议而非新全局注册表**，体现克制\n- **Excel 页面只抽骨架+钩子**而非宽泛 `ExcelImportController`，避免过度抽象\n- **请求级服务容器**是 Flask 生态下最自然的依赖注入方式\n- **治理台账使用受控 JSON 代码块**而非自由格式正文，机器可读门禁可靠\n\n**可改进点：**\n- plan 自身的 56 条修正记录体现了极其充分的迭代审查，但也说明文档本身已接近认知天花板\n- 部分任务步骤拆得过细（如任务 1 有 7+3 个步骤），实际执行中可能需要合并执行\n- ScheduleRunInput 27 字段归属规则写得很详尽但尚属纸面方案，最终形态要到实施时才能确定\n\n## 遗漏检查\n\n**已确认的遗漏（本轮新发现，已记录为结构化发现）：**\n1. `web/ui_mode.py:_read_ui_mode_from_db` 的直接 `SystemConfigService(conn, ...)` 装配未在任务 2 或任务 8 显式声明\n2. 静默异常门禁扫描范围应把 `web/ui_mode.py` 与 `web/bootstrap/` 一起纳入\n3. F401 全局忽略移除前需先评估影响面\n\n**未发现的重大遗漏：**\n- 问题覆盖矩阵（第七章）将 A1-E6 + 补充发现全部映射到任务，无无主项\n- 固定边界（Win7 / Python 3.8 / Chrome109 / 数据库迁移链路）被明确标为接受风险\n- 禁止项（4 大类 + 6 小项）覆盖了最常见的技术债务扩散模式\n- 验收口径（第九章 5 条）可操作、可验证\n\n## 是否存在过度设计\n\n**结论：不存在过度设计。**\n\n所有新增结构（`web/routes/domains/`、`core/services/scheduler/<子包>/`、`web/pageflows/`、`data/queries/`、`core/infrastructure/data_repairs/`、`tests/<分层>/`）都有明确的职责边界和真实的代码迁入对象，不是空架子。plan 明确禁止了\"新总抽象\"\"新全局注册表\"\"第二套事实源\"等过度设计模式。",
      "conclusionMarkdown": "第三轮从全局视角评估 plan 的可达性、设计优雅度和可能的遗漏。 ## 目标可达性评估 **总体判断：目标可达，但需注意执行节奏。** 1. **批次 0（工程基线与治理台账）**：完全可行，无代码行为改动，风险最低。 2. **批次 1（装配收口与目录骨架）**：可行但有工作量风险。45 个文件的平铺目录需分组迁移，50+ 处相对导入需修正。plan 已通过\"分批物理迁移\"策略降低了风险。 3. **批次 2（配置与主链收口）**：最具技术挑战性。`ScheduleRunInput` 27 字段拆分为 `RunCommand` / `RunContext` / `ScheduleOrchestrationOutcome`、`persist_schedule()` 21 参数收口为对象边界、多处兼容桥删除——这些都是有明确前后依赖的精细改动。plan 通过充分的实施前确认和结构门禁降低了风险。 4. **批次 3（算法与数据）**：可行。`GreedyScheduler.schedule(...)` 拆分有明确的 6 段职责划分；`database.py` 与 `backup.py` 拆分边界清晰。 5. **批次 4（界面与前端）**：可行但范围广。包含 Excel 页面流程骨架、双模板收敛、静态资源构建入口、行内脚本迁出等多个交叉改动。plan 通过试点→扩展的渐进策略控制了风险。 6. **批次 5（测试与文档）**：低风险，主要是文件迁移与文档整理。 ## 设计优雅度评估 **优点：** - **\"非同名子包\"策略**避免了 `scheduler.py` 与 `scheduler/` 冲突，是简洁正确的决策 - **调度服务子包化**且根层只保留门面，符合 Python 包设计惯例 - **`number_utils.py` 保留在根层共享位置**而非强移入 `config/`，尊重实际跨包依赖 - **前端采用 DOM 协议而非新全局注册表**，体现克制 - **Excel 页面只抽骨架+钩子**而非宽泛 `ExcelImportController`，避免过度抽象 - **请求级服务容器**是 Flask 生态下最自然的依赖注入方式 - **治理台账使用受控 JSON 代码块**而非自由格式正文，机器可读门禁可靠 **可改进点：** - plan 自身的 56 条修正记录体现了极其充分的迭代审查，但也说明文档本身已接近认知天花板 - 部分任务步骤拆得过细（如任务 1 有 7+3 个步骤），实际执行中可能需要合并执行 - ScheduleRunInput 27 字段归属规则写得很详尽但尚属纸面方案，最终形态要到实施时才能确定 ## 遗漏检查 **已确认的遗漏（本轮新发现，已记录为结构化发现）：** 1. `web/ui_mode.py:_read_ui_mode_from_db` 的直接 `SystemConfigService(conn, ...)` 装配未在任务 2 或任务 8 显式声明 2. 静默异常门禁扫描范围应把 `web/ui_mode.py` 与 `web/bootstrap/` 一起纳入 3. F401 全局忽略移除前需先评估影响面 **未发现的重大遗漏：** - 问题覆盖矩阵（第七章）将 A1-E6 + 补充发现全部映射到任务，无无主项 - 固定边界（Win7 / Python 3.8 / Chrome109 / 数据库迁移链路）被明确标为接受风险 - 禁止项（4 大类 + 6 小项）覆盖了最常见的技术债务扩散模式 - 验收口径（第九章 5 条）可操作、可验证 ## 是否存在过度设计 **结论：不存在过度设计。** 所有新增结构（`web/routes/domains/`、`core/services/scheduler/<子包>/`、`web/pageflows/`、`data/queries/`、`core/infrastructure/data_repairs/`、`tests/<分层>/`）都有明确的职责边界和真实的代码迁入对象，不是空架子。plan 明确禁止了\"新总抽象\"\"新全局注册表\"\"第二套事实源\"等过度设计模式。",
      "evidence": [],
      "reviewedModules": [
        "plan 整体结构与 10 个任务"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-计划复杂度接近认知天花板但可接受",
        "F-maintainability-7",
        "F-结构决策简洁实用无过度设计"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-ui-mode-py-直接装配未纳入任务-2-收口范围",
      "severity": "medium",
      "category": "maintainability",
      "title": "ui_mode.py 直接装配未纳入任务 2 收口范围",
      "descriptionMarkdown": "web/ui_mode.py 第 221 行 `SystemConfigService(conn, ...)` 是一处直接装配，但任务 2 的搜索范围仅限 `web/routes/`。当请求级服务容器建立后，render_ui_template 执行时 g.services 已可用，该处应改为从容器取用或显式登记到治理台账。当前 plan 将 ui_mode.py 放在任务 8 治理，但未提及此处直接装配需同步处理或登记。",
      "recommendationMarkdown": "在任务 2 步骤 7 的残余装配清点中显式覆盖 `web/ui_mode.py`，或在任务 8 步骤 7.5 中明确声明此处需改为从 g.services 取用（如果请求上下文此时已具备条件）。",
      "evidence": [
        {
          "path": "web/ui_mode.py",
          "lineStart": 221,
          "lineEnd": 221,
          "symbol": "SystemConfigService(conn, ...)"
        },
        {
          "path": "web/ui_mode.py"
        }
      ],
      "relatedMilestoneIds": [
        "R2-logic-rigor"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-maintainability-2",
      "severity": "low",
      "category": "maintainability",
      "title": "CalendarService/ConfigService 延迟导入实际无循环依赖",
      "descriptionMarkdown": "plan 中任务 5 步骤 6 要求 \"明确延迟导入最终命运\"，但经代码验证，CalendarService (calendar_service.py) 和 ConfigService (config_service.py) 均未导入 schedule_service 或其模块间任何形成循环的路径。延迟导入纯属历史遗留防御性写法，不存在真实循环依赖。plan 对此留了一个开放决策点，但建议直接给出结论：应移至模块顶层。",
      "recommendationMarkdown": "在 plan 中补充明确结论：CalendarService / ConfigService 已无循环依赖，任务 5 应直接移至模块顶层导入，不留开放决策。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 259,
          "lineEnd": 260
        },
        {
          "path": "core/services/scheduler/calendar_service.py",
          "lineStart": 1,
          "lineEnd": 13
        },
        {
          "path": "core/services/scheduler/config_service.py",
          "lineStart": 1,
          "lineEnd": 15
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/calendar_service.py"
        },
        {
          "path": "core/services/scheduler/config_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "R2-logic-rigor"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-f401-全局忽略移除需前置评估影响面",
      "severity": "medium",
      "category": "maintainability",
      "title": "F401 全局忽略移除需前置评估影响面",
      "descriptionMarkdown": "pyproject.toml 第 31 行将 F401 列入全局 ignore 列表。plan 任务 3 步骤 8.2 要求 \"先移除全局 F401 忽略，再同步覆盖根层门面\"，但未要求在移除前先全量搜索评估影响面。ruff 移除全局 F401 后，所有未标注 `# noqa: F401` 的文件都会立即报错，可能远超根层门面范围。plan 应要求 \"移除前先执行一次 ruff check --select F401 并记录影响文件清单\"。",
      "recommendationMarkdown": "在任务 3 步骤 8.2 中增加前置步骤：先执行 `python -m ruff check --select F401` 记录当前影响文件清单，再按清单逐文件加内联 noqa 或 per-file-ignores，最后再移除全局忽略。",
      "evidence": [
        {
          "path": "pyproject.toml",
          "lineStart": 31,
          "lineEnd": 31
        },
        {
          "path": "pyproject.toml"
        }
      ],
      "relatedMilestoneIds": [
        "R2-logic-rigor"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-maintainability-4",
      "severity": "medium",
      "category": "maintainability",
      "title": "静默异常门禁扫描范围未覆盖 web/bootstrap/ 和 web/ui_mode.py",
      "descriptionMarkdown": "现有 test_no_silent_exception_swallow (test_architecture_fitness.py line 404) 的扫描范围由 CORE_DIRS 决定（web/routes, core/services, data/repositories, core/models, core/infrastructure, web/viewmodels），不包含 web/bootstrap/ 和 web/ui_mode.py。plan 任务 1 步骤 6 要求 \"把 web/bootstrap/ 补入扫描范围\"，但未显式提及 web/ui_mode.py。ui_mode.py 包含至少 15+ 处 except Exception 后静默回退（pass/return 空值/return 默认值），是当前仓库静默回退密度最高的单文件之一。",
      "recommendationMarkdown": "在任务 1 步骤 6 中把 web/ui_mode.py 显式纳入静默异常门禁扫描范围，与 web/bootstrap/ 同批登记白名单。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 21,
          "lineEnd": 22
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 1,
          "lineEnd": 421
        },
        {
          "path": "tests/test_architecture_fitness.py"
        },
        {
          "path": "web/ui_mode.py"
        }
      ],
      "relatedMilestoneIds": [
        "R2-logic-rigor"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-pre-commit-钩子使用裸-ruff-命令存在版本漂移",
      "severity": "low",
      "category": "maintainability",
      "title": "pre-commit 钩子使用裸 ruff 命令存在版本漂移",
      "descriptionMarkdown": "当前 .pre-commit-config.yaml 第 9 行直接调用 `ruff check --fix --exit-non-zero-on-fix`，使用 system PATH 中的 ruff。plan 正确识别了这个风险并要求改成 `python -m ruff`，但实际实施中需注意 pre-commit 的 language: system 模式下 python -m ruff 可能依赖当前 shell 环境的 python 版本。plan 应考虑在 entry 中使用与 scripts/run_quality_gate.py 一致的调用方式。",
      "recommendationMarkdown": "确保 .pre-commit-config.yaml 的 entry 与 scripts/run_quality_gate.py 使用完全一致的 ruff 调用方式和版本断言逻辑，避免本地钩子与门禁脚本产生不同结果。",
      "evidence": [
        {
          "path": ".pre-commit-config.yaml",
          "lineStart": 9,
          "lineEnd": 10
        },
        {
          "path": ".pre-commit-config.yaml"
        }
      ],
      "relatedMilestoneIds": [
        "R2-logic-rigor"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-计划复杂度接近认知天花板但可接受",
      "severity": "low",
      "category": "maintainability",
      "title": "计划复杂度接近认知天花板但可接受",
      "descriptionMarkdown": "plan 总共 10 个任务，56 条已吸收修正、十多万字，复杂度已经接近实施执行人的认知天花板。部分任务的步骤拆分粒度过细（如任务 1 有7 个主步骤 + 3 个半步骤、任务 3 有11 个主步骤），实际执行时很难严格按顺序来。但从治理角度看，这种粒度确实减少了歧义空间，属于“宁偶不缺”的实践，是可接受的代价。",
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R3-overall-assessment"
      ],
      "trackingStatus": "accepted_risk"
    },
    {
      "id": "F-maintainability-7",
      "severity": "low",
      "category": "maintainability",
      "title": "ScheduleRunInput 字段归属尚不确定但 plan 已尽力明确",
      "descriptionMarkdown": "plan 任务 5 步骤 3.5 定义了 ScheduleRunInput 27 字段归属规则，但当前 run_command.py 、run_context.py 和 ScheduleOrchestrationOutcome 均为待建文件，字段模型的最终形态要到实施时才能确定。plan 写得足够详细以指导实施，但字段归属规则不宜被视为最终形态，应允许在实施时根据实测微调。",
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R3-overall-assessment"
      ],
      "trackingStatus": "accepted_risk"
    },
    {
      "id": "F-结构决策简洁实用无过度设计",
      "severity": "low",
      "category": "maintainability",
      "title": "结构决策简洁实用无过度设计",
      "descriptionMarkdown": "plan 对 web/routes/domains/ 采用“非同名子包”策略避免 scheduler.py 与 scheduler/ 同名冲突，是简洁而正确的决策。调度服务采用子包化且根层只保留门面的做法也合理。number_utils.py 保留在根层共享位置而非强移入 config/ 子包，符合实际跨包依赖现状。前端采用 DOM 协议而非新全局注册表，也是克制的好决策。整体结构决策简洁实用，未发现过度设计。",
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R3-overall-assessment"
      ],
      "trackingStatus": "accepted_risk"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:e96f198f6dc77da91549f383b288e0bc58f65082329ea3a08229dd1d06c23543",
    "generatedAt": "2026-04-06T07:40:07.699Z",
    "locale": "zh-CN"
  }
}
```

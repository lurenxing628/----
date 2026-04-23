# plan-05 后续结构债治理与文档同步 三轮深度审查
- 日期: 2026-04-04
- 概述: 对 05_后续结构债治理与文档同步.plan.md 进行事实核验、结构评估与交叉审查三轮审查
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# plan-05 后续结构债治理与文档同步 三轮深度审查

**审查日期**: 2026-04-01
**审查对象**: `.limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md`

## 审查策略

- **第一轮（事实核验）**：逐项核实 plan 中声称的行数、复杂度、文件存在性、引用链等事实基线
- **第二轮（结构评估）**：评估批次划分合理性、依赖关系、风险点、完成标准可操作性
- **第三轮（交叉审查）**：与已有 review、阶段 04 成果、架构适应度门禁做交叉比对，查找遗漏与矛盾

## 评审摘要

- 当前状态: 已完成
- 已审模块: schedule_summary.py 事实基线, batch_service.py 事实基线, schedule_service.py 事实基线, test_architecture_fitness.py 账本现状, 批次A架构, 批次B拆分可行性, 批次C拆分可行性, 批次D文档流程, 兼容边界完备性, 回归清单覆盖, 历史review关闭状态, plan revision声称与实际对比, 跨批次一致性
- 当前进度: 已记录 3 个里程碑；最新：R3-cross-check
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 9
- 问题严重级别分布: 高 0 / 中 1 / 低 8
- 最新结论: ## 综合审查结论 ### 总判定：有条件通过（先修 3 处再执行） 本 plan 相比初版已有显著改善——前两轮 review 提出的 9 项发现中有 7 项被有效修复，治理方向正确，约束条款完备，回归覆盖大幅增强。但经定量分析，仍有 3 处必须修正后才能安全执行： ### 必须修正项（阻塞执行） | # | 问题 | 修正要求 | |---|------|---------| | 1 | **行数基线过时**：plan 声称 schedule_summary.py 为 922 行，实际为 **957 行**；build_result_summary 位置为 717-955 行而非 688-921 行 | 更新 plan 中所有行数与行号引用为实际值 | | 2 | **批次 B 第二段几乎必然需要**：第一段迁出 ~352 行后仍剩 ~605 行，远超 500 行门禁；plan 不应将第二段描述为条件分支 | 将批次 B 改为"两段均为必做"；补充定量估算（第一段 ~605 行 → 第二段 ~423 行） | | 3 | **批次 C 迁移清单不完整**：仅迁 _probe + _ensure (~56 行) 后仍剩 ~508 行；需追加迁出 _invoke_template_resolver 与 _default_template_resolver (~36 行) | 在批次 C 第一段步骤中补上这两个依赖方法，或说明保留在 BatchService 中通过 svc 参数回调的方案 | ### 建议改善项（不阻塞但强烈推荐） 1. **复杂度基线预跑**：在批次 B/C 开始前先跑一次 radon 测量并记录输出，避免依赖 known_violations 中可能过时的声称值 2. **build_result_summary 复杂度备案方向**：补充一段说明——若两段拆分后该函数复杂度仍远超 15，下一步可考虑将 warning 流水线拼装、algo_dict 拼装、metrics 装配等分段包装为带明确入参的构造函数 3. **批次 B/C 可并行**：二者分别针对 schedule_summary.py 和 batch_service.py，无强依赖关系，可在批次 A 完成后并行推进 ### 整体优点总结 1. 治理方向从"一次到位"收敛为"先拆最稳定边界、再按测量决定"，符合低风险迭代原则 2. 禁止静默回退、禁止调整门禁口径、禁止泛化文件命名三道防线完备可检查 3. 必跑回归从 ~6 组增加到 ~17 组，覆盖排产摘要链与批次 Excel 导入链的核心合同 4. 12 条兼容边界声明每条都对应到具体代码位置或回归测试 5. "不达标则暂停 → 新 review → 新 plan"的出口设计合理，不虚假承诺 6. 前两轮 review 的 9 项发现中 7 项已有效修复
- 下一步建议: 修正 plan 中的 3 处必修项后即可开始执行批次 A
- 总体结论: 有条件通过

## 评审发现

### schedule_summary.py 行数声称与实际不符

- ID: F01
- 严重级别: 中
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R1-fact-check
- 说明:

  plan 声称 schedule_summary.py 当前 922 行，实际为 957 行，偏差 35 行。build_result_summary() 位置也相应偏移（声称 688-921，实际 717-955）。这使得批次 B 第一段拆分后能否降到 500 行以下更加不确定，可能直接影响是否需要进入第二段拆分的判断基线。
- 建议:

  修正 plan 中的行数与行号为最新实际值；同时重新评估第一段拆分是否足以把文件降到 500 行以下。
- 证据:
  - `core/services/scheduler/schedule_summary.py:717-955`
  - `core/services/scheduler/schedule_summary.py`

### 复杂度声称值未独立核验

- ID: F02
- 严重级别: 低
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: R1-fact-check
- 说明:

  plan 声称 build_result_summary 复杂度=57、_freeze_meta_dict=17、_summary_degradation_state=19、update=17，这些数值均来自 known_violations 登记，但 plan 未提供核验命令或核验输出。若实际复杂度已因阶段04后续小改而变化，拆分策略可能需要调整。
- 建议:

  在批次 B/C 开始前，先跑一次 radon 测量并记录输出作为执行前基线。

### [高] 批次B第一段拆分必然不足以达标：冻结+退化共~352行迁出后仍剩~605行，远超500行门禁

- ID: F-other-3
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2-structural-eval

### [高] 批次C迁移清单不足以达到500行门禁：仅迁_probe+_ensure共~56行后仍剩~508行，需补上_invoke_template_resolver与_default_template_resolver

- ID: F-other-4
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2-structural-eval

### [中] 两段式策略缺少定量预测：plan应预先给出第一段~605行、第二段~425行的估算

- ID: F-other-5
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2-structural-eval

### [中] build_result_summary复杂度降幅预期不足：即使辅助函数全部外提，函数内仍有12-15个if分支

- ID: F-other-6
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2-structural-eval

### [低] 批次B/C不存在强依赖但被线性排列

- ID: F-低-批次b-c不存在强依赖但被线性排列
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R2-structural-eval

### [高] plan已经回应了前两轮review的大部分发现，但行数基线仍未修正，导致‘第一段拆分不够’这一核心问题被掩盖

- ID: F-other-8
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R3-cross-check

### [中] 批次C的依赖方法迁移缺失是前轮review未充分强调的新问题

- ID: F-中-批次c的依赖方法迁移缺失是前轮review未充分强调的新问题
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: R3-cross-check

## 评审里程碑

### R1-fact-check · 第一轮：事实核验

- 状态: 已完成
- 记录时间: 2026-04-04T17:02:10.409Z
- 已审模块: schedule_summary.py 事实基线, batch_service.py 事实基线, schedule_service.py 事实基线, test_architecture_fitness.py 账本现状
- 摘要:

  逐项核实 plan 中声称的行数、函数位置、复杂度登记、引用链、文件存在性等事实基线。

  ### 核验结果总表

  | 声明项 | plan 声称 | 实际值 | 判定 |
  |--------|----------|--------|------|
  | `schedule_summary.py` 总行数 | 922 行 | **957 行** | ❌ 偏差 35 行 |
  | `build_result_summary()` 位置 | 688-921 行 | **717-955 行** | ❌ 偏移约 30 行 |
  | `build_result_summary()` 复杂度 | 57 | 未独立测量，但 `known_violations` 中确实登记 | ⚠️ 待核验 |
  | `_freeze_meta_dict` 复杂度 | 17 | 函数位于 395-429 行（35 行）；`known_violations` 中登记存在 | ⚠️ 待核验 |
  | `_summary_degradation_state` 复杂度 | 19 | 函数位于 512-602 行（90 行）；`known_violations` 中登记存在 | ⚠️ 待核验 |
  | `schedule_service.py` 总行数 | 397 行 | **398 行** | ✅ 基本正确 |
  | `_run_schedule_impl` 复杂度 | 2 | 函数 298-396 行，已是薄编排；`known_violations` 中仍登记 | ✅ 高度可信为陈旧项 |
  | `_get_template_and_group_for_op` 复杂度 | 1 | 仅 2 行薄转调（189-190），确认为陈旧项 | ✅ 确认 |
  | `batch_service.py` 总行数 | 563 行 | **564 行** | ✅ 基本正确 |
  | `update()` 位置 | 330-409 行 | 330-409 行 | ✅ 一致 |
  | `_probe_template_ops_readonly()` 仍在 BatchService | 是 | 159-166 行仍在 `batch_service.py` | ✅ 确认 |
  | `_ensure_template_ops_in_tx()` 仍在 BatchService | 是 | 168-215 行仍在 `batch_service.py` | ✅ 确认 |
  | `create_batch_from_template_no_tx()` 已是薄转调 | 是 | 528-555 行已委托给 `batch_template_ops` | ✅ 确认 |
  | `_known_oversize_files()` 9 项 | 是 | 9 项（47-55 行） | ✅ 确认 |
  | `schedule_service.py` 不在 oversize 登记中 | 是 | 确认不在 | ✅ 确认 |
  | `_build_overdue_items` 被测试/审计直接引用 | 是 | 两处确认（回归测试 + 审计探针） | ✅ 确认 |
  | `orchestrate_schedule_run` 以关键字参数调用 `build_result_summary` | 是 | 确认 147-178 行关键字调用 + 五元组解构 | ✅ 确认 |
  | `batch_template_ops.py` 已存在 | 隐含提及 | 存在，含 `create_batch_from_template_no_tx` 等 3 个公共函数 | ✅ 确认 |

  ### 关键偏差

  1. **`schedule_summary.py` 行数偏差 35 行（922→957）**：plan 后续批次 B 的拆分策略以 500 行门禁为目标，多出 35 行意味着实际需要迁出的代码量比 plan 估算更多。第一段拆完后能否降到 500 行以下更加不确定。
  2. **`build_result_summary()` 行号偏移约 30 行**：影响批次 B 步骤 3 中函数定位；虽然不影响逻辑正确性，但说明 plan 编写时基线已过时。
  3. **复杂度数值均为声称值**：plan 中三个关键复杂度数值（57/17/19）未能独立核验，但均出现在 `known_violations` 登记中，可信度中等。
- 结论:

  逐项核实 plan 中声称的行数、函数位置、复杂度登记、引用链、文件存在性等事实基线。 ### 核验结果总表 | 声明项 | plan 声称 | 实际值 | 判定 | |--------|----------|--------|------| | `schedule_summary.py` 总行数 | 922 行 | **957 行** | ❌ 偏差 35 行 | | `build_result_summary()` 位置 | 688-921 行 | **717-955 行** | ❌ 偏移约 30 行 | | `build_result_summary()` 复杂度 | 57 | 未独立测量，但 `known_violations` 中确实登记 | ⚠️ 待核验 | | `_freeze_meta_dict` 复杂度 | 17 | 函数位于 395-429 行（35 行）；`known_violations` 中登记存在 | ⚠️ 待核验 | | `_summary_degradation_state` 复杂度 | 19 | 函数位于 512-602 行（90 行）；`known_violations` 中登记存在 | ⚠️ 待核验 | | `schedule_service.py` 总行数 | 397 行 | **398 行** | ✅ 基本正确 | | `_run_schedule_impl` 复杂度 | 2 | 函数 298-396 行，已是薄编排；`known_violations` 中仍登记 | ✅ 高度可信为陈旧项 | | `_get_template_and_group_for_op` 复杂度 | 1 | 仅 2 行薄转调（189-190），确认为陈旧项 | ✅ 确认 | | `batch_service.py` 总行数 | 563 行 | **564 行** | ✅ 基本正确 | | `update()` 位置 | 330-409 行 | 330-409 行 | ✅ 一致 | | `_probe_template_ops_readonly()` 仍在 BatchService | 是 | 159-166 行仍在 `batch_service.py` | ✅ 确认 | | `_ensure_template_ops_in_tx()` 仍在 BatchService | 是 | 168-215 行仍在 `batch_service.py` | ✅ 确认 | | `create_batch_from_template_no_tx()` 已是薄转调 | 是 | 528-555 行已委托给 `batch_template_ops` | ✅ 确认 | | `_known_oversize_files()` 9 项 | 是 | 9 项（47-55 行） | ✅ 确认 | | `schedule_service.py` 不在 oversize 登记中 | 是 | 确认不在 | ✅ 确认 | | `_build_overdue_items` 被测试/审计直接引用 | 是 | 两处确认（回归测试 + 审计探针） | ✅ 确认 | | `orchestrate_schedule_run` 以关键字参数调用 `build_result_summary` | 是 | 确认 147-178 行关键字调用 + 五元组解构 | ✅ 确认 | | `batch_template_ops.py` 已存在 | 隐含提及 | 存在，含 `create_batch_from_template_no_tx` 等 3 个公共函数 | ✅ 确认 | ### 关键偏差 1. **`schedule_summary.py` 行数偏差 35 行（922→957）**：plan 后续批次 B 的拆分策略以 500 行门禁为目标，多出 35 行意味着实际需要迁出的代码量比 plan 估算更多。第一段拆完后能否降到 500 行以下更加不确定。 2. **`build_result_summary()` 行号偏移约 30 行**：影响批次 B 步骤 3 中函数定位；虽然不影响逻辑正确性，但说明 plan 编写时基线已过时。 3. **复杂度数值均为声称值**：plan 中三个关键复杂度数值（57/17/19）未能独立核验，但均出现在 `known_violations` 登记中，可信度中等。
- 证据:
  - `tests/test_architecture_fitness.py:43-56#_known_oversize_files`
  - `tests/test_architecture_fitness.py:603-694#known_violations in test_cyclomatic_complexity_threshold`
  - `core/services/scheduler/schedule_summary.py:717-955#build_result_summary`
  - `core/services/scheduler/batch_service.py:528-555#create_batch_from_template_no_tx`
  - `core/services/scheduler/schedule_orchestrator.py:147-178`
- 问题:
  - [中] 文档: schedule_summary.py 行数声称与实际不符
  - [低] 文档: 复杂度声称值未独立核验

### R2-structural-eval · 第二轮：结构评估（批次划分、可行性、风险与完备性）

- 状态: 已完成
- 记录时间: 2026-04-04T17:03:37.431Z
- 已审模块: 批次A架构, 批次B拆分可行性, 批次C拆分可行性, 批次D文档流程, 兼容边界完备性, 回归清单覆盖
- 摘要:

  ### 结构评估总览

  #### 1. 批次划分合理性

  | 批次 | 评估 | 要点 |
  |-----|------|------|
  | A（账本陈旧项清理） | ✅ 合理 | 风险最低、依赖最少，适合首批 |
  | B（schedule_summary 拆分） | ⚠️ 策略正确但估算不充分 | 两段式方向对了，但缺少定量预测；第一段必然不够 |
  | C（batch_service 收口） | ⚠️ 迁移清单不完整 | 仅移 _probe + _ensure 不够减到 500 行；遗漏依赖方法 |
  | D（文档收口） | ✅ 合理 | 流程清晰 |

  #### 2. 定量可行性分析

  **批次 B（schedule_summary.py，实际 957 行）：**
  - 第一段迁出冻结（~69行）+ 退化（~283行）≈ 352 行 → 剩余 ~605 行 → ❌ 超标
  - 第二段迁出装配辅助（~182行）→ 剩余 ~423 行 → ✅ 达标
  - 结论：**两段都必须做**，plan 不应把第二段描述为"仅在第一段后仍未达标时"的条件分支

  **批次 C（batch_service.py，实际 564 行）：**
  - 仅迁 _probe + _ensure（~56行）→ 剩余 ~508 行 → ❌ 超标
  - 追加迁出 _invoke_template_resolver + _default_template_resolver（~36行）→ 剩余 ~472 行 → ✅ 达标
  - 结论：**迁移清单不完整**，需要补上依赖方法

  #### 3. 兼容边界评估

  12 条兼容边界声明均合理且具备可操作性。`build_result_summary` 五元组合同、`result_summary` 字段路径、批次 Excel 三条核心语义均有独立回归守护。

  #### 4. 回归清单覆盖评估

  对比上一版 review 的发现，当前版本已补齐大部分遗漏的回归用例，覆盖率显著改善。

  #### 5. 约束条款评估

  "禁止静默回退 / 广义异常兜底 / 泛化杂物间文件"三条约束具有明确可检查性。"本 plan 内不得调整门禁口径"的兜底约束避免了"接受现状"风险。
- 结论:

  ### 结构评估总览 #### 1. 批次划分合理性 | 批次 | 评估 | 要点 | |-----|------|------| | A（账本陈旧项清理） | ✅ 合理 | 风险最低、依赖最少，适合首批 | | B（schedule_summary 拆分） | ⚠️ 策略正确但估算不充分 | 两段式方向对了，但缺少定量预测；第一段必然不够 | | C（batch_service 收口） | ⚠️ 迁移清单不完整 | 仅移 _probe + _ensure 不够减到 500 行；遗漏依赖方法 | | D（文档收口） | ✅ 合理 | 流程清晰 | #### 2. 定量可行性分析 **批次 B（schedule_summary.py，实际 957 行）：** - 第一段迁出冻结（~69行）+ 退化（~283行）≈ 352 行 → 剩余 ~605 行 → ❌ 超标 - 第二段迁出装配辅助（~182行）→ 剩余 ~423 行 → ✅ 达标 - 结论：**两段都必须做**，plan 不应把第二段描述为"仅在第一段后仍未达标时"的条件分支 **批次 C（batch_service.py，实际 564 行）：** - 仅迁 _probe + _ensure（~56行）→ 剩余 ~508 行 → ❌ 超标 - 追加迁出 _invoke_template_resolver + _default_template_resolver（~36行）→ 剩余 ~472 行 → ✅ 达标 - 结论：**迁移清单不完整**，需要补上依赖方法 #### 3. 兼容边界评估 12 条兼容边界声明均合理且具备可操作性。`build_result_summary` 五元组合同、`result_summary` 字段路径、批次 Excel 三条核心语义均有独立回归守护。 #### 4. 回归清单覆盖评估 对比上一版 review 的发现，当前版本已补齐大部分遗漏的回归用例，覆盖率显著改善。 #### 5. 约束条款评估 "禁止静默回退 / 广义异常兜底 / 泛化杂物间文件"三条约束具有明确可检查性。"本 plan 内不得调整门禁口径"的兜底约束避免了"接受现状"风险。
- 问题:
  - [低] 其他: [高] 批次B第一段拆分必然不足以达标：冻结+退化共~352行迁出后仍剩~605行，远超500行门禁
  - [低] 其他: [高] 批次C迁移清单不足以达到500行门禁：仅迁_probe+_ensure共~56行后仍剩~508行，需补上_invoke_template_resolver与_default_template_resolver
  - [低] 其他: [中] 两段式策略缺少定量预测：plan应预先给出第一段~605行、第二段~425行的估算
  - [低] 其他: [中] build_result_summary复杂度降幅预期不足：即使辅助函数全部外提，函数内仍有12-15个if分支
  - [低] 其他: [低] 批次B/C不存在强依赖但被线性排列

### R3-cross-check · 第三轮：交叉审查（与已有 review 及代码现状交叉比对）

- 状态: 已完成
- 记录时间: 2026-04-04T17:04:02.135Z
- 已审模块: 历史review关闭状态, plan revision声称与实际对比, 跨批次一致性
- 摘要:

  ### 与已有 review 的交叉比对

  #### 前两轮 review 发现的关闭状态追踪

  | 序号 | 前轮发现 | 当前 plan 是否修复 | 本轮评估 |
  |-----|---------|------------------|---------|
  | 1 | 超长文件数量 10→9 不一致 | ✅ plan 已修正为 9 | 确认修复 |
  | 2 | 批次 B 行数目标不可达 | ⚠️ plan 改为两段式 | 方向正确，但行数基线仍错（922→957），第一段注定不够的事实未体现 |
  | 3 | build_result_summary 复杂度不可能降到 ≤15 | ✅ plan 改为"不达标则暂停" | 风险下行策略正确 |
  | 4 | create_batch_from_template_no_tx 白名单已失效 | ✅ plan 移到批次 A 清理 | 确认修复 |
  | 5 | 批次 C 行数余量过小 | ⚠️ plan 新增 _probe + _ensure 迁移 | 仍不够：需补上 _invoke_template_resolver 与 _default_template_resolver |
  | 6 | 批次 A 与基线脱节 | ✅ plan 重写为"全量清理陈旧项" | 确认修复 |
  | 7 | 回归清单遗漏 summary 合同用例 | ✅ plan 已补齐 6 组回归 | 确认修复 |
  | 8 | batch_excel_import.py 未纳入范围 | ✅ plan 已加入批次 C 文件清单 | 确认修复 |
  | 9 | 批次 C 误把陈旧白名单项当热点 | ✅ plan 改为批次 A 中清理 | 确认修复 |

  #### 本轮新发现 vs 前轮遗留

  - **行数基线错误**（F01）：前轮 review-1 指出"922 行，移出 215 行后仍有 707 行"；前轮 review-2 指出"923 行"。但**实际**文件已有 **957 行**——三个数值都不一致，说明基线在不断漂移而 plan 没有及时刷新。当前 plan 使用的 922 仍是过时数字。
  - **批次 C 依赖方法遗漏**（F04）：前轮 review-1 建议"一并迁移 _probe + _ensure"，plan 采纳了但没有深究 _ensure_template_ops_in_tx 的内部依赖链（调用 _invoke_template_resolver → _default_template_resolver），导致仅迁 _probe + _ensure 后仍差 8 行不达标。
  - **build_result_summary 复杂度预期**（F06）：前轮 review-1 建议将复杂度目标从"≤15"降为"≤30"；当前 plan 选择了更激进的策略——"不达标则暂停"。这个策略虽然没有虚假承诺，但也意味着执行者可能在两段拆分都完成后仍然发现 build_result_summary 复杂度远高于 15，然后被迫暂停并开新一轮。plan 应至少给出备案方向提示。

  #### plan 修订要点的核实

  plan 声称做了 5 项收敛调整，逐条核实：

  1. ✅ 不再预设 schedule_summary_payload.py → 确认：步骤中无此文件名
  2. ✅ 不再预设 batch_update_support.py → 确认：改为"仅在需要时新增 batch_write_rules.py"
  3. ✅ 删除"接受当前水平"口子 → 确认：步骤 11 明确"必须暂停并开新 review"
  4. ✅ 新增静默回退禁令 → 确认：统一执行节奏第 5 条
  5. ✅ 补上 _build_overdue_items 兼容策略 → 确认：步骤 9 与兼容边界第 11 条

  ### plan 整体优点

  1. **治理方向正确**：从"一次到位"收敛为"先拆最稳定边界、再按测量决定"，符合低风险迭代原则
  2. **约束条款完备**：禁止静默回退、禁止调整门禁口径、禁止泛化文件命名，形成三道防线
  3. **回归覆盖显著改善**：相比初版，必跑回归已从 ~6 组增加到 ~17 组
  4. **兼容边界声明具体可检查**：12 条声明中每条都能对应到具体的代码位置或回归测试
  5. **暂停机制设计合理**：不虚假承诺能达标，而是预留"暂停→新 review→新 plan"的出口

  ### plan 仍存在的主要风险

  1. **行数基线过时**：957 行的实际值未反映在 plan 中，可能导致执行者对工作量产生误判
  2. **两段式拆分几乎必然都要做**：plan 的条件分支描述暗示第二段"可能不需要"，但定量分析显示它几乎是必须的
  3. **批次 C 迁移清单不完整**：遗漏 _invoke_template_resolver 和 _default_template_resolver 两个依赖方法
  4. **build_result_summary 复杂度**：即使两段拆分都完成，该函数复杂度很可能仍远超 15，暂停出口的概率较高
- 结论:

  ### 与已有 review 的交叉比对 #### 前两轮 review 发现的关闭状态追踪 | 序号 | 前轮发现 | 当前 plan 是否修复 | 本轮评估 | |-----|---------|------------------|---------| | 1 | 超长文件数量 10→9 不一致 | ✅ plan 已修正为 9 | 确认修复 | | 2 | 批次 B 行数目标不可达 | ⚠️ plan 改为两段式 | 方向正确，但行数基线仍错（922→957），第一段注定不够的事实未体现 | | 3 | build_result_summary 复杂度不可能降到 ≤15 | ✅ plan 改为"不达标则暂停" | 风险下行策略正确 | | 4 | create_batch_from_template_no_tx 白名单已失效 | ✅ plan 移到批次 A 清理 | 确认修复 | | 5 | 批次 C 行数余量过小 | ⚠️ plan 新增 _probe + _ensure 迁移 | 仍不够：需补上 _invoke_template_resolver 与 _default_template_resolver | | 6 | 批次 A 与基线脱节 | ✅ plan 重写为"全量清理陈旧项" | 确认修复 | | 7 | 回归清单遗漏 summary 合同用例 | ✅ plan 已补齐 6 组回归 | 确认修复 | | 8 | batch_excel_import.py 未纳入范围 | ✅ plan 已加入批次 C 文件清单 | 确认修复 | | 9 | 批次 C 误把陈旧白名单项当热点 | ✅ plan 改为批次 A 中清理 | 确认修复 | #### 本轮新发现 vs 前轮遗留 - **行数基线错误**（F01）：前轮 review-1 指出"922 行，移出 215 行后仍有 707 行"；前轮 review-2 指出"923 行"。但**实际**文件已有 **957 行**——三个数值都不一致，说明基线在不断漂移而 plan 没有及时刷新。当前 plan 使用的 922 仍是过时数字。 - **批次 C 依赖方法遗漏**（F04）：前轮 review-1 建议"一并迁移 _probe + _ensure"，plan 采纳了但没有深究 _ensure_template_ops_in_tx 的内部依赖链（调用 _invoke_template_resolver → _default_template_resolver），导致仅迁 _probe + _ensure 后仍差 8 行不达标。 - **build_result_summary 复杂度预期**（F06）：前轮 review-1 建议将复杂度目标从"≤15"降为"≤30"；当前 plan 选择了更激进的策略——"不达标则暂停"。这个策略虽然没有虚假承诺，但也意味着执行者可能在两段拆分都完成后仍然发现 build_result_summary 复杂度远高于 15，然后被迫暂停并开新一轮。plan 应至少给出备案方向提示。 #### plan 修订要点的核实 plan 声称做了 5 项收敛调整，逐条核实： 1. ✅ 不再预设 schedule_summary_payload.py → 确认：步骤中无此文件名 2. ✅ 不再预设 batch_update_support.py → 确认：改为"仅在需要时新增 batch_write_rules.py" 3. ✅ 删除"接受当前水平"口子 → 确认：步骤 11 明确"必须暂停并开新 review" 4. ✅ 新增静默回退禁令 → 确认：统一执行节奏第 5 条 5. ✅ 补上 _build_overdue_items 兼容策略 → 确认：步骤 9 与兼容边界第 11 条 ### plan 整体优点 1. **治理方向正确**：从"一次到位"收敛为"先拆最稳定边界、再按测量决定"，符合低风险迭代原则 2. **约束条款完备**：禁止静默回退、禁止调整门禁口径、禁止泛化文件命名，形成三道防线 3. **回归覆盖显著改善**：相比初版，必跑回归已从 ~6 组增加到 ~17 组 4. **兼容边界声明具体可检查**：12 条声明中每条都能对应到具体的代码位置或回归测试 5. **暂停机制设计合理**：不虚假承诺能达标，而是预留"暂停→新 review→新 plan"的出口 ### plan 仍存在的主要风险 1. **行数基线过时**：957 行的实际值未反映在 plan 中，可能导致执行者对工作量产生误判 2. **两段式拆分几乎必然都要做**：plan 的条件分支描述暗示第二段"可能不需要"，但定量分析显示它几乎是必须的 3. **批次 C 迁移清单不完整**：遗漏 _invoke_template_resolver 和 _default_template_resolver 两个依赖方法 4. **build_result_summary 复杂度**：即使两段拆分都完成，该函数复杂度很可能仍远超 15，暂停出口的概率较高
- 问题:
  - [低] 其他: [高] plan已经回应了前两轮review的大部分发现，但行数基线仍未修正，导致‘第一段拆分不够’这一核心问题被掩盖
  - [低] 其他: [中] 批次C的依赖方法迁移缺失是前轮review未充分强调的新问题

## 最终结论

## 综合审查结论

### 总判定：有条件通过（先修 3 处再执行）

本 plan 相比初版已有显著改善——前两轮 review 提出的 9 项发现中有 7 项被有效修复，治理方向正确，约束条款完备，回归覆盖大幅增强。但经定量分析，仍有 3 处必须修正后才能安全执行：

### 必须修正项（阻塞执行）

| # | 问题 | 修正要求 |
|---|------|---------|
| 1 | **行数基线过时**：plan 声称 schedule_summary.py 为 922 行，实际为 **957 行**；build_result_summary 位置为 717-955 行而非 688-921 行 | 更新 plan 中所有行数与行号引用为实际值 |
| 2 | **批次 B 第二段几乎必然需要**：第一段迁出 ~352 行后仍剩 ~605 行，远超 500 行门禁；plan 不应将第二段描述为条件分支 | 将批次 B 改为"两段均为必做"；补充定量估算（第一段 ~605 行 → 第二段 ~423 行） |
| 3 | **批次 C 迁移清单不完整**：仅迁 _probe + _ensure (~56 行) 后仍剩 ~508 行；需追加迁出 _invoke_template_resolver 与 _default_template_resolver (~36 行) | 在批次 C 第一段步骤中补上这两个依赖方法，或说明保留在 BatchService 中通过 svc 参数回调的方案 |

### 建议改善项（不阻塞但强烈推荐）

1. **复杂度基线预跑**：在批次 B/C 开始前先跑一次 radon 测量并记录输出，避免依赖 known_violations 中可能过时的声称值
2. **build_result_summary 复杂度备案方向**：补充一段说明——若两段拆分后该函数复杂度仍远超 15，下一步可考虑将 warning 流水线拼装、algo_dict 拼装、metrics 装配等分段包装为带明确入参的构造函数
3. **批次 B/C 可并行**：二者分别针对 schedule_summary.py 和 batch_service.py，无强依赖关系，可在批次 A 完成后并行推进

### 整体优点总结

1. 治理方向从"一次到位"收敛为"先拆最稳定边界、再按测量决定"，符合低风险迭代原则
2. 禁止静默回退、禁止调整门禁口径、禁止泛化文件命名三道防线完备可检查
3. 必跑回归从 ~6 组增加到 ~17 组，覆盖排产摘要链与批次 Excel 导入链的核心合同
4. 12 条兼容边界声明每条都对应到具体代码位置或回归测试
5. "不达标则暂停 → 新 review → 新 plan"的出口设计合理，不虚假承诺
6. 前两轮 review 的 9 项发现中 7 项已有效修复

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnkkxihx-mktmh1",
  "createdAt": "2026-04-04T00:00:00.000Z",
  "updatedAt": "2026-04-04T17:04:16.174Z",
  "finalizedAt": "2026-04-04T17:04:16.174Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "plan-05 后续结构债治理与文档同步 三轮深度审查",
    "date": "2026-04-04",
    "overview": "对 05_后续结构债治理与文档同步.plan.md 进行事实核验、结构评估与交叉审查三轮审查"
  },
  "scope": {
    "markdown": "# plan-05 后续结构债治理与文档同步 三轮深度审查\n\n**审查日期**: 2026-04-01\n**审查对象**: `.limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md`\n\n## 审查策略\n\n- **第一轮（事实核验）**：逐项核实 plan 中声称的行数、复杂度、文件存在性、引用链等事实基线\n- **第二轮（结构评估）**：评估批次划分合理性、依赖关系、风险点、完成标准可操作性\n- **第三轮（交叉审查）**：与已有 review、阶段 04 成果、架构适应度门禁做交叉比对，查找遗漏与矛盾"
  },
  "summary": {
    "latestConclusion": "## 综合审查结论\n\n### 总判定：有条件通过（先修 3 处再执行）\n\n本 plan 相比初版已有显著改善——前两轮 review 提出的 9 项发现中有 7 项被有效修复，治理方向正确，约束条款完备，回归覆盖大幅增强。但经定量分析，仍有 3 处必须修正后才能安全执行：\n\n### 必须修正项（阻塞执行）\n\n| # | 问题 | 修正要求 |\n|---|------|---------|\n| 1 | **行数基线过时**：plan 声称 schedule_summary.py 为 922 行，实际为 **957 行**；build_result_summary 位置为 717-955 行而非 688-921 行 | 更新 plan 中所有行数与行号引用为实际值 |\n| 2 | **批次 B 第二段几乎必然需要**：第一段迁出 ~352 行后仍剩 ~605 行，远超 500 行门禁；plan 不应将第二段描述为条件分支 | 将批次 B 改为\"两段均为必做\"；补充定量估算（第一段 ~605 行 → 第二段 ~423 行） |\n| 3 | **批次 C 迁移清单不完整**：仅迁 _probe + _ensure (~56 行) 后仍剩 ~508 行；需追加迁出 _invoke_template_resolver 与 _default_template_resolver (~36 行) | 在批次 C 第一段步骤中补上这两个依赖方法，或说明保留在 BatchService 中通过 svc 参数回调的方案 |\n\n### 建议改善项（不阻塞但强烈推荐）\n\n1. **复杂度基线预跑**：在批次 B/C 开始前先跑一次 radon 测量并记录输出，避免依赖 known_violations 中可能过时的声称值\n2. **build_result_summary 复杂度备案方向**：补充一段说明——若两段拆分后该函数复杂度仍远超 15，下一步可考虑将 warning 流水线拼装、algo_dict 拼装、metrics 装配等分段包装为带明确入参的构造函数\n3. **批次 B/C 可并行**：二者分别针对 schedule_summary.py 和 batch_service.py，无强依赖关系，可在批次 A 完成后并行推进\n\n### 整体优点总结\n\n1. 治理方向从\"一次到位\"收敛为\"先拆最稳定边界、再按测量决定\"，符合低风险迭代原则\n2. 禁止静默回退、禁止调整门禁口径、禁止泛化文件命名三道防线完备可检查\n3. 必跑回归从 ~6 组增加到 ~17 组，覆盖排产摘要链与批次 Excel 导入链的核心合同\n4. 12 条兼容边界声明每条都对应到具体代码位置或回归测试\n5. \"不达标则暂停 → 新 review → 新 plan\"的出口设计合理，不虚假承诺\n6. 前两轮 review 的 9 项发现中 7 项已有效修复",
    "recommendedNextAction": "修正 plan 中的 3 处必修项后即可开始执行批次 A",
    "reviewedModules": [
      "schedule_summary.py 事实基线",
      "batch_service.py 事实基线",
      "schedule_service.py 事实基线",
      "test_architecture_fitness.py 账本现状",
      "批次A架构",
      "批次B拆分可行性",
      "批次C拆分可行性",
      "批次D文档流程",
      "兼容边界完备性",
      "回归清单覆盖",
      "历史review关闭状态",
      "plan revision声称与实际对比",
      "跨批次一致性"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 9,
    "severity": {
      "high": 0,
      "medium": 1,
      "low": 8
    }
  },
  "milestones": [
    {
      "id": "R1-fact-check",
      "title": "第一轮：事实核验",
      "status": "completed",
      "recordedAt": "2026-04-04T17:02:10.409Z",
      "summaryMarkdown": "逐项核实 plan 中声称的行数、函数位置、复杂度登记、引用链、文件存在性等事实基线。\n\n### 核验结果总表\n\n| 声明项 | plan 声称 | 实际值 | 判定 |\n|--------|----------|--------|------|\n| `schedule_summary.py` 总行数 | 922 行 | **957 行** | ❌ 偏差 35 行 |\n| `build_result_summary()` 位置 | 688-921 行 | **717-955 行** | ❌ 偏移约 30 行 |\n| `build_result_summary()` 复杂度 | 57 | 未独立测量，但 `known_violations` 中确实登记 | ⚠️ 待核验 |\n| `_freeze_meta_dict` 复杂度 | 17 | 函数位于 395-429 行（35 行）；`known_violations` 中登记存在 | ⚠️ 待核验 |\n| `_summary_degradation_state` 复杂度 | 19 | 函数位于 512-602 行（90 行）；`known_violations` 中登记存在 | ⚠️ 待核验 |\n| `schedule_service.py` 总行数 | 397 行 | **398 行** | ✅ 基本正确 |\n| `_run_schedule_impl` 复杂度 | 2 | 函数 298-396 行，已是薄编排；`known_violations` 中仍登记 | ✅ 高度可信为陈旧项 |\n| `_get_template_and_group_for_op` 复杂度 | 1 | 仅 2 行薄转调（189-190），确认为陈旧项 | ✅ 确认 |\n| `batch_service.py` 总行数 | 563 行 | **564 行** | ✅ 基本正确 |\n| `update()` 位置 | 330-409 行 | 330-409 行 | ✅ 一致 |\n| `_probe_template_ops_readonly()` 仍在 BatchService | 是 | 159-166 行仍在 `batch_service.py` | ✅ 确认 |\n| `_ensure_template_ops_in_tx()` 仍在 BatchService | 是 | 168-215 行仍在 `batch_service.py` | ✅ 确认 |\n| `create_batch_from_template_no_tx()` 已是薄转调 | 是 | 528-555 行已委托给 `batch_template_ops` | ✅ 确认 |\n| `_known_oversize_files()` 9 项 | 是 | 9 项（47-55 行） | ✅ 确认 |\n| `schedule_service.py` 不在 oversize 登记中 | 是 | 确认不在 | ✅ 确认 |\n| `_build_overdue_items` 被测试/审计直接引用 | 是 | 两处确认（回归测试 + 审计探针） | ✅ 确认 |\n| `orchestrate_schedule_run` 以关键字参数调用 `build_result_summary` | 是 | 确认 147-178 行关键字调用 + 五元组解构 | ✅ 确认 |\n| `batch_template_ops.py` 已存在 | 隐含提及 | 存在，含 `create_batch_from_template_no_tx` 等 3 个公共函数 | ✅ 确认 |\n\n### 关键偏差\n\n1. **`schedule_summary.py` 行数偏差 35 行（922→957）**：plan 后续批次 B 的拆分策略以 500 行门禁为目标，多出 35 行意味着实际需要迁出的代码量比 plan 估算更多。第一段拆完后能否降到 500 行以下更加不确定。\n2. **`build_result_summary()` 行号偏移约 30 行**：影响批次 B 步骤 3 中函数定位；虽然不影响逻辑正确性，但说明 plan 编写时基线已过时。\n3. **复杂度数值均为声称值**：plan 中三个关键复杂度数值（57/17/19）未能独立核验，但均出现在 `known_violations` 登记中，可信度中等。",
      "conclusionMarkdown": "逐项核实 plan 中声称的行数、函数位置、复杂度登记、引用链、文件存在性等事实基线。 ### 核验结果总表 | 声明项 | plan 声称 | 实际值 | 判定 | |--------|----------|--------|------| | `schedule_summary.py` 总行数 | 922 行 | **957 行** | ❌ 偏差 35 行 | | `build_result_summary()` 位置 | 688-921 行 | **717-955 行** | ❌ 偏移约 30 行 | | `build_result_summary()` 复杂度 | 57 | 未独立测量，但 `known_violations` 中确实登记 | ⚠️ 待核验 | | `_freeze_meta_dict` 复杂度 | 17 | 函数位于 395-429 行（35 行）；`known_violations` 中登记存在 | ⚠️ 待核验 | | `_summary_degradation_state` 复杂度 | 19 | 函数位于 512-602 行（90 行）；`known_violations` 中登记存在 | ⚠️ 待核验 | | `schedule_service.py` 总行数 | 397 行 | **398 行** | ✅ 基本正确 | | `_run_schedule_impl` 复杂度 | 2 | 函数 298-396 行，已是薄编排；`known_violations` 中仍登记 | ✅ 高度可信为陈旧项 | | `_get_template_and_group_for_op` 复杂度 | 1 | 仅 2 行薄转调（189-190），确认为陈旧项 | ✅ 确认 | | `batch_service.py` 总行数 | 563 行 | **564 行** | ✅ 基本正确 | | `update()` 位置 | 330-409 行 | 330-409 行 | ✅ 一致 | | `_probe_template_ops_readonly()` 仍在 BatchService | 是 | 159-166 行仍在 `batch_service.py` | ✅ 确认 | | `_ensure_template_ops_in_tx()` 仍在 BatchService | 是 | 168-215 行仍在 `batch_service.py` | ✅ 确认 | | `create_batch_from_template_no_tx()` 已是薄转调 | 是 | 528-555 行已委托给 `batch_template_ops` | ✅ 确认 | | `_known_oversize_files()` 9 项 | 是 | 9 项（47-55 行） | ✅ 确认 | | `schedule_service.py` 不在 oversize 登记中 | 是 | 确认不在 | ✅ 确认 | | `_build_overdue_items` 被测试/审计直接引用 | 是 | 两处确认（回归测试 + 审计探针） | ✅ 确认 | | `orchestrate_schedule_run` 以关键字参数调用 `build_result_summary` | 是 | 确认 147-178 行关键字调用 + 五元组解构 | ✅ 确认 | | `batch_template_ops.py` 已存在 | 隐含提及 | 存在，含 `create_batch_from_template_no_tx` 等 3 个公共函数 | ✅ 确认 | ### 关键偏差 1. **`schedule_summary.py` 行数偏差 35 行（922→957）**：plan 后续批次 B 的拆分策略以 500 行门禁为目标，多出 35 行意味着实际需要迁出的代码量比 plan 估算更多。第一段拆完后能否降到 500 行以下更加不确定。 2. **`build_result_summary()` 行号偏移约 30 行**：影响批次 B 步骤 3 中函数定位；虽然不影响逻辑正确性，但说明 plan 编写时基线已过时。 3. **复杂度数值均为声称值**：plan 中三个关键复杂度数值（57/17/19）未能独立核验，但均出现在 `known_violations` 登记中，可信度中等。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 43,
          "lineEnd": 56,
          "symbol": "_known_oversize_files"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 603,
          "lineEnd": 694,
          "symbol": "known_violations in test_cyclomatic_complexity_threshold"
        },
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 717,
          "lineEnd": 955,
          "symbol": "build_result_summary"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 528,
          "lineEnd": 555,
          "symbol": "create_batch_from_template_no_tx"
        },
        {
          "path": "core/services/scheduler/schedule_orchestrator.py",
          "lineStart": 147,
          "lineEnd": 178
        }
      ],
      "reviewedModules": [
        "schedule_summary.py 事实基线",
        "batch_service.py 事实基线",
        "schedule_service.py 事实基线",
        "test_architecture_fitness.py 账本现状"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F01",
        "F02"
      ]
    },
    {
      "id": "R2-structural-eval",
      "title": "第二轮：结构评估（批次划分、可行性、风险与完备性）",
      "status": "completed",
      "recordedAt": "2026-04-04T17:03:37.431Z",
      "summaryMarkdown": "### 结构评估总览\n\n#### 1. 批次划分合理性\n\n| 批次 | 评估 | 要点 |\n|-----|------|------|\n| A（账本陈旧项清理） | ✅ 合理 | 风险最低、依赖最少，适合首批 |\n| B（schedule_summary 拆分） | ⚠️ 策略正确但估算不充分 | 两段式方向对了，但缺少定量预测；第一段必然不够 |\n| C（batch_service 收口） | ⚠️ 迁移清单不完整 | 仅移 _probe + _ensure 不够减到 500 行；遗漏依赖方法 |\n| D（文档收口） | ✅ 合理 | 流程清晰 |\n\n#### 2. 定量可行性分析\n\n**批次 B（schedule_summary.py，实际 957 行）：**\n- 第一段迁出冻结（~69行）+ 退化（~283行）≈ 352 行 → 剩余 ~605 行 → ❌ 超标\n- 第二段迁出装配辅助（~182行）→ 剩余 ~423 行 → ✅ 达标\n- 结论：**两段都必须做**，plan 不应把第二段描述为\"仅在第一段后仍未达标时\"的条件分支\n\n**批次 C（batch_service.py，实际 564 行）：**\n- 仅迁 _probe + _ensure（~56行）→ 剩余 ~508 行 → ❌ 超标\n- 追加迁出 _invoke_template_resolver + _default_template_resolver（~36行）→ 剩余 ~472 行 → ✅ 达标\n- 结论：**迁移清单不完整**，需要补上依赖方法\n\n#### 3. 兼容边界评估\n\n12 条兼容边界声明均合理且具备可操作性。`build_result_summary` 五元组合同、`result_summary` 字段路径、批次 Excel 三条核心语义均有独立回归守护。\n\n#### 4. 回归清单覆盖评估\n\n对比上一版 review 的发现，当前版本已补齐大部分遗漏的回归用例，覆盖率显著改善。\n\n#### 5. 约束条款评估\n\n\"禁止静默回退 / 广义异常兜底 / 泛化杂物间文件\"三条约束具有明确可检查性。\"本 plan 内不得调整门禁口径\"的兜底约束避免了\"接受现状\"风险。",
      "conclusionMarkdown": "### 结构评估总览 #### 1. 批次划分合理性 | 批次 | 评估 | 要点 | |-----|------|------| | A（账本陈旧项清理） | ✅ 合理 | 风险最低、依赖最少，适合首批 | | B（schedule_summary 拆分） | ⚠️ 策略正确但估算不充分 | 两段式方向对了，但缺少定量预测；第一段必然不够 | | C（batch_service 收口） | ⚠️ 迁移清单不完整 | 仅移 _probe + _ensure 不够减到 500 行；遗漏依赖方法 | | D（文档收口） | ✅ 合理 | 流程清晰 | #### 2. 定量可行性分析 **批次 B（schedule_summary.py，实际 957 行）：** - 第一段迁出冻结（~69行）+ 退化（~283行）≈ 352 行 → 剩余 ~605 行 → ❌ 超标 - 第二段迁出装配辅助（~182行）→ 剩余 ~423 行 → ✅ 达标 - 结论：**两段都必须做**，plan 不应把第二段描述为\"仅在第一段后仍未达标时\"的条件分支 **批次 C（batch_service.py，实际 564 行）：** - 仅迁 _probe + _ensure（~56行）→ 剩余 ~508 行 → ❌ 超标 - 追加迁出 _invoke_template_resolver + _default_template_resolver（~36行）→ 剩余 ~472 行 → ✅ 达标 - 结论：**迁移清单不完整**，需要补上依赖方法 #### 3. 兼容边界评估 12 条兼容边界声明均合理且具备可操作性。`build_result_summary` 五元组合同、`result_summary` 字段路径、批次 Excel 三条核心语义均有独立回归守护。 #### 4. 回归清单覆盖评估 对比上一版 review 的发现，当前版本已补齐大部分遗漏的回归用例，覆盖率显著改善。 #### 5. 约束条款评估 \"禁止静默回退 / 广义异常兜底 / 泛化杂物间文件\"三条约束具有明确可检查性。\"本 plan 内不得调整门禁口径\"的兜底约束避免了\"接受现状\"风险。",
      "evidence": [],
      "reviewedModules": [
        "批次A架构",
        "批次B拆分可行性",
        "批次C拆分可行性",
        "批次D文档流程",
        "兼容边界完备性",
        "回归清单覆盖"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-other-3",
        "F-other-4",
        "F-other-5",
        "F-other-6",
        "F-低-批次b-c不存在强依赖但被线性排列"
      ]
    },
    {
      "id": "R3-cross-check",
      "title": "第三轮：交叉审查（与已有 review 及代码现状交叉比对）",
      "status": "completed",
      "recordedAt": "2026-04-04T17:04:02.135Z",
      "summaryMarkdown": "### 与已有 review 的交叉比对\n\n#### 前两轮 review 发现的关闭状态追踪\n\n| 序号 | 前轮发现 | 当前 plan 是否修复 | 本轮评估 |\n|-----|---------|------------------|---------|\n| 1 | 超长文件数量 10→9 不一致 | ✅ plan 已修正为 9 | 确认修复 |\n| 2 | 批次 B 行数目标不可达 | ⚠️ plan 改为两段式 | 方向正确，但行数基线仍错（922→957），第一段注定不够的事实未体现 |\n| 3 | build_result_summary 复杂度不可能降到 ≤15 | ✅ plan 改为\"不达标则暂停\" | 风险下行策略正确 |\n| 4 | create_batch_from_template_no_tx 白名单已失效 | ✅ plan 移到批次 A 清理 | 确认修复 |\n| 5 | 批次 C 行数余量过小 | ⚠️ plan 新增 _probe + _ensure 迁移 | 仍不够：需补上 _invoke_template_resolver 与 _default_template_resolver |\n| 6 | 批次 A 与基线脱节 | ✅ plan 重写为\"全量清理陈旧项\" | 确认修复 |\n| 7 | 回归清单遗漏 summary 合同用例 | ✅ plan 已补齐 6 组回归 | 确认修复 |\n| 8 | batch_excel_import.py 未纳入范围 | ✅ plan 已加入批次 C 文件清单 | 确认修复 |\n| 9 | 批次 C 误把陈旧白名单项当热点 | ✅ plan 改为批次 A 中清理 | 确认修复 |\n\n#### 本轮新发现 vs 前轮遗留\n\n- **行数基线错误**（F01）：前轮 review-1 指出\"922 行，移出 215 行后仍有 707 行\"；前轮 review-2 指出\"923 行\"。但**实际**文件已有 **957 行**——三个数值都不一致，说明基线在不断漂移而 plan 没有及时刷新。当前 plan 使用的 922 仍是过时数字。\n- **批次 C 依赖方法遗漏**（F04）：前轮 review-1 建议\"一并迁移 _probe + _ensure\"，plan 采纳了但没有深究 _ensure_template_ops_in_tx 的内部依赖链（调用 _invoke_template_resolver → _default_template_resolver），导致仅迁 _probe + _ensure 后仍差 8 行不达标。\n- **build_result_summary 复杂度预期**（F06）：前轮 review-1 建议将复杂度目标从\"≤15\"降为\"≤30\"；当前 plan 选择了更激进的策略——\"不达标则暂停\"。这个策略虽然没有虚假承诺，但也意味着执行者可能在两段拆分都完成后仍然发现 build_result_summary 复杂度远高于 15，然后被迫暂停并开新一轮。plan 应至少给出备案方向提示。\n\n#### plan 修订要点的核实\n\nplan 声称做了 5 项收敛调整，逐条核实：\n\n1. ✅ 不再预设 schedule_summary_payload.py → 确认：步骤中无此文件名\n2. ✅ 不再预设 batch_update_support.py → 确认：改为\"仅在需要时新增 batch_write_rules.py\"\n3. ✅ 删除\"接受当前水平\"口子 → 确认：步骤 11 明确\"必须暂停并开新 review\"\n4. ✅ 新增静默回退禁令 → 确认：统一执行节奏第 5 条\n5. ✅ 补上 _build_overdue_items 兼容策略 → 确认：步骤 9 与兼容边界第 11 条\n\n### plan 整体优点\n\n1. **治理方向正确**：从\"一次到位\"收敛为\"先拆最稳定边界、再按测量决定\"，符合低风险迭代原则\n2. **约束条款完备**：禁止静默回退、禁止调整门禁口径、禁止泛化文件命名，形成三道防线\n3. **回归覆盖显著改善**：相比初版，必跑回归已从 ~6 组增加到 ~17 组\n4. **兼容边界声明具体可检查**：12 条声明中每条都能对应到具体的代码位置或回归测试\n5. **暂停机制设计合理**：不虚假承诺能达标，而是预留\"暂停→新 review→新 plan\"的出口\n\n### plan 仍存在的主要风险\n\n1. **行数基线过时**：957 行的实际值未反映在 plan 中，可能导致执行者对工作量产生误判\n2. **两段式拆分几乎必然都要做**：plan 的条件分支描述暗示第二段\"可能不需要\"，但定量分析显示它几乎是必须的\n3. **批次 C 迁移清单不完整**：遗漏 _invoke_template_resolver 和 _default_template_resolver 两个依赖方法\n4. **build_result_summary 复杂度**：即使两段拆分都完成，该函数复杂度很可能仍远超 15，暂停出口的概率较高",
      "conclusionMarkdown": "### 与已有 review 的交叉比对 #### 前两轮 review 发现的关闭状态追踪 | 序号 | 前轮发现 | 当前 plan 是否修复 | 本轮评估 | |-----|---------|------------------|---------| | 1 | 超长文件数量 10→9 不一致 | ✅ plan 已修正为 9 | 确认修复 | | 2 | 批次 B 行数目标不可达 | ⚠️ plan 改为两段式 | 方向正确，但行数基线仍错（922→957），第一段注定不够的事实未体现 | | 3 | build_result_summary 复杂度不可能降到 ≤15 | ✅ plan 改为\"不达标则暂停\" | 风险下行策略正确 | | 4 | create_batch_from_template_no_tx 白名单已失效 | ✅ plan 移到批次 A 清理 | 确认修复 | | 5 | 批次 C 行数余量过小 | ⚠️ plan 新增 _probe + _ensure 迁移 | 仍不够：需补上 _invoke_template_resolver 与 _default_template_resolver | | 6 | 批次 A 与基线脱节 | ✅ plan 重写为\"全量清理陈旧项\" | 确认修复 | | 7 | 回归清单遗漏 summary 合同用例 | ✅ plan 已补齐 6 组回归 | 确认修复 | | 8 | batch_excel_import.py 未纳入范围 | ✅ plan 已加入批次 C 文件清单 | 确认修复 | | 9 | 批次 C 误把陈旧白名单项当热点 | ✅ plan 改为批次 A 中清理 | 确认修复 | #### 本轮新发现 vs 前轮遗留 - **行数基线错误**（F01）：前轮 review-1 指出\"922 行，移出 215 行后仍有 707 行\"；前轮 review-2 指出\"923 行\"。但**实际**文件已有 **957 行**——三个数值都不一致，说明基线在不断漂移而 plan 没有及时刷新。当前 plan 使用的 922 仍是过时数字。 - **批次 C 依赖方法遗漏**（F04）：前轮 review-1 建议\"一并迁移 _probe + _ensure\"，plan 采纳了但没有深究 _ensure_template_ops_in_tx 的内部依赖链（调用 _invoke_template_resolver → _default_template_resolver），导致仅迁 _probe + _ensure 后仍差 8 行不达标。 - **build_result_summary 复杂度预期**（F06）：前轮 review-1 建议将复杂度目标从\"≤15\"降为\"≤30\"；当前 plan 选择了更激进的策略——\"不达标则暂停\"。这个策略虽然没有虚假承诺，但也意味着执行者可能在两段拆分都完成后仍然发现 build_result_summary 复杂度远高于 15，然后被迫暂停并开新一轮。plan 应至少给出备案方向提示。 #### plan 修订要点的核实 plan 声称做了 5 项收敛调整，逐条核实： 1. ✅ 不再预设 schedule_summary_payload.py → 确认：步骤中无此文件名 2. ✅ 不再预设 batch_update_support.py → 确认：改为\"仅在需要时新增 batch_write_rules.py\" 3. ✅ 删除\"接受当前水平\"口子 → 确认：步骤 11 明确\"必须暂停并开新 review\" 4. ✅ 新增静默回退禁令 → 确认：统一执行节奏第 5 条 5. ✅ 补上 _build_overdue_items 兼容策略 → 确认：步骤 9 与兼容边界第 11 条 ### plan 整体优点 1. **治理方向正确**：从\"一次到位\"收敛为\"先拆最稳定边界、再按测量决定\"，符合低风险迭代原则 2. **约束条款完备**：禁止静默回退、禁止调整门禁口径、禁止泛化文件命名，形成三道防线 3. **回归覆盖显著改善**：相比初版，必跑回归已从 ~6 组增加到 ~17 组 4. **兼容边界声明具体可检查**：12 条声明中每条都能对应到具体的代码位置或回归测试 5. **暂停机制设计合理**：不虚假承诺能达标，而是预留\"暂停→新 review→新 plan\"的出口 ### plan 仍存在的主要风险 1. **行数基线过时**：957 行的实际值未反映在 plan 中，可能导致执行者对工作量产生误判 2. **两段式拆分几乎必然都要做**：plan 的条件分支描述暗示第二段\"可能不需要\"，但定量分析显示它几乎是必须的 3. **批次 C 迁移清单不完整**：遗漏 _invoke_template_resolver 和 _default_template_resolver 两个依赖方法 4. **build_result_summary 复杂度**：即使两段拆分都完成，该函数复杂度很可能仍远超 15，暂停出口的概率较高",
      "evidence": [],
      "reviewedModules": [
        "历史review关闭状态",
        "plan revision声称与实际对比",
        "跨批次一致性"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-other-8",
        "F-中-批次c的依赖方法迁移缺失是前轮review未充分强调的新问题"
      ]
    }
  ],
  "findings": [
    {
      "id": "F01",
      "severity": "medium",
      "category": "docs",
      "title": "schedule_summary.py 行数声称与实际不符",
      "descriptionMarkdown": "plan 声称 schedule_summary.py 当前 922 行，实际为 957 行，偏差 35 行。build_result_summary() 位置也相应偏移（声称 688-921，实际 717-955）。这使得批次 B 第一段拆分后能否降到 500 行以下更加不确定，可能直接影响是否需要进入第二段拆分的判断基线。",
      "recommendationMarkdown": "修正 plan 中的行数与行号为最新实际值；同时重新评估第一段拆分是否足以把文件降到 500 行以下。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 717,
          "lineEnd": 955
        },
        {
          "path": "core/services/scheduler/schedule_summary.py"
        }
      ],
      "relatedMilestoneIds": [
        "R1-fact-check"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F02",
      "severity": "low",
      "category": "docs",
      "title": "复杂度声称值未独立核验",
      "descriptionMarkdown": "plan 声称 build_result_summary 复杂度=57、_freeze_meta_dict=17、_summary_degradation_state=19、update=17，这些数值均来自 known_violations 登记，但 plan 未提供核验命令或核验输出。若实际复杂度已因阶段04后续小改而变化，拆分策略可能需要调整。",
      "recommendationMarkdown": "在批次 B/C 开始前，先跑一次 radon 测量并记录输出作为执行前基线。",
      "evidence": [],
      "relatedMilestoneIds": [
        "R1-fact-check"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-3",
      "severity": "low",
      "category": "other",
      "title": "[高] 批次B第一段拆分必然不足以达标：冻结+退化共~352行迁出后仍剩~605行，远超500行门禁",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R2-structural-eval"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-4",
      "severity": "low",
      "category": "other",
      "title": "[高] 批次C迁移清单不足以达到500行门禁：仅迁_probe+_ensure共~56行后仍剩~508行，需补上_invoke_template_resolver与_default_template_resolver",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R2-structural-eval"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-5",
      "severity": "low",
      "category": "other",
      "title": "[中] 两段式策略缺少定量预测：plan应预先给出第一段~605行、第二段~425行的估算",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R2-structural-eval"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-6",
      "severity": "low",
      "category": "other",
      "title": "[中] build_result_summary复杂度降幅预期不足：即使辅助函数全部外提，函数内仍有12-15个if分支",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R2-structural-eval"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-低-批次b-c不存在强依赖但被线性排列",
      "severity": "low",
      "category": "other",
      "title": "[低] 批次B/C不存在强依赖但被线性排列",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R2-structural-eval"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-other-8",
      "severity": "low",
      "category": "other",
      "title": "[高] plan已经回应了前两轮review的大部分发现，但行数基线仍未修正，导致‘第一段拆分不够’这一核心问题被掩盖",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R3-cross-check"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-中-批次c的依赖方法迁移缺失是前轮review未充分强调的新问题",
      "severity": "low",
      "category": "other",
      "title": "[中] 批次C的依赖方法迁移缺失是前轮review未充分强调的新问题",
      "descriptionMarkdown": null,
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "R3-cross-check"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:3e5f7745b1b77ec59984e13f7e9fb3bce441e51bc87bb3014abea987242870c2",
    "generatedAt": "2026-04-04T17:04:16.174Z",
    "locale": "zh-CN"
  }
}
```

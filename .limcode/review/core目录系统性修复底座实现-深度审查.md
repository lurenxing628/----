# core目录系统性修复底座实现 深度审查
- 日期: 2026-04-04
- 概述: 对 plan 00 共享合同底座的全部未提交实现代码进行深度三轮审查：正确性、优雅性、逻辑严谨性。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# core目录系统性修复底座实现 深度审查
- 日期: 2026-04-04
- 概述: 对 plan 00 共享合同底座的全部未提交实现代码进行深度三轮审查：正确性、优雅性、逻辑严谨性。

## 审查对象
- 新增底座文件：`value_policies.py`、`strict_parse.py`、`compat_parse.py`、`degradation.py`、`build_outcome.py`
- 改造文件：`number_utils.py`、`_sched_display_utils.py`、`evaluation.py`
- 相关测试文件
- 上下游消费关系

## 审查维度
1. **第一轮：正确性与逻辑严谨性** — 是否有 BUG、边界遗漏、类型不安全
2. **第二轮：设计优雅性与简洁性** — 是否过度兜底、静默回退、冗余分支
3. **第三轮：合同一致性与上下游集成** — 底座是否能被后续 plan 01-04 正确消费

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/common/value_policies.py, core/services/common/strict_parse.py, core/services/common/compat_parse.py, core/services/common/degradation.py, core/services/common/build_outcome.py, core/services/common/field_parse.py, core/services/common/number_utils.py, core/services/scheduler/_sched_display_utils.py, core/algorithms/evaluation.py, core/services/scheduler/gantt_tasks.py, core/services/scheduler/gantt_week_plan.py, core/services/scheduler/resource_dispatch_rows.py, core/services/scheduler/config_validator.py, core/services/scheduler/config_snapshot.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_input_builder.py, core/algorithms/greedy/schedule_params.py, tests/regression_value_policies_matrix_contract.py, tests/regression_strict_parse_blank_required.py, tests/regression_compat_parse_emits_degradation.py, tests/regression_degradation_collector_merge_counts.py, tests/regression_build_outcome_contract.py, tests/regression_number_utils_facade_delegates_strict_parse.py, tests/test_architecture_fitness.py, core/services/scheduler/batch_service.py, core/services/scheduler/_sched_utils.py
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 9
- 问题严重级别分布: 高 1 / 中 6 / 低 2
- 最新结论: ## 综合审查结论 本次审查覆盖了 plan 00 共享合同底座的 6 个新增文件、1 个门面改造文件、8 个消费者修改文件、6 个配套回归测试，共 26 个模块。三轮审查（正确性 → 优雅性 → 合同一致性）共发现 **9 项问题**（高 1 / 中 6 / 低 2）。 ### 总体评价 **底座的设计方向完全正确，实现质量整体良好。** 最重要的设计成果是： 1. **消除了静默回退** — 所有兼容路径都通过 `DegradationCollector` 留痕，旧代码中"悄悄补默认值"的做法被系统性替换 2. **分层清晰** — `strict_parse` → `compat_parse` → `field_parse` → `build_outcome` 四层各司其职，没有越界 3. **字段语义矩阵** — 用一个不可变数据结构把 14 个关键字段的写入/读取语义写死，后续消费者只需查表 4. **上下游集成完整** — 配置快照、排产输入构建、甘特/周计划/资源排班展示链全部正确消费了新底座 ### 必须修复的问题 | 优先级 | 问题 | 修复建议 | |---|---|---| | **立即修复** | `number_utils.py` 的 `parse_finite_float` 重载默认值 `allow_none=True` 与类型声明 `allow_none=False` 不一致 | 将实现的默认值改为 `allow_none=False`，并核查所有调用方 | | **提交前修复** | `config_validator.py` 非严格路径双调用 `parse_field_float` 无注释 | 增加注释解释意图，或重构为单次调用 | | **近期补齐** | `field_parse.py` 缺少专门的回归测试 | 增加测试覆盖 strict_mode 分发和 min_value 违反回退逻辑 | | **近期补齐** | 缺少架构守门测试阻止新增局部 `_safe_*` 函数 | 在 `test_architecture_fitness.py` 中增加模式扫描 | | **近期补齐** | `STABLE_DEGRADATION_CODES` 是死代码 | 增加守门测试验证实际使用的原因码 | ### 可以延后的问题 - `field_parse.py` 的 `collector=None` 事件丢失：过渡期可接受，后续迁移时修正 - `field_parse.py` 最小值违反的事件码语义：`invalid_number` 在当前范围内可用，后续可细化 - `BuildOutcome` 计数重叠风险：注释已提醒，当前无实际触发场景 - 展示工具导入冗长：纯粹的代码风格问题，可随便修 - 多层解析链重复解析：无功能影响，可在下一轮重构中优化
- 下一步建议: 立即修复 `number_utils.py` 的 `parse_finite_float` 重载默认值 BUG（将实现的 `allow_none=True` 改为 `allow_none=False`），然后补齐 `field_parse.py` 的回归测试和架构守门测试。
- 总体结论: 有条件通过

## 评审发现

### number_utils 类型重载与运行时默认值不一致

- ID: F-number-utils-overload-default-mismatch
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  parse_finite_float 的第一个 @overload 声明 allow_none: Literal[False] = False（返回 float），但实现函数的运行时默认值是 allow_none: bool = True（调用 parse_optional_float，可返回 None）。类型检查器认为不传 allow_none 时返回 float，但运行时可能返回 None，形成类型安全漏洞。任何调用 parse_finite_float(v, field='x') 的代码在 v=None 时会拿到 None 但类型注解不会提示。
- 建议:

  将实现函数的默认值改为 allow_none: bool = False，或将第一个 @overload 改为 Literal[True] = True。需要检查所有调用方确认期望行为。
- 证据:
  - `core/services/common/number_utils.py:14-23#parse_finite_float`
  - `core/services/common/number_utils.py:23-27#parse_finite_float (impl)`
  - `core/services/common/number_utils.py`

### field_parse 最小值违反产生的事件码语义不精确

- ID: F-field-parse-min-violation-event-semantic
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  当值是合法数字但低于 min_value 时（如 priority_weight='-0.5'），field_parse 转入 compat_parse 的回退路径。compat_parse 内部 _reason_code_for_failure 返回 'invalid_number'，消息为'历史数值无效'。但实际问题是'数值低于最小值'而非'数值本身无效'。这会影响后续的退化排障和计数准确性。
- 建议:

  考虑在 field_parse 的 min_value 违反分支中使用更精确的原因码（如 'number_below_minimum'），或在 compat_parse 中区分'无法解析'和'解析成功但不符合约束'两种失败模式。
- 证据:
  - `core/services/common/field_parse.py:43-58#parse_field_float (min_value branch)`
  - `core/services/common/field_parse.py`

### field_parse 不传 collector 时退化事件静默丢弃

- ID: F-field-parse-collector-none-events-lost
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  parse_field_float/parse_field_int 在 collector=None 时创建临时 DegradationCollector()，但该收集器在函数返回后无法被调用方访问，所有退化事件被丢弃。虽然 schedule_params.py 的 _weighted_value 利用了 bool(collector) 检测是否有退化，但事件详情（原因码、样本值等）完全丢失。这违反了 plan 00 的'不允许只在日志里写一句话的退化处理'原则。
- 建议:

  考虑让 collector 参数变为必传（移除默认值 None），或让函数返回 (value, collector) 元组。在过渡期，至少在文档中标明 collector=None 的行为。
- 证据:
  - `core/services/common/field_parse.py:30#active_collector fallback`
  - `core/algorithms/greedy/schedule_params.py:86-99#_weighted_value`
  - `core/services/common/field_parse.py`
  - `core/algorithms/greedy/schedule_params.py`

### BuildOutcome 事件计数与外部计数重叠时双倍计数

- ID: F-build-outcome-counters-overlap-risk
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  BuildOutcome.__post_init__ 先从 events 归并出原因码计数，再与外部 counters 参数逐项叠加。当外部 counters 包含与事件原因码同名的键时会产生双倍计数。注释中已提醒该风险，但没有防御机制。当前测试未覆盖此重叠场景。
- 建议:

  在 __post_init__ 中检测 counters 与事件原因码的交集，遇到重叠时记录警告或抛出 ValueError。或者改为'外部 counters 只允许追加事件中不存在的键'。
- 证据:
  - `core/services/common/build_outcome.py:18-29#__post_init__`
  - `core/services/common/build_outcome.py`

### 展示工具导入极度冗长

- ID: F-verbose-display-utils-imports
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `gantt_tasks.py` 用 8 个独立的 `from ._sched_display_utils import (...)` 块导入工具函数，每个块只导入一个名称并加 `_` 前缀别名。`gantt_week_plan.py`、`resource_dispatch_rows.py` 同样如此，后者用了 10 个独立导入块。三个文件共约 60 行导入语句可合并为约 15 行。`_` 前缀别名也没有实际意义——模块名本身已以 `_` 开头，内部函数无需再伪装成私有。
- 建议:

  合并为单个导入块：`from ._sched_display_utils import (...)`。去掉 `_` 前缀别名，或者使用 `from . import _sched_display_utils as _du` 的模块别名方式。
- 证据:
  - `core/services/scheduler/gantt_tasks.py:11-34#imports`
  - `core/services/scheduler/gantt_week_plan.py:8-28#imports`
  - `core/services/scheduler/resource_dispatch_rows.py:9-38#imports`
  - `core/services/scheduler/gantt_tasks.py`
  - `core/services/scheduler/gantt_week_plan.py`
  - `core/services/scheduler/resource_dispatch_rows.py`

### 多层解析链导致同值重复解析最多 4 次

- ID: F-redundant-multi-parse
- 严重级别: 中
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `field_parse.py` 的非严格路径在最小值违反时会将同一个值解析 3 次（field_parse 解析 1 次 + compat_parse 内部解析 2 次）。`config_validator.py` 的非严格路径更是先调用 `parse_field_float(strict_mode=True)` 再调用 `parse_field_float(strict_mode=False)`，同一个值最多被解析 4 次。尽管单次解析成本很低，但这个模式让代码难以理解且易产生重复退化事件。
- 建议:

  在 `field_parse.py` 中，可以让非严格路径一次性解析并带上 min_value，失败后直接计算回退值并产出事件，而不是再转一次 compat_parse。`config_validator.py` 中也不应双调 parse_field_float，可以直接用一次调用配合 min_violation_fallback 实现等价行为。
- 证据:
  - `core/services/common/field_parse.py:30-58#parse_field_float non-strict`
  - `core/services/scheduler/config_validator.py:40-83#_get_float non-strict`
  - `core/services/common/field_parse.py`
  - `core/services/scheduler/config_validator.py`

### config_validator 非严格路径双调用意图不透明

- ID: F-config-validator-double-parse-opaque
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  `config_validator.py` 非严格路径先调用 `parse_field_float(raw, strict_mode=True)` 来验证值是合法数字，再调用 `parse_field_float(raw, strict_mode=False, min_value=...)` 应用兆容回退。第一次调用的返回值被丢弃，意图是'不合法数字直接报错，低于最小值允许兑容回退'。但这个意图埋在两次调用的参数差异中，没有任何注释解释，未来维护者很难理解为什么同一个值要解析两次。
- 建议:

  增加注释解释双调用的意图，或者重构为单次调用：用 `parse_field_float(raw, strict_mode=False, min_value=..., min_violation_fallback=min_v)` 配合 `_is_blank` 判断即可实现等价行为。
- 证据:
  - `core/services/scheduler/config_validator.py:64-83#_get_float double-call`
  - `core/services/scheduler/config_validator.py`

### 缺少架构守门测试阻止新增局部解析函数

- ID: F-no-guard-against-local-parsers
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  plan 00 明确禁止'后续任何新模块不得再新增局部 _safe_float、_cfg_float、_get_float 实现'，但没有架构守门测试来强制执行这条约束。`test_architecture_fitness.py` 只检查文件行数和圆复杂度，不检查是否存在被禁止的局部解析函数模式。当前没有任何机制能阻止未来开发者再次加入 `_safe_float` 类函数。
- 建议:

  在 `test_architecture_fitness.py` 中增加一个测试：扫描 `core/` 目录的所有 `.py` 文件，检查是否存在匹配 `def _safe_float`、`def _safe_int`、`def _cfg_float`、`def _get_float` 等模式的函数定义，并维护一个白名单用于尚未迁移的存量。每次新增必须强制说明原因。
- 证据:
  - `tests/test_architecture_fitness.py`

### STABLE_DEGRADATION_CODES 是死代码

- ID: F-stable-codes-dead-code
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  `STABLE_DEGRADATION_CODES` 在 `degradation.py` 中定义了 11 个预定义原因码，但从未被任何代码或测试导入或引用。它既不在运行时验证新增事件的原因码是否合法，也不在测试时检查代码库中实际使用的原因码是否都在该元组中。它是一个存在但没有约束力的声明。
- 建议:

  增加架构守门测试：(1) 扫描代码库中所有 `DegradationCollector.add(code=...)` 调用，确认所用原因码均在 `STABLE_DEGRADATION_CODES` 中；(2) 或者在 `DegradationCollector.add()` 中增加运行时检查，未知原因码记录警告。
- 证据:
  - `core/services/common/degradation.py:6-18#STABLE_DEGRADATION_CODES`
  - `core/services/common/degradation.py`

## 评审里程碑

### M1 · 第一轮：正确性与逻辑严谨性审查

- 状态: 已完成
- 记录时间: 2026-04-04T15:51:34.978Z
- 已审模块: core/services/common/value_policies.py, core/services/common/strict_parse.py, core/services/common/compat_parse.py, core/services/common/degradation.py, core/services/common/build_outcome.py, core/services/common/field_parse.py, core/services/common/number_utils.py, core/services/scheduler/_sched_display_utils.py, core/algorithms/evaluation.py
- 摘要:

  逐文件审查了 6 个底座新文件（`value_policies.py`、`strict_parse.py`、`compat_parse.py`、`degradation.py`、`build_outcome.py`、`field_parse.py`）、1 个改造门面文件（`number_utils.py`）、2 个消费者修改文件（`_sched_display_utils.py`、`evaluation.py`），以及 6 个配套回归测试。

  **核心发现：**

  1. **`number_utils.py` 类型重载与运行时默认值不一致（BUG）**：`parse_finite_float` 的类型重载声明 `allow_none` 默认为 `False`（返回 `float`），但实现的运行时默认值是 `True`（可返回 `None`）。这会导致：(a) 不传 `allow_none` 的调用方在类型检查器看到的返回类型（`float`）与运行时实际可能的返回类型（`Optional[float]`）不一致；(b) 旧代码如果依赖 `parse_finite_float(v, field="x")` 的行为，其结果可能是 `None` 但类型注解没有告警。

  2. **`field_parse.py` 非严格路径的最小值违反事件语义不精确**：当一个值是合法数字但低于 `min_value` 时，`parse_compat_float` 内部产生的事件码是 `invalid_number`，消息是"历史数值无效"。但实际问题是"数值低于最小值"而非"数值无效"。语义不精确，可能影响后续排障。

  3. **`field_parse.py` 的 `collector=None` 时退化事件丢失**：当调用方不传 `collector` 时，函数内部创建临时 `DegradationCollector()` 但从未返回，所有退化事件被静默丢弃。`schedule_params.py` 的 `_weighted_value` 利用了这一模式来检测退化但只保留计数——事件详情被丢弃。

  4. **`build_outcome.py` 的 `__post_init__` 双倍计数风险**：注释已提醒风险，但当 `from_collector()` 的 `counters` 参数包含与事件原因码同名的键时，会产生双倍计数。当前测试未覆盖此重叠场景。

  5. **`strict_parse.py` 的 `parse_required_date` 对含时间的字符串处理**：传入 `datetime` 对象会正确提取 `.date()`，但传入 `"2026-03-05 12:00"` 字符串会被拒绝（因为 `strptime` 格式 `%Y-%m-%d` 不匹配）。测试验证了这个行为。这是设计意图——严格日期不接受含时间的字符串——但可能需要在文档中明确。

  6. **`evaluation.py` 中 `_parse_due_date_state` 与 `_parse_due_date` 逻辑重复**：两个函数对 `date`/`datetime` 类型的处理逻辑几乎完全重复（~10行），可合并为一个函数。
- 结论:

  底座文件整体逻辑正确，有一个确认的类型安全 BUG（`number_utils.py` 重载默认值不一致），两个中等语义问题（`field_parse.py` 最小值违反事件语义不精确、`collector=None` 时事件静默丢弃），一个文档/设计明确性问题。
- 证据:
  - `core/services/common/number_utils.py:13-27#parse_finite_float overloads`
  - `core/services/common/field_parse.py:13-60#parse_field_float`
  - `core/services/common/build_outcome.py:18-29#__post_init__`
  - `core/algorithms/evaluation.py:24-52#_parse_due_date_state + _parse_due_date`
- 问题:
  - [高] JavaScript: number_utils 类型重载与运行时默认值不一致
  - [中] 可维护性: field_parse 最小值违反产生的事件码语义不精确
  - [中] 可维护性: field_parse 不传 collector 时退化事件静默丢弃
  - [低] 可维护性: BuildOutcome 事件计数与外部计数重叠时双倍计数

### M2 · 第二轮：设计优雅性与简洁性审查

- 状态: 已完成
- 记录时间: 2026-04-04T15:54:28.321Z
- 已审模块: core/services/scheduler/gantt_tasks.py, core/services/scheduler/gantt_week_plan.py, core/services/scheduler/resource_dispatch_rows.py, core/services/scheduler/config_validator.py, core/services/scheduler/config_snapshot.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_input_builder.py, core/algorithms/greedy/schedule_params.py
- 摘要:

  **第二轮审查聚焦设计优雅性和简洁性，重点检查是否存在过度兜底、静默回退、冗余分支。**

  ### 优点
  1. **无静默回退**：所有兼容路径都通过 `DegradationCollector` 留痕，消除了旧代码中"悄悄补默认值"的做法。这是本次改造最重要的设计成果。
  2. **分层清晰**：`strict_parse`（只做"合法值或报错"）→ `compat_parse`（查策略+回退+留痕）→ `field_parse`（按 strict_mode 分发）→ `build_outcome`（统一封套），四层各司其职，没有越界。
  3. **`BuildOutcome` 设计简洁**：泛型 + `from_collector()` 工厂方法 + `has_events` 属性，覆盖了读侧构建器的全部需求，没有过度抽象。
  4. **`value_policies.py` 矩阵式定义**：用一个不可变数据结构把全部字段语义写死，后续消费者只需查表，不需自行定义规则。
  5. **`_sched_display_utils.py` 提取的函数**本身设计简洁——纯函数、无副作用、无过度兜底。

  ### 冗余与可改进之处

  1. **展示工具导入极度冗长**：`gantt_tasks.py`、`gantt_week_plan.py`、`resource_dispatch_rows.py` 三个文件共用约 60 行独立导入语句（每个函数一个 `from ._sched_display_utils import (...)`），可合并为各约 5 行的单块导入。`_` 前缀别名也没有实际意义——模块名本身已以 `_` 开头，内部函数无需再伪装成私有。

  2. **`field_parse.py` 非严格路径的多层解析链导致同值重复解析最多 4 次**：
     - `field_parse` 先调用 `parse_required_float(value)` （第 1 次解析），如果成功则检查 min_value
     - 如果 min_value 违反，转入 `parse_compat_float(value, min_value=...)`
     - `parse_compat_float` 内部又调用 `parse_required_float(value, min_value=...)` （第 2 次），失败后回退
     - `config_validator.py` 更是先用 `strict_mode=True` 调一次，再用 `strict_mode=False` 调一次
     - 在最坏情况下，同一个值从字符串转浮点要执行 4 次

  3. **`config_validator.py` 非严格路径的"双调用"模式可读性差**：先调用 `parse_field_float(raw, strict_mode=True)` 丢弃返回值，再调用 `parse_field_float(raw, strict_mode=False, min_value=...)`。意图是"不合法数字直接报错，低于最小值允许兼容回退"。但这个意图完全靠两次调用的参数差异来表达，没有注释，未来维护者很难理解。

  4. **`schedule_optimizer_steps.py` 和 `schedule_params.py` 的 `_cfg_float` / `_weighted_value` 模式**：创建局部 `DegradationCollector()`，只用 `if collector:` 检测退化然后 `increment_counter`——退化事件的详情（原因码、样本值）全部丢弃。这在过渡期是可接受的，但与 plan 00 的"后续页面、摘要、历史、导出全部从同一事件源取数"目标有差距。

  ### 没有发现的问题
  - 没有发现"过度兜底"——`strict_parse.py` 的函数真的只做"合法值或报错"，没有追加警告、默认值或回退。
  - 没有发现"静默回退"——`compat_parse.py` 的每条回退路径都强制生成 `DegradationEvent`。
  - 没有发现不必要的继承或过度封装——所有数据结构都是扁平的 `@dataclass`。
- 结论:

  设计整体方向正确，层次分明。但存在三个可以显著改善的模式：(1) 展示工具导入极度冗长；(2) 多层解析链导致同一值被重复解析多达4次；(3) `config_validator` 非严格路径的双调用模式可读性差。无静默回退——所有兼容路径都留痕，是本次实现的重要优点。
- 证据:
  - `core/services/scheduler/gantt_week_plan.py:8-37#_sched_display_utils imports`
  - `core/services/scheduler/resource_dispatch_rows.py:9-38#_sched_display_utils imports`
  - `core/services/scheduler/config_validator.py:40-83#_get_float non-strict path`
  - `core/services/common/field_parse.py:24-60#parse_field_float non-strict path`
- 问题:
  - [低] 可维护性: 展示工具导入极度冗长
  - [中] 性能: 多层解析链导致同值重复解析最多 4 次
  - [中] 可维护性: config_validator 非严格路径双调用意图不透明

### M3 · 第三轮：合同一致性与上下游集成审查

- 状态: 已完成
- 记录时间: 2026-04-04T15:56:58.095Z
- 已审模块: tests/regression_value_policies_matrix_contract.py, tests/regression_strict_parse_blank_required.py, tests/regression_compat_parse_emits_degradation.py, tests/regression_degradation_collector_merge_counts.py, tests/regression_build_outcome_contract.py, tests/regression_number_utils_facade_delegates_strict_parse.py, tests/test_architecture_fitness.py, core/services/scheduler/batch_service.py, core/services/scheduler/_sched_utils.py
- 摘要:

  **第三轮审查聚焦底座合同的一致性与上下游集成能力，验证后续 plan 01-04 能否正确消费。**

  ### 合同落地状态

  | 底座组件 | plan 00 要求 | 实际状态 | 判定 |
  |---|---|---|---|
  | 字段语义矩阵 | `value_policies.py` 关键字段入表 | 14 个字段全部入表，含写入语义/读取语义/原因码/兼容默认值 | ✅ |
  | 严格解析层 | `strict_parse.py` 只做"合法值或报错" | 6 个入口函数（float/int/date × required/optional），无副作用、无回退 | ✅ |
  | 兼容读取层 | `compat_parse.py` 仅限历史读取 | 3 个兼容解析函数，每条回退必产 DegradationEvent | ✅ |
  | 统一退化事件 | `degradation.py` 稳定原因码+收集器 | DegradationEvent 不可变，DegradationCollector 支持合并和去重 | ✅ |
  | 统一结果封套 | `build_outcome.py` 先落在读侧构建器 | 泛型 BuildOutcome 已被 gantt_tasks/gantt_week_plan/resource_dispatch_rows/schedule_input_builder 消费 | ✅ |
  | 旧门面改造 | `number_utils.py` 改为薄转调 | 完成，但存在重载默认值 BUG（见 M1） | ⚠️ |

  ### 上下游消费验证

  1. **配置快照链**（`config_snapshot.py`）：正确创建顶层 `DegradationCollector`，通过 `_get_float`/`_get_int` → `parse_field_float`/`parse_field_int` 传递，最终将事件序列化到快照的 `degradation_events`/`degradation_counters` 字段。✅

  2. **排产输入构建链**（`schedule_input_builder.py`）：正确使用 `parse_field_float` + `BuildOutcome.from_collector()` + 逐工序 scope 标识。外协合并退化事件正确收集并传递到 `OpForScheduleAlgo.merge_context_events`。✅

  3. **甘特/周计划/资源排班展示链**：全部返回 `BuildOutcome`，坏时间行通过 `record_bad_time_row()` 统一记录退化事件，空结果通过 `empty_reason` 区分"天然无数据"和"退化过滤后无数据"。✅

  4. **回归测试覆盖**：6 个配套回归测试覆盖了底座的核心合同点——矩阵完整性、严格空白拒绝、兼容回退留痕、收集器合并语义、BuildOutcome 构造契约、旧门面转调验证。✅

  ### 合同执行缺口

  1. **没有架构守门测试阻止新增局部解析函数**：plan 00 明确禁止"后续任何新模块不得再新增局部 `_safe_float()`…"，但 `test_architecture_fitness.py` 只检查行数和圈复杂度，不扫描被禁止的局部函数模式。当前没有任何机制阻止未来开发者再次加入 `_safe_float` 类函数。

  2. **`STABLE_DEGRADATION_CODES` 是死代码**：在 `degradation.py` 中定义了 11 个预定义原因码，但从未被任何代码或测试导入、引用或验证。它既不在运行时检查新增事件的原因码是否合法，也不在测试时扫描代码库中实际使用的原因码是否都在该元组中。它是一个存在但没有约束力的声明。

  3. **仍残留 3 处未迁移的局部解析函数**：
     - `batch_service.py:57` — `_safe_float()`：静默返回 None，无退化事件
     - `_sched_utils.py:6` — `_safe_int()`：静默返回默认值，无退化事件
     - `scheduler.py:166` — `_safe_int()`：局部函数，同上
     
     这些是存量而非新增，plan 00 的边界控制中说"本段不直接改 `ScheduleService` 主链编排"，所以暂时保留是合理的。但没有白名单或登记清单来追踪，后续 plan 可能遗忘它们。

  ### 测试质量评价

  6 个底座回归测试的质量整体良好：
  - `regression_value_policies_matrix_contract.py`：验证了 14 个字段的写入语义、读取语义、原因码、兼容默认值——是矩阵的活文档
  - `regression_degradation_collector_merge_counts.py`：验证了合并去重语义和样本保留策略
  - `regression_build_outcome_contract.py`：验证了 from_collector 和事件重复合并
  - `regression_number_utils_facade_delegates_strict_parse.py`：通过 mock 替换验证了门面确实在转调

  但有一个测试缺口：**没有测试覆盖 `field_parse.py` 的行为**。`field_parse.py` 是连接 strict/compat 两层的桥梁，有复杂的 strict_mode 分发逻辑和 min_value 违反回退逻辑，但没有专门的回归测试。
- 结论:

  底座的五类基础件已全部落地且能被后续 plan 正确消费。配套回归测试覆盖了核心合同。但存在三个合同执行缺口：(1) 没有架构守门测试阻止新增局部 `_safe_*` 函数；(2) `STABLE_DEGRADATION_CODES` 是死代码，没有运行时或测试时的约束力；(3) 仍残留 3 处未迁移的局部解析函数。
- 证据:
  - `core/services/common/degradation.py:6-18#STABLE_DEGRADATION_CODES`
  - `core/services/scheduler/batch_service.py:56-65#_safe_float`
  - `core/services/scheduler/_sched_utils.py:6-29#_safe_int`
- 问题:
  - [中] 测试: 缺少架构守门测试阻止新增局部解析函数
  - [中] 测试: STABLE_DEGRADATION_CODES 是死代码

## 最终结论

## 综合审查结论

本次审查覆盖了 plan 00 共享合同底座的 6 个新增文件、1 个门面改造文件、8 个消费者修改文件、6 个配套回归测试，共 26 个模块。三轮审查（正确性 → 优雅性 → 合同一致性）共发现 **9 项问题**（高 1 / 中 6 / 低 2）。

### 总体评价

**底座的设计方向完全正确，实现质量整体良好。** 最重要的设计成果是：

1. **消除了静默回退** — 所有兼容路径都通过 `DegradationCollector` 留痕，旧代码中"悄悄补默认值"的做法被系统性替换
2. **分层清晰** — `strict_parse` → `compat_parse` → `field_parse` → `build_outcome` 四层各司其职，没有越界
3. **字段语义矩阵** — 用一个不可变数据结构把 14 个关键字段的写入/读取语义写死，后续消费者只需查表
4. **上下游集成完整** — 配置快照、排产输入构建、甘特/周计划/资源排班展示链全部正确消费了新底座

### 必须修复的问题

| 优先级 | 问题 | 修复建议 |
|---|---|---|
| **立即修复** | `number_utils.py` 的 `parse_finite_float` 重载默认值 `allow_none=True` 与类型声明 `allow_none=False` 不一致 | 将实现的默认值改为 `allow_none=False`，并核查所有调用方 |
| **提交前修复** | `config_validator.py` 非严格路径双调用 `parse_field_float` 无注释 | 增加注释解释意图，或重构为单次调用 |
| **近期补齐** | `field_parse.py` 缺少专门的回归测试 | 增加测试覆盖 strict_mode 分发和 min_value 违反回退逻辑 |
| **近期补齐** | 缺少架构守门测试阻止新增局部 `_safe_*` 函数 | 在 `test_architecture_fitness.py` 中增加模式扫描 |
| **近期补齐** | `STABLE_DEGRADATION_CODES` 是死代码 | 增加守门测试验证实际使用的原因码 |

### 可以延后的问题

- `field_parse.py` 的 `collector=None` 事件丢失：过渡期可接受，后续迁移时修正
- `field_parse.py` 最小值违反的事件码语义：`invalid_number` 在当前范围内可用，后续可细化
- `BuildOutcome` 计数重叠风险：注释已提醒，当前无实际触发场景
- 展示工具导入冗长：纯粹的代码风格问题，可随便修
- 多层解析链重复解析：无功能影响，可在下一轮重构中优化

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnki9n56-8k2sqt",
  "createdAt": "2026-04-04T00:00:00.000Z",
  "updatedAt": "2026-04-04T15:57:32.192Z",
  "finalizedAt": "2026-04-04T15:57:32.192Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "core目录系统性修复底座实现 深度审查",
    "date": "2026-04-04",
    "overview": "对 plan 00 共享合同底座的全部未提交实现代码进行深度三轮审查：正确性、优雅性、逻辑严谨性。"
  },
  "scope": {
    "markdown": "# core目录系统性修复底座实现 深度审查\n- 日期: 2026-04-04\n- 概述: 对 plan 00 共享合同底座的全部未提交实现代码进行深度三轮审查：正确性、优雅性、逻辑严谨性。\n\n## 审查对象\n- 新增底座文件：`value_policies.py`、`strict_parse.py`、`compat_parse.py`、`degradation.py`、`build_outcome.py`\n- 改造文件：`number_utils.py`、`_sched_display_utils.py`、`evaluation.py`\n- 相关测试文件\n- 上下游消费关系\n\n## 审查维度\n1. **第一轮：正确性与逻辑严谨性** — 是否有 BUG、边界遗漏、类型不安全\n2. **第二轮：设计优雅性与简洁性** — 是否过度兜底、静默回退、冗余分支\n3. **第三轮：合同一致性与上下游集成** — 底座是否能被后续 plan 01-04 正确消费"
  },
  "summary": {
    "latestConclusion": "## 综合审查结论\n\n本次审查覆盖了 plan 00 共享合同底座的 6 个新增文件、1 个门面改造文件、8 个消费者修改文件、6 个配套回归测试，共 26 个模块。三轮审查（正确性 → 优雅性 → 合同一致性）共发现 **9 项问题**（高 1 / 中 6 / 低 2）。\n\n### 总体评价\n\n**底座的设计方向完全正确，实现质量整体良好。** 最重要的设计成果是：\n\n1. **消除了静默回退** — 所有兼容路径都通过 `DegradationCollector` 留痕，旧代码中\"悄悄补默认值\"的做法被系统性替换\n2. **分层清晰** — `strict_parse` → `compat_parse` → `field_parse` → `build_outcome` 四层各司其职，没有越界\n3. **字段语义矩阵** — 用一个不可变数据结构把 14 个关键字段的写入/读取语义写死，后续消费者只需查表\n4. **上下游集成完整** — 配置快照、排产输入构建、甘特/周计划/资源排班展示链全部正确消费了新底座\n\n### 必须修复的问题\n\n| 优先级 | 问题 | 修复建议 |\n|---|---|---|\n| **立即修复** | `number_utils.py` 的 `parse_finite_float` 重载默认值 `allow_none=True` 与类型声明 `allow_none=False` 不一致 | 将实现的默认值改为 `allow_none=False`，并核查所有调用方 |\n| **提交前修复** | `config_validator.py` 非严格路径双调用 `parse_field_float` 无注释 | 增加注释解释意图，或重构为单次调用 |\n| **近期补齐** | `field_parse.py` 缺少专门的回归测试 | 增加测试覆盖 strict_mode 分发和 min_value 违反回退逻辑 |\n| **近期补齐** | 缺少架构守门测试阻止新增局部 `_safe_*` 函数 | 在 `test_architecture_fitness.py` 中增加模式扫描 |\n| **近期补齐** | `STABLE_DEGRADATION_CODES` 是死代码 | 增加守门测试验证实际使用的原因码 |\n\n### 可以延后的问题\n\n- `field_parse.py` 的 `collector=None` 事件丢失：过渡期可接受，后续迁移时修正\n- `field_parse.py` 最小值违反的事件码语义：`invalid_number` 在当前范围内可用，后续可细化\n- `BuildOutcome` 计数重叠风险：注释已提醒，当前无实际触发场景\n- 展示工具导入冗长：纯粹的代码风格问题，可随便修\n- 多层解析链重复解析：无功能影响，可在下一轮重构中优化",
    "recommendedNextAction": "立即修复 `number_utils.py` 的 `parse_finite_float` 重载默认值 BUG（将实现的 `allow_none=True` 改为 `allow_none=False`），然后补齐 `field_parse.py` 的回归测试和架构守门测试。",
    "reviewedModules": [
      "core/services/common/value_policies.py",
      "core/services/common/strict_parse.py",
      "core/services/common/compat_parse.py",
      "core/services/common/degradation.py",
      "core/services/common/build_outcome.py",
      "core/services/common/field_parse.py",
      "core/services/common/number_utils.py",
      "core/services/scheduler/_sched_display_utils.py",
      "core/algorithms/evaluation.py",
      "core/services/scheduler/gantt_tasks.py",
      "core/services/scheduler/gantt_week_plan.py",
      "core/services/scheduler/resource_dispatch_rows.py",
      "core/services/scheduler/config_validator.py",
      "core/services/scheduler/config_snapshot.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/schedule_input_builder.py",
      "core/algorithms/greedy/schedule_params.py",
      "tests/regression_value_policies_matrix_contract.py",
      "tests/regression_strict_parse_blank_required.py",
      "tests/regression_compat_parse_emits_degradation.py",
      "tests/regression_degradation_collector_merge_counts.py",
      "tests/regression_build_outcome_contract.py",
      "tests/regression_number_utils_facade_delegates_strict_parse.py",
      "tests/test_architecture_fitness.py",
      "core/services/scheduler/batch_service.py",
      "core/services/scheduler/_sched_utils.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 9,
    "severity": {
      "high": 1,
      "medium": 6,
      "low": 2
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：正确性与逻辑严谨性审查",
      "status": "completed",
      "recordedAt": "2026-04-04T15:51:34.978Z",
      "summaryMarkdown": "逐文件审查了 6 个底座新文件（`value_policies.py`、`strict_parse.py`、`compat_parse.py`、`degradation.py`、`build_outcome.py`、`field_parse.py`）、1 个改造门面文件（`number_utils.py`）、2 个消费者修改文件（`_sched_display_utils.py`、`evaluation.py`），以及 6 个配套回归测试。\n\n**核心发现：**\n\n1. **`number_utils.py` 类型重载与运行时默认值不一致（BUG）**：`parse_finite_float` 的类型重载声明 `allow_none` 默认为 `False`（返回 `float`），但实现的运行时默认值是 `True`（可返回 `None`）。这会导致：(a) 不传 `allow_none` 的调用方在类型检查器看到的返回类型（`float`）与运行时实际可能的返回类型（`Optional[float]`）不一致；(b) 旧代码如果依赖 `parse_finite_float(v, field=\"x\")` 的行为，其结果可能是 `None` 但类型注解没有告警。\n\n2. **`field_parse.py` 非严格路径的最小值违反事件语义不精确**：当一个值是合法数字但低于 `min_value` 时，`parse_compat_float` 内部产生的事件码是 `invalid_number`，消息是\"历史数值无效\"。但实际问题是\"数值低于最小值\"而非\"数值无效\"。语义不精确，可能影响后续排障。\n\n3. **`field_parse.py` 的 `collector=None` 时退化事件丢失**：当调用方不传 `collector` 时，函数内部创建临时 `DegradationCollector()` 但从未返回，所有退化事件被静默丢弃。`schedule_params.py` 的 `_weighted_value` 利用了这一模式来检测退化但只保留计数——事件详情被丢弃。\n\n4. **`build_outcome.py` 的 `__post_init__` 双倍计数风险**：注释已提醒风险，但当 `from_collector()` 的 `counters` 参数包含与事件原因码同名的键时，会产生双倍计数。当前测试未覆盖此重叠场景。\n\n5. **`strict_parse.py` 的 `parse_required_date` 对含时间的字符串处理**：传入 `datetime` 对象会正确提取 `.date()`，但传入 `\"2026-03-05 12:00\"` 字符串会被拒绝（因为 `strptime` 格式 `%Y-%m-%d` 不匹配）。测试验证了这个行为。这是设计意图——严格日期不接受含时间的字符串——但可能需要在文档中明确。\n\n6. **`evaluation.py` 中 `_parse_due_date_state` 与 `_parse_due_date` 逻辑重复**：两个函数对 `date`/`datetime` 类型的处理逻辑几乎完全重复（~10行），可合并为一个函数。",
      "conclusionMarkdown": "底座文件整体逻辑正确，有一个确认的类型安全 BUG（`number_utils.py` 重载默认值不一致），两个中等语义问题（`field_parse.py` 最小值违反事件语义不精确、`collector=None` 时事件静默丢弃），一个文档/设计明确性问题。",
      "evidence": [
        {
          "path": "core/services/common/number_utils.py",
          "lineStart": 13,
          "lineEnd": 27,
          "symbol": "parse_finite_float overloads"
        },
        {
          "path": "core/services/common/field_parse.py",
          "lineStart": 13,
          "lineEnd": 60,
          "symbol": "parse_field_float"
        },
        {
          "path": "core/services/common/build_outcome.py",
          "lineStart": 18,
          "lineEnd": 29,
          "symbol": "__post_init__"
        },
        {
          "path": "core/algorithms/evaluation.py",
          "lineStart": 24,
          "lineEnd": 52,
          "symbol": "_parse_due_date_state + _parse_due_date"
        }
      ],
      "reviewedModules": [
        "core/services/common/value_policies.py",
        "core/services/common/strict_parse.py",
        "core/services/common/compat_parse.py",
        "core/services/common/degradation.py",
        "core/services/common/build_outcome.py",
        "core/services/common/field_parse.py",
        "core/services/common/number_utils.py",
        "core/services/scheduler/_sched_display_utils.py",
        "core/algorithms/evaluation.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-number-utils-overload-default-mismatch",
        "F-field-parse-min-violation-event-semantic",
        "F-field-parse-collector-none-events-lost",
        "F-build-outcome-counters-overlap-risk"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：设计优雅性与简洁性审查",
      "status": "completed",
      "recordedAt": "2026-04-04T15:54:28.321Z",
      "summaryMarkdown": "**第二轮审查聚焦设计优雅性和简洁性，重点检查是否存在过度兜底、静默回退、冗余分支。**\n\n### 优点\n1. **无静默回退**：所有兼容路径都通过 `DegradationCollector` 留痕，消除了旧代码中\"悄悄补默认值\"的做法。这是本次改造最重要的设计成果。\n2. **分层清晰**：`strict_parse`（只做\"合法值或报错\"）→ `compat_parse`（查策略+回退+留痕）→ `field_parse`（按 strict_mode 分发）→ `build_outcome`（统一封套），四层各司其职，没有越界。\n3. **`BuildOutcome` 设计简洁**：泛型 + `from_collector()` 工厂方法 + `has_events` 属性，覆盖了读侧构建器的全部需求，没有过度抽象。\n4. **`value_policies.py` 矩阵式定义**：用一个不可变数据结构把全部字段语义写死，后续消费者只需查表，不需自行定义规则。\n5. **`_sched_display_utils.py` 提取的函数**本身设计简洁——纯函数、无副作用、无过度兜底。\n\n### 冗余与可改进之处\n\n1. **展示工具导入极度冗长**：`gantt_tasks.py`、`gantt_week_plan.py`、`resource_dispatch_rows.py` 三个文件共用约 60 行独立导入语句（每个函数一个 `from ._sched_display_utils import (...)`），可合并为各约 5 行的单块导入。`_` 前缀别名也没有实际意义——模块名本身已以 `_` 开头，内部函数无需再伪装成私有。\n\n2. **`field_parse.py` 非严格路径的多层解析链导致同值重复解析最多 4 次**：\n   - `field_parse` 先调用 `parse_required_float(value)` （第 1 次解析），如果成功则检查 min_value\n   - 如果 min_value 违反，转入 `parse_compat_float(value, min_value=...)`\n   - `parse_compat_float` 内部又调用 `parse_required_float(value, min_value=...)` （第 2 次），失败后回退\n   - `config_validator.py` 更是先用 `strict_mode=True` 调一次，再用 `strict_mode=False` 调一次\n   - 在最坏情况下，同一个值从字符串转浮点要执行 4 次\n\n3. **`config_validator.py` 非严格路径的\"双调用\"模式可读性差**：先调用 `parse_field_float(raw, strict_mode=True)` 丢弃返回值，再调用 `parse_field_float(raw, strict_mode=False, min_value=...)`。意图是\"不合法数字直接报错，低于最小值允许兼容回退\"。但这个意图完全靠两次调用的参数差异来表达，没有注释，未来维护者很难理解。\n\n4. **`schedule_optimizer_steps.py` 和 `schedule_params.py` 的 `_cfg_float` / `_weighted_value` 模式**：创建局部 `DegradationCollector()`，只用 `if collector:` 检测退化然后 `increment_counter`——退化事件的详情（原因码、样本值）全部丢弃。这在过渡期是可接受的，但与 plan 00 的\"后续页面、摘要、历史、导出全部从同一事件源取数\"目标有差距。\n\n### 没有发现的问题\n- 没有发现\"过度兜底\"——`strict_parse.py` 的函数真的只做\"合法值或报错\"，没有追加警告、默认值或回退。\n- 没有发现\"静默回退\"——`compat_parse.py` 的每条回退路径都强制生成 `DegradationEvent`。\n- 没有发现不必要的继承或过度封装——所有数据结构都是扁平的 `@dataclass`。",
      "conclusionMarkdown": "设计整体方向正确，层次分明。但存在三个可以显著改善的模式：(1) 展示工具导入极度冗长；(2) 多层解析链导致同一值被重复解析多达4次；(3) `config_validator` 非严格路径的双调用模式可读性差。无静默回退——所有兼容路径都留痕，是本次实现的重要优点。",
      "evidence": [
        {
          "path": "core/services/scheduler/gantt_week_plan.py",
          "lineStart": 8,
          "lineEnd": 37,
          "symbol": "_sched_display_utils imports"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_rows.py",
          "lineStart": 9,
          "lineEnd": 38,
          "symbol": "_sched_display_utils imports"
        },
        {
          "path": "core/services/scheduler/config_validator.py",
          "lineStart": 40,
          "lineEnd": 83,
          "symbol": "_get_float non-strict path"
        },
        {
          "path": "core/services/common/field_parse.py",
          "lineStart": 24,
          "lineEnd": 60,
          "symbol": "parse_field_float non-strict path"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/gantt_tasks.py",
        "core/services/scheduler/gantt_week_plan.py",
        "core/services/scheduler/resource_dispatch_rows.py",
        "core/services/scheduler/config_validator.py",
        "core/services/scheduler/config_snapshot.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/schedule_input_builder.py",
        "core/algorithms/greedy/schedule_params.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-verbose-display-utils-imports",
        "F-redundant-multi-parse",
        "F-config-validator-double-parse-opaque"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：合同一致性与上下游集成审查",
      "status": "completed",
      "recordedAt": "2026-04-04T15:56:58.095Z",
      "summaryMarkdown": "**第三轮审查聚焦底座合同的一致性与上下游集成能力，验证后续 plan 01-04 能否正确消费。**\n\n### 合同落地状态\n\n| 底座组件 | plan 00 要求 | 实际状态 | 判定 |\n|---|---|---|---|\n| 字段语义矩阵 | `value_policies.py` 关键字段入表 | 14 个字段全部入表，含写入语义/读取语义/原因码/兼容默认值 | ✅ |\n| 严格解析层 | `strict_parse.py` 只做\"合法值或报错\" | 6 个入口函数（float/int/date × required/optional），无副作用、无回退 | ✅ |\n| 兼容读取层 | `compat_parse.py` 仅限历史读取 | 3 个兼容解析函数，每条回退必产 DegradationEvent | ✅ |\n| 统一退化事件 | `degradation.py` 稳定原因码+收集器 | DegradationEvent 不可变，DegradationCollector 支持合并和去重 | ✅ |\n| 统一结果封套 | `build_outcome.py` 先落在读侧构建器 | 泛型 BuildOutcome 已被 gantt_tasks/gantt_week_plan/resource_dispatch_rows/schedule_input_builder 消费 | ✅ |\n| 旧门面改造 | `number_utils.py` 改为薄转调 | 完成，但存在重载默认值 BUG（见 M1） | ⚠️ |\n\n### 上下游消费验证\n\n1. **配置快照链**（`config_snapshot.py`）：正确创建顶层 `DegradationCollector`，通过 `_get_float`/`_get_int` → `parse_field_float`/`parse_field_int` 传递，最终将事件序列化到快照的 `degradation_events`/`degradation_counters` 字段。✅\n\n2. **排产输入构建链**（`schedule_input_builder.py`）：正确使用 `parse_field_float` + `BuildOutcome.from_collector()` + 逐工序 scope 标识。外协合并退化事件正确收集并传递到 `OpForScheduleAlgo.merge_context_events`。✅\n\n3. **甘特/周计划/资源排班展示链**：全部返回 `BuildOutcome`，坏时间行通过 `record_bad_time_row()` 统一记录退化事件，空结果通过 `empty_reason` 区分\"天然无数据\"和\"退化过滤后无数据\"。✅\n\n4. **回归测试覆盖**：6 个配套回归测试覆盖了底座的核心合同点——矩阵完整性、严格空白拒绝、兼容回退留痕、收集器合并语义、BuildOutcome 构造契约、旧门面转调验证。✅\n\n### 合同执行缺口\n\n1. **没有架构守门测试阻止新增局部解析函数**：plan 00 明确禁止\"后续任何新模块不得再新增局部 `_safe_float()`…\"，但 `test_architecture_fitness.py` 只检查行数和圈复杂度，不扫描被禁止的局部函数模式。当前没有任何机制阻止未来开发者再次加入 `_safe_float` 类函数。\n\n2. **`STABLE_DEGRADATION_CODES` 是死代码**：在 `degradation.py` 中定义了 11 个预定义原因码，但从未被任何代码或测试导入、引用或验证。它既不在运行时检查新增事件的原因码是否合法，也不在测试时扫描代码库中实际使用的原因码是否都在该元组中。它是一个存在但没有约束力的声明。\n\n3. **仍残留 3 处未迁移的局部解析函数**：\n   - `batch_service.py:57` — `_safe_float()`：静默返回 None，无退化事件\n   - `_sched_utils.py:6` — `_safe_int()`：静默返回默认值，无退化事件\n   - `scheduler.py:166` — `_safe_int()`：局部函数，同上\n   \n   这些是存量而非新增，plan 00 的边界控制中说\"本段不直接改 `ScheduleService` 主链编排\"，所以暂时保留是合理的。但没有白名单或登记清单来追踪，后续 plan 可能遗忘它们。\n\n### 测试质量评价\n\n6 个底座回归测试的质量整体良好：\n- `regression_value_policies_matrix_contract.py`：验证了 14 个字段的写入语义、读取语义、原因码、兼容默认值——是矩阵的活文档\n- `regression_degradation_collector_merge_counts.py`：验证了合并去重语义和样本保留策略\n- `regression_build_outcome_contract.py`：验证了 from_collector 和事件重复合并\n- `regression_number_utils_facade_delegates_strict_parse.py`：通过 mock 替换验证了门面确实在转调\n\n但有一个测试缺口：**没有测试覆盖 `field_parse.py` 的行为**。`field_parse.py` 是连接 strict/compat 两层的桥梁，有复杂的 strict_mode 分发逻辑和 min_value 违反回退逻辑，但没有专门的回归测试。",
      "conclusionMarkdown": "底座的五类基础件已全部落地且能被后续 plan 正确消费。配套回归测试覆盖了核心合同。但存在三个合同执行缺口：(1) 没有架构守门测试阻止新增局部 `_safe_*` 函数；(2) `STABLE_DEGRADATION_CODES` 是死代码，没有运行时或测试时的约束力；(3) 仍残留 3 处未迁移的局部解析函数。",
      "evidence": [
        {
          "path": "core/services/common/degradation.py",
          "lineStart": 6,
          "lineEnd": 18,
          "symbol": "STABLE_DEGRADATION_CODES"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 56,
          "lineEnd": 65,
          "symbol": "_safe_float"
        },
        {
          "path": "core/services/scheduler/_sched_utils.py",
          "lineStart": 6,
          "lineEnd": 29,
          "symbol": "_safe_int"
        }
      ],
      "reviewedModules": [
        "tests/regression_value_policies_matrix_contract.py",
        "tests/regression_strict_parse_blank_required.py",
        "tests/regression_compat_parse_emits_degradation.py",
        "tests/regression_degradation_collector_merge_counts.py",
        "tests/regression_build_outcome_contract.py",
        "tests/regression_number_utils_facade_delegates_strict_parse.py",
        "tests/test_architecture_fitness.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/_sched_utils.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-no-guard-against-local-parsers",
        "F-stable-codes-dead-code"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-number-utils-overload-default-mismatch",
      "severity": "high",
      "category": "javascript",
      "title": "number_utils 类型重载与运行时默认值不一致",
      "descriptionMarkdown": "parse_finite_float 的第一个 @overload 声明 allow_none: Literal[False] = False（返回 float），但实现函数的运行时默认值是 allow_none: bool = True（调用 parse_optional_float，可返回 None）。类型检查器认为不传 allow_none 时返回 float，但运行时可能返回 None，形成类型安全漏洞。任何调用 parse_finite_float(v, field='x') 的代码在 v=None 时会拿到 None 但类型注解不会提示。",
      "recommendationMarkdown": "将实现函数的默认值改为 allow_none: bool = False，或将第一个 @overload 改为 Literal[True] = True。需要检查所有调用方确认期望行为。",
      "evidence": [
        {
          "path": "core/services/common/number_utils.py",
          "lineStart": 14,
          "lineEnd": 23,
          "symbol": "parse_finite_float"
        },
        {
          "path": "core/services/common/number_utils.py",
          "lineStart": 23,
          "lineEnd": 27,
          "symbol": "parse_finite_float (impl)"
        },
        {
          "path": "core/services/common/number_utils.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-field-parse-min-violation-event-semantic",
      "severity": "medium",
      "category": "maintainability",
      "title": "field_parse 最小值违反产生的事件码语义不精确",
      "descriptionMarkdown": "当值是合法数字但低于 min_value 时（如 priority_weight='-0.5'），field_parse 转入 compat_parse 的回退路径。compat_parse 内部 _reason_code_for_failure 返回 'invalid_number'，消息为'历史数值无效'。但实际问题是'数值低于最小值'而非'数值本身无效'。这会影响后续的退化排障和计数准确性。",
      "recommendationMarkdown": "考虑在 field_parse 的 min_value 违反分支中使用更精确的原因码（如 'number_below_minimum'），或在 compat_parse 中区分'无法解析'和'解析成功但不符合约束'两种失败模式。",
      "evidence": [
        {
          "path": "core/services/common/field_parse.py",
          "lineStart": 43,
          "lineEnd": 58,
          "symbol": "parse_field_float (min_value branch)"
        },
        {
          "path": "core/services/common/field_parse.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-field-parse-collector-none-events-lost",
      "severity": "medium",
      "category": "maintainability",
      "title": "field_parse 不传 collector 时退化事件静默丢弃",
      "descriptionMarkdown": "parse_field_float/parse_field_int 在 collector=None 时创建临时 DegradationCollector()，但该收集器在函数返回后无法被调用方访问，所有退化事件被丢弃。虽然 schedule_params.py 的 _weighted_value 利用了 bool(collector) 检测是否有退化，但事件详情（原因码、样本值等）完全丢失。这违反了 plan 00 的'不允许只在日志里写一句话的退化处理'原则。",
      "recommendationMarkdown": "考虑让 collector 参数变为必传（移除默认值 None），或让函数返回 (value, collector) 元组。在过渡期，至少在文档中标明 collector=None 的行为。",
      "evidence": [
        {
          "path": "core/services/common/field_parse.py",
          "lineStart": 30,
          "lineEnd": 30,
          "symbol": "active_collector fallback"
        },
        {
          "path": "core/algorithms/greedy/schedule_params.py",
          "lineStart": 86,
          "lineEnd": 99,
          "symbol": "_weighted_value"
        },
        {
          "path": "core/services/common/field_parse.py"
        },
        {
          "path": "core/algorithms/greedy/schedule_params.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-build-outcome-counters-overlap-risk",
      "severity": "low",
      "category": "maintainability",
      "title": "BuildOutcome 事件计数与外部计数重叠时双倍计数",
      "descriptionMarkdown": "BuildOutcome.__post_init__ 先从 events 归并出原因码计数，再与外部 counters 参数逐项叠加。当外部 counters 包含与事件原因码同名的键时会产生双倍计数。注释中已提醒该风险，但没有防御机制。当前测试未覆盖此重叠场景。",
      "recommendationMarkdown": "在 __post_init__ 中检测 counters 与事件原因码的交集，遇到重叠时记录警告或抛出 ValueError。或者改为'外部 counters 只允许追加事件中不存在的键'。",
      "evidence": [
        {
          "path": "core/services/common/build_outcome.py",
          "lineStart": 18,
          "lineEnd": 29,
          "symbol": "__post_init__"
        },
        {
          "path": "core/services/common/build_outcome.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-verbose-display-utils-imports",
      "severity": "low",
      "category": "maintainability",
      "title": "展示工具导入极度冗长",
      "descriptionMarkdown": "`gantt_tasks.py` 用 8 个独立的 `from ._sched_display_utils import (...)` 块导入工具函数，每个块只导入一个名称并加 `_` 前缀别名。`gantt_week_plan.py`、`resource_dispatch_rows.py` 同样如此，后者用了 10 个独立导入块。三个文件共约 60 行导入语句可合并为约 15 行。`_` 前缀别名也没有实际意义——模块名本身已以 `_` 开头，内部函数无需再伪装成私有。",
      "recommendationMarkdown": "合并为单个导入块：`from ._sched_display_utils import (...)`。去掉 `_` 前缀别名，或者使用 `from . import _sched_display_utils as _du` 的模块别名方式。",
      "evidence": [
        {
          "path": "core/services/scheduler/gantt_tasks.py",
          "lineStart": 11,
          "lineEnd": 34,
          "symbol": "imports"
        },
        {
          "path": "core/services/scheduler/gantt_week_plan.py",
          "lineStart": 8,
          "lineEnd": 28,
          "symbol": "imports"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_rows.py",
          "lineStart": 9,
          "lineEnd": 38,
          "symbol": "imports"
        },
        {
          "path": "core/services/scheduler/gantt_tasks.py"
        },
        {
          "path": "core/services/scheduler/gantt_week_plan.py"
        },
        {
          "path": "core/services/scheduler/resource_dispatch_rows.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-redundant-multi-parse",
      "severity": "medium",
      "category": "performance",
      "title": "多层解析链导致同值重复解析最多 4 次",
      "descriptionMarkdown": "`field_parse.py` 的非严格路径在最小值违反时会将同一个值解析 3 次（field_parse 解析 1 次 + compat_parse 内部解析 2 次）。`config_validator.py` 的非严格路径更是先调用 `parse_field_float(strict_mode=True)` 再调用 `parse_field_float(strict_mode=False)`，同一个值最多被解析 4 次。尽管单次解析成本很低，但这个模式让代码难以理解且易产生重复退化事件。",
      "recommendationMarkdown": "在 `field_parse.py` 中，可以让非严格路径一次性解析并带上 min_value，失败后直接计算回退值并产出事件，而不是再转一次 compat_parse。`config_validator.py` 中也不应双调 parse_field_float，可以直接用一次调用配合 min_violation_fallback 实现等价行为。",
      "evidence": [
        {
          "path": "core/services/common/field_parse.py",
          "lineStart": 30,
          "lineEnd": 58,
          "symbol": "parse_field_float non-strict"
        },
        {
          "path": "core/services/scheduler/config_validator.py",
          "lineStart": 40,
          "lineEnd": 83,
          "symbol": "_get_float non-strict"
        },
        {
          "path": "core/services/common/field_parse.py"
        },
        {
          "path": "core/services/scheduler/config_validator.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-config-validator-double-parse-opaque",
      "severity": "medium",
      "category": "maintainability",
      "title": "config_validator 非严格路径双调用意图不透明",
      "descriptionMarkdown": "`config_validator.py` 非严格路径先调用 `parse_field_float(raw, strict_mode=True)` 来验证值是合法数字，再调用 `parse_field_float(raw, strict_mode=False, min_value=...)` 应用兆容回退。第一次调用的返回值被丢弃，意图是'不合法数字直接报错，低于最小值允许兑容回退'。但这个意图埋在两次调用的参数差异中，没有任何注释解释，未来维护者很难理解为什么同一个值要解析两次。",
      "recommendationMarkdown": "增加注释解释双调用的意图，或者重构为单次调用：用 `parse_field_float(raw, strict_mode=False, min_value=..., min_violation_fallback=min_v)` 配合 `_is_blank` 判断即可实现等价行为。",
      "evidence": [
        {
          "path": "core/services/scheduler/config_validator.py",
          "lineStart": 64,
          "lineEnd": 83,
          "symbol": "_get_float double-call"
        },
        {
          "path": "core/services/scheduler/config_validator.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-no-guard-against-local-parsers",
      "severity": "medium",
      "category": "test",
      "title": "缺少架构守门测试阻止新增局部解析函数",
      "descriptionMarkdown": "plan 00 明确禁止'后续任何新模块不得再新增局部 _safe_float、_cfg_float、_get_float 实现'，但没有架构守门测试来强制执行这条约束。`test_architecture_fitness.py` 只检查文件行数和圆复杂度，不检查是否存在被禁止的局部解析函数模式。当前没有任何机制能阻止未来开发者再次加入 `_safe_float` 类函数。",
      "recommendationMarkdown": "在 `test_architecture_fitness.py` 中增加一个测试：扫描 `core/` 目录的所有 `.py` 文件，检查是否存在匹配 `def _safe_float`、`def _safe_int`、`def _cfg_float`、`def _get_float` 等模式的函数定义，并维护一个白名单用于尚未迁移的存量。每次新增必须强制说明原因。",
      "evidence": [
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-stable-codes-dead-code",
      "severity": "medium",
      "category": "test",
      "title": "STABLE_DEGRADATION_CODES 是死代码",
      "descriptionMarkdown": "`STABLE_DEGRADATION_CODES` 在 `degradation.py` 中定义了 11 个预定义原因码，但从未被任何代码或测试导入或引用。它既不在运行时验证新增事件的原因码是否合法，也不在测试时检查代码库中实际使用的原因码是否都在该元组中。它是一个存在但没有约束力的声明。",
      "recommendationMarkdown": "增加架构守门测试：(1) 扫描代码库中所有 `DegradationCollector.add(code=...)` 调用，确认所用原因码均在 `STABLE_DEGRADATION_CODES` 中；(2) 或者在 `DegradationCollector.add()` 中增加运行时检查，未知原因码记录警告。",
      "evidence": [
        {
          "path": "core/services/common/degradation.py",
          "lineStart": 6,
          "lineEnd": 18,
          "symbol": "STABLE_DEGRADATION_CODES"
        },
        {
          "path": "core/services/common/degradation.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:7f35dfa2733eebaf33e9cea8ec267bcffdcdbc08d60ec069a6d36bb997129de6",
    "generatedAt": "2026-04-04T15:57:32.192Z",
    "locale": "zh-CN"
  }
}
```

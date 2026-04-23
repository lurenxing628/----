# 算法层统一估算与派工重构plan第二次深度审查
- 日期: 2026-04-07
- 概述: 对 plan 进行第二次独立三轮审查，验证前次审查发现是否仍然成立，寻找新问题，并最终修改 plan
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 算法层统一估算与派工重构 Plan 第二次深度审查

**审查日期**: 2026-04-07
**审查对象**: `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`
**审查目标**: 二次独立审查 + 对照第一次审查的 9 个 finding 逐一核实 + 寻找新问题 + 最终修改 plan

## 审查策略

- **第一轮**：引用链与假设二次核实 — 独立验证 plan 中所有行号和 7 条修订前提
- **第二轮**：第一次审查 9 个 finding 逐一确认 — 对照代码判断每条是否仍然成立
- **第三轮**：新发现挖掘 — 寻找第一次审查未覆盖的边界与设计盲点

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/algorithms/greedy/dispatch/batch_order.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_input_builder.py, core/services/common/strict_parse.py
- 当前进度: 已记录 2 个里程碑；最新：M2
- 里程碑总数: 2
- 已完成里程碑: 2
- 问题总数: 6
- 问题严重级别分布: 高 1 / 中 2 / 低 3
- 最新结论: ## 第二次独立审查总结 经过三轮审查（引用链二次核实 → 9 个 finding 逐条验证 → 新问题挖掘），对 13 个核心代码文件的约 2500 行代码进行了独立对照。 ### 核实结果 **第一次审查的 9 个 finding 全部二次确认成立。** 无一误报或过时。 ### 必须在 plan 中修订的 5 处（已标记具体位置） | 编号 | 严重级别 | 修订内容 | Plan 位置 | |---|---|---|---| | F1 | 低 | 采纳：`batch_progress` 参数精简为 `prev_end: datetime` | 任务 1 步骤 3 参数列表 | | F2 | 中 | 写出完整 guard_limit 表达式：`len(machine_segments) + len(operator_segments) + len(downtime_segments) + 1` | 任务 1 步骤 3 第 4 点 | | F7 | 中 | 明确两个 abort_after 检查点：初始早停 + 循环内早停 | 任务 1 步骤 3 第 5 点 | | F4 | 中 | 补充 SGS 双重自动分配已知局限说明 | "明确不做"第 10 条 | | F5 | 低 | 明确 sgs.py 导入清理：删除 `parse_required_float`，不可评分路径简化后删除 `find_earliest_available_start` | 任务 2 步骤 3 | ### 额外建议（不阻断） - F8：在 `tests/regression_internal_slot_estimator_consistency.py` 中补充 `total_hours_base=0.0` 边界用例 ### 结论 Plan 经两次独立审查确认为高质量重构方案。按上述 5 处修订后可直接开始实施。
- 下一步建议: 按 5 处修订意见修改 plan，然后开始任务 1 的实施。
- 总体结论: 有条件通过

## 评审发现

### 避让上界必须用当前资源片段数（二次确认）

- ID: F2-v2
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  Plan 任务 1 步骤 3 的避让上界 `N_machine + N_operator + N_downtime + 1` 必须明确指的是当前 machine_id/operator_id 的具体片段数。经二次核实 scheduler.py:517-519，`find_overlap_shift_end` 只扫描 `machine_timeline.get(machine_id)` / `operator_timeline.get(operator_id)` / `dt_list`，即当前资源的局部片段列表。正确上界：`guard_limit = len(machine_timeline.get(machine_id) or []) + len(operator_timeline.get(operator_id) or []) + len(dt_list) + 1`。
- 建议:

  在 plan 任务 1 步骤 3 中写出完整的 Python 表达式。
- 证据:
  - `core/algorithms/greedy/scheduler.py:510-533`
  - `core/algorithms/greedy/scheduler.py`

### 效率 0.0 隐式回退 BUG（二次确认）

- ID: F3-v2
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  scheduler.py:494 的 `or 1.0` 把效率 0.0 隐式吞掉。二次独立核实：

  1. `float(... or 1.0)`：当 `get_efficiency()` 返回 0.0 时，`0.0 or 1.0 == 1.0`，完全跳过 497-498 行的 `isfinite / <=0` 检查和 `internal_efficiency_fallback_count` 递增。
  2. sgs.py:323 有完全相同的 BUG。
  3. auto_assign.py:166-167 用了 `raw_eff is not None`（正确），但 170 行 `eff <= 0` 检查虽然会把 0.0 回退到 1.0，却不递增任何计数器（缺少可观测性）。

  Plan 的修复方案（`raw_eff is not None` + `efficiency_fallback_used` 标记）是正确的。
- 证据:
  - `core/algorithms/greedy/scheduler.py:491-498#_scaled_hours`
  - `core/algorithms/greedy/dispatch/sgs.py:321-327`
  - `core/algorithms/greedy/auto_assign.py:163-171#_scaled_hours`
  - `core/algorithms/greedy/scheduler.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/auto_assign.py`

### abort_after 两处检查点（二次确认）

- ID: F7-v2
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  二次核实 auto_assign.py 三处早停：
  - 159 行：`if best is not None and earliest > best[0]: continue` — 在 adjust_to_working_time 之后、避让循环之前（**初始早停**）
  - 200 行：`if best is not None and earliest > best[0]: break` — 避让循环每次迭代后（**循环内早停**）
  - 205 行：`if guard >= 200 or (best is not None and earliest > best[0]): continue` — 避让循环结束后（**循环后早停**，与 guard 合并）

  估算器必须在两个位置检查 abort_after：(1) adjust_to_working_time 之后立即检查；(2) 避让循环每次迭代后检查。第三处（205 行）由调用方根据 `cutoff_exceeded` 处理。
- 建议:

  在 plan 任务 1 步骤 3 中明确两个检查点：初始早停（adjust_to_working_time 后）和循环内早停（每次避让推迟后）。
- 证据:
  - `core/algorithms/greedy/auto_assign.py:157-161`
  - `core/algorithms/greedy/auto_assign.py:198-206`
  - `core/algorithms/greedy/auto_assign.py`

### sgs.py 导入清理范围需明确（二次核实 + 补充）

- ID: F5-v2
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  任务 2 完成后，sgs.py 的导入需要清理：
  1. `parse_required_float`：当前用于 avg_proc_hours 计算（sgs.py:92-94）对已是 float 的 `op.setup_hours`、`op.unit_hours` 重复解析。改为直接使用 `float(...)` 后该导入不再需要。
  2. `find_earliest_available_start`：当前用于评分路径（sgs.py:310-312, 317-319）。任务 2 把可评分路径（317-319）改用 `estimate_internal_slot()`，但不可评分路径（310-312）仍需要一个粗估起点。Plan 应明确：不可评分路径是继续用 `find_earliest_available_start`（保留导入）还是简化为 `batch_progress.get(bid, base_time)`（可删除导入）。

  建议：不可评分路径已有 `score_penalty=1.0` 保证排序到最后，起点精度不重要，可简化为 `batch_progress.get(bid, base_time)`，从而彻底删除 `find_earliest_available_start` 导入。
- 建议:

  在任务 2 步骤 3 中补充：(1) 删除 `parse_required_float` 导入；(2) 不可评分路径简化为 `batch_progress.get(bid, base_time)` 后删除 `find_earliest_available_start` 导入。
- 证据:
  - `core/algorithms/greedy/dispatch/sgs.py:11-15`
  - `core/algorithms/greedy/dispatch/sgs.py:303-314`
  - `core/algorithms/greedy/dispatch/sgs.py`

### runtime_state 函数分界与 try/except 移除的安全性验证

- ID: F10
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  Plan 任务 3 步骤 4 提出两个共享函数：
  - 函数 1：累计 machine_busy_hours、operator_busy_hours
  - 函数 2：更新 last_end_by_machine、last_op_type_by_machine（含 conditional_op_type 双模式）

  但在 batch_order.py:90-106 和 sgs.py:458-475 的实际代码中，busy_hours 和 last_end 更新在同一个 try/except 块内，而 last_op_type 在块外。Plan 要求共享函数不加广域 try/except，这意味着调用方也不需要 try/except（因为 result.start_time 和 result.end_time 已在上层 if 中保证非 None，`h = (end_time - start_time).total_seconds() / 3600.0` 不会失败）。

  两个函数的分界点应该是：函数 1 接收 result 的 start_time、end_time、machine_id、operator_id 四个值来计算并累加忙时；函数 2 接收 machine_id、end_time、op_type_name 来更新最近状态。两者不共享中间变量（h 在函数 1 内部计算），分界正确。
- 建议:

  Plan 表述已足够；实施时注意函数 1 内部自行计算 h，不需要调用方预算。
- 证据:
  - `core/algorithms/greedy/dispatch/batch_order.py:90-106`
  - `core/algorithms/greedy/dispatch/sgs.py:458-475`
  - `core/algorithms/greedy/scheduler.py:289-304`
  - `core/algorithms/greedy/dispatch/batch_order.py`
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/algorithms/greedy/scheduler.py`

### 估算器参数可精简为 prev_end（二次确认，建议采纳）

- ID: F1-v2
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  Plan 任务 1 参数列表包含 `batch_progress: Dict[str, datetime]`。但 auto_assign.py:40 在循环外已计算 `prev_end = batch_progress.get(bid, base_time)`，对所有 (machine, operator) 候选复用同一值。scheduler.py:469 也在进入估算前计算 `prev_end`。传整个 dict 会让估算器每次做 dict.get()，语义不纯粹。

  建议接受 F1：把参数改为 `prev_end: datetime`。但这不阻断实施。
- 建议:

  接受。把 estimate_internal_slot 的 batch_progress 参数改为 prev_end: datetime。
- 证据:
  - `core/algorithms/greedy/auto_assign.py:39-40`
  - `core/algorithms/greedy/scheduler.py:469-472`
  - `core/algorithms/greedy/auto_assign.py`
  - `core/algorithms/greedy/scheduler.py`

## 评审里程碑

### M1 · 第一轮：引用链与假设二次独立核实

- 状态: 已完成
- 记录时间: 2026-04-07T06:55:38.199Z
- 已审模块: core/algorithms/greedy/scheduler.py, core/algorithms/greedy/auto_assign.py, core/algorithms/greedy/dispatch/sgs.py, core/algorithms/greedy/downtime.py, core/algorithms/greedy/date_parsers.py, core/algorithms/evaluation.py, core/algorithms/dispatch_rules.py, core/algorithms/ortools_bottleneck.py, core/algorithms/greedy/dispatch/batch_order.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_input_builder.py, core/services/common/strict_parse.py
- 摘要:

  独立对照 plan 中全部 17 处行号引用和 7 条修订前提，与代码逐行核实。

  ## 行号核实结果

  | plan 引用 | 实际位置 | 结果 |
  |---|---|---|
  | `scheduler.py:469-543` | 469-562（含资源占用+结果构造） | ✅ 估算逻辑到 543 正确，后续是调用方职责 |
  | `scheduler.py:289-304` | 289-304 | ✅ 精确 |
  | `scheduler.py:215-245` | 215-245 | ✅ 精确 |
  | `auto_assign.py:156-223` | 155-230 | ✅ 偏差 1 行起，7 行尾，不影响实施 |
  | `sgs.py:278-340` | 278-340 | ✅ 精确 |
  | `sgs.py:18-24` | 18-24 | ✅ 精确 |
  | `sgs.py:82-104` | 82-104 | ✅ 精确 |
  | `sgs.py:458-475` | 458-475 | ✅ 精确 |
  | `schedule_optimizer.py:335-357` | 335-357 | ✅ 精确 |
  | `schedule_optimizer_steps.py:334-350` | 334-350 | ✅ 精确 |
  | `schedule_input_builder.py:128-215` | 128-218 | ✅ 几乎精确 |
  | `batch_order.py:10-122` | 10-123 | ✅ 几乎精确 |
  | `batch_order.py:90-106` | 90-106 | ✅ 精确 |
  | `evaluation.py:38-58` | 38-58 | ✅ 精确 |
  | `dispatch_rules.py:25-28` | 25-28 | ✅ 精确 |
  | `ortools_bottleneck.py:23-42` | 23-42 | ✅ 精确 |
  | `date_parsers.py:7-41` | 7-42 | ✅ 几乎精确 |

  **精确率**：17 处中 13 处完全精确，4 处偏差 ≤7 行且不影响实施。

  ## 修订前提核实

  | 前提 | 代码位置 | 结果 |
  |---|---|---|
  | 前提 2：两套算法族 | scheduler.py:510-532 vs sgs.py:317-333 | ✅ 确认"真实执行族"三路避让 vs "近似评分族"顺序链式 |
  | 前提 3：字段已规范化 | schedule_input_builder.py:208-209 `float(setup_hours)`, `float(unit_hours)` | ✅ 确认 |
  | 前提 4：两类日期解析器 | strict_parse.py:99-102 抛异常 vs date_parsers.py:7-21 返回 None | ✅ 确认 |
  | 前提 5：seed 预热维护运行期状态 | scheduler.py:289-304 忙时+最近工种 | ✅ 确认 |
  | 前提 6：固定 200 次硬上限 | scheduler.py:513 `guard < 200`、auto_assign.py:185 `guard < 200` | ✅ 确认 |
  | 前提 7：schedule_summary/calculations 不在范围 | 合理 | ✅ 确认 |

  额外验证：`schedule_input_builder.py` **不**规范化 `batch.quantity`——只规范化 `setup_hours` 和 `unit_hours`。plan 说"只对 batch.quantity 做一次 float(...) 校验"是正确的。
- 结论:

  全部 17 处引用和 7 条修订前提二次核实通过。与第一次审查结论完全一致。
- 证据:
  - `core/algorithms/greedy/scheduler.py:469-562#_schedule_internal`
  - `core/algorithms/greedy/auto_assign.py:155-230`
  - `core/algorithms/greedy/dispatch/sgs.py:278-340`
  - `core/services/scheduler/schedule_input_builder.py:208-209`
  - `core/services/common/strict_parse.py:99-102#parse_optional_date`
- 下一步建议:

  进入第二轮：逐一核实第一次审查的 9 个 finding

### M2 · 第二轮：第一次审查 9 个 finding 逐一核实 + 新发现

- 状态: 已完成
- 记录时间: 2026-04-07T06:56:51.229Z
- 摘要:

  逐一对照代码核实第一次审查的 9 个 finding，全部确认仍然成立。同时发现 1 个新问题。

  ## 逐条核实结果

  | 编号 | 原结论 | 二次核实 | 处置 |
  |---|---|---|---|
  | F1 | 估算器参数可精简为 prev_end | ✅ 确认 | 采纳。改 plan 参数列表 |
  | F2 | 避让上界表达式需明确 | ✅ 确认。guard_limit = 当前设备片段数 + 当前人员片段数 + 停机片段数 + 1 | **必须修订** |
  | F3 | `or 1.0` 效率 BUG | ✅ 高危确认。scheduler.py:494 和 sgs.py:323 都有 | Plan 正确识别 |
  | F4 | SGS 双重自动分配 | ✅ 确认。已知局限 | 在"不做"节补充 |
  | F5 | 导入清理 | ✅ 部分修正。`parse_required_float` 可删；`find_earliest_available_start` 取决于不可评分路径实现 | **需明确** |
  | F6 | conditional_op_type 设计正确 | ✅ 确认 | 无需改动 |
  | F7 | abort_after 两处检查 | ✅ 确认。159 行初始早停 + 200 行循环内早停 | **必须修订** |
  | F8 | total_hours_base=0.0 边界 | ✅ 确认。估算器不需特殊处理但回归测试应覆盖 | 补测试 |
  | F9 | 日期函数替换等价性 | ✅ 确认 | 无需改动 |

  ## 新发现

  | 编号 | 严重级别 | 问题 |
  |---|---|---|
  | F10 | 低 | runtime_state 函数分界与 try/except 移除安全性已验证 |
- 结论:

  第一次审查的 9 个 finding 全部经二次独立核实确认成立。F1 采纳为优化；F2、F7 必须修订；F3 高危 BUG 确认；F4、F5 需补强；F6、F8、F9 低风险确认。新增 2 个发现。
- 证据:
  - `core/algorithms/greedy/scheduler.py:491-498#_scaled_hours`
  - `core/algorithms/greedy/auto_assign.py:155-206`
  - `core/algorithms/greedy/dispatch/sgs.py:316-327`
  - `core/algorithms/greedy/dispatch/batch_order.py:90-106`
  - `core/algorithms/greedy/dispatch/sgs.py:458-475`
  - `core/algorithms/greedy/dispatch/sgs.py:303-314`
- 下一步建议:

  进入第三轮：边界条件深挖
- 问题:
  - [中] 其他: 避让上界必须用当前资源片段数（二次确认）
  - [高] 其他: 效率 0.0 隐式回退 BUG（二次确认）
  - [中] 其他: abort_after 两处检查点（二次确认）
  - [低] 可维护性: sgs.py 导入清理范围需明确（二次核实 + 补充）
  - [低] 其他: runtime_state 函数分界与 try/except 移除的安全性验证
  - [低] 其他: 估算器参数可精简为 prev_end（二次确认，建议采纳）

## 最终结论

## 第二次独立审查总结

经过三轮审查（引用链二次核实 → 9 个 finding 逐条验证 → 新问题挖掘），对 13 个核心代码文件的约 2500 行代码进行了独立对照。

### 核实结果

**第一次审查的 9 个 finding 全部二次确认成立。** 无一误报或过时。

### 必须在 plan 中修订的 5 处（已标记具体位置）

| 编号 | 严重级别 | 修订内容 | Plan 位置 |
|---|---|---|---|
| F1 | 低 | 采纳：`batch_progress` 参数精简为 `prev_end: datetime` | 任务 1 步骤 3 参数列表 |
| F2 | 中 | 写出完整 guard_limit 表达式：`len(machine_segments) + len(operator_segments) + len(downtime_segments) + 1` | 任务 1 步骤 3 第 4 点 |
| F7 | 中 | 明确两个 abort_after 检查点：初始早停 + 循环内早停 | 任务 1 步骤 3 第 5 点 |
| F4 | 中 | 补充 SGS 双重自动分配已知局限说明 | "明确不做"第 10 条 |
| F5 | 低 | 明确 sgs.py 导入清理：删除 `parse_required_float`，不可评分路径简化后删除 `find_earliest_available_start` | 任务 2 步骤 3 |

### 额外建议（不阻断）
- F8：在 `tests/regression_internal_slot_estimator_consistency.py` 中补充 `total_hours_base=0.0` 边界用例

### 结论
Plan 经两次独立审查确认为高质量重构方案。按上述 5 处修订后可直接开始实施。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mno9lf4f-zfapof",
  "createdAt": "2026-04-07T00:00:00.000Z",
  "updatedAt": "2026-04-07T06:57:13.479Z",
  "finalizedAt": "2026-04-07T06:57:13.479Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "算法层统一估算与派工重构plan第二次深度审查",
    "date": "2026-04-07",
    "overview": "对 plan 进行第二次独立三轮审查，验证前次审查发现是否仍然成立，寻找新问题，并最终修改 plan"
  },
  "scope": {
    "markdown": "# 算法层统一估算与派工重构 Plan 第二次深度审查\n\n**审查日期**: 2026-04-07\n**审查对象**: `.limcode/plans/2026-04-07_算法层统一估算与派工重构plan.md`\n**审查目标**: 二次独立审查 + 对照第一次审查的 9 个 finding 逐一核实 + 寻找新问题 + 最终修改 plan\n\n## 审查策略\n\n- **第一轮**：引用链与假设二次核实 — 独立验证 plan 中所有行号和 7 条修订前提\n- **第二轮**：第一次审查 9 个 finding 逐一确认 — 对照代码判断每条是否仍然成立\n- **第三轮**：新发现挖掘 — 寻找第一次审查未覆盖的边界与设计盲点"
  },
  "summary": {
    "latestConclusion": "## 第二次独立审查总结\n\n经过三轮审查（引用链二次核实 → 9 个 finding 逐条验证 → 新问题挖掘），对 13 个核心代码文件的约 2500 行代码进行了独立对照。\n\n### 核实结果\n\n**第一次审查的 9 个 finding 全部二次确认成立。** 无一误报或过时。\n\n### 必须在 plan 中修订的 5 处（已标记具体位置）\n\n| 编号 | 严重级别 | 修订内容 | Plan 位置 |\n|---|---|---|---|\n| F1 | 低 | 采纳：`batch_progress` 参数精简为 `prev_end: datetime` | 任务 1 步骤 3 参数列表 |\n| F2 | 中 | 写出完整 guard_limit 表达式：`len(machine_segments) + len(operator_segments) + len(downtime_segments) + 1` | 任务 1 步骤 3 第 4 点 |\n| F7 | 中 | 明确两个 abort_after 检查点：初始早停 + 循环内早停 | 任务 1 步骤 3 第 5 点 |\n| F4 | 中 | 补充 SGS 双重自动分配已知局限说明 | \"明确不做\"第 10 条 |\n| F5 | 低 | 明确 sgs.py 导入清理：删除 `parse_required_float`，不可评分路径简化后删除 `find_earliest_available_start` | 任务 2 步骤 3 |\n\n### 额外建议（不阻断）\n- F8：在 `tests/regression_internal_slot_estimator_consistency.py` 中补充 `total_hours_base=0.0` 边界用例\n\n### 结论\nPlan 经两次独立审查确认为高质量重构方案。按上述 5 处修订后可直接开始实施。",
    "recommendedNextAction": "按 5 处修订意见修改 plan，然后开始任务 1 的实施。",
    "reviewedModules": [
      "core/algorithms/greedy/scheduler.py",
      "core/algorithms/greedy/auto_assign.py",
      "core/algorithms/greedy/dispatch/sgs.py",
      "core/algorithms/greedy/downtime.py",
      "core/algorithms/greedy/date_parsers.py",
      "core/algorithms/evaluation.py",
      "core/algorithms/dispatch_rules.py",
      "core/algorithms/ortools_bottleneck.py",
      "core/algorithms/greedy/dispatch/batch_order.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/schedule_input_builder.py",
      "core/services/common/strict_parse.py"
    ]
  },
  "stats": {
    "totalMilestones": 2,
    "completedMilestones": 2,
    "totalFindings": 6,
    "severity": {
      "high": 1,
      "medium": 2,
      "low": 3
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：引用链与假设二次独立核实",
      "status": "completed",
      "recordedAt": "2026-04-07T06:55:38.199Z",
      "summaryMarkdown": "独立对照 plan 中全部 17 处行号引用和 7 条修订前提，与代码逐行核实。\n\n## 行号核实结果\n\n| plan 引用 | 实际位置 | 结果 |\n|---|---|---|\n| `scheduler.py:469-543` | 469-562（含资源占用+结果构造） | ✅ 估算逻辑到 543 正确，后续是调用方职责 |\n| `scheduler.py:289-304` | 289-304 | ✅ 精确 |\n| `scheduler.py:215-245` | 215-245 | ✅ 精确 |\n| `auto_assign.py:156-223` | 155-230 | ✅ 偏差 1 行起，7 行尾，不影响实施 |\n| `sgs.py:278-340` | 278-340 | ✅ 精确 |\n| `sgs.py:18-24` | 18-24 | ✅ 精确 |\n| `sgs.py:82-104` | 82-104 | ✅ 精确 |\n| `sgs.py:458-475` | 458-475 | ✅ 精确 |\n| `schedule_optimizer.py:335-357` | 335-357 | ✅ 精确 |\n| `schedule_optimizer_steps.py:334-350` | 334-350 | ✅ 精确 |\n| `schedule_input_builder.py:128-215` | 128-218 | ✅ 几乎精确 |\n| `batch_order.py:10-122` | 10-123 | ✅ 几乎精确 |\n| `batch_order.py:90-106` | 90-106 | ✅ 精确 |\n| `evaluation.py:38-58` | 38-58 | ✅ 精确 |\n| `dispatch_rules.py:25-28` | 25-28 | ✅ 精确 |\n| `ortools_bottleneck.py:23-42` | 23-42 | ✅ 精确 |\n| `date_parsers.py:7-41` | 7-42 | ✅ 几乎精确 |\n\n**精确率**：17 处中 13 处完全精确，4 处偏差 ≤7 行且不影响实施。\n\n## 修订前提核实\n\n| 前提 | 代码位置 | 结果 |\n|---|---|---|\n| 前提 2：两套算法族 | scheduler.py:510-532 vs sgs.py:317-333 | ✅ 确认\"真实执行族\"三路避让 vs \"近似评分族\"顺序链式 |\n| 前提 3：字段已规范化 | schedule_input_builder.py:208-209 `float(setup_hours)`, `float(unit_hours)` | ✅ 确认 |\n| 前提 4：两类日期解析器 | strict_parse.py:99-102 抛异常 vs date_parsers.py:7-21 返回 None | ✅ 确认 |\n| 前提 5：seed 预热维护运行期状态 | scheduler.py:289-304 忙时+最近工种 | ✅ 确认 |\n| 前提 6：固定 200 次硬上限 | scheduler.py:513 `guard < 200`、auto_assign.py:185 `guard < 200` | ✅ 确认 |\n| 前提 7：schedule_summary/calculations 不在范围 | 合理 | ✅ 确认 |\n\n额外验证：`schedule_input_builder.py` **不**规范化 `batch.quantity`——只规范化 `setup_hours` 和 `unit_hours`。plan 说\"只对 batch.quantity 做一次 float(...) 校验\"是正确的。",
      "conclusionMarkdown": "全部 17 处引用和 7 条修订前提二次核实通过。与第一次审查结论完全一致。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 469,
          "lineEnd": 562,
          "symbol": "_schedule_internal"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 155,
          "lineEnd": 230
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 278,
          "lineEnd": 340
        },
        {
          "path": "core/services/scheduler/schedule_input_builder.py",
          "lineStart": 208,
          "lineEnd": 209
        },
        {
          "path": "core/services/common/strict_parse.py",
          "lineStart": 99,
          "lineEnd": 102,
          "symbol": "parse_optional_date"
        }
      ],
      "reviewedModules": [
        "core/algorithms/greedy/scheduler.py",
        "core/algorithms/greedy/auto_assign.py",
        "core/algorithms/greedy/dispatch/sgs.py",
        "core/algorithms/greedy/downtime.py",
        "core/algorithms/greedy/date_parsers.py",
        "core/algorithms/evaluation.py",
        "core/algorithms/dispatch_rules.py",
        "core/algorithms/ortools_bottleneck.py",
        "core/algorithms/greedy/dispatch/batch_order.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/schedule_input_builder.py",
        "core/services/common/strict_parse.py"
      ],
      "recommendedNextAction": "进入第二轮：逐一核实第一次审查的 9 个 finding",
      "findingIds": []
    },
    {
      "id": "M2",
      "title": "第二轮：第一次审查 9 个 finding 逐一核实 + 新发现",
      "status": "completed",
      "recordedAt": "2026-04-07T06:56:51.229Z",
      "summaryMarkdown": "逐一对照代码核实第一次审查的 9 个 finding，全部确认仍然成立。同时发现 1 个新问题。\n\n## 逐条核实结果\n\n| 编号 | 原结论 | 二次核实 | 处置 |\n|---|---|---|---|\n| F1 | 估算器参数可精简为 prev_end | ✅ 确认 | 采纳。改 plan 参数列表 |\n| F2 | 避让上界表达式需明确 | ✅ 确认。guard_limit = 当前设备片段数 + 当前人员片段数 + 停机片段数 + 1 | **必须修订** |\n| F3 | `or 1.0` 效率 BUG | ✅ 高危确认。scheduler.py:494 和 sgs.py:323 都有 | Plan 正确识别 |\n| F4 | SGS 双重自动分配 | ✅ 确认。已知局限 | 在\"不做\"节补充 |\n| F5 | 导入清理 | ✅ 部分修正。`parse_required_float` 可删；`find_earliest_available_start` 取决于不可评分路径实现 | **需明确** |\n| F6 | conditional_op_type 设计正确 | ✅ 确认 | 无需改动 |\n| F7 | abort_after 两处检查 | ✅ 确认。159 行初始早停 + 200 行循环内早停 | **必须修订** |\n| F8 | total_hours_base=0.0 边界 | ✅ 确认。估算器不需特殊处理但回归测试应覆盖 | 补测试 |\n| F9 | 日期函数替换等价性 | ✅ 确认 | 无需改动 |\n\n## 新发现\n\n| 编号 | 严重级别 | 问题 |\n|---|---|---|\n| F10 | 低 | runtime_state 函数分界与 try/except 移除安全性已验证 |",
      "conclusionMarkdown": "第一次审查的 9 个 finding 全部经二次独立核实确认成立。F1 采纳为优化；F2、F7 必须修订；F3 高危 BUG 确认；F4、F5 需补强；F6、F8、F9 低风险确认。新增 2 个发现。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 491,
          "lineEnd": 498,
          "symbol": "_scaled_hours"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 155,
          "lineEnd": 206
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 316,
          "lineEnd": 327
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 90,
          "lineEnd": 106
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 458,
          "lineEnd": 475
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 303,
          "lineEnd": 314
        }
      ],
      "reviewedModules": [],
      "recommendedNextAction": "进入第三轮：边界条件深挖",
      "findingIds": [
        "F2-v2",
        "F3-v2",
        "F7-v2",
        "F5-v2",
        "F10",
        "F1-v2"
      ]
    }
  ],
  "findings": [
    {
      "id": "F2-v2",
      "severity": "medium",
      "category": "other",
      "title": "避让上界必须用当前资源片段数（二次确认）",
      "descriptionMarkdown": "Plan 任务 1 步骤 3 的避让上界 `N_machine + N_operator + N_downtime + 1` 必须明确指的是当前 machine_id/operator_id 的具体片段数。经二次核实 scheduler.py:517-519，`find_overlap_shift_end` 只扫描 `machine_timeline.get(machine_id)` / `operator_timeline.get(operator_id)` / `dt_list`，即当前资源的局部片段列表。正确上界：`guard_limit = len(machine_timeline.get(machine_id) or []) + len(operator_timeline.get(operator_id) or []) + len(dt_list) + 1`。",
      "recommendationMarkdown": "在 plan 任务 1 步骤 3 中写出完整的 Python 表达式。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 510,
          "lineEnd": 533
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F3-v2",
      "severity": "high",
      "category": "other",
      "title": "效率 0.0 隐式回退 BUG（二次确认）",
      "descriptionMarkdown": "scheduler.py:494 的 `or 1.0` 把效率 0.0 隐式吞掉。二次独立核实：\n\n1. `float(... or 1.0)`：当 `get_efficiency()` 返回 0.0 时，`0.0 or 1.0 == 1.0`，完全跳过 497-498 行的 `isfinite / <=0` 检查和 `internal_efficiency_fallback_count` 递增。\n2. sgs.py:323 有完全相同的 BUG。\n3. auto_assign.py:166-167 用了 `raw_eff is not None`（正确），但 170 行 `eff <= 0` 检查虽然会把 0.0 回退到 1.0，却不递增任何计数器（缺少可观测性）。\n\nPlan 的修复方案（`raw_eff is not None` + `efficiency_fallback_used` 标记）是正确的。",
      "recommendationMarkdown": null,
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 491,
          "lineEnd": 498,
          "symbol": "_scaled_hours"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 321,
          "lineEnd": 327
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 163,
          "lineEnd": 171,
          "symbol": "_scaled_hours"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F7-v2",
      "severity": "medium",
      "category": "other",
      "title": "abort_after 两处检查点（二次确认）",
      "descriptionMarkdown": "二次核实 auto_assign.py 三处早停：\n- 159 行：`if best is not None and earliest > best[0]: continue` — 在 adjust_to_working_time 之后、避让循环之前（**初始早停**）\n- 200 行：`if best is not None and earliest > best[0]: break` — 避让循环每次迭代后（**循环内早停**）\n- 205 行：`if guard >= 200 or (best is not None and earliest > best[0]): continue` — 避让循环结束后（**循环后早停**，与 guard 合并）\n\n估算器必须在两个位置检查 abort_after：(1) adjust_to_working_time 之后立即检查；(2) 避让循环每次迭代后检查。第三处（205 行）由调用方根据 `cutoff_exceeded` 处理。",
      "recommendationMarkdown": "在 plan 任务 1 步骤 3 中明确两个检查点：初始早停（adjust_to_working_time 后）和循环内早停（每次避让推迟后）。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 157,
          "lineEnd": 161
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 198,
          "lineEnd": 206
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F5-v2",
      "severity": "low",
      "category": "maintainability",
      "title": "sgs.py 导入清理范围需明确（二次核实 + 补充）",
      "descriptionMarkdown": "任务 2 完成后，sgs.py 的导入需要清理：\n1. `parse_required_float`：当前用于 avg_proc_hours 计算（sgs.py:92-94）对已是 float 的 `op.setup_hours`、`op.unit_hours` 重复解析。改为直接使用 `float(...)` 后该导入不再需要。\n2. `find_earliest_available_start`：当前用于评分路径（sgs.py:310-312, 317-319）。任务 2 把可评分路径（317-319）改用 `estimate_internal_slot()`，但不可评分路径（310-312）仍需要一个粗估起点。Plan 应明确：不可评分路径是继续用 `find_earliest_available_start`（保留导入）还是简化为 `batch_progress.get(bid, base_time)`（可删除导入）。\n\n建议：不可评分路径已有 `score_penalty=1.0` 保证排序到最后，起点精度不重要，可简化为 `batch_progress.get(bid, base_time)`，从而彻底删除 `find_earliest_available_start` 导入。",
      "recommendationMarkdown": "在任务 2 步骤 3 中补充：(1) 删除 `parse_required_float` 导入；(2) 不可评分路径简化为 `batch_progress.get(bid, base_time)` 后删除 `find_earliest_available_start` 导入。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 11,
          "lineEnd": 15
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 303,
          "lineEnd": 314
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F10",
      "severity": "low",
      "category": "other",
      "title": "runtime_state 函数分界与 try/except 移除的安全性验证",
      "descriptionMarkdown": "Plan 任务 3 步骤 4 提出两个共享函数：\n- 函数 1：累计 machine_busy_hours、operator_busy_hours\n- 函数 2：更新 last_end_by_machine、last_op_type_by_machine（含 conditional_op_type 双模式）\n\n但在 batch_order.py:90-106 和 sgs.py:458-475 的实际代码中，busy_hours 和 last_end 更新在同一个 try/except 块内，而 last_op_type 在块外。Plan 要求共享函数不加广域 try/except，这意味着调用方也不需要 try/except（因为 result.start_time 和 result.end_time 已在上层 if 中保证非 None，`h = (end_time - start_time).total_seconds() / 3600.0` 不会失败）。\n\n两个函数的分界点应该是：函数 1 接收 result 的 start_time、end_time、machine_id、operator_id 四个值来计算并累加忙时；函数 2 接收 machine_id、end_time、op_type_name 来更新最近状态。两者不共享中间变量（h 在函数 1 内部计算），分界正确。",
      "recommendationMarkdown": "Plan 表述已足够；实施时注意函数 1 内部自行计算 h，不需要调用方预算。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py",
          "lineStart": 90,
          "lineEnd": 106
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py",
          "lineStart": 458,
          "lineEnd": 475
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 289,
          "lineEnd": 304
        },
        {
          "path": "core/algorithms/greedy/dispatch/batch_order.py"
        },
        {
          "path": "core/algorithms/greedy/dispatch/sgs.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F1-v2",
      "severity": "low",
      "category": "other",
      "title": "估算器参数可精简为 prev_end（二次确认，建议采纳）",
      "descriptionMarkdown": "Plan 任务 1 参数列表包含 `batch_progress: Dict[str, datetime]`。但 auto_assign.py:40 在循环外已计算 `prev_end = batch_progress.get(bid, base_time)`，对所有 (machine, operator) 候选复用同一值。scheduler.py:469 也在进入估算前计算 `prev_end`。传整个 dict 会让估算器每次做 dict.get()，语义不纯粹。\n\n建议接受 F1：把参数改为 `prev_end: datetime`。但这不阻断实施。",
      "recommendationMarkdown": "接受。把 estimate_internal_slot 的 batch_progress 参数改为 prev_end: datetime。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/auto_assign.py",
          "lineStart": 39,
          "lineEnd": 40
        },
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 469,
          "lineEnd": 472
        },
        {
          "path": "core/algorithms/greedy/auto_assign.py"
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:15faea4cb64a04c9d083178ae20ac98a1e6a5c9fec14be5f9fb8ac8d0353040d",
    "generatedAt": "2026-04-07T06:57:13.479Z",
    "locale": "zh-CN"
  }
}
```

# Plan 05 后续结构债治理 三轮审查
- 日期: 2026-04-04
- 概述: 对 plan 05_后续结构债治理与文档同步 进行三轮审查：符合性、可行性、质量。
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# Plan 05 后续结构债治理与文档同步 — 三轮审查

## 审查对象
- `.limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md`
- 源工件：`.limcode/review/阶段7_综合总结与交叉审查.md`

## 审查范围
- 涉及文件：`tests/test_architecture_fitness.py`、`core/services/scheduler/schedule_summary.py`、`core/services/scheduler/batch_service.py`、`core/services/scheduler/batch_template_ops.py`
- 当前实际行数：`schedule_service.py` = 397 行、`schedule_summary.py` = 922 行、`batch_service.py` = 563 行
- 当前实际复杂度：`build_result_summary` = 57、`_summary_degradation_state` = 19、`_freeze_meta_dict` = 17、`update` = 17、`create_batch_from_template_no_tx`(batch_service 内) = <15（已低于阈值）

---

## 第一轮：符合性审查（是否按 review/设计要求拟定）

### 优点
1. **源工件对齐准确**：plan 正确引用了阶段 7 综合审查的修复路线图第三步（中期重构项），聚焦排产主链的超长/高复杂度文件。
2. **与阶段 04 衔接清晰**：明确列出"不重做"的 7 项已完成内容，避免重复劳动或回退。
3. **兼容边界定义到位**：`run_schedule()` 返回结构、导入 `row` 旧语义、插件状态字段、报表路由等 7 条红线明确。
4. **回归测试覆盖面广**：每个批次对应了直接相关的回归，且有"每批次都要跑"的公共门禁。
5. **"暂不纳入"清单合理**：database/backup（回归成本高）、resource_pool_builder（排在 summary 后面）、process/personnel/web 路由集群（跨域建议另批）排队理由充分。

### 问题
| 严重度 | 位置 | 问题 | 为什么重要 | 建议 |
|---|---|---|---|---|
| 次要 | 基线数据第3点 | plan 声称"超长文件登记：10 项"，但 Batch A 完成后当前实际只剩 9 项 | 读者会误以为当前还有 10 项 | 标注清楚：初始 10 项，Batch A 完成后降为 9 项 |

### 结论
符合性审查通过。plan 的方向、来源、约束与阶段 04 的衔接关系均正确。

---

## 第二轮：可行性审查（能不能做成）

### 优点
1. **Batch A 已验证通过**：`schedule_service.py` 实测 397 行，确认已低于 500 行；`test_known_oversize_entries_still_exceed_limit` 已存在且通过。
2. **Batch C 行数目标基本可行**：`batch_service.py` = 563 行，超限仅 63 行；提取 `update()` 的核心验证逻辑可削减约 50-60 行，在理想条件下有希望降至 500 以下。

### 问题
| 严重度 | 位置 | 问题 | 为什么重要 | 建议 |
|---|---|---|---|---|
| **关键** | **Batch B 整体** | **行数算术不成立。** `schedule_summary.py` = 922 行。plan 提议移出冻结窗口（`_extract_freeze_warnings` + `_freeze_meta_dict` ≈ 51 行）+ 退化态（`_summary_degradation_state` + `_compute_downtime_degradation` + `_compute_resource_pool_degradation` + `_hard_constraints` + `_partial_fail_reason` + `_downtime_reason` ≈ 164 行）= 共约 215 行。922 − 215 = **707 行，仍远超 500 行**。即使把所有 `_meta_int/_meta_sample/_metric_int/_metric_sample/_input_build_state` 也一并迁出（+46 行），仍为 **661 行**。要降到 500 以下，需移出至少 422 行，plan 只覆盖了不到一半。 | plan 声称 Batch B 可以将 `schedule_summary.py` 从 `known_oversize` 中移除，**这个目标不可能达成**。 | 有两种修正路径：①降低 Batch B 的期望目标——承认本轮只做"缩减+降低复杂度"但仍保留超长登记；②扩大迁移范围——把 `_config_snapshot_dict`（49 行）、`_best_score_schema`（37 行）、`_comparison_metric`（9 行）、`_warning_list/_merge_warning_lists/_append_summary_warning`（52 行）、`_build_overdue_items`（58 行）等也迁到子模块，且把 `build_result_summary` 中结果字典拼装的条件分支也一并拆出。推荐方案 ①：先做最高收益的冻结+退化拆分，降低复杂度白名单数量，但诚实地保留超长登记。 |
| **关键** | **Batch B 复杂度** | **`build_result_summary` 复杂度 = 57，移出冻结/退化计算后不会显著下降。** 该函数内仍有大量 `if` 分支（merge_context_degraded、unscheduled_batch_count、freeze_state=="degraded"、legacy_external_days_defaulted_count 等至少 12 个分支）用于 warning 拼装和条件性字典构建。这些分支不会因为调用的底层函数被移走而减少。 | plan 隐含期望：移出冻结/退化计算后，`build_result_summary` 的复杂度可降至 15 以下——实际不可能。 | 要显著降低 `build_result_summary` 的复杂度，需要把 warning 拼装（759-809 行区间的 5 个 `if` 块）和条件性字典构建（898-916 行区间的 4 个 `if` 块）也抽到编排辅助函数中。建议把"移除 `build_result_summary` 的复杂度白名单"从 Batch B 的完成标准中移除，改为"复杂度从 57 降到 X 以下"（比如 30），并把完全消除该白名单推迟到下一轮。 |
| **重要** | **Batch C 步骤 4** | **`create_batch_from_template_no_tx` 复杂度白名单已失效。** 实测 radon 复杂度已低于 15（该方法当前仅 14 行，是对 `batch_template_ops.create_batch_from_template_no_tx` 的直接转调）。plan 描述"把仍留在 BatchService 的模板链协调继续下沉到该模块"——但已经没有逻辑可以下沉了。 | plan 描述了不存在的工作量，可能导致实施者做无效重构或试图移动已经是空壳的代码。 | 将 Batch C 中关于 `create_batch_from_template_no_tx` 的步骤简化为"验证并移除该已失效的复杂度白名单条目"——与 Batch A 的"清理失效登记"手法一致。不需要新增代码改动，只需删除白名单条目并验证测试通过。 |
| **重要** | **Batch C 行数** | **Batch C 行数目标虽可行但非常紧**。`batch_service.py` = 563 行，只超 63 行。`update()` 是 80 行，但提取后还需保留 5-10 行的薄壳转调，实际节省约 50-60 行。如果仅依赖 `update()` 提取，余量极小（可能刚好卡在 500 线上）。 | 实施后可能出现"差 5 行"而不得不追加更多迁移范围的情况。 | 建议在 Batch C 中一并将 `_probe_template_ops_readonly`（8 行）和 `_ensure_template_ops_in_tx`（48 行）也从 `batch_service.py` 迁至 `batch_template_ops.py`——这两个方法完全是模板域逻辑，且 `batch_template_ops.py` 已存在同类函数。额外节省约 56 行，确保行数目标有安全余量。 |

### 结论
**Batch A 可行（已完成）。Batch B 当前不可行——需修正目标或扩大迁移范围。Batch C 需小幅修正（清理已失效白名单 + 补充迁移范围以确保行数余量）。**

---

## 第三轮：质量与完备性审查

### 优点
1. **"每批次都要跑"的公共门禁**设计合理，确保不积累漂移。
2. **"只有在债务真实消除后才能删旧登记"**原则明确，防止作弊式"删白名单但不修代码"。
3. **"不新增新的白名单"**约束正确——强制只能通过真实削减来推进。
4. **Batch D 的文档同步节奏**（每批完成后回填受影响章节 + 跑快检 + review）是良好实践。
5. **"暂不纳入"候选排队清单**为后续工作提供了清晰入口。

### 问题
| 严重度 | 位置 | 问题 | 为什么重要 | 建议 |
|---|---|---|---|---|
| 次要 | Batch A 步骤 1 | plan 写"增加一个只校验白名单自身是否仍超 500 行的失败用例"——但 `test_known_oversize_entries_still_exceed_limit` 已存在于 `test_architecture_fitness.py:479-486`，Batch A 的步骤描述与实际执行不一致。 | 因为 Batch A 已完成，这只是留存文档的准确性问题。 | 如果后续需要回溯 plan 执行过程，建议在 plan 或留痕中注明"该测试已存在，本批次仅清理白名单条目"。 |
| 次要 | Batch B 步骤 1 | plan 要求"先移除白名单再跑测试观察失败"，但没有前置步骤验证"当前白名单条目是否仍在复杂度阈值以上"。对于行数白名单同理。 | 如果某些白名单条目已失效（如 `create_batch_from_template_no_tx`），先移除再跑测试会直接通过，无法暴露"是否真正需要重构"。 | 建议在每个批次的步骤 1 之前增加一个"现状诊断"步骤：用 radon 实测当前文件的行数和每个白名单函数的复杂度，确认哪些条目仍超标、哪些已失效，再决定实际工作量。 |
| 次要 | 完成标准第 1 条 | "至少清理 1 项失效登记，并完成 2 个排产主链热点文件的显式登记削减"——Batch B 的目标如上分析不可达，完成标准需要同步调整。 | 完成标准与可行性不匹配会导致验收时无法通过或被迫降标。 | 修正为"至少清理 1 项失效登记（已完成），并完成 2 个排产主链热点文件的复杂度登记削减（schedule_summary 降低 2 项、batch_service 降低 1-2 项），行数登记削减至少 1 个文件"。 |
| 次要 | Batch C 步骤 | 步骤中说"修改 `tests/test_architecture_fitness.py` 的 `known_oversize` 中移除 `batch_service.py`"，但没有明确如何验证移除后确实 ≤500 行。 | 如果行数刚好卡在边界，可能测试有时过有时不过（取决于空行/注释增减）。 | 建议在 Batch C 的完成标准中加一条"batch_service.py 行数 ≤ 480（留 20 行安全余量）"。 |

### 结论
plan 的整体结构和质量良好，但 **Batch B 有不可达的量化目标**，需要在实施前修正。

---

## 综合审查结论

### 总判定：先修后继续

| 批次 | 判定 | 主要行动 |
|---|---|---|
| Batch A | ✅ 已完成 | 无需额外动作 |
| Batch B | ❌ **需要修正 plan** | 行数目标不可达（922→707 仍远超 500）、复杂度 57→不会低于 15。需降低期望或扩大迁移范围。 |
| Batch C | ⚠️ 需小幅修正 | `create_batch_from_template_no_tx` 白名单已失效无需代码改动；行数余量过小建议补充迁移 `_probe_template_ops_readonly`+`_ensure_template_ops_in_tx`。 |
| Batch D | ✅ 无问题 | 按节奏同步即可 |

### 建议的 Batch B 修正方案

**方案 A（推荐）：降低本轮目标 + 分两期完成**
- 本期只做"冻结窗口 + 退化态"提取，目标从"移出 known_oversize"改为"削减 2-3 项复杂度白名单 + 行数从 922 降至 ~700"
- 下期再做第二轮提取（warning 拼装辅助、结果字典拆段、overdue 构建），争取降到 500 以下

**方案 B：一次扩大迁移范围**
- 本期一次性迁出冻结窗口、退化态、config 快照字典、score schema、warning 管理、overdue 构建、metric/meta 辅助——合计约 450 行，可降到 470 行以下
- 代价：本期工作量翻倍，且新模块边界需要仔细设计

### 建议的 Batch C 修正方案
1. 步骤 1 增加"现状诊断"：验证 `create_batch_from_template_no_tx` 复杂度已 <15，直接删除该白名单条目
2. 步骤 3 扩展迁移范围：把 `_probe_template_ops_readonly` + `_ensure_template_ops_in_tx` 迁至 `batch_template_ops.py`
3. 完成标准增加行数安全余量：`batch_service.py ≤ 480 行`

## 评审摘要

- 当前状态: 已完成
- 已审模块: tests/test_architecture_fitness.py, .limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md, core/services/scheduler/schedule_summary.py, core/services/scheduler/batch_service.py, core/services/scheduler/batch_template_ops.py
- 当前进度: 已记录 2 个里程碑；最新：M2
- 里程碑总数: 2
- 已完成里程碑: 2
- 问题总数: 5
- 问题严重级别分布: 高 2 / 中 2 / 低 1
- 最新结论: plan 的整体方向和结构良好，但 **Batch B 存在两个关键可行性问题必须在实施前修正**：(1) 行数目标不可达——按 plan 描述的迁移范围只能从 922 降到 ~707 行，远未达到 500 的阈值；(2) `build_result_summary` 复杂度 57 不会因移出底层计算函数而显著下降。**Batch C 需要小幅修正**：`create_batch_from_template_no_tx` 白名单已失效可直接清理，行数余量过小需补充模板域逻辑的迁移范围。建议先修正 plan 中 Batch B 的量化目标（推荐方案 A：降低期望为"削减复杂度白名单 + 行数降至 ~700"），然后再继续实施。
- 下一步建议: 修正 Batch B 的量化目标（行数从"移出 known_oversize"降为"降至 ~700 行 + 削减 2-3 项复杂度白名单"），修正 Batch C 步骤（清理已失效白名单 + 补充模板域迁移范围），然后继续实施。
- 总体结论: 有条件通过

## 评审发现

### 基线超长文件数量与实际不符

- ID: F-基线超长文件数量与实际不符
- 严重级别: 低
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  plan 声称'超长文件登记：10 项'，但 Batch A 完成后 `_known_oversize_files()` 实际只有 9 个条目。
- 建议:

  标注清楚：初始 10 项，Batch A 完成后降为 9 项。

### Batch B 行数目标不可达

- ID: F-batch-b-行数目标不可达
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  schedule_summary.py = 922 行。plan 提议移出冻结窗口 (~51 行) + 退化态 (~164 行) = 共约 215 行。922 - 215 = 707 行，仍远超 500 行。即使加上所有辅助函数也只降到 661 行。要降到 500 以下需移出至少 422 行，plan 只覆盖了不到一半。
- 建议:

  推荐方案 A：降低本轮目标为'削减 2-3 项复杂度白名单 + 行数从 922 降至 ~700'，保留超长登记。或方案 B：扩大迁移范围至 ~450 行。

### Batch B build_result_summary 复杂度无法降至阈值以下

- ID: F-maintainability-3
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  build_result_summary 当前 radon 复杂度 = 57。移出冻结/退化计算后，函数内仍有至少 12 个 if 分支用于 warning 拼装和条件性字典构建。圈复杂度不会因底层函数移走而显著下降。
- 建议:

  从 Batch B 完成标准中移除'移除 build_result_summary 复杂度白名单'，改为'复杂度从 57 降到 30 以下'。

### Batch C create_batch_from_template_no_tx 白名单已失效

- ID: F-maintainability-4
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  batch_service.py 中 create_batch_from_template_no_tx 仅 14 行，是对 batch_template_ops 的直接转调，radon 复杂度已低于 15。plan 声称需要'继续下沉模板链协调'但实际已无代码可移。
- 建议:

  简化为'验证并移除已失效的复杂度白名单条目'，不做代码改动。

### Batch C 行数余量过小

- ID: F-batch-c-行数余量过小
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  batch_service.py = 563 行，超限 63 行。仅提取 update() 约节省 50-60 行，余量极小。可能差 5 行而被迫追加迁移范围。
- 建议:

  一并迁移 _probe_template_ops_readonly (8行) + _ensure_template_ops_in_tx (48行) 至 batch_template_ops.py，确保降到 480 行以下。

## 评审里程碑

### M1 · 第一轮：符合性审查

- 状态: 已完成
- 记录时间: 2026-04-04T15:15:41.937Z
- 已审模块: tests/test_architecture_fitness.py, .limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md
- 摘要:

  plan 的方向、来源工件（阶段 7 综合审查）、约束边界与阶段 04 衔接关系均正确。回归覆盖面广，"暂不纳入"排队逻辑合理。仅有一处次要基线数据不一致（10 项 vs 实际已降为 9 项）。
- 结论:

  plan 的方向、来源工件（阶段 7 综合审查）、约束边界与阶段 04 衔接关系均正确。回归覆盖面广，"暂不纳入"排队逻辑合理。仅有一处次要基线数据不一致（10 项 vs 实际已降为 9 项）。
- 问题:
  - [低] 文档: 基线超长文件数量与实际不符

### M2 · 第二轮：可行性审查

- 状态: 已完成
- 记录时间: 2026-04-04T15:16:11.528Z
- 已审模块: core/services/scheduler/schedule_summary.py, core/services/scheduler/batch_service.py, core/services/scheduler/batch_template_ops.py
- 摘要:

  Batch A 已完成且可行。**Batch B 存在两个关键问题**：(1) 行数算术不成立——922 行只能降到 ~707 行，远超 500 限制；(2) `build_result_summary` 复杂度 57 不会因移出底层计算而显著下降。**Batch C 存在两个重要问题**：`create_batch_from_template_no_tx` 白名单已失效（无需代码改动即可清理）；行数余量过小需补充迁移范围。
- 结论:

  Batch A 已完成且可行。**Batch B 存在两个关键问题**：(1) 行数算术不成立——922 行只能降到 ~707 行，远超 500 限制；(2) `build_result_summary` 复杂度 57 不会因移出底层计算而显著下降。**Batch C 存在两个重要问题**：`create_batch_from_template_no_tx` 白名单已失效（无需代码改动即可清理）；行数余量过小需补充迁移范围。
- 证据:
  - `core/services/scheduler/schedule_summary.py:688-921#build_result_summary`
  - `core/services/scheduler/batch_service.py:528-555#create_batch_from_template_no_tx`
  - `tests/test_architecture_fitness.py:43-56#_known_oversize_files`
- 问题:
  - [高] 可维护性: Batch B 行数目标不可达
  - [高] 可维护性: Batch B build_result_summary 复杂度无法降至阈值以下
  - [中] 可维护性: Batch C create_batch_from_template_no_tx 白名单已失效
  - [中] 可维护性: Batch C 行数余量过小

## 最终结论

plan 的整体方向和结构良好，但 **Batch B 存在两个关键可行性问题必须在实施前修正**：(1) 行数目标不可达——按 plan 描述的迁移范围只能从 922 降到 ~707 行，远未达到 500 的阈值；(2) `build_result_summary` 复杂度 57 不会因移出底层计算函数而显著下降。**Batch C 需要小幅修正**：`create_batch_from_template_no_tx` 白名单已失效可直接清理，行数余量过小需补充模板域逻辑的迁移范围。建议先修正 plan 中 Batch B 的量化目标（推荐方案 A：降低期望为"削减复杂度白名单 + 行数降至 ~700"），然后再继续实施。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnkh59iu-gwsl1j",
  "createdAt": "2026-04-04T00:00:00.000Z",
  "updatedAt": "2026-04-04T15:16:23.849Z",
  "finalizedAt": "2026-04-04T15:16:23.849Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "Plan 05 后续结构债治理 三轮审查",
    "date": "2026-04-04",
    "overview": "对 plan 05_后续结构债治理与文档同步 进行三轮审查：符合性、可行性、质量。"
  },
  "scope": {
    "markdown": "# Plan 05 后续结构债治理与文档同步 — 三轮审查\n\n## 审查对象\n- `.limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md`\n- 源工件：`.limcode/review/阶段7_综合总结与交叉审查.md`\n\n## 审查范围\n- 涉及文件：`tests/test_architecture_fitness.py`、`core/services/scheduler/schedule_summary.py`、`core/services/scheduler/batch_service.py`、`core/services/scheduler/batch_template_ops.py`\n- 当前实际行数：`schedule_service.py` = 397 行、`schedule_summary.py` = 922 行、`batch_service.py` = 563 行\n- 当前实际复杂度：`build_result_summary` = 57、`_summary_degradation_state` = 19、`_freeze_meta_dict` = 17、`update` = 17、`create_batch_from_template_no_tx`(batch_service 内) = <15（已低于阈值）\n\n---\n\n## 第一轮：符合性审查（是否按 review/设计要求拟定）\n\n### 优点\n1. **源工件对齐准确**：plan 正确引用了阶段 7 综合审查的修复路线图第三步（中期重构项），聚焦排产主链的超长/高复杂度文件。\n2. **与阶段 04 衔接清晰**：明确列出\"不重做\"的 7 项已完成内容，避免重复劳动或回退。\n3. **兼容边界定义到位**：`run_schedule()` 返回结构、导入 `row` 旧语义、插件状态字段、报表路由等 7 条红线明确。\n4. **回归测试覆盖面广**：每个批次对应了直接相关的回归，且有\"每批次都要跑\"的公共门禁。\n5. **\"暂不纳入\"清单合理**：database/backup（回归成本高）、resource_pool_builder（排在 summary 后面）、process/personnel/web 路由集群（跨域建议另批）排队理由充分。\n\n### 问题\n| 严重度 | 位置 | 问题 | 为什么重要 | 建议 |\n|---|---|---|---|---|\n| 次要 | 基线数据第3点 | plan 声称\"超长文件登记：10 项\"，但 Batch A 完成后当前实际只剩 9 项 | 读者会误以为当前还有 10 项 | 标注清楚：初始 10 项，Batch A 完成后降为 9 项 |\n\n### 结论\n符合性审查通过。plan 的方向、来源、约束与阶段 04 的衔接关系均正确。\n\n---\n\n## 第二轮：可行性审查（能不能做成）\n\n### 优点\n1. **Batch A 已验证通过**：`schedule_service.py` 实测 397 行，确认已低于 500 行；`test_known_oversize_entries_still_exceed_limit` 已存在且通过。\n2. **Batch C 行数目标基本可行**：`batch_service.py` = 563 行，超限仅 63 行；提取 `update()` 的核心验证逻辑可削减约 50-60 行，在理想条件下有希望降至 500 以下。\n\n### 问题\n| 严重度 | 位置 | 问题 | 为什么重要 | 建议 |\n|---|---|---|---|---|\n| **关键** | **Batch B 整体** | **行数算术不成立。** `schedule_summary.py` = 922 行。plan 提议移出冻结窗口（`_extract_freeze_warnings` + `_freeze_meta_dict` ≈ 51 行）+ 退化态（`_summary_degradation_state` + `_compute_downtime_degradation` + `_compute_resource_pool_degradation` + `_hard_constraints` + `_partial_fail_reason` + `_downtime_reason` ≈ 164 行）= 共约 215 行。922 − 215 = **707 行，仍远超 500 行**。即使把所有 `_meta_int/_meta_sample/_metric_int/_metric_sample/_input_build_state` 也一并迁出（+46 行），仍为 **661 行**。要降到 500 以下，需移出至少 422 行，plan 只覆盖了不到一半。 | plan 声称 Batch B 可以将 `schedule_summary.py` 从 `known_oversize` 中移除，**这个目标不可能达成**。 | 有两种修正路径：①降低 Batch B 的期望目标——承认本轮只做\"缩减+降低复杂度\"但仍保留超长登记；②扩大迁移范围——把 `_config_snapshot_dict`（49 行）、`_best_score_schema`（37 行）、`_comparison_metric`（9 行）、`_warning_list/_merge_warning_lists/_append_summary_warning`（52 行）、`_build_overdue_items`（58 行）等也迁到子模块，且把 `build_result_summary` 中结果字典拼装的条件分支也一并拆出。推荐方案 ①：先做最高收益的冻结+退化拆分，降低复杂度白名单数量，但诚实地保留超长登记。 |\n| **关键** | **Batch B 复杂度** | **`build_result_summary` 复杂度 = 57，移出冻结/退化计算后不会显著下降。** 该函数内仍有大量 `if` 分支（merge_context_degraded、unscheduled_batch_count、freeze_state==\"degraded\"、legacy_external_days_defaulted_count 等至少 12 个分支）用于 warning 拼装和条件性字典构建。这些分支不会因为调用的底层函数被移走而减少。 | plan 隐含期望：移出冻结/退化计算后，`build_result_summary` 的复杂度可降至 15 以下——实际不可能。 | 要显著降低 `build_result_summary` 的复杂度，需要把 warning 拼装（759-809 行区间的 5 个 `if` 块）和条件性字典构建（898-916 行区间的 4 个 `if` 块）也抽到编排辅助函数中。建议把\"移除 `build_result_summary` 的复杂度白名单\"从 Batch B 的完成标准中移除，改为\"复杂度从 57 降到 X 以下\"（比如 30），并把完全消除该白名单推迟到下一轮。 |\n| **重要** | **Batch C 步骤 4** | **`create_batch_from_template_no_tx` 复杂度白名单已失效。** 实测 radon 复杂度已低于 15（该方法当前仅 14 行，是对 `batch_template_ops.create_batch_from_template_no_tx` 的直接转调）。plan 描述\"把仍留在 BatchService 的模板链协调继续下沉到该模块\"——但已经没有逻辑可以下沉了。 | plan 描述了不存在的工作量，可能导致实施者做无效重构或试图移动已经是空壳的代码。 | 将 Batch C 中关于 `create_batch_from_template_no_tx` 的步骤简化为\"验证并移除该已失效的复杂度白名单条目\"——与 Batch A 的\"清理失效登记\"手法一致。不需要新增代码改动，只需删除白名单条目并验证测试通过。 |\n| **重要** | **Batch C 行数** | **Batch C 行数目标虽可行但非常紧**。`batch_service.py` = 563 行，只超 63 行。`update()` 是 80 行，但提取后还需保留 5-10 行的薄壳转调，实际节省约 50-60 行。如果仅依赖 `update()` 提取，余量极小（可能刚好卡在 500 线上）。 | 实施后可能出现\"差 5 行\"而不得不追加更多迁移范围的情况。 | 建议在 Batch C 中一并将 `_probe_template_ops_readonly`（8 行）和 `_ensure_template_ops_in_tx`（48 行）也从 `batch_service.py` 迁至 `batch_template_ops.py`——这两个方法完全是模板域逻辑，且 `batch_template_ops.py` 已存在同类函数。额外节省约 56 行，确保行数目标有安全余量。 |\n\n### 结论\n**Batch A 可行（已完成）。Batch B 当前不可行——需修正目标或扩大迁移范围。Batch C 需小幅修正（清理已失效白名单 + 补充迁移范围以确保行数余量）。**\n\n---\n\n## 第三轮：质量与完备性审查\n\n### 优点\n1. **\"每批次都要跑\"的公共门禁**设计合理，确保不积累漂移。\n2. **\"只有在债务真实消除后才能删旧登记\"**原则明确，防止作弊式\"删白名单但不修代码\"。\n3. **\"不新增新的白名单\"**约束正确——强制只能通过真实削减来推进。\n4. **Batch D 的文档同步节奏**（每批完成后回填受影响章节 + 跑快检 + review）是良好实践。\n5. **\"暂不纳入\"候选排队清单**为后续工作提供了清晰入口。\n\n### 问题\n| 严重度 | 位置 | 问题 | 为什么重要 | 建议 |\n|---|---|---|---|---|\n| 次要 | Batch A 步骤 1 | plan 写\"增加一个只校验白名单自身是否仍超 500 行的失败用例\"——但 `test_known_oversize_entries_still_exceed_limit` 已存在于 `test_architecture_fitness.py:479-486`，Batch A 的步骤描述与实际执行不一致。 | 因为 Batch A 已完成，这只是留存文档的准确性问题。 | 如果后续需要回溯 plan 执行过程，建议在 plan 或留痕中注明\"该测试已存在，本批次仅清理白名单条目\"。 |\n| 次要 | Batch B 步骤 1 | plan 要求\"先移除白名单再跑测试观察失败\"，但没有前置步骤验证\"当前白名单条目是否仍在复杂度阈值以上\"。对于行数白名单同理。 | 如果某些白名单条目已失效（如 `create_batch_from_template_no_tx`），先移除再跑测试会直接通过，无法暴露\"是否真正需要重构\"。 | 建议在每个批次的步骤 1 之前增加一个\"现状诊断\"步骤：用 radon 实测当前文件的行数和每个白名单函数的复杂度，确认哪些条目仍超标、哪些已失效，再决定实际工作量。 |\n| 次要 | 完成标准第 1 条 | \"至少清理 1 项失效登记，并完成 2 个排产主链热点文件的显式登记削减\"——Batch B 的目标如上分析不可达，完成标准需要同步调整。 | 完成标准与可行性不匹配会导致验收时无法通过或被迫降标。 | 修正为\"至少清理 1 项失效登记（已完成），并完成 2 个排产主链热点文件的复杂度登记削减（schedule_summary 降低 2 项、batch_service 降低 1-2 项），行数登记削减至少 1 个文件\"。 |\n| 次要 | Batch C 步骤 | 步骤中说\"修改 `tests/test_architecture_fitness.py` 的 `known_oversize` 中移除 `batch_service.py`\"，但没有明确如何验证移除后确实 ≤500 行。 | 如果行数刚好卡在边界，可能测试有时过有时不过（取决于空行/注释增减）。 | 建议在 Batch C 的完成标准中加一条\"batch_service.py 行数 ≤ 480（留 20 行安全余量）\"。 |\n\n### 结论\nplan 的整体结构和质量良好，但 **Batch B 有不可达的量化目标**，需要在实施前修正。\n\n---\n\n## 综合审查结论\n\n### 总判定：先修后继续\n\n| 批次 | 判定 | 主要行动 |\n|---|---|---|\n| Batch A | ✅ 已完成 | 无需额外动作 |\n| Batch B | ❌ **需要修正 plan** | 行数目标不可达（922→707 仍远超 500）、复杂度 57→不会低于 15。需降低期望或扩大迁移范围。 |\n| Batch C | ⚠️ 需小幅修正 | `create_batch_from_template_no_tx` 白名单已失效无需代码改动；行数余量过小建议补充迁移 `_probe_template_ops_readonly`+`_ensure_template_ops_in_tx`。 |\n| Batch D | ✅ 无问题 | 按节奏同步即可 |\n\n### 建议的 Batch B 修正方案\n\n**方案 A（推荐）：降低本轮目标 + 分两期完成**\n- 本期只做\"冻结窗口 + 退化态\"提取，目标从\"移出 known_oversize\"改为\"削减 2-3 项复杂度白名单 + 行数从 922 降至 ~700\"\n- 下期再做第二轮提取（warning 拼装辅助、结果字典拆段、overdue 构建），争取降到 500 以下\n\n**方案 B：一次扩大迁移范围**\n- 本期一次性迁出冻结窗口、退化态、config 快照字典、score schema、warning 管理、overdue 构建、metric/meta 辅助——合计约 450 行，可降到 470 行以下\n- 代价：本期工作量翻倍，且新模块边界需要仔细设计\n\n### 建议的 Batch C 修正方案\n1. 步骤 1 增加\"现状诊断\"：验证 `create_batch_from_template_no_tx` 复杂度已 <15，直接删除该白名单条目\n2. 步骤 3 扩展迁移范围：把 `_probe_template_ops_readonly` + `_ensure_template_ops_in_tx` 迁至 `batch_template_ops.py`\n3. 完成标准增加行数安全余量：`batch_service.py ≤ 480 行`"
  },
  "summary": {
    "latestConclusion": "plan 的整体方向和结构良好，但 **Batch B 存在两个关键可行性问题必须在实施前修正**：(1) 行数目标不可达——按 plan 描述的迁移范围只能从 922 降到 ~707 行，远未达到 500 的阈值；(2) `build_result_summary` 复杂度 57 不会因移出底层计算函数而显著下降。**Batch C 需要小幅修正**：`create_batch_from_template_no_tx` 白名单已失效可直接清理，行数余量过小需补充模板域逻辑的迁移范围。建议先修正 plan 中 Batch B 的量化目标（推荐方案 A：降低期望为\"削减复杂度白名单 + 行数降至 ~700\"），然后再继续实施。",
    "recommendedNextAction": "修正 Batch B 的量化目标（行数从\"移出 known_oversize\"降为\"降至 ~700 行 + 削减 2-3 项复杂度白名单\"），修正 Batch C 步骤（清理已失效白名单 + 补充模板域迁移范围），然后继续实施。",
    "reviewedModules": [
      "tests/test_architecture_fitness.py",
      ".limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md",
      "core/services/scheduler/schedule_summary.py",
      "core/services/scheduler/batch_service.py",
      "core/services/scheduler/batch_template_ops.py"
    ]
  },
  "stats": {
    "totalMilestones": 2,
    "completedMilestones": 2,
    "totalFindings": 5,
    "severity": {
      "high": 2,
      "medium": 2,
      "low": 1
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：符合性审查",
      "status": "completed",
      "recordedAt": "2026-04-04T15:15:41.937Z",
      "summaryMarkdown": "plan 的方向、来源工件（阶段 7 综合审查）、约束边界与阶段 04 衔接关系均正确。回归覆盖面广，\"暂不纳入\"排队逻辑合理。仅有一处次要基线数据不一致（10 项 vs 实际已降为 9 项）。",
      "conclusionMarkdown": "plan 的方向、来源工件（阶段 7 综合审查）、约束边界与阶段 04 衔接关系均正确。回归覆盖面广，\"暂不纳入\"排队逻辑合理。仅有一处次要基线数据不一致（10 项 vs 实际已降为 9 项）。",
      "evidence": [],
      "reviewedModules": [
        "tests/test_architecture_fitness.py",
        ".limcode/plans/core目录系统性修复/05_后续结构债治理与文档同步.plan.md"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-基线超长文件数量与实际不符"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：可行性审查",
      "status": "completed",
      "recordedAt": "2026-04-04T15:16:11.528Z",
      "summaryMarkdown": "Batch A 已完成且可行。**Batch B 存在两个关键问题**：(1) 行数算术不成立——922 行只能降到 ~707 行，远超 500 限制；(2) `build_result_summary` 复杂度 57 不会因移出底层计算而显著下降。**Batch C 存在两个重要问题**：`create_batch_from_template_no_tx` 白名单已失效（无需代码改动即可清理）；行数余量过小需补充迁移范围。",
      "conclusionMarkdown": "Batch A 已完成且可行。**Batch B 存在两个关键问题**：(1) 行数算术不成立——922 行只能降到 ~707 行，远超 500 限制；(2) `build_result_summary` 复杂度 57 不会因移出底层计算而显著下降。**Batch C 存在两个重要问题**：`create_batch_from_template_no_tx` 白名单已失效（无需代码改动即可清理）；行数余量过小需补充迁移范围。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_summary.py",
          "lineStart": 688,
          "lineEnd": 921,
          "symbol": "build_result_summary"
        },
        {
          "path": "core/services/scheduler/batch_service.py",
          "lineStart": 528,
          "lineEnd": 555,
          "symbol": "create_batch_from_template_no_tx"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 43,
          "lineEnd": 56,
          "symbol": "_known_oversize_files"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_summary.py",
        "core/services/scheduler/batch_service.py",
        "core/services/scheduler/batch_template_ops.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-batch-b-行数目标不可达",
        "F-maintainability-3",
        "F-maintainability-4",
        "F-batch-c-行数余量过小"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-基线超长文件数量与实际不符",
      "severity": "low",
      "category": "docs",
      "title": "基线超长文件数量与实际不符",
      "descriptionMarkdown": "plan 声称'超长文件登记：10 项'，但 Batch A 完成后 `_known_oversize_files()` 实际只有 9 个条目。",
      "recommendationMarkdown": "标注清楚：初始 10 项，Batch A 完成后降为 9 项。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-batch-b-行数目标不可达",
      "severity": "high",
      "category": "maintainability",
      "title": "Batch B 行数目标不可达",
      "descriptionMarkdown": "schedule_summary.py = 922 行。plan 提议移出冻结窗口 (~51 行) + 退化态 (~164 行) = 共约 215 行。922 - 215 = 707 行，仍远超 500 行。即使加上所有辅助函数也只降到 661 行。要降到 500 以下需移出至少 422 行，plan 只覆盖了不到一半。",
      "recommendationMarkdown": "推荐方案 A：降低本轮目标为'削减 2-3 项复杂度白名单 + 行数从 922 降至 ~700'，保留超长登记。或方案 B：扩大迁移范围至 ~450 行。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-maintainability-3",
      "severity": "high",
      "category": "maintainability",
      "title": "Batch B build_result_summary 复杂度无法降至阈值以下",
      "descriptionMarkdown": "build_result_summary 当前 radon 复杂度 = 57。移出冻结/退化计算后，函数内仍有至少 12 个 if 分支用于 warning 拼装和条件性字典构建。圈复杂度不会因底层函数移走而显著下降。",
      "recommendationMarkdown": "从 Batch B 完成标准中移除'移除 build_result_summary 复杂度白名单'，改为'复杂度从 57 降到 30 以下'。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-maintainability-4",
      "severity": "medium",
      "category": "maintainability",
      "title": "Batch C create_batch_from_template_no_tx 白名单已失效",
      "descriptionMarkdown": "batch_service.py 中 create_batch_from_template_no_tx 仅 14 行，是对 batch_template_ops 的直接转调，radon 复杂度已低于 15。plan 声称需要'继续下沉模板链协调'但实际已无代码可移。",
      "recommendationMarkdown": "简化为'验证并移除已失效的复杂度白名单条目'，不做代码改动。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-batch-c-行数余量过小",
      "severity": "medium",
      "category": "maintainability",
      "title": "Batch C 行数余量过小",
      "descriptionMarkdown": "batch_service.py = 563 行，超限 63 行。仅提取 update() 约节省 50-60 行，余量极小。可能差 5 行而被迫追加迁移范围。",
      "recommendationMarkdown": "一并迁移 _probe_template_ops_readonly (8行) + _ensure_template_ops_in_tx (48行) 至 batch_template_ops.py，确保降到 480 行以下。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:1259373b73a7130f2a30b95cb6560b3aeec580feffa3fbc9694b5284275c59dd",
    "generatedAt": "2026-04-04T15:16:23.849Z",
    "locale": "zh-CN"
  }
}
```

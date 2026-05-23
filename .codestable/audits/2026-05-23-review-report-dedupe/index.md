---
doc_type: audit-index
status: completed
title: "两份 Review 报告核实去重最终版"
date: 2026-05-23
scope:
  - "review-244fbb7-to-d37df6d.md"
  - ".limcode/review/a205-to-48d172d-recent-4-commits-deep-review.md"
current_head: "48d172d2"
subagents_created_total: 17
max_parallel_subagents: 16
failed_spawn_attempts: 1
---

# 两份 Review 报告核实去重最终版

## 结论摘要

本次把两份报告合并成一份当前可执行的结论：

- 报告 A：`review-244fbb7-to-d37df6d.md`
- 报告 B：`.limcode/review/a205-to-48d172d-recent-4-commits-deep-review.md`

核实后最重要的变化是：报告 A 里很多 P0/P1 是 `d37df6d` 回滚态风险，不应再直接当成当前 HEAD 的阻断问题。当前 HEAD 是 `48d172d2`，已经恢复了 schema v14、Gantt 只读、`scenario_id`、`gantt_zoom`、vendor patch、Gantt 关键回归测试、Gantt 弹窗公开展示等多条合同。

当前仍需要修的重点，主要集中在 8 类：

1. 分析页诊断把未知状态显示成正常，并且 `NaN` / `Infinity` 会让诊断构建报错。
2. 报表页只填一个日期时，会悄悄换成版本范围或默认 7 天。
3. Gantt 前端对接口错误、错误数据形状、`window.Gantt` 缺失的用户可见报错还不够清楚。
4. 资源排班超期摘要解析回归没有进必跑门禁。
5. 周计划模拟方案预览会同时显示“模拟方案”和“对比方案”提示。
6. 资源排班导出文件名只清理了部分字段，`scope_id` 仍可能带非法字符。
7. 数据库高版本库没有 fail-fast，虽然“14 倒退 11”已经修回，但未来高版本库仍可能被静默接受。
8. 若干 P2 维护项仍在：`gantt_render.js` 过长、关键链异常折叠、文档状态需要保持和当前代码一致。

最终判定：当前分支不是“报告 A 说的那种整片回滚坏态”，但仍是 `needs_follow_up`。建议先修 P1，再做 P2 收口。

## 本次核实方式

- 本轮一共真实创建 17 个子代理；最高同时并行 16 个。不是口头模拟。
- 其中 1 个是探针子代理，15 个是模块核实子代理，探针关闭后又补了 1 个对抗性复核子代理。中途有 1 次额外 spawn 因达到并行上限失败，关闭探针后已补上。
- 子代理只读为主，分别核实数据库迁移、Gantt 只读、`scenario_id`、`gantt_zoom`、vendor patch、质量门禁、Gantt 前端错误、Gantt 方案一致性、公开展示、前端复杂度、文档、分析诊断、资源排班、提交关系、去重和对抗性复核。
- 主线程只做少量关键证据定位和最终合并。
- 有些子代理跑了定向测试；本报告没有声称完整 clean-worktree quality gate 已通过。

## 范围说明

第一份报告的范围写作 `244fbb7..d37df6d`，但按 Git 正常方向看，`d37df6d` 是 `244fbb7` 的祖先，这个区间字面上近似空区间。结合报告内容，它实际在审“从 `244fbb7` 倒退到 `d37df6d` 会丢掉哪些 Gantt 能力”。所以报告 A 更像一份回滚风险报告，不是当前 HEAD 状态报告。

第二份报告覆盖 `a205e83..48d172d`，当前 HEAD 正是 `48d172d2`，因此报告 B 的问题更接近当前真实剩余问题。

## 去重后的当前发现

| ID | 严重度 | 状态 | 来源 | 当前结论 |
|---|---|---|---|---|
| F-01 | P1 | 当前仍成立 | B3 + B4 | 分析页诊断对未知状态和非有限数字处理不严 |
| F-02 | P1 | 当前仍成立 | B2 | 报表页单边日期会静默回退 |
| F-03 | P1 | 当前仍成立 | A P1-4 + A P2-5 | Gantt 前端错误边界不够清楚 |
| F-04 | P1 | 当前仍成立 | A P1-3 + B5 | 超期摘要解析回归没有进必跑门禁 |
| F-05 | P1 | 当前仍成立 | B1 | 周计划模拟方案预览提示重复 |
| F-06 | P1 | 当前仍成立 | B6 + A P1-6 残留 | 资源排班展示/导出名称合同不完整 |
| F-07 | P1 | 当前残留 | A P0-1 | 当前 schema 已是 14，但高版本库缺 fail-fast |
| F-08 | P2 | 当前仍成立 | A P2-1 | `gantt_render.js` 仍过长，职责集中 |
| F-09 | P2 | 当前仍成立 | A P2-3 | 关键链读取异常仍会被折叠成 `repo_exception` |
| F-10 | P2 | 测试缺口 | A P2-4 | Week/Month 假期宽度当前不能证实为 bug，但缺回归 |
| F-11 | P2 | 文档维护项 | A P2-2 | 当前文档已恢复不少，但需要后续验收时继续同步 |

## 当前仍成立的问题明细

### F-01：分析页诊断不能把未知或坏数字当正常

严重度：P1
建议动作：`cs-issue`

当前代码里，`graph_status` 缺失时会先变成 `unknown`，但 `_overall_health_status()` 没有处理 `unknown` 或陌生状态，最后落到 `ok`。这会让页面外层显示“正常”，但具体项又写“状态未知”，前后打架。

证据：

- `web/viewmodels/scheduler_analysis_diagnostic_health.py:113`
- `web/viewmodels/scheduler_analysis_diagnostic_health.py:23`
- `web/viewmodels/scheduler_analysis_diagnostic_health.py:60`
- `web/viewmodels/scheduler_analysis_diagnostic_helpers.py:216`
- `templates/scheduler/analysis_parts/_diagnostic_sections.html:31`

同时，`safe_float()` 没有检查 `NaN` / `Infinity`，`safe_int()` 没有接住 `OverflowError`，`format_hours()` 会对非有限数字做 `int(value)`，可能直接报错。

证据：

- `web/viewmodels/scheduler_analysis_diagnostic_helpers.py:100`
- `web/viewmodels/scheduler_analysis_diagnostic_helpers.py:109`
- `web/viewmodels/scheduler_analysis_diagnostic_helpers.py:209`
- `web/viewmodels/scheduler_analysis_diagnostic_delay_impact.py:124`
- `web/viewmodels/scheduler_analysis_vm.py:121`

修复要求：

- 只有 `graph_status == "available"` 且没有循环、错误、提醒时才允许返回 `ok`。
- 缺失、`unknown`、陌生状态都显示为“未知”或“需要关注”，不能显示“正常”。
- 诊断数字必须检查有限值，`NaN`、`Infinity`、`-Infinity` 都不能当正常数字。
- 回归测试覆盖缺 status、unknown、陌生状态、`NaN`、`Infinity`。

### F-02：报表页单边日期不能静默回退

严重度：P1
建议动作：`cs-issue`

页面端 `page_date_range_or_version_span()` 只有开始和结束都填了才使用用户输入。只填一边时，它会直接回到版本排程范围或最近 7 天。用户以为查了自己填的日期，实际页面展示了别的范围。

证据：

- `web/routes/report_plan_preview.py:83`
- `web/routes/report_plan_preview.py:91`
- `web/routes/report_plan_preview.py:104`
- `web/routes/reports.py:238`
- `web/routes/reports.py:322`

修复要求：

- 页面端和导出端规则统一：只要用户填了开始或结束任意一个，就必须校验两边。
- 缺一边时返回清楚的可见错误。
- 只有两边都空，才允许自动使用版本范围或默认 7 天。
- 增加资源负荷页和停机影响页的页面端回归测试。

### F-03：Gantt 前端错误边界不够清楚

严重度：P1
建议动作：`cs-issue`

当前坏时间行、日历加载失败已经有降级提示和测试，不应继续说“所有错误都会被吞”。但还有三个明确残留：

- HTTP 非 2xx 时，前端先抛 `甘特图数据请求失败（HTTP xxx）`，没有优先读取后端 JSON 错误正文。
- `payload.data.tasks` 不是数组时，会被转成空数组，用户看到“暂无排程数据”。
- `window.Gantt` 缺失时，adapter 会抛 `Frappe Gantt 未加载。`，但 boot 依赖检查和页面错误区没有提前把它显示给用户。

证据：

- `static/js/gantt_boot.js:289`
- `static/js/gantt_boot.js:331`
- `static/js/gantt_boot.js:360`
- `static/js/gantt_render.js:986`
- `static/js/gantt_render.js:1024`
- `static/js/gantt_adapter.js:59`
- `web/routes/domains/scheduler/scheduler_gantt.py:234`

修复要求：

- HTTP 错误时先尝试读取 JSON，优先显示后端 `error.message`。
- 成功响应后校验 `payload.data` 和 `data.tasks` 形状；不合格就显示数据格式错误。
- boot 阶段检查 `window.Gantt`，或统一 catch render 错误并写入 `#ganttError`。
- 增加 3 个回归：后端 JSON 错误正文展示、非数组 tasks 不显示空状态、缺 Gantt 时显示可读错误。

### F-04：超期摘要解析回归没有进必跑门禁

严重度：P1
建议动作：`cs-issue`

Gantt 大范围测试删除这个历史问题已经基本修回，当前 `tools/test_registry.py` 已恢复多组 Gantt 关键回归。但资源排班超期摘要解析测试仍没有进入必跑门禁，后续解析器退化可能漏掉。

证据：

- `tests/regression_resource_dispatch_overdue_summary_formats.py:11`
- `tools/test_registry.py:132`
- `tools/test_registry.py:516`
- `tests/test_run_quality_gate.py:650`

修复要求：

- 把 `tests/regression_resource_dispatch_overdue_summary_formats.py` 加入 `QUALITY_GATE_GUARD_TESTS`。
- 加入 `REQUIRED_REGRESSION_GROUPS["scheduler_batches_material_resource"]`。
- 在 `tests/test_run_quality_gate.py` 加高价值测试断言。
- 可一起评估是否把资源排班 partial/invalid overdue surface 测试也加入同组。

### F-05：周计划模拟方案预览提示重复

严重度：P1
建议动作：`cs-issue`

模拟方案预览本身已经能保住 `scenario_id`，不会回落正式排程。但周计划页面会同时显示“正在预览模拟方案”和“正在查看对比方案”，用户容易误会自己到底在看模拟方案还是普通对比方案。

证据：

- `templates/scheduler/week_plan.html:94`
- `templates/scheduler/week_plan.html:99`
- `core/models/schedule_plan_role.py:26`
- `core/services/scheduler/schedule_plan_query_service.py:87`

修复要求：

- 周计划 comparison 提示加 `not plan_resolution.is_scenario_preview`。
- 或者在 viewmodel 层把“模拟方案预览”和“对比方案”拆成两个明确字段。
- 增加模板回归，断言 scenario preview 只出现一个清楚提示。

### F-06：资源排班展示/导出名称合同不完整

严重度：P1
建议动作：`cs-issue`

Gantt 弹窗暴露 `internal`、`urgent` 这类内部值的问题当前已修回。但同类问题在资源排班还残留：

- 资源排班页面版本摘要仍直接显示 `schedule_time` 原始值。
- 导出文件名只清洗了模拟方案字段和方案标签，`scope_id` 仍直接拼进去。
- 如果把 Excel 内容也算公开输出，`source`、`lock_status` 等内部值也需要转成人话。

证据：

- `templates/scheduler/resource_dispatch.html:166`
- `web/viewmodels/scheduler_history_summary.py:210`
- `web/viewmodels/scheduler_resource_dispatch.py:28`
- `web/viewmodels/scheduler_resource_dispatch.py:263`
- `tests/test_resource_dispatch_viewmodel.py:315`

修复要求：

- 文件名所有动态片段统一过安全清洗，至少先补 `scope_id`。
- 页面摘要优先用 `schedule_time_display`。
- 如纳入 Excel 输出，同步补 `source_label`、`lock_status_label`。
- 回归覆盖危险 `scope_id`，断言文件名不含 `/ \ : * ? " < > |`。

### F-07：数据库高版本库缺 fail-fast

严重度：P1
建议动作：`cs-issue`

报告 A 原来的“schema 从 14 倒退到 11”当前已经过期。现在版本号是 14，v12/v13/v14 迁移和 schema 表都在。

证据：

- `core/infrastructure/migration_state.py:8`
- `core/infrastructure/migrations/__init__.py:18`
- `core/infrastructure/migrations/__init__.py:35`
- `core/infrastructure/migrations/v12.py:54`
- `core/infrastructure/migrations/v13.py:59`
- `core/infrastructure/migrations/v14.py:15`
- `schema.sql:399`

但当前仍没有 `current_version > CURRENT_SCHEMA_VERSION` 的明确失败分支。也就是说，如果某个数据库版本是 15 或更高，代码可能直接当成“不需要迁移”。

证据：

- `core/infrastructure/database.py:157`
- `core/infrastructure/migration_runner.py:121`
- `core/infrastructure/migration_runner.py:205`

修复要求：

- 在读出 `current_version` 后、进入 `< CURRENT_SCHEMA_VERSION` 判断前，加高版本 fail-fast。
- 抛 `MigrationContractError`，提示数据库版本高于当前程序，不允许继续启动。
- 增加临时库回归：`SchemaVersion = CURRENT_SCHEMA_VERSION + 1` 时必须报错。

## 已过期或不再作为当前缺陷的问题

这些问题在报告 A 的回滚态里有历史依据，但当前 HEAD 已经修回，不应继续写成当前阻断：

| 原问题 | 当前结论 | 证据 |
|---|---|---|
| Schema 从 14 倒退到 11 | 已修回到 14 | `core/infrastructure/migration_state.py:8` |
| Gantt 只读页能拖但不保存 | 已恢复 readonly 合同 | `templates/scheduler/gantt.html:279`, `static/js/gantt_adapter.js:33` |
| `scenario_id` 被静默忽略 | 当前页面和 data 接口都继续传 | `web/routes/domains/scheduler/scheduler_gantt.py:76`, `web/routes/domains/scheduler/scheduler_gantt.py:227` |
| Frappe Gantt 午夜结束加一天 | 当前 vendor patch 已恢复 | `static/js/frappe-gantt.min.js:1`, `tests/regression_frappe_gantt_short_task_contract.py:52` |
| `gantt_zoom` / 分钟级缩放被删除 | 当前已恢复 | `static/js/gantt_zoom.js:14`, `static/js/gantt_ui.js:110` |
| Gantt 专项门禁大范围删除 | 当前主保护网已恢复 | `tools/test_registry.py:77` |
| Gantt resolved plan 又按 role 二次解析 | 当前主链使用 resolved identity | `core/services/scheduler/gantt_service.py:332` |
| Gantt 弹窗暴露 `internal/urgent` | 当前已走公开中文转换 | `static/js/gantt_contract.js:195`, `static/js/gantt_render.js:1047` |
| 文档/vendor patch 合同完全丢失 | 当前已恢复关键文档 | `.codestable/architecture/ui-gantt.md:1`, `.codestable/vendor/frappe-gantt-local-patches.md:1` |
| Week/Month 假期宽度确定错误 | 当前不能证实 | `static/js/gantt_render.js:673`, `static/js/gantt_zoom.js:164` |

## 修复计划

### 第一批：先修会影响用户判断和验收的 P1

1. 修 F-01 分析页诊断。
   - 改 `web/viewmodels/scheduler_analysis_diagnostic_health.py`。
   - 改 `web/viewmodels/scheduler_analysis_diagnostic_helpers.py`。
   - 必要时改 `web/viewmodels/scheduler_analysis_diagnostic_delay_impact.py`。
   - 补 `tests/regression_scheduler_analysis_diagnostic_contract.py`。
   - 验证：`pytest -q tests/regression_scheduler_analysis_diagnostic_contract.py tests/regression_metrics_to_dict_nonfinite_safe.py`。

2. 修 F-02 报表页单边日期。
   - 改 `web/routes/report_plan_preview.py`。
   - 补资源负荷页、停机影响页页面端测试。
   - 验证：相关报表回归和导出回归。

3. 修 F-03 Gantt 前端错误边界。
   - 改 `static/js/gantt_boot.js`。
   - 如需要，少量改 `static/js/gantt_render.js` 错误显示入口。
   - 补 HTTP JSON 错误、非数组 tasks、缺 `window.Gantt` 三类测试。
   - 验证：Gantt boot / data error / adapter 相关回归。

4. 修 F-04 质量门禁遗漏。
   - 改 `tools/test_registry.py`。
   - 改 `tests/test_run_quality_gate.py`。
   - 验证：`pytest -q tests/test_run_quality_gate.py tests/regression_resource_dispatch_overdue_summary_formats.py`。

5. 修 F-05 周计划重复提示。
   - 改 `templates/scheduler/week_plan.html` 或对应 viewmodel。
   - 补 scenario preview 只显示一个提示的回归。
   - 验证：`tests/regression_scenario_preview_secondary_outputs.py` 和新增模板回归。

6. 修 F-06 展示/导出名称合同。
   - 改 `web/viewmodels/scheduler_resource_dispatch.py`。
   - 改 `templates/scheduler/resource_dispatch.html`。
   - 视范围改 `core/services/scheduler/resource_dispatch_excel.py`。
   - 补 `tests/test_resource_dispatch_viewmodel.py`。

7. 修 F-07 高版本数据库 fail-fast。
   - 改 `core/infrastructure/database.py`。
   - 视实际调用链同步 `core/infrastructure/migration_runner.py`。
   - 补数据库 schema version 回归。

### 第二批：P2 收口

1. 关键链异常可见性。
   - 收窄 `core/services/scheduler/gantt_critical_chain_provider.py` 的宽泛捕获。
   - 或保留降级，但必须把真实错误类型和可读信息带到诊断里。

2. Gantt render 拆分。
   - `static/js/gantt_render.js` 当前仍约 1116 行。
   - 优先拆 popup、holiday、decorations、legend，不改变行为。

3. Week/Month 假期宽度测试。
   - 当前不能证实为运行 bug。
   - 补测试锁 `scale.dayWidth`，避免以后回退成整周/整月宽度。

4. 文档跟随。
   - 每修完一批，回填 `.codestable/architecture/ui-gantt.md`、`.codestable/vendor/frappe-gantt-local-patches.md` 或相关 issue/fix-note。
   - 不需要恢复旧大文档全文，但要让“保留什么、下线什么、靠哪些测试保护”说清楚。

## 建议验收命令

后续已经对本报告做了更深的根因下钻和对抗性审核，形成了新的执行蓝本：

- `.codestable/issues/2026-05-23-review-report-dedupe-fix-plan/review-report-dedupe-fix-plan-analysis.md`

所以本节下面的命令只保留为“去重报告阶段的初版建议”。真正执行和验收时，以新的 issue analysis 文档为准。

第一批修完后建议至少跑：

```bash
pytest -q tests/regression_scheduler_analysis_diagnostic_contract.py tests/regression_metrics_to_dict_nonfinite_safe.py
pytest -q tests/regression_reports_export_version_default_latest.py
pytest -q tests/regression_scenario_preview_secondary_outputs.py tests/regression_gantt_draft_save_and_preview.py
pytest -q tests/regression_resource_dispatch_overdue_summary_formats.py tests/test_resource_dispatch_viewmodel.py
pytest -q tests/test_run_quality_gate.py
git diff --check
```

准备真正收尾时再跑：

```bash
python scripts/run_quality_gate.py --require-clean-worktree
```

注意：当前工作区有未跟踪输入报告 `review-244fbb7-to-d37df6d.md`，因此在它被纳入、删除、或明确排除之前，不能声称有 clean-worktree proof。

## 子代理结果去重说明

- A P0-1 被拆成两部分：版本倒退已修，高版本 fail-fast 残留。
- A P0-2、P0-3、P1-1、P1-2、P1-5、P1-6 大部分已由后续提交修回。
- A P1-3 和 B5 合并为门禁大类，但当前只保留 B5 的资源排班超期摘要门禁遗漏为待修。
- B3 和 B4 合并为分析诊断数据可信度问题。
- B6 和 A P1-6 的残留合并为展示/导出名称合同问题。
- A P2-4 未证实，不列当前 bug，只列测试缺口。

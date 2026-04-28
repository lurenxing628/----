---
doc_type: feature-design
feature: 2026-04-28-scheduler-summary-result-summary-contract
status: approved
summary: 固定 summary/result_summary 写入、读回和页面展示的公开形状。
tags: [scheduler, summary, history, ui-contract, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: scheduler-summary-result-summary-contract
---

# Summary 与历史回放合同设计

## 0. 承接边界

PR-5 只承接 PR-4 已证明的优化器输出：rejected 诊断在进入 summary 前没有丢，公开 attempts 和内部 diagnostics 已经分层。PR-5 不能把 PR-4 的通过结果当成落库、历史读回或页面展示已经稳定。

本次只证明 `build_result_summary -> persist_schedule -> ScheduleHistory` 这条链，以及这些历史数据进入页面后的展示边界。

明确不做：

- 不新增 `if`、fallback、兜底、静默吞错或宽泛默认值逻辑。
- 不在模板、route 或 viewmodel 里补二次过滤来掩盖上游泄漏。
- 不改 `summary_schema_version=1.2`；如果红灯证明必须升版本，先停下来说明。
- 不改变 `OptimizationOutcome` 字段，不改优化器主逻辑。
- 不减少 full-test-debt。

## 1. 对外形状

- `result_summary.algo.attempts` 只保留页面可展示字段，不出现 `tag`、`used_params`、`algo_stats`、`origin`。
- `result_summary.diagnostics.optimizer.attempts` 可以保留排障字段，并在正常大小下随历史 JSON 落库。
- 正式测试覆盖的分析页、系统历史页、排产首页、周计划页、甘特图、资源排班页、报表入口和报表子页响应，不展示 `INTERNAL_OPTIMIZER_SECRET` 这个内部诊断词；本结论不扩大成所有页面或所有 API 的承诺。
- summary size guard 保持现状：如果 summary 超大，可以截断 diagnostics 并设置 `summary_truncated/diagnostics_truncated`，不能为了保留 diagnostics 放宽大小保护。

## 2. 证据路径

1. 用测试构造带 `INTERNAL_OPTIMIZER_SECRET` 的 rejected diagnostics。
2. 先走 `build_result_summary`，确认公开 attempts 和 diagnostics 分层。
3. 再走 `persist_schedule` 写入真实 SQLite `ScheduleHistory`。
4. 用 `ScheduleHistoryRepository.get_by_version()` 读回并 `json.loads`，确认公开字段稳定、内部 diagnostics 正常落库。
5. 用真实 app 和真实模板访问分析页、系统历史页、排产首页、周计划页、甘特图、资源排班页、报表入口和报表子页，确认这些响应不出现 `INTERNAL_OPTIMIZER_SECRET`。

## 3. 文件边界

- `core/services/scheduler/summary/schedule_summary.py`：summary 构建和 size guard。
- `core/services/scheduler/summary/schedule_summary_assembly.py`：`algo` 和 diagnostics 装配入口。
- `core/services/scheduler/summary/optimizer_public_summary.py`：公开 attempts 与内部 diagnostics 投影。
- `core/services/scheduler/run/schedule_persistence.py`：历史写入入口。
- `web/routes/normalizers.py`、`web/viewmodels/scheduler_summary_display.py`：页面读 summary 和显示摘要的稳定边界，只读核对；默认不改。
- `templates/scheduler/*.html`、`templates/system/history.html`、`templates/reports/*.html`：只做真实 HTML 验证，不在模板里补过滤。

## 4. 推进策略

1. 创建 PR-5 feature 三件套并把 items 改为 `in-progress`。
2. 补真实落库读回测试，走 `build_result_summary -> persist_schedule -> ScheduleHistoryRepository.get_by_version -> json.loads`。
3. 补真实页面和接口响应不泄漏测试，构造内部诊断词，访问分析页、系统历史页、排产首页、周计划页、甘特图、资源排班页、报表入口和报表子页。
4. 跑 PR-5 目标测试、ruff、pyright、full-test-debt、台账检查、yaml 校验和 `git diff --check`。
5. 请 subagent 复审落库/页面/历史读取、内部诊断不外泄、无新增兜底和 M5/PR-6 头部承接。
6. 写 acceptance，checklist 的 checks 按真实结果标 `passed/failed`，items 标 `done`，并在 PR-6 头部写清完整 M4 已完成内容和不能继承的 proof 边界。

## 5. 验收契约

- `build_result_summary` 输出的公开 attempts 不含 `source`、`tag`、`used_params`、`algo_stats`、`origin`。
- `diagnostics.optimizer.attempts` 在正常大小下落库并读回，保留 `origin.type/field/message` 和内部排障词。
- 历史读回后公开 attempts 形状不变化。
- 正式测试覆盖的分析页、系统历史页、排产首页、周计划页、甘特图、资源排班页、报表入口和报表子页响应不出现 `INTERNAL_OPTIMIZER_SECRET`。
- 不改 schema 版本，不新增 fallback/兜底/静默吞错，不减少 full-test-debt。

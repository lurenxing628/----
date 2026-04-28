---
doc_type: feature-design
feature: 2026-04-28-batches-page-viewmodel
status: approved
summary: 收口 /scheduler/ 批次首页页面状态构建，让 route 只负责接请求、调服务和渲染页面。
tags: [scheduler, route, ui-contract, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: batches-page-viewmodel
---

# batches_page() viewmodel 设计

## 0. 承接边界

PR-8 承接 PR-7 已证明的 `/scheduler/run` 结果：表单解析、服务调用、ViewResult 构建、flash、异常边界和跳转已经完成。

但 PR-7 不证明 `/scheduler/` 批次首页。PR-8 必须自己证明批次筛选、批次行、配置面板、最近排产快照、latest summary 解析和页面快照。

明确不做：

- 不改 `/scheduler/run`、`scheduler_run.py`、`RunScheduleViewResult` 或运行排产 flash。
- 不改 `batches_manage_page()` 的新增、删除、批量修改和 `part_options`。
- 不改 `scheduler_excel_batches.py`、`scheduler_config.py` 保存链路、页面说明 registry、route wrapper。
- 不重写 `templates/scheduler/batches.html` 或 `web_new_test/templates/scheduler/batches.html`；执行中复审发现 `?status=` 已表示“全部状态”但状态下拉框没有对应选项，因此只允许补齐这个既有页面合同的选项，不改模板字段名和页面结构。
- 不改 `build_summary_display_state()`、summary、result_summary、历史落库或共享展示规则。
- 不新增业务 `if`、fallback、兜底、静默吞错、新默认值、新 reason 或新 details。
- 不减少 full-test-debt；P1-19 只按 complexity、ui_contract、test_coverage 处理。

## 1. 对外合同

- `batches_page()` route 只保留：读 `request.args`、取 `g.services`、调用服务、解析最近历史 summary、保留现有历史读取失败日志边界、调用批次页 viewmodel、渲染 `scheduler/batches.html`。
- 批次页 viewmodel 只消费普通数据和服务返回对象，不导入 Flask、service、repo 或 route。
- 没有 `status` 参数时默认 `pending`；显式 `?status=` 继续表示全部状态。
- `only_ready` 为空时不过滤；有值时按批次 `ready_status` 精确过滤。
- 批次行继续保留原始 `to_dict()` 字段，并补 `priority_zh`、`ready_status_zh`、`status_zh`。
- 当前配置面板继续复用既有配置展示 helper，不写库、不修库。
- 最近排产快照继续复用既有 summary 展示 helper；summary 解析失败时仍展示基础历史信息和公开提示。

## 2. 实现策略

1. 先新增默认可收集的 PR-8 测试，覆盖默认 status、空 status、only_ready、批次行中文字段、配置降级、无最近历史、summary 解析失败、latest algo config snapshot 和非 pending 控件隐藏。
2. 新增 `web/viewmodels/scheduler_batches_page.py`，拆出筛选状态、批次行、配置面板、最近排产快照和模板上下文构建。
3. 把 `scheduler_batches.py:batches_page()` 里的页面展示装配搬到 viewmodel；route 保留请求边界、服务调用、历史读取异常日志和模板渲染。
4. 如果复杂度降到阈值内，用 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 移除 P1-19 复杂度登记；否则停线说明，不为指标新增逻辑。
5. 执行后请 subagent 复审 PR-8 页面合同、无新增兜底、共享层影响、测试是否只断用户可见结果、CodeStable 回填和债务口径。

## 3. 验收契约

- 默认 status、空 status、only_ready、批次行中文字段均有默认可收集测试覆盖。
- 配置降级只显示公开中文提示，不泄漏隐藏字段名，不触发配置写回。
- 无最近历史显示空历史文案；summary 解析失败时仍显示版本基础信息和解析失败提示。
- latest algo config snapshot 显示目标中文名和自动回写资源状态。
- 非 pending 状态不显示执行排产控件。
- `batches_page()` 不再直接循环拼批次展示行、不再直接拼配置降级字段、不再直接算最近快照展示字段。
- 不改 `/scheduler/run`、批次管理页、Excel 批次页、配置保存链路或共享 summary 展示规则；模板只补齐 `status=` 既有“全部状态”合同的下拉选项。
- P1-19 若关闭，只写 complexity 关闭；`tools/check_full_test_debt.py` 仍按真实结果记录，不写 full-test-debt 减少。

## 4. 与项目级架构文档的关系

本次是页面 route 层职责收口，不新增用户能力、不新增跨模块业务接口。若验收确认只是 route 展示拼装下沉到纯 viewmodel，则 architecture 和 requirements 无需更新；roadmap、items.yaml、source-map 和 feature acceptance 必须回写。

---
doc_type: feature-design
feature: 2026-04-28-scheduler-run-view-result
status: approved
summary: 收口 /scheduler/run 页面提示构建，让 route 只负责接请求、调用服务、flash 和跳转。
tags: [scheduler, route, ui-contract, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: scheduler-run-view-result
---

# /scheduler/run ViewResult 设计

## 0. 承接边界

PR-7 承接 PR-6 已证明的稳定落库输出：坏排产结果会在落库前被拒绝，simulate 不改真实批次/工序状态和资源，auto-assign persist 只补内部缺资源工序的空字段。

但 PR-6 只证明 `schedule_persistence.py` 的落库合同，不证明 `/scheduler/run` route、view result、flash、跳转或页面文案已经完成。PR-7 必须自己证明 route 只做表单解析、服务调用、view result、flash 和跳转。

明确不做：

- 不处理 `batches_page()`，不拆批次页筛选、配置面板、最近历史面板或模板。
- 不改 `ScheduleService.run_schedule()`、summary、result_summary、落库、模板、`scheduler_week_plan.py`、`scheduler_batches.py`、`scheduler_bp.py`。
- 不新增业务 `if`、fallback、兜底、静默吞错、新默认值、新 reason 或新 details。
- 不减少 full-test-debt；P1-18 只按 complexity、ui_contract、test_coverage 处理。

## 1. 对外合同

- `/scheduler/run` route 只保留：读表单、调用 `ScheduleService.run_schedule()`、构建 `RunScheduleViewResult`、flash、异常边界、跳转回 `scheduler.batches_page`。
- `RunScheduleViewResult` 只消费 `ScheduleService.run_schedule()` 返回的公开 dict，并复用 `build_summary_display_state()`。
- 主提示继续保持原用户可见口径：成功显示“排产完成”，部分完成显示“排产部分完成”，失败显示“排产失败”，并带版本、成功数、失败数和超期文字。
- 降级、告警、错误预览和超期样本继续按现有公开展示规则输出，不展示内部 code、内部异常明细或 diagnostics。
- 超期批次最多展示 10 个批次号；告警、错误和次级降级继续交给现有 flash helper 控制数量。

## 2. 实现策略

1. 先新增默认可收集的 PR-7 测试，覆盖 ViewResult 纯构建和 `/scheduler/run` 用户可见 flash。
2. 新增 `web/viewmodels/scheduler_run_view_result.py`，定义 `RunScheduleViewResult` 和 `build_run_schedule_view_result(result)`。
3. 把 `scheduler_run.py` 里已有主提示、主降级、超期样本、告警和错误预览判断搬到 viewmodel；route 只按 ViewResult flash。
4. 如果复杂度降到阈值内，用 `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields` 移除 P1-18 复杂度登记；否则停线说明，不为指标新增逻辑。
5. 执行后请 subagent 复审 PR-7 合同、无新增兜底、共享层影响、测试是否绑定内部 summary、CodeStable 回填和债务口径。

## 3. 验收契约

- `RunScheduleViewResult` 纯构建测试覆盖成功、部分成功、失败、公开降级提示、告警数量、错误预览、超期样本最多 10 个。
- route 测试只 mock service，断用户可见 flash 和跳转，不断 service 内部 summary 结构。
- `run_schedule()` 不再直接解释 summary 深层展示字段。
- 不改 `scheduler_week_plan.py`、`scheduler_batches.py`、`scheduler_bp.py` 共享 helper，不改变模拟排产和批次页行为。
- P1-18 若关闭，只写 complexity 关闭；`tools/check_full_test_debt.py` 仍按真实结果记录，不写 full-test-debt 减少。

## 4. 与项目级架构文档的关系

本次是页面 route 层职责收口，不新增用户能力、不新增跨模块业务接口。若验收确认只是 route 展示拼装下沉到纯 viewmodel，则 architecture 和 requirements 无需更新；roadmap、items.yaml、source-map 和 feature acceptance 必须回写。

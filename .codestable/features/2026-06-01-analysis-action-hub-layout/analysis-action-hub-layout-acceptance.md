---
doc_type: feature-acceptance
feature: 2026-06-01-analysis-action-hub-layout
status: accepted
summary: 排产分析页首屏行动区已落地，推荐结论、代表方案摘要、主要诊断和下一步入口被放到详细表格、指标和优化过程之前。
tags: [aps, workbench, analysis, scheduler]
roadmap: aps-frontend-workbench
roadmap_item: analysis-action-hub-layout
---

# analysis-action-hub-layout acceptance

## 1. 接口契约核对

- 新增 `web/viewmodels/scheduler_analysis_action_hub.py`，输出普通 dict 形式的 `analysis_action_hub`，包含推荐卡、代表方案摘要、诊断卡、下一步入口、中文提示和空状态。
- `analysis_action_hub` 只读取已有 `candidate_comparison_display`、`diagnostic_sections` 和候选行里的 `links`，不重新计算候选方案、不改变推荐规则。
- 下一步入口从已经生成好的 `WorkbenchLink` 中筛选设备甘特图、人员甘特图、资源排班和超期清单，保留 `version`、`plan_role`、日期、查询日、周期、资源和批次上下文。
- 诊断卡只摘取诊断区已有标题、状态、摘要、代表条目和公开链接；没有可判断数据时显示“暂时不能判断”，不把未知当 0。
- 路由在 `attach_candidate_plan_links()` 之后生成 `analysis_action_hub`，保证行动区拿到的是已经带好上下文的链接。

## 2. 行为与决策核对

- `templates/scheduler/analysis.html` 的选中版本展示顺序已调整为：版本身份、行动区、告警/空状态、详细方案对比、完整诊断、指标、优化过程，趋势图仍保留在页面后部。
- 新增 `_action_hub.html` 展示“结论和下一步”行动区。行动区内部先显示推荐结论和代表方案摘要，再显示主要诊断，最后显示下一步入口。
- `_candidate_comparison.html` 继续保留完整方案对比表；当行动区已展示推荐结论和摘要时，详细对比区不重复展示这两块，避免首屏重复。
- 没有候选方案时，行动区显示“本次没有开启方案对比，只生成了正式采用方案。”这类中文空状态。
- 日期范围缺失时，行动区入口渲染为禁用状态，并显示包含“日期范围”的中文原因。
- 本阶段没有改 `core/algorithms/`、`schema.sql`、`vendor/`，没有新增外部前端资源。

## 3. 验收场景核对

- 首屏顺序：`tests/regression_scheduler_analysis_workbench_layout.py` 断言版本身份后立即进入行动区，详细方案对比、完整诊断、指标和优化过程在后。
- 行动区内部顺序：同测试断言推荐卡、代表方案摘要、诊断卡和下一步入口的相对顺序。
- 上下文链接：同测试断言行动区链接保留 `version`、`plan_role`、日期范围、`query_date`、`period_preset`、资源和批次上下文。
- 候选方案空状态：同测试断言无候选方案时显示中文空状态，不展示假推荐。
- 日期缺失禁用原因：同测试断言缺少日期范围时行动区按钮禁用并显示中文原因。
- 内部字段不外露：同测试使用可见文本提取，断言页面正文不出现 `plan_role`、`scenario_id`、`source_table`、`candidate_id`、`candidate_key`、`op_id`、`schedule_id` 等内部词。
- 旧详细对比区兼容：同测试覆盖没有传入 `analysis_action_hub` 时，详细方案对比区仍能显示推荐卡，避免旧渲染路径崩掉。
- 方案推荐中文化、三方案摘要、候选链接合同和诊断区合同由既有回归继续覆盖。

## 4. 术语一致性

- 用户可见文案使用“排产分析行动入口”“推荐结论”“正式采用方案”“原算法代表方案”“重点工序优先代表方案”“设备甘特图”“资源排班”“超期清单”等中文业务话。
- `plan_role`、`scenario_id`、`source_table`、`candidate_id`、`candidate_key` 等内部字段只留在 URL、参数或测试层，不进入普通页面正文。
- 诊断表达继续使用“暂时不能判断”“这块信息不完整”等保守说法，不写“唯一根因”。

## 5. 架构归并

- 已更新 `.codestable/architecture/ARCHITECTURE.md`：
  - 记录 `scheduler_analysis_action_hub.py` 是排产分析首屏行动区的 ViewModel。
  - 记录 `_action_hub.html` 是行动区模板。
  - 记录分析页选中版本后的新顺序。
  - 明确行动区只复用已有候选展示、诊断展示和 `WorkbenchLink`，不重算业务规则。

## 6. requirement 回写

- 已更新 `.codestable/requirements/candidate-comparison-business-view.md`：
  - 状态从 `draft` 更新为 `current`。
  - `implemented_by` 补入候选方案空状态、三方案摘要、工作台链接合同和本阶段行动区。
  - 新增当前实现和 2026-06-01 变更日志。

## 7. roadmap 回写

- 已把 `.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml` 中 `analysis-action-hub-layout` 标记为 `done`。
- 已把 roadmap 主文档第 6 节子 feature 清单第 4 条标记为 `done`。
- 已在 roadmap 变更日志记录本阶段完成情况。

## 8. attention.md 候选盘点

- 本阶段没有发现需要写入 `.codestable/attention.md` 的新环境陷阱或长期启动注意事项。

## 9. 遗留

- 诊断卡目前只展示已有诊断信息；诊断卡里的专门“继续查看入口”依赖后续报表回跳、延期事实桥接和资源派工分层，不在本阶段承诺补齐。
- 后续 `gantt-task-detail-panel`、`resource-dispatch-execution-lane`、`reports-workbench-backlink` 继续按 roadmap 推进。

## 验证附录

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_analysis_workbench_layout.py tests/regression_scheduler_candidate_plain_language.py tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scheduler_analysis_template_parts.py tests/regression_scheduler_analysis_diagnostic_contract.py tests/regression_scheduler_analysis_candidate_links_and_roles.py`：110 passed
- 本地 SubAgent 双轨复审：定向复审与盲审均为“无阻塞”，用后已关闭。
- Claude Code 独立复审：delegate `claude-analysis-hub-review2-20260601-120517-93908` 使用两个 `model: "opus"` 子代理，结论为“无阻塞”；delegate tmux 会话和本次 Terminal 残留窗口已清理。

---
doc_type: feature-acceptance
feature: 2026-05-22-gantt-draft-save-and-preview
status: accepted
roadmap: gantt-result-view-and-manual-adjustment
roadmap_item: gantt-draft-save-and-preview
summary: Scenario 模拟方案可保存，并可通过 scenario_id 在只读甘特图中显式预览；正式排产版本和默认结果页不变。
tags: [scheduler, gantt, scenario, preview]
---

# gantt-draft-save-and-preview acceptance

## 验收结论

本阶段完成了 Scenario 模拟方案保存和只读甘特图显式预览：

- Draft 会在保存 Scenario 前重新校验。
- `blocked` 草稿不能保存。
- `valid` / `warning` 草稿可以保存成 Scenario。
- 保存 Scenario 不写 `Schedule`、`ScheduleHistory`、`ScheduleVersionSeq`、`ScheduleCandidate*`。
- 甘特图带 `scenario_id` 时读取 Scenario 行。
- 甘特图不带 `scenario_id` 时仍走旧的正式版本 / 候选方案链路。
- 找不到、版本不匹配、角色不匹配的 `scenario_id` 会报错，不回退到 adopted。
- 页面、视图切换、周切换、查询表单和数据请求都会保留 `scenario_id`。
- 页面明确提示“当前正在预览模拟方案，正式计划还没有改变”。

## 主要证据

- `tests/regression_gantt_draft_save_and_preview.py` 覆盖迁移、保存、blocked 拒绝、正式表不变、显式预览和非法 Scenario 不回退。
- `tests/regression_gantt_adjustment_draft_model.py` 和 `tests/regression_gantt_adjustment_validate_simulate.py` 继续锁住 Draft 与校验阶段合同。
- `tests/regression_gantt_critical_chain_provider.py` 继续锁住关键工序缓存和候选方案链路。
- `tests/check_quickref_vs_routes.py` 通过，接口速查表和真实路由一致。

## 对抗审核

本阶段使用 3 个子代理做了对抗审核：

- 保存链路审核：无阻塞问题；确认 Scenario 保存不写正式排产表，blocked 会拒绝。
- 查询链路审核：无阻塞问题；确认 `scenario_id` 贯穿时间范围、明细、超期标记和关键工序。
- 页面/路由审核：无阻塞问题；确认页面和 JS 不丢 `scenario_id`，没有打开拖动保存或正式发布入口。

一个非阻塞建议已采纳：v12 升级测试增加 Scenario 索引和 `detect_schema_is_current()` 断言。

## 本阶段不做

- 不打开拖动编辑入口。
- 不发布正式版本。
- 不生成新的正式版本号。
- 不把 Scenario 默认用于报表、周计划或资源排班。
- 不新增正式采用按钮。

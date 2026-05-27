---
doc_type: feature-acceptance
feature: 2026-05-27-candidate-drilldown-empty-states
status: accepted
roadmap: aps-three-gap-directions
roadmap_item: candidate-drilldown-empty-states
created: 2026-05-27
---

# 方案对比钻取、空状态和失败状态验收

## 验收结论

已完成。

本阶段把方案对比的“能不能点进去看明细”从简单看角色存在，改成先看这套方案是否真的有可查看明细。没有保存候选明细时，页面不再给假跳转，而是直接用中文告诉用户“这套对比参考方案没有保存明细，当前无法查看明细。”正式采用方案仍然可以正常跳到甘特图、周计划和资源排班。

## 已落地范围

- 分析页方案对比行新增 `detail_saved`、`can_open_detail` 和中文不可查看原因。
- 链接生成层只在方案身份存在且明细可打开时生成设备甘特图、人员甘特图、周计划、资源排班四个入口。
- 模板无链接时展示 ViewModel 给出的中文原因，不自己读取内部字段判断。
- 资源负荷页和停机影响页的摘要与“当前方案”统一使用模拟预览公开名称；没有名称时显示“模拟预览（未命名）”。
- 报表导出测试补充文件名、工作表名、表头和工作簿内容的内部字段防泄漏检查。
- 测试补充候选方案 stream 导出，防止大数据导出路径漏出内部字段。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_analysis_candidate_links_and_roles.py tests/regression_scheduler_candidate_reports_contract.py tests/regression_scheduler_candidate_plain_language.py tests/regression_frontend_offline_static_assets.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_candidate_analysis_contract.py tests/regression_scenario_preview_secondary_outputs.py tests/regression_report_export_size_mode_selection.py tests/regression_reports_export_version_default_latest.py`
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/regression_report_export_size_mode_selection.py`

## 子代理复审

- 调查阶段使用 5 个子代理，分别检查分析页跳转链路、周计划页面和导出、资源负荷与停机影响报表、测试覆盖、CodeStable 和提交隔离。
- 实现后第一轮使用 4 个子代理做对抗性审核，分别检查假跳转、报表导出、提交隔离、用户可见文案和离线资源。
- 第一轮复审发现的阻塞点已经修复：补 CodeStable 回写，补未命名模拟预览提示条精确测试，补候选方案 stream 导出防泄漏测试，提交时排除后续执行事件和 schema 草稿。
- 修复后已补同范围第二轮复审：子代理 `019e6722-e7f5-7280-8e35-9f7cfc0c2b58` 复查方案对比钻取、空状态、报表导出、用户可见中文、离线资源和提交隔离，结论 OK，无阻塞项。

## 未做

- 不新增候选方案全量明细大屏。
- 不做任意两个候选方案自由比较。
- 不开放派工确认、开工、完工或报异常。
- 不改排程算法。
- 不改数据库、迁移或现场执行事件。

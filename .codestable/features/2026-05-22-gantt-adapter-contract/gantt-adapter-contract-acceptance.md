---
doc_type: feature-acceptance
feature: 2026-05-22-gantt-adapter-contract
status: accepted
roadmap: gantt-result-view-and-manual-adjustment
roadmap_item: gantt-adapter-contract
summary: 甘特图 Frappe 适配层已落地，查看模式、缩放、点击和未来模拟事件出口完成合同收口。
tags: [scheduler, gantt, adapter, acceptance]
---

# gantt-adapter-contract acceptance

## 1. 完成范围

- 新增 `static/js/gantt_adapter.js`，统一创建 Frappe Gantt。
- `static/js/gantt_render.js` 不再直接拼 Frappe options，而是通过 adapter 创建实例。
- 模板和镜像模板在 `gantt_zoom.js` 后加载 `gantt_adapter.js`。
- 新增 `tests/regression_gantt_adapter_contract.py`，覆盖 view/simulate、缩放、点击回调和真实 vendor 几何。
- `tools/test_registry.py` 把适配层测试纳入甘特图门禁分组。

## 2. 明确未做

- 没有开放模拟调整按钮。
- 没有保存草稿。
- 没有新增后端保存接口。
- 没有写 `Schedule` / `ScheduleHistory`。
- 没有替换甘特组件，也没有改 vendor 文件。

## 3. 验收结果

- `view` 模式继续只读，禁拖、禁拉伸、禁进度拖动。
- `simulate` 模式只提供未来 `onDraftChange` 事件出口，不连接保存。
- 缩放仍复用 `gantt_zoom.js`，没有复制第二套映射。
- 点击任务条详情和批次聚焦保留。
- 下一阶段可以启动 `gantt-simulation-entry-shell`，但仍不能保存正式计划。

## 4. 证明

- `node --check static/js/gantt_adapter.js`
- `node --check static/js/gantt_render.js`
- `pytest -q -p no:cacheprovider tests/regression_gantt_adapter_contract.py tests/regression_gantt_readonly_mode_contract.py tests/regression_gantt_zoom_contract.py tests/regression_gantt_zoom_decoration_sync.py tests/regression_gantt_zoom_range_guard.py tests/regression_gantt_critical_outline_sync.py tests/regression_scheduler_candidate_py38_contract.py`

---
doc_type: feature-ff-note
feature: browser-extreme-stress-data
date: 2026-06-10
requirement:
tags: [scheduler, browser-qa, stress-data, gantt]
---

## 做了什么
新增一个前台浏览器极限压测造数入口，用隔离临时库生成更复杂的排产数据，方便直接打开浏览器看排产页和甘特图表现。

## 改了哪些
- `tests/_scripts_e2e/run_browser_extreme_stress_case.py` — 复用原合成压测底座，叠加班组、人员日历、设备停机、外协组、交期挤压、长短工序和隐藏失败边界批次。
- `docs/dev/aps-browser-scheduler-qa-replay.md` — 记录 2026-06-10 前台实跑规模、前台排产结果、甘特范围保护和设备/人员视图验证结果。

## 怎么验证的
用 `.venv/bin/python -m py_compile` 做语法检查；生成 91 个主批次和 867 道批次工序的临时库后启动本地服务，并在可见浏览器里执行排产，版本 1 成功 819/819，设备/人员甘特首周均渲染 208 条任务，时间粒度切到小时后仍正常显示。

---
doc_type: issue
slug: trial-adoption-issue-severity
status: fixed
created: 2026-09-15
last_reviewed: 2026-09-15
related_roadmap: workbench-manual-remediation
validation_status: targeted-passed-manual-recheck-pending
---

# 试调采用预检的真实阻断原因被当成响应损坏

## 现场与根因

5005 手动验收从正式 v15 创建并调整了 74 道工序的试调，保存为场景 `24f3a24c774f798956d313f329fada7373bd56e440bf65ae`、源草稿 `5af05e356ed5142b1073d96074a48ad4fcb60917c9701dae`。采用预检显示“读到的采用数据不完整或对不上”，无法确认。

实际只读调用定位到：`trial_adoption_validation.py:35–37` 将 12 条 `batch_not_ready` 问题作为阻止正式采用的原因返回，但它们沿用了草稿检查的 `severity=warning`。`TrialAdoptionAPI.js:20–22,42` 明确只接受采用阻断原因中的 `severity=blocker`，因此正确的业务原因被前端判为响应不合约。不是场景工序缺失、已报工数据丢失或引用错配。

## 修复

`core/models/workbench_trial_adoption.py:14–17` 在构造 `TrialAdoptionBlocked` 时复制每条问题并将其 severity 规范为 blocker。问题 code、message、task_ref 和 related_task_ref 保留。该异常本身表示“此问题正在阻止正式采用”，因此输出类型与采用结果一致；保存时原场景的 warning 状态不变。

没有降低前端校验、没有过滤齐套问题、没有改 `_settings` 或采用资格、没有重写场景/草稿、没有放宽报工保护及完整范围约束。前端无需修改或重新构建。

## 定向验证

- 新增 API 回归使用真实临时 SQLite 场景和实际 HTTP 预检响应，再交给项目真实 `TrialAdoptionAPI.js` 源码解析；修复前在其第 42 行精确复现用户错误，修复后通过。
- 2 个新增参数用例覆盖 `ready_status=no/partial`。预检仍不可采用、无写入令牌，issues 与 blocked_reasons 一致且具有正确 blocker 类型，场景原 warning 和全部数据库快照不变。
- 运行 `test_trial_adoption_api.py`、`test_trial_adoption_validation.py`、`test_trial_adoption_raw.py`、`test_trial_adoption_atomic.py`、`test_trial_source_presentation.py`：**54 passed in 12.31s**。
- 补充既有 `test_trial_adoption_boundaries.py`、`test_trial_adoption.py`：**25 passed in 6.34s**。这些用例继续验证未齐套拒绝、正式版本/报工/资源/日历/工时等漂移拒绝以及正常采用。
- 共 79 个专项通过；`git diff --check` 对本项文件通过。新增用例位于既有注册文件，不新增注册项。

对现场库使用 SQLite URI `mode=ro` 及正式日期转换选项，在临时 Flask 请求上下文中调用原预检路由，再让实际前端源码解析原响应：HTTP 200、解析成功、12 条 blocker、`can_adopt=false`、连接 `total_changes=0`。对应问题为：

| 批次 | 当前齐套状态 | 涉及工序 |
| --- | --- | --- |
| QA-20260509-B07 | partial | 4 |
| QA-20260509-B11 | no | 2 |
| UX-0510-E04 | partial | 4 |
| UX-0510-E05 | no | 2 |

## 齐套规则的证据边界

- 既有实现 `trial_adoption_validation.py:113–117` 固定 `ready_check=True`；`trial_validation.py` 的草稿检查允许 warning 保存，正式采用则重新校验并拒绝这些问题。
- 既有测试 `tests/workbench/test_trial_adoption_boundaries.py:15–43` 已包含 readiness 参数，明确设置 `ready_status=no` 后预检不可采用、直接采用也必须拒绝。这是本次修复前已存在的可执行合同。
- `.codestable/features/2026-09-09-workbench-trial-adoption/` 的说明要求复核当前真实约束、不能借 HTTP 成功发布冲突场景；没有找到“试调采用必须继承原排产齐套开关”的明确文档承诺。
- 当前 v15 的 `ScheduleHistory.result_summary.run_ref` 为 `46101de71a13c41ec1e28f3e32d3ec644dd8151d7f5950bc`，其原运行输入确实是 `ready_check=False`。该设置可追溯；候选来源快照还保存 `source.capture.input`。但正式计划来源的 `trial_base._plan` 只返回 identity/source_table，现有试调 admission 没有定义继承该设置的 policy 字段或规则。因此本轮没有据此自动绕开既有强制齐套检查。

主代理可通过 UI 补齐上述测试批次，基于更新后的真实快照重新建立试调，继续正向采用验收；旧场景不会被悄悄刷新成新资料。

本代理未操作浏览器、未构建、未重启、未写入现场业务数据。未运行全门禁或整仓测试；保留既有脏工作区，不提交，不声称 clean-worktree proof。

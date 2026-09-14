---
doc_type: issue-fix-note
issue: nine-test-failures
date: 2026-09-14
tags: [tests, runtime, browser, reports, portable]
---

## 范围与原因

修复便携版验证期间收集到的九项失败。五项后台任务测试共用的 `paused_compute` 替身不接受正式调用的 `on_progress`；导航脚本已完成 28 项检查，Python 包装器仍要求 26 项；几何测试使用了旧按钮名称和旧页面文案；报表与执行复盘的恢复测试在异步响应体采集完成前读取响应列表。

## 实际修改

- `tests/workbench/run_runtime_support.py`：显式接收并转交 `on_progress`，保留暂停、释放及真实计算路径。
- `tests/workbench/test_final_foundation_navigation.py`：核对实际执行的 28 项检查全部通过。
- `tests/ui_geometry_probe_scenarios.mjs`、`tests/app_runtime/ui_geometry_contract_data.py`：同步“展开计划列表”和当前报表列表、日期输入、查询按钮、读取提示的名称；保留真实批次、精确日期及全部布局阈值。
- `tests/workbench/final_execution_report_reentry.cjs`：收到响应时同步记录位置，跟踪所属请求与响应体读取；在页面切换、重启及采样前显式等待完成。读取错误保留到证据并令测试失败，超时明确报错。
- 本次不修改生产排产逻辑，不删除或降低布局、数据、快照、重启、备份和停机断言。

## 验证

- 原失败的五项后台任务用例与导航用例：`6 passed in 1.93s`；日志 `/tmp/aps-nine-fixes-runtime-20260914.log`。
- 页面几何原失败用例：`1 passed in 19.44s`，覆盖 20 个场景 × 1024/768 两种宽度及数据保留断言；日志 `/tmp/aps-geometry-fix-20260914-r2.log`。直接关联的三个小契约测试另有 `3 passed in 1.32s`，日志 `/tmp/aps-geometry-contract-fix-20260914.log`。
- 报表恢复：`.venv/bin/python -m pytest tests/workbench/test_final_execution_report_reentry.py -q`，`2 passed in 26.34s`；日志 `/tmp/aps-report-reentry-fix-20260914.log`。reports/review 均完整执行侧栏返回、F5、同端口新进程恢复、真实导出、旧快照显式拒绝、明确刷新及不存在工序的错误路径。
- 原九项失败现已全部定点通过，另有三个直接关联契约用例通过；未跳过失败用例，未删除原断言。`git diff --check` 通过。

## 交付与限制

- 用户明确要求修复后提交并推送，并跳过完整质量门禁；本次仅执行针对性验证，提交和推送不触发本地门禁钩子。不宣称整仓门禁通过或 clean-worktree proof。
- 同次交付包含此前已实现并验证的 Win7 便携版改动，详见 `.codestable/features/2026-09-14-win7-portable-release/win7-portable-release-ff-note.md`。
- 当前宿主为 macOS；Windows EXE、PowerShell 5.1 和 Win7 真机验收不在本次已完成的验证范围内。

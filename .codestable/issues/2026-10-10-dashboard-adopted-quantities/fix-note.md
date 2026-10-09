---
doc_type: issue-fix-note
date: 2026-10-10
status: in-progress
---

# 值班台丢失已采用计划的工序数量

状态：共同根因已修复，宿主 5000 工序只读复核通过；HTTP 后置复验及 Win7 实机复验继续进行。

真实复杂样例完成排产、采用和六条分次报工后，后置 HTTP 验收发现值班台的全部 5000 个工序丢失采用数量。现场实际甘特及正常计划任务读取正确；值班台 `quantity`、`batch_quantity` 均为 null，`quantity_basis=unknown`，`quantity_reason=plan_target_not_recorded`。其余任务身份、原始时间、资源及工序字段一致。例 `CS-BATCH-001` 的正确数量为 8。

共同根因是 `DashboardFacts._plan` 调用既有 `project_tasks` 时漏传 `conn`，导致既有 `_adopted_quantities(None, plan_ref)` 明确返回“未记录”，从未读取正式采用审计的不可变来源。修复仅补 `conn=self.conn`，复用原审计核验及采用时数量转换；没有读取当前批次数量兜底，没有修改算法、额度或业务数据。

全局搜索和 AST 检查生产代码中的全部六处 `project_tasks` 调用，原唯一遗漏是值班台。修复后计划查询、值班台、基线比较和基线身份验证均传入原读事务连接。

忽略目录 `output/win7-complex-20261010/` 保存：

- `final-host-after-partial-http-red-v1.json`：原后置验收失败未覆盖。合并值班台、独立分析、完整实际甘特均为真实 HTTP 200/no-store，单请求未超过 60 秒；合并 envelope 8343508 B，`analysis_error=null`。失败原因是任务数量事实不一致，不是读取超时。
- `dashboard-actual-task-field-difference.json`：两次真实 HTTP 诊断、全部 5000 个差异统计、四字段的原值和正确值；未改数据。
- `project-task-call-conn-audit.json`：全部六处生产调用的连接参数检查。
- `dashboard-adopted-quantities-readonly-green.json`：修复代码以独立 query-only 连接读取已有正式计划和六条真实部分报工。值班台、正常计划任务查询、完整现场实际甘特的 5000 个任务身份及四个数量字段逐一完全一致；数量均为真实已采用值，`quantity_basis=run_admission`、`quantity_reason=null`。没有任何写 SQL。此证据不替代重启后的真实 HTTP 或 Win7 实机验证。

新增 `tests/workbench/test_dashboard_adopted_quantities.py`：真实 worker → 候选采用，以及真实试调保存 → 试调采用两种来源；每路对计划、实际甘特、报工、合并值班台、独立分析五个公共 API 核对六个分件任务（数量 1）及两个共同任务（数量 3）。再经真实 `BatchService.update` 把当前批次数量从 3 改为 5，证明已采用任务的数量、批量、来源依据及缺项状态不随当前资料变更；所有 GET 表快照未变。正常修复 2 passed（9.78 秒），Ruff 通过；隔离进程仅恢复旧 dashboard 缺连接行为，两路均准确失败（12.67 秒），没有替换 worker、审计或数量判断。两次输出分别保存在 `dashboard-adopted-quantities-test-initial.log`、`dashboard-adopted-quantities-test-red.log`。

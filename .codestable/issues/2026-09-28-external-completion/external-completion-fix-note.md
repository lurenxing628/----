---
doc_type: issue-fix-note
status: verified-related-scope
date: 2026-09-28
issue: external-completion
summary: 外协完工以空本厂资源进入排产和试调，保留自制资源及执行事实保护
---

# 外协完工后续排产修复

用户授权修复前一轮独立复查发现的 P1，并将工作区全部业务改动分批提交和推送。沿用只跑相关测试、不跑完整门禁的要求。本轮由主代理直接修复，没有新增子代理。

## 根因与修复

- `execution_ledger_guard.ledger_fact_changes` 原来无条件要求唯一设备和人员。现在从 `ExecutionLedgerScopeRepository.scope_task_rows` 读取实际工序来源；外协允许两个资源为空，自制继续检查唯一有效资源，未知来源和外协误带本厂资源明确拒绝。
- `schedule_execution_guardrails._build_execution_seed_result` 原来也对外协调用自制资源校验。现在外协沿用实际起止时间并保持空资源，不预留本厂产能；自制仍走原资源保护。
- `trial.execution_anchors._seed_arrangement` 原来按空资源键查永久引用。现在空资源保留为空，非空资源仍严格按已登记引用解析，支持已完工外协在正式计划试调后再次采用。
- 新增 6 个回归场景：整批/分件外协，选中/未选中该外协的后续排产；选中时继续采用、试调、再采用；以及自制缺资源和外协误带资源的拒绝保护。另一自制批次仍在原可用时间开工，证明外协未占本厂产能。
- 修复相关旧测试夹具：显式安装设备多工种和多时段日历合同；用于部分报工保护的批次采用完整整批路线；日历证书断言覆盖当前七组事实。没有放宽产品校验。

## 验证

证据位于 `evidence/external-completion-fix-20260928/`，仅使用临时 SQLite 数据库，未修改生产数据。

- 初轮相关回归：128 个节点中 122 通过，6 个旧夹具失败；针对修正的两份测试复跑 26 通过。
- 修正后完整相关组最终结果：128 passed（`related-final.log`）。产品修改文件局部 Pyright：0 errors / 0 warnings；修改范围 Ruff 通过。
- 本次只声明相关范围验证。分批提交及远端合并后的检查结果另记录在交付记录，不将历史验证或工作区清洁状态冒充完整门禁证据。

## 可恢复记录

整理前所有 505 个非忽略改动已保存到 `/tmp/aps-before-batched-commit-20260928-232252.{json,patch,tar.gz}`；包含原 HEAD、路径和文件摘要。原始诊断与历史修复记录保留。

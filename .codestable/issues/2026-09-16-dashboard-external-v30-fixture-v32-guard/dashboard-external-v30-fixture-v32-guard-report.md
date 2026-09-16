---
doc_type: issue-report
issue: 2026-09-16-dashboard-external-v30-fixture-v32-guard
status: resolved
resolved: 2026-09-16
severity: P2
created: 2026-09-16
source: 日常门禁 daily-fast-gate（2026-09-16 提交批次收尾时的 44 个失败之一）
tags: [workbench, dashboard, outsourcing, schema, v32, test-fixture]
---

# 外协处置回填测试的 v30 冻结夹具撞上 v32 读取守卫

## 现象

`tests/workbench/test_dashboard_external_handling_schema.py::test_explicit_helper_backfills_only_mapping_and_is_idempotent`
在本批提交后稳定失败，错误是

```
core.models.workbench_command.WorkbenchCommandRejected: 真实外协登记结构尚未完整接入；未补表或改动原资料。
```

## 复现

1. `tests/workbench/dashboard_external_migration_support.py::fixed_v30_connection` 用冻结的 v30 DDL 建库并把
   SchemaVersion 写成 30，不跑任何迁移。
2. 用例先对这个 v30 库调用 `core/infrastructure/workbench_dashboard_external_schema.install`（被测的外协处置
   映射回填助手），再用 `case.item("external")` 读回结果。
3. 读取路径 `core/services/workbench/dashboard_external.py:99` 调用
   `WorkbenchOutsourcingRepository.require_schema()`，该方法在本批 v32 之后额外要求
   `core/infrastructure/workbench_outsourcing_source_schema.contract_issues` 为空，也就是要求
   `WorkbenchOutsourcingSourceConfirmations` 表及其触发器齐全。v30 夹具没有这张表，读取被拒绝并返回 503。

## 事实与证据

- 基线 `7034b873` 上 `require_schema` 只核对外协本表、元数据与计划身份三组合同，用例通过。
- 本批 `data/repositories/workbench_outsourcing_repo.py:20-22` 把来源确认合同并进了 `require_schema`，
  这是 `wbfix-outsourcing-existing-source` 条目「存量工序的当前来源确认」的一部分，属于有意收紧。
- 用例本身验证的是「回填助手只补映射、幂等、不碰原对象」，与外协来源确认无关；它失败是因为读取阶段
  经过了一个新增的、与被测对象无关的前置守卫。

## 影响

- 只影响这条回归用例和「拿 v30 冻结库直接读外协/仪表盘」这种测试场景；生产库都已迁到 v32。
- 日常门禁会因此挡住推送，直到二选一处理。

## 可选处理（待裁决，本轮按用户要求搁置）

1. 夹具在读取前补装 v32 两张表（`workbench_outsourcing_source_schema.install` +
   `workbench_execution_void_schema.install_execution_voids`），被测助手本身不动，原对象 DDL 相等的断言照常保留。
2. 把 `require_schema` 拆成读/写两级：仪表盘只读路径不要求来源确认表。代价是外协来源合同的覆盖面变窄。
3. 用 `pytest.mark.xfail(strict=True, reason=<本 issue>)` 显式挂起该用例，直到 1 或 2 落地。

用户于 2026-09-16 先选择搁置、只记录；同日在推送前收尾时听取解释后改选选项 1。

## 处理（2026-09-16，选项 1）

- `tests/workbench/dashboard_external_migration_support.py` 新增 `install_v32_read_guards(conn)`：在调用方的
  事务里补装 `WorkbenchOutsourcingSourceConfirmations` 与 `WorkbenchProductionReportVoids` 两组对象，
  分别走 `workbench_outsourcing_source_schema.install` 和 `workbench_execution_void_schema.install_execution_voids`。
- `test_explicit_helper_backfills_only_mapping_and_is_idempotent` 在 `case.register()` 之前调用一次；
  被测的回填助手、`production_storage` 前后相等与原对象 DDL 相等的断言全部不动。
- 没有改共享夹具 `external_v30_case`：`tests/workbench/test_dashboard_external_reads.py:18-24` 明确锁住
  「冻结 v30 库缺 v32 表时外协类目读取为 unavailable 且表不存在」，把补装放进夹具会让它失败。
  两个用例对同一夹具的诉求不同，所以由需要「loaded」读取的用例自己补装。
- 验证：`test_dashboard_external_handling_schema`、`test_dashboard_external_reads`、
  `test_dashboard_external_migration` 三个文件 56 passed；ruff 通过。

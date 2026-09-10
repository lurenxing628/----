---
doc_type: feature-design
feature: workbench-template-lineage
status: approved
summary: 在真实模板复制事务保存永久来源与完整内容，版本化保留实例变更，接入D05有效样本。
tags: [workbench, lineage, calibration]
---

# 依据和范围

本轮实施由用户明确批准，遵循 workbench-contracts §8.2/D05，不重启审批。
仅独占来源模块、专属测试/文档，以及 batch_operations.py、batch_template_ops.py、calibration_facts.py 的最小接合。
不修改 schema.sql、migrations、current version、main、registry、UI、执行 ledger 或其他代理文件。
不访问生产库、旧预览端口63938、PID68615；不启动子代理，不 stage/commit。

# 存储契约

- `WorkbenchTemplateLineageOrigins` 每个永久执行 `operation_ref` 最多一个不可修改的来源。
- 来源包含 `template_operation_ref`、当时 `template_revision`、完整原始模板行、完整新实例状态、两个 SHA-256 指纹和证据格式版本。
- 每个 SQLite 值带类型编码：NULL、INTEGER、REAL、TEXT、BLOB 严格区分；BLOB 用十六进制可逆保存，浮点用 hex 可逆保存。新批次写入不经过旧 model 的 NULL→0 转换。
- `WorkbenchTemplateLineageEvents` 只追加创建、工序变更、批次语义变更、永久引用退役、明确撤回。状态列没有 affinity，保留原始 SQLite 类型。
- 新引用生成时才记录 birth；安装不回填任何已有实例的 birth 或来源。旧实例没有源证据就是不足，不从图号、序号、工种、相同工时猜配。
- 工序工艺字段或批次所属零件/数量曾改变即污染；恢复原值不能抹除历史。状态、资源分配、展示编号改变有版本记录，但不单独构成模板工艺污染。
- 删除或 REPLACE 通过永久引用退役保留旧来源，即使 SQLite recursive_triggers=OFF 也不换绑。原来源和事件禁止 UPDATE/DELETE/REPLACE。
- 明确复制实例时保存直接父来源和复制当时 `source_event_id/source_eligible`；父实例之后变化不改写子实例当时来源。复制一个已有污染/撤回来源的实例仍保留来源，但不能重新变成合格样本。无来源实例的复制也不能凭空生成模板关系。
- schema helper 仅暴露 `objects/contract_issues/install`，install 必须由调用方显式事务持有；首次安装、重复检查和事务回滚均不更新任何业务表。不修改或分配全局 schema version，不自动修复部分安装。

# 真实调用链

1. `BatchService.create_batch_from_template` → `batch_template_ops.create_batch_from_template_no_tx` → `TemplateLineageWriter.copy_template`。
2. 旧 Excel `batch_excel_import.import_batches_from_preview_rows(auto_generate_ops=True)` 复用同一路径。
3. `WorkbenchBatchOperationService.sync` → `insert_operation(template=True)` → 同一 writer；先检查 schema 再删除旧实例。
4. `WorkbenchBatchBulkService.apply(copy)` → `insert_operation(template=False)` → `copy_instance`，按源实例真实永久关系保留复制修订。
5. 手工编辑、旧服务直接更新、删除/替换：通过来源专属触发器留痕，不修改执行账本。

缺少来源 schema 时，需要保存来源的新复制显式失败并由原事务回滚，不静默漏记。没有发生复制的旧资料读取仍保持明确不足。

# 校准接合

`CalibrationFacts.read` 批量读取明确来源，复核来源指纹、birth、当前状态与变更历史，再使用同一个 `ExecutionLedgerService.load/project_loaded`。
每个实例只投影一次；按准确模板永久引用和修订筛选有效样本，同零件待核对实例只计候选/排除数。
沿用近20、至少5、中位数和完整报工口径；NULL不按0。模板更新定额后的新 revision 不与旧 revision 混算。
新增 `samples_by_template`、`unbound_samples_by_part`、`source_constraints` 供主线详情/UI接合；保留 `samples_by_part` 审计集合，不得把该集合的所有 selected 行直接当某一模板样本。
采纳/锁定仍关闭，没有假装已接采用事务。

# 验收

真实 SQLite、真实 BatchService/工作台命令/模板身份修订/执行 ledger；覆盖复制、同步、手改、幂等、撤回、旧实例、改码、重建、模板修订、污染转复制、回滚、原BLOB保留、五样本建议。
执行 scoped ruff、pyright、Python3.8语法、大小/复杂度扫描；共享目录已有大量并发脏改，只报告局部 dirty 验证。

# 主线协调项

2026-09-10 本轮主线要求立即确认DDL后，已通知定稿并冻结：2表、3索引、10触发器，共15对象。
`objects()` 的 `json.dumps(sort_keys=True,separators=(",",":"),ensure_ascii=True)` SHA-256：
`a276b25bec87ac42895ebf0104cec2b50234b870a973fe3fc750b1c542abbd33`。
helper 文件 SHA-256：`0c85019ffcef59a4c3410d1dd969e4318b5dbfafb51b9bacfc7c2ddb4044f76a`。
主线统一v27合并lineage+trial；后续DDL或影响DDL的模型字段常量变更必须先通知主线。

- `core/services/scheduler/batch_copy.py` 是另外的旧批次复制入口，当前写域不允许修改；请由主线改用 `TemplateLineageWriter.copy_instance`，以取代它的 model 数值默认化复制。此项已在会话中明确报告路径。
- `core/services/workbench/calibration.py` 的 workspace 尚写死“全部未关联”，详情仍取 `samples_by_part`。请主线读取 `facts.source_constraints`，详情用目标 `samples_by_template[template_ref]` 与明确标注的 unbound candidates；不能混用别的模板 selected 标记。此项已明确报告路径。
- 统一迁移安装来源 helper、测试registry、路由/UI验收、采纳与锁定不在本任务写域。
- 已安装新schema的旧批次回归发现 `tests/workbench/test_batch_commands.py:test_delete_preserves_every_unrelated_table_and_other_batch` 的 affected集合需要主线更新：删除必须追加来源退役事件，其专属 sqlite_sequence 因此推进。这不是其他业务表被修改；专属测试逐表核对并只允许该事件序列变化。本任务不越界修改共享测试。

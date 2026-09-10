---
doc_type: feature-design
feature: wb-execution-ledger
status: approved
summary: 分次报工的永久身份、只追加修订与统一执行投影领域层
tags: [workbench, execution, sqlite]
---

# 0. 授权与事实

按本轮用户授权和 roadmap `wb-execution-ledger` 实施领域层；来源是
`workbench-contracts.md` 第3/6节。不改迁移注册、旧执行服务、排产、plan/batch/report、web/frontend/build。
不启动其他代理，不提交。当前工作区已有大量 staged/dirty，本轮只能提供局部验证。

# 1. 范围

复杂度：跨表事务与历史事实整合。复用永久 operation/task/plan 引用和
`WorkbenchCommandService.execute`，仅提供 `install_execution_ledger(conn)` 给主代理接迁移。
查询不安装、不补身份。实际小时永远不从跨度或计划时间推导。

# 2. 接口交付

DTO：`core.models.workbench_execution.ProductionReport/ExecutionProjection`，`to_dict()` 为契约第6节完整字段。
额外 `revision_ref` 是随机持久原值引用，不是内部 revision；`local_operator` 是服务端本机操作者，
`declared_operator` 是用户填写声明人，二者分开。

```python
ExecutionLedgerService(conn, *, clock=None, context_factory=None)
  .get_task(task_ref, *, comparison_task_ref=None) -> ExecutionProjection
  .get_report(report_ref) -> ProductionReport
  .project_operations(operation_refs, *, comparison_plan_ref=None) -> list[ExecutionProjection]
  .list_tasks(plan_ref, *, size=100, after_task_ref=None) -> dict
  .snapshot(operation_ref) -> dict  # 私有写上下文，不进公共DTO
  .read_snapshot()                 # 多次查询共享读取事务
  .find_report(report_no) -> ProductionReport | None
  .workspace_projection(plan_ref, tasks) -> dict

WorkbenchProductionReportService(conn, *, clock=None, context_factory=None, actor_provider=None)
  .execute(action, ref, payload, *, request_key, validate_context) -> CommandResult
  .preview(action, ref, payload) -> dict  # 只读校验，不签完成回执
  .preview_batch(items) -> dict
  .execute_batch(items, *, context_ref, request_key, validate_context) -> CommandResult
  .execute_import(preview_ref, *, request_key, load_items, validate_context) -> CommandResult
```

`action=create/supplement/correct`；create 的 ref 是当前正式 task_ref，其余为 report_ref。
`validate_context(ref, action, snapshot)` 必须在外层命令事务内校验原 write_token。
`context_factory(ref, actions, snapshot)` 对接既有令牌签发器；未接时明确不可写，不伪造令牌。
写命令统一自己调用 `WorkbenchCommandService`，不提供自行 commit 的 apply。
重放使用原始规范化 sparse 输入，在 guard/时钟/当前事实校验之前返回原 receipt。

`workspace_projection` 返回 `available=true/time_basis=factory_local/projections/resources/snapshot_facts`。
`projections` 是完整DTO字典列表；资源目录分 `machines/operators`，每项
`{kind,ref,business_code,label,available}`，同时包含新报工和可核实的旧实际资源。
无法消歧的旧资源只返回null与 `legacy_resource_identity_unresolved`，不能按现值同号关联。
`snapshot_facts` 包含 ledger/plan clock、投影hash、资源hash与 `legacy_source_hash`。
需要固定as_of时构造器传 `clock=lambda: captured_factory_local_datetime`，不在每次子查询换当前时间。

`items=[{action,ref,payload}]`。预检返回 `rows/summary/can_confirm/snapshot/projections`，
`row_number` 是1基输入序号，`rows.action` 是真实create/supplement/correct。
失败抛异常并带原行号，不写预览表。确认回调 `(context_ref, 'batch', snapshot)`。
导入确认单独以 `{preview_ref}` 为意图指纹，原bytes解析在外层命令重放检查之后由服务端
`load_items()` 提供；已提交重放不依赖过期内存预检、令牌或原bytes仍在。
同request_key异preview_ref仍拒绝，不能直接lookup绕过输入核验。

旧完工补录是 `create + legacy_fact_ref + 非空reason`，所有字段仍稀疏；
普通create不能使已完成工序降级，需显式correct。仅有旧start、不存在旧finish时，
旧start不是额外逐次报工；无新记录时数量未知，有明确新记录后按新记录累计和完整性判断。

# 3. 验收与边界

- 原计划身份永久保留；新计划仅通过相同 operation_ref 关联，不按批次/工序号猜。
- 分件实例目标为1，批量实例使用权威 Batches.quantity；未知目标为null，0不等于未知。
- 部分记录 end 不完成工序；齐全且累计精确达到目标才推导完整完成。
- 旧原表逐行保留；旧事件额外只追加快照。合法旧finish独立保持complete/legacy_incomplete。
- 旧finish数量为工序累计确认，不把多个版本的同一完成确认相加；来源无法消歧则标invalid并拒绝写。
- 明确 legacy_fact_ref 的补充报工替代同来源数量参与统计，不重复累加；不自动伪造逐次行。
- 更正保留所有版本、原因、前后值、本机操作者、声明人、请求键和回执关联。
- 下游生产与新采用安排冲突时拒绝，不能静默撤销保护；剩余计划不自行重算，返回null和缺项原因。
- SQL按 operation_ref 分块读取，有明确行数/字节上限，超限拒绝而非截断。
- 旧源UPDATE/DELETE只产生 `legacy_source_changed` 可见gap，并使 `legacy_source_hash` 变化。
  对照按归档原id、全部LEGACY_COLUMNS逐列类型保真进行，不从当前旧源重新计算完成状态或数量。
  归档不覆盖，合法旧finish继续complete，source缺失也不会解除保护。日期converter不构成虚假差异。
- 新 `recorded_at` 与修订时点由服务端工厂本地clock显式保存。旧 `created_at` 保留原值，
  标注 `created_at_time_basis=legacy_storage/created_at_default_basis=utc`，不伪装实际本地时间。
  不可展示的BLOB/日期元数据返回null+类型与gap；原表和归档SQLite存储类型均保留。

# 4. 精确 Schema 交付

`execution_ledger_objects()` 返回22个对象；`install_execution_ledger(conn)` 必须在调用方迁移事务中，
不自行commit。原表数据不变；缺失或部分ledger拒绝修补。当前clock初始行是 `(1,1,1)`。
`execution_ledger_contract_issues(conn)` 只读检查，不承担启动注册。

4张新表：

- `WorkbenchExecutionLedgerClock(singleton, revision, next_report_no)`。
- `WorkbenchExecutionLegacyFacts`：legacy_fact_ref主键、operation/task/plan永久引用、
  actual_machine_ref/actual_operator_ref，加29个原事件列。原事件列无affinity，UNIQUE(id)，不丢原存储类型。
- `WorkbenchProductionReports`：report_ref主键、唯一report_no、operation_ref、原录入task/plan、source、
  唯一可空legacy_fact_ref、recorded_at；身份外键指向永久引用表，不因源操作删除级联抹历史。
- `WorkbenchProductionReportRevisions`：随机revision_ref主键、report_ref、sequence、previous_revision_ref、
  action、values_json、reason、local_operator、declared_operator、recorded_at、request_key。
  report_ref+sequence及previous_revision_ref唯一，request_key延迟外键约束到同事务回执。

8个显式索引（主键、UNIQUE另有SQLite自动索引）：

- `idx_wb_execution_reports_operation(operation_ref, recorded_at, report_ref)`，作用于Reports。
- `idx_wb_execution_reports_task(recorded_against_task_ref)`，作用于Reports。
- `idx_wb_execution_legacy_operation(operation_ref, id)`，作用于LegacyFacts。
- `idx_wb_execution_legacy_unbound(op_id)`，仅未绑定operation或task的LegacyFacts。
- `idx_wb_execution_revisions_request(request_key)`，作用于Revisions。
- `idx_wb_execution_task_operation(operation_ref, kind, version)`，作用于WorkbenchPlanSourceRefs。
- `idx_wb_execution_source_row_history(kind, source_key, version, operation_id)`，作用于WorkbenchPlanSourceRefs。
- `idx_wb_execution_resource_history(kind, entity_key)`，作用于WorkbenchEntityRefs。

10个触发器：`wb_execution_{reports,revisions,legacy}_{no_update,no_delete,clock}` 共9个；
`wb_execution_capture_legacy` 仅在原Events INSERT时追加归档，不改原事件。
捕获严格验证schedule/adopted/无scenario、原schedule/version/op、原工序实例与batch归属；
碰号candidate/scenario、错batch、同号重建不能绑定official，无法证明的原行仍完整存档且标明未绑定。

# 5. 证据与边界

现有复用：`OperationExecutionFeedbackService._load_current_official_schedule` 的正式可录入校验，
`WorkbenchPlanIdentityRepository` 的永久工序/任务身份，`WorkbenchCommandService.execute` 的外层事务与回执，
以及原事件模型的严格合法序列校验。均通过symbol_locator和当前源码核对，没有修改这些旧服务。

已测规模合同：5000行同文件纯内存预检、原子确认、同号重导；10000工序分块读投影。
规模测试同时检查SQL条数/SQLite VM步数及主键查询计划，拒绝二次全表联接，不只计返回行数。
新增源码AST按Python3.8语法解析；没有引入运行时依赖。

明确未实施：HTTP/前端/文件编解码由各适配包负责；排产、批次、报表、校准调用方及迁移注册由主线负责。
未找到能区分原全量计划与真实剩余安排的持久标记，因此remaining_plan保留null和相应gap，不按跨度/比例补时长。
现有BatchOperations没有独立piece_quantity字段；分件目标1的前提是piece_id表示单件实例，不将其当多件包再套批次数量。
Win7真机、最终包和整仓clean gate不属于本领域局部证明；本轮保留所有dirty/staged，未提交、未构建、未碰productionDB。

# 6. 本域最终验证

正常项目公共fixture入口：**72 passed in 54.28s**。真实临时磁盘SQLite，未mock数据库；
Python **3.8.10** / SQLite **3.35.5**。精确命令如下，避免通配符带入主线并行新增的迁移测试：

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_execution_ledger.py \
  tests/workbench/test_execution_ledger_commands.py \
  tests/workbench/test_execution_ledger_constraints.py \
  tests/workbench/test_execution_ledger_contracts.py \
  tests/workbench/test_execution_ledger_legacy.py \
  tests/workbench/test_execution_ledger_scale.py \
  tests/workbench/test_execution_ledger_scope.py \
  tests/workbench/test_execution_ledger_source_integrity.py
```

- 覆盖稳定单号/引用、跨版本与同号重建、分件目标、未知/0/过量、稀疏补齐、完整完成和旧finish独立保护。
- 覆盖只有旧start后完整新报告可完成、完整完成不能被新增空记录降级、追加更正/原值/原因/双操作者历史。
- 覆盖下游事实与新采用安排冲突、原始旧表逐行保持、写失败与receipt失败全回滚、原请求/过期导入重放。
- 覆盖旧候选/场景/错batch碰号不绑定official、原源UPDATE/DELETE和类型漂移使快照变化而不撤销归档完成。
- 覆盖query_only、生产连接日期converter、旧BLOB不可展示标记、资源永久身份歧义gap。
- 5000行预检SELECT少于120、VM步数少于500000；10000工序SELECT少于260、VM步数少于15000000；
  主键联接查询计划禁止 `SCAN bo`。这些是已通过的用例上界，不是任意硬件延迟承诺。
- 本域所有产品/专属测试 `ruff check` 通过；产品代码radon最高函数复杂度13，低于项目门限15。
  依旧是dirty-worktree局部证明，不宣称clean-worktree/full gate/Win7真机验证。

最终关键源SHA-256（供主线绑定，不代替整仓/最终包hash）：

```text
production_report_prepare.py 16b97acbc52684577051a3376196cf4ec22a9247da6748c0be4d320d2c036d14
production_report_validation.py ca55a94b9e1cde334dd6c9496b2d03cf30de3226e7d9d11bfdcebaec369a6d87
execution_ledger.py ce28728001fcea61bbeb1f57c8c438d607918ea574346dacd48c428125a180f0
execution_ledger_totals.py 229b8529dbead8d91968698feae15801dae5ec26b49d383de0a4a30125538496
workbench_execution_source_repo.py 3c9e4712941d94fb1785ea5185e7a0311e8210719281d4c286bbfdc844126663
workbench_execution_ledger_schema.py f2fc3eac1e6d85ea70b7f9e6a3fab69ce2552bf72d4260514f67bc6d003720a2
```

本任务不包含十列 Excel 文件编解码或HTTP/Gantt适配；Excel来源的单号幂等/补齐规则属于本领域。
Win7真机和整仓门禁另由主线执行，本轮使用真实临时SQLite覆盖下面清单。

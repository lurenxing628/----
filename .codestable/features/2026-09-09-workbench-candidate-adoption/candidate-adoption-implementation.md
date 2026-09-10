---
doc_type: feature-implementation
feature: workbench-candidate-adoption
status: integration-pending
summary: BX 独占新增模块实现候选正式采用最小后端路径，默认关闭，等待主线联合接入。
tags: [workbench, candidate, adoption, transaction]
---

# BX 候选正式采用后端

## 授权与范围

- 依据本轮明确实施授权和 roadmap `workbench-contracts.md` 第 7 节；永久候选不装成旧 `plan_ref`。
- 仅新增 `run_candidate_adoption*.py` 服务、`workbench_run_adoption.py` 模型、独立路由、专属测试和本目录文档。
- 没有修改 BL DTO/GET、BP UI、AV 作业、AS 计算、旧 scheduler、schema、迁移注册、main、build、registry；没有 stage/commit。
- 所有运行测试只使用 pytest 临时 SQLite 文件，不打开生产库，不启动或占用旧用户端口。

## 现有代码证据

- 已运行 symbol_locator：`persist_schedule_core_in_tx` 的 whereis/callers/callees，`allocate_next_version` 的 whereis，`validate_execution_guard_before_persist` 的 callers。
- `core/services/scheduler/run/schedule_persistence.py`：事务内核心还会改 BatchOperations/Batches 状态；不适合本次只追加正式版本的组合合同。
- `core/services/scheduler/gantt_adjustment_publish_service.py`：旧 scenario 发布自己拥有 `BEGIN IMMEDIATE`，不能套进新命令事务；未调用或改变它。
- `data/repositories/schedule_history_repo.py::allocate_next_version`：数据库 AUTOINCREMENT 序列并对齐历史最大版本。BX 先只读确认分配表存在，禁止把 helper 的 CREATE IF NOT EXISTS 用作修复。
- `core/services/scheduler/schedule_service.py::_RUN_SCHEDULE_LOCK`：旧 run 与 AV worker 的共同运行锁。BX 同样取得它；繁忙即拒绝，不等长计算。另一个 BX 短请求锁用于串行处理同时采用的幂等意图。
- `core/services/scheduler/run/schedule_execution_resource_facts.py::_latest_plan_rows`：每道工序最后一次正式安排不一定在最大版本里；BX 要求候选覆盖该完整集合，并通过永久身份仓库校验每组旧 task/operation 实例关系。
- `core/services/scheduler/run/schedule_execution_persistence_guard.py`：复用执行 revision、完整资源执行快照、已开始和已完工保护，不用 BatchOperations.status 猜实际生产。
- `core/infrastructure/workbench_plan_identity_schema.py`：现有触发器在追加 Schedule/History 时生成新的 official/task 永久身份；不需要新增 schema。
- `core/services/workbench/commands.py`：BEGIN IMMEDIATE 下先检查原 receipt，再执行 guard/mutate/receipt，一次 COMMIT；COMMIT ACK 不确定时必须查原请求。

## 实施路径

1. `preview(candidate_ref)` 在 query_only 快照下读取真实受理回执、运行终态、候选原始结果、验证 payload、全部明细和完整受理事实。
2. 精确比较受理时 baseline、facts_hash 与当前值；facts 使用 AV 原口径，保留 BLOB 的字节编码及所有表/字段，不挑选少数字段制造“未漂移”。新执行投影必须与受理投影相同，并由现有执行领域确认基线确实是当前可执行正式计划；不能把最大版本的模拟记录或损坏摘要当作正式基线。
3. 复用 AS 输入准备与链闭合验证；重新校验实际派工的工种、在岗、人员资质、设备授权、供应商、物料条件、资源互斥、冻结/执行种子、日历效率/跨班次时长/停机和外协周期。
4. 预览成功才签发绑定候选、完整事实与合法 payload 摘要的短期 WriteContext。预览不分配版本、不写任何数据库行。
5. confirm 取得运行锁后进入命令的同一 BEGIN IMMEDIATE；再次执行 1-3 并校验 WriteContext，之后才分配数据库版本。
6. 新同前缀 adapter 组合现有 ScheduleRepository、ScheduleHistoryRepository、WorkbenchPlanIdentityRepository、OperationLogger。仅追加完整 Schedule/History、已有身份触发器生成的 refs、OperationLogs 和 CommandReceipts，不改主数据状态或原资源配置，不复制/修改执行记录。
7. 审计保存 source candidate/run、baseline、版本、完整事实/候选/验证摘要、原因、声明人、本机服务读取的应用操作者；声明人不伪装认证身份。History 和 OperationLogs 中的采用追溯与命令 receipt 同事务。维护来源归档仍由现有维护域负责。
8. 同键同规范化输入返回原 receipt；同键异输入冲突。同候选换新键不能再次采用，因为受理 baseline/facts 已旧。存储异常沿用公共命令服务的 unknown 合同，先查询原 key，不自动重跑。

## 主线挂点

无需新增 schema，也无需修改旧共享 helper。待主线联合验证后自行接入：

- 在工作台 blueprint 装配调用 `web.routes.workbench.run_candidate_adoption.register_run_candidate_adoption_routes(bp)`。
- 显式设置 `WORKBENCH_CANDIDATE_ADOPTION_ENABLED=True` 才启用新预览能力；默认 False。现有候选 GET `capabilities.adopt` 本轮仍为 False。
- 复用主线已注册的 `GET /api/workbench/v1/commands/<request_key>` 查询原 receipt。独立模块不再重复注册通用查询。
- 主线负责测试 registry、冻结打包和最终运行/UI 接入；BX 没有代改这些独占域。
- 沿用现有应用请求维护门禁；本模块不建立另一套维护 journal/审计来源，也不能脱离主线维护保护直接对生产库启用。

POST `/api/workbench/v1/scheduling/candidates/<candidate_ref>/adopt-preview`：空 JSON 对象 `{}`；成功返回 query envelope，data 含 `validation`、`write_context`、完整 task_count 和明确 baseline（空基线为 null/null）。

POST `/api/workbench/v1/scheduling/candidates/<candidate_ref>/adopt`：

```json
{"request_key":"candidate-adoption-000001","write_token":"preview token","input":{"confirm":true,"reason":"采用原因","declared_operator":"声明操作人"}}
```

返回普通 CommandResult，`data.official_plan` 是真实新 official PlanIdentity，`data.candidate_ref` 仍为原候选；不把 candidate_ref 注册到旧计划映射。receipt 中的身份描述是提交时结果，重放后页面应刷新当前计划，不据旧 receipt 推断它仍是最新版本。

## 明确阻断边界

- partial/未排完/损坏/未知合法性保持 blocked，completed 仅是引擎状态，不是采用证明。
- 候选必须完整覆盖选中工序，且覆盖所有工序的最后正式安排；不偷偷合并未选中的旧 pending 安排。子范围候选需要重新选全相关批次并生成。
- 所有分件候选暂不采用，包括单件分支；现有 AS 多件量/前后序适配不足时不伪造证明。
- `Schedule` 旧写入口仅保留秒精度，因此候选含微秒时阻断，不四舍五入改变已验证安排。
- 实际生产必须保持其真实区间；不以标准工时反算旧实际。当前上游预检将尚未可信完工的生产标记以 `execution_review_required` 阻断，本模块不绕过它生成候选。
- 当前 facts_hash 沿用全表事实快照，非关键日志变化也可能导致 409。这是保守拒绝，不是遗漏事实；本轮不扩大到改 AV 快照定义。
- 资源或日历合法性不能证明的冻结旧安排也阻断。缺少 schema/身份时不自修复、不开放能力。

## 验证记录

执行结果、规模耗时及尚未完成的联合验证见 `candidate-adoption-acceptance.md`。这是 dirty worktree 上的局部验证，不是 clean-worktree proof。

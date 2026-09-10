---
doc_type: feature-implementation
feature: workbench-run-jobs
status: implemented-integration-pending
summary: AV独立实现真实候选排产的持久受理、结果台账和重启核对，宿主接线前默认关闭
tags: [workbench, scheduling, persistence, recovery]
---

# AV 持久受理与运行台账

## 授权与范围

沿用已批准的 `workbench-contracts.md` 第3/7节和
`2026-09-09-workbench-preflight/workbench-preflight-design.md` 的 accept/prepare/worker/get/recover 合同。
本轮用户明确授权 AV 亲自实施独立写集。未创建代理或任务，未读生产库，未 build/commit/升级依赖。
所有业务与容量测试均使用临时真实 SQLite；产品运行环境实测为 Python 3.8。

不改 AS 的 `run_compute*`、`run_input*`、`workbench_run_compute.py`，不改 preflight/plan/scheduler/shared。
不改 `schema.sql`、migration version/registry、global `__init__`、browser/main 或打包入口。
v26 注册、宿主派发器和新候选 catalog 由主线后续处理，本块不能被描述为页面已经上线。

## 可集成接口

- `core/infrastructure/workbench_run_schema.py`:
  `install_workbench_run_schema(conn)` 必须由调用方持有外层迁移事务；不 BEGIN/COMMIT、不自动修复。
  `workbench_run_objects()` 返回精确 DDL；`workbench_run_contract_issues(conn)` 只执行 SELECT。
  残缺结构拒绝；整套表丢失但 `scheduling.run` 受理回执还在时拒绝重建引用。
- `core/services/workbench/run_jobs.py`:
  `WorkbenchRunService(conn, integration_enabled=False, input_resolver=None,
  context_factory=None, context_validator=None, clock=None)`。
  方法 `preview(input_ref)`、`accept(input_ref,write_token,request_key)`、
  `get(run_ref)`、`lookup(request_key)`、`recover_unfinished_runs(executor_is_active=None)`。
- `core/services/workbench/run_worker.py`:
  `WorkbenchRunWorker(conn, clock=None).execute(run_ref)`。
  调用线程自己打开/关闭连接；不要跨线程复用请求中的 `g.db`。
  计算失败先持久记录失败结果，再原样抛出原异常；结果提交不确定抛 `WorkbenchCommandUncertain`。
- `web/routes/workbench/scheduling_jobs.py`:
  `register_scheduling_job_routes(bp)` 注册下列独立 JSON 路由，未改全局注册：
  `POST /api/workbench/v1/scheduling/runs/preview`，输入 `{input_ref}`；
  `POST /api/workbench/v1/scheduling/runs`，输入 `{input_ref,write_token,request_key}`；
  `GET /api/workbench/v1/scheduling/runs/<run_ref>`；
  `GET /api/workbench/v1/scheduling/requests/<request_key>`。

HTTP 启用同时要求 `WORKBENCH_RUN_JOBS_ENABLED is True` 和
`app.extensions['workbench_run_dispatcher']` 是宿主连接的 callable。
查询沿用标准 `meta.as_of/snapshot_ref` 读取上下文；这个短期读取快照不是运行或候选的永久身份。
普通 preflight 仍保持原来的 `write_token=null/run=false`，不把它当作执行授权。
宿主接好后，新的 preview 重验旧 `input_ref`/完整事实/唯一执行台账/阻断项，才签发 `scheduling.run` 写上下文。
受理事务再次全部验证；同键同 `input_ref` 重放既有 receipt，允许原 token 已失效；异载荷409。
跨命令 request_key 由现有 `WorkbenchCommandReceipts` 的唯一键和动作/上下文核对保护。

## 精确持久对象

| 表 | 身份与内容 |
| --- | --- |
| `WorkbenchRunJobs` | 永久48位随机 `run_ref`；唯一request_key；规范输入、原始全事实、AJ投影、正式基线；受理字段不可改；状态与执行者记录 |
| `WorkbenchRunReceipts` | 永久结果receipt_ref；每run唯一；终态、完整结果manifest、内部失败诊断；仅追加 |
| `WorkbenchRunCandidates` | 永久candidate_ref；每run真实candidate_key/sequence唯一；候选完整dataclass artifacts，包括results和ValidatedSchedulePayload |
| `WorkbenchRunCandidateTasks` | 永久row_ref；candidate_ref+operation_ref唯一；每条经验证排程、资源、时间、source、locked；仅追加 |

额外对象：`idx_wb_run_state`；四表共7个禁止删除/更新触发器；
`wb_run_admission_immutable`、`wb_run_state_transition`。精确文本以 `workbench_run_objects()` 为准，共14对象。
受理receipt复用现有 `WorkbenchCommandReceipts(action='scheduling.run')`，与新Jobs行同事务提交。
新表 FK 指向现有永久 `WorkbenchPlanSourceRefs`，不直接将裸工序号作为公开身份。
新候选不是已登记 PlanIdentity，公开结果固定 `plans=[]/plan_catalog_connected=false`。
`candidate_ref/row_ref` 不冒充 `plan_ref/task_ref`；未来catalog必须明确接入这些已有永久行。

## 事务与状态机

1. 受理：`BEGIN IMMEDIATE` 下重验预检、授权、AJ精确范围，保存输入/快照/基线/run及受理receipt，COMMIT后才派发。
2. 领取：同一个 `schedule_service._RUN_SCHEDULE_LOCK` 下短事务 CAS `queued -> running/computing`。
3. 计算：领取已提交后，用SQLite Backup API取得一致的独立内存库，立即释放原库读锁。在内存库的 AS `candidate_read_snapshot` 内恢复原AJ DTO、重验业务指纹，执行真实 prepare/compute；原库不持读/写事务、不写阶段、不分配正式版本。
4. 结果：短 `BEGIN IMMEDIATE` 再验事实与执行者，保存所有真实候选和完整明细、结果receipt和终态，一次提交。
5. 重启：先核对receipt/明细，再核对活动执行者。已提交结果不重跑；确无结果且确无活动执行者才interrupted；未知保持running/awaiting_reconciliation。

状态：`queued -> running -> complete|partial|failed|interrupted`；未领取queued经明确恢复核对可interrupted。
阶段仅有 `queued/computing/finished/awaiting_reconciliation`，progress始终null。
worker对非queued运行只读既有状态，不因重复调用、GET轮询次数、浏览器超时或旧时间戳重新计算。
不同request_key使用同一旧preflight时，前次受理使原fullfacts改变，后续明确409，不擅自刷新旧预检。

受理后业务指纹包含完整schema和所有原表，唯一排除本块四张台账及动作恰为`scheduling.run`的受理receipt。
这是为避免自己的queued/running/结果写入使已受理输入自失效；没有排除配置、日历、正式计划、旧候选、资源或执行事实。
原始事实以完整行和SQLite blob类型标记保存，不能从摘要重建输入；不依赖内存token解析结果。

## 宿主后续接线

- 主线在正式迁移中调用installer，自己负责v26/registry/schema快进合同。
- 同一个本机worker dispatcher需在请求外用独立连接执行 `execute(run_ref)`，捕获并记录明确异常；不能同步阻塞HTTP受理请求。
- dispatcher抛错时HTTP仍是已持久受理202，带 `dispatch_pending=true`；原key重放不再次派发。宿主核对原运行，不重新受理。
- 新进程无法仅凭随机executor_ref知道旧执行者已退出，默认None待核对。宿主 `executor_is_active(ref)` 必须以进程退出证据或既有单实例DB运行锁为依据，返回True/False/None，不能按时间推断False。
- 取得现有单实例运行锁并完成启动核对后再开放普通请求；恢复函数和旧排产同锁，不新增平行排产锁。
- 源码未改SQLite journal_mode。`run_worker_snapshot.computation_database` 使用一致内存库，使长计算不占原库读锁或写锁；补测WAL/DELETE两种模式的另一连接提交，以及真实BackupManager维护备份和运行状态查询。

## 验证边界

本轮普通回归数量和最终静态检查结果见acceptance；覆盖真实候选、受理幂等与过期授权、原正式计划/历史/旧候选保留、严格installer、12并发受理、双worker与旧锁、查询running、计算中另一连接写入与维护备份、结果第二写失败全原子、进程退出、COMMIT确认丢失、未知执行者及HTTP接线。
容量独立用例为100批次乘50工序、100组独立设备人员，真实4候选共20000持久明细。首跑1 passed in145.30s，最终源码回归结果另见acceptance。
不得将此场景替代AS单设备/人员争用5000工序未通过的容量结果；未重复该长跑。
此工作区原有大量并行暂存/未暂存/未跟踪内容；没有完整质量门禁、clean-worktree proof、Win7真机或页面集成完成声明。

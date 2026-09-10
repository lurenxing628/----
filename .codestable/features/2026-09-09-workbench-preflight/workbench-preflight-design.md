---
doc_type: feature-design
feature: workbench-preflight
status: approved
summary: 执行排产页真实只读预检及完整单次规则和精确批次范围控件
tags: [workbench, scheduling, preflight]
---

# 执行排产页预检块

## 范围与授权

总体路线图与 contracts 第7节已获批准，本轮用户明确授权 AM 独占实施预检模型、preflight 服务/路由、五个前端文件及专属测试。入口、全局注册与构建由主代理处理；AJ 独占执行台账。本文不是另起研究流程。

不改 scheduler 算法、正式 run 持久化、ScheduleConfig、schema、plan/batch/ledger、共享传输、main/build/global __init__。不创建 Codex 任务或子代理；不读生产DB、不 build、不 commit。

## 接口与事实

- `register_preflight_routes(bp)` 注册 `POST /api/workbench/v1/scheduling/preflight`。
- 输入严格为 `batch_refs,start_date,end_date,ready_check,missing_resource_policy,completed_policy`；合同草案的业务 `batch_ids` 收紧为用户指定的永久 `batch_refs`，不接受别名猜测。最多5000个，不重复；空数组明确无可排结果，不自动变全库。
- `PreflightService(conn).evaluate(input)` 返回 `(data, full_facts_fingerprint)`；只读事务直接从原始行读取，禁止 `BatchOperation.from_row` 的 null 补0行为。
- 已安装时唯一消费 AJ `ExecutionLedgerService.project_operations()`。未安装或结构不完整时只保留旧保护，并给出 `execution_ledger_unavailable`，不能受理 run；AJ 查询失败不回退假空投影。
- 工序状态互斥：eligible / auto_assign_required / skipped / blocked / protected。`eligible_tasks=ready_tasks+auto_assign_required`，不宣称后者已匹配资源；未生成工艺按批计数。字段缺项优先于资源排除，前序排除向同批同分件后序传递解释。
- `actual_fact_tasks` 只统计真正有报工/旧事件的工序，`protected_tasks` 另含待核实的原执行标记；没有事件的completed标记受保护，但不冒充已发生事实。
- 部分报工的结束不视为整道完成；未知剩余量不补0、不解锁。合法旧 finish 可为 complete/legacy_incomplete，仍保护。invalid 保持阻断。
- 日期窗口为工厂本地墙钟 `[开始日00:00,结束日次日00:00)`；`effective_start` 只是窗口下界，不是实际首个日历槽位。`calendar_check=not_evaluated`，不绿标全通过。
- `input_ref` 是900秒进程内短期上下文，绑定完整规范输入、精确scope、所有SQLite表及schema内容指纹。重启、过期、任一事实漂移后拒绝。
- `resolve_preflight_input(conn,input_ref)` 必须在后续调用方的受理事务内重验；不是运行授权。`write_token=null`，`capabilities.scheduling.run=false`，`run_worker_not_connected` 明确给出。

## 前端挂载

`window.PreflightWorkspace({onNavigate,initialContext})`，加载次序：PreflightContract.js、PreflightAPI.js、PreflightControls.jsx、PreflightBatchPicker.jsx、PreflightWorkspace.jsx。

复用现有 APSResourceAPI 的只读 preview、APSBatchAPI 及真实分页/selection快照，日期/数字/下拉由主壳 WorkbenchControls/WorkbenchNumberControls 统一接管。自身根有 `.plana`，padding=0/max-width=none，不依赖样板祖先。规则与检查行同高grid，样板的计划窗口、规则、检查、范围选择与排产按钮完整保留。

默认不选择批次；全部待排/仅齐套/筛选全选均由服务端返回精确refs。跨页选择不丢失，5000项不在DOM逐项铺开，错误保留原选择。所有参数变化作废旧结果并中止旧请求；失效context明确报错并提供显式重新选范围。

范围默认折叠以保持原样板首屏规则布局；批次列表按20/50/100分页，工序结果和未生成工艺项按100项分页。无缺项时跳转补资料按钮禁用，不导航到无关全量范围。

## 下一阶段的确切方法

以下是待实现的方法合同，不是当前能力：

1. `WorkbenchRunService.accept(input_ref,write_token,request_key)`：同一短写事务重新核验本块 `resolve_preflight_input`、唯一执行投影、范围和cap，持久保存规范输入、完整事实/执行快照、基线、run_ref与受理receipt；成功后才能交worker。不能凭本块现有null write_token受理。
2. `prepare_candidate_run_input(conn,normalized_input,execution_projections)`：将本次覆盖值应用于内存配置副本，筛除精确工序范围并保留执行保护，生成经过验证的 ScheduleRunInput。必须适配新ledger，不能无条件调用旧collector或旧from_row。日历/设备人员可行性在此或实际计算中验证。
3. `WorkbenchRunWorker.execute(run_ref)`：沿用同一个排产运行锁，计算期间不持写事务；实际阶段才更新stage，进度未知保持null。候选完整行及结果receipt/run终态在结果事务一同保存，不自动发布正式计划。
4. `WorkbenchRunService.get(run_ref)` 与 `recover_unfinished_runs()`：重启先核对结果事务；已提交候选恢复终态，确无结果且无活动执行者才interrupted。不要把轮询超时变成重跑。

当前可复用源码证据：

- `core/services/scheduler/schedule_service.py:32,198`：`_RUN_SCHEDULE_LOCK` 与 `run_schedule` 的现有锁生命周期；锁需在后续共享执行入口中沿用。本块未取锁运行。
- `core/services/scheduler/run/schedule_input_collector.py:266`：`collect_schedule_run_input` / ScheduleRunInput。当前读取旧执行链与全局配置，且齐套/缺资源排除语义不同，不能直接当新预检输入适配器。
- `core/services/scheduler/run/schedule_orchestrator.py:280`：`orchestrate_schedule_run` 已有 `allocate_version=False,persist_schedule_fn=None,version_override=...` 的无正式发布编排参数；输出含真实候选比较，但整个新worker链仍需另做读写审计和生命周期实现。
- `core/services/scheduler/run/schedule_optimizer.py:214`：`optimize_schedule` 可复用现有优化计算，不另造算法或三方案名称。
- `core/services/scheduler/run/schedule_candidate_persistence.py:230`：`persist_candidate_comparison` 已有真实候选与明细写入，但当前依赖正式version/adopted；不是独立run候选集生命周期。
- `core/services/scheduler/run/schedule_candidate_persistence_helpers.py:29`：`persist_schedule_run_with_candidates` 会先调用正式 `persist_schedule_core_in_tx` 并清理无history候选，禁止直接作为新候选worker结果提交。
- `core/services/scheduler/schedule_service.py:289,321`：旧默认run调用正式持久化，不能从新页面偷调；即使simulate分支不正式落库，也不提供新受理和候选持久生命周期。

## 验收范围

专属API测试覆盖null/0、非法日期/数值/refs、未齐套/未生成工艺、外协必填、资源缺口与后序断链、旧finish、开工、跨夜、完整scope/fullfacts指纹过期和只读异常。AJ实际安装联调用分次报工、未知/0/部分/完工/分件测试。临时真实Flask+SQLite与Chrome109校验1920/1392浅深色、无mock `.plana` 祖先、grid对齐、统一日期下拉、空/错误/巨大refs/失效context/跨页选择。

每个真实预检前后逐表相同、total_changes不变；本轮只能提供dirty工作区定点证据，不能宣称clean-worktree proof、全门禁、Win7真机或后续run功能完成。

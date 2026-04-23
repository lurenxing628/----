# 未提交修改三轮深度审查
- 日期: 2026-04-02
- 概述: 针对当前工作区未提交修改开展三轮递进式深度review，重点核查变更范围、引用链影响及问题修复闭环。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# 未提交修改三轮深度审查

- 日期：2026-04-02
- 审查目标：对当前工作区未提交修改进行三轮递进式深度审查，确认变更是否真正解决目标问题，并检查引用链、函数变量影响与潜在回归风险。
- 审查方式：Round 1 识别变更与外层影响面；Round 2 深入核心实现与调用链；Round 3 对照测试/契约/风险进行闭环判断。
- 当前状态：进行中

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/infrastructure, web/routes/system_backup.py, core/services/system/system_maintenance_service.py, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_persistence.py, core/services/scheduler/freeze_window.py, app.py, app_new_ui.py, web/bootstrap/factory.py, web/bootstrap/launcher.py, installer/aps_win7.iss, installer/aps_win7_legacy.iss, installer/aps_win7_chrome.iss, assets/启动_排产系统_Chrome.bat
- 当前进度: 已记录 3 个里程碑；最新：round3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 1
- 问题严重级别分布: 高 0 / 中 1 / 低 0
- 最新结论: Three-round review completed. Judgment: the infrastructure maintenance/backup/transaction fixes in Round 1 are effectively solved; the runtime ownership/shared-state/installer-stop chain in Round 3 is also effectively solved; however, the scheduler terminal/reschedulable fix in Round 2 is only partially solved. The main contract has been tightened across algorithm input, freeze seed, persistence scope, and batch-status denominator, but `ScheduleService._run_schedule()` still lacks a short-circuit when `reschedulable_operations` becomes empty, so the system can still generate a no-op schedule version with history artifacts. Because of that residual behavior, the underlying issue is not fully closed yet and follow-up is still required. Review scope note: due tool limitations in this run, the exact live uncommitted diff could not be independently enumerated via `git diff`; the review is therefore based on branch history, traced high-risk files, and regression evidence from the current workspace.
- 下一步建议: Add an explicit empty-`reschedulable_operations` guard in `ScheduleService._run_schedule()`, prevent version/history creation for that no-op path, add a regression covering 'batch status allowed but all operations terminal', then rerun a focused scheduler review.
- 总体结论: 需要后续跟进

## 评审发现

### 空排产版本仍可生成

- ID: sched-empty-reschedulable-noop
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: round2
- 说明:

  `ScheduleService._run_schedule()` 在按 terminal 状态过滤出 `reschedulable_operations` 后，没有对空集合做 fail-fast 或 no-op 返回，而是继续分配版本号并调用 `persist_schedule()` 写入排产历史。对于批次状态仍为 pending/scheduled、但其工序已经全部 completed/skipped 等 terminal 的场景，用户会得到一个表面成功但没有任何实际排产动作的新版本；这会污染版本序列与历史审计结果，也让“本次排产是否真的生效”变得难以判断。当前回归已覆盖 terminal 工序过滤和分母修正，但没有覆盖这一入口短路缺口。
- 建议:

  在 `run_schedule()` 计算出 `reschedulable_operations` 后，针对空集合显式返回业务错误或 no-op 结果，并阻止版本号分配与 `ScheduleHistory` 留痕；同时补一条回归测试覆盖“批次状态允许，但工序全为 terminal”场景。
- 证据:
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `core/services/scheduler/freeze_window.py`
  - `tests/regression_schedule_service_reschedulable_contract.py`
  - `tests/regression_schedule_persistence_reschedulable_contract.py`
  - `tests/regression_schedule_service_missing_resource_source_case_insensitive.py`

## 评审里程碑

### round1 · Round 1：基础设施维护窗口、备份恢复与事务嵌套链路审查

- 状态: 已完成
- 记录时间: 2026-04-02T15:22:05.221Z
- 已审模块: core/infrastructure, web/routes/system_backup.py, core/services/system/system_maintenance_service.py
- 摘要:

  本轮聚焦基础设施层修复闭环，沿着 `web/routes/system_backup.py::backup_restore` → `core.infrastructure.backup.BackupManager.restore` → `core.infrastructure.database.ensure_schema/_migrate_with_backup` → `core.infrastructure.transaction.TransactionManager.transaction` 的链路做了逐段核查。

  结论：这一组修复基本收口了此前最危险的三类问题：
  1. 维护窗口并发进入：`maintenance_window()` 通过线程内重入 + 跨线程/跨进程锁文件双层机制，能够阻止并发备份/恢复/迁移，同时允许同线程同库的 restore→before_restore backup→migrate 嵌套链继续执行。
  2. 恢复后迁移一致性：`backup_restore()` 显式在同一维护窗口内执行 `mgr.restore()` 与 `ensure_schema()`，避免“恢复完成但迁移尚未完成”期间被其它请求插入。
  3. 嵌套事务一致性：`TransactionManager.transaction()` 把最外层事务切回 `BEGIN/COMMIT`，内层改为 `SAVEPOINT`，并对 `RELEASE SAVEPOINT` / `ROLLBACK TO SAVEPOINT` / `commit()` 失败做了回滚补偿，语义与回归测试一致。

  本轮未发现新的阻断级问题；从实现与回归脚本对照看，这一组修改对原目标问题的修复是有效的。
- 结论:

  基础设施维护窗口、恢复迁移与嵌套事务三条主链路闭环良好，当前未见阻断性残留缺陷。
- 证据:
  - `core/infrastructure/backup.py`
  - `core/infrastructure/database.py`
  - `core/infrastructure/transaction.py`
  - `web/routes/system_backup.py`
  - `tests/regression_maintenance_window_mutex.py`
  - `tests/regression_exit_backup_maintenance.py`
  - `tests/regression_transaction_savepoint_nested.py`
- 下一步建议:

  继续进入 Round 2，深入排查排产服务对 terminal/reschedulable 工序集合的收口是否真正覆盖 schedule/freeze/persist 全链路。

### round2 · Round 2：排产服务 terminal/reschedulable 收口链路深挖

- 状态: 已完成
- 记录时间: 2026-04-02T15:23:11.155Z
- 已审模块: core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_persistence.py, core/services/scheduler/freeze_window.py
- 摘要:

  本轮沿 `ScheduleService._run_schedule()` → `build_freeze_window_seed()` → `persist_schedule()` 做了引用链核查，重点验证 terminal 工序（completed/skipped 等）是否已经从算法输入、冻结窗口、Schedule 落库、状态回写、批次状态分母中彻底剔除。

  确认已修复的部分：
  1. `run_schedule()` 先计算 `reschedulable_operations`，再用该集合构建算法输入与缺资源集合；terminal 工序不会再进入算法主链。
  2. `build_freeze_window_seed()` 已优先消费调用方传入的 `reschedulable_operations`，冻结窗口 seed 与主排产集合保持同口径。
  3. `persist_schedule()` 通过 `allowed_op_ids=reschedulable_op_ids` 只写入可重排工序；状态回写与批次状态统计也只基于可重排集合，不再把 completed/skipped 工序错误计入分母。
  4. 回归脚本同时覆盖了 mixed-case `source=INTERNAL` 缺资源识别与 mixed-status 批次的状态保持。

  但本轮发现一个残余逻辑缺口：当批次本身未被 fail-fast 拒绝、但其工序集合在过滤后 `reschedulable_operations` 为空时，`run_schedule()` 没有提前短路，而是继续分配版本号、构造摘要并调用 `persist_schedule()` 写历史留痕。这样会产生“看似成功、实则无任何排程动作”的空排产版本，说明 terminal/reschedulable 契约虽然已在落库和状态回写层收口，但在服务入口的 no-op 防御仍未完全闭环。
- 结论:

  terminal/reschedulable 主修复已经覆盖算法、冻结和持久化主链，但服务入口仍缺少“0 可重排工序”短路，问题未算完全收口。
- 证据:
  - `core/services/scheduler/schedule_service.py`
  - `core/services/scheduler/schedule_persistence.py`
  - `core/services/scheduler/freeze_window.py`
  - `tests/regression_schedule_service_reschedulable_contract.py`
  - `tests/regression_schedule_persistence_reschedulable_contract.py`
  - `tests/regression_schedule_service_missing_resource_source_case_insensitive.py`
- 下一步建议:

  进入 Round 3，继续审查运行时锁/共享状态/启动器与安装器协同链路，确认单活保护和停机契约是否已与测试闭环。
- 问题:
  - [中] 其他: 空排产版本仍可生成

### round3 · Round 3：运行时单活、共享状态目录与安装器停机契约闭环审查

- 状态: 已完成
- 记录时间: 2026-04-02T15:30:13.008Z
- 已审模块: app.py, app_new_ui.py, web/bootstrap/factory.py, web/bootstrap/launcher.py, installer/aps_win7.iss, installer/aps_win7_legacy.iss, installer/aps_win7_chrome.iss, assets/启动_排产系统_Chrome.bat
- 摘要:

  本轮沿 `app.py` / `app_new_ui.py` → `web.bootstrap.factory` → `web.bootstrap.launcher` → `installer/*.iss` 做了运行时 ownership 与停机契约的闭环核查，并补看了 `assets/启动_排产系统_Chrome.bat` 的客户端接入路径。

  确认闭环成立的关键点：
  1. **父/子进程 ownership 划分清晰**：`should_use_runtime_reloader()` 只在 debug 且非 frozen 时启用 reloader；`_should_register_exit_backup()` / `should_own_runtime_resources()` 进一步要求 `WERKZEUG_RUN_MAIN=true` 的子进程才持有运行时资源。因此 debug 父进程不会抢占运行时锁、不会提前写 host/port/contract，也不会注册清理回调。
  2. **单活锁与运行时契约指向同一状态目录**：两套入口都先用 `current_runtime_owner()` 生成 owner，再以 `acquire_runtime_lock(runtime_dir, prelaunch_log_dir, owner, exe_path)` 把锁写到共享 `LOG_DIR`；随后 `_configure_runtime_contract()` 写入 `APS_RUNTIME_SHUTDOWN_TOKEN`、`APS_RUNTIME_DIR`、`APS_RUNTIME_OWNER`，并把 host/port/db/runtime.json 主写到共享日志目录。
  3. **兼容旧工具链的镜像仍被保留**：`write_runtime_host_port_files()` 与 `write_runtime_contract_file()` 在共享 `LOG_DIR` 之外，还会向 `runtime_dir/logs` 写镜像；`delete_runtime_contract_files()` 通过 contract 中的 `runtime_dir` 与 `data_dirs.log_dir` 反向清理主目录和镜像目录，避免残留导致后续误判。
  4. **停机 helper 能接受 runtime root 或 state dir**：`stop_runtime_from_dir()` 先用 `_resolve_runtime_stop_context()` 归一化输入。若传入 `.../logs`，会把它视为 state dir；若传入 runtime root，则优先读 `runtime_dir/logs` 镜像。contract 缺失但 host/port 仍健康时，它会返回 busy 而不误删信号文件；不健康时才清理 contract 并按需关闭 APS Chrome。
  5. **安装器与 helper 的契约已经对齐**：`installer/aps_win7.iss` 与 `installer/aps_win7_legacy.iss` 先从 `SharedLogDirPath` / `LegacyLogDirPath` 里的 `aps_runtime.lock` 或 `aps_runtime.json` 解析 `exe_path`，再对 `SharedDataRootPath`、`LegacyDataRootPath`、`RegisteredMainAppDirPath`、当前 `{app}` 逐个执行 `--runtime-stop <runtime_dir>`。这与 launcher 的“runtime root + runtime_dir/logs 镜像”语义一致，而不是旧的“直接传 logs 目录”模式。`aps_win7_chrome.iss` 也确认仍是浏览器运行时安装器，不参与主程序 precleanup。
  6. **前端启动脚本也已切到共享状态口径**：`启动_排产系统_Chrome.bat` 会先解析 `APS_SHARED_DATA_ROOT` / 注册表 / `%ProgramData%\APS\shared-data`，再从共享 `LOG_DIR` 读取 lock、host、port、launch_error，并用 owner 比对决定复用、阻塞还是启动新实例。

  结合回归脚本看，Round 3 覆盖了 reloader 父/子进程 ownership、共享日志目录主写 + runtime_dir/logs 镜像、contract 清理、`stop_runtime_from_dir()` 的 state-dir 兼容，以及安装器 precleanup / uninstall 的调用约束。当前未见新的断链或残留竞态。
- 结论:

  运行时单活、共享状态目录、helper 停机与安装器联动链路基本闭环，当前未见新的阻断性缺陷。
- 证据:
  - `app.py`
  - `app_new_ui.py`
  - `web/bootstrap/factory.py`
  - `web/bootstrap/launcher.py`
  - `assets/启动_排产系统_Chrome.bat`
  - `installer/aps_win7.iss`
  - `installer/aps_win7_legacy.iss`
  - `installer/aps_win7_chrome.iss`
  - `tests/regression_runtime_lock_reloader_parent_skip.py`
  - `tests/regression_shared_runtime_state.py`
  - `tests/regression_runtime_contract_launcher.py`
  - `tests/test_win7_launcher_runtime_paths.py`
- 下一步建议:

  汇总结论并结束本次三轮审查；最终结论需要明确指出 Round 2 仍存在“0 可重排工序”空排产版本残余问题。

## 最终结论

Three-round review completed. Judgment: the infrastructure maintenance/backup/transaction fixes in Round 1 are effectively solved; the runtime ownership/shared-state/installer-stop chain in Round 3 is also effectively solved; however, the scheduler terminal/reschedulable fix in Round 2 is only partially solved. The main contract has been tightened across algorithm input, freeze seed, persistence scope, and batch-status denominator, but `ScheduleService._run_schedule()` still lacks a short-circuit when `reschedulable_operations` becomes empty, so the system can still generate a no-op schedule version with history artifacts. Because of that residual behavior, the underlying issue is not fully closed yet and follow-up is still required. Review scope note: due tool limitations in this run, the exact live uncommitted diff could not be independently enumerated via `git diff`; the review is therefore based on branch history, traced high-risk files, and regression evidence from the current workspace.

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnhm9oy9-4d6506",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "updatedAt": "2026-04-02T15:30:26.091Z",
  "finalizedAt": "2026-04-02T15:30:26.091Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "未提交修改三轮深度审查",
    "date": "2026-04-02",
    "overview": "针对当前工作区未提交修改开展三轮递进式深度review，重点核查变更范围、引用链影响及问题修复闭环。"
  },
  "scope": {
    "markdown": "# 未提交修改三轮深度审查\n\n- 日期：2026-04-02\n- 审查目标：对当前工作区未提交修改进行三轮递进式深度审查，确认变更是否真正解决目标问题，并检查引用链、函数变量影响与潜在回归风险。\n- 审查方式：Round 1 识别变更与外层影响面；Round 2 深入核心实现与调用链；Round 3 对照测试/契约/风险进行闭环判断。\n- 当前状态：进行中"
  },
  "summary": {
    "latestConclusion": "Three-round review completed. Judgment: the infrastructure maintenance/backup/transaction fixes in Round 1 are effectively solved; the runtime ownership/shared-state/installer-stop chain in Round 3 is also effectively solved; however, the scheduler terminal/reschedulable fix in Round 2 is only partially solved. The main contract has been tightened across algorithm input, freeze seed, persistence scope, and batch-status denominator, but `ScheduleService._run_schedule()` still lacks a short-circuit when `reschedulable_operations` becomes empty, so the system can still generate a no-op schedule version with history artifacts. Because of that residual behavior, the underlying issue is not fully closed yet and follow-up is still required. Review scope note: due tool limitations in this run, the exact live uncommitted diff could not be independently enumerated via `git diff`; the review is therefore based on branch history, traced high-risk files, and regression evidence from the current workspace.",
    "recommendedNextAction": "Add an explicit empty-`reschedulable_operations` guard in `ScheduleService._run_schedule()`, prevent version/history creation for that no-op path, add a regression covering 'batch status allowed but all operations terminal', then rerun a focused scheduler review.",
    "reviewedModules": [
      "core/infrastructure",
      "web/routes/system_backup.py",
      "core/services/system/system_maintenance_service.py",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_persistence.py",
      "core/services/scheduler/freeze_window.py",
      "app.py",
      "app_new_ui.py",
      "web/bootstrap/factory.py",
      "web/bootstrap/launcher.py",
      "installer/aps_win7.iss",
      "installer/aps_win7_legacy.iss",
      "installer/aps_win7_chrome.iss",
      "assets/启动_排产系统_Chrome.bat"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 1,
    "severity": {
      "high": 0,
      "medium": 1,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "round1",
      "title": "Round 1：基础设施维护窗口、备份恢复与事务嵌套链路审查",
      "status": "completed",
      "recordedAt": "2026-04-02T15:22:05.221Z",
      "summaryMarkdown": "本轮聚焦基础设施层修复闭环，沿着 `web/routes/system_backup.py::backup_restore` → `core.infrastructure.backup.BackupManager.restore` → `core.infrastructure.database.ensure_schema/_migrate_with_backup` → `core.infrastructure.transaction.TransactionManager.transaction` 的链路做了逐段核查。\n\n结论：这一组修复基本收口了此前最危险的三类问题：\n1. 维护窗口并发进入：`maintenance_window()` 通过线程内重入 + 跨线程/跨进程锁文件双层机制，能够阻止并发备份/恢复/迁移，同时允许同线程同库的 restore→before_restore backup→migrate 嵌套链继续执行。\n2. 恢复后迁移一致性：`backup_restore()` 显式在同一维护窗口内执行 `mgr.restore()` 与 `ensure_schema()`，避免“恢复完成但迁移尚未完成”期间被其它请求插入。\n3. 嵌套事务一致性：`TransactionManager.transaction()` 把最外层事务切回 `BEGIN/COMMIT`，内层改为 `SAVEPOINT`，并对 `RELEASE SAVEPOINT` / `ROLLBACK TO SAVEPOINT` / `commit()` 失败做了回滚补偿，语义与回归测试一致。\n\n本轮未发现新的阻断级问题；从实现与回归脚本对照看，这一组修改对原目标问题的修复是有效的。",
      "conclusionMarkdown": "基础设施维护窗口、恢复迁移与嵌套事务三条主链路闭环良好，当前未见阻断性残留缺陷。",
      "evidence": [
        {
          "path": "core/infrastructure/backup.py"
        },
        {
          "path": "core/infrastructure/database.py"
        },
        {
          "path": "core/infrastructure/transaction.py"
        },
        {
          "path": "web/routes/system_backup.py"
        },
        {
          "path": "tests/regression_maintenance_window_mutex.py"
        },
        {
          "path": "tests/regression_exit_backup_maintenance.py"
        },
        {
          "path": "tests/regression_transaction_savepoint_nested.py"
        }
      ],
      "reviewedModules": [
        "core/infrastructure",
        "web/routes/system_backup.py",
        "core/services/system/system_maintenance_service.py"
      ],
      "recommendedNextAction": "继续进入 Round 2，深入排查排产服务对 terminal/reschedulable 工序集合的收口是否真正覆盖 schedule/freeze/persist 全链路。",
      "findingIds": []
    },
    {
      "id": "round2",
      "title": "Round 2：排产服务 terminal/reschedulable 收口链路深挖",
      "status": "completed",
      "recordedAt": "2026-04-02T15:23:11.155Z",
      "summaryMarkdown": "本轮沿 `ScheduleService._run_schedule()` → `build_freeze_window_seed()` → `persist_schedule()` 做了引用链核查，重点验证 terminal 工序（completed/skipped 等）是否已经从算法输入、冻结窗口、Schedule 落库、状态回写、批次状态分母中彻底剔除。\n\n确认已修复的部分：\n1. `run_schedule()` 先计算 `reschedulable_operations`，再用该集合构建算法输入与缺资源集合；terminal 工序不会再进入算法主链。\n2. `build_freeze_window_seed()` 已优先消费调用方传入的 `reschedulable_operations`，冻结窗口 seed 与主排产集合保持同口径。\n3. `persist_schedule()` 通过 `allowed_op_ids=reschedulable_op_ids` 只写入可重排工序；状态回写与批次状态统计也只基于可重排集合，不再把 completed/skipped 工序错误计入分母。\n4. 回归脚本同时覆盖了 mixed-case `source=INTERNAL` 缺资源识别与 mixed-status 批次的状态保持。\n\n但本轮发现一个残余逻辑缺口：当批次本身未被 fail-fast 拒绝、但其工序集合在过滤后 `reschedulable_operations` 为空时，`run_schedule()` 没有提前短路，而是继续分配版本号、构造摘要并调用 `persist_schedule()` 写历史留痕。这样会产生“看似成功、实则无任何排程动作”的空排产版本，说明 terminal/reschedulable 契约虽然已在落库和状态回写层收口，但在服务入口的 no-op 防御仍未完全闭环。",
      "conclusionMarkdown": "terminal/reschedulable 主修复已经覆盖算法、冻结和持久化主链，但服务入口仍缺少“0 可重排工序”短路，问题未算完全收口。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "core/services/scheduler/freeze_window.py"
        },
        {
          "path": "tests/regression_schedule_service_reschedulable_contract.py"
        },
        {
          "path": "tests/regression_schedule_persistence_reschedulable_contract.py"
        },
        {
          "path": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py"
        }
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_persistence.py",
        "core/services/scheduler/freeze_window.py"
      ],
      "recommendedNextAction": "进入 Round 3，继续审查运行时锁/共享状态/启动器与安装器协同链路，确认单活保护和停机契约是否已与测试闭环。",
      "findingIds": [
        "sched-empty-reschedulable-noop"
      ]
    },
    {
      "id": "round3",
      "title": "Round 3：运行时单活、共享状态目录与安装器停机契约闭环审查",
      "status": "completed",
      "recordedAt": "2026-04-02T15:30:13.008Z",
      "summaryMarkdown": "本轮沿 `app.py` / `app_new_ui.py` → `web.bootstrap.factory` → `web.bootstrap.launcher` → `installer/*.iss` 做了运行时 ownership 与停机契约的闭环核查，并补看了 `assets/启动_排产系统_Chrome.bat` 的客户端接入路径。\n\n确认闭环成立的关键点：\n1. **父/子进程 ownership 划分清晰**：`should_use_runtime_reloader()` 只在 debug 且非 frozen 时启用 reloader；`_should_register_exit_backup()` / `should_own_runtime_resources()` 进一步要求 `WERKZEUG_RUN_MAIN=true` 的子进程才持有运行时资源。因此 debug 父进程不会抢占运行时锁、不会提前写 host/port/contract，也不会注册清理回调。\n2. **单活锁与运行时契约指向同一状态目录**：两套入口都先用 `current_runtime_owner()` 生成 owner，再以 `acquire_runtime_lock(runtime_dir, prelaunch_log_dir, owner, exe_path)` 把锁写到共享 `LOG_DIR`；随后 `_configure_runtime_contract()` 写入 `APS_RUNTIME_SHUTDOWN_TOKEN`、`APS_RUNTIME_DIR`、`APS_RUNTIME_OWNER`，并把 host/port/db/runtime.json 主写到共享日志目录。\n3. **兼容旧工具链的镜像仍被保留**：`write_runtime_host_port_files()` 与 `write_runtime_contract_file()` 在共享 `LOG_DIR` 之外，还会向 `runtime_dir/logs` 写镜像；`delete_runtime_contract_files()` 通过 contract 中的 `runtime_dir` 与 `data_dirs.log_dir` 反向清理主目录和镜像目录，避免残留导致后续误判。\n4. **停机 helper 能接受 runtime root 或 state dir**：`stop_runtime_from_dir()` 先用 `_resolve_runtime_stop_context()` 归一化输入。若传入 `.../logs`，会把它视为 state dir；若传入 runtime root，则优先读 `runtime_dir/logs` 镜像。contract 缺失但 host/port 仍健康时，它会返回 busy 而不误删信号文件；不健康时才清理 contract 并按需关闭 APS Chrome。\n5. **安装器与 helper 的契约已经对齐**：`installer/aps_win7.iss` 与 `installer/aps_win7_legacy.iss` 先从 `SharedLogDirPath` / `LegacyLogDirPath` 里的 `aps_runtime.lock` 或 `aps_runtime.json` 解析 `exe_path`，再对 `SharedDataRootPath`、`LegacyDataRootPath`、`RegisteredMainAppDirPath`、当前 `{app}` 逐个执行 `--runtime-stop <runtime_dir>`。这与 launcher 的“runtime root + runtime_dir/logs 镜像”语义一致，而不是旧的“直接传 logs 目录”模式。`aps_win7_chrome.iss` 也确认仍是浏览器运行时安装器，不参与主程序 precleanup。\n6. **前端启动脚本也已切到共享状态口径**：`启动_排产系统_Chrome.bat` 会先解析 `APS_SHARED_DATA_ROOT` / 注册表 / `%ProgramData%\\APS\\shared-data`，再从共享 `LOG_DIR` 读取 lock、host、port、launch_error，并用 owner 比对决定复用、阻塞还是启动新实例。\n\n结合回归脚本看，Round 3 覆盖了 reloader 父/子进程 ownership、共享日志目录主写 + runtime_dir/logs 镜像、contract 清理、`stop_runtime_from_dir()` 的 state-dir 兼容，以及安装器 precleanup / uninstall 的调用约束。当前未见新的断链或残留竞态。",
      "conclusionMarkdown": "运行时单活、共享状态目录、helper 停机与安装器联动链路基本闭环，当前未见新的阻断性缺陷。",
      "evidence": [
        {
          "path": "app.py"
        },
        {
          "path": "app_new_ui.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/bootstrap/launcher.py"
        },
        {
          "path": "assets/启动_排产系统_Chrome.bat"
        },
        {
          "path": "installer/aps_win7.iss"
        },
        {
          "path": "installer/aps_win7_legacy.iss"
        },
        {
          "path": "installer/aps_win7_chrome.iss"
        },
        {
          "path": "tests/regression_runtime_lock_reloader_parent_skip.py"
        },
        {
          "path": "tests/regression_shared_runtime_state.py"
        },
        {
          "path": "tests/regression_runtime_contract_launcher.py"
        },
        {
          "path": "tests/test_win7_launcher_runtime_paths.py"
        }
      ],
      "reviewedModules": [
        "app.py",
        "app_new_ui.py",
        "web/bootstrap/factory.py",
        "web/bootstrap/launcher.py",
        "installer/aps_win7.iss",
        "installer/aps_win7_legacy.iss",
        "installer/aps_win7_chrome.iss",
        "assets/启动_排产系统_Chrome.bat"
      ],
      "recommendedNextAction": "汇总结论并结束本次三轮审查；最终结论需要明确指出 Round 2 仍存在“0 可重排工序”空排产版本残余问题。",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "sched-empty-reschedulable-noop",
      "severity": "medium",
      "category": "other",
      "title": "空排产版本仍可生成",
      "descriptionMarkdown": "`ScheduleService._run_schedule()` 在按 terminal 状态过滤出 `reschedulable_operations` 后，没有对空集合做 fail-fast 或 no-op 返回，而是继续分配版本号并调用 `persist_schedule()` 写入排产历史。对于批次状态仍为 pending/scheduled、但其工序已经全部 completed/skipped 等 terminal 的场景，用户会得到一个表面成功但没有任何实际排产动作的新版本；这会污染版本序列与历史审计结果，也让“本次排产是否真的生效”变得难以判断。当前回归已覆盖 terminal 工序过滤和分母修正，但没有覆盖这一入口短路缺口。",
      "recommendationMarkdown": "在 `run_schedule()` 计算出 `reschedulable_operations` 后，针对空集合显式返回业务错误或 no-op 结果，并阻止版本号分配与 `ScheduleHistory` 留痕；同时补一条回归测试覆盖“批次状态允许，但工序全为 terminal”场景。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "core/services/scheduler/freeze_window.py"
        },
        {
          "path": "tests/regression_schedule_service_reschedulable_contract.py"
        },
        {
          "path": "tests/regression_schedule_persistence_reschedulable_contract.py"
        },
        {
          "path": "tests/regression_schedule_service_missing_resource_source_case_insensitive.py"
        }
      ],
      "relatedMilestoneIds": [
        "round2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:215a7f44bc08ac709c524ea702eb6318f03967145c1a28c08687d4337b107656",
    "generatedAt": "2026-04-02T15:30:26.091Z",
    "locale": "zh-CN"
  }
}
```

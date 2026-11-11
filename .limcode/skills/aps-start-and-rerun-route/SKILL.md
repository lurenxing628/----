---
name: aps-start-and-rerun-route
description: 启动 APS 服务、查看现有计划甘特，或按明确授权在全新/空业务表隔离数据库注入排产样例并完成排产采用。按请求选择独立模式；普通查看、改后验证和重跑业务排产不代表授权重建样例。
---

# APS 启动、查看与样例重跑

先按用户已授权的任务选择模式，直接完成，不重复确认同一个决定：

| 请求 | 模式 | 行为 |
|---|---|---|
| 启动项目 / 启动服务 | `start-only`（无命令时默认） | 复用符合身份合同的健康实例，或启动服务；打开首页，不创建样例、不执行排产 |
| 查看已有甘特 / 查看最新结果 | `view-only` | 只读取已运行服务的最新正式计划并打开工作台；无服务、无可查看计划或身份不一致时明确失败，不启动、不补数据 |
| 明确要求在隔离样例库创建样例并排产，且已指定目标数据库 | `rerun --db-path <隔离库>` | 校验目标库为不存在或空业务表的隔离库，启动或复用匹配实例，通过公开工作台 HTTP 接口注入样例、排产并采用，再核对服务返回的正式计划版本 |

“再跑一遍”“改后验证”要沿用上下文的已授权动作；单独出现时不能推导出样例写入授权。业务排产使用项目现行业务入口，本技能的 `rerun` 专用于全新或空业务表的隔离样例库。

## 用法

```bash
python .limcode/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py start-only
python .limcode/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py view-only --no-open
python .limcode/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py rerun --db-path /absolute/path/to/isolated-demo.db
```

- `--db-path`：`rerun` 必须显式传入非空目标路径，且仅接受尚未创建或业务表完全为空的隔离数据库；不接受仅靠默认值或 `APS_DB_PATH` 推定写入目标。其他模式按参数、`APS_DB_PATH`、`repo_root/db/aps.db` 顺序解析。
- `--host` / `--port`：启动时首选地址，默认 `127.0.0.1:5000`。实际 endpoint 以当前仓库 runtime 契约及健康检查为准，不能因另一个端口健康就复用。
- `--wait-seconds`：启动等待时间，默认 60 秒。
- `--no-open`：不打开浏览器，输出实际 URL。

## 样例写入范围与隔离守卫

`rerun --db-path` 在启动服务前与注入前双重核验目标数据库：只允许不存在的新路径或仅含系统初始化表（`SchemaVersion`、`ScheduleConfig`、`OperationLogs`、`SystemJobState`、`WorkbenchSourceRevisions`、`WorkbenchPlanIdentityClock`、`WorkbenchExecutionLedgerClock`）的空业务库；一旦任意业务表存在既有数据行，立即拒绝重跑，**绝不执行任何破坏性删表或删行**，完整保留触发器与正式计划保护。随后统一通过公开工作台 HTTP 命令契约写入 `ROUTEDEMO_` 资源、工作日历、工艺路线、批次，并执行预检、后台排产与正式候选采用。

## 结果与失败

- 启动报告实际 `host`、`port`、`server_started_now`、`url`。
- 查看报告服务返回的 `version`、`plan_ref`、`task_count`、工作台 `url`；读取 `/api/workbench/v1/plans` 与对应 `/workspace`（`task_count` 取自正式计划完整任务总数，支持 `/workspace` 返回首屏分页任务切片 `tasks`）。不跳过最新不可用计划去选择旧版本或候选方案。
- 重跑报告 `version`、`plan_ref`、`task_count`、工作台 `url`（从采用回执读取 `official_plan.version` 后回读 `/api/workbench/v1/plans` 与 `/workspace` 复核同一版本）。服务版本不符、计划编号缺失或不可查看时失败；不得自行补身份或冒充成功。
- 旧 `/scheduler/gantt/data` 已退役，不再作为验收接口；链接使用新工作台的正式计划编号。
- 实例与数据库身份核验：同时核查 `logs/aps_host.txt`、`logs/aps_port.txt`、`logs/aps_db_path.txt`、`logs/aps_runtime.json` 与 `/system/health` 返回的活进程 `db_path`、`instance_id`、`pid` 交叉一致；任一缺失或不匹配即明确失败，保留错误原因，不静默切库、覆盖其他实例或补造结果。

兼容变化：原来不带命令会重建样例，现在只启动；显式 `rerun` 名称保留，必须带隔离空库 `--db-path`，且已移除旧 `--view` 参数。查看模式要求服务已运行；只有启动请求才使用 `start-only`。

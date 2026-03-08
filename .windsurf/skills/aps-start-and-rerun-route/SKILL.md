---
name: aps-start-and-rerun-route
description: Starts APS project, reruns a complex scheduling case on the real database, validates /scheduler/gantt/data, and opens /scheduler/gantt with the latest version. Use when the user asks 启动项目/再跑一遍/重跑排产/打开或查看 scheduler gantt/我改了系统再验证一次.
---

# APS 启动并重跑真实排产

## Quick start

- 重跑排产（默认）：`python .windsurf/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py`
- 仅启动项目：`python .windsurf/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py start-only`
- 默认行为：
  - 如果服务未启动，自动执行 `start.bat`
  - `rerun`：使用真实库 `db/aps.db` 重建一组 `ROUTEDEMO_` 前缀复杂样例并执行排产，校验 `/scheduler/gantt/data`，并打开对应版本页面
  - `start-only`：只启动并校验服务健康，不执行排产（默认打开首页）

## 适用场景（触发词）

- 启动项目 / 启动服务
- 再跑一遍 / 同样流程再跑
- 我改了系统，再验证一次
- 打开 / 查看 `/scheduler/gantt` 页面结果

## 参数

- `command`：`rerun`（默认）或 `start-only`
- `--view machine|operator`：甘特视图，默认 `machine`
- `--host`：默认 `127.0.0.1`
- `--port`：默认 `5000`
- `--wait-seconds`：等待服务就绪超时（秒），默认 `60`
- `--no-open`：不自动打开浏览器，仅输出 URL

## 工作流（给 Agent）

1. 直接运行 runner 脚本，不手工拼接长命令。
2. 若用户要求“仅启动”，使用 `start-only`。
3. 脚本成功后回报：
   - `rerun`：`version`、`week_start`、`task_count`、`url`
   - `start-only`：`server_started_now`、`url`
4. 脚本失败时，直接回传错误摘要，并提示先检查端口占用与 `start.bat` 启动输出。

## 输出模板（建议）

```markdown
已完成重跑并启动项目：
- version：<n>
- week_start：<yyyy-mm-dd>
- task_count：<n>
- 页面：<url>
```

---
name: aps-start-and-rerun-route
description: Starts APS project, reruns a complex scheduling case on the real database, validates /scheduler/gantt/data, and opens /scheduler/gantt with the latest version. Use when the user asks 启动项目/再跑一遍/重跑排产/打开或查看 scheduler gantt/我改了系统再验证一次.
---

# APS 启动并重跑真实排产

## Quick start

- 重跑排产（默认）：`python .windsurf/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py`
- 仅启动项目：`python .windsurf/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py start-only`
- 默认行为：
  - 优先探测健康实例：先按 `--host` / `--port` 探测，再按 `logs/aps_host.txt` + `logs/aps_port.txt` 探测
  - 仅当当前仓库的运行时 `host` / `port` / `db_path` 都能证明该实例归属且 DB 与目标一致时，才允许复用
  - 若没有健康实例，自动执行 `start.bat`，并等待运行时 endpoint 就绪
  - `rerun`：默认回退到 `db/aps.db`，但若显式传入 `--db-path` 或设置 `APS_DB_PATH`，则以该目标 DB 为准；脚本会重建一组 `ROUTEDEMO_` 前缀复杂样例并执行排产，校验 `/scheduler/gantt/data`，并打开对应版本页面
  - `start-only`：只启动并校验服务健康，不执行排产（默认打开首页）

## 适用场景（触发词）

- 启动项目 / 启动服务
- 再跑一遍 / 同样流程再跑
- 我改了系统，再验证一次
- 打开 / 查看 `/scheduler/gantt` 页面结果

## 参数

- `command`：`rerun`（默认）或 `start-only`
- `--view machine|operator`：甘特视图，默认 `machine`
- `--host`：优先探测/启动的 host，默认 `127.0.0.1`
- `--port`：优先探测/启动的 port，默认 `5000`；实际访问地址以 `logs/aps_host.txt` 与 `logs/aps_port.txt` 为准
- `--db-path`：目标 DB 路径；优先级 `--db-path` > `APS_DB_PATH` > `repo_root/db/aps.db`
- `--wait-seconds`：等待服务就绪超时（秒），默认 `60`
- `--no-open`：不自动打开浏览器，仅输出 URL

## 工作流（给 Agent）

1. 直接运行 runner 脚本，不手工拼接长命令。
2. 若用户要求“仅启动”，使用 `start-only`。
3. 脚本成功后回报：
   - `rerun`：`version`、`week_start`、`task_count`、`host`、`port`、`url`
   - `start-only`：`server_started_now`、`host`、`port`、`url`
4. 脚本失败时，直接回传错误摘要，并优先检查：
  - `logs/aps_host.txt` / `logs/aps_port.txt` / `logs/aps_db_path.txt` 是否已生成且彼此一致
   - `GET /system/health` 是否返回 `{"app":"aps","status":"ok"}`
  - 当前仓库 runtime `host` / `port` / `db_path` 是否能证明命中的健康实例属于本仓库
   - `start.bat` 启动输出

## 输出模板（建议）

```markdown
已完成重跑并启动项目：
- version：<n>
- week_start：<yyyy-mm-dd>
- task_count：<n>
- 页面：<url>
```

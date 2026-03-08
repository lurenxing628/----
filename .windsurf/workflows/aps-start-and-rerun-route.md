---
description: 启动 APS 并重跑真实排产：必要时拉起服务、重建 ROUTEDEMO_ 样例、校验 /scheduler/gantt/data 并返回页面地址
---
当用户提到“启动项目 / 启动服务 / 再跑一遍 / 重跑排产 / 打开或查看 scheduler gantt / 我改了系统再验证一次”时，使用本 workflow。

- 本地 skill 说明：`.windsurf/skills/aps-start-and-rerun-route/SKILL.md`

1. 先判断用户需要的模式。
   - 默认用 `rerun`：重跑真实排产。
   - 若用户明确说“只启动”或“先把服务拉起来”，改用 `start-only`。

2. 直接运行 runner 脚本，不要手工拼接一长串命令。
   - 重跑排产：`python .windsurf/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py`
   - 仅启动项目：`python .windsurf/skills/aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py start-only`

3. 按需补参数。
   - `--view machine|operator`：默认 `machine`
   - `--host`：默认 `127.0.0.1`
   - `--port`：默认 `5000`
   - `--wait-seconds`：默认 `60`
   - `--no-open`：只输出 URL，不自动打开浏览器

4. 依赖 runner 的默认行为，不重复造轮子。
   - 若服务未启动，脚本会自动执行 `start.bat`。
   - `rerun` 会使用真实库 `db/aps.db` 重建一组 `ROUTEDEMO_` 前缀复杂样例、执行排产、校验 `/scheduler/gantt/data`，并打开对应版本页面。
   - `start-only` 只启动并校验服务健康，不执行排产。

5. 成功后按模式回报结果。
   - `rerun`：回报 `version`、`week_start`、`task_count`、`url`
   - `start-only`：回报 `server_started_now`、`url`

6. 失败时只回传错误摘要，不要自己发散修别的问题。
   - 先提示检查端口占用。
   - 再提示查看 `start.bat` 启动输出。
   - 如用户要继续排查，再进入更细的启动/运行调试。

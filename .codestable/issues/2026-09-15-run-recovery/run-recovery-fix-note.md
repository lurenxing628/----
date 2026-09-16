---
doc_type: issue-fix-note
status: fixed
date: 2026-09-15
title: 恢复数据库后的排产请求识别与真实查询状态
roadmap: workbench-manual-remediation
items: [wbfix-run-recovery, wbfix-run-panel]
---

## 问题与证据

对应用户批注 19、20 和总方案 B6。恢复数据库之后，浏览器仍保存上次排产的 request_key；原实现 found=false 永久轮询，无实际请求时也显示“正在查询”。空范围预览的 no_eligible_tasks 又落入提交结果不确定的通用文案。

本次实际旧编号为 `run-86a45790db230dc6e7bf182e88df2830e20f9b3ad4795de1`。此前只读核对已证明：测试备份中任务 complete/finished，当前恢复后数据库无同号任务及受理回执。恢复后的漏验属于上一轮验证缺项。本子任务没有修改真实数据库、清浏览器记录或重启活服务。

## 修复

- 新增 `core/services/workbench/run_data_context.py`。`data_context_ref` 由当前数据库 scope 和成功恢复的 journal job_ref 集合生成；普通服务重启、创建备份、删除备份、失败恢复和自动还原不改变它。成功恢复把 `data_context_before` 写在同一个已有 journal 终态记录中。未确认恢复继续服从既有启动门禁。
- 这比拟方案更小：复用已有持久 journal，而非新增代次文件或数据库表。现有 journal 位于数据库外，维护删除仅删除选定备份，未找到会因普通重启或备份轮换而清理 journal 的产品路径。
- 排产预览的写入快照绑定数据代次，恢复前预览不能恢复后受理。Preview、Admission 返回 `data_context_ref`；Lookup 返回 `found/run/data_context_ref/resolution`，其中 resolution 为 found、context_replaced 或 unresolved。
- Lookup 先核对当前数据库任务及回执。当前记录存在时总是读取当前结果；记录不一致继续明确报错。不同但无法证明是旧数据代次的客户端字符串不构成解除理由。
- 旧 v1 pending 仅在最近成功恢复 journal 登记的保护备份中，按原 request_key 找到任务与 scheduling.run 受理回执且 SHA256 前后均一致，才判定 context_replaced。备份使用 SQLite `mode=ro&immutable=1` 并显式关闭连接；不访问浏览器指定路径，不扫描任意备份，不补写旧历史。缺文件、变更、缺表或未知请求都保持 unresolved。
- 新 pending 使用 v2，保存数据代次和最少身份信息。正常终态和已证明恢复的旧请求移到最近记录，再仅解除同号 pending；最近结果可重新打开查询。旧标签页不能删除新排产记录，其他页面存储不变。
- 无记录或查询失败持续 60 秒暂停自动查询；真实排队/计算记录继续查询，计时本身从不触发重新提交。页面只在真正发出请求时显示查询中，展示最近查询时间并提供有文字的“查询结果”。
- 候选排产区按标题说明、动作与原因、最近记录、阶段与候选分区。编号保持折叠。计算期间的提示说明本机继续计算，不再要求用户一直停留或禁止刷新页面。
- 空批次范围直接禁用开始按钮并说明选择批次；no_eligible_tasks 有专门提示。读取预览失败统一要求重新检查，不进入提交结果不确定状态。

## 文件与集成

产品文件：`run_data_context.py`、`run_jobs.py`、`system_files.py`、`web/routes/workbench/scheduling_jobs.py`、`RunJobAPI.js`、`RunJobPanel.jsx`、`RunJobControls.jsx`、`styles/34-run.css` 的 run 区规则。无新前端 build-order 条目，未手改 static。

测试文件：新增 `test_run_data_context.py`、`run_recovery_widgets_cases.cjs`；更新既有 run 浏览器 fixture/probe、空范围验收、UI 合同、并发与真实恢复生命周期断言。既有并发测试三个计算替身原先缺少当前 `on_progress` 参数，已按真实签名透传，保留原并发断言。

## 验证

- 定义和影响面：执行 `python3 -m tools.symbol_locator whereis lookup --at core/services/workbench/run_jobs.py:125` 与 `callers lookup --json`。静态工具对同名服务方法有动态歧义，后续按实际 route 构造与调用核对。保留已有 dirty 工作区和定位快照。
- `.venv/bin/python -m pytest tests/workbench/test_run_jobs_api.py tests/workbench/test_run_jobs_atomic.py tests/workbench/test_run_jobs_concurrency.py tests/workbench/test_run_jobs_restart.py tests/workbench/test_run_jobs_recovery.py -q`：35 passed。
- `.venv/bin/python -m pytest tests/workbench/test_run_data_context.py tests/workbench/test_system_restore_host.py tests/workbench/test_system_restore_host_recovery.py tests/workbench/test_system_maintenance_restore.py tests/workbench/test_system_maintenance_api.py -q`：76 passed，包含真实隔离 HTTP 恢复和原进程必须停止、重启才能恢复写入的生命周期。
- `node tests/workbench/test_run_ui_refinement.cjs`：通过，含 v1/v2、本域 pending 解除、其他记录保留、旧页不得解除新请求、预览失败文案合同。
- `.venv/bin/python -m pytest tests/workbench/test_run_job_widgets.py -q -s`：最终 1 passed / 119.29 秒。Chrome 109、4 个宽度/主题组合、261 项行为断言通过；含 v1/v2 恢复识别、60 秒暂停、长期运行续查、断网同号恢复、其他 pending 保留和最近记录重开。真实计算 5000 工序 × 4 候选，共 20000 条候选任务，DOM 150 节点；当前源码 SHA 与测试编译版本一致，业务事实保持不变。
- 最终浏览器证据目录：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-run-job-widgets-rh3wdn25`，含 `run-job-widgets.json`、`sqlite-proof.json` 和浅/深色截图。中间一轮因并行源码变化触发 SHA 核对；最终冻结后已完整重跑通过。
- `git diff --check`：本轮改动范围通过。

全局构建与真实页面当前旧请求恢复验证由主代理在并行分支汇合后执行。按用户最新明确要求不跑全门禁，仅报告本轮定点专项；本记录不是 clean-worktree proof。

---
doc_type: feature-design
feature: 2026-04-28-runtime-launcher-stop-contract
status: approved
summary: 收口 launcher 启动现场门面，把 runtime 启停、锁、合同和进程探测下沉，同时修正 APS Chrome 停止误判。
tags: [startup, runtime, launcher, technical-debt]
roadmap: p1-scheduler-debt-cleanup
roadmap_item: runtime-launcher-stop-contract
---

# runtime launcher stop contract 设计

## 0. 承接边界

本任务只处理 M7-A：`web/bootstrap/launcher.py` 过长、runtime 状态分类复杂、Chrome 停止链路复杂和 APS Chrome 停止误报失败。

明确不做：

- 不改变 `entrypoint.py`、`run_quality_gate.py`、批处理和安装包依赖的公开函数名、状态文件名、合同字段或 CLI 返回码。
- 不扩大 Chrome 清理范围，仍然只认 APS 专用 `--user-data-dir` profile。
- 不处理 plugin enabled source，plugin 走 M7-B。
- 不处理 P1-25；它没有当前路径、台账或测试 nodeid。
- 不声明 full-test-debt 减少。
- 不新增兜底逻辑；只把已有判断按职责搬清楚，并修正 Chrome 停止成功标准。

## 1. 对外合同

- `web/bootstrap/launcher.py` 继续作为稳定门面，保留原公开函数名和返回值。
- `stop_runtime_from_dir()` 仍返回 `0/1`。
- `stop_aps_chrome_processes()` 仍返回 `bool`。
- 内部可以用结构化结果区分 Chrome stop 失败原因，但不得变成新的公开入口。
- APS Chrome 停止成功标准改为“最终复查后没有同 profile 的 Chrome 进程”，不再要求旧 pid 每个都单独杀成功。

## 2. 实现策略

1. 先补红灯测试，覆盖 Chrome pid 被连带关闭、最终仍残留、无 logger 时失败原因可见、CLI 带 `--stop-aps-chrome`。
2. 新增 `launcher_network.py`、`launcher_paths.py`、`launcher_processes.py`、`launcher_contracts.py`、`launcher_stop.py`，让 `launcher.py` 只做门面和测试兼容转调。
3. 拆低 `_classify_runtime_state`、`_list_aps_chrome_pids`、`stop_runtime_from_dir` 和 `acquire_runtime_lock` 的复杂度。
4. 同步 Chrome 独立安装脚本，让它也按“最终复查”判断，不因为某个旧 pid 已经消失而提前失败。
5. 刷新启动链台账和样本坐标，确认新模块仍在 `web/bootstrap/**/*.py` 扫描范围内。

## 3. 验收契约

- `launcher.py` 小于 500 行，新拆出的启动链模块也都小于 500 行。
- P1-20、P1-21、P1-22 对应的 oversize/complexity 登记关闭。
- 启动链专项测试、runtime stop CLI、架构体检、台账检查通过。
- 没有新增 active xfail，也不把 full-test-debt 写成减少。

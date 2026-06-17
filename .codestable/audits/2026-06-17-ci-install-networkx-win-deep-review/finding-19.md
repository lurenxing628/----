# Finding 19：README、开发文档、架构文档和专项回放文档仍引用迁移前路径

- 优先级：P1 阻塞
- 结论：测试目录大迁移后，多个仍被用户或 AI 会话使用的文档没有同步。照文档运行会跑空目录、找不到测试文件，或得到与当前默认配置相反的理解。

## 根因

本分支大规模迁移测试目录，但文档引用没有被同等强度地检查。当前门禁能证明测试代码本身收集，但不能证明 README、开发文档、架构文档和专项回放文档里的命令仍可执行。

大白话说：代码和测试搬家了，路牌没一起搬。后来的人按路牌走，会走到空房间。

## 证据

- `README.md:88-90`：常用定向命令仍写 `.venv\Scripts\python -m pytest tests/regression -q`。
- 目标提交里 `tests/regression` 只有 `tests/regression/__init__.py`，该命令不会覆盖真实专项回归。
- `开发文档/README.md:23-25`：开发基线只安装 `requirements.txt` 和 `requirements-dev.txt`，没有 `requirements-optimizer-lite-win7.txt`。
- `开发文档/README.md:108-109`：仍写 `tests/regression/regression_collection_contract.py`，但目标提交不存在该文件。
- `.codestable/architecture/ARCHITECTURE.md:62`：仍列出 `tests/regression_aps_workbench_flow_contract.py`、`tests/regression_scheduler_historical_plan_label_contract.py` 等迁移前路径。
- `.codestable/architecture/ARCHITECTURE.md:77`：仍写 `tests/regression_resource_dispatch_public_output_contract.py`。
- `.codestable/architecture/ARCHITECTURE.md:84`：仍写 `graph_analysis_mode=off` 是默认关闭模式，但当前代码默认是 `on`。
- `.codestable/architecture/ui-gantt.md:17` 和 `:42`：仍引用 `web_new_test/templates/scheduler/gantt.html` 和现代模板镜像，目标提交里该路径不存在。
- `docs/dev/aps-browser-scheduler-qa-replay.md:850-875`：回放命令仍引用 `tests/test_scheduler_run_view_result_contract.py`、`tests/regression_scheduler_run_surfaces_resource_pool_warning.py`、`tests/regression_schedule_service_reject_no_actionable_schedule_rows.py`、`tests/regression_scheduler_week_plan_no_reschedulable_flash.py`，目标提交均不存在。

## 影响

- 新人、AI 子代理、后续维护者按文档执行会得到错误 proof。
- 架构文档会误导大家以为图分析默认关闭，从而低估 NetworkX 安装和 Win7 打包风险。
- 专项回放文档会让人以为历史自动化命令仍然可复跑，实际文件已经迁移。

## 建议

- 给文档引用路径加检查：文档中的 `tests/...`、`templates/...`、`web_new_test/...` 至少要能在目标提交中存在。
- README 和开发文档同步 NetworkX 安装命令。
- 架构文档里同步当前 `graph_analysis_mode=on` 的事实。
- 专项回放文档保留历史命令时要标注“历史路径”，并给出当前可运行的新路径。

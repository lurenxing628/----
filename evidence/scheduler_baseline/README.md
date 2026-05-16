# NetworkX 引入前排产基线

本目录保存引入 NetworkX 前的排产结果基线，用于后续验证 `graph_analysis_mode=report` 只读旁路不改变排产结果。

## 捕获时间

2026-05-17 01:37:09 CST（Asia/Shanghai）

## 分支与提交

- 分支：`feature/networkx-scheduler-graph`
- 原始工作树状态：`00_git_status_before_networkx.txt`
- 原始提交：`00_git_commit_before_networkx.txt`
- 分支创建后状态：`00_git_status_on_feature_branch_before_networkx.txt`
- 分支创建后提交：`00_git_commit_on_feature_branch_before_networkx.txt`

## Python 与依赖基线

正式项目口径使用 `.venv/bin/python` 捕获：

- Python 版本：`01_python_version_before_networkx.txt`
- Python 完整版本：`01_python_full_version_before_networkx.txt`
- pip freeze：`02_pip_freeze_before_networkx.txt`
- 根目录副本：`../baseline_pip_freeze_before_networkx.txt`

辅助记录：本机默认 `python` 版本另存为：

- `01_default_python_version_before_networkx.txt`
- `01_default_python_full_version_before_networkx.txt`
- `02_default_python_pip_freeze_before_networkx.txt`

当前项目 `.venv` 探针结论：`04_current_env_networkx_import_probe.txt` 显示未安装 NetworkX。

## 核心文件指纹

`03_core_file_hashes_before_networkx.txt` 记录以下文件 SHA256：

- `requirements.txt`
- `requirements-dev.txt`
- `pyproject.toml`
- `schema.sql`

阶段 0 后 `requirements.txt` 的 hash 不应变化。

## 目的

后续 `graph_analysis_mode=report` 时，必须证明排产核心结果未改变。

## 对比规则

严格比较：

- `op_id`
- `batch_id`
- `op_code`
- `seq`
- `source`
- `machine_id`
- `operator_id`
- `supplier_id`
- `start_time`
- `end_time`
- `lock_status`

忽略：

- `version`
- `time_cost_ms`
- `ScheduleHistory.id`
- `OperationLogs.id`
- `result_summary.algo.graph_analysis`
- `result_summary.diagnostics.graph_analysis`

## 案例

三组案例通过 `tools/capture_networkx_phase0_baseline.py` 在复制库 `/tmp/aps_networkx_phase0_baseline.db` 上生成，没有直接写入 `db/aps.db`。

- `case_001_normal_result.json`：普通内部排产；`batch_ids=UX-0510-E02`；2 条 `schedule_rows`；`strategy=due_date_first`。
- `case_002_urgent_result.json`：急件/优先级排产；`batch_ids=UX-0510-E03,UX-0510-E02`；4 条 `schedule_rows`；`strategy=priority_first`。
- `case_003_external_result.json`：含外协工序排产；`batch_ids=UX-0510-E01`；4 条 `schedule_rows`；`strategy=due_date_first`。

注意：`simulate=True` 仍会写入 `Schedule`、`ScheduleHistory` 和 `OperationLogs`，不能直接对生产库执行。

## 阶段 0 禁止事项

阶段 0 不安装 NetworkX，不新增 `requirements-optimizer-lite-win7.txt`，不修改 `requirements.txt`，不新增 `core/services/scheduler/graph/`，不改排产主链文件，不新增迁移，不改页面，不跑 PyInstaller 打包。

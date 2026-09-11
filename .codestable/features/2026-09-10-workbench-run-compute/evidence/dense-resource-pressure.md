# 密集单资源 5000 工序：未通过

本机记录日期：2026-09-10，Asia/Shanghai。运行 Python 3.8.10，临时 SQLite，真实算法，无 mock、无生产库。

## 原参数

- 100 批：B1、CAP-001 至 CAP-099，每批 50 道单链内部工序，共 5000 道。
- 每批 quantity=3、priority=normal、ready_status=yes、due_date=2026-09-25；所有工序 source=internal、op_type_id=T1、setup_hours=0、unit_hours=0.001、status=pending。
- **全部 5000 道固定同一真实资源对 M1/O1**，该人员有该设备授权；未创建第二资源组。
- 窗口 2026-09-09 至 2026-09-25（结束日次日 00:00 为排他上界）；ready_check=true、missing_resource_policy=auto_assign、completed_policy=preserve_actuals。
- 使用 `default_snapshot_values()`，覆盖 algo_mode=greedy、graph_candidate_weight_count=3、time_budget_seconds=600、ortools_enabled=no、freeze_window_enabled=no。
- AS 运行期副本 graph_analysis_mode=on、auto_assign_persist=no：原算法加 3 个真实图候选，非减少为一个方案。
- 无既有正式安排、无执行报告；AJ 提供真实 5000 条未报工投影。未设自定义日历，沿用现有引擎真实默认工作日/周末规则。
- 原测试尾部要求四候选各 5000 行、全表不变和 elapsed<180；**未运行到这些成功断言，不能声称已满足**。

## 命令与日志

当时 `tests/workbench/test_run_compute_capacity.py` 使用上述单资源参数。该文件后来改为分散负载，不能用当前文件冒充这次原负载。

```text
.venv/bin/python -m pytest -q tests/workbench/test_run_compute_capacity.py --disable-warnings --durations=3 --maxfail=1

============================= slowest 3 durations ==============================
0.93s setup    tests/workbench/test_run_compute_capacity.py::test_5000_operations_produce_complete_candidates_with_no_database_changes
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! KeyboardInterrupt !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
/Users/lurenxing/GitHub/----/core/services/scheduler/calendar_engine.py:64: KeyboardInterrupt
(to show a full traceback on KeyboardInterrupt use --full-trace)
no tests ran in 340.33s (0:05:40)
```

观察到仍在 CPU 计算后，AS 对自己这次 pytest 进程发送 SIGINT，退出码 2。上述是 pytest 实际给出的中断位置；当次没有 `--full-trace`，**没有取得完整 Python 调用栈**，不得补造或把第64行当成已定位性能根因。

中断前一次本机原生采样记录了 Python 3.8.10、physical footprint 156.6M、peak 163.6M；原生符号采样不能替代 Python 级性能归因。此处不声称 scheduler 已通过容量门槛，也不声称中断场景完成了候选/逐表验收。

## 后续边界

单资源密集争用的 5000 工序容量目标保持未通过。100 资源分散用例的通过结果只证明另一个负载，不替换本记录。用户明确要求不要在本轮长时间重复该单资源压力跑；主线继续 AV run 接合，性能专项另行授权。

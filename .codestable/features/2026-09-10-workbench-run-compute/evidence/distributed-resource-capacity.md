# 分散资源 5000 工序：独立通过证据

本机记录日期：2026-09-10，Asia/Shanghai。Python 3.8.10，临时 SQLite；测试入口 `tests/workbench/test_run_compute_capacity.py:10`。

## 负载

- 100 批，每批 50 道单链内部工序，共 5000 道；quantity=3、setup_hours=0、unit_hours=0.001。
- 第1批固定 M1/O1，其余各批各自固定 CM001/CO001 至 CM099/CO099；共 **100 个真实设备/人员组**，全部写入真实机器、人员和授权表，不 mock 资源。
- 与密集单资源场景相同的日期窗口、单次规则、greedy、3 档图权重和 600 秒候选预算；仍计算原算法加 3 个真实图候选。
- 每个候选都验证精确 5000 个 op_id 和 5000 行，所有行正时长；读取所有表逐行比对且 total_changes 不变。

## 实际输出

```text
.venv/bin/python -m pytest -q tests/workbench/test_run_compute_capacity.py --disable-warnings --durations=3 -o faulthandler_timeout=120 --maxfail=1

.                                                                        [100%]
============================= slowest 3 durations ==============================
108.63s call     tests/workbench/test_run_compute_capacity.py::test_5000_operations_produce_complete_candidates_with_no_database_changes
0.65s setup    tests/workbench/test_run_compute_capacity.py::test_5000_operations_produce_complete_candidates_with_no_database_changes

(1 durations < 0.005s hidden.  Use -vv to show these durations.)
1 passed in 109.53s (0:01:49)
```

108.63 秒是 pytest 的整个 test call 计时，包含测试体内的负载准备和前后比对，不冒充独立测得的纯优化耗时。所有候选仅存在内存，不写 Schedule、ScheduleHistory、ScheduleVersionSeq、ScheduleCandidate 或其他表。

本项是 dirty 工作区中的分散负载容量证据，不是最终 HEAD/clean proof；更不能替代 `dense-resource-pressure.md` 中未通过的单资源密集争用目标。

# Finding 01：full-test-debt 的 serial 分片并没有独占运行

- 优先级：P1 阻塞
- 结论：不能把当前 full-test-debt 的 sharded 结果当成“串行污染已经隔离”的证明。

## 根因

`tools/full_test_debt_shards.py` 把 runtime、port、long_gate、evidence、scheduler_graph 等用例归到 serial，语义上是“这些用例需要避开并发污染”。但是 `tools/collect_full_test_debt.py` 只是在分组名上叫 serial，真正执行时把 serial 和 parallel 分片全部放进同一个 `worker_jobs`，然后同一轮 `subprocess.Popen()` 全部启动，最后才逐个 `communicate()`。

大白话说：代码嘴上说“这一组要单独跑”，实际是“一起点火，只是名字叫 serial”。

## 调用链

- `tools/check_full_test_debt.py --sharded --shard-count 3`
- 调用 `tools/collect_full_test_debt.py --sharded`
- `split_nodeids()` 返回 `serial_nodeids, parallel_shards`
- `collect_full_test_debt.py` 第 590-596 行构造 `serial + parallel-*`
- 第 601-635 行统一 `Popen()`

## 证据

- `tools/collect_full_test_debt.py:590-596`：serial 和 parallel 都进入 `worker_jobs`。
- `tools/collect_full_test_debt.py:601-635`：同一个循环启动所有进程。
- `tools/collect_full_test_debt.py:636-646`：启动完后才收结果。
- 子代理 D1 的只读模拟输出：`popen:serial`、`popen:parallel-1`、`popen:parallel-2`，然后才 `communicate:serial`。

## 影响

- 如果 serial 用例确实有全局状态污染，当前门禁没有做到隔离。
- full-test-debt 可能在本地和 CI 上偶发稳定、偶发失败，或更危险地“污染互相抵消后假通过”。

## 建议

- 把 serial worker 和 parallel workers 拆成两个阶段：serial 完全跑完后再启动 parallel，或 parallel 完全跑完后再跑 serial。
- 补一个测试钉住 Popen 顺序：serial 与 parallel 不能同时处于启动状态。

---
title: SGS 单趟重叠索引精确复用
date: 2026-09-08
status: implemented
method: Memoization
verification: scoped-dirty-worktree
performance_status: paired-timing-verified
---

# 结论

- 已实施保守的资源重叠索引复用。仅在同一次 SGS 内、同一资源域和资源 ID 的完整段内容相等时复用；内容不同即替换旧索引，不保存历史代际。
- 未缓存完整时间槽、派工结果或评分 key；自动选机、负载排序、日历、rule、窗口、abort_after、计数和失败处理仍按原路径执行。
- 新增 57 项独立合同/等价测试通过；SGS 及直接相邻回归共 223 项通过。定向 Ruff/Pyright 通过，11 个本轮产品/测试文件通过 Python 3.8 AST 解析。
- 这是 dirty worktree 上的局部验证，不是全 algorithm、整仓门禁或 clean-worktree proof。按主代理 2026-09-08 的协调要求，不运行全量，暂不继续计时。

# 测量与选择

`tests/_support/sgs_slot_reuse_case.py` 使用真实 `GreedyScheduler.schedule`、SGS、自动派工、`CalendarEngine`。日历记录来自纯内存 provider，`sqlite3.connect` 被显式禁止。数据为确定性构造的中型排程，不是工厂真实 DB 数据。

规模：36 批、每批 8 道工序，共 288 道待排工序；12 台设备、12 名人员；每工种 4 台候选设备、每台 2 名可用人员；另有 36 条 seed 占用和每台 4 条停机，包含周末、人员效率差异、连续前置链和资源竞争。

| 函数/工作量 | before | after |
| --- | ---: | ---: |
| `SegmentOverlapIndex.__init__` | 151740 | 608 |
| `SegmentOverlapIndex._materialize` | 135510 | 607 |
| `estimate_internal_slot` | 50580 | 50580 |
| `_pair_score` | 44960 | 44960 |
| `SegmentOverlapIndex.shift_end` | 723291 | 723291 |
| `CalendarEngine.add_working_hours` | 241097 | 241097 |

before 的 151740 次索引构建中，151132 次再次遇到相同序列和相同内容。实际重复成本首先落在索引构建/物化；日历仍占较大成本，但不属于本轮所有权范围。选择局部索引 Memoization，不扩展为日历结果缓存或整个评分缓存。

完整 324 条输出（含 seed）、summary（仅排除耗时字段）、warnings、errors、failure_details、strategy、params、algo stats 精确相等，不只比较 makespan，也不使用近似误差。

已有非 profiler 耗时原始值：before 为 2.383225 / 2.413824 / 2.396245 秒，after 为 2.219710 / 2.255134 / 2.246062 秒。两组内部逐次串行，但**未确认其他代理当时没有同时跑性能或测试**，因此这些仅是未隔离观察，不据此宣称加速比例或任何规模收益。机器无关的调用数与结果等价是当前主证据。profiler 自身耗时只用于定位，不能当作运行收益。

# 最小接入与失效合同

- `core/algorithm_runtime/slot_overlap_reuse.py`：单趟 helper。按 `(machine/operator/downtime, resource_id)` 保存最新 tuple 快照和索引。每次复用前重新对照完整段内容，覆盖追加、空档插入、删除、清空、整体替换、同长度原地修改；不是只看 `len` 或对象 `id`。
- `run_state.py`：自建机台时间轴使用不重写 dict 读写操作的 `SlotReuseTimeline`，用于携带本趟可选 helper。调用方借入的普通 dict 保持身份/别名，仍走原来的单 estimate 索引路径，不做猜测式包装。
- `dispatch/sgs.py`：仅包住原 SGS loop；正常退出和异常退出都在 `finally` 释放本趟 helper。默认非 SGS、下一次 schedule、不同 state 不共享。
- `internal_slot.py`：新增可选 helper，仍在原估算器中运行所有计算与校验。
- `auto_assign.py`、`dispatch/sgs_scoring.py`、`internal_operation.py`：各自仅传入本趟 helper，不改变资源选择或评分；探测到正式落位之间也能复用索引。
- `downtime.py`：保留已有惰性物化及 `zip/map/accumulate` 优化。已物化数组可跨 estimate 复用；未物化时每次 estimate 仍从首次线性查询开始，防止多次零跳查询提前触发乱序异常。
- 两处已有 Pyright 错误已先复现再修复：只读扫描参数从 `List` 标为 `Sequence`；`_materialize` 返回已确定的 starts，用局部变量排除 `_starts is None`，不靠 ignore/cast 隐藏问题。

快照比较仍有 O(T) 成本；只消除重复索引物化，不把完整排槽宣称为 O(log T)。每个资源只保留最新索引，内存随本趟资源及段数增长，不随所有探测次数累计。估算期间输入不可变的原合同继续成立。

# 验证与边界

- `test_sgs_slot_reuse_contract.py`：同资源复用、三个资源域隔离、全部修改方式失效、旧索引不可变快照、乱序零跳/实际跳转、窗口等号、早停、工时/数量/优先级/换型/效率重新计算、零工时、120 次随机交错修改、生命周期和借入 dict 别名。
- `test_sgs_slot_reuse_equivalence.py`：SLACK/CR/ATC，固定资源/自动分配，普通 SGS/图 ready 与图评分，seed/停机/周末/效率变化，窗口失败及传播，零工时，完整结果/失败明细/计数逐字段一致，同 scheduler 跨次隔离。
- 初次图夹具漏 `sort_key_by_op_id` 的 12 项失败已修正；最终新增专项 57/57、相关回归 223/223。新测试的混合 kwargs 字典类型也已补齐，最终定向 Pyright 为零错误。
- 未运行全 algorithm 或完整 `scripts/run_quality_gate.py`；冻结后由主代理统一跑。当前 macOS 的仓库 `.venv/bin/python` 实际版本为 Python 3.8.10，223 项测试在该解释器上执行，另有 Python 3.8 AST 和 Pyright 的 3.8 配置验证；未在 Win7 实机执行。
- 未修改 `greedy/scheduler.py`、`optimizer*`、evaluation、服务输入收集、前端/启动/打包、共享注册台账；现场 scheduler 文件存在其他工作并发修改，未覆盖。没有 commit，没有启动代理，没有真实 DB 访问。已有暂存项 `tests/gate_meta/test_frozen_bundle_contract.py` 未动。

# 证据与复跑

- `before.json`、`after.json`：各自三次无 profiler 耗时、完整结果、cProfile 调用数、自定义重复构建计数和两个热点模块哈希。
- `comparison.json`：仅比较已捕获证据，完整结果哈希相等；显式标记计时非独占。
- `verification.json`：实际专项命令、stdout/stderr、返回码、源码 SHA-256；本轮产品/测试文件在验证前后未变化。
- 本轮修改前的允许文件快照保存在 `/tmp/sgs-probe-reuse-before.J9DYWv`，用于分离本轮增量与原有 dirty 修复，不是持久基线。

从仓库根目录执行：

```bash
.venv/bin/python .codestable/refactors/2026-09-08-sgs-probe-reuse/verify.py
.venv/bin/python .codestable/refactors/2026-09-08-sgs-probe-reuse/summarize.py
```

主代理已于 2026-09-08 关闭全部 SubAgent、冻结源码并确认没有其他本轮性能任务后，执行下述固定资源/自动派工中型场景开关交替计时；相关源码哈希、完整结果、原始 before 输出校验均通过：

```bash
.venv/bin/python .codestable/refactors/2026-09-08-sgs-probe-reuse/paired_measure.py --exclusive-window-confirmed
```

最终 `paired.json`：每个场景每种开关 5 次，交替执行。自动派工中位数 2.418640s -> 2.212872s（8.51%）；固定资源 0.264760s -> 0.245173s（7.40%）。两种场景完整结果精确一致、测量期间源码未变化。只说明本机这两个 288 工序样本，不声称 Win7 或所有规模都有同等提升；这也不是 clean-worktree proof。

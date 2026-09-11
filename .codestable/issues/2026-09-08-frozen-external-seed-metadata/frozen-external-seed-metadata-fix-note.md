---
doc_type: issue-fix
issue: 2026-09-08-frozen-external-seed-metadata
path: fast-track
fix_date: 2026-09-08
tags: [A14, freeze, external-group, seed, backend]
---

# A14 冻结外协种子组身份传递修复

## 1. 结论与范围

- 已补齐生产 freeze -> 输入过滤 -> seed 转换 -> 算法缓存重建链路。冻结工序仍从待排列表剔除，不通过重复传全量 operations 绕过缺口。
- 保留普通算法调用、冻结窗口选择规则、执行事实优先级和完整排产结果；不修改前端、数据库 schema 或 ScheduleResult 公共字段。
- 本轮只改下列 6 个产品文件、2 个测试文件及本记录，不提交，不更新公共台账、测试登记或基线。
- 共享工作区进入时已脏，期间仍有其他任务修改。本文的本轮差异以用户提供的源码快照及实际写集为准，不把整个 git diff 算作本轮改动。

## 2. 根因与真实复现

- `core/services/scheduler/run/freeze_window.py:231` 的 `_build_seed_results` 从原始 BatchOperation 和旧排程构建种子，不含外协组身份；原始 BatchOperation 本身没有这组增强字段。
- 权威组信息由 `core/services/scheduler/run/schedule_input_builder.py:122` 的 `_build_external_merge_context` 从 PartOperations / ExternalGroups 解析，并存入 OpForScheduleAlgo。
- `core/services/scheduler/run/schedule_input_runtime_support.py:22` 在进入优化器前剔除冻结工序。旧 `rebuild_external_group_cache_from_seeds` 却只从剩余 operations 解组键；旧 `coerce_seed_result_item` 也不传递组信息。
- 真实场景：先按 separate 生成版本 1，再将对应工艺组改为 merged、开启 1 天冻结窗。组的首成员成为冻结种子，第二成员仍需排产。旧算法没有组键，第二成员重新消耗 3 天，破坏同组同起止规则。

测试数据库中的版本 2 时间对照（均为 2026 年、08:00:00）：

| 工序 | 旧代码 | 本轮修复后的约定 |
| --- | --- | --- |
| 冻结首成员 | 09-08 至 09-11，locked | 原样保留 |
| 未冻结同组成员 | 09-11 至 09-14 | 复用 09-08 至 09-11，仍为 unlocked |
| 后续独立外协工序 | 09-14 开始 | 09-11 开始，不再多占一次合并组周期 |

健康 merged 组通常全冻或全不冻，本轮不声称普通健康冻结必然出现部分组；集成测试显式通过版本间工艺变化构造真实触发面。

## 3. 实际修改

| 文件与定位 | 本轮修改 |
| --- | --- |
| `core/services/scheduler/run/schedule_input_seed_metadata.py:18` | 新增窄职责内部转换；只对冻结集合中的外协种子，按精确 op_id 匹配过滤前增强工序，再校验 batch/source/seq/merge context。merged 组保留 op_id、batch_id、ext_group_id；缺失、重复或矛盾则抛 ValidationError，不按邻居猜组。 |
| `core/services/scheduler/run/schedule_input_runtime_support.py:167` | 在执行/冻结种子合并与既有冲突检查之后、待排过滤之前附加内部组身份。不改变执行事实的时间、资源、seed_source 或 state_revision。 |
| `core/services/scheduler/run/schedule_seed_contracts.py:60` | 原有 dict 边界继续构造 ScheduleResult；存在内部元数据时验证并转为内部种子载体。坏元数据仍走 invalid_seed_results 错误和计数，不吞错。 |
| `core/algorithms/greedy/seed.py:13` | `_SeedScheduleResult` 用非 dataclass 字段的 slot 保存身份；不增加公共结果字段。`seed_external_group_keys` 校验身份后产出明确组键映射，`seed_result_for_output` 恢复普通 ScheduleResult。 |
| `core/algorithms/greedy/external_groups.py:14` | 缓存重建接受内部组键映射，不再要求冻结工序仍在 operations；与重叠输入冲突时停止。原有组块不一致的 warning/计数及降级规则不变。 |
| `core/algorithms/greedy/scheduler.py:387`、`:411` | 调度入口解析并传组键；记录输出时剥离内部载体，完整输出仍为原始 ScheduleResult 类型。 |
| `tests/algorithm/test_seed_external_group_cache_rebuild.py:217` | 扩展算法/种子边界测试：空 operations、坏元数据、身份冲突、重复工序、跨批次隔离、执行事实合并不变、重复候选复用不丢身份。保留原有普通 API 无资料时不猜归属的测试。 |
| `tests/schedule/service/test_frozen_external_seed_metadata_integration.py:84` | 新增真实数据库、真实输入采集、真实优化器和调度、真实持久化的 batch_order/sgs 集成回归；观测包装仅记录参数并调用原函数，不 stub 生产结果。 |

实现期间曾让 external_groups 直接导入 seed，导入扫描发现这会扩大已有文件环；最终改由 scheduler 传入组键映射，消除了本轮新增依赖。未修改 evaluation.py、run_context.py、dispatch_context.py、optimizer_graph_ready*.py 或 schedule_optimizer*.py。

## 4. 数据与公共边界保留证据

- 集成测试 `:98` 至 `:127`：冻结 ID 不在真实算法 operations 中；seed 与未排工序合计 3 条完整结果，失败数为 0；新版本 3 条记录完整落库。同组未冻结成员复用冻结时间，但不新增锁定。
- 集成测试 `:123`、`:124`：旧版本 Schedule 全列和旧 ScheduleHistory 全列重排前后相等。
- 集成测试 `:132`：健康全组冻结、separate、关闭冻结三种情形，工序 ID、设备、人员、开始/结束时间不变，锁定数量与 API 顶层键集符合原约定。
- 集成测试 `:151`：通过真实 `OperationExecutionFeedbackService.start_operation` 生成一条非空执行事件；重排后事件全列原样保留，执行事实种子的 seed_source/state_revision 保留，固定工序时间、设备、人员不变，4 条结果完整，旧排程全列不变。
- 算法测试及集成测试确认元数据不出现在 dataclass 字段、vars 输出、公共 API 返回中；所有最终结果的实际类型仍是 ScheduleResult。
- 公共 schema 文件 `core/algorithm_contracts/types.py` 与原始快照逐字节一致，SHA-256：`57d94f1fc97d3a70a34481236da6316e9ed6c8f92066959b5908ef73d97b3427`。
- 没有操作真实业务库。以上数据证明来自生产代码驱动的临时测试库，不冒充生产数据迁移验证。

## 5. 实际验证

运行时为仓库 `.venv/bin/python`，版本 **Python 3.8.10**。

| 验证 | 实际结果 |
| --- | --- |
| 原始快照 + 新集成测试，未叠加修复 | **2 failed, 4 passed**；batch_order/sgs 均在组缓存未重建断言失败，数据库时间也确认同组成员另起块 |
| 共享工作区 A14 算法测试 + 新集成测试 | **35 passed** |
| 原始快照只叠加本轮 6 个产品文件和 2 个测试文件后的相关回归 | **108 passed in 1.21s** |
| 共享工作区扩大到 tests/algorithm、tests/schedule/service、三份冻结窗口测试 | **953 passed, 1 failed in 16.48s**；失败为 `test_algorithms_a3_dependency_boundary.py:399` 固定模块总数断言：当次现场 802，基线 786。首次扩大回归同为 953/1，当时现场 799。不能称全绿。 |
| 8 个本轮 Python 文件的 ruff check | **All checks passed** |
| 6 个产品文件的 pyright，使用 pyrightconfig.gate.json | **0 errors, 0 warnings** |
| 本轮已跟踪文件的 git diff --check | 通过 |

隔离回归命令（cwd 为下述隔离目录；Python 使用共享仓库的绝对 `.venv/bin/python`）：

```bash
python -m pytest -q tests/algorithm/test_seed_external_group_cache_rebuild.py tests/algorithm/test_optimizer_seed_boundary_contract.py tests/algorithm/test_optimizer_seed_results_contract.py tests/algorithm/test_greedy_scheduler_algo_stats_seed_counts.py tests/schedule/service/test_frozen_external_seed_metadata_integration.py tests/schedule/service/test_schedule_input_collector_contract.py tests/schedule/service/test_schedule_input_collector_legacy_compat.py tests/schedule/service/test_scheduler_reschedule_execution_minimum_guard.py tests/calendar_maintenance/test_freeze_window_bounds.py tests/calendar_maintenance/test_freeze_window_fail_closed_contract.py tests/calendar_maintenance/test_freeze_window_disabled_reason_coverage.py
```

类型检查初次直接调用 `.venv/bin/pyright` 因旧 Documents 路径 shebang 失败，随后用 `.venv/bin/python -m pyright --project pyrightconfig.gate.json <6个产品文件>` 完成；没有修改环境或升级依赖。

## 6. 快照、导入检查与限制

- 原始源码快照：`/tmp/aps-backend-closeout.9GGk2u/starting-tree.tar.gz`，SHA-256：`b490aef78cc9913c5f31d48c4ee5de35faf7b94cf031f961259870b6636dfd23`。
- 隔离目录：`/tmp/aps-a14-snapshot-compare.xGihPy`。先仅放入新集成测试得到红灯，再机械叠加本轮明确文件得到绿灯；未覆盖共享仓库旧改动，也未把其他并行任务变化叠进隔离副本。
- 收尾逐文件 SHA-256 比对确认：共享工作区中本轮 6 个产品文件、2 个测试文件与已通过隔离回归的副本一致；公共 schema 文件也与原始快照一致。
- 隔离导入检查使用 `tools.scan_import_cycles.scan(roots, repo_root=...)` 比较圈成员及 source/target 模块边：本轮生产模块 786 -> 787；加入本轮生产/测试文件后含测试总数为 1524。生产目录环 3、含测试目录环 4、硬文件环 9、纯显式硬文件环 0、运行时文件环 13，拓扑及圈内模块边均不变，解析错误 0。
- 共享现场的两种正式 `scan_import_cycles --fail-on-new-cycle` 最终仍退出 1：差异在 process/unit_excel 文件圈、`web.bootstrap.startup_config -> config`，含测试另有 `_frozen_bundle_contract.py:198` 未解析动态导入；最终报告不再包含本轮算法新增文件圈。本轮不更新这些公共基线。
- 未运行完整 `scripts/run_quality_gate.py`：共享现场正在并行修改，扩大回归与正式导入基线检查尚有上述阻断，且本轮明确不更新公共基线。隔离副本验证也不是最终 HEAD 上的 clean-worktree proof。
- 未在 Win7 真机运行；已在 Python 3.8.10 验证，仅用标准库，不增加运行时或联网依赖。
- 本轮所有修改均未提交。公共模块计数与其他全局基线由主代理合并全部独占写集后统一核对；本记录不把这些限制写成完成或通过。

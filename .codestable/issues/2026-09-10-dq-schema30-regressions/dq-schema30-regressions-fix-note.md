---
doc_type: issue-fix
status: partial
created: 2026-09-10
summary: DQ 分阶段完成旧迁移与候选采纳断言兼容及十三文件登记；保留 DI 旧 fixture、并行 discovery 和 tracked-proof 失败
tags: [workbench, schema30, regression, registry, DQ]
---

# DQ 分阶段交接

- 仅修改 13 个测试或登记 Python 文件及本文。没有修改产品、新主线 v30 测试、固定 SQL、calibration host/live_server、DM probes 或暂存区。
- 阶段一：旧迁移继续从真实旧 fixture 升级到 CURRENT；DK 碰撞基线改用固定 v29 SQL，绝不把当前 v30 标成未修 v29。
- 阶段二：精确修复候选采纳 DashboardItems 断言，登记主线/DG/DH/DI/DL 已交接的 13 个固定文件。
- 本轮不是全绿门禁或 clean-worktree proof；未运行共享 fullgate、5000 工序容量测试，未 stage/commit。
- 运行目录：`/tmp/aps-dq-schema30-nerOOH`。XML、`test-receipts.json`、`registry-inventory.json`、`before-hashes.json`、`protected-verification.json` 均在其中，不写共享 QualityGate 证据。

# 精确写集

以下路径均相对仓库 `/Users/lurenxing/GitHub/----`，是在已有 dirty 内容上局部修改。

| 文件 | 本轮修改 |
| --- | --- |
| tests/workbench/test_execution_ledger_migration.py | 旧 v24 到 CURRENT 允许精确四张新增表，并检查来源映射 |
| tests/workbench/test_run_schema_migration.py | v25 到 CURRENT 的表集、手动逐步 DDL 对照和缺失合同集合追加 v30 |
| tests/workbench/test_plan_migration_integration.py | 旧 v23 到 CURRENT 的新增表集与 origins 检查 |
| tests/workbench/test_trial_lineage_migration.py | v26 到 CURRENT 的新增表集与 origins 检查 |
| tests/workbench/test_lineage_lookup_migration.py | v27 到 CURRENT 的新增表集与 origins 检查 |
| tests/workbench/test_calibration_dashboard_migration.py | v28 升级目标与备份名使用 CURRENT，保留原 source mapping 断言，新增 11 项检查器反例合同 |
| tests/workbench/legacy_migration_current_support.py | 新增旧回归专用检查器；不代替主线 v30 migration 测试 |
| tests/workbench/plan_identity_write_guard_support.py | frozen_v29_connection 从固定 SQL 构造，校验 SHA、真实版本、两个 guard 尚不存在；证据描述不再声称 current29 |
| tests/workbench/test_plan_identity_insert_collision.py | 改用固定旧 fixture，保留 56 项原 guard/碰撞合同，新增两个未修 v29 live/retired 对照 |
| tests/workbench/test_run_candidate_adoption_support.py | DashboardItems 复用 DJ 的精确 task 映射检查，其他原始行及类型断言保留 |
| tools/test_registry_groups_workbench.py | 固定追加 12 required + 1 supplemental；旧 group/target 顺序保留 |
| tests/gate_meta/test_workbench_registry_contract.py | 新增归属、顺序、changed-source selection 合同；原 29 项 retention 合同同时覆盖 candidate 和 trial |
| tests/gate_meta/test_long_gate_manifest.py | 明确 32 groups / 506 required targets，尾部顺序精确追加两个组 |

没有修改 `schema29_regression_support.py`、`trial_support.py` 或 `trial_adoption_support.py`。定位器未找到未索引的测试 helper 后，改用实际文件和 rg 核对调用方，没有修改产品定义或重建 SCIP。

# 兼容边界

- 全部旧 raw table、SQLite storage types、旧 DDL、identity、history、备份和重开幂等断言仍在，不删除旧表或 source mapping 断言，不跳过失败。
- `WorkbenchOutsourcingOperationOrigins` 必须精确对应仍存在的活动永久 operation_ref；batch_ref 只取该 ref 最早的 lineage `created` 记录。没有出生记录，包括只有其他事件时，必须为 NULL；不查询当前同编号 batch 猜身份。
- `WorkbenchOutsourcingReceipts`、`WorkbenchOutsourcingMembers`、`WorkbenchOutsourcingFacts` 必须为空。检查器反例覆盖缺项、额外/退休身份、猜 batch、非 created、后续 created、类型变更和三张非空事实表。
- 固定 v29 SHA-256 为 `d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648`。guard step 测试只在真实 v29 上显式安装两个 guard；新增未修对照证明递归 OFF 时人工强制重复 ref 的 REPLACE 可改变数据，外层回滚仍恢复。不是复现历史 BP 随机故障。
- 候选采纳新增 DashboardItems 必须恰好等于每个新 task 的 actual/downtime 两项、batch_ref 为 NULL。旧 item/ref/行/类型不变；拒绝丢项、重复、旧/未知 task、错误类别、非法 ref 和原 raw 数据变更。

# 新登记固定清单

| 分类 / group | tests/workbench/ 下精确文件名 |
| --- | --- |
| required / workbench_system | test_system_restore_host.py |
| required / workbench_system | test_system_restore_host_drain.py |
| required / workbench_system | test_system_restore_host_recovery.py |
| required / workbench_calibration_adoption | test_calibration_adoption_host.py |
| required / workbench_outsourcing | test_outsourcing_facts.py |
| required / workbench_outsourcing | test_outsourcing_identity.py |
| required / workbench_outsourcing | test_outsourcing_schema.py |
| required / workbench_outsourcing | test_outsourcing_atomic.py |
| required / workbench_outsourcing | test_outsourcing_api.py |
| required / workbench_zero_duration | test_zero_duration_contract.py |
| required / workbench_zero_duration | test_zero_duration_calendar.py |
| required / workbench_zero_duration | test_zero_duration_boundaries.py |
| supplemental / workbench_browser | test_process_quota_widgets.py |

全仓 required：30/494 -> 32/506；其中 workbench：22/221 -> 24/233。supplemental 仍为 15 groups，63 -> 64 targets。旧组 ID 和旧 target 序列逐项保留为前缀，discovery 函数 AST 修改前后完全相同。没有 glob target、分类降级或扩大 skip。零时长登记仅代表数学与禁用边界测试，完整零时长采纳仍禁用。

# 实测结果

项目 `.venv/bin/python` 实测为 Python 3.8.10，已安装 networkx 3.1。各次测试无 skip；不同执行批次有重叠，不将计数简单累加为唯一用例总数。

| 范围 | 结果 | XML |
| --- | --- | --- |
| 修改前 7 个旧迁移/入口文件 + DK | 44 passed / 12 failed / 53 errors | legacy-before.xml |
| 第一阶段相同八文件，含新旧基线对照 | 111 passed | legacy-after.xml |
| trial 六文件 + DL 三文件，未修改时即通过 | 126 passed | trial-before.xml |
| 修改前候选采纳五文件 | 44 passed / 8 failed，均为 DashboardItems | candidate-before.xml |
| 最终迁移/DK/候选采纳/trial raw/DL，共 18 文件 | 271 passed，33.20s | regressions-final.xml |
| 旧 run compute 五文件 | 50 passed | compute-regression.xml |
| DH 三文件 + 主线 calibration host | 30 passed | completed-host.xml |
| DG Chrome109 浏览器八场景 | 1 passed，16.38s | dg-browser.xml |
| 最终 registry + manifest + full-debt registry contract | 428 passed / 2 failed | meta-final.xml |
| DI 五文件，在当前版本复验 | 87 fixture errors，同一个旧版本前置断言 | outsourcing-current.xml |
| 额外系统 python3.8：DK、calibration migration、support 和登记合同 | 143 passed / 2 failed，系统解释器缺 networkx | python38.xml |

系统 `python3.8` 的两项失败发生在 `seed_v28 -> seed_v26 -> WorkbenchRunWorker` 构造旧 fixture 时，尚未进入迁移断言；`find_spec('networkx')` 为 None。没有安装依赖或关闭图功能来制造通过。同两项在项目 Python 3.8.10 `.venv` 的最终回归中通过。

Ruff 对 13 个本轮 Python 文件通过；Python 3.8 语法扫描 13 文件，解析拒绝 0、运行/语义风险 0。Radon 对本轮修改前后比较，新增/加重 >15 的复杂度项为 0；8 项原有超限保持原值，没有刷新基线或宣称全仓静态门禁通过。

全部命令使用显式测试路径、`-q --tb=short --show-capture=no -p no:cacheprovider`、独立 `--basetemp` 和 `--junitxml`。`test-receipts.json` 记录每个 XML 的精确文件集及全部失败 nodeid；XML 保留逐项结果。复跑使用新的临时目录，勿覆盖本目录。

# 保留的失败与下一阶段

1. DI 的 `outsourcing_support.py:76` 仍从当前 schema.sql bootstrap 后断言版本 29，并要求外协表尚不存在。本轮五文件共 87 项均在这里报错；用户交接的 87+20 历史通过数没有冒充本轮 v30 通过。这个 DI support 不在授权写集，未修改。需由 DI/主线将独立 v29 extension 基线固定到真实 v29，或单独验证 CURRENT；不能把完整 v30 改版本标签叫 v29。
2. discovery 失败按要求保留。2026-09-10 10:51:41 +08:00 的最新库存为 8 个未登记测试：`test_dashboard_external_identity.py`、`test_dashboard_external_reads.py`、`test_dashboard_external_snapshot.py`、`test_outsourcing_identity_migration.py`、`test_outsourcing_targets_labels.py`、`test_outsourcing_widgets.py`、`test_system_restore_entrypoint.py`、`test_system_restore_entrypoint_recovery.py`。最终 meta 执行时为 7 个，其后新增 labels 文件；不倒改历史执行结果。等待主线/DN/DO/DP 完成后再登记。
3. tracked-proof 原断言失败在 `tests/gate_meta/test_full_test_debt_registry_contract.py:1264`，首先命中未跟踪的 `tests/gate_meta/test_workbench_registry_contract.py`。10:51 库存 required 未 tracked 共 233 个；未放宽断言，也未 stage 任何文件。
4. 同根因 8 项候选采纳旧失败已在本轮复现并精准修复；5000 工序容量用例也调用同一 support，但本轮没有执行，不声称其容量证明通过。

# 文件保留核验

- HEAD 为 `de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`。所有本轮内容未提交；仓库原本即有大量 staged/unstaged/untracked 内容。
- 40 个记录保护文件哈希前后相同，包括 v1..29 migrations、固定 v24..29 SQL、schema.sql、指定 calibration host/support、DM 的 test_process_quota_protection.py 和 frozen_bundle。
- 整个 staged diff SHA-256 前后均为 `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`。
- frozen_bundle 保持 staged 200+/0-，文件 SHA-256 为 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`。
- 本轮 13 个 Python 文件最终哈希在 `protected-verification.json`；修改前原稿在运行目录的 `before/`。未改产品数据库，测试全部使用临时 SQLite/本地临时 host，无共享整库 fullgate、全局前端构建或 Git 暂存动作。

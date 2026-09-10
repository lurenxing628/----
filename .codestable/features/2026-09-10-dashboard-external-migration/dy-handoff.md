---
doc_type: feature-implementation
feature: dashboard-external-schema31
status: implemented
summary: DY schema31 接入、固定登记和非空真实迁移证据；保留并行 DX 与 untracked gate 边界。
tags: [migration, dashboard, outsourcing, retention]
---

# DY 交接记录

## 结论与范围

- `CURRENT_SCHEMA_VERSION=31`；`MIGRATIONS[31]` 注册 `v31.run`，事务内调用 DT `install(conn)`。
- DT 实数为 3 张表、10 个触发器，共 13 个具名对象。`schema.sql` 追加同一 helper 生成的 DDL；旧 schema30 全字节仍是新文件前缀。
- 固定30非空库仅为已有永久 `outsourcing_ref` 生成独立 item 映射，不生成处置 states/history，不改既有外协事实、旧四类 Dashboard 或生产表。
- 新外协登记只生成自己的映射；原 item_ref 不变。已有显式 DT helper 与处置历史的30库也可真实升级，原 rows/DDL 全保留。
- 新增 DT contract 在 `query_only` 下只读；缺失13对象中任一个、错误 DDL、残缺旧扩展均拒绝，不偷安装或猜测补映射。
- 全局 current 检查仍含历史 `OperationExecutionEvents` SAVEPOINT 写探针；不宣称整个 current 检查能在 `query_only` 下成功，也没有修改该历史逻辑。
- 未触碰生产或旧 preview，未访问端口52392/58448；后续实际升31仍由主代理负责。

## 本轮源码文件

- 新增 `core/infrastructure/migrations/v31.py`；修改 `migrations/__init__.py`、`migration_state.py`、`schema.sql`。
- 新增 `tests/workbench/test_dashboard_external_migration.py` 与 `dashboard_external_migration_support.py`。
- 精准兼容7个旧迁移测试：`test_outsourcing_identity_migration.py`、`test_execution_ledger_migration.py`、`test_run_schema_migration.py`、`test_plan_migration_integration.py`、`test_trial_lineage_migration.py`、`test_lineage_lookup_migration.py`、`test_calibration_dashboard_migration.py`。固定起点、旧 DDL、typed rows、备份与重启断言均保留，追加31映射严格检查；历史 helper 不改。
- DT `test_dashboard_external_handling_schema.py` 的30场景改用固定30；DO `test_dashboard_external_reads.py` 同时覆盖固定30无 helper 和 current31有 helper。未删除来源未知、风险或保留断言。
- 固定登记修改 `tools/test_registry_groups_workbench.py`、`tests/gate_meta/test_workbench_registry_contract.py`、`tests/gate_meta/test_long_gate_manifest.py`。
- 没有修改 UI/main/build、DP 系统入口、主 `run_live_server`、calibration host 或 v1..30 迁移。

## 固定登记

- 原32个 required groups 不变，原 targets 顺序保留为前缀；DT5文件 + DP3文件 + DY1文件：required 511 -> 520，workbench required 238 -> 247。
- DP实际文件为 `test_system_restore_entrypoint.py`、`test_system_restore_entrypoint_fail_closed.py`、`test_system_restore_entrypoint_recovery.py`；support只作为影响范围，不当作测试目标。
- supplemental 65 targets 不变；DX `test_dashboard_external_handling_widgets.py` 尚未交接，未抢登记、未豁免 discovery。
- coverage 的 missing/duplicates/unknown 均为空；required registry hash `ae7b1a0b43b751d3e42c2bb95c1f8a0b957322a8e2389ba03fd58963b4776d4b`。

## 验证

- 全部使用仓库 `.venv/bin/python`，实际版本 Python 3.8.10；没有新增依赖。
- 9个主迁移文件合跑：106 passed，其中 DY 36；见 `dy-migration-tests.xml`。
- DT5 + DO3文件：84 passed；见 `dt-do-tests.xml`。
- `tests/migration_db`：135 passed；固定 `workbench_system` required 11文件：128 passed。
- 两个 registry meta：427 passed / 1 failed；唯一失败为 DX未交接 browser 的 discovery，原检查保留。见 `registry-tests.xml`。
- 本轮17个Python文件 Ruff通过；tracked修改 `git diff --check` 通过。
- 真实故障覆盖 step / preflight probe / 备份后的 actual migration。actual路径明确是目标临时库，失败后旧数据、DDL、版本与备份逐项相等。
- 完整 gate 未运行：只读调用实际 `_assert_guard_tests_ready()` 已因未跟踪 required 文件拒绝；未启动会清理旧门禁产物的完整 gate，更未 stage 伪造 tracked proof。
- 本次为 dirty/untracked 工作区局部验证，不是 clean-worktree proof；Win7实机未运行。

## 可审计证据

- `evidence/typed-raw-ddl.json` 保存迁移前、真实备份、迁移后逐表所有值及 SQL storage classes；bytes/float额外保留hex表达；三份完整 DDL 一并保留。
- 独立夹具包含74个旧表、157条旧行；升级后77表。真实备份与迁移前raw/DDL完全相等；新增 Items=3、States=0、History=0。
- 原有3笔外协登记、4条事实、2条generic处置历史、真实报工、执行事件、排期、候选、场景、refs和来源gap均进入保留证明；重启不变且不再生成备份。
- 临时迁移后库：`evidence/fixture-v31.db`，SHA-256 `03ea6afcd652da698ed31ebe59694c5707b14a2e0276bb5454cc448eaa53358c`。
- 真实30备份：`evidence/backups/aps_backup_20260910_113718_before_migrate_v30_to_v31.db`，SHA-256 `82e454237af994a3230c0dddfff641dc72dcd7812b78be73fa4ffc4fba13c59b`。
- 复现证据命令：`.venv/bin/python -m tests.workbench.dashboard_external_migration_support <全新不存在的目录>`；只创建独立测试夹具，不操作已有数据库。

## 冻结与未提交边界

- 开始前立即核对：`schema-v30.sql` 和当时 `schema.sql` SHA-256均为 `16460ac6d0f95373eca466b101cfcc46097187760e2438fb3a8c292c28761b2e`；该fixture已由新测试和registry meta固定SHA，未修改。
- 当前 `schema.sql` SHA-256：`b939a2d6516925863e6f7f0fb3db32ea83a94e4204a8df8c1f6574953bb17b47`。
- 起止核对43个受保护文件：v1..30、schema-v24..30、DT helper及5个历史migration helper，全部字节不变。
- staged diff SHA-256起止均为 `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`；`test_frozen_bundle_contract.py`仍为staged 200+/0-。
- 本轮没有 stage/commit；仓库原有大量未暂存与未跟踪内容全部保留。主代理后续实际迁移和 DX browser登记尚需分别完成。

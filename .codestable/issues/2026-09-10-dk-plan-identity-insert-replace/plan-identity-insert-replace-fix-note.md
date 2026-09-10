---
doc_type: issue-fix-note
status: integration-pending
owner: DK
date: 2026-09-10
---

# DK 计划身份 INSERT OR REPLACE 定点修复

## 结论与边界

- 修复 helper 和局部验证已完成；新 migration / 新版本门禁注册由主代理接入。本轮没有注册，也没有把未升级 current29 宣称为已修复。
- 原样运行专属测试：2 failed / 2 passed；失败都是 forced `INSERT OR REPLACE` 未抛出 `sqlite3.IntegrityError`。原始输出保存在 `evidence/WorkbenchPlanIdentity/2026-09-10-dk/baseline-red.log`。
- 只证实强制重复 ref 下的覆盖行为；没有复现此前随机 ref 故障，不宣称随机根因已证实。旧 BP 证据包未在本轮读取或改写。

## 根因与修复

- 实际文件名为 `core/infrastructure/workbench_plan_identity_schema.py`。`_source_triggers`（124 行）在源表 INSERT 后先退休冲突绑定，再由 `_insert`（105 行）插入新 ref。任务 ref 由 `_task_insert`（171 行）生成。
- 外层 `INSERT OR REPLACE` 的冲突处理传入这些触发器写入；生成 ref 与已有 ref 相同时，原身份行被覆盖，而非按普通 INSERT 抛错。真实 `get_connection` / current29 / `recursive_triggers=0` 已保存覆盖前后所有表数据。
- `data/repositories/workbench_plan_identity_repo.py:84` 起是 SELECT-only 校验与解析，不是原子写入边界；改读层不能撤回已提交的覆盖，所以未修改该文件。
- 新增 `core/infrastructure/workbench_plan_identity_write_guard.py:23`：仅向 `WorkbenchPlanSourceRefs` 和 `WorkbenchTaskRefs` 追加两个 BEFORE INSERT 触发器，按 ref 主键查重并显式 `RAISE(ABORT, ...)`。检查包含退休 ref，不再抽签、不重试、不猜身份，也不依赖 DELETE 触发器是否递归执行。
- ABORT 回滚整条失败 SQL；异常继续传播，由既有 `TransactionManager` 回滚所属业务事务。未吞错，也未把 ABORT 冒充为独立回滚所有先前 SQL。
- helper 的 `install()`（45 行）保持事务边界，拒绝部分/错误 schema 和缺失身份；只追加触发器，不改表、不回填 ref、不改时钟、不更新 SchemaVersion。

## 修改清单

- 新增产品 helper：`core/infrastructure/workbench_plan_identity_write_guard.py`。
- 修改专属测试：`tests/workbench/test_plan_identity_insert_collision.py`。
- 新增专属 support：`tests/workbench/plan_identity_write_guard_support.py`。
- 新增本记录及独立目录 `evidence/WorkbenchPlanIdentity/2026-09-10-dk/` 内证据。
- 原身份 schema/repository、旧 probe support、`schema.sql`、v24..29 migrations 和 schema-v24..28 fixtures 的 15 个 SHA-256 均与修改前一致。没有修改 system/outsource/processquota/registry、schema 注册或旧 preview；没有 stage/commit。

## 实测证据

- 运行时：Python 3.8.10，SQLite 3.35.5，macOS；没有在真实 Win7 机器运行，但未新增依赖或使用高于 Python 3.8 的语法/API。
- 专属测试显式由 `ensure_schema` 创建 current29 文件库，再经真实 `get_connection` 连接并应用独立 helper（测试 41 行）；不是修改共享 schema fixture。历史 backfill 子例仍使用固定 v24 DDL。
- 专属 56 项：源 ref live/retired、递归 OFF/ON、INSERT/REPLACE、UPDATE/REPLACE、单条多行回滚、完整业务事务回滚、任务 ref 嵌套冲突、七类同编号替换与旧身份/旧任务保留、升级幂等/重开/数据和存储类型不变、损坏拒绝、DDL 失败回滚、调用方回滚升级。
- 直接影响面另 228 项：`test_plan_persistent_identity.py`、`test_plan_migration_integration.py`、`test_plan_query_api.py`、`test_plan_catalog.py`、`test_report_execution_ledger_identity.py`。这些使用原有 fixture，证明旧身份契约和直接消费面没有回归，不冒充已注册新版本的全链路证明。
- 合并运行 **284 passed in 35.21s**；完整结果：`evidence/WorkbenchPlanIdentity/2026-09-10-dk/local-regression.xml`。3 个改动 Python 文件的 Ruff 检查通过。
- `rawfacts-final/manifest.json` 保存运行时、15 个受保护文件的前后哈希，以及 8 组逐表原始值/逐行 SQLite 存储类型/DDL/抽签与插入尝试/异常/回滚状态；16 个 rawfacts 与数据库 payload 哈希已逐个复核。初次 `rawfacts/` 也保留，未覆盖。
- current29 未升级且递归 OFF 的两例仍记录为覆盖；递归 ON 的未升级样本被既有 lineage append-only 约束阻断，不能误报成当前身份写保护已生效。升级后的四例统一在身份写入口显式失败。
- 当前为多人并发的大量 dirty worktree。本轮按定点范围没有执行整仓 `scripts/run_quality_gate.py`，不提供 clean-worktree proof，不代替主代理的最终集成门禁。

## 主代理接入要求

1. 分配新的追加 schema 版本，不修改 v24..29 历史 migration 或固定 fixtures。新 migration 在现有迁移备份/事务框架内调用 `install_plan_identity_write_guards(conn)`；成功后由既有 runner 推进版本。
2. 新版本的契约检查要求 `plan_identity_write_guard_contract_issues(conn)` 无问题；旧版本仍按旧契约识别并进入升级。不要在 GET/repository/get_connection 中静默安装或修复触发器。
3. 新版本 fresh bootstrap 追加 `plan_identity_write_guard_objects()` 返回的两个对象，并同步新版本契约；不要重写历史 DDL。helper 没有自带版本号，避免撞其他代理的升级注册。
4. 接线后由主代理补注册测试、真实 v29 到新版本升级/重启/fresh 全链路与最终门禁。本轮专属测试明确固定 current29 起点，主代理提升 CURRENT_SCHEMA_VERSION 时需同时维护测试起点策略，不能删除旧版证据掩盖基线。

# Schema v32 集成记录

- 日期：2026-09-15。
- 范围：外协来源确认与报工撤销两个独立扩展的统一迁移；未操作真实数据库、未启动应用、未提交代码。
- 状态：产品迁移源已定稿；专项验证通过。工作区包含既有改动，不属于 clean-worktree proof。

## 实现

`core/infrastructure/migrations/v32.py` 在同一个可回滚事务内依次安装来源确认和报工撤销扩展；迁移注册表与 `CURRENT_SCHEMA_VERSION` 升为 32，`migration_state.py` 纳入两个结构合同。`schema.sql` 展开与安装器相同的 12 个对象：2 张新表、10 个触发器。

迁移只添加空表与触发器，不推断旧来源、不生成撤销事实、不重写旧操作出生记录、不修改旧报工或命令回执。原 v25 报工结构与 v30 外协结构的安装器合同保持原有对象集合。新库从完整 `schema.sql` 初始化，无需跑旧版迁移。

## 历史证据

- 新增冻结 `tests/workbench/fixtures/schema-v31.sql`，SHA-256：`b939a2d6516925863e6f7f0fb3db32ea83a94e4204a8df8c1f6574953bb17b47`。
- 既有 `schema-v25.sql` 至 `schema-v30.sql` 原文件未修改。
- 历史 seed 过去调用当前业务服务，服务新增严格 v32 合同后不能再用它造旧数据库。改为从隔离的 `7034b873` 执行原 helper 生成固定业务 SQL，加载时保持原版 DDL；六版全部字段值、SQLite 类型、DDL 与原生成库逐项相同，FK 检查通过。来源及 schema/data 哈希见 `tests/workbench/frozen_business_seed_support.py` 和 `fixtures/business-seed-v*.sql`。
- 普通当前运行 fixture 显式安装新撤销扩展；它们与真正冻结的历史迁移 fixture 分开，不用当前版本常量伪造旧 schema。

## 验证

使用项目 `.venv/bin/python`（Python 3.8）对以下 9 个迁移文件执行专项测试：

- `test_execution_ledger_migration.py`
- `test_run_schema_migration.py`
- `test_plan_migration_integration.py`
- `test_trial_lineage_migration.py`
- `test_lineage_lookup_migration.py`
- `test_calibration_dashboard_migration.py`
- `test_outsourcing_identity_migration.py`
- `test_dashboard_external_migration.py`
- `test_manual_remediation_schema_migration.py`

结果：**126 passed in 35.86s**。新增专项覆盖 v31→v32 全部旧表逐字段值和类型保留、旧 DDL 原样保留、迁移前备份完整一致、重复启动无变化、两扩展间失败回滚、probe/actual 两阶段注入失败、部分安装拒绝、缺失及错误触发器拒绝、全新与升级结构一致。

实际日志：`/tmp/aps-schema32-migration.log`。`git diff --check` 通过。

## 测试登记与边界

本轮 13 个新/漏登记测试文件已按既有 owner 登记，浏览器测试保持显式执行分类。纯静态清单核对证明每项文件存在且只有一个 owner。新增 fixture/support 是依赖，不登记为 pytest target。

用户明确禁止全门禁后，仅继续上述迁移专项；没有运行 `run_quality_gate` 任意模式或整仓测试。此前正在执行的注册合同组已中断（当时 123 passed，1 deselected），不声称完整注册组通过。已有算法注册表比旧审查清单多 20 个工作区既有测试，本轮未扩修这项历史基线；主代理已知悉。

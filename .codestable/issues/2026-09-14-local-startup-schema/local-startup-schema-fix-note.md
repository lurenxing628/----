---
doc_type: issue-fix-note
status: fixed
date: 2026-09-14
title: 本地旧库执行事件结构修复并启动
---

## 根因与范围

- 用户授权修复本地数据库并在内置浏览器启动；本轮未修改产品代码。
- 原库 `db/aps.db` 的 SchemaVersion 实际为 19（更新时间 2026-06-03），并非 31。启动报错中的 31 来自迁移预检副本完成 v20–v31 后的最终契约校验，失败后原库保持 19。
- 原库 OperationExecutionEvents 缺少事件时间、事件类型与状态配对 CHECK、两个复合外键及父表身份唯一索引；该表原有记录数为 0。
- 当前约束来自 `core/infrastructure/migrations/v15.py:11`，由 v18/v19 继承；已有 v19 库的后续迁移没有重建这张旧表。v19 重建入口为 `core/infrastructure/migrations/v19.py:36`，最终结构检查位于 `core/infrastructure/migration_state.py:99`。

## 实际修复

1. 使用 SQLite Backup API 保存原库和演练副本，目录 `backups/startup_schema_repair_20260914_130553/`，原始备份为 `aps_before.db`。
2. 在演练副本中复用现行 `v19.run()` 重建执行事件表及索引，不手改版本号；调用 `ensure_schema()` 执行正式 v20–v31 迁移。
3. 演练验证成功后，原库使用 BEGIN IMMEDIATE 获取写锁，核对 sqlite_master 和全部原表数据仍与备份一致，才执行同样修复及正式迁移。
4. 原库升级为 31，数据保留证据和备份 SHA-256 保存在上述目录的 `verification.json`。

## 验证

- 演练副本、原库均通过 `PRAGMA integrity_check`、`PRAGMA foreign_key_check` 和 `current_schema_contract_issues()`，结构问题为 0。
- 逐表读取原字段、排序并比较数据及 SHA-256：32 张原有业务表、13,735 条原记录完全一致；SchemaVersion 按正式迁移更新。比对在启动服务前完成，之后正常使用可新增运行记录。
- `.venv/bin/python -m pytest -q tests/operation_execution/test_operation_execution_migration_v19_contract.py tests/migration_db/test_migration_schema_contract.py`：34 passed in 5.18s。
- 最终以 `APS_ENV=production .venv/bin/python app.py` 启动；运行时契约地址为 `http://127.0.0.1:5000`，内置浏览器实际显示“值班台 · APS 智能排产”、当前正式 v14 及风险清单。
- 开发模式首次启动时，重载子进程写入的端口 5705 与实际监听 5000 不一致；已停止该进程，使用现有 production 配置启动，最终地址一致。该开发重载问题未在本轮修改产品代码。
- 本轮为本地数据库修复，未执行整仓质量门禁，不声称 clean-worktree proof。

## 保留内容

- 本记录、数据库备份及验证文件未提交；`db/aps.db.lock` 为运行时锁文件，服务运行期间保留。
- 初始未跟踪文件 `logs/aps_launch_error.txt` 由成功启动的现有清理逻辑移除。
- 未执行 git commit、push 或无关代码修改。

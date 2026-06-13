---
doc_type: issue-fix
issue: 2026-06-10-backup-failure-messages
status: fixed
path: fast-track
fix_date: 2026-06-10
tags: [backup, restore, route-error-message]
---

# 备份链路失败提示修复记录

## 1. 问题描述

2026-06-10 深审报告指出两条备份链路问题：

- P1-2：手动备份时，`BackupManager.backup()` 的完整性检查失败会抛 `RuntimeError`，页面入口如果没有转成中文提示，就会落到 500。
- P2-1：恢复前自动备份失败时，旧语义容易和真正恢复失败混在一起，用户看不出数据库还没有被恢复、原数据库没有被改动。

## 2. 根因

- 手动备份入口需要把 `RuntimeError` 明确转成可读 `flash`，不能让它继续冒泡到全局 500。
- 恢复流程里 `self.backup(suffix="before_restore")` 发生异常时，数据库还没有进入复制恢复阶段，应返回专门错误码和专门文案。

## 3. 修复方案

- 手动备份失败提示统一改成“备份完整性检查失败或备份写入异常，已放弃本次备份以保护数据，请查看日志。”
- 恢复前备份失败返回 `before_restore_backup_failed`，提示用户“恢复前备份创建或完整性检查失败，数据库未恢复，原数据库没有被修改。”
- 路由级测试覆盖手动备份和恢复两个入口，确保不会出现 500 或通用 `restore_failed` 文案。

## 4. 改动文件清单

- `web/routes/system_backup.py`
- `core/infrastructure/backup.py`
- `tests/app_runtime/test_backup_create_integrity_error_message.py`
- `tests/app_runtime/test_restore_success_condition.py`
- `tests/migration_db/test_restore_pre_snapshot_failure_contract.py`

## 5. 验证结果

- `.venv/bin/python -m pytest tests/app_runtime/test_backup_create_integrity_error_message.py tests/app_runtime/test_restore_success_condition.py tests/migration_db/test_restore_pre_snapshot_failure_contract.py tests/migration_db/test_backup_integrity_check_contract.py`：9 passed。
- `.venv/bin/python -m ruff check core/infrastructure/backup.py web/routes/system_backup.py tests/app_runtime/test_backup_create_integrity_error_message.py tests/app_runtime/test_restore_success_condition.py tests/migration_db/test_restore_pre_snapshot_failure_contract.py`：All checks passed。
- `.venv/bin/python scripts/run_quality_gate.py --fast-precheck`：passed。该命令只是快速静态预检，不是完整质量门禁证明。
- `python .codestable/tools/validate-yaml.py --file .codestable/issues/2026-06-10-backup-failure-messages/backup-failure-messages-fix-note.md --require doc_type --require status`：1 passed；当前环境缺 PyYAML，工具使用内置 fallback parser。

## 6. 遗留事项

- 未跑完整 clean-worktree 质量门禁，因为当前工作区包含本次改动以及先前已存在的未提交文件。

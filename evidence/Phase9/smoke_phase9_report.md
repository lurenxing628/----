# Phase9（系统管理：备份/日志/历史）冒烟测试报告

- 测试时间：2026-01-24 02:00:56
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录：`D:\Github\APS Test`

## 0. 测试环境（隔离目录）
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase9_cy4zw_jp`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase9_cy4zw_jp\aps_phase9_test.db`
- 备份目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase9_cy4zw_jp\backups`

## 1. 页面可访问（系统管理三页）
- GET /system/backup：200
- GET /system/logs：200
- GET /system/history：200

## 2. 备份文件：创建/删除/批量删除/恢复闭环（含 before_restore）
- POST /system/backup/create (follow redirects)：200
- 最新备份文件：aps_backup_20260124_020058_manual.db
- 备份操作日志：通过（log_id=1）
- POST /system/backup/create#2 (follow redirects)：200
- POST /system/backup/delete (follow redirects)：200
- 备份删除：通过（aps_backup_20260124_020100_manual.db 已删除）
- POST /system/backup/create#3 (follow redirects)：200
- POST /system/backup/delete-batch (follow redirects)：200
- 备份批量删除：通过（aps_backup_20260124_020101_manual.db 已删除）
- 已删除 OP_BAK（用于验证恢复）
- POST /system/backup/restore (follow redirects)：200
- 恢复校验：通过（OP_BAK 已回归）
- before_restore 备份：通过（1 个）
- 恢复操作日志：通过（log_id=1）

## 3. 清理过期备份（cleanup）
- POST /system/backup/cleanup (follow redirects)：200
- 清理过期备份：通过（旧文件已删除）
- 清理操作日志：通过（log_id=2）

## 4. 日志筛选（按时间）与排产历史展示 + 日志删除/批量删除
- OperationLogs 按时间过滤：通过（start_time 生效）
- GET /system/history?version=1：200
- POST /system/logs/delete (follow redirects)：200
- 日志删除：通过（id=3 已删除）
- POST /system/logs/delete-batch (follow redirects)：200
- 日志批量删除：通过（ids=[4, 2] 已删除）

## 5. 自动任务（按请求触发）：自动备份 / 自动清理备份 / 自动清理日志
- POST /system/backup/settings：302
- GET /system/backup (trigger maintenance)：200
- 自动备份：通过（1 个，示例：aps_backup_20260124_020112_auto.db）
- 自动清理备份：通过（过期文件已删除）
- POST /system/logs/settings：302
- GET /system/logs (trigger maintenance)：200
- 自动清理日志：通过（2000 年旧日志剩余 0 条 < 20）

## 结论
- 通过：Phase9（系统管理：备份/日志/历史）冒烟测试通过。
- 总耗时：27629 ms

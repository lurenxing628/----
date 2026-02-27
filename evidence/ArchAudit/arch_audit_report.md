# APS 架构合规审计报告

- 生成时间：2026-02-27 12:25:56
- 仓库根目录：`D:\Github\APS Test`

## 总结
- 总问题数：5
  - 分层违反：1
  - 文件超限：4
  - 禁止模式：0
  - 命名问题：0
- 结论：FAIL（存在违反项）

## 分层违反
- [LAYER] web/routes/excel_demo.py:24 - route 直接执行 conn.execute

## 文件超限
- [SIZE] core/services/scheduler/batch_service.py - 686 行（超过 500 行限制）
- [SIZE] core/services/scheduler/config_service.py - 701 行（超过 500 行限制）
- [SIZE] core/services/scheduler/schedule_optimizer.py - 508 行（超过 500 行限制）
- [SIZE] core/services/scheduler/schedule_service.py - 534 行（超过 500 行限制）

## 禁止模式
- 无

## 命名问题
- 无


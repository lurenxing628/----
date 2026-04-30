---
doc_type: refactor-scan
refactor: 2026-04-30-techdebt-phase4-ledger-complexity
status: confirmed
scope: 阶段 4 处理技术债台账中 open 的超长文件和高复杂度函数。
summary: 以行为不变为底线，把 scheduler summary、配置字段、基础设施、工艺/报表/路由拆成 facade 加小模块，并用台账和门禁证明数量下降。
tags: [techdebt, oversize, complexity, quality-gate]
---

# techdebt phase4 ledger complexity scan

## 扫描范围

- 台账 active oversize：8 个。
- 台账 active complexity：29 个。
- 本阶段优先处理排产 summary、配置字段、数据库/迁移/事务/备份、工艺路线、单元 Excel、报表计算和相关路由。

## 选中清单

- ✓ S1：拆 `core/services/scheduler/summary/schedule_summary.py` 的摘要大小保护、运行状态和告警状态。
- ✓ S2：拆 `core/services/scheduler/config/config_field_spec.py` 的字段校验和兼容读取。
- ✓ S3：拆 `core/infrastructure/transaction.py`、`backup.py`、`migrations/v4.py`、`database.py` 的高复杂度入口。
- ✓ S4：拆 `core/services/report/calculations.py`、`unit_excel/template_builder.py`、`route_parser.py`、`part_service.py`。
- ✓ S5：拆被本阶段服务变动牵到的具体路由：`personnel_pages.py`、`scheduler_excel_calendar.py`、`system_backup.py`。

## 明确不做

- 不处理 full-test-debt，只要求不新增。
- 不扩大 silent fallback 治理范围。
- 不做全路由整理、全 UI 文案整理、历史文档重写。
- 不改数据库 schema、迁移版本号、排产算法语义、用户可见文案。

## 风险

- scheduler summary 的 `__all__` 和旧兼容导入路径不能变。
- 配置字段默认值、字段 key、选择项、隐藏字段不能漂移。
- 数据库迁移失败回滚、备份、维护窗口和事务语义必须先用测试兜住再拆。
- route 只能变薄，不能顺手改变请求、flash、模板上下文和返回码。

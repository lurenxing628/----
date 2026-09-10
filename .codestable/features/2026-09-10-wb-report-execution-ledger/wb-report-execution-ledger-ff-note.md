---
doc_type: feature-ff-note
feature: wb-report-execution-ledger
date: 2026-09-10
requirement: workbench-foundation-read-loop
tags: [reports, execution-ledger, sqlite, snapshot]
---

## 做了什么
AR 将报表中心五专题与正式执行复盘接入 AJ 的唯一 `ExecutionLedgerService.workspace_projection(plan_ref, tasks)`；只使用该投影的完成、数量、首开工、确认完工和缺口。当前正式采用计划、计划完工日期包含边界、10 分钟容差和全筛选范围导出的定义不变。旧 `events`/`event_count` 仍只计旧事件，另加 `production_reports`/`production_report_count` 与全部记录数；工时未知不补零，已知小计不冒充完整总量。

## 改动位置
- `core/services/workbench/report_facts.py:73`：`read(scope, as_of=None)` 单次批量读取，完整 ledger snapshot facts 入指纹，SQLite DATE/BLOB 私有事实按类型序列化。
- `core/services/workbench/report_queries.py:22`、`report_columns.py:1`：同 cohort 的明细、资源汇总、可见缺口与新增导出列；按 BC 接口核对补齐总记录/旧事件/逐次报工三组计数，实际记录时间、工时未知记录的标签覆盖两类事实。
- `core/services/workbench/review_projection.py:19`、`review_records.py:23`：直接消费唯一状态；新报工及全部修订、旧事实和原计划/任务/资源引用保留，不按重号改指对象。
- `core/services/workbench/review_values.py:21`、`review_summary.py:28`：已知/未知小时与旧事件/逐次报工计数分开；趋势使用日期计数累加，避免逐日期重扫全部工序。
- `core/services/workbench/review_legacy.py:12`、`review_export_labels.py:15`：只从公开旧事实按原任务分组展示暂停与异常，不判完成、不推算加工小时。
- `core/services/workbench/report_exports.py:42`：CSV/XLSX 导出完整范围与结构化修订；XLSX 单元格超过 32767 字符显式拒绝并指向 CSV，不截断。
- `web/routes/workbench/reports.py:26`、`reports_catalog.py:21`：先捕获或恢复工厂墙钟，再传入 reader；使用既有范围 token 格式和校验，分页/详情/导出冻结同一时点。
- `tests/workbench/report_execution_ledger_support.py:58`：新增完整 `app.create_app` 临时库夹具，使用生产 `get_connection`，断言 DATE 转换；不改任何既有 fixture。
- `tests/workbench/test_report_execution_ledger_{read,export,identity,scale,boundaries}.py`：新增 22 项合同测试。
- `tests/workbench/test_report_boundaries.py:107`：经主线程授权，仅把公式备注改为在合法新事件 INSERT 时写入，并断言该条 CSV 中和；不修改不可变归档。

## 验证与保留证据
`.venv/bin/python` 为 Python 3.8.10。既有 `test_report_{read,export,boundaries}.py`、`test_migration_pages_fixture.py` 加上述五个专属测试文件，补齐 BC 导出列后的最终一轮：**73 passed in 80.50s**。覆盖真实 HTTP 报工/补录/更正读回、null/0/部分与完整完成、外协、原计划引用跨重排/完整 app 重启、工序/资源重号替换、DATE 转换、全范围 CSV/XLSX、冻结事实有效时点、WAL 并发提交、缺失台账显式拒绝。

10000 工序：单次 `project_loaded`，357 次 SELECT，其中 34 批报工查询，无 N+1；一次本机完整 API 请求约 5.8 秒。修改的 12 个产品文件均少于 500 行、radon 复杂度不超过 15，Python 3.8 AST 检查通过。GET 在真实 `query_only` 连接运行，并核对全库转储或原事实行不变。

AJ 自有 `legacy_source_hash`/`legacy_source_changed` 已协作接入，AR 未改 ledger：原表 UPDATE/DELETE 后旧快照失效，刷新后缺口可见；归档、原完成和数量保留，源已漂移后再次改变仍使新快照失效。公式测试原有中和要求保留。旧 `created_at` 保留 `legacy_storage` 及 AJ 的默认来源声明，不猜测 UTC/本地转换。

## 限制
这是并行 dirty-worktree 定向验证，不是 clean-worktree proof；未运行整仓门禁、未 commit、未 build、未访问生产 DB，也没有 Win7 实机验证。上限仍为 10000 工序、20000 个旧事实与报工修订合计，并服从 AJ 完整投影大小及既有导出上限。超过 XLSX 单元格上限的完整修订历史使用 CSV。前端显示调整由 BC 独立负责，AR 已交付稳定 DTO 与真实临时 app 夹具。

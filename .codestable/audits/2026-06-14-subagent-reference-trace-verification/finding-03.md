---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "performance-03"
nature: performance
severity: P2
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 03：批次/物料/人员列表先全量装配后分页

## 速答

多个列表页先从数据库拉一整批对象，在 Python 里过滤、拼展示行，最后才 `paginate_rows()` 切当前页。

## 关键证据

- `web/routes/material.py:106`：批次物料页直接 `batch_svc.list()` 拉全部批次，用于下拉和齐套汇总；该页没有分页。
- `web/routes/domains/scheduler/scheduler_batches.py:73`、`:81`：排产批次页先 `batch_svc.list()` 和 `build_batch_rows()`，再内存分页。
- `web/routes/domains/scheduler/scheduler_batches.py:140-154`：批次管理页先按 `status` 拉取，再按 `only_ready` 循环过滤，最后分页。
- `web/routes/personnel_pages.py:31-74`：人员页拉人员、全部设备、全部人员设备关联，按人员分组拼展示行后分页。
- `data/repositories/batch_repo.py:47-62`：`BatchRepository.list()` 没有 `LIMIT/OFFSET`，最后 `fetchall`。

## 影响

当前本地库批次数较少时不明显，但数据逐年积累后，页面只显示 100 行，后台仍可能先读取和装配全部候选行。

## 修复方向

给 service/repo 增加分页和 `ready_status` 等筛选参数；页面需要全局汇总时单独走轻量统计 SQL，不复用全量列表。

## 建议动作

`cs-refactor`，因为主要是查询面和列表装配方式优化，行为目标不变。


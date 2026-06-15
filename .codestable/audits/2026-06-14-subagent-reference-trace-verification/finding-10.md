---
doc_type: audit-finding
audit: 2026-06-14-subagent-reference-trace-verification
finding_id: "bug-10"
nature: bug
severity: P2
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 10：批次/人员动作回跳丢查询上下文

## 速答

批次批量动作、新增失败、人员删除/批量动作固定跳回列表页，没带原来的筛选和页码。

## 关键证据

- `web/routes/domains/scheduler/scheduler_batches.py:214`：批次新增失败回 `batches_manage_page`，没带原查询。
- `web/routes/domains/scheduler/scheduler_batches.py:240`、`:264`、`:346`、`:354`、`:363`、`:378`：批量删除/复制/修改多处固定回 `batches_manage_page`。
- `web/routes/domains/scheduler/scheduler_batches.py:132-137`：批次管理页缺 `status` 参数时默认 `pending`，所以回跳后常回到“待排”。
- `web/routes/domains/scheduler/scheduler_batches.py:220-231`：单条删除已经使用 `_safe_next_url`，说明已有安全回跳样板。
- `web/routes/personnel_pages.py:147`、`:159`、`:185`、`:196`、`:220`：人员删除/批量动作固定回 `personnel.list_page`。
- 子代理校正：人员页没有 status 列表筛选，真正丢的是 `team_id`/页码上下文。

## 影响

用户在筛选态或分页态操作后会被带回默认列表，容易误以为操作影响了其他数据，也增加重复找回上下文的成本。

## 修复方向

复用 `_safe_next_url`，模板提交 `next=request.full_path`；没有 next 时显式保留当前查询态。

## 建议动作

`cs-issue`，因为这是用户流程正确性问题，修复范围可控。


---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-12"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 12：工时/归属确认只有「本页全选」（50 行/页），大零件跨页重复劳动

## 速答

工时确认要求每道工序逐行勾选「已核对」才能保存，而全选只有「确认本页已核对工时」（每页 50 行）；归属确认同款。120 序的零件要翻 3 页、每页先全选再复核，漏一页保存就报「请明确勾选确认工序 N」，报错后还要自己找是哪页漏了。服务端协议本来就要求一次提交全部有效工序，分页从来不是提交单位，「本页全选」是前端自己切碎的。

## 关键证据

- `frontend/workbench/app/ProcessHoursEditor.jsx:39` — `if (!current.confirmed) throw C.failure('请明确勾选确认工序 ' + row.sequence + ' 的工时 / 周期。')`。
- `ProcessHoursEditor.jsx:69-70` — 全选只覆盖 `paging.rows`（当前页）；`ProcessSourceEditor.jsx:97-99` 归属「确认本页已核对工序」同款。
- 每页 50 行：`ProcessStageEditor.jsx:41` `usePage` 里 `useState(50)`，`:53` 超过 50 才出分页器。
- 服务端粒度：`tests/workbench/test_process_stage_api.py:143-157` 断言 `hours_confirm` / `source_confirm` 必须含全部有效工序，少一行 409 `operation_set_mismatch`。工时载荷根本不带逐工序 confirmed（`core/models/workbench_process_commands.py:72-84,91`），逐行勾选是纯前端闸门；归属载荷要求每行 `confirmed: true`（`:59-61`）但不关心用户在哪一页勾的。
- 归属的写入令牌绑定已核对的输入（`web/routes/workbench/process_writes.py:75`），编辑器本页全选时已调 `invalidate()`（`ProcessSourceEditor.jsx:99`），跨页全选沿用同一机制即可。

## 影响

大零件（工序多）的录入确认是明显的重复劳动和出错点；保存报错不给定位。触发条件：任何超过 50 道工序的零件工艺维护。

## 修复方向

① 提供「确认全部 N 道」跨页全选，带二次确认弹窗说明范围；② 保存校验失败时在错误信息里列出未确认工序所在页码并支持一键定位。两项都是纯前端改动，不需要改服务端或合同测试。

## 建议动作

`cs-issue`，编辑器交互增强。

## 复核记录（2026-09-13）

- 原「跨页确认需与服务端保存协议核对一致性」查实为不需要：协议已是整零件粒度。
- 坐标由构建产物（`ProcessHoursEditor.js:59,168-190`、`ProcessSourceEditor.js:323-342`、`ProcessStageEditor.js:66-71`）改为源码。

## 实施记录（2026-09-13）

- 状态：resolved。`ProcessStageEditor.unconfirmed()` 按页汇总 + 「定位到第 N 页」；工时 / 归属编辑器新增「确认全部 N 道已核对」二次确认。
- 详见 [remediation-record.md](remediation-record.md)。

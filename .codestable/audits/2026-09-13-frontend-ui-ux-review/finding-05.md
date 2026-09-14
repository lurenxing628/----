---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-05"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 05：排产数字未全局等宽——`--num-variant: tabular-nums` 令牌零消费，主数据表未设等宽数字

## 速答

排产界面大量时间、工时、数量列纵向扫读，但等宽数字只在 15 处点状覆盖，主数据表 `table.wb-table` 与值班台表都没有设置；字体令牌层声明的 `--num-variant: tabular-nums`（注释写着 Numbers are always tabular）全仓无人消费，与设计承诺自相矛盾。结果是纵向扫列时数字抖动错位，核对更费力。

## 关键证据

- `frontend/workbench/prototype/tokens/typography.css:55` 声明 `--num-variant: tabular-nums`；`frontend/` 全树 `var(--num-variant)` 消费 **0** 处。
- `frontend/workbench/app/styles/` 内 `tabular-nums` 共 **15** 处（全 `frontend/` 含原型与 JSX 为 236 处，多在原型组件里）；主数据表 `table.wb-table` 的 th/td（`20-controls.css:425-431`）、值班台表（`36-analysis.css:27-28`）、外协表、候选表、`tt-table` 均未设。
- 表格正文字号：`20-controls.css:429` 用 `--font-size-2` = 13px（`typography.css:31-35`，阶梯 12 / 13 / 14px）。

## 影响

时间、工时、数量核对时数字错位，长时间阅读疲劳。触发条件：所有数据表，全天候。

## 修复方向

`table.wb-table td` 加 `font-variant-numeric: var(--num-variant)`，一处覆盖全仓；`20-controls.css` 是唯一允许 `!important` 的层，也已持有该 td 规则，落点合规。关键时间/数量列若仍有错位再单独处理。

## 建议动作

`cs-issue`，单规则修改，附截图对比。

## 复核记录（2026-09-13）

- 原条目把「13px / 12px 字号偏小」与「数字未等宽」捆在一条 P1 里。字号大小属设计判断，且与路线图 `wbui-tokens-states` 已交付的字号分档决定相抵（`--font-size-2` 明确定义为 secondary body，`-3` = 14px 才是 default body），已拆出转入索引「观察项 O1」；本条只保留可核实的等宽数字缺陷。
- 值班台表引用由 `36-analysis.css:29-31` 更正为 `:27-28`；补充 15 处的统计口径。

## 实施记录（2026-09-13）

- 状态：resolved。`table.wb-table tbody td` 消费 `--num-variant`。
- 详见 [remediation-record.md](remediation-record.md)。

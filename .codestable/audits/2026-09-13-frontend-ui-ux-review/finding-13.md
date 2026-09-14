---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "bug-13"
nature: bug
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 13：「已开工工序」规则是看得见却永远改不了的假控件

## 速答

排产检查的「已开工工序」规则渲染成单选组（保留记录 / 可重排），但 value 写死 `preserve_actuals`、`onChange` 为空函数、选项「可重排」永久禁用。排产员会反复尝试点击一个被设计成永远失败的控件，怀疑系统坏了。

## 关键证据

- `frontend/workbench/app/PreflightControls.jsx:14` — `<Segment label="已开工工序" value="preserve_actuals" choices={[["preserve_actuals", '保留记录'], ['reopen', '可重排', true]]} disabled={disabled} onChange={() => {}} />`。

## 影响

假控件破坏界面可信度：用户发现点不动后，会对其他真正可用的控件也产生怀疑。触发条件：每次打开排产检查的规则区。

## 修复方向

不可配置的规则用纯文本展示：「已开工工序：保留记录（不可修改）」，不渲染成单选组。待未来真正放开配置时再恢复控件。

## 建议动作

`cs-issue`，单行组件替换，零风险。

## 复核记录（2026-09-13）

- 事实核实无误；坐标由构建产物 `:64-69` 改为源码 `:14`。

## 实施记录（2026-09-13）

- 状态：resolved。`PreflightControls.jsx` 假单选改为固定说明文字。
- 详见 [remediation-record.md](remediation-record.md)。

---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-04"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 04：现场工序详情时间轴「计划」条对比度 1.36:1，近隐形

## 速答

现场记录展开工序详情后的作业时间线里，「计划」条用 `--ui-info-border`（`#bfdbfe`）画在 `#f8fafc` 轨道上，对比度仅 1.36:1（非文字元素需 3:1）；同轨「实际」条用绿色 3.15:1。计划 vs 实际这一核心对比里，计划条在普通显示器偏淡、在工厂老显示器或远看下基本消失。

## 关键证据

- `frontend/workbench/app/styles/35-field.css:15` — `.field-timeline-track .planned{background:var(--ui-info-border)}`，同轨 `.actual{background:var(--ui-success)}`；轨道底色 `--surface-2` 在 `35-field.css:1` 映射为 `--ui-surface-muted`（`prototype/tokens/colors.css:29`，`#f8fafc`）。
- 色值：`--ui-info-border` `#bfdbfe`（`colors.css:49`），`--ui-success` `#16a34a`（`colors.css:17`）。WCAG 复算：planned **1.36:1**，actual **3.15:1**。
- 渲染位置：`frontend/workbench/app/FieldDetail.jsx:18-23`，时间线只在展开某道工序的详情后出现，现场记录列表页本身不显示。

## 影响

现场记录页用户无法直观对比「计划该做什么」与「实际做了什么」。触发条件：展开任一工序详情查看作业时间线。

## 修复方向

planned 换更深一档的令牌（如 `--ui-info-text` 描边空心底，或甘特计划边色 `--wb-gantt-plan-edge` 系），与 actual 形成明度差而不是只靠色相变淡。

## 建议动作

`cs-issue`，单规则修改，需展开详情后截图复核实际观感。

## 复核记录（2026-09-13）

- 原「截图佐证：`field-1280-720-light.png` 中计划条几乎不可辨」撤销：整改前（`baseline-current`，09-12 13:23）与整改后（`browser-e696`，09-12 21:48）两套 1280 截图都只显示现场记录表格，时间线不在图上。
- CSS 事实与对比度结论不变，补渲染位置说明。

## 实施记录（2026-09-13）

- 状态：resolved。`35-field.css` `.planned` 改实色填充 + 1px 内描边。
- 详见 [remediation-record.md](remediation-record.md)。

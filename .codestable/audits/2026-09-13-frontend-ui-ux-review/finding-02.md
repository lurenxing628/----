---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-02"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 02：暗色主题表格行 hover 色与卡片底色完全相同，悬停零反馈

## 速答

`--ui-table-row-hover-bg` 与 `--ui-card-bg` 在暗色令牌里同为 `#1e293b`（1.00:1），深色模式下滑过表格行没有任何视觉反馈；hover 是排产员横向读长行的主要定位辅助。

## 关键证据

- `frontend/workbench/prototype/tokens/dark.css:34` — `--ui-table-row-hover-bg: #1e293b`，与 `:15` 的 `--ui-card-bg: #1e293b` 相同；`:22` 已有更暗一档的 `--ui-surface-muted: #162032` 可用。
- 消费方：`frontend/workbench/app/styles/20-controls.css:431`（`tbody tr:is(:hover,:focus-within)`，带 !important）、`21-table-frame.css:40-41`（固定列同步刷 hover 色）。
- 斑马纹令牌 `--ui-table-row-even-bg`（`dark.css:34` 为 `#162032`，`colors.css:56` 为 `#fcfcfc`）在应用样式层零消费，没有兜底。
- 浅色 hover `#f1f5f9` on `#ffffff` 仅 1.06:1，同样偏弱。

## 影响

深色模式用户在批次、资源、记录等宽表里横向扫读长行时失去行定位，容易串行读错数据。触发条件：暗色主题 + 任何宽表格。

## 修复方向

暗色 hover 改 `--ui-surface-muted` 或更亮一档，浅色 hover 一并评估加深。改动位置是 `前端设计/tokens/dark.css`，再用 `scripts/workbench/import_prototype.py --update` 导入快照；不能直接改 `frontend/workbench/prototype/tokens/dark.css`。

## 建议动作

`cs-issue`，单行令牌修复，需明暗双主题截图复核。

## 复核记录（2026-09-13）

- 事实与行号全部核实无误。
- 补充快照导入约束，原文没有说明。

## 实施记录（2026-09-13）

- 状态：resolved。`前端设计/tokens/dark.css` 暗色 hover 改 `#334155`，经 `import_prototype.py --update` 进快照。
- 详见 [remediation-record.md](remediation-record.md)。

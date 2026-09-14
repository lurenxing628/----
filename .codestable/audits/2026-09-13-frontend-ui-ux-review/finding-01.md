---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-01"
nature: usability
severity: P1
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 01：甘特条「冲突/超期」与「成功/锁定」仅靠红绿 pastel 填充区分，色盲不可辨

## 速答

计划甘特 / 试调甘特 / 现场甘特里，critical（红）与 success（绿）的填充、描边、文字三色对按 WCAG 相对亮度复算只有 1.02–1.15，即两种状态的明度几乎相同，只靠色相区分。红绿色盲排产员分不出「冲突/超期」与「正常完成/已锁定」，而冲突正是甘特图最需要一眼扫出的状态。

## 关键证据

- 调色板：`frontend/workbench/prototype/ui_kits/workbench/gantt-theme.css:22-28`，critical fill `#f5dfe0` / edge `#b25f69` / ink `#822f3e`，success fill `#dceee8` / edge `#527f70` / ink `#245e4d`；`:33` stop fill `#fbf1f2`。
- WCAG 复算（2026-09-13）：fill 对 **1.056**，edge 对 **1.023**，ink 对 **1.148**，暗色 edge 对 **1.072**，critical fill vs stop fill **1.148**。红绿色盲模拟值（原报 1.04 / 1.07 / 1.10）仓内没有模拟矩阵，本轮未复核，只作参考。
- 消费方：`frontend/workbench/app/styles/33-gantt-foundation.css:86-89`（`.plan-bar.critical` / `.success`）、`32-process-trial.css:86-87`（`.tt-bar.conflict` / `.locked`）、`33-plan-gantt.css:18-19`（`.plan-swatch`）。
- 已有的非颜色通道只在图例上：`33-plan-gantt.css:19` 的 `.plan-swatch.conflict` 用 1px dashed 边，条本身没有对应处理。
- 文字语义色四档全部过 WCAG AA，问题只集中在甘特 pastel 调色板。

## 影响

色盲用户在甘特上看不出哪些条是冲突/超期、哪些是正常/锁定，排产冲突扫读这一核心任务对这部分用户失效。触发条件：查看任何含冲突或完成状态的甘特图。

## 修复方向

补非颜色通道，顺已有语言扩展：critical 条加斜纹或加粗边，success 条内加 ✓ 或状态字前缀，让条本身自解释。不动色板；若确要动色板，改 `前端设计/` 里的源文件再用 `scripts/workbench/import_prototype.py --update` 导入，`frontend/workbench/prototype/` 是按 sha256 校验的快照，直接改会让构建报 Snapshot hash mismatch。

## 建议动作

`cs-issue`，与 finding-14（候选甘特图例）同批实施。

## 复核记录（2026-09-13）

- 原引用 `33-gantt-foundation.css:76-79` 实为 `.plan-resource` / `.plan-track`，`:158` 实为 `.fg-group-summary` 且用的是 primary 系令牌、与红绿无关；`32-process-trial.css:83-84`、`33-plan-gantt.css:17-18` 各偏 1–3 行。已全部更正。
- fill 对比度由 1.02 更正为 1.056；其余数字与复算一致。
- 虚线先例由 `33-gantt-foundation.css:79` 更正为 `33-plan-gantt.css:19`。

## 实施记录（2026-09-13）

- 状态：resolved。甘特条改为斜纹 / 内环双编码（`--wb-gantt-critical-stripe`、`--wb-gantt-overlap-stripe`、`--wb-gantt-success-ring`），图例同步；候选甘特重叠条改 overlap 色系。
- 详见 [remediation-record.md](remediation-record.md)。

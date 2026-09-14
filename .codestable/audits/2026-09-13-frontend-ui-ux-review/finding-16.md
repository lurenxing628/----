---
doc_type: audit-finding
audit: 2026-09-13-frontend-ui-ux-review
finding_id: "usability-16"
nature: usability
severity: P2
confidence: high
suggested_action: cs-issue
status: resolved
reviewed: 2026-09-13
---

# Finding 16：现场实际甘特「实际报工」条与「原计划基线」条填充明度比 1.002，只靠色相与虚线边区分

## 速答

现场实际甘特里实际条用 `--wb-gantt-primary-fill`（`#dceaf9`），计划基线条用 `--wb-gantt-plan-fill`（`#e8e8e8`），两者相对亮度几乎完全相同（1.002:1），描边也只有 1.18:1。区分全靠「淡蓝 vs 淡灰」的色相差和基线条的上下虚线边；在色弱、老显示器或远看场景下，计划 vs 实际这一核心对比会退化成只剩虚线这一条线索。

## 关键证据

- 调色板：`frontend/workbench/prototype/ui_kits/workbench/gantt-theme.css:7` `--wb-gantt-plan-fill: #e8e8e8`、`:8` plan-edge `#767676`；`:14` `--wb-gantt-primary-fill: #dceaf9`、`:15` primary-edge `#6085ac`。暗色 `:39` / `:46` 为 `#303030` / `#253b50`。
- WCAG 复算：浅色 fill 对 **1.002**，edge 对 **1.178**，暗色 fill 对 **1.144**；两种填充对白底各为 1.22，即都极淡。
- 消费方：`frontend/workbench/app/styles/33-plan-gantt.css:26-28` — `.fg-act` 用 primary-fill 加 inset 1px primary-edge 实线环，`.fg-plan` 用 plan-fill 加 `border-block: 1px dashed` plan-edge，`.fg-remaining` 用 reference-fill 加虚线边。
- 对照 P2-V7：同组令牌里 primary-fill vs reference-fill 为 1.137，原审计报了这一对，漏了更糟的 plan 对。

## 影响

现场实际甘特的核心任务是对比计划与实际；填充明度相同意味着色弱用户和低质量显示器上只剩虚线边一个线索，条短或缩放小时虚线不可辨。触发条件：现场实际甘特任何视图。

## 修复方向

计划基线条改为描边空心（透明底 + 虚线框）或加斜纹，让形状通道独立于填充；或把 plan-fill 降一档明度。色板改动走 `前端设计/` 快照通道。与 finding-01 的双通道编码同批处理。

## 建议动作

`cs-issue`，与 finding-01 / 14 合并为甘特状态编码专项。

## 复核记录（2026-09-13）

- 本条为复核新增：原审计在 P2-V7 逐令牌读过同一组规则，但没有把任意两色两两比过去。
- 定为 P2 而非 P1，因为 `.fg-plan` 已有虚线边形状通道，且截图中基线条呈细条形态，与实际条几何不同。

## 实施记录（2026-09-13）

- 状态：resolved。`.fg-plan` 改透明底 + 四边虚线，`.fg-remaining` 透明底，网格线去 opacity。
- 详见 [remediation-record.md](remediation-record.md)。

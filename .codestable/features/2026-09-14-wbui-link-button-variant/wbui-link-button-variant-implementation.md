---
doc_type: feature-implementation
feature: 2026-09-14-wbui-link-button-variant
status: implemented
implemented: 2026-09-14
tags: [workbench, ui, controls, navigation]
---

# 链接样式按钮变体：实施记录

## 改动

- `frontend/workbench/app/styles/20-controls.css`：在 `button.btn.danger` 规则后新增三条 `button.btn.link` 规则（常态 / hover·active / 禁用），每条 `!important` 前带 `/* override: 选择器; 原因 */` 注释；只用令牌 `--ui-info-text`、`--ui-primary`、`--ui-info-muted`、`--wb-control-edge-hover`、`--space-1`。
- `frontend/workbench/app/RunCandidateWorkspace.jsx`：`.rc-nav` 里「返回排产记录」「返回正式计划」两个按钮改 `className="btn link"`。
- `frontend/workbench/app/styles/34-run.css`：删除过渡期的 `.rc-nav .btn{text-decoration:underline}` 规则，由变体统一负责。
- `tests/workbench/test_run_candidate_widgets.cjs`：新增 `nav-buttons-read-as-links` 检查（透明底、透明边框、下划线、高度不低于 32px）。

## 验证

- `node tests/workbench-app-styles.cjs`：0 违规。
- `tests/workbench/test_ui_refinement_style_gate.py`、`test_style_build_sources.py`、`test_run_candidate_widgets.py`（含新增检查）：56 通过，static 已按 build_id 194744… 重建。
- 未跑全量门禁。

## 后续

- 其他工作区的纯导航按钮（值班台跳转、批次「下一步 · 去排产」等）是否迁移到 `btn link`，待用户逐页确认后再做，避免一次性改变所有按钮的视觉层级。

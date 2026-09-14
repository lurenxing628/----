---
doc_type: feature-design
feature: 2026-09-14-wbui-link-button-variant
status: approved
summary: 给共享按钮加一个受控的「链接样式」变体，让候选页等处只负责跳转的按钮读起来像文字链接，不再与旁边的动作按钮抢眼。
tags: [workbench, ui, controls, navigation]
---

# 链接样式按钮变体

## 0. 背景

2026-09-13 前端 UI/UX 审计 finding-15：候选工作区行动区里「返回排产记录 / 返回正式计划」这类导航按钮和「采用方案 / 试调」这类动作按钮并列、外观相同。整改时只做到了分组、分隔线和下划线，因为 `20-controls.css:30-60` 用 `!important` 锁死了 `button.btn` 的边框 / 底色 / 文字色 / 内边距，而硬规则只允许 `20-controls.css` 出现 `!important`，别的样式文件改不动它。

## 1. 目标与边界

- 目标：一个类名 `btn link`，让按钮呈现为无边框、透明底、带下划线的文字链接，同时保留共享控件的高度、字号、焦点环和禁用语义。
- 只在 `20-controls.css` 增加变体，不改 `.btn` 基础规则；每条 `!important` 前写 `/* override: 选择器; 原因 */`（样式门禁规则 `important-override`）。
- 首批消费方只有候选工作区 `.rc-nav` 的两个返回按钮；其他页面的导航类按钮是否迁移另行决定。
- 明确不做：不新增第二种链接颜色、不做图标按钮的链接变体、不改共享 `Button` 组件的属性面。

## 2. 方案

| 状态 | 规则 |
|---|---|
| 常态 | `background: transparent`、`border-color: transparent`、`color: var(--ui-info-text)`、`padding: 5px var(--space-1)`、`text-decoration: underline`、下划线色 `--wb-control-edge-hover` |
| hover / active | 底色与边框保持透明，文字与下划线改 `--ui-primary` |
| 禁用 | 文字 `--ui-info-muted`，去掉下划线 |
| 焦点 | 沿用 `.btn` 的 `focus-visible` 外框，不另写 |

选择器特异性：基础规则是 `body.aps-workbench :is(…button.btn…)` 及其 `:hover` 版本，变体用 `body.aps-workbench button.btn.link` 与 `…:is(:hover,:active):not(:disabled):not([aria-disabled="true"])`，都比对应基础规则高一级，且写在其后。

## 3. 验收

- `node tests/workbench-app-styles.cjs` 0 违规（`!important` 只出现在 `20-controls.css` 且都带 override 注释）。
- 候选工作区探针 `tests/workbench/test_run_candidate_widgets.cjs` 断言 `.rc-nav .btn.link` 的计算样式：透明底、透明边框、`text-decoration-line` 含 `underline`。
- 深浅两主题下按钮文字对比度不低于 4.5:1（`--ui-info-text` 与 `--ui-primary` 都是既有可读令牌）。

## 4. 与既有决定的关系

- 不违反 `wbui-r2-empty-height-reason-copy`（禁用原因展示）与 `wbui-run-stepper`（主按钮层级）。
- 审计 finding-15 由「部分修复」转为「已修」，见 `.codestable/audits/2026-09-13-frontend-ui-ux-review/remediation-record.md`。

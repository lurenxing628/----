---
doc_type: issue-fix
issue: 2026-07-22-field-gantt-dark-badge-contrast
path: fast-track
fix_date: 2026-07-22
tags: [前端, 深色模式, 甘特图, 可读性, 设计令牌]
---

# 现场实际甘特深色模式时间徽标修复记录

## 1. 问题描述

前端设计工作台切换到深色模式后，「现场实际甘特」中实际工序条右侧的完工偏差徽标可读性过低。用户标记的具体实例是 `50 检验` 工序中的 `−12m`。

## 2. 根因

`前端设计/ui_kits/workbench/field-gantt.css` 的 `.fg-act-badge` 使用接近白色的固定背景，却把文字色设为会随主题变化的 `--ui-text`。深色模式把 `--ui-text` 重指派为浅色，造成浅色文字叠在浅色徽标上。

继续核对设计系统后，还发现该徽标只借用了单个文字令牌，背景和各状态覆盖写法没有与标准 `Badge` 组件统一成完整的颜色令牌对。

## 3. 修复方案

- 默认徽标成对使用 `--badge-secondary-bg` 与 `--badge-secondary-text`。
- 准时或提前状态使用 `--badge-success-bg` 与 `--badge-success-text`。
- 进行中状态使用 `--badge-primary-bg` 与 `--badge-primary-text`。
- 延后状态使用 `--badge-warning-bg` 与 `--badge-warning-text`。
- 严重延后状态使用 `--badge-danger-bg` 与 `--badge-danger-text`。

这样徽标的背景和文字来自同一套语义，不再把主题正文色与固定浅色背景混用。

## 4. 改动文件清单

- `前端设计/ui_kits/workbench/field-gantt.css`：统一实际工序条内各状态徽标的背景、文字令牌对。

## 5. 验证结果

- 通过本地服务器在内置浏览器中重新加载 `ui_kits/workbench/index.html`，进入「现场实际甘特」复现用户标记位置。
- 深色模式下，`−12m` 的实测颜色为文字 `rgb(6, 95, 70)`、背景 `rgb(209, 250, 229)`，对比度约 `6.78:1`。
- 深色模式下，现有全部徽标的最低实测对比度约 `6.37:1`；`进行中` 约 `7.15:1`。
- 浅色模式下重复检查，现有全部徽标的颜色令牌和对比度与深色模式一致，没有因修复产生反向退化。
- 最后已把浏览器恢复到用户原来的深色模式，并保留在「现场实际甘特」页面。

## 6. 遗留事项

- 设计系统的 `--badge-*` 令牌值与正式产品 `static/css/style.css` 中 `.badge-*` 的颜色值一致，但正式产品当前仍把这组值直接写在 `style.css`，尚未收编进 `static/css/00-tokens.css`。这是跨设计稿与正式产品的令牌单一真源治理事项，不属于本次局部可读性修复范围。

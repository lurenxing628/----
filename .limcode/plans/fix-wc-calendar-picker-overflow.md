## 1. 问题描述

- 入口：
  - 排产调度 → 工作日历配置（`/scheduler/calendar`）
  - 人员管理 → 人员详情 → 个人工作日历（`/personnel/<id>/calendar`）
- 操作：点击“选择”打开日期选择弹层。
- 现象：日期格子/日期数字在弹层右侧（或整体）超出白色弹层边框（截图所示）。

## 2. 根因分析（已定位）

- v2 UI（`web_new_test/templates/base.html`）会加载 `web_new_test/static/css/style.css`。
- 该 CSS 中存在“兼容 V1 模板的 legacy button 样式”：
  - `button:not(.btn)` 会被统一赋予较大的 `padding: 0.5rem 1rem`、`display:inline-flex` 等。
- 日期选择器使用 CSS Grid：
  - `.wc-cal-grid { grid-template-columns: repeat(7, 1fr); }`
  - Grid 轨道的最小尺寸默认是 `auto`，会参考子项 min-content size。
- 日期格子按钮由于 padding 过大，使其 min-content 变宽，导致 7 列网格总宽度 > 面板宽度（296px），从而出现溢出。

## 3. 修复思路

目标：让日期选择器在 **v1/v2 两种 UI** 下都稳定显示。

措施：

1. **提升选择器样式特异性**，确保能覆盖 v2 的 `button:not(.btn)` 规则（其特异性高于单纯的 `.wc-cal-day`）。
2. **重置日期格子/导航按钮的 padding/min-width**，避免 min-content 被撑大。
3. 将网格列定义改为 **`minmax(0, 1fr)`**，防止轨道被 min-content 反向撑开（更健壮）。
4. 兼容性：给 `.wc-cal-panel` 明确 `box-sizing: border-box`，使固定宽度在 v1/v2 表现一致。

## 4. 具体修改点

> 仅涉及样式，不改动业务逻辑。

### 4.1 修改模板内 date picker 样式（两处）

文件：
- `templates/scheduler/calendar.html`
- `templates/personnel/calendar.html`

修改其 `<style>` 中与 `.wc-cal-*` 相关的规则：

- 将网格列：
  - `repeat(7, 1fr)` → `repeat(7, minmax(0, 1fr))`
- 给选择器内部规则统一加前缀 `.wc-cal-panel`（提高特异性）：
  - 例如：`.wc-cal-day` → `.wc-cal-panel .wc-cal-day`
- 对按钮补充/覆盖：
  - `.wc-cal-panel .wc-cal-day { padding:0; min-width:0; line-height:1; display:flex; align-items:center; justify-content:center; }`
  - `.wc-cal-panel .wc-cal-nav { padding:0; min-width:0; }`
- `.wc-cal-panel { box-sizing:border-box; }`

（如需彻底兜底，可选加：`.wc-cal-panel { overflow:hidden; }`，但优先不加，避免未来内部浮层/阴影被裁剪。）

### 4.2（可选）去重优化

两处模板的 date picker CSS 完全一致，可选：

- 抽取为 `static/css/calendar_picker.css`
- 两处模板改为 `<link rel="stylesheet" ...>` 引入

此项为可选优化；若本次以快速修复为主，可先直接同步修改两处模板，后续再抽取。

## 5. 验收标准（手工）

在 **v2 模式** 与 **v1 模式** 下分别验证：

1. 打开日期选择弹层，7 列日期格子完全位于弹层白色边框内（无横向溢出/换行错位）。
2. 翻月（‹/›）后网格仍正常，不抖动、不溢出。
3. 已配置日期高亮、周末标识、选中态仍正常。
4. 两个入口页面（全局/个人工作日历）表现一致。

## 6. 回滚方案

- 仅改动模板内 CSS（或新增静态 CSS 文件），若出现样式回归可直接回退对应 commit。
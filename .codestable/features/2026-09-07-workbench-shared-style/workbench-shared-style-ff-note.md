---
doc_type: feature-ff-note
feature: workbench-shared-style
date: 2026-09-07
tags: [frontend, prototype, shared-style, contrast]
---

## 范围与决定

按用户授权，以现场记录为参照，统一当前 `ui_kits/workbench/index.html` 内同类传输按钮、顶部统计条和普通数据表。不是全仓换肤，不新增业务数据或接口，也不把所有专用图形改成同一结构。用户随后指出的首页时间条对比度、基础资料小卡片文字贴边一并修复。

## 实现

- 新增 `前端设计/ui_kits/workbench/workbench-ui.js`、`workbench-ui.css`。组件及样式通过 `wb-*` 明确接入，不替换全局 DS，不对所有 button/table 盲目覆盖。按钮使用已有本地 Lucide 文件导入、文件导出、文件下载图标，保留可见文字、处理函数、禁用状态与主次关系；常规操作组靠右并可换行。
- 统计条统一为相邻分栏、上方名称、下方数值，沿用现有语义色的可读文字令牌；不制造原本没有的指标。普通表格统一表头、字号、行距、分隔线、悬停和选中表现，继续委托原 DS/原生表格的排序、筛选、列宽处理。
- 值班台通过 `dashboard-markup.js`、`dashboard-views.js` 接入统计和普通明细表；现场记录通过 `field-report-markup.js`、`field-report-views.js`、`field-reporting.js` 接入统计与传输按钮，包括导入弹窗。现场记录的 `r-table` 是视觉参照且含报工历史、元数据、行内表单，不再套通用单元格规则。
- `plana-logic.js` 接入当前 ProcessNative 的 4 类统计输出、9 处普通表格模板与传输按钮，保留数据、事件钩子及动态状态。原生表格框架去除额外浮卡；工时编辑列的强调色、紧凑输入密度和分组行保留。菜单只统一图标，不改成带框工具栏按钮。
- `BaseShared.jsx`、`BaseBatches.jsx` 接入当前批次页及相关维护弹窗。`ReportsScreen.jsx`、`DelayScreen.jsx`、`CalibScreen.jsx`、`AnalysisScreen.jsx`、`BasicDataScreen.jsx`、`GanttScreen.jsx`、`GanttBoard.jsx`、`FieldGanttScreen.jsx` 接入各自等价区域。分析页只将顶部联动指标提为统计条，方案选择卡、对比图、负荷矩阵、联动对比表保留。
- 表格中的链接、晚交、利用率、校准偏差、灰色状态文字改用同语义可读颜色；没有修改计算、阈值、状态或数据。手机端共用传输按钮仍保留 44px 点击高度。
- `dashboard-workbench.css` 将首页任务时间条改为实心蓝/橙语义色；`field-gantt.css` 实际条与图例同步为实心状态色。`gantt-board.css` 保留原 COLOR 与条体填色，修复标签和边界；`GanttBoard.jsx` 仅为条体添加 `data-status` 并去掉尾号文字的单独透明度。计划虚线、停机斜纹、时间长度/位置、实际间隙、仅开工标记及选链淡化逻辑保留。已有 `field-reporting.css` 时间条与本轮开始备份逐字相同。
- `plana.css` 仅针对产能链内的 5 张小资源卡设置 12px 留白、28px 图标列、可伸缩文字列和 13px 名称；长名称可换行，主链在 1280px 以下沿用原纵向排列，避免固定三栏挤占正文。工艺/物料输入卡、日历卡的内部样式和业务结构未改。
- 用户追加反馈校准表仍有圆角，定位到外层 `.bd-table-scroll` 的 8px 圆角。校准表、批次列表/工序表、共享导入预览的这 4 处容器明确添加 `wb-table-frame`，与内层共用表格框架一并直角化，不覆盖输入框、菜单和按钮圆角。
- `index.html` 加载共用资源，并给本轮变化的资源更新版本号；未新增远端脚本、样式、运行时或依赖。

## 覆盖面

当前实际路由为值班台、基础资料 ProcessNative、批次管理、执行排产、计划甘特、方案分析、现场记录、现场实际甘特、执行复盘报表、工时校准、主数据总览、系统管理，以及报表进入的延期说明。基础资料另覆盖 8 个原生页签、5 个工艺筛选和相关弹窗。没有给原本无统计条/导出功能的页面凭空加数字或操作。

专用日历、工艺流程、资源链、方案矩阵、甘特坐标与业务图例不套普通表格样式；只对被指出的资源卡留白、同类时间条可读性做定点修改。旧版独立 HTML 方案稿及未启用的替代页面未纳入整页改版。

## 验证

以下为本轮实际运行的局部验证：

- 原入口值班台 149 项；现场报工 74 项、行内数量 69 项、更正/审计 62 项、原记录连续性 63 项、布局 41 项通过。
- 报工工具栏及真实 XLSX 导出往返 76 项，真实 XLSX 导入集成 44 项通过；自动完工模型 9 个、导入模型 23 个单元测试通过。
- 报工浅深色 CSS 检查 5736 项通过，文字最低 4.58:1，12 个时间图形最低 4.55:1。
- `tests/workbench-native-style.cjs` 原生页签 2383 项、`tests/workbench-batches-style.cjs` 批次及共享组件 170 项通过；`前端设计/ui_kits/workbench/tests/workbench-business-style.cjs` 业务页 154 项通过。
- `前端设计/ui_kits/workbench/tests/workbench-shared-style.cjs` 最终原入口 493 项及 1084 个文字颜色样本通过，文字最低 4.76:1，覆盖小卡片留白、文字换行约束和普通表格内外框直角。
- `tests/workbench-timebars-contrast.cjs` 最终 5631 项通过，220 个文字样本最低 4.744:1、192 个条体/边界样本最低 4.344:1。22 个非选中条继续有意淡化，不把该态纳入 4.5:1/3:1 达标声明。现场实际甘特 `field-gantt.integration.cjs --host` 最终 245 项通过。
- 工作台顶层 16 个 JS 语法、24 个 JSX 转译、7 个 CSS 解析通过；最后追加变动的 3 个 JSX 重新转译通过。22 个已有变化文件与本轮备份比对的空白检查通过；22 个变化资源引用均已更新为 `20260907-unified-style-3`，原有暂存内容未变。
- 本轮真实创建 4 个子代理，分工为原生基础资料、React 业务页、批次/共享组件、时间条；均已审阅整合并关闭，无创建失败。主代理负责共用样式、入口、集成回归及小卡片修复。

## 边界与现存事项

浏览器工具此前拒绝访问该本地文件，本轮未改走其他浏览器、HTTP、复制页面或 CDP 绕过。测试基于实际 index 脚本、JSDOM、CSS 合同及真实 XLSX；不宣称新的浏览器截图、像素验收或真实视口无重叠证明。新增测试处理了 JSDOM 对 CSS 自定义属性、内联 background 和 author !important 的已知差异，但不替代实际浏览器排版。

这是静态样板修改，没有运行会生成范围外产物的后端整仓质量门禁，不构成 clean-worktree proof。页面原有部分导入/导出仍为示例操作，本轮没有把按钮换肤说成已接好后台。原生工时详情的导入按钮存在本轮前就未绑定监听的问题，保持现状，没有借统一风格擅自扩展功能。宿主已有 `fill-opacity` React 警告仍在。

原有暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行和其他未提交工作保留，本轮未提交。`前端设计/` 仍被 Git 忽略；新增根目录测试和本记录未跟踪。修改前 59 个原型文件/测试与 SHA-256 清单位于 `/Users/lurenxing/.codex/visualizations/2026/09/07/01a079ea-544f-73f0-aef0-d63b087bb017/workbench-before-shared-style/`，59 份备份已逐一验签。刷新页面加载新资源，同时仍会重置本次示例会话。

复跑原型测试时使用现有本地 QA 依赖：`NODE_PATH=/Users/lurenxing/.codex/visualizations/2026/09/07/01a079ea-544f-73f0-aef0-d63b087bb017/.qa-dom/node_modules node <上述测试路径>`。没有向产品添加依赖。

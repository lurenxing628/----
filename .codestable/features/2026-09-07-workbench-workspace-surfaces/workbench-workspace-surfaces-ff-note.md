---
doc_type: feature-ff-note
feature: workbench-workspace-surfaces
date: 2026-09-07
requirement:
tags: [workbench, gantt, reports, prototype]
---

## 做了什么
按用户确认的意见，将主甘特和现场实际甘特的工具栏、图例、时间轴置于同一细边框工作区，保持直角、无阴影；报表资源负荷数据区与左表统一底色并补齐左右留白。按钮 6px / 分段组 8px、任务条配色和数据均不变。

## 改了哪些
- `前端设计/ui_kits/workbench/GanttBoard.jsx`、`FieldGanttScreen.jsx`：增加 `.gb-workspace`，保留顶部标题/统计在框外、悬浮详情在框外，事件与时间数据不变。
- `gantt-board.css`：统一 1px 外框、12px 工具栏留白和图例分隔线；去掉图内重复外框，原 `.gb-board` 继续承担横向滚动。
- `index.html`：资源负荷 `.load-list` 使用 `--ui-card-bg`，`.load-row` 使用 `12px 14px` 留白，原等高与窄屏堆叠规则不变；刷新相关资源版本。
- `ReportsScreen.jsx`：链接使用与左表一致的 `--ui-info-text`，避免深色模式在新底色上只有 3.98:1 对比度；未改原数据和点击回调。
- 新增 `tests/workbench-workspace-surfaces.cjs`，更新 `tests/workbench-chart-radius.cjs` 的工作区外框角色合同。

## 怎么验证的
新增分组/底色/留白/主题/交互 251 项、主甘特 2748 项、现场完整宿主 293 项、现场样式 562 项、图表圆角 1123 项、业务形状 506 项、业务交互 154 项及共用页面 1419 项通过。3 份 JSX 转译、2 份 CSS 解析与本地资源路径检查通过。

此前浏览器访问被明确拒绝，本轮未绕过，以上为源码、JSDOM 和 CSS 合同，不是新浏览器截图或真实视口对齐证明。仅原型修改，未运行生产后端整仓门禁，未提交；前端目录仍受 Git 忽略。原有暂存文件 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行和其他未提交改动保留。刷新原页面会重新初始化示例报工会话。

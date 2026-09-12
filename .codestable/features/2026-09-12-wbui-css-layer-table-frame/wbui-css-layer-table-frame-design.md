---
doc_type: feature-design
slug: wbui-css-layer-table-frame
status: approved
created: 2026-09-12
feature: 2026-09-12-wbui-css-layer-table-frame
roadmap: workbench-ui-refinement
roadmap_item: wbui-css-layer-table-frame
summary: 应用 CSS 层与内部滚动表格框
tags:
- workbench
- ui
---

# 应用 CSS 层与内部滚动表格框

依据用户批准的 implementation-20260912.md 并行实施。范围为样式基座、构建清单及对应验证；不改领域 API 和业务规则。

采用应用自有 CSS 清单，原型 CSS 之后加载。表格采用 max-height 受视口约束的内部滚动框，thead top:0，首尾关键列固定。共享 CSS 明确覆盖现有原型 important 规则，注释注明原因。静态控件样式从 JSX 移到 CSS，JS 仅维护主题图标变量。圆角、字号、层级和严重度统一引用 tokens；1280 宽保持侧栏与主内容预算，保留基础资料首屏结构。

验收先做隔离组件浏览器/构建合同验证，再由主线程统一构建并验证真实工作区；不把 dirty 工作区结果写成 clean proof。

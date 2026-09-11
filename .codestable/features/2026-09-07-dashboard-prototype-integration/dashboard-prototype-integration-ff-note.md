---
doc_type: feature-ff-note
feature: dashboard-prototype-integration
date: 2026-09-07
requirement:
tags: [prototype, dashboard, frontend]
---

## 做了什么
将用户确认的第二版样板整合进 `前端设计/ui_kits/workbench/index.html` 的值班台。保留应用侧栏和全部其他子页面，增加问题清单、影响明细、候选方案对比、现场回填、外协登记与处理记录；示例状态在切页后保留，整页刷新重置。未连接后端或生产数据库，回填变化不伪装为排程重算。

## 改了哪些
- `DashboardScreen.jsx`、`dashboard-{model,markup,views,workbench}.js`、`dashboard-workbench.css`：原生组件、示例数据、输入校验、生命周期与局部响应式样式。
- `index.html`、`AppShell.jsx`、`app.jsx`：本地资源加载、值班台独立的方案上下文、保留其他页面的原有上下文。
- `assets/dashboard-icons.js`、`assets/lucide-LICENSE`：本地 Lucide 1.8.0 图标子集及许可；没有新增远程运行依赖。原型已有 React/Babel CDN 引用未在本轮改造。

## 怎么验证的
- `tests/dashboard-integration.cjs`：完整入口在 JSDOM 中加载，通过 149 项断言，覆盖六类问题及三个页签、指标计算、表单校验、键盘操作、暗色切换、11 个子页面往返、卸载清理和事件不重复提交。开发验证依赖为 jsdom 26.1.0、React/ReactDOM 18.3.1、Babel standalone 7.29.0，通过 `NODE_PATH` 指向本机临时 QA 依赖目录运行。
- 四个原文件备份及 SHA-256 清单位于 `/Users/lurenxing/.codex/visualizations/2026/09/07/01a079ea-544f-73f0-aef0-d63b087bb017/workbench-before-integration/`，校验通过；原有脚本与远程依赖清单保持不变。
- 浏览器工具此前拒绝本地文件访问，本轮没有绕过限制，没有真实截图、布局像素或打印实测证明；请在已经打开的页面刷新验看。未跑生产全量门禁，本轮范围仅为静态原型；已有大量工作区改动且原型目录被 Git 忽略，因此仅报告局部验证，未提交或暂存文件。

---
doc_type: feature-ff-note
feature: plan-trial-sample
date: 2026-09-08
requirement:
tags: [workbench, prototype, comparison, gantt]
---

## 做了什么
新增独立的方案试调交互样板，保留原有原型页面，复用现有颜色、字体、圆角、甘特色板和本地 Lucide 图标。三个预置方案的对比、甘特和批次交付联动；支持工序试调、约束冲突提示、确认采用、本地版本记录及 CSV 导出。

## 改了哪些
- `前端设计/ui_kits/workbench/trial-sample.html`、`trial-sample.css`：独立静态入口及同风格布局，主验收视口 1920x1080。
- `trial-sample-model.js`：预置方案、纯时段汇总、约束检查和 CSV；冲突草稿只可 inspect，不可 evaluate 或导出为可行方案。
- `trial-sample-views.js`、`trial-sample.js`：联动视图、本地存储、草稿与正式快照分离、采用确认和记录；固定工序不开放编辑，未知换型次数不推断。
- `app.jsx`：只增加受白名单约束的初始 `?view=` 定位，供样板返回对应原型页面；无参数或未知参数仍进入值班台。
- `tests/trial-sample-model.cjs`、`tests/trial-sample-browser.cjs`：纯模型与真实浏览器回归。

## 怎么验证的
- `node --test 前端设计/ui_kits/workbench/tests/trial-sample-model.cjs`：32/32 通过，包含跨时区、结构错误、资源/人员重叠、前后序、日历、固定工序、连续试调及 CSV。
- 使用本机 bundled Playwright 对临时回环静态服务运行 `tests/trial-sample-browser.cjs`：51 项检查通过，包括 1920x1080、390px、浅色/暗色/打印、冲突拦截、采用与刷新、放弃草稿不影响正式快照、导出及返回原型白名单。样板无外部请求、无缺失资源、无页面异常。
- `app.jsx` 经项目自带 Babel 转译通过。已查看浅色、暗色、打印和窄屏截图；临时服务仅用于验证，最终 HTML 不依赖服务。

## 范围与剩余事项
仅为本地示例，不调用真实排产引擎或生产接口，不声称实现通用 APS 求解。前端目录受现有 Git 忽略；本轮未提交，未动原有暂存和其他未提交内容。未运行生产整仓门禁，也未在 Win7/Chrome 109 实机验证；本次不是 clean-worktree proof。整体观感待用户确认。

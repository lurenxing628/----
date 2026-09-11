---
doc_type: feature-implementation
feature: workbench-workflow-polish
date: 2026-09-08
status: implemented
---

## 交付范围

实际并行调用 4 个继承模型的 subagent，分别实施现场甘特、批次管理、值班台、报表复盘；均已返回并关闭。主代理实施方案工作区、试调冲突、排产前检查和路由集成，并复跑真实入口测试。用户视觉验收待现场确认，没有自动提交。

所有运行代码仅在 `前端设计/ui_kits/workbench/`。基础资料、现场记录、主数据、系统管理、定额校准未无故重写业务，保留原实现并纳入全页回归。未修改 Python、生产数据或全局设计系统资源。

## 主要修改

- `trial-sample-model.js / trial-sample-views.js / trial-sample.css`：相邻工序不改时间坐标；金边内收；真重叠分轨并标记区间。保留精确时长、固定工序和完整提示。人员分组复用相同任务集合。
- `plan-workbench.js / PlanShared.jsx / AnalysisScreen.jsx / GanttBoard.jsx / DelayScreen.jsx / plan-workbench.css`：方案对比、计划甘特、交付风险共用已验证的 4 批 8 工序试调样例，采用版本和记录与独立试调页共享。移除旧的不同月份指标、虚构因果时间线及按时间排序冒充关键路径。保留未采用、冲突不可采用、未知换型次数等状态。
- `preflight-model.js / GanttScreen.jsx`：读取批次当前已保存资料，排除完成/取消批次；未提交草稿不计入。缺资源暂不排不阻断其他可用工序，工时/外协缺项不能冒充自动分配成功。齐套与未生成工艺分别披露，检查不声称已调用排产引擎。
- `BaseBatches.jsx / batch-draft-model.js / batch-workbench.css`：切页保留状态和草稿，批量修改/复制/删除预览旧新值，确认时校验版本；全选限定当前结果，支持定向补齐和返回排产；删除弱化且保留确认，操作列固定右侧。
- `DashboardScreen.jsx / dashboard-*.js / dashboard-workbench.css`：6 类 15 个具体条目独立处置，责任人/期限/措施/完成凭据与历史可核对，重开保留原证据；人工关闭不清零计算风险。来源不匹配时明确说明，不假定位。
- `FieldGantt*.jsx / fg-screen-* / field-gantt*.css`：顶区收紧，分组折叠、只看选中、定位与视口恢复，区分已完晚/应完未闭合/剩余安排预计晚；计划、实际、剩余和原资源参考继续分行。首段不足显示完整刻度时不显示半截文字，完整值仍在提示中。
- `ReportsScreen.jsx / ExecutionReviewScreen.jsx / AnalysisShared.jsx / report-workbench.css / execution-review.css`：传递完整八项 scope 与独立 taskId，返回保留专题/排序/分页/选中/图表/滚动；图表默认折叠、明细前置。
- `app.jsx / AppShell.jsx / index.html / trial-sample.html`：路由上下文和浏览器前进后退、数据来源标识、试调入口、加载顺序、按内容散列更新缓存版本；窄屏页头换行。

## 验证

模型组合命令 `node --test` 覆盖 trial、workflow、batch、dashboard、field Gantt、execution analysis、report scope：87 个 Node 测试单元通过，其中批次模型内部 70 项、甘特模型内部 114 项断言。

真实 Chrome 独立上下文：全页 workflow 最终 247 项通过，14 页 × 1920×1080/1392×924 × 明暗主题，56 张截图；方案选择/采用/独立试调互通/返回/排产补齐链已验证，追加断言确认固定操作列不会挡住状态列。单独 `file://` 模式在 1920×1080 验证主页面和试调共享选择状态，测试浏览器允许本地文件访问，未更改用户浏览器配置。

其他定向回归：trial 51 项；文字 12 组/192 标签；现场甘特隔离 37 项、真实完整入口 13 项；报表复盘真实路由 139 项；值班台 Chrome 98 项、DOM 165 项；批次 Chrome 24 项、DOM 48 项；离线资源/本地依赖完整性/全部 JSX 234 项；业务圆角与界面结构 378 项。390px 批次页头补修后实际整页宽度为 390px。

旧布局测试同步至新数据和交互合同，不再断言已移除的虚构因果及重复推荐卡。JSDOM 测试使用明确的离线测试 origin，避免 `about:blank` 的 history 实现异常；未屏蔽错误，未修改生产逻辑迁就模拟器。

共享样式最终 1651 项通过，检查 1442 段文字，最小对比度 4.76:1；发现的值班台中性状态标签低对比度已修正。未降低 4.5:1 检查门槛。

测试依赖均复用本机：Playwright 为 `/Users/lurenxing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`；旧 DOM/CSS 套件依赖位于 `/Users/lurenxing/.codex/visualizations/2026/09/07/01a079ea-544f-73f0-aef0-d63b087bb017/.qa-dom/node_modules`。初次缺少 NODE_PATH 的失败已定位，不安装或升级产品依赖。

## 证据与限制

- 修改前完整副本和解包对照：`/tmp/aps-workbench-before-parallel.YKMpD8/`；最终全页截图：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workflow-qa-EBkXWg/`。
- 原型目录被 Git 忽略；本轮未强制加入版本控制。原有暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行保留，其他脏改不回退。
- 未运行生产整仓质量门禁，理由是本轮仅隔离前端原型、工作区存在大量原有改动；未验证真实 Win7。以上是原型局部验证，不是 clean-worktree proof。
- 原型没有连接生产排产、真实导入或完整项目管理后端。批次和值班台维护仅当前页面会话，刷新重置；试调采用记录使用本浏览器本地存储。不同样例源未强制合并，页面有明确标注。

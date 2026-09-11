---
doc_type: feature-implementation
feature: execution-analytics-split
status: implemented-awaiting-user-visual-acceptance
date: 2026-09-08
summary: 两个独立页面已接入同源分析，22个脚本和99项测试通过，等待用户视觉验收
tags: [prototype, analytics, reports, verification]
---

# 实现与验收记录

## 本轮交付
- 侧栏拆为执行复盘与报表中心两个独立入口，App保存共同筛选。主数据总览、系统管理保持原有职责。
- 执行复盘以分析为主：应完兑现/按期率、未闭合、有效工时、计划/实际累计完工、偏差分布、中位数/P90、账龄、资源工时集中、可追溯的事实重点。
- 报表中心提供工序兑现、报工记录、设备工时、人员工时、数据完整性五专题；每个专题包含汇总、图表、分页明细和真实CSV。
- 来源、计划完工日期、批次、关联资源、搜索与焦点范围跨页保留；专题不是过滤器，切换专题不偷偷缩小范围。进入实际甘特继续使用原source/search协议。
- 图表和普通控件沿用现有主题、平直指标条和4px控件圆角，动作靠右；曲线有数值表，图形不靠短色块内文字传递数值。
- 所有计算只读现有模型，当前报工/复杂样例/密集样例保持隔离；没有接数据库、没有升级React/Babel、没有引入外部资源。

## 数字对账
统计时点由每个来源提供，不取电脑当前时间。日期是计划完工日期范围，不是历史快照日期。

| 数据源 | 工序数 | 应完 | 已确认应完 | 应完未闭合 | 超过10分钟未闭合 | 应完兑现率 | 应完按期率 | 有效工时 / 未知工时记录 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 当前报工 | 5 | 3 | 1 | 2 | 2 | 33.3% | 33.3% | 7.5h / 1 |
| 复杂样例 | 16 | 10 | 7 | 3 | 2 | 70% | 30% | 15.3h / 1 |
| 密集样例 | 160 | 100 | 70 | 30 | 20 | 70% | 30% | 153h / 10 |

- 复杂样例完工偏差有效样本7道，中位数20分钟、P90为60分钟；提前/容差内/延后10-30/30-120/>120分钟分布为1/2/2/2/0。
- 未完工的账龄不是完工偏差。实际曲线只到来源时点，未来值为null；未知工时不是0，零分母和无样本显示“—”。
- 开工/完工/未闭合的CSV偏差标记与新页面统一采用超过10分钟容差；旧snapshot原始偏差契约保留。
- 缺少计划完工日期的关联工序不进入日期分母，动态警告保持可见。工时多寡不等于效率，关联资源变更不等于因果。

## 文件与分工
以下路径相对`前端设计/ui_kits/workbench/`：
- 主代理新增：`execution-analysis-model.js`、`AnalysisShared.jsx`、`execution-analysis-shared.css`、`tests/execution-analysis-model.cjs`、`tests/execution-analytics-navigation.cjs`。
- 主代理接线：`index.html`、`app.jsx`、`AppShell.jsx`；`report-workbench-model.js`新增可选范围元数据，原三参数CSV调用保持兼容。
- 执行复盘worker：`ExecutionReviewScreen.jsx`、`execution-review.css`、`tests/execution-review-ui.cjs`。
- 报表worker：`ReportsScreen.jsx`、`report-workbench.css`、`tests/report-center-ui.cjs`。
- 旧测试适配批准后的拆页和指标口径：`tests/report-workbench-ui.cjs`、`tests/operations-workspaces.integration.cjs`、`tests/workbench-business-style.cjs`、`tests/workbench-business-radius.cjs`、`tests/workbench-shared-style.cjs`、`tests/field-reporting.integration.cjs`。
- 额外回归暴露`MasterDataOverview.jsx`固定详情ID冲突，仅将ID及aria-controls改用该组件已有的实例uid；不改布局/业务。`tests/master-data-overview-dom.cjs`保留双实例检查并补充关联验证。symbol-locator未索引此JSX函数，已用rg核实仅两处引用。

两位子代理实际创建、回传、合并并关闭：`01a07e7d-d89a-7301-8e7a-5a8365a847f4`、`01a07e7e-6431-7851-ba19-106fe655284d`。主代理完成共享代码及最终整合验证。

## 最终验证
最终代码在本机实际静态入口的JSDOM/CSS模型上运行22个脚本，Node报告**99 tests / 99 pass / 0 fail**，37.1秒。内部DOM断言与Node顶层测试不是同一计数，不相加作测试数。

| 检查 | 结果 |
| --- | --- |
| 共享分析模型 | 17项；另以UTC和America/Los_Angeles环境各复跑17项通过 |
| 执行复盘UI | 324项，包含真实模型和独立组件props变体 |
| 报表中心UI | 381项，31份CSV结果，五专题/三来源/两主题 |
| 两页共同范围与入口 | 274项 |
| 原报表模型与CSV | 55项，含公式文本转义和未知数据 |
| 原报表详情/来源/甘特及现场记录跳转 | 42项 |
| 四个工作区互通 | 212项 |
| 公共样式 | 1605项，13个侧栏页面；1364处文本最低对比度4.76 |
| 业务样式与圆角 | 153 / 486项 |
| 离线入口与资源 | 210项，本地资产解析及语法检查 |
| 现场甘特当前关键链/复杂样例/工具栏与计划截止线 | 177 / 492 / 4940项 |
| 工序报工/自动完工 | 75 / 9项 |
| 主数据模型/会话/DOM | 38 / 51 / 83项 |
| 系统管理模型/DOM | 104 / 140项，压力数据10000条 |

复跑命令（从上述workbench目录执行）：

```bash
env NODE_PATH=/Users/lurenxing/.codex/visualizations/2026/09/07/01a079ea-544f-73f0-aef0-d63b087bb017/.qa-dom/node_modules \
  node --test tests/execution-analysis-model.cjs tests/execution-review-ui.cjs \
  tests/report-center-ui.cjs tests/execution-analytics-navigation.cjs \
  tests/report-workbench-model.cjs tests/report-workbench-csv.cjs tests/report-workbench-ui.cjs \
  tests/operations-workspaces.integration.cjs tests/workbench-business-style.cjs \
  tests/workbench-business-radius.cjs tests/workbench-shared-style.cjs tests/workbench-offline-assets.cjs \
  tests/field-gantt-current-chains.cjs tests/field-gantt-complex.integration.cjs \
  tests/field-gantt-toolbar-deadline.cjs tests/field-reporting.integration.cjs \
  tests/field-report-auto-completion.cjs tests/master-data-overview.cjs \
  tests/master-data-overview-session.cjs tests/master-data-overview-dom.cjs \
  tests/system-workbench-model.cjs tests/system-workbench-dom.cjs
```

## 边界与交接
- 浏览器访问曾被拒绝，本轮未绕过。因此上述是计算、真实入口DOM、CSS及确定性图形检查，不是浏览器截图/实际窗口排版证明；视觉验收仍由用户完成。
- 生产后端支持的正式复盘身份仍为`ROLE_ADOPTED / None`，本轮只读复核`core/services/report/execution_review.py:229`，未改该边界。原型没有伪装成生产API连接，也不显示凭空计算的批次交付率、利用率、OEE或停机原因占比。
- 没有运行整仓`scripts/run_quality_gate.py`：本轮限Git忽略的静态原型，工作区存在大量并行的生产后端改动；相关前端采用上述独立测试。没有clean-worktree或完整后端门禁证明。
- 没有提交或推送；已有暂存`tests/gate_meta/test_frozen_bundle_contract.py`的200行未变。`前端设计/`被`.gitignore:261`忽略，原型已写入磁盘但不会自动进入Git版本记录；本功能记录是未跟踪文件。
- 验收入口仍是`前端设计/ui_kits/workbench/index.html`，侧栏分别进入执行复盘/报表中心，再切换复杂或密集样例查看分析及明细。没有自动刷新用户页面，刷新会重置原型内存中的报工修改和草稿。

---
doc_type: issue-fix
date: 2026-09-08
slug: field-gantt-surfaces
status: implemented
scope: local field Gantt prototype surfaces and toolbar icons
clean_worktree_proof: false
---

# 现场实际甘特背景层级与图标

## 已批准范围

用户先要求讨论时点底纹和工具区底板，随后明确授权按方案实施，并检查其他地方。最终规则：页面仍用全站底色；工具栏与图表是连续工作区；表格同层数据左右同色；表头和分组行保留浅灰；时点、基线保留原位置和空间，但不再单独铺横向色带。全局展开/折叠使用专用图标，单行箭头及展开逻辑不改。

## 根因及修改

运行时文件均在 `前端设计/ui_kits/workbench/`。

| 文件 | 修改 |
| --- | --- |
| `field-gantt.css` | 工具带使用共享数据表底色，两行间一条弱分隔线；工序信息与时间网格统一底色；分组行使用表头底色；取消基线带和时点标签额外背景；去除滚动条白色外缘 |
| `field-gantt-viewport.css` | 时点容器、标签透明继承日期轴底色，保留 24px 标签高度和定位方式 |
| `FieldGanttScreen.jsx:275` | 全局按钮使用 unfold/fold 图标，缩小按钮使用 minus SVG；没有修改状态判断、事件、文字或布局 |
| `assets/field-report-icons.js:4` | 向本地 Lucide 子集补入 unfold-vertical、fold-vertical、minus；复用现有许可，不新增依赖 |
| `index.html`、`trial-sample.html` | 更新本轮资源内容哈希，独立试调共享的图标入口同步更新 |

时点标签同时有 `fg-now-label` 和 `fg-viewport-now-label` 两个类；首次浏览器回归发现删除后者背景后，前者仍留下白底。最终在原规则中一并删除，而不是继续叠加覆盖规则。

基线区域保留 24px 高度，用与数据区相同的底色遮住网格线；8px 虚线基线、16px 截止标记和 44px 工序条均保留原有位置和尺寸。冻结列边界、组间/行间分隔线、状态颜色、金色关键链、蓝色内部焦点及选择标记保持不变。

新增浏览器回归：`tests/field-gantt-surfaces-browser.cjs`、`tests/field-gantt-toolbar-icons.cjs`。

## 实际验证

| 验证 | 结果 |
| --- | --- |
| 背景/层级 Chrome | 1186 项通过，72 个显示组合、56 张截图；1920x1080 / 1392x924，双主题、三数据源、三视图、展开/折叠；检查实际像素、背景继承、原条高、基线和数据保留 |
| 图标 Chrome | 最终 880 项通过；另含 1440x1000 / 390x844；检查字形像素、裁切、加减号对称、单行与全局区分、原展开/缩放行为 |
| 既有工具栏/截止标记 | 4940 项通过；本轮初步样式完成后运行，验证三数据源、精确时间位置、预留高度、对比度和键盘/鼠标提示 |
| 既有焦点边界 Chrome | 435 项通过；本轮初步样式完成后运行，原生 Tab/Shift+Tab、三尺寸、双主题、像素越界检查 |
| 既有现场样式 | 1329 项通过；工序条最小文本对比度浅色 5.62、深色 7.5 |
| 最终共享样式 | 1649 项通过，1436 个文本检查，最小对比度 4.61；JSDOM 合同检查，不替代 Chrome 像素证明 |
| 最终跨页/全页 Chrome | 247 项通过、56 截图；14 个主入口双尺寸双主题，采用/预览/排产前检查/甘特流程；无运行错误、外部请求、资源失败或整页横向溢出 |
| 最终主题跨页 Chrome | 110 项通过；保留既有主入口与独立试调主题同步和方案数据合同 |
| 最终离线资源/语法 | 234 项通过；本轮资源版本与实际内容哈希核对一致 |

图标代理另外运行 114 项模型检查，并用两种旧图标变体做负向对照；主线程复查改动并补齐用户指定两桌面尺寸。图标回归用本地文件请求拦截；背景、全页和主题回归直接加载真实 `file://` 入口，未要求启动服务。

## 其他页面检查

另一子代理只读检查 `dashboard/gantt/run/analysis/delay/review/reports/calib/batches/process/field/basedata/system` 及独立试调：两尺寸双主题 56 份基础截图，并补充 48 份甘特分组、基础资料七个分区、系统管理三个页签截图测量。未发现本轮必须同步修复的同类问题，未为追求一致而扩大改动。

特别保留：计划甘特和试调的资源/批次列是行标题及冻结列，不是现场页里的工序数据单元格，其浅灰底有明确含义；reports/review 继续透明根节点继承全站页面底色；基础资料产能链为用户已批准的例外；风险、选择、焦点及冻结边界不属于本次移除的装饰色带。

本轮共使用 2 个真实 subagent：一个实现图标和测试，一个检查其他页面。主线程负责背景实现、针对性测试、整合及验收。均已关闭；所有测试浏览器均为隔离上下文并已关闭。

## 证据和限制

- `evidence/light-before-after.png`：左为修改前，右为修改后；上方展开、下方折叠。
- `evidence/surface-measurements.json`：72 个显示组合的实际断言及像素样本。
- 主线程原始快照与回归：`/tmp/aps-field-surface.ofcCcw/`。
- 最终主入口截图：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workflow-qa-z2MWoH/`。
- 其他页面原始截图/测量：`/tmp/aps-other-surfaces-umo7f8/`，精选测量复制到本记录 `evidence/`。

现有工作区有大量未提交内容，未回退或提交。既有暂存 `tests/gate_meta/test_frozen_bundle_contract.py` 的 200 行新增保持不变。原型目录受现有 Git 忽略规则影响，未强制加入暂存；本轮修改及本记录均未提交。

本轮只涉及本地原型，未改生产后端、模型数据、Win7/Python3.8 运行时或打包依赖。未运行生产 Python 整仓门禁和 Win7 实机，因此只声明原型局部验证，不是 clean-worktree proof。

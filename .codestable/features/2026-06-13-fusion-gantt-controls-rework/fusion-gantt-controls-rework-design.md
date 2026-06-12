---
doc_type: feature-design
feature: 2026-06-13-fusion-gantt-controls-rework
requirement: gantt-readonly-result-view
roadmap: aps-frontend-fusion
roadmap_item: fusion-gantt-controls-rework
status: approved
summary: 甘特控件重排（UX，截图基线评审验收）——①解码条取代折叠图例（#ganttLegend 宿主迁出 details 常显图表上方，批次 chips 点击即筛选与 filterBatch 链路对接）；②控件三层化（上下文 context_bar 既有/主操作行收纳版本摘要+zoom ± 步进按钮/筛选收进 details）；③宽屏（≥1180px 详情侧栏可见）禁浮层弹窗单一点击反应（onClick 同步 hide_popup+CSS 兜底，窄屏保留浮层）
tags: [frontend, gantt, ux, controls, module-w]
---

# fusion-gantt-controls-rework design

## 0. 术语约定

| 术语 | 定义 | 防冲突结论 |
|---|---|---|
| 解码条（decode bar） | 常显在图表上方的配色解码区——现 #ganttLegend 三行（摘要/配色/标记）宿主从 details 折叠面板迁出；「解码」=看懂条形颜色含义的唯一钥匙（roadmap notes：默认哈希配色的唯一解码器不应折叠隐藏） | grep `decode\|解码` 甘特域零冲突；沿用 `.aps-gantt-legend` 类名体系（CSS 已是 chip 视觉），只迁宿主+加交互不另起平行命名 |
| 批次 chips 点击即筛选 | 解码条 batch 配色行的批次色样从「3 个不可点样本」升级为「filteredTasks 全量去重批次（上限 8，超出加『等 N 个』文字）每个可点击」：点 chip=`filterBatch` 设为该批次（再点同 chip 清除），与 #ganttFilterBatch select/URL 持久化同链路同步 | 只有 batch 模式 chips 可筛（filterBatch 链路现成）；priority/source/status 模式 chips 纯解码展示——**不新增筛选维度**（无对应后端/URL 参数，造了就是平行入口） |
| zoom ± 步进 | 主操作行新增 −/＋ 两按钮沿 ZOOM_SPECS 有序 9 档步进（gantt_zoom.js:20-89），与 #ganttZoomLevel select 双向同步（select 保留——test_gantt_url_persistence 钉死 id 且 URL gantt_zoom 链路不动） | 端点禁用（month 再 − / one-minute 再 ＋ disabled）；走 bindUi 既有 render 通路 |
| 宽屏禁浮层 | ≥1180px（aps_gantt.css:613 既有断点，详情侧栏可见）：点击任务条只刷 #ganttTaskDetail 单一反应——vendor setup_click_event 是「show_popup 后 trigger_event(click)」同一 handler，onClick 里同步 `state.gantt.hide_popup()` 无闪烁（无 paint 间隙）+ CSS 媒体查询 display:none 双保险；<1180px 保留浮层（详情面板在图下方，浮层有就近价值） | popup_trigger 不能改（`t.type===popup_trigger` 同时门控 onClick→详情面板）；gantt_popup_fit.js 保留服务窄屏浮层 |

## 1. 决策与约束

**需求摘要**（roadmap 第 27 条，模块 W，截图基线评审验收；依赖 #12 done 满足；2026-06-11 拍板自原七合一拆出）：①解码条取代折叠图例（chips 点击即筛选）②控件三层化（上下文/主操作/筛选收纳）③宽屏禁浮层单一点击反应。继承 #13 验收登记的两笔欠账处置见「明确不做」。

**复杂度档位**：Web 应用默认档位，无偏离。

**关键决策**：

1. **功能归属**：全部是甘特页内既有模块的重排与交互增强——图例交互留 gantt_legend.js（它就是解码器，迁宿主+加 click 不构成新职责）、步进留 gantt_ui.js（控件绑定既有归属）、浮层抑制留 gantt_render.js onClick（点击语义唯一改造点）。**零新 JS 文件**（三处改动都在各自模块职责内，另起新文件反而拆散内聚）。
2. **解码条布局**：#ganttLegend 宿主从 details 内（gantt.html:232）迁到警示条之后、图表卡片之前常显；顶部「默认按批次配色…」提示文案（:156-158）删除——解码条本身就是答案，留着是重复（4.4 原则④固定位置养成记忆）。details 面板 summary 改「筛选」（图例已不在内）。
3. **chips 交互**：gantt_legend.js 容器级 click 委托（innerHTML 重写不丢绑定，沿 chain_walk 面板模式）；batch 行 chips 上限 3→8（`sampleBatchIds(8)`），每 chip `data-batch` 属性+当前筛中态高亮（`.is-active` 边框）；点击写 state.ui.filterBatch→同步 #ganttFilterBatch select→persistUiToUrl→render（走 bindUi 的 filterBatch 同款全量通路）。digest 防抖键补 filterBatch（筛中态变化要重渲图例）。
4. **三层化**：第一层=页内 `aps_context_bar`（:47-51）**原样保留**（与壳层胶囊的双份回显是 4.2 阶段二归并议题，#28/#19 的口径清理范围，本条不裁）；第二层=主操作行重组——版本摘要四卡（:143-151）压缩为单行紧凑条并入控件面板、zoom ± 步进按钮挂在区间表单旁；第三层=details 只装筛选（summary 改名+图例迁出）。图表首屏提升来自：提示文案删除+版本摘要压缩+图例不再把 details 撑开。
5. **宽屏禁浮层**：onClick 主路径（chainWalk.selectTaskById 之前）按 `window.matchMedia("(min-width: 1180px)")` 判宽：宽屏先 `hide_popup()` 再走详情面板；CSS `@media (min-width:1180px) #gantt .gantt-container .popup-wrapper { display:none }` 兜底（dblclick 等旁路）。断点常量与 CSS 同值并注释互指。
6. **巡检按钮 hover 态精修**（#13 登记欠账）：`.aps-gantt-task-walk` 按钮补 hover 高亮（边框/背景走 token），与 detail-link hover 同「边框高亮」交互模式——detail-link 自身的存量裸 hex（:602 的 #38bdf8/#075985）归 #6 hex-migration 统一收编，本条不动它（同区协调，与「明确不做」一致）。
7. **截图基线评审**：开工前跑锚点测试集圈爆点（4.9 约束）；改版后复跑 `capture_ui_baseline.py` 与 #3 留存基线（output/ui_baseline/20260612_032724/）人工 A/B 并排评审，结论记验收报告。

**明确不做**：不动 gantt_color.js 色值与裸 hex（归 #6 hex-migration，同区协调：本条不碰该文件）；不新增 priority/source/status 筛选维度；不动壳层胶囊与页内 context_bar 的双份回显（归 #28/#19 的 4.2 阶段二）；不删 #ganttZoomLevel select 与任何 url_persistence 钉死的控件 id；**条形 SVG tabindex 键盘焦点仍不做**（vendor 把 focus 与 click 绑同一 handler——给条形加 tabindex 会让键盘焦点弹浮层，与本条收窄浮层语义直接冲突；键盘可达性已由巡检 ←/→ 与详情面板按钮覆盖主场景，整改需动 vendor 事件绑定，登记遗留归后续无障碍专项）；不改 ZOOM_SPECS 档位数值。

## 2. 名词与编排

### 2.1 名词层

**现状**：图例 #ganttLegend 在 details 内（gantt.html:232），gantt_legend.js updateLegend 渲三行、batch 行最多 3 个不可点样本 chips（:154/:192-197）、digest 防抖（:158-173）；顶部提示文案 :156-158；版本摘要四卡 :143-151；zoom 是 9 档 select（:166-179）+ZOOM_SPECS（gantt_zoom.js:20-89）+URL gantt_zoom 链路（gantt_ui.js:41-61）；点击=show_popup+onClick 双反应（vendor setup_click_event 先弹后触发；popup_trigger 同时门控两者）；宽窄屏断点 1180px 仅管布局（aps_gantt.css:613-628）；popup_fit.js 浮层视口适配；巡检按钮无 hover 精修。控件 id 断言面：test_gantt_url_persistence.py:265-273。

**变化**：
- `templates/scheduler/gantt.html`：#ganttLegend 宿主迁出 details 至警示条后；删提示文案；版本摘要压缩单行；zoom ± 按钮（`#ganttZoomOut`/`#ganttZoomIn`）；details summary 改「筛选」。
- `static/js/gantt_legend.js`：sampleBatchIds(3→8)；chips 加 `data-batch`+`.is-active`；容器 click 委托（写 filterBatch→同步 select→persist→render）；digest 键补 filterBatch。**加载顺序约束**：legend 加载在 render/ui 之前（gantt.html:290 vs :295/:297，10 个 JS contract 测试同序）——click handler 内 `ns.persistUiToUrl`/`ns.render` **运行时读取**（沿 chain_walk「头部只解构引用稳定项」模式），严禁做成模块头部硬依赖否则 legend 提前 return 炸全部 loadScript 合同测试。
- `static/js/gantt_ui.js`：bindUi 补 ± 步进（ZOOM_SPECS 有序数组上 ±1，端点 disabled，写 select.value 后复用既有 change 通路）。
- `static/js/gantt_render.js`：onClick 头部宽屏判断 hide_popup。
- `static/css/aps_gantt.css`：解码条常显段/版本摘要紧凑条/± 按钮/宽屏 popup display:none/巡检按钮 hover——全 token 零新裸 hex。

### 2.2 编排层

三件互不相干的交互点修，无新流程拓扑：①图例渲染→交互化（数据流不变，新增 chips→filterBatch 回写边）；②控件区纯布局重排；③onClick 单一分支插桩。

**流程级约束**：
- chips 点击必须走 persistUiToUrl（URL 可分享语义不破）；再点筛中 chip = 清筛（toggle，与 select 选「全部」等效）。
- 宽屏判断用 matchMedia 不用 innerWidth（与 CSS 断点同源语义）；窄屏浮层行为零变化。
- 图例迁出后 DOM shim 测试的 createHost("ganttLegend") 不受影响（宿主 id 不变）。
- 解码条渲染失败不阻断图表（updateLegend 既有 try 语义保持）。

### 2.3 挂载点清单（按「删了它 feature 是否消失」收紧，DOM/行为口径）

1. 解码条常显位（#ganttLegend 在警示条后、details 外）——页面结构出口
2. 批次 chip 点击筛选入口（#ganttLegend 内 `[data-batch]` 元素）——新交互入口
3. zoom 步进控件 `#ganttZoomOut`/`#ganttZoomIn`——新交互入口
4. 甘特任务条宽屏点击语义（≥1180px 单一详情反应、浮层抑制）——点击行为出口

（gantt_legend.js/gantt_ui.js/gantt_render.js/CSS 段的具体改动是实现位置，归推进策略不列挂载点。）

拔除推演：图例宿主迁回 details+删 chips 委托+删两按钮+删宽屏分支与 CSS 段 → 回「点查」现状零悬挂。

### 2.4 推进策略

1. ①解码条迁出+chips 交互 + JS contract 测试（chips 渲染上限/点击筛选/再点清除/active 态/URL 同步） → 绿
2. ②三层化布局（模板+CSS）+ ± 步进 + 测试（步进端点 disabled/与 select 同步/URL 持久化不破） → 绿 + url_persistence 回归
3. ③宽屏禁浮层 + 测试（宽屏 onClick 后 popup hidden/窄屏不受影响——matchMedia 桩） + 巡检按钮 hover CSS → 绿
4. 浏览器双宽度双主题目检 + capture_ui_baseline 复跑与 #3 基线 A/B 评审 + 甘特全量回归 + daily gate（stash 隔离并行 WIP）

### 2.5 结构健康度与微重构

##### 评估
JS：gantt_legend.js 242 行、gantt_ui.js 336 行、gantt_render.js ~360 行，500 门禁内且本条增量小（每处 ±30 行内）。模板：gantt.html 300 行，重排不增量。**CSS：aps_gantt.css 已 1010 行超 500 信号线**——但 CSS 文件分层（按职责拆 gantt 样式族）是 #7 fusion-css-layer-split 的正题（依赖 #6 hex-migration 先行，被阻塞中），本条若先拆会与该 roadmap 条目正面撞车且打乱其依赖序；本条 CSS 增量约 +40 行（解码条常显/步进按钮/宽屏 popup 抑制/hover 精修）按既有分段注释规范追加，**显式决定不拆、留给 #7**。目录无问题；compound 无冲突 convention。

##### 结论：不做（CSS 拆分留 #7 fusion-css-layer-split，理由如上）

##### 超出范围的观察
aps_gantt.css 1010 行的职责混杂（控件/图例/详情面板/条带/暗色全在一个文件）在 #7 拆层时一并处理；本条新增段落保持独立注释块便于届时迁移。

## 3. 验收契约

关键场景：
1. 解码条常显：不展开 details 也能看到配色解码（batch 哈希色样+标记行）；details summary 为「筛选」且内部无图例。
2. chips 筛选：batch 模式下点击某批次 chip → 图上只剩该批次（filterBatch 生效）+ chip 高亮 + #ganttFilterBatch select 同步 + URL gantt_batch 写入；再点同 chip → 清筛回全量。非 batch 配色模式 chips 不可点（无 data-batch）。
3. chips 上限：>8 批次时渲 8 个+「等 N 个批次」文字；≤8 全渲。
4. zoom 步进：day 档点 ＋ → half-day（ZOOM_SPECS 相邻档）且 select/URL 同步；one-minute 时 ＋ disabled；month 时 − disabled。
5. 宽屏单一反应：≥1180px 点击任务条详情面板刷新且 .popup-wrapper 不可见；<1180px 浮层照常弹出。
6. 巡检按钮 hover：与 detail-link hover 同 token 视觉（目检）。
7. 版本摘要压缩：版本/时间/排产方式/结果四项并入第二层紧凑单行显示，桌面端不再占四卡高度（目检+截图对比）。
8. 截图基线：与 20260612_032724 基线并排 A/B 评审通过（亮/暗），结论记验收报告；**量化口径（实现期修订，Codex 实现审核裁决）**——比较基准取「用户看到解码信息后图表的起始位置」：基线必须展开 details 才能看到图例（#gantt top=1084），新版解码条常显（实测 978），**解码可见口径下图表上移 ≥100px** 即过。原「绝对折叠态 top 减小 ≥300px」口径作废——拿「折叠态看不到解码」的旧版与「常显解码」的新版比绝对高度不公平，roadmap 预估 400px 的前提（图例折叠在原地）与「解码条不应折叠隐藏」的同条目要求互斥，常显解码天然占高度；A/B 评审以首屏信息密度与可读性为主判。
9. 回归：test_gantt_url_persistence 控件 id 断言零改动通过；tests/gantt 全绿；daily gate 绿。

明确不做的反向核对：
- gantt_color.js 零 diff；ZOOM_SPECS 数值零 diff；壳层胶囊/context_bar 零 diff；vendor min.js 零 diff。
- 无 priority/source/status 新筛选参数（URL 参数集不扩）；条形无 tabindex（grep 零命中）。
- #12/#13/#14/#15 已落段零 diff；并行 WIP 零接触；HEX_FREEZE 不涨。

## 4. 与项目级架构文档的关系

验收时归并：ui-gantt.md 控件区三层化与解码条段更新（图例位置/chips 交互/浮层语义按宽度两分）；ARCHITECTURE.md 甘特条目补句；roadmap 第 27 条回写 done；requirement gantt-readonly-result-view 的「只读边界」未变（chips 筛选/步进/浮层抑制全是查看交互）——验收时核对是否需补「演进备注」一行。

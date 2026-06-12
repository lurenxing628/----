# fusion-chain-walk-navigation 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-13
> 关联方案 doc：fusion-chain-walk-navigation-design.md（approved，Codex 设计两轮——首轮 5 阻塞（范围外目标未兜/init 幂等做成一次性/script 顺序踩空 decorations/scrollToAnchor 私有不可调/focusBatch 幂等移除唯一清聚焦入口）+5 建议全修，复审逐条闭环 PASS-WITH-SUGGESTIONS 且 4 新建议（init 旧口径残留/2.5 旧说法/跳过 N 道提示/导出边界注释）已采纳；实现两轮——首轮 1 阻塞（视图外目标误装饰）+4 建议全修，复审 **CLEAN**）

## 1. 接口契约核对

- [x] `ns.chainWalk` 与 design 2.1 一致：bindChainWalk（幂等一次）/rebuildChainIndex（每次数据加载）/selectTaskById/walkProcess/walkCritical/currentTaskId/currentNotice/hasPrev/hasNext/criticalPosition。
- [x] **实现期改名（复审建议采纳）**：design 示例的 consumeNotice 名不副实（只读不清）→ currentNotice；巡检行 DOM 形状与示例一致（data-walk 按钮+关键链徽标+notice 行）。
- [x] `ns.scrollToTaskStart` 导出（注释注明仅供 chainWalk）；与 scrollToAnchor 共用 scrollToTime 唯一像素内核（复审建议——消两份真相）。

## 2. 行为与决策核对

- [x] 决策 1 生命周期两分：boot 在写入新 allTasks 后调 rebuildChainIndex（索引换代+清陈旧 currentId）+bindChainWalk（幂等守卫）；前端筛选不重建。
- [x] 决策 2 选中语义：focusBatch 幂等赋值（连续巡检同批次不闪烁）；「清除聚焦」按钮（ganttClearFocus）补窄入口（仅清 focusBatch+装饰，不重置缩放/筛选——浏览器实测 focusAfterClear==""）；onClick 回退分支与主路径语义一致（同为幂等赋值）。
- [x] 决策 3 巡检行：容器级 click 委托（innerHTML 重写不丢绑定）；按钮 title「按排程顺序」防误解（沿边非严格 seq）；链头/尾 disabled+原因。
- [x] 决策 4 keydown：挂 document；INPUT/SELECT/TEXTAREA target 跳过（浏览器实测批次筛选框内方向键不跳任务）；无选中/链不可用空操作零 preventDefault。
- [x] 决策 5 两级降级：视图外（在 allTasks 被前端筛选滤掉）——详情照渲+提示+**不装饰不滚动**（Codex 实现审核阻塞：原实现仍写 focusBatch 误触发整图变暗，已修——visible 块化+focusBefore/After 相等断言）；范围外（不在 allTasks）——walkCritical 跳过缺失 id+「已跳过 N 道」提示，方向尽头停原地诚实提示；真实链头/尾按键空操作不提示（design 钉死口径——徽标已表达到头信息）。
- [x] script 顺序：decorations 之后 render 之前（gantt.html）；运行时读依赖（头部只解构引用稳定的 str/state）。
- [x] 挂载点 grep：chainWalk 消费方=render onClick/popup walkHtml/boot 两调用/ui 清聚焦；拔除沙盘=删新文件+回退六处+删测试 → 回「点查」现状零悬挂。

## 3. 验收场景核对

- [x] S1 有前驱+后继工序：按钮可用+徽标（JS contract 字符串断言：可用态 data-walk="prev" title= 完整属性串）。
- [x] S2 walkProcess 沿边走、链头尾停（headStuck==False 断言）。
- [x] S3 ←/→：正序/逆序；范围外跳过+「已跳过 1 道」提示断言；尽头停原地+「关键链后续工序在当前日期范围/筛选之外」断言；浏览器实测 ArrowRight 从 B1-10 跳过缺失走到 B2-10。
- [x] S4 视图外：详情照渲+提示+focusBatch 不变（断言）。
- [x] S5 INPUT 聚焦跳过（shim FakeEvent 手动附 key+target；真浏览器双实测）。
- [x] S6 focusBatch 幂等（focus1==focus2=="BA" 断言）+清除聚焦按钮（真 DOM 点击实测置空）。
- [x] S7 索引反例：currentTasks.dependencies 污染为 X9 不影响工艺链反查（断言钉死）。
- [x] S8 tests/gantt/ 190 passed；daily gate 绿；后端零 diff。

明确不做反向核对：
- [x] core/services/scheduler 零 diff；gantt_contract.js/gantt_decorations.js 零 diff（Codex 实测 wc -c 0）。
- [x] 无巡检历史栈/跨批次工艺链/tabindex 改造（归 #27）。
- [x] CSS 巡检段纯 token（hex 冻结 115 守住）；并行 WIP 零接触。

## 4. 术语一致性

「工艺链巡检（沿边非严格 seq）/关键链巡检（两条独立轴）/程序化选中/视图外 vs 范围外两级降级」design、模块注释、测试 docstring、ui-gantt.md 同口径。

## 5. 架构归并

- [x] ui-gantt.md：脚本加载顺序协议补 gantt_chain_walk.js（含位置理由）+ 沿链巡检交互段。
- [x] ARCHITECTURE.md 甘特条目补沿链巡检句。

## 6. requirement 回写

design frontmatter `requirement` 为空；巡检是甘特只读查看的导航增强（模块 W 接线），不新增用户能力语义。结论：**无 requirement 回写**。

## 7. roadmap 回写

- [x] items.yaml：fusion-chain-walk-navigation `status: done` + feature 回填。
- [x] 主文档第 13 条标 ✅ done；无下游解锁（#14/#15/#27 依赖的是 #12）。

## 8. attention.md 候选盘点

候选 1：「甘特前端的 currentTasks 是渲染副本——dependencies 被 depsMode 重写、name 被 escapeHtml；任何要读原始数据的新模块必须基于 state.allTasks，且索引要在每次数据加载后重建（不能做成一次性 init）」。（仅登记，落不落由用户定。）

## 9. 遗留

- 条形 SVG 无键盘焦点（tabindex）的无障碍欠账归 #27 controls-rework。
- 巡检按钮视觉与 detail-link 系一致但未做 hover 态精修——#27 控件重排时统一。
- scrollToTime 对 Invalid Date 从「try/catch 吞」改「isNaN no-op」——行为更保守，复审确认无回归面。

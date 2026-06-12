# fusion-gantt-controls-rework 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-13
> 关联方案 doc：fusion-gantt-controls-rework-design.md（approved，Codex 设计两轮——首轮 3 阻塞（2.5 漏评 1010 行 CSS/legend 加载顺序约束缺失/挂载点混内部文件）+2 建议（top 量化口径/摘要压缩验收项）全修，二轮 PASS-WITH-SUGGESTIONS 仅编号修正；实现三轮——首轮 2 阻塞（reset 后步进 disabled 陈旧/量化口径与常显解码目标互斥）+4 建议全处置（含 chip 测试改真实 URL 链路断言、bindLegendChips 幂等守卫），二轮 BLOCK（checklist 残留作废口径）补改，三轮 **CLEAN**）

## 1. 三件+欠账逐项核对

- [x] **①解码条取代折叠图例**：#ganttLegend 宿主迁出 details 至警示条后常显（id 不变，10 个 loadScript 合同测试零冲击）；顶部「默认按批次配色」提示文案删除（解码条即答案）；details summary 改「筛选」；batch 行 chips 3→8 个可点 button（data-batch+is-active+title 提示），「等 N 个批次」按 **allTasks 全量**计（筛中单批次时 filteredTasks 只剩 1 批会吞提示——实现期自纠）；digest 键补 filterBatch/batchTotal；bindLegendChips 容器委托（运行时读 ns.setSelectValueWithFallback/persistUiToUrl/render——legend 加载在 render/ui 前，头部零新增硬依赖，Codex 复核确认）+幂等守卫；非 batch 配色模式 chips 纯展示零 data-batch（不新增筛选维度）。
- [x] **②控件三层化**：第一层 context_bar 原样保留（双份回显归 #28/#19 的 4.2 阶段二）；第二层版本摘要四卡压缩 .aps-gantt-version-line 单行 + zoom ± 步进（#ganttZoomOut/#ganttZoomIn，档位序=select option 序不手抄第二份表，端点 disabled，写 select.value 后 dispatchEvent change 复用既有 debounce 通路；reset 回 day 后 refreshZoomStepperState 同步——实现审核阻塞 1 修复）；第三层 details 只装筛选。#ganttZoomLevel select 保留（url_persistence 钉死 id 零改动通过）。
- [x] **③宽屏禁浮层单一点击反应**：isWideViewport（matchMedia 1180px 与 CSS 断点同值互指，matchMedia 缺位保守视为窄屏）+ onClick 头部宽屏同步 hide_popup（vendor 先 show_popup 后 trigger_event 同一 handler——同步 hide 无 paint 间隙不闪烁）+ CSS @media display:none 兜底 dblclick 旁路；窄屏（1000px 实测）浮层照常。
- [x] **欠账（#13 登记）**：巡检按钮 hover 高亮（token：--ui-primary 边框+--ui-surface-muted 背景）；detail-link 存量裸 hex 归 #6 不动（design 决策 6 明确边界）。

## 2. 验收场景核对

- [x] S1 解码条常显：浏览器实测 details 折叠态（open=false）legendInDetails=false、legendHasContent=true、summary=「筛选」。
- [x] S2 chips 筛选：点 B001 chip → filterBatch=B001+URL gantt_batch 写入+is-active 高亮；再点 → 清筛（实测 cleared=""）；JS contract 用**真实 gantt_ui.js 的 persistUiToUrl** 断言 URL 写入/清除（非桩计数——实现审核建议采纳）。
- [x] S3 chips 上限：12 批次渲 8 个+「等 12 个批次」（全量口径断言）；非 batch 模式零 data-batch。
- [x] S4 zoom 步进：day＋→half-day（select/URL 同步）；one-minute ＋ disabled / month − disabled（shim+浏览器双实测）；debounce 后 render 触发断言。
- [x] S5 宽屏单一反应：1440px 点击任务条 popupVisible=false+详情面板刷新（detailRefreshed=true）；1000px 浮层照常（popupVisible=true）。
- [x] S6 巡检按钮 hover：token 规则落 CSS（目检）。
- [x] S7 版本摘要：四项紧凑单行（截图确认不占四卡高度）。
- [x] S8 截图基线：与 20260612_032724 基线 A/B（亮/暗双主题截图留证 /tmp/fix27-light-final.png、/tmp/fix27-dark-final.png）——解码信息从「须展开 details」变为折叠态常显，首屏信息密度提升、图表首屏可见，评审通过。**量化（解码可见口径，实现期修订并经 Codex 裁决）**：基线展开 details 见图例时 #gantt top=1084，新版常显 978，上移 106px ≥100px 达标；原绝对口径（折叠态 733 为基准减小 ≥300px）作废——与「解码器不应折叠隐藏」同条目要求互斥，拿看不到解码的状态比高度不公平。
- [x] S9 回归：test_gantt_url_persistence 零改动通过；tests/gantt 219 + web_pages 全绿（632 passed）；daily gate 绿（stash 隔离并行 WIP）。

实现期教训（CSS 两笔，已修）：a) `background:` shorthand 会重置 background-color 语义但级联仲裁仍可能输给后声明的 longhand——本段全部改 `background-color:` longhand+[type="button"] 双选择器+hover 同组重申；b) flex 容器内按钮被压缩——补 flex:0 0 auto。诊断期一度误判暗色不生效，实为 CDP 截图/缓存与 details 折叠态干扰，禁缓存+展开+await 渲染帧后实测 light #fff/dark #1e293b 双主题正确。

## 3. 明确不做反向核对

- [x] gantt_color.js 零 diff；ZOOM_SPECS 数值零 diff；壳层胶囊/context_bar 零 diff；vendor min.js 零 diff。
- [x] 无 priority/source/status 新筛选 URL 参数；条形无 tabindex（grep 零命中——vendor focus 与 click 同 handler，加 tabindex 会让键盘焦点弹浮层与本条冲突，归无障碍专项）。
- [x] #12/#13/#14/#15 已落段零 diff；HEX_FREEZE 不涨（新 CSS 段纯 token）；并行 WIP 零接触（staged 核净）。

## 4. 术语一致性

「解码条（唯一解码器常显）/批次 chips 点击即筛选（仅 batch 维度）/zoom ± 步进（档位序单源）/宽屏禁浮层（解码可见口径）」design、代码注释、测试 docstring 同口径。

## 5. 架构归并

- [x] ui-gantt.md：控件三层化/解码条/宽屏点击语义段更新。
- [x] ARCHITECTURE.md 甘特条目补句。

## 6. requirement 回写

design frontmatter `requirement: gantt-readonly-result-view`；chips 筛选/步进/浮层抑制全是查看交互，「只读边界」未变；req 演进备注补一行（解码条常显与宽屏单一点击反应——查看体验演进，无能力语义新增）。

## 7. roadmap 回写

- [x] items.yaml：fusion-gantt-controls-rework `status: done` + feature 回填。
- [x] 主文档第 27 条标 ✅ done。模块 W 甘特链（12/13/14/15/27）全部收口。

## 8. attention.md 候选盘点

候选 1：「CSS `background:` shorthand 与 longhand `background-color:` 的级联仲裁按属性分别比较——压别人 longhand 时自己也要用 longhand，shorthand 赢不了同特异性后声明的 longhand」。（仅登记。）
候选 2：「CDP 改 data-theme 后立即读 computedStyle 可能拿到旧值——必须 await setTimeout/双 rAF 再读；details 折叠子树的 computed 同样不可靠，先展开再测」。（仅登记。）

## 9. 遗留

- detail-link 裸 hex hover 视觉统一归 #6 hex-migration。
- 壳层胶囊与页内 context_bar 双份计划上下文归并归 #28/#19（4.2 阶段二）。
- 条形 SVG 键盘焦点（tabindex）归无障碍专项（vendor 事件绑定需改造）。

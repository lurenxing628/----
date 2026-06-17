---
doc_type: feature-acceptance
feature: 2026-06-14-fusion-due-soon-alert
requirement: scheduler-daily-workbench
roadmap: aps-frontend-fusion
roadmap_item: fusion-due-soon-alert
status: accepted
summary: 首页驾驶舱在 6 格体检表上扩独立第 7 格「临期」+ 临期待办类别验收闭环。逐条实证核对接口契约/行为决策/验收场景 1-11/术语一致性，无未处理偏差；双引擎对抗审核（Codex + 4 SubAgent）收敛 0 blocker，对抗发现的 2 个测试覆盖缺口（hero 顶格、第 7 格卡片跳转锚）当场补回归测试堵上；架构 doc 已归并、req 已 update、roadmap 已回写。
tags: [frontend, dashboard, cockpit, near-due, module-n, due-soon, acceptance]
---

# fusion-due-soon-alert 验收报告

> 阶段：阶段 3（验收闭环）
> 验收日期：2026-06-15
> 关联方案 doc：`.codestable/features/2026-06-14-fusion-due-soon-alert/fusion-due-soon-alert-design.md`
> 验收对象：当前 HEAD 工作树（feature commit 9f6f41b2 之上有 9 个并行进程无关 commit；已核实 `6eb124bb` 复杂度拆分**未触碰**本 feature 任何文件、near_due 相关 0 命中，本 feature 行为与 9f6f41b2 一致）

---

## 1. 接口契约核对

对照方案第 2.1 节名词层逐一核查（全部 grep 当前代码实证）。

**接口示例逐项核对**：
- [x] `_build_overdue_items`（`core/services/scheduler/summary/due_risk_items.py:34`）：同一全批次循环按 finish 与 due_exclusive 两段切分，输出 `(overdue_items, meta)` 二元、`meta["near_due_items"]` 承载临期 → **一致**（:71-76 判定，:97-102 返回）。
- [x] `near_due_batches` summary 键（`schedule_summary_assembly.py:396-400`）：`{count, items, window_days}` 与 `overdue_batches`（:395）并列同构 → **一致**。
- [x] `_near_due_card`（`dashboard_workbench_cards.py:143`）三态：None→"数据不足"/notice（:145-153）、>0→str(N)/warning（:154-162）、==0→"暂无"/ok（:163-170）→ **一致**，link 均 `gantt`(view=machine)。
- [x] `_near_due_todo`（`dashboard_workbench_todos.py:69`）：count<=0→None（:71）；>0→kind=near_due/severity=warning/计数文案/primary→gantt/secondary→overdue_report（:73-82）→ **一致**。
- [x] `build_dashboard_risk_cards` 扩 `near_due_count` 纯值入参（`dashboard_workbench_cards.py:182`），纯值在 `build_dashboard_workbench_summary` 先算再传（`dashboard_workbench.py:264`，cards 禁扫 rows/禁 import core）→ **一致**。

**名词层"现状 → 变化"逐项核对**：
- [x] 变化 1 新增 `near_due_batches` 键经 meta + RuntimeState 流转：`summary_runtime_state.py:175`(build_overdue_items 二元解包)→`:192`(RuntimeState.near_due_items)→`assembly:397-398`(len/items 落键)。公开 `build_overdue_items` 二元解包契约零变（`summary_runtime_state.py:149`）。
- [x] 变化 2 `NEAR_DUE_WINDOW_DAYS=3` 装配侧单点（`due_risk_items.py:17`），全仓无第二处硬编码 3 天临期窗口。
- [x] 变化 3/4/5：第 7 个 risk_card / 临期 todo / 扩签名均落地（见上）。

**澄清（措辞差异，非偏差）**：design 2.1 接口示例把 card 写成 `kind:"near_due"`/`label:"临期"`，实现为 `kind:"near_due_batches"`/`label:"临期批次"`。核实**实现正确遵循「与 overdue 并列同构」**原则——超期 card kind=`overdue_batches`/todo kind=`overdue`，临期 card kind=`near_due_batches`/todo kind=`near_due`，card 用 `*_batches`、todo 用裸名，两侧完全同构。design 示例为不精确简写，实现无偏差，无需改代码。

**流程图核对**（2.2 mermaid）：装配侧两段切分（B 分支 C/D/E）→ near_due_batches 键 → size-guard → DB；首页 index 读 count → build_summary → 第 7 格 + todo。所有节点 grep 确认有落点（见第 2 节编排变化）。

---

## 2. 行为与决策核对

**需求摘要 / 明确不做（范围守护，全部 grep 实证）**：
- [x] 不新建表 / 不新增首屏扫描 / 不改排产算法：`core/algorithms/` grep near_due/临期 **0 命中**；首页只读冻结 `near_due_batches.count`。
- [x] 临期判定不引入 now：`due_risk_items.py` grep `now/datetime.now/utcnow` **无命中**。
- [x] 不接现场事实：临期纯 `finish vs due_exclusive`，与 ExecutionFactProvider 无关。
- [x] 不引入新 severity 档：`_SEVERITY_ORDER={danger,warning,notice,ok}`（`dashboard_workbench.py:41`）四档未变；CSS grep 无 `near_due`/`unknown` 档。
- [x] 不外显内部身份：临期 items 仅 `batch_id/due_date/finish_time`（`due_risk_items.py:78-82`），grep op_id/schedule_id/scenario_id/source_table/candidate_id **无命中**；端到端测试断言可见文本不含这些 token。
- [x] schema_version 仍 "1.2"（`assembly:368`），纯增量加键不升版本。

**关键决策落地**：
- [x] 决策 1 口径=finish-基准：`due_risk_items.py:71-76` 两段切分，now 无关可冻结。
- [x] 决策 2 格位=独立第 7 格：`build_dashboard_risk_cards` 返回 7 元素列表，临期居末（`dashboard_workbench_cards.py:200-215`）。
- [x] 决策 3 同链路扩字段：同一循环、同 due_date/finish/due_exclusive，无第二次遍历。
- [x] 决策 4 窗口常量单点：`NEAR_DUE_WINDOW_DAYS` 在 due_risk_items.py（核心判定唯一发生地），viewmodel 不 import 它、只消费 window_days 结论。

**编排层"现状 → 变化"逐项核对**：
- [x] 变化 1 装配侧两段判定（`due_risk_items.py:68-83`）；变化 2 RuntimeState 取 near_due_items（`summary_runtime_state.py:192`）+ assembly 加键。
- [x] 变化 3 size-guard 两路径：tier `_trim_near_due_items`（`summary_size_guard.py:124-128`，:171-172 调用）+ TruncationTier near_due_items_limit（`schedule_summary_types.py:137-141`）；minimal `_minimal_due_count_field`（`summary_size_guard_fields.py:218-222`，:257 调用 near_due_batches）。
- [x] 变化 4 首页独立非致命读取 `_summary_near_due_count`（`dashboard.py:111-129`）：返回 `Optional[int]`，缺键→None、坏值→None、count<items 不一致→None、键在且 0→0，**不返回 (0,error)、不并入全局 count_error**；唯一读点 `dashboard.py:374`，传 `:420`。
- [x] 变化 5 build_summary 仅闸门化不二次读（`dashboard_workbench.py:214`，与超期 :211 同构）。
- [x] 变化 6 hero 排序不改：排序键 `(_SEVERITY_ORDER[severity], str(kind))`（`dashboard_workbench.py:168`）未动，build_cockpit_hero 未改。

**流程级约束**：
- [x] 错误语义：缺键诚实降级不放大（见变化 4 + 验收场景 9）；坏交期 `invalid_due` 记账（`due_risk_items.py:53-63,85-95`），warning 文案已含"临期"（:87"已忽略超期与临期判断"）。
- [x] 互斥/幂等：`finish>=due_exclusive` 归超期、`<` 才入临期，零重叠（单测 test_mutual_exclusion）。
- [x] 零扫描 / 诚实空态 / 退化缺席：见验收场景 1/7/10。

**挂载点反向核对（可卸载性）**——对照 2.3 节，实际 grep + 拔除沙盘：
- [x] M1 summary schema near_due_batches 键（`assembly:396`）：删→临期无数据源、第 7 格永远"数据不足"、feature 消失。
- [x] M2 体检表数据源 `build_dashboard_risk_cards` 第 7 格（`dashboard_workbench_cards.py:214`）：删→第 7 格消失。
- [x] M3 待办类别 `_near_due_todo` 注入 `_todo_items`（`dashboard_workbench.py:152`）：删→临期待办消失。
- [x] M4 窗口常量 `NEAR_DUE_WINDOW_DAYS`（`due_risk_items.py:17`）：删→窗口口径无源、判定崩。
- [x] M5 说明书两份：`page_manuals_system.py:19/73/80`（7 格 + 临期条）+ `static/docs/scheduler_manual.md:70/78`（七格 + 临期条）：删→说明书谎报格数。
- [x] **反向 grep**：near_due/临期 全仓命中（排除 .codestable/测试）全部落在上述挂载点 + 内部支撑 wire（index 读取 / build_summary 传值 / RuntimeState 字段 / size-guard / 模板注释），无清单外漏记引用。
- [x] **拔除沙盘**：逐挂载点逆向推演，删任一则临期能力对应部分消失；模板 `dashboard.html` `{% for card %}` 循环对格数无感（:57 注释已改 7 格），非挂载点。

---

## 3. 验收场景核对

对照方案第 3 节，逐条可观察证据（单测在项目 .venv 实跑全绿，61 passed）。

- [x] **S1** 3 临期批次→count==3、第 7 格 value="3"/warning/可跳 gantt：`test_dashboard_workbench_contract.py:223-235`（near_due_count=3→卡片 warning/"3" + todo + action_paths=[/scheduler/gantt, /reports/overdue]）+ 端到端 `test_dashboard_near_due.py:63-111`（真实 DB→渲出 value）+ **新增** `test_dashboard_near_due_hero.py`（卡片 link path=/scheduler/gantt 断言，堵审核发现的卡片跳转锚缺口）。证据来源：单测 + 集成 + 端到端。
- [x] **S2** hero 顶格三分支：**新增** `test_dashboard_near_due_hero.py` 三测试——无超期+仅临期→临期顶 hero；有超期→超期顶 hero、临期落 rest；无超期+data_gap→data_gap 顶 hero（kind 字母序）、临期落 rest。证据来源：回归测试（堵审核发现的「hero 无正向断言」最大缺口）。
- [x] **S3** 恰 7 格、临期居末：`test_dashboard_workbench_contract.py:194-210`（kind 列表精确顺序锁定 + latest_version/scheduled_batches 不复活）。
- [x] **S4** finish==due_exclusive→归超期：`test_near_due_items.py:52-57`。
- [x] **S5** finish==due_exclusive−3天→计入临期（闭下界）：`test_near_due_items.py:60-65`。
- [x] **S6** finish<下界→健康：`test_near_due_items.py:68-73`。
- [x] **S7** count==0→第 7 格 ok"暂无"、临期 todo 缺席：`test_dashboard_workbench_contract.py:215-220` + `test_dashboard_near_due.py:20-22`（count==0→0 区别于缺键 None）。
- [x] **S8** 超大清单：tier 裁 items 保 count/window_days≤512KB（`test_schedule_summary_size_guard_large_lists.py:287-297`）+ minimal 保 count 丢 items（:300-312，与 overdue 同构）。
- [x] **S9** 缺键→"数据不足"/notice、不 KeyError、不显 0、todo 缺席、其余 6 格照常：`test_dashboard_workbench_contract.py:239-250`（含 :250 断言缺临期键时超期仍计数="3"，证不放大成全摘要降级）+ `test_dashboard_near_due.py:15-17`。
- [x] **S10** 退化场景临期 todo 缺席：`test_dashboard_workbench_contract.py:253-265`（摘要不可用闸门）+ 退化用例 `set(todos)=={"data_gap"}`（:648/:674/:706/:729/:748 共 5 处）。
- [x] **S11** 非法交期 invalid_due 记账跳过不冒充：`test_near_due_items.py:83-89`（invalid_due_count==1、items/near_due 均空）。

**前端浏览器肉眼验证**：
- [ ] 第 7 格 7 格栅格对齐 / 亮·暗·打印三态 / 临期三态（有值·空态·缺键）：**CLI 环境无浏览器，未执行**。静态核对：CSS `.aps-dashboard-risk-grid` 为既有响应式 `grid-template-columns: repeat(3/2/1, minmax(0,1fr))`（`ui_contract.css:5945/6147/6157`），7 格靠 grid 自动换行（宽屏 3+3+1、中屏 2×3+1、窄屏单列）、各档等宽对齐。**末行单格视觉是否可接受需人工目检**——见第 9 节遗留。

---

## 4. 术语一致性

对照方案第 0 / 2.1 节 grep 代码：
- `near_due` / `临期`：命中全部落在 due_risk_items / cards / todos / dashboard route / size-guard / workbench / 说明书 / 测试，语义一致（卡片 kind=near_due_batches、todo kind=near_due，与 overdue 同构）✓
- `near_due_batches`：summary 键 + size-guard + 读取 + 卡片 kind，全仓一致 ✓
- `NEAR_DUE_WINDOW_DAYS`：单点 `due_risk_items.py:17`，仅 assembly:399 复用、测试 import，无第二处定义 ✓
- 防冲突 grep：`datetime.now` 在临期判定 **0**、内部身份字段在临期 items **0**、CSS/`_SEVERITY_ORDER` 新增 near_due/unknown 档 **0** ✓

无不一致。

---

## 5. 架构归并

**已实际写入** `.codestable/architecture/ARCHITECTURE.md`「3. 子系统索引」首页驾驶舱条目（line 49），三处归并：
- [x] **标题**：①②③④ 四段的「③6 格体检表」→「③7 格体检表（fusion-due-soon-alert，2026-06-15 扩第 7 格临期）」。
- [x] **名词 + 动词骨架**：体检表枚举「六格→七格…/临期」；补 `due_risk_items.py` 两段切分（finish vs due_exclusive 严格互斥零重叠）、`near_due_batches{count,items,window_days}` 与 overdue 并列同构（schema 1.2 纯增量、零新数据链路、不接现场、不依赖 now）、size-guard 两路径保 count、`NEAR_DUE_WINDOW_DAYS=3` 单点；补微重构拆 `dashboard_workbench_todos.py` + 中立 `dashboard_workbench_shared.py`（单向 import 无环）+ cards 第 7 格 `_near_due_card`。
- [x] **流程级约束**：缺临期键诚实降级（第 7 格"数据不足"、不放大成全摘要降级，刻意不复用超期缺键返回 0 + 全局 count_error）、坏交期 invalid_due 记账不冒充。

> ARCHITECTURE.md 无独立「契约 4.11」段（4.11 是 roadmap 主文档的契约编号），临期/超期同口径已落在首页驾驶舱条目描述内，不另起段。

---

## 6. requirement 回写

`requirement: scheduler-daily-workbench`（status=current）。本次实现新增了用户可感的风险维度（临期），属改用户故事/能力枚举 → 触发 **cs-req update**（实际写文件，保留原始愿景）：
- [x] 用户故事风险枚举（line 16）加「临期（排程完工卡在交期前几天、还没真正超期）」，成为第 6 类风险维度。
- [x] 文末变更日志加 2026-06-15 条目：临期独立第 7 格 + 待办类别、与超期同口径互斥、**实时计算不保存已处理状态（守 req「不保存已处理 / 已忽略 / 指派给谁」边界）**、缺键诚实"数据不足"不伪造 0。
- [x] `last_reviewed` 更新为 2026-06-15。
- [x] **边界冲突核对**：req line 34「不保存已处理状态」——临期 todo `handling_state_label="实时生成，暂未保存已处理状态"`（`dashboard_workbench_todos.py:79`），**符合不冲突**；其余边界（不替用户处理/不写现场/不决定候选/不取代专页/报表只读）临期均不触碰。

---

## 7. roadmap 回写

`roadmap: aps-frontend-fusion` / `roadmap_item: fusion-due-soon-alert`（两字段都有值，必须回写）：
- [x] `aps-frontend-fusion-items.yaml` 条目（line 237-243）：`status: in-progress → done`，notes 补 2026-06-15 验收闭环裁决摘要；`feature: 2026-06-14-fusion-due-soon-alert` 核对一致。
- [x] 主文档 `aps-frontend-fusion-roadmap.md` 第 30 条（line 317）：加 `✅ done（2026-06-15…）` + 验收回写段（两项裁决：独立第 7 格 / finish-基准；near_due_batches 同源切分 / 常量单点 / 缺键诚实降级 / 微重构拆三文件）。
- [x] `validate-yaml.py --file` 校验 items.yaml：**1 passed, 0 failed**。

---

## 8. attention.md 候选盘点

- [x] **无候选**：本 feature 未暴露「下一个 feature 还会再撞一次」的环境 / 工具 / 工作流类信息。验收期用 `PYTHONPATH=<repo> .venv/bin/python` 跑 /tmp 临时脚本属通用 Python 运行知识；workbench 三文件单向 import 无环拓扑属本 feature 架构约定（已落 ARCHITECTURE.md，非 attention 级硬约束）。`.codestable/attention.md` 当前仍为空模板，无需追加。

---

## 9. 遗留

**对抗审核裁决（Codex + 4 SubAgent 双引擎，2026-06-15，收敛 0 blocker）**：
- SubAgent A（边界零重叠）：PASS，无确认问题。
- SubAgent B（诚实降级不吞错）：6 契约全达成，无吞错 / 伪装，存疑 3 项核实后非 blocker。
- SubAgent C（import 拓扑 / Py3.8）：5 约束全 PASS（含实跑 import 自证无环、ruff Py3.8 通过）。
- SubAgent D（验收场景证据）：指出 ①场景 2 hero 顶格无正向断言（最大缺口）②场景 1 第 7 格卡片 link 去向无测试锚 → **两者当场补 `test_dashboard_near_due_hero.py` 3 测试堵上**（已实证 + 落地回归）；③场景 1 count==3 无单一全链路测试、④场景 10 退化对临期搭便车覆盖 → 切分/读取/渲染/卡片三层已分别覆盖，判定覆盖度观察非缺陷。
- Codex：契约 4 报「宽 except 无栈日志 + positive_int 伪装 0」FAIL、契约 2 报「todo None/0 都缺席不区分」可疑。**裁决见下**。

**已知限制 / 待人工补**：
1. **前端浏览器目检未执行**（CLI 无浏览器）：第 7 格 7 格栅格对齐（3+3+1 末行单格）、亮 / 暗 / 打印三态、临期三态（有值 / 空态 / 缺键）需人工在浏览器确认。CSS 为既有响应式等宽栅格、技术层面对齐成立，但末行单格视觉是否符合设计需目检。

**裁决记录（非 blocker，依据如下）**：
2. **宽 except 无栈日志**（Codex 4a：`due_risk_items.py:55/95`、`summary_runtime_state.py:38/45/92`）：均为**既有代码**——`_build_overdue_items` 是微重构「只搬不改行为」从 assembly 搬来（design 2.5 明示不改函数体）、runtime_state 类型兜底是既有逻辑，**非本 feature 新增**。坏交期路径诚实记账（invalid_due_count + 样本 + 原始串 due_text!r + warning 文案 + logger.warning），不吞错 / 不伪装坏值；strptime 对脏字符串的 ValueError 栈无增量信息。本 feature **新增代码**（`_summary_near_due_count` / `_near_due_card` / `_near_due_todo` / 两段切分判定）零新增宽 except、零吞错。建议后续独立 issue 评估是否给坏交期日志加 exc_info（价值低），本 feature 不扩大范围改既有代码。
3. **positive_int 伪装 0**（Codex 4b：`summary_size_guard_fields.py:33`）：既有 size-guard 工具函数，临期 count 不经它（minimal 路径用 `size_guard_scalar`），与本 feature 无直接关系，非本 feature 引入。
4. **todo None/0 都缺席不区分**（Codex 契约 2）：**by-design**——临期待办只在「有临期」时出现，无临期（无论真 0 还是缺数据）都不应有「临期待办」，区分两态的是常驻的第 7 格卡片（数据不足 vs 暂无），非待办。

**实现期顺手发现**：无（本 feature 实现已在 9f6f41b2 提交，验收期仅核对 + 补 2 测试 + 回写文档）。

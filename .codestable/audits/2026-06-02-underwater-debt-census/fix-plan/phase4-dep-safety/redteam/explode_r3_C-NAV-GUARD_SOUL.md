# 逐簇爆炸对抗 r3 · C-NAV-GUARD · 主透镜【灵魂线热路径+收口等价】

> 只读不改。行号均 r3 当场 rg/sed 回盘（不信旧值）。默认怀疑：多维度存疑即红。
> 成员债：R54 / R44 / R58。本轮以 Q4/Q5/Q6（灵魂线热路径 + 收口逐分支等价）为重。

---

## 0) r3 回盘锚点（当前工作区实测，覆盖 dossier 旧值）

| 锚点 | dossier/cluster 旧值 | r3 实测 file:line | 偏差 |
|---|---|---|---|
| collar 真符号 | `build_workbench_plan_context` | def 在 workbench_links.py:187，**但全仓调用方一律用别名 `ln` import** | ⚠️见爆点① |
| collar 是否 emit 3 fail-open 键 | cluster 假设「收口点承载 guard 全集」 | **187-258 仅 emit is_preview:61 / can_write_feedback(已门控):62，三关键键(is_comparison/is_superseded/is_current_executable) 一个都不 emit** | ⚠️见爆点② |
| fail-open 判定 | links.py:292 | `_is_current_official_identity`:292-297 = `not is_comparison and not is_superseded_by_newer_version and is_current_executable_official_version is True` | ✅方向坐实 |
| gate | links.py:149/157/158 | `_feedback_guard_context`:149，`formal_adopted`:157，`can_write=bool(...)`:158 | ✅ |
| 门控落点 | links.py:248 | `"can_write_feedback": can_write`:248 | ✅（实读 :62 输出键，sed 区段相对偏移，符号准） |
| R58 病灶 | :86/:91 | `context.update(guard_fields)`:91 唯一命中 | ✅ |
| R44 副本 / import | :36-37 / :6 | `selected_plan_role`:36-37；`ROLE_ADOPTED` from schedule_plan_query_service:6 | ✅ |
| **L5 第5套 路径** | cluster:3/16/A-2 写 `web/routes/domains/scheduler/scheduler_gantt_task_detail.py` | **该路径不存在！实盘 `web/viewmodels/scheduler_gantt_task_detail.py`** | 🔴见漏项A |
| L5 机制 | 别名元组 | `_PLAN_GUARD_FIELD_ALIASES`:8-25 + `context["is_comparison"]=bool(...or data.get("is_comparison_plan"))`:98 | ⚠️多源别名，见爆点③ |
| N1 安全链 | Layer1-C:35 称 `_can_write_feedback:89`+`_is_official_plan:70-84` 严格蕴含 | **两函数在该文件均不存在！** `_identity_allows_query_membership_check`:130 = `bool(identity.get("can_write_feedback"))` 直接读预算字段 | 🔴见爆点④ |

---

## R58 —— 🟡 黄（有条件可做：仅 Batch-1 纯注释安全；任何收敛红）

**判定**：本轮计划动作=「:91 上方按符号插『我是故意的』注释 + 绑 keep_plan_guard_fields 契约」→ **黄（条件绿）**。Phase2「剔 can_write_feedback 一键」→ **红**。

**证据（r3 实读）**：`_publish_context`:85 → :88 把 raw `can_write_feedback` 喂 builder（builder 内 :158 gate 成 can_write 写 :248）→ **:91 `context.update(guard_fields)` 用 `_plan_guard_fields`:82 抽出的未门控 raw can_write_feedback 覆盖回门控值**。坐实 P2 护栏被动削弱。

**条件（必须全满足才算黄→绿）**：
1. 注释**纯增量**、零 dict 键变更、零逻辑变更（dossier §4 已钉 4 点文案）。
2. 按符号 `context.update(guard_fields)` 重定位，**禁照抄行号**（文件 M 态 + R54 会再移行）。
3. **硬序 R58 先落**（A-1#1）：注释稳定→R54 动闸门元组→R44 动 getter。

**灾难链（若越界 Phase2 剔键）**：剔 update 里 can_write_feedback → 现有 keep_plan_guard_fields 用例 superseded 路径 builder-gated≡raw≡True **仍绿（盲点）** → 但 preview-adopted / 非 adopted 路径 context.can_write_feedback 静默 True→False 翻转 → 未来若有人据 nav context 渲染写按钮，行为悄改而测试无感。**测试绿但护栏语义已变 = 典型静默失效**。修正：Phase2 前必补 preview-adopted + 非 adopted 两反例 parity，排 R54 之后，owner 拍板。

---

## R54 —— 🔴 红（多维存疑，灵魂线热路径 + 收口非等价双爆）

**判定**：**红**。owner_pending=true 本就不该给终态，但 r3 在主透镜下挖出**两个 cluster/dossier 未覆盖的硬爆点**，使「收口到 collar」方向若照计划执行=连环炸。

### 爆点②（致命，Q4 灵魂线热路径 + Q5 收口等价同时破）：collar 当前根本不产 3 个 fail-open 键
- r3 实读 collar 187-258：**只 emit is_preview / can_write_feedback(已门控)，is_comparison / is_superseded_by_newer_version / is_current_executable_official_version 一个都不产**。collar 入参只有 `is_preview:18`/`can_write_feedback:19`，**无任何通道拿到这三键**。
- cluster A-2 步骤1「收口点先承载 guard 字段」+ 字段40「内部从 plan_role_filter_fields 产出 guard 全集」=**计划假设 collar 能内部调 view_context 取全集，但 collar 现状不调、也无 plan_resolution 入参**。
- **灾难链**：若按计划让 5 套 delegate 到 collar，而 collar 仍只产 is_preview/can_write → 5 套丢掉 is_comparison/is_superseded/is_current_executable → 下游 `_is_current_official_identity`:292 `not None=True`、`not None=True`、`None is not True`→ 前两键 fail-OPEN（旧正式版/比较版冒充现行采用方案）→ execution_review 闸:394 放行 + can_emit_feedback_write_urls:469 放行 → **向历史/比较方案写现场事实（脏写、不可逆）**。
- **前置（红→可议的唯一路径）**：必须先给 collar 加「承载 plan_resolution / 调 plan_role_filter_fields 产 3 键」的入参与函数体（这是新增承重逻辑，**非纯 delegate**），且 collar 输出三键须走 view_context default_plan_resolution_dict 的 fail-CLOSED 默认（is_superseded=False / is_current_executable=False）。owner 须把「collar 扩成 guard 产出点」当独立承重改动审，不可混进「5 套 delegate」一笔带过。

### 爆点③（Q5 收口非等价反例，cluster 仅含糊提「机制不同」未给反例）：L5 的 is_comparison 多源别名，收口即静默放宽
- L5 `_PLAN_GUARD_FIELD_ALIASES`:13 = `("is_comparison", ("is_comparison","is_comparison_plan"))` + :98 `context["is_comparison"]=bool(context.get("is_comparison") or data.get("is_comparison_plan"))`。
- 真相源 view_context 的 is_comparison 由 `ln(role=,source_table=)` 派生（≠原始键直取），L1-L4 取 plan_role_filter_fields 已命名键。**L5 是唯一吃 `is_comparison_plan` 回退别名的面**。
- **灾难链**：R54「统一键名/delegate 到 collar」若丢 is_comparison_plan 回退 → 一个只设 is_comparison_plan(未设 is_comparison) 的 gantt task-detail 上下文 → is_comparison=falsy → `not is_comparison`=True → fail-OPEN。**禁统一键名（cluster 禁区已列，但未点名 is_comparison_plan 这条具体丢键路径）**。

### 爆点①（Q6 测试/改面遗漏，cluster 路径错 + co-change grep 纪律不足）
- **cluster 三处写 L5 在 `web/routes/domains/scheduler/scheduler_gantt_task_detail.py` —— 该文件不存在**，实盘在 `web/viewmodels/`。照 cluster 路径动手=改空气，L5 漏迁 → 收口不完整债残留（fix_invalidation_risk②）。
- collar 真符号 `build_workbench_plan_context` **全仓调用方一律别名 `ln` import**（navigation_context/dashboard/resource_dispatch/analysis_links/gantt_task_detail/navigation_links/reports_workbench 全是 `from ... import ln` / `ln(...)`）。R54 加 guard 字段、R42 删 plan_id 形参时，**co-change grep 必须同查 `build_workbench_plan_context` 与 `ln(` 两形态**（D2 已提但 cluster A 节未落实到 R54 改面清单）。漏查=漏改别名调用点。

### 其余维度
- Q1 承重误删：禁区行（292-297 判定方向、view_context fail-closed 默认、:149-161 gate、:469-473）cluster 已列全，**只要不照「纯 delegate」抹掉 5 套各自的三键来源即不误删**——但爆点②证明「纯 delegate」本身就是误删入口。
- Q2 分层：web/viewmodels→core/services 合法，view_context 不反向 import web（r3 实测零命中），**0 违规不破**。✅
- Q3 迁移耦合：R54 不碰 v18/v19 DB CHECK（guard 投影是 web 层显示/护栏，非 effective_plan_role schema），无启动探针炸。✅
- Q6 测试序：删任一手维列表**前**先迁 regression_scheduler_workbench_link_guardrails.py:120-162（_is_formal_adopted_context 下游读端 missing/None/False/True×拦放矩阵）+ 各面契约测试改读 collar 输出，同 commit，避免护栏裸奔窗口。

**修正建议（R54 维持红，前置硬条件）**：(a) 先把「collar 扩成 3 键 guard 产出点 + fail-CLOSED 默认」当独立承重改动 owner 审过；(b) L5 路径改 `web/viewmodels/`，is_comparison_plan 回退别名显式保留并 parity 钉死；(c) co-change 同查 `ln(`；(d) 与 R42 同批（互锁 collar 签名 187-210 + dict 229-258）。任一未满足 = 连环 fail-OPEN 脏写。

---

## R44 —— 🟢 绿（low、只喂模板显示 kwarg、不碰闸门；硬序末位 + 路径准）

**判定**：**绿**（条件极轻）。

**证据**：副本 selected_plan_role:36-37 仅喂 week_plan.py:352 / gantt.py:299 的 `effective_plan_role=` **模板显示 kwarg**（r3 实测两消费者），不碰 _PLAN_GUARD_FIELD_NAMES 闸门、不碰 can_write/can_dispatch。core 收口点 view_context:201 比 web 更防御（`(pr or {})`），收口只增强不削弱。唯一行为差 = None→AttributeError vs "adopted"，生产入参恒 dict 不可达。分层 web→core 合法、无环（r3 实测 view_context 零 web import）。

**条件（不影响绿）**：硬序末位（R58→R54→R44），动手前按符号重盘 :7/:36-37（B01 会再移行）；补 test_selected_plan_role_parity 钉 5 边界 + None 反例；禁顺手统一 :33 requested_plan_role。

---

## 漏项（本轮新发现，未被 cluster/dossier 计划覆盖）

- **漏项A（路径错，会改空气）**：cluster 三处把 L5 写成 `web/routes/domains/scheduler/scheduler_gantt_task_detail.py`——**不存在**，实盘 `web/viewmodels/scheduler_gantt_task_detail.py`。A-2 步骤、对抗复核行 16/38/94 全须订正，否则 L5 漏迁。
- **漏项B（爆点②，最致命）**：cluster/R54-dossier 假设「collar 能内部产 guard 全集」，但 r3 实读 collar 187-258 **当前不产 3 个 fail-open 键、也无 plan_resolution 入参**。「5 套 delegate 到 collar」在 collar 扩产能力前=**直接抹掉三键的 fail-OPEN 入口**。须把「collar 扩成 guard 产出点」立为独立承重前置。
- **漏项C（爆点④，跨债承重链断裂未捕获）**：Layer1-C:35 给 N1「行为安全」背书的 `_can_write_feedback:89`+`_is_official_plan:70-84` **在 scheduler_resource_dispatch_execution_context.py 中不存在**；N1:130 实为 `bool(identity.get("can_write_feedback"))` 直读预算字段。N1 安全实依赖「谁填 identity.can_write_feedback 时已过 gate」。**R58 病灶(:91 用 raw 覆盖 can_write_feedback) 若与喂给 N1 的同一 identity 流相交 → N1 fail-OPEN 写门放行**。R58↔N1 这条灵魂线耦合 cluster B 节(R54/R58↔N1)只标「同护栏概念、不同文件、不撞行号」，**未捕获「N1 的安全前提就是 can_write_feedback 已门控，而 R58 正在反门控」这一实质耦合**。须 owner 复核 N1 读的 identity 来源是否经过 R58 覆盖路径。
- **漏项D（爆点③具体丢键路径）**：cluster「禁统一键名」是泛泛禁令，未点名 L5 唯一的 `is_comparison_plan` 回退别名(:13/:98)——这是统一时最易被「DRY 清理」掉的具体 fail-OPEN 丢键点，须显式列入 R54 禁区行。

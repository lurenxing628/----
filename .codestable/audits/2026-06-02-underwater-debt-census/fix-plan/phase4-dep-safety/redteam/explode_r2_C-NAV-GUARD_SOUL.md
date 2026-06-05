# 逐簇爆炸对抗 r2 — C-NAV-GUARD / SOUL 透镜（灵魂线热路径 + 收口等价）

> 只读不改。行号均当轮 rg 回盘（2026-06-05），不信旧值。成员债 R54 / R44 / R58 + 邻接 N1。
> 主透镜 Q4/Q5/Q6 为重，六质问全过。默认怀疑：多维度存疑即红。

## 0) 当轮回盘锚点（全部实盘命中，与 dossier 一致除标注外）

| 锚点 | dossier/cluster 标注 | 实盘回盘 | 判 |
|---|---|---|---|
| R58 `context.update(guard_fields)` | :91 | **:91** ✅ | 准 |
| R58 `_publish_context` / `_plan_guard_fields` / 元组 | :85 / :80,:82 / :12 | **:85 / :80,:82 / :12** ✅ | 准 |
| R44 `def selected_plan_role` web 副本 | :36-37 | **:36-37** ✅ | 准 |
| R44 `import ROLE_ADOPTED` 真来源 | schedule_plan_query_service | **:6 = schedule_plan_query_service** ✅ | 准（非 view_context） |
| R44 core 收口点 | view_context:201 | **:201**（`(plan_resolution or {})` 更防御）✅ | 准 |
| R54 L1/L3/L4 def | reports:36 / resource:64 / dashboard:8 | **:36 / :64 / :8** ✅ | 准 |
| **R54 L5 gantt_task_detail** | cluster 写 `web/routes/domains/scheduler/` | **实盘 `web/viewmodels/scheduler_gantt_task_detail.py:8` `_PLAN_GUARD_FIELD_ALIASES`** | ⚠️**路径错**（详漏项①） |
| LB 闸 `_is_current_official_identity` | :292 | **:292-297** ✅ fail-OPEN(comp/super)+fail-CLOSED(cur is True) | 准 |
| 收口符号别名 | `build_workbench_plan_context` | **全调用方以别名 `ln` import** | ⚠️co-change 纪律（漏项②） |
| N1 `_identity_allows_query_membership_check` | execution_context:129-130 | **:129-130 = `bool(identity.get("can_write_feedback"))`** ✅ | 准 |
| **N1 源链 `_can_write_feedback:89`/`_is_official_plan:70-84`** | cluster/corrections C 称在 execution_context.py 本文件 | **本文件无此二符号；def 在 `core/services/scheduler/schedule_plan_identity_builder.py`（且 builder 名亦被别名 `n`）** | ⚠️**源链跨模块、行号假**（漏项③） |

**5 套手维面 fail-open 关键键当轮普查**（每套须各带 is_comparison + is_superseded_by_newer_version + is_current_executable_official_version）：reports=1/1/1、nav=1/1/1、resource=1/1/1、dashboard=1/1/1、gantt=2/1/1（gantt comp=2 系 `is_comparison_plan` 别名）→ **5 套当前全带齐三关键键，未坏。债为 split 结构潜伏 fail-open，非现网漏洞** ✅ 坐实 R54 dossier「未坏」。

---

## Q1 承重误删（统一/DRY 名义抹承重不对称）

- **R54**：最大爆点。5 套看似 DRY 重复 **实为护栏冗余**——下游 `_is_current_official_identity:293-294` 对 `is_comparison`/`is_superseded_by_newer_version` 用 `not context.get(...)`（**fail-OPEN**），对 `is_current_executable_official_version` 用 `is True`（fail-CLOSED）。任一面收口时漏拷前两键 → 该键 falsy → `not falsy`=True → 旧正式版/比较版冒充现行采用版 → execution_review 写门（links.py 闸）放行 → 脏写历史/比较方案现场事实（不可逆）。**禁以统一名义删任一面而不迁下游、禁透传裸键、禁翻 :294 fail-closed→fail-open**。
- **R58/N1**：承重不对称 = 隐式化失忆（N1 把五连合取塌成 `bool(get("can_write_feedback"))`，零注释）。只补注释+绑 parity，不动逻辑。
- 判：见各债终判。承重禁区行（按符号回盘）：links.py:292-297 判定方向 / :149-161 `_feedback_guard_context`(:157 formal_adopted/:158 can_write) / :248 门控落点 / :469 can_emit；nav:91 update / :12-31 元组 / :80-82。

## Q2 分层导入环

- R54 收口（reports L1 新增 `from core.services.scheduler.schedule_result_view_context import plan_role_filter_fields`）= web/viewmodels→core/services 合法向；view_context 不反向 import web，**无环**。
- R44 收口（nav re-export core selected_plan_role）= web→core 合法，已有 `ln` 别名 web→core 先例，无环。
- **collar 在 web/viewmodels，真相源在 core/services；禁向（core.models→services、core.algorithms→services、data→service）零触碰**。Q2 全绿。

## Q3 迁移耦合

- 本簇三债 + N1 改纯 Python 投影/门控逻辑，**不碰 schema CHECK / v18·v19 DB CHECK**（adopted-only 已下沉 v19 CHECK：effective_plan_role=adopted/source_table=schedule，与 guard 字段投影解耦）。改码不触迁移，**启动探针不炸**。Q3 全绿。

## Q4 灵魂线热路径（主透镜）

- **R58**：本轮纯增量注释（:91 上方），**零逻辑、零 dict 键变更、不改 raise**。灵魂线安全。但 Phase2「剔 update 里 can_write_feedback」**不在本轮**——若误做即 §7 反例（preview-adopted/非 adopted True→False 静默翻转），故钉死「本轮只注释」。
- **R44**：core 版比 web 版**更**防御（多 `(pr or {})`），收口只增强不削弱，**不新增兜底/不静默回退/不吞错/不改 loud raise**。灵魂线安全。
- **R54**：收口**不得**引入兜底；当前 5 套均带 `if value is not None`（reports:58 / resource:80 / nav:82）/`if key in`（dashboard:131）/gantt `_MISSING` sentinel(:7,:94) 的**静默丢键**路径——漏键正是 fail-open 入口，收口后须走收口点 fail-closed 确定默认值（view_context default_plan_resolution_dict 已给 is_superseded=False/is_current_executable_official_version=False），**禁保留「缺了就不写」**。本债 P5 维持确定性默认即可，**禁改 raise**（非 P4）。
- **N1**：`can_write_feedback` 单字段是隐式护栏，**不在 N1 闸加 raise/兜底/preview 旁路**；只补注释钉「can_write_feedback⇒adopted-only」来源链。Q4 主透镜下三债无新增兜底/吞错。

## Q5 收口行为等价（主透镜·逐分支）

- **R44**：5 边界值逐分支等价，**唯一分歧 None→AttributeError(旧) vs "adopted"(新)**；生产消费者（week_plan:44/:352、gantt:30/:299）入参恒 dict，反例不可达，但属可观察行为差异 → **owner 裁是否接受 None→"adopted"**。常量同一（`"adopted"`，两路同源 schedule_plan_role.py）。
- **R54**：新旧两路**不必然逐分支等价**。①源键改名（L1/L3 从 plan_resolution 手映射 requested_role→requested_plan_role；L2/L4/L5 从已命名键过滤），双键并存口径须 parity。②**关键反例**：三关键键在 {缺失/None/False/True} 四态下拦/放矩阵——旧路缺键静默不写 vs 新路收口点给 fail-closed 默认，**必须逐键四态钉死等价**，尤其 is_current_executable_official_version 缺→新路 False→`is not True` 拦（方向不能反）。③**字段集分叉**：reports `_copy_plan_guard_fields:36` 带 12 键但**缺** plan_identity_error/blocking_error/blocking_scope 三阻断态，经 `reports_execution_review_context.py:43-45` overrides 第二路注入——**禁把两路并一条**（丢阻断态）。
- 判：R54 Q5 高危存疑 → 红/黄（见终判）。

## Q6 测试迁移序（主透镜）

- **硬序 R58→R54→R44**（同 nav_publish 文件，M/MM 漂移态；任一先落移 :91/:36/:12 行号，后落者按符号回盘，禁照抄）。
- **R54 删任一手维面前**，先确认对应契约测试改读收口点输出（regression_reports_workbench_navigation_contract.py:406 / regression_scheduler_workbench_link_guardrails.py:120-162 逐键四态 / regression_dashboard_workbench_contract.py / regression_resource_dispatch_*），**删列表与改测试同 commit**，否则护栏裸奔窗口。
- **R58 Phase2（若做）先迁测试后改码**：现 keep_plan_guard_fields 用例 adopted+非preview 下 builder-gated≡raw，**剔 update 后仍绿但语义不安全**——须先补 preview-adopted/非 adopted 两反例固化 True→False，再改码。序倒=测试绿但护栏静默破。

---

## 终判

### 🔴 R54 — 红（会炸，最危爆点）
**灾难链**：5 套手维 guard 列表任一面收口时漏拷 `is_comparison` 或 `is_superseded_by_newer_version`（fail-OPEN 键）→ 该键 falsy → `_is_current_official_identity:293-294` `not get()`=True → 误判旧正式版/比较版为现行官方版 → `_is_formal_adopted_context:300` 放行 → execution_review 写门 + can_emit_feedback_write_urls:469 双双放行 → **向历史/比较方案脏写现场执行事实（不可逆）**。第二爆点：漏迁 L5 gantt_task_detail(别名元组面)或并掉 reports 第二注入路径(丢 3 阻断态)→ 收口不彻底/丢阻断。
**红因**：load_bearing 护栏 + 多维存疑（Q1 删错=静默 fail-open、Q5 四态不等价、Q6 序错裸奔），属「测试绿但护栏已破」静默失效类。
**前置/禁区**：①收口到已存在 `build_workbench_plan_context`(:187)，禁新建；②与 R42/R60 同改该函数签名/dict **MUST 同批**；③逐键四态 parity 钉死前禁删任一面；④禁删 `if value is not None`/`if key in` 而不补 fail-closed 默认；⑤禁碰 :292-297 判定方向、view_context default fail-closed 默认；⑥owner_pending=true，只标不给终态。

### 🟡 R58 — 黄（本轮注释安全；Phase2 收敛有条件）
**本轮**：纯增量注释，零逻辑/零 dict 键变更，Q1-Q6 全过 → 安全。
**黄条件**：Phase2「剔 update 里 can_write_feedback」**不得本轮做**——须先补 preview-adopted/非 adopted 两反例 parity 固化 True→False、排 R54 之后、owner 拍板；否则 §7 静默翻转（测试盲绿）。禁误删整行(连带丢 can_dispatch 致 superseded 派工护栏失效)。注释按符号 `context.update(guard_fields)`(:91) 重定位，禁照抄 registry :86。

### 🟡 R44 — 黄（low，有条件可做）
**黄条件**：①None→"adopted" 边界行为变化 owner 须裁（生产不可达但可观察）；②**必须排 B01(R58→R54)动完 nav_publish 之后**，动手前重 rg 回盘 :6/:36-37（文件 M 漂移态 + B01 再改行号）；③仅允许动 :6-7(import)+:36-37(删 def)，禁碰 :12-31 元组/:80-82/:32-33 sibling。满足即低风险（只喂模板显示 kwarg，不碰闸门）。

### 🟡 N1（邻接，纳本簇护栏概念）— 黄
**黄条件**：只补注释+绑 parity，禁放宽成 or/禁加 preview 旁路/禁动 :129-130。**注释钉来源链时不得引用本文件不存在的 `_can_write_feedback:89`/`_is_official_plan:70-84`**（见漏项③）——须跨模块溯到 plan_identity 真实产出点。owner_pending，只标不给终态。

---

## 漏项（本轮新发现，计划未覆盖/缺前置）

- **①【路径错·中】** cluster C-NAV-GUARD.md 把 R54 第 5 面 gantt_task_detail 标 `web/routes/domains/scheduler/scheduler_gantt_task_detail.py`——**实盘在 `web/viewmodels/scheduler_gantt_task_detail.py:8`**（`_PLAN_GUARD_FIELD_ALIASES` 别名元组）。L4 dashboard 与 L5 gantt 都在 viewmodels，cluster 路径前缀须订正，否则迁面/回盘指错文件。
- **②【co-change 纪律·高】** 收口符号 `build_workbench_plan_context` **被全部 7 个调用方以别名 `ln` import**（navigation_context/analysis_links/resource_dispatch/dashboard/gantt_task_detail/navigation_links/reports_workbench）。R54 加 guard 字段 / R42 删 plan_id 形参时，**co-change grep 必须同查 `build_workbench_plan_context` 与 `ln(` 两种形态**，否则漏改别名调用点（这些都不传 plan_id，TypeError 风险低但 guard 字段透传须覆盖）。本簇计划只在 D2 一句带过，未上升为 R54 收口的硬前置。
- **③【源链假行号·高】** cluster D 节 / corrections C 节钉 N1 注释「绑 can_write_feedback⇒adopted-only 来源链」并引 `_can_write_feedback:89`/`_is_official_plan:70-84` 在 execution_context.py——**该文件无此二符号**；`can_write_feedback` 经 `context.get("plan_identity")`←`_execution_svc().get_execution_context()` 跨模块来，真定义族在 `schedule_plan_identity_builder.py`（且 builder 被别名 `n`）。N1 的「显式自证退化成隐式远端依赖」**比 dossier 描述更严重**（跨模块+别名双层不透明）；注释禁引本文件假行号，前置须先 rg 锚定真实产出点，否则失忆债注释自身就是错链。

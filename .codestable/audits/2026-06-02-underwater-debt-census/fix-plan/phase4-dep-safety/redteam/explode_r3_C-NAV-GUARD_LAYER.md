# 逐簇爆炸对抗 r3 · C-NAV-GUARD · 主透镜【分层导入环+迁移耦合】

> 只读不改。行号已全部 rg 当前工作区回盘。默认怀疑：多数维度存疑即标红。
> 成员债：R54 / R44 / R58。主攻 Q2(分层环) / Q3(迁移耦合)，六质问点全过。

---

## 判定总览

| 债 | 判定 | 一句话 |
|---|---|---|
| **R54** | 🟡 黄（高危条件） | split 收口本身安全方向（web→core.services 合法、无环），但**三套丢键语义+三套源键命名**未对齐就并表=静默 fail-open |
| **R58** | 🟢 绿（本轮仅注释） | 纯增量注释零逻辑零 dict 键变更；Phase2 收敛才有翻转风险，不在本轮 |
| **R44** | 🟢 绿 | low，只喂模板显示 kwarg，不碰闸门；core 更防御，收口不改生产行为 |

---

## R54 🟡 — fail-open 主链未当前已坏，但收口动作本身是新爆点入口

**当前盘点（回盘坐实，未坏）**：五套面三关键键 is_comparison / is_superseded_by_newer_version / is_current_executable_official_version **当前全各带 1 次**（L5 is_comparison=2 因 :98 二次兜底），下游 `_is_current_official_identity`（workbench_links.py:294-296）逐字坐实 fail-OPEN（前两键 `not <truthy>`）+ fail-CLOSED（第三键 `is True`）。债是 split 结构，非已坏。

**Q2 分层导入环 → 0 违规坐实**：workbench_links.py 不 import web；view_context 不 import web；五套面收口走 web→core.services 合法方向，view_context 不反指 web，无环。reports(L1) 收口后新增 `import plan_role_filter_fields` 仍合法 web→core。**Q2 绿。**

**Q3 迁移耦合 → 真实间接耦合（计划未提及，本轮新发现）**：v19.py:18-19 DB CHECK 钉死 `effective_plan_role='adopted'` + `source_table='schedule'`（adopted-only 已下沉 v19 CHECK 坐实）。R54 改 web 投影层不直接碰 DB 写，但**护栏链是写门禁的上游**：若收口误翻 fail-open → 旧正式版/比较版冒充 adopted 现行版 → `can_emit_feedback_write_urls`(469) 放行 → 写侧最终撞 v19 CHECK（轻则启动探针/约束 raise 在生产炸，重则若 effective_plan_role 字段被投影污染则脏写被 DB 拒）。**改码不改迁移这里是「迁移当最后一道闸」的反向耦合**——护栏破了 DB 兜底，但 DB raise≠静默，属响声爆。计划须在 parity 钉「收口后写链接对非 adopted 仍 False」。

**Q5 收口行为等价 → 三套丢键语义分叉（最危爆点，计划只提一种）**：
- L1 reports `_copy_plan_guard_fields`(reports_workbench.py:51-53)：`for...if value is not None: context[key]=value` → **None 值丢键**。
- L3 resource(resource_dispatch.py:81)/L4 dashboard(dashboard_workbench_context.py:131)：`if key in identity/filters` → **None 值保留**（只要键在）。
- 三套对「键存在但值=None」行为不同：reports 不写→下游读 None；resource/dashboard 写 None→下游读 None。**巧合都 fail-open 到同终态**，但收口并表到收口点确定布尔后，is_current_executable_official_version 缺→False→`is not True`→拦，**reports 旧路 None 与新路 False 在第三键拦放结果反转**（旧 None→拦，新 False→拦，等价）但前两键旧 None→放、新 False→放（等价）——逐键四态 {缺失/None/False/True}×拦放矩阵必须钉死，**漏一键即静默放宽**。

**源键命名三重分叉（计划只标双分叉，本轮升三）**：
- L1/L3：`requested_role/selected_role/is_official/is_preview` 手映射改名。
- L2/L4：从 `plan_role_filter_fields` 取已命名键过滤。
- **L5 别名元组**(gantt_task_detail.py:8-21)：`is_comparison` 带 alias `is_comparison_plan`，且 :98 `context["is_comparison"]=bool(context.get("is_comparison") or data.get("is_comparison_plan"))` 二次兜底。**收口源 view_context 的 is_comparison 是 `is_comparison_plan(role,source_table)` 函数重算结果(:129/:179/:373)，不读 `data.get("is_comparison_plan")` 这个原始键**。L5 收口后若 delegate 到收口点，丢掉 `or data.get("is_comparison_plan")` 兜底 → 上游塞 is_comparison_plan=True 而 role/source_table 不触发函数重算的场景 → gantt 比较版 is_comparison 漏判 False → `_is_current_official_identity` 误判现行官方 → execution_review/写链接 fail-OPEN。**这是 split 真正会炸的反例，parity 必须覆盖「is_comparison_plan=True 但函数重算=False」。**

**灾难链**：收口漏对齐 L5 is_comparison_plan 兜底（或漏迁某套丢键语义）→ 比较/旧正式版 is_comparison/is_superseded 静默 falsy → `not falsy`=True → `_is_current_official_identity` 真 → `_is_formal_adopted_context`(300) 真 → execution_review 闸(394)/can_emit_feedback_write_urls(469) 放行 → 向历史/比较方案写现场事实（脏写不可逆，写侧撞 v19 CHECK 或污染 effective_plan_role）。

**修正建议（前置/顺序/禁区）**：
1. **owner_pending 守住**：R54 owner_pending=true，本轮只标不给终态。
2. **路径前缀错必须先订正**：簇文件锚点表 + corrections C 节把 L5 写成 `web/routes/domains/scheduler/scheduler_gantt_task_detail.py`，**实盘 = `web/viewmodels/scheduler_gantt_task_detail.py`**。照旧路径 rg 会 No such file，co-change 漏改 L5=收口不彻底（fix_invalidation_risk②）。
3. **同批互锁**：R54↔R42 同改 build_workbench_plan_context(187)/plan_id 形参(191)/dict(233) MUST 同批；D2 co-change 纪律——删 plan_id 须同查别名调用点（navigation_links.py:40 `build_workbench_plan_context(plan_role=ROLE_ADOPTED)` 不传 plan_id、analysis_links.py:24、gantt_task_detail.py:78、reports_workbench.py:77、dashboard:119、resource_dispatch:95 全不传 plan_id，TypeError 低危但须覆盖）。
4. **parity 三维矩阵**：① 三关键键×四态×拦放；② 三套丢键语义（None 丢 vs None 留）对齐；③ L5 `is_comparison_plan` 兜底 vs 收口点函数重算等价。三者任一缺=静默 fail-open，**测试绿不代表护栏在**（当前五套都带齐键，删任一前测试仍绿）。
5. **禁区行不碰**：workbench_links.py:294-296 判定方向（严禁翻 fail-closed→open）、:149-161 _feedback_guard_context、:469-473 can_emit、view_context default fail-closed 默认(:94-95/:145-146)。禁删/统一键名/透传裸 key。
6. **静默丢键禁保留**：收口后禁留 `if value is not None`/`if key in` 丢键路径，缺键走收口点 fail-closed 确定默认。

---

## R58 🟢 — 本轮纯注释，零逻辑变更

病灶 `context.update(guard_fields)` 实盘唯一命中 **navigation_publish.py:91**（registry :86 错坐实）；:86 guard_fields=_plan_guard_fields，:88 把 raw can_write_feedback 喂 builder，builder gate 成 can_write 写 :248，:91 update 用 raw 覆盖回门控值=护栏被动削弱，但**零生产消费**（nav_links 不传播该字段，真放行走 can_emit_feedback_write_urls:469）。本轮只在 :91 上方插「我是故意的」注释（钉 4 点），零 dict 键变更、零分层风险。**Q4 灵魂线**：本轮不改 raise、不加兜底。**条件**：注释先落（SEQ-NAV #1），后落者按符号重定位禁照抄行号。Phase2「剔 can_write_feedback」才有 preview-adopted/非 adopted True→False 静默翻转风险，归 owner，不在本轮。

---

## R44 🟢 — low，core 更防御，收口不改生产行为

副本 selected_plan_role(navigation_publish.py:36-37) vs core 收口点(view_context.py:201-202，多 `(plan_resolution or {})` None 防御)。import ROLE_ADOPTED 真来源 = schedule_plan_query_service:6（非 view_context）坐实。只喂 week_plan:352/gantt:299 的 `effective_plan_role=` 模板显示 kwarg，不碰任何闸门。唯一行为差异 None→AttributeError vs "adopted"，生产无 None 调用方=反例不可达。Q2 分层 web→core 合法无环。**条件**：排 SEQ-NAV 末位（R58→R54→R44），动手前重盘 :7/:36-37；新增 test_selected_plan_role_parity（当前不存在）同 PR；禁顺手统一 :33 requested_plan_role。

---

## N1 / N2 承重邻接（同护栏概念，Batch-2 同期不同文件，只标不给终态）

- **N1** execution_context.py:129-130 `_identity_allows_query_membership_check` = `bool(identity.get("can_write_feedback"))` 单字段（五连合取收敛）。行为安全（can_write_feedback⇒adopted-only），但显式自证退化成隐式远端依赖、零注释=失忆债。修法补「我是故意的」注释钉 can_write_feedback⇒adopted-only 来源链+绑 parity；禁放宽成 or、禁加 preview 旁路。**owner_pending，只标。**
- **N2** operation_execution_event.py:160-163 `_event_id_for_revision` 末位 `return 0` sentinel，非末位缺 id 已 `if index<total: raise`（坐实）。补注释（末位 id 不参与下游拼接故允 0）+绑「非末位缺 id 必抛错」契约；禁删 raise。**owner_pending，只标。**

---

## 本轮新发现漏项（计划未覆盖）

1. **L5 路径前缀错**：锚点表/corrections C 写 `web/routes/domains/scheduler/scheduler_gantt_task_detail.py`，实盘 `web/viewmodels/scheduler_gantt_task_detail.py`——照旧路径 rg 空，L5 漏迁风险。
2. **三套丢键语义分叉**（计划只提「静默丢键」一类）：L1 `if value is not None`（None 丢）vs L3/L4 `if key in`（None 留），收口 parity 须分别对齐两种语义。
3. **L5 is_comparison_plan 兜底 vs 收口点函数重算**：收口源用 `is_comparison_plan()` 函数重算不读该原始键，L5 :98 二次兜底丢失=gantt 比较版 fail-open，parity 必覆盖「源键 True 但函数重算 False」反例。
4. **Q3 反向迁移耦合**：护栏 fail-open 后写链接撞 v19 CHECK(effective_plan_role/source_table=adopted/schedule)，DB 是最后一道闸（响声爆非静默），parity 须钉「非 adopted 写链接仍 False」。

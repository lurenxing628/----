# 原子簇 C-NAV-GUARD — 干扰图重建 Layer2 产物（只读不改）

> 成员债: R54 / R44 / R58 | 主文件: scheduler_reports_workbench.py, scheduler_navigation_publish.py, scheduler_resource_dispatch.py, dashboard_workbench_context.py, scheduler_gantt_task_detail.py, scheduler_workbench_links.py
> 真相源: PlanIdentity 投影统一点 = `core/models/schedule_plan_identity.py`(PlanIdentity.to_dict) + `core/services/scheduler/schedule_result_view_context.py` plan_role_filter_fields(:277) / selected_plan_role(:201)
> 收口点(均已存在,禁新建): build_workbench_plan_context(workbench_links.py:187) / selected_plan_role(view_context:201) / gate _feedback_guard_context(workbench_links.py:149) / can_emit_feedback_write_urls(workbench_links.py:469)
> 本档案只产计划。承重(R54/R58/N1/N2)唯一合法修法 = 收口已存在点 + 绑契约/parity + 「我是故意的」注释；禁删/统一键名/透传/翻 fail-closed→fail-open。

> **2026-06-08 B 执行终态：G04 fixed。** R58 只补承重注释；R54 已把五个 guard 投影面收口到既有 `build_workbench_plan_context` / `plan_guard_fields_for_context`，并保留各自键面形状；R44 已收口到 core `selected_plan_role`。本档旧行号只作历史计划证据，后续不要重复处理 R54/R58/R44。

## 0) rg 回盘锚点（当前工作区，不信旧值）

| 锚点 | 实盘 file:line |
|---|---|
| R54 L1 reports `_copy_plan_guard_fields` def / call | scheduler_reports_workbench.py:36 / 77 |
| R54 L2 nav `_PLAN_GUARD_FIELD_NAMES` / `_plan_guard_fields` ret | scheduler_navigation_publish.py:12 / 82 |
| R54 L3 resource_dispatch `_copy_plan_guard_fields` def / call×2 | scheduler_resource_dispatch.py:64 / 95 / 199 |
| R54 L4 dashboard `_PLAN_GUARD_FIELD_NAMES` / apply | dashboard_workbench_context.py:8 / 130 |
| **R54 L5 gantt_task_detail 别名元组（不同机制!）** | scheduler_gantt_task_detail.py:9-15 / call build_workbench_plan_context:78 |
| R44 web 副本 selected_plan_role / sibling requested | scheduler_navigation_publish.py:36-37 / 32-33 |
| R44 import ROLE_ADOPTED 真来源 | scheduler_navigation_publish.py:6 = schedule_plan_query_service（**非 view_context**） |
| R44 core 收口点 selected_plan_role | view_context.py:201-202（多 `(pr or {})` 防御） |
| R58 病灶 context.update(guard_fields) / _publish_context | scheduler_navigation_publish.py:91 / 85 |
| R58 builder gate / 门控落点 | workbench_links.py:149-161(_feedback_guard_context, can_write:158) / 248 |
| 收口签名 build_workbench_plan_context / plan_id 形参 / dict | workbench_links.py:187 / 191 / 233 |
| 下游 fail-open 判定 _is_current_official_identity | workbench_links.py:292-304 |
| R42（跨簇,同改收口签名）入口 | navigation_context.py:21/57/76-78(plan_id=) |

## A) 原子子簇（必须同批/同提交 vs 可独立）

### A-1 原子子簇【SEQ-NAV】= R58 → R54 → R44（同物理文件 scheduler_navigation_publish.py，必须同批或显式串行）
- **原子原因**：三债全改同一文件 navigation_publish.py，且文件已 M/MM 漂移态。任一先落即移动 :91/:36/:12 行号，后落者照抄行号必错位。R58 注释插在 :91 上方 → 下方全下移；R54 增删 `_PLAN_GUARD_FIELD_NAMES` 元组键 → :36/:82 再移；R44 删 :36-37 def → 下方 `_plan_guard_fields` 再移。
- **内部顺序（硬序）**：
  1. **R58 先**（纯增量注释，零逻辑/零 dict 键变更，planned_deps「R58 注释先落」）。在 :91 `context.update(guard_fields)` 上方按符号定位插「我是故意的」注释（钉 4 点：覆盖未门控 guard / 已知护栏削弱 / 当前零消费 / 真放行走 can_emit_feedback_write_urls:469）。
  2. **R54 次**（B01 guard 收口 + 契约/parity，PHASE0§10#1：B01 先于 B02）。
  3. **R44 末**（B02 收口 selected_plan_role 到 core，PHASE0§10#1 要求 R44 排 B01 之后；动手前重新 rg 回盘 :7/:36-37）。
  - 理由链：承重注释先落不动逻辑 → guard 收口稳定闸门元组形态 → R44 才在稳定后回盘改 :36-37。

### A-2 R54 自身的多面 delegate（簇内子序，非跨债同批，但单债内一次改完）
- 收口点 build_workbench_plan_context 先承载 guard 字段（步骤1）→ 5 套手维面 delegate（步骤2）。5 面互为收口点下游消费者、彼此无顺序敏感，但**都依赖步骤1先落**。
- **5 面（含 corrections C 节种子，已 rg 复核）**：L1 reports:36 / L2 nav:12 / L3 resource_dispatch:64 / L4 dashboard:8 / **L5 gantt_task_detail:9-15（别名元组机制，与 L1-L4 的 `_PLAN_GUARD_FIELD_NAMES`/`_copy_plan_guard_fields` 不同符号）**。

### A-独立项
- R58 的「本轮注释」本身不与 R54/R44 逻辑耦合，仅同文件行号耦合 → 故归 SEQ-NAV 同批，不可真独立。
- R44 的 parity 测试（test_selected_plan_role_parity）可独立新增，但代码改动锁 SEQ-NAV 末位。

## B) 跨簇边（本簇成员 → 其他簇/债）

| 边 | 关系类型 | 说明 |
|---|---|---|
| **R54 ↔ R42**（同 C01，但不同原子簇）| 同文件同改（收口签名）| 二者同改 build_workbench_plan_context 签名(187)+返回 dict(229-258)。R42 删 plan_id 形参(191)/dict 行(233)；R54 加 guard 字段行。**MUST 同批次**——planned_deps「R54→R42 必须同批次」。批次张力：batch_hint 把 R42 列 Batch-3，deps 要求与 R54(Batch-2)同批 → **owner 裁**（R42 提前 or R54 延后）。R42 入口实盘在 navigation_context.py:76-78(plan_id=)，回盘已确认。|
| **R54 ↔ R60**（同 C01）| 同文件同改 | R60 删 plan_id 字段表(workbench_links.py)，与 guard 投影相邻。删 plan_id 表时禁动 dict:229-258 guard 段；同 R42 族,同批或明确隔离。|
| **R54 ↔ R22**（同 C01）| 真相源先于收敛 | 若 R22 改 view_context plan_role_filter_fields(277-347) → 真相全集先稳定,R54 再 delegate。R22 须升 24 键 exact parity(corrections A)。|
| **R54 ↔ R66**（同 C01）| 已满足的同文件行号前置 | R54 已先落;R66 已于 2026-06-09 按 suffix 签名重定位并删除 reports_workbench.py 私有死函数(删除前 :139-152)。两者不同符号不重叠;workbench_links.py LIVE `_context_summary` 仍在 :210/:399。|
| **R44 ↔ R21**（同 C01）| 收口范式参照（软）| R44 照搬 gantt_plan_query.py:46-47 re-export 范式；R21 若先删该 shim,R44 降级为直接 re-export core,**非硬阻塞**。|
| **R44 ↔ R72/R10**（同 C01）| 同概念别面（软）| effective_plan_role 内联实现(week_plan:232 / reports_plan_template_fields:81),明确**排除出 R44 收口范围**,owner 决定是否随 B02 一并收。|
| **R58 ↔ LB02**（同 C01）| parity 先于收敛（承重邻接）| LB02 标 file:workbench_links.py 同文件干扰;只要不改 :149-161/:469 符号签名即弱耦合。|
| **R54/R58 ↔ N1**（execution_context.py:129-130）| 承重邻接（同护栏概念）| N1 _identity_allows_query_membership_check 收敛成单字段 can_write_feedback,与本簇 guard 护栏同源;N1 修法=补注释+绑 parity,纳入 Batch-2 同期但**不同文件**,不撞行号。|
| **R54/R58 ↔ reports overrides 第二注入路径** | 修A失效B（双分叉）| reports 缺 plan_identity_error/blocking_error/blocking_scope 三阻断态字段,经 reports_execution_review_context.py(:overrides) 另一路注入(实盘确认 dashboard.py/reports_execution_review_context.py 也写这三键)。**禁把 reports 两条注入路径并一条**(丢阻断态)。|

## C) 相对旧 146 边的变化（逐条）

- **删（误标/假边，corrections B 节）**：本簇三成员的 interference_edges 全为 same_file 干扰边，B 节假边清单（R02↔R25 / R45↔{LB07,R33,R51} / R20↔{R08,R09,R12} / R32↔R15 / LB04↔{LB07,R33} / R26↔R43 / config_snapshot R26↔R71 / R13↔R18 解耦）**均不含本簇成员**，故本簇无边因 B 节被删。
- **删（已 fixed 前置，corrections E）**：簇 C01 内 LB06/R56/R57/R07/R16/LB03 已 fixed → 本簇与它们的潜在 same_file 边降为「fixed 前置已完成」非活动边。具体：**R54 ↔ LB06** 边降级（LB06 reports_page_support.py 已 fixed，仅缺认账注释）。
- **新增**：
  - **R54 第 5 套手维面 = gantt_task_detail.py:9-15**（corrections C 节升级 3/4→5 套）。registry/报告未连此边 → **新增 R54 内部 delegate 面**（注：机制不同,别名元组非 `_PLAN_GUARD_FIELD_NAMES`,R54 dossier 字段9「恰 4 套」verify 是按那两个符号名 scope 的,与本条不冲突,本条按「concept surface」计第 5 面）。
  - **新增 R54/R58 ↔ N1 边**（execution_context.py:129-130，执行重构新引入债，同护栏概念,Batch-2 同期）。
  - **新增 R54 ↔ reports 第二注入路径边**（双分叉:字段集分叉,reports 经 overrides 另一路）。
- **降级**：
  - **R44「web 多兜底/统一改行为」方向 → refuted 并反转**（corrections B/A:core 更防御 None,import 真来源是 schedule_plan_query_service 非 view_context）→ R44 危险度降（low,只喂模板显示 kwarg,不碰闸门）。
  - **R58「生产漏洞」→ 降为潜伏护栏削弱**（零生产消费,nav context 的 can_write_feedback 无下游读取,真放行走 can_emit_feedback_write_urls:469）。

## D) 承重前置（门控簇内结构动作 + 禁区行）

- **R58 承重注释先落**（A-1#1）= 门控 R54 动 navigation_publish.py 的前置（注释稳定后再动闸门元组）。
- **R54 guard 收口 + 契约/parity 必须先落**（PHASE0§10#1）= 门控 R44 动同文件 + 门控 R58 任何 Phase2 收敛。
- **真相源稳定（R22 若动 view_context:277-347）先于 R54 delegate**。
- **禁区行（簇内结构动作绝不触碰）**：
  - workbench_links.py:292-304 `_is_current_official_identity` 判定方向（`is_comparison`/`is_superseded` 用 `not <truthy>` fail-open + `is_current_executable_official_version is not True` fail-closed）—— **严禁为「统一」翻 fail-closed→fail-open**。
  - workbench_links.py:149-161 `_feedback_guard_context`（:157 formal_adopted / :158 can_write）+ :248 门控落点 + :469-473 can_emit_feedback_write_urls —— builder gate 本体,禁动。
  - view_context default_plan_resolution_dict 的 is_superseded=False / is_current_executable_official_version=False fail-closed 默认值,禁改方向。
  - navigation_publish.py:91 context.update(guard_fields)——R58 只在上方插注释,禁删整行/禁剔键(剔 can_write_feedback 须 owner Phase2+补 preview-adopted/非adopted 两反例 parity)。
  - navigation_publish.py:12-31 `_PLAN_GUARD_FIELD_NAMES` / :80-82 `_plan_guard_fields` / :32-33 requested_plan_role —— R44 禁顺手统一,R44 仅允许动 :6-7(import) + :36-37(删 def)。
  - **静默丢键禁保留**（灵魂线）：收口后禁保留 `if value is not None`(reports:53/resource:80/nav:82)/`if key in identity`(dashboard:131) 的丢键路径——漏键正是 fail-open 入口,缺键须走收口点 fail-closed 确定默认值,不得静默不写。
- **N1/N2 承重前置**：N1(execution_context:129-130 单字段收敛)/N2(operation_execution_event:156-163 return 0 sentinel)只标不动逻辑,补注释+绑契约（N1 钉 can_write_feedback⇒adopted-only 来源链；N2 钉非末位缺 id 必抛错）;owner_pending,只标不给终态。

## E) fixed 成员残留动作（认账注释）

- 本簇三成员 R54/R44/R58 **均已 fixed**（2026-06-08 B 执行补登）。旧计划段保留执行纪律，不再表示待办。
- 簇内已 fixed 前置（作为 DAG 起点已完成,残留=认账注释,不属本簇修法,但门控/邻接）：
  - **LB06**（reports_page_support.py,与 R54 共址 reports_workbench 链）：仅缺认账注释（corrections D）。
  - **R56**（load_bearing,navigation_context/reports_page_support/reports_execution_review_context 同提交）：走高风险结构路线删 `_is_execution_review_request` 本体,偏离铁律3,护栏未 fail-open,owner 须认账偏离（corrections D）。
  - **R07**（用 ValidationError 非 AppError/NOT_FOUND,跨文件错误类不对称）:owner 裁是否统一错误类。
  - **LB03**：仅缺认账注释,勿粘 §90 LB-B4 反向文案（现盘 fail-CLOSED 非 fail-OPEN）。

## 对抗复核（本簇 rg 自证）
- gantt_task_detail.py:9-15 确为别名元组 `(target,(aliases))` 机制,无 `_PLAN_GUARD_FIELD_NAMES`/`_copy_plan_guard_fields` → corrections「5 套」substance 成立,与 R54 dossier「4 套(按两符号名)」不矛盾,系 scope 不同,本档已显式调和。
- build_workbench_plan_context:187 / plan_id:191 / dict plan_id:233 实盘确认 → R54↔R42 同批互锁坐实。
- R44 import ROLE_ADOPTED 实盘 :6 = schedule_plan_query_service,非 view_context → corrections A 校正坐实。
- R58 病灶 :91 实盘唯一命中 → registry 旧 :86 不准坐实。

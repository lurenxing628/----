# 逐簇爆炸对抗 r1 — C-NAV-GUARD（主透镜：灵魂线热路径 + 收口等价）

> skeptic 第 1 轮 / 只读不改 / 默认怀疑。成员债 R54 / R44 / R58。
> 全锚点已在当前工作区 rg/Read 回盘（不信旧值）。fail-open 点 `_is_current_official_identity` 实盘坐实。

## 判定总表

| 债 | 判定 | 一句话 |
|---|---|---|
| R54 | 🔴 红 | split 收口若漏迁任一面的三关键键 / 缺键语义 → 静默 fail-open 脏写 |
| R58 | 🟡 黄 | 本轮纯注释安全；Phase2 剔 update 静默翻转 gate，须前置反例 parity |
| R44 | 🟢 绿（有 1 条前置硬序） | 收口到 core 更防御点，只喂模板显示，不碰闸门 |

---

## R54 — 🔴 红（本簇最危爆点，会炸）

**证据（实盘 file:line）**
- fail-open 判定 `_is_current_official_identity`：`web/viewmodels/scheduler_workbench_links.py:292-297`
  - `:294 not context.get("is_comparison")` + `:295 not context.get("is_superseded_by_newer_version")` = **truthy → 漏键/None 即放行（fail-OPEN）**
  - `:296 is_current_executable_official_version is True` = 漏键 fail-CLOSED（反向安全）
- 收口点 `build_workbench_plan_context`：`scheduler_workbench_links.py:187`，返回 dict `:230-248` **当前完全不收三关键 guard 字段**（只有 `:247 is_preview` / `:248 can_write_feedback`），所有面在 builder 输出后手补挂。
- execution_review 写闸：`scheduler_workbench_links.py:300 _is_formal_adopted_context`（调 :292）+ 二次复用 `can_emit_feedback_write_urls:469`。

**当前未坏**：6 个面全各带齐 `is_comparison` + `is_superseded_by_newer_version` + `is_current_executable_official_version`：
- L1 reports_workbench `web/viewmodels/scheduler_reports_workbench.py:42/43/46`（mapping，缺键路径 `if value is not None` 丢键）
- L2 nav_publish `web/routes/domains/scheduler/scheduler_navigation_publish.py:17/18/21`（元组，`:82 if fields.get(key) is not None` 丢键）
- L3 route resource_dispatch `web/routes/domains/scheduler/scheduler_resource_dispatch.py:69/70/73`
- L4 dashboard `web/viewmodels/dashboard_workbench_context.py:13/14/17`（`:130 for key in`，`if key in` 丢键）
- L5 gantt_task_detail `web/viewmodels/scheduler_gantt_task_detail.py:13/14/17`（别名元组 `_PLAN_GUARD_FIELD_ALIASES`，`:96 if value is not _MISSING` 丢键——**第 3 套独立缺键语义**）

**灾难链**：A-2 步骤2「5 套 delegate 到收口点 + 删私有列表」时，三套缺键写法互不相同（`is not None` / `if key in` / `is not _MISSING`），任一面漏迁或收口点未给 fail-closed 确定默认 → 该面 `is_comparison`/`is_superseded` 键缺失 → 下游 `not context.get(...)` = `not None` = True → `_is_current_official_identity` 误判现行官方版 → execution_review(:300/:469) 放行 → **旧正式版/比较版冒充现行采用方案，写侧护栏被绕，向历史/比较方案写现场事实（脏写、不可逆）**。

**修正建议（前置/顺序/禁区）**
- 禁区行（绝不触碰方向）：`scheduler_workbench_links.py:294-296` 三键判定方向；view_context `default_plan_resolution_dict` 的 is_superseded=False / is_current_executable_official_version=False fail-closed 默认值。
- 收口后**禁保留** `if value is not None`(reports:53/nav:82) / `if key in`(dashboard) / `if value is not _MISSING`(gantt_task_detail:96) 丢键路径——缺键须走收口点 fail-closed 确定默认，不得静默不写。
- parity 必测三关键键 × {缺失/None/False/True} × 拦放矩阵，逐面（含 L5）。
- 同批次互锁：R42 删 plan_id 形参(:191)+dict 行(:233) 与 R54 加 guard 字段同改 build_workbench_plan_context → **MUST 同批**。owner 须裁 batch_hint(R42=Batch-3) vs deps(同 R54 Batch-2) 张力。
- owner_pending：只标不给终态。

## R58 — 🟡 黄（条件：本轮注释可做；Phase2 收敛须前置反例 parity）

**证据**：`scheduler_navigation_publish.py:88` raw can_write_feedback 喂 builder（gate 成门控值落 `scheduler_workbench_links.py:248`），`:91 context.update(guard_fields)` 随后用 raw 覆盖回门控值。零生产消费坐实：`scheduler_navigation_links.py` grep can_write_feedback **零命中**；真写链接收口 `can_emit_feedback_write_urls` 两消费者（reports_workbench.py:361 读 row_context / route resource_dispatch.py:202 读 filters）**均不读 nav context**。

**条件/灾难链**：本轮仅在 :91 上方按符号插「我是故意的」注释（钉 4 点）→ 安全。误删整行 → 连带丢 can_dispatch，superseded 派工护栏失效（响声有，违规）。Phase2 剔 can_write_feedback 一键 → 现有 keep_plan_guard_fields 用例（adopted+非preview，builder-gated≡raw）仍绿，但 preview-adopted / 非 adopted 路径静默 True→False 翻转 → **静默炸点**。
**前置**：Phase2 须先补 preview-adopted + 非 adopted 两反例 parity（先迁测试后改码），且排在 R54 之后。禁区行：:91 整行 / :80-82 / :12 元组 / workbench_links.py:149-161,248,469-473。

## R44 — 🟢 绿（1 条前置硬序）

**证据**：web 副本 `scheduler_navigation_publish.py:36-37 return str(plan_resolution.get("selected_role") or ROLE_ADOPTED)`；core 收口点 `core/services/scheduler/schedule_result_view_context.py:201-202 return str((plan_resolution or {}).get(...))` **更防御**。只喂 effective_plan_role= 模板显示 kwarg，不碰任何闸门。import 真来源 `:6 schedule_plan_query_service`（非 view_context）。唯一行为差异 None→raise vs "adopted"，生产无 None 调用方（week_plan/gantt 入参恒 dict）。
**前置硬序**：B01（R58→R54）必须先落本文件，R44 排末位且动手前重新 rg 回盘 :6/:36-37（文件 M/MM 漂移态）。仅允许动 :6-7(import)+:36-37(删 def)。owner_pending。

---

## 漏项（本轮新发现，计划未覆盖）

1. **第 6 个手维 guard/drop 面被 cluster/dossier 完全漏列**：`web/viewmodels/scheduler_resource_dispatch.py:40-73` `_PUBLIC_FILTER_DROP_KEYS`（含 is_comparison:68 / is_current_executable_official_version:70 / is_superseded_by_newer_version:71，外加 L1-L5 都没有的 `is_current_executable_version:69` / `schedule_result_status:63` / `scenario_name:72`）。它是脱敏 drop 集（:270 `if key not in _PUBLIC_FILTER_DROP_KEYS`），机制≠guard 投影，但键集独立手维、含三关键键。R54 统一时若误当第 7 套 guard 面去并、或漏随 guard 字段集同步 → 公开 filters 漏脱敏 / 误删。**cluster 把 L3 只标 route 文件，漏 viewmodel 文件**。
2. **同文件第 2 套 superseded/comparison 消费判定**：同文件 `:148-194`（`_official_kind_label:152` / `_public_plan_kind_label:161` / `_official_guardrail_text:172` / `_public_plan_guardrail_text:180`）独立读 `is_superseded_by_newer_version`(:153/:173) / `is_comparison`(:166/:190)，不走 `_is_current_official_identity` 收口。R54 收口口径若与这套消费不一致 → 文案/护栏判定分叉。
3. **L5 `is_comparison` 二次衍生合并**：`scheduler_gantt_task_detail.py:98 context["is_comparison"] = bool(context.get("is_comparison") or data.get("is_comparison_plan"))` —— L5 独有，从 `is_comparison_plan` 别名补 is_comparison。统一收口若漏迁此行 → is_comparison_plan 来源丢失 → 该面 is_comparison 静默变 falsy → fail-OPEN。别名元组 :13 `("is_comparison", ("is_comparison", "is_comparison_plan"))` 也含此别名，收口点须同时吸收别名映射否则丢键。
4. **cluster L5 路径错**：cluster 写 `web/routes/domains/scheduler/scheduler_gantt_task_detail.py`，实盘在 `web/viewmodels/scheduler_gantt_task_detail.py`（route 路径不存在）。R54 动手前按真实 viewmodel 路径回盘。

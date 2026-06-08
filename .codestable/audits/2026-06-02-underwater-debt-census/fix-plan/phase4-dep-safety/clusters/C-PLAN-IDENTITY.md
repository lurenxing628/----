# 簇 C-PLAN-IDENTITY 原子重建报告（方案身份族）

> 成员债 R21 / R22 / R23 / R72 · 桶 B02 身份族 · 簇 C01 子分区
> 只读不改产物（gitignored）。行号均 2026-06-05 rg 回盘，不信旧值。
> 收口点全部已存在（铁律 5），无新建第二模块。

## 0. 成员速览（回盘确认）

| 债 | 主文件:行 | 病理 | 承重 | owner_pending | 修法类 | 收口/处置点 |
|---|---|---|---|---|---|---|
| R23 | `core/models/schedule_plan_role.py:21` `_normalize_role` + `core/services/scheduler/schedule_plan_query_service.py:17/:102` import/调用 | P5 dedup（已清理） | false | false | 收口 dedup 已落 | model `_normalize_role`（已存在）|
| R22 | `core/services/scheduler/schedule_result_view_context.py:73` `default_plan_resolution_dict`（2026-06-08 已收口）| P5 收口 | false | false | fixed | 已调用 `build_plan_identity(...).to_dict()`；`normalize_plan_role` / builder / `PlanIdentity.to_dict` 均保留 |
| R21 | `core/services/scheduler/gantt_plan_query.py` 三死 shim @42/46/59 + import @14-25（2026-06-08 已删） | P3 死 shim | false | false | fixed | 三死 shim 已删；**保留 dpr_dict wrapper @32-39** 与四个 LIVE range 函数 |
| R72 | `web/routes/domains/scheduler/scheduler_gantt.py:136` + `scheduler_week_plan.py:67` `_get_plan_role_arg` 双份 | P5 dedup(N1家族) | false | **true** | 收口 dedup | web `scheduler_utils.py`（已存在，须补 `from flask import request`）|

---

## A. 原子子簇（必须同批/同提交 vs 可独立）

### 原子子簇 ① 【R22 + R21】— dpr_dict wrapper precondition 强耦合（硬序，必须同窗口）

- **成员**：R22（收口委托）、R21（删 3 死 shim）。
- **原子原因（precondition 前置 + parity 先于收敛）**：
  - R21 的 `gantt_plan_query.py:32-39` `default_plan_resolution_dict` wrapper（try → `_default_plan_resolution_dict`，except 重抛 loud 文案「未知的排产方案角色：{role}」）是 **R22 收口的 precondition**：契约测试 `tests/schedule/summary/test_schedule_result_view_context.py:294-301`（`test_gantt_plan_query_wrapper_keeps_legacy_bad_role_message`）钉死该遗留文案。
  - R21 **绝不可先删该 wrapper**，否则 R22「保留遗留文案包装」约束失效、契约测试变红。
  - R21 删的另 3 个 shim（resolve_plan:42 / selected_plan_role:46 / _has_explicit_gantt_range:59）与 R22 在 **同物理文件 gantt_plan_query.py 相邻但不同区段**，R21 删 import 区(:14-25)会让 wrapper 行号上移约 9 行 → R22 若用 file:line 锚 wrapper 须重盘，**建议 R22 用符号名 `default_plan_resolution_dict` 锚定**。
- **内部顺序（谁先谁后）**：
  1. **R22 先**：(a) 落 parity 测试（24 键 exact `==`，Batch-1 网，先于收敛）→ (b) 收口委托 build_plan_identity/SchedulePlanResolution.to_dict；
  2. **R21 后**：删 3 死 shim + 3 import，**严守保留 :32-39 wrapper**；
  3. 理由：parity 先于收敛（R22 自身两步内部硬序）；R21 删 shim 不依赖 R22 完成，只须 R22 已锁定「wrapper 保留」这一约束即可，故 R21 可紧随 R22 同提交，但顺序上 R22 在前更安全（确保 wrapper 不被误判为可删空壳）。

### 原子子簇 ② 【R23】— 已独立先落（B02 热身第一刀）

- **成员**：R23 单债。
- **原子原因**：无前置债（registry `planned_deps_hint=none`、`co_change_within_group` 空、`fix_invalidation_risk=none`）。收口点 model `_normalize_role` 是唯一动作，无其他债排队收此符号。
- **内部顺序**：单债无内部序。**唯一软排序**：与同文件兄弟 R34（同住 query_service.py，属 NAV/REPO 簇）协调——R23 最小落法已令其后锚点净上移 4 行（import +1、重复块 -5；`get_plan_time_span_for_resolution:210→206`），R34 后续必须基于删后现盘按符号重 rg 定位。**与 R22（view_context）无序约束**。
- **独立性**：R23 收口范围**仅** model:21 / service 旧重复体两份字节级重复逻辑，**不碰** view_context:65 `normalize_plan_role`（带校验的第三变体，语义不同），故与 R22 的 :73-150 区段零重叠，可任意先后。

### 原子子簇 ③ 【R72】— 独立叶子（owner 裁断后落，与 R44 协调非排序）

- **成员**：R72 单债。
- **原子原因**：叶子级弱耦合，`fix_invalidation_risk=无直接失效`，无硬前置债。收口落点 web `scheduler_utils.py` 与簇内其他债零符号冲突。
- **内部顺序**：单债无内部序。**同文件行号联动（非语义碰撞）**：与 R21/R55（同住 scheduler_gantt.py）、R44（同住两路由 import 块）存在 import/行号联动 → 谁后做谁须重新 rg 回盘（week_plan.py 当天高频漂移，def 已 +7、call 已 +15）。**建议与同文件邻债同批或显式串行**避免交叉位移返工。
- **跨子簇关系**：R72 与原子子簇①的 R21 **同住 scheduler_gantt.py**，但 R21 改 query shim 层、R72 删 :136 def + :181/:325 call，**不同区段、低碰撞**，仅需行号联动协调，非原子合并。

> **结论：3 个原子子簇。** ①{R22,R21} 硬序同窗口；②{R23} 独立先落；③{R72} 独立叶子。①②③之间仅 R21↔R72 同文件行号联动（软），无原子合并必要。

---

## B. 跨簇边（本簇成员 → 其他簇债）

| 本簇债 | 指向外簇债 | 外簇/落点 | 关系类型 | 强度 | 处置 |
|---|---|---|---|---|---|
| R22 | **LB03** | C01 承重族（`schedule_plan_identity_builder.py`，LB=true，B01）| **parity 先于收敛 + same_symbol(build_plan_identity)** | 软序 | R22 只 CALL build_plan_identity 不改 builder 内部。LB03 把 P4 静默吞改 loud 只改两 parse 键**取值**不改键集；R22 parity 用「键集+取值」exact 断言即覆盖。**先 R22 parity 钉键集（Batch-1）→ R22 收口 / LB03 都在其后，互不破键集**。B01（LB03 承重注释+guard 收口）须全局先落于 B02 身份族动工。|
| R22 | **R44** | NAV-GUARD 簇（`scheduler_navigation_publish.py:36` selected_plan_role 副本）| same_file 标记（view_context）实为**假** | — | R44 真改 navigation_publish.py，本文件 selected_plan_role 在 :201 远离 R22 :73-150。不撞行号、不撞 dict 键。**删边**（见 C）。|
| R22 | **R54** | REPORTS 簇（`scheduler_reports_workbench.py`，LB=true）| same_file 标记（view_context）实为**假** | — | R54 改 viewmodels plan-guard 字段列表，rg 确认不触 schedule_result_view_context.py。**删边**（见 C）。|
| R23 | **R34** | NAV/REPO 簇（同住 `schedule_plan_query_service.py`）| **同文件同改（行号联动，非语义碰撞）** | 软序 | R23 最小落法已落 → 其后锚点净上移 4 行（`get_plan_time_span_for_resolution:210→206`）。R34 后续基于删后现盘按符号重 rg 定位。无硬序。|
| R21 | **R44** | NAV-GUARD 簇 | **收口范式先例（软）** | 软序 | R21 删本文件 selected_plan_role re-export shim(:46) 会抽掉 R44 收口照搬的 re-export 范式先例 → R44 应**直接 re-export core 收口点**，不照抄 gantt_plan_query。非硬阻塞，宜同 Batch-4 协调。|
| R21 | **R55** | GANTT 簇（同住 scheduler_gantt.py / gantt_service.py）| 同文件行号联动 | 软 | 改不同区段，谁后做谁重盘。无硬序。|
| R72 | **R44** | NAV-GUARD 簇 | **收口落点协调（非排序）** | 协调项 | R72→web `scheduler_utils.get_plan_role_arg`（请求层读 flask.request）；R44→core `schedule_result_view_context.selected_plan_role`（已 resolve 角色）。**两个不同落点**，分层裁断不同：R72 绝不能下沉 core（破 core→flask 越层），R44 在 core 有同名孪生。owner 须共识「web/core 各落各点、不硬塞同一 helper、也不各建各的」。无硬序。|
| R72 | **R55 / R10** | GANTT 簇（scheduler_gantt.py / gantt_service.py / week_plan 关联）| 同文件行号联动 | 软 | week_plan.py 当天高频漂移热点，落地前以实时 rg 重盘。|

---

## C. 相对旧 146 边的变化（删/新/降）

### 删除的边（corrections B 节假边 + 本簇核实）

1. **删 R22↔R23（view_context.py 假同文件边）**：interference 标 `file:view_context.py`，但工作区**无 view_context.py 文件**（registry 文件名简写）。R23 真改 `schedule_plan_role.py:21` + `schedule_plan_query_service.py:17/:102`，**不碰** view_context:73 区段；R22 收口在 :73-150 孤立区段。零重叠 → **假边删除**。
2. **删 R22↔R44（view_context 同文件边）**：corrections 标 R44 真实 primary_file = `scheduler_navigation_publish.py`；本文件 selected_plan_role 在 :201，远离 R22 :73-150。不撞 → 删 same_file 边（保留 §B 的范式协调软关系，但非碰撞边）。
3. **删 R22↔R54（view_context 同文件边）**：R54 真改 viewmodels（`scheduler_reports_workbench.py` 等 5 套手维列表），rg 确认不触 schedule_result_view_context.py。R54 真实 primary_file 在别处 → 删 same_file 假边。

### 新增的边

4. **新增 R22→LB03（parity 先于收敛 / same_symbol build_plan_identity，跨簇软序）**：旧图 R22 多按 same_file 连邻居；本轮回盘 R22 真正的语义依赖是收口符号 build_plan_identity——LB03 给 canonical 加了 `result_summary_parse_failed/reason` 两键（drift 来源，22≠24）。这是**承重族跨簇边**，旧 146 边中按 same_symbol 已有标记，本轮**强化为 parity-先于-收敛排序边**（先 R22 parity 钉 24 键 exact，再收敛）。

### 降级的边

5. **降级 R21↔R44**（gantt_plan_query / scheduler_gantt same_file）：旧标 same_file 硬碰撞 → 实为**软范式先例**（R44 应直接 re-export core，不照抄 R21 shim）。降为软协调，非硬阻塞。
6. **降级 R72↔R44**（scheduler_gantt + week_plan same_file）：旧标双文件同改硬碰撞 → 实为**收口落点协调项**（web vs core 不同落点 + import 块行号联动），降为协调+软联动，无硬序。
7. **降级 R21/R72/R55 三者 scheduler_gantt.py same_file 簇内边**：均改不同区段，由「同文件硬串行」降为「行号联动软协调（谁后做谁重盘）」。

### 不变（保留为真边）

- **保留 R22↔R21（强耦合硬序）**：dpr_dict wrapper precondition，原子子簇①核心边，不可删不可降。
- **保留 R23↔R34（同文件行号联动软序）**：query_service.py 真同文件，R23 删行致行号位移属实。

---

## D. 承重前置（簇内 LB/N1/N2/R03/R58 承重点门控）

本簇 4 个成员**自身全 `load_bearing=false`**，`lb_no_touch=null`、`lb_colocation_danger=none`。簇内**无承重债主体**，但有两条**跨簇承重前置门**与一处契约前置：

1. **LB03 承重前置（全局门，B01 先落）**：R22 收口委托的 `build_plan_identity` 所在 `schedule_plan_identity_builder.py` 是承重（LB03，B01）。**禁区行（R22 绝不改，只 CALL/读）**：
   - `schedule_plan_identity_builder.py:158`（build_plan_identity 签名）及其函数体；
   - `core/models/schedule_plan_identity.py:46-71`（PlanIdentity.to_dict 24 键定义，含 :58/:59 两 parse 键）。
   - 门控：LB03 承重注释 + guard 收口（B01）须**先于** B02 身份族动工，R22 才动方案身份族收口。
2. **N1 家族（R72 病理来源，非本簇承重禁区，但属 N1 命名统一对象）**：R72 是 N1-dup（同段 plan_role 取参散两处）。N1 真正的承重不对称落在 `scheduler_resource_dispatch_execution_context.py:129-130 can_write_feedback`（在别簇），R72 仅是 N1 家族的 web 取参 dedup，**无承重禁区行**。
3. **契约前置（parity 先于收敛，非承重但门控收敛）**：
   - R22 收敛（删 :77-100 手搓 dict 改委托）**前置**必须落 **24 键 exact `==` parity 测试**（不可照抄 `regression_scheduler_plan_identity_evidence_contract.py:194` 的 22 键 superset，那是 drift 0→2 而 CI 全绿的根因，须同步升级为 24 键 exact）。
   - R21 删 3 shim **不需** parity（纯透传等价），但**禁区**：`gantt_plan_query.py:32-39` dpr_dict wrapper + :11-13 其 import（R22 precondition），`:50-156` 全部 LIVE range 辅助函数（gantt_service 真依赖，误删整模块=甘特周计划范围解析静默断裂）。

### 禁区行汇总（簇内绝不碰）

- `schedule_plan_identity_builder.py:158` + 函数体（LB03 承重，R22 只 CALL）
- `core/models/schedule_plan_identity.py:46-71`（PlanIdentity.to_dict 24 键，R22 只读）
- `gantt_plan_query.py:32-39`（dpr_dict wrapper，R21 保留 / R22 precondition）+ :11-13 其 import
- `gantt_plan_query.py:50-156`（4 个 LIVE range 函数，整文件保留）
- `schedule_plan_query_service.py:101-104`（resolve_plan 静默归一→loud raise 双段，R23 只换 :102 符号来源不改语义）
- view_context `normalize_plan_role:65`（带校验第三变体，R23 绝不并入 dedup，误并=ValueError→ValidationError 行为变更+静默错身份）

---

## E. fixed 成员前置残留动作

本簇当前 **R21/R22/R23 已 fixed**；R72 仍 planned（R72 owner_pending）。

本簇收敛依赖的外簇承重前置已满足：
- **LB03（B01）**：已 fixed，R22 收敛所需的承重认账注释 + guard 收口已落账。
- 簇内**无 LB03/LB06/R56/R07/R16/R57 这类已 fixed 成员**作为前置，故无「认账注释残留动作」落在本簇。
- **owner_pending 残留**：仅 R72 仍待 owner 裁断「收口名公开化 + 与 R44 web/core 落点共识」。R22 已按 O14 裁定 fixed，不再等待裁断。

# 逐簇爆炸对抗 r1 · C-PLAN-IDENTITY · 主透镜【承重误删 LB】

> 成员 R21 / R22 / R23 / R72 · 只读不改 · 行号 2026-06-05 实时 rg 回盘
> skeptic 默认怀疑：找不到爆点才算绿。本轮主攻 Q1 承重误删 + 全过六质问。

## 0. 逐债判定速览

| 债 | 判定 | 一句话 |
|---|---|---|
| R21 | 🟢 绿（有 1 条强制前置） | 3 死 shim 实测零生产/零测试消费，删之安全；强制前置=R22 锁定「wrapper 保留」+ 整文件保留 LIVE 区。 |
| R22 | 🔴 **红（计划低估了行为变化）** | 收口委托 build_plan_identity 后 no_history 页 `result_summary_parse_failed` 取值 **False→True 翻转**，下游报表模板字段行为静默改变；计划只要求「键集 exact==」parity，**抓不到取值翻转**。 |
| R23 | 🟢 绿 | 两处字节级相同纯 dedup，收口到已存在 model `_normalize_role`；唯一红线（误并 view_context:65 带校验变体）已被禁区拦截。 |
| R72 | 🟢 绿（owner 裁断后落） | 6 行纯取参 dedup，落 web `scheduler_utils.py`；分层红线（绝不下沉 core）已钉死，唯一硬动作=补 `from flask import request`。 |

---

## 1. 🔴 R22 —— 本簇唯一红，新爆点：no_history 收口取值翻转（计划漏判）

### 实锤证据链（本轮盘上跑出，决定性）

- 手搓内层 dict（`schedule_result_view_context.py:77-100`）= **22 键**；canonical `PlanIdentity.to_dict`（`schedule_plan_identity.py:46`）= **24 键**；`MISSING={result_summary_parse_failed, result_summary_parse_reason}`、`EXTRA=[]`。与 dossier 字段 7 字字吻合。
- **关键反例（dossier 漏判处）**：实跑真实代码——
  - `parse_result_summary_payload(None).parse_failed = False`（`scheduler_history_parser.py:53`，None/"" 走 missing 分支，parse_failed=False）
  - **但** `_summary_unavailable(None, parse) = (True, '排产摘要缺失')`（`schedule_plan_identity_builder.py:128`，第一行 `if summary_parse.parse_failed` 为 False 不命中，落到「摘要缺失」分支返回 True）
  - 故 build_plan_identity（result_summary=None）→ `result_summary_parse_failed=bool(summary_unavailable)=True`（builder:233）。
- 当前手搓 dict **无此键** → 下游 `plan_role_filter_fields`（view_context:329-330）`bool(plan_identity.get("result_summary_parse_failed") or data.get(...))` 两路皆缺 ⇒ 恒 **False**。
- **结论**：R22 收口后，no_history/missing_history 页（调用点 :449/:457）该键从 **False 翻成 True**。

### 灾难链（改 X→静默→坏数据流到 Y）

改 R22「删 :77-100 手搓 dict 改委托 build_plan_identity」→ no_history/missing_history 页 `result_summary_parse_failed` 静默 False→True
→ 下游读该键者行为反转：`reports_plan_template_fields.py:45`（`if ... or data.get("result_summary_parse_failed")`）、`:61`（`if data.get("result_summary_parse_failed")`）走入「解析失败」分支
→ 3 套手维 plan-guard 列表（`scheduler_navigation_publish.py:27` / `scheduler_resource_dispatch.py:79` / `dashboard_workbench_context.py:23`）把该键纳入并据此渲染 → **只读无历史页报表模板字段渲染态翻转**（本无历史的方案被标成「摘要解析失败」）。
→ 静默：CI 不红——因计划 parity 只要求「键集 exact ==」（dossier 字段 7/11），键集补齐后 == 成立，但**取值翻转无人断言**。evidence_contract:194 现 `set(identity) >= {…}` superset（22 键、漏列两 parse 键），收口后仍恒真，drift 与翻转双双逃逸。

### 为何计划判定不足

dossier 字段 7「委托后多出 3 键无害（schedule_result_status/schedule_lock_status/detail_saved 手搓已有）」**只覆盖了手搓已存在的 3 键**，把 MISSING 两 parse 键当成「补键」处理，**未识别这两键在 no_history 场景的取值是 True 而非 False**。这正是「测试绿但护栏已破」的静默失效——severity 名义 medium（只读页），但**行为变化是确凿存在的**，不是「纯补键无害」。

### 修正建议（前置/顺序/禁区）

1. **parity 测试升级为「键集 + 取值」exact 双断言**（不止键集）：对 no_history/missing_history 实际传参（version=None, result_summary=None, source_table=schedule, effective_role=adopted）断言 `result_summary_parse_failed/reason` 的**具体取值**==canonical 输出（=True/'排产摘要缺失'）。这是把翻转钉成「owner 显式知情决策」的红线，**先于收口落地（Batch-1）**。
2. **owner 裁断项（升级）**：no_history 页该键应保持旧 False 还是接受新 True？若要保旧语义，收口时须显式覆写（传 result_summary 非 None 哨兵 / 收口后 override），否则即行为变更。**owner_pending=true，本报告不替其定稿，但标红「这是行为变化非纯补键」**。
3. **承重禁区（R22 只 CALL 不改，实证成立）**：`schedule_plan_identity_builder.py:158`（build_plan_identity 签名 + 函数体，LB03 承重）、`schedule_plan_identity.py:46-71`（PlanIdentity.to_dict 24 键）。R22 委托是包内同层 `from .schedule_plan_identity_builder import build_plan_identity`，0 跨层、0 环（builder 顶部仅 import core.models.*，不反向 import view_context）。**承重误删风险=无**——R22 不删/不统一/不透传 builder 内部。
4. **外层 `is_official` 取值**（view_context:142 `bool(plan_identity["is_official"])` 方括号硬取）：收口后若整体委托 SchedulePlanResolution.to_dict 需确认仍提供该键，否则 KeyError；属正向改善（改 .get 更稳），非破坏。

---

## 2. 🟢 R21 —— 绿（强制前置已在计划中，实证零消费）

### 实证（本轮独立 rg）

- `gantt_service.py:12` import 块仅取 4 个 LIVE：`attach_gantt_range_metadata / build_empty_week_plan_payload / get_version_time_span_dates / resolve_gantt_range_for_version`，**不含任一死 shim**。
- 3 个删除目标全仓回扫：
  - `_has_explicit_gantt_range`：rg 全仓仅命中 `gantt_plan_query.py:59` 其 def 自身，**零消费者（连测试都没有）**。
  - `resolve_plan@42` / `selected_plan_role@46`：全仓 import gantt_plan_query 的只有 gantt_service:12（不含它们）+ 测试 `regression_schedule_result_view_context.py:295`（只调保留的 wrapper）。callgraph 5/2 条 inbound 经源码 import 实证为同名假阳性。
- 续命测试 `regression_schedule_result_view_context.py:294-301` 只断言 `default_plan_resolution_dict("bad")` 抛「未知的排产方案角色：bad」——只测 R21 **保留**的 wrapper（:32-39，实测在位，:38 loud raise ValidationError）。

### 为何不红（但有强制前置）

承重误删的两个真实雷点已被 cluster 禁区覆盖，复核成立：
- **禁区 A**：`gantt_plan_query.py:32-39` dpr_dict wrapper + `:11-13` 其 import（R22 precondition）——R21 删它=续命测试红 + R22「保留遗留文案」约束失效。**R21 绝不碰**。
- **禁区 B**：`:50-156` 含 `get_version_time_span_dates@50`（**它是 shim 但被 gantt_service:15/179/187 真用，不在删除清单**）+ 3 个真 LIVE range 函数。误判整模块死=甘特周计划范围解析静默断裂。
- **强制前置**：R22 必须**先**锁定「wrapper 保留」约束，R21 才删另 3 shim（顺序：R22 收口 → R21 删 3 shim + 3 import）。R21 删 import 区致 wrapper 行号上移约 9 行 → **R22 锚 wrapper 用符号名不用 file:line**。
- 灵魂线：纯删透传空壳，不新增兜底/静默回退/吞错；保留的 wrapper 是 loud raise，不动即不违灵魂线。分层 0 违规（纯删，不新增 import）。

---

## 3. 🟢 R23 —— 绿（纯 dedup，红线已拦截）

- 两处函数体字节级相同（实测）：`schedule_plan_role.py:21-23` ≡ `schedule_plan_query_service.py:28-30`，均 `str(role or "").strip()` / `text or ROLE_ADOPTED`。收口到已存在 model `_normalize_role`，service→model 合法层向（service:9 已 import 该 model），0 环（model 仅 import typing）。
- **唯一红线（已被禁区双拦截）**：绝不把 service:28 误并 view_context `normalize_plan_role:65`——后者带 `VALID_PLAN_ROLES` 校验、`raise ValidationError`（实测 :65-70）；而 resolve_plan 双段（:106 静默归一 `_normalize_role` → :107-108 `if not in VALID: raise ValueError`）依赖「先静默归一再 loud ValueError」。误并 → role="bogus" 抛错类型 ValueError→ValidationError、抛错点前移 → 上游 catch ValueError 者静默漏接 → 错误角色当合法放行（身份族最怕的静默错身份）。**cluster 禁区 + dossier §4/§7 已拦截**。
- 承重误删风险=无（lb=false，纯 dedup 非删承重）。无前置债，可独立先落。软排序：与同文件 R34（query_service.py）协调，R23 先删 :28-30 三行让 R34 基于删后行号定位。

---

## 4. 🟢 R72 —— 绿（owner 裁断后落，分层红线已钉）

- 两份 `_get_plan_role_arg` 实测：`scheduler_gantt.py:136` / `scheduler_week_plan.py:67`（dossier 已修正 week_plan +7 漂移），6 行纯取参（`request.args.get("plan_role")` → strip → `text or None`），字节级相同。call 点 gantt:181/325、week_plan:288/375。tests/ 零守卫。
- 收口落 web `scheduler_utils.py`（实测存在，仅 `from flask import g`，**缺 request**——本债最易踩坑，须补 `from flask import request`）。week_plan:47 已 `from .scheduler_utils import` 同方向边，0 环。
- **分层硬红线（实证成立）**：getter 读 `flask.request`，`rg "request.args.get.*plan_role|def get_plan_role_arg" core/` 为空 → core 无孪生。**绝不下沉 core/services 或 core/shared**（=core→flask 跨层 import，破 0 违规）。与 R44（收 core，已 resolve 角色）天然两个落点。
- 灵魂线：空串→None 是真实语义，收口**绝不顺手加默认 ROLE_ADOPTED 兜底**（否则静默选错计划角色，low 升正确性 bug）。承重误删风险=无。owner_pending=true（裁①公开名②与 R44 落点共识），只标不给终态。

---

## 5. 六质问点全过结论

- **Q1 承重误删**：簇内 4 债自身 lb=false，**无承重误删**。R22 只 CALL build_plan_identity（LB03 承重，禁区 builder:158 / identity:46-71，不改）；R21 禁区 A/B 整文件保留；R23/R72 纯 dedup 非删承重。✅ 但 R22 收口存在**非承重的取值翻转**（见 §1，主爆点）。
- **Q2 分层导入环**：R22 委托=包内同层 0 环；R21 纯删不新增 import；R23 service→model 合法向、model 仅 import typing 0 环；R72 绝不下沉 core（红线已钉），week_plan→utils 同向边已存在 0 环。✅ 0 违规可保。
- **Q3 迁移耦合**：v19.py:14-19 DB CHECK `source_table='schedule'` + `effective_plan_role='adopted'`。R22 收口委托 build_plan_identity 须传 `source_table=schedule / effective_role=adopted`，手搓 dict 现值 `SOURCE_SCHEDULE="schedule"` / `ROLE_ADOPTED="adopted"`（实测常量）**正好对齐 v19 CHECK**，改码不破探针。✅ 但 parity 测试须把 source_table=schedule 钉进断言，防收口误传他值触发 DB CHECK。
- **Q4 灵魂线热路径**：R22 收口**不新增兜底**，反而消除「缺键静默 False」——但此次消除是「False→True 翻转」，不是单纯去回退（见 §1）。R21/R23/R72 均无新增静默回退/吞错。✅（R22 取值翻转单列红）
- **Q5 收口行为等价**：R23 两路字节级等价无反例 ✅；R72 两副本字节级等价无反例 ✅；R21 死 shim 纯透传等价 ✅；**R22 不等价**——no_history 场景 result_summary_parse_failed 旧 False vs 新 True（🔴 §1）。
- **Q6 测试迁移序**：R21 删 3 shim 无需迁测试（零引用）；R22 须**先**升级 parity（键集→键集+取值 exact）+ evidence_contract:194 superset→24 键 exact，再收口；R23/R72 收口后补单源守卫（非前置）。续命测试 :294-301 R21/R22 都不得碰（R22 保留 wrapper）。

---

## 6. 漏项（本轮新发现 / 计划未覆盖的爆点或缺失前置）

1. **【最重要】R22 收口的 no_history 取值翻转未被计划识别**：dossier 把 MISSING 两 parse 键当「无害补键」，实测 `_summary_unavailable(None,·)=(True,'排产摘要缺失')` → 收口后该键 False→True，下游 `reports_plan_template_fields.py:45/61` + 3 套手维列表行为反转。计划的「键集 exact==」parity **抓不到取值翻转**。前置缺失：parity 必须升级为「键集+取值」双断言并对 no_history 实参断言具体取值；owner 须显式裁「保旧 False 还是接受新 True」。
2. **R21 删 import 区致 wrapper 行号上移（≈9 行）**：计划已提醒 R22 用符号名锚，但若 R22 先收口、R21 后删，R22 落地时 wrapper 仍在原行；若顺序反了（R21 先删），R22 锚点漂移。强制顺序「R22 锁约束 → R21 删」必须执行批次显式串行，否则同窗口并行改同文件易交叉返工。
3. **evidence_contract:194 superset 是双重逃逸口**：不仅放过 drift（0→2），收口后也放过取值翻转。必须与 R22 parity 同批升级为 24 键 exact + 取值断言，否则 R22 收口「CI 全绿」是假绿。
4. **R72 week_plan.py 当天高频漂移**：def +7/call +15，落地前必须实时 rg 重盘，registry/blast 静态行号已失真；与 R21/R55 同文件须显式串行避免位移返工。


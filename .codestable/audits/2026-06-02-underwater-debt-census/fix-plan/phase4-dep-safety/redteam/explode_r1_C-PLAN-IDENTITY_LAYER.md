# 逐簇爆炸对抗 · C-PLAN-IDENTITY · 透镜 LAYER（分层导入环+迁移耦合）· 第 1 轮

> skeptic 默认怀疑，只读不改任何 .py。行号均 2026-06-05 实时 rg/sed 回盘。
> 主透镜按指派聚焦 Q2（分层导入环）/Q3（迁移耦合），并对全簇六质问点过一遍。
> 成员：R21 / R22 / R23 / R72。

---

## 总判

| 债 | 判定 | 一句话 |
|---|---|---|
| R22 | 🔴 红 | 收口若顺手删掉 view_context.py:74 `normalize_plan_role(plan_role)` 这一行（"反正 builder 会归一"），R21 wrapper 的 `field=="plan_role"` 重抛精度失效 → 静默错身份 / 契约测试红被改宽 → fail-open。 |
| R21 | 🟡 黄 | 纯删 3 死 shim 本身安全（零生产/零测试消费），但**硬前置**=R22 必须先锁死 wrapper 续命且 wrapper 依赖的是 view_context:74 的 raise，不是 :77-100 的 dict。R21 误删整模块/误删 wrapper 两条灾难链已被 dossier 拦住。 |
| R23 | 🟡 黄 | dedup 两份字节相同 `_normalize_role` 本身零行为差；唯一红线=绝不可误并入 view_context:65 `normalize_plan_role`（带 VALID 校验、抛 ValidationError）——误并 = ValueError→ValidationError 静默错身份。需符号锚定 + 与 R34 同文件行号联动软序。 |
| R72 | 🟢 绿 | 收口落点 web `scheduler_utils.py`，读 flask.request 留在 web 层，core/ 零 flask（已 rg 实证 exit-0 空），不下沉 core 即不越层、不成环（week_plan→utils 边已存在）。唯一硬动作=补 `from flask import request` + 落地前重盘 week_plan.py 高频漂移行号。 |

---

## R22 🔴 —— 本簇最危爆点（Q2 表面绿、Q5 收口等价被击穿）

### 灾难链（改 X→静默→坏数据流到 Y）
1. R22 计划=删 `schedule_result_view_context.py:77-100` 手搓 22 键 dict，改委托 `build_plan_identity(...).to_dict()`（24 键）。
2. **被所有 dossier 漏掉的真相**：R21 wrapper（`gantt_plan_query.py:38`）`except ValidationError ... if (exc.details or {}).get("field")=="plan_role": raise ValidationError("未知的排产方案角色：{role}")` 捕的是**内层 `_default_plan_resolution_dict`（=view_context `default_plan_resolution_dict:73`）抛出的 plan_role ValidationError**。
3. 该 raise 的**唯一来源**是 `default_plan_resolution_dict` 函数体**第一行 :74 `requested_role = normalize_plan_role(plan_role)`** → `normalize_plan_role:69 raise ValidationError(field="plan_role")`。**它在 :77-100 dict 体之外**，R22 计划删的区段不含它。
4. **击穿点**：`build_plan_identity` 经 sed:175 实证 = `requested = _text(requested_role) or ROLE_ADOPTED`，**不校验 VALID_PLAN_ROLES、不抛 field="plan_role"**（rg 实证 builder 内零 `normalize_plan_role`/`VALID_PLAN_ROLES`/`field="plan_role"`）。即 builder 对坏 role**静默归一为 adopted**。
5. 若 R22 收口时"既然 builder 内部会处理 role，就把 :74 standalone normalize 也删了/绕过" → `default_plan_resolution_dict("bad")` 不再抛 field="plan_role" → wrapper :38 永不触发 → ① 契约测试 `regression_schedule_result_view_context.py:300 assert "未知的排产方案角色：bad"` **变红**；② 若有人顺手把红测试改宽（最可能的二次伤害），则坏 plan_role 被 builder 静默吞成 adopted，no_history/missing_history 页（:449/:457 调用）渲染出一份**伪造的 adopted 身份**——身份族最怕的静默错身份 fail-open。

### 修正建议（前置/顺序/禁区行）
- **新增禁区行（本轮新发现，计划未覆盖）**：`schedule_result_view_context.py:74 normalize_plan_role(plan_role)` 这一行 R22 **绝不可删/绕过**。它是 R21 wrapper `field=="plan_role"` 精度的**唯一上游来源**，是 R22 自己收口的隐式 precondition，不只是"保留 R21 wrapper"。
- R22 收口范围严格锁定 :77-100（内层 dict）+ 可选 :142 `plan_identity["is_official"]` 方括号改 `.get()`；**:74 normalize_plan_role 必须原样保留在 dict 委托之前**。
- parity 测试必须**同时断言两件事**：(a) 24 键 exact `==`（已识别，覆盖 22→24 drift，MISSING={result_summary_parse_failed,result_summary_parse_reason} 已 Python 实锤）；(b) **`default_plan_resolution_dict("bad")` 仍抛 field="plan_role" 的 ValidationError**（即把 :300 文案契约纳入 R22 自己的 parity 网，而非仅靠 R21 续命测试间接守）。否则 (a) 全绿但护栏 (b) 已破=典型"测试绿但护栏失效"。
- 顺序：B01（LB03 承重认账）→ Batch-1 parity（24 键 exact + bad-role raise 双断言）→ R22 收口 → R21 删 3 shim（严守保留 wrapper + 不影响 :74）。

### 旁证（无害项，避免误升风险）
- 外层 :141-142 `plan_identity["user_label"]/["is_official"]` 硬取——委托 24 键含此二键，不 KeyError。
- 缺的 2 键全下游 `.get()` 读（view_context:330/333、reports_plan_template_fields:45/61、scheduler_workbench_links:276/359、scheduler_resource_dispatch:157/185）→ 22→24 纯增键不炸 KeyError；但**今天缺键**=这些 plan_role 阻断守卫在 no_history 页恒读 None→False（静默 fail-open，正是 severity 的来源，medium 成立）。

---

## R21 🟡 —— 安全但硬绑 R22，禁区两条

### 证据
- `rg "from .*gantt_plan_query import"` 全仓**仅** `gantt_service.py:12`，只取 4 个 LIVE range 函数（attach_gantt_range_metadata/build_empty_week_plan_payload/get_version_time_span_dates/resolve_gantt_range_for_version），**零死 shim**。
- `selected_plan_role` 真实消费者（gantt_service:34/281/334/354、gantt_critical_chain_provider:21/161）全 import 自 `schedule_result_view_context`，非本文件 :46 shim。
- 唯一测试命中 `gantt_plan_query.default_plan_resolution_dict("bad")`（:298）= R21 **保留**的 wrapper，删 3 shim 零测试变红。
- Q2 分层：纯删除不新增 import，删后剩余 import 全被 LIVE 函数继续用（无悬空），不引入 core.models→core.services / 任何环，0 AST 违规。Q3 迁移耦合：本债与 v18/v19 DB CHECK 无关。

### 灾难链（已被 dossier 拦，复核成立）
- ☠️ 误判整模块死→连带删 → 打断 gantt_service 对 4 LIVE range 函数真调用 → 甘特周计划范围解析静默断裂。防线=禁区 B（:50-156 整文件保留）。
- ☠️ 误删 :32-39 wrapper → R22 precondition 失效 + :300 测试红。防线=禁区 A。

### 修正建议
- 禁区 A：`gantt_plan_query.py:32-39` wrapper + :11-13 其 import（R22 precondition）。禁区 B：`:50-156` 4 个 LIVE range 函数。
- 顺序硬绑：**R22 先锁 wrapper 续命 → R21 后删 3 shim**。R21 用符号名锚定，删 import 区致 wrapper 行号上移约 9 行（156 行文件实测，:32 会上移）。

---

## R23 🟡 —— dedup 安全，唯一红线=不并入带校验第三变体

### 证据
- model `schedule_plan_role.py:21-23` 与 service `schedule_plan_query_service.py:28-30` 函数体**逐字相同**（sed 实证 `text=str(role or "").strip()` / `return text or ROLE_ADOPTED`）。
- 收口方向 service→model 合法层向（service:9 已 import 该 model），model 仅 import typing→**零导入环**（Q2 绿）。
- resolve_plan 双段（:105-108）：:106 `_normalize_role(role)` 静默归一 → :107-108 `if not in VALID_PLAN_ROLES: raise ValueError`。

### 灾难链（误并入第三变体）
- view_context `normalize_plan_role:65-71` 带 `VALID_PLAN_ROLES` 校验、对 bad role 抛 **ValidationError**；`_normalize_role` 对 bad role **静默返回原值**。
- 若 dedup 误把 service:28 收口到 :65 → `resolve_plan("bogus")` 抛错类型 ValueError→ValidationError、抛点前移 → 上游 catch ValueError 的调用方静默漏接 → 坏角色被当合法放行（静默错身份）。

### 修正建议
- 收口点=model `_normalize_role`（已存在）；禁区=`schedule_plan_query_service.py:105-108` 双段（仅换 :106 符号来源，不改语义）+ `normalize_plan_role:65`（绝不并入）。
- 与同文件 R34 软序：R23 先删 :28-30 三行 → R34 基于删后行号定位（纯行号联动，无语义碰撞）。

---

## R72 🟢 —— 分层落点天然分离，唯一坑=补 request import

### 证据（Q2 主透镜重点）
- `rg "from flask|import flask" core/` → **exit-0 空**：core/ 整体零 flask，下沉 getter 到 core/services 或 core/shared = `core→flask` 越层 + 破 AST 0 违规。R72 落点 web `scheduler_utils.py`（读 flask.request）留在 web 层=合法。
- 与 R44 落点天然分离：R72=请求层取参（core 无孪生，rg `request.args.get("plan_role")` core/ 空）；R44=已 resolve 角色（core 有同名 selected_plan_role）。**不可硬塞同一 helper**。
- 导入环：week_plan:47 已 `from .scheduler_utils import _current_scheduler_operator`（边已存在）；gantt 新增同方向边（route→utils，utils 不反向）→ 不成环。
- 两副本字节相同（sed 实证），纯 dedup 无行为差。

### 修正建议
- 收口落点 web `scheduler_utils.py`（已存在），**必补 `from flask import request`**（现仅 `from flask import g`）——本债最易踩坑（latent NameError）。
- 落地前以实时 rg 重盘 week_plan.py（def 已 +7、call 已 +15，当天高频漂移热点）。
- 灵魂线：空串→None 语义原样保留，禁顺手加默认 ROLE_ADOPTED 兜底。owner_pending=true，落点公开名 + 与 R44 共识待 owner 裁。

---

## 漏项（本轮新发现，计划/dossier 未覆盖）

1. **【最危·已上判】R22 的隐式 precondition 不是"保留 R21 wrapper"，而是"保留 view_context.py:74 `normalize_plan_role(plan_role)` 这一行"**。所有 dossier（R21§6、R22§6、cluster§A①/§D）都只钉"R21 保留 :32-39 wrapper"，没人指出 wrapper 捕获的 `field=="plan_role"` raise 的真实源头在 view_context:74、且 `build_plan_identity` 不会替代它（builder 静默归一坏 role）。R22 若按"委托 builder 即可"的直觉删掉 :74，24 键 exact parity 仍可能全绿、但 bad-role loud 文案护栏已破——典型测试绿/护栏破。**须把"bad-role 仍抛 field=plan_role"纳入 R22 自身 parity 双断言。**
2. **Q3 迁移耦合本簇为空（确认非漏）**：v18/v19 DB CHECK（effective_plan_role=adopted / source_table=schedule 的 adopted-only 下沉）与本簇 4 债零代码耦合——R22 委托 build_plan_identity 时 source_table 恒 SOURCE_SCHEDULE、effective=adopted（:80/:82），与 CHECK 同向，不触发启动探针炸。无改码不改迁移的耦合面。
3. **R23 第三变体外部消费者更广**：`normalize_plan_role` 另有 resource_dispatch_service.py:271/355、resource_dispatch_execution_service.py:77 三个 core 外部消费者——加重"绝不可在 R23 内误统一三变体"的爆炸面（误并波及派工链）。

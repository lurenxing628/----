# Layer3 回炉裁定 V2 —— 争议组 ③R22 三透镜红因合并 / ⑫R42 :57 override + 完整删点清单

> 裁定 agent，只读不改。行号均经 2026-06-05 工作区 rg/sed 回盘（不信旧值，权威路径以 _layer2_residual.md 为准）。
> 铁律守则：承重只补注释+绑契约/parity；灵魂线 P4 改 loud raise/补可观测、P5 收口到已存在点；分层 0 违规；owner_pending 只标不给终态修法/不分配批次。

回盘锚点（本轮亲核）：
- view_context = `core/services/scheduler/schedule_result_view_context.py`
- `normalize_plan_role` **def :65（含 raise ValidationError field="plan_role" @:69）**，调用 **:74**（`requested_role = normalize_plan_role(plan_role)`，在手搓 dict :77-100 体外）
- `_summary_unavailable` 在 **builder `schedule_plan_identity_builder.py:128`**（不在 view_context），None→`return True,"排产摘要缺失"`@:132 → :233 `result_summary_parse_failed=bool(summary_unavailable)`
- no_history 调用 @**:446/:449**、missing_history @**:452/:457**（dossier 449/457 准）
- collar `build_workbench_plan_context` def 头 :187 / `plan_id` 形参 **:191** / dict 键 **:233**
- navigation_context.py：`publish_workbench_navigation_context(**kwargs)` :56 → `build_workbench_plan_context(**kwargs)` **:57**；显式 plan_id 读入 **:78**
- dashboard_workbench_context.py：`_context_kwargs` :84 / `"plan_id":…` **:92** / `build_workbench_plan_context(**_context_kwargs(...))` **:119-120**

---

## 争议③ —— R22 三透镜红因合并裁定

三透镜回炉项原文（_layer3_explosion.md §回炉表 row 3 / 爆点 #22 #23）：LB 透镜红因=no_history `result_summary_parse_failed` False→True 取值翻转；LAYER 透镜红因=删 view_context:74 破 bad-role raise；SOUL 透镜黄（触发面窄 medium）。争议焦点：两红因是否同一动作、能否合并，收口安全路径怎么排。

### 裁定 3-1：两红因【不是同一动作，但同源于"R22 委托收口"这一步，必须合并为同一闸门治理】

【裁定】#22（取值翻转）与 #23（删 :74 破 raise）是 R22 收口动作触发的**两个独立失效面**，不可互相替代、不可只防一个；但二者都只在"把手搓 dict 改成委托 build_plan_identity"那一刻发生，故合并为 R22 收口的**单一 owner 闸门 + 双断言 parity** 一次性钉死。

【证据】
- #22 实锤：`_summary_unavailable` 在 `core/services/scheduler/schedule_plan_identity_builder.py:128`，入参 result_summary 为 None/缺失时 `:132 return True, "排产摘要缺失"` → `:233 result_summary_parse_failed=bool(summary_unavailable)=True`。no_history 路径（view_context:446/449）调 build_plan_identity 时 result_summary 必为 None（无历史即无摘要），故委托后该键**必然 True**。手搓 dict（:77-100）无此键，下游 `schedule_result_view_context.py:329-330` `plan_identity.get("result_summary_parse_failed") or data.get(...)` 两路皆缺 ⇒ 恒 **False**。**False→True 翻转确凿，非潜在**。下游渲染态翻转点：`reports_plan_template_fields.py:45/61`（读该键）+ collar 自身 `scheduler_workbench_links.py:276` `_has_blocked_plan_identity` 也读 `result_summary_parse_failed`（回盘 :276 在场）。
- #23 实锤：`normalize_plan_role` def `view_context:65`，**函数体内 :69 `raise ValidationError(..., field="plan_role")`**；:74 是 `default_plan_resolution_dict` 体内第一行 `requested_role = normalize_plan_role(plan_role)`，**在手搓 dict :77-100 之外**。R21 wrapper（gantt_plan_query.py:32-39）的 `field=="plan_role"` 重抛精度、续命测试 `regression_schedule_result_view_context.py:294/300`（"未知的排产方案角色：bad"）唯一上游就是 :74 这条调用。若 R22"既然委托 builder 就把 :74 一起删"——build_plan_identity 对 bad role **不 raise**、静默归一 adopted（builder 无等价 ValidationError(field=plan_role) 出口）→ bad role 静默吞成 adopted 伪身份，而 24 键键集 parity 仍全绿（典型"测试绿护栏破"）。
- 两者为何不可合并成一个断言：#22 是**取值**问题（键在、值翻转），#23 是**控制流**问题（raise 消失）；键集 exact== 抓不到 #22 的取值翻转，也抓不到 #23 的 raise 缺失。evidence_contract `:194 set(identity) >=` superset 对二者**双重逃逸**。

### 裁定 3-2：R22 收口安全路径【分三步，先 parity 后止血再单拍 no_history】

【裁定】按以下严格顺序，**任何一步未落地不得进入下一步**：

- **第 1 步（先于一切收口，Batch-1 纯增量网）—— 24 键 exact parity 双断言先落**：
  1. 对 `VALID_PLAN_ROLES` 全集断言 `default_plan_resolution_dict(role)['plan_identity']` 键集 **exact ==** `build_plan_identity(..., source_table=SOURCE_SCHEDULE).to_dict()` 键集（**==，非 >=**）；
  2. 同测对 **no_history 实参**断言 `result_summary_parse_failed` 的**具体取值**（钉住"今天手搓侧=False、委托后=True"的差，这是 #22 的红线）；
  3. 升级 `regression_scheduler_plan_identity_evidence_contract.py:194` 的 `set(identity) >=` superset → **24 键 exact ==**（堵 superset 逃逸口，否则 drift 0→2 继续 CI 全绿）。
  - 此步**只增不改生产**，承重 builder:158 / PlanIdentity.to_dict:46-71 只 CALL 不碰（禁区）。

- **第 2 步（内层委托，最小止血）—— 删 :77-100 手搓内层 dict 改委托 build_plan_identity().to_dict()，但 :74 normalize_plan_role 调用绝不删**：
  - 收口点为已存在的 `build_plan_identity`（builder:158）+ `SchedulePlanResolution.to_dict`（resolution:64），不新建第二模块（铁律 5 守）；
  - **#23 止血关键：`view_context:74` `requested_role = normalize_plan_role(plan_role)` 这行作为 bad-role loud raise 的唯一上游，保留不动**——委托只替换 :77-100 的 dict 字面量，不替换 :74 的前置 normalize。R21 wrapper 精度、续命测试 :294/:300 因此续命；
  - 灵魂线合规：此步**消除**现有"缺键静默 False"隐式回退，不新增兜底；遇 bad role 仍由保留的 :74→:69 loud raise（不改静默）。

- **第 3 步（no_history 场景单独拍）—— #22 取值语义交 owner，不在收口里自行定终态**：
  - 委托后 no_history 页 `result_summary_parse_failed` 必翻 True，下游 `reports_plan_template_fields.py:45/61` + 3 套手维列表 + collar :276 渲染态变化（无历史方案被标"摘要解析失败"）。**这是行为变化，不是 bug 修复**；
  - parity 第 2 步的取值断言会把这个翻转**显式逼到台面**（红），由 owner 裁"保旧 False（no_history 视为正常）"还是"接受新 True（无历史即标摘要不可用）"；
  - 收口 agent **不得**自行在 no_history 分支塞 `result_summary_parse_failed=False` 覆写（那是新增静默兜底，违灵魂线）——若 owner 选"保旧 False"，须由 owner 指定的合规手段（如 no_history 专用 summary_parse 占位使 _summary_unavailable 返 False），不由收口 agent 私拍。

### 裁定 3-3：owner 闸门【R22 owner_pending=true，#22 取值语义=owner 业务裁断】

【裁定 · 待owner】R22 `owner_pending=true`（_layer2_residual + dossier 字段 2/4/12 实证）。**#23（删 :74）不是 owner 裁断项——它是技术红线，裁定直接固化为"绝不删 :74"，无选项**。**#22（no_history 取值 False vs True）是 owner 业务裁断项**：

- 选项 A：**保旧 False**——no_history 无历史方案视为"无摘要可解析即不算失败"，维持当前 reports/手维列表渲染态不变。优点零行为漂移；缺点与 canonical 语义分叉需专门兜（且兜法须合规非静默）。
- 选项 B：**接受新 True**——统一到 canonical"无摘要=parse_failed=True"，no_history 方案显式标"摘要解析失败"。优点语义统一、零特例代码；缺点 reports_plan_template_fields:45/61 + 3 套手维列表 + collar:276 渲染态翻转，须确认产品可接受"无历史方案被标摘要解析失败"文案。
- 【建议】**倾向选项 B**（语义统一、不引入 no_history 特例兜底、最契合"收口=消除手搓分叉"初衷），但因涉及用户可见渲染文案翻转，**须 owner 拍板**；终态修法与执行批次 owner 裁后定稿。

---

## 争议⑫ —— R42 :57 override kwargs 未审 + 完整删除点清单

R42 `owner_pending=false`（dossier 实证）→ 本组给终态删点清单 + 分配批次。两个回炉项：爆点 #21（dossier 漏 dashboard_workbench_context.py:92）、回炉项 #12（navigation_context:57 `**kwargs` 路径是否含 plan_id 未回盘）。

### 裁定 12-1：navigation_context.py:57 `**kwargs` 路径【不含 plan_id，删 :191 形参对 :57 安全，无 TypeError】

【裁定】回炉项 #12 审清：**:57 的 `**kwargs` 不含 plan_id**，删 :191 形参不会经 :57 触发 TypeError。:57 不是危险点。真正经 `**` 展开炸的是 dashboard_workbench_context.py:119（见 12-2）。

【证据】链路全回盘：
- `:57 build_workbench_plan_context(**kwargs)` 的 kwargs 来自 `:56 def publish_workbench_navigation_context(**kwargs)`；
- 其唯一调用方 `scheduler_navigation_publish.py:87 publish_workbench_navigation_context(can_write_feedback=..., **kwargs)`，该 `**kwargs` 来自 `_publish_context(plan_resolution, **kwargs)`（:85）；
- `_publish_context` 三调用方 `:109/:137/:168`，全文件 **`plan_id` 0 命中**（`rg plan_id scheduler_navigation_publish.py` 仅 :24-26 的 `plan_identity_error/blocking_error/blocking_scope`，非 plan_id）。
- 结论：plan_id 进入 collar 只走 navigation_context.py **:78 显式 `plan_id=_request_arg("plan_id")`** 这一条（:76-78 块），与 :57 `**kwargs` 路径**互斥不交叉**。:57 路径无 plan_id 注入。

### 裁定 12-2：dashboard_workbench_context.py:92 是真删点【dossier 漏，删 :191 不同删 :92 ⇒ TypeError 500 启动即炸】

【裁定】爆点 #21 成立。dossier 把 `dashboard_workbench.py:121` 判"消失"**正确**（该文件 plan_id 0 命中），但 plan_id 落点**迁到了同名不同文件** `dashboard_workbench_context.py:92`，经 :119-120 `build_workbench_plan_context(**_context_kwargs(...))` 的 `**` 展开真实流入被删形参。**:92 必须与 :191 形参同提交删除**，否则 dashboard 值班台首页 TypeError 500。

【证据】
- `web/viewmodels/dashboard_workbench_context.py` 真实存在；`_context_kwargs` def `:84`，**`:92 "plan_id": _filter_or_none(filters, ("plan_id",))`** 在场；`:119-120 context = build_workbench_plan_context(**_context_kwargs(...))`。
- collar `:191 plan_id: Any = None` 有默认值，但 `**_context_kwargs` 把 `"plan_id"` 键**显式展开成关键字实参**，删形参后该键 ⇒ `TypeError: build_workbench_plan_context() got an unexpected keyword argument 'plan_id'`，dashboard 路由加载即炸。

### 裁定 12-3：删 :191 形参的 TypeError 面【3 个显式传 plan_id 的调用方，全删点清单如下；4 个不传的安全】

【裁定】全仓 8 个 `build_workbench_plan_context(` 调用方回盘，**只有 3 个显式/展开传 plan_id**，删 :191 形参后这 3 个会 TypeError，必须同提交删除其 plan_id 实参；其余 4 个不传 plan_id，删形参对它们**安全**（默认值 None 兜住，无需改）。

【证据】8 调用方逐核（`rg build_workbench_plan_context\(`）：
| 调用点 | 传 plan_id？ | 删 :191 后 |
|---|---|---|
| navigation_context.py:76-78（`plan_id=_request_arg("plan_id")` @:78） | **是·显式** | 必须删 :78 |
| scheduler_reports_workbench.py:77-79（`plan_id=plan_id` @:79） | **是·显式** | 必须删 :79（连带 :60 形参） |
| dashboard_workbench_context.py:119-120（经 `**_context_kwargs` @:92） | **是·展开** | 必须删 :92 |
| navigation_context.py:57（`**kwargs`，链不含 plan_id） | 否 | 安全（裁定 12-1） |
| scheduler_analysis_links.py:24 | 否 | 安全 |
| scheduler_resource_dispatch.py:95 | 否 | 安全 |
| scheduler_gantt_task_detail.py:78 | 否 | 安全 |
| scheduler_navigation_links.py:40（仅 `plan_role=ROLE_ADOPTED`） | 否 | 安全 |

### 裁定 12-4：别名 `n(` 调用形态【全仓无 `as n` 真别名，D2 的"别名 n("是符号简写非真实 import，无额外漏改点】

【裁定】_layer2_residual D2 提醒"删 R42 形参须同查 `build_workbench_plan_context` 与 `n(` 两种调用形态"——回盘**全仓无 `as n` 别名 import**（`rg "build_workbench_plan_context as"` 0 命中，navigation_context.py:21 是真名 import）。D2 的 `n(` 是对 collar 长名的口语简写，**不存在隐藏的别名调用点**。但 D2 的实质纪律仍成立且已被 12-3 覆盖：dashboard/reports/gantt_task_detail/navigation_links 四处别名口语指代的调用点已逐一核到（其中 dashboard=:92 真传、reports=:79 真传、gantt_task_detail/navigation_links 不传）。**结论：无 `n(` 别名漏改点，co-change grep 纪律落到 12-3 的 3 个真传点即完备**。

### 裁定 12-5：R42 完整删除点清单【终态，已剔消失点、补 :92、含 emit 双 plan_style】

【裁定 · 终态（owner_pending=false）】R42 = P6 纯直删，**与 R60 强制单次提交**，rebase 在 R54 新签名之后（Batch-3）。删点清单（行号经本轮回盘）：

- **删读入**：`navigation_context.py:78`、`reports_page_support.py:104` + `:143`、`dashboard.py:241`（**非 registry :172**）。
- **删存储/展开**：`scheduler_workbench_links.py:191`（形参）+ `:233`（dict 键）、**`dashboard_workbench_context.py:92`（#21 漏删点，新补）**。
- **删透传**：`scheduler_reports_workbench.py:60`（形参）+ `:79`（透传实参）。
- **删 emit**（按符号删单行、绝不连片邻参）：`scheduler_workbench_link_query.py:118`（常规 plan_style）+ `:154`（execution_review plan_style）——emit 唯一归 R42，R60 不重复删。
- **删字段表**（R60 承认面，MUST 与 R42 同删）：`scheduler_navigation_links.py:12` + `:52`、`reports_export_support.py:14`。
- **剔除（不在清单）**：~~`dashboard_workbench.py:121`~~（已证消失）；~~roadmap acceptance.md:52 / checklist.yaml:82~~（幻觉/不存在）。**roadmap 仅 `aps-frontend-workbench-items.yaml:289` 一处真删**（须先与在途 workbench roadmap owner 对齐 in-progress feature 契约）。
- **禁区行（删 plan_id 绝不顺手碰）**：`navigation_context.py:79`（R56 plan_role 强制 ROLE_ADOPTED 护栏）/:80（scenario_id）；`reports_page_support.py` build_report_context 内 LB06 execution-review→adopted/scenario=None 强制分支；emit :118/:154 相邻的 version/plan_role/scenario_id `_append_param`（link_query:117/119/120，C1 灾难链）。
- **parity 门**：删后断言 ①`query["plan_id"]`/`hidden_inputs["plan_id"]` 键消失（contract :122/:126）②`version/plan_role/scenario_id/back_to` 逐字 == 删前（:123/:127 back_to 保留）③覆盖 emit-A（常规）+ emit-B（execution_review）两 plan_style。先迁测试（去 plan_id 留 back_to）→ 后删生产 → 跑测试自证。

---

## 对批次计划的影响汇总

**R22（C-PLAN-IDENTITY，owner_pending=true）**
- 前置顺序固化：B01/LB03 先行 → Batch-1 parity（24 键 exact + no_history `result_summary_parse_failed` 取值断言 + evidence_contract:194 升 24 键 exact）→ R22 第 2 步委托收口 → R21 删 3 shim。
- 新增禁区（按符号）：**view_context:74 `normalize_plan_role` 调用绝不删/绕**（bad-role loud raise 唯一上游，R21 wrapper 精度命脉）；builder:158 build_plan_identity + PlanIdentity.to_dict:46-71（只 CALL 不改）；gantt_plan_query.py:32-39 wrapper + :11-13 import 别名。
- owner 闸门：**#22 no_history 取值 False vs True 须 owner 拍**（建议 B 接受 True，但涉用户可见文案翻转）；#23 删 :74 = 技术红线无选项。收口 agent 禁在 no_history 分支私塞覆写（违灵魂线）。
- 续命测试 :294/:300 R21/R22 都不碰（保留 wrapper）。

**R42（C-NAV-PLANID，owner_pending=false）**
- 批次：Batch-3，**R42⇔R60 强制单次提交**，rebase 在 R54（Batch-2 guard 收口）新签名后。
- 删点清单补 1 剔 3：**补 dashboard_workbench_context.py:92**（#21 启动即炸点）；剔 dashboard_workbench.py:121 + roadmap acceptance.md:52 + checklist.yaml:82（幻觉/消失）。
- :57 `**kwargs` 路径经回炉审清=不含 plan_id=非危险点，无需处理；无 `as n` 真别名漏改点。
- F 门：roadmap items.yaml:289 下线须与在途 aps-frontend-workbench owner 对齐（触 in-progress feature 契约）。
- 灾难链守卫：emit :118/:154 按符号删单行，绝不连片 link_query:117/119/120 邻参（C1 version 静默错位）。

**跨组无冲突**：R22 与 R42 不同簇、不同文件、不同符号，无同文件碰撞；R42 涉及的 collar `build_workbench_plan_context` 与 R22 的 `build_plan_identity` 是两条独立收口/删除链，批次间无序约束。

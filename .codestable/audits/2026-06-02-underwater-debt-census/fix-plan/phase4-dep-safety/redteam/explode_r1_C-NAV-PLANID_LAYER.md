# 逐簇爆炸对抗 r1 — 簇 C-NAV-PLANID（主透镜：分层导入环+迁移耦合 LAYER）

> 第1轮 skeptic / 只读不改 / 默认怀疑。行号 2026-06-05 rg 实盘回盘，旧值不信。
> 成员债 [R42, R60, R64, R65, R66]。主透镜 Q2(分层导入环)/Q3(迁移耦合) 为重，六质问全过。
> 产物 gitignored，本轮发现喂 Layer4。

---

## 主透镜结论先行（Q2 / Q3）

- **Q2 分层导入环 = 🟢 绿（全簇）**。5 文件 import 实盘回盘：
  - `navigation_context.py` → `core.models.schedule_plan_role`(:7) + web 内（:8/9/12/15/18/21），web→core.models 正向。
  - `reports_page_support.py` → `core.infrastructure.errors`(:7) + `core.services.report`(:8) + web 内，正向。
  - `reports_export_support.py` → `core.services.common`(:8)/`core.services.report`(:9/10) + web 内，正向。
  - `scheduler_navigation_links.py` / `scheduler_workbench_link_query.py` / `scheduler_reports_workbench.py` → **零 core import**，纯 web/viewmodels 同层。
  - 本簇 5 债**全是删除**（删形参/删 dict 键/删元组项/删 def/删 import/化简 or 短路），删除**不可能**新增 `core.models→core.services`/`core.algorithms→core.services`/`repo→service` 越层，**不可能**制造导入环。**0 AST 违规。Q2 对全簇无爆点。**

- **Q3 迁移耦合 = 🟢 绿（全簇）**。v19 DB CHECK 实盘（v19.py:14/15/18/19）钉的是 `source_table='schedule'` + `effective_plan_role='adopted'`，**与 plan_id 零耦合**。plan_id 是死面包屑，全程不进任何 resolver/DB/schema/CHECK（`git grep '\bplan_id\b' core/ data/`=0）。删 plan_id **不触发任何启动探针/CHECK**。Q3 对全簇无爆点。

> 主透镜两维全绿——本簇真实爆点**不在分层/迁移**，而在 **caller 签名契约（TypeError）+ 相邻身份参数误删（静默错位）+ 跨文件 LIVE 误删**。下列逐债判定。

---

## 逐债判定

### 🔴 R42 — plan_id 死面包屑全链下线【会炸：dossier 漏列第 8 删点 → 删完启动即 TypeError】

**判定 🔴（修法清单不完整，照单执行必炸）**。debt 本身死证成立、分层/迁移无害，但 **dossier R42 §4/§8 把 `dashboard_workbench.py:121` 当"已消失"剔除时，把符号搞混了**——消失的是旧文件 `dashboard_workbench.py`，但 plan_id 落点**迁移到了同名不同文件** `dashboard_workbench_context.py:92`，dossier 全程未抓到这第 8 个落点。

**实盘证据（本轮新挖）**：
- `web/viewmodels/dashboard_workbench_context.py:92` = `"plan_id": _filter_or_none(filters, ("plan_id",))`，是 `_context_kwargs()` 返回 dict 的键。
- 同文件 `:119` = `context = build_workbench_plan_context(**_context_kwargs(...))` —— **`**` 展开传入**。
- 故 `plan_id=` 经 `**kwargs` 真实流入 `build_workbench_plan_context` 的 `plan_id` 形参（`scheduler_workbench_links.py:191`）。

**完整灾难链 C0（dossier 未覆盖，最危）**：
R42 按 dossier 清单删 `workbench_links.py:191` 形参 `plan_id: Any=None` →（dossier 清单**不含** dashboard_workbench_context.py:92，因误判已消失）→ :92 仍产出 `"plan_id":...` 键 → `build_workbench_plan_context(**{...,"plan_id":...})` → **TypeError: unexpected keyword argument 'plan_id'** → **dashboard 值班台首页 500 启动即炸**（非静默，但红在生产路径，CI 若无 dashboard 冒烟则漏网）。

**修正建议（前置/禁区）**：
1. **R42 删点清单 MUST 补第 8 点**：`dashboard_workbench_context.py:92` 删 `"plan_id": _filter_or_none(...)` dict 键，**与 :191 形参同提交**（删形参⇔删所有 `**kwargs` 来源键，原子）。
2. **前置 grep 纪律（layer2 D2 强化）**：删 :191 前，对 `build_workbench_plan_context` 全 7 caller 逐一核 `plan_id=`/dict-key——本轮已核：navigation_context:78(删)、reports_workbench:79(删)、**dashboard_workbench_context:92(删，dossier 漏)**；gantt_task_detail:78 / analysis_links:24 / resource_dispatch:95 **不传 plan_id 安全**；navigation_context:57 走 override `**kwargs` 路径需 owner 复核 kwargs 来源。
3. **禁区行（C1 静默爆点，已坐实）**：删 `link_query:118`（plan_id）时**绝不碰** :117 version/:119 plan_role/:120 scenario_id；删 :154 时绝不碰 :153 version/:155 plan_role——三真身份参数前后紧夹 plan_id，误伤=URL 丢身份→version 解析静默错位。
4. **禁区行（承重）**：`navigation_context.py:79`（plan_role 强制 ROLE_ADOPTED，R56 已 fixed）/:80 scenario_id；`reports_page_support.py:104/:143` 删 plan_id 形参时绝不碰密集相邻的 :154/:184/:230/:241/:261 `plan_role=raw_plan_role, scenario_id=...` 透传（LB06 域，本体已迁 reports_execution_review_context.py/reports_request_support.py）。
5. **函数名口径纠偏**：dossier/cluster 称禁区在 `build_workbench_navigation_context`，实盘 :78-80 在 `current_workbench_navigation_context`(:69) 内、调 `build_workbench_plan_context`——物理行对、函数名错，按符号定位不按裸行号。
6. 灵魂线：纯删不加兜底；contract 测试 :109/:122/:126 plan_id 三断言先退、:123/:127 back_to 留；items.yaml:289 owner 对齐。

### 🟡 R60 — plan_id 进合同字段表的承认面【条件：只删 plan_id 一项 + emit:118/154 归 R42 + 与 R42 同提交】

**判定 🟡（本体安全，但半截/误删元组邻键即炸，强约束）**。死证成立、分层/迁移无害。三处删点实盘坐实：`navigation_links.py:12`（`_REPORT_CONTEXT_FIELD_NAMES` 元组，:11-28，plan_id 在 :12，相邻 :13 back_to/:14 scenario_id）、`:52`（`_has_navigation_context` 判空元组，:47-63，相邻 :51 version/:60 scenario_id/:61 back_to/:63 plan_role）、`reports_export_support.py:14`。

**条件（缺一即黄转红）**：
- **C2 半截残渣**：R60 删字段表而 R42 留读/存 → `build_workbench_plan_context` 仍写 plan_id 进 context、emit 仍读出 → 链接挂 plan_id 但表不认 = 新 P3。**MUST 与 R42 单次提交**。
- **C-emit 双删冲突**：emit `link_query:118/154` 归 R42 删，**R60 不得重复删**，否则同点双删/键位移。
- **C-邻键误删（dossier 标的本债最大风险）**：元组删行只动 `"plan_id",` 一项，**绝不连带** back_to/scenario_id/version/plan_role/date_*/resource_*/scope_* —— 误删=隐藏表单/导出 URL 丢真承重透传键→报表跨页丢上下文（date_range/resource/scope）→静默坏页面，high 级回归。

### 🟡 R65 — `_target_url` 死分支三件套【条件：三件套原子 + :7 必保 + 化简留 plan_url】

**判定 🟡（误删 :7 即静默炸报表导航，执行精度要求高）**。死分支恒真证成立、分层/迁移无害。三件套实盘零漂移：删 def :74-78、化简 :160 `plain_url or _target_url(...)`→`plain_url`、删孤儿 import :4 urlencode / :6 query_for_target。本轮独立坐实 :4/:6 删后无残留引用（urlencode 仅 :76、query_for_target 仅 :75，均 _target_url 体内）。

**条件（缺一即黄转红）**：
- **C-:7 误删（本债最大爆点，已实盘坐实）**：`:7` 是三联导入 `from .scheduler_workbench_links import TARGET_PAGE_PATHS, build_workbench_link, build_workbench_plan_context`。TARGET_PAGE_PATHS 在 :77(死 def 内删) **+ :177(`build_report_navigation_links` 真用，留)** 双处用；build_workbench_link/build_workbench_plan_context 更是全文件核心。**绝不可删 :7 整行，也绝不可从 :7 摘 TARGET_PAGE_PATHS**——误删→:177 NameError→报表导航条全挂。
- **C-内部三件套原子**：删 def 不化简 :160 → `_target_url` 未定义 NameError 破 build。MUST 同提交，按符号定位（R64 漂移可吸收）。
- 化简须**留 plain_url**（删 ` or _target_url(...)`），删错操作数留 `_target_url` 即 NameError。

### 🟢 R64 — `_has_navigation_date_range` 新建即死【安全：零调用零测试纯叶子】

**判定 🟢**。实盘零漂移（def :66-67，全仓唯一命中即 def 自身，rg+callgraph 双证零调用，tests 零命中）。删 :67 后 `_has_value`(:35) 仍被 :49 用不成孤儿。分层/迁移无害。唯一隐患=手滑波及相邻活函数（:47-63 `_has_navigation_context` 被 :114 真用 / :70 `_use_plain_scheduler_chrome` / :35 `_has_value` / :31 `_text`）→ 锚定单符号 `def _has_navigation_date_range` 即规避，属操作失误非债爆炸半径。与 R65 仅行号漂移（同文件，符号定位可吸收），逻辑零耦合。

### 🟢 R66 — `_context_summary` reports_workbench 私有死副本【安全：按 suffix 签名定位即可】

**判定 🟢（前提：严格按签名定位 + R54 后重定位）**。实盘坐实 dead `reports_workbench.py:150 (context, suffix="")` vs LIVE `workbench_links.py:258 (context, target_page, view=None)`@:448 调用，签名特征 `suffix` 可区分。dead 全仓零调用（prod/test/__all__/导入方四路零引用）。分层/迁移无害。两个软约束：① R54 `_copy_plan_guard_fields:36` 在 :150 上方，落地后 :150 漂移→**删前按 `suffix` 签名实时 rg 重定位，禁用裸 :150**；② **绝不跨文件批量/IDE rename 误删 workbench_links.py:258 LIVE**（→:448 build_workbench_link 的 context_summary 文案静默丢失/NameError）。

---

## 漏项（本轮新发现，未被计划覆盖）

1. **【最危·R42】dossier 漏 dashboard_workbench_context.py:92 删点**：dossier 把 `dashboard_workbench.py:121` 判为"消失"，但 plan_id 落点迁到**同名不同文件** `dashboard_workbench_context.py:92`，经 `:119 build_workbench_plan_context(**_context_kwargs)` 的 `**` 展开真实流入被删形参。修法清单缺此点 = **删 :191 形参后 dashboard 启动即 TypeError 500**。前置 MUST 把 :92 dict 键纳入 R42 同提交删除清单。
2. **【R42】navigation_context.py:57 override 路径 `build_workbench_plan_context(**kwargs)` 的 kwargs 来源未审**：:78 那条是显式 plan_id（已在清单），但 :57 走 `_navigation_context_override()` 的 `**kwargs`，其 kwargs 是否含 plan_id 键未回盘——若含且不删=同 C0 TypeError。owner 须补审 kwargs 来源。
3. **【R42 函数名口径错】**：cluster/dossier 多处写禁区在 `build_workbench_navigation_context`，实盘是 `current_workbench_navigation_context`(:69)。不撼结论但执行须按符号。
4. **【R60 计划外相邻 plan_role 族】**：link_query 顶部 :6-9 另有 `plan_role/requested_plan_role/effective_plan_role/scenario_id` 字段表 + :78-79 `execution_review` plan_style——R60/R42 删 plan_id 时若粗匹配 plan_* 易误伤，需明列这些非删区。

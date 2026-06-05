# 逐簇爆炸对抗 r1 — C-NAV-PLANID / 主透镜 SOUL（灵魂线热路径 + 收口等价）

> skeptic 第 1 轮，只读不改任何 .py。行号 2026-06-05 rg 实盘回盘，旧值不信。
> 成员债 [R42, R60, R64, R65, R66]。主透镜 Q4/Q5/Q6（灵魂线热路径 + 收口等价 + 测试迁移序），六质问点全过。
> 默认怀疑：多数维度存疑即标红，不放过「测试绿但护栏已破」的静默失效。

## 实盘回盘真相表（本轮亲采，2026-06-05）

| 点 | 文件:line | 实盘内容 | 判 |
|---|---|---|---|
| emit-A | scheduler_workbench_link_query.py:118 | `_append_param(query,"plan_id",...)`，**被 :117 version / :119 plan_role / :120 scenario_id 前后夹住** | C1 灾难链坐实 |
| emit-B | scheduler_workbench_link_query.py:154 | execution_review 分支（:152 `if plan_style=="execution_review"`），**只有 version:153/plan_id:154/plan_role:155 三参，本就无 scenario_id**，:156 `return` | 与 emit-A 结构不对称（真实，非债，见漏项 X1） |
| R60 字段表-1 | scheduler_navigation_links.py:12 | `_REPORT_CONTEXT_FIELD_NAMES` 元组首项 plan_id；元组 :11-28 共 16 项，:13 back_to/:14 scenario_id 紧随 | 删 :12 一项，邻键禁碰 |
| R60 判空 | scheduler_navigation_links.py:52 | `_has_navigation_context` any() 元组 :50-62 内 plan_id；:51 version / :63 `_text(plan_role)!=ROLE_ADOPTED` | 删 :52 一项 |
| R60 字段表-2 | reports_export_support.py:14 | `_EXPORT_CONTEXT_KEYS` 元组 :13-29 首项 | 删 :14 一项 |
| R64 死叶子 | scheduler_navigation_links.py:66-67 | `_has_navigation_date_range`，零调用；body 用 `_has_value`（:36 def，:49 另用→删 :67 不成孤儿） | 纯删 :66-67 |
| R65 死 def | scheduler_navigation_links.py:74-78 | `_target_url`，内用 query_for_target(:6 import)/urlencode(:4 import)/TARGET_PAGE_PATHS(:7) | 三件套① |
| R65 化简点 | scheduler_navigation_links.py:160 | `_plain_link(label, plain_url or _target_url(...), ...)`，9 spec plain_url 全非空→短路恒真 | 三件套② |
| R65 孤儿 import | scheduler_navigation_links.py:4 / :6 | urlencode / query_for_target，删 def 后孤儿 | 三件套③ |
| **R65 禁删** | scheduler_navigation_links.py:7 | `TARGET_PAGE_PATHS`，**:177 build_report_navigation_links 真用**（亲见） | 绝不可删 |
| R66 死副本 | scheduler_reports_workbench.py:150 | `def _context_summary(context, suffix="")`，零调用 | 纯删 :150-163 |
| **R66 LIVE 异签** | scheduler_workbench_links.py:258 | `def _context_summary(context, target_page, view=None)`，**:448 build_workbench_link 真调** | 绝不可误删 |
| R54 guard 形参 | scheduler_workbench_links.py:206-207 | `guardrail_text:str=""` / `guardrail_reason_type:str=""`，在 plan_id 形参 :191 **之后** | R54 先→R42 rebase 后 |
| R54 同文件 | scheduler_reports_workbench.py:36 | `_copy_plan_guard_fields`，在 R66 死函数 :150 **上方** | R54 先→R66 按 suffix 符号重定位 |
| R42 读入 | navigation_context.py:78 | `plan_id=_request_arg("plan_id")`，**:79 plan_role 强制护栏 / :80 scenario_id 禁碰** | 删 :78 不碰 :79/:80 |
| R42 读入 | reports_page_support.py:104 / :143 | `plan_id=_request_text("plan_id")` | 删，LB06 adopted/scenario 分支禁碰 |
| R42 透传 | scheduler_reports_workbench.py:60(形参)/:79(透传) | `plan_id: Any=None` / `plan_id=plan_id` | 删 |
| roadmap | items.yaml:289 | "…导出链接和筛选隐藏字段保留 plan_id 与 back_to" **仅此 1 处真实**（acceptance/checklist 幻觉证实） | F 门 owner 对齐下线 |
| 死证 | core/ data/ | `\bplan_id\b` 去 plan_identity/idempotency **0 命中** | 死面包屑成立 |
| contract | regression_reports_workbench_navigation_contract.py:109/122/126 | plan_id 三断言；:123/127 back_to **保留** | 先迁测试 |

## 逐成员判定

### R42 — plan_id 死面包屑全链下线 → 🟡黄（有条件可做）
- **Q4 灵魂线**：P6 纯直删，无 raise 改造、无收口、无热路径放大。死证坐实（core/data 零 resolver）。灵魂线本身✅，不触 P4 类风险。
- **Q1 承重误删 + Q5 收口等价**：最危是 **C1（emit 误删邻参）**——emit-A :118 被 version:117/plan_role:119/scenario_id:120 前后夹住。**灾难链**：删 :118 时若手滑波及相邻 `_append_param(version/plan_role/scenario_id)` → 导航/报表 URL 丢真身份参数 → 下游 version 解析**静默错位**（version 是真消费者）→ 打开错版本报表，**无任何报错**。这是「测试绿但护栏已破」的典型静默失效（contract 只断言 plan_id 消失/back_to 保留，未逐字钉 version/plan_role/scenario_id 不变）。
- 黄条件（缺一即升红）：① 必须按符号删 `_append_param(query,"plan_id",...)` 整行，绝不裸行号 sed；② parity 断言**必须扩成**「删后 query 的 version/plan_role/scenario_id/back_to 逐字 == 删前」，dossier §7 已要求但 contract 现状未覆盖→**必须先补这条 parity 再删**；③ R54 先落（:206-207 在 :191 后），R42 删 plan_id 形参 rebase 在 R54 新签名后；④ 与 R60 同提交（见下）。
- **Q6 测试序**：先迁 contract :109/:122/:126（去 plan_id 留 back_to）→ 再删生产 → 跑测试。序错=中间态红。
- **Q2/Q3**：纯 web 层删除，零越层、零导入环、零迁移耦合。

### R60 — plan_id 字段表承认面 → 🟡黄（必须与 R42 同提交）
- **Q4/Q5**：P6 纯删元组项，无收口、无 raise。✅灵魂线。
- **Q1 承重误删**：最危 = **元组删行连带删邻键**。:13 back_to / :14 scenario_id 紧贴 :12 plan_id（_REPORT_CONTEXT_FIELD_NAMES），export 表 :14 plan_id 后是 back_to/scope_*。**灾难链**：误删 back_to 或 scope_*/resource_* → 隐藏表单/导出 URL 丢真承重透传键 → 报表跨页跳转**静默丢上下文**（date_range/resource/scope 失传）→ high 级回归，无报错。
- 黄条件：① **MUST 与 R42 单次提交**——半截即残渣（C2：R42 留读存而 R60 删表 = preserved_report_context_fields 迭代到不存在键被跳过留死表；R60 删表而 R42 留 = emit 仍挂 plan_id 字段表却不认 = 隐蔽残渣）；② emit :118/:154 **归 R42 删，R60 不得重复删**（同点双删=键位移冲突）；③ 三张表只删 plan_id 一项，邻键禁碰。
- **Q6**：与 R42 共享同一组 contract 断言，**只迁一次**，禁两债各改一遍。
- **Q2/Q3**：零越层、零迁移耦合。LB05 假边（primary 在 execution_review.py 非 link_query）已证，无协调。

### R64 — _has_navigation_date_range 死叶子 → 🟢绿（安全）
- 全仓零调用（rg + callgraph 双证）、零测试耦合。删 :66-67 后 `_has_value`(:36) 仍被 :49 用，不成孤儿（亲证）。非承重、非收口、非 P4。Q1-Q6 全过。
- 唯一隐患=手滑波及相邻活函数 :47-63 `_has_navigation_context`/:70-71 `_use_plain_scheduler_chrome`（NameError），按符号锚定即规避，属操作失误非债爆点。
- 建议与 R65 同提交避行号二次漂移（软约束，逻辑零耦合）。

### R65 — _target_url 死分支三件套 → 🟡黄（执行精度门）
- **Q5 收口等价**：:160 `plain_url or _target_url(...)` → `plain_url` 是表达式等价替换。9 spec plain_url 全非空字面量（亲见 :144-152 / :168-174 走 :177 路径）→ 短路恒真，逐分支等价✅。**但等价依赖「specs 第 3 字段恒非空」不变量**——若未来新增 plan_url='' spec 则化简丢 _target_url 回落=行为分歧。
- **Q1 误删（最危）**：三件套删 :4/:6 两 import，**但 :7 TARGET_PAGE_PATHS 绝不可删**——:177 build_report_navigation_links 真用（亲见）。**灾难链**：把 :7 误判孤儿一并删 → :177 NameError → 报表导航条全挂（fail-fast 非静默，但全栈级破坏）。这是本债真实最大爆点。
- 黄条件：① 三件套硬原子同提交（删 def + 化简 :160 + 删 :4/:6），缺①②即 NameError 破 build；② :7 必须保留；③ **必须补不变量护栏测试** `specs 第 3 字段恒非空`，把化简前提钉成红线防回归（dossier §7 要求）。
- **Q6**：零测试迁移（_target_url 测试零命中）；护栏为新增非迁移。
- **Q2/Q3**：纯删减依赖，零越层零环零迁移。

### R66 — _context_summary 死副本 → 🟡黄（跨文件误删门）
- P6 纯删 :150-163，非承重、非收口、非 P4。✅灵魂线。
- **Q1 误删（最危）**：**跨文件误删 LIVE 同名异签** scheduler_workbench_links.py:258 `(context, target_page, view=None)`（:448 真调，亲见）。**灾难链**：IDE 全局 rename / 裸行号误删 :258 → 所有 workbench link 卡片 context_summary 文案静默丢失或 NameError。
- **Q6 行号漂移**：R54 改 :36 `_copy_plan_guard_fields`（在 :150 上方，亲证）→ R66 删除前**必须按 `suffix` 签名实时 rg 重定位**，严禁沿用 :150（三处口径打架 old:141-154/blast:144/evidence:150，实盘 :150）。
- 黄条件：① 严格按 `def _context_summary(...suffix...)` 签名定位本文件 :150，绝不跨文件批量；② R54 先落或同提交，删前实时重定位。
- **Q2/Q3**：零越层零环零迁移。

## 漏项 / 本轮新发现（计划未覆盖的爆点 / 缺失前置）

- **X1（新发现，结构不对称非债，但 parity 必须覆盖）**：emit-A(:118 `_append_plan_query`) 与 emit-B(:154 `_append_target_plan_query` execution_review 分支) **身份参数集不同**——emit-A 删 plan_id 后剩 version/plan_role/scenario_id 三参；emit-B 本就只有 version/plan_id/plan_role 三参（**无 scenario_id**），删后剩两参。这是真实合法非对称（execution_review 身份不带 scenario_id），但 **R42 的 parity 断言必须分别覆盖两种 plan_style**，否则只测常规分支会漏掉 execution_review 分支的误删——dossier §7 已点名但 contract 现状（:105 用例只走 utilization 常规分支）**未覆盖 execution_review emit-B 路径**，是计划缺失前置。

- **X2（缺失前置，最高优先级）**：C1 灾难链的 parity 断言（query 的 version/plan_role/scenario_id/back_to 删前后逐字相等）**当前 contract 测试根本不存在**——:122/:126 只断言 plan_id 值，:123/:127 只断言 back_to，**version/plan_role/scenario_id 零断言**。这意味着删 emit 时即使误伤相邻身份参数，**现有测试全绿也照样放过**（测试绿但护栏已破）。**前置 MUST**：先补 version/plan_role/scenario_id parity 断言（含 emit-A 与 emit-B 两 plan_style），再动 emit。这条不补=整簇最大静默失效口。

- **X3（缺失护栏）**：R65 化简等价依赖「9 specs plain_url 恒非空」不变量，**当前无任何测试钉死该不变量**。删 _target_url 后若未来加 plain_url='' spec，化简静默丢回落且无测试拦截。前置=补 `test_all_nav_specs_have_nonempty_plain_url`。

- **X4（F 门缺口确认）**：roadmap items.yaml:289 是 in-progress `aps-frontend-workbench` feature 契约文字，删它需 owner 对齐（registry 另称的 acceptance.md:52 / checklist.yaml:82 经回盘证实为幻觉——目录无 checklist，acceptance 内 0 个 plan_id）。不对齐 owner 直接删 = 触碰在途 feature 契约。

- **X5（无新增爆点确认）**：本簇全非承重、全 web 层删除，Q2 分层环 / Q3 迁移耦合（schema CHECK / v18·v19 DB CHECK）**全零命中**——本簇与 adopted-only v19 CHECK、operation_execution_scope R09 收口家均无交集，不属灵魂线热路径（LB03 latest_executable_official_version 不在本簇文件）。Q4 灵魂线对本簇=纯绿（无 raise 改造对象）。

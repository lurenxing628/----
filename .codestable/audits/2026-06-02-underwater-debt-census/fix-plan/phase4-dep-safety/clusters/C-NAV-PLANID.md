# 簇 C-NAV-PLANID 原子簇重建（只读产物）

> 成员债 [R42, R60, R64, R65, R66] | 主文件 navigation_context.py / reports_page_support.py / scheduler_workbench_links.py / scheduler_workbench_link_query.py / scheduler_navigation_links.py
> 本档案只读不改任何 .py，行号均 2026-06-05 rg 实盘回盘，旧值不信。

## A) 原子子簇拆分

本簇 5 债全为 P6 死码（severity medium/low，全非承重 load_bearing=false / owner_pending=false），但物理落点分三组，**两个强原子子簇 + 一个孤立债**。

### 子簇 AS-1 = {R42, R60}「plan_id 死面包屑整链下线」— 强原子，MUST 同一次提交
- 原子原因（三重）：
  1. **同符号 co-change**（registry interference_edge `same_symbol=true, sym:build_workbench_plan_context`）：R42 删该函数读入/存储侧（`scheduler_workbench_links.py:191` 形参 + `:233` dict 键），R60 删字段表承认侧（`scheduler_navigation_links.py:12/52`、`reports_export_support.py:14`），操作同一死数据流两端。
  2. **共享 emit 点**（实盘双证）：`scheduler_workbench_link_query.py:118`（`_append_plan_query` 内 `_append_param(query,"plan_id",context.get("plan_id"))`）与 `:154`（`_append_target_plan_query` 的 `execution_review` 分支，:152 `if plan_style=="execution_review"`）既是 R42 回吐点也是 R60 承认面。**这两行只能删一次，由 R42 统一删，R60 不得重复删**——分两次删=同点双删冲突/键位移。
  3. **半截即残渣**（无安全中间态）：只删一边 = 字段表认一个无人写入的键（R42 先 → R60 后的中间态）或 emit 引用已删的键（R60 先 → R42 后的中间态），均落新 P3 债（corrections C2/灾难链①）。
- 测试同退（共享同一组断言，只迁一次）：`tests/web_pages/test_reports_workbench_navigation_contract.py:109`（fixture URL 去 `plan_id=PLAN-RPT` 片段）/ `:122`（删 `query["plan_id"]` 断言）/ `:126`（删 `hidden_inputs["plan_id"]` 断言），**保留 :123/:127 back_to 断言**。
- roadmap 同退：`.codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml:289` **仅此 1 处真实**（registry 声称的 acceptance.md:52 / checklist.yaml:82 是幻觉——目录无 checklist 文件、acceptance 内 0 个 plan_id）。
- **内部顺序**：R42 与 R60 之间**无先后，必须合并单次提交**；唯一硬分工=emit:118/154 归 R42 删、R60 不动。整子簇执行顺序见下「关键内部顺序」（先迁测试 → 再删生产 → 跑测试自证）。

### 子簇 AS-2 = {R64, R65}「scheduler_navigation_links.py 同文件死叶子」— 行号原子，强建议同提交
- 原子原因：**两债同物理文件且都做删除，行号互相漂移**。R64 删 :66-67（`_has_navigation_date_range` def，位于 R65 `_target_url` :74 上方）；R65 删 :74-78 def + 化简 :160 + 删孤儿 import :4/:6。R64 先落则 R65 的 :74-78/:160 上移 ~2-3 行；R65 先落则删 :4/:6 import 把 R64 的 :66 大幅上移。
- **逻辑零耦合**（重要区分）：R64 的 `_has_navigation_date_range` 不被 R65 任何符号引用，R65 改的 `_target_url`/import 也不碰 R64——即使分提交也**不会 NameError**。原子性只为「避免行号二次漂移」，不是逻辑硬约束。两债均建议按**符号定位**而非裸行号。
- **R65 自身内部三件套硬原子**（缺一即 NameError，破 build）：① 删 `def _target_url`(:74-78) ② 把 :160 `_plain_link(label, plain_url or _target_url(...), ...)` 化简为 `_plain_link(label, plain_url, ...)` ③ 删孤儿 import :4 `urlencode` + :6 `query_for_target`。**:7 `TARGET_PAGE_PATHS` 绝不可删**（实盘 :177 `build_report_navigation_links` 真用，是本债最大误删爆炸点）。
- **内部顺序**：同次提交则按原始行号自上而下删（先 :66-67 再 :74-78）一次算好补丁；若分提交，建议 **R65 先、R64 后**（R65 在文件下半，先删不冲 R64 的 :66-67；反之 R64 先删会冲 R65 锚点行号），但因均按符号定位，顺序为软约束。

### 孤立债 AS-3 = {R66}「scheduler_reports_workbench.py 私有死副本 _context_summary」— 可独立
- 不与 AS-1/AS-2 任何成员共文件、共符号、共行。唯一交互见 §B（同文件 R54 跨簇行号前置 + 跨文件 R42 仅「读它确认 LIVE 别误删」）。
- 改点：删 `scheduler_reports_workbench.py:150-163` 死 `_context_summary(context, suffix="")`（按 **suffix 形参签名**定位，非裸行号）。
- **跨文件误删红线**：绝不动 `scheduler_workbench_links.py:258` 的 LIVE 同名异签 `_context_summary(context, target_page, view=None)`（:448 `build_workbench_link` 真调）。

## B) 跨簇边（本簇成员 → 其他簇债）

| 本簇债 | 指向 | 关系类型 | 实盘依据 / 处置 |
|---|---|---|---|
| **R42/R60**（AS-1）| **R54**（NAV-GUARD 簇）| **parity/承重先于动同文件 + 同符号 rebase** | R54（Batch-2 P5 收口）在 `build_workbench_plan_context` 加 guard 字段——实盘已见 `scheduler_workbench_links.py:206 guardrail_text:str=""` / `:207 guardrail_reason_type:str=""` 形参在位。R42 删该函数 plan_id 形参(:191) **MUST rebase 在 R54 新签名之后**，否则形参列表互撞。**R54 先 → R42/R60 后**。 |
| **R66**（AS-3）| **R54**（NAV-GUARD 簇）| **承重先于动同文件（纯行号偏移）** | R54 改同文件 `scheduler_reports_workbench.py:36 _copy_plan_guard_fields`（13/16 键手维 mapping，Batch-2 收口到 PlanIdentity.to_dict），位于 R66 死函数 :150 **上方**。R54 落地后 :150 下移 → **R66 删除前必须按 suffix 签名实时 rg 重定位**，严禁沿用 :150。R54 先 → R66 后，或同提交。两者改不同符号无逻辑耦合。 |
| **R42**（AS-1）| **R56/R57**（已 fixed，navigation_context.py）| **承重禁区（已 fixed，退化为禁区约束）** | 删 `navigation_context.py:78 plan_id=_request_arg(...)` 时**绝不碰** :79（R56 `plan_role=... else ROLE_ADOPTED` 护栏）/ :80（scenario_id）。三者是同一 `build_workbench_navigation_context(...)` 调用的不同关键字实参，语法独立。 |
| **R42**（AS-1）| **LB06**（已 fixed，reports_page_support.py）| **承重禁区（已 fixed）** | 删 `reports_page_support.py:104/:143 plan_id` 形参时**绝不碰** build_report_context 内 execution-review→plan_role='adopted'/scenario_id=None 强制分支（LB06 承重护栏，已补注释）。 |
| **R42/R66**（AS-1/AS-3）| **LB02**（workbench_links.py / reports_workbench）| **假/弱边——同文件粗匹配噪声** | interference_edge 标 same_file，但 R42 在 workbench_links 的真实点是 :191/:233 plan_id 读存，R66 删 :150 孤立死函数，均 same_symbol=false，不与 LB02 共符号/共行。**降级为非协调对象**（见 §C）。 |
| **R42**（AS-1）| **R67**（reports_export_support.py）| **同文件粗匹配，弱** | same_file=true / same_symbol=false。R42/R60 在 export_support 的点是 :14 `_EXPORT_CONTEXT_KEYS` 删 plan_id 一行；需确认 R67 守护范围不含该元组项即可，无强序。 |
| **R66**（AS-3）| **R42**（**同簇内** AS-1）| **只读确认，非改动边** | R66 跨文件「读 workbench_links 确认 LIVE _context_summary:258 别误删」，不改该文件。属簇内交互，非真跨簇。 |

## C) 相对旧 146 边的变化（逐条）

### 删除（边作废）
- **R42↔R56**：R56 `status_2026_06_05=fixed`（corrections E 节）。旧「活跃同文件兄弟需顺序协调」边删除 → 退化为禁区行约束（navigation_context.py:79，见 §D）。
- **R42↔R57**：R57 `fixed`（corrections E 节）。旧 fallback 双构建路径协调边删除 → R42 删 plan_id 不触 plan_role/scenario_id 解析路径。
- **R42↔LB06**：LB06 `fixed`（corrections D/E 节）。旧 reports_page_support 承重协调边删除 → 退化为禁区行（adopted/scenario_id 强制分支）。
- **R60↔LB05**：LB05 primary 实为 `execution_review.py`（非 link_query），interference_edge 标 link_query 为**文件共置噪声**，LB05 守护与 R60 删除点无交集 → **假边删除**。
- **R42/R66↔LB02**：same_file 粗匹配，same_symbol=false，无共符号/共行 → **降为非协调（见降级）**。

### 新增 / 强化
- **R42→R54 同符号 rebase 边（强化）**：实盘坐实 R54 guard 字段已落 `workbench_links.py:206-207`，R42 删 plan_id 形参须 rebase 其后。原 registry 仅标 same_file，现强化为 **same_symbol co-change 硬序**（R54 先 → R42 后）。
- **R66→R54 同文件行号前置（新增/明确）**：R54 改 :36 区间漂移 R66 的 :150，新增「R54 先 / R66 按 suffix 符号重定位」软序边。

### 降级
- **R65↔R42 节奏脱钩（降级为弱）**：同 `scheduler_navigation_links.py` 但 R42 在该文件无任何改点（R42 真实点在 navigation_context/reports_page_support/workbench_links/link_query），与 R65 的 _target_url/specs **无符号交集、无行号撞车**。R42 体量大且 Batch-3 门控，R65 Batch-1 后无门控 → **不建议同提交，降为弱同文件提示边**。
- **R64↔R42 / R66↔LB02/LB06**：同上，same_file 噪声 → 降为非阻塞提示。
- **R60↔R54（navigation_links 元组）**：registry hint 称 R54 相邻 navigation_links，但 R54 `all_files` **不含 scheduler_navigation_links.py**，`_REPORT_CONTEXT_FIELD_NAMES` 唯一定义/消费均在 navigation_links（R60 改），R54 收的是别表 → **零行号冲突，降级为「无 R54↔R60 协调依赖」**。

> 校正种子已核（corrections B 节假边 R02↔R25 / R45↔LB07等 / R20↔R08等 / R32↔R15 / LB04↔LB07等 / R26↔R43 / config_snapshot / R13↔R18 解耦 / R05→R34 降级）**均不落本簇成员**，本簇无重叠假边需删（本簇假/弱边仅上列 LB05/LB02 同文件噪声）。

## D) 承重前置 + 禁区行门控

本簇 5 债自身全非承重（load_bearing=false / lb_no_touch=null），**无簇内 LB/N1/N2/R03/R58 承重点需先落注释**。承重门控全来自**毗邻已 fixed 护栏 + 跨簇 R54**，门控如下结构动作：

### 禁区行（删除时绝不顺手碰/统一/透传）
- `navigation_context.py:79` — R56 `plan_role=plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED`（execution_review/adopted 强制语义，已 fixed）。
- `navigation_context.py:80` — `scenario_id=scenario_id`（同函数承重数据面）。
- `reports_page_support.py` build_report_context 内 execution-review→`plan_role='adopted'/scenario_id=None` 强制分支（LB06 承重，已 fixed）。
- **link_query:117/119/120 与 :153/:155**（version/plan_role/scenario_id）— C1 最危灾难链：删 :118/:154 plan_id 时误伤前后紧邻的真身份参数 → URL 丢身份 → version 解析**静默错位**（无报错）。实盘已证 plan_id 被三个真消费身份参数前后夹住。
- `scheduler_navigation_links.py:7` `TARGET_PAGE_PATHS` import — R65 三件套**绝不可删**（:177 真用）。
- `scheduler_navigation_links.py` 三张表/判空元组其余键（back_to/scenario_id/date_*/resource_*/scope_*/version/plan_role）— R60 只删 plan_id 一项。
- `scheduler_navigation_links.py:47-63 _has_navigation_context` / :70-71 `_use_plain_scheduler_chrome` / :35-36 `_has_value` / :31 `_text` — R64/R65 相邻活函数，误删即 NameError。注：`_has_value` 在 :49（留）与 :67（R64 删）两用，删 :67 后 :49 仍在不成孤儿；:63 用的是 `_text` 非 `_has_value`（registry 口误，已核）。

### 跨簇承重前置（门控簇内结构动作）
- **R54 必须先落（Batch-2）**，门控 AS-1 的 R42 删形参（rebase 在 R54 新签名后）+ AS-3 的 R66 删除（按 suffix 符号重定位，R54 漂移 :150）。
- **F 门（owner 对齐）**：AS-1 触碰 in-progress `aps-frontend-workbench` roadmap items.yaml:289，需 owner 对齐下线 + 接受 contract 三断言退法。

## E) fixed 成员残留动作（前置已完成，标残留）

本簇成员**无一是 fixed**（R42/R60/R64/R65/R66 全 planned）。fixed 仅作为 R42 的**毗邻前置护栏**，已落地，残留动作 = 仅认账/禁区约束，不再改：
- **R56**（navigation_context.py:79 fixed）：偏离铁律 3（走结构路线删字面量本体，护栏重定位到页级 identity_error+blocked，未 fail-open，契约 `regression_execution_review_identity_guardrail` 钉死）。残留 = **owner 认账此偏离**（corrections D 节）；R42 执行时只把 :79 当禁区，不连带改。
- **R57**（navigation_context.py fixed）：已收敛，残留 = 无；R42 删 plan_id 不触解析路径。
- **LB06**（reports_page_support.py fixed）：优于计划（更硬 fail-closed），残留 = **仅缺认账注释**（corrections D 节，勿粘 §90 LB-B4 反向 fail-open 文案）；R42 只把 adopted/scenario_id 强制分支当禁区。
- **R54**（跨簇，planned 非 fixed，但 Batch-2 前置）：升级为 **5 套手维列表**，本簇受影响的是 ③`scheduler_resource_dispatch.py` / ④`scheduler_reports_workbench.py:36`（R66 同文件上方）；R42 受其在 workbench_links 的新 guard 签名约束。R54 先落是 AS-1/AS-3 的硬/软前置。

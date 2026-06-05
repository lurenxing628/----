# 红队 round1 · 2 号 agent · 簇拆并角度（只读不改）

> 攻击角度：原子簇拆并粒度。哪个该拆（误判同文件/同簇）？哪个该并（漏硬耦合）？C01 巨簇切分对吗？R54 五套手维列表是否被当成一个原子簇正确处理？
> 回盘 HEAD c2aa7501，行号全部当前工作区 rg 实盘，不信旧值。被测对象=_interference_rebuilt.md + clusters/C-NAV-*.md + corrections。
> 铁律遵守：只读不改任何 .py；承重只挑「没标到」的问题，不建议删/统一/透传。

## 发现清单（6 个真问题 + 1 个澄清不计入）

### P1【该并未并 / 重灾区漏登】R54 五套手维面分散在 5 个不同物理文件，G04 只物理绑定了其中 1 套，§3 重灾区表漏登另 4 套所在文件
- **问题**：R54 被认定为「一个 owner_pending 承重单债」(G04 成员)，A-2 节正确把「5 套手维面一次改完」定性为单债内子序。但 G04 这个**原子单元的物理边界只含 navigation_publish.py（L2 那套）**，与 R58/R44 同文件绑定。另外 4 套 R54 手维面在 4 个独立文件里，DAG 里**没有任何原子绑定把这 5 套钉在同一次提交**。§3「重灾区文件清单」只把 `scheduler_navigation_publish.py` 和 `scheduler_workbench_links.py` 列为 R54 命中文件，而 R54 真正改动的另 4 个文件（dashboard / resource_dispatch / reports_workbench / gantt_task_detail）**全部缺席重灾区表**。
- **证据（实盘 rg）**：5 套手维面分散落点——
  - L2 `web/routes/domains/scheduler/scheduler_navigation_publish.py:12` `_PLAN_GUARD_FIELD_NAMES`（16 键，G04 唯一物理含的那套）
  - L1 `web/viewmodels/scheduler_reports_workbench.py:36` `_copy_plan_guard_fields`（12 键）
  - L3 `web/routes/domains/scheduler/scheduler_resource_dispatch.py:64` `_copy_plan_guard_fields`（15 键）
  - L4 `web/viewmodels/dashboard_workbench_context.py:8` `_PLAN_GUARD_FIELD_NAMES`（16 键，≡L2 逐字）
  - L5 `web/viewmodels/scheduler_gantt_task_detail.py:8` `_PLAN_GUARD_FIELD_ALIASES`（别名元组）
- **为何是硬伤**：R54 是承重失忆债，5 套手抄列表本就是「同一概念被复制 5 份、易漂移」的典型。若拆批时只按 G04 的物理文件边界（navigation_publish.py）执行，另 4 套不在同一原子单元里 → 极易出现「改了 L2 忘了 L1/L3/L4/L5」的半截收口，正是该债要治的病本身。重灾区表既然按「物理文件 ≥2 债且顺序敏感」收录，**至少 reports_workbench.py（R54·L1 + R66 死副本 :150 + R42/R60 同文件）已是 ≥2 债顺序敏感文件，却没进表**。
- **修正建议（只读，不动代码）**：(1) 在 §1 G04「内部顺序」列显式列出 5 套手维面的 5 个 file:line，并标注「5 套必须同窗口、按符号收口、收口后逐套重 rg 复核字段集一致」；(2) §3 重灾区表补登 `web/viewmodels/scheduler_reports_workbench.py`（R54·L1 + R66 + R42/R60）、`web/viewmodels/dashboard_workbench_context.py`（R54·L4）、`web/routes/domains/scheduler/scheduler_resource_dispatch.py`（R54·L3；注：R08/R09 在另一文件 `web/viewmodels/scheduler_resource_dispatch_execution.py`，与本 L3 文件不同，不并）、`web/viewmodels/scheduler_gantt_task_detail.py`（R54·L5）为 R54 跨文件命中；(3) 因这是承重单债，绑「5 套字段集 parity」守卫钉住三种基数，禁统一（见 P2）。

### P2【字段集分叉被低估】R54 五套手维面是 3 种不同基数（16/15/12 键）+ 源键分叉，corrections/cluster 只描述为二元「源键分叉 + 字段集分叉」且 surface 归属标错
- **问题**：corrections C 节与 C-NAV-GUARD §A-2 把 R54 双分叉描述为「③同名键 vs ④别名键 requested_role/selected_role/is_official」+「④缺 plan_identity_error/blocking_error/blocking_scope 三阻断态字段」。实盘核出**实际更碎**：是 3 种字段集基数，且别名分叉的 surface 归属与文档相反。
- **证据（实盘逐键数）**：
  - L2 nav_publish = **16 键**（含 `plan_role_status` + 三阻断态 `plan_identity_error/blocking_error/blocking_scope`）
  - L4 dashboard = **16 键**（与 L2 逐字相同）
  - L3 resource_dispatch = **15 键**——**缺 `plan_role_status`**（该 surface 守 13 个身份键 + parse_failed/reason；`plan_role_status` 实盘只出现在该文件 :267 一个无关 filter，不在 guard 元组内）
  - L1 reports_workbench = **12 键**——缺 `plan_role_status` + 三阻断态全缺，且**用别名源键** `data.get("requested_role")/("selected_role")/("is_official")/("is_preview")`
  - L5 gantt = 别名元组，含 `plan_role_status`
- **归属错**：文档说「③resource_dispatch 同名键 vs ④reports_workbench 别名键」。实盘：**用别名源键的是 L1 reports（requested_role/selected_role/is_official/is_preview），不是某个被标为「④」的；L3 resource_dispatch 反而是同名键**。文档把别名分叉挂在 ④reports 是对的方向，但同时把③resource_dispatch 也算进「同名」时漏了它缺 plan_role_status 这一第三种基数。
- **为何是硬伤**：「禁统一键名」这条承重红线建立在「字段集分叉」之上。若 owner 只知道两种分叉（16 全 vs 缺三阻断态），收口时很可能把 L3 的 15 键当成 16 键「补齐」`plan_role_status` → 这恰恰是「统一」改行为，违 R54 承重红线。三种基数必须各自钉 parity。
- **修正建议**：把 corrections C / C-NAV-GUARD §A-2 / §5.1 R54 行的「双分叉」改述为「三种基数（16/15/12）+ L1 别名源键分叉」，并在 G04 parity 守卫里**分三组钉死键集**，禁任意 surface 向 16 键看齐。

### P3【行号漂移误值】C-NAV-GUARD §0 锚点表把 resource_dispatch 标「def:64 / call×2 :95 / :199」，实盘只有 1 个 guard-copy call（:109），:95 是 build collar call 不是 guard call，:199 无对应
- **问题**：C-NAV-GUARD.md:14 锚点行 `R54 L3 resource_dispatch _copy_plan_guard_fields def / call×2 | :64 / 95 / 199`。
- **证据（实盘）**：该文件 291 行；`_copy_plan_guard_fields` def 在 :64，**唯一调用点在 :109**；:95 是 `build_workbench_plan_context(...)` collar 调用（不是 guard-copy）；:199 处无 `_copy_plan_guard_fields` 调用（rg 全文件仅 :64 def + :109 call 两处命中）。
- **为何是硬伤**：「call×2」是凭空多出的一个调用点。动手时若按文档去 :95/:199 找 guard-copy 调用会扑空或误改 collar 调用行（:95），且 :109 真调用点反而没被锚定 → 收口 L3 时漏改真调用点。
- **修正建议**：把锚点改为 `def :64 / call :109`（collar 调用单列为 :95 build_workbench_plan_context，区分语义），删「×2 / :199」。

### P4【layer/路径误标】R54 四套手维面被 corrections / C-NAV-GUARD 标在 `web/routes/domains/scheduler/`，实盘其中 reports_workbench 与 dashboard 在 `web/viewmodels/`
- **问题**：corrections C 节列 R54 5 套时 ④`scheduler_reports_workbench.py:36`、①`dashboard_workbench_context.py:8`、⑤`scheduler_gantt_task_detail.py:8`，C-NAV-GUARD §3 行头主文件也含这些短名；但落点目录被默认归到 routes 域。
- **证据（实盘 rg）**：`_copy_plan_guard_fields`/`_PLAN_GUARD_FIELD_NAMES` 的真实路径——`web/viewmodels/scheduler_reports_workbench.py`、`web/viewmodels/dashboard_workbench_context.py`、`web/viewmodels/scheduler_gantt_task_detail.py`、`web/viewmodels/scheduler_navigation_links.py`（R64/R65）均在 **viewmodels 层**；只有 `scheduler_navigation_publish.py`、`scheduler_resource_dispatch.py`、`scheduler_analysis_links.py` 在 `web/routes/domains/scheduler/`。
- **为何是硬伤**：(1) 「分层 0 违规」是铁律，viewmodels↔routes 是两个分层，R54 同时落两层这一事实在文档里被抹平成「都在 routes」，掩盖了「收口点在 viewmodels（workbench_links）、消费面横跨 viewmodels + routes」的真实分层拓扑；(2) 拆批时按错误路径定位文件 → rg 扑空。
- **修正建议**：cluster 头与 corrections 逐个补全 R54 5 套的完整路径前缀（3 套 viewmodels / 2 套 routes/domains/scheduler），并在 §3 重灾区注明 R54 是跨 viewmodels+routes 两层的承重面。

### P5【该拆未拆风险 / collar 第 6 消费者漏盘】build_workbench_plan_context（R54/R42 共改收口签名）有第 6 个调用方 scheduler_analysis_links.py:24，全图未登记，删 plan_id 形参(R42)时漏盘其调用方
- **问题**：R42 删 `build_workbench_plan_context` 的 plan_id 形参(:191) + dict 行(:233)，是「改收口函数签名」的动作。文档把 collar 的消费方列了 5 套手维面，但 collar 真实调用方 rg 出 **6 处生产代码**：resource_dispatch / dashboard / **analysis_links** / gantt_task_detail / navigation_context / reports_workbench（+ 多个 test）。其中 `web/routes/domains/scheduler/scheduler_analysis_links.py:24` 调用 collar，**全程未在任何簇/边/重灾区出现**。
- **证据（实盘 rg）**：`rg -l build_workbench_plan_context` 命中 analysis_links.py:24（`_plan_role_links` 内），它调 collar 但**不抄 guard 字段**（无 `_copy_plan_guard_fields`/`_PLAN_GUARD_FIELD_NAMES`），故不是第 6 套手维面——这点 R54「5 套」计数没错（澄清见 C1）。但它是 collar 签名的消费者：R42 删 plan_id 形参后，凡 analysis_links 是否传 plan_id 需确认。实盘 analysis_links:24 的调用**未传 plan_id**（kwargs 无 plan_id），故 R42 删形参对它安全——但这是核出来的结论，文档里没核过它就不知道。
- **为何是硬伤**：R42 改的是**收口函数签名**，删形参的安全性取决于**全部调用方**是否传该形参，不止 5 套手维面。漏一个调用方就可能 TypeError（若它恰好传了 plan_id=）。analysis_links 不在盘内 = 签名改动的影响面没盘全。
- **修正建议**：在 G01/G04 R42 改签名处补「collar 全调用方清单（含 analysis_links:24）已 rg 确认无一传 plan_id」一行作为删形参的前置自证；或把 analysis_links 列为 collar 签名变更的只读确认点。

### P6【拆分定性可疑但结论可接受 → 降级为提示】G02 把 R64/R65 标「逻辑零耦合、原子仅为防行号漂移」，但 R65 三件套删 import :4/:6 会大幅上移 R64 的 :66，反向行号耦合比文档承认的更强
- **问题**：G02 / C-NAV-PLANID AS-2 说 R64↔R65「逻辑零耦合，即使分提交也不会 NameError，原子仅为防行号二次漂移」，建议分提交则「R65 先、R64 后」。
- **证据（实盘）**：`scheduler_navigation_links.py` 中 R64 删 `_has_navigation_date_range`:66-67，R65 删 `_target_url`:74-78 + 删 import `urlencode`:4 + `query_for_target`:6 + 化简 :160。R65 删 :4/:6 两行 import → R64 的 :66 上移 2 行。文档自己也说这点，但定性为「软约束」。
- **为何只算提示不算硬伤**：逻辑零耦合的判断正确（`_has_navigation_date_range` 与 `_target_url`/import 确无符号交叉，实盘 :49 `_has_value` 留、:7 `TARGET_PAGE_PATHS` 留均已核），「按符号定位」的兜底也对。所以**结论（建议按符号定位、可分可合）成立**，只是「R65 先 R64 后」的软序理由表述可以更准（真正驱动顺序的是 import 删除的行号杠杆，不是 def 位置）。不构成执行风险。
- **修正建议**：保持 G02 拆分结论不变；若要精确，把内部顺序理由从「R65 在文件下半」改为「R65 删 :4/:6 import 上移幅度最大，故按符号定位优先于裸行号」。

---

## C1【澄清·不计入问题】R54「5 套手维面」计数经核**成立**，analysis_links 不是第 6 套
- 核查：`scheduler_analysis_links.py:24` 虽调 collar，但**不复制 guard 字段**（无 `_copy_plan_guard_fields`/`_PLAN_GUARD_FIELD_NAMES`/别名元组），是 benign passthrough，不是手维面。故 R54「5 套手维列表」基数正确，corrections 升级 3/4→5 套的结论站得住。
- L2≡L4（nav_publish ≡ dashboard，16 键逐字相同）经实盘确认，verify「L2/L4 逐字相同」成立。
- 这条只是为 P5 划清边界：analysis_links 是 collar 签名消费者（P5 范畴），不是 guard 手维面（不增 R54 计数）。

## 综合判断（簇拆并角度）
- **巨簇 C01（NAV-PLANID + NAV-GUARD + PLAN-IDENTITY 三簇 + 跨簇边）切分粒度大体正确**：AS-1{R42,R60} 同符号 co-change 强原子、AS-3{R66} 孤立、SEQ-NAV{R58→R54→R44} 同文件硬序——这些拆分都有实盘支撑，无误拆。
- **唯一系统性硬伤集中在 R54**：作为「一个原子单债」概念正确，但它是**跨 5 文件、3 种字段基数的承重失忆债**，而 DAG 的物理原子单元 G04 只锁住其中 1 套 + §3 重灾区漏登另 4 套文件 + collar 签名第 6 调用方漏盘。R54 的「跨文件原子性」没有被任何调度单元结构化钉死，正是该债最容易在拆批执行时漂移之处。


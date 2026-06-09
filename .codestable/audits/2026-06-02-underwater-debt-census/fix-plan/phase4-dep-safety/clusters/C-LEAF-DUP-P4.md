# 簇 C-LEAF-DUP-P4 — 原子簇依赖图重建

> 成员: R68 R69 R70 R03 R32 R40 R53 R61 LB04 R41 R43
> 主要文件: schedule_summary_degradation.py / schedule_execution_persistence_guard.py / schedule_service.py / schedule_candidate_runner.py / backup.py / material_repo.py / batch_order.py / report_context_filters.py / boolean_normalize.py / enum_display.py / scheduler_run.py
> 本簇是「干扰图重建」原子簇 agent 产物（只读）。行号均 rg 回盘（2026-06-05），不信旧 blast 值。

## A) 原子子簇

本簇名为 C-LEAF-DUP（叶子/逐字两份/P4 灵魂线），但实际成员互相之间**几乎全部物理解耦**——没有任何两个成员改同一物理文件。下面 11 个成员拆成 **9 个原子子簇**：3 个内部有强顺序门（R68 / R69 / R03），其余全是单成员独立原子单元。

### AS-1 · R68（`_meta_bool_state` 逐字两份收口）— 内部两步原子
- 成员: R68（独占 `summary/schedule_summary_degradation.py:123` + `summary/schedule_summary_downtime_degradation.py:30`，收口家 `summary/summary_count_parse.py`，rg 回盘均零漂移）。
- 原子原因: 两份逐字 def + 收口同时改回归网，是一个 PR 内不可拆的「parity 先于收敛」单元。
- 内部顺序（强制）: **① 先建 parity 测试（Batch-1 ROOT）→ ② 后删两份、提升单份到 `summary_count_parse.py`（Batch-15）**。倒序失回归网。
- 灵魂线红区: parity 测试与收口都**严禁压扁 `(bool, parse_failed)` 二元组**为单 bool；坏 meta 的 `return bool(default), True`（degradation.py:132/139/140、downtime:39/46/47）必须保 loud（保 `parse_failed` 位）。
- 与 R69/R70 仅同批 B15、不同文件，排程时确认追加到收口模块的 def 名不撞（已核：R69 收 `_op_seq`→`schedule_input_contracts.py`，R70 纯删，均不碰 `summary_count_parse.py`），无技术先后。

### AS-2 · R69（`_op_seq` 两份收口单点 + 坏 seq 改 loud）— 内部两步原子
- 成员: R69（独占 `run/schedule_execution_persistence_guard.py:49` + `run/schedule_input_runtime_support.py:19`，收口家已存在点 `run/schedule_input_contracts.py`）。
- 原子原因: 收口单点 + 坏 seq 由静默 `return 0` 改 loud + 护栏文件回归网，同一 PR。
- 内部顺序（强制）: **① 先建坏-seq loud/可观测 护栏测试 + 单点 import 契约测试 → ② 后提升 `_op_seq`、两文件改 import、except 改 loud**。
- 行号回盘（必须用，blast `:143/:149` 已过期 +63）: 消费者 **`persistence_guard.py:206`（`completed_seq=_op_seq(completed_op)`）+ `:212`（revision 过滤）**、`runtime_support.py:216`。
- 灵魂线红区: 护栏文件内坏 seq **严禁保留 `except (TypeError,ValueError): return 0` 静默归 0**——P4 改 loud raise 或补可观测降级标记（owner 设计前置裁 loud 方向）。
- owner_pending=false，但收口家落点 + loud 方向是 owner 设计前置（registry hint），排 Batch-15 第三落（R70/R68 之后，非技术阻塞）。

### AS-3 · R70（死副本纯删）— 单成员独立
- 成员: R70（**2026-06-08 已 fixed**；已纯删旧 `schedule_service.py:46-50` 死副本）。
- 原子原因: 单文件单点纯删，零前置零收口。
- 关键纠偏: twin 框架**不成立**——live 唯一在 `run/schedule_input_collector.py:79`（注意 `run/` 子目录，顶层同名壳无此符号），死副本零调用。**不动 live 一字**。
- 禁区（删时严禁碰）: `schedule_service.py` 的 `ValidationError` import（并发拒绝路径仍用，删则 NameError）。
- Batch-15 本桶最先落（零前置零风险），已完成。

### AS-4 · R03（候选 FAILED 态承重护栏 + 下游脚手架）— 内部两段拆分
- 成员: R03（独占 `run/schedule_candidate_runner.py`，B14 独占文件，ISOLATED）。owner_pending=true。
- 原子原因: 同债内承重段(A)与 owner_pending 下游段(B)必须拆批，不能同 PR。
- 内部顺序: **(A) 承重注释段** 随 Batch-1 ROOT 立即落（`runner.py:216` 上方补「我是故意的」三行注释，逻辑零改）；**(B) 下游 FAILED 脚手架** owner 裁断 `ScheduleCandidate.status` 枚举契约后才动，LATE，本轮不分配批次。
- 承重禁区（绝不动）: `:28` class CandidateTrialFailure 基类、`:216` `except CandidateTrialFailure`（禁改回 except Exception/禁扩面/禁删）、`:217` `return _failed_plan(...)`（禁透传）。
- **missing 态可达性铁律**（corrections §A）: `_baseline_missing_or_failed:267 return True` 使 **missing 态生产可达**（rg 确认 `:267 return True`），只 failed 半支不可达。(B) 段若清理须 **None/missing/failed/completed 四态 parity**，missing 态保留+补不可达注释，owner 裁 failed 态——**禁裸删 dashboard_workbench.py:156**（会静默吞 baseline 缺失告警）。

### AS-5 · R32（backup 完整性校验 except→raise）— 单成员独立
- 成员: R32（独占 `core/infrastructure/backup.py`，rg 确认 `integrity_check :334` / 病灶 `except Exception as e: :335` / `os.replace :343`）。owner_pending=true。
- 原子原因: 单文件单 except 块改 raise + 新建契约测试，同 PR；ISOLATED，`same_file_siblings=[]`。
- P4 修法: :335-337 由「warning 后落 :343 os.replace 升正式」改 loud raise（跑不起 integrity 的库不算可信备份）。owner 裁「硬 raise vs 可观测降级」后锁终态/分批。
- 禁区: `:338-342` else 分支 raise 不得改弱、`:343` os.replace 不得加二次兜底、`:346-352` finally 清理保留。
- 非阻塞 precondition: `system_backup.py:108` 仅 catch MaintenanceWindowError，R32 的 RuntimeError 会落裸 500，可同改可后补。

### AS-6 · R40（material_repo 库存 except→raise）— 单成员独立
- 成员: R40（独占 `data/repositories/material_repo.py`，rg 确认 `val=float(val) :69` / 病灶 `except Exception: :70` / 静默保留 `val=updates.get :72`）。owner_pending=true。
- 原子原因: 单文件单 except 块改 raise，ISOLATED，`same_file_siblings=[]`。
- P4 修法: 删 :70-72 让 :69 自然抛 ValueError（方向 A，零 import 零越层）+ 「我是故意的」注释；方向 B 引 core.ValidationError 会造 data→core.infrastructure 错误耦合（不推荐）。owner 裁错误分类。
- 禁区: **只删 :70-72，必保 :69 的 float 转换**（误连删则坏值仍落 REAL 列退化）。生产路径不可达（service 层 `_norm_float` 已拦），改 raise 零行为影响。

### AS-7 · R53（死空操作面包屑直删）— 单成员独立
- 成员: R53（**2026-06-08 已 fixed**；已纯删旧 `core/algorithms/greedy/dispatch/batch_order.py:74` 一行 `_ = scheduled_count`）。owner_pending=false。
- 原子原因: 单行纯删，ISOLATED，无 unused-arg 复发（:58 仍真用 `scheduled_count`）。
- 禁区（正确性，非承重）: 现盘 :39 形参 / :58 真消费 / :74 return（旧 :75），误删均被契约测试 `test_greedy_refactor_contract.py` 响亮拦截。
- 终态验证: `tests/algorithm/test_greedy_refactor_contract.py` + `tests/algorithm/test_greedy_scheduler_base_date.py` 共 28 passed；`sgs.py:127` 同形态行非本债未动。

### AS-8 · R61（出生即死死簇直删 + 测试重定向）— 单成员独立（已 fixed）
- 成员: R61（**2026-06-08 已 fixed**；已独占清理 `core/services/report/report_context_filters.py` 死簇）。owner_pending=false。
- 原子原因: 删死簇 **必须**与改测试同一提交（否则中间态 CI 红）——这是「同 PR 原子」不是「前置债」。
- 删除范围（rg 回盘）: 旧 `filter_plan_rows_for_report_context:172-187` + `_plan_row_matches_batch:160-161` + `_plan_row_matches_resource:164-169` 已删除。
- 严格保留孪生/共享: **`filter_downtime_rows_for_report_context:244`（report_engine.py:406 live）、`_row_text:156`（downtime live :191/:209/:223）、`normalize_report_resource_filter:119`（本文件 :252 + report_engine/web 多处 live）一个字节不动**。
- 测试: import 已删 plan 死函数；两条负向测试已**重定向**断言体到 `normalize_report_resource_filter`（零覆盖损失），downtime 四测/normalize 直测/request 层测保留。
- 簇 C01 但 interference_edges（LB02/LB05/R14）均指向 `report_engine.py`（他文件），本删除不触 report_engine 一字，无跨债行号约束。

### AS-9 · LB04（`normalize_yes_no_wide` 双实现承重）— 单成员独立纯增量
- 成员: LB04（承重 load_bearing=true，债主体 `core/shared/boolean_normalize.py:33`，对照实现 `normalization_matrix.py:168`，shim `enum_normalizers.py:172`，rg 三处全命中零漂移）。owner_pending=false。
- 原子原因: 注释 + parity 契约测试是纯增量安全网，单 PR，零结构改。
- 承重唯一合法动作: **`boolean_normalize.py:33` def 上方补「我是故意的」注释 + 新建 `tests/regression_boolean_normalize_wide_parity_contract.py`**（全 wide 别名 × 是/否/None/空串/未知 × 4 unknown_policy 矩阵逐格同值）。
- 唯一合法消重方向（本批不执行）: 上层 matrix 反向 delegate 到下层 boolean_normalize（services→shared 合法下行）。**绝对禁删 shared 改指 services**（造 models↔services 环 + 越层）。
- core.algorithms 当前零消费（rg 实证），注释里 algorithms 论据须标「前瞻」防误删。Batch-1 ROOT，作为所有 yes/no 收敛动作的安全网前置。

### AS-10 · R41（enum 中文标签收口 enum_normalizers + 测试改 loud）— 单成员独立
- 成员: R41（独占 `web/routes/enum_display.py`（6 个 `*_zh`，rg 命中 13/24/33/47/62/73）+ `process_bp.py` `_source_zh`）。owner_pending=true。
- 原子原因: 收口 + 钉死测试改 loud 同 PR；但 owner 须先裁 4 处语义。
- 收口点（已存在，不新建）: machine_status_label:124 / batch_priority_label:209 / ready_status_label:220 / calendar_day_type_label:231 / operator_status_label:82 / source_type_label:159。**`batch_status_zh` 无 canonical 收口点 → 保留不收口**（强建 batch_status_label = 新 P5，禁）。
- owner 裁 4 语义（硬门控）: ready 空串「未齐套↔齐套」反转、operator「停用/休假」→「停用」、day_type/priority/operator 空串「-」→label 默认值、_source_zh 外协误判修复。
- 灵魂线: 收口包装**禁 try/except 吞错/禁兜底**；ready/source 未知值走 `unknown_policy="passthrough"` 暴露，**禁贴回确定态**；`test_enum_display_consistency.py:59/60/61` 改 loud 暴露**禁删了重钉静默**。
- 排 Batch-1（LB04 安全网）之后，registry hint Batch-5。

### AS-11 · R43（顶层 9 wrapper 别名残渣删除）— 单成员独立（删模块+迁测试同 PR 原子）
- 成员: R43（整组 9 wrapper + compat，主文件 `web/routes/scheduler_run.py`，桶 B13）。owner_pending=true。
- 原子原因: 删 wrapper 必须与迁/删测试同 PR（中间态 CI 红）；流程前置 = owner 认账 roadmap 延期决定。
- **roadmap 延期行 = `:522`**（rg 实测「先保留旧 wrapper…」在 522；corrections §F 已纠 dossier 把 522 反向污染成 521，以 522 为准）。
- 迁移面（registry「15」低估）: **22 文件**（19 plain import-rewrite + 3 契约：wrapper_import_order_contract 整删、route_registration_contract:88 改、sp05 三 ROUTE 表改）。
- 灵魂线: 删 wrapper 同时清 `domains/scheduler/scheduler_config.py:95` 的 `sys.modules.get` 软 fallback（删后永 None，退化单路）。
- registry hint Batch-14（全局最晚），owner_pending 不锁批次。

## B) 跨簇边（本簇成员 → 其他簇债）

本簇成员物理上高度孤立，跨簇边集中在 **R41 / R43**（web 表现层的下游消费者文件互撞）与 **R69**（新增收口边）。逐条：

| 边 | 本簇成员 | 指向（他簇债） | 关系类型 | 说明 |
|---|---|---|---|---|
| E1 | **R43** → R26 | 同文件同改 + 收口前置 | **强串行** | 共碰 `scheduler_config.py`（顶层 wrapper）+ `test_sp05_path_topology_contract.py`。R26 收 config/summary shim 若先落，R43 删时以 R26 残留集为准。建议 R26 先或合批改 SP05。 |
| E2 | **R43** → R01 | 同文件同改（parity 弱） | **二选一串行** | 共改 `test_sp05_path_topology_contract.py`。R43 删表项致后续行号上移，R01 若绝对行号锚定会漂。串行或合批。 |
| E3 | **R43** → R41 | 承重/行为先于动同文件 | **条件串行** | 共碰 `scheduler_batches.py`。R41 若「改 batches 行为」须先在 domains 叶子完成，R43 才能删顶层别名；R41 若也删别名类可合批。 |
| E4 | **R41** → R37 | 同文件同改（diff 排序） | **弱串行** | 共享下游消费者 `equipment_pages.py`。R37 删死方法、R41 改 import 源，函数体不交叠，按文件粒度排序避免 diff 冲突。 |
| E5 | **R41** → LB04 | 收口前置（同收口点文件 enum_normalizers.py） | **时序：R41 在 LB04 之后** | R41 大批新增对 `enum_normalizers.py` 的调用，必须等 LB04 承重护栏 + parity 安全网先就位（Batch-1）。改的符号不重叠（LB04=yes_no_wide，R41=*_label），fix_invalidation_risk=none，仅护栏先行。**LB04 在本簇，故此边为簇内时序门，见 D 节。** |
| E6 | **R69** → R18/R15 等 run/ 包债 | 新增收口边（无环已核） | **无前置** | R69 新增 `persistence_guard → schedule_input_contracts` import 边（同 run/ 包，已 rg 核 contracts 无回指，无环）。收口家 `schedule_input_contracts.py` 当前无其他债收口 `_op_seq`，无同收口点竞争。 |
| E7 | **R03** → owner（ScheduleCandidate.status 枚举契约） | parity 先于收敛 | **LATE，跨债裁断** | (B) 段牵动已落库 status 枚举契约（completed/failed/skipped/not_run），是 owner 全局裁断点，非本簇内可解。 |
| E8 | **R32** → R40（同桶 B16 P4 对） | co_change 同批，不同文件 | **可并行** | R32/R40 同为 P4 灵魂线对，但不同文件、互不影响，无技术先后。 |

注: **R68/R70/R53/R61 对外零跨簇边**（各自 ISOLATED，物理独占文件，无他簇债共载体；其中 R53/R61/R70 已 fixed）。R32↔R15 的 registry same_symbol 边是**假边**（见 C 节，删除）。

## C) 相对旧 146 边的变化（删 / 新 / 降）

### 删除（假边 / 已修，逐条）
- **删 R32↔R15**（corrections B 节假边）: registry same_symbol `sym:replace` 边。回盘实证：R32 的 `os.replace` 在 `backup.py:343`（os 模块）；R15 实为 datetime P5 债，其 `replace` 是 `execution_fact_provider.py:89` 的 **str.replace**（文本归一化）——同名异物，纯假边。删边。（注：R32 dossier §6 误把 R15 定位到 `migration_backup.py:56`，论据错结论对，二者本就零耦合。）
- **删 LB04↔LB07**、**删 LB04↔R33**（corrections B 节假边）: registry 标 `same_file:schedule_config_runtime_coercion.py`，但回盘 LB04 主文件是 `boolean_normalize.py`，LB07 实为 `schedule_config_runtime_snapshot.py`、R33 实为 `compat_parse.py`，并非同驻；且 core/algorithms 经 number_utils 引用为假（rg algorithms 零消费）。删边。
- **删 R43↔R26 的 config_snapshot 假碰撞维度**（corrections B 节）: `config_snapshot.py` R26↔R71 顶层 shim vs 深实现是已知假碰撞；但 R43↔R26 经 `scheduler_config.py`(顶层 wrapper)+SP05 的边**真实保留**（见 E1）。仅剔除 config_snapshot 这一假碰撞维度。
- **降级确认（已 fixed 前置）**: LB06/R56/R57/R07/R16/LB03 已 fixed（见 E 节），本簇内 LB04 的 Batch-1 安全网与它们同批但互不改同行段——这些 fixed 项不再作为本簇的活动边，仅作前置已完成态。

### 新增 / 修正（行号漂移导致的边重定位，非新逻辑边）
- **新增 R69 收口边 `persistence_guard → schedule_input_contracts`**（E6）: 旧图无此边（收口家是本轮才选定的已存在点），新增、已核无环。
- **修正 R69 消费者行号**: 旧 blast `:143/:149` → 回盘 `:206/:212`（+63 行，persistence_guard 被 resource-dispatch 工作下移）。边端点重定位，非新边。
- **修正 R03 下游消费者行号**: 旧 registry workbench `:231/:207` → 回盘 `dashboard_workbench.py:156`；helpers `:324/:329` → `:360/:365`。边端点重定位。
- **修正 R43 迁移面**: 旧「15 文件」→ 回盘 **22 文件**（19 plain + 3 契约），E1/E2/E3 串行边强度据此上调。

### 降级
- **R41↔R37 / R41↔R43 由「同文件硬冲突」降为「diff 排序弱串行」**（E3/E4）: 经回盘三者改的是**不同函数体**（R37 删死方法、R41 改 import 源、R43 删别名），非同符号同行，降为「按文件粒度排序减 diff 冲突」的弱边。
- **R41↔LB04 由「同收口点竞争」降为「护栏时序门」**（E5）: 二者收口符号不重叠（yes_no_wide vs *_label），fix_invalidation_risk=none，仅 R41 须排 LB04 安全网之后，非内容冲突。

## D) 承重前置（簇内 LB/N1/N2/R03/R58 注释·parity 是否必须先落 + 门控的禁区行）

本簇有 **2 个承重点**：**LB04**（load_bearing=true）与 **R03 (A) 段**（load_bearing 字段 false 但 `lb_no_touch` 非空，按铁律 3 当承重处理）。二者的承重注释 + parity 网必须**先落（Batch-1 ROOT）**，门控簇内的结构动作：

### 承重门 1 · LB04（Batch-1 必须先落）
- **必落前置**: ① `boolean_normalize.py:33` def 上方补「我是故意的」注释；② 新建 `tests/regression_boolean_normalize_wide_parity_contract.py` parity 安全网。
- **门控**: **R41 收口（AS-10）必须等本门落地后**才能大批接入 `enum_normalizers.py`（E5）。任何针对 yes/no 归一的收敛/删除动作都须等此 parity 网先就位。
- **禁区行（绝不触，仅注释+测试）**: `boolean_normalize.py:5-8`（别名常量）、`:33-62`（函数体，禁删/禁改语义/禁改返回字面量/禁改 policy 默认）、`normalization_matrix.py:168-195`（对照实现，禁单边改）。**绝对禁删 shared 改指 services**（造 models↔services 环 + 越层，击穿 R29 分层前提）。

### 承重门 2 · R03 (A) 段（Batch-1 必须先落）
- **必落前置**: `runner.py:216` 上方补三行「我是故意的」中文注释（钉 b81f8b3f narrow-except 护栏，逻辑零改）。契约 `runner_contract.py:473/486/488` 已测试形式钉死意图，注释是唯一源码缺口。
- **门控**: R03 (B) 下游脚手架清理**必须等 (A) 注释 + owner 枚举裁断**，且 (B) 推进时**不得连带改 (A) 的三禁区行**。
- **禁区行（绝不触）**: `runner.py:28`（class CandidateTrialFailure 基类）、`:216`（`except CandidateTrialFailure`，禁改回 except Exception/禁扩面/禁删）、`:217`（`return _failed_plan`，禁透传）。
- **missing 态四态 parity 门**: (B) 段任何清理前必须先有 None/missing/failed/completed 四态 parity（`_baseline_missing_or_failed:267 return True` 使 missing 可达），**禁裸删 `dashboard_workbench.py:156`**。

### 非承重但「正确性禁区」（不门控批次，删时勿碰）
- R70: 2026-06-08 已 fixed；仍保 `schedule_service.py` 的 `ValidationError` import（并发拒绝路径仍用）。
- R40: `material_repo.py:69` float 转换（只删 :70-72）。
- R53: `batch_order.py:39/:58/:74`（形参/真消费/return；旧 return :75 已因删 no-op 上移）。
- R61: 2026-06-08 已 fixed；当前仍禁删 `_row_text` / `normalize_report_resource_filter` / `filter_downtime_*`（live 孪生/共享，已在执行后复核保留）。
- R69: 护栏文件 except 改 loud 属灵魂线（非承重禁区），可正常改 except→loud，不受「仅注释」限制。

### 灵魂线前置（P4 改 loud / 不留静默）
R69（坏 seq→loud）、R32（integrity except→raise）、R40（float except→raise）、R41（未知值 passthrough 暴露）、R43（清 scheduler_config.py:95 软 fallback）——均**禁新增兜底/静默回退**；R32/R40/R41/R03(B) owner_pending=true，待裁前不锁终态/不分批。

## E) fixed 成员残留动作

本簇成员中 **R53、R61、R70 已在 2026-06-08 fixed**；R68/R69/R03/R32/R40/LB04/R41/R43 仍按各自状态推进。fixed 项（LB06/R56/R57/R07/R16/LB03）作为 **DAG 前置已完成**，与本簇的交集仅为：
- **LB03/LB06** 与 LB04 同属 Batch-1 承重注释网，但改不同文件、不同行段，互不阻塞。残留动作（他簇）: LB03 缺认账注释（勿粘 §90 LB-B4 反向文案，现盘已 fail-CLOSED）、LB06 缺认账注释。**不在本簇 owner 范围**，仅记录为前置已完成。
- **R56**（fixed，偏离铁律 3 走结构路线删字面量匹配）、**R07**（fixed，偏离错误类）需 owner 认账偏离——他簇残留，本簇无依赖。

本簇内 **R53/R70 fixed 只需保留终态登记，无承重认账注释**；承重认账注释（LB04 / R03-A）曾属本簇未落的 planned 动作——**2026-06-10 补登：均已落地**（LB04 注释+锁步矩阵随 fae8829b(2026-06-08) 落、第二/三句于 2026-06-10 补全并翻 fixed；R03-A 三行护栏注释 2026-06-10 按 dossier 草稿落地，R03 整体因 (B) 段留 planned）。

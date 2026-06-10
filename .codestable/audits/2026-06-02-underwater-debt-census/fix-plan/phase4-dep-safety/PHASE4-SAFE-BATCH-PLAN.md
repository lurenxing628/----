# PHASE4 · 80 条水下语义债 — 修复前依赖分析与安全批次计划

> 装配主笔产物（只读不改任何 .py）。HEAD 基线 c2aa7501（部分回炉裁定基线 b08162cd，已在对应处标注）。⚠️ 2026-06-08 注：c2aa7501 仅为**分析快照基线**；A（test-gate-cleanup P0–P7）收官后 B 的**真实漂移基线 = `3f8f7c5f`**（B 产物入库定稿点），详见下方「2026-06-08 A 收官增量」条。
> **✅ 2026-06-05 状态更新：§3 全部 38 条 owner 闸门已逐条裁定**（裁决与落地要点见同目录 `OWNER-DECISIONS-2026-06-05.md`；其中 O23 改裁保留、O26 裁第三选项 C 全收口、O08 随 O07 消解）。裁定单元现可锁 patch、按 §1 批次序列进执行；下文铁律 5 的「待裁」约束对已裁单元解除。
> **⚠️ 2026-06-05 晚增量：产物入库时另有 3 个门禁修复提交触碰债务锚点**——R09 家 tokens 副本已搬至 `core/models/`（路径级漂移）、LB02/LB05 宿主行号整体上移 ~17。执行前必读同目录 `ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md`（结论：38 裁定与批次序全部不变）。
> **✅ 2026-06-08 A 收官增量（test-gate-cleanup P0–P7 全部完成，B 启动前必读）**：A 阶段在 `tests/+tools/` 工作面收官（P1 删 35 个 DROP 死代码测试 / P3 197 个 main-style→pytest 全清零 / P5 业务合并+剪脆性尾 123 文件 / P6 迁 562 测试文件入 `tests/<模块>/` 子目录并去 `regression_` 前缀 / P7 防回潮门禁）。
> - **生产锚点零漂移**：`git diff 3f8f7c5f..HEAD -- core/ data/ web/ desktop/ plugins/ app.py config.py` 为空，A 生产代码零改动 → 本计划全部承重 / 收口 / 灵魂线 / facade 生产锚点**逐字幸存**，dossier 生产行号仍有效（仍按铁律 1 重 rg 校准）。
> - **测试路径锚点已机械对齐**：B 全部 `tests/` 锚点经 P6 重映射（旧 `tests/regression_X.py` → `tests/<模块>/test_X.py`，含 `_guardrail→_guard` 等少量词干缩写）。本计划 + 76 dossiers + `_registry.json` 已用 `.codestable/refactors/2026-06-01-test-gate-cleanup/p6_path_map.csv`（561 行 old→new）经同目录 `remap_b_anchors.py` 一次性替换完成（IN_CSV 残留 0）；**6 个被 P1 删 / P5 合并的文件不在映射表**（`sp06_no_duplicate_defs` / `scheduler_candidate_py38_contract` / `aps_workbench_flow_contract` / `scheduler_workbench_link_guardrails` / `boolean_normalize_wide_parity_contract` / `gantt_critical_chain_normalize_parity`），已在相关 dossier 就地标注终态（no-op / 重指合并目标）。
> - **两个新机制 B 必须感知**：① **P7 防回潮门禁**（full gate 第 17 步，base-ref d4589d77）—— 约束见下「ROOT · 门禁总纲」+ `_B_COMPAT_SAFEGUARDS.md`；② **P4 xdist 并行**（daily gate）—— B 自建 oracle 默认落并行面，约束见 `_B_COMPAT_SAFEGUARDS.md`「P4 并行机制对 B 的约束」节。
> - **A 收官不变量**：collect **3751** / required **1796** / serial **770**（删 R51 两续命测试后 collect→3749，见 R51 条）。
> 本计划的价值不是「怎么修」，而是「按什么顺序修、哪些必须一起改、哪些碰都不能碰、每批修完怎么验证没炸」。
> 输入：_interference_rebuilt.md（42 原子簇 + 13 H 硬边 + ROOT/A/B/C/D 草案）、_layer3_explosion.md（11 标红债 + 6 硬阻断新爆点 + 12 簇 go-no-go + 23 新爆点）、redteam/verdict_V1..V5.md（12 回炉争议已拍定）、_layer1_corrections.md + _layer2_residual.md、dossiers/{id}.md ×73。
>
> **全文执行纪律（贯穿所有批次，逐批不再重复）**：
> 1. **所有 file:line 须按符号重 rg 回盘**——本档所有行号是 2026-06-05 簇内实盘值，但删改会位移，动手前对每个锚点用符号名（非裸行号）重 rg；权威路径以 _layer2_residual.md §权威真实路径表为准（含 4 处前缀订正：schedule_repo.py / part_repo 等在 `data/repositories/` 无 core/ 前缀；nav_publish 在 `web/routes/domains/scheduler/`）。
> 2. **承重只补注释 + 绑契约/parity，绝不删/统一/透传**。
> 3. **灵魂线不新增兜底；P4 改 loud raise 或补可观测；P5 收口到已存在点（绝不新建模块）**。
> 4. **分层 0 违规**（禁 core→flask、禁 model→data、禁 data→core 反向 import 造环）。
> 5. **owner_pending 债只列「待裁」，绝不给终态修法、绝不分配执行批次**。（✅2026-06-05：38 闸门已全部裁定，本条对已裁单元解除——见 §3 裁定列与 `OWNER-DECISIONS-2026-06-05.md`。）
> 6. **绝不静默截断**——任何简化/合并/折算处理在文中显式 log 标注「⚠简化声明」。

---

## 0. 总纲

### 0.1 脊梁（执行哲学，四步骨架）

整个 80 债清理（净化后 73 债 → 42 原子簇 G01–G42 + GF1 共享前置门；其中 **G02={R64,R65} NAV-PLANID** 由红队 RT3-P01 补登，落 Batch-A 死叶子，恢复 G02 标签后 roster 与「42 原子簇 G01–G42」算术自洽，见 §1.0/§1.2）的安全顺序由一条脊梁支配，**任何批次内的任何动作都从属于它**：

1. **承重先钉**——所有 load_bearing 点（LB01/LB02/LB05/LB07/LB08/LB03/R03-A/R05-step1/R22-parity/N1/N2）先以「我是故意的」注释 + 绑契约/parity 钉死，再谈任何删改。承重注释是 13 条 H 硬边的共同 source（零入边纯 source），构成 ROOT 批。**注释写错方向（fail-CLOSED 写成 fail-OPEN）比漏边更危险**（见 §3.2 方向硬门）。
2. **guard 真相源收口**——所有 P5 收口动作只许收口到「已存在」的真相源符号（绝不新建模块）：R09→`operation_execution_scope.py:9 parse_positive_execution_int`、R54 五套手维面→`PlanIdentity.to_dict` + view_context `plan_role_filter_fields`/`default_plan_resolution_dict`、R41 5 族→`enum_normalizers.py` 已存在 *_label、R69→`schedule_input_contracts.py`、R11/R63→单份 `_normalize`。收口前先把真相源**扩成产出点**（R54 的 collar 扩 3 键、R05 的 collar 扩 team 谓词），扩产是独立承重前置改动，须过 owner 审。
3. **SCC 按文件原子串行**——同物理文件被 ≥2 债命中（24 重灾区文件）时，按符号自下而上、或按显式硬序（如 EXEC-FACT provider 链 R15→R19→R13、PARSE-INT R01→R04、dispatch_rules R49→R51→R50、CONFIG facade R33→R30/R31）一次原子提交或显式串行 + 逐步重 rg；中间提交允许红（如 R01 删函数 + 删 SP05 断言必须同提交，否则中间态必红）。
4. **facade 最晚**——所有 re-export 壳 / 顶层 shim 的删除（G18/R26、G23/R33、G16/R45≡R48（⚠ **零生产下游例外且已 fixed**：唯一旧测试路径已由 A P1.1 删除，退 sp06 为 no-op，故实际归 **Batch-A 早删、非 Batch-D**）、G17/R31、G37/R02（⚠ **test-only 例外**：生产零下游消费者，其「下游收敛」= 同步改 1 处测试 import、在 Batch-A 自带完成 → 故实际归 **Batch-A 早删、非 Batch-D**；见 §1.1 Batch-A 成员清单 + G37「先拆测试 import 再删壳」前置安全网，及 dossier R02.md 字段 8 生产零消费证据）、R29 薄壳化）排在所有「下游收敛」之后；R26（G18）是全局最晚批（Batch-D），须晚于 R29/R33/R52 三桶收敛（E07/E08/E09 硬前置）。

> **脊梁的失败模式（为什么是这个顺序）**：颠倒任一步即静默炸——承重不先钉则后续删改打穿消毒/护栏（LB01↔R17 同 `_build_event_payload`）；收口不先扩产则裸 delegate 抹键 fail-OPEN（R54 collar 不产 3 键时「5 套 delegate」=直接脏写历史现场，爆点 #1）；SCC 不串行则行号互撞致 Edit old_string 失配 + 半截残骸；facade 不最晚则先删壳致下游 ImportError（loud，但延迟暴露——R26 的 2 离线消费者 CI 不跑）。

### 0.2 与旧 MASTER-PLAN 的关系（继承 + 本轮校正声明）

本计划**继承**旧 MASTER-PLAN 的核心约束体系（承重只补注释、灵魂线不新增兜底、P5 收口已存在点、分层 0 违规、parity 先于收敛），并在其上做 6 类**本轮校正**（全部经 dossier + 第二双眼睛 verify 双核 + 红队 3 轮 + 5 份回炉裁定确认；逐条映射见 §5）：

- **C1 修法被实质推翻**：R09 收口点已存在（作废「新建 parse_optional_positive_int」批，O01/O02 已裁为只收编 A/B 两副本 + 双路 parity）；R34 纯删（O10 已裁，repoint 目标 `get_plan_time_span_for_resolution` 存在，旧锚 :210、R23 后现盘 :206，执行按符号重 rg，非「收敛重构」）；R13 解耦 R18（O06 已裁先迁 3 测试后删，2026-06-10 owner 已确认并 fixed）；R18 stub raise 是契约护栏非死码；R17 改删 `:81` 推导式项（非旧 `:64`）；R15 收口去 `parse_operation_event_time`（非 strict_parse）；R03 四态 parity（missing 态 `:267` 生产可达，非全死分支）；R44 方向反转（core 更防御，非「web 多兜底」）。
- **C2 干扰图净化**：旧 146 边 → 删 **29**（假边 22 + 已修对消 5 + **方向并 2**）+ 新 19（含红队 E28/E29 同文件承重毗邻）+ 降 18 = 重建 **~136 边**，跨簇有效约束边 29 条（H 13/S 14/P 2），真门控分层硬边仅 **13 条 H 边**，全图无环（环成员=空）。〔权威 `_layer2_residual.md:9`：删 29/重建 ~136；旧文「删 27/~138」漏算「方向并 2」已订正。〕
- **C3 R54 升 5 套手维面**：非旧报告 3 套 / registry 4 套；跨 5 物理文件 + 3 种字段基数（L2/L4=16 键、L3=15 键缺 plan_role_status、L1=12 键缺三阻断态 + 别名源键、L5 别名元组）；**禁统一键名**（分三组基数各钉 parity，禁向 16 键看齐 = 统一改行为违承重红线）。
- **C4 新引入债 N1/N2 + R56 入 fixed**：执行重构新增 N1（can_write_feedback 失忆债，门控 R08 删死分支）/ N2（`_event_id_for_revision` return 0 sentinel）补注释 + 绑契约；R56 走高风险结构路线（违铁律 3）已入 fixed，退化为 R42 删 plan_id 的**禁区行**（`:79` plan_role 强制 adopted）+ owner 认账偏离。
- **C5 R29 误标纠回 planned**：权威 CSV 整目录 ABSENT，number_utils 仍全量 delegation-facade、4 兄弟全薄壳；**重新入排后 O20 已裁 KEEP+注释**，并因此把 E07 纠成 **R29/G26 先闭合、R26/G18 后删 facade**（KEEP 注释即闭合）。
- **C6 批次结构收缩**：旧 16 批因含已推翻/已完成占位（新建模块、R13+R18 同原子、R34 收敛重构、R56 承重待做）；重建为 **ROOT + 4 大批（A/B/C/D）**，原 owner_pending 单元已按 OWNER-DECISIONS 裁后口径分流到对应批次。

### 0.3 本计划覆盖的硬清单（一条都不许丢，逐条在批次中出现）

- **11 条标红债**（多轮多透镜多数红）：R09 / R15 / R19 / R52 / R14 / R69 / R54 / R04 / R42 / R22 / R05。每条在 §2 有专项处置，并在对应批次的「前置安全网」或「owner 闸门」逐条出现。
- **6 个硬阻断新爆点**（照 cluster/dossier 直接执行即炸）：#1 collar 不产 3 键（R54）、#7 R15 空值即 raise、#19 R05 team 谓词 builder 耦合 + #20 R05 双轨共用收口点、#21 R42 dashboard_workbench_context.py:92 漏删点、#22 R22 no_history 取值翻转 + #23 R22 删 view_context:74 破 bad-role raise。每条在 Layer4 出批次前逐条闭合（见对应批次前置安全网 / owner 闸门）。
- **6 承重文件全标禁区**：operation_execution_feedback_service.py（LB01）、execution_review.py（LB02/LB05）、scheduler_navigation_publish.py + navigation_context.py（LB06/R56 + R58）、config_snapshot/coercion 双栈（LB07）、scheduler_public_errors.py（LB08）、schedule_plan_identity_builder.py（LB03）、**operation_execution_scope.py（R09 收口家 + LB01 最终底同住）**。〔**计数说明（一致性 P2 收口）**：行内列出 7 个 .py basename，但 **scheduler_navigation_publish.py 与 navigation_context.py 同属 LB06/R56 一个承重槽，算 1 个承重点**（参 `_layer2_residual.md:25`），加上 LB01/LB02-LB05/LB07/LB08/LB03/operation_execution_scope = **6 个承重点**；config 双栈（config_snapshot + coercion）同理算 1 个 LB07 槽（占多 .py）。「6 承重」与「7 basename」无矛盾。〕
- **STRICT-4 一字不碰**：`scope.py:9` + `feedback_support:161`（真 loud raise）；`public_errors:167` + `auto_assign:114`（V1⑥裁定：实为 `except: return 0` →0 哨兵，分类失真，禁区注释须纠偏，禁收口当「→raise/写入闸门」）。
- **Optional-5 收编面**：viewmodel:33（B 副本）+ service:24（A 副本，含调用点 :169/:180/:181）已认；persistence_errors:13（第 3 份，V1⑤/O02 裁定归 R04 禁区不归 R09 收编面，保持现状 + 注释）。

---

## 1. 批次序列

<!-- ANCHOR-SEC1 -->

### 1.0 序列总览

**批次总数：5（ROOT + Batch-A/B/C/D）**，以 42 原子调度单元（G01–G42）+ GF1 共享前置门为粒度，尊重 13 条 H 硬边 + Layer3 强制前置编排。

> **G02 标签归位说明（一致性 P1 收口）**：权威源 `_interference_rebuilt.md:17` 定义 **G02={R64,R65} NAV-PLANID**（且 :61 列入「多债强原子 20 个」）。R64/R65 经红队 RT3-P01 补登入 Batch-A，下方序列与 §1.2 成员清单以 **G02(R64+R65)** 标签登记，使「42 原子簇 G01–G42」在 roster 内算术成立（41 个独立 G 号 + G02 = 42，外加 GF1 前置门）。R64/R65 同文件同原子提交但改点不同、不可同质化（见 §1.2）。

```
ROOT  承重注释 + 共享前置门（纯增量零结构，零入边，最先落）
  GF1·reject_integer_float 默认 False+parity🟢 fixed(fae8829b) ┃ G15a·LB07 双栈注释+spec_sync parity🟢 fixed(fae8829b)
  G07a·LB01 两处注释🟢 fixed ┃ G05·LB02/LB05 注释+回归🟢 fixed(fae8829b) ┃ G40a·LB08 注释+绑契约🟢 fixed
  G33a·R05 步1 扩collar+步2 五parity🟢 fixed(fae8829b) ┃ LB03·B01 承重注释+guard 收口🟢 fixed(fae8829b) ┃ G27p·R22 24键 exact parity🟢 fixed
  [+认账注释 R56禁区行/R07错误类/LB06双宿主/N1真闸/N2 sentinel，均按 OWNER-DECISIONS 裁后口径]
  2026-06-10 ROOT 执行补登：fae8829b(2026-06-08 "add ROOT safety guards") 实际已落 GF1/G33a 步1+步2/LB04 注释+锁步矩阵/N1 真闸注释/N2 sentinel 注释+契约/G15a/G05/LB03/G27p 等 ROOT 安全网，但 LB04/N1/N2 当时漏翻 registry——2026-06-10 逐项核验后补翻 fixed（N1 另于当日补齐 service can_write_feedback≡feedback_write_enabled 同源守卫测试，E26 完整闭合）；R03-A 承重注释（ROOT 唯一真欠账）于 2026-06-10 按 dossier 草稿落地。含义：G22/G33/R41 的 ROOT 前置门均已开，Batch-C/D 对应 ⏸ 的「裁前 STOP」与「前置未落」拦截全部解除。

Batch-A  独立死叶子 / 零前置 / owner=false（最早可落）
  G02(R64+R65)* G14(R10) G16(R45≡R48已fixed/no-op) G21(R28已fixed) G28(R23)
  G31(R38part+R39) G32(R38 op_type/operator) G35(R36) G37(R02) G11(R11≡R63) G38(R06+R27+gantt)
  2026-06-08 执行补登：G02/G14/G16/G21/G28/G31/G32/G35/G37/R53/R61/R70 已在 `_registry.json` 与对应 dossier 登记 fixed；本清单保留批次归属，不表示这些单元仍待执行。G16 的旧 sp06 锚点已随 A P1.1 删除测试文件变为 no-op；G21 采用保留 `_safe_float` 名的薄包装方案，fitness 白名单经实测保留；R53 已删旧 `batch_order.py:74` 空操作行；R61 已删旧 report_context_filters.py 计划行 Python 过滤死簇并把负向测试重定向到 `normalize_report_resource_filter`；R70 已删旧 `schedule_service.py:46-50` 死副本。
  [+ LEAF-DUP-P4 纯删叶子：R53(2026-06-08 已 fixed) / R61(2026-06-08 已 fixed) / R70(2026-06-08 已 fixed) 随 A 落；LB04 安全网归 ROOT/Batch-A 之交]
  *G02(R64/R65) 同文件 scheduler_navigation_links.py，改点不同不可同质化（见 §1.2）；与 R42(G01)/R67(G34) 同文件四单元串行块

> **2026-06-09 ROOT 执行补登**：G07a/LB01 已 fixed。`core/services/scheduler/operation_execution_feedback_service.py` 只补两处承重注释：`_load_current_official_schedule` 上方钉写侧 fail-CLOSED 第一闸，`_build_event_payload` 写死 `SOURCE_SCHEDULE/ROLE_ADOPTED/None` 上方钉落库前消毒层；硬拒条件、`can_write_feedback` 第二硬门和三写死字段均未改。后续 R17/R20/R14 仍须按符号重 rg，严禁把这些注释解读成可透传 context。
  *G03(R66) 受 E04 软序，已在 G04(R54) 后于 2026-06-09 按符号重定位并 fixed；G25(R49旁支) 已并回 Batch-B 的 G24 一次原子执行，不在 Batch-A 单独落

Batch-B  依赖 ROOT 承重门 / 单门控前置
  G06(R62，2026-06-08 已fixed) ┃ G07(R17/R20)←G07a🔒 ┃ G08(R15/R17/R20)←与G07同原子
  G12(R12)←G11 ┃ G13(R55)⏸本轮跳过(O09) ┃ G19(R01+R04，2026-06-08 已fixed)←GF1 ┃ G20(R59，2026-06-08 已fixed)←GF1
  G24(R49含G25旁支+R50+R51，2026-06-08 已fixed) ┃ G40(R46)🟢 fixed←G40a ┃ G30(R34+R35) ┃ G36(R37) ┃ G39(R52+R25 KEEP注释)

Batch-C  身份族收敛 / 收口委托（依赖承重族 + parity）
  G04(R58→R54→R44)←LB03+R22parity；同批带走 E03→G01 ┃ G01(R42+R60)←G04
  G27(R22+R21)←LB03+G27p（2026-06-08 已 fixed） ┃ G09(R15/R19/R13 已 fixed) ┃ G10(R18/R19 repo私有版 已 fixed) ┃ G29(R72)🟢 fixed(2026-06-10)
  G15(R47+R71)🟢 fixed(2026-06-10) ┃ G22(R08+R09)🟢 fixed(2026-06-10) ┃ G33(R05步3)🟢 fixed(2026-06-10) ┃ G34(R67)🟢 fixed(2026-06-10)
  G17(R31)←E05/E06 同G23窗口 ┃ G23(R30+R33)←R33步1先

Batch-D  facade 删除最晚 / 跨 owner-pending 收口
  G18(R26)←G26+G23+G39 三桶收敛(E07/E08/E09)+E10 软自 G15
  G26(R29 KEEP注释)←O20 已裁保留🟢 fixed(9c51f52b，number_utils 头部 O20 KEEP 注释已落) ┃ G41(R14)⏸←LB01让位(E13)+三步前置
  G42(R24 KEEP注释+事实记录)←O23 已裁保留不删🟢 fixed(9c51f52b，schedule_diagnostic_contract 头部 O23 KEEP 注释+compound 事实记录已落)（‖G41 可并行）
  2026-06-10 补登：G26/G42 已于 2026-06-09 随 9c51f52b 落 KEEP 注释并在 registry 标 fixed——E07(G26/R29) 随之闭合；E09(G39/R52→G18) 早已随 O07 KEEP(2026-06-08) 闭合。G18 仅剩 E08(G23) 一个硬前置。
```

**11 标红债批次落位一行速查**：R05→ROOT(G33a step1/2)🟢 fixed(fae8829b) + Batch-C(G33 step3)🟢 fixed(2026-06-10，三步全收口)；R22→ROOT(G27p parity) + Batch-C(G27)🟢 fixed；R54→ROOT(collar 扩产前置) + Batch-C(G04)🔴⏸；R42→Batch-C(G01，E03 rebase R54 后)🔴；R04→Batch-B(G19，依 GF1)🔴；R09→Batch-C(G22)🟢 fixed(2026-06-10)；R15→Batch-C(G09 provider 链第一段，2026-06-09 fixed)；R19→Batch-C(G09 provider 收口 + G10 repo私有版注释/parity，2026-06-09 fixed)；R52→Batch-B(G39 KEEP注释，O07 已裁保留)🔴；R14→Batch-D(G41)🟢 fixed(2026-06-10)；R69→Batch-D/LEAF 桶🟢 fixed(2026-06-10，O24 loud raise+收口 schedule_input_contracts)。

**6 硬阻断新爆点闭合落位**：#1 collar 不产 3 键→ROOT 扩产前置 owner 闸门 F门(R54)；#7 R15 空值即 raise→Batch-B G08 前置安全网（分支级保 `if not text: return None`）+ Batch-C G09 owner 闸门；#19/#20 R05 双轨+builder 耦合→ROOT G33a step1 扩产前置（含 include_team_context 信号 + 派工轨单独入口）；#21 R42 :92 漏删→Batch-C G01 前置安全网（删点清单补 :92 同提交）；#22/#23 R22 双翻→2026-06-08 已由 G27 补齐「键集+取值 exact + bad-role raise」断言并按 O14 收口，状态 fixed。

> **⚠简化声明**：序列总览中 LEAF-DUP-P4 簇的 11 债（R69/R03/R41/R68/R32/R40/R53/R61/R70/R43/LB04）未单独成 G 编号原子单元（它们在 _interference_rebuilt §1 未占 G## 槽位，原 registry 以「Batch-1/5/15」桶标），本计划按其性质归入 Batch-A（纯删叶子 R53/R61/R70/R10 类 + LB04 安全网前置）与 Batch-B/Batch-D（R69/R03/R41/R68/R32/R40/R43 按 §3/OWNER 裁后门控落）。归并处已在对应批次显式登记，不静默吞。LB04 作为「所有 yes/no 收敛动作安全网前置」归 ROOT/Batch-A 之交（注释 + 全矩阵 parity，零结构）。
>
> **⚠简化声明补登（红队第1轮 RT3-P01 采纳·原计划全文零命中的 2 漏债；2026-06-08 已执行）**：**R64 / R65** 两条 `kind:real / load_bearing:false / needs_adversarial:false` 活债（registry B17-LEAF-DEAD 单元）此前被整份计划吞掉——既非 §0.2 列的对消/作废 7 条，也不在上述 11 债内，是静默蒸发。历史实证：R64 = **真零调用死 helper** `_has_navigation_date_range`（执行前 `web/viewmodels/scheduler_navigation_links.py:66-67`，全仓零调用）、R65 = 同文件孪生但**性质不同——是 `_target_url` 的 P6 死分支**（红队第2轮·1号 RT22 采纳纠正：R65 **非零调用死 helper**，执行前 `_target_url` 在 `_plain_link(label, plain_url or _target_url(...), ...)` 有真实引用，只是被 `or` 短路恒真遮蔽——9 条 spec 的 plain_url 字面量 9/9 非空，dossier R65 §52 定性为死分支非死码）。**2026-06-08 终态**：G02 已登记 fixed，R64/R65 已同一原子提交完成；当前 `_has_navigation_date_range` / `_target_url` / 旧 `plain_url or _target_url(...)` 均零命中；`TARGET_PAGE_PATHS` 保留并继续服务报表导航；`test_all_nav_specs_have_nonempty_plain_url` 护栏已落。**后续交接**：R42/R67 再进 `scheduler_navigation_links.py` 时必须按当前符号重 rg，禁信 G02 执行前旧裸行号；禁误伤 `_has_navigation_context`、`_use_plain_scheduler_chrome`、`_has_value`、`TARGET_PAGE_PATHS`。
>
> **⚠单文件三批四单元串行编排块（红队第2轮·2号 P-RT22-01 采纳·`scheduler_navigation_links.py` 跨两批四单元战场；G02 已落）**：第1轮 RT3-P01 只钉了「R64/R65↔R42 same_file」一对，**漏了同文件第三、第四单元**——历史实盘该文件被 **Batch-A/G02 的 R64/R65 + Batch-C/G01 的 R42 + Batch-C/G34 的 R67** 四处编辑触碰。R67.md:156-166 自述「R42 同文件碰撞面应扩到本文件抄点③④，串行避 diff-hunk 互撞须同覆盖本文件」。**当前炸点**：Batch-A/G02 已删除 R64/R65，旧行号下方所有锚点（含 R67 的旧 `:186`）已经系统性上移；跑到 Batch-C 时 R42/R67 的裸行号已全漂，且 G01 与 G34 在同文件同批还要互相串行（E17 只说「diff-hunk 串行」未说先后），三方混改易让 G01 的旧 `:40` 收口误碰 R67 元组首键 `plan_id`（R67.md:52「禁改 superset 元组里 plan_id 等非资源键，那是 R42 地盘」）。**编排块硬序/交接**（类比 §1.3 dispatch_rules 显式硬序）：
> 1. **Batch-A/G02 已完成**：当前只做交接复核，确认 `_has_navigation_context` / `preserved_report_context_fields` / `_REPORT_CONTEXT_FIELD_NAMES` / `TARGET_PAGE_PATHS` 按当前符号仍在；不要再按旧 R64/R65 行号重复删除。
> 2. **Batch-C 进该文件前**：对 R42(`:40 build_workbench_plan_context`)、R67(`_REPORT_CONTEXT_FIELD_NAMES` 元组 + `preserved_report_context_fields`) **全部按符号重 rg**，禁信本档裸行号。
> 3. **E17 拆两条件分支**（与 §1.4 G34/O18 联动）：「O18=保现状/仅注释 → R67↔R42 零冲突，无需串行」；「O18=收编③④ → R67 元组拼接 MUST 晚于 R42 删 collar 形参之后、且不得触碰元组内 `plan_id` 成员、并先过 `web.viewmodels→core.services.report` 分层门（违则分层 0 红）」。
> 在 §1.4 G01/G34 与本 §1.0 序列中「R64/R65 same_file」一律读作「R64/R65/R42/R67 四单元 same_file 串行块」。

### 1.1 ROOT — 承重注释 + 共享前置门（纯增量零结构，最先落）

**成员（调度单元 + 债）**：GF1（reject_integer_float 非债前置门）、G15a（LB07 注释 + spec_sync parity）、G07a（LB01 两处注释）、G05（LB02/LB05 注释 + 既有回归 `tests/operation_execution/test_execution_review_identity_guard.py`，盘上 173 行、经 test_registry:289 注册）、G40a（LB08 注释 + 绑契约）、G33a（R05 步1 扩 collar + 步2 五条 parity）、LB03（B01 承重注释 + guard 收口）、G27p（R22 24 键 exact parity）、LB04（boolean_normalize 全矩阵 parity 安全网）、+ 认账注释群（R56 禁区行 / R07 错误类 / LB06 双宿主 / N1 真闸 / N2 sentinel）。

**是否原子**：非单提交——ROOT 是「一组纯增量零结构动作」，各承重注释/parity 之间无行号互撞（不同文件），可分多次提交但**全部须先于任何删改批落地**。GF1 是 G19(R04)/G20(R59) 的硬门；各承重注释是 13 H 边的共同 source。

**为何这批**：承重注释与 parity 是纯增量（只加注释行 / 加测试，不删不改函数体），零回归风险，且是后续所有删改的安全网前置。先把「我是故意的」钉死，后续删改才有红线可守。

> **⚠本批重 rg 纪律（C5 逐批落地）**：ROOT 是全文行号位移的**源头**（在多承重文件锚符号上方插注释行），故 ROOT 执行前与执行后均须按符号重 rg。**本批高危锚点符号清单（执行前 rg 现场定位，弃裸行号）**：LB01 `_build_event_payload`/写死消毒块、LB02/LB05 五硬钉 + `execution_review` 签名、LB07 双栈 `@dataclass` + `_handle_missing_value`、LB03 `build_plan_identity`/`PlanIdentity.to_dict`、R05 `normalize_schedule_resource_filter`/`_normalize_team_axis`、R22 `normalize_plan_role`、GF1 `parse_required_int`。**ROOT 注释落地后须把「下游删点已位移」交接给 Batch-B/C**（Batch-B 已有「⚠行号位移总纲」承接，Batch-C 靠它兜）。

**前置安全网（逐条点名，含 Layer3 强制前置）**：
- **GF1·reject_integer_float 是「ROOT 新建受控参数」非「现有参数改默认值」**（强制前置；红队第1轮 RT1-P0-1/RT2-问题2 采纳纠定性）：**全仓 rg 零命中——`reject_integer_float` 当前不存在；真符号 `core/shared/strict_parse.py:81 def parse_required_int(value, *, field, min_value)` 无任何 float 拒绝参数，文件仅 130 行无 `:46` 锚点（旧锚点 `:46` 作废）**。GF1 实为「在 `core/shared/strict_parse.py:81 parse_required_int` 新增 `reject_integer_float: bool = False` kwarg（按符号 rg 定真实行，弃 `:46`）+ 透传链 + parity」三件套，**不是确认默认值**。加参数 + 默认 False 与「ROOT 纯增量零结构」自洽（不改现有调用方行为），但执行者须知是新增；落点显式登记 ①新建 kwarg 落 `core/shared/strict_parse.py:81` + ②确认 `core/services/common/strict_parse.py` 是否同步该参数 + ③8 处 algorithms 调用方（sgs_graph 等）的 `parse_required_int` 调用确认默认 False 不回归。自带 parity `True→3.0 raise / False→3.0 接受`，含 sgs_graph 风格 `parse_required_int` 调用断言。**默认 True 会炸 sgs_graph 等 8 处 algorithms 调用方**（3.0 由接受变 raise 排程静默回归）。门控 G19(R04)/G20(R59)。O38 已裁合规：加 kwarg 默认 False 非新建模块。
- **G33a·R05 扩 collar（含爆点 #19/#20 闭合）**：步1 扩 `normalize_schedule_resource_filter` 成 team 谓词产出点——接口含 `include_team_context` 信号（步3 搬谓词漏带该布尔即 `no such column: o.team_id`，爆点 #19）；放开空 id=全量 + 中文注释「id 空→全量（故意）」；**给派工轨单独入口，禁裸改 `:65-66 raise`**（双轨共用收口点，裸改污染超期/明细轨 + 报表轨，爆点 #20）；collar 只产 SQL fragment 文本 + 参数，**禁反向 import data SQL builder**（model→data 越层 + 环，分层违规）。步2 落 5 条 parity（team-only / operator-空-全量 / machine-空-全量 / team-空-全量 / bad-raise）。
- **G27p·R22 parity 升级（含爆点 #22/#23 闭合）**：升「键集 + 取值」exact 双断言——对 no_history 实参断言 `result_summary_parse_failed` 具体取值（爆点 #22：`_summary_unavailable(None,·)=(True,'排产摘要缺失')` 致 False→True 翻转，键集 parity 抓不到）；加「bad-role 仍抛 `field=plan_role`」断言（爆点 #23：删 view_context:74 破 R21 wrapper 精度唯一上游）；`evidence_contract:194` 升 24 键 exact（superset 双重逃逸口）。**view_context:74 `normalize_plan_role` 绝不删/绕过**。
- **G05·LB02/LB05 注释**：仅 `:209` 上方 + 五硬钉（`:58`/`:180-181`/`:191-192`/`:221`/`:236`）旁补注释；既有回归即 **`tests/operation_execution/test_execution_review_identity_guard.py`（盘上 173 行，4 组反例全绿，与 R56 共用该护栏，经 test_registry:289 注册，核存在用 `rg <name> tools/test_registry*` 非 `fd`）**；注释须交叉引用 web 真定义宿主（`reports_request_support.py:75` / `reports_execution_review_context.py:8`，**非 reports_page_support**）+ v19 DB CHECK 双列（爆点 #6/#18：读侧无 DB CHECK 兜底，此硬钉是读路径唯一最后一道）+ schema:284 candidate_rows 第二表。
- **G07a·LB01 注释**：两处「我是故意的」注释先落且锚符号上方（门控整个 service 文件删改）；禁区 `:369-374`/`:381-382`/`:471-473` 只补注释；**文案禁出现「写死冗余」式措辞**（埋删除诱因）。
- **G40a·LB08 注释🟢 fixed**：已钉死承重边界（正则反解桥），R46 已在其保护下删除；O35 已裁注释产出点按实证 `internal_operation.py:119/148/150/152/154` 改写，**禁贴 planned 草稿指 auto_assign（消费方非产出点）**。
- **G15a·LB07 注释 + 扩 spec_sync parity**：两栈 @dataclass 上方补注释（对侧路径互填）+ 扩 spec_sync_contract 覆盖三 helper 逐分支 + **`_handle_missing_value` INHERIT_LEGACY 两栈不对称**（爆点 #11：service `config_field_coercion.py:115` 多一条 legacy-omission 分支返 Tuple，model 栈无、返裸 Any，parity 须显式覆盖否则「DRY 统一」静默丢语义且 parity 全绿）。
- **LB03·B01 承重注释 + guard 收口**：全局承重族先落，门控 G27 全 B02 身份族；R22 只 CALL `build_plan_identity`/`PlanIdentity.to_dict:46-71` 不改 builder。
- **LB04 安全网**：boolean_normalize 仅 `:33` 上方补注释（algorithms 标「前瞻」）+ 新建全矩阵 parity 网；**绝对禁删 shared 改指 services**（core.models→core.services.common→core.models.enums 导入环 + 越层）；是 Batch-A 所有 yes/no 收敛动作的安全网前置。
- **⚠门禁可执行性总纲（红队第2轮·3号 plan_rt2_3 采纳·贯穿所有批次门禁，逐批不再重复）**：
  - **(1) 删/收编 parse helper 须同 PR 核退/留白名单（问题1·中）**：`tests/gate_meta/test_architecture_fitness.py:229 test_no_new_local_parse_helpers` 除查「新增」外还有第二条断言 `:254-256 stale_entries = LOCAL_PARSE_HELPER_ALLOWLIST - found_allowlist`（白名单实盘 3 项：`_sched_utils.py:_safe_int`/`batch_service.py:_safe_float`/`system_config_service.py:_get_int`，`:75-79`）。**凡删除或收编命中 `LOCAL_PARSE_HELPER_NAMES`（`:63-74`：`_safe_int/_safe_float/_safe_seq/safe_*/_cfg_*/_get_int/_get_float`）的函数，须同提交实测决定白名单退/留**：删掉函数名才退；保留函数名做薄包装则通常仍按名命中，白名单要保留，否则 fitness 会红。2026-06-08 G21/R28 已实测：`_safe_float` 走方案 b 保名薄包装，`:77` 白名单必须保留，`-k test_no_new_local_parse_helpers` 通过。执行者删任何 helper 前仍须 rg 该集合自检。
  - **(2) 语义雷达门禁拆可机器判定两半（问题2·中）**：`.codestable/semantics/run_drift_scan.py` 脚本头自述「只读、不直接 fail，drift exit 0/1 都正常（1=有 findings）」——**CI 跑它永远绿，不能作机器红/绿门**。各批「语义雷达无新漂移」门禁正名为两半：**(a) `run_semantic_guards.py` 必须 exit 0**（property + snapshot 守卫 test_config_field_properties/test_plan_role_properties/test_semantic_snapshots，真能红，作机器门）；**(b) drift 须显式对比 `evidence/SemanticDebt/drift/drift-baseline.json` findings 数 vs HEAD 基线，差值 >0 才算新漂移并人工裁断**（非机器红门，是人工核查项）。缺 `.venv-semantic`(Py3.14) 则 drift return 2 不可判定。
  - **(3) 门禁清单写全路径名 + 标 test_registry（问题3·低）**：`regression_execution_review_identity_guardrail`（R56）/`spec_sync` 等简称 **`fd` 按文件名搜不到**（regression_ 前缀长名，经 `tools/test_registry_groups_scheduler.py` 注册）。门禁清单统一写全名 **`tests/operation_execution/test_execution_review_identity_guard.py`**（9 def，test_registry:289 引用）/ **`tests/config/test_scheduler_config_spec_sync_contract.py`**（test_registry:56 引用），核存在用 `rg <name> tools/test_registry*` 而非 `fd`，免误判门禁缺失而绕过。
  - **(4) DB CHECK 门禁正名为「v19 CHECK」（问题4·低）**：实盘 `rg CHECK core/infrastructure/migrations/v18.py` **零命中**——`source_table='schedule'`/`effective_plan_role='adopted'` 两 CHECK 全在 **`v19.py:14-19`**，v18 仅 schema 前置无 CHECK。各批门禁「v18/v19 DB CHECK 不破」正名为「**v19 DB CHECK 不破（两列），经 `tests/migration_db/test_migrations.py` + `tests/migration_db/test_migration_schema_contract.py` 机器验证；v18 仅 schema 前置**」，避免验证「v18 CHECK」查无对象。
  - **(5) P7 防回潮门禁（2026-06-08 A 收官新增 · full gate 第 17 步 `tools/scan_anti_regression_gate.py`，B 全程纳入每批 go-no-go）**：对「自基线 `d4589d77` 以来 `git diff --diff-filter=A` 新增的文件」施三规则——① 新增收集型测试文件须含 test 函数（否则 main-style 空壳/0 收集）、② 须有模块 docstring、③ 新增生产源文件须落在某 required 回归组 `*_file_scopes` glob 内。**对 B 的实际约束面（经核查）**：(a) 规则③ **B 全程零触发**——B 无任何新增生产 `.py`，三处源动作（R09 收口 / R54 collar 扩产 / GF1 新增 kwarg）全是改既有文件；(b) 规则①② 仅当 B **新建独立测试文件**时触发（如新 parity oracle），须带模块 docstring + 真 test 函数，且**落 P6 终态拓扑 `tests/<模块>/test_*.py`，禁旧扁平 `tests/regression_*.py`**；(c) **删测试永不触发**（`--diff-filter=A` 只看新增，删除走 D；R51 续命测试删除已实测豁免、零禁删白名单依赖）。门禁只在 full gate（`run_quality_gate.py`）跑，daily/pre-push 快门禁不跑。
  - **(6) 批后单测验证须规避 P4 并行 flaky（2026-06-08 A 收官新增）**：A 的 P4 给 daily gate 接入 xdist 并行 + serial 分流（`tools/full_test_debt_shards.classify_nodeid` 按文件名/路径模式自动打 serial marker）。B 自建 oracle 默认落**并行面**，若含全局态污染（`mod.X.attr=` 改全局模块 / `os.environ` 写 / 全局单例改）会被 xdist 同 worker 跨文件复用污染致 flaky。**B 批后单 oracle 验证一律用裸单进程 `.venv/bin/python -m pytest <file> -p no:cacheprovider`，不经 daily gate**；新建测试先 `classify_nodeid` 预判 serial/parallel。详见 `_B_COMPAT_SAFEGUARDS.md`「P4 并行机制对 B 的约束」节。

**不可碰清单（按符号）**：
- STRICT-4 一字不碰：`scope.py:9` / `feedback_support:161`（真 loud raise）；`public_errors:167` / `auto_assign:114`（→0 哨兵，V1⑥：禁区注释须纠偏，禁称「→raise/写入闸门」）。
- LB01 禁区 `:369-374`/`:381-382`/`:471-473`；LB02/LB05 五硬钉 + `:209` 签名（禁加 plan_role/scenario_id 形参）；LB07 `coercion:470 置零` + loud raise 族（MISSING_POLICY_ERROR:71-72 按符号语义认定）+ 30 字段锁步表；R05 collar `:65-66 raise`（双轨）+ `_normalize_team_axis:65`（展示轴禁误并）+ repo team 双 join `:462-463`/空 id 全量 `:455/:460`；view_context `:74 normalize_plan_role` + `:65`；`builder:158` + `PlanIdentity.to_dict:46-71`。
- **§3.2 方向硬门**（认账注释专属）：`navigation_context.py:79`（R56 退化禁区行，现盘 fail-CLOSED：非法 role→ROLE_ADOPTED）+ LB06 双宿主（`reports_execution_review_context.py` + `reports_request_support.py`，现盘 fail-CLOSED 强制 adopted+scenario=None）——**认账注释先核现盘 fail-CLOSED 方向再下笔，禁粘 §90 LB-B4 反向 fail-OPEN 旧文案**，写反 = 承重击穿按 P0 处理。
- N1 真闸（爆点 #4）：注释钉「真闸在 `feedback_service:369-382` 双 raise，本字段 `can_write_feedback` 仅 query 优化短路」，**禁引 dossier 幻觉锚点 `:89`/`:70-84`**（execution_context.py 无此二符号）。N2：禁删 `if index<total: raise`（`:161/:162`），`:179 return 0` + `:205 previous_event_id=0` 同 sentinel 禁顺手统一/置非 0。

**收口行为差异检查项（None vs raise 反例）**：
- GF1：`reject_integer_float=False` 时 `3.0→接受`（现状），`=True` 时 `3.0→raise`（R04/R59 收口后行为），parity 双向各一例。
- R22 parity：no_history 实参 → `result_summary_parse_failed` 取值（False[旧] vs True[收口后]）；bad-role → 抛 `field=plan_role`（保）vs 静默归 adopted（破，禁）。
- R05 parity：team-only → team 双 join 谓词在；operator/machine 空 id → 全量（非 raise）；team 空 → 全量（非 raise，按 O16 空班组=看全部）；bad → raise。
- LB07：`非dict→None 不抛` / `count 坏值→1 不抛` / `空 choices→True` / `except continue 静默跳` / `_handle_missing_value` INHERIT_LEGACY 两栈差异逐字保真。

**批后门禁**（措辞遵 §1.1 ⚠门禁可执行性总纲）：
- `tests/gate_meta/test_architecture_fitness.py` 21 项全绿 + 0 分层违规（ROOT 纯增量，理应零违规；若红说明注释/parity 误触结构）。**注**：本批不删 parse helper，不触 `test_no_new_local_parse_helpers:254-256 stale_entries` 第二断言（总纲(1)）。
- 语义雷达：`.codestable/semantics/run_semantic_guards.py` exit 0（property+snapshot 真机器门）+ drift 对比 baseline findings 数无增（人工核查项，非机器红门；总纲(2)）。承重注释是「钉死概念身份」动作，应降漂移不升。
- **v19 DB CHECK 不破**（ROOT 不动 DB；LB01/LB02 注释须与 v19 `CHECK(source_table='schedule')`/`CHECK(effective_plan_role='adopted')` 双列交叉引用，验注释与 CHECK 1:1），经 `tests/migration_db/test_migrations.py`+`tests/migration_db/test_migration_schema_contract.py` 机器验证；v18 无 CHECK（总纲(4)）。
- 本批专项契约逐条点名：GF1 parity 绿（True/False×3.0）；R22 24 键 exact + 取值 + bad-role raise 三断言绿；R05 五 parity 绿；LB07 `tests/config/test_scheduler_config_spec_sync_contract.py` 三 helper + INHERIT_LEGACY 绿；LB04 全矩阵 parity 绿；`tests/operation_execution/test_execution_review_identity_guard.py`（R56，经 test_registry 注册，用 `rg` 核存在非 `fd`）绿。

**go-no-go 判据**：ROOT 全部承重注释 + parity 落地且上述门禁全绿 → 放行 Batch-A/B。任一承重 parity 红（尤其 R22 取值翻转断言、R05 双轨 parity、GF1 默认值）→ STOP，回查注释/parity 是否误触函数体。

**owner 裁后执行口径（2026-06-05 已全裁，照 §3/OWNER 执行）**：
- F门-R54-collar：选 plan_resolution 入参 + fail-CLOSED 默认形态，先扩 3 键产出点再允许 delegate。
- R05 collar：含 include_team_context 信号 + 派工轨单独入口；`(team,"")` 语义为全量。
- R22：no_history 接受新 True；前端文案须改中性，不写成解析失败吓用户。
- LB08：注释文案产出点按 `internal_operation.py` 实证，禁写到 auto_assign 消费方。
- R56 认账接受；R07 按 O31 统一成 AppError/ErrorCode.NOT_FOUND，并补 schedule=None→raise 回归测试；persistence_errors:13 归 R04 禁区保持现状+注释；LB03/LB06 落认账注释。
- N1 钉 feedback_service:369-382 真写闸；N2 钉 `_event_id_for_revision` 非末位缺 id 必抛错契约。

### 1.2 Batch-A — 独立死叶子 / 零前置 / owner=false（最早可落）

**成员（调度单元 + 债）**：G14(R10 死方法 `gantt_service:60-62`)、G16(R45≡R48 整文件删 `config_adapter.py`，2026-06-08 已 fixed)、G21(R28 收口 `parse_finite_float`，2026-06-08 已 fixed)、G28(R23 dedup `_normalize_role` 收口 model)、G31(R38 part 份 + R39 `list_unparsed`)、G32(R38 op_type:73/operator:85 两份)、G35(R36 两死方法)、G37(R02 test-only 壳)、G11(R11≡R63 去重 `_normalize` 收口 `gantt_critical_chain.py`，2026-06-08 已 fixed)、G38(R06+R27+gantt 四空包同提交，2026-06-08 已 fixed)。**G03(R66，2026-06-09 已 fixed)**：已在 G04(R54) 后按 suffix 签名重定位并删除 reports_workbench 私有死函数；**G25(R49 旁支)** 已并回 Batch-B 的 G24 一次原子 fixed，不在 Batch-A 单独执行。**+ 纯删叶子**（原 LEAF-DUP-P4 桶，按 ⚠简化声明归入此批）：R53(`batch_order.py` 旧 :74 一行，2026-06-08 已 fixed)、R61(plan 死簇 `:160/164/172-187` + 重定向负向测试)、R70(`schedule_service.py` 旧 :46-50 死副本，2026-06-08 已 fixed)。**+ G02(R64+R65，2026-06-08 已 fixed)**：权威源 `_interference_rebuilt.md:17` 定义 G02={R64,R65} NAV-PLANID；历史动作是 R64 删除 `_has_navigation_date_range`、R65 完成 `_target_url` 死分支三件套并保留 `TARGET_PAGE_PATHS`。当前本段只保留批次归属和历史原因，不再表示 R64/R65/R66 待删；后续 R42/R67 进入同文件时按符号重 rg。

> **2026-06-08 执行补登**：G02/G11/G14/G16/G21/G28/G31/G32/G35/G37/G38/R53/R61/R70 已在 `_registry.json` 与对应 dossier 登记 fixed。上方成员段保留批次归属和执行纪律，不再表示这些单元仍待执行；后续不要重复处理 R64/R65/R11/R63/R10/R45/R48/R28/R23/R36/R38/R39/R02/R06/R27/gantt 空包/R53/R61/R70。G02 的旧 `scheduler_navigation_links.py` 裸行号已经随删除上移,后续 Batch-C 的 R42/R67 必须按符号重 rg；G11 已把单份 `_normalize_critical_chain_result` 收口到 `gantt_critical_chain.py:67-88`，后续 R12/R55 只能在该单份 helper 上继续改；G16 的旧 sp06 锚点已随 A P1.1 删除测试文件变为 no-op；G21 的 `_safe_float` 保名薄包装仍需保留 fitness 白名单；G38 已把 SP05 service 拓扑元组收回 `("config", "run", "summary")`，并删除四空包 no-import 循环；R53 已删旧 `batch_order.py:74` no-op，现盘 :39 形参/:58 真消费/:74 return 均保留；R61 已删 report_context_filters.py 旧计划行 Python 过滤死簇，当前 live `filter_downtime_rows_for_report_context` / `_row_text` / `normalize_report_resource_filter` 均保留；R70 已删旧 `schedule_service.py:46-50` 死副本，`ValidationError` import 与 run/input_collector live helper 均保留。

**是否原子**：可执行成员**互相独立**（跨文件零碰撞），可各自单提交；簇内多债（G31 R38part+R39、G38 四空包）须各自原子同提交（见前置）。G03 曾是软序延后项，已于 2026-06-09 fixed；G25 是并回 G24 的同债旁支，不按 Batch-A 独立提交。整批 owner=false。

**为何这批**：全是「零前置、零 owner 裁断、误删均 loud（ImportError/NameError/SyntaxError/测试红）非静默炸」的死叶子，最早可落腾出心智空间。**例外已闭合** G03 受 E04 软序（R54 改 reports_workbench 上方区域漂移 R66）→ 已紧随 G04 后于 2026-06-09 按 suffix 符号重定位并删除。

> **⚠本批重 rg 纪律（C5 逐批落地）**：Batch-A 多为整段/整方法删，**删任一处即位移其下所有锚点**，故每删一处后立即 `rg` 复核活近亲在位（go-no-go 即此）。**本批高危锚点符号清单（执行前 rg 现场定位，弃裸行号）**：G02 `_has_navigation_date_range`/`_target_url`/`urlencode`/`query_for_target`（删后复核 `_has_navigation_context`/`TARGET_PAGE_PATHS`/`_REPORT_CONTEXT_FIELD_NAMES`/`preserved_report_context_fields` 在位）、G14 `resolve_version`、G25 `parse_dispatch_rule`（2026-06-08 已并回 G24 fixed）、G37 `report.py:180` 兄弟壳、G38 `_assert_init_has_no_imports`、G11 `_copy_critical_chain_result`/`_normalize`。G02 与 R42(G01)/R67(G34) same_file，删后其下锚点系统性上移，交接给 Batch-C（见 §1.0 三批四单元串行块）。

**前置安全网（逐条点名）**：
- G11(R11≡R63)：2026-06-08 已 fixed；已先建 normalize parity 黄金基线并扩到 11 个 legacy 边界（钉 `available=0→True` + `bool()` 包裹差异），再把单份 helper 收口到 `gantt_critical_chain.py:67-88`；support/provider 两路仅改调用目标，未 `return raw`，未误删 `_copy_critical_chain_result`。A1 前置已满足，后续 G12/G13 仍只许在单份 helper 上继续改。
- G38(R06+R27+gantt 空包)：2026-06-08 已 fixed；已按**四包一次性原子提交**执行：`tests/gate_meta/test_sp05_path_topology_contract.py:312` 仅保留 `("config", "run", "summary")`，旧 `:315-316` delayed 循环已删除，四个空包 `batch/calendar/dispatch/gantt` 的 tracked `__init__.py` 已删除；`_assert_init_has_no_imports` 定义保留在现盘 `:175`，web 域调用仍在 `:408`，`:637` 第二处三元组未动。
- G37(R02)：先拆测试 import（`:11` 单符号改指 resource_matching_context）→ 后删壳 `:461-475`；禁连删兄弟壳 `:478`（report.py:180 承重）。
- G16(R45≡R48)：2026-06-08 已 fixed；`config_adapter.py` 已删，旧 `tests/regression_sp06_no_duplicate_defs.py` 已由 A P1.1 删除，旧清单同步步骤为 no-op；继续禁碰 `core/algorithms/greedy/schedule_params.py`（same_file 误标零碰撞）。
- R53：2026-06-08 已 fixed；已删旧 `batch_order.py:74` `_ = scheduled_count` 空操作行；现盘 :39 形参、:58 真消费、:74 return 均保留；`sgs.py:127` 同形态行不是本债，未动。
- G21(R28)：2026-06-08 已 fixed；采用方案 b，`_safe_float` 保名薄包装到 `parse_finite_float(value, field="ext_days", allow_none=True)`。已跑 `pytest -k test_no_new_local_parse_helpers`，fitness 白名单 `:77` 必须保留；后续只做残留 rg，禁重复删除白名单。
- G25(R49 旁支)：**2026-06-08 已并回 G24 fixed**，不在 Batch-A 单独落。旧要求是与 G24（Batch-B）的 R49 主体、R50、R51 并回一次原子 diff，按 file:line 定点删旁支行、禁符号名全局删；现盘禁再按旧 G25 锚点重复施工。
- R61：2026-06-08 已 fixed；已删旧计划行 Python 过滤死簇并同步重定向测试；当前仍禁删 live 孪生 `_row_text:156`/`normalize_report_resource_filter:119`/`filter_downtime_*:244`。
- R70：2026-06-08 已 fixed；旧 `schedule_service.py:46-50` 死副本已删，仍保 `ValidationError` import（并发拒绝路径仍用）。
- **R64/R65（G02，红队 RT3-P01 补登 + 红队第2轮 RT22 纠 R65 性质）**：2026-06-08 已按同文件同一原子提交完成,下列要点现在作为复核/交接,不再作为待施工步骤：
  - **R64 终态**：`_has_navigation_date_range` 已删除,当前全仓零命中。
  - **R65 终态**：`_target_url` 已删除;旧 `plain_url or _target_url(...)` 已化简为 `plain_url`;本文件 `urlencode`/`query_for_target` 孤儿 import 已删除;`TARGET_PAGE_PATHS` 保留。
  - **护栏已落**：`test_all_nav_specs_have_nonempty_plain_url` 已钉住 specs 第 3 字段非空不变量。
  - **后续交接**：`_has_navigation_context`、`_use_plain_scheduler_chrome`、`TARGET_PAGE_PATHS`、`_REPORT_CONTEXT_FIELD_NAMES`、`preserved_report_context_fields` 均按当前符号重 rg 复核;R42/R67 进本文件时不要信 G02 删除前的旧行号。

**不可碰清单（按符号）**：G14(R10) 活近亲 `resolve_version:60`（旧 :64；误删静默炸周计划版本解析）；G35(R36)/G31/G32 各 repo 活近亲；R37 已 fixed 后活近亲 `list_links_with_operator_info:82`（旧 :92，后续禁再按旧 `:82-90` 施工）；R53 已 fixed 后仍禁 `:39/:58/:74 return`；R64/R65 活近亲 `_has_navigation_context:47`（误删炸导航 chrome 判定）；G11 已 fixed 后仍禁 `_copy_critical_chain_result:108`（缓存浅拷，非 normalize 点）+ 禁 `support:36 return raw`。

**收口行为差异检查项**：G11 收口 `available=0`：取 `bool(available)` 会把 `0→False`（静默放宽，禁），须保 support 的写法令 `available=0→True`；G28(R23) 已收口为 model:21 真相源 + service:17 import/:102 调用，**绝不并入 view_context:65**（带 VALID 校验抛 ValidationError，错误类型前移致上游 catch ValueError 静默漏接）。

**批后门禁**：fitness 21 项全绿 + 0 分层违规；语义雷达无新漂移；v18/v19 不破；本批专项：G11 已 fixed 后以 `test_gantt_critical_chain_normalize_parity.py` 11 边界绿 + `rg` 证单份 `_normalize_critical_chain_result` + `_copy_critical_chain_result` 在位，G38 SP05 topology contract 绿（现盘 `:175 def`/`:317` 起 strong-compat 断言不碰）、G16 已 fixed 后以残留 `rg` 证 `config_adapter`/三符号/`NO_CFG_GET_TARGETS` 零命中且 `schedule_params.py` 在位、G21 已 fixed 后以 `_safe_float` 现函数体 + `test_no_new_local_parse_helpers` 证明 allowlist 保留正确、R53 已 fixed 后以 `tests/algorithm/test_greedy_refactor_contract.py` + `tests/algorithm/test_greedy_scheduler_base_date.py` 28 passed 和 `rg` 证 batch_order.py no-op 零命中、删后逐个 grep 复核活近亲在位（resolve_version:60（旧 :64） / list_links_with_operator_info:82（旧 :92） / sgs_scoring:34 / ordering:59 / _copy:108）。

**go-no-go 判据**：每个死叶子删后立即 grep 活近亲在位 + 该文件相关测试绿 → 放行下一叶子。任一活近亲 grep 落空 → 误删，立即 revert。

**owner 裁后门控**：本批无未裁债（全 owner=false）。R61/R70/R53 等若 owner 对「纯删」有异议在此前拦截，否则按 false 落。

### 1.3 Batch-B — 依赖 ROOT 承重门 / 单门控前置

> **2026-06-08 执行补登**：G06(R62) 已 fixed：按符号重盘后，把 execution_review 报表层四组 `*_identity_label`/`*_export_label` 假字段收成公开 `*_label`，同步删除模板 `text-meta` 死副行并把 title 改回 `*_label`，xlsx 直接读 `*_label`，并补 dict/xlsx/模板三类守卫；LB02/LB05 adopted-only 护栏和 state 层真身份键未动。G12(R12) 已 fixed。已在 R11/R63 单份归一前置满足后，只补关键链坏时间行可观测信号：`dropped_count` / `critical_chain_partial` 穿过 `_empty_result`、单份 `_normalize_critical_chain_result`、`gantt_contract.py` 的 available=False 分支与前端 `gantt_contract.js` 状态归一。G24(R49+R50+R51，含 G25 旁支) 已 fixed：同一原子 diff 删除 5 行死别名、`mean_positive`、`statistics` import、`parse_dispatch_rule`、`parse_strategy` 与两份续命测试；`import math`、非有限工时回退契约、同名前缀活函数和 schedule_params/optimizer_config loud raise 收口点未动。G30(R34+R35) 已 fixed：按 O10 纯删口径删除 `schedule_repo.py` 四个死方法，退四件套测试/脚本引用，`benchmark_fjsp.py` 改指既有 `SchedulePlanQueryRepository.get_plan_time_span`。G39(R52+R25) 已 fixed：按 O07 方向 B 只补「我是故意的」注释，保留全量扫描 oracle 与 R25 service 垫片，不删 impl、不新建 `test_sgs_graph_ready.py`。R55/G13 仍按 O09 本轮跳过，未随 R12 改 scope。

> **2026-06-08 执行补登**：G07/G08 的 R17/R20 已 fixed，同一原子处理 feedback service/support 两个文件的死导入/死键与 labels shim 收口。R17 只删 `EXECUTION_EVENT_EXCEPTION` 死导入和 `_REPORTED_STATUS_BY_ACTION` 死项，保留 `EXECUTION_ACTION_REPORT_EXCEPTION` 活键；R20 删除 `core/services/scheduler/operation_execution_labels.py` 纯转出垫片，5 个消费方改直连 model，并同步摘门禁文档旧路径。R15 provider 坏时间解析未混入本簇，仍按 G09 `R15→R19→R13` 串行链处理。

**成员（调度单元 + 债）**：G06(R62)已 fixed；G07(R17/R20)←G07a🔒；G08(R15/R17/R20)与 G07 同原子；G12(R12)←G11；G13(R55)⏸**本轮跳过，仅保留暂停占位**；G19(R01+R04)←GF1；G20(R59)已 fixed←GF1；G24(R49 含 G25 旁支 + R50 + R51)已 fixed；G40(R46)已 fixed←G40a已 fixed；G30(R34+R35)已 fixed；G36(R37)；G39(R52+R25)已 fixed，按 O07 仅 KEEP 注释、不删 impl/垫片、不新建迁移测试。

**是否原子**：簇内强原子——G07/G08（R17/R20 跨 service+support 同原子提交）；G19（R01 先删→R04 后收口必同 PR）；G24 已按「R49 主体 + G25 旁支 + R50/R51 一次原子 diff」执行完，后续禁再按旧锚点重复施工；G39 只做 O07 已裁的保留注释动作，历史“迁测试+删 impl+删 R25 垫片”路线作废不执行；G12 单独穿单份 `_normalize` 白名单，G13/R55 本轮不随 G12 改。跨成员无序（除门控前置）。

**为何这批**：每个成员恰有一个 ROOT 承重门或 GF1/G11 前置；前置绿后即可落，不涉身份族大收敛（那在 Batch-C）。

**前置安全网（逐条点名，含 Layer3 强制前置 + 标红债）**：
- **⚠行号位移总纲（红队第1轮 RT1-P1-5 采纳·贯穿 Batch-B/C 所有同文件删点）**：ROOT 批已对多个承重文件**插入注释行**（G07a 在 LB01 锚符号上方两处、G05 LB02/LB05 五硬钉旁、G15a LB07 两栈上方、LB03 builder 上方等），这些插入令该文件**所有**后续删点行号系统性下移——不止同簇删点。故 Batch-B/C 正文里所有「删 :NN 非 :MM 活键」式裸行号断言（如下文 R17「删 :81 非 :80」、R09 收编面、R47 死活参 8 处逐字相同）**一律以 `<符号名/键名>` rg 现场定位为准，删除前对每个锚点重 rg，信旧裸行号即误删相邻活键**；本档所有 :NN 是 2026-06-05 实盘值，ROOT 注释落地后必漂。**R01 先删** `_iter:67-87`（含 `:72`，缩 R04 收口面 6→5）→ R04 后收口剩 5 点 + **6 处 except 同 PR 加 ValidationError 不可拆**（漏改任一→脏 op_id 由静默 skip 变 ValidationError 上抛炸排程统计/持久化）；R01 删函数 + 删 SP05 断言必同提交（中间提交必红，显式声明）；同删孤儿 `typing:5 Iterator`。E24 与 G40a 认账协同（R04 哨兵 B/C 仅注释禁改 raise）。
- **G08(R15/R17/R20)🔴**（2026-06-08 R17/R20 已 fixed；R15 provider 留 G09）：R15 收口 `parse_operation_event_time` **空值本身就 raise**（爆点 #7），整体 delegate 把合法空时间炸 raise=正常读历史 500；**收口必分支级**——`if not text: return None` 留在 provider 本地，仅坏值走收口符号；坏值方向 loud raise（须确认下游接得住）或可观测降级标记；先补三处 required/optional parity（含空值分支断言）。R17 已只删 service/support 死导入与 support 死项，未重构 `_build_event_payload`；R20 已删除 labels shim 并改 5 个消费方直连 model。爆点 #8：启动探针 `migration_operation_execution_contract.py:349/355` INSERT `event_time:"not-a-date"` 靠拒绝判库迁移态，后续 G09 改 R15 provider 前须继续确认不撼「坏 event_time 必被拒」预期。
- **G07(R17/R20)🔴**（2026-06-08 已 fixed）：←G07a（LB01 注释先落，裸奔期禁动 service 文件）；R17↔LB01 同 `_build_event_payload` 函数体（最危险边），已按禁区只删 import 死物；R20 漏改旧路会 ImportError（loud 非静默），本次已全量改直连 model。
- **G39(R52+R25)🔴**（R52 标红，O07 已裁保留）：**两份同名 ready_queue.py 防混（红队 RT1-P0-2/RT2-问题3 采纳）：impl=`core/algorithms/greedy/dispatch/ready_queue.py:103 get_ready_operation_ids`（历史拟删点，本轮不删）、R25 垫片=`core/services/scheduler/graph/ready_queue.py`（补注释后 13 行 re-export，本轮也不删）**。**✅ O07 已裁方向 B：保留 impl 当差分校验尺子 + 补「我是故意的」注释（禁裸留无注释）**——`core/algorithms/greedy/dispatch/ready_queue.py:103 get_ready_operation_ids` 与 R25 垫片**均不删、不新建 `test_sgs_graph_ready.py`**，既有 `tests/scheduler_graph/test_ready_queue.py` 原样存活，**P7 rule①② 对 R52 不适用**。下述「方向 A 删除」编排已被 O07 否决、仅存技术分析（不执行，论证为何不可裸删）：曾拟走 A 先新建 `tests/scheduler_graph/test_sgs_graph_ready.py` 按 **31 用例**全量分流（dossier「~23」严重失真，V4⑦：23 个走全量版 `_ready()`→`get_ready_operation_ids` 删即全断含 **16 个 ReadyQueueContractError 合同（红队 RT3-P03 采纳：实盘 `rg -c ReadyQueueContractError test_ready_queue.py`=16，非旧值 15，±1 漂移会致 A2 漏接 1 合同覆盖）** + LIVE ValidationError 契约按 `test_graph_ready_state_*` 符号重 rg + 2 个差分 oracle 两路都改）；爆点 #16：`_full_scan_ready_ids:81` helper 体调 impl，删 helper 与改 **2 个差分 oracle 函数**（当前 `:273 branch_join` 含 4 字面量 `:278/:281/:284/:287`，`:290 fixed_predecessor` 含 1 字面量 `:299`，共 **5 处字面量行**；权威 verdict_V4，旧数量表述把 5 字面量误记为 6）的字面量同原子；parity 异常类不同只能断「均拒绝」禁断同类型；None 分支两路分别写；同提交退 lazy_runtime:29+metrics_topology:142。
- **G40(R46)🟢 fixed**：←G40a 已 fixed（LB08 注释先落）；R46 已按符号 grep 重定位删除 `_safe_identifier` 私有死别名；**同名陷阱 `v4_sanitizers.py:37 _safe_identifier` 活函数**保留，legacy 正则桥、`public_safe_identifier`、`_positive_int`、`make_public_error`、`__all__` 未动。
- **G12(R12)🟢 fixed**：←G11；已保留 `:84` 坏时间行过滤，仅补 collector；`:54` 与 `:328-334` 双补 dropped_count 并穿 `_normalize` 白名单；爆点 #14 已处理，contract available=False 分支显式保留 `dropped_count` / `critical_chain_partial`。JS 状态归一也保留新键，R55 scope 未做。
- **G13(R55)🟡⏸**：←G11；**O09 已裁本轮不做**，这里只保留暂停占位。重启条件=怀疑者过 PHASE0 §6 三问 + R11/R63 单份化前置就绪；未重启前不得随 G12 同改 `_normalize`。三问原文见 §3 O09：① 当下债 vs 在途中间态、② `:385 None 回退`是否有意、③ 裸删 vs 补 scope 标记；禁破坏 `:385 None 回退` + support:55-56 分流判据。
- **G24(R49+R50+R51)🟢 fixed**：2026-06-08 已按一次原子 diff 执行，旧「从大行号往小删」是执行前口径。已删除 R49 5 行死别名、R50 `mean_positive` + `import statistics`、R51 `parse_dispatch_rule` / `parse_strategy` 与两份 case-insensitive 续命测试；R51 `:25` 静默兜底断言未迁移未保留；R50 `import math` 保留；R49 活近亲 `evaluation._parse_due_date_state` / `sgs_scoring._parse_due_date` 未动；收口点 `schedule_params:277/346` + `optimizer_config:166/189` loud raise 只读确认在位。
- **R49-self 执行口径（红队 RT3-P02 采纳·同债拆两批须钉同提交序）🟢 fixed**：R49 的 G25 旁支已并回 G24 一次原子执行。现盘禁再按旧 Batch-A/G25 锚点单独施工；后续复核只看全仓是否还有 `parse_dispatch_rule` / `parse_strategy` / R49 死别名残留。
- **G20(R59)🟢 fixed**：2026-06-08 已在 GF1 前置满足后收口。`parse_report_nonnegative_int` 保留 blank→`blank_default` 短路，非 blank 委派 `parse_required_int(..., min_value=0, reject_integer_float=True)`；已删除 `_INT_TEXT_PATTERN` / `_parse_plain_report_int` / `import re`；`parse_report_int` 与 `__all__` 未动。
- **G19(R01+R04)🟢 fixed**：2026-06-08 已按强序完成。R01 先删 `_iter/count/has` 死链、两层旧导出和 SP05 续命断言；R04 后把 `_strict_positive_int` 收口到 `parse_required_int(..., reject_integer_float=True)`，剩余 5 处调用点捕获 `ValidationError`；B/C 哨兵只补注释和 parity，LB08 文案/正则桥与 STRICT-4 未动。GF1 已落地且默认 False，后续 G20 可视为前置满足。
- **G30(R34+R35)🟢 fixed**：2026-06-08 已按 O10 纯删口径闭合。已删除 `schedule_repo.py` 旧 `get_version_time_span` / `list_between` / `list_overlapping_with_details` / `list_dispatch_rows_with_resource_context` 四个死方法；`benchmark_fjsp.py` 改指 repo 层既有 `SchedulePlanQueryRepository.get_plan_time_span(version=..., source_table=SOURCE_SCHEDULE, candidate_id=None)`；facade 仅保留两条活方法返回类型断言（现 `test_schedule_service_facade_delegation.py:29-33`）。后续禁再按旧删点施工，活近亲现为 `schedule_repo.py:36` / `:79`。
- **G06(R62)🟢 fixed**：2026-06-08 已按符号 `_resource_pair_payload`+`!=` 重盘执行；payload+dict+模板（`!=`副行 + title 改回 `_label`）+xlsx 四处同一原子 diff 闭合，并补 dict/xlsx/模板三类守卫。禁区已守住：未碰 `:58-236` adopted-only 护栏段，未删 state 层 latest_*/counterpart_* 真身份键。后续禁再按旧锚点重复施工。
- **G36(R37)🟢 fixed**：2026-06-08 已按符号删除 `list_links_with_machine_names` 死方法（旧锚 `operator_machine_repo.py:82-90`）；源码内该符号零命中。活近亲 `list_links_with_operator_info` 保留并上移到 `operator_machine_repo.py:82`，后续禁再按旧行号 `:82-90` 施工。

**不可碰清单（按符号）**：LB01 `:369-374/:381-382/:471-473`；R15 provider `if not text: return None` 空值短路 + support:228 raise；R19 `snapshot:42 return sorted`（事实承重）；R52 ReadyQueueContractError 抛错链 loud raise；R46 同名陷阱 `v4_sanitizers:37`；R12 `_copy:108`/`:84 过滤`/sort:114/max:262/出口 try-except；R55 `:385 None 回退`；R51 收口点 schedule_params/optimizer_config（只读）；R50 `import math:3`；G30 fixed 后 R34 活近亲 `schedule_repo.py:36` / `:79` + facade `:29-33`；STRICT-4 全程。

**收口行为差异检查项（None vs raise 反例逐条）**：
- R15：空值 `""→None`（保 provider 本地，非 raise）vs 坏值 `"not-a-date"→raise/可观测`（收口符号）——爆点 #7 的核心反例。
- R04：脏 op_id → 静默 skip[旧] vs ValidationError 上抛[收口后]；6 处 except 须全接住 ValidationError，漏一处即上抛炸链。
- R52：parity 只能断「均拒绝」（ReadyQueueContractError vs ValidationError 异常类不等价，禁断同类型）。
- R59：`'1.0'/1.0→1`[F1 前裸收口撞 `:247/:250` raise] vs `reject_integer_float=True` 委托[F1 后]。
- R62：三键恒等删行为等价（no-op），但 title 属性前后须逐字相等（漏改→`title=""`）。
- R12：全坏行 → `available=False` 分支须带 dropped_count（漏→最该报警处无信号）。

**批后门禁**：fitness 21 项全绿 + 0 分层违规（R52 收口 ready_queue→sgs_graph 不得越层/造环；R19 repo 收 service=data→service 越层禁）；语义雷达无新漂移；**v18/v19 DB CHECK 不破（R15/R17 改 event_time 解析 + 启动探针 `:349/355` 仍须被拒，专项验）**；本批专项契约：R04 6-except 全接 ValidationError 绿 + GF1 parity 绿、R15 三 required/optional parity（含空值）绿、R52 impl 保留 + 「我是故意的」注释（O07 方向 B，**不新建 test_sgs_graph_ready.py**；既有 `tests/scheduler_graph/test_ready_queue.py` 仍全绿、差分 oracle 注释到位）+ 异常「均拒绝」断言绿、R62 三套 parity 快照（dict/xlsx/模板含 title）绿、R12 dropped_count 穿白名单 + available=False 分支保键绿、R11/R63 已 fixed 后 normalize 11 边界绿。

**go-no-go 判据**：每个簇前置绿 + 该簇专项 parity 绿 + 活近亲 grep 在位 → 放行。R52/O07 已裁 KEEP：G39 只补注释，若出现删 impl、删 R25 垫片或新建 `test_sgs_graph_ready.py` → STOP。R15 收口若整体 delegate（未分支级保空值）→ STOP。（E16「__all__ 串行对账」已经红队第2轮 P-RT22-02 判为伪串行边降登记备查，不再作 R19 收口 go-no-go 门。）

**owner 裁后门控（照 §3/OWNER 执行）**：
- R55/O09：本轮不做，仅保留重启条件说明，不进入本批执行门。
- R34/O10：纯删；若未来改裁迁活孪生，才回升为 R05 后置前置。
- R15/O03：坏值 loud raise，合法空时间仍留本地 `return None`；R15/R19/O05 同批裁定已完成。

### 1.4 Batch-C — 身份族收敛 / 收口委托（依赖承重族 + parity）

**成员（调度单元 + 债）**：G04(R58→R54→R44)←LB03+R22parity；G01(R42+R60)←G04(E03)；G27(R22+R21，2026-06-08 已 fixed)←LB03+G27p；G09(R15→R19→R13，三者已 fixed)；G10(R18+R19 repo私有版，二者已 fixed)；G29(R72)🟢 fixed(2026-06-10)；G15(R47+R71)🟢 fixed(2026-06-10)；G22(R08+R09)🟢 fixed(2026-06-10)；G33(R05 步3)🟢 fixed(2026-06-10)；G34(R67)🟢 fixed(2026-06-10)；G17(R31)🟢 fixed(2026-06-10)；G23(R30+R33)🟢 fixed(2026-06-10)。

> **2026-06-08 执行补登**：G04(R58/R54/R44) 与 G01(R42/R60) 已 fixed，并已在 `_registry.json`、`_registry_index.json` 与对应 dossier 登记。G04 终态：R58 只补承重说明，不做 Phase2 剔键；R54 把五个 guard 投影面收口到既有 `build_workbench_plan_context` / `plan_guard_fields_for_context`，保留各自键面形状与 L5 OR；R44 收口到 core 的 `selected_plan_role`，不碰 guard 闸门。G01 终态：`plan_id` 死面包屑整链下线，`version/plan_role/scenario_id/back_to` 等真上下文键保留。
>
> **2026-06-08 G27 执行补登**：G27(R22/R21) 已 fixed。实盘侦察发现 G27p parity 证据不足，本次先补 `tests/schedule/summary/test_schedule_result_view_context.py::test_default_plan_resolution_identity_matches_canonical_no_history_identity`，用 `VALID_PLAN_ROLES` 逐值断言 `default_plan_resolution_dict(role)["plan_identity"] == build_plan_identity(...).to_dict()`，并钉住 no_history 的 `result_summary_parse_failed=True`。随后 R22 删除手写 `plan_identity` 字典，收口到既有 `build_plan_identity(...).to_dict()`，保留 `normalize_plan_role`，不改 builder / `PlanIdentity.to_dict`；O14 裁定的用户可见文案同步改为中性「本方案暂无排产摘要」。R21 仅删除 `gantt_plan_query.py` 的 `resolve_plan` / `selected_plan_role` / `_has_explicit_gantt_range` 三个死 shim 与专属 import，`default_plan_resolution_dict` wrapper、遗留 bad-role 文案和四个 LIVE range 函数均保留。

**是否原子**：身份族强原子——G04（R58→R54→R44 同 nav_publish 硬序）+ E03 硬同批带走 G01（R54→R42/R60 同符号 `build_workbench_plan_context` rebase）；G27（R22 先→R21 后同窗口）；G09（provider 链 R15→R19→R13 同文件串行 + 逐步重 rg）；G22（R08 先→R09 后串行）；G23（R33 步1→R30→R33 步2/3 硬序）；G33（R05 步1→步2→步3 不可换序）。

**为何这批**：集中所有「收口委托到真相源」+ 裁后身份/承重收敛；依赖 ROOT 的承重注释族 + parity 全绿。这是误删风险最高的批（6 承重文件多在此动手）。

**前置安全网（逐条点名，含全部相关标红债 + 硬阻断爆点）**：

> **2026-06-08 补充说明**：下方 G04/G01 的安全网条目现在作为执行前归档保留，用来解释为什么当时必须按这个顺序做；G04/G01 已 fixed，勿按这些 MUST 文字重复执行 R58/R54/R44/R42/R60。

- **G04(R58→R54→R44)🔴**（R54 标红 + 爆点 #1/#2/#3）：
  - **爆点 #1（硬阻断）**：collar `build_workbench_plan_context` 真宿主 **`web/viewmodels/scheduler_workbench_links.py:187`**（红队 RT1-P1-4/RT2-问题1 采纳订正宿主目录：`web/routes/domains/scheduler/` 下只有 `scheduler_analysis_links.py`，无 workbench_links；全计划凡引 collar 须带 `web/viewmodels/` 前缀，否则扩 collar 第一步即找不到文件——D1「prose 改了表没同步」残瑕第 5 处）。该 collar `:187-258` 当前**不产** is_comparison/is_superseded/is_current_executable 三 fail-open 键、无 plan_resolution 入参（实盘 grep 该三键 + plan_resolution 在该文件零命中，`plan_id:191` 形参在）→ 「5 套 delegate 到 collar」前 **MUST 先在 ROOT 把 collar 扩成 3 键 guard 产出点（fail-CLOSED 默认）**，裸 delegate=抹键 fail-OPEN 脏写历史现场（不可逆）。V3④裁选项 I（先扩产 + 过 owner 审，再 6 面 delegate）。
  - R54 五套手维面跨 5 文件 3 基数，**禁向 16 键看齐**（L3 的 15 键补 plan_role_status=统一改行为违承重红线）；分三组基数（L2/L4=16、L3=15、L1=12）各钉 parity 守卫；逐键四态 parity（缺失/None/False/True×拦放）。
  - **爆点 #2（第 6 手维面）**：`scheduler_resource_dispatch.py:40-73 _PUBLIC_FILTER_DROP_KEYS` 脱敏集（V3⑥裁定「同步面、禁 delegate」：独有 schedule_result_status:63/is_current_executable_version:69/scenario_name:72，误并=漏脱敏），R54 统一时禁当第 7 套 guard 去并。
  - **爆点 #3（L5 OR 兜底）**：`scheduler_gantt_task_detail.py:98 bool(get(is_comparison) or data.get(is_comparison_plan))`，收口源 view_context 函数重算不读原始键，统一丢回退→「源键 True 但函数重算 False」gantt 比较版 fail-OPEN。
  - **第二套 superseded/comparison 消费面**（V3 裁定「下游展示判定面、禁 delegate 禁合并」）键名变更须同步，展示侧 fail-OPEN 延伸。
  - R58 仅 `:91` 上方注释（本轮只注释，Phase2 剔单键须先补 preview-adopted+非adopted 两反例 parity、排 R54 后、owner 拍）；R44 排末位（重盘 `:6/:36-37`，仅动 import+删 def，方向反转 core 更防御）。
- **G01(R42+R60)🔴**（R42 标红 + 爆点 #21）：←G04（E03 硬同批，R54 先落 R42 rebase 新签名）；
  - **爆点 #21（硬阻断）**：删点清单 **MUST 补 `dashboard_workbench_context.py:92`** 与 `:191` 形参同提交（plan_id 落点迁同名不同文件，经 `:119 build_workbench_plan_context(**_context_kwargs)` 的 `**` 展开真实流入；删 :191 形参后 dashboard 启动即 TypeError 500）。V2⑫确认 TypeError 面=3 个显式传 plan_id 调用方（navigation_context:78、reports_workbench:79、dashboard_workbench_context:92），其余不传安全。**两锚区分（一致性 P3 防误读）：`navigation_context.py:78` 是 plan_id 读入/传参点（TypeError 面），与 `:79/:80`（R56/R57 已 fixed 的 fail-CLOSED 护栏禁区行，plan_role 强制 adopted，§3.2 方向硬门）性质不同、非同锚——:78 是删形参关心的调用点，:79/:80 是认账注释绝不可改方向的禁区，二者紧邻但勿混。**
  - emit `:118/154` 唯一归 R42 删（按符号删 plan_id 单行绝不连片，C1 emit 误删邻参→URL 丢 version）；R60 不重复删 emit；R42/R60 单次提交；parity 扩「删后 version/plan_role/scenario_id/back_to 逐字==删前」含 emit-A/emit-B 两 plan_style（contract 现状零断言三参=最大静默口）。
  - V2⑫终态删点清单：补 :92、剔 dashboard_workbench:121 与两幻觉 roadmap 行、含 emit:118/154 双 plan_style；R42⇔R60 单次提交 rebase 在 R54 后。
  - 爆点 #12（V2⑫）：`:57 navigation_context` 走 `**kwargs` 链全程 plan_id=0 命中→不含 plan_id，删 :191 形参对 :57 安全无 TypeError；co-change 只查真名 `build_workbench_plan_context`（**红队 RT3 噪音采纳：全仓零 `as n` 别名，原 D2「别名 `n(`」纪律是幻觉前提已删，全真名 import**）。**collar 调用方口径（一致性 P2 收口，以 verdict_V2 + RT22 备注统一）：共 8 个生产调用方文件**（navigation_context、dashboard_workbench_context、resource_dispatch、gantt_task_detail、reports_workbench、navigation_links、analysis_links + navigation_context.py 第二注入路径），**其中仅 3 个真传 plan_id**（navigation_context:78、reports_workbench:79、dashboard_workbench_context:92）会触 TypeError 面，其余 5 个不传 plan_id 删形参安全。删形参前 rg 全 8 调用方复核无遗漏真传点。
  - E03 补：collar 第 6 调用方 `analysis_links.py:24` 未传 plan_id（只读确认点，删形参安全）。
- **G27(R22+R21)🔴（2026-06-08 已 fixed，以下为执行纪律归档）**：←LB03+G27p；本次实盘补齐 24 键 exact + no_history 取值 parity 后，R22 已收口到 `build_plan_identity(...).to_dict()`，只 CALL 不改 builder；R21 已删 3 死 shim 与专属 import。**已复核保留** dpr_dict wrapper、`_default_plan_resolution_dict` import 别名、bad-role loud 文案、`normalize_plan_role`、builder / `PlanIdentity.to_dict`、以及四个 LIVE range 函数。
- **G09(R15→R19→R13)🟢 fixed**：同 provider.py 文件；**O03/O05/O06/O37 已裁串行序 R15→R19→R13**。2026-06-09 已完成 R15：`_parse_execution_time` 保合法空值本地 `None`，非空委托 `parse_operation_event_time`，坏值 loud raise；未整体 delegate、未改 support/state_builder。2026-06-09 已完成 R19：`execution_snapshot.positive_op_ids` 保 sorted 并补指纹排序注释，`execution_snapshot` 顶层 provider import 改局部 import防运行时环，`execution_fact_provider._positive_op_ids` 委托既有 `positive_op_ids`，provider missing 文案 parity 已锁定。2026-06-10 已完成 R13：owner 确认单机无仓库外读者后，先迁测试再删 `ExecutionFact.last_event_schedule_version/last_event_schedule_id`、`_fact_from_state` 的 `latest` 形参、两处旧字段赋值、调用点 `latest_events.get(scope)` 实参，并删除孤儿 `_latest_events_by_scope`。R13↔R18 解耦已守住（未碰 repo:400/402）。**E16 降为登记备查·无依赖（红队第2轮·2号 P-RT22-02 采纳）**：`__all__` 伪串行边不再作机器门，禁照旧 `:118-122` 锚点去 execution_snapshot.py 找 R01/R46 的导出条目。
- **G10(R18+R19 repo私有版)🟢 fixed**：R18 已独立补 repo stub 护栏注释（六格 stub raise 是契约护栏非死码，foundation 测试 :383/:385 断言 raise，禁直删/禁退断言/禁改 return {} 静默）；R19 repo 处已按 O04 保私有版补「顺序无关」注释和 parity，未下沉 service；R13 不碰 repo，R13 只在 G09 provider 殿后处理。G10 已收口。
- **G22(R08+R09)🟢 fixed(2026-06-10)**（R09 标红 + 爆点 #12/#13）：已按硬序收口——N1 守卫(E26)先落→R08 候选 A(删死常量+两死分支,保 feedback_write_enabled 参数,可达组合 parity 先行)→R09 收编 A/B 两副本为 scope.py:9 薄 wrap(C 路同形态,两路 parity:合法面零漂移+严格面 5.9/3.0/True→None,O01);STRICT-4 与 scope:36-50 未碰,persistence_errors:13 归 R04 未卷入(O02);爆点 #12 audit=脏值塌 0 为无效哨兵较旧截断误命中更安全。原前置说明:←N1 注释(E26，先钉 service:127≡:130 同源守卫)+R07 前置(E25 已满足)；
  - **R09/O01 已裁 C 严格**；收编**只动 A/B 两 Optional 副本收口到 scope.py:9，C 保持不动**；STRICT-4 一字不碰（§3.1 family 对照，全仓 **12 处**同名异义函数极易误删 STRICT 当重复）。
  - 分两路 parity：test_AB 零漂移 + test_C_float_bool 钉 5.9/3.0/True（C 严格 5.9→None vs A/B 宽松 5.9→5）。
  - 爆点 #12：B 副本 `:257/:258 _positive_int(...) or 0` 外层兜底——若收口到 scope 严格版（catch→None），`5.9` 由 `int→5` 变 `None or 0=0`，op_id 塌成 0 注入 task_card（另一条坏数据流，须审计）。
  - 爆点 #13（V1⑤/O02 裁定）：`persistence_errors:13` 归 **R04 禁区**不归 R09 收编面（按 R09 收编它会违 R04 灵魂线在错误路径抛二次异常）；保持现状+注释。
  - **连带（V1）**：R09 收编串行链真正待收编 Optional 副本只剩 `resource_dispatch_execution_service.py:24` + `scheduler_resource_dispatch_execution.py viewmodel:33`。
  - E28：R09 收编**禁碰同文件 `:36-50` LB01 最终底**（删空行/调 import/移函数都漂 raise 锚点，按符号定位）；R08 候选 A 只删 `:25/:227-228/:367-368` 保 `feedback_write_enabled` 参数（`:234` 活消费，误删→「填写实际」按钮门禁塌缩静默放开误填）；R08→R09 串行。
- **G33(R05 步3)🟢 fixed(2026-06-10)**（R05 标红 + 爆点 #19/#20，步1/2 已在 ROOT fae8829b）：已按硬序收口——repo `list_dispatch_rows` 五个内联 where 分支全部替换为 `normalize_dispatch_resource_filter` 委托（team 双 join/空 id 全量逐分支等价），`build_schedule_detail_sql` 的 `include_team_context` 保持无条件 True 不随 filter 收窄（防爆点 #19 no such column）并留注释；`_normalize_scope_type` 合法集收敛到 `SUPPORTED_DISPATCH_RESOURCE_TYPES`（保默认 operator+中文文案+field，续命直调测试零改动）。行为差异=两类严格化：非法 scope_type 与「空 type+非空 id」均由静默全量变 loud ValidationError（生产入口先归一/默认 operator，均不可达）。smoke team 活用例/五 parity/resource_dispatch 整包 136 passed。
- **G15(R47+R71)🟢 fixed(2026-06-10)**：G15a/LB07 注释+三 helper 等价 parity 已随 fae8829b 落地(O17 前置满足)；R47 已按调用函数名逐块手删六死点(2 形参+4 死实参,invalid 路 4 活实参与 collector.add 降级记录全保)；R71 按 O17 仅 parity 守卫结案、双栈不物理合并。原执行纪律归档：**R47 按调用函数名逐块手删**（只删 model:88/:159/:214+service:68/:158/:211 死点，爆点 #10：死参活参 `raw_value=raw_value` 全栈 8 处逐字相同，盲 grep/sed 必误删 `_record_invalid_choice_degradation` 活参 :116/:119→invalid 降级证据静默丢，blank parity 测试不覆盖 invalid 路）；删后跑 blank+invalid 两路 degradation 回归；R71 改 loud 另立债。
- **G34(R67)🟢 fixed(2026-06-10)**：①②已收编为遍历收口点新常量 REPORT_RESOURCE_FILTER_ARG_KEYS+常量↔签名契约；③④按 O18 保现状仅注释（两 superset 不同形禁互抄）；收口点签名未动；E17 走 (a) 零冲突分支。原执行纪律归档：①②纯 6 键必收（喂收口点零新增依赖）；O18 已裁第 4 处保现状，③④保持现状/仅注释；禁动收口点签名 `:119-127`。**R67↔R42 同文件串行（E17 拆两条件分支，红队第2轮 P-RT22-04 采纳）**：(a)「O18=保现状/仅注释 → R67↔R42 零冲突，无需串行」；(b)历史备选「若未来收编③④ → R67 对 `_REPORT_CONTEXT_FIELD_NAMES` 做元组拼接（`(...前缀键..., *REPORT_RESOURCE_FILTER_ARG_KEYS)`，R67.md:46/76），该元组**首键 `plan_id` 是 R42 地盘**——拼接 MUST 晚于 R42 删 collar 形参之后、**禁碰元组内 `plan_id` 成员**、且 **MUST 先过 `web.viewmodels → core.services.report` 分层门**」。本文件归「三批四单元串行编排块」（见 §1.0 ⚠单文件三批四单元串行块总纲），G34 进该文件前对元组/遍历点按符号重 rg。
- **G29(R72)🟢 fixed(2026-06-10)**：已按 O19 执行——公开名 get_plan_role_arg 落 web scheduler_utils.py(已补 request import)，gantt/week_plan 删副本改共享，空串→None 零变化无 ROLE_ADOPTED 兜底，守卫测试新建并双注册；分层红线守住未下沉 core。
- **G17(R31)+G23(R30+R33)🟢 fixed(2026-06-10)**：已按硬序收口——G23 一个 commit 内原子完成 R33 步1（两测试 import 迁 core.shared）→R30（删 shared date 切片+三常量）→R33 步2/3（git rm 三壳+退 config_contract 断言，死保 degradation 条目）；G17 紧随的下一 commit 删 shared 源 WRITE_INTERNAL_ONLY（壳先于源满足，全仓零残留）；degradation:15、core.shared 禁区、float/int 禁误删区全守；双轨对抗审核零阻塞。原执行纪律归档：E05/E06 硬序 **R33 步1（迁两测试 import）→R30（删 shared 实现 + 三 FieldPolicy + 三常量）→R33 步2/3（删壳 + `:411` 断言）**；R31 不晚于 R33（A14 方向修正：壳 import 源，先删壳 R33 再删源 R31，否则 facade:11 残 import loud ImportError）；**死保 degradation:15**（V4②裁定：无论叫壳叫实现都死保，config_contract:15 不动，删元组只动 `:14/:16/:19`）；绝不碰 core.shared 三模块全文。

**不可碰清单（按符号，6 承重文件集中区）**：
- operation_execution_scope.py：`:9` 收口家本体 + `:36-50` LB01 最终底（三 raise :44/:47/:50）全禁碰。
- R54 禁区：links.py `:292-296` 判定方向 / `:149-161` gate / `:248` / `:469-473` / view_context fail-closed 默认；`_PUBLIC_FILTER_DROP_KEYS`（禁 delegate）。
- R22/R21 禁区：view_context `:74`/`:65` + builder:158 + to_dict:46-71 + gantt_plan_query `:32-39 wrapper`/`:11-13 import`/`:50-156` 四 LIVE。
- R09 STRICT-4 全程；R15 provider 空值短路 + R19 snapshot:42 sorted；R18 repo 六格 unscoped stub（2026-06-10 注释后现盘 :356/:358/:402-:408）；R13 provider raise 软禁区（2026-06-10 现盘 :93/:96，旧 :99/:102）；R05 旧 collar raise 双轨 + `_normalize_team_axis`(展示轴) + team 双 join 谓词(2026-06-10 步3 后已收敛进 collar :120-124，repo 内联 :461-463 已退场)；R47 invalid 4 活实参 model:173/:225+service:170/:222；LB07 coercion :470/loud raise 族/30 字段表；R31 :6/:7/:8 活常量；degradation:15。
- R42 禁区：link_query :117/119/120+:153/155 三真身份参、navigation_context:79/80（R56 adopted 强制 fail-CLOSED 方向硬门）、:7 TARGET_PAGE_PATHS、workbench_links.py:210 LIVE _context_summary、三张字段表非 plan_id 键、`_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS:266`。

**收口行为差异检查项（None vs raise 反例逐条）**：
- R54：5 套 delegate 前后逐键四态（缺失/None/False/True）拦放一致；L5 「is_comparison_plan=True 但函数重算=False」反例必拦（爆点 #3）；reports 第二注入路径丢 3 阻断态反例必拦。
- R42：删 :191 形参后 dashboard_workbench_context:92 启动不 TypeError（爆点 #21）；version/plan_role/scenario_id/back_to 逐字==删前。
- R22：no_history result_summary_parse_failed False[旧] vs True[收口后]（owner 取向）；bad-role 抛 field=plan_role（保）。
- R09：C 路 5.9→None（严格保）vs A/B 5.9→5（宽松，owner 取向）；B 副本 5.9→None or 0=0（塌 0 坏流，爆点 #12）。
- R15：空值→None（provider 本地）vs 坏值→raise/可观测；R19 sorted 保（sha256 指纹，2026-06-09 已 fixed）。
- R05：team-only 谓词在 / 空 id 全量（非 raise）/ team 空全量（非 raise）/ bad raise。

**批后门禁**：fitness 21 项全绿 + **0 分层违规（R29/R72 core→flask 禁、R05 collar model→data 禁造环、R19 repo data→service 越层禁、LB04 导入环禁）**；语义雷达 `.codestable/semantics/` 无新漂移（R54 三基数键、R22 plan_role、R09 op_id 语义均为雷达盯防概念，收敛后须降漂移不升）；v18/v19 DB CHECK 不破（R22 收口 no_history 翻转 DB 层不兜底须验注释覆盖；R09 op_id 收编不撼 OperationExecutionEvents CHECK）；本批专项契约：R54 三基数分组 parity + 第 6 手维面同步 + L5 OR 兜底反例全绿、R42 删点含 :92 + 四参逐字 parity 绿、R22 键集+取值 exact + bad-role raise 绿、R09 双路 parity（AB 零漂移 + C float/bool）绿、R05 五 parity + smoke:177-194 绿、R47 blank+invalid 两路 degradation 绿、R19 positive_op_ids 黄金用例绿（E16 __all__ 对账已降伪串行边备查，非门）、R13 退场同原子已完成且删后无 TypeError、R33 facade 三步删序后 regression_config_service_component_contract 绿。

**go-no-go 判据**：
- 身份族（G04→G01/G27）：collar 已扩 3 键（ROOT 闸门绿）+ R54 三基数 parity 绿 + R42 :92 删点在清单 + R22 取值/bad-role 断言绿 → 放行；任一缺 → STOP。
- provider 链（G09）：O03/O05/O06/O37 已裁且已执行。R15/R19/R13 均 fixed；R13 已经 owner 确认并完成退场同原子（形参 + 实参 + 字段 + 孤儿 helper），且未碰 repo stub。
- 注：R13 registry 中 `owner_pending=false` 表示 O06 已裁“先迁测试后删”的方向；2026-06-10 owner 已补确认单机无仓库外读者，R13 已按该路线执行。
- R09（G22）：O01/O02 已裁，C 严格 vs A/B 宽松 + STRICT-4 grep 确认未动 + 两路 parity 绿 → 放行。
- R05（G33 步3）：collar 已扩（步1/2 ROOT 绿）→ 放行步3；collar 未扩 → 步3 STOP（裸搬谓词消失）。

**owner 裁后门控（照 §3/OWNER 执行）**：R54 collar 形态 F门-1/2/3；R22 no_history 取值取向；R09 C 严格 vs A/B 宽松（+ persistence_errors:13 归 R04）；R15 坏值 loud raise已 fixed，R19 sorted/provider/repo parity 已 fixed，R13 已 owner 补确认并 fixed；R71 仅 parity；R67 第 4 处 superset 保现状；R72 web/core 各落各点 + request import；R34 纯删（若未来迁活孪生才排 R05 后）；R47/R71 同批执行。

### 1.5 Batch-D — facade 删除最晚 / 跨 owner-pending 收口

**成员（调度单元 + 债）**：G18(R26 顶层 5 shim 删)🟢 fixed(2026-06-10，与 R43 同窗)；G26(R29 KEEP 注释，O20 已裁保留)；G41(R14 删死门)🟢 fixed(2026-06-10)；G42(R24 KEEP 注释 + 事实记录，O23 已裁保留不删)。**+ 需门控的 LEAF-DUP-P4 残余**（按 ⚠简化声明归入此批，随各自 owner 门落）：R69🟢、R03🟢、R41🟢、R68🟢、R32🟢、R40🟢、R43🟢——**七债已全部于 2026-06-10 按 O24-O29 裁定收口 fixed**。

**是否原子**：G18 单文件三步迁移须同窗口；G41/G42 各自独立可并行；R69 两份 `_op_seq` 原子同改；R43↔R26 共碰 scheduler_config.py+SP05 串行。

**为何这批**：facade 删除是全局最晚（脊梁第 4 步）——R26（G18）须晚于 R29/R33/R52 三桶收敛（E07/E08/E09 硬前置）；R14/R24 牵动灵魂线 + roadmap 调和，前置最重；LEAF 残余债的 owner 设计裁断（loud vs 降级）多在此收口。

> **⚠本批重 rg 纪律（C5 逐批落地）**：Batch-D 在 ROOT/A/B/C 全部删改之后落地，**前面四批的位移已层层叠加**，本批所有裸行号（R69 两份 `_op_seq`、R26 ~93 处重指基数 / SP05 段、R14 `:328`/`:358`、R43 `:522`/22 文件迁移点）一律失真，执行前对每个锚点按符号重 rg。**本批高危锚点符号清单（执行前 rg 现场定位，弃裸行号）**：R69 `_op_seq`（guard/runtime 两份 def + 三消费，禁碰 `_seed_seq`/`_seed_op_id`）、R14 `_resolve_strict_plan`（撞 LB01）/`resolve_existing_plan`、R26 顶层 5 shim + SP05 `BEHAVIOR_*` 段、R29 `regression_number_utils_facade_delegates_strict_parse`、R41 全 6 枚举族 `*_source_zh`/`*_merge_mode_zh`、R24 `safe_int`/`safe_float`/`NonFiniteDiagnosticNumber`。

**前置安全网（逐条点名，含标红债 R14/R69）**：
- **G18(R26)🟡**：晚于 R29(G26)/R33(G23)/R52(G39) 三桶收敛（E07/E08/E09）+ E10 软自 G15；迁 2 离线消费者（tools:17/audit:87 手动验证清单，CI 不跑=延迟暴露）；改 SP05 BEHAVIOR_* 两字典（:20-31/:33-82）非 STRONG_*，`:638` 第二处不碰；重指基数用 ~93 处/53 文件（非旧值 71）；R26↔R01/R43 SP05 同文件串行各改各段（E11）。
- **G26(R29)🟡**：**O20 已裁 KEEP + 显性「有意保留」注释**，不阻塞 G18；不走薄壳化，不改 2 活消费者 `excel_validators:26`/`scheduler_excel_calendar_rows:8`。历史 B 薄壳化路线（重写 monkeypatch、改活消费者）本轮作废。
- **G41(R14)🔴⏸**（R14 标红）：←LB01 承重裁断先行（E13，`:134-139` 让位，撞 LB01 同符号 `_resolve_strict_plan`）；三步前置（迁灵魂线测试 / 改 roadmap:485-498+items.yaml:83 / 确认无树外调用）；**owner 裁 `:328` 候选灵魂线改钉 resolve_existing_plan 层禁平移活门 diagnose**（活门走 resolve_plan fallback_to_adopted 静默不 raise→「非 scenario 缺角色应 raise」灵魂线被悄丢）；`:358 scenario` 灵魂线两门同源可平移；**删死门不得顺手修 resolve_plan 静默回退（铁律 4）**。
- **G42(R24)🟡**：**O23 已改裁保留不删**——core 预留件留作「诊断回归 core 契约层」未来地基，只补「故意保留」注释 + 事实记录 `.codestable/compound/2026-06-05-decision-r24-diagnostic-contract-keep.md`；不删 core 文件，不剪测试，不调和 networkx roadmap，PR-9 roadmap 引用保留不动。路 B（改活 web 路径指零消费 core 合同）仍违铁律 5，绝不执行；**绝不反删 web 孪生护栏**；‖ G41 可并行。
- **R69🔴⏸**（标红 + 爆点 #15，V5⑨裁定）：O24 已裁 loud raise；收口家 `schedule_input_contracts.py` 已确认无环；**两份 `_op_seq`（guard:49/runtime:19 def + guard:206/212/runtime:216 三消费）原子同改**；parity 两份同钉 `seq=0/None→走短路不 raise`（合法）+ `seq="abc"→loud raise`（坏类型）；**loud 只动 except 域，`or 0` 兜的 None/0/空串绝不卷入**（爆点 #15：`completed_seq<=0` 合法短路，卷入 raise→双热路径可用性放大）；**禁碰 `_seed_seq:190`/`_seed_op_id:175` 及 runtime:261-262**（V5⑨：`:262` 是 `_seed_seq` 张冠李戴非 R69）。
- **R03⏸**（四态 parity）：(A) 承重注释段安全随 ROOT（`:216` 上方禁碰 `:28/:216/:217`）；(B) 段 owner 裁 ScheduleCandidate.status 枚举契约前禁动，先建 None/missing/failed/completed 四态 parity，**missing 态 `:267 return True` 生产可达保留 + 补不可达注释**（下游 6 处消费 dashboard_workbench:156 等，非 1 处，爆点）；绝不裸删 6 消费点。
- **R41🟡⏸**（爆点 ⑧/V5⑧）：排 ROOT/Batch-A 之交的 LB04 安全网之后；**改面是全 6 枚举族**（machine/operator/day_type/batch_status/priority/ready+process_bp 的 _source_zh/_merge_mode_zh，经 *_bp 薄壳扇出 13+ 页面），非 2 文件；**5 族可收口到 `enum_normalizers.py` 已存在 *_label，`batch_status_zh` 无 canonical 收口点必留私有**（强建 batch_status_label=新 P5 违铁律 5，禁）；owner ≥6 处裁断硬门；测试 `test_enum_display_consistency.py:18/19/25/26/59-61` 改 loud 暴露**禁贴回收口输出复活静默**。
- **R68/R32/R40🟡⏸**：R68 parity 先于收敛，逐符号删禁碰 downtime `_meta_int_state:23`，禁压扁 `(bool,parse_failed)` 二元组；R32 owner 裁硬 raise vs 可观测降级（禁区 `:339 else raise 不改弱`/`:343 os.replace 不加二次兜底`/finally 保留，强制回归项=else 未被连带改弱）；R40 方向 A 只删 material_repo `:70-72` 保 `:69 float`（生产 service `_norm_float` 已拦改 raise 零行为影响），方向 B 引 core.ValidationError 造 data→core 耦合不推荐，owner 裁错误分类。
- **R43🟡⏸**：owner 认账 roadmap 延期决定（`:522` 非污染值 521，F门 verify 已纠）；删 9 wrapper + compat + 清 scheduler_config.py:95 软 fallback；迁 22 文件（19 plain+3 契约）；R43↔R26 共碰 scheduler_config.py+SP05 串行。

**不可碰清单（按符号）**：R14 `_resolve_strict_plan`（撞 LB01）+ `:358 scenario` 灵魂线 + resolve_plan 静默回退（禁顺手修）；R24 web 孪生 NonFiniteDiagnosticNumber/safe_int/safe_float；R69 `_seed_seq:190`/`_seed_op_id:175`/runtime:261-262 + `or 0` 合法路径；R03 CandidateTrialFailure:28/except:216/_failed_plan:217 + 6 消费点；R41 `batch_status_zh`（保留私有）+ test 静默断言禁贴回；R68 downtime `_meta_int_state:23`；R32 `:339 else raise`/`:343 os.replace`；R40 `:69 float`；R26 SP05 `:638` 第二处 + STRONG_*；R29 STRICT-4（number_utils 收口家不撼 raise）。

**收口行为差异检查项（None vs raise 反例逐条）**：
- R14：非 scenario 缺角色 → raise[灵魂线，保]vs fallback_to_adopted 静默[活门 diagnose，禁平移]。
- R69：seq=0/None → 短路不 raise[合法]vs seq="abc" → loud raise[坏类型]；except 域外的 `or 0` 路径绝不卷入。
- R24：O23 已裁 KEEP，历史“路 A 删 core”作废；本轮只补注释+事实记录，路 B 改活 web 路径仍禁。
- R03：missing 态 `:267 return True` 生产可达保留 vs failed 态不可达收敛。
- R41：ready 空串「未齐套」→「齐套」反转（最危险，调度员误放行）/ operator「停用/休假」→「停用」丢休假 / unknown 透传→「未知」丢值——owner 逐项裁。
- R40：service `_norm_float` 已 raise（拦在前），data 层 `:70-72` 删后零行为影响。

**批后门禁**：fitness 21 项全绿 + 0 分层违规（R24 路 B core→web 越层禁、R40 方向 B data→core 耦合不推荐）；语义雷达无新漂移（R41 枚举族 zh-label、R03 baseline 态、R69 seq 语义均盯防概念）；v18/v19 不破；本批专项契约：R69 两份 parity（seq=0/None 不 raise + seq=abc raise）绿、R03 四态 parity 绿、R41 全 6 族×5 类 parity + 测试 loud 暴露绿、R26 SP05 BEHAVIOR_* 迁移 + 2 离线消费者手验绿、R14 灵魂线测试迁移后 resolve 行为绿、R24 仅 KEEP 注释 + 事实记录且 web 孪生护栏在位。

**go-no-go 判据**：
- R26（G18）：R29/R33/R52 三桶已收敛 + 2 离线消费者已迁手验 → 放行；任一桶未收敛 → STOP（facade 不可早删）。
- R14（G41）：LB01 承重裁断已落 + O21/O22 钉层 + 三步前置齐 → 放行；任一前置缺失 → STOP。
- R69：owner 已定 loud vs 降级方向 + 两份 parity 绿 → 放行。
- R41：LB04 安全网（ROOT/Batch-A 之交）已落 + owner ≥6 裁断已回 + 测试改 loud 不贴回 → 放行。

**owner 裁后门控（照 §3/OWNER 执行）**：R14 按 O21/O22 钉 resolve_existing_plan 层，`:358` 可平移；R69/O24 loud raise；R03/O25 missing 态保留；R41/O26 第三选项 C；R32/O27 硬 raise；R40/O28 方向 A；R43/O29 认账提前删。R29/O20 与 R24/O23 走 KEEP。

---

## 2. 11 条标红债专项处置

> 11 条 = R09 / R15 / R19 / R52 / R14 / R69 / R54 / R04 / R42 / R22 / R05（_layer3_explosion §二.1）。每条：灾难链 / 旧计划为何会炸 / 修正后安全路径（分步）/ owner 闸门。所有 file:line 执行时按符号重 rg。

### R09（PARSE-INT，Batch-C/G22，5 透镜全红，最高置信）
- **灾难链**：A/B 副本 `int(value)`（5.9→5/True→1）vs C 收口点 STRICT（5.9→None/True→None）；按「字节对齐 A/B」新建宽松 sink 把 C 一并收口→C 经用户输入路径（request.args schedule_id）放宽→5.9 当 op_id=5 进 `_row_matches_feedback_target` 误命中相邻行→现场记录静默写到错任务。
- **旧计划为何炸**：旧 MASTER-PLAN「唯一批准新建 parse_optional_positive_int」——收口点其实**已存在**（scope.py:9，执行重构新建 loud raise），照旧建模块 + 字节对齐 A/B 会把 C 路严格语义静默放宽。
- **修正安全路径**：① O01/O02 已裁：C 路保持严格，A/B 两 Optional 副本按宽松语义收编；② 收编**只动 A/B 两 Optional 副本**（viewmodel:33 + service:24）收口到 scope.py:9，C 不动；③ STRICT-4（scope:9/feedback_support:161/public_errors:167/auto_assign:114）一字不碰（§3.1 family，全仓 12 处同前缀同名异义）；④ 分两路 parity（test_AB 零漂移 + test_C_float_bool 钉 5.9/3.0/True）；⑤ B 副本 `or 0` 外层兜底审计（5.9→None or 0=0 塌 0 坏流，爆点 #12）；⑥ persistence_errors:13 归 R04 禁区不收编（V1⑤/O02）；⑦ 禁碰同文件 :36-50 LB01 最终底（E28）；⑧ 强串行 R07/R08 后重 grep。
- **`_positive_int` family 实盘对照表（红队第1轮 RT1-P2-6 采纳·G22 收编前先逐行核返回类型，杜绝按裸 `_positive_int` 全局替换）**：`rg "def _positive_int"` 实盘 12 处同前缀，**收编只动 `-> Optional[int]` 的 A/B 两份，STRICT `-> int` 四份一字不碰**——
  | # | file:line | 返回类型 | 分类 | 动作 |
  |---|---|---|---|---|
  | 1 | `scheduler_resource_dispatch_execution_context.py:28` | `Optional[int]` | Optional | （B 副本面之一，按 V1 口径核） |
  | 2 | `scheduler_resource_dispatch_execution.py（viewmodel）:33` | `Optional[int]` | Optional-**B 收口** | 收编→scope.py:9 |
  | 3 | `operation_execution_scope_read.py:21` | `Optional[int]` | Optional | （按 V1 口径核） |
  | 4 | `resource_dispatch_execution_service.py:24` | `Optional[int]` | Optional-**A 收口** | 收编→scope.py:9 |
  | 5 | `schedule_persistence_errors.py:13` | `Optional[int]` | Optional-**第3份** | **归 R04 禁区不收编（V1⑤）** |
  | 6 | `scheduler_public_errors.py:167` | `int` | **STRICT-4** | 一字不碰 |
  | 7 | `auto_assign_resource_errors.py:114` | `int` | **STRICT-4**（→0 哨兵，V1⑥） | 一字不碰 |
  | 8 | `operation_execution_scope.py:9` | `int` | **STRICT-4·收口家本体** | 一字不碰（收口目标，扩非删） |
  | 9 | `operation_execution_feedback_support.py:161` | `int` | **STRICT-4** | 一字不碰 |
  | 10-12 | `_positive_int_set`×3 / `_positive_int_text`×1 / data_contract `_positive_int(value, field_name)` 同名异签 | 异签 | 异签族 | 不卷入收编 |
  执行前对每行 `-> Optional[int]` vs `-> int` 现场重核，**真正待收编只剩 #2 viewmodel:33 + #4 service:24 两份**（V1 连带口径），其余全禁。
- **owner 裁后门控**：O01 保 C 严格、A/B 宽松；O02 persistence_errors:13 归 R04 禁区 + 注释。

### R15（EXEC-FACT，Batch-B/G08 + Batch-C/G09，r1×3+r2×2 红）
- **灾难链**：provider:85-95 空→None（合法 optional）+ 坏→None（P4 残留）双静默；收口符号 `parse_operation_event_time` **空值也 raise**→整体 delegate 把「任务未开始」合法空时间炸 raise→`_fact_from_state:52/53` 内联 kwarg 构造、facts_by_scope 链全程**裸奔无 except**→正常读历史计划 500 / 上层吞掉则执行事实全空喂重排。
- **旧计划为何炸**：旧计划写「区分空值→None vs 坏值→raise」，但没意识到收口符号 `:80` **空值本身就 raise**（爆点 #7 比计划口径更狠一层）；整体 delegate 会把合法空时间也炸。
- **修正安全路径**：① 收口必**分支级**——`if not text: return None` 留在 provider 本地，仅坏值走收口符号；② 坏值方向 loud raise（须确认 `_fact_from_state` 裸奔链接得住）或可观测降级标记，禁更深 return None；③ 先补三处 required/optional parity（含空值分支断言）；④ 启动探针 `migration_operation_execution_contract.py:349/355` 喂 not-a-date 边界须不冲突（爆点 #8）；⑤ provider 链串行序 R15→R19→R13（V1①）。
- **owner 裁后门控**：O03 已裁坏值 loud raise、合法空时间仍 `return None`，且 R15 已 fixed；O05/O37 已裁 provider 链当前顺序为 R15 fixed → R19 fixed → R13 fixed。

### R19（EXEC-FACT，Batch-B/C 三处 G08/G09/G10，多轮红）
- **灾难链**：snapshot:42 `return sorted(out)` 喂 :80→:93 sha256 指纹（事实承重）；naive「三处统一到不排序版」或让 snapshot 走不排序→同输入 sha256 漂移→下游 4 处 guard/publish/scenario 快照比对静默失真；repo 收 service=data→service 越层，provider 环已通过 snapshot 局部 import 消解。
- **旧计划为何炸**：旧计划把三份 `_normalize`/排序视作「重复可统一」，统一到不排序版即静默漂移指纹，且无单测拦截。
- **修正安全路径**：① canonical 强制 sorted + 「指纹依赖排序」注释（等同承重待遇，爆点 #9）；② provider 收口同层（收 sorted 后 missing[0] 文案变须 parity 断言,现盘 :128）；③ repo 保私有版补「顺序无关」注释禁下沉（避越层）；④ 先补 positive_op_ids 黄金用例（F-fingerprint 门）；⑤ **E16 是伪串行边，降登记备查（红队第2轮 P-RT22-02）**——R19 的 `__all__` = `execution_snapshot.py:123/:127`（`:127 positive_op_ids`），与 R01（`schedule_payload_contract.py:410`）、R46（`core/models/scheduler_public_errors.py` 根本不动 `__all__`）物理零重叠，三债顺序无关，无须串行对账。
- **owner 裁后门控**：O04 repo 保私有版 + 注释，避越层/环；O05 与 R15 同批裁。
- **2026-06-09 执行补登**：R19 已 fixed。snapshot 保 sorted 并补指纹排序注释；provider 收口到既有 `positive_op_ids` 前，先把 snapshot 顶层 provider import 改成函数内局部 import 防运行时环；repo 保私有版并补顺序无关注释/parity；未新建模块、未让 data→service。

### R52（GRAPH-ERR-DIAG，Batch-B/G39，r1×3+r2×2 全红）
- **灾难链**：裸删 impl `core/algorithms/greedy/dispatch/ready_queue.py:103 get_ready_operation_ids`→R25 垫片 `core/services/scheduler/graph/ready_queue.py` import ImportError→`tests/scheduler_graph/test_ready_queue.py` 整文件 **31 用例**蒸发（dossier「~23」失真）+ LIVE ValidationError 契约按 `test_graph_ready_state_*` 符号重 rg + `_full_scan_ready_ids:81` helper 一并炸→LIVE sgs_graph 行为覆盖一次性清零。**（红队第1轮 RT1-P0-2/RT2-问题3 采纳补全前缀：仓内两份同名 ready_queue.py——impl=`core/algorithms/greedy/dispatch/`、R25 垫片=`core/services/scheduler/graph/`，垫片补注释后 13 行，`:103` 越界；裸写 `ready_queue.py:103` 会在垫片上找 `:103` 致 Edit old_string 必失配或删错文件，删点须文件+行号+符号三锁定）。**
- **旧计划为何炸**：dossier「~23 LIVE-only」方向倒置（V4⑦：实测 31 用例，23 个走全量版 `_ready()`→`get_ready_operation_ids` 删即全断含 16 个 ReadyQueueContractError 合同，红队 RT3-P03 纠实盘=16 非 15），迁移方案没安排这些归属。
- **爆点编号说明（一致性 P3 收口·#17 去向）**：`_layer3_explosion §三` 23 爆点中 **#17 = 「R52 dossier『~23 测试』严重失真」（迁移清单 18 用例无归属）**，是本条 R52 的同源子爆点，与 **#16（`_full_scan_ready_ids:81` helper 二次爆点）紧邻并同属 R52 测试迁移战场**；本计划正文以「31 用例全量分流 + 16 RQErr 合同 + #16 helper/oracle 同原子」一并闭合 #16/#17，#17 未单独点名是因已并入 R52 测试归属安全路径（②③），非跳号漏引。全计划「23 爆点」编号 #1–#23 连续无缺号。
- **修正安全路径**：① **✅ O07 已裁方向 B**（保留 impl 作差分校验尺子 + 「我是故意的」注释，禁裸留无注释）——impl `core/algorithms/greedy/dispatch/ready_queue.py:103` 与 R25 垫片均不删、**不新建 `test_sgs_graph_ready.py`**，既有 `tests/scheduler_graph/test_ready_queue.py` 原样存活，P7 rule①② 不适用；② 〔作废·方向 A 不执行〕曾拟走 A 先新建 `test_sgs_graph_ready.py` 按 31 用例全量分流（LIVE→新文件、full_scan 差分→改字面量 + 删 `_full_scan_ready_ids` helper、ReadyQueueContractError 全量合同 owner 显式裁归属）；③ 爆点 #16：删 `_full_scan_ready_ids` helper 与改 **2 个差分 oracle 函数**（当前 `:273 branch_join` 4 字面量 `:278/:281/:284/:287` + `:290 fixed_predecessor` 1 字面量 `:299` = 共 **5 处字面量行**，权威 verdict_V4；旧数量表述误记）的字面量同原子；④ parity 异常类不同只能断「均拒绝」禁断同类型；⑤ None 分支两路分别写；⑥ 同提交退 lazy_runtime:29+metrics_topology:142；⑦ 契约行号按符号重定位。
- **owner 裁后门控**：O07 已裁 B 保留作差分 oracle；方向 A 删除路线只作历史技术分析，不执行。

### R14（GRAPH-ERR-DIAG，Batch-D/G41，r1-LB/LAY 红 + 双门已裁）
- **灾难链**：删死门 `_resolve_strict_plan:134`（非 scenario 走 resolve_existing_plan loud raise「无回退」）；把 `:328` 候选灵魂线平移活门 diagnose（活门走 resolve_plan fallback_to_adopted 静默不 raise）→解析被 fallback 吃→「非 scenario 缺角色应 raise（无静默回退）」灵魂线覆盖被悄丢；撞 LB01 同符号承重。
- **旧计划为何炸**：旧计划当作普通死门删除，没看到平移 :328 到活门会让灵魂线被 fallback 静默吞，且撞 LB01 同符号。
- **修正安全路径**：① 跨簇 LB01 承重裁断先行（E13，:134-139 让位）；② owner 裁 `:328` 改钉 resolve_existing_plan 层**禁平移活门**；③ `:358 scenario` 灵魂线两门同源可平移；④ 删死门不得顺手修 resolve_plan 静默回退（铁律 4）；⑤ 三步前置（迁灵魂线测试 / 改 roadmap:485-498+items.yaml:83 / 确认无树外调用）。
- **owner 裁后门控**：O21/O22 已裁按 resolve_existing_plan 层钉住 `:328`，灵魂线两门按裁定处理。

### R69（LEAF-DUP-P4，Batch-D/15，r1×3+r2-SOUL 红，V5⑨拍定）
- **灾难链**：坏 seq 静默 return 0（persistence_guard:49+runtime_support:19 两份）；P4 改 loud 若粗暴把 `seq=0/None`（合法默认，`int(getattr(op,"seq",0) or 0)` 兜）也卷入 raise→guard:207/:212+runtime:217 把 seq=0 当合法短路（放空/排除非错误）翻成 `_completed_downstream_rows`+`_downstream_operations` 双热路径 raise 可用性放大。
- **旧计划为何炸**：「P4 一律改 loud」会把 `or 0` 兜的合法 seq=0/None 短路也卷入 raise；且 dossier 锚点 `:262` 张冠李戴（V5⑨：那是 `_seed_seq` 非 `_op_seq`）。
- **修正安全路径**：① 两份 `_op_seq`（guard:49/runtime:19 def + guard:206/212/runtime:216 三消费）原子同改；② **loud 只动 `except (TypeError,ValueError)` 域**，`or 0` 兜的 None/0/空串绝不卷入；③ parity 两份同钉 seq=0/None→短路不 raise + seq="abc"→loud raise；④ 收口家 `schedule_input_contracts.py` 已存在无环（V5⑨）；⑤ 禁碰 `_seed_seq:190`/`_seed_op_id:175`/runtime:261-262。
- **owner 裁后门控**：O24 已裁 loud raise；`or 0` 兜的 None/0/空串不卷入。

### R54（NAV-GUARD，ROOT 扩产 + Batch-C/G04，r1/r3-SOUL 红，V3④拍定）
- **灾难链**：5 套手维 guard 列表收口时漏拷 is_comparison/is_superseded（fail-OPEN 键）或抹 L5 `is_comparison_plan` OR 兜底→`_is_current_official_identity:294 not None`=True→旧/比较版冒充现行采用版→can_emit_feedback_write_urls:469 放行→向历史/比较方案脏写现场事实（不可逆）。
- **旧计划为何炸**：旧计划假设「collar 能内部产 guard 全集」→「5 套 delegate 到 collar」；但 collar `build_workbench_plan_context:187-258` **当前不产** 3 fail-open 键、无 plan_resolution 入参（爆点 #1），裸 delegate=直接抹键 fail-OPEN。
- **修正安全路径（V3④选项 I）**：① 先扩 collar 成 3 键 guard 产出点（走 view_context default_plan_resolution_dict 的 fail-CLOSED 默认）当**独立承重前置改动审**（ROOT）；② 再 6 面 delegate；③ 5 套跨 3 基数（16/15/12），**禁向 16 键看齐**（补 plan_role_status=统一改行为违承重红线），分三组各钉 parity；④ 第 6 手维面 `_PUBLIC_FILTER_DROP_KEYS`（同步面禁 delegate，爆点 #2）；⑤ L5 OR 兜底反例必拦（爆点 #3）；⑥ reports 第二注入路径禁并（丢 3 阻断态）；⑦ 与 R42/R60 同改 collar 签名 MUST 同批。
- **owner 闸门**：collar 入参形态（plan_resolution 入参 vs 局部源）+ fail-CLOSED 默认形态（F门-1/2/3）。

### R04（PARSE-INT，Batch-B/G19，r1-LB/SOUL 红，双爆点，2026-06-08 已 fixed）
- **灾难链**：F1 `reject_integer_float` 默认 True→sgs_graph 8 处 algorithms 调用方 3.0 由接受变 raise 排程静默回归；ValidationError 非 ValueError 子类，6 处 except 漏改任一→脏 op_id 由静默 skip 变 ValidationError 一路上抛炸排程统计/持久化。
- **旧计划为何炸**：F1 默认值若取 True 立刻炸现有调用方；6 处 except 异常逃逸若漏改任一即上抛。
- **修正安全路径**：① F1 必默认 False + 自带 parity（True→3.0 raise/False→3.0 接受，含 sgs_graph 风格调用断言，ROOT/GF1）；② R01 先删→R04 按新行号重 rg（缩收口面 6→5）；③ 6 处 except 同 PR 加 ValidationError 不可拆；④ 哨兵 B(auto_assign:114→0)/C(persistence:13→None) 仅注释禁改 raise；⑤ LB08 文案/正则桥不碰。
- **执行终态**：已按上述路径落地；R01 死链已删，R04 收口后实际剩余 5 处调用点均捕获 `ValidationError`，B/C 哨兵继续保持 `→0` / `→None`，并由新增 parity 钉住。
- **owner 闸门**：哨兵 B/C 注释（不改 raise）；persistence:13 归属（V1⑤归 R04 禁区）。

### R42（NAV-PLANID，Batch-C/G01，r1-LAY 红，爆点 #21）
- **灾难链**：dossier 漏 `dashboard_workbench_context.py:92` 删点（plan_id 落点迁同名不同文件，经 `:119 build_workbench_plan_context(**_context_kwargs)` 的 `**` 展开真实流入被删形参）→删 `:191` 形参后 dashboard 值班台首页 TypeError 500 启动即炸；C1 emit 误删邻参（link_query:117-120 三真身份参夹住 plan_id）→URL 丢 version 静默错位。
- **旧计划为何炸**：删点清单不完整（漏 :92），照单删 :191 形参 dashboard 启动即 TypeError 500（V2⑫确认 TypeError 面=3 个显式传 plan_id 调用方）。
- **修正安全路径**：① 删点清单 MUST 显式分两文件两行（红队 RT1-P1-3 采纳拆跨文件行号）：**`web/viewmodels/scheduler_workbench_links.py:191`（collar `plan_id` 形参删）+ `web/viewmodels/dashboard_workbench_context.py:92`（`"plan_id"` 字典键，经 `:119 build_workbench_plan_context(**_context_kwargs)` 的 `**` 展开真实流入；删 collar 形参后此键无消费方即 TypeError 500）**——两者是「删形参/被展开命中」因果对，非同文件两行；dashboard 实盘仅 136 行，按 `:191` 去 dashboard 删会越界失配，按符号定位；② emit :118/154 按符号删 plan_id 单行绝不连片（唯一归 R42，R60 不重复删）；③ parity 扩「删后 version/plan_role/scenario_id/back_to 逐字==删前」含 emit-A/emit-B 两 plan_style；④ R54 先落 R42 rebase；⑤ 与 R60 单次提交；⑥ co-change 同查真名 `build_workbench_plan_context`（**红队 RT3 噪音采纳删幻觉规约：全仓零 `as n` 别名，全用真名 import，原「别名 `n(`」co-change 纪律建在不存在前提上，已删；只查真名即可**）。collar **共 8 个生产调用方文件**（计数以 verdict_V2 + RT22 备注为准，一致性 P2 收口；多出 navigation_context），**其中仅 3 个真传 plan_id**（navigation_context:78、reports_workbench:79、dashboard_workbench_context:92）触 TypeError 面，余 5 不传安全。
- **owner 裁后门控**：无独立未裁项（随 R54 collar 闸门 + R60 同提交）；R56 禁区行按 O30 认账，`:79` fail-CLOSED 方向不许写反。

### R22（PLAN-IDENTITY，ROOT parity + Batch-C/G27，r1-LB/LAY 红，爆点 #22/#23，V2③拍定）
- **灾难链**：收口委托 build_plan_identity 后 no_history 页 `result_summary_parse_failed` 取值 **False→True 翻转**（`_summary_unavailable(None,·)=(True,'排产摘要缺失')`），下游 reports_plan_template_fields:45/61+3 套手维列表渲染态翻转（无历史方案被标「摘要解析失败」）；且删 view_context:74 normalize_plan_role 行→R21 wrapper `field=="plan_role"` raise 精度失效→bad role builder 静默归一 adopted；24 键 parity 仍全绿（典型测试绿护栏破）。
- **旧计划为何炸**：旧 parity 只验「键集 exact」抓不到取值翻转（#22）；evidence_contract:194 superset 双重逃逸；「委托 builder 即可删 :74」破 bad-role raise（#23）。
- **修正安全路径（V2③三步）**：① parity 升「键集+取值」exact 双断言（对 no_history 实参断言 result_summary_parse_failed 具体取值）+「bad-role 仍抛 field=plan_role」断言 + evidence_contract:194 升 24 键 exact（ROOT，即 G27p）；② 删 :77-100 委托但 **`:74 normalize_plan_role` 绝不删**（止血）；③ no_history 取值交 owner；④ B01/LB03 先行，R22 只 CALL 不改 builder:158/to_dict:46-71。
- **owner 闸门**：no_history 取值保旧 False vs 接受新 True（涉用户可见文案翻转，B 建议但须拍）；#23 无选项=技术红线（必保 :74）。

### R05（RESOURCE-REPO，ROOT step1/2 + Batch-C/G33 step3，3 透镜全红，爆点 #19/#20）
- **灾难链**：collar（column_name 单列 team→空串 + SUPPORTED 无 team + :66 类型有 id 空 raise）结构表达不了承重三轴；步3 先收敛把派工读取收口到未扩 team 现状 collar→team 双 join 谓词（repo:462-463）凭空消失→班组视角静默返全量坏数据；空 id 直塞→collar:66 raise→全量视图整页 500；且 normalize_schedule_resource_filter 是双轨共用收口点（超期/明细轨+报表轨），裸改 :65-66 raise 污染另两轨；team 谓词依赖 build_schedule_detail_sql(include_team_context=True)，搬谓词漏带该布尔→no such column: o.team_id。
- **旧计划为何炸**：旧计划「步3 先收敛收口到现状 collar」——collar 没扩 team 谓词，搬谓词即消失；裸改 :65-66 污染另两轨；漏带 include_team_context 布尔即 SQL 报错。
- **修正安全路径（硬序不可换）**：① 步1 扩 collar（team 谓词接口含 include_team_context 信号 + 放开 id 空=全量 + 中文注释，禁 except 吞错/默认空串静默放行，给派工轨单独入口禁裸改 :65-66 raise）；② 步2 落 5 条 parity（team-only/operator-空-全量/machine-空-全量/team-空-全量/bad-raise）；③ 步3 才搬 :462-463/:455/:460 进收口点；④ collar 只产 SQL fragment 文本+参数**禁反向 import data SQL builder**（model→data 越层+环）；⑤ 禁误并毗邻 `_normalize_team_axis:65`（展示轴）；⑥ 行号系统性 +1 漂移按符号 rg。
- **owner 闸门**：collar 形态 + `(team,"")` 语义已裁（O16：空班组=看全部）。

> **⚠简化声明**：R69 在 _layer3_explosion §二.1 标红清单列为第 6 条，但其调度归属在 LEAF-DUP-P4 桶（未占 G## 槽位），本计划归 Batch-D；与其余 10 条（均有 G 编号原子单元）的批次性质不同，已在 §1 序列总览 ⚠简化声明登记。

---

## 3. owner 裁断汇总表

> 原 19 条 + 本轮新增。每条=背景 + 选项 + 裁定 + **逻辑归属簇**。
> **✅ 2026-06-05 owner 已逐条裁定全部 38 闸门**——「裁定」列即最终决定，原「只标不给终态」纪律由本次裁定解除。与原建议不同的两处已加粗：**O23 改裁保留（非删）**、**O26 裁第三选项 C 全收口**；O08 因 O07 裁「保留」自动消解。逐条落地要点见同目录 `OWNER-DECISIONS-2026-06-05.md`。
> **末列「逻辑归属簇」读法（一致性 C7 消歧）**：末列写的是该单元**裁后落入的逻辑簇/批（非执行排期）**。裁断门已过 → 这些单元现可锁 patch、按 §1 批次序列（ROOT→A→B→C→D）进批（各批 go-no-go 的「裁前 STOP」条件已满足）。

| # | 闸门 | 背景（实盘锚点） | 选项 | ✅ 裁定（2026-06-05 owner） | 逻辑归属簇（已裁，可进批）|
|---|---|---|---|---|---|
| O01 | R09 C 路语义取向 | A/B 宽松 5.9→5、C 严格 5.9→None；收编只动 A/B（viewmodel:33+service:24）到 scope.py:9 | A 保 C 严格 / B 放宽 A/B | A（严格更安全，防脏 op_id 误命中） | G22/Batch-C |
| O02 | persistence_errors:13 归属 | `int(value or 0)` 不 wrap 收口点；R04 列禁区 vs residual 列 R09 第 3 副本（矛盾指令） | 归 R04 禁区+注释 / 收编 R09 | 归 R04 禁区，保持现状+注释（V1⑤，收编会违 R04 灵魂线二次抛错） | G22/Batch-C |
| O03 | R15 坏值方向 | 收口符号空值即 raise；下游 facts_by_scope 裸奔无 except | loud raise / 可观测降级标记 | loud raise 报错拦住；执行留一手：合法空时间仍 `if not text: return None`（RK07），只炸真坏值 | G08/G09 |
| O04 | R19 repo 落点 | snapshot:42 sorted 是 sha256 指纹承重；repo 收 service=越层 | 保私有版+注释 / 收口 canonical | 保私有补「顺序无关」注释（避越层） | G09/G10 |
| O05 | R15/R19 provider链裁定 | provider 链 R15→R19→R13 串行，先落者漂移后者 Edit 锚点 | 同批裁 / 分批 | R15/R19/R13 已 fixed（V1①/O37） | G09 |
| O06 | R13 删/留二次确认 | 死字段被测试读活（R19 后现盘：reschedule:200 + scope_read_contract:149/260-261/291-292/322-323） | 先迁 3 测试后删 / 保留 | 删：owner 已于 2026-06-10 确认单机无仓库外读者；R13 已先迁测试后删 | G09/G10 |
| O07 | R52 A/B 决策门 | 裸删 impl→31 用例蒸发；B 保留作差分 oracle | A 删 impl / B 保留 | B 保留：留作差分 oracle + 补「我是故意的」注释（禁裸留无注释） | G39/Batch-B |
| O08 | R52 子门 A1/A2 | 16 个 ReadyQueueContractError 全量合同用例归属（红队 RT3-P03 纠实盘=16 非 15） | A1 随删丢合同 / A2 改写 LIVE 等价断言保留 | 已消解——O07 裁保留，不删即无合同迁移问题（若未来改裁删，按 A2 保合同覆盖） | G39 |
| O09 | R55 PHASE0 §6 三问（内联自 R55 dossier:154，C3 收口）| R55 `needs_adversarial=true` 且 registry `verdict=null`，三流程门未过却被排进可执行 A3。**三问原文：① 当下债 vs 在途中间态（这是已成型的债，还是重构在途的中间态？）；② `:385 None 回退`是否有意设计（filters 空=看整版故走 provider full，不能把 None 当 bug 删）；③ 裸删 filtered 过滤 vs 补 scope 标记（裸删=filtered 视图变整版反砍业务）**。`owner_pending+needs_adversarial+verdict=null` 是触发条件非三问本身。| 过三问做 / 本轮不做 | 本轮不做；重启条件=怀疑者过三问 + R11/R63 单份化前置就绪 | G13/Batch-B |
| O10 | R34 detail_queries | 纯删 vs 迁活孪生 list_dispatch_rows（落点 R05 team-join 战场） | 纯删 / 迁活孪生（排 R05 后） | 纯删（repoint 目标存在）；迁则回升硬前置 | G30/Batch-B |
| O11 | R54 collar 形态 F门-1 | collar 不产 3 键、无 plan_resolution 入参 | plan_resolution 入参 / 局部源 + parity 违 P5 护栏托付 | 选项 I（plan_resolution 入参，V3④） | ROOT/G04 |
| O12 | R54 collar F门-2 | R42 删形参与 collar 扩产同批冲突 | 同批 / 分批 rebase | 同批（E03 硬序） | ROOT/G04 |
| O13 | R54 collar F门-3 | 缺键语义 fail-CLOSED 默认形态 | fail-CLOSED 默认 / fail-open | fail-CLOSED（默认拦） | ROOT/G04 |
| O14 | R22 no_history 取值 | False→True 翻转涉用户可见「排产摘要缺失」文案 | A 保旧 False / B 接受新 True | B 接受新 True（V2③）；⚠前端文案须重写为中性措辞（如「本方案暂无排产摘要」，禁用「解析失败/缺失」吓用户） | G27/ROOT |
| O15 | R05 collar 形态 | column_name 单列表达不了三轴 | 扩 team 谓词接口形态 owner 定 | 含 include_team_context 信号 + 派工轨单独入口 | ROOT/G33a |
| O16 | R05 (team,"") 语义 | 空 team 字符串裁断 vs 全量 | 裁断 / 全量 | 全量（空班组=看全部，现场口径） | ROOT/G33a |
| O17 | R71 物理收敛 | 三 helper byte 等价，收口 service→core.models | 物理收敛 / 仅 parity 守卫 | 仅 parity 守卫、不物理合并；前置先落 LB07 承重注释 + helper parity（改 loud 另立债不变） | G15/Batch-C |
| O18 | R67 第 4 处收编 | scheduler_navigation_links.py superset 不在 all_files | 收编 superset / 保持现状+注释 | ①②必收，③④全收或全不收，第 4 处保现状 | G34/Batch-C |
| O19 | R72 公开名+落点 | dedup 落 web scheduler_utils，与 R44 协调 | 公开名 owner 定 | web/core 各落各点，必补 request import | G29/Batch-C |
| O20 | R29 KEEP vs 薄壳化 | number_utils 全量 delegation-facade，2 活消费者 | KEEP+注释 / B 薄壳化（前置 G18） | KEEP + 显性「有意保留」注释（不阻塞 G18） | G26/Batch-D |
| O21 | R14 :328 钉层 | 平移活门 diagnose→灵魂线被 fallback 吞 | 钉 resolve_existing_plan 层 / 平移活门 | 钉 resolve_existing_plan 层（禁平移） | G41/Batch-D |
| O22 | R14 灵魂线两门 | :134 死门 + :358 scenario 门撞 LB01 | :358 同源平移 / 不动 | :358 可平移，:328 禁平移 | G41/Batch-D |
| O23 | R24 路 A/B | 路 A 删 core 安全 / 路 B 改指零消费 core 违铁律 5 | A 删 core / B 改指（另立 P5） | **改裁：保留不删（非原建议 A）**——core 预留件留作「诊断回归 core 契约层」的未来地基：补「故意保留」注释 + 事实记录 `.codestable/compound/2026-06-05-decision-r24-diagnostic-contract-keep.md`；绝不走 B 让活路径改指它（丢 NaN/Inf 护栏踩 P4）；PR-9 roadmap 引用保留不动、roadmap 调和前置随之取消 | G42/Batch-D |
| O24 | R69 方向 | owner_pending=false 但设计前置定方向 | loud raise / 保留归0+可观测降级 | loud raise（护栏文件，上游已清洗近零误伤，V5⑨） | Batch-D |
| O25 | R03 status 契约+态 | missing 态:267 生产可达（6 消费点） | missing 保留+不可达注释 / 收敛 | missing 态保留（生产可达） | Batch-D |
| O26 | R41 ≥6 处枚举族 | 改面全 6 族非 2 文件；batch_status 无收口点 | A 5 族全收口 / B 仅 machine | **裁第三选项 C：6 族尽量全收口（超出原 A/B）**——ready 空值打补丁钉「未齐套」（禁标准版默认「齐套」）、operator 打补丁保留「停用/休假」、source 顺手修「外协误判自制」bug、priority/day_type 空值接受变默认值、batch_status 无收口点保留私有；测试改 loud 暴露禁贴回（V5⑧） | Batch-D |
| O27 | R32 raise vs 降级 | :335 warning 吞→:343 os.replace 升正式倒挂 | 硬 raise / 可观测降级 | 硬 raise：校验不过拦住、不升正式备份（:342 已 raise 拦不通过份不变） | Batch-D |
| O28 | R40 错误分类 | material_repo:70-72 静默回退；service 已拦 | A 只删:70-72 保:69 / B 引 core.ValidationError | A（B 造 data→core 耦合不推荐） | Batch-D |
| O29 | R43 roadmap 延期认账 | :522 延期行（非污染 521）；9 wrapper+22 文件迁 | 认账延期+删 wrapper / 不删 | 认账提前删：改 roadmap:522「先保留」为「已批准收口」+ 删 9 wrapper + 迁 22 测试文件 + 改 SP05 三表 + 同步清 scheduler_config.py:94-98 软 fallback | Batch-D |
| O30 | R56 偏离铁律 3 认账 | 删 `_is_execution_review_request` 本体（违承重只补注释）；未 fail-open 契约钉死 | 认账偏离+入账 / 回滚 | 认账（已 fixed，契约钉死） | fixed 残留 |
| O31 | R07 错误类统一 | ValidationError vs 写门 feedback_service:385 AppError/NOT_FOUND 不对称 | 统一 AppError / 保 ValidationError | 统一 AppError/ErrorCode.NOT_FOUND：补 import + 补 schedule=None→raise 专项回归 | fixed 残留 |
| O32 | LB03/LB06 认账注释 | 现盘 fail-CLOSED，勿粘 §90 LB-B4 反向 fail-OPEN 文案 | 落认账注释（双宿主） | 落 reports_execution_review_context+reports_request_support（非 reports_page_support） | ROOT |
| O33 | N1 注释文案 | can_write_feedback 失忆债；真闸 feedback_service:369-382 | 补「我是故意的」注释+绑 parity | 钉真闸（禁引幻觉 :89/:70-84） | ROOT/G22 |
| O34 | N2 注释文案 | _event_id_for_revision return 0 sentinel | 补注释+绑「非末位缺 id 必抛错」契约 | 禁删 `if index<total: raise` | ROOT |
| O35 | LB08 注释文案产出点 | 正则桥承重；产出点 internal_operation.py:119/148/150/152/154 | 按实证改写 | 禁贴 planned 草稿指 auto_assign（消费方） | G40a/ROOT |
| O36 | R58 Phase2 剔单键 | 本轮只注释；Phase2 剔 can_write_feedback 单键翻转 | 本轮只注释 / Phase2 做 | 本轮只注释（Phase2 须补两反例 parity 排 R54 后） | G04 |
| O37 | EXEC-FACT 串行序确认 | V1①已拍 R15→R19→R13 | 确认 / 复议 | 确认 R15→R19→R13（R13 dossier「R13 先」判负） | G09 |
| O38 | GF1 新建参数是否违铁律 3（红队 RT1-P0-1 采纳新增） | `reject_integer_float` 全仓零命中，是「ROOT 新建 kwarg + 透传 + parity」非现有参数改默认值；加在 `core/shared/strict_parse.py:81 parse_required_int`，旧锚点 `:46` 作废 | 视为合规纯增量（加 kwarg 非新建模块）/ 视为违铁律 3 须另立 | 合规（加 kwarg 默认 False 不改现有调用方行为，与「ROOT 纯增量零结构」自洽，非「新建模块」） | ROOT/GF1 |

> **计数：38 条 owner 闸门，2026-06-05 已全部裁定**（覆盖 11 标红债的全部 owner_pending 点 + 6 fixed 残留认账 + N1/N2/LB08 注释文案 + EXEC-FACT 串行序确认 + GF1 新建参数合规性；O08 随 O07 裁「保留」消解）。裁定单元现可锁 patch、按 §1 批次序列进执行；逐条落地要点见 `OWNER-DECISIONS-2026-06-05.md`。

### 3.1 `_positive_int` 同符号 family 对照表（R09 收编误删防护·内联自包含）

> 全文凡「见 §3.1 family 对照」均指本表。`rg "def _positive_int"` 实盘 **12 处同前缀同名异义**，跨两个语义 family；收编者全仓 grep 一次撞 12 处极易误删 STRICT 当重复副本——这恰是灵魂线（坏值 raise）被静默削弱的入口。**铁律：收编只动 Optional family 的 A/B 两份，STRICT family 四份一字不碰。**所有 file:line 执行时按符号重 rg（ROOT 注释落地后必漂）。

| # | file:line | 返回类型 | 分类 | 动作 |
|---|---|---|---|---|
| 1 | `scheduler_resource_dispatch_execution_context.py:28` | `Optional[int]` | Optional·C 路已收口 | wrap 收口点，严格 5.9→None，禁碰（与 N1:129-130 同文件，E29）|
| 2 | `scheduler_resource_dispatch_execution.py（viewmodel）:33` | `Optional[int]` | Optional-**B 收口** | 收编→scope.py:9 |
| 3 | `operation_execution_scope_read.py:21` | `Optional[int]` | Optional·已收口 C 族 | 不卷入 |
| 4 | `resource_dispatch_execution_service.py:24` | `Optional[int]` | Optional-**A 收口**（含调用点 :169/:180/:181）| 收编→scope.py:9 |
| 5 | `schedule_persistence_errors.py:13` | `Optional[int]` | Optional-**第3份** | **归 R04 禁区不收编（V1⑤/O02）** |
| 6 | `scheduler_public_errors.py:167` | `int` | **STRICT-4** | 一字不碰（R46 删 :162-164 毗邻但非同函数）|
| 7 | `auto_assign_resource_errors.py:114` | `int` | **STRICT-4**（→0 哨兵，V1⑥）| 一字不碰 |
| 8 | `operation_execution_scope.py:9` | `int` | **STRICT-4·收口家本体**（真符号 `parse_positive_execution_int`）| 一字不碰（收口目标，扩非删）|
| 9 | `operation_execution_feedback_support.py:161` | `int` | **STRICT-4** | 一字不碰 |
| 10-12 | `_positive_int_set`×N / `_positive_int_text` / data_contract `_positive_int(value, field_name)` 同名异签 | 异签 | 异签族 | 不卷入收编 |

> **真正待收编只剩 #2 viewmodel:33 + #4 service:24 两份**（V1 连带口径，参 `_interference_rebuilt.md §3.1`）。STRICT-4 = #6/#7/#8/#9；其中 #8/#9 是真 loud raise，#6/#7 是 `except: return 0` →0 哨兵（V1⑥：禁区注释须纠偏，禁称「→raise/写入闸门」）。

### 3.2 承重护栏方向硬门（认账注释专属·内联自包含）

> 全文凡「见 §3.2 方向硬门」均指本表。R42 删 plan_id 时若顺手补 R56/LB06 认账注释，极易粘错方向（fail-CLOSED→fail-OPEN）= 承重护栏反转，**比漏边更危险**。凡触碰下述行，**先核现盘 fail-CLOSED 方向再下笔，方向写反 = 承重击穿按 P0 处理**（实盘以 `_interference_rebuilt.md §3.2` 为准，执行时重 rg）。R66/G03 已按 suffix 签名纯删 `_context_summary` 死函数，不属于 plan_id 删除或 R56/LB06 认账注释动作。

| 禁区行 | 现盘方向（实盘 rg）| 认账注释必须写 | 严禁 |
|---|---|---|---|
| `web/navigation_context.py:79`（R56 退化禁区行）| **fail-CLOSED**：`plan_role = plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED`（非法 role→强制 adopted）| plan_role 非法→强制 ROLE_ADOPTED | 粘 §90 LB-B4 fail-OPEN 旧文案（写成「非法 role 放行/默认开放」）|
| LB06 双宿主 `reports_execution_review_context.py` + `reports_request_support.py` | **fail-CLOSED**：execution-review 强制 adopted + scenario=None | execution-review→强制 adopted+scenario=None | 同上方向反转 |

> 注：LB06 真定义宿主是 `reports_execution_review_context.py:8` + `reports_request_support.py:75`（**非 reports_page_support**，verify 纠偏，O32）。

---

## 4. 全局风险 register

> top 风险 + 触发条件 + 缓解 + 监测信号。按严重度排序（P0=承重击穿/不可逆脏写，P1=静默坏数据流，P2=loud 可见但延迟暴露）。

| # | 风险 | 严重度 | 触发条件 | 缓解 | 监测信号 |
|---|---|---|---|---|---|
| RK01 | R54 collar 未扩产即 5 套 delegate | P0 | 跳过 ROOT collar 扩产前置直接 Batch-C delegate | ROOT collar 扩 3 键 fail-CLOSED 产出点 owner 审过为 G04 硬前置（爆点 #1） | `_is_current_official_identity:294` not None 旧版冒充现行；feedback write url 对历史版放行 |
| RK02 | 认账注释方向写反（fail-CLOSED→fail-OPEN） | P0 | R42 认账注释触碰 navigation_context:79 / LB06 双宿主时粘 §90 LB-B4 旧文案 | §3.2 方向硬门：下笔前核现盘 fail-CLOSED 方向；R66/G03 不触碰该注释面 | 注释写「非法 role 放行/默认开放」即反转 |
| RK03 | R09 误删 STRICT 当重复副本 | P0 | 全仓 grep `_positive_int` 撞 12 处同名异义，误删 scope:9/feedback_support:161 | §3.1 family 对照表（实盘 12 处：Optional×5/STRICT×4/异签×3），收编只动 Optional 的 A/B 两份，STRICT-4 一字不碰 | 坏值由 raise 变 None 静默；op_id 误命中相邻行 |
| RK04 | R42 漏 dashboard_workbench_context.py:92 删点 | P0 | 照 dossier 删 :191 形参未补 :92 | 删点清单 MUST 含 :92 同提交（爆点 #21） | dashboard 值班台首页启动 TypeError 500 |
| RK05 | R05 步3 先于步1（搬谓词谓词消失） | P0 | 不遵硬序，先收敛收口到未扩 collar | 硬序步1扩→步2 parity→步3 搬，不可换序 | 班组视角静默返全量坏数据 / 全量视图整页 500 |
| RK06 | R22 parity 只验键集漏取值翻转 | P1 | 旧 parity 键集 exact，no_history result_summary_parse_failed False→True | parity 升「键集+取值」exact + bad-role raise 双断言（爆点 #22/#23） | 无历史方案被标「摘要解析失败」；bad role 静默归 adopted |
| RK07 | R15 整体 delegate 炸合法空时间 | P1 | 收口符号空值即 raise，未分支级保 provider 本地 | `if not text: return None` 留 provider 本地（爆点 #7） | 正常读历史计划 500 / 执行事实全空喂重排 |
| RK08 | R19 统一不排序版漂移 sha256 指纹 | P1 | naive「三处统一」破 snapshot:42 sorted | canonical 强制 sorted+注释，黄金用例 F-fingerprint 门（爆点 #9） | 下游 4 处 guard/publish/scenario 快照比对静默失真 |
| RK09 | R04 6 处 except 漏改任一 | P1 | ValidationError 非 ValueError 子类，漏改即上抛 | 6 处 except 同 PR 加 ValidationError 不可拆 | 脏 op_id 由静默 skip 变 ValidationError 炸排程统计/持久化 |
| RK10 | R54 三基数向 16 键看齐 | P1 | L3 的 15 键「补齐」plan_role_status | 分三组基数（16/15/12）各钉 parity，禁补齐 | 统一改行为违承重红线；公开 filters 漏脱敏（爆点 #2） |
| RK11 | R47 盲 grep/sed 删活参 | P1 | `raw_value=raw_value` 全栈 8 处逐字相同，死活参紧邻 | 按调用函数名逐块手删，禁全局替换（爆点 #10） | invalid 降级证据静默丢失，blank parity 测试全绿 |
| RK12 | R52 删 `_full_scan_ready_ids` helper 漏改差分 oracle 字面量 | P1 | helper 体调 impl，当前 2 差分 oracle 函数（:273/:290）共 5 处字面量调它 | 若未来重启方向 A，删 helper 与改当前 5 处字面量（:278/:281/:284/:287/:299）须同原子（爆点 #16；权威 verdict_V4=2 oracle 函数/5 字面量，非「旧文误记」） | NameError/差分 oracle 炸 |
| RK13 | R69 loud 卷入合法 seq=0 短路 | P1 | P4 粗暴改 loud，`or 0` 兜的 None/0/空串卷入 | loud 只动 except 域，合法路径不卷入（爆点 #15） | 双热路径 raise 可用性放大 |
| RK14 | R14 平移 :328 灵魂线被 fallback 吞 | P1 | 把死门候选平移活门 diagnose | owner 裁钉 resolve_existing_plan 层禁平移 | 「非 scenario 缺角色应 raise」覆盖被悄丢 |
| RK15 | R12 available=False 分支吞 dropped_count | P1 | 只标「两份 _normalize」卡口，漏 contract:22-39 | available=False 分支显式保新键（爆点 #14） | 全坏行最该报警处无信号 |
| RK16 | R26 facade 早删（2 离线消费者 CI 不跑） | P2 | R26 先于 R29/R33/R52 三桶收敛 | E07/E08/E09 硬前置 + 迁 2 离线消费者手验 | tools:17/audit:87 测试红（延迟暴露） |
| RK17 | R33/R30/R31 facade 删序错 | P2 | R31 先于 R33（先删源后删壳） | A14 修正 R33→R31（先删壳 import 再删源） | facade:11 残 import loud ImportError |
| RK18 | R25 垫片先删测试未迁 | P2 | R52 未迁测试即删 R25 垫片 | R25 与 R52 同提交且晚于测试迁移 | test_ready_queue.py:18 import + `_full_scan_ready_ids:81` helper 双红 |
| RK19 | R29 续命点指错文件 | P2 | 照 dossier 改 warmstart:136（无关 number_utils） | 真续命点 regression_number_utils_facade_delegates_strict_parse.py:45-48（V4⑪） | 以为前置满足实则没动真续命点 |
| RK20 | R41 测试贴回收口输出复活静默 | P1 | 改 loud 后把收口输出贴回断言「对齐」 | 测试改 loud 暴露禁贴回（V5⑧硬门） | ready 空串「未齐套」→「齐套」静默复活（调度员误放行） |
| RK21 | 行号漂移致 Edit old_string 失配/误删相邻活函数 | P1 | 删改位移后照搬旧行号 | 全文纪律：按符号重 rg，删后 grep 活近亲 | resolve_version:60（旧 :64） / v4_sanitizers:37 / sgs_scoring:34 等误删 |
| RK22 | 并行 Claude git clean 删本计划 untracked 产物 | P2 | 多进程共享工作区他人 git clean/checkout | 写完立即 git add -f（已执行）；兜底从 agent jsonl 捞 | 产物文件消失 |
| RK23 | TCC ~/Documents 目录 EPERM 闪断 | P2 | macOS 授权回收（非仓库 bug） | 用户重新授权；非代码问题 | 整目录 Operation not permitted |

> **top 5 必盯**：RK01（R54 collar 扩产）/ RK02（注释方向）/ RK03（STRICT 误删）/ RK04（R42 :92 漏删）/ RK05（R05 硬序）——全 P0，照 cluster/dossier 直接执行即炸的硬阻断爆点，Layer4 出批次前已逐条闭合到 ROOT/Batch-C 前置安全网与 owner 闸门。

---

## 5. 与旧 MASTER-PLAN 16 批的差异

> 逐批映射（旧批→新批）+ 为什么变（引用校正）。旧 16 批因含已推翻/已完成占位，重建为 ROOT+4 大批（_interference_rebuilt §5.5）。

### 5.1 结构性映射（旧 16 批 → 重建 ROOT+4 大批）

| 旧批（MASTER-PLAN 概念） | 新批 | 变化原因（引用校正） |
|---|---|---|
| Batch-0 承重注释（分散各批） | **ROOT** 统一上提 | C6：承重根前置统一上提，GF1+LB01/LB02/LB05/LB07/LB08/LB03/R05-step1/R22-parity 全部上提为 13 H 边共同 source |
| 旧「新建 parse_optional_positive_int」批 | **作废** | C1/L1.5.1：R09 收口点 scope.py:9 已存在，改双路 parity 收编（G22/Batch-C） |
| 旧 R13+R18 同原子批 | **拆分** G09(R13)/G10(R18) | C1：R13 死字段被 5 测试读活，解耦 R18，升 owner 二次确认 |
| 旧 R34 收敛重构批 | **降纯删** G30/Batch-B | C1：repoint 目标 get_plan_time_span_for_resolution 存在（旧锚 :210，R23 后现盘 :206，执行按符号重 rg），纯删；R05→R34 降软 |
| 旧 R56 承重待做批 | **入 fixed** | C4：R56 走结构路线已 fixed，退化为 R42 禁区行+owner 认账 |
| Batch-1 yes/no 收敛（旧 MASTER-PLAN 批号）| **Batch-A**（LB04 安全网前置）+ 散落各债 | LB04 注释+全矩阵 parity 是所有 yes/no 收敛安全网 |
| Batch-3/5 收口债（R62/R41 等） | **Batch-B/D** 按门控落 | R62←G05(Batch-B)；R41 排 LB04 后(Batch-D) |
| Batch-8 R05 | **ROOT step1/2 + Batch-C step3** | C：R05 硬序三步，扩产前置上提 ROOT |
| Batch-13 R34/身份族 | **Batch-C** 身份族收敛 | G04→G01/G27 collar 扩产 + parity |
| Batch-14 facade（R26） | **Batch-D** 最晚 | E07/E08/E09：R26 晚于 R29/R33/R52 三桶收敛 |
| Batch-15 LEAF 残余（R69/R68 等） | **Batch-D**（owner 门后落） | C5：R29 复活；R69 owner 定 loud 方向 |
| 旧 16 批 owner_pending 分散 | **Batch-C/D 后置集中** | C6：原 16 owner_pending 中 R29/R52/R24 已裁 KEEP，R55 本轮暂停，其余按裁后门控落 |

### 5.2 与旧计划最大的 5 个差异（核心）

1. **R09 收口点已存在 → 作废建模块批，改双路 parity**：旧批批准「唯一新建 parse_optional_positive_int」，实盘 scope.py:9 已建（loud raise）；改为只收编 A/B 两 Optional 副本 + C 路严格不动 + 两路 parity，owner 裁 C 取严格 vs 放宽（C1/L1.5.1）。

2. **R54 升 5 套手维面 + collar 必须先扩产（爆点 #1）**：旧报告记 3 套/registry 4 套，实盘 5 套跨 3 字段基数（16/15/12）；且 collar 当前不产 3 fail-open 键，「5 套 delegate」前 MUST 先把 collar 扩成 fail-CLOSED 产出点当独立承重前置审——这是旧计划完全没攻到的硬阻断，裸 delegate=不可逆脏写历史现场（C3/V3④）。

3. **R13 解耦 R18 + R34 纯删（repoint 目标存在）**：旧批「R13+R18 同原子」「R34 收敛到 column_name」均被推翻——R13 死字段被 5 测试读活升 owner、R18 stub raise 是契约护栏；R34 的 get_plan_time_span_for_resolution 存在（旧锚 :210，R23 后现盘 :206，执行按符号重 rg）故纯删，R05→R34 由硬降软（C1）。

4. **批次由 16 收缩为 ROOT+4，owner_pending 后置按裁后口径执行**：旧 16 批含大量已推翻/已完成占位；重建为 ROOT（承重+前置门）→A（死叶子）→B（单门控）→C（身份族）→D（facade 最晚）。原待裁清单已由 owner 裁定分流：R29/R52/R24 走 KEEP，R55 本轮暂停，其余按裁后门控落（C6）。

5. **R56 入 fixed + R29 误标纠回 planned 复活 R26 前置 + N1/N2 新债入账**：R56 走高风险结构路线已 fixed（违铁律 3 待认账，退化为 R42 禁区行）；R29 权威 CSV ABSENT 纠回 planned，E07 已纠为 R29/G26 先闭合、R26/G18 后删 facade；执行重构新增 N1（can_write_feedback 失忆债门控 R08）/N2（return 0 sentinel）补注释+绑契约（C4/C5）。

### 5.3 verify 纠 dossier 自身错误（最终以 verify 为准，不撼批次仅纠引用）
- R43 roadmap 延期行 521→**522**；R47 parity 方法名 `_emit_ln`→`_emit_blank_required`；R54 键数 L1=13/L4=12→**L1=12/L4=16**；R34 repoint 目标「不存在」→**存在(旧锚 service:210，R23 后现盘 service:206)**；R29 续命点 warmstart:136→**regression_number_utils_facade_delegates_strict_parse.py:45-48**；R69 锚点 :262→**`_seed_seq` 非 `_op_seq`**（V5⑨）。

---

## 6. 产物索引

> 各产物一句话导航（权威副本在 `.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety/`；`docs/_panorama_data/phase4_dep_safety/` 只是 gitignored 旧镜像/缓存，本轮不得作为落点）。

| 产物 | 一句话导航 |
|---|---|
| `PHASE4-SAFE-BATCH-PLAN.md`（本档） | 装配主笔：脊梁总纲 + ROOT/A/B/C/D 批次序列 + 11 标红债专项 + 38 owner 闸门 + 风险 register + 旧计划差异 + 红队第1轮修订记录(§7) + 红队第2轮修订记录(§8) |
| `_interference_rebuilt.md` | Layer2 干扰图重建：42 原子簇 G01-G42 + GF1 + 29 跨簇边（H13/S14/P2）+ DFS 验环（无环）+ 24 重灾区文件 + §3.1 family 对照 + §3.2 方向硬门 + 红队第1轮 11 采纳 |
| `_layer3_explosion.md` | Layer3 爆炸对抗：73 债 go/no-go + 11 标红确认 + 10 虚惊 + 12 簇 go-no-go + 23 计划外爆点（6 硬阻断）+ 12 回炉建议 |
| `_layer1_corrections.md` | Layer1 校正种子：修法被推翻（A）/ 边校正（B）/ 新债 N1N2+R54 五套（C）/ 偏离认账（D）/ fixed 态（E）/ verify 纠错（F） |
| `_layer2_residual.md` | Layer2 收敛：权威真实路径表（4 前缀订正）+ 6 承重文件 + R09 收编面权威口径（STRICT4/Optional5）+ 残留文档瑕疵 |
| `redteam/verdict_V1.md` | 回炉裁定：EXEC-FACT 串行序 R15→R19→R13 + persistence_errors:13 归 R04 + STRICT 4 处分类纠偏 |
| `redteam/verdict_V2.md` | 回炉裁定：R22 两红因合并单闸门 + 安全路径三步 + R42 删点 :92 + 终态删点清单 |
| `redteam/verdict_V3.md` | 回炉裁定：R54 collar 扩产选项 I + 第 6 手维面 _PUBLIC_FILTER_DROP_KEYS + L5 OR 兜底 + _copy 非卡口框定 |
| `redteam/verdict_V4.md` | 回炉裁定：R52 测试归属 31 用例（dossier ~23 倒置）+ degradation 活桥接壳 + R29 续命点重定位 |
| `redteam/verdict_V5.md` | 回炉裁定：R41 改面 6 族 + batch_status 留私有 + R69 seq=0 合法短路 + :262 张冠李戴纠偏 |
| `dossiers/{id}.md` ×73 | 逐债细节（每份含对抗核验）；`_fixed_confirm.md`（6 fixed 债）/`_newdebt_guard.md`（N1）/`_newdebt_parse-except.md`（N2）|
| `clusters/*.md` ×12 | 12 簇逐簇产物（C-NAV-PLANID / C-NAV-GUARD / C-EXEC-FACT / C-EXEC-REVIEW / C-GANTT / C-CONFIG-DUAL / C-COMPAT-DISPATCH / C-PARSE-INT / C-PLAN-IDENTITY / C-RESOURCE-REPO / C-GRAPH-ERR-DIAG / C-LEAF-DUP-P4）|
| `_registry.json` / `_registry_index.json` / `_clusters.json` / `_layer1_input.json` / `_layer1_summary.md` | 确定性真相源 registry（80 债导航总表）+ 索引 + 簇映射 + Layer1 输入/汇总 |
| `build_registry.py` | registry 构建脚本（确定性真相源生成器）|

---

> **装配完成声明**：本计划装配自上述全部输入，11 标红债 + 6 硬阻断新爆点逐条落位于对应批次的前置安全网或 owner 闸门（无一遗漏，见 §0.3 + §1.0 速查 + §2 + §4 top5）。所有 file:line 为 2026-06-05 实盘值，**执行时一律按符号重 rg 回盘**，权威路径以 `_layer2_residual.md` 为准。§3 共 38 闸门已在 2026-06-05 全部裁定，执行时按裁定列落地；任何简化/合并以「⚠简化声明」显式标注，无静默截断。红队第1轮 9 项采纳已逐条修订，见 §7。

---

## 7. 红队第1轮修订记录

> 红队第1轮 3 份产物（`redteam/plan_rt1_1.md` 脑内执行者 / `plan_rt1_2.md` 依赖反序猎手 / `plan_rt1_3.md` 原子性+闸门猎手）合计提出 14 个问题点（含去重）。逐条裁定如下，所有反证均 2026-06-05 实盘 rg 回盘。**采纳 9 项 / 驳回 5 项（其中 4 项为「已核无硬伤·登记备查」，1 项噪音规约随采纳清除）**。批次序、债计数（73 债 + R64/R65 补登=实为登记疏漏非净化错）、脊梁四步不变式未被任何采纳项动摇——9 项采纳全是「锚点/措辞/漏登/计数漂移」层，无依赖反序硬伤。

| # | 红队来源 | 问题 | 裁定 | 反证（实盘） | 落点 |
|---|---|---|---|---|---|
| 1 | RT1-P0-1 / RT2-问题2 | GF1 `reject_integer_float` 被当「现有前置门改默认值」，实为待新建参数 | **采纳** | 全仓 rg 零命中；`core/shared/strict_parse.py:81 parse_required_int` 无 float 拒绝参数、文件仅 130 行无 `:46` | §1.1 GF1 重定性为「新建受控参数」+ 新增 O38 闸门 |
| 2 | RT1-P0-2 / RT2-问题3 | R52 impl 路径丢 package 前缀，会删错壳/impl | **采纳** | impl=`core/algorithms/greedy/dispatch/ready_queue.py:103`、垫片=`core/services/scheduler/graph/ready_queue.py`（补注释后 13 行，`:103` 越界） | §1.3 G39 + §2 R52 灾难链补全双路径，三锁定 |
| 3 | RT1-P1-3 | R42 `:92`(dashboard) 与 `:191`(collar) 跨文件行号挤一句 | **采纳** | dashboard 实盘 136 行，`:92`=`"plan_id"` 键；collar `:191`=形参，跨文件 | §2 R42 安全路径拆两文件两行带路径 |
| 4 | RT1-P1-4 / RT2-问题1 | collar `build_workbench_plan_context` 宿主目录全文写错（routes/domains→viewmodels） | **采纳** | 真宿主 `web/viewmodels/scheduler_workbench_links.py:187`；`routes/domains/scheduler/` 下只有 `scheduler_analysis_links.py` | §1.4 G04 爆点 #1 订正宿主 + co-change 真名纪律提升正文 |
| 5 | RT1-P1-5 | ROOT 注释插入致同文件下游删点系统性下移，正文仍留裸行号断言 | **采纳** | LB01/LB02/LB07/LB03 注释行插入必下移后续锚点 | §1.3 Batch-B 前置加「⚠行号位移总纲」，裸行号改按符号 rg |
| 6 | RT1-P2-6 | R09 family 12 处同前缀实盘坐实，G22 正文未给全锚点 | **采纳** | `rg "def _positive_int"` 12 处（Optional×5 / STRICT×4 / 异签×3） | §2 R09 嵌入 12 行 family 对照表（返回类型分类） |
| 7 | RT3-P01 | R64/R65 两条 `kind:real` 死 helper 被整份计划吞掉（漏债） | **采纳** | `_truth.json` R64/R65 `kind:real/load_bearing:false`，B17-LEAF-DEAD；`_has_navigation_date_range:66` 全仓零调用；与 R42 same_file | §1.0 ⚠简化声明补登 + §1.2 Batch-A 成员/前置/不可碰清单 |
| 8 | RT3-P02 | R49 一债拆 G25(Batch-A)/G24(Batch-B) 两批却无同提交/串行声明 | **采纳** | 两半共享 `parse_dispatch_rule`（真宿主 `core/algorithms/dispatch_rules.py:28`）调用图，跨批易致孤儿/NameError | §1.3 G24 加 R49-self 串行边 + G25 标注（推荐并回一原子） |
| 9 | RT3-P03 | R52 RQErr 合同数计划四处写「15」，实盘 16 | **采纳** | `rg -c ReadyQueueContractError test_ready_queue.py`=16（用例总数 31 ✓） | §1.3/§1.3 owner/§2/§3 O08 四处「15」→16 |
| 10 | RT3-噪音 | D2「别名 `n(`」co-change 纪律是幻觉前提 | **采纳清除** | 全仓零 `as n` 别名，7 调用方全真名 import | §1.4 G01 爆点 #12 + §2 R42 删幻觉规约 |
| 11 | RT1-P2-7 / RT2-问题4 / RT3 | R34 repoint 目标存在 / R26 5 shim 清单未展开 / 各「无硬伤」靶点 | **驳回（登记备查）** | `get_plan_time_span_for_resolution` 存在 ✓（旧锚 :210，R23 后现盘 :206，执行按符号重 rg）；R26 5 shim 待 G18 落地前补（非本轮硬伤） | 无需改文（C1 校正成立；R26 shim 清单留 §1.5 执行前补） |
| 12 | RT2-问题4 | R26「顶层 5 shim」清单本计划未展开 | **驳回（登记备查）** | E07/E08/E09 三桶→R26 方向正确，仅 shim 明细待补，非反序硬伤 | §1.5 G18 已注「2 离线消费者 + 三桶硬前置」，5 shim 执行前从 B14 补 |
| 13 | RT2 §2 / RT3 §回盘 | 13 H 边/dispatch 三债/R45≡R48/R25+R52 等批次序无反序 | **驳回（确认正确）** | 逐条对照批次拓扑方向全对，脊梁第 1/4 步设防到位 | 无需改文 |
| 14 | RT3 / RT1 总结 | R69 等 11 标红债 owner_pending 未被偷给终态 | **驳回（裁前合规；裁后已解除）** | 该条记录的是 2026-06-05 前状态；现 38 闸门已裁，按 OWNER-DECISIONS 执行 | 已由裁后口径补丁同步正文 |

**修订后全局一致性自检**：批次总数仍 5（ROOT+A/B/C/D）；G 编号 42 + GF1 不变；owner 闸门 37→**38**（新增 O38·GF1 合规性）；标红债仍 11；债登记 73 + **R64/R65 补登 2**（此前漏登非净化错，registry B17-LEAF-DEAD 本就在册）；RQErr 合同 15→**16**（实盘纠正）；collar 宿主全文应为 `web/viewmodels/`（爆点 #1 已订正，§0.3/§3.2 残留裸写引用执行时按本记录宿主为准）。无采纳项触碰脊梁四步或 13 H 边方向。

---

## 8. 红队第2轮修订记录

> 红队第2轮 3 份产物（`redteam/plan_rt2_1.md` 复攻1·第1轮采纳是否真改对 / `plan_rt2_2.md` 复攻2·同文件多批触碰只对账一对 + 伪串行锚点 / `plan_rt2_3.md` 复攻3·门禁可执行性）合计提出 9 个问题点。逐条裁定，所有反证均 2026-06-05 实盘 rg 回盘。**采纳 9 项 / 驳回 0 项**（2 项非硬伤备注随采纳登记备查）。批次序、债计数、脊梁四步、13 H 边方向不变——9 项采纳全是「退场面缺登 / 伪串行边降级 / 同文件三方碰撞升串行块 / 措辞同质化 / 门禁措辞可执行性」层，无依赖反序硬伤；其中 E16 由「串行门」降为「登记备查」是**减少**一条伪依赖（非新增）。

| # | 红队来源 | 问题 | 危险度 | 裁定 | 反证（实盘 rg 回盘） | 落点 |
|---|---|---|---|---|---|---|
| 1 | plan_rt2_1 问题1 | RT3-P01 补登 R64/R65 时把 R65 误同质化为「零调用死 helper」，实为 `_target_url` P6 死分支（`:160` 有真引用被 `or` 短路遮蔽），照「直删 def」即 NameError | 中 | **采纳** | `:74 def _target_url`（活函数），`:160 plain_url or _target_url(...)` 真引用，孤儿 import `:4 urlencode`/`:6 query_for_target`，护栏 `:7 TARGET_PAGE_PATHS` 被 `:177` 真用 | §0.1 补登声明 + §1.2 成员/前置安全网：改回「死分支三件套」口径（删 def+化简 :160+删孤儿 import）+ 补禁区 `:7` + 护栏 `test_all_nav_specs_have_nonempty_plain_url`，与 R64 去同质化 |
| 2 | plan_rt2_2 P-RT22-01 | `scheduler_navigation_links.py`（205 行）是三批四单元战场（R64/R65@A + R42@C/G01 + R67@C/G34），计划只钉 R64/R65↔R42 一对，漏 R67 第三方；Batch-A 删点先位移全文，Batch-C 三方混改 R42 `:40` 易碰 R67 元组里 plan_id 键 | 高 | **采纳** | `:11 _REPORT_CONTEXT_FIELD_NAMES` 元组（R64/R65 上方不位移）+ `:186 preserved_report_context_fields`（R67 遍历点，在 R64/R65 下方会上移）；`:40 build_workbench_plan_context`（R42）；文件 205 行 | §1.0 新增「⚠单文件三批四单元串行编排块」总纲（三步硬序 + 重 rg）；§1.4 G01/G34 与 §1.0 序列「R64/R65 same_file」一律读作四单元串行块 |
| 3 | plan_rt2_2 P-RT22-02 | E16 旧报告把 R01/R46/R19 误当共享 `__all__` 串行对账，是伪串行边——三个 `__all__` 在三不同文件；R19 当前 `__all__` 在 execution_snapshot.py:123-128，会把改 R01/R46 引到错文件 | 中 | **采纳** | R01=`schedule_payload_contract.py:410`、R19=`execution_snapshot.py:123/127`、R46=`core/models/scheduler_public_errors.py` **根本不动 `__all__`**（`_safe_identifier:163` 不在 `__all__:340-349`，导出 `public_safe_identifier`） | §1.4 G09 + §2 R19：E16 降「登记备查·无依赖」，拆三条独立事实，三债顺序无关；同步降 §1.3 Batch-B go-no-go / §1.4 Batch-C 门禁 + go-no-go 三处依赖 |
| 4 | plan_rt2_2 P-RT22-03 | G09(R13) 退场清单漏 `_fact_from_state` 的 `latest` 形参与调用点实参，只删字段两行→形参悬空/调用 TypeError；R19 后现盘赋值 `:61-62` 紧贴 R15/R19 后续函数体 | 中 | **采纳** | R19 后现盘：`_fact_from_state:45`，形参 `latest:48`，赋值 `:61-62`，调用点实参 `latest_events.get(scope):112`，孤儿 `_latest_events_by_scope:152-159`+`:107` | §1.4 G09：R13 退场补全四处同原子（字段 :28-29 + 形参 :48 + 实参 :112 + 孤儿 `_latest_events_by_scope`），并注按键名/符号重 rg；同步 Batch-C 门禁/go-no-go |
| 5 | plan_rt2_2 P-RT22-04 | R67 第4处 O18 一旦裁「收编③④」则元组拼接撞 R42 的 plan_id 键 + 新增 viewmodels→core.services.report 跨层边，E17 单句「diff-hunk 串行」未防分层门 | 低-中 | **采纳** | R67 superset 元组首键 `plan_id`（R42 地盘）；O18 已裁第 4 处保现状；历史收编第4处才会新增 `web.viewmodels→core.services.report` 跨层边 | §1.4 G34：E17 拆两条件分支（保现状=零冲突 / 历史收编③④=晚于 R42 删形参+禁碰 plan_id 成员+先过分层门），分层门风险从 dossier 提 G34 正文 |
| 6 | plan_rt2_3 问题1 | `test_no_new_local_parse_helpers` 第二断言 `stale_entries`（:254-256）——删/收编 parse helper 令白名单 3 项失效致 fitness 第11项转红，门禁零处提示须同退白名单 | 中 | **采纳** | `:254-256 stale_entries = LOCAL_PARSE_HELPER_ALLOWLIST - found_allowlist`；白名单 3 项 `_sched_utils:_safe_int`/`batch_service:_safe_float`/`system_config_service:_get_int`；**本轮删点全不在 `LOCAL_PARSE_HELPER_NAMES` 集合** | §1.1 ⚠门禁可执行性总纲(1)：补防御性总纲「删/收编命中 NAMES 集的函数须同退白名单」，并标注本轮 3 白名单项经核未落入删点（防御性非必触发） |
| 7 | plan_rt2_3 问题2 | 语义雷达「无新漂移」无法机器判红——run_drift_scan.py 自述不直接 fail，exit 0/1 都正常，CI 跑它永远绿 | 中 | **采纳** | `run_drift_scan.py:2-4` 头注释「只读、不直接 fail，drift exit 0/1 都正常」 | §1.1 ⚠门禁总纲(2)：拆两半——(a) `run_semantic_guards.py` exit 0 作机器门 / (b) drift 对比 baseline findings 数 >0 人工裁断；同步 ROOT 批后门禁 |
| 8 | plan_rt2_3 问题3 | ROOT 门禁「regression_execution_review_identity_guardrail/spec_sync」用简称且 fd 搜不到（文件实存经 test_registry 注册），裸名抽查会误判缺失 | 低 | **采纳** | `tests/operation_execution/test_execution_review_identity_guard.py`（实存，test_registry:289）+ `tests/config/test_scheduler_config_spec_sync_contract.py`（实存，test_registry:56） | §1.1 ⚠门禁总纲(3)：门禁清单写全路径名 + 标 test_registry 注册，核存在用 `rg <name> tools/test_registry*` 非 `fd`；同步 ROOT 批后门禁 |
| 9 | plan_rt2_3 问题4 | 「v18 DB CHECK」查无对象——CHECK 两列全在 v19.py:14-19，v18 零 CHECK | 低 | **采纳** | `rg CHECK v18.py`=0；`v19.py:14/15/18/19` 两列 CHECK；载体 regression_migrations+regression_migration_schema_contract | §1.1 ⚠门禁总纲(4)：正名「v19 DB CHECK 不破（两列），经 regression_migrations+regression_migration_schema_contract 验；v18 仅 schema 前置无 CHECK」；同步 ROOT 批后门禁 |

**非硬伤备注（随采纳登记备查，不改批次序）**：
- **R49 §189 消费图夸大（plan_rt2_1 备注）**：计划 §189 称 `parse_dispatch_rule` 被「greedy 内 sgs_scoring/sgs/scheduler 多文件消费」，实盘 `rg parse_dispatch_rule` 全仓仅 2 命中（`dispatch_rules.py:28` 定义 + 1 测试），无 greedy 子模块消费。R49-self 跨批串行序结论（G25 旁支晚于或并回 G24）本身保守无害，仅「炸点描述」基于幻觉消费图，影响可信度不影响安全——保留串行结论，执行者勿据「多文件消费」幻觉前提推演。
- **collar 真调用方 7→8（plan_rt2_1/RT22 备注）**：collar `build_workbench_plan_context` 真调用方实为 8 个生产文件（计划 §388/§235 记 7），多出 `web/navigation_context.py`；不影响删形参安全性（navigation_context 经 `**kwargs` 链 plan_id=0，爆点 #12 已覆盖），仅计数下沉，备查。

**修订后全局一致性自检**：批次总数仍 5（ROOT+A/B/C/D）；G 编号 42 + GF1 不变；owner 闸门仍 **38**（本轮无新增 owner 闸门，R67 O18/R13 O06 均已在册）；标红债仍 11；债登记 73 + R64/R65 补登 2 不变；RQErr 合同 16 不变；**E16 由「串行门」降为「登记备查」（减一条伪依赖，13 H 硬边方向不变）**；新增 1 个「单文件三批四单元串行编排块」（`scheduler_navigation_links.py`，非新批次、是同批内编排约束）。无采纳项触碰脊梁四步或 13 H 边方向。

---

## 9. 附录 · 13 条 H 硬边表（C1 内联自包含）

> 全文凡「13 条 H 硬边/尊重 13 H 边」均指本表（权威源 `_interference_rebuilt.md §2.1 + §4.1`）。**H=硬序（违序即 ImportError/NameError/契约红/承重失效）**；方向 `源→汇` 读作「源先于汇 / 源门控汇」。执行者据此核「我这步是否违 H 边」无须跳外档。所有 file:line 执行时按符号重 rg。

| H# | edge-id | 边（源→汇）| 门控什么 / 违序后果 |
|---|---|---|---|
| H1 | E01 | GF1 → G19(R04) | `reject_integer_float` 默认 False 先绿，R04 才收口；否则现有 `parse_required_int` 8 调用方 3.0 由接受变 raise 静默回归 |
| H2 | E02 | GF1 → G20(R59) | 同上；R59 裸收口撞续命测试 :247/:250 raise |
| H3 | E03 | G04(R54) → G01(R42/R60) | R54 guard 字段落 workbench_links:206-207 后，R42 删 plan_id 形参 :191 须 rebase 其后（签名互撞），MUST 同批 |
| H4 | E05 | G23(R33) → G17(R31) | R33 删 value_policies 壳须不晚于 R31 删 shared 源 :9，否则 facade:11 残 import loud ImportError |
| H5 | E06 | G23(R33) → G17(R30,R31) | 三常量 re-export：壳 R33 先停 import，R30/R31 两 shared 侧删动作彼此无序（A14 已纠 R33→{R30,R31}）|
| H6 | E07 | G26(R29) → G18(R26) | facade 删晚于收敛：R26 顶层 shim 2 离线消费者经老路径，先删 shim 致其测试红（PHASE0§10.2）；O20 KEEP 时该边视为已满足 |
| H7 | E08 | G23(R33) → G18(R26) | 同上（B06 桶）|
| H8 | E09 | G39(R52) → G18(R26) | 同上（B09 桶）；O07 KEEP 注释完成后才视为收敛 |
| H9 | E12 | LB03(B01 承重)+G27p(R22 parity) → G27(R22/R21)| LB03 承重注释+guard 收口须全局先落于 B02 身份族；R22 先落 24 键 exact parity 钉键集再收敛 |
| H10 | E13 | G07a(LB01 承重注释) → G41(R14) | R14 删 :134-139 前 LB01 承重裁断必先行（同符号 `_resolve_strict_plan`，删除让位）|
| H11 | E16(部分)| G09/G10(R19) ↔ G19(R01)/G40(R46) | `__all__` 同符号块高顺序敏感——**已经 P-RT22-02 判为伪串行边降「登记备查」**（三 `__all__` 在三不同文件物理零重叠，三债顺序无关，不再作机器门；列此仅为 13 计数溯源）|
| H12 | E26(注释面)| N1 → G22(R08)/G04(R54/R58) | R08 删死分支依赖 service:127≡:130 同源，N1「我是故意的」注释+绑 parity 守卫须先于 R08 删（H 仅约束注释面，行号面 S）|
| H13 | GF1 两门 | （= H1/H2 的 GF1 共享前置门归并计）| `_interference_rebuilt §4.1` 把「GF1 两门」单列以凑 13 计数；实质即 E01+E02 的 GF1 source 性质 |

> **H 边计数溯源**：`_interference_rebuilt §4.1:259` 明列 13 H = E01,E02,E03,E05,E06,E07,E08,E09,E12,E13,E16(部分),E26(注释面),GF1 两门。其中「GF1 两门」与 E01/E02 同源（H13 即 H1/H2 的 source 归并），E16 已降伪串行边但仍计入 H 计数溯源。**另有 GANTT 内收口前置硬边 A08(R11/R63→R12)/A09(R11/R63→R55) 是单元内/簇内硬序**（G11 先于 G12；R55 本轮跳过），已在 §1.2 G11 前置安全网固化，不计入跨簇 13 H（避免重复计数）。A11/A12/A13(R29/R33/R52→R26) 即 E07/E08/E09 的来源边，A14(R33→R31) 即 E05 的方向修正，均不增条数。

## 10. 附录 · E03–E29 edge-id 对照速查表（C2 内联自包含）

> 全文凡引用 E03–E29 任一 edge-id 均可在此查「源→汇 / 软硬 / 约束含义」（权威源 `_interference_rebuilt.md §2.1`）。**H=硬序、S=软序（零成本先后/重 rg 纪律）、P=前置已完成**。E01/E02 见 §9 H1/H2。

| edge-id | 源→汇 | 类型 | 约束含义（违序/不遵后果）|
|---|---|---|---|
| E03 | G04(R54)→G01(R42/R60) | **H** | 同符号 build_workbench_plan_context co-change，R42 删形参须 rebase R54 扩产后；MUST 同批 |
| E04 | G04(R54)→G03(R66) | S/P | 已满足:R54 改 reports_workbench 上方区域后,R66 按 suffix 符号重定位到删除前 :139-152 并于 2026-06-09 fixed |
| E05 | G23(R33)→G17(R31) | **H** | facade 删序：先删壳 import 再删 shared 源，否则 facade:11 残 import ImportError |
| E06 | G23(R33)→G17(R30,R31) | **H** | 三常量 re-export，壳 R33 先停 import；R30/R31 同窗口同 diff |
| E07 | G26(R29)→G18(R26) | **H** | facade 删晚于收敛（2 离线消费者）；O20 KEEP 时该前置以 KEEP 注释闭合 |
| E08 | G23(R33)→G18(R26) | **H** | facade 删晚于收敛（B06 桶）|
| E09 | G39(R52)→G18(R26) | **H** | facade 删晚于收敛（B09 桶）；O07 KEEP 注释完成后闭合 |
| E10 | G15(R71)→G18(R26) | S | 转出边：R71(B03) 先 R26(B14) 后天然满足，不同文件不撞行号 |
| E11 | G18(R26)↔G19(R01)/R43 | S | SP05 同文件各改各段串行避 git 行号漂移误合，无逻辑依赖 |
| E12 | LB03(B01 承重)+G27p(R22 parity)→G27(R22/R21)| **H** | parity 先于收敛 + same_symbol build_plan_identity；LB03 先落 |
| E13 | G07a(LB01 承重注释)→G41(R14)| **H** | 承重让位 + same_symbol `_resolve_strict_plan`；LB01 裁断先行 |
| E14 | G41(R14)→G05(LB02/LB05)/R61 | S | report_engine 邻域避让，迁灵魂线测试触碰邻域须避让 |
| E15 | G40(R46)→G22(R09)| S | `_positive_int:167` 软位移，R46 删 :162-164 后 R09 动 :167 按符号 grep 重定位 |
| E16 | G09/G10(R19)↔G19(R01)/G40(R46)| **S（伪串行降级）**| 原标「__all__ 同符号块串行」，P-RT22-02 判**伪串行边**（三 `__all__` 三文件零重叠，三债顺序无关，不再作门）|
| E17 | G33(R67)→G01(R42)| S | diff-hunk 串行避互撞；O18 裁「收编③④」时升条件硬序（晚于 R42 删形参+禁碰 plan_id 成员+过分层门）|
| E18 | G33(R05)→G30(R34)| S（条件硬）| 仅 R34 选「迁 detail_queries 到活孪生」才回升硬前置（落点是 R05 team-join 战场）|
| E19 | G28(R23)→G30(R34)| S | R23 最小落法让 query_service 后续锚点净上移 4 行（import +1、重复块 -5；`get_plan_time_span_for_resolution:210→206`），R34 基于删后符号重 rg 定位 |
| E20 | G27(R21)→G04(R44)| S | R21 删 selected_plan_role shim，R44 直接 re-export core 不照抄 |
| E21 | G29(R72)→G04(R44)| S | 收口落点协调（非排序），web/core 各落各点 owner 共识 |
| E22 | G13(R55)→G27(R21)/G04(R44)/G29(R72)| S | 消费者只读触发条件勿砍 resource_type/resource_id |
| E23 | G39(R52)→G24(R50)| S | sgs.py 弱边，仅簇内共现登记 |
| E24 | G19(R04)↔G40(LB08)| S | 承重认账协同（毗邻），LB08 注释先落或同批 |
| E25 | G22(R09)→R07(已 fixed)| **P** | 前置已完成：R07 改 raise 已落，R09 收 A 副本在 R07 稳定行号重盘 |
| E26 | N1→G22(R08)/G04(R54/R58)| **H(注释)/S(行号)**| N1 补注释+绑 parity 守卫先于 R08 删；与 R54/R58 同护栏概念 |
| E27 | N2↔G04/G22/LB01宿主| S | event-id 契约（:156-163 return 0 sentinel）与 LB01 宿主同源，禁删 `if index<total: raise` |
| E28 | R09(G22)↔LB01 最终底(scope.py:36-50)| S | 同文件承重毗邻，R09 收编禁碰 :36-50（按符号定位）|
| E29 | N1↔R09(C 路 context.py:28-30)| S | 同文件承重毗邻，收编 A/B 副本前先在此钉死 C 路 parity |

## 11. 附录 · 24 重灾区文件清单（C9 内联自包含·SCC 串行取用）

> 脊梁第 3 步「24 重灾区文件按符号自下而上」即指本清单（权威源 `_interference_rebuilt.md §3`）。**判据：同一物理 .py（或同一测试文件 / emit 点）被 ≥2 债命中 + 行号/符号互相位移**。按危险度排序。所有 file:line 执行时按符号重 rg。

| 危险度 | 物理文件 | 命中债 | 顺序约束（简）|
|---|---|---|---|
| 🔴 最危 | `operation_execution_feedback_service.py` | LB01(承重)+R17+R20 | G07 强序 LB01 注释先→R17 删 :12→R20 改 :52；LB01↔R17 同 `_build_event_payload` 最危险边 |
| 🔴 最危 | `report/execution_review.py` | LB02+LB05(承重)+R62 | G05 注释先(ROOT)→G06 后；R62 按符号+`!=` 重 grep 禁照抄行号 |
| 🔴 最危 | `gantt_critical_chain_provider.py` | R12+R55(+R13 跨簇)，R11/R63 已 fixed | G11 单份 helper 前置已满足→G12/G13 加键穿三白名单；禁误删 `_copy:108` |
| 🟠 高 | `gantt_service.py` | R10+R55(+R34/R21/R63/R11/R12 弱) | 同 PR 物理串行；R10 fixed 后 grep `resolve_version:60`（旧 :64） |
| 🟠 高 | `scheduler_navigation_publish.py` | R58(承重邻)+R54+R44 | G04 硬序 R58→R54→R44（重 rg :6/:36-37）|
| 🟠 高 | `web/.../scheduler_workbench_links.py` | R42+R54(跨簇)+R60 邻 | E03 硬序 R54 先→R42 rebase；禁动 dict guard 段/禁翻 fail-open |
| 🟠 高 | `algorithms/dispatch_rules.py` | R49+R50+R51 ✅ fixed | G24 已一次原子 diff 闭合；保 `import math` 与 `build_dispatch_key`，禁再按旧行号重复删 |
| 🟠 高 | `schedule_payload_contract.py` | R01+R04 ✅ fixed | G19 已按强序闭合；后续禁按旧行号重复施工，现盘 `_strict_positive_int` 只剩 5 个调用点 |
| 🟠 高 | `data/repositories/schedule_repo.py` | R34+R35 | O10 已裁纯删；G30 一原子 diff 自下而上 |
| 🟡 中 | `config_snapshot.py`+`schedule_config_runtime_coercion.py`(双栈)| LB07(承重)+R71+R47 | G15 硬序 LB07 注释+parity 先→R47+R71 同批 |
| 🟡 中 | `web/viewmodels/scheduler_resource_dispatch_execution.py` | R08+R09(B 副本)| O01/O02 已裁；G22 串行 R08 先→R09 后，只收 A/B Optional 副本 |
| 🟡 中 | `gantt_plan_query.py` | R21+R22(precondition)| G27 硬序 R22 先→R21 后（严守保留 :32-39 wrapper+:50-156 LIVE）|
| 🟡 中 | `schedule_plan_query_service.py` | R23+R34 | E19 软序 R23 先让 R34 基于删后符号重 rg 定位；后续锚点净上移 4 行 |
| 🟡 中 | `data/repositories/part_repo.py` | R38(part)+R39 | G31 已 fixed（旧风险记录：同 commit 按符号名） |
| 🟡 中 | `models/scheduler_public_errors.py` | LB08(承重)+R46(+R09 `_positive_int` 毗邻)| G40 已 fixed：LB08 注释已先落、R46 死别名已删；R09 后续只按符号重定位 |
| 🟡 中 | `common/value_policies.py`(壳)+`shared/value_policies.py`(源)| R30+R33+R31 | E05/E06 硬序 R33 步1→R30→R33 步2/3；死保 degradation:15 |
| 🟡 中 | `tests/gate_meta/test_sp05_path_topology_contract.py` | R06+R27+gantt 空包(+R01/R26/R43 别段)| G38 已 fixed；后续别段仍禁碰现盘 :175 def/:317 起 strong-compat 断言 |
| 🟡 中 | `tests/config/test_config_service_component_contract.py` | R33+R30(交界)| G23 内 R33 步2/3 在 R30 之后 |
| 🟢 低-中 | `execution_snapshot.py` | R19+R01+R46(__all__ 块)| E16 已降伪串行边；R19 强制保 `sorted:42`（sha256 指纹）|
| 🟢 低 | `web/.../reports_export_support.py`+`scheduler_navigation_links.py`(两元组)| R42+R60+R67(+R64/R65 G02 已 fixed)| E17 diff-hunk 串行；G02 已完成,后续只复核 `TARGET_PAGE_PATHS` 仍保留并按符号重 rg 当前 navigation_links 锚点；**本文件即三批四单元串行块**（见 §1.0）|
| 🔴 承重邻 | `models/operation_execution_scope.py` | R09 收口家(:9)+LB01 最终底(:36-50)| E28 同文件承重毗邻；R09 收编禁碰 :36-50；**承重文件 +1=6** |
| 🟡 中 | `web/viewmodels/scheduler_reports_workbench.py`(L1)| R54·L1(12 键别名源键)+R66 fixed+R42/R60 邻 | R54 五套同窗口已落；R66 已按 suffix 签名纯删；后续仍禁向 16 键看齐 |
| 🟡 中 | `web/viewmodels/dashboard_workbench_context.py`(L4)| R54·L4(16 键≡L2)| R54 五套同窗口；删 :191 形参后 :92 dict 键 TypeError（爆点 #21）|
| 🟡 中 | `web/routes/domains/scheduler/scheduler_resource_dispatch.py`(L3)| R54·L3(15 键缺 plan_role_status)| R54 五套同窗口；禁补 plan_role_status「补齐」16 键 |
| 🟡 中 | `web/viewmodels/scheduler_gantt_task_detail.py`(L5)| R54·L5(别名元组异机制)| R54 五套同窗口；别名元组机制禁混并 |

> **重灾区计数：24 个物理/测试文件**（原 19 + 红队第1轮补登 5：operation_execution_scope.py + R54 缺席四文件 reports_workbench/dashboard_workbench_context/resource_dispatch/gantt_task_detail）。其中 **6 个含承重点**、**3 个为「最危险边」宿主**（feedback_service 的 LB01↔R17、execution_review 的承重五钉↔R62、gantt_critical_chain_provider 的 `_copy`↔`_normalize`）。上表 25 行是因 L1-L5 五文件 + scope.py 同列展开，去重物理文件数 = 24。

---

## 终检收口记录（Layer4 final）

> Layer4 终检 5 路（sign1/sign2 双签 PASS + consistency + comp1 + comp2）逐条收口。安全分析层结论（批次序/承重前置/标红债/owner 闸门）一字未改实质，仅补文档自包含性与计数一致性。所有内联实体从实体源 rg/读取真值，行号标「执行时重 rg」。

| # | 问题（来源）| 处置 |
|---|---|---|
| 1 | [P1·consistency] G02={R64,R65} 标签缺席致「42 簇」算术为假 | **修讫**：§0.1/§1.0 恢复 G02 标签 + 归位说明，§1.0 序列总览 & §1.2 成员清单标 `G02(R64+R65)`；41 独立 G 号 + G02 = 42 自洽 |
| 2 | [P2·consistency] 边数 删27/~138 vs 权威 删29/~136 | **修讫**：§0.2 C2 改「删 29（含方向并 2）+ 重建 ~136」，注明权威 `_layer2_residual:9`；全文仅此一处边数 |
| 3 | [P2·consistency] 承重「6」vs 行内 7 basename | **修讫**：§0.3 加计数说明「nav_publish+navigation_context 同 LB06 槽算 1、config 双栈同 LB07 槽算 1，共 6 承重点」|
| 4 | [P2·consistency] R52「差分 oracle 数量」口径不一 | **修讫**：核 verdict_V4=**2 个差分 oracle 函数(当前 :273/:290) + 5 处字面量行**，§1.3/§2/RK12 三处订正，旧数量表述标注为误记 |
| 5 | [P2·consistency] collar 调用方正文 7 vs 备注 8 | **修讫**：§1.4/§2-R42 回填「共 8 调用方 + 仅 3 真传 plan_id(navigation_context:78/reports_workbench:79/dashboard:92)」口径 |
| 6 | [P3·consistency] R42 navigation_context :78 vs :79/:80 | **修讫**：§1.4 加两锚区分注（:78=plan_id 读入/传参点；:79/:80=R56/R57 fixed fail-CLOSED 护栏禁区）|
| 7 | [P3·consistency] 爆点 #17 失踪 | **修讫·无需补编号**：核 _layer3 #17=「R52 dossier ~23 测试失真」是 R52 同源子爆点（与 #16 紧邻），§2-R52 加说明已并入测试归属安全路径闭合，#1–#23 连续无缺号 |
| 8 | [中·comp1] §3.1/§3.2 悬空跨引用 6 处 | **修讫·已内联**：新建 §3.1（`_positive_int` 12 处 family 对照表）+ §3.2（方向硬门两禁区行表），全文「见 §3.1/§3.2」就地可查 |
| 9 | [低·comp1] STRICT-4 同名异义 12 vs 9+ | **修讫**：§1.4 G22 + RK03「9+」统一为「12 处（Optional×5/STRICT×4/异签×3）」|
| 10 | [高 C1·comp2] 13 H 硬边从未枚举 | **修讫·已内联**：新增「§9 附录 13 条 H 硬边表」逐条列源→汇/门控/违序后果 + 计数溯源 |
| 11 | [高 C2·comp2] E03–E29 只引用未定义 | **修讫·已内联**：新增「§10 E03–E29 edge-id 对照速查表」id→源→汇→软硬→约束含义 |
| 12 | [高 C3·comp2] O09「PHASE0 §6 三问」缺失 | **修讫·已内联**：从 R55 dossier:154 抄三问原文（① 当下债 vs 在途中间态 ② :385 None 回退是否有意 ③ 裸删 vs 补 scope 标记）入 O09 + §1.3 G13 |
| 13 | [中 C4·comp2] 「Batch-1」撞名 | **修讫**：5 处本轮批次误称「Batch-1」改 ROOT/Batch-A；§5.1 旧批 + §1.0 简化声明 2 处保留并标「(旧 MASTER-PLAN 批号)」|
| 14 | [中 C5·comp2] 重 rg 纪律未落每批 | **修讫**：ROOT/Batch-A/Batch-D 各补「⚠本批重 rg 纪律」+ 高危锚点符号清单（Batch-B 已有位移总纲，Batch-C 靠它兜）|
| 15 | [中 C6·comp2] G05「173 行回归」无文件名 | **修讫**：核盘上 `tests/operation_execution/test_execution_review_identity_guard.py`=173 行，§1.1 ROOT 成员 + G05 前置补全名 + test_registry:289 |
| 16 | [中 C7·comp2] owner 表末列与「暂不分配」矛盾 | **修讫**：§3 表头 + 末列改「逻辑归属簇（非执行排期，待 owner 裁后才进批）」+ 消歧读法 |
| 17 | [低 C8/C9·comp2] 边数打架 + 24 重灾区文件未内联 | **修讫**：C8 边数同第 2 条一并修（删29/~136）；C9 新增「§11 附录 24 重灾区文件清单」内联，SCC 串行就地取用 |

**全文计数自检（收口后）**：
- 原子簇 **42**（G01–G42，G02={R64,R65} 标签已归位）+ GF1 前置门 = 43 调度单元 ✅
- H 硬边 **13**（§9 表逐条列，计数溯源至 `_interference_rebuilt §4.1`）✅
- 承重点 **6**（§0.3 计数说明：7 basename 去 LB06/LB07 同槽合并 = 6）✅
- 标红债 **11**（R09/R15/R19/R52/R14/R69/R54/R04/R42/R22/R05，§2 专项齐）✅
- 爆点 **23**（#1–#23 连续，#17 已说明归属，无缺号）✅
- owner 闸门 **38**（O01–O38，末列正名为「逻辑归属簇」）✅
- 边删 **29** / 重建 **~136**（跨簇有效约束边 29 = H 13/S 14/P 2）✅
- 6 硬阻断爆点 **#1/#7/#19/#20/#21/#22/#23** 逐条闭合 ✅
- **全文计数自洽，无数字打架**。安全分析层结论（批次序/承重前置/标红债/owner 闸门）实质未动。

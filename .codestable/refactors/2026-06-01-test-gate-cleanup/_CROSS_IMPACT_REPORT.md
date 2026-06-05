# A 先行对 B 的影响评估报告

## 一、总判断（先 A 后 B，影响到底多大？）

**结论：可控偏强耦合，需 2 处前置加固，但不必调整 A→B 的总顺序。** 经 8 维度核对 + 对抗验证后，先做 A 再做 B **不存在"会让 B 根本无法还债"的全局阻断**——A 的删/剪/合并刀口与 B 的承重护栏、灵魂线续命断言在内容上**系统性错开**（A 专剪脆性快照尾，B 专依赖真断言核心），A 总体不删 B 的安全网、不违反 B 承重纪律。

但有 **2 处真冲突必须在 A 落地前处置**，否则先 A 会塌掉 B 的局部安全网：(1) **`sort_strategy_case_insensitive` 合并簇**把 R51 灵魂线必须整体铲除的坏值静默回退断言焊进存活文件（D3 经对抗验证仍成立的 blocker）；(2) **A 的机读真相源 `L3_verdicts.csv` 与正文裁决自相矛盾**，多处把 B 全批次 go-no-go 门禁载体 `test_architecture_fitness.py` 标成 DROP，靠正文修正才保住（埋雷）。

最大的面状影响是 **P6 目录迁移导致 B 约 199 个锚点路径整体失效**（D6，high），但 B 已有"按符号重 grep 回盘"的成熟机制可吸收，属"大面积重定位"而非"安全网损毁"。

---

## 二、被对抗验证证伪 / 降级的发现（剔除与降级清单）

以"对抗验证后仍成立（holds=true）"为准，以下发现经验证**不成立或被显著降级**，已从真实冲突清单中剔除或下调：

| 维度 | 原发现 | 原定级 | 验证结论 | 处置 |
|---|---|---|---|---|
| **D1** | A 删 sp05 抽掉 B 的 G38/R26/R43 唯一回归门 | blocker | **证伪（holds=false）**：B 不是依赖 sp05 存活，而是**亲手要掏空/改它**；R26.md:200 明载 `load_bearing=false`，误删只响亮 ImportError，不破任何不变量。"唯一回归门"被引证反了。 | 剔除/降 low |
| **D1** | A 删 sp06 抽掉 R45/R48 loud 回归网 + R68 dedup 守卫 | blocker | **证伪**：B 的修法**恰恰是删 sp06 的一行**（R45.md:36）；所谓"漏退→FileNotFoundError"是保留 sp06 才有的风险，A 整删后该 failure mode 结构上不可能发生。R68 守卫根本不是 sp06。 | 剔除/降 low |
| **D2** | csv:620 与三份执行文档打架 → 误删 B oracle | medium | **证伪（holds=false）**：A 三份权威文档全部 KEEP，CSV 那格是 agent 原始误判已被正文当场推翻；唯一 CSV→rm 自动化硬筛 `verdict=='DROP'`，结构上排除 DROP_WITH_TOOL。 | 降 medium→台账卫生 |
| **D4** | enum_display 整文件无法切分（真冲突） | high | **证伪**：A 裁决理由**自带切分判据**——明写"unknown-passthrough/None-fallback 行为 VALUABLE 要保留"，R41 续命所需的 :59-61 恰是 A 点名要保留的行，二者方向一致。 | 降 high→medium |
| **D5** | 删 test_architecture_fitness 抽掉 B 每批 go-no-go | blocker | **证伪**：GOVERNANCE.md:6 定权威序 > CSV，三份上层文档显式"例外保留"，A 正常执行不会删。 | 降 blocker→medium 台账卫生 |
| **D5** | 删 verify_required/long_gate 让 run_quality_gate 抛 ImportError 打断 B | high | **证伪**：B fix-plan 全树对 `run_quality_gate` **0 命中**，B 各批门禁从不调它；且发现自承"风险仅在 A 内部中间态，不波及 B 执行期"。 | 剔除→none |
| **D6** | P6 让 89 个文件锚点路径整体失效（67 是冰山） | high | **降级**：'67 漏算'是误读（真相源表2标题已点名 P6 漂移）；KEEP/KEEP_TRIM 是 git mv 内容不变，无安全网被毁，B 本就按符号锚定。 | 降 high→medium |
| **D8** | A 把 R54/LB02/LB05 护栏 MERGE 撞"严禁合并"铁律 | blocker | **部分证伪**：承重"严禁删/合并"铁律约束的是承重**生产代码**，不是测试文件；R58=not-a-dependency。但 R54 对该测试文件的**锚点依赖真实**。 | 降 blocker→high（性质改为锚点漂移） |
| **D8** | architecture_fitness CSV vs 正文矛盾 | blocker | **降级**：同 D5，无机械路径会删它。 | 降 blocker→low 台账卫生 |

**仍成立（holds=true）的硬冲突只有两条**：D3 的 `sort_strategy` 合并（blocker 维持）、D6 的"B 缺 P6 级路径重映射协议"（medium 维持）。

---

## 三、按严重度分层的真实冲突

### 🔴 BLOCKER（A 落地前必须处置，否则先 A 不安全）

#### B-1【承重纪律相关 / 灵魂线】`sort_strategy_case_insensitive` 合并焊死 R51 必铲断言

- **冲突是什么**：A 按 P5 把 `regression_sort_strategy_case_insensitive.py` 与 `regression_sort_strategies_priority_case_insensitive.py` 参数化合并为一个**存活文件**，且 A 合并纪律"参数化后断言条数 ≥ 合并前各文件之和（去重）"**强制保留所有断言**。
- **涉及债**：R51（灵魂线，整体退场）。
- **文件**：`tests/regression_sort_strategy_case_insensitive.py`、`tests/regression_sort_strategies_priority_case_insensitive.py`、`core/algorithms/sort_strategies.py`。
- **为什么（证据）**：
  - A 裁决：`L3_verdicts.csv:431-432`（两文件同簇 `sort_strategy_case_insensitive`）+ `PLAN.md:205`（断言条数≥之和）+ `_CROSS_IMPACT_TRUTH.md:19,61`。
  - B 要求：`R51.md:40/43/86/99/123` + `PHASE4-SAFE-BATCH-PLAN.md:213`（G24）逐条要求该文件**"整体退场，禁迁移禁保留 :25 兜底断言（保留=复活 P4 静默回退）"**。
  - 实读 `regression_sort_strategy_case_insensitive.py:25`：`assert parse_strategy("unknown", default=SortStrategy.DUE_DATE_FIRST)==SortStrategy.DUE_DATE_FIRST` —— **正是灵魂线禁止的坏值静默回退**，被测的 `parse_strategy` 即 R51 删除目标 `sort_strategies.py:161-173`。
  - 实读合并目标 `regression_sort_strategies_priority_case_insensitive.py`：`grep parse_strategy 计数=0`，只测 `StrategyFactory.create+BatchForSort` 的优先级大小写排序 —— 这是 **R51 不删、有真价值的存活算法契约**。
  - 两文件测的是**不同契约**（string→enum 解析容错 vs 存活算法的优先级排序），A 的"same case-insensitivity contract"是误判。合并后 R51 无法 `git rm` 整文件（会连带删存活契约），只能做"外科摘除一支 parametrize"——而这**与 A 的断言条数纪律正面冲突**，A 合并者若守纪律就会拒绝删该支。两份门禁互判对方违规。
- **怎么缓解**：把 `regression_sort_strategy_case_insensitive.py` **移出合并簇**，改判随 R51 整体退场（DROP-with-debt），`priority` 文件独立 KEEP 不合并；并在 A 的 GOVERNANCE 合并对账表给该簇打 **`B-R51 例外`** 标记。若 A 已合并，则 R51 执行时改为"外科删除源自 parse_strategy 的那条 parametrize 用例 + 删 `sort_strategies.py:161-173`"，并在 PR 注明"此处 A 合并纪律为 R51 灵魂线让位"。

> **⚠️ 承重纪律红线提示**：此条是先 A 后 B 中唯一经对抗验证仍成立、且直接触及"灵魂线续命断言被反向钉成契约存活"的冲突。R51 的灵魂线诉求是**根除**坏值静默回退，A 的合并把它**焊成永久契约**——这是与 B 承重/灵魂线纪律方向相反的实质冲突，必须先修 A 裁决。

---

### 🟠 HIGH（B 需大面积重定位锚点 / 核验断言完整性）

#### B-2 `workbench_link_guardrails` 被合并 —— R54/LB02/LB05 的 fail-open 逐键四态 parity oracle 锚点失效

- **冲突是什么**：A 把 `regression_scheduler_workbench_link_guardrails.py` 并入 `workbench_links_viewmodel` 簇（`git rm` 原文件 + parametrize 重组）。该文件是 R54 删手维面所需的逐键四态拦放 parity oracle 落点。
- **涉及债**：R54、LB02、LB05。
- **文件**：`tests/regression_scheduler_workbench_link_guardrails.py`、`tests/regression_scheduler_workbench_links_contract.py`、`web/viewmodels/scheduler_workbench_links.py`、`core/services/report/execution_review.py`。
- **为什么（证据）**：`R54.md:76/:118` 精确锚定 `_is_formal_adopted_context` 下游读端逐键 `:120-162`（`:131 pop / :136 =False / :137 is_comparison=True / :147 is_superseded=True`），实读代码 `:121-150` 逐行吻合；`explode_r2/r3:58/63` 要求"删手维面前先迁 :120-162，同 commit 避免护栏裸奔窗口"；`PHASE4:286`"R54:5 套 delegate 前后逐键四态拦放一致"。**注意定性已被验证修正**：承重"严禁合并"铁律约束的是承重**生产代码**，不是测试文件，故 R58=not-a-dependency，**这不是承重纪律违规**；但 A 合并的"去重"步骤有吞掉 guard 侧断言的真实风险（两文件都 import `can_emit_feedback_write_urls`、都测 execution_review 链，存在断言重叠）。
- **怎么缓解**：(1) A 合并时**强制保留全部 guard 断言**（四态矩阵 :121-150、`forbidden_keys` :233、`can_emit` 逐字段 :23-52），**对 guard 断言禁止去重**；(2) A 合并 commit 记录原 test 函数迁入新文件的位置；(3) B 的 R54 ROOT/Batch-C 动手前 `rg test_execution_review_guardrail_uses_full_plan_identity` 确认函数仍在、四态用例齐；(4) **排期上让 B 的 G04/G05 与 A 的 workbench_links_viewmodel 合并避免交叠窗口**，不可两边同期改这两文件。LB02/LB05 侧实为 low（仅需把 CI 回归命令里的文件路径改名）。

#### B-3 P6 目录迁移让 B 约 199 个锚点的路径维度整体失效

- **冲突是什么**：A 的 P6 把 tests/ 根目录 **626 个平铺文件**迁入 `tests/<模块>/<子模块>/` 并去前缀，B 76 份 dossier 中**约 199 个去重 `tests/xxx.py:line` 锚点（覆盖 105 个文件，其中 ~86-89 个 KEEP/KEEP_TRIM）**的路径整体失效。
- **涉及债**：全体 76 债通用（典型 R05/R22/R59/LB02/R54）。
- **为什么（证据）**：实测 `find tests -maxdepth 1 *.py = 626`，与 `PLAN.md:182` 字字吻合；B 锚点形如 `R59.md:124 tests/regression_web_silent_fallback_contract.py:241-250`，P6 去前缀+迁子目录后路径不复存在。B 另有 **~22 条 grep 核验命令把 `tests/<旧文件名>.py` 写死**（P6 改名后直接 no-such-file）。
- **关键缓和事实**：P6 是 **git mv（内容不变）**，B 依赖的断言体逐字幸存，**零安全网被删、零承重纪律违规**；B 已有"档案行号一律视为待复核 + 按符号重 grep 回盘"成熟机制（已吸收过 +9/+180~190 行历史漂移），故为 high 不升 blocker。
- **怎么缓解**：A 执行 P6 时产出一份**"旧路径→新路径"映射表**（git mv 全程可机械生成）；B 在 A 定稿后对 76 份 dossier 跑一次性脚本，按"去前缀文件名 + 符号名"重新 grep 全部 199 个锚点；把 B 的 ~22 条 `rg PATTERN tests/具体文件.py` 升级为 `rg -rn PATTERN tests/`（跨改名仍命中符号）；ANCHOR-DRIFT 备忘补一节"P6 落地后批量路径重映射 SOP"。

---

### 🟡 MEDIUM（局部锚点漂移 / 需现场 grep / 台账卫生）

| 编号 | 冲突 | 债 | 文件 | 证据 file:line | 缓解 |
|---|---|---|---|---|---|
| B-4 | enum_display 单测函数内 A 剪标签对与 R41 要改 loud 的坏值行交织，粗心按"L14-61"整删会误删 :59-61 | R41 | `tests/test_enum_display_consistency.py` | `_CROSS_IMPACT_TRUTH.md:54` A 理由自述坏值/None 行 valuable 须保留；`R41.md` :59-61 是收口前差分 oracle | A 行级手术：只删纯标签映射行，保留 :18/:19-20/:23/:59-61；交接清单标注"R41 待改写，勿删坏值/None 行" |
| B-5 | `route_registration_contract` 并簇致 R43 要改的 :88 wrapper import 锚点漂移 | R43 | `tests/test_scheduler_route_registration_contract.py` | `R43.md:104/141` :88 `importlib.import_module("web.routes.scheduler_run")` | R43（Batch-D）按 `test_legacy_leaf_import` 函数名/import 字符串 rg 重定位，弃裸行号 |
| B-6 | `aps_workbench_flow_contract` 并簇，R57 PIN 的"有意 fallback 透传"断言易被当冗余去重 | R57（已 fixed） | `tests/regression_aps_workbench_flow_contract.py` | `_fixed_confirm.md:86` :346/:347/:353 `home_query[plan_role]==[baseline_best]` 被 PIN | A 合并时标 `R57-PINNED 勿去重`，逐条保留三 PIN 断言；B 侧合并后跑一次确认红线生效 |
| B-7 | P3 把 22 个 B 依赖的 main-style 文件 `def main→def test_xxx`，符号锚点改名 | R05/R32/R51/R04/R70 等 | `test_scheduler_resource_dispatch_smoke.py` 等 22 个 | 实测 22 个 main-style 在 P3 改写面 | B 锚【被测生产符号/断言字符串】（P3 不动）而非测试函数名；勿照抄绝对行号 |
| B-8 | `regression_aps_three_gap_docs_quality_gate` 反向 doc-pin 门被 A 剪，R20 失记账自证 | R20（R15/R49/R69 不受波及） | `tests/regression_aps_three_gap_docs_quality_gate.py` | `R20.md:101/136`；`R20.md` 自评"记账失败非安全失守" | 非安全网；B 侧 R20 把 docs_quality_gate 自证换成直接 grep 指南文本，或 A 保留 `test_developer_guide_lists_*` 单测 |
| B-9 | `test_registry_groups_scheduler.py`（tools/）P0.3 收窄通配，B 新建的 parity 测试可能落在被收窄掉的路径 | R56 + 门禁可判定性 | `tools/test_registry_groups_scheduler.py` | `PLAN.md:65` P0.3 改 36 个 `**`；`PHASE4:130` B 按全名核存在 | P0.3 后跑 `daily_gate_scope_payload` 验证 B 现存锚点仍被收集；B 新建 3 个 parity 测试须显式登记进门禁组 |
| B-10 | R29 曾把 A 的 `L3_verdicts.csv:174` 当授权依据，分析时该目录 ABSENT 致"授权链断裂"被迫 owner-pending | R29 | `_fixed_confirm.md`、`_registry.json`、`common/number_utils.py` | A 产物状态漂移已实际反噬 B 一条裁决（目录现已补回） | B 启动前重新核对所有引用 A 产物的 B 锚点（尤其 R29），按 A 当前定稿状态重判 |
| B-11 | **（台账卫生）** `L3_verdicts.csv:620` 仍标 `test_architecture_fitness.py` 为 DROP_WITH_TOOL，与 GOVERNANCE/PLAN/L3 正文的 KEEP 修正打架 | R15/R28 | `L3_verdicts.csv:620` | 正文 `GOVERNANCE.md:109`/`PLAN.md:41,123`/`L3_VERDICTS.md:91,96` 全 KEEP；CSV→rm 仅硬筛 `=='DROP'`，结构上排除 | 执行前就地把 csv:620 改成 KEEP 消雷；严禁裸筛 CSV `DROP_WITH_TOOL` 后 `git rm` |

---

## 四、量化汇总

| 量化项 | 数值 | 说明 |
|---|---|---|
| **A 会"物理删除"的 B 依赖测试** | **0 个**（经验证） | sp05/sp06/py38/check/smoke 全部经对抗验证为 B 不依赖其存活（B 反而要删/不靠它），无现存安全网被 A 误删 |
| **A 合并会"反向焊死/有去重风险"的 B 断言** | **2 处** | sort_strategy（blocker，焊死 R51 必铲断言）、workbench_link_guardrails（high，去重有吞 guard 断言风险） |
| **A 会令路径整体失效的 B 锚点** | **~199 个**（覆盖 ~105 个文件，其中 ~86-89 个 KEEP/KEEP_TRIM 内容保留但 P6 必迁） | P6 迁移，git mv 内容不变，按符号可重定位 |
| **P3 改函数名影响的 B 依赖 main-style 文件** | **22 个** | `def main→def test_xxx`，B 改锚生产符号即可吸收 |
| **P5 剪尾致行号上移的 B 依赖 KEEP_TRIM 文件** | **27 个** | 实测剪除区与 B 依赖区系统性错开，纯行号顺移 |
| **B 写死 `tests/<文件>.py` 路径、P6 后失效的 grep 核验命令** | **~22 条** | 需升级为 `rg -rn PATTERN tests/` |
| **承重纪律实质违规** | **0 处确认** | D8 原报 1 处（workbench MERGE）经验证为锚点漂移而非纪律违规；唯 sort_strategy 触及灵魂线方向冲突（B-1） |
| **A 内部裁决/台账自相矛盾埋雷** | **2 处** | `csv:620` 与 `csv:431-432 簇登记`，均需执行前对齐正文 |

---

## 五、顺序与前置加固建议（坚持先 A 后 B 的前提下）

### 5.1 必须为 B 做保护的 A 阶段

| A 阶段 | 动作 | 为 B 做的保护 | 对应冲突 |
|---|---|---|---|
| **P5 合并（剪尾/MERGE）** | 合并 `sort_strategy_case_insensitive` 簇 | **🔴 把 `regression_sort_strategy_case_insensitive.py` 移出合并簇，改随 R51 退场；对账表打 `B-R51 例外`** | B-1 |
| **P5 合并** | 合并 `workbench_links_viewmodel` 簇 | **强制保留全部 guard 四态断言，禁对 guard 去重；记录函数迁入新位置；与 B 的 G04/G05 错开窗口** | B-2 |
| **P5 合并** | 合并 `workbench_context_propagation` 簇 | 标 `R57-PINNED 勿去重`，逐条保留 :346/:347/:353 | B-6 |
| **P5 剪尾** | 剪 `test_enum_display_consistency.py` | 行级手术保留 :18/:19-20/:23/:59-61，勿按 L14-61 整删 | B-4 |
| **P6 迁移** | 626 文件迁子目录去前缀 | **必须等全部 P0-P7 跑完、tests 定稿后再启动 B（严禁迁移中途穿插 B）；产出旧→新路径映射表；B 在 A 定稿后一次性脚本重生成 199 个 dossier 锚点** | B-3 |
| **P3 改写** | main-style → pytest | 记录 22 个文件改写后函数迁入位置；B 锚生产符号/断言串 | B-7 |
| **P2.2 删工具** | 删 verify_required/简化 long_gate | **删工具 + 重接 `run_quality_gate.py` import/编排 + 删 :1680 硬编码路径校验放在同一原子提交**（只影响 A 内部中间态，A 完成态门禁可用后才交棒，不波及 B） | （D5，已降级） |
| **P0.3** | 收窄 test_registry 通配 | 收窄后跑 `daily_gate_scope_payload` 确认 B 锚点测试仍被收集；B 新建 parity 测试须显式登记 | B-9 |
| **A 收尾（台账对齐）** | 修正机读真相源 | **就地把 `L3_verdicts.csv:620`（architecture_fitness）改 KEEP、`csv:431-432`（sort_strategy 簇）按 B-R51 例外标注**，使机读源与正文一致 | B-11、B-1 |
| **禁删清单** | A 的禁删/不可删清单 | 将 `test_architecture_fitness.py`（B 全批次 go-no-go 门禁载体，含 0 分层违规 + R28 :77 白名单 + silent_fallback 台账）明确列入 A 的禁删清单 | B-11 |

### 5.2 对 B 零影响、可放心先做的 A 阶段

- **P0 配置提速**（FOCUSED 调整、scope 通配收窄的非破坏部分）—— 除 P0.3 需配套验证外，配置提速本身对 B 零影响。
- **删除 6 个门禁自指工具**（check_quickref/selftest_report_metadata 等）—— B 零引用，删之无碍。
- **A 对 `.codestable/semantics/` 全程不碰** —— B 的语义雷达门 `run_semantic_guards.py`/`run_drift_scan.py` 与 drift 基线在 A 执行后原样可用。
- **A 删 sp05/sp06/py38/real_db_replay check/smoke** —— 经对抗验证 B 不依赖其存活（B 反而要删/不靠它），**A 先删对 B 是减负**；唯一须做的是**交接：把 B dossier 里"同提交退 sp05/sp06 断言行"的步骤标注为"已由 A 删除，本步无操作"**，避免 B 执行时去改不存在的文件而困惑。

### 5.3 一句话收尾

先 A 后 B 的总顺序**无需调整**；只要在 A 落地前钉死两件事——**(1) `sort_strategy` 文件移出合并簇（保住 R51 灵魂线）、(2) `architecture_fitness` 与全部机读 CSV 对齐正文 KEEP**——并在 P5/P6 按上表做好合并去重保护与路径映射交接，B 即可在 A 定稿后安全启动。**唯一须显著标红的承重/灵魂线方向冲突是 B-1（sort_strategy 焊死 R51 必铲断言）**，其余皆为可控的锚点漂移与台账卫生。

—— 相关权威文档绝对路径：
- A：`/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/{GOVERNANCE.md,PLAN.md,L3_VERDICTS.md,L3_verdicts.csv,_CROSS_IMPACT_TRUTH.md}`
- B：`/Users/lurenxing/Documents/GitHub/----/.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety/{PHASE4-SAFE-BATCH-PLAN.md,OWNER-DECISIONS-2026-06-05.md,ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md,dossiers/,clusters/}`
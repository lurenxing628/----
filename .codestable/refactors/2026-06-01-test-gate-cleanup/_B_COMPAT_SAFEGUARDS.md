# A(test-gate-cleanup)执行时的 B(80 条水下债)兼容护栏清单

> **执行 A 的人/AI 必读。** 本清单把 `_CROSS_IMPACT_REPORT.md`(20 agent 8 维度核对 + 对抗验证)的全部加固点细化到「触发阶段 + 精确文件:行 + 必做动作 + 验证命令 + 对应 B 债」级别。
> 上游事实源:`_CROSS_IMPACT_TRUTH.md`(确定性交集)、`_CROSS_IMPACT_REPORT.md`(裁决报告)。
> B 计划权威目录:`.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety/`(PHASE4-SAFE-BATCH-PLAN.md / OWNER-DECISIONS-2026-06-05.md / dossiers/ / ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md)。

---

## 0. 一句话纪律

**先 A 后 B 的总顺序无需调整。** 经对抗验证,A 不物理删除任何 B 现存安全网、不违反 B 承重纪律(承重护栏「严禁删/合并」约束的是**生产代码**,不是测试文件)。但有 **2 件事必须在 A 落地前钉死**,且 **P5/P6 两个阶段必须按本表保护**,否则先 A 会塌掉 B 的局部安全网或让 R51 灵魂线诉求反向失败:

1. **🔴 `regression_sort_strategy_case_insensitive.py` 必须移出合并簇**(已在 `L3_verdicts.csv` 落实为 `HOLD_FOR_R51`)。
2. **🟠 `L3_verdicts.csv` 两处埋雷已就地消除**(`test_architecture_fitness.py` 改回 `KEEP`;`sort_strategy` 簇解散)——**严禁裸筛 csv `verdict` 后机械 `git rm`**。

---

## 1. 🔴 BLOCKER（A 落地前必处置）

### B-1 `sort_strategy` 合并会焊死 R51 灵魂线「必铲」断言

| 项 | 内容 |
|---|---|
| **触发阶段** | P5.1 MERGE 簇合并 |
| **对应 B 债** | **R51**（灵魂线,Batch-7 / G24,与 R49+R50 同原子） |
| **冲突本质** | A 原把 `regression_sort_strategy_case_insensitive.py` 与 `regression_sort_strategies_priority_case_insensitive.py` 合并为一个**存活文件**,且 A 合并纪律「参数化后断言条数 ≥ 合并前之和」会**强制保留** `:25` 的 `parse_strategy("unknown", default=X)==X` —— 而这条**正是 R51 灵魂线要根除的 P4 坏值静默回退**。合并 = 把已判死刑的兜底语义焊成永久契约,与 B 方向正面对撞。 |
| **证据** | A:`L3_verdicts.csv` 原 431/432 行同簇;`PLAN.md` P5.1「断言条数≥之和」。 B:`R51.md:35-44`「直删 `sort_strategies.py:161-173` 整个 `parse_strategy` + **两续命测试整体退场,严禁保留 :25 兜底续命**」;`PHASE4-SAFE-BATCH-PLAN.md:213`(G24)。 实读:`regression_sort_strategy_case_insensitive.py:25` 确为坏值兜底断言;`regression_sort_strategies_priority_case_insensitive.py` `grep parse_strategy 计数=0`,测的是 StrategyFactory 存活算法,两文件契约**不同**,原合并判定有误。 |
| **必做动作（已落实)** | csv 已改:`regression_sort_strategy_case_insensitive.py` → `verdict=HOLD_FOR_R51`、merge_cluster 清空(A 阶段**不合并·不剪·不删·不迁**,命运绑 R51);`regression_sort_strategies_priority_case_insensitive.py` → `verdict=KEEP`、merge_cluster 清空(独立保留,不进任何簇)。 |
| **A 执行时校验** | 合并阶段确认 `sort_strategy_case_insensitive` 簇**已不存在**:`rg "sort_strategy_case_insensitive" L3_verdicts.csv` 应仅命中 `HOLD_FOR_R51` 那一行的文件名,无 `MERGE:` 行。 |
| **交棒给 B** | R51 执行(Batch-7,与 R49/R50 同原子,从大行号往小删)时,`git rm tests/algorithm/test_sort_strategy_case_insensitive.py` + `git rm tests/resource_dispatch/test_dispatch_rule_case_insensitive.py` + 删 `sort_strategies.py:161-173`,**不写 parity**(R51.md:77-86 行为故意不等价)。 |

> **关联**:R51 的**另一续命测试** `regression_dispatch_rule_case_insensitive.py`(csv 行 323,A 判 `KEEP`)同样要随 R51 整体退场。csv 已加标注:**A 勿在 P7 防回潮门禁里把它锁成「有价值测试」**,否则 B 删它时会触发新门禁。

---

## 2. 🟠 HIGH（B 需大面积重定位 / 核验断言完整性）

### B-2 `workbench_link_guardrails` 合并有吞 guard 断言风险（R54/LB02/LB05）

| 项 | 内容 |
|---|---|
| **触发阶段** | P5.1 合并 `workbench_links_viewmodel` 簇 |
| **对应 B 债** | **R54**（5 套手维 guard 面 + 双分叉,ROOT/Batch-C）、**LB02/LB05**（execution_review 承重宿主） |
| **冲突本质** | 该文件是 R54 删手维面所需的**逐键四态拦放 parity oracle** 落点。两簇文件都 import `can_emit_feedback_write_urls`、都测 execution_review 链,合并「去重」步骤有吞掉 guard 侧断言的真实风险。**注意:这不是承重纪律违规**(铁律约束生产代码,非测试),但断言丢失会让 R54 失去回归网。 |
| **证据** | `R54.md:76/:118` 锚 `_is_formal_adopted_context` 下游逐键 `:120-162`(`:131 pop`/`:136 =False`/`:137 is_comparison=True`/`:147 is_superseded=True`);`explode_r2/r3:58/63`「删手维面前先迁 :120-162,同 commit 避免护栏裸奔」;`PHASE4:286`「R54:5 套 delegate 前后逐键四态拦放一致」。 |
| **必做动作** | A 合并时:① **对 guard 断言禁止去重**,逐条保留四态矩阵(`:121-150`)、`forbidden_keys`(`:233`)、`can_emit` 逐字段(`:23-52`);② 在合并 commit 里**记录原 test 函数迁入新文件的位置**;③ csv 已加 `[⚠B-COMPAT B-2]` 标注。 |
| **排期纪律** | **B 的 G04/G05(R54)与 A 的 `workbench_links_viewmodel` 合并避免交叠窗口**——不可两边同期改 `regression_scheduler_workbench_link*.py` 与 `web/viewmodels/scheduler_workbench_links.py`。 |
| **A 执行时校验** | 合并后 `rg "def test_.*guardrail" tests/`(新文件)确认 guard 测试函数仍在;`rg "forbidden_keys|is_superseded|is_comparison" tests/`(新文件)四态断言齐。 |
| **B 执行时校验** | R54 动手前 `rg "test_execution_review_guardrail_uses_full_plan_identity" tests/` 确认函数仍在、四态用例齐。 |

> LB02/LB05 侧实为 **low**:仅需把 CI 回归命令里的文件路径改名,不涉断言。

### B-3 P6 目录迁移令 B 约 199 个锚点的路径维度整体失效（全体 76 债通用）

> **✅ 2026-06-08 已解锁 + A 侧已执行**：A 全部 P0–P7 已收官（P6 定稿），B-3 的「P6 后、tests 定稿后再启 B」时序闸**已满足**，B 现可启动。「旧→新路径映射表」= `.codestable/refactors/2026-06-01-test-gate-cleanup/p6_path_map.csv`（561 行）已落地；B 的 ~199 dossier 锚点 + 84 门禁载体路径 + `_registry.json` 已由同目录 `remap_b_anchors.py` 一次性机械重映射完成（IN_CSV 残留 0，PHASE4/dossiers/OWNER 导航文档 0 残留）；6 个 P1 删 / P5 合并文件不在表内、已就地回写终态。下表为原始预案，保留作背景。

| 项 | 内容 |
|---|---|
| **触发阶段** | P6 目录重组(626 文件迁 `tests/<模块>/<子模块>/` + 去前缀 + 改 testpaths) |
| **对应 B 债** | 全体 76 债通用(典型 R05/R22/R59/LB02/R54) |
| **冲突本质** | B 76 份 dossier 含**约 199 个去重 `tests/xxx.py:line` 锚点(覆盖 ~105 文件,其中 ~86-89 个 KEEP/KEEP_TRIM)**,P6 去前缀+迁子目录后路径全部不复存在;另有 **~22 条 grep 核验命令把 `tests/<旧文件名>.py` 写死**,P6 改名后直接 no-such-file。 |
| **关键缓和** | P6 是 **git mv(内容不变)**,B 依赖的断言体逐字幸存——**零安全网被删、零承重违规**;B 已有「档案行号一律视为待复核 + 按符号重 grep 回盘」成熟机制(ANCHOR-DRIFT 已吸收过历史漂移)。故定 high 不升 blocker。 |
| **必做动作** | ① **P6 必须等全部 P0-P7 跑完、tests 定稿后再启动 B,严禁迁移中途穿插 B**;② A 执行 P6 时**产出一份「旧路径→新路径」映射表**(git mv 全程可机械生成,如 `git log --diff-filter=R --summary` 或迁移脚本直接落 csv);③ 交给 B:在 A 定稿后跑一次性脚本,按「去前缀文件名 + 符号名」重新 grep 全部 199 个锚点重生成 dossier;④ 把 B 的 ~22 条 `rg PATTERN tests/具体文件.py` 升级为 `rg -rn PATTERN tests/`(跨改名仍命中符号);⑤ **A 自己的路径锚点同样会断,分两机制(2026-06-06 核验更正,勿混述为「硬校验 required」)**：**(硬失败)** `tools/test_registry.py:64-65/77` 的 `count("/")==1` 单层校验作用于 **test-only helper / helper-impact 目标**(`_is_top_level_test_only_helper_path` / `_is_regular_helper_impact_target`，**非 required**),P6 迁子目录会让这些 helper 路径 `raise ValueError`,须放开校验或同步改 `TEST_ONLY_HELPER_IMPACT`;**(软失配)** required/startup 清单走 `normalize_test_paths`(:111-124)**无单层校验、不 raise**,P6 后**静默失配 / 报 missing**,须批量重写 `test_registry_data.py` 的 required+startup 路径。「旧→新」映射须**同时覆盖 B 的 199 dossier 锚点 + A 的 required/startup 清单两套**(本表原只列了 B 锚点)。 |
| **更新 B 文档** | 在 B 的 `ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md` 补一节「P6 落地后批量路径重映射 SOP」。 |

---

### B-12 锁 `architecture_fitness=KEEP` 后，P2.2 删 `architecture_scan_cache.py` 会断其 import 链（🔴红队 2026-06-05 补，HIGH）

> **✅ 2026-06-08 已消解**：A 的 P2.2 实际走「塌缩缓存层」（提交 `0506b27d`）而非裸删——`tools/architecture_scan_cache.py` 仍存（公共 API 全保留）、三段 import 链通、`tests/gate_meta/test_architecture_fitness.py` collect 21 项无 error。预警的 collection-error 未发生，B go-no-go 载体健康、无需 B 侧动作。（注：`architecture_*_scan_map`/`*_scan_entries` 系列 API 实际散在 `quality_gate_operations` 等、非全定义于 `architecture_scan_cache.py`，但塌缩已保 import 链通，不影响结论。）下表为原始预案。

| 项 | 内容 |
|---|---|
| **触发阶段** | P2.2 脚手架瘦身（PLAN.md「删 `architecture_scan_cache.py` + 缓存」） |
| **对应 B 债** | B 全批次 go-no-go（R15/R28 + C-EXEC-FACT 分层红线靠 `test_architecture_fitness.py` 守） |
| **冲突本质** | 我已把 `test_architecture_fitness.py` 锁 `KEEP`，但它到 `architecture_scan_cache` 是**三段顶层硬 import**：`test_architecture_fitness.py:25 → tools/quality_gate_support.py:32 → tools/quality_gate_operations.py:5 → tools/architecture_scan_cache.py`。P2.2 裸删该模块 → architecture_fitness **一 import 即 collection-error** → A 的 P2 门禁红、B go-no-go 起不来。**这是锁 KEEP 后新生的配套义务，首轮漏写（红队 RT2 抓出）。** |
| **A 自身前置矛盾（非本加固引入）** | `scripts/run_quality_gate.py:26` 顶层 `from tools.architecture_scan_cache import architecture_scan_cache_metadata`（:1951 调用）+ `tests/gate_meta/test_architecture_scan_cache.py`（csv:8 判 KEEP_TRIM）都直连该模块——**A 一边要删模块、一边留 live 门禁入口和自测，P2.2 本身就与 A 自己冲突**，先于本加固存在。 |
| **必做动作** | P2.2「删 `architecture_scan_cache.py`」必须改为「**塌缩缓存层**」并放**同一原子提交**：①保留 `aggregate_architecture_scan`/`scan_files_with_cache`/`architecture_oversize_scan_map`/`architecture_complexity_scan_map`/`architecture_silent_scan_entries` 的公共 API 行为（移壳或留薄实现）；②改接 `tools/quality_gate_operations.py:5` 与 `scripts/run_quality_gate.py:26` 的 import；③同步处理 `tests/gate_meta/test_architecture_scan_cache.py`。 |
| **验证** | `.venv/bin/python -m pytest tests/gate_meta/test_architecture_fitness.py --collect-only`（删 cache 后 collection 不炸）+ `.venv/bin/python scripts/run_quality_gate.py --require-clean-worktree`（live 门禁不 ImportError）。 |
| **门级纪律** | **P2.2 真正落地前必须解决此项**（P2 早于 P5/P6，有窗口）；未解决前 `test_architecture_fitness.py` 的 KEEP 是空头支票。 |

---

## 3. 🟡 MEDIUM（局部锚点漂移 / 需现场 grep / 台账卫生）

| 编号 | 触发阶段 | 冲突 | B 债 | 精确动作 + 验证 |
|---|---|---|---|---|
| **B-4** | P5.2 剪 `test_enum_display_consistency.py` 脆性尾 | A 剪标签对与 R41 要改 loud 的坏值行交织,粗心按「L14-61」整删会误删 `:59-61` | R41 | **行级手术**:只删纯标签映射行,**保留 `:18`/`:19-20`/`:23`/`:59-61`**(坏值·None·passthrough 行,R41 收口前差分 oracle);csv 已加 `[⚠B-COMPAT B-4]` |
| **B-5** | P5.1 `scheduler_route_registration` 并簇 | 致 R43 要改的 `:88` wrapper import 锚点漂移 | R43(Batch-D) | R43 按 **`test_legacy_leaf_import` 函数名 / `importlib.import_module("web.routes.scheduler_run")` import 字符串** rg 重定位,弃裸行号 |
| **B-6** | P5.1 `aps_workbench_flow_contract` 并簇 | R57 PIN 的「有意 fallback 透传」断言易被当冗余去重 | R57(已 fixed) | A 合并时标 `R57-PINNED 勿去重`,**逐条保留 `:346`/`:347`/`:353`** `home_query[plan_role]==[baseline_best]`;csv 已加标注;B 侧合并后跑一次确认红线生效 |
| **B-7** | P3 main-style→pytest | 22 个 B 依赖的 main-style 文件 `def main→def test_xxx`,符号锚点改名 | R05/R32/R51/R04/R70 等 | B 锚**被测生产符号/断言字符串**(P3 不动)而非测试函数名;勿照抄绝对行号。A 记录改写后函数迁入位置 |
| **B-8** | P1/P5 剪 `regression_aps_three_gap_docs_quality_gate` 反向 doc-pin | R20 失记账自证(非安全网) | R20(R15/R49/R69 不波及) | B 侧 R20 把 docs_quality_gate 自证换成直接 grep 指南文本,或 A 保留 `test_developer_guide_lists_*` 单测 |
| **B-9** | P0.3 收窄 `tools/test_registry_groups_scheduler.py` 36 个 `**` | B 新建的 parity 测试可能落在被收窄掉的 scope | R56 + 门禁可判定性 | P0.3 后跑 `daily_gate_scope_payload` 验证 B 现存锚点测试仍被收集;**B 新建的 3 个 parity 测试须显式登记进门禁组** |
| **B-10** | A 产物状态漂移 | R29 曾把 A 的 `L3_verdicts.csv:174` 当授权依据,分析时该目录 ABSENT 致「授权链断裂」被迫 owner-pending(目录现已补回) | R29 | **B 启动前重新核对所有引用 A 产物的 B 锚点(尤其 R29),按 A 当前定稿状态重判** |
| **B-11** | A 收尾台账对齐 | `csv:620` 曾标 `test_architecture_fitness.py` 为 DROP_WITH_TOOL,与正文 KEEP 打架 | R15/R28 | **已就地改回 `KEEP`**;严禁裸筛 csv `DROP_WITH_TOOL` 后 `git rm`;`architecture_fitness` 列入 A 禁删清单 |

---

## 4. A 各阶段为 B 做的保护（执行清单）

| A 阶段 | 动作 | 为 B 做的保护 | 冲突 |
|---|---|---|---|
| **P0.3** | 收窄 test_registry 通配 | 收窄后跑 `daily_gate_scope_payload` 确认 B 锚点测试仍被收集;B 新建 parity 须显式登记 | B-9 |
| **P3 改写** | main-style→pytest | 记录 22 文件改写后函数迁入位置;B 锚生产符号/断言串 | B-7 |
| **P5.1 合并** | `sort_strategy` 簇 | 🔴 已移出簇(`HOLD_FOR_R51`),A 不动,绑 R51 | B-1 |
| **P5.1 合并** | `workbench_links_viewmodel` 簇 | 强制保留 guard 四态断言,禁去重;记录迁入位置;与 G04/G05 错开窗口 | B-2 |
| **P5.1 合并** | `workbench_context_propagation` 簇 | 标 `R57-PINNED 勿去重`,保留 `:346/:347/:353` | B-6 |
| **P5.1 合并** | `scheduler_route_registration` 簇 | 合并 commit 记录 wrapper import 锚点新位置 | B-5 |
| **P5.2 剪尾** | `test_enum_display_consistency.py` | 行级手术保留 `:18/:19-20/:23/:59-61` | B-4 |
| **P6 迁移** | 626 文件迁子目录去前缀 | 🟠 等 A 全部 P0-P7 跑完再启 B;产「旧→新路径映射表」;B 一次性脚本重生成 199 锚点 | B-3 |
| **P2.2 删工具** | 删 verify_required / 简化 long_gate / **塌缩 architecture_scan_cache** | 🔴**B-12 HIGH**：删 `architecture_scan_cache.py` 必须改「塌缩缓存层」——保留 `architecture_*_scan_map`/`aggregate_architecture_scan`/`scan_files_with_cache` 公共 API + 改接 `quality_gate_operations.py:5`、`run_quality_gate.py:26` + 同步 `test_architecture_scan_cache.py`，放同一原子提交；否则锁 KEEP 的 `test_architecture_fitness.py` collection-error（A 门禁红 + B go-no-go 起不来）。验证 `pytest tests/gate_meta/test_architecture_fitness.py --collect-only`（✅2026-06-08 已消解：A 走塌缩非裸删，模块仍存、collect 21 无 error）| B-12 |
| **A 收尾** | 台账对齐 | 已改 `csv:620`→KEEP、`sort_strategy` 簇解散;`architecture_fitness` 列入禁删清单 | B-11/B-1 |

---

## 5. 对 B 零影响、可放心先做的 A 部分

- **P0 配置提速**（FOCUSED 调整、scope 通配收窄的非破坏部分）——除 P0.3 需配套验证(B-9),配置提速本身对 B 零影响。
- **删 6 个门禁自指工具**（check_quickref / selftest_report_metadata 等)——B 全树 0 引用,删之无碍;且 B 各批门禁**从不调 `run_quality_gate`**(fix-plan 全树 0 命中)。
- **A 全程不碰 `.codestable/semantics/`**——B 的语义雷达门 `run_semantic_guards.py` / `run_drift_scan.py` 与 drift 基线在 A 执行后原样可用。
- **A 删 sp06/py38/real_db_replay check/smoke**——经对抗验证 **B 不依赖其存活**(B 反而要删/不靠它,A 先删对 B 是减负);交接:把 B dossier 里「同提交退 sp06 断言行」的步骤标注为「已由 A 删除,本步无操作」。
  - 具体:`R45.md:36` B 的修法本就是删 sp06 一行。
  - **🔴 更正(第三轮红队 2026-06-05):`test_sp05_path_topology_contract.py` 不在此列——首版把 sp06 的结论张冠李戴到了 sp05。sp05 实为 R43(改其三表)/R01/R26 的串行依赖 + B 的 Batch-A G38 门禁载体,A 不可在 P1.1 早删。已改 csv 为 `HOLD_FOR_R43`,详见 §8 B-13。**

---

## 6. 本次已就地落实的 csv 消雷记录（`L3_verdicts.csv`,2026-06-05）

| 文件 | 原 verdict | 新 verdict | 原因 |
|---|---|---|---|
| `test_architecture_fitness.py` | `DROP_WITH_TOOL` | **`KEEP`** | 消雷 B-11:与 GOVERNANCE/PLAN/L3 正文 KEEP 对齐;它是 B 全批次 go-no-go 门禁载体 |
| `regression_sort_strategy_case_insensitive.py` | `MERGE:sort_strategy_case_insensitive` | **`HOLD_FOR_R51`** | B-1:移出簇,随 R51 整体退场,A 不动 |
| `regression_sort_strategies_priority_case_insensitive.py` | `MERGE:sort_strategy_case_insensitive` | **`KEEP`** | B-1:独立保留(存活算法契约),不合并 |
| `regression_dispatch_rule_case_insensitive.py` | `KEEP`（reason 追加标注) | `KEEP` | B-1 关联:R51 另一续命测试,A 勿在 P7 锁死 |
| `regression_scheduler_workbench_link_guardrails.py` | `MERGE`（reason 追加) | `MERGE` | B-2:禁对 guard 断言去重 |
| `regression_scheduler_workbench_links_contract.py` | `MERGE`（reason 追加) | `MERGE` | B-2 同簇 |
| `regression_aps_workbench_flow_contract.py` | `MERGE`（reason 追加) | `MERGE` | B-6:R57-PINNED 勿去重 |
| `test_enum_display_consistency.py` | `KEEP_TRIM`（reason 追加) | `KEEP_TRIM` | B-4:剪尾行级手术保留坏值/None 行 |

> `HOLD_FOR_R51` / `HOLD_FOR_R43` 是新引入的非自动化 verdict 值:A 的 csv→rm 硬筛只认 `verdict=='DROP'`、合并只认 `MERGE:*`,二者都不匹配 → A 的 **csv 驱动**自动化都会跳过(默认不动),正是「交棒 R51/R43」所需。
> **⚠ 但这只对 csv→rm / MERGE 自动化成立——对 P3.4 删 main-style collector 不成立**:`HOLD_FOR_R51` 的 `regression_sort_strategy_case_insensitive.py` 与 `regression_dispatch_rule_case_insensitive.py` 是 `def main` 形态,collector 一删它们就静默收集=0(假绿),见 §8 BLOCKER。

---

## 7. 机读源权威性（红队 2026-06-05 补，防混用过期快照）

- **唯一权威机读源 = `L3_verdicts.csv`**（终态 KEEP429/MERGE37/DROP_WITH_TOOL6/HOLD_FOR_R51 1/DROP38/REWRITE3/ISOLATE_PERF8/KEEP_TRIM123，总 645）。A 合并/删除一律以 csv 的 `verdict` 列（`DROP` 精确值、`MERGE:` 前缀）为准。
- **`summary.json` 是变更前快照，勿用于驱动 A 的合并/删除**：其 `distribution`（KEEP427/MERGE39/DWT7）、`multi_file_cluster_detail.sort_strategy_case_insensitive`（仍列 2 文件）均为 B-COMPAT 调整**之前**的值，且 `l3_csv_path` 指向已不存在的 `/tmp/regovern/`。已加 `_stale_since` 标记。
- **`raw_verdicts/B10_sched_b.csv`、`B14_other_b.csv` 是 12 批原始裁决备份**，保留改前值（sort_strategy=MERGE、architecture_fitness=DROP_WITH_TOOL）是预期的历史快照；**若未来重跑 L3 workflow 重新汇总，必须重新应用本文件 §6 的 csv 消雷 + §1/§2 的 B-12/B-1 处置**，否则埋雷复活。
- 散落在 `GOVERNANCE.md`/`BASELINE.md`/`PLAN.md` 正文的 `KEEP 427`/`MERGE 39`/`DROP_WITH_TOOL 7` 是 L3 原始裁决叙述，真值以本 §6 表 + `L3_VERDICTS.md §1 脚注` 为准（差量：+2 KEEP / -2 MERGE / -1 DWT / +1 HOLD）。注：第三轮后 sp05 由 DROP→`HOLD_FOR_R43`，DROP 38→37。

---

## 8. 第三轮交界对抗补遗（2026-06-05，B→A 反向 / 时序咬合 / 门禁基线 / 共享工具）

> 前两轮偏 A→B 单向 + 我的加固自洽。第三轮专盯交界面，抓到 1 BLOCKER + 2 HIGH + 4 MEDIUM 新真问题（全在前两轮盲区，B-1~B-12 未覆盖）。**总顺序「先 A 后 B + P6 后启 B」不变。** 裁决全文见 `_B_COMPAT_BOUNDARY_VERDICT.md`。

### 🔴 BLOCKER — P3.4 删 collector 让 R51 续命测试静默归零（时序咬合 / B→A）

- **交界**：`regression_sort_strategy_case_insensitive.py`（HOLD_FOR_R51）与 `regression_dispatch_rule_case_insensitive.py`（KEEP）均为 `def main` 形态（af630f64 前实测 `def main=1 / def test_=0`），靠 `tests/conftest.py` 的 collector（`_is_main_style_regression`:34 / `pytest_collect_file`:58 / `RegressionMainFile`:85 / `RegressionMainItem`:90，首个 fixture 在 :130）才被当测试运行。B-1 锁它们「不转/不删」→ P3.3 不转 → P3.4 删 collector 后标准收集器找不到 `def test_` → **收集 0 项、exit 0、零报错=假绿**；`:25` 坏值兜底断言（R51 灵魂线 oracle）从此不再运行。R51（Batch-7，远晚于 P3）执行时**删的是尸体、中间回归无网**。
- **修法（已写入 PLAN P3.4）**：二选一——①P3.3 把这两文件也转 pytest（`def main→def test_`、`:25` 断言体逐字保留，不违 B-1 语义）；②删 collector 前加「无残留 main-style `regression_*`」守卫。R51 dossier 注：动手前 `pytest <file> --collect-only` 应 >0 用例。
- **🆕 2026-06-06 复核补强（3-agent + 实跑，B→A）**：
  - **R51 主体已拆**：两文件已在 `af630f64` 转 pytest（`def test_` 各 1，`:25` 坏值断言逐字保留），原「P3.3 不转→静默归零」路径已断；但守卫断言仍须保留。
  - **BLOCKER 范围远大于这 2 个**：删 collector 真正卡点是「**全部纯 main-style==0**」(实测 2026-06-06 仍剩 **52**)。其中 **11 个是门禁必跑成员，分两类(10-agent 核验更正)**：**7 个 `required`**(`QUALITY_GATE_REQUIRED_TESTS`，在 `iter_required_tests()` 210 内：dashboard_overdue_count_tolerance、gantt_calendar_load_failed_degraded、gantt_url_persistence、report_export_large_scope/size_mode、safe_next_url_hardening、scheduler_analysis_observability)删 collector 后**静默少跑**(required marker 只能打在已收集 item，收集 0 项即无 item 可标)；**4 个 startup-regression**(`QUALITY_GATE_STARTUP_REGRESSION_ARGS`：app_new_ui_secret_key/security_hardening/session_contract、runtime_lock_reloader)删 collector 后被显式路径命令 **loud fail**(no tests collected / exit 4-5)。前者静默(危险)、后者响亮(易发现)，都须转完；**真正靠守卫断言兜底的是前 7 个**。
  - **守卫断言 vs 核销器(B-14 已消解后更新)**：守卫断言**不能用 `verify_required_regressions` 核销器替代**——M4a(`eaf83cbf`)已把它瘦身为**只读核销 CLI**(仍在跑，但语义是事后核销 required⊄debt，非「删 collector 当下阻断收集骤降」)；核销器读的是**已收集集**，抓不到「本应收集却没收集」。**结论：P3.4 删 collector 同提交必须自带「无残留 main-style」AST/grep 守卫断言，这是唯一能在删除当下硬拦的兜底。** 三条 AND 卡点见 `PLAN.md` §P3.4。

### 🟠 B-13 HIGH — sp05 是 R43/R01/R26 串行依赖 + Batch-A G38 门禁载体，不可 P1.1 早删（护栏盲区）

- **交界**：`test_sp05_path_topology_contract.py` 原 csv 判 `DROP`（P1.1 最早就 `git rm`）。但 `R43.md:52` step4 要改其三表（`ROUTE_COMPAT_MODULES:94`/`ROUTE_BEHAVIOR_COMPAT_SYMBOLS:105`/`SCHEDULER_REAL_ROUTE_FILES:150`），`R43.md:65-66` R01(Batch-B)/R26(Batch-D) 强串行依赖同文件，`PHASE4:191` Batch-A go-no-go「G38 SP05 topology contract 绿」。A 早删 → B 的 Batch-A G38 不可满足 + R43 改一个已删文件 + 删 wrapper 的 topology 回归网消失。**这更正了我 §5 首版「sp05 可放心删」的张冠李戴错误（把 sp06 的 `R45:36` 结论安给了 sp05）。**
- **修法（已落实）**：csv 改 `HOLD_FOR_R43`（A 跳过不删）；sp05 须存活到 R43/R01/R26 全改完再退场/重写；§5 已更正。

### ✅ B-14 已消解（2026-06-06 commit `eaf83cbf` P2.2-M4a）— 原断言失实，更正存档

- **B-14 当时准确，已按其修法消解（非失实）**：B-14（2026-06-05）预警「`run_quality_gate.py:25` 是 verify_required 无条件顶层 import，删模块须同一原子提交改接否则 ImportError」——经核 **eaf83cbf 父提交 `:25` 确为该 import**（`from tools import verify_required_regressions_from_full_test_debt as required_regressions_verifier`），预警属实。eaf83cbf（M4a）**正是按 B-14 修法做的**：同一提交删该顶层 import 行（diff 实证 `-from tools import verify_required...`）+ 删 `_load_required_regressions_verifier_proof` + 核销器 620→268 行瘦身。**现状（消解后）**：`:25` 上移为 architecture_scan_cache（即 B-12 那行），verify_required 无顶层 import、仅子进程命令字符串在 `:1654`（`["python","tools/verify_required_regressions_from_full_test_debt.py"]`），模块 11758B；实跑 `import scripts.run_quality_gate` 成功。原 `:1858` 调用点行号随之漂移（现 `:1654` 一带）。
- **现状**：eaf83cbf（P2.2-M4a，2026-06-06 02:55）已把 required 改 `@pytest.mark.required`（conftest 自动打标 1821 nodeid）、核销器瘦身为只读 CLI、§1.4 SOP 第 3 行对齐。删/退役 verify_required **不引发 import 期 ImportError**（实跑 `import scripts.run_quality_gate` 成功且 sys.modules 不含该模块）；真实残留点是运行期子进程调用（`:1654`）+ §1.4 SOP 直跑，非顶层 import。
- **对 B 无冲击（原结论仍成立）**：B 计划全树对 `run_quality_gate`/`sync_debt_ledger` 0 命中。

### 🟡 B-15 MEDIUM — oversize 扩产无登记接口（门禁基线联动，J2 真雷）

- **交界**：`test_architecture_fitness.py:377` 对未登记的超 500 行新文件硬红，扫描含 `web/viewmodels`。R54 收口点 `web/viewmodels/scheduler_workbench_links.py` 实测 **487 行**，加 guard 入参 + 4 套 delegate 接线后跨 500 风险真实；`sync_debt_ledger` 无「非启动链新增 oversize 登记」接口。
- **修法**：R54（Batch-C）设 go-no-go 行数检查点（扩产前后实测目标文件行数，逼近 500 优先拆文件/拆函数=门禁本意；确无法缩才 owner 经 `set-entry-fields` 受控登记 + accepted_risks）。
- **注**：silent 侧**不需要**重刷——实测门禁非启动链只续管 `legacy_swallow_hit`，B 的 6 个目标文件 silent 台账命中全 0（见下「误报 #11」）；B-15 只管 oversize/complexity。

### 🟡 B-9 升级 MEDIUM — parity 测试远多于「3 个」，须过 A 的 P6/P7

- B 新建/扩写 parity ≥10 个；其中 `regression_boolean_normalize_wide_parity_contract.py`、`regression_gantt_critical_chain_normalize_parity.py` **实测仓库不存在**（B 待新建）。**裁定**：B 在 A 之后新建的测试一律遵 A 的 P6 子目录 + 去前缀 + `_contract/_guard/_smoke` 后缀 + `def test_` + docstring + scope 登记；P6 迁移脚本附产「B 新文件目标子目录映射」。多数 parity 是扩写既有 pytest-style 文件，门禁压力小。

### 🟡 B-4 补 / B-11·B-12 旁注 MEDIUM

- **B-4 补**：`regression_schedule_result_view_context.py:294-300`（R22 bad-role oracle『未知的排产方案角色：bad』）在 KEEP_TRIM 保留区 124-291 **外侧**，P5.2 剪尾勿砍；csv:360 reason 已追加保留标注；B 侧 `pytest -k legacy_bad_role_message` 自检。
- **B-11/B-12 旁注**：`test_architecture_fitness.py` 是「**A 禁删但 B 可改**」——R28 收口须同步退其 `:77 LOCAL_PARSE_HELPER_ALLOWLIST` 条目（否则 `:254` stale 守卫红），故 A 的 P7 防回潮门禁**只可禁删、绝不可对它加内容指纹/禁改锁**；B 改 `:77` 须与该批次同提交。

### B-2 措辞修正（low）

- B-2「与 G04/G05 避免交叠窗口」在 B-3「P6 后、tests 定稿后启 B」强串行下属冗余：B 的整个 ROOT→D 序列本就整体在 A 全 P0-P7 之后，不存在同期窗口。措辞保留作双保险，不构成新约束。

### 已证伪、别再报警的误报（第三轮实测）

- **#11「B 改静默回退→台账 stale→go-no-go 红→须重刷静默台账」= 伪**：`tools/quality_gate_operations.py:812-830` 门禁非启动链只续管 `legacy_swallow_hit=True`，B 的 6 个目标文件 silent 台账命中全 0 → silent 侧 fitness 不会红；`refresh --mode scan-startup-baseline` 只刷启动链，对这些文件 no-op。
- **#12「B 照抄 §1.4 SOP 撞已删 verify_required 卡死」= 伪**：B 计划 0 处引用 A 的 §1.4 SOP / `run_quality_gate`；真问题是 A 内部债（已并入 B-14）。
- **#13「P3.3 改写 HOLD 文件 + P7 锁禁删致 B git rm 触发门禁」= 伪**：`PLAN.md:200` 已写明「P7 只拦新增违规，不锁既有测试的删除」并点名这两文件 B 仍要删。（这两文件的**真**风险是上面的 BLOCKER collector 删除，非 P7 锁删。）

---

## 9. P4 并行机制对 B 的约束（2026-06-08 A 收官后补，holistic critic 抓的 8 维之外盲区）

A 的 P4（提交 `337a7672`）给 daily gate 接入 pytest-xdist 并行 + serial 分流，B 全部产物制定于其之前、对该机制**零感知**（PHASE4/dossiers/ANCHOR-DRIFT/_B_COMPAT 原文 grep `xdist|worksteal|serial 分流` = 0）。机制实体：`tests/conftest.py` 的 `pytest_collection_modifyitems` 按 `tools/full_test_debt_shards.classify_nodeid` 自动给 serial 用例打 marker；`scripts/run_daily_quality_gate.py` 把 impact 步拆 not-serial（`-n auto --dist worksteal` 并行）/ serial（串行）两步、命令为三元组 `(label, command, allow_no_tests)`。对 B 的三层约束：

- **(1) B 自建 oracle 默认落并行面**：`classify_nodeid` 的 serial 判定靠文件名/路径模式（`SERIAL_FILE_PATTERNS`/`SERIAL_NODEID_PATTERNS`/`SERIAL_EXACT_PATHS`），覆盖 runtime/startup/port/long_gate/win7 等真进程独占测试。现有逻辑 parity 形态测试实测全判 `parallel`（如 `tests/algorithm/test_sort_strategy_case_insensitive.py`、`tests/resource_dispatch/test_dispatch_rule_case_insensitive.py`——注：这两个恰是 R51 待 `git rm` 退场的续命测试，此处仅借其路径形态示例 `classify_nodeid` 的并行判定，非 B 要保留的 oracle）。**B 起草每个新 parity 测试前先 `.venv/bin/python -c 'import tools.full_test_debt_shards as s; print(s.classify_nodeid("<拟用路径>"))'` 预判**。
- **(2) 全局态污染 oracle 会被 xdist 同 worker 跨文件复用污染致 flaky**：凡含全局模块属性赋值（`mod.X.attr=`，记忆铁律「mod.X.attr 赋值就是改全局模块」）/ `os.environ` 写 / 全局单例改的 oracle，要么走 pytest `monkeypatch` fixture 自动还原，要么文件名纳入 `SERIAL_FILE_PATTERNS` 强制串行。R54 四态 / R09 双路 parity 等含全局改写的 oracle 须逐个判（当前生产 oracle 是纯函数 parity、风险低，但 B 新建的须逐个核）。
- **(3) 批后单测验证一律用裸单进程**：`.venv/bin/python -m pytest <file> -p no:cacheprovider`，**不经 daily gate**（避开 xdist；且 daily gate 的 impact 步已是 serial/not-serial 两步三元组形状，与 B 计划各批「批后门禁」旧叙述的单步门禁形态不同——B 若必须经 daily gate 验，须按现状两步形状）。serial 不变量复核：`.venv/bin/python -m pytest --collect-only -q -m serial 2>/dev/null | tail -1` 对齐基线，每批后确认未漂移。

> **副本权威性提醒**：B 计划权威目录是 git tracked 的 `.codestable/audits/.../phase4-dep-safety/`（本文件 §0 顶部已指明）；`docs/_panorama_data/phase4_dep_safety/` 是 `.gitignore` 忽略的工作镜像，**可能陈旧**（曾出现 ANCHOR-DRIFT 镜像滞后于权威副本两节）。一切以 `.codestable` 副本为准；读到 docs 镜像与 `.codestable` 不一致时，信 `.codestable`。

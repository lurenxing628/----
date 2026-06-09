# 锚点漂移备忘（2026-06-05 晚 · 入库提交之后）

> 执行批次（ROOT→A→B→C→D）前必读的增量备忘。本文记录「phase4 分析定稿之后、产物入库推送之时」工作区发生的全部代码改动对债务锚点的影响。核验人：owner 会话 2026-06-05 晚，逐锚点 grep 回盘。

## 一、基线澄清（最重要）

phase4 四层分析（含全部 dossier 对抗核验附录）是在**已包含工作台 item8 + 复审修复全部改动的工作区**上做的（证据：R08.md:41、LB05.md:182 明确记录"工作区有未提交改动"并按其回盘）。这些改动后被原样提交为 `6759b0f9`。**因此提交本身 = 分析基线，零漂移。**

已抽验逐字命中的锚点（2026-06-05 晚复核）：R09 context.py:28（调用 :96/:97/:107/:258/:271/:272）、viewmodel:33（调用 :257/:258/:353）、收口点 operation_execution_scope.py:9、R15 provider `if not text` :87、R54 collar build_workbench_plan_context :187、LB08 scheduler_public_errors.py:167、R24 禁区行 helpers.py :101/:127/:144。

## 二、分析后真实增量：3 个门禁修复提交（3e2d4678 / e1eccacd / 9983f3d3）

### ⚠️ 1. R09/R08 区域：tokens 模块换了地址（唯一路径级漂移）

- `core/services/scheduler/resource_dispatch_execution_tokens.py` → **`core/models/resource_dispatch_execution_tokens.py`**（git mv 100% 同体，函数体零改动；起因：viewmodel import 它违反"viewmodel 只许 core.models*"门禁）。
- 受影响引用（按旧路径 grep 会落空）：`_layer2_residual.md:37`（R09 Optional-5 清单）、`dossiers/_newdebt_parse-except.md:44`（`:13-18 _positive_int_text` wrap re-raise，行号仍准、目录已变）、`dossiers/R08.md:148`。
- **对 R09 修法零影响**：该副本本就是"已收编 wrap re-raise"终态，不在待收编面里；待收编三处（service:24 / viewmodel:33 / persistence_errors:13）全部未动。利好：wrap 副本现与收口点同住 core/models，收编 import 拓扑更扁平。
- 同步改的 3 个 import 点：viewmodel:23、context.py:13、regression_operation_execution_event_sequence_contract.py:17（均为单行替换+ruff 排序，未位移 `_positive_int` 锚点，已验证）。

### 2. LB02/LB05/R62 宿主 execution_review.py：行号整体上移 ~17，语义零损

- 删除 `_public_report_datetime`（原 :75-89，item8 新增的中文时间格式化，自带"时间记录异常"静默兜底）+ `_display_time` 恢复 ISO 口径（复审回退，详见提交 9983f3d3）。
- **五处 ROLE_ADOPTED 硬钉一字未碰**，新坐标 = dossier 记录过的"今晨"坐标：`:58`（不变）/ `:163` / `:174` / `:204` / `:219`（dossier 旧值 :180-181/:191-192/:221/:236）。签名 `execution_review` :209→**:192**，xlsx :247→**:230**，`get_execution_state_for_scopes` :206→**:189**；R62 锚 `_execution_review_row` →**:284** 起、`_resource_pair_payload` →**:392** 起。
- 被删函数不在任何债务登记内（LB05.md:182 仅将其列入"工作区非注释改动"盘点）；删除属灵魂线正向（少一个静默兜底），并缩小了承重宿主附近的逻辑改动面。G05 批次单元（补注释）修法不变。

### 3. R43：wrapper 契约测试 +12 行（零影响）

- `regression_scheduler_wrapper_import_order_contract.py` 注入隔离 `APS_DB_PATH`（修测试对宿主机本地库的依赖）。dossier 钉的 :12-22/:63/:83 整体下移 ~12 行。R43 裁定执行时**整文件删除**，此漂移随之消灭。

### 4. 零债务交集改动

`scheduler_analysis_trends.py`（build_trend_rows 拆分）、`scheduler_week_plan_response.py`（导出文件名口径回退）、`tools/quality_gate_shared.py`、`regression_scheduler_candidate_week_plan_contract.py`——四者均不在任何 dossier 锚点中（已 grep 验证）。

## 三、对执行批次的指令

1. **38 项 owner 裁定、批次序（ROOT→A→B→C→D）、H 边、原子簇划分全部不变。**
2. R09 单元执行时，Optional-5 清单中 tokens 副本按新路径 `core/models/resource_dispatch_execution_tokens.py` 回盘。
3. G05（LB02/LB05 注释）按符号定位五硬钉，行号用本文 §二.2 新坐标起步、仍须现场 grep。
4. 其余一切照旧：档案行号一律视为待复核，动手前独立 grep 回盘。

## 四、另一处环境事实（非债务，防误判）

本地 `db/aps.db` 是"SchemaVersion=19 但表结构停在旧契约"的半截迁移活标本，会被 v19 fail-fast 契约拦住应用启动——**这是护栏正确行为**。执行批次跑回归时若见 `MigrationContractError`，用隔离 `APS_DB_PATH` 或重建本地库，**禁止放宽迁移契约**。

## 五、P6 落地后批量路径重映射 SOP（A→B 交接，2026-06-06 补，落地 B-3 §62 待办）

> A 的 P6 目录重组（`git mv` 迁 `tests/<模块>/子目录/` + 去前缀）会令 B 全体 ~199 个 `tests/xxx.py:line` dossier 锚点的路径维度整体失效。**B 必须等 A 全部 P0-P7 跑完、tests 定稿后再启动**（B-3 强串行，严禁迁移中途穿插 B）。重映射 SOP：
> 1. A 在 P6 迁移脚本里**产「旧路径→新路径」映射表**（csv，`git mv` 可机械生成）。
> 2. B 启动前跑一次性脚本：按「去前缀文件名 + 被测符号名/断言字符串」对全部 199 锚点 `rg -rn PATTERN tests/` 重定位、重生成 dossier（断言体 git mv 逐字幸存，按符号必命中）；档案行号一律视为待复核（§三.4 既有纪律）。
> 3. **⚠ 不止 B 的 199 锚点**：A 自己的 **required 路径锚点也会断**——`tools/test_registry.py:64/77` 硬校验 required 路径单层 `tests/文件.py`、`tools/test_registry_data.py` 写死单层路径。A 的 P6 须连带放开单层校验 + 重写 test_registry_data.py；映射表**同时覆盖 B 的 199 dossier 锚点和 A 的 required 清单两套**。
> 4. 权威与细节见 A 的 `.codestable/refactors/2026-06-01-test-gate-cleanup/_B_COMPAT_SAFEGUARDS.md` §B-3（⑤ 项，2026-06-06 补）+ §8（P3.4 删 collector 卡点 / 11 个 required 成员 / 守卫断言时序雷）。

## 六、✅ P6 已落地（2026-06-08 补 · 映射已交付；路径维度已于 2026-06-08 代 B 执行，见 §七）

> A 的 P6（Phase A 加固 + Phase B 8 波迁移 + Phase C 交接）**已全部收官并 push**（分支 `cleanup/p3-main-style-to-pytest`，提交链 `ff5f305b..017c1920`，全门禁 GATE_EXIT=0，两轮 holistic 对抗审核 0 阻塞）。SOP §五 的 A 侧责任**已履行**，B 侧重生成待 B 阶段执行。

1. **权威映射表已落地**：`.codestable/refactors/2026-06-01-test-gate-cleanup/p6_path_map.csv`（561 行 `old_path,new_path,module,kind`），机械覆盖全部 P6 `git mv`。§五.3 的 A 自有锚点已连带修复：`tools/test_registry.py` 单层校验已放开（commit `ca982c8d`，`count("/")==1`→`startswith("tests/")`）、`test_registry_data.py`/`full_test_debt_shards.py`/`quality_gate_shared.py`/pyright config/治理台账全部重指新路径（契约三角逐字一致、0 flat 残留，再审核已铁证）。

2. **B 锚点 vs 映射核对结论（只读审计，B 启动前可直接采信）**：dossier 全树引用 **106 条**去重扁平旧测试路径，**纯 P6 目录重组造成的漂移，CSV 100% 覆盖**。106 条账面拆解（B 拿 106 对账时按此核销，避免凭空差额）：
   - **97 条**精确命中 CSV `old_path`，对应 `new_path` 全部落盘存在（0 反例）。
   - **4 条**为 dossier 旧名与现存近名不一致（**P5.1 合并改名 / 命名漂移**，非笔误）：`regression_aps_workbench_flow_contract`(P5.1 commit `1fa076fb` 合并为 `aps_workbench_first_round_flow_contract`)、`regression_scheduler_workbench_link_guardrails`(现存近名 `..._links_contract`，复数+contract，与单数+guardrails 在 dossier 中或为并列两测试)、`run_real_db_replay_check/_smoke`(现存近名 `run_real_db_replay_e2e`)——真测试均以近名存在且**新名都在 CSV 里**，B 按「去前缀文件名 + 被测符号/断言串」`rg` 核认对应关系即命中（§五.2 既定做法）。
   - **2 条**为 **B 待新建的 parity/黄金基线测试**（`regression_boolean_normalize_wide_parity_contract` LB04、`regression_gantt_critical_chain_normalize_parity` R11/C-GANTT）：全 git 历史从未作为测试文件存在,dossier 自身明确标注「收口前不存在、须新建」——**本就不应在 CSV/磁盘**,既非 P6 漂移也非悬空,是 B 收口产物锚点。**2026-06-08 补登**：R11/C-GANTT 已在 B 执行中落为 `tests/gantt/test_gantt_critical_chain_normalize_parity.py`；**2026-06-10 补登**：LB04 parity 已落——未新建文件，而是 fae8829b 往既有 `tests/models_domain/test_yesno_normalization_contract.py` 新增全矩阵锁步测试（双注册 test_registry），LB04 已翻 fixed。
   - **2 条**真悬空（见下 §六.3）+ **1 条**通配占位示例 `tests/xxx.py`（§五.1 例示,剔除）。
   - 核销:97 + 4 + 2 + 2 + 1 = **106**,账面平。

3. **⚠ 2 条真悬空锚点 ≠ P6 漂移（B 须单独裁定，CSV 不该也无法覆盖）**：这两条是**测试删除/废弃**所致，P6 只迁「迁移时点存在」的文件，故不在映射内：
   - `tests/regression_sp06_no_duplicate_defs.py`：已在 commit `7ca42ca4`（P1.1 删 35 个 DROP 死代码测试，**早于 P6**）删除；磁盘已无、CSV 未收录、`tests/` 全树无 `NO_CFG_GET_TARGETS` 符号。dossier 多处（REPORT.md:1298/1301、R45）仍当【现存】白名单守卫引用——**B 须确认该锚点已废或重指**。
   - `tests/regression_scheduler_candidate_py38_contract.py`：无改名链、磁盘无；现存 py38 扫描器是 `tests/gate_meta/test_scan_py38plus_syntax.py`。dossier（_real_debt.json、R02/R71）仍当【现存】py38 契约引用——**B 须裁定指向新扫描器还是确认已废**。
   - （另:占位符 `tests/xxx.py` 是 SOP §五.1 通配示例，非真锚点，B 重生成时剔除。）

4. **§二.3 的 R43 漂移已消灭确认**：`regression_scheduler_wrapper_import_order_contract.py` P6 中迁为 `tests/excel_data_io/test_scheduler_wrapper_import_order_contract.py`（未删除——R43「执行时整文件删除」属 B 阶段裁定动作，尚未执行）。其 dossier 锚点路径维度按 CSV 重指即可;若 B 仍裁定删除,则该锚点随之消灭。

5. **§三.4 纪律不变**:档案行号一律视为待复核,B 重生成时按符号/断言串现场 `rg` 回盘(断言体 `git mv` 逐字幸存,按符号必命中)。详细逐行命中表见 P6 审计产物（审计脚本与 old→new 对账逻辑已固化,可复跑）。

## 七、2026-06-08 A 收官终态补登（remap 已代执行 + 两新机制 + test_registry 行号弃用）

A 全部 P0–P7 已收官（B 真实漂移基线 = `3f8f7c5f`，B 产物入库定稿点；抬头 `c2aa7501` 仅分析快照）。在 §五/§六 交付映射表的基础上，本轮**已代 B 机械执行路径维度重映射**，并补两项 A 引入的新机制约束：

1. **路径重映射已实际落地（非仅交付映射表）**：同目录脚本 `.codestable/refactors/2026-06-01-test-gate-cleanup/remap_b_anchors.py` 已按 `p6_path_map.csv` 对 **PHASE4 主计划 + 76 dossiers + `_registry.json`（两套副本）** 完成 old→new 路径字符串替换（IN_CSV 残留 0；PHASE4/dossiers/OWNER 导航文档 0 残留）。B 不再需要「重生成 dossier 路径维度」，只需在执行每个原子簇时按符号/断言串 `rg` 校准**行号**（§三.4/§六.5 纪律）。§六.2/§六.3 的 6 个删除/合并/待新建文件不在映射表，已在相关 dossier 就地回写终态。

2. **⚠ test_registry 等 tools/ 注册表的绝对行号锚点一律弃用**：B 计划/dossier 多处写 `test_registry:289`（exec_review 注册）、`test_registry:56`（spec_sync 注册）这类对 `tools/test_registry_*.py` 的**绝对行号**引用——A 的 P6 重写了 `test_registry_data.py`/`test_registry_groups_*.py`，这些行号已全漂（实测 exec_review 现散在 `test_registry_groups_scheduler.py` + `test_registry_data.py`，行号随版本变）。**一律按测试文件全路径名 `rg <new_path> tools/test_registry*` 重定位，弃裸行号。** 另 LB07 的 spec_sync 测试 A 后已脱离 required/daily 门禁组（只在 full gate 收集），B「rg 核存在即视为已纳门禁」前提不成立，须直接 `pytest <file>` 验。

3. **两个 A 新机制 B 须感知（详见 `_B_COMPAT_SAFEGUARDS.md` §9 + PHASE4 §1.1 总纲 (5)(6)）**：① **P7 防回潮门禁**（full gate 第 17 步）——规则③ B 零触发、规则①② 仅新建独立测试触发（须 docstring + test 函数 + 落 P6 子目录）、删测试永不触发；② **P4 xdist 并行**——B 自建 oracle 默认落并行面，含全局态污染须 `monkeypatch` 或强制 serial，批后单测一律裸单进程 `-p no:cacheprovider` 验、不经 daily gate。

4. **副本权威性**：本文档权威副本 = git tracked 的 `.codestable/audits/.../phase4-dep-safety/ANCHOR-DRIFT-2026-06-05-POSTCOMMIT.md`；`docs/_panorama_data/` 镜像 `.gitignore` 忽略、可能陈旧（D7-02 核查曾见镜像滞后权威两节），一切以 `.codestable` 为准。

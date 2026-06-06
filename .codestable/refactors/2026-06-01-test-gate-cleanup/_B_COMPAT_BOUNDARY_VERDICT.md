All key facts are now independently verified. The J2 silent-ledger dispute is confirmed: `architecture_silent_scan_entries()` gates non-startup paths on `legacy_swallow_hit`, and all 6 B-target files have **0** ledger entries — so the J2-silent-stale chain is genuinely false, but the J2-oversize chain (R54 expanding `scheduler_workbench_links.py` which is at 487 lines toward the 500 limit) remains live. The R22 bad-role oracle at line 294-300 is confirmed outside the 124-291 KEEP_TRIM retention zone. P3.4 deleting the collector against the 4 main-style oracles is confirmed. I have enough to write the verdict.

Now synthesizing the final report.

---

# A↔B 交界面第 3 轮对抗裁决报告

## 一句话结论

**有新雷。** 站在前两轮(A→B 文件级影响 + A 自洽红队)的结论之上,本轮在 5 个交界维度共抓到 **4 个 `holds=true && is_new=true && severity>=high` 的新真问题**——全部落在前两轮的盲区(B→A 反向 / 门禁基线联动 / 共享工具接口 / 护栏交界),现有 `_B_COMPAT_SAFEGUARDS`(B-1~B-12)无一覆盖。**先 A 后 B 的总顺序不被推翻**,但其中 **1 条是 blocker(P3.4 删 collector 致 R51 续命测试静默归零),2 条 high 须在 A 落地前补护栏(sp05 矛盾、verify_required 多点 import 链)**,否则会让 B 的批次门禁不可满足或 A 自身 live 门禁 ImportError。

同样重要的是:**前两轮和本轮自己提出的好几个"惊悚 high"经实测被证伪**(尤其 J2 静默台账联动、J4 §1.4 SOP 卡死 B)——它们的因果链建立在错误前提上,本报告据实降级,不重复报警。

---

## 一、重点盲区复盘:J1(B→A 反向)与 J2(门禁基线联动)到底有没有新雷

这是用户点名最可能藏雷的两个方向。逐个交代实测结论:

### J1(B→A 反向)——**有 1 个 blocker,但不在最初设想的方向**

最初设想的"B 改 R51/R54 生产行为 → A 判 KEEP 的测试断言失败"这条路**基本不成立**:R54 收口后 collar 恒产 3 guard 键,A 保留的 `regression_scheduler_workbench_link_guardrails.py` 里手动 `pop`/注入虽语义变虚构,但断言结果仍 fail-closed 通过,**不致断**(low,已被 B-2/B-3 覆盖)。

真正的 blocker 是**时序错位制造的"删尸"**:A 的 P3.4 无条件删 main-style collector,会让 B 在 R51 执行**之前几个阶段**就静默失去续命测试的回归网(详见 §三-① blocker)。这是 B→A 与时序咬合的交叉雷,前两轮只盯"断言被焊死/被合并",完全没看"collector 删除让 main-style 测试收集=0=假绿"。

### J2(门禁基线联动)——**最初的"静默台账联动"是误报,真雷在 oversize 扩产**

本轮多个维度都独立提出过"B 删改生产静默回退点 → architecture_fitness 静默台账出 stale → go-no-go 红 → 须 sync_debt_ledger 重刷"。**实测证伪**:

- 门禁实扫集 `architecture_silent_scan_entries()`(`tools/quality_gate_operations.py:812-830`)对**非启动链路径只续管 `legacy_swallow_hit=True` 的遗留项**;
- 解析真台账 `开发文档/技术债务治理台账.md`,B 的 5 个目标文件(`material_repo` / `sort_strategies` / `dispatch_rules` / `batch_service` / `enum_normalizers` / `scheduler_workbench_links`)在 silent 条目里**命中数全是 0**;
- 所以 B 删这些点既不会让任何台账条目变 stale,也不会进比较集 → **silent 侧 fitness 不会红**。

> 因此"B 每 batch 必须跑 `sync_debt_ledger refresh --mode scan-startup-baseline` 重刷静默台账"这条护栏**不需要**——而且该命令只刷启动链,对这些非启动链文件本就 no-op,反证提出者把门禁 scope 理解反了。

**但 J2 没有完全空手**——真雷换了一个子类:**oversize 扩产无登记路径**。`test_architecture_fitness.py:377` 对未登记的超 500 行新文件硬红,扫描范围含 `web/viewmodels`(CORE_DIRS)。实测 R54 的收口点 `web/viewmodels/scheduler_workbench_links.py` **当前 487 行,距 500 仅 13 行**,R54 要加 guard 入参 + 收口逻辑 + 4 套 delegate 接线,跨 500 风险真实;而 `sync_debt_ledger` 的三个 refresh 模式没有任何"非启动链新增 oversize 登记"接口,B 计划也无"批后 fitness 红分情况处置"一节(详见 §三-补建 B-15)。这条定 **medium**(loud 硬红、可原地拆文件、不需重做依赖分析)。

---

## 二、分层裁决总表

| 层级 | # | 交界问题 | 方向 | severity | is_new |
|---|---|---|---|---|---|
| **新增必须处置** | 1 | P3.4 删 collector 让 R51 续命测试在 R51 执行前静默归零 | 时序咬合 / B→A | **blocker** | ✓ |
| | 2 | §5 断言"B 不依赖 sp05 存活"与 R43 改 sp05 三表 + Batch-A G38 门禁正面矛盾 | 护栏盲区 | **high** | ✓ |
| | 3 | P2.2 删 verify_required 炸 `run_quality_gate.py:25` 无条件顶层 import(B-12 同型漏钉)+ §1.4 SOP 自指失效 | 共享工具接口 | **high** | ✓ |
| **建议补** | 4 | B 新建 parity 测试远多于 B-9 登记的"3 个",须过 A 的 P7 新文件门禁 + P6 命名/目录 | 门禁基线联动 | medium | ✓ |
| | 5 | oversize 扩产(R54)无登记接口,B 计划无批后台账重刷 SOP | 门禁基线联动 | medium | ✓ |
| | 6 | R22 bad-role oracle(`view_context:294-300`)落在 KEEP_TRIM 保留区 124-291 外侧,P5.2 剪尾可能误砍 | B→A | medium | ✓ |
| | 7 | R28 须编辑 A 锁 KEEP 的 `test_architecture_fitness.py:77` 白名单——KEEP≠冻结,P7 不可加禁改锁 | 门禁基线联动 | medium | ✓ |
| **已被覆盖** | 8 | R54 dossier test_consumers 未登记 A 的 MERGE+P6 改名 | B→A | low | B-2/B-3 |
| | 9 | B-2"避免交叠窗口"措辞与 B-3 强串行矛盾(冗余死条款) | 时序咬合 | medium | B-3 |
| | 10 | B 73 份 dossier 对 A 几乎失明(仅 2 处提 A),B-10 未落到每份 dossier | B→A | low | B-10 |
| **误报(已证伪,不处置)** | 11 | "B 改静默回退 → 台账 stale → go-no-go 红 → 须重刷静默台账" | 门禁基线联动 | none | — |
| | 12 | "§1.4 SOP 把已删 verify_required 串在前,B 照抄即卡死" | 共享工具 | low(降级) | — |
| | 13 | "P3.3 改写 HOLD_FOR_R51 文件 + P7 锁成禁删致 B git rm 触发门禁" | B→A | low(降级) | — |

---

## 三、新增必须处置(high+ / blocker,is_new && holds)

### ① [BLOCKER] P3.4 删 main-style collector 让 R51 续命测试在 R51 执行前静默归零

- **交界**:A 的 P3.4(`PLAN.md`)无条件删 `tests/conftest.py:51-106` + `main_style_regression_runner.py`——这是 main-style 文件(只有 `def main`、无 `def test_`、名 `regression_*`)被当测试**运行**的唯一机制。
- **方向 / 涉及债**:时序咬合 + B→A;**R51**。
- **证据(file:line,已实测)**:
  - `tests/regression_sort_strategy_case_insensitive.py`:`def main=1 / def test_=0`(HOLD_FOR_R51);
  - `tests/regression_dispatch_rule_case_insensitive.py`:`def main=1 / def test_=0`(KEEP,R51 另一续命测试);
  - `PLAN.md` P3.4「全转完后删 `conftest.py:51-106` + `main_style_regression_runner.py`」;
  - B-1 明令 A 对这两文件「不合并·不剪·不删·不迁」→ P3.3 不会把它们转成 pytest → 保持 main-style → P3.4 删 collector 后 **pytest 标准收集器 import 但找不到 `def test_` → 收集 0 项、exit 5/0、零报错**;`:25` 的坏值兜底断言(R51 灵魂线 oracle)从此不再运行。
- **为什么是 blocker 而非 high**:P3.4 远早于 B 的 Batch-B/G24(R51 落点)。R51 真正 `git rm` 时,这两个"续命测试"已死了好几个阶段——**B 以为在删活护栏,实则删尸,中间任何回归无网**。`_B_COMPAT_SAFEGUARDS` §6 断言"HOLD_FOR_R51 是 A 任何自动化都会跳过的 verdict"——该断言只对 csv→rm/MERGE 自动化成立,**对 P3.4 collector 删除不成立**。
- **修法(二选一,必须先裁)**:
  - (甲推荐)P3.3 把这两个 main-style 文件也转成 pytest 风格(`def main→def test_`、**`:25` 坏值断言体逐字保留**、删 `find_repo_root` 样板),不违 B-1"不删不合并"语义(断言体不变);
  - (乙)P3.4 删 collector 前加守卫:断言"无残留 main-style `regression_*` 文件"逼转换闭环;
  - 并在 R51 dossier 注明:R51 动手前先 `pytest tests/regression_sort_strategy_case_insensitive.py --collect-only` 确认收到 >0 用例,否则护栏早已失效。

### ② [HIGH] §5 断言"B 不依赖 sp05 存活"与 R43 改 sp05 三表 + Batch-A G38 门禁正面矛盾

- **交界**:`_B_COMPAT_SAFEGUARDS.md` §5 把 `sp05/sp06/py38/real_db_replay` 一锅断言"B 不依赖其存活,A 先删对 B 是减负",证据只引 `R26.md:200`(load_bearing=false)与 `R45.md:36`(sp06)。**但 sp05 的证据是张冠李戴**(sp06 的结论安给了 sp05),且 §5 漏核了 O29 刚授权提前删的 R43。
- **方向 / 涉及债**:护栏盲区;**R43 / R01 / R26**。
- **证据(file:line,已实测)**:
  - `L3_verdicts.csv:642` `test_sp05_path_topology_contract.py,DROP,...,B14_other_b` → A 在 P1.1(最早的破坏性阶段)就 `git rm`;
  - `R43.md:52` 修法 step4 = 改 `test_sp05_path_topology_contract.py` 的三表 `ROUTE_COMPAT_MODULES(:94)/ROUTE_BEHAVIOR_COMPAT_SYMBOLS(:105)/SCHEDULER_REAL_ROUTE_FILES(:150)`;`R43.md:109` 把 sp05 当删 wrapper 的**唯一 topology 回归网**(漏改→loud fail);
  - `R43.md:65-66` 标 **R01(Batch-B)/R26(Batch-D)也串行依赖 sp05 同文件**;
  - Batch-A 批后门禁 `PHASE4...:191`「G38 SP05 topology contract 绿」——在 Batch-D(R43)**之前**。
- **冲击**:A 按 P1.1 早删 sp05 → B 的 **Batch-A G38 门禁直接不可满足(文件没了)**;R43 step4 改一个已删文件;R01 删函数 + 删 sp05 断言的"同提交"无锚;删 wrapper 的 topology 回归网消失(误删将不再 loud fail)。`modify sp05 某些行` ≠ `A 可先 git rm 整个 663 行 14 测试函数的文件`。
- **修法**:新增 **B-13(HIGH)** 并改写 §5,把 sp05 移出"可放心删":
  - (甲推荐)A 把 `test_sp05_path_topology_contract.py` 从 DROP 改 **HOLD_FOR_*** (同 HOLD_FOR_R51 机制,csv→rm/合并都不匹配故 A 跳过),因 sp05 横跨 Batch-B(R01)+Batch-D(R26/R43),须存活到最后一个改完再退场/重写;
  - (乙)若 A 坚持删,把"清 sp05 三表"动作从 R43 dossier 上提到 P1.1,且 Batch-A G38 改为"sp05 已由 A 退场、门禁取消、wrapper 删除正确性改由 R43 自带 grep + registrar 护栏(`sp05:484-571` 启动链 passivity 由 domains 叶子独立守)兜底";
  - 无论哪条,同步标注 R01/R26/R43 三债对 sp05 的串行依赖。**sp06/py38 侧 §5 结论正确,唯 sp05 错。**

### ③ [HIGH→✅已消解] P2.2 删 verify_required 炸 `run_quality_gate.py:25` 无条件顶层 import + §1.4 SOP 自指失效

> **✅ 已消解(2026-06-06 commit `eaf83cbf` P2.2-M4a)**:本裁决(2026-06-05)**准确**——其时 `:25` 确为 verify_required 顶层 import(eaf83cbf 父提交实证)。M4a **正是按本裁决修法**:同一提交删该顶层 import 行 + 核销器 620→268 瘦身为只读 CLI + 改 §1.4 SOP 第 3 行。现状 `:25` 上移为 architecture_scan_cache、verify_required 无顶层 import。下文交界/证据为**消解前的历史快照**。详见 `_B_COMPAT_SAFEGUARDS.md` §8 B-14。

- **交界**:`run_quality_gate.py:25`(已实测)是 `from tools import verify_required_regressions_from_full_test_debt as required_regressions_verifier` 的**无条件顶层硬 import**,紧邻 `:26` 的 `architecture_scan_cache`(B-12 已钉)。P2.2-M4 明文删 `verify_required...py`(该文件当前 EXISTS,26722B)。**B-12 精确钉了 `:26`,却漏了 `:25` 这个同型炸点。**
- **方向 / 涉及债**:共享工具接口;**P2.2-M4 / R15 / R41 / R54**。
- **证据(file:line)**:
  - `scripts/run_quality_gate.py:25` 顶层 import + `:1858` 真实调用 `write_required_regressions_proof_bundle(...)`;
  - `PLAN.md:120` P2.2「删 `verify_required_regressions_from_full_test_debt.py` + `test_registry.py` 大半」;
  - `PLAN.md:33` §1.4 SOP 第 3 行仍调该已删工具(且第 5 行调 `run_quality_gate.py`)——**A 同一份 PLAN 自指又自删**。
- **冲击**:P2.2 一旦 `git rm` 该模块而不在同提交改接 `:25`,`run_quality_gate` 模块 load 即 ImportError → A 自己的 P2.4 验证命令 `run_quality_gate.py --require-clean-worktree` 起不来,A 红线"不改对外 CLI"被 ImportError 实质架空。
- **关键校正(对 B 的冲击降级)**:实测 **B 计划全树对 `run_quality_gate`/`sync_debt_ledger` 0 命中**,B 各批门禁是**直跑 `pytest tests/test_architecture_fitness.py` 21 项**,不经 `run_quality_gate`,也不照抄 A 的 §1.4 SOP(那是 A 自己的 SOP)。所以"B 照抄 §1.4 即 no-such-file 卡死"是**误报(见 §五-12)**。真问题是 **A 内部一致性债 + B-12 同型漏钉**:必须当 A 必修项处理,而非 B 交界 blocker。
- **修法**:新增 **B-14**,与 B-12 并列入 P2.2 原子提交:
  - P2.2-M4 删模块的**同一提交**内改接/移除 `run_quality_gate.py:25` import 及 `:1858` 使用点;落地后跑 `python -c 'import scripts.run_quality_gate'` 不 ImportError;
  - 同提交把 §1.4 SOP 第 3 行 verify_required 替换为 P2.2 后等价命令(`pytest -m required`),避免 B 若真去引用时撞死命令;
  - `long_gate_manifest.py:127` / `quality_gate_shared.py:122/772-773` 经核是字符串字面量(非 import),module-load 不炸,语义层随编排改即可。

---

## 四、建议补(medium,值得补但不卡执行)

### ④ B 新建 parity 测试远多于 B-9 的"3 个",须过 A 的 P7/P6
B-9 只说"3 个 parity 测试须登记进门禁组",实际 B 新建/扩写 ≥10 个(`test_sgs_graph_ready`/LB04 全矩阵/R05 五条/R22 24键/R62 三套快照/GF1/R47/R09/R54 三基数/R58…),其中 `regression_boolean_normalize_wide_parity_contract.py`、`regression_gantt_critical_chain_normalize_parity.py` **实测仓库不存在**、不在 csv。A 的 P7(`PLAN.md:199`)门禁三关:①须有 `def test_` ②强制 docstring ③新源文件须 scope 覆盖。**修法**:升级 B-9 为全量枚举 + 裁定"B 在 A 之后新建的测试一律遵 A 的 P6 子目录 + 去前缀 + `_contract/_guard/_smoke` 后缀 + `def test_` + docstring + scope 登记";由 P6 迁移脚本附产"B 新文件目标子目录映射"。注:多数 B parity 是**扩写既有 pytest-style 文件**(`spec_sync_contract`/`execution_review_identity_guardrail`/`schedule_result_view_context` 实测都是 `def test_`),门禁压力小;真风险只在落新文件者 + 一条 trivial 的 docstring 勾。

### ⑤ oversize 扩产无登记接口,B 无批后台账重刷 SOP(J2 真雷)
见 §一-J2。R54 收口点 `scheduler_workbench_links.py` 实测 **487 行**逼近 500;`sync_debt_ledger` 无"非启动链新增 oversize 登记"命令。**修法**:新增 **B-15**——在 B 的 PHASE4 计划补"批后 fitness 红分情况处置"一节(新增 oversize 首选拆文件/拆函数=门禁本意,确无法缩才 owner 经 `set-entry-fields` 受控登记 + accepted_risks);把 R54 落为 Batch-C go-no-go 检查点(扩产前后实测目标文件行数,逼近 500 优先拆分)。**注意:silent 侧重刷义务实测不需要(§五-11),B-15 只管 oversize/complexity。**

### ⑥ R22 bad-role oracle 落在 KEEP_TRIM 保留区外侧,P5.2 剪尾可能误砍
实测 `regression_schedule_result_view_context.py` 共 301 行,`:294 def test_gantt_plan_query_wrapper_keeps_legacy_bad_role_message` / `:300 assert "未知的排产方案角色：bad" in exc.message`;`csv:360` KEEP_TRIM 保留区界定为 `line:124-291`,剪除对象枚举为"中文文案子串 line:160/183/202"——**`:294-300` 在保留区外、形态正是"遗留中文文案断言"**。这是 R22(爆点#23)删 `normalize_plan_role` 后兜 bad-role 静默归 adopted 的唯一 oracle。**降级理由**:verdict 明确枚举了剪除的三行(非"291 后全删"),且 `:300` 用 `in`(含关键片段)正是 P5.2 trim 的目标态而非要删的 exact-match 态;误删需"执行者把 124-291 当穷举白名单 + 横扫所有中文断言"的 careless 失败模式。**修法**:新增 B-4 同级条目明确保留 `:294-300`,`csv:360` reason 追加 `[⚠B-COMPAT 保留:294-300 R22]`,B 侧动手前 `pytest -k legacy_bad_role_message` 自检。

### ⑦ R28 须编辑 A 锁 KEEP 的 `test_architecture_fitness.py:77` 白名单——KEEP≠冻结
R28 收口(`_safe_float` 改 raise)必须同步退 `test_architecture_fitness.py:77` 的 `LOCAL_PARSE_HELPER_ALLOWLIST` 条目,否则 `:254` stale_entries 守卫红(`R28.md:65`)。A 把该文件锁 KEEP + 列禁删。**修法**:在 B-11/B-12 旁补一句——`test_architecture_fitness.py` 是"**A 禁删但 B 可改**",A 的 P7 防回潮门禁绝不可对它加"内容指纹/禁改"锁,只可禁删;B 改 `:77` 白名单的时机须与该批次同提交(避免分两次提交中间门禁红)。

---

## 五、已被覆盖(确认无需新动作)/ 误报(已证伪,不处置)

**已被 `_B_COMPAT` 覆盖,无需重复**:
- **#8** R54 dossier test_consumers 未登记 A 的 MERGE+P6 改名 → B-2/B-3 已从 A→B 覆盖"合并禁去重 + P6 重 grep";收口后 collar 恒产键使 `pop` 用例语义虚构但断言仍 fail-closed 通过,**low 非 blocker**。
- **#9** B-2"避免交叠窗口"是 B-3 强串行下的冗余死条款,仅措辞误导 → 建议改写 B-2 措辞,无需新护栏。
- **#10** B dossier 对 A 失明(仅 R43/`_fixed_confirm` 2 处提 A)→ B-10 已是兜底,建议升级为"A 已改文件 × B 引用"交集检查单(本轮已算出量级),但属 low。

**误报(因果链建立在错误前提,实测证伪——别再报警)**:
- **#11 "B 改静默回退 → 静默台账 stale → go-no-go 红 → 须重刷"**:实测门禁非启动链只续管 `legacy_swallow_hit`,B 的 6 个目标文件台账命中**全 0** → silent 侧 fitness 不会红,重刷义务不存在;且建议的 `refresh --mode scan-startup-baseline` 只刷启动链,对这些文件 no-op。**holds=false,severity=none。**
- **#12 "§1.4 SOP 把已删 verify_required 串在前 → B 照抄即卡死"**:实测 B 计划 0 处引用 A 的 §1.4 SOP / `run_quality_gate`,B 门禁直跑 `pytest test_architecture_fitness.py` 自洽 → "B 照抄"前提不存在。真问题是 A 内部债(已并入 §三-③ B-14),**对 B 的交界 high 降为 low**。
- **#13 "P3.3 改写 HOLD_FOR_R51 文件 + P7 锁成禁删 → B git rm 触发门禁"**:`PLAN.md:200` 已逐字写明"门禁只拦新增违规,不锁既有测试的删除",且**点名这两个文件 B 仍要删**。P7 项①是"新增时缺 `def test_` 才拦"的 additive 新增门,结构上不可能在 `git rm` 既有文件时触发。该保护已存在,提议属重复造轮子。**holds=false。**(注:这两文件的**真**风险是 #1 blocker 的 collector 删除,不是 P7 锁删。)

---

## 六、明确建议:是否补 `_B_COMPAT_SAFEGUARDS` / 调批次时序

**结论:需要补,但不需调整"先 A 后 B + P6 后启 B"的总时序骨架。** 具体补丁清单:

| 补丁 | 内容 | 严重度 | 落点 |
|---|---|---|---|
| **裁 blocker** | P3.4 删 collector 前:把 R51 两个续命测试转 pytest(断言体逐字保留)**或**加"无残留 main-style"守卫 | blocker | `PLAN.md` P3.3/P3.4 + §6 加排除条款 + R51 dossier 注 `--collect-only>0` |
| **新增 B-13** | sp05 从 DROP 改 HOLD_FOR_*(或清表上提 P1.1),改写 §5 把 sp05 移出"可放心删",标注 R01/R26/R43 串行依赖 | high | `_B_COMPAT_SAFEGUARDS` §5 + 新 B-13 |
| **新增 B-14** | P2.2-M4 删 verify_required 的**同原子提交**改接 `run_quality_gate.py:25` import + `:1858` 使用点 + §1.4 SOP 第 3 行;落地验 `python -c 'import scripts.run_quality_gate'` 不炸 | high | P2.2 验收 + 新 B-14(与 B-12 并列) |
| **新增 B-15** | B 批后 fitness 红分情况处置 SOP(仅 oversize/complexity,silent 不需);R54 落 Batch-C go-no-go 行数检查点 | medium | B 的 PHASE4 计划 + `_B_COMPAT` |
| **升级 B-9** | "3 个 parity"改全量枚举 + 裁定 B 新建测试遵 A 的 P6/P7 终态约定 | medium | `_B_COMPAT_SAFEGUARDS` B-9 |
| **B-4 同级** | 保留 `regression_schedule_result_view_context.py:294-300` + `csv:360` reason 追加保留标注 | medium | `_B_COMPAT` + `L3_verdicts.csv` |
| **B-11/12 旁注** | `test_architecture_fitness.py` = "A 禁删但 B 可改",P7 不得加禁改锁(供 R28 退白名单) | medium | `_B_COMPAT` B-11/B-12 |
| **B-2 措辞** | 改写"避免交叠窗口"为与 B-3 一致(B-ROOT 是 B 序列内最先,整体仍在 A 全 P0-P7 后) | low | `_B_COMPAT` B-2 |

**时序骨架不动**:B-3"P6 后、tests 定稿后启 B"正确;唯一的硬序新增是 **blocker #1**——P3.4 删 collector 这个动作必须在删之前完成 R51 续命测试的 pytest 转换或加守卫,否则 A→B 窗口内 B 的回归网静默失效。这是 A 阶段内部的硬序,不影响 A/B 之间的总顺序。

**关键证据文件(绝对路径)**:
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/PLAN.md`(§1.4 SOP:29-36、P3.4:149-150、P6:188-193、P7:199-200)
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/_B_COMPAT_SAFEGUARDS.md`(§5:115-118、§6:135、B-9:89、B-12:66-76)
- `/Users/lurenxing/Documents/GitHub/----/.codestable/refactors/2026-06-01-test-gate-cleanup/L3_verdicts.csv`(:360 view_context KEEP_TRIM、:620 fitness KEEP、:642 sp05 DROP)
- `/Users/lurenxing/Documents/GitHub/----/scripts/run_quality_gate.py:25`(verify_required 顶层硬 import)
- `/Users/lurenxing/Documents/GitHub/----/tools/quality_gate_operations.py:812-830`(silent 扫描非启动链 legacy 门控——J2 误报的实证)
- `/Users/lurenxing/Documents/GitHub/----/.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety/dossiers/R43.md`(:52/:65-66/:109/:142-144 sp05 三表 + 串行依赖)
- `/Users/lurenxing/Documents/GitHub/----/tests/regression_schedule_result_view_context.py:294-300`(R22 bad-role oracle,保留区外)
- `/Users/lurenxing/Documents/GitHub/----/tests/regression_sort_strategy_case_insensitive.py` & `regression_dispatch_rule_case_insensitive.py`(main-style 实测 def main=1/def test_=0)
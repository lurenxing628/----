# 红队第1轮·3号 — 原子性+闸门猎手对 PHASE4-SAFE-BATCH-PLAN.md 的攻击报告

> 视角：批内两债撞行号没拆开 / 该同提交没同提交；11 标红债是否被偷偷给终态修法；owner_pending 是否全部「只标」。
> 纪律：只读不改任何 .py；所有行号 2026-06-05 实盘 rg 回盘；权威路径以 _layer2_residual.md §权威真实路径表为准。

## 结论速览

发现 **3 个真问题** + 1 个噪音规约。其余攻击靶点（R42+R60、R45≡R48、R25+R52、R06+R27、R34+R35、dispatch_rules 三债同提交）回盘后判**无硬伤**。

---

## P-RT13-01 · R64/R65 两条真债被整份计划吞掉（漏债）【高】

**问题（哪批+哪债）**：计划全文（grep 计数 = 0）从未出现 R64 / R65。§1.0 ⚠简化声明只列「LEAF-DUP-P4 簇的 11 债：R69/R03/R41/R68/R32/R40/R53/R61/R70/R43/LB04」，把 R64/R65 漏在外，既不入 Batch-A 也不入 Batch-D，无任何 G 编号、无承重门、无 owner 闸门。

**为什么会炸（file:line/符号/测试）**：
- registry 实证 R64/R65 是 `kind:real` / `status:planned` 的活债：R64 = 死 helper `_has_navigation_date_range`（`web/viewmodels/scheduler_navigation_links.py:66-67`，rg 回盘 def 原样在位、全仓零调用），R65 = 同文件孪生。registry `planned_batch_hint` 明写「建议与 R65 打包成同一原子提交（同文件）」。
- 致命点：R64/R65 与 **R42（G01，Batch-C）same_file**（registry interference_edges 标 `same_file:true`，同 `scheduler_navigation_links.py`）。R42 在 Batch-C 改该文件 collar 调用区（`:40 build_workbench_plan_context(plan_role=ROLE_ADOPTED)` 等），而 R64 死 helper 在 `:66-67`、活近亲 `_has_navigation_context:47-63` 被 `:71/:114/:142/:175` 真用。两债同文件却没被纳入 §1.3 dispatch 式串行编排，删 R64 时若照旧行号（漂移后）易误伤 `_has_navigation_context` 或与 R42 改动行号互撞。
- 净化叙事把 80→73 债，但 R64/R65 不是被裁掉的 7 条（计划 §0.2 列的对消/作废清单里没有 R64/R65），是**静默蒸发**。

**修正建议**：把 R64/R65 显式登记进 Batch-A（纯删叶子，owner=false，registry 已判 load_bearing:false / needs_adversarial:false），并在 §1.4 G01 的不可碰清单 + §1.0 序列里标注「R64/R65 与 R42 same_file，删序须按符号重 rg、与 G01 改区行号对账」；⚠简化声明的「11 债」改「13 债」补 R64/R65。

## P-RT13-02 · R49 一债拆两批（G25@Batch-A + G24@Batch-B）却无同提交/串行声明【中】

**问题（哪批+哪债）**：R49 被拆成两半落到不同批：G25（Batch-A，§1.2，删旁支 4~5 行）+ G24（Batch-B，§1.3，主体 `dispatch_rules.py:28-35` 一次原子删）。计划只在 G24 内声明「R49+R50+R51 一次原子 diff」，**未对 G25↔G24 这同一债的两半建立任何同提交边或串行序**；§3 owner 表、序列总览的硬边里都没有 R49-self 串行。

**为什么会炸（file:line/符号）**：
- `dispatch_rules.py` 的符号被 greedy 内 `dispatch/sgs_scoring.py`、`dispatch/sgs.py`、`scheduler.py` 多文件消费（rg 回盘）。G25 旁支删点（计划写 evaluation:40-41/ortools:24-25，实盘活同前缀函数在 `sgs_scoring:34`/`ordering:59`）与 G24 主体删 `dispatch_rules.py:28 parse_dispatch_rule` 共享调用图。
- Batch-A 早于 Batch-B 落地：若 G25 先删旁支调用点、G24 的 `dispatch_rules.py` 实现还在 → 实现变孤儿（无 loud，纯死码堆积）；反向若 Batch-B 先删实现而 Batch-A 旁支调用未清 → 调用悬空 NameError。计划自己在 G25 警告「禁符号名全局删，铲 sgs_scoring:34/ordering:59 活同前缀 NameError」，恰恰说明两半共享符号命名空间，更需要同债串行钉死，但没钉。

**修正建议**：在 §1.0 序列与 §1.3 G24 显式加一条 R49-self 串行边「G25 旁支删点须晚于或同 G24 主体删，且删后 grep `parse_dispatch_rule` 全仓零残引用」；或干脆把 R49 旁支并回 G24 一次原子，不跨批拆。

## P-RT13-03 · 标红债 RQErr 合同数 15 vs 实盘 16（数字漂移，弱化 R52 闸门）【低-中】

**问题（哪批+哪债）**：R52（标红，G39@Batch-B）。计划 §1.3 / §1.4 / O08 / RK12 四处统一写「**15 个** ReadyQueueContractError 合同」（V4⑦ 拍定 31 用例中 15 个 RQErr）。

**为什么会炸（测试名）**：rg 回盘 `tests/scheduler_graph/test_ready_queue.py`：`def test_` 计数 = **31**（与计划吻合 ✓），但 `ReadyQueueContractError` 出现 = **16** 处。若 16 是 16 个合同用例而计划按「15」分流，A2（改写 LIVE 等价断言保留）会漏接 1 个合同覆盖，删 impl 后该用例静默失覆盖。需在 owner 闸门 O08 前核对「15 还是 16 个 RQErr 用例」——这是标红债的合同覆盖完整性，不能带着 ±1 的数字漂移进批。

**修正建议**：执行前对 `test_ready_queue.py` 逐个数 RQErr 用例（区分 `raises(ReadyQueueContractError)` 断言用例 vs import/import-as 出现），把 §1.3/§1.4/O08/RK12 的「15」核准为实盘值（疑为 16），再据准数做 A2 分流。

---

## 噪音规约（非炸点，但建议清掉，免误导执行者）

- **D2 别名 `n(` 纪律是幻觉前提**：§1.4 G01 / §2-R42 / _layer2_residual D2 反复要求「删 R42 形参须同查 `build_workbench_plan_context` 与别名 `n(` 两调用形态」。rg 回盘全仓**无 `as n` 别名**，7 个调用方（navigation_context / analysis_links / resource_dispatch / dashboard_workbench_context / navigation_links / gantt_task_detail / reports_workbench）全用真名 import。co-change grep 只需查真名即可，别名规约建在不存在的前提上，应删以免执行者空跑。

## 回盘判无硬伤的靶点（明说，免得被当漏查）

- **R42+R60（G01）同提交闸门成立**：回盘 `dashboard_workbench_context.py` 真实路径在 `web/viewmodels/`（非 routes/domains），`:92` 是 `_context_kwargs` 字典 `"plan_id"` 键、`:119` 经 `**_context_kwargs` 展开流入 collar、`:191` 是 collar def `plan_id: Any = None` 形参——计划「删 :191 形参 MUST 同删 :92 字典键否则 TypeError 500」逻辑正确，爆点 #21 闭合无误。
- **R45≡R48（G16）整删合理**：registry 确认两编号同指 `config_adapter.py` 死壳（R45 死壳/R48 迁移残渣）；2026-06-08 终态已 fixed，旧 sp06 文件已由 A P1.1 删除，清单同步 no-op。
- **R25+R52（G39）同提交声明在位**：§1.3「R52 迁 31 测试 + 删 impl + R25 垫片同提交」+ RK18 缓解，原子声明完整。test_ready_queue 实盘 31 用例确认（dossier ~23 失真已被 V4⑦ 纠回）。
- **R06+R27+gantt（G38）四包同提交在位**：sp05 contract `_assert_init_has_no_imports:173` def + `:316/:409` 断言实盘在位，「四包一次性原子提交、保 :173 def、:638 第二处不碰」声明完整。
- **R34+R35（G30）repoint 目标存在**：`get_plan_time_span_for_resolution` 实盘在 `schedule_plan_query_service.py:210`（§5.3 verify 纠 dossier「不存在」为「存在」正确）；活近亲 `schedule_repo.py:71 list_version_rows_by_op_ids_start_range`/`:160 list_by_version_with_details` 在位，不可碰清单准。
- **dispatch_rules 三债（R49/R50/R51 在 G24 内）一次原子声明在位**：`import math:3` 保留正确；`:28 parse_dispatch_rule` 等 def 实盘在位，「从大行号往小删」串行纪律对。（注：R49 跨批拆分问题见 P-RT13-02，与三债同提交是两件事。）
- **R69 标红债未被偷给终态**：虽 owner_pending=false（O24），但只给「loud raise（建议）vs 可观测降级」方向选项交 owner 拍，未落终态 patch；两份 `_op_seq` 原子同改 + `or 0` 合法路径不卷入 except 域，合规。其余 10 标红债（R09/R15/R19/R52/R14/R54/R04/R42/R22/R05）均带 ⏸ owner 闸门、只列待裁，未发现被偷分配终态修法。

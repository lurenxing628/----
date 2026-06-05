# 红队第2轮·2号 — 复攻2：行号位移链 / 测试退场顺序 / 同文件多批触碰

> 视角：带第1轮 9 项采纳结论重新脑内逐批跑全序列，专找「执行到第 N 批才暴露」的炸点——
> 同一物理文件被 ≥2 批触碰但只对账了其中一对、内部行号位移链、测试/形参退场顺序漏挂。
> 纪律：只读不改任何 .py；所有 file:line 按符号 rg 回盘（HEAD c2aa7501）；权威路径以 _layer2_residual.md 为准。
> 下列为复攻发现，逐条已回盘；末尾「登记已核·非炸点」列出查后确认无硬伤者，免被当漏查。

---

## 摘要

发现 **4 个真问题**（1 高 / 2 中 / 1 低-中）。全部是「同文件多批触碰只对账了一对」或「跨文件锚点被一句话挤在一起」类——第1轮抓了 R64/R65↔R42 same_file（RT3-P01）与 R49 跨批串行（RT3-P02），但**漏了同一文件第三、第四个触碰单元**，以及 `__all__` 串行边（E16）把三个不同文件的 `__all__` 当成「共享一个块」的幻觉锚点。这些都只在跑到 Batch-C 时才暴露。

---

## P-RT22-01 ·【高】`scheduler_navigation_links.py` 是**三批四单元**战场，计划只对账了 R64/R65↔R42 一对，漏 R67(G34) 第三方

**问题（批次+债）**：`web/viewmodels/scheduler_navigation_links.py`（实盘 205 行）被以下单元触碰：
- **Batch-A**：R64 删 `_has_navigation_date_range:66-67` + R65 删 `_target_url:74-78`/化简 `:160`/删孤儿 import `:4/:6`（同文件原子）。
- **Batch-C/G01**：R42 改 `:40 build_workbench_plan_context(plan_role=ROLE_ADOPTED)` 调用区 + import `:7`（collar 签名删 plan_id 形参后此 import 不变但调用语义受 collar 改动牵连）。
- **Batch-C/G34**：R67 抄点④ `_REPORT_CONTEXT_FIELD_NAMES`（实盘 `:11` 元组首，16 键 `:12-28`，资源键尾块 `:23-28`）+ 遍历点 `:186 preserved_report_context_fields`。

**为什么会炸（file:line/符号）**：计划 §1.0 ⚠简化声明补登（红队第1轮 RT3-P01）只钉了「R64/R65 与 R42 same_file」，§1.4 G34 也只给了「R67↔R42 diff-hunk 串行（E17）」。**但三者是同一个 205 行文件里跨两批的四处编辑**，且 R67 自己的 dossier（R67.md:156-166）明写「R42 同文件碰撞面应扩到 `scheduler_navigation_links.py`（抄点③④），不止 `reports_export_support.py`；串行避 diff hunk 互撞的范围应同时覆盖本文件」。脑内执行序列：Batch-A 先删 R64(`:66-67`)+R65(`:74-78`+`:160`)→文件从 205 行缩到约 195 行，`:186 preserved_report_context_fields`（R67 G34 的遍历点）下移到约 `:176`、`_REPORT_CONTEXT_FIELD_NAMES` 元组若在 R64/R65 上方（`:11-28`）不动但其下所有锚点系统性上移。等跑到 Batch-C 的 G01(R42) 与 G34(R67) 时，计划正文给的 R67 `:186`/`:11-28` 与 R42 `:40` 已全部漂移，且 G34 与 G01 在**同一文件同一批**还要互相串行（E17 只说「diff-hunk 串行」未说先后），三方混改极易让 G01 的 `:40` 收口误碰 R67 的 `_REPORT_CONTEXT_FIELD_NAMES` 元组成员（该元组首键就是 `plan_id`——正是 R42 的地盘，R67.md:52「禁改 superset 元组里 plan_id 等非资源键，那是 R42 地盘」）。

**修正建议**：把 `scheduler_navigation_links.py` 升为**单文件三批四单元串行编排块**（类比 §1.3 dispatch_rules 的显式硬序）：① Batch-A 的 R64/R65 先落且删后立即 `rg` 复核 `_has_navigation_context:47`/`preserved_report_context_fields` 在位；② Batch-C 进该文件前对 R42(`:40`)、R67(`_REPORT_CONTEXT_FIELD_NAMES` 元组 + `:186`) **全部按符号重 rg**；③ E17 明确「R67 抄点③④保现状/仅注释（O18 倾向）时与 R42 零冲突，一旦 owner 裁收编第4处则 R67 元组拼接 MUST 晚于 R42 删 plan_id 形参之后、且不得触碰元组内 `plan_id` 成员」。在 §1.4 G01 与 §1.0 序列把「R64/R65 same_file」扩成「R64/R65/R67 三单元 same_file」。

---

## P-RT22-02 ·【中】E16 `__all__` 串行边把**三个不同文件的 __all__** 当「共享一个块」——幻觉锚点 `:118-122` 会把 R01/R46 引到错文件

**问题（批次+债）**：计划 §1.4 G09 / §2 R19 / RK-E16 写「R19 与 R01/R46 共享 `__all__:118-122` 串行对账（E16）」，把 R01(Batch-B/G19)、R46(Batch-B/G40)、R19(Batch-B+C/G08·G09) 当作「同一 `__all__` 块顺序敏感」。

**为什么会炸（file:line）**：实盘三个 `__all__` 在**三个不同文件**，物理零重叠：
- R01 的 `__all__` = `core/services/scheduler/run/schedule_payload_contract.py:410-416`（删 `:414-415` 两条目），R01 主文件就是它（R01.md:18/46）。
- R19 的 `__all__` = `core/services/scheduler/execution_snapshot.py:118-123`（条目 `:122 positive_op_ids`），`:118-122` 这个锚点**只属于 execution_snapshot.py**（R19.md:60、live `rg __all__ execution_snapshot.py`=`:118`/`:122`）。
- R46 的 `__all__` = `scheduler_public_errors.py:340-351`，且 **R46 根本不动它**——`_safe_identifier` 不在 `__all__`（R46.md:52/80：「R46 删除完全不触碰 `__all__`，对 R01/R19 顺序不敏感，可任意先后」）。

也就是说 E16「三债共享 `__all__:118-122` 串行对账」是**伪串行边**：R01/R46/R19 在 `__all__` 上零物理重叠，`sym:__all__` 边是 registry 的「同符号名同居」误判，dossier 已各自否掉。真正的危害是锚点 `:118-122` 写在 G09 正文里，执行者改 R01/R46 时若信此锚点会去 execution_snapshot.py（R19 的家）找 R01/R46 的导出条目——而它们根本不在那里（R01 在 payload_contract:414-415，R46 不在任何 `__all__`）。

**修正建议**：§1.4 G09 / §2 R19 / RK-E16 删除「R01/R46/R19 共享 `__all__:118-122` 串行对账」这条伪串行边，改为三条独立事实：R01 改 `schedule_payload_contract.py:414-415`、R19 改 `execution_snapshot.py:122`、R46 不改任何 `__all__`（仅同符号名同居，顺序无关）。E16 从「串行对账门」降为「登记备查·无依赖」。

---

## P-RT22-03 ·【中】G09(R13) 漏挂 `_fact_from_state` 的 `latest` 形参 `:43` + 调用点实参 `:123` 退场，只删字段 → 删后 TypeError

**问题（批次+债）**：Batch-C/G09 删 R13 死字段，计划正文只写「删最上方死字段 R13(`:23-24/:56-57`)」。

**为什么会炸（file:line/符号）**：实盘 `execution_fact_provider.py`：`last_event_schedule_version`/`_id` 死字段定义在 `:23-24`（live 确认 ✅），赋值在 `_fact_from_state` 体内 `:56-57`（`last_event_schedule_version=None if latest is None else int(latest.schedule_version)`，live ✅，计划锚点对，R19.md 的 `:20-21/:42-43/:96` 是 registry 失真值，R13.md:27 已纠）。**但 R13 的真正退场面不止两行字段**——R13.md:50-52 列明：(a) 删字段 `:23-24`；(b) `_fact_from_state` **删 `latest` 形参（`:43`）+ 删 `:56-57` 两行赋值 + 删调用点 `:120-125` 里传入的 `latest_events.get(scope)` 实参（`:123`）**；(c) 评估连带删 `_latest_events_by_scope:163-170` + `:118` 调用（删字段后成孤儿）。计划 G09 只点了 `:23-24/:56-57`，**漏了 `:43` 形参 + `:123` 实参**。若照计划只删字段两行：`_fact_from_state` 仍声明 `latest` 形参、`:56-57` 删后该形参变未用参数；若顺手把 `:56-57` 删了又没删 `:43` 形参与 `:123` 实参，则形参悬空——更糟的是若执行者「为了干净」删了 `:43` 形参却漏 `:123` 调用点实参，下一次调用 `_fact_from_state(..., latest_events.get(scope), ...)` 即 **TypeError: unexpected positional arg**，且这是 facts 主链热路径（读历史/重排）。此外 `:56-57`（R13 赋值）落在 `_fact_from_state` 体 `:40-62` 内，**与 R15 的 `_parse_execution_time` 调用 `:54/55` 仅隔 1-2 行**——R15(G08,Batch-B)先改、R13(G09,Batch-C)后删，同函数体内 1-2 行间距，比计划「删上方位移下方、先 R15 不位移任何人」的框架紧得多：R13 删 `:56-57` 会让其下行号上移，若 R15 在 Batch-B 已在同体内增删过行，G09 动手时 `:56-57` 必漂，须按 `last_event_schedule_version=` 键名 rg 而非裸行号。

**修正建议**：§1.4 G09 R13 退场清单补全为「删字段 `:23-24` + 删 `_fact_from_state` `latest` 形参（按符号定位，现 `:43`）+ 删赋值 `:56-57` + 删调用点实参 `latest_events.get(scope)`（现 `:123`）+ 评估连带删 `_latest_events_by_scope`/`:118` 孤儿（R13.md:52）」，四处**同一原子提交**；并注明 `:56-57` 在 `_fact_from_state` 体内紧贴 R15 的 `:54/55`，G09 动手前对该函数体整体重 rg。

---

## P-RT22-04 ·【低-中】R67 第4处「保现状/仅注释」与 R42 同文件，但 O18 倾向收编①②、③④保现状——若 owner 裁收编③④则与 R42 删形参产生**元组拼接 × 形参删除**跨批序

**问题（批次+债）**：O18（R67 第4处收编）+ G34（Batch-C）+ G01/R42（Batch-C）。

**为什么会提**：R67 抄点③④是 superset 元组（`_REPORT_CONTEXT_FIELD_NAMES` 16 键，首键 `plan_id`）。O18/dossier 倾向「①②纯6键必收，③④保现状/仅注释」——若按倾向走，R67 与 R42 在该文件零冲突（R42 删 collar 形参 plan_id，不碰元组成员）。**但 O18 是 owner_pending**：一旦 owner 裁「收编第4处」，R67 要对 `_REPORT_CONTEXT_FIELD_NAMES` 做元组拼接（`(...前缀键..., *REPORT_RESOURCE_FILTER_ARG_KEYS)`，R67.md:46/76），而该元组首键 `plan_id` 正是 R42 的死面包屑地盘。两债同批同文件，且元组里有 R42 关注的键——计划 §1.4 G34 只给「R67↔R42 diff-hunk 串行（E17）」一句，未区分「O18 走保现状（零冲突）」vs「O18 走收编③④（元组拼接撞 plan_id 键，须晚于 R42 删形参且禁碰元组内 plan_id 成员）」两条路。脑内执行到 Batch-C 若 owner 临时拍「收编第4处」，E17 这一句不足以防 G34 元组拼接误动 plan_id 键。另：R67.md:115/130 指出收编第4处会新增 `web.viewmodels → core.services.report` 跨层边，须先过 AST/分层门——这条分层风险计划 §1.4 G34 也只字未提（只说「①②必收」）。

**修正建议**：§1.4 G34 / O18 把 E17 拆成两条件分支：「O18=保现状/仅注释 → R67↔R42 零冲突，无需串行」；「O18=收编③④ → R67 元组拼接 MUST 晚于 R42 删 collar 形参、禁碰元组内 `plan_id` 成员、且先过 `web.viewmodels→core.services.report` 分层门（否则违分层 0）」。把分层门风险从 dossier 提升到 G34 前置安全网正文。

---

## 登记已核·非炸点（查后确认无硬伤，免被当漏查）

- **R13 锚点 `:23-24/:56-57` 计划值正确**：live 回盘字段定义 `:23-24`、赋值 `:56-57` 与计划 G09 吻合；R19.md 携带的 `:20-21/:42-43/:96` 是 registry 失真值，R13.md:27 已纠为当前态——计划 G09 取的是纠正后值，**非 bug**（仅 P-RT22-03 的形参/实参退场面缺登）。
- **R64/R65 same_file↔R42 已被第1轮 RT3-P01 闭合**：本轮只补出「第三方 R67 同文件」（P-RT22-01），R64/R65 自身归 Batch-A 纯删、与 `_has_navigation_context:47` 活近亲不重叠，第1轮处置正确。
- **R49 跨批串行（G25@A/G24@B）已被第1轮 RT3-P02 闭合**：§1.3 已加 R49-self 串行边「G25 晚于或同 G24，删后 `rg parse_dispatch_rule` 零残引用」，复核无新增反序。
- **EXEC-FACT provider 内 R15→R19→R13 串行序方向正确**：R15 def `:85`（不位移上方）、R19 `_positive_op_ids:70`、R13 字段 `:23-24`——「先改下方后删上方」原则成立（V1①）；本轮只补出 R13 退场面缺形参/实参（P-RT22-03），串行方向本身无反序。
- **R19 provider 局部副本 `:70` vs execution_snapshot 全局 `positive_op_ids:28` 是两个符号**：未混淆；R19 的 provider 触碰（`:70/:82`）与 snapshot 触碰（`:28/:40 sorted`）分属两文件，计划 §1.4 G09「provider 链」与 R19 snapshot:40 sorted 承重（爆点 #9）各自独立，无冲突。

---

## 总结（复攻2 逐批结论）

第1轮已把「被当现状的待建前置（GF1）/ 路径丢前缀（R52）/ 跨文件行号挤一句（R42 :92/:191）/ 漏债（R64/R65）/ 跨批串行（R49）/ 计数漂移（RQErr 16）」六类抓干净。复攻2 专打「同文件多批触碰只对账一对」与「伪串行锚点」，得 4 个新炸点：
- **P-RT22-01（高）**：`scheduler_navigation_links.py` 实为三批四单元（R64/R65@A + R42@C/G01 + R67@C/G34）战场，计划只钉了 R64/R65↔R42 一对，漏 R67 第三方——跑到 Batch-C 三方混改 + 行号已被 Batch-A 删点系统性位移时暴露。
- **P-RT22-02（中）**：E16「R01/R46/R19 共享 `__all__:118-122`」是伪串行边——三个 `__all__` 在三个不同文件物理零重叠，R46 根本不动 `__all__`，锚点 `:118-122` 只属 execution_snapshot.py，会把改 R01/R46 的执行者引到错文件。
- **P-RT22-03（中）**：G09 R13 退场清单漏 `_fact_from_state` 的 `latest` 形参（`:43`）+ 调用点实参（`:123`），只删字段两行→删后形参悬空/调用 TypeError，且 `:56-57` 紧贴 R15 `:54/55` 同函数体须按键名 rg。
- **P-RT22-04（低-中）**：R67 第4处 O18 一旦裁「收编③④」则元组拼接撞 R42 的 plan_id 键 + 新增 viewmodels→core.services.report 跨层边，E17 单句「diff-hunk 串行」未防，须拆 O18 两分支并把分层门提正文。

共性病根：**same_file 干扰边只两两登记，三方以上同文件碰撞未升为「单文件多批串行编排块」**；以及 `sym:__all__` 这类「同符号名」边被当成「同物理块」串行，制造伪锚点。批次拓扑方向（脊梁四步、13 H 边）仍无反序，问题全在「执行到 Batch-C 同文件混改时」的锚点/退场面层。


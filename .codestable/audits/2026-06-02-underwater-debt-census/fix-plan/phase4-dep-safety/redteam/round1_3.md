# 红队 3 号 · 排序约束/批次依赖攻击（只读不改）

> 攻击角度：排序约束错——批次顺序反了？承重前置 / facade 晚于收敛(B13) / parity 先于收敛(LB07/R22/R68) 有没有被违反？R09 收口点已存在后批次依赖是否还成立？R13↔R18 解耦后批次是否正确？
> 输入：_interference_rebuilt.md + clusters/{CONFIG-DUAL,COMPAT-DISPATCH,PARSE-INT,EXEC-FACT,PLAN-IDENTITY,RESOURCE-REPO}.md + 当前代码 rg 实盘（HEAD c2aa7501）。
> 默认怀疑，只报真问题不凑数。

---

## 发现 1（真问题·硬·文档自相矛盾）：B13 facade 三常量删序方向，E05 与 A14 给出相反方向

**问题**：同一条 facade ImportError 删序约束，主综合在两处标了**相反的有向边方向**。

- §2.1 边表 E05（line 83）：`G23(R33) → G17(R31)`，释义「R33 删壳须**不晚于** R31 删源:9」→ 即 **R33 先**。
- §4.2 新增边 A14（line 280）：`R31→R33（删序硬约束）`→ 即 **R31 先**。
- 二者描述的是同一条 `facade:11 残 import loud ImportError` 约束，方向恰好对调。

**实盘证据**（rg 回核 HEAD c2aa7501）：
- facade 壳 `core/services/common/value_policies.py:3-11`：`from core.shared.value_policies import ( ... WRITE_INTERNAL_ONLY, )`，`__all__`（:29）re-export。
- shared 源 `core/shared/value_policies.py:9`：`WRITE_INTERNAL_ONLY = "write_internal_only"`。
- 依赖方向：**facade 壳 import shared 源**。要避免 ImportError，必须**先删/收 facade 壳的 import（R33），再删 shared 源定义（R31）**。

**判定**：E05（R33→R31，R33 先）方向**正确**；A14（R31→R33）方向**写反**。§3 重灾区行（line 203）与簇 C-CONFIG-DUAL §B（line 43，「R33 不晚于 R31」）也都站 R33 先一侧。A14 是孤立的方向错误。

**修正建议**：把 §4.2 A14 改为 `R33→R31（删序硬约束：facade 壳删 import 不晚于 shared 删源，否则 facade:11 loud ImportError）`，与 E05 对齐。注意：这是文档标注错误，不动任何 .py；簇内硬序「R33 步1→R30→R33 步2/3」本身是对的，**真实落地序不受影响**，但有向边表自相矛盾会误导后续 Layer 拓扑工具。

---

## 发现 2（真问题·中·边方向标注误导）：E06 / A15 把 B13 三常量边标成 R30→R31，掩盖真正的约束源是 facade(R33)

**问题**：§2.1 E06（line 84）`G23(R30) → G17(R31)`、§4.2 A15（line 281）`R30→R31`，都把「三常量 re-export」硬序标成 R30 先于 R31。

**实盘证据**：R30 删的三常量 `VALUE_DATE/VALUE_DATETIME/READ_FILTER_ONLY` 定义在 `core/shared/value_policies.py:12/16/17`，而 facade 壳 `core/services/common/value_policies.py:6-8` `from core.shared.value_policies import (READ_FILTER_ONLY, VALUE_DATE, VALUE_DATETIME)` import 它们（:24-26 re-export）。

**判定**：R30（删 shared 三常量定义）与 R31（删 shared WRITE_INTERNAL_ONLY 定义）**同为 shared 侧删除动作，彼此间无强先后**——它们的共同硬约束源是「facade 壳(R33)必须先停止 import 这四个常量」。把边标成 `R30→R31` 是把两个对等的 shared 删动作之间生造了一条方向，真正该画的是 `R33 → {R30, R31}`（facade 清理先于 shared 删源）。E06 释义里「R30 须与 R31/facade **同窗口**」其实已暗示这点，但方向箭头与释义打架。

**修正建议**：E06 / A15 改为 `R33 → {R30, R31}（facade 壳停 import 先于 shared 删三常量+WRITE_INTERNAL_ONLY 定义；R30/R31 之间无序，同窗口）`。否则下游若按 `R30→R31` 拓扑排，会误以为 R30 必须严格先于 R31，而实际它们可同 diff，唯一硬前置是 R33 步1（迁测试 import）。

---

## 发现 3（核查通过·非硬伤）：R09 收口点已存在后，批次「作废建模块」依赖成立，无残留旧假设

实盘确认 `core/models/operation_execution_scope.py:9 def parse_positive_execution_int` **存在**；`parse_optional_positive_int` 全仓 rg = 0（新建前提确实作废）。主综合 §1 G22（line 37）、§5.1（line 336）已正确作废「新建模块」步、改 G22 为「收编 2 旧副本 + 分两路 parity（C 严格 5.9→None vs A/B 宽松 5.9→5）」。

批次依赖核对：G22 落 Batch-C，前置 = N1 注释(E26) + R07 前置(E25 已满足) + owner 裁；R09 不再门控任何「建模块」前置批，R46→R09 已由硬边降软位移(E15)。**该角度无排序硬伤**——批次依赖与「收口点已存在」事实自洽。唯一须盯：R09 A 副本归 G19 邻域(service:24)、B 副本归 G22(viewmodel:33)，两路 parity 不互为前置，§2.3 已专项验环为无环，正确。

---

## 发现 4（核查通过·非硬伤）：R13↔R18 解耦后，G09/G10 批次拆分正确，无残留旧同原子假设

实盘确认 `data/repositories/operation_execution_event_repo.py` 第 354/356/399/401/403/405 行整组 `raise _unscoped_execution_read_error()`（stub raise 契约护栏已在场），R13 死字段在 `core/services/scheduler/execution_fact_provider.py:23-24`（`last_event_schedule_version/id`）+ 赋值:56-57。

解耦前提成立：repo 已 stub raise → R13 不碰 repo → R13(G09 provider 链) 与 R18(G10 repo 链) 解耦。主综合 §1 G09/G10（line 24-25）、L09（line 299）、§5.1（line 337）均已把旧「R13+R18 同原子提交」拆开，R13 升 owner 二次确认（3 测试读活）。批次上 G09(provider 链)/G10(repo 链)各自独立落 Batch-C，无强先后。**该角度无排序硬伤**——拆分与解耦事实一致。

---

## 发现 5（核查通过·非硬伤）：parity 先于收敛三条主线（LB07/R22/R05）方向全部正确

- **LB07（G15a）→ R47/R71**：§2.2 ROOT（line 116）把 LB07 双栈注释+扩 spec_sync parity 上提 ROOT，门控 G15 收敛/R47 删参；簇 C-CONFIG-DUAL §A ASC-1（line 16-18）「LB07 先→R47+R71 同批(parity 绿后)」一致。parity 先于收敛✓。
- **R22（G27p）→ R21**：§2.2 ROOT（line 121）R22 24 键 exact parity 先落，§1 G27（line 43）「R22 先(parity)→R21 后」；簇 C-PLAN-IDENTITY §A①（line 27-30）同序，且 R21 严守保留 dpr_dict wrapper:32-39（R22 precondition）。parity 先于收敛✓。
- **R05（G33a）→ R05 步3 收敛**：§2.2 ROOT（line 119）R05 步1 扩 collar+步2 五条 parity 先落，门控步3；簇 C-RESOURCE-REPO §D（line 92）「步1 扩 collar→步2 parity→步3 收敛不可换序」。parity 先于收敛✓，且 collar 在 core.models 禁反向 import data.repositories（0 分层违规要求保留）。

任务铁律提到的 R68 在本批 12 簇成员清单中未出现（疑为笔误或属未纳入综合的 LEAF-DUP-P4 簇邻域），无法对 R68 做排序核查，此处不凑数。

---

## 发现 6（核查通过·非硬伤）：facade 晚于收敛(R26/G18) + 承重根 ROOT 零入边，方向正确

- **R26(G18) 最晚**：§2.1 E07/E08/E09（line 85-87）`G18(R26)→{G26(R29),G23(R33),G39(R52)}` 三桶收敛后 R26 才删，落 Batch-D（最晚）；簇 §B（line 44）「三桶先收敛 R26 后」+ R29 误标纠回 planned 复活 R26 facade 删序前置（E07）。facade 晚于收敛✓，方向无反转。
- **承重根 ROOT 零入边**：GF1/LB01/LB02/LB05/LB07/LB08/LB03/R05-step1/R22-parity 全为纯增量注释+parity，§2.3 验环确认零入边纯 source。GF1 默认 False 门控 G19/G20（E01/E02）方向正确（默认 True 会炸 parse_required_int 调用方，实盘 `parse_optional_positive_int=0` 旁证收口点策略）。

---

## 返回摘要

发现 2 个真问题（均文档有向边方向标注，不影响实际落地序但会误导下游拓扑工具）+ 4 项核查通过。

1. （硬·自相矛盾）B13 facade 删序方向：§4.2 A14 标 `R31→R33` 与 §2.1 E05 标 `R33→R31` 相反；实盘 facade 壳 `core/services/common/value_policies.py:3-11` import shared 源 `core/shared/value_policies.py:9`，正确方向是 R33（删壳）先于 R31（删源），A14 写反，须改为 R33→R31。
2. （中·方向误导）§2.1 E06 / §4.2 A15 把三常量边标成 `R30→R31`，但 R30/R31 同为 shared 侧删动作彼此无序，真正硬约束源是 facade 壳(R33)先停 import（实盘 :6-8 import 三常量），应改为 `R33→{R30,R31}`。
3. （通过）R09 收口点 `parse_positive_execution_int` 实盘存在(:9)、`parse_optional_positive_int` 全仓0，「作废建模块」批次依赖成立，无残留旧假设。
4. （通过）R13↔R18 解耦：repo:354-405 已 stub raise、R13 死字段在 provider:23-24/56-57，G09/G10 批次拆分正确无残留旧同原子。
5. （通过）parity 先于收敛三主线 LB07→R47/R71、R22→R21、R05 步2→步3 方向全对；R68 不在本批 12 簇成员中，未核（不凑数）。
6. （通过）R26(G18) facade 晚于三桶收敛落 Batch-D、承重根 ROOT 零入边、GF1 默认 False 门控 G19/G20 方向均正确。

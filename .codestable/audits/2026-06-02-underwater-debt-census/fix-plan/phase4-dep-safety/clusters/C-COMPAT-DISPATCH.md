# 簇 C-COMPAT-DISPATCH — 干扰图重建（Layer2 原子簇分析）

> 只读不改产物。成员债 R30 / R33 / R29 / R49 / R50 / R51。
> 主文件 compat_parse.py · value_policies.py · number_utils.py · dispatch_rules.py · sort_strategies.py · field_parse.py
> 回盘时间 2026-06-05。本文档做：A 原子子簇 / B 跨簇边 / C 边变化 / D 承重前置 / E fixed 残留。

## 0) 成员速览（回盘锚点）

| 债 | 桶 | 主文件 | 修法类 | lb | owner_pending | 当前锚点（rg 回盘） |
|---|---|---|---|---|---|---|
| R30 | B06 | compat_parse.py / value_policies.py | 直删 date 切片+退测试 | false | false | parse_compat_date@:198 / _date_fallback@:143 / 三策略@:179-208 / 常量:12/:16/:17 |
| R33 | B06 | core/services/common/{compat_parse,field_parse,value_policies}.py | 删三壳+迁/退测试（三步） | false | false | 三壳 def=0；测试 emits_degradation:18 / matrix:18 / config_contract:14/16/19/355/393-411 |
| R29 | B05 | core/services/common/number_utils.py | KEEP（owner-pending，授权 CSV 缺）/ 若薄壳化先重写 monkeypatch 为身份测试 | false | **true** | common/number_utils.py 全量 delegate→core.shared.strict_parse |
| R49 | B06 | dispatch_rules.py / evaluation.py / ortools_bottleneck.py | 直删 5 行死别名（定点删） | false | false | dispatch_rules:25 / evaluation:40-41 / ortools:24-25 |
| R50 | B05 | dispatch_rules.py | 直删 mean_positive+import statistics+外科退测试 | false | false | mean_positive@:112-132 / import statistics@:4 |
| R51 | B06 | dispatch_rules.py / sort_strategies.py | 直删两宽容解析器+**连退**续命测试 | false | false | parse_dispatch_rule@:28-35 / parse_strategy@sort_strategies:161-173 |

## A) 原子子簇（必须同批/同提交 vs 可独立）

本簇拆 **3 个原子子簇 + 1 个孤立 owner-pending 节点**。

### A1 · compat-facade 收敛链 {R33, R30}（必须同提交 + 硬内部顺序）
- **原子原因**：① 二者都改 `tests/regression_config_service_component_contract.py`（R33 删 :14/:16/:19 元组条目 + :393-399/:402-411 身份断言；交界行 `:411 parse_compat_date is` 在 R30 删实现后必失效，由 R33 步骤2 删）；② R30 删 `core.shared` 的 `parse_compat_date`/三 FieldPolicy/三常量，R33 删 `core.services.common` 三壳——壳 re-export 这些符号，删序错即 ImportError 或测试红。
- **内部顺序（硬，registry deps_hint + 两 dossier 双证）**：
  1. **R33 步骤1**（迁 `emits_degradation:18` + `matrix_contract:18` 两测试 import 从 `core.services.common.*` → `core.shared.*`）——为 R30 解锁，最先；
  2. **R30**（删 shared 实现：`parse_compat_date`@:198-215 / `_date_fallback`@:143-150 / date import :11/:14 / 三 FieldPolicy :179-208 / 三常量 :12/:16/:17 + 退 date 用例）；
  3. **R33 步骤2/3**（删 config_contract 身份断言含 :411 + 退元组三条 + 删三 .py 壳）。
  - 违序后果：R30 先删而 R33 步骤1 未迁 → :18 ImportError、:411 AttributeError（响声债，非静默）。

### A2 · dispatch_rules 三债同物理文件 {R49, R50, R51}（必须同一原子 diff，避免行号互撞）
- **原子原因**：三者全改 `core/algorithms/dispatch_rules.py`：R49 删 :25（顶部）、R51 删 :28-35（首函数）、R50 删 :112-132（末函数）+ :4 `import statistics`。删任一处都使其下方行号位移；R51 删首函数会把 R49(:25 之下)/R50(:112) 整体上移 7~8 行。**须一次性按行号快照删或按符号名定位**，严禁跨批拿旧绝对行号盲删。
- **内部顺序（人工 review 心智序，非运行期依赖）**：R49（零风险纯死别名，先清场）→ R51（medium，删宽容解析器并**连退** case_insensitive 续命测试，灵魂线红线：测试 :25 兜底断言禁迁/禁保留）→ R50（删 mean_positive，删 import statistics 前须确认 `statistics` 全文件零残留——回盘仅 :4+:132，可删；`import math`@:3 **保留**，:78/:95 真用）。从大行号往小行号删则各步互不回踩。
- **定点删红线**：R49 严禁按符号名全局删 `_parse_due_date`（`sgs_scoring.py:34` 同名活函数 + `evaluation.py:26 _parse_due_date_state` 重前缀，误删即 NameError 炸派工评分）。

### A3 · evaluation/ortools 死别名 {R49 之 4 行}（可与 A2 解耦独立）
- `evaluation.py:40-41` 与 `ortools_bottleneck.py:24-25` 两处 R49 死别名与 dispatch_rules.py **不同文件、互不影响**，可单独删，无行号互撞、无序约束（dossier 字段 12 明示）。即 R49 本体跨 3 文件，仅 dispatch_rules 那一行卷入 A2 原子，另 4 行可独立。

### A4 · R29（孤立，owner-pending，**只标不给终态**）
- **不进任何原子删除批**。R29 误标 not_applicable → corrections E 节纠为 **planned(owner-pending)**：授权 CSV 整目录 ABSENT，`common/number_utils.py` 仍全量 delegation-facade 到 `core.shared.strict_parse`（回盘证实 :5 import + parse_finite_float/int 薄壳），半截迁移不对称客观在场。
- **修法两选一交 owner**：(KEEP) 仅补显性「有意保留」注释，不写代码，不阻塞任何批次；(B 收敛/薄壳化) **前置硬约束**：须**先重写 monkeypatch 为身份测试**（`regression_config_service_component_contract.py` + `regression_ortools_warmstart_failure_contract.py:136` 经 monkeypatch 续命），否则老路径测试红。**本 Layer 只标 owner-pending，不给终态。**

## B) 跨簇边（本簇成员 → 其他簇债）

均为「同物理文件 / 收口前置」依赖，且全部指向 **C01 内其他子簇**（本回干扰图只有 C01/C02/ISOLATED，C01 即原 146 边主簇；这里的「跨簇」指本原子子簇外的债）：

| 本簇债 | 指向 | 关系类型 | 说明 |
|---|---|---|---|
| R30 → **R31**（B13，value_policies 壳 WRITE_INTERNAL_ONLY / re-export） | facade 收口前置 + 同收口锚点 | 删 `VALUE_DATE/VALUE_DATETIME/READ_FILTER_ONLY` 三常量前，`core/services/common/value_policies.py:6-8/:24-26` re-export 须同批删或 facade 先收，否则 ImportError 打挂 facade 全表面（**R30 最大爆炸点**）。R31 随 R33 节奏（corrections 种子）。 |
| R33 → **R31** | 同文件同改（壳吞并） | R33 删 value_policies 壳会连带吞掉 :11/:29 的 WRITE_INTERNAL_ONLY 壳侧 re-export；R31 只处置 `core.shared` 源侧 :9。建议 R33 删壳 ≥ R31 删源同批或 R33 先。 |
| R33 → **R29** | 禁区伴随（**非前置**） | `_SERVICE_COMMON_NEUTRAL_HELPERS` 元组 :15 `degradation` 是 R29 有意保留反例（且 degradation 是真承重实现非壳）。R33 删元组只动 :14/:16/:19，**死保 :15**。 |
| R51 → 收口点 **schedule_params.py:277/:346 + optimizer_config.py:166/:189** | parity/收口在位前置（只读） | R51 删宽容解析器的前提是严格 `require_choice→Enum()` loud-raise 收口点已在位（已回盘）。R51 不写这些文件，仅删前只读确认。 |
| R51/R33 → **schedule_params.py（LB07 所在）** | 仅只读，无写 | interference_edges 经 schedule_params 牵出 LB07，但 R51/R33 都不改 schedule_params.py，**互不接触**。 |

## C) 相对旧 146 边的变化（逐条：删/新/降）

**删除（corrections B 节假边 / 已解耦，本簇相关）**：
- **删 R50↔R25**（registry same_file via `sgs.py`）：R25=`ready_queue.py`、R50 改 `dispatch_rules.py` 不碰 sgs.py（仅用 sgs.py 论证死残渣）。回盘证实 R25 primary=ready_queue.py、R50 primary=dispatch_rules.py → **假碰撞，删边**。
- **删 R45↔{R33,R51}**（corrections B 节）：R45 primary=`config_adapter.py`（回盘证实），非 schedule_params.py；schedule_params.py 是 greedy 同目录他文件，零碰撞 → **删边**。R51/R33 与 R45 无干扰。
- **删 LB04↔R33**（corrections B 节）：不同 primary_file（boolean_normalize.py vs compat_parse.py 壳），core/algorithms 经 number_utils 引用为假 → **删边**。

**新增/澄清（dossier 回盘补强，非旧 registry 显式边）**：
- **新 R30↔R31（B13 facade）跨桶硬序边**：旧 registry 未把 R31 列入 R30 interference_edges，但 dossier 回盘三常量 re-export 爆炸链证实 R30 删常量必须与 R31/B13 facade 删除同窗口 → 补一条 facade 收口前置边。
- **新 R29↔{R04,R28} 同文件（number_utils.py）边澄清**：R04(edges 含 R29)/R28(edges 含 R29) 与 R29 同 number_utils.py same_file，但 R29 KEEP/owner-pending → 该边降为「若 R29 走 B 收敛才激活」的条件边。

**降级**：
- **降 R50 桶序耦合**：R50 在 B05、R49/R51 在 B06，旧叙事「三债同 Batch」。dossier 纠为**物理同文件须同一 diff**（R50 末尾删不回推上游），桶号差异不构成硬阻塞 → 由「跨桶硬序」降为「同 diff 原子」软编排。
- **降 R51→R49 顺序**：由「运行期依赖」降为「人工 review 心智序」（都是 P6/直删，无运行期先后，仅行号互撞需同 diff）。

（旁证：corrections B 节其余假边 R02↔R25 / R20↔{R08,R09,R12} / R32↔R15 / R26↔R43 / config_snapshot R26↔R71 / R13↔R18 解耦 / R05→R34 降级均不含本簇成员，不在本簇删除范围，仅记录于全局校正。）

## D) 承重前置（LB/N 承重点注释/parity 门控簇内结构动作）

- **本簇 6 债全部 load_bearing=false、lb_no_touch=null、lb_colocation_danger=none**（六 dossier 一致回盘）。**簇内无承重点需先落注释/parity 来门控删除动作**。
- 簇内 interference_edges 牵出的承重邻居 **LB04 / LB07** 均在本簇成员**不触碰**的文件（boolean_normalize.py / schedule_config_runtime_*.py / schedule_params.py）；R51/R33 仅只读 schedule_params.py 确认收口点在位，不写 → 不构成承重前置门控。
- **禁区行（非承重但属活契约/他债，删除禁外溢）**：
  - compat_parse.py:9-17 float/int/is_blank_input import + :129-195 float/int 函数体（R30 禁误删）；
  - value_policies.py:6-11 WRITE_* + :14-15 VALUE_FLOAT/INT + :22-178 FieldPolicy 类与 13 个 float/int 策略 + :211-227 推导 dict/查询函数（R30 禁误删）；
  - `core.shared.{compat_parse,field_parse,value_policies}` 全文（R33 禁碰，手滑删即炸生产直连方）+ config_contract :15 degradation（R33 死保）；
  - dispatch_rules.py:3 `import math`（R50 保留）、:39 起 DispatchInputs/:55 build_dispatch_key（R49/R51 禁碰）；
  - sgs_scoring.py:34 `_parse_due_date` + evaluation.py:26 `_parse_due_date_state`（R49 定点删红线，重名活函数）；
  - schedule_params.py:277/:346 + optimizer_config.py:166/:189 收口点（R51 只读）。
- **N1/N2/R03/R58 等执行重构新承重点**：均不在本簇文件内（N1=scheduler_resource_dispatch_execution_context.py、N2=operation_execution_event.py、R03=schedule_config_runtime_read.py、R58=scheduler_navigation_publish.py），**对本簇无门控**。

## E) fixed 成员残留动作

- 本簇 **6 债无一在 fixed 名单**（fixed = LB03/LB06/R07/R16/R56/R57，均不属本簇）。无「fixed 作为前置已完成、需补认账注释」的残留。
- 唯一须认账的非标准态是 **R29**（corrections E 节：误标 not_applicable → planned/owner-pending）：残留动作 = owner 裁 KEEP vs 薄壳化；若 KEEP 则补「有意保留半截 facade」显性注释 + 上交 open_question，本 Layer 不给终态。

## 返回摘要

簇 C-COMPAT-DISPATCH | 原子子簇:3+1孤立 — A1{R33,R30}同提交,A2{R49,R50,R51}同diff,A3{R49之evaluation/ortools 4行}可独立,A4 R29 owner-pending孤立只标 | 关键内部顺序:R33步1迁import→R30删shared实现→R33步2/3删壳+:411；A2按符号名/行号快照同diff删(R49清场→R51连退测试→R50删函数+import statistics) | 跨簇边:R30/R33→R31(facade收口前置/壳吞并),R33→R29(禁区死保degradation:15),R51→schedule_params/optimizer_config收口点(只读在位前置) | 边变化:删 R50↔R25(假sgs碰撞)/R45↔{R33,R51}(R45=config_adapter非schedule_params)/LB04↔R33；新 R30↔R31(B13 facade三常量re-export硬序)/R29↔{R04,R28}条件边；降 R50跨桶→同diff软编排、R51→R49运行期序→心智序 | 承重前置:无(6债全lb=false,LB04/LB07在不触碰文件,N1/N2/R03/R58不在簇内);禁区=core.shared三模块/degradation:15/import math:3/sgs_scoring:34同名活函数

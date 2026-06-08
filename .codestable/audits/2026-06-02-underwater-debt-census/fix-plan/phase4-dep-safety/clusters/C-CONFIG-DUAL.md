# C-CONFIG-DUAL 簇拆分 — config 双栈 (model↔service) 收敛 + adapter/shim/常量死叶子

> 成员: LB07, R47, R71, R45, R48, R26, R31 | 只读不改, 只产计划 | 回盘日 2026-06-05
> 主文件: schedule_config_runtime_coercion.py / _read.py / _snapshot.py / config_snapshot.py / config_adapter.py / config_service.py / value_policies.py

## A. 原子子簇

本簇 7 成员拆为 **4 个原子子簇**（其中 1 个是承重前置门、2 个独立死叶子、1 个晚序 facade）。判据: 同物理文件改一处顶掉另一处行号 / 收口前置 / 承重前置。

### 原子子簇 ASC-1 — config 双栈 helper 锁步收敛 【LB07 → R71 + R47 同批】
- **成员**: LB07(承重根/load_bearing=true/owner_pending), R71(三 helper 双栈/owner_pending), R47(死参 raw_value 双栈/终态可给)
- **原子原因**:
  - 三者全部落在同一组承重文件 `core/models/schedule_config_runtime_coercion.py` + `_read.py` + `core/services/scheduler/config/config_field_coercion.py` + `config_snapshot.py`，改任一函数体都会位移彼此锚行。
  - R71 收敛(service 反向复用 model 删 service 副本)与 R47 删死参是**同两栈文件的对称删动作**，若分两次提交，先动的一侧会令另一侧 file:line 全失效 → 必须同批由同一只手统筹。
  - LB07 是 R71/R47 的**承重安全网前置**: helper 级 parity 契约不落地就动收敛 → 锁步守卫缺位 → 静默漂移 → LB07 承重失效(Phase1 边 LB07→R71、LB07→R47)。
- **内部顺序(硬先后)**:
  1. **LB07 先**: 两栈 @dataclass 上方补「我是故意的/分层被迫双栈/加字段须两栈同改」中文注释(落点 model snapshot.py:7 / service config_snapshot.py:24) + 扩 `regression_scheduler_config_spec_sync_contract.py` 覆盖三 helper 逐分支 parity(真值表见 LB07 字段7 / R71 §7)。**纯增量零结构**，Batch-1 全局 ROOT。
  2. **R47 + R71 同批(parity 绿之后)**: 批内**先删两栈死参(R47)** → 签名更接近后**再收敛双栈(R71)**，parity 比对更干净。
  - ⚠️ 行号方向回盘(纠 R71 §5 笔误，已被 R71 对抗核验确认): R47 的 `_record_blank_choice_degradation` 在两栈中均**位于三 helper 之下**(model :83 vs helper :31/:49; service :63 vs helper :29/:45)。删 R47 死参只推移其**下方**符号，**不动三 helper 定义行**。但仍须同批统一回盘(R47 实参 :159/:214 与 helper 调用点混居函数体)。
- **owner 裁断门(阻塞终态非阻塞分析)**: LB07/R71 owner_pending=true，owner 须先裁「永久双栈仅 parity 锁步」vs「R71 物理收敛到 model」。**LB07 注释+扩 parity + R47 直删终态修法在任一裁断下都成立可先行**; R71 物理收敛动作待裁。

### 原子子簇 ASC-2 — config_adapter 整文件删 【R45 ≡ R48 已 fixed】
- **成员**: R45(死壳视角), R48(整模块迁移残渣视角) — 同一物理文件 `core/algorithms/greedy/config_adapter.py`(历史回盘 27 行) 的**两个叙述视角，同 same_symbol=read_critical_schedule_config**。
- **2026-06-08 执行终态**: `core/algorithms/greedy/config_adapter.py` 已删除；`CriticalConfigReadResult` / `read_schedule_config_value` / `read_critical_schedule_config` / `config_adapter` 在 `core/ web/ data/ tests/ tools/` 当前零命中。
- **旧 sp06 退行口径**: `tests/regression_sp06_no_duplicate_defs.py` 已由 A P1.1 整删，`NO_CFG_GET_TARGETS` 全树零命中；历史清单同步步骤为 **no-op**，不得为补这一步恢复旧测试文件。
- **原子原因**: 非两次动作，是**一次整文件删除**。现在已完成，后续不再重复投工。
- **独立性**: 零 LB 耦合、生产零引用、owner_pending=false；与 ASC-1 双栈收敛**正交**。`core/algorithms/greedy/schedule_params.py` 是活文件，仍禁碰。

### 原子子簇 ASC-3 — WRITE_INTERNAL_ONLY 源定义删 【R31 独立，跨簇绑 R33】
- **成员**: R31(死常量源定义 `core/shared/value_policies.py:9`) — 簇内**独立**，无本簇同文件兄弟(同文件兄弟 R33 在 C01 的 compat_parse.py 子簇，不在本簇)。
- **原子原因/顺序**: 见跨簇边 §B(R31→R33 删序硬约束)。owner_pending=false，终态=直删 :9。

### 原子子簇 ASC-4 — 顶层 config/summary 5 shim 删 【R26 晚序独立】
- **成员**: R26(5 个顶层 shim: config_service/config_snapshot/config_validator/schedule_summary/schedule_summary_types) — owner_pending=true。
- **原子原因**: 三步协调迁移(迁 2 离线消费者 + 重指 53 测试文件/~93 import + 改 SP05 BEHAVIOR_* 两字典 + 删 5 shim)须在**同一窗口**完成，但与本簇其余成员**无原子绑定**——它是 Batch-14 全局最晚、桶 B13。
- **独立性**: 与 R71 经"shim→深文件"转出边**软相关非原子**(R26 顶层 config_snapshot.py 是 5 行 shim，R71 改深 config/config_snapshot.py，不同物理文件不撞行号)。详见 §B/§C 假碰撞。

## B. 跨簇边 (本簇成员 → 其他簇债)

本簇 7 成员均归 C01 大簇下;以下"跨簇"指**指向本 C-CONFIG-DUAL 7 成员之外**的 C01 同桶债的真实依赖。

| 源(本簇) | 目标(他簇债) | 关系类型 | 顺序 | 说明 |
|---|---|---|---|---|
| **R31** | **R33**(compat_parse.py 子簇, B06/Batch-7) | **收口前置/同删序** | **R33 不晚于 R31** | R33 整文件删 `core/services/common/value_policies.py`(吸收 R31 关注的 :11 import + :29 __all__ 两行)并迁测试 `regression_value_policies_matrix_contract.py:18` import 回承重点 `core.shared.value_policies`。若 R31 抢先删 shared 源 :9 → facade :11 残留 `import WRITE_INTERNAL_ONLY` **loud ImportError**(CI 拦截非静默)。回盘确认三处行号 :9/:11/:29 零漂移。 |
| **R26** | **R29**(number_utils, B05) / **R33**(B06) / **R52**(B09) | **承重/收口前置** | **三桶先收敛, R26 后** | PHASE0 §10.2 facade 删除晚于收敛: 若 B05/B06/B09 测试仍经 R26 顶层 config/summary 老路径走, 先删 shim 会让其测试红。R26 排 Batch-14 全局最晚硬约束来源。 |
| **R26** | **R71**(本簇) | 软相关(转出边, 非原子) | R71 先, R26 后 | R26 顶层 config_snapshot.py:3 转出的正是 R71 编辑的深 config/config_snapshot.py; 让 R71 parity 收口落地后 R26 再搬入口, 天然满足(R71 在 B03 早桶, R26 Batch-14)。**不撞行号**(不同文件不同层)。 |
| **R26** | **R01**(schedule_payload_contract.py) / **R43**(web/routes route wrapper) | 同文件串行(仅 SP05 测试文件相邻) | 串行编辑各改各段 | R01 改 SP05:54-55、R43 改 SP05 ROUTE_* 段、R26 改 SP05 SERVICE_BEHAVIOR_* 段(:20-82)+ 文档树(:640-658)。同一 `test_sp05_path_topology_contract.py` 串行编辑避免 git 行号漂移误合; 无逻辑依赖。 |
| **LB07/R71/R47** | LB04(boolean_normalize.py) / R29(weights.py) / R33(compat_parse.py) | 同文件干扰(非原子) | 整组 [LB07,R47,R71] co_change 后统一回盘, LB04/R33 排不同批 | LB04/R33 若改 coercion.py 上半部会推移 helper :31/:49 行号; 原则同 R47——本簇三栈改后统一回盘。LB04 在 boolean_normalize.py(非本簇文件)、R29 在 weights.py，均经调用链关联标 same_file 干扰边，非真同符号碰撞。 |
| **R45/R48** | LB07/R33/R51(schedule_params.py) | **假边(见 §C)** | 无 | registry 误标 same_file; 真实 `core/algorithms/greedy/schedule_params.py` 非 R45 的 config_adapter.py。零碰撞。 |

## C. 相对旧 146 边的变化 (删/新/降)

### 删除 (假边 / 误标 same_file, corrections B 节坐实)
- **删 R45↔{LB07, R33, R51}** (3 条假边): registry interference_edges 把 `schedule_params.py` 标为与 R45 same_file，实为 `core/algorithms/greedy/schedule_params.py`(R45 同目录他文件)，R45 主文件是 config_adapter.py，**不同文件零碰撞**。R45 删壳完全不触碰 schedule_params.py。`fix_invalidation_risk=none`。
- **删 R48↔{LB07, R33, R51}** (3 条假边): 同上，R48≡R45 同物理文件，registry 同样误标。
- **删 R26↔R43**: R43 的 `scheduler_config.py` = `web/routes/scheduler_config.py`(route wrapper)，与 R26 的 `core/services/scheduler/config/*` 纯 basename 假碰撞，回盘 `core/services/scheduler/config/scheduler_config.py` 不存在。唯一真相邻仅 SP05 测试文件(降为同文件串行，见 §B)。
- **删 R26↔R71 的 config_snapshot.py 假碰撞**: R26=顶层 shim `core/services/scheduler/config_snapshot.py`(5 行/199B)，R71=深 `core/services/scheduler/config/config_snapshot.py`(17655B)，不同物理文件 → **不串行化为原子**(降为转出边软相关，见 §B)。`ls` 双文件体积已证。

### 新增 (回盘补出的真实边)
- **新 R26→{R29(B05), R33(B06), R52(B09)}** 三条硬前置(承重/收口前置): PHASE0 §10.2 "facade 删除晚于收敛"。普查曾断言 R26 "0 生产消费者"被对抗核验**推翻**——存在 2 个离线非测试消费者(tools/capture_networkx_phase0_baseline.py:17 + audit/2026-03/20260316_schedule_audit_probes.py:87)，verdict=depends。R26 须晚于三桶收敛，否则其测试经老路径变红。
- **新 R31→R33 删序硬约束边**(收口前置): R33 删 facade 须不晚于 R31 删 shared 源, 否则 facade :11 残留 import loud ImportError。

### 降级
- **R45↔R48 降为"同删非依赖"**: 不是"谁先谁后"边，是**同一次整文件删除**(合并单提交)。视作原子合并(ASC-2)，从依赖边降为合并标记。
- **R26↔R71 降为软相关**(转出边、非原子串行): 见上假碰撞条; R71 先 R26 后是排期天然序，非硬阻塞。
- **LB07→R47/R71 维持承重前置硬边**(未变): parity 先于收敛, 唯一不降。

### 本簇新增 R45/R48 fixed 补登
- corrections E 节原 fixed 名单 (LB03/LB06/R07/R16/R56/R57) **均不在本簇 7 成员内**，这个判断仍保留。
- 2026-06-08 B 执行终态补登新增 **R45/R48 fixed**：`config_adapter.py` 已删除，旧 sp06 退行因测试文件已由 A P1.1 删除变为 no-op。
- 本簇其余成员仍按原计划归属处理，尤其 LB07/R71/R47 的承重/双栈收敛没有因为 R45/R48 fixed 而自动完成。

## D. 承重前置

本簇唯一承重点 = **LB07**(load_bearing=true; 同文件毗邻承重 LB04 在 boolean_normalize.py, 不在本簇文件)。LB07 的承重注释 + helper 级 parity 必须**先落**, 门控本簇 ASC-1 内所有结构动作(R71 物理收敛、R47 双栈删参)。

### 必须先落 (Batch-1 全局 ROOT, 纯增量零结构)
1. **两栈 @dataclass 上方补「我是故意的」中文注释**: model `schedule_config_runtime_snapshot.py:7` + service `config/config_snapshot.py:24`(对侧路径互填, 钉"分层被迫双栈/加字段须两栈同改/收敛前先补 parity")。
2. **扩 parity 契约**: `regression_scheduler_config_spec_sync_contract.py` 从仅比 spec 字段扩到覆盖三 helper(`ensure_schedule_config_snapshot`/`normalize_weight_triplet`/`coerce_runtime_config_field` + R71 的 `_float_matches_choice`/`_normalize_valid_texts`/`_coerce_degradation_event`)逐分支等价(含 strict/非strict × 缺/坏/越界, 断言 返回值+是否raise+ValidationError.field+degradation计数 四者全等)。这是 R71 物理收敛的准入门。

### 禁区行 (绝不删/统一/透传/改逻辑, 仅补注释; 回盘真实行号)
- **置零承重**: model `coercion.py:470` `graph_downstream_weight = 0 if critical==0 and impact==0 else ...`; service 对侧 helper `config_snapshot.py:89` `_graph_downstream_weight_for_visible_weights`(调用点 :295/:450)。
- **灵魂线 loud raise (禁改兜底)**: model coercion.py `:72`(MISSING_POLICY_ERROR raise) / `:153` / `:165` / `:208` / `:220` / `:258` / `:302`; service 对称 `config_field_coercion.py:156/:205`。⚠️ registry lb_no_touch 写"coercion:73-80"实测 :71-72，**禁区按符号语义认定(MISSING_POLICY_ERROR raise 块)不按行号**; R47/R71 改 coercion 后须重新回盘。
- **30 字段锁步表本体**: model :8-39 / service :25-56 逐字段, 只补注释。
- **read.py 承重读取入口**: `read_runtime_cfg_raw_value:10` + `runtime_cfg_read_error:33`(loud `raise...from exc`), R71 收敛三 helper 不得越界到此。
- 灵魂线: 非 strict 路 `MISSING_POLICY_FALLBACK_WITH_DEGRADATION`(coercion:434/:70) 带 DegradationCollector 是**已设计可观测降级**, 补注释不当 bug 删; 三 helper 现有 `except Exception: continue`/`count=1` 是**已存在行为**, parity 必须逐字保真, 不得"顺手"改 loud raise。

### 门控关系
- LB07 注释+parity **门控** → R71 物理收敛(删 service 副本)、R47 双栈删参。Phase1 边 LB07→R71、LB07→R47 硬不降。
- ASC-2(R45/R48)、ASC-3(R31)、ASC-4(R26) **非承重, 无禁区行, 不受 LB07 门控**(R45/R48 删壳不进 schedule_params.py; R26/R31 纯删 shim/常量)。

## E. fixed 成员残留动作

**本簇 7 成员中 R45/R48 已 fixed，其余成员仍按原计划处理。** corrections E 节旧 fixed 名单(LB03/LB06/R07/R16/R56/R57)均在本簇之外；2026-06-08 另补登 G16/ASC-2:
- LB07/R71: 承重注释+helper parity 两件计划工作均未落, 6 处 def 仍逐字双栈, parity 守卫缺口实证在场。
- R47: 两栈对称死参未删、4 调用点未改。
- R45/R48: **已 fixed**。`core/algorithms/greedy/config_adapter.py` 已删除；旧 `tests/regression_sp06_no_duplicate_defs.py` 已由 A P1.1 删除，旧清单同步 no-op；生产/测试/工具当前零引用。
- R26: 5 shim 全在纯转出、2 离线消费者仍老路径、SP05 仍冻结。
- R31: 三处 :9/:11/:29 原样。

**作为前置已完成的他簇 fixed 残留动作 (本簇依赖侧)**: 无——本簇无任何边指向 fixed 成员。R26 的硬前置 R29/R33/R52 与软前置 R71 均为 `planned`(非 fixed), 须在其收敛后 R26 方可动, 属正常 DAG 前置非 fixed 认账。

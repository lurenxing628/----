# 逐簇爆炸对抗 r1 · C-CONFIG-DUAL · 主透镜 SOUL（灵魂线热路径+收口等价）

> skeptic 第1轮 / 只读不改 / 默认怀疑 / 回盘日 2026-06-05
> 输入：cluster C-CONFIG-DUAL + 7 dossier(LB07/R47/R71/R45/R48/R26/R31) + _layer2_residual + _layer1_corrections + 当前代码 rg 回盘
> 行号一律以本轮 rg 回盘为准，旧值不信。

---

## 0. 本轮回盘锚点（自查，不信旧值）

- LB07 双栈 @dataclass：model `schedule_config_runtime_snapshot.py:8` / service `config/config_snapshot.py:25`。**零漂移**。
- R71 三 helper def：`_float_matches_choice` model coercion:31 / service field_coercion:45；`_normalize_valid_texts` model:49 / service:29；`_coerce_degradation_event` model read:68 / service config_snapshot:153。**6 处零漂移**，且逐字节比对三对函数体**确为 byte-for-byte 相同**（已 sed dump 比对，证 dossier「byte 等价」成立）。
- 承重 loud raise（model coercion）：`:72`(MISSING_POLICY_ERROR) `:153/:208`(strict 空值) `:165/:220/:258/:302`(填写不正确) `:385`(TypeError 类型)。置零 `:470`。read.py loud：`:10/:33` 入口 + `:22/:24/:49/:51/:63/:65` raise...from exc。**全部命中**。
- R47 死参 `_record_blank_choice_degradation`：model def:83(形参:88) 调用:155(实参:159)/:210(实参:214)；service def:63(形参:68) 调用:158(内联)/:207(实参:211)。
- R45/R48 `config_adapter.py`=**27 行**，全仓引用仅自身 + `sp06:15`(路径成员，非符号)。
- R31 `WRITE_INTERNAL_ONLY`：源 `core/shared/value_policies.py:9`、facade import `common/value_policies.py:11`、__all__ `:29`。**3 行零漂移**。
- R26 5 shim：`config_service/snapshot/validator.py` 各 5 行；在 SP05 `SERVICE_BEHAVIOR_COMPAT_SYMBOLS(:20-31)`+`PUBLIC_SYMBOLS(:33-82)`，**非 STRONG**（dossier 纠偏成立）。离线消费者 2 个复现（tools:17 / audit:87）。

---

## 1. 逐成员判定

### LB07 — 🟡 黄（承重，注释+扩parity 可先行；但 parity 范围有致命漏项，见 §2）
- 候选修法（补「我是故意的」注释 + 扩 helper parity）本身零结构、零 import、0 AST 违规，承重禁区只补注释——**这部分安全**。
- 但「扩 parity 覆盖三 helper + spec 字段」的范围**不足以守住承重失效的真正入口**（§2 漏项 A）。在 parity 范围补全前标黄，不标绿。

### R71 — 🟡 黄（owner 裁断门 + LB07 前置；物理收敛方向合法但等价面被夸大）
- 三 helper byte 等价属实，`core.services→core.models` 下行边合法、不成环（已证 service 侧大量已 import core.models）。收口到已存在 model 三符号，不新建模块。
- 黄因：① owner_pending（物理收敛待裁）未解；② LB07 helper-parity 必须先绿；③ dossier/对抗核验断言「两栈 helper 逐字等价、parity 守住即可收敛」掩盖了 `_handle_missing_value` 的**真实不对称**（§2 漏项 A）——若 R71 收敛只盯 3 helper，邻近 `_handle_missing_value` 分叉无人守。

### R47 — 🟡 黄（终态直删成立，但 co-change 邻接行有静默误删陷阱，见 §2 漏项 B）
- 死参断言成立：`_record_blank_choice_degradation` 形参 raw_value 两栈均从不读，删它运行期零行为变化；现成 2 条 degradation regression（真名后缀 `_emit_blank_required`，非 dossier 误写的 `_emit_ln`）守门。
- 黄因：dossier「6 编辑点」框定 under-warn 了邻接陷阱——model :159 与 :173、:214 与 :225 仅隔约 14 行，**字面同为 `raw_value=raw_value,`**，:173/:225 属 LIVE 的 `_record_invalid_choice_degradation`（其 message 真用 raw_value）。任何按行/按字面 grep 删而不绑定外层函数名 → 误删 :173/:225 → invalid-choice 降级丢失被拒值、kwarg 仍被活函数接受 → **不 loud、静默降级质量回归**。须绑函数名删，不可按 `raw_value=raw_value` 字面删。

### R45 ≡ R48 — 🟢 绿（同文件整删合并单提交，最低风险一刀）
- 27 行死壳，生产零引用、零动态 import；唯一约束=同提交退 `sp06:15` 路径，漏退则 `path.read_text` FileNotFoundError **loud 红**（非静默）。新路径 `schedule_params.py:59 _snapshot_attr` 已 loud-raise 形态。删壳不碰 `schedule_params.py`(LB07/R33/R51 居所)。正交于双栈收敛。**安全直删。**

### R31 — 🟢 绿（死常量直删，唯一陷阱=删序，且 loud 兜底）
- `WRITE_INTERNAL_ONLY` 三处、零生产/零测试消费（16 FieldPolicy 无一赋、compat_parse 只比 WRITE_OPTIONAL）。唯一排序陷阱：R31 先删源 `:9` → facade `:11` 残留 import **loud ImportError**（CI 拦截，非静默）。R33 删 facade 不晚于 R31 删源即安全。禁区：不得顺手动 `:6/:7/:8`(活常量)。**安全，按序即可。**

### R26 — 🟡 黄（晚序 facade，硬前置 B05/B06/B09；SP05 字典精度陷阱被 under-spec，见 §2 漏项 C）
- 纯转出 shim，误删只 loud ImportError。硬前置 R29(B05)/R33(B06)/R52(B09) 收敛 + R71 软前置；2 离线消费者须先迁（否则 loud ImportError）；owner_pending 待裁解冻。
- 黄因：见漏项 C——SP05 两字典各含 10 键，R26 只许删其中 5 键，删错/删多会静默解冻无关 compat 面（含 R01 的 schedule_persistence 符号）。

---

## 2. 漏项（本轮新发现，计划/dossier 未覆盖的爆点）

### 漏项 A【高·主透镜命中】LB07/R71 parity 范围漏掉 `_handle_missing_value` 真实不对称——两栈非 byte 等价
- **dossier/对抗核验断言**：R71 三 helper「byte-for-byte 相同」、LB07 parity 扩到「三 helper + spec」即可守住承重。
- **回盘反证**：紧邻同一 missing-policy 热路径的 `_handle_missing_value` **两栈不等价**：
  - service `config_field_coercion.py:115` 多一条分支 `if policy == MISSING_POLICY_INHERIT_LEGACY_OMISSION: return True, fallback`（import 于 :14），且返回 `Tuple[bool, Any]`。
  - model `coercion.py` 同函数**无此分支**、返回裸 `Any`。
  - model 全文件 grep `MISSING_POLICY_INHERIT_LEGACY_OMISSION` = **零命中**：model 栈根本不认识 legacy-omission 策略。
- **灾难链**：LB07 注释钉「加/改字段须两栈同改」，但 parity 守卫范围（3 helper + spec 字段）**不覆盖 `_handle_missing_value`**。一旦 owner 走 R71 物理收敛、或将来有人「DRY 统一」`_handle_missing_value`：
  - 若收敛到 model 版（无 INHERIT_LEGACY 分支）→ service 侧 legacy-omission 配置静默丢失「按 fallback 继承」语义、改走 missing_required 降级或 raise → 配置页/快照口径变；
  - 若强行把 model 对齐 service 但漏改返回签名（model `Any` vs service `Tuple[bool,Any]`）→ 调用点解包错位 → 静默坏值流入 snapshot；
  - parity 测试**绿**（它只比 3 helper），护栏已破——典型「测试绿但护栏破」静默失效。
- **修正建议（前置/禁区）**：LB07 扩 parity **必须把 `_handle_missing_value` 纳入逐分支真值表**（含 ERROR/FALLBACK/INHERIT_LEGACY × 两栈返回签名差异），并在两栈该函数上方各补「我是故意的：service 多 INHERIT_LEGACY 分支 + Tuple 返回是有意，model 栈不提供 legacy 继承；收敛前先在 parity 钉死此差异」注释。**禁**在收敛/统一时把 service 的 INHERIT_LEGACY 分支并掉或把 model 返回签名强对齐而不补 parity。此漏项把 LB07 从「黄·可先行」的注释面**扩大了承重禁区认定面**。

### 漏项 B【中·主透镜命中】R47 邻接 `raw_value=raw_value,` 字面同形误删陷阱
- 计划「6 编辑点」未点名：model :159(死,blank)↔:173(活,invalid)、:214(死,blank)↔:225(活,invalid) 字面完全相同且近邻；service :158/:170、:211/:222 同形。
- **灾难链**：按字面 `raw_value=raw_value` 批量删 → 命中 :173/:225（`_record_invalid_choice_degradation` 活调用，其 message 真引用 raw_value）→ kwarg 仍被活函数签名接受 → **不报错**、invalid-choice 降级丢失被拒原值 → 静默降级质量回归。
- **修正建议**：R47 删除**必须绑外层函数调用名 `_record_blank_choice_degradation` 的实参块**，逐块核对，禁按 `raw_value=raw_value` 字面或行号删；删后跑 `_emit_blank_required` 两条 + invalid-choice 降级回归确认 message 仍含拒值。

### 漏项 C【中】R26 SP05 两字典各 10 键，只许删 R26 的 5 键——删错=静默解冻无关 compat 面（含 R01 符号）
- 回盘 `SERVICE_BEHAVIOR_COMPAT_SYMBOLS(:20-31)` 与 `PUBLIC_SYMBOLS(:33-82)` 各含 **10 键**：R26 的 5（config_service/snapshot/validator/schedule_summary/schedule_summary_types）+ 非 R26 的 5（freeze_window/schedule_input_builder/schedule_input_collector/schedule_orchestrator/**schedule_persistence**）。
- **灾难链**：dossier 说「删 5 条键」未强调字典含 10 键且 R01 的 `count_actionable_schedule_rows/has_actionable_schedule_rows` 正落在 `schedule_persistence` 公开符号项里。R26 与 R01 同改 SP05、dossier 称「各改各段」——实则**同改这两个字典**，非纯相邻行段。删多/删错键 → 静默解冻 schedule_persistence 等无关 compat 面，且与 R01 SP05 编辑直接撞同字典。
- **修正建议**：R26 改 SP05 须**按 old→new key 精确点名删 5 键**（禁整字典删），并与 R01 串行编辑时声明改的是同两字典的不同 key（非不同行段），先 R01 后 R26 或反序均可但须各自只动自己的 key、改后 diff 两字典键集核对。

### 漏项 D【低·已被计划隐含但本轮坐实】R71/R47 co-change 后承重锚行回盘纪律
- R47 删参/ R71 收敛动 coercion.py 函数体后，承重禁区行（:153/:208/:470/:72 等）行号必移。计划已说「整组改后统一回盘」，本轮确认禁区须**按符号语义(MISSING_POLICY_ERROR raise 块 / graph_downstream_weight=0)认定，不按行号**——重申，非新爆点。

---

## 3. 六质问点速答（本簇）
- Q1 承重误删：LB07/R71/R47 修法均守「只补注释/直删死物，不删置零/不删 loud raise」——本体无误删；**但 §2-A 暴露 parity 范围漏 `_handle_missing_value`，承重禁区认定面须扩**。
- Q2 分层导入环：候选修法零新增 import（LB07 注释、R45/R48/R31 纯删），R71 收敛 `core.services→core.models` 合法、不成环。**0 违规未被击穿。**
- Q3 迁移耦合：本簇与 v18/v19 DB CHECK / adopted-only 无耦合（config 双栈不碰 plan_role/source_table）。无启动探针炸点。
- Q4 灵魂线热路径：本簇无 P4-raise 改造需求；非 strict 的 FALLBACK_WITH_DEGRADATION + DegradationCollector 是已设计可观测降级，禁当 bug 删。**但 §2-A 的 INHERIT_LEGACY 静默继承分支是真实可用性/口径放大点**，须 parity 钉死。
- Q5 收口等价：R71 三 helper 逐分支等价成立；**`_handle_missing_value` 两栈不等价（§2-A），收口前必须逐分支补 parity**。R45/R48/R31/R26 非收口、无等价问题。
- Q6 测试迁序：R45/R48 同提交退 sp06:15（漏退 loud 红）；R31 R33 删 facade 不晚于删源（反序 loud ImportError）；R26 SP05 契约最先改 + 53 文件/~93 import 重指 + 2 离线脚本先迁（基数用 93 非旧 71）。R47 删前取 `_emit_blank_required` 绿基线。**序错均 loud（红/ImportError），无复活兜底；唯 §2-B/§2-C 是静默误删/误解冻陷阱。**

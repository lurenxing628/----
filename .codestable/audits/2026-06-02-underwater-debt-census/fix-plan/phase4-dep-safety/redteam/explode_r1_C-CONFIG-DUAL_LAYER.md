# 逐簇爆炸对抗 r1 · C-CONFIG-DUAL · 主透镜【分层导入环+迁移耦合】

> skeptic 第1轮，只读不改，默认怀疑。回盘日 2026-06-05，cwd=/Users/lurenxing/Documents/GitHub/----。
> 成员：LB07 / R47 / R71 / R45 / R48 / R26 / R31。所有 file:line 经本轮独立 rg/sed 回盘，不信旧值。

---

## 主透镜结论先行（Q2 分层导入环 / Q3 迁移耦合）

- **Q2（分层导入环）= 0 违规，绿。** 实测 `rg "from core.services|import core.services" core/models/schedule_config_runtime_*.py` → **exit=1 零命中**：model 栈对 service 零依赖。R71 候选收敛方向 = service 反向 import model 三 helper，即 `core.services.scheduler.config.* → core.models.schedule_config_runtime_*`，是**已存在的合法下行边**（`config_page_outcome.py` / `config_field_spec.py` 已 `from core.models` import）。model 栈不回头 import service → **不成环**。LB07/R47/R45/R48/R26/R31 候选修法均零新增 import 或只减边。本簇主透镜「分层导入环」**整簇无爆点**。
- **Q3（迁移耦合）= N/A，绿。** v18/v19 的 DB CHECK 全部钉在 `OperationExecutionEvents`（`effective_plan_role='adopted'` / `source_table='schedule'`，v19:14-30），**与 schedule_config 双栈零交集**。本簇不碰执行事件 schema，改码不触发任何启动探针。Q3 对 C-CONFIG-DUAL 不适用。

**主透镜判定：本簇在「分层导入环+迁移耦合」两条主轴上全绿。** 真正的爆点不在主透镜，而在**承重护栏的静默失效**（Q1/Q4/Q5/Q6），见下。

---

## 逐成员判定

### 🔴 LB07 — 承重根，parity 守卫缺口实证在场（会炸：静默分叉污染排产）
**判定 🔴红**（非「修法会炸」，而是「**当前护栏已破，后续任何收敛动作都会在无守卫下静默漂移**」——正是任务要抓的「测试绿但护栏已破」）。

**证据（本轮回盘）**：
- 两栈 @dataclass：model `schedule_config_runtime_snapshot.py:7-8` / service `config/config_snapshot.py:24-25`，逐字段 parity 当前成立。
- **parity 守卫缺口实锤**：`rg "_float_matches_choice|_normalize_valid_texts|_coerce_degradation_event" tests/config/test_scheduler_config_spec_sync_contract.py` → **exit=1 零命中**。即：删/改任一 helper 函数体**不会让任何测试变红**。三 helper（决定 choices 匹配 / 空白归一 / 降级判定口径）当前是「碰巧等价」而非「被守卫等价」。
- 两栈无任何「我是故意的/双栈/parity」注释（与 evidence 一致）。

**完整灾难链**：LB07 注释+helper-parity 不先落 → 后续 LLM（或 R71 收敛半途）单边改一个 helper（如把 `_float_matches_choice` 空 choices 的 `return True` 误改，或 `_coerce_degradation_event` 的 `count=max(1,...)` 下限改掉）→ **无任何测试拦截** → model 栈（喂算法/排产）与 service 栈（喂配置页）对同一字段的合法值/降级口径**静默分叉** → 算法用一套口径排产、配置页存另一套 → 排产正确性被污染**且无 loud 信号**（踩灵魂暗线）。

**修正建议（前置/禁区）**：
- **前置硬门（Batch-1 ROOT，纯增量零结构）**：① 两栈 @dataclass 上方补「我是故意的」中文注释（model snapshot.py:7 / service config_snapshot.py:24，对侧路径互填）；② 扩 `regression_scheduler_config_spec_sync_contract.py` 覆盖三 helper 逐分支等价（strict/非strict × 缺/坏/越界，断言 返回值+是否raise+ValidationError.field+degradation计数 四者全等）。**这是 R71/R47 物理收敛的唯一准入门，硬不降。**
- **禁区行（只补注释，绝不删/统一/透传）**：置零承重 `coercion.py:470`（回盘确认逐字：`graph_downstream_weight=0 if critical==0 and impact==0 else int(ScheduleConfigSnapshot.graph_downstream_weight)`）+ service 对侧 helper `config_snapshot.py:89`；loud raise 族 `coercion.py:72/:153/:165/:208/:220/:258/:302`（**registry lb_no_touch 写「:73-80」实测 :71-72，禁区按 MISSING_POLICY_ERROR raise 符号语义认定，不按行号**）；30 字段锁步表 model :8-39 / service :25-56。
- **owner_pending=true**：永久双栈 vs R71 物理收敛待裁；但 LB07 注释+扩 parity 在任一裁断下都成立，**可先行**。

---

### 🔴 R47 — 删死参 raw_value：紧邻 LB07 loud raise + 活兄弟函数同名参数（会炸：误删活参/误删 raise）
**判定 🔴红**（修法本体 trivial，但**编辑现场的静默误删风险高**，多维度存疑 → 按默认怀疑标红，须前置守卫+逐行核）。

**证据（本轮回盘，这是本簇最被低估的爆点）**：
- 死参 `_record_blank_choice_degradation` def @ model `coercion.py:83`，死形参 `raw_value: Any,` @ `:88`（函数体 :91-98 只读 field_name/fallback/scope，**从不读 raw_value**，:97 `sample=None`）。死实参在 `:159`（_choice 内 blank 分支）+ `:214`（_yes_no 内 blank 分支）。service 对称：def `:63` / 形参 `:68` / 实参 `:158`（单行内联）+ `:211`。
- **危险点 1（活兄弟同名参数）**：紧邻的 `_record_invalid_choice_degradation`（model :101，形参 `raw_value: Any,` @ **:106**）是**活函数**——:116 message 插 `{raw_value}`、:119 `sample=str(raw_value or "")`。若执行者用 `replace_all "raw_value=raw_value"` 或按参数名 grep-删，会**误删 :173/:225（model）、:170/:222（service）这些传给 invalid_choice 的活实参** → invalid_choice 降级消息丢实际值 → 静默退化（TypeError 才会 loud，丢值不 loud）。
- **危险点 2（紧邻 loud raise）**：R47 的 6 个编辑点全在 `if text==""`（非strict 降级）分支，但与 `if strict_mode and text==""` 的 loud raise（model :153/:208，service :156/:217）**物理仅隔 1-3 行**。逐行核不严会误伤 raise → strict 校验从 raise 退化成兜底 → 坏配置静默放行（踩灵魂线）。
- **危险点 3（灵魂线）**：`collector.add(code="blank_required")`（:92-98）是**已设计可观测降级**，非死代码；删死参时绝不能连这条 add 一起删。

**完整灾难链**：粗暴按 `raw_value` 名删 → 误删 invalid_choice 活实参（:173/:225）→ 排产/配置页的「填写不正确」降级消息丢失实际值 → 静默丢可观测性；或误删紧邻 :153/:208 raise → strict 空值校验失守 → 坏配置静默进排产。

**修正建议**：
- **前置**：LB07 注释+parity 先落（Batch-1）→ R47 与 R71 同批（parity 绿之后），批内**先删两栈死参（R47）再收敛（R71）**。
- **唯一允许动的 6 行（按符号定位，非按名 grep）**：model `coercion.py:88`(形参)/`:159`(实参)/`:214`(实参)；service `config_field_coercion.py:68`(形参)/`:158`(内联实参)/`:211`(实参)。**禁动** `_record_invalid_choice_degradation` 的任何 raw_value（model :106/:116/:119/:173/:225；service 对侧），**禁动** 紧邻 raise（:153/:208/:156/:217），**禁删** `collector.add(blank_required)`。
- **守卫测试**（dossier 笔误已纠）：基线跑真名 `test_..._emit_blank_required`（regression_config_validator_preset_degradation.py:210 / regression_schedule_config_snapshot_optional_guard.py:107），**非** dossier 误写的 `_emit_ln`（照旧名 `pytest -k` 匹配不到 → 误判无守门）。

---

### 🟡 R71 — 三 helper 物理收敛跨模块复用：分层绿但 owner 未裁 + parity 前置未落
**判定 🟡黄**（分层维度绿、收口点真实存在，但**有两个硬前置未满足**：LB07 parity 门 + owner 裁断；满足后可做）。

**证据**：6 处 def 零漂移（model coercion :31/:49、read :68；service field_coercion :45/:29、snapshot :153），三对 byte-for-byte 等价。收口方向 `core.services→core.models` 合法下行、不成环（Q2 已证）。收口点 = 已存在的 model 三符号，非新建第二模块（不踩 P5）。

**条件（黄→可做的前提，缺一即退红）**：
1. **LB07 helper-parity 必须先绿**（当前缺口实证在场，见 LB07 🔴）——否则收敛把双栈合一后，未来单边改无守卫，静默漂移。
2. **owner 须裁**「永久双栈仅 parity」vs「物理收敛」——owner_pending=true，收敛动作待裁，**本轮不得给终态**。
3. **收敛逐字保真灵魂线**：`_float_matches_choice` 空 choices→True、`except Exception: continue`；`_coerce_degradation_event` 非dict→None（**禁误改成 raise**，否则排产侧降级读取从「静默丢弃」变「崩」，static 方向反转）；`count=max(1,int(...or 1))` 下限钳 1。三者是**已存在行为，parity 须逐字保真，不得「顺手」改 loud raise**。
4. **与 R47 同批、同方向、改后统一回盘**（避免行号位移）。

**dossier 已纠笔误（不影响判定）**：R71 §5 称「删 R47 service 函数会令 `_float_matches_choice`(:45) 行号上移」方向有误——R47 的 `_record_blank_choice_degradation`(service :63) 位于三 helper(:29/:45)**之下**，删它只推移其下方，不动三 helper 行。本轮 r1 已确认（R71 对抗核验第 7 条已记此纠正）。

---

### 🟢 R45 / R48 — config_adapter 整文件删（ASC-2 单提交）
**判定 🟢绿**（同一物理文件两视角，零 LB 耦合、生产零引用、owner_pending=false，本簇最早最低风险一刀）。

**证据**：`config_adapter.py` 实测 27 行；`config_adapter` 全仓唯一外部引用 = `tests/regression_sp06_no_duplicate_defs.py:15`（NO_CFG_GET_TARGETS 路径成员，非符号 import）。删文件方向 `core.algorithms→core.models` 合法、只减边、零越层（Q2 绿）。`_snapshot_attr@greedy/schedule_params.py:59` 已是收敛后 loud-raise 形态，替代路径在场。
**唯一约束（历史 loud 非静默）**：旧 sp06 清单若仍指向已删文件，则 `path.read_text` 抛 FileNotFoundError → sp06 红（CI 立即可见）。2026-06-08 终态下 R45≡R48 已 fixed，旧 sp06 文件已由 A P1.1 删除，清单同步 no-op。
**与双栈收敛正交**：adapter 只 import FROM model snapshot，删它不动 LB07 本体，无须等 ASC-1。

---

### 🟡 R26 — 顶层 5 shim 删（B13 全局最晚 facade）：硬前置链长 + 重指基数易错漏
**判定 🟡黄**（low 严重度、误删只 loud ImportError，但**三步协调迁移须同窗口完成**且**前置链最重**，owner_pending=true 待裁；条件满足后可做）。

**证据**：5 shim 实测纯转出（config_service/snapshot/validator 各 5 行，schedule_summary 29 / types 25）。**非 0 生产消费者**——回盘坐实 2 个离线消费者（`tools/capture_networkx_phase0_baseline.py:17` + `audit/2026-03/20260316_schedule_audit_probes.py:87`，活引用），先删 shim → 它们 loud ImportError。测试侧 53 文件经顶层 shim 进（回盘 `rg -l` = **53**，与 registry 一致）。

**条件（黄→可做的前提）**：
- **硬前置（PHASE0 §10.2 facade 晚于收敛）**：R29(B05)/R33(B06)/R52(B09) 三桶**先收敛**，否则其测试经 R26 老路径变红。R26 排 Batch-14 全局最晚的硬约束来源。
- **软前置**：R71（本簇）先收口落地，R26 再搬入口（R26 顶层 config_snapshot.py:3 转出的正是 R71 编辑的深 config/config_snapshot.py；不同物理文件**不撞行号**，是转出边软相关，非原子）。
- **重指基数陷阱**：registry 旧值「71 处 import」**已漂**，dossier 回盘 ~93 处（本轮独立计 53 文件确认，import 行数 91-93 口径微差）。**以 71 为基数会漏 ~20 处悬空老路径**——须以 53 文件全量 grep 残留为准。
- **SP05 改 BEHAVIOR_* 两字典**（:20-31 + :33-82），**非** STRONG_*（registry phase1_blast 误标，回盘 STRONG 集 :15-18 只含 2 个 optimizer）；与 R01(:54-55)/R43(ROUTE_* 段) 串行编辑同一 SP05 文件避免行号漂移。
- **owner_pending=true**：SP05 冻结面解冻许可待裁。

---

### 🟢 R31 — WRITE_INTERNAL_ONLY 死常量源删（ASC-3，跨簇绑 R33）
**判定 🟢绿**（P6 死常量、零生产/零测试消费、owner_pending=false、直删 :9 终态可给；唯一陷阱是删序，且陷阱炸点 loud 非静默）。

**证据**：3 处实测 `core/shared/value_policies.py:9`(源) + `core/services/common/value_policies.py:11`(import) + `:29`(__all__)，零漂移。16 个 FieldPolicy 无一赋 WRITE_INTERNAL_ONLY，`compat_parse.py:165/188/208` 只比 `==WRITE_OPTIONAL`。common facade 实测 37 行（R33 整文件删它，吸收 :11/:29）。
**唯一排序硬约束（loud）**：R33（B06/Batch-7）删 common facade ≤ R31（B13/Batch-14）删 shared 源 :9；若 R31 抢先删 :9，facade :11 残留 `import WRITE_INTERNAL_ONLY` → **loud ImportError**（CI 拦截，非静默）。
**操作禁区**：只删 :9，**不得顺手动** :6/:7/:8（WRITE_REQUIRED/OPTIONAL/NOT_APPLICABLE，16 处在用 + compat_parse 在比，删则静默改解析语义）。

---

## 漏项 / 本轮新发现（计划未充分覆盖的爆点）

1. **【高】R47 误删半径被低估**：计划只警告「两栈对称同删」，但**未明确警告紧邻的活兄弟 `_record_invalid_choice_degradation`（model :106/:116/:119/:173/:225）同名 raw_value 参数**。按名 grep / replace_all 删会静默丢 invalid_choice 降级消息的实际值（TypeError 才 loud，丢值不 loud）。**须在 R47 执行卡补「按符号定位 `_record_blank_choice_degradation` 单函数，禁按 raw_value 名全删」红线**。
2. **【中】LB07 parity 门是整簇 ASC-1 的唯一真守卫，但当前实证缺口**：spec_sync 契约对三 helper **零引用**（本轮回盘 exit=1 实锤）。计划已列「扩 parity」，但须强调**这不是锦上添花，而是当前护栏已破的修复**——在 parity 绿之前，R71/R47 的任何函数体改动都处于「测试绿但护栏破」的静默失效区。
3. **【低-提醒】R26 重指基数**：计划/registry 仍有「71 处」残值流通，须统一钉死「以 53 文件全量 grep 残留为准，禁用 71 基数」，否则留悬空老路径（loud 但延迟暴露，离线脚本 CI 不跑）。
4. **【澄清】主透镜两轴本簇全绿**：分层导入环（Q2）与迁移 DB CHECK 耦合（Q3）对 C-CONFIG-DUAL **均无爆点**——真爆点全在承重护栏的静默失效（Q1 R47 误删 / Q4-Q5 R71 收敛逐字保真 / LB07 parity 缺口）。主透镜分配与本簇真实风险面**错配**，建议 Layer4 排批时按「承重护栏」轴而非「分层」轴排 C-CONFIG-DUAL。

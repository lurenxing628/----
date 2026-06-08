# 逐簇爆炸对抗 r3 · C-CONFIG-DUAL · 主透镜【分层导入环+迁移耦合】

> skeptic 第3轮 / 只读不改 / 默认怀疑。回盘日 2026-06-05，cwd=/Users/lurenxing/Documents/GitHub/----
> 成员: LB07 R71 R47 R45 R48 R26 R31
> 主透镜专攻 Q2(分层导入环)/Q3(迁移耦合)；六质问全过。
> **主透镜结论先行**: 本簇 Q2/Q3 **彻底为绿**——model 栈 + algorithms 栈对 core.services **零依赖**(rg 实证空)，R71 收敛方向 service→core.models 是已大量存在的合法下行边，0 导入环、0 越层；本簇无任何 v18/v19 DB CHECK / schema CHECK 耦合(配置双栈纯内存 dataclass，不碰迁移)。**真危险不在分层环，在 Q1 双栈静默分叉**(LB07)，且已被 LB07 parity 前置门设计性拦住、被 owner_pending 卡住终态。无「会静默炸」的真红债。

---

## 六质问点逐项裁决(本簇整体)

- **Q1 承重误删**: LB07 是真危爆点根，但计划修法是「仅补注释+扩 parity，零删除/统一/透传」，禁区行(置零 :470 / loud raise 族 / 30字段表)只补注释。R47 是死参直删(load_bearing=false)但落在 LB07 承重文件，须避开禁区。**计划守住承重，未误删** → 见各债判定。
- **Q2 分层导入环**: rg 实证 `core/models/schedule_config_runtime_*.py` 对 `core.services` **NONE**；`core/algorithms/greedy/schedule_params.py` 对 `core.services` **NONE**。R71 收敛 service→core.models 合法(config_page_outcome.py/config_field_spec.py 已 import core.models)，model 不回指 service 不成环。R45/R48 删 algorithms→models 叶子边只减边。R26/R31 同层子包下沉/删常量只减边。**0 违规，主透镜本簇全绿。**
- **Q3 迁移耦合**: 本簇 7 债**无一碰 DB 迁移/schema CHECK**。配置双栈是纯内存 dataclass 校正引擎，与 v18/v19 的 effective_plan_role/source_table CHECK 无任何耦合。「改码不改迁移=启动探针炸」在本簇不适用。**绿。**
- **Q4 灵魂线热路径**: 非 strict 路 `MISSING_POLICY_FALLBACK_WITH_DEGRADATION`(coercion:70/:434) 带 DegradationCollector 是**已设计可观测降级**；三 helper 现有 `except Exception: continue`/`count=1` 是**已存在行为**。计划反复钉死「parity 逐字保真、不得顺手改 loud raise」。无新增兜底/静默回退/吞错。**绿。**
- **Q5 收口行为等价**: R71 收敛点(model 三 helper)与被删 service 副本已 byte-for-byte 等价(本轮重比对确认)；parity 测试设计断言「返回值+是否raise+ValidationError.field+degradation计数」四者全等，覆盖 strict×缺/坏/越界。R47 是纯无副作用删参(函数体不读 raw_value，回盘 model:83-99 确认)。**等价可守，但见 R47 漏项**。
- **Q6 测试迁移序**: R26 删 shim 须晚于 R29(B05)/R33(B06)/R52(B09) 收敛 + R71 收口(否则测试经老路径红)；R31 删 shared 源须不晚于 R33 删 facade(否则 facade:11 残留 import loud ImportError)。**序错=loud 红(非静默)，但卡批次**。

---

## 逐债判定

### 🟢 LB07 — 双栈 ScheduleConfigSnapshot 承重根(load_bearing=true, owner_pending)
**判定: 🟢绿(计划修法安全) / 但它是全簇唯一真危爆点的「锁」，锁本身合规。**

**证据(本轮回盘)**:
- model `core/models/schedule_config_runtime_snapshot.py:7-39` 与 service `core/services/scheduler/config/config_snapshot.py:24-56` 各 **30 字段、byte-for-byte 逐字段同名同序同默认**(本轮 sed dump 双侧逐行确认)。
- 两栈注释 `rg 故意|刻意|双栈|parity|锁步|逐字段|mirror` → **ZERO 命中**(注释未落)。
- parity 守卫缺口: `tests/config/test_scheduler_config_spec_sync_contract.py`(47行) 对三 helper `_float_matches_choice/_normalize_valid_texts/_coerce_degradation_event/ensure_*/normalize_weight_triplet/coerce_*` **全部零命中** → 删/改任一 helper 不会让该测试红，守卫缺口实证在场。
- 承重禁区行回盘: 置零 model `coercion.py:470` ✅；service 对侧 helper `config_snapshot.py:89`(调用:295/:450) ✅；loud raise `MISSING_POLICY_ERROR` model `coercion.py:71-72` ✅(registry 旧值 :73-80 有 ~2-7 行漂移，按符号语义认定正确)；strict 空值 raise :153/:208 ✅。

**为何绿而非红**: 计划修法严格 = 补注释(纯文档零结构)+扩 parity(纯加测试)，两者在 owner 任一裁断(永久双栈 vs R71 收敛)下都成立、都可先行。**没有删/统一/透传动作触碰 30 字段表或禁区行。** 这正是 P3 承重的正确治理——钉住而非收敛掉。

**潜伏灾难链(说明为何它是「锁」)**: 若有人**违反计划**对双栈做 DRY 统一/单边加字段 → 算法栈(model，喂排产)用旧默认值、配置页栈(service)存新值 → 非 strict 路坏/缺数据被静默兜成默认 → 排产用错权重/降级判定**且无 loud 信号** → 静默污染排产正确性。这是全簇唯一「静默炸」路径，**计划用 LB07 注释+helper parity 前置门把它焊死**。锁合规、绿。

### 🟡 R71 — 三 helper 双栈逐字复制(owner_pending, 物理收敛待裁)
**判定: 🟡黄(有条件可做)。条件: ①LB07 注释+helper parity 必须先全绿(硬前置门，不可先于此动收敛) ②owner 先裁「物理收敛 vs 仅 parity」 ③与 R47 同批、改后统一回盘。**

**证据**: 6 处 def 零漂移(model coercion:31/:49, read:68 ; service field_coercion:45/:29, snapshot:153)，三对 byte-for-byte 等价。收敛方向 service→core.models 合法(rg 实证)、不成环。

**条件不满足时的灾难链**:
- 在 parity 前动收敛 → 删 service 副本时若**顺手把 `except Exception: continue` 改成 loud raise**(看着像 bug)→ 降级事件读取从「静默丢弃」变「崩」，static→loud 方向反转，排产侧降级路径异常 → 行为分叉。**修正: parity 必须逐字保真现有吞错语义，禁「顺手修好它」**。
- 在 parity 前动收敛 → 锁步守卫缺位，未来单边 drift 无测试拦 → 回到 LB07 静默分叉。**修正: spec_sync_contract 扩三 helper 真值表(空choices→True / `<=1e-9` 边界含 / count `max(1,...)` / 非dict→None)必须先 green。**

**前置/禁区**: 收敛只在三 helper 函数体内，禁越界到 coercion:470/:71-72/:153 等禁区；禁新建第三模块(=新P5)，唯一收口点=已存在 model 三符号。

### 🟡 R47 — 死参 raw_value 双栈对称删(load_bearing=false, owner_pending=false 可给终态)
**判定: 🟡黄(有条件可做)。条件: ①与 R71 同批、改后统一回盘 ②【本轮新发现漏项，见下】按调用块精确删，禁全局替换 `raw_value=raw_value`。**

**证据 + 本轮新发现漏项(防呆缺口)**: `_record_blank_choice_degradation` 函数体(model:83-99)确实不读 raw_value(只用 label/fallback，sample=None)，死参确认。但同文件同函数体内 `raw_value=raw_value` **字面完全相同的实参共 4 处**:
- model: `:159`/`:214` = `_record_blank_choice_degradation`(死，**要删**)；`:173`/`:225` = `_record_invalid_choice_degradation`(**活参**，:166 message 读 `{raw_value}`，**绝不能删**)。
- service: `:158`(内联)/`:211` = blank(死，删)；`:170`/`:222` = invalid(活，留)。

dossier 字段1只列了正确的 4 个删除点(model:159/:214 + service:158/:211)，但**未显式警告**同函数体内物理相邻的 4 个 invalid 活参 `raw_value=raw_value`。执行者若用 sed/全局替换删「raw_value=raw_value」会**误删活参** → invalid 降级 message `{raw_value}` NameError(loud，浪费一轮)。**修正: 计划须前置写明「逐调用块手删，blank 块删、invalid 块留；删 def 形参 model:88/service:68 后须复核两栈 invalid 路径 raw_value 仍活」。** 紧邻 loud raise(:153/:160/:208/:217)在 `if strict_mode` 分支、删的 6 行全在 `if text==""` 非 strict 分支，物理相邻语义隔离，逐行核对勿误伤。

### 🟢 R45 ≡ R48 — config_adapter 整文件删(load_bearing=false, owner_pending=false)
**判定: 🟢绿(安全，C01 簇内最早最低风险一刀)。**

**证据**: 文件 27 行；`rg config_adapter|read_critical_schedule_config|read_schedule_config_value|CriticalConfigReadResult core web data`(排除自身)→**生产零引用**；唯一外部引用 sp06:15 路径成员。R45/R48 = 同物理文件两叙述，**合并单提交整删**。唯一约束链: 同提交退 sp06:15(漏退→`path.read_text` FileNotFoundError→sp06 红，**响亮非静默**)。与双栈收敛正交(adapter 只 import FROM model，删它不动双栈本体)。删 algorithms→models 叶子边只减边，0 越层 0 环。

### 🟢 R31 — WRITE_INTERNAL_ONLY 死常量源定义删(load_bearing=false)
**判定: 🟢绿(安全)。约束: R33 删 facade 须不晚于 R31 删 shared 源。**

**证据**: 三处 :9(源)/:11(facade import)/:29(facade __all__) 零漂移；`rg write_internal_only` 全仓无旁路硬编码消费；16 个 FieldPolicy 无一用它，compat_parse 分支只比 WRITE_OPTIONAL。**删序陷阱坐实(回盘 common facade :11 在 `from core.shared.value_policies import (...)` 块内)**: R31 抢先删 :9 而 R33 facade 未删 → 加载 facade 即 loud ImportError(CI 拦截，**非静默**)。修正: R33(Batch-7)删 facade 不晚于 R31(Batch-14)删源，天然满足。禁顺手动 :6/:7/:8(三活常量)。

### 🟢 R26 — 顶层 config/summary 5 shim 删(load_bearing=false, owner_pending=true)
**判定: 🟢绿(本体安全，灾难性低)。但前置最重、晚序硬约束多，owner 须先裁解冻。**

**证据**: 5 shim 纯转出零逻辑，删错只 loud ImportError(不破不变量)。**两离线消费者反例坐实**(本轮回盘): `tools/capture_networkx_phase0_baseline.py:17` + `audit/2026-03/20260316_schedule_audit_probes.py:87` 仍走顶层老路径 → 普查「0生产消费者」被推翻，**裸 rm 会让这俩 ImportError**，须先迁。SP05 冻结面改 **BEHAVIOR_* 两字典**(:20/:33，回盘确认 STRONG :15 只含 optimizer，registry 误标 STRONG 已纠)。

**Q6 晚序硬约束(序错=测试经老路径 loud 红，非静默)**: R26 删 shim 须晚于 R29(B05)/R33(B06)/R52(B09) 三桶收敛 + R71 收口(R26 顶层 config_snapshot.py 转出的正是 R71 编辑的深 config/config_snapshot.py)。R26 排 Batch-14 全局最晚天然满足。import 重指基数须用回盘 ~93 处/53 文件(registry 旧值 71 会漏 ~22 处悬空老路径)。

---

## 漏项(本轮新发现，没被簇计划充分覆盖的爆点/缺失前置)

1. **【R47 防呆缺口·黄】** dossier 字段1只列 4 个正确删除点，**未显式警告**同函数体内 4 个字面相同的 invalid 活参 `raw_value=raw_value`(model:173/:225, service:170/:222)。计划须前置写明「逐调用块手删、禁全局替换/sed、删 def 形参后复核 invalid 路径 raw_value 仍活」。后果 loud(NameError)非静默，但会浪费一轮且违「只动声明范围」。
2. **【R47/R71 同批回盘纪律·提醒】** R47 删 model:88/service:68 死形参会令其**下方**符号行号上移；R71 三 helper(model:31/:49,service:29/:45)在 R47 函数(model:83/service:63)**之上**不受影响，但 read:68/snapshot:153 的 `_coerce_degradation_event` 及 coercion 下半部禁区(:470)在其下会位移 → **R47/R71 同批改后须统一重 rg 回盘禁区行(尤其 :470 置零、:153/:208 raise)，不信旧行号**。
3. **【主透镜空网确认·非债】** 主透镜专攻的分层导入环(Q2)与迁移耦合(Q3)在本簇**找不到任何爆点**——这不是漏查，是本簇性质(纯内存配置双栈、收敛方向天然合法下行)决定。本簇真危险全在 Q1 双栈静默分叉，已被 LB07 parity 前置门设计性焊死、被 owner_pending 卡终态。**无真红债。**
4. **【R26 离线消费者验证门·缺失前置】** 两离线脚本(tools/、audit/)CI 不一定跑，须把它们纳入 R26 删前**手动验证清单**，否则迁漏延迟到离线运行才暴露。

# 逐簇爆炸对抗 r3 · C-CONFIG-DUAL · 主透镜=灵魂线热路径+收口等价

> 只读不改任何 .py。行号 2026-06-05 当前工作区 rg 实测回盘，不信旧值。
> 成员债: LB07 / R71 / R47 / R45 / R48 / R26 / R31。主攻 Q4(灵魂线热路径)/Q5(收口逐分支等价)/Q6(测试迁移序)。
> 默认怀疑：多数维度存疑即标红，不放过「测试绿但护栏已破」的静默失效。

---

## 判定总览

| 债 | 判定 | 一句话 |
|---|---|---|
| LB07 | 🟢绿（仅注释+扩parity，owner_pending 不给终态） | 承重双栈，候选修法零结构，先落是 R71/R47 的安全网 |
| R71 | 🟡黄（守卫缺口实证 + owner裁断门 + Q5反转风险） | 物理收敛前必须先扩三 helper parity，否则静默漂移无拦 |
| R47 | 🔴红（双胞胎函数误删活参 → 静默吞 invalid_choice 上报） | 删 blank 死参时极易连坐删 invalid 活参，踩灵魂线 |
| R45 | 🟢绿（直删死壳 + 同提交退 sp06:15） | 27行死壳零生产引用，漏退测试是 loud 红非静默 |
| R48 | 🟢绿（≡R45 单提交整删） | 同物理文件第二叙述，合并单删 |
| R26 | 🟡黄（晚序 facade + 2 离线消费者 + 三桶前置 + 守卫不进 STRONG） | 必晚于 R29/R33/R52 收敛，先删则老路径测试红 |
| R31 | 🟡黄（删序硬约束：R33 删 facade 须不晚于 R31 删源） | 反序 → facade :11 残留 import loud ImportError |

---

## 🔴 R47 — 双胞胎函数误删活参（本簇唯一红，落 coercion 灵魂线热路径）

### 实测回盘（已 rg 当前行号）
两栈各有**一对结构近孪生**的降级记录函数，紧邻摆放：
- model `coercion.py`: `_record_blank_choice_degradation` :83-98（`raw_value:Any` @:88 **死**，body 仅用 label/fallback/field_name，`sample=None`）↔ `_record_invalid_choice_degradation` :101-120（`raw_value:Any` @:106 **活**，:116 插 `{raw_value}`、:119 `sample=str(raw_value or "")`）。
- service `config_field_coercion.py`: `_record_blank_choice_degradation` :63-78（死参 @:68）↔ `_record_invalid_choice_degradation` :81-100（活参 @:86，:96/:99 读）。

R47 dossier 字段1 列「删两栈 blank 死实参」——但**全文件 `raw_value=raw_value,` 实参点共 8 处**：model :159/:173/:214/:225、service :158/:170/:211/:222。其中 **:159/:214（model blank）、:158/:211（service blank）可删**；**:173/:225（model invalid）、:170/:222（service invalid）是活参，删则炸**。两组调用块文本逐字相同（`scope=/field=/raw_value=raw_value/fallback=`），靠 grep `raw_value=raw_value` 盲删必中活参。

### 灾难链（改X→静默→坏数据流到Y）
执行者按 dossier「删两栈死参 raw_value」用 `rg raw_value=raw_value` 批量定位 → **连坐删掉 `_record_invalid_choice_degradation` 调用点的 `raw_value=raw_value`（:173/:225/:170/:222）** → invalid 函数体真读 raw_value(:116/:119)，删调用实参后：同步删形参=`TypeError` loud(低危被测试抓)；只删调用实参留形参=**该参取缺省/异常，invalid_choice 降级消息里 `{raw_value}` 变空、`sample` 丢真值** → 配置页坏选项值（如 graph_on_mode 填非法串）的降级上报**静默丢失原始坏值证据**，运维看不到用户填了什么 → 灵魂线「可观测降级」退化成「半哑降级」，排产仍按 fallback 跑但失去诊断线索。**更隐蔽**：R47 现成 parity 测试 `..._emit_blank_required`（dossier verify 已纠名）只覆盖 blank 路，**不覆盖 invalid_choice 路**——误删 invalid 活参**测试全绿，护栏已破**。

### 修正建议（前置/顺序/禁区行）
1. **禁区行（绝不碰）**：`_record_invalid_choice_degradation` 全体（model:101-120 / service:81-100）+ 其 4 调用点活实参（model:173/:225 / service:170/:222）+ 紧邻 strict loud raise（model:153/:166/:208/:220 / service 对侧:156/:205）。
2. **只动 6 处死点**：model 形参:88、实参:159/:214；service 形参:68、实参:158/:211。**按「调用的是 `_record_blank_choice_degradation`」逐点确认函数名再删**，禁用裸 `raw_value=raw_value` 全局替换。
3. **顺序**：LB07 注释+扩 parity 先 → R47+R71 同批（先删死参再收敛）→ 删后必跑 blank 与 invalid **两路** degradation 回归（现成 blank 测试不足以守 invalid，须补 invalid 路断言或人工核 :116 消息逐字不变）。

---

## 🟡 R71 — 物理收敛前守卫缺口 + Q5 静默→loud 反转风险

### 实测
三 helper 双栈逐字等价（逐行 Read 确认）：`_float_matches_choice`(coercion:31↔field_coercion:45)、`_normalize_valid_texts`(:49↔:29)、`_coerce_degradation_event`(read:68-94↔config_snapshot:153-179，**byte-for-byte**)。
- **守卫缺口实证**：`rg 三helper名 tests/` = **ZERO 命中**。删/改任一 helper body **不会让任何测试变红**。
- **收口边未建**：`rg "from core.models" service两文件` = 空 → service→model 反向复用边当前不存在（R71 确未开工，LB07 确为前置，符合）。
- **分层安全**：service 两文件无 `from core.algorithms`；收口方向 core.services→core.models 合法下行、不成环。

### 条件（满足才 🟡，否则升🔴）
**条件A（硬前置）**：扩 `regression_scheduler_config_spec_sync_contract.py` 覆盖三 helper 逐分支（含 `choices=()`→True、`abs==1e-9` inclusive、`except Exception:continue` 静默跳、`非dict→None`、`count` 坏值→1 下限钳）必须**先绿**，否则收敛=盲收。
**条件B（Q5 灵魂线保真）**：`_coerce_degradation_event` 现有 `not isinstance(dict)→return None`(:71/:156) 与 `except:count=1`(:85/:170) 是**已设计静默语义**，收敛/parity **逐字保真**；任何把坏 seq 的 `return None` 顺手改成 raise = 静默→loud 反转，下游 `seed_snapshot_degradation_collector`(read:97) 从「静默丢弃坏事件」突变成「加载即崩」=可用性放大，**禁改**。
**条件C（owner裁断门）**：owner_pending=true，物理收敛 vs 仅 parity 待 B03 裁；扩 parity（纯加测试）无须裁可先行。

### 灾难链（若跳过条件A）
跳过扩 parity 直接删 service 三 helper 副本改 import → 守卫缺口下**收敛 diff 无测试比对** → 若收敛时手滑改了 `_normalize_valid_texts` 的保序逻辑（如误用 `sorted(set())`）→ model 栈喂算法、service 栈喂配置页对 choices 合法值口径**静默分叉** → 算法判某权重选项非法回落默认、配置页判合法 → 排产用错权重，无任何报错。

---

## 🟡 R26 — 晚序 facade（必晚于 R29/R33/R52 收敛 + 2 离线消费者）

### 实测
5 顶层 shim 纯转出（config_service/snapshot/validator/schedule_summary/types）。**2 离线活消费者复现**：`tools/capture_networkx_phase0_baseline.py:17`(ConfigService) + `audit/2026-03/20260316_schedule_audit_probes.py:87`(build_overdue_items) → **普查「0 生产消费者」被推翻**，先删=ImportError(loud)。R26↔R71 config_snapshot.py 假碰撞确认（199B shim vs 17655B 深文件，不同物理文件）→ 降软相关。

### 条件
必晚于 **R29(B05)/R33(B06)/R52(B09)** 三桶收敛（facade 删除晚于收敛）；先删则三桶测试经顶层老路径变红(loud)。重指清单基数以回盘 **~93 处 import / 53 文件**为准（registry 旧值71会漏~22处悬空）。改 SP05 认准 **BEHAVIOR_* 两字典**(`:20-31`+`:33-82`)，**非 STRONG_***(:15-18 当前只含2 optimizer)。owner_pending=true 待裁解冻。R71 先 R26 后（Batch-14 天然满足）。

### 灾难链
以 registry「71处」为基数重指 → 漏 ~22 处顶层 import 未迁 → 删 shim 后悬空老路径 ImportError(loud)；或漏迁 2 离线脚本 → CI 不跑则延迟到离线运行才暴露。**均 loud 非静默**，故 🟡 而非 🔴。

---

## 🟡 R31 — 删序硬约束（R33 删 facade ≤ R31 删源）

### 实测
`WRITE_INTERNAL_ONLY` 仅 3 处：源 `core/shared/value_policies.py:9` + facade `core/services/common/value_policies.py:11`(import)/:29(__all__)。零生产/零测试消费（16 FieldPolicy 无一用、compat_parse 只比 ==WRITE_OPTIONAL）。R33 facade 文件**当前仍在**(:11/:29 实测在场)。

### 条件 + 灾难链
**R33（Batch-7）删 facade 须不晚于 R31（Batch-14）删源**。反序（R31 先删 :9）→ facade :11 残留 `from core.shared.value_policies import (...WRITE_INTERNAL_ONLY...)` → 加载 common facade **loud ImportError**，CI 拦截。禁区：R31 只删 :9，**不得碰 :6/:7/:8**(WRITE_REQUIRED/OPTIONAL/NOT_APPLICABLE，16 处在用，删则静默改解析语义)。loud 非静默 → 🟡。

---

## 🟢 绿（安全可做）

- **LB07**：承重，候选修法仅「两栈 @dataclass 上方补『我是故意的』中文注释（model snapshot:7 / service config/config_snapshot:24）+ 扩三 helper parity」，零删除/统一/透传。禁区行实测保真：置零 coercion:470 + service helper `_graph_downstream_weight_for_visible_weights`、loud raise coercion:72/153/166/208/220/258/302、read 入口 read_runtime_cfg_raw_value:10。owner_pending 只标不给终态。Batch-1 全局 ROOT 先落，门控 R71/R47。**安全**。
- **R45 / R48**：同一物理文件 `core/algorithms/greedy/config_adapter.py`(实测27行)两叙述，**合并单提交整删** + 同提交退 `tests/regression_sp06_no_duplicate_defs.py:15`(NO_CFG_GET_TARGETS)。生产零引用(rg 三符号仅自身命中)，替代路径 `schedule_params.py:59 _snapshot_attr` 已 loud-raise 就位。漏退 sp06:15 → FileNotFoundError 红(loud)。与双栈收敛正交、零 LB 耦合。**最早最低风险一刀，安全**。

---

## 漏项（本轮新发现，没被簇计划充分覆盖的爆点/缺失前置）

1. **【R47 活参连坐——计划覆盖不足，建议升关注】** 簇文档 ASC-1 与 R47 dossier 只强调「删两栈死参」「避开 loud raise 禁区」，**未点名同文件存在 `_record_invalid_choice_degradation` 这个结构孪生且 raw_value 是活参**。两组调用块 `raw_value=raw_value,` 文本完全相同，盲 grep/sed 替换必误伤 invalid 活参，且现成 blank parity 测试**不覆盖 invalid 路**→测试绿但 invalid_choice 降级证据静默丢失。**前置建议**：R47 执行清单必须显式列「禁区=invalid 4 调用点 model:173/:225 service:170/:222」并补 invalid 路 degradation 回归断言。

2. **【R47/R71 同批后承重行号必重回盘——已标但缺硬闸】** R47 删 model coercion 6 行 + R71 收敛 service 三 helper 后，LB07 禁区行(:470/:72/:153...)与 R71 锚行(:31/:49)全部位移。簇文档 §A 已要求「整组改后统一回盘」，但**未给「回盘后才能跑 LB07 parity 验收」的硬闸**——若收敛中途以旧行号核禁区可能误判。前置建议：[LB07,R47,R71] co_change 提交后、跑 parity 前，强制 rg 重定位全部承重符号。

3. **【R26 SP05 文档树断言 :640-658 易漏】** R26 三步只强调删 BEHAVIOR_* 两字典 + 迁93 import，但 `migrated_root_names`(:641 含 config_service.py @:648)+「兼容薄门面」标注(:655) 删 shim 后期望需同步改，否则 SP05 自身红。属脚注级、执行易漏，建议提为显式 step。

4. **【R71 Q5 反转——条件B 须写进收敛准入，不止 parity】** 守卫缺口下，扩 parity 若只断言「两栈 model_fn(x)==service_fn(x)」而**不断言「两栈都不 raise」**，则同步把两栈坏 seq 的 `return None` 都改成 raise 仍会 parity 通过(两侧一致)却踩灵魂线(静默→loud 全局反转)。parity 真值表须显式 pin「`非dict→返回 None 且不抛`」「`count 坏值→1 且不抛`」，否则等价测试守不住灵魂线方向。

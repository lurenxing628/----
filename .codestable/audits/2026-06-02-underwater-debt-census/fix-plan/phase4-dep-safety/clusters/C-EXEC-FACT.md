# C-EXEC-FACT 原子簇分析（只读不改）

> ✅ **2026-06-08 B 执行补登**：G07/G08 中的 R17/R20 已 fixed 并同原子处理。R17 删除 feedback service/support 里的死导入与 `_REPORTED_STATUS_BY_ACTION` 死项；R20 删除 service 层 `operation_execution_labels.py` 纯转出垫片并改 5 个消费方直连 model。`R15` 在 G08 只作为 support 侧已落地 raise 禁区被守住，provider 坏时间解析残债仍留给 G09。

> ✅ **2026-06-09 ROOT 执行补登**：G07a/LB01 已 fixed。`_load_current_official_schedule` 上方已补写侧 fail-CLOSED 第一闸注释，`_build_event_payload` 写死 `SOURCE_SCHEDULE/ROLE_ADOPTED/None` 上方已补落库前消毒注释；硬拒条件、`can_write_feedback` 第二硬门和三写死字段均未改。后续同文件动作仍须按符号重 rg，禁把 LB01 注释解读成可透传 context。

> ✅ **2026-06-09 R15 执行补登**：G09 provider 链第一段 R15 已 fixed。`execution_fact_provider._parse_execution_time` 保留合法空时间 `None/""/" "` 本地返回 `None`，非空值委托既有真相源 `parse_operation_event_time`；坏时间从静默 `None` 升级为 loud raise。未改 support/state_builder 既有语义。R19/R13 已在后续补登中 fixed。

> ✅ **2026-06-09 R19 执行补登**：G09/G10 中 R19 已 fixed。`execution_snapshot.positive_op_ids` 保 sorted 并补指纹排序承重注释；`execution_snapshot` 顶层 provider import 改为函数内局部 import，避免 provider 反向收口时形成运行时环；`execution_fact_provider._positive_op_ids` 委托既有 `positive_op_ids`；`operation_execution_event_repo._positive_ids` 按 O04 保留私有版并补顺序无关注释/parity，不下沉 service、不碰 R18 stub。G09 已在 R13 后收口，G10 仅剩 R18 stub 护栏。

> ✅ **2026-06-10 R13 执行补登**：owner 已确认单机无仓库外读者，R13 按 O06 完成“先迁测试后删”。`ExecutionFact.last_event_schedule_*`、`_fact_from_state` 的 `latest` 形参/实参、旧字段赋值与孤儿 `_latest_events_by_scope` 已删除；相关测试已退旧字段断言。R13 未碰 repo stub，R18 仍 planned。

> 簇 id: C-EXEC-FACT | 成员债: LB01 R13 R15 R17 R18 R19 R20 | 簇内分区 scheduler-exec-diag
> 回盘日 2026-06-05 / HEAD c2aa7501 / 全部行号经本轮 rg 复盘（不信旧值）
> 性质: SCC 串行链，含「最危险的边」LB01↔R17（同 `_build_event_payload` 函数体）
> 物理文件分布:
> - `operation_execution_feedback_service.py`: LB01(承重宿主) + R17(死import:12) + R20(labels import:52)
> - `operation_execution_feedback_support.py`: R17(死import:11/推导式项:81) + R15(`_parse_feedback_datetime`:225) + R20(labels import:24) + R09(他簇)
> - `execution_fact_provider.py`: R13(死字段/形参/实参/孤儿 helper，fixed) + R15(`_parse_execution_time`, fixed) + R19(`_positive_op_ids`, fixed)
> - `operation_execution_event_repo.py`: R18(stub:400-406) + R19(`_positive_ids`:67-80, fixed 保私有版); R13 已解耦,不碰 repo stub
> - `execution_snapshot.py`: R19 收口点(`positive_op_ids`:29-42, fixed)

---

## A) 原子子簇拆分（必须同批/同提交 vs 可独立）

### 子簇 A1 — service 文件「承重门控 + 同文件删改」原子链
**成员**: LB01 → R17 → R20（三者同居 `operation_execution_feedback_service.py`）
**原子原因**:
1. **承重前置**: LB01 是 load_bearing=true 宿主，硬拒 :369-371 + 写死消毒 :471-473 + 第二硬门 :381 是承重护栏。R17 删 :12 死 import、R20 改 :52 labels import 都在同一物理文件，**必须等 LB01「我是故意的」注释先落、把承重显性化后才能动**（PHASE0 §10.1「最危险承重边裸奔期严禁改动」）。
2. **行号位移耦合**: R17 删 :12 一行 → 其下所有行（含 R20 的 :52、LB01 注释锚点 :369/:471）上移 1 行。R20 改 :52 → 与 R17 的 :12 同 import 块。三者改同文件，须一次原子提交或严格串行 + 每步重 rg 回盘，否则后改桶照旧行号改错位置。
**内部顺序（强制）**: **LB01（先落两处注释，锚定在符号上方，随符号移动不丢）→ R17（删 service:12 死 import）→ R20（改 service:52 labels import 为绝对 model 路径）**。理由: 承重先于动同文件; R17 删 import 缩文件; R20 在 R17 之后重新 rg `from .operation_execution_labels import` 真实行再改（不照抄 :52 快照）。

### 子簇 A2 — support 文件「R17 删推导式项 + R15 收口」原子协调
**成员**: R15（`_parse_feedback_datetime`:225 已落地）+ R17（删 :81 推导式项 + :11 孤立 import）+ R20（改 :24 labels import）
**原子原因**: 三者同居 `operation_execution_feedback_support.py`。R17 删 :81 一行 → :225（R15 战场）整体上移 1 行；R17 删 :11 → :24（R20 战场）上移 1 行。**R15 的 support 处已落地（in_progress 部分）**，但其 :225 raise 语义是灵魂线禁区，R17 删 :81/:11 时**绝不碰 :225 起的 `_parse_feedback_datetime` raise**。
**内部顺序**: **R15 先（support 处其实已落地，仅需守住 :225 raise）→ R17 删 :81/:11 → R20 改 :24**。R17/R20 在 support 文件的删改宜与 A1 的 service 删改**同一原子提交**（R17 跨 service:12 + support:11/81 三处，R20 跨 service:52 + support:24 + context:11 多处）。

### 子簇 A3 — provider 文件「R15 已收口 → R19 改 → R13 删字段」串行链
**成员**: R15（2026-06-09 已 fixed，provider `_parse_execution_time` 空值保 None、坏值 loud raise）→ R19（2026-06-09 已 fixed，`_positive_op_ids` 委托 `positive_op_ids`）→ R13（2026-06-10 已 fixed，删除死字段/赋值/形参/实参/孤儿 `_latest_events_by_scope`）
**原子原因**: 三者同居 `execution_fact_provider.py`，删改互相移动行号。R13 删字段(-2)+赋值(-2)+可能删 `_latest_events_by_scope`(-8) → 下方 R19(:70)、R15(:85) 集体上移最多 ~13 行。R19 改 :70-82 → 影响 R13 :118 调用点附近。**先改语义（R15 收口、R19 收口）后删死物（R13 删字段）**，避免后改桶撞行号 + 防删物时误伤 raise 语义。
**内部顺序（强制）**: **R15 先（已 fixed，SCC 最前置，先收口解析语义）→ R19（已 fixed，收口 `_positive_op_ids` 并补 sorted parity）→ R13 最后（已 fixed，删字段缩文件）**。注: R13 已经 owner 二次确认后执行，且没有只删字段两行，而是同步处理形参、实参、赋值和孤儿 helper。

### 子簇 A4 — repo 文件「R18 stub 护栏注释 + R19 repo 私有版」协调
**成员**: R18（stub :402 补护栏注释）+ R19（2026-06-09 已 fixed，`_positive_ids`:67 按 O04 保留私有版并补顺序无关注释/parity）
**原子原因**: R18 改 :402 一带的 stub 护栏；R19 的 :67 与 stub 组（:400-406）相距 330+ 行，物理不重叠，仅文件级保守串行。R13 已与 R18 解耦，R13 不碰 repo stub。
**内部顺序**: R19 repo 处已保留私有版并补注释/parity；R18 独立处置 stub 护栏。两者仅需同文件保守串行，无逻辑先后。

### 可独立（不强制同批）
- R18 的注释动作与 A3 的 provider 链**无逻辑耦合**（仅文件级保守串行 R19）。
- LB01 的注释口径与他簇 LB02/LB05/LB06（execution_review 读侧对称护栏）应统一文案，但**非硬阻塞**。

---

## B) 跨簇边（本簇成员 → 其他簇债）

| 本簇债 | 指向 | 关系类型 | 说明 |
|---|---|---|---|
| LB01 | R14（schedule_delay_diagnosis_service.py，同符号 `_resolve_strict_plan`） | 同符号但**跨文件**、无 import 关系 | LB01 仅补注释不碰该符号；R14 与本文件零 import 环。弱边，仅口径协调 |
| LB01 | LB02/LB05/LB06（execution_review.py 读侧 adopted-only） | parity/文案口径统一（写侧↔读侧对称纵深） | 非硬序；四处注释应统一「只能挂在正式采用方案上」口径，防语义漂移 |
| R15 | R32（`sym:replace`） | **假边（删）** | corrections B 节: R32=backup os.replace，R15=provider:89 str.replace，同名异物纯假边 |
| R15 | R30/R33/R49（B06 桶内 datetime co_change） | 收口方向一致（不同文件，无硬序） | 桶级若定统一去向，R15 须跟；纯独立文件，无行号撞 |
| R19 | R01/R46（E16 `__all__` 历史边） | **伪串行登记**：三处 `__all__` 分属三文件，R46 不动 execution_snapshot.py | 红队第2轮 P-RT22-02 已判伪边；登记备查，不作 R19 执行门 |
| R20 | R08/R09/R12 | **假边（删×3）** | corrections B 节: R20 在 context.py:11，不碰 ..._execution.py（R08/R09）/gantt_tasks（R12），三边全假 |

---

## C) 相对旧 146 边的变化（逐条删/新/降）

### 删除（假边 / 已修推翻）
1. **R20↔R08 删**: corrections B — R20 真实触及 `..._execution_context.py:11`，非 `..._execution.py`；后者 rg `operation_execution_labels` 零命中。假边。
2. **R20↔R09 删**: 同上，R20 不碰 `..._execution.py`。假边。
3. **R20↔R12 删**: corrections B — `gantt_tasks.py:8` 直连 model 不经垫片，R20 删垫片不改 gantt_tasks。假边。
4. **R15↔R32 删**: corrections B — os.replace（R32 backup）vs str.replace（R15 provider:89）同名异物，纯假边。
5. **R16↔R15（同文件 state_builder）边失效（已修前置）**: R16 已 fixed（corrections E）；R15 在 state_builder 处也已落地（in_progress 已收口 :37-41）。原「R15 须避让 R16 删表 :33-39」降为「R16 已修，R15 state_builder 处已落地」——边消解。

### 降级
6. **R13↔R18 强耦合 → 解除（降为零耦合/各自独立）**: corrections B「解耦」+ R13/R18 dossier。registry 旧设「R13 连带删 repo:254 方法、与 R18 同原子提交」基于「repo 方法是死码」旧假设；现 repo:400/402 已是 stub raise（契约护栏），R13 **不碰 repo**，R18 独立补注释。R13↔R18 从「强同批原子」降为「R13 不入 repo、R18 自处置」。
7. **R13 自身性质降级后已执行**: 死字段曾被测试读活；2026-06-10 owner 确认单机无仓库外读者后，已先迁测试再删 provider 字段和 latest 尾巴。

### 新增/强化
8. **新强化 LB01↔R17（最危险的边）**: 同属 `_build_event_payload`（:455-494）函数体——R17 触及 reported_status :475 与 LB01 写死 :471-473 同函数体。承重门控边强化为「LB01 注释先落 R17 才能动」。
9. **R15 provider 处真 P4 残留已收口（corrections A/C → 2026-06-09 fixed）**: provider 坏值不再 return None 静默；合法空值继续 None，坏值走 `parse_operation_event_time` loud raise。R15 owner_pending 已关闭。
10. **R19↔R01/R46（E16 `__all__` 边）降为伪串行登记**: 红队第2轮 P-RT22-02 已判定三处 `__all__` 分属三文件且 R46 不动 execution_snapshot.py；不再作为 R19 go/no-go 门。

---

## D) 承重前置（LB/N1/N2/R03/R58 注释/parity 是否先落 + 门控的禁区行）

### 簇内唯一承重点: LB01（load_bearing=true）
**必须先落**: LB01 两处「我是故意的」中文注释**门控整个 service 文件的删改**（A1 子簇）。
**门控的结构动作**:
- 门控 R17 删 service:12 死 import（同文件 `_build_event_payload` 函数体内）
- 门控 R20 改 service:52 labels import

**禁区行（lb_no_touch，任何债不得改其逻辑，只可上方加注释）**:
- `feedback_service.py:369-371` 硬拒分支三条件 + :374 `raise _conflict("not_current_official_plan")`（写侧 adopted-only 第一道闸）
- `feedback_service.py:381-382` `can_write_feedback` 第二硬门
- `feedback_service.py:471-473` 写死消毒层（`SOURCE_SCHEDULE / ROLE_ADOPTED / None`，故意忽略 context 同名字段，defense-in-depth，禁改透传）
- `feedback_service.py:347-356`（R20 dossier 标的审计 raw dict 承重字段，禁碰）
- 配套最终底（簇外但相关，禁删其 raise）: schema.sql:190-192 三 CHECK; `operation_execution_scope.py validate_current_official_execution_scope` 三 raise

### 灵魂线软禁区（非 LB 但语义神圣，禁改静默/兜底）
- `feedback_support.py:225` 起 `_parse_feedback_datetime` raise（R15 已落地，R17 删 :81/:11 时绝不碰）
- `execution_fact_provider.py:79-84` 的空值短路 + `parse_operation_event_time` 委托（合法 optional，禁整体 delegate 导致空值 raise；坏值分支必须 loud，禁加更深 return None）
- `repo:400/402/404/406` 等 stub `raise _unscoped_execution_read_error()`（R18/R13 禁改静默 return {}，删→退化 AttributeError 击穿契约）
- `execution_snapshot.py:42` `return sorted(out)`（事实承重: sha256 指纹稳定性依赖排序；R19 canonical 实现强制保 sorted）

### N1/N2/R03/R58: 本簇无（N1/N2 在 context.py/event.py 属他簇；R03/R58 不在本簇）

---

## E) fixed 成员作为前置（残留认账动作）

| fixed 债 | 状态 | 对本簇的残留动作 |
|---|---|---|
| **R16** | 已 fixed（corrections E，结构性消除） | R15 在 `state_builder.py:37-41` 处**已收口落地**（delegate `parse_operation_event_time`，空→None/坏→raise loud）。残留: 无代码动作，仅认账 R16 删表已完成、R15 state_builder 处不再是活债。原「R15 避让 R16 删表」前置已消解。|

> 其余 fixed（LB03/LB06/R07/R56/R57）不在本簇成员，无本簇残留。

---

## 一句话定性

C-EXEC-FACT = SCC 串行链，4 个原子子簇按物理文件切分。承重唯一点 LB01 门控 service 文件全部删改（注释先落 → R17 → R20）。最危险边 LB01↔R17 同 `_build_event_payload`。R13↔R18 强耦合已解除；R20↔R08/R09/R12、R15↔R32 经核为假边删除。R15、R19、R13 已 fixed，G09 provider 链收口；G10 只剩 R18 stub 护栏 planned。

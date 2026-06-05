# 簇 C-GANTT 原子簇重建（只读产计划）

> 成员债 R10 / R11 / R12 / R55 / R63；主文件 gantt_service.py / gantt_service_support.py / gantt_critical_chain.py（+ provider / contract）
> 回盘日 2026-06-05，行号已 rg 复核当前工作区，不信旧值。自成簇 C01（B08+B14 SCC-GANTT），不阻塞他桶。

## 0) 行号回盘（当前工作区，全部命中，旧 old_location 已失真）

| 债 | 锚点 | 真实 file:line | 旧值漂移 |
|---|---|---|---|
| R10 | 死方法 `get_latest_version_or_1` | gantt_service.py:60-62 | 无（活方法 `resolve_version`:64 禁触） |
| R10 | 测试 stub 镜像 | regression_scheduler_week_plan_summary_observability.py:59-60 | 无 |
| R11/R63 | support 版 `_normalize` def / 调用 | gantt_service_support.py:32 / :58 | 无 |
| R11/R63 | provider 版 `_normalize` def / 调用 | gantt_critical_chain_provider.py:113 / :180 | +9（旧 :104-128/:171，旧值并入相邻 `_copy`:104） |
| R11/R63 | 收口落点（已存在） | gantt_critical_chain.py（两路 :7/:19 已 import） | — |
| R12 | 丢坏行裸 `continue` | gantt_critical_chain.py:84（`_build_nodes`:79） | 无 |
| R12 | 注入点 / 空路径 | gantt_critical_chain.py:312-334 / `_empty_result`:54 / `_unavailable_result`:71 | 无 |
| R55 | filtered 病灶 | gantt_service.py:344(filters)/:384(调用)/:385 None回退 | +9（旧 335/375） |
| 公共 | 出口分叉 | gantt_service.py:384(support)/:386(provider get_critical_chain) | 旧 375/377 是 build_tasks 块 |
| 公共 | 三道白名单 | provider `_copy`:104 / 两份 `_normalize`:32+:113 / contract `_public_critical_chain`:19（`:40 return raw` 透传） | — |

承重/精度禁区行确认：`_copy_critical_chain_result`(provider:104) 与 `_normalize`(:113) 是两个独立 staticmethod，收口只动 `_normalize`，**禁误删 `_copy`**；`resolve_version`(gantt_service.py:64) 是活方法，R10 删 :60-62 后须 grep 复核 :64 仍在。`gantt_critical_chain.py` 仅 import `._sched_utils`/`.gantt_task_labels`，不反向 import support/provider → 收口下沉 `_normalize` 到它**无环、0 越层**。

## A) 原子子簇拆分（必须同批/同提交 vs 可独立）

簇 C-GANTT 拆成 **3 个原子子簇**，全部进同一 PR（gantt_service.py 物理串行约束），但内部是严格偏序链。

### 原子子簇 A1：`{R11, R63}` —— 单一物理动作（同一债）
- **原子原因**：R11≡R63 是**同一对** `_normalize_critical_chain_result` 副本（support:32-51 + provider:113-137）的去重收口，registry 多处明示「合并为单个 work item」。两条改的是完全相同的两段代码，不是两个动作。
- **内部顺序**：**无谁先谁后**——本就一次落地。若误拆两人各改一份副本，会撞改 support.py+provider.py 同两文件，且可能一人删 support 一人删 provider 造成调用悬空。**必须合并派工，禁拆两条。**
- **动作**：抽单份 `_normalize_critical_chain_result(raw)` 到已存在落点 `gantt_critical_chain.py`，support:58 / provider:180 两路改调它；逐字保留 8 键归一不变量；收口取/补 support 的 `bool(is_available)` 显式包裹（provider:134 裸传，两路当前等价但 support 写法更稳）。**绝不 `return raw`、不删键、不改默认值**（灾难链：support:58 改 return raw → 缺 available/edge_type_stats 默认 → collect_gantt_degradation_events:70 判 available 失效，降级该报不报=灵魂线违规）。
- owner_pending：R11=true（其档全程「若获批」）/ R63=false（其档给终态）。合并 work item 以 R63 终态修法为准，R11 的 owner 裁断点（保留哪份写法）并入。

### 原子子簇 A2：`{R12}` —— 在统一后的单份 helper 加 `dropped_count`/`critical_chain_partial`
- **原子原因（收口前置）**：R12 给关键链结果加可观测降级键，必须加在 A1 统一后的**单份** helper + 注入点（gantt_critical_chain.py:312-334）。若 A1 未先合并，R12 要改两份副本 = 复活 A1 这条 P5。Phase1 已标 `R11→R12` 收口前置边。
- **内部顺序**：**A1 先于 A2**（强偏序）。A2 与 A3 之间无强先后，但都晚于 A1。
- **动作**：保留 :84 过滤本身（刻意韧性，删它 → None 流入 :114 sort/:262 max → TypeError 被出口 try/except 接住 → 整链 available:False 功能回归）；照搬 gantt_tasks.py:192-196 的 `DegradationCollector`+`record_bad_time_row`(helper _sched_display_utils.py:84，code `bad_time_row_skipped`)，scope 取关键链专属（如 `gantt.critical_chain`，勿混 gantt_tasks 的 `gantt.tasks`）；注入点 :328-334 加 `dropped_count:int`+`critical_chain_partial:bool`；**`_empty_result`(:54) 也须带 dropped_count**（否则「全坏行」最该报警的场景反而无信号，自相矛盾）。新键须穿三道白名单（卡口是两份/收口后单份 `_normalize`，contract:40 `return raw` 透传不卡）。owner_pending=false。

### 原子子簇 A3：`{R55}` —— 在统一后的单份 helper 加 `scope=filtered/full`
- **原子原因（收口前置 + 呈现失真补标记）**：R55 给关键链结果加 scope 消歧，必须加在 A1 统一后的单份 helper，default `'full'`，由 filtered 调用点（support `critical_chain_for_plan_detail_filter`:54）**显式覆写**为 `'filtered'`，provider `get_critical_chain`:143（无 filter）= `'full'`。**禁在 helper 里靠「filters 空否」反推**（静默推断违灵魂线，且 provider full 路径无 filters 上下文，反推必错）。若 A1 未先合并 → 两份各加一遍易分叉。
- **内部顺序**：**A1 先于 A3**（强偏序）。scope 须穿三道白名单：主闸 `_normalize`、provider `_copy_critical_chain_result`(:104-110，当前只复制 ids/edges/edge_type_stats/reason_code，**会丢 scope，须补**)、contract `_public_critical_chain` unavailable 分支(:22-39 build 固定键，会吞 scope；:40 透传分支保留)。
- **红线**：严禁裸删 filtered 过滤逻辑（裸删=把 filtered 视图改成整版，反砍业务=违灵魂线）；禁破坏 support:55-56 `if not filters: return None` 分流判据 + gantt_service.py:385 None 回退（有意降级，scope 修法不动）。owner_pending=true → **终态修法（scope 落点写法、本轮是否做）待 owner+怀疑者复核**（needs_adversarial=true 且 registry verdict=null，PHASE0 §6 三问：None 回退是否有意/裸删 vs 补标记/当下债 vs 在途态）。

### 独立成员：`{R10}` —— 同 PR 但逻辑独立
- **是否原子**：R10 删 gantt_service.py:60-62 死方法 + stub:59-60，与 A1/A2/A3 **逻辑零重叠**（删头部死叶子 vs 改中段/底层归一）。**非原子**：不门控也不被门控任何收口动作。
- **为何仍同 PR**：纯物理约束——R10 与 R55 共居 gantt_service.py，PHASE0 §3「同文件不得两 PR 并发改」。R10 删 :60-62 后 R55 的 :384 上移 3 行，但 R55 按符号名定位不受影响；**任意顺序皆安全**。推荐 R10 先删（缩短文件）。
- 精度禁区：删 :60-62 后须 grep 复核 `def resolve_version`(:64) 仍在（相邻活方法，名字也含 version，误删即静默炸周计划版本解析）。owner_pending=false，纯删除无 parity，反需删 stub。

### 严格偏序总链
```
A1{R11≡R63}（统一单份 _normalize）
        ├──> A2{R12}（加 dropped_count/critical_chain_partial）
        └──> A3{R55}（加 scope=filtered/full）   ← owner 门控本轮是否做
R10（独立，同 PR 物理串行，任意顺序）
```
A2 与 A3 强烈建议**同一次改 `_normalize`**（共用三道白名单，避免两轮穿白名单 + 两轮改同函数）。

## B) 跨簇边（本簇成员指向【其他簇】债的依赖）

本簇五债的 interference_edges 几乎全落在 C01 簇内同文件兄弟（R21/R34/R44/R72 等仍属同一大簇 C01）。但 `_clusters.json` 把 C01 整体当一簇——本任务按 SCC-GANTT 子簇视角，下列是 C-GANTT 五债指向**簇外（同 C01 但非本五债）**的边：

| 本簇债 | 指向 | 文件 | 关系类型 | 处置 |
|---|---|---|---|---|
| R55 | R21 | scheduler_gantt.py / gantt_plan_query.py | 同文件（消费者侧）：R55 prod 链经 scheduler_gantt.py:345-351 组装 resource_type/resource_id 传到 :344 | **非改同段**：R55 只读该消费者；若 R21 改 :345-351 data_kwargs，须确认 resource_type/resource_id 仍传到 :344（R55 病灶触发条件，勿顺手砍） |
| R55 | R44 | scheduler_gantt.py | 同文件（消费者侧） | 同上，R55 不改该文件，无 dict 键撞 |
| R55 | R72 | scheduler_gantt.py | 同文件（消费者侧） | 同上 |
| R55/R10/R11/R12/R63 | R34 | gantt_service.py | 同文件：R34 纯删死方法（corrections A 节纠正：非「收敛到 column_name」，repoint 目标 `get_plan_time_span_for_resolution` 存在）；需确认 R34 改区是否落 :344-384 窗口 | 若落同窗口则串行；R34 落点在 schedule_repo 死方法（subclusters R34→schedule_repo.py），实际不在 gantt_service.py 病灶段，**仅同文件合并冲突约束，无语义碰撞** |
| R10/R11/R12/R55/R63 | R21 | gantt_service.py | 同文件（gantt_plan_query 落点 R21） | 仅合并冲突，同 PR 或串行 |

**关键结论**：C-GANTT 对簇外**无收口前置 / 无 parity 前置 / 无承重前置**边——所有「收口前置」「同改」边都在本五债**内部**（A1→A2/A3）。对外只有**「同文件勿并发改 + 消费者触发条件勿砍」**两类弱约束（PHASE0 §3 物理串行）。本簇自成闭环，不阻塞他桶，他桶也不门控本簇启动。

## C) 相对旧 146 边的变化（逐条：删 / 新 / 降）

> 对照 corrections B 节假边清单 + A 节修法推翻 + E 节 fixed 态，逐条裁定本簇相关边。

### 删除（误标 / 假边）
- **删 `R12↔R20`（gantt_tasks.py 假碰撞）**：corrections B 节明示 R20=operation_execution_labels 在 context.py:11，**不碰** gantt_tasks.py / ..._execution.py，三边（R20↔R08/R09/R12）全假。R12 interference 里的 R20（why=gantt_tasks.py）是假边，删。
- **删 R12 的 same_file 噪声边 `R12↔{R10,R11,R21,R34,R63}`**：corrections + R12 档案 §5 证实这些 why 指向 gantt_service.py，**不是** R12 所在的 gantt_critical_chain.py，`same_symbol=false` 且行段不重叠，属「同分区不同文件」噪声边，降级为非约束（见下「降级」）。

### 新增（旧图缺、本轮坐实）
- **新增 `A1→A2`（R11/R63 → R12，收口前置硬边）**：旧图按 same_file 噪声把 R11/R12 当对称同文件边；本轮坐实为**有向收口前置**——R12 加 dropped_count 必须在 A1 统一后的单份 helper，倒序复活 P5。这是语义边，非物理边。
- **新增 `A1→A3`（R11/R63 → R55，收口前置硬边）**：同理，R55 加 scope 必须落 A1 单份 helper。Phase1 已标 `R11→R55`，本轮确认为硬前置且方向明确。
- **新增 `R12 ⟂ R55 同批边（共用三道白名单）`**：二者新键（dropped_count/critical_chain_partial vs scope）落同一 `_normalize`+`_copy`+contract 白名单，宜同 PR 一次穿白名单。非偏序，是「同批协同」边。

### 降级（硬依赖 → 软约束）
- **降 `R10↔R55`：硬「同文件撞」→ 软「同 PR 物理串行」**：R10 删 :60-62 / R55 改 :384，相距 280+ 行，物理不重叠，任意顺序安全（R55 按符号定位）。仅 PHASE0 §3「勿两 PR 并发改 gantt_service.py」，无致命撞车。
- **降 `R12↔{R10/R11/R21/R34/R63}` same_file 噪声 → 非约束**：见上「删除」，gantt_critical_chain.py 内 R12 `same_file_siblings=[]`，唯一真共址是 R55（why 同含 gantt_critical_chain.py + gantt_service.py），但 R12 在 :84/:328-334、R55 在 :344-384（gantt_service.py 侧），文件内行段隔开 >300 行，仅键集需协调键名不冲突。
- **降 `R55→R21/R44/R72`：同文件 → 消费者只读触发条件**：R55 不改 scheduler_gantt.py，只依赖其 :345-351 把 resource_type/resource_id 传到 :344；降为「他债改该段时勿砍触发条件」的软提醒。

### 本簇不涉及的 corrections B/E 项（确认无关，不误用）
- R02↔R25、R45↔{LB07,R33,R51}、R32↔R15、LB04↔{LB07,R33}、R26↔R43、config_snapshot R26↔R71、R13↔R18 解耦、R05→R34 降级、R20↔R08/R09 —— 均**不含本簇五债**（R20↔R12 那条已在上「删除」处理）。本簇无 fixed 成员（R10/R11/R12/R55/R63 均 planned/owner_pending，无一在 LB06/R56/R57/R07/R16/LB03 已修清单）。

## D) 承重前置（门控簇内哪些结构动作 + 禁区行）

本簇五债 `load_bearing=false`、`lb_no_touch=null`，**无 §5 承重清单文件、无 N1/N2/R03/R58 承重点落在本簇文件**。但 phase1_blast 标出**毗邻承重行为**（归一调用对 support 路径承重），门控如下：

### 门控关系：parity 黄金基线先于结构动作（F 门）
- **A1（收口去重）的门**：动手前**必须先建 parity 黄金基线测试** `tests/regression_gantt_critical_chain_normalize_parity.py`（当前不存在），对**当前两副本**断言逐键等价（含 5 类边界：`{}`/非dict/`available=0`/`available="yes"`/`available=False`无code），尤其钉死 `bool(is_available)` 包裹差异。**无 parity 不得收口**——这是 P5 收口的安全门，门控 A1 的删副本动作。
- **A2/A3 的门**：在 A1 单份 helper 上加键后，须断言新键**穿透三道白名单不被剥离**（卡口是 `_normalize`，contract:40 透传不卡），且 `ids/edges/makespan_end/available` 既有取值不变（补可观测不改行为）。

### 禁区行（绝不删/统一/透传/裸砍，仅可改调用目标 / 加注释 / 加标记）
1. `gantt_service_support.py:58` `return _normalize_critical_chain_result(raw)` —— **禁改 `return raw`**（raw 缺 available/edge_type_stats 默认，归一是 support 路径唯一补默认点）；仅可改为调单份 helper。
2. `gantt_service_support.py:70-71` `collect_gantt_degradation_events` 读 available/reason_code —— 依赖归一后字段，禁让其读未归一 raw；亦是 R55 scope 降级域邻接（:75 `scope="scheduler.gantt"` 是 DegradationEvent 域名，**与关键链 scope 同名异义，勿混**）。
3. `gantt_critical_chain_provider.py:104-110` `_copy_critical_chain_result` —— 与 `_normalize`(:113) 是**两个独立 staticmethod**，A1 只收口 `_normalize`，**严禁误删 `_copy`**（:157/:184/:188 等 6 处缓存浅拷在用）；A3 须在 `_copy` 补 scope（当前只复制 ids/edges/edge_type_stats/reason_code）。
4. `gantt_critical_chain_provider.py:180` `computed = self._normalize_critical_chain_result(raw)` —— 禁删归一、禁直接缓存 raw（:183 `_critical_chain_cacheable` 读 available）。
5. `gantt_contract.py:19-40` `_public_critical_chain` —— 白名单依赖归一后 `available is False` 分支；:40 `return raw` 透传分支保留新键（partial/scope 主场景透过），unavailable 分支(:22-39) 须确认新键合理保留/置默认。
6. `gantt_critical_chain.py:84` `if not st or not et or not (st < et): continue` —— R12 **禁删/改条件**（删它 → None 流入 :114 sort/:262 max → TypeError → 出口 try/except 接住 → 整链 available:False 功能回归 = 过度激进）。
7. `gantt_critical_chain.py:312-359` 出口 try/except（:338-341 出口A / :352-359 出口B）—— R12 不碰（其领地是注入点+三白名单）；若另有 P4 出口吞错债（R55 档曾提及但实为呈现失真，不在此），需独立处理，A2 不顺手动。
8. `gantt_service.py:64-69` `resolve_version` —— R10 删 :60-62 死方法的**操作精度禁区**（活方法，名字含 version，误删即静默炸周计划版本解析）；删后立即 grep 复核 :64 在。
9. `gantt_service.py:385-390` filters 空→None→fallback provider full —— R55 灵魂线「有意降级」回退，scope 修法不得破坏；`gantt_service_support.py:55-56` `if not filters: return None` 分流判据同禁动。
10. `gantt_critical_chain.py:347` 算法不变量注释「输入：某一 version 的全量排程（不按周截断）」—— 只读，R55 scope 修法只在算法外加标记，不动算法。

> 「我是故意的」注释需求：本簇无承重点须补认账注释（lb=false）；但 A2 保留 :84 过滤、A3 不删 filtered 过滤，二者本质是「刻意韧性/有意降级」——收口/加键时宜就近补一行注释钉死「此过滤/None 回退是刻意行为，新键只旁路标记不改其语义」，防未来 LLM 失忆删除。

## E) fixed 成员残留动作（认账注释）

**本簇无 fixed 成员。** R10/R11/R12/R55/R63 五债状态：
- R10 planned（owner_pending=false，可直删）
- R11 planned（owner_pending=true）
- R12 planned（owner_pending=false）
- R55 planned（owner_pending=true，needs_adversarial=true 且 verdict=null）
- R63 planned（owner_pending=false）

无一落在 corrections E 节已修清单（LB03/LB06/R07/R16/R56/R57）。故**无 fixed 前置残留动作、无需补认账注释**（认账注释属 LB03/R07/R56 等已修偏离债，不涉本簇）。

唯一「待 owner」残留：
- A1 的 R11（owner_pending=true）裁断点 = 合并取 support 的 `bool()` 包裹写法 vs provider 裸写法（建议保留 `bool()`）；与 R63 终态修法合并为单 work item。
- A3 的 R55（owner_pending=true）裁断点 = PHASE0 §6 三问（None 回退是否有意 / 裸删 vs 补标记 / 当下债 vs 在途态）+ 本轮是否做；怀疑者复核门未过前不锁终态 patch。

## 返回串

簇 C-GANTT | 原子子簇:3个 [A1{R11≡R63}同一物理动作 / A2{R12} / A3{R55}] + R10独立同PR | 关键内部顺序:A1(统一单份_normalize)→A2(加dropped_count/critical_chain_partial)+A3(加scope=filtered/full,二者同改_normalize)；R10任意序但同PR串行(删:60-62后grep复核resolve_version:64) | 跨簇边:对簇外无收口/parity/承重前置,仅R55→R21/R44/R72消费者只读触发条件勿砍+R34/R21同gantt_service.py勿并发改(PHASE0§3) | 边变化:删[R12↔R20假边(R20在context.py不碰gantt_tasks)、R12↔gantt_service.py五债same_file噪声]/新[A1→A2、A1→A3收口前置硬边、R12⟂R55同批穿白名单]/降[R10↔R55硬撞→软同PR串行、R55→消费者软提醒] | 承重前置:本簇lb=false无承重点,门=A1必先建normalize parity黄金基线(钉bool(is_available)差异)否则禁收口;禁区:support:58禁return raw、provider _copy:104禁误删(独立于_normalize:113)、:84过滤禁删(否则None→TypeError整链降级)、resolve_version:64禁误删、:385 None回退+:55-56分流判据禁破坏

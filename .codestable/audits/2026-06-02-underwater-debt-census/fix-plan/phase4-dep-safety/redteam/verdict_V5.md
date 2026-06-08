# Layer3 回炉争议裁定 — V5（争议组 ⑧R41 改面 / ⑨R69 seq=0 短路）

> 裁定 agent，只读不改。所有 file:line 均当前工作区（git b08162cd 基线）rg/sed 回盘实测，旧值（blast / dossier old_location）一律不信。
> 铁律：承重只补注释+绑契约/parity；灵魂线不新增兜底，P4 改 loud raise 或补可观测；P5 收口已存在点；owner_pending 只标不给终态修法/不分配批次。
> 每条给【裁定】+【证据】+【对批次计划的影响】。不和稀泥。

---

## ⑧ R41 改面 6 族重新框定 —— 爆点说 dossier/r1 低估改动面（6 族枚举映射映非 2 文件）

### 裁定 8.1：改面框定——爆点成立但非"dossier 漏报"，是 r1 视角窄；dossier 字段8 已枚举全 6 族

【裁定】R41 的收口改面**确为 6 枚举族（machine/operator/day_type/batch_status/priority/ready）+ process_bp 的 _source_zh/_merge_mode_zh**，绝非"ready 一处 / 2 文件"。但这不是 R41.md dossier 的缺陷——dossier 字段7 已逐符号给 6 族反例、字段8 已逐行枚举全部 13+ 消费点。被低估的是 **r1-SOUL 早期"只盯 ready"** 的视角，r2-SOUL 逐 def 对照后已纠正（_layer3_explosion.md:152）。回炉以"6 族全枚举"为准。

【证据】6 族 def 实测：`web/routes/enum_display.py:13`(machine)/`:24`(operator)/`:33`(day_type)/`:47`(batch_status)/`:62`(priority)/`:73`(ready)；process_bp `web/routes/process_bp.py:16`(_merge_mode_zh)/`:22`(_source_zh)。坏值/空串口径分歧实锤：`enum_display.py:21/30/44/59` `return v or "-"`（空串→"-"）、`:29` `"停用/休假"`、`:70` `"未知"`、`:79` `return "未齐套"`（ready 末行）、`process_bp.py:25` `return "自制"`（_source_zh else 吞"外协"别名/未知=误判）。

【对批次计划的影响】不改前置/顺序，仅**扩 owner 裁断材料口径**：回炉 owner 裁断门从 r1 的 4 处扩到 ≥6 处（_layer3_explosion.md:152），parity 必须全 6 族 ×{合法/空串/None/未知/多枚举态}逐格。R41 仍排 Batch-5、须在 Batch-1（LB04 安全网）之后。

### 裁定 8.2：收口范围——5 族可收口、batch_status_zh 必须保留私有（无 canonical 收口点）

【裁定】6 族里**只有 5 族有 enum_normalizers 已存在收口点**；`batch_status_zh` **无 canonical 收口函数，必须保留私有**，强行新建 `batch_status_label` = 制造新 P5（违铁律5），禁止。爆点未触及此点，本裁定补钉。

【证据】收口点实测 `core/services/common/enum_normalizers.py`：`operator_status_label:82` / `machine_status_label:124` / `source_type_label:159` / `batch_priority_label:209` / `ready_status_label:220` / `calendar_day_type_label:231`——**无 batch_status_label**。仓内 `batch_status_label` 仅为 `scheduler_batches.py:80` 的 viewmodel 注入参数名（喂入私有 `_batch_status_zh`），非 normalizers canonical 符号。

【对批次计划的影响】收口清单锁定 5 族；`batch_status_zh` 列入"保留私有禁收口"禁区，写进 Batch-5 R41 任务卡。

### 裁定 8.3：测试硬门——test_enum_display_consistency 钉静默断言禁贴回收口输出复活

【裁定】`tests/web_pages/test_enum_display_consistency.py` 钉死旧静默口径的断言，收口后**必须改 loud 暴露/passthrough 真口径，绝不删了重钉静默、绝不把收口输出贴回断言来"对齐"**——后者=接受静默改写复活（灵魂线击穿）。硬门，列复活红线。

【证据】_layer3_explosion.md:218（"R41 test_enum_display_consistency:59-61 钉静默断言"）+ :220（"测试改 loud 暴露禁贴回收口输出（复活硬门）"）。dossier 字段2 实测 `:59-61` 仍断言 `ready_zh("weird"/""/None)=="未齐套"`。

【对批次计划的影响】Batch-5 R41 任务卡：测试迁移序=先按 owner 裁断改断言为 loud 暴露口径→再代码收口；复活红线（禁贴回收口输出）写进 owner 闸门。

### 裁定 8.4（owner_pending=true，只标不给终态）：≥6 处语义裁断硬门，待 owner

【裁定·待owner】owner_pending=true，**暂不给终态修法/暂不分配执行批次**。爆点强调"owner 4 裁断项不变"——核准：4 项核心裁断（operator 停用/休假去留、ready 空串目标文案、空串"-"→default-label 是否可接受、unknown 透传 vs "未知"）不变，但 r2-SOUL 已把"硬门计数"展开为 ≥6 处（覆盖 machine/operator 各自的 unknown 透传去留）。给 owner 的是**选项+建议**，不写终态：

- 选项A（建议）：5 族全收口到对应 *_label，空串/未知/None 一律走 passthrough 真口径（"未知"/原值/default-label），ready 空串接受由"未齐套"→"齐套"反转。**建议**：A 最干净、消灭第二套口径，但调度员对"空 ready→齐套"的误读风险须 owner 确认是否前端加保护。
- 选项B：仅收文案全等的 machine（几乎等价），其余族保留私有，待逐族单独裁。**建议**：B 最保守、改面最小，但 P5 双口径只消一族，债基本未还。
- 反转风险点（owner 必须逐项拍）：ready 空串 未齐套↔齐套（最危险，会让调度员把未齐套批当齐套放行）、day_type/operator/machine 空串 "-"↔default-label/"未知"、operator "停用/休假"→"停用"丢"休假"、priority/ready/day_type unknown 透传 vs "未知"。

【证据】反转实锤见裁定8.1 证据行；dossier 字段7(a)-(f) 逐符号反例 + 字段12 三裁断门；_layer3_explosion.md:70/152。

【对批次计划的影响】owner 闸门=Batch-5 前硬门控（未裁不得动手）；选项/建议入 owner 裁断材料；**本裁定不分配批次执行细节**，仅转述 registry 既有 Batch-5 建议。

---

## ⑨ R69 seq=0 合法短路等价拍定 —— 爆点说 loud 化会把 seq=0 合法短路卷进 raise

### 裁定 9.1：爆点成立——seq=0 是合法短路，loud 只能动 except 域，`or 0` 兜的 None/0/空串绝不卷入 raise

【裁定】爆点**完全成立且是本债最关键约束**。`_op_seq` 体 `int(getattr(op,"seq",0) or 0)` 两层兜（getattr 默认 0 + `or 0`）把 `None/0/""` 故意映射为 0，而 guard :207 / guard :212 / runtime :217 把 `seq==0` 当**合法"无有效完成态"短路**（放空 return / 过滤排除，非错误）。P4 loud 化**只能对 `except (TypeError, ValueError)` 域内的坏类型（如 seq="abc"、不可 int 化对象）raise**；`or 0` 兜的合法 None/0/空串路径**绝不卷入 raise**，否则把合法短路翻成热路径可用性放大。

【证据】两份函数体逐字节相同（`guard:49-53` / `runtime:19-23`）：`return int(getattr(op,"seq",0) or 0)` + `except (TypeError, ValueError): return 0`。合法短路三点实测：
- `schedule_execution_persistence_guard.py:207` `if not completed_batch_id or completed_seq <= 0: return out`（seq=0→放空 return）
- `schedule_execution_persistence_guard.py:212` `if _op_batch_id(op) != completed_batch_id or _op_seq(op) <= completed_seq: continue`（seq=0→过滤）
- `schedule_input_runtime_support.py:217` `if op_id != int(completed_op_id) and batch_id == completed_batch_id and seq > completed_seq:`（seq=0→`seq>completed_seq` 恒假，正常排除）
上游清洗佐证"正常路径 except 不触发"：`batch_operation.py:24` `seq: int = 0`(typed)、`:81` `parse_int_or_default(seq, 0, field="seq")`。

【对批次计划的影响】R69 修法约束写死："loud 只动 except 域，`or 0` 兜的 None/0/空串合法路径不卷入"（_layer3_explosion.md:218）。parity 必须**两份同钉** `seq=0/None`→走短路不 raise + `seq="abc"`→loud raise（_layer3_explosion.md:219），证明 loud 化没污染合法 0 短路。

### 裁定 9.2：爆点措辞纠偏——"双热路径 :207/:262"里 :262 是 `_seed_seq` 非 `_op_seq`，不在 R69 收口范围

【裁定】爆点（_layer3_explosion.md:68/264）称"guard:207 + runtime:262 双热路径"——**:262 措辞不精确，须纠偏**。runtime `:262` 的 `completed_seq<=0` 短路用的是 **`_seed_seq`（:190 另一函数）**，不是 `_op_seq`。R69 的 `_op_seq` 消费者**只有 3 处**：guard :206/:212 + runtime :216。`_seed_seq`/`_seed_op_id` 是 R69 禁区（铁律：只动 `_op_seq` 两份，`_seed_*` 一字不碰）——r1-LB 曾误把 `_seed_*` 当 R69 漏口，r2 已推翻（_layer3_explosion.md:126/135）。loud 化的"双热路径"实指 guard 与 runtime **各自的 _op_seq 路径**（:207 短路 + :217 过滤），二者须**原子同改否则 parity 裂**——这层是对的，只是行锚 :262 张冠李戴。

【证据】`runtime:261` `completed_seq = _seed_seq(completed_seed)` / `:262` `if not completed_batch_id or completed_seq <= 0:`——消费 `_seed_seq` 非 `_op_seq`。`_seed_seq` def 实测 `runtime:190`，体 `int(seed.get("seq") or 0)`（dict 取值，与 `_op_seq` 的 getattr 不同符号）。`_op_seq` 全消费者：`guard:206/:212`、`runtime:216`（grep 实测，仅此 3 处）。

【对批次计划的影响】R69 禁区行精确化："只动 `_op_seq`（guard:49/runtime:19 两份 def + guard:206/212/runtime:216 三消费），禁碰 `_seed_seq:190`/`_seed_op_id:175` 及 runtime:261-262 短路"。批次卡纠正爆点的 :262 锚点为"`_seed_seq` 路径，非本债"，避免回炉时误把 :262 卷入 R69 改面。

### 裁定 9.3：收口家——schedule_input_contracts.py 已存在、无回指、无环，合法

【裁定】收口到 `core/services/scheduler/run/schedule_input_contracts.py` 合法：已存在文件（非新建，不触铁律5）、无 `_op_seq`、无对 guard/runtime 回指→新增 `guard→contracts` 边无环。爆点未质疑此点，确认有效。

【证据】`schedule_input_contracts.py` 已存在（4693B），grep `_op_seq|persistence_guard|runtime_support`→NONE（无符号、无回指）；runtime 既有 `:9 from .schedule_input_contracts import ...`（同收口家既有边）；tests/ 引用 `_op_seq`→NONE（无现存测试需先迁）。

【对批次计划的影响】收口落点确认 `schedule_input_contracts.py`；新增测试（坏 seq loud/降级护栏 + 单点 import 契约 + revision 过滤 parity）属修法一部分，非前置迁移。

### 裁定 9.4（owner_pending=false，给选项+建议）：loud raise vs 可观测降级，待 owner 定方向

【裁定】R69 owner_pending=**false**，可给终态方向，但"loud raise vs 保留归0+可观测降级"是 owner 设计前置（registry planned_deps_hint），给选项+建议：

- 选项A（建议，倾向 loud raise）：坏 seq（except 域）→ `raise AppError(...)`。**建议理由**：(1) 此处是 execution persistence 护栏文件，护栏内坏 seq 更应暴露而非静默归 0；(2) 上游 `parse_int_or_default`(batch_operation:81) 已清洗，正常路径 except 不触发，loud 化几乎零误伤；(3) 静默归 0 的真实危害链实锤——guard:207 短路放空 downstream 集合 / guard:212 过滤被污染 / runtime:217 `seq>completed_seq` 恒假漏排工序，护栏静默失效。
- 选项B：护栏路径 loud raise、算法路径（runtime）保留归0+补结构化 log/counter 降级标记。适用于 owner 判定算法侧坏 seq 需容忍不中断。
- 红线（两选项共有，不可破）：**绝不沿用 `except (TypeError,ValueError): return 0` 原样静默**；合法 seq=0/None/空串路径**不卷入**（见裁定9.1）。

【证据】危害链三点见裁定9.1 证据行；上游清洗 batch_operation:81；护栏文件性质（schedule_execution_persistence_guard.py）。owner_pending=false 来源 R69.md §4/§12。

【对批次计划的影响】owner 设计闸门=Batch-15 前定"收口家(已确认 contracts)+ loud 方向(A/B)"；R69 排 Batch-15 本桶第三落（R70、R68 之后），排序来自 owner 需先定方向，**非技术硬阻塞**；与 R68/R70 仅同批不同文件，无顺序硬依赖。

---

## 裁定汇总（喂 Layer4 批次计划）

| 争议 | 裁定一句话 | 批次影响锚点 |
|---|---|---|
| ⑧R41 改面 | 改面确为 6 族非 2 文件（dossier 字段8 已枚举，被低估的是 r1 窄视角）；5 族可收口、batch_status_zh 必留私有 | Batch-5（LB04 后）；owner ≥6 裁断硬门；测试禁贴回收口输出 |
| ⑧R41 owner | owner_pending=true 只标；4 核心裁断不变、展开为 ≥6 处；给选项A/B+建议不给终态 | owner 闸门=Batch-5 硬门控 |
| ⑨R69 seq=0 | 爆点成立：seq=0 合法短路，loud 只动 except 域，`or 0` 兜的 None/0/空串绝不卷入 raise | parity 两份同钉 seq=0/None 不 raise + seq="abc" raise |
| ⑨R69 锚点 | 爆点 :262 张冠李戴——那是 `_seed_seq` 非 `_op_seq`；R69 只 3 消费点(guard:206/212+runtime:216)，禁碰 _seed_* | 禁区精确化，:262 不卷入 R69 |
| ⑨R69 方向 | owner_pending=false；收口家 contracts 已确认无环；loud raise(建议) vs 降级 待 owner | Batch-15 第三落；owner 定 loud 方向，非技术阻塞 |

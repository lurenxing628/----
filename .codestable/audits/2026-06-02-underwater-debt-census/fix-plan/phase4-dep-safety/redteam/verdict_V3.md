# Layer3 回炉裁定 V3 — R54 collar 扩产前置闭合 / ⑥面 drop 集 / 第2套消费判定 / ⑪_copy 框定错位

> 裁定 agent：只读不改。所有 file:line 均当前工作区 rg 现盘（不信旧值），权威路径以 `_layer2_residual.md` 表为准。
> 承重债（R54 load_bearing=true）唯一合法修法 = 收口到已存在点 + 绑契约/parity + 「我是故意的」注释；绝不删/合并/透传裸 key。owner_pending 只标闸门、不给终态修法、不分配执行批次。

---

## 争议④ R54 collar 扩产前置闭合 —— 主裁定

### ④-A 爆点坐实：collar 当前不产三键，「裸 delegate」= 抹键 fail-OPEN

**【裁定】爆点成立、定为硬阻断前置。** collar `build_workbench_plan_context` 当前返回 dict 只 emit `is_preview`/`can_write_feedback`，**不产** is_comparison / is_superseded_by_newer_version / is_current_executable_official_version 三键，也**无 plan_resolution 入参**——因此「5 套手维列表直接 delegate 到 collar」在 collar 扩产之前 = 抹掉三键的 fail-OPEN 入口，不是收口而是制造护栏裸奔。r1/r2 假设「collar 能内部产 guard 全集」被 r3-SOUL 实读推翻，本裁定确认 r3 正确。

**【证据】当前 rg 现盘（web/viewmodels/scheduler_workbench_links.py）：**
- `def build_workbench_plan_context`:**187**，签名形参止于 `is_preview:204` / `can_write_feedback:205`，**无 plan_resolution / guard dict 入参**。
- 返回 dict 起 `return {`:**230**，键集只含到 `"is_preview": preview`:**247** / `"can_write_feedback": can_write`:**248**——**三 fail-open 键一个都不在返回 dict 内**。
- 下游放行判定 `_is_current_official_identity`（同文件，判定体 :**294-296**）：`not context.get("is_comparison")`:294 `and not context.get("is_superseded_by_newer_version")`:295 `and context.get("is_current_executable_official_version") is True`:296。
  - 前两键走 `not <truthy>` = **fail-OPEN**：键缺失 → `context.get` 为 None → `not None` = True → 不拦。
  - 第三键走 `is True` = **fail-CLOSED**：键缺失 → None ≠ True → 拦（反向安全）。
- 二次复用同 guard：`can_emit_feedback_write_urls`（同文件 :472-473 读 can_write_feedback/can_dispatch），及 `is_superseded_by_newer_version` 在 :**369** 另有消费。

**【真相源已现成、可作 collar 内部数据源】** `core/services/scheduler/schedule_result_view_context.py`：
- `default_plan_resolution_dict`:**73**，给 fail-CLOSED 默认 `is_current_executable_official_version: False`:**94** / `is_superseded_by_newer_version: False`:**95** / `is_current_executable_version: False`:93。
- 全键投影体 :101 起，含 `is_comparison`:**129**（经 `is_comparison_plan(...)` 函数重算）/ :179 第二处重算。
- 旁路真相源 `PlanIdentity.to_dict`（core/models/schedule_plan_identity.py:**46**）亦产三键：`is_current_executable_version`:65 / `is_current_executable_official_version`:**66** / `is_superseded_by_newer_version`:**67**。

**结论**：「collar 扩成 3 键 guard 产出点（走 view_context fail-CLOSED 默认）」必须立为**独立承重前置改动、单独过 owner 审**，先于任何「delegate」动作。这是争议④的核心定论。

### ④-B 安全路径选项 + 建议 + owner 闸门

题面两条候选路径：(I) 先扩 collar 产出全键（从 plan_role_filter_fields / PlanIdentity.to_dict 取）再 delegate；(II) 各面保留本地源、只加 parity 钉同步。逐条拍：

**选项 I — collar 扩产为唯一 guard 产出点 + 6 面 delegate（彻底收口）**
- 做法：给 collar 加 plan_resolution/guard dict 入参，内部从单一来源 `plan_role_filter_fields`（含 `default_plan_resolution_dict` 的 fail-CLOSED 默认）产三键全集写进返回 dict:230-248；6 个手维面全部改为读 collar 输出，删各自私有列表与手映射。
- 优点：根除 split 结构，未来单改一处不再静默失护栏；键集来源单一可注释钉死。
- 代价/风险：collar 扩参与 R42（删 plan_id 形参 :191 + dict 键 :231）/R60 强撞，MUST 同批次；6 面 delegate 须逐面迁契约测试同 commit；新旧两路边界值须逐键四态 parity（{缺失/None/False/True}×拦放）钉死，尤其 L5 `is_comparison_plan` OR 兜底（gantt_task_detail:98）与 view_context 函数重算的「源键 True 但重算 False」分叉。

**选项 II — 各面保留本地源 + 只加 parity 钉同步（不收口）**
- 做法：不动 collar，6 面各保留手维列表，新增一套 parity 测试断言 6 面键集恒等。
- 优点：改动面小、不撼 collar 签名、规避 R42/R60 同批次互锁。
- 致命缺陷：**违 P5 收口铁律**——split 结构本身就是 fail-open 风险根因（任一面单改即静默失护栏），parity 测试只能在 CI 抓「已经改歪」的回归，挡不住「新增第 7 面忘了同步」「运行期某面被绕过」；且 6 面源键命名两套（L1/L3 从原始 plan_resolution 手映射改名 vs L2/L4/L6 取已命名键过滤），parity 要钉的等价关系本身脆弱。本质是把承重护栏的正确性长期托付给「人记得同步」。

**【建议】采选项 I，但拆成两段闸门、严禁一步到位。**
- 第 1 段（独立承重前置，必须先过 owner 审）：**只扩 collar 成 3 键 guard 产出点 + fail-CLOSED 默认 + 契约测试**，此段 collar 同时产新键、6 面仍读各自旧源（双跑），不删任何手维列表。这一段把「collar 能产键」这件被 r1/r2 误判的事实先做实、可对账。
- 第 2 段（收口 delegate）：契约/parity 落地后，6 面逐面改读 collar 输出、删本地列表，删列表与改测试同 commit（无护栏裸奔窗口）。

**【owner 闸门】（owner_pending=true，只标不给终态）：**
1. **F 门-1 修法形态**：collar 加「plan_resolution 入参」vs 加「接收 guard dict 入参」——两种入参形态由 owner 裁，未裁不进执行批次。
2. **F 门-2 批次冲突**：R54↔R42 deps 判「必须同批次」（同改 collar 签名/dict），但 batch_hint 把 R42 列 Batch-3、R54 列 Batch-2——内部张力，owner 在 Layer4 总计划裁：R42 提前与 R54 合批，或 R54 延后到含 R42 的批。**不擅自定终态。**
3. **F 门-3 语义取舍**：源键改名双键并存（如 `requested_role` 与 `requested_plan_role` 同在）时取值口径，及旧路「缺键静默不写 fail-open」是否一律替换为收口点 fail-CLOSED 默认——owner 逐键拍。

---

## 争议⑥ guard 第6面 `_PUBLIC_FILTER_DROP_KEYS` 纳入 R54 收口面清单口径

**【裁定】纳入 R54 收口面清单，但定性为「键集独立手维面，机制 ≠ guard 投影，禁当第 7 套 guard 去并/收口 delegate」。** 它是脱敏 drop 集（决定哪些键不暴露给公开 filters），不是 guard 投影（决定护栏拦放）。R54 统一 guard 时若误把它当同类 guard 面并入收口或漏同步，会导致**公开 filters 漏脱敏/误删内部键**。正确口径：列入清单做「同步纪律对象」（R54 改三关键键命名/键集时须同查此 drop 集是否需跟随），而**不**做 delegate 收口。

**【证据】rg 现盘（web/viewmodels/scheduler_resource_dispatch.py）：**
- `_PUBLIC_FILTER_DROP_KEYS = {`:**40**，消费点 `_public_filters`:**269-270** `return {key: value for key, value in filters.items() if key not in _PUBLIC_FILTER_DROP_KEYS}`:270。
- 集内含三关键键 `is_comparison`:**68** / `is_superseded_by_newer_version`:**71**，及 L1-L5 各 guard 列表都**没有**的独立成员：`schedule_result_status`:**63** / `is_current_executable_version`:**69**（注意是 `_version` 非 `_official_version`）/ `scenario_name`:**72**。
- 题面给的旧锚点 `:40-73` 现盘为 drop 集字面区间，准（集合从 40 起，成员散布到 72，闭合在 73 行附近）。

**【为何不能并入 guard 收口】** 此集的语义是「输出脱敏」，与 guard 投影「拦放判定」是两套机制；二者键集**交叠但不相等**（drop 集独有 schedule_result_status/is_current_executable_version/scenario_name）。若 R54 以「统一 guard 键名」为由动这三关键键的拼写，drop 集这一面必须**手工跟随核对**，否则脱敏漏键（内部键泄到公开 filters）。这是「同步纪律」不是「收口 delegate」。

---

## 争议（第2套）superseded/comparison 消费判定纳入收口面清单口径

**【裁定】纳入清单，但定性为「下游消费/展示判定面，禁 delegate 收口、禁与 guard 投影合并」。** 题面给的 `:148-194` 区间在 resource_dispatch 内是一组**读 filters 的 guardrail 文案/分类标签函数**（消费侧），不是手维 key 列表（投影侧）。R54 收口动的是「谁产 guard 字段」，这组是「谁读 guard 字段」——读端只能跟随键名变更同步，不能被「统一」掉。列入清单做禁区/同步对象。

**【证据】rg 现盘（web/viewmodels/scheduler_resource_dispatch.py，:148-194 区间内全是消费函数）：**
- `_has_unexecutable_result`:**148**（读 filters 判不可执行）。
- `_official_kind_label`:**152**：`if filters.get("is_superseded_by_newer_version")`:**153** → 区分「历史/被取代」文案。
- `_public_plan_kind_label`:**161**：`if filters.get("is_comparison")`:**166**。
- `_official_guardrail_text`:**172**：`if filters.get("is_superseded_by_newer_version")`:**173**。
- `_public_plan_guardrail_text`:**180**：`if filters.get("is_comparison")`:**190**。
- `_public_plan_identity`:**196**（汇出公开身份 dict）。
- 另该文件 :124 `_public_plan_view_label` 内亦读 `is_comparison`:124。

**【口径】** 这些消费点用 `filters.get(key)`（truthy）读三关键键——若上游某投影面漏产该键，这里读到 None/缺失即走「非历史/非比较」文案分支 = **展示侧也 fail-OPEN**（把旧/比较版的护栏文案误显示为正常）。因此它们是 R54 fail-OPEN 灾难链的**展示侧延伸**，必须：(a) 列入「键名变更同步对象」（R54 改键名时这 6 处读点同步）；(b) 列入禁区（不得为「统一」把这些 `filters.get` 改成依赖 collar 内部状态而绕过 filters 透传）。**不做 delegate 收口**——它们消费的是 filters 流，不是 guard 产出点。

---

## 争议⑪ `_copy` 非卡口框定错位修正

**【裁定】框定错位成立，回写修正：`_copy_critical_chain_result:104` 不是 strip 卡口，是天然保留新键的整体浅拷，禁列为「会丢键须补」点，且列为禁删/禁动禁区。** GANTT 簇真卡口只有两道：**单份 `_normalize`（必改）** + **contract unavailable 分支（须补）**；`_copy` 非卡口、contract 透传分支不卡。簇计划/dossier 反复称「_copy 会丢须补」是错误框定，会让 review 把注意力放错，且越改 _copy 越接近误删（它服务于多处缓存浅拷）。

**【证据】rg 现盘（core/services/scheduler/gantt_critical_chain_provider.py）：**
- `def _copy_critical_chain_result`:**104**，首行 `out = dict(result or {})`:**105** —— **整体浅拷**，任何新增键自动随 `dict()` 进入 out，**天然保留**，不是逐字段白名单拷贝，故结构上**不可能** strip 掉新键。
- 其后只对 `ids`/`edges`/`edge_type_stats`/`reason_code` 做容器深拷规整（:106-109），**不删任何键**。
- 该符号被别名 `ln(` 遮蔽（rg `def _copy_critical_chain_result` 在 grep 输出里显示为 `ln(...)`），与 R03/R42 的 `n(`/`ln(` 别名遮蔽同源——这正是过往「rg 零命中以为禁区失踪」的来由，需按符号/按首行 `dict(result)` 特征定位，不按别名。

**【修正口径】** GANTT 收口 review 的注意力应钉在：(1) 两份 `_normalize` 收口去重时的 `available=0→True` + `bool()` 包裹差异（须先建 normalize parity 黄金基线）；(2) contract unavailable 分支须补默认。`_copy_critical_chain_result:104` **禁动**（6 处缓存浅拷在用，误删/改成白名单拷贝会丢新键或破坏缓存隔离），列入承重禁区按符号定位。

---

## R54 收口面清单（最终拍定：6 投影面 + 真相源 + 收口点 + 下游判定）

> 行号 rg 现盘；以下「面」分三类——**投影面**（可 delegate 收口）/ **同步面**（禁 delegate，键名变更须跟随）/ **禁区面**（禁动方向）。

| # | 面 | 文件:line | 类别 | 收口口径 |
|---|----|-----------|------|---------|
| L1 | `_copy_plan_guard_fields`(mapping 形) | scheduler_reports_workbench.py:36 / call 98 | 投影面 | delegate 到 collar 输出，删本地手映射 |
| L2 | `_PLAN_GUARD_FIELD_NAMES` 元组 | scheduler_navigation_publish.py:12 / `_publish_context`:85 / call 109 | 投影面 | delegate；改时禁碰 R58 承重段 |
| L3 | `_copy_plan_guard_fields`(元组 forloop 形) | scheduler_resource_dispatch.py:64 / call 109,199 | 投影面 | delegate，删本地列表 |
| L4 | `_PLAN_GUARD_FIELD_NAMES`(report 漏列第4套) | dashboard_workbench_context.py:8 / apply 130-132 | 投影面 | **必须含**，漏迁=收口不彻底（残债） |
| L5 | `is_comparison_plan` OR 兜底 | scheduler_gantt_task_detail.py:13(别名元组) / :98 `bool(...or data.get("is_comparison_plan"))` | 投影面+反例源 | delegate；parity 必覆盖「源键 True 但 view_context 函数重算 False」分叉 |
| **L6** | `_PUBLIC_FILTER_DROP_KEYS` 脱敏 drop 集 | scheduler_resource_dispatch.py:40-73 / 消费 :270 | **同步面（禁 delegate）** | 含三关键键 + 独有 schedule_result_status:63/is_current_executable_version:69/scenario_name:72；改三关键键命名须手工跟随核对，禁当第7套 guard 并入 |
| 消费 | superseded/comparison 展示判定 6 处 | scheduler_resource_dispatch.py:153/166/173/190 + 124 + `_public_plan_identity`:196 | **同步面（禁 delegate）** | 读端 filters.get 透传，键名变更同步；禁改成绕 filters |
| 收口点 | `build_workbench_plan_context`(collar) | scheduler_workbench_links.py:187 / return dict 230-248 | **扩产点** | 当前不产三键，须先扩成 guard 产出点（fail-CLOSED 默认） |
| 真相源 | `plan_role_filter_fields` / `default_plan_resolution_dict` / `PlanIdentity.to_dict` | view_context.py:73/101/129 + schedule_plan_identity.py:46/65-67 | 数据源 | collar 内部从此取全键 |
| 下游闸 | `_is_current_official_identity` 判定方向 | scheduler_workbench_links.py:294-296 | **禁区面** | `not <truthy>`(294/295 fail-open) + `is True`(296 fail-closed) 方向禁翻 |
| 禁区 | view_context fail-CLOSED 默认值 | view_context.py:93-95 | **禁区面** | is_superseded=False/is_current_executable_official_version=False 方向禁改 |
| 禁区 | `_copy_critical_chain_result`(GANTT 框定错位) | gantt_critical_chain_provider.py:104-105 | **禁区面** | 整体浅拷非 strip，禁动（见争议⑪） |

**面数总账**：可 delegate 投影面 = **5（L1-L5）**；同步面（禁 delegate）= **2（L6 drop 集 + superseded/comparison 消费判定）**；扩产点 1 + 真相源 1 + 禁区 3。题面「5 套 delegate」指的是 L1-L5；L6 与消费判定**不在 delegate 之列**，是本裁定新拍定的同步纪律面。

---

## 对批次计划的影响汇总（前置/顺序/禁区/owner 闸门）

**改前置：**
- 新增独立承重前置「collar 扩成 3 键 guard 产出点 + fail-CLOSED 默认 + 契约测试」，**必须先于** L1-L5 任何 delegate 动作；此前置单独过 owner 审（F 门-1 修法形态）。
- 删任一手维列表**前**，其对应契约测试须先改读 collar 输出，删列表与改测试同 commit（无护栏裸奔窗口）。

**改顺序：**
- R54↔R42↔R60 同改 collar 签名/dict，**MUST 同批次**（owner 裁 batch_hint Batch-2 vs deps 同批的张力，F 门-2）。
- R58→R54→R44 同 nav_publish 文件硬序；R54 guard 收口 + 契约测试落地后 R44 才能动且不得碰 L2 `_PLAN_GUARD_FIELD_NAMES`(:12)。
- 若 R22 改真相源 `plan_role_filter_fields`(view_context:101-179)，须先于 R54 delegate（目标稳定后再 delegate）。

**改禁区（新增/确认）：**
- 新增 L6 `_PUBLIC_FILTER_DROP_KEYS`(:40-73) 为同步面（禁 delegate）；新增 superseded/comparison 消费 6 处(:153/166/173/190/124/196) 为同步面。
- 确认禁区：collar 判定方向(:294-296)、view_context fail-CLOSED 默认(:93-95)、`_copy_critical_chain_result:104-105`（框定错位修正：禁动、非卡口）。

**owner 闸门（owner_pending=true，只标不分配执行批次）：**
- F 门-1：collar 加 plan_resolution 入参 vs 加 guard dict 入参。
- F 门-2：R42 与 R54 合批方案（提前 R42 / 延后 R54）。
- F 门-3：源键双键并存取值口径 + 「缺键静默不写」是否一律替换为 fail-CLOSED 默认。

**parity 必覆盖矩阵**：三关键键（is_comparison / is_superseded_by_newer_version / is_current_executable_official_version）× 四态（缺失/None/False/True）× 拦放结果，收口前后逐键完全一致；额外覆盖 L5「源键 True 但函数重算 False」、reports 第二注入路径阻断态、L6 drop 集脱敏键集恒等。

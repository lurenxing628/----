# 逐簇爆炸对抗 r1 — 簇 C-GANTT（灵魂线+收口等价透镜）

> skeptic 第1轮，只读不改。默认怀疑。回盘日 2026-06-05，行号已 rg 复核当前工作区。
> 成员：R10 / R11 / R12 / R55 / R63。主透镜 Q4(灵魂线热路径)/Q5(收口逐分支等价)/Q6(测试迁移序)。
> 主文件：gantt_service.py / gantt_service_support.py / gantt_critical_chain.py / gantt_critical_chain_provider.py / gantt_contract.py

---

## 0) 本轮回盘锚点（全部现场 sed 命中，与计划/dossier 对账）

| 锚点 | 真实 file:line | 与计划是否一致 |
|---|---|---|
| R10 死方法 `get_latest_version_or_1` | gantt_service.py:60-62 | ✅ |
| R10 活方法 `resolve_version`（禁触） | gantt_service.py:64-69 | ✅ |
| R10 stub | regression_scheduler_week_plan_summary_observability.py:59-60 | ✅，零调用（grep EXIT=1） |
| support `_normalize` def / 调用 | gantt_service_support.py:32-51 / :58 | ✅ |
| provider `_normalize` def / 调用 | gantt_critical_chain_provider.py:113-137 / :180 | ✅ |
| provider `_copy_critical_chain_result` | gantt_critical_chain_provider.py:104-110 | ✅ |
| R12 `:84` 裸 continue（`_build_nodes`:79） | gantt_critical_chain.py:84 | ✅ |
| R12 注入点 return dict | gantt_critical_chain.py:328-334 | ✅ |
| `_empty_result`（无 dropped_count） | gantt_critical_chain.py:54-63 | ✅ |
| sort / max（删 :84 即 None 流入） | gantt_critical_chain.py:114 / :262 | ✅ |
| R55 filters 构造 / 调用 / None 回退 | gantt_service.py:344 / :384 / :385-389 | ✅ |
| contract `_public_critical_chain` | gantt_contract.py:19；available=False 分支 :22-39；`return raw` :40 | ✅ |
| parity 黄金基线测试 | **不存在**（确认 ls 落空） | ✅ 与计划一致 |

---

## 1) 逐成员判定

### R10（独立死方法删除）— 🟢 绿（安全）

- **证据**：`get_latest_version_or_1` 全仓零调用（`rg ... | rg -v "def "` EXIT=1，callgraph 0 入边）；活方法 `resolve_version`(gantt_service.py:64) 现场在，与死方法 :60-62 物理隔离；stub:59 零 invoke。纯删除不新增 import/兜底，0 越层，无 P4 诉求。
- **Q4 灵魂线**：纯删，不落热路径、不新增兜底。✅
- **唯一操作精度禁区**：按 :60-62 行号精删，删后立即 `grep "def resolve_version"` 复核 :64 仍在（名字相近，误删即静默炸周计划版本解析）。计划 §D 禁区行 #8 已覆盖。
- 结论：**安全可做，与 A1/A2/A3 逻辑零重叠，同 PR 任意顺序。**

### R11 ≡ R63（A1 抽单份 `_normalize`）— 🟡 黄（有条件：先建 parity 黄金基线 + 保留 `bool()` 包裹 + 禁 `return raw`）

- **证据·两份逐字段等价已复核**：support:32-51 与 provider:113-137 九键逐字段语义等价；唯一微差 support `bool(is_available)`(:48 显式包裹) vs provider 裸 `is_available`(:134)，当前两路 `is_available` 已是 bool 故运行时等价。
- **Q5 收口逐分支反例（必钉死，否则静默放宽）**：
  - `available=0`：`isinstance(0,bool)=False` → 现行两版均 `is_available=True`；若收口手滑写 `bool(available)` → `bool(0)=False`，**静默把"available 缺省真"翻成 False**。这是本簇最隐蔽的等价陷阱（与 R09 C 路 5.9→None 同形：收口时一个真值语义被悄悄改）。parity 必覆盖 `available=0` / `available="yes"`。
  - `reason_code` 归一层**不得**提前 clamp 白名单——真正白名单收敛在下游 contract:32-34（`not in _ALLOWED → "unknown"`）。收口若顺手在归一层 clamp = 改两阶段职责。
- **Q4 灵魂线热路径**：`gantt_service_support.py:58 return _normalize_critical_chain_result(raw)` 是 support 路径**唯一补默认点**。**禁改 `return raw`**（raw 缺 available/edge_type_stats 默认 → `collect_gantt_degradation_events`(support.py:71，现场确认读 `critical_chain.get("available") is False` + reason_code) 判 available 失效 → 降级该报不报=灵魂线违规）。这是 P5 去重，不得借机加兜底。
- **条件**：(1) 动手前先建 `regression_gantt_critical_chain_normalize_parity.py`（当前不存在），对**当前两副本**断言逐键等价做黄金基线——无 parity 不得收口（计划 §D F门）；(2) 收口取 support 的 `bool()` 写法或合并补上；(3) R11 owner_pending=true，终态以 R63（owner_pending=false 给终态）修法为准合并单 work-item。
- 结论：**条件满足即安全。禁拆两人各改一份副本（会撞改 support.py+provider.py 同两段、悬空调用）。**

### R12（A2 加 dropped_count/critical_chain_partial）— 🟡 黄（有条件：A1 必先 + 保留 :84 过滤 + 穿真正的卡口 + _empty_result 同补键）

- **证据·:84 过滤是刻意韧性，禁删**：现场 `if not st or not et or not (st < et): continue`。删它 → None 流入 :114 `items.sort(key=...x.get("start"))` / :262 `max(...key=x.get("end"))`（`None < datetime` → TypeError）→ 被 :338-341（出口A `compute_critical_chain_from_rows` try/except → `_unavailable_result("rows_exception")`）或 :352-359（出口B）接住 → **整链 available:False 功能回归**（把"丢一行仍出链"砍成"一行坏数据全链不可用"）。计划判定正确，禁区行 #6 成立。
- **Q4 灵魂线（本债病理 P4）**：:84 静默丢坏行 + 结果 dict(:328-334) 无降级标记 → 经归一 `available` 默认 True → 用户看 available:True 以为完整。**正确修法=补可观测降级标记（DegradationCollector 范式，照搬 gantt_tasks.py:192-196），不是加兜底、不是 raise 整链**。P4 此处选"丢行+留痕"，符合灵魂线。
- **自相矛盾反例（计划已抓，现场坐实）**：全坏行 → `_build_nodes` 返回空 nodes → :314 `if not nodes: return _empty_result()`；而 `_empty_result`(:54-63) **现场确认无 dropped_count 且 available:True** → 最该报警的"全是坏行"场景反而零信号。**修法必须同时给 _empty_result 带 dropped_count**，否则补了等于没补。
- **条件**：(1) **A1 强前置**——R11/R63 未先合并，R12 加键要改 provider:127 + support:43 两副本=复活 P5（Phase1 边 R11→R12 成立）；(2) scope/键名取关键链专属（`gantt.critical_chain`，勿混 gantt_tasks 的 `gantt.tasks`）；(3) 穿真正卡口（见漏项 ②）。
- 结论：**A1 落地后单点加键 + _empty_result 同补，安全。倒序（先 R12 后 R11）= 复活 P5。**

### R55（A3 加 scope=filtered/full）— 🔴 红（owner 门控未过 + 灵魂线反推陷阱 + None 回退禁区，本轮不得落终态 patch）

- **证据·债活**：四关键链文件 grep `scope.*filtered|'scope'` 零命中，scope 标记确不存在；`critical_chain_for_plan_detail_filter`(support.py:54-58) 把"周窗口+资源子集"rows 喂进 `compute_critical_chain_from_rows`（算法契约 gantt_critical_chain.py:347 明写"全量排程不按周截断"），子集 makespan 经同一 `_normalize` 以 available:True 对外，无 scope → 前端 gantt_legend.js:185 `summaryItem("完工", makespanEnd)` 用户读成整版完工。呈现失真真实。
- **为何红（多维度存疑）**：
  1. **owner_pending=true + needs_adversarial=true + registry verdict=null**。PHASE0 §6 三问（None 回退是否有意 / 裸删 vs 补标记 / 当下债 vs 在途态）**未过怀疑者+owner 门**。计划 §A3/§E 自己声明"终态修法待 owner+怀疑者复核，不锁终态 patch"。本轮 skeptic 复核：**门未过，不得落地终态写法**——这是红的核心，不是修法本身错，是**流程门未通过却被排进可执行 A3**。
  2. **灵魂线反推陷阱（Q4）**：若有人图省事在 helper 里靠"filters 空否"反推 scope=filtered/full = 静默推断违灵魂线，且 provider full 路径(get_critical_chain:143，现场确认 `*` 后仅 plan_resolution/plan_query_service，**无 filters 上下文**)反推必错。scope 必须由调用点显式赋值（support:54 显式 'filtered'、provider:143 default 'full'）。
  3. **None 回退禁区（Q5 边界）**：`critical_chain is None`(gantt_service.py:385) → 回退 provider full，是灵魂线"有意降级"。`if not filters: return None`(support.py:55-56) 是 filtered/full 分流判据。scope 修法若动这两处=破坏分流，**禁动**。
- **裸删红线**：严禁裸删 filtered 过滤逻辑（裸删=把 filtered 视图改成整版，反砍业务=违灵魂线"不补反砍"）。
- 结论：**本轮标红——分析已透但 owner/怀疑者门未过，A3 终态 patch 不得进本批；待门过后降黄。**

---

## 2) 漏项（本轮新发现，计划未覆盖或框定不准的爆点）

① **【计划框定失真，但偏保守】"三道白名单"过计数——`_copy_critical_chain_result`(provider:104-110) 不是 strip 点**。现场坐实其首行 `out = dict(result or {})` **整体浅拷所有键**（包括未来 scope/dropped_count/critical_chain_partial 都会被 dict() 带过去），只对 ids/edges/edge_type_stats/reason_code 四键重设。**故 A3 禁区行 #3「_copy 会丢 scope 须补」、A2「穿 _copy」是误判**——_copy 天然保留新键，无需补。真正的 rebuild-from-scratch 卡口只有**两个**：(a) 两份 `_normalize`（support:43-51 / provider:127-137 显式重建 dict），(b) contract `_public_critical_chain` 的 `available is False` 分支(:24-39 固定 5 键 build，**会吞 scope/dropped_count/partial**)。contract:40 `return raw` 透传分支保留新键。后果：按计划"补 _copy"是写冗余无害代码（不炸），但**框定错误会让 review 把注意力放错**——真正必须盯死的是「available=False 时 partial/scope 也要在 contract:24-39 合理保留/置默认」，这正是 R12/R55 partial-but-unavailable 组合态最易漏的一道。建议修正计划：白名单从"三道"改为"两道真卡口（_normalize×1收口后 + contract available=False 分支），_copy 非卡口"。

② **【R12 真正风险点被 §7 待填掩盖】R12 dossier §7「收口行为差异」有两个重复小节、第二个标"（待填）"**——本轮补全核心反例：R12 加键唯一会被吞的路径是 **available=False 时走 contract:24-39**。即"丢了坏行(partial=True) 但链仍 available=True"走 :40 透传（partial 活）；但"全坏行→_empty_result→若后续被判 unavailable"或"算法异常→_unavailable_result→available=False"时，partial/dropped_count 在 contract:24-39 被吞。**最该报"全坏行"的场景恰好落 available=False 分支被吞**——与 ① 的 contract 卡口叠加，是 R12 的真盲区。修法须在 contract available=False 分支显式保留 dropped_count/critical_chain_partial。

③ **【边级已 raise vs 节点级静默 的政策不对称，计划仅作"依据"未作"风险"】** 现场确认 `tests/regression_gantt_critical_chain_unavailable.py:215-248` 断言 `_choose_control_prev` 对边级时间异常**已 raise ValueError"时间字段缺失"**。而该 raise 被 `_compute_critical_chain_from_loaded_rows` 的外层 `compute_critical_chain*` try/except(:338/:352) 接住 → `_unavailable_result`。即**边级 loud raise 最终也降成 available:False**（loud 在内层、catch 在外层）。R12 在节点级补"丢行+留痕"后，系统出现两种坏行政策：节点级=partial 旁路标记仍 available、边级=raise 整链 unavailable。**二者并存不矛盾（节点级是"个别坏行可容忍"、边级是"链结构断裂不可信"），但 review 必须确认 R12 不把节点级也改成 raise**（那会和 :84 删除一样触发整链回归）。计划 §4 禁区行已禁碰 :338-341/:352-359，本项确认该禁区充分。

④ **【测试迁移序 Q6】R10/R11/R63 删旧符号前先迁测试——现状友好但需显式确认**：`rg "_normalize_critical_chain_result" tests/` = 0 命中（无直引/mock），删 staticmethod 不断测试直引点；R10 stub 零 invoke 可直删。**但 parity 黄金基线测试(`regression_gantt_critical_chain_normalize_parity.py`)必须先于 A1 收口建立**，否则 `available=0` 静默放宽（漏项①陷阱）无网可兜——这是本簇唯一的"测试序硬前置"。snapshot 测试(:122 subset 检查)**抓不到字段分叉**（加键不红、内层分叉不红），不能当去重正确性证明，正确性只靠 parity。

⑤ **【A2/A3 同改 _normalize 的协同未明确 _empty_result 路径】** R12 的 dropped_count 要落 :328-334 注入点 **+ _empty_result(:54)**，而 R55 的 scope 落 _normalize；但 _empty_result(gantt_critical_chain.py:54) 与 _unavailable_result(:71) **不经 _normalize**（它们是 compute 层早返回，直接进 build_gantt_contract 流，support 路径经 :58 _normalize 但 provider full 路径 _empty_result 的 raw 也会过 :180 _normalize）。需确认：_empty_result 产物经 _normalize 时，dropped_count 若加在 _empty_result 而 _normalize 不认该键 → 被 _normalize 重建 dict 时剥离。**即 R12 加 dropped_count 必须同时在 _normalize 的白名单 dict 里认这两个键**，否则"全坏行"信号加在 _empty_result 也会被下游 _normalize 吞掉。这是 ① 卡口与 R12 _empty_result 的交叉盲区，计划 §A2 提到"_empty_result 须带 dropped_count"但未串到"_normalize 必须同认键否则白加"。

---

## 返回串

C-GANTT/SOUL/r1 | 🔴 R55(A3 scope):owner_pending+needs_adversarial+verdict=null 三门未过却排进可执行→灵魂线反推陷阱(provider full 无 filters 上下文反推必错)+None 回退禁区(gantt_service:385/support:55-56)若被动则破坏 filtered/full 分流→失真换形式复发,本轮不得落终态 patch | 🟡 R11≡R63(A1):须先建 parity 黄金基线钉死 available=0 陷阱(收口手滑写 bool(0)=False 静默放宽真值语义)+保留 support bool() 包裹+禁 support:58 改 return raw(否则 collect_gantt_degradation_events 判 available 失效降级该报不报); R12(A2):A1 强前置(否则改两副本复活 P5)+保留 :84 过滤(删则 None→sort/max TypeError→整链 available:False 回归)+_empty_result 与 _normalize 必须同认 dropped_count 键否则全坏行信号被吞 | 🟢 R10:零调用死方法纯删,删后 grep 复核 resolve_version:64 在 | 漏项: ①计划"三道白名单"过计数——_copy(:104)首行 dict(result) 整体浅拷,天然保留新键,非 strip 点;真卡口仅 _normalize+contract available=False 分支(:24-39),补 _copy 是无害冗余但框定错位 ②R12 真盲区在 contract available=False 分支吞 partial/dropped_count(全坏行恰落此分支),须显式保留 ③边级已 raise 但被外层 try/except 降 available:False,确认 R12 勿把节点级也改 raise ④parity 测试是本簇唯一测试序硬前置,snapshot subset 抓不到字段分叉 ⑤_empty_result 加 dropped_count 须同步进 _normalize 白名单否则被剥离

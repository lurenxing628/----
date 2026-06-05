# 逐簇爆炸对抗 · 第2轮 · 簇 C-GANTT（灵魂线热路径透镜）

> skeptic r2，只读不改，默认怀疑。主透镜：灵魂线热路径 + 收口逐分支等价（Q4/Q5/Q6 为重）。
> 成员债 R10 / R11 / R12 / R55 / R63。行号全部 2026-06-05 rg 当前工作区回盘，不信旧值。
> 找不到爆点才算绿；多维度存疑即标红。

## 回盘锚点（当前工作区，全部命中）

| 锚点 | 真实 file:line | 说明 |
|---|---|---|
| R10 死方法 `get_latest_version_or_1` | gantt_service.py:60 | 活方法 `resolve_version`:64（邻接，禁误删） |
| R10 stub 镜像 | regression_scheduler_week_plan_summary_observability.py:59 | def 无调用 |
| R11/R63 support `_normalize` def/调用 | gantt_service_support.py:32 / :58 | 显式重建 dict（return {...}） |
| R11/R63 provider `_normalize` def/调用 | gantt_critical_chain_provider.py:113 / :180 | staticmethod，显式重建 dict |
| `_copy_critical_chain_result`（禁误删） | provider:104，调用 :157/:184/:188/:192/:196/:199 | `out = dict(result or {})` 先整拷再覆写 4 键 |
| R12 :84 过滤 | gantt_critical_chain.py:84 `if not st or not et or not (st < et): continue` | 受害 sort :114(`x.get("start")`) / max-via _sink_id :261-262 |
| R12 注入点 | gantt_critical_chain.py:312，return dict :328-334（**仅 5 键，无 available**） | available 是 `_normalize` 补的 |
| R12 空路径 | `_empty_result`:54（**available:True** @:61）/ `_unavailable_result`:71 | 走 :315 另一条 return |
| R12 出口吞错 | compute_critical_chain_from_rows:337（try/except :338-341）/ compute_critical_chain:344（:352-359 两段 try） | 裸删 :84 后 TypeError 落这里 |
| R55 病灶 | gantt_service.py:344(filters)/:384(调用)/:385 None回退→:386 provider full | :471 是 task-detail 路径，非本病灶 |
| R55 None分流判据 | support `critical_chain_for_plan_detail_filter`:54-58（`if not filters: return None` :55-56） | 灵魂线有意降级 |
| contract `_public_critical_chain` | gantt_contract.py:19；unavailable 硬build :22-39；`:40 return raw` 透传 | 卡口分层 |
| parity 测试 | tests/regression_gantt_critical_chain_normalize_parity.py | **不存在**（收口安全门未建） |

---

## 逐成员判定

### R10 —— 🟢 绿（安全直删）

- **修法**：纯删 gantt_service.py:60-62 死方法 + stub:59-60。owner_pending=false。
- **Q1 承重误删**：lb=false，无承重不对称可抹。✅
- **Q2 分层环**：纯删不新增 import，0 越层。✅
- **Q4 灵魂线热路径**：纯删除，不新增兜底/静默/吞错，无 P4 loud-raise 诉求。死方法 `return v if v>0 else 0` 的名实矛盾（名 `_or_1` 实返 0）随删消失，**不在任何热路径**（callgraph 0 入边、rg 0 调用，已第2轮独立复跑 `rg get_latest_version_or_1 core/ web/ data/ | rg -v "def "` EXIT=1 思路核对）。✅
- **Q5 收口等价**：非收口，N/A。
- **Q6 测试迁移序**：删 stub:59-60 即可，stub 实际被断言的是 resolve_week_range/get_week_plan_rows，删它不牵连。✅
- **唯一操作精度禁区**：删 :60-62 后立即 grep 复核 `def resolve_version`:64 仍在（相邻活方法，名字也含 version，被 scheduler_gantt.py:187 `svc.resolve_version` 真实消费）。误删即静默炸周计划版本解析——这是**操作精度**风险非计划缺陷，计划已覆盖。
- **判定**：绿。无爆点。

### R11 ≡ R63 —— 🟡 黄（有条件可做：parity 黄金基线为硬门）

- **修法**：抽单份 `_normalize_critical_chain_result` 到已存在落点 gantt_critical_chain.py，support:58 / provider:180 两路改调它。R11 owner_pending=true / R63 owner_pending=false，合并单 work item。
- **Q4 灵魂线热路径（主透镜核心）**：第2轮逐字读两份实体确认**逐字段等价**，唯一微差 support `bool(is_available)`（:49 显式包裹）vs provider 裸 `is_available`（:134），运行时两路前置分支已保证 bool，等价；**收口必须取 support 的 `bool()` 写法**（防未来上游 available 漏成非 bool 时 support 路径丢防御）。本债 P5 去重，**不改 loud raise、不新增兜底**——符合灵魂线不放大。✅
- **Q5 收口逐分支等价（主透镜核心，黄的根因）**：两份对 `available=0` 均走 `else True`（`isinstance(0,bool)` False），收口若手滑写 `bool(available)` 会把 `0→False`、`"yes"→True` 双向破等价 → **静默放宽语义**（available=0 现得 True，bool() 写法得 False，关键链可用性翻转）。这是收口最易踩的静默坑。**必须先建 parity 黄金基线测试**（5 类边界：`{}`/非dict/`available=0`/`available="yes"`/`available=False`无code），钉死 `available=0→True` 与 `bool()` 包裹差异，**无 parity 不得收口**。parity 测试当前不存在（已 ls 确认），此门未建即动 = 红。
- **Q4 灾难链（若违红线）**：误删 support 份并把 :58 改 `return raw` → support 路径（有 detail_filters 的甘特）payload 缺 available/edge_type_stats 默认 → `collect_gantt_degradation_events`（support:65-68 读 `critical_chain.get("available") is False`/reason_code）判 available 失效 → 降级该报不报（**静默，灵魂线违规**），白名单 :40 `return raw` 把非归一 payload 透前端。**禁区 support:58 禁改 return raw**。
- **Q2 分层环**：落点 gantt_critical_chain.py 已被两路 import（support:7 / provider:19），仅多取一符号，不新增 import 边；该文件只 import `._sched_utils`/`.gantt_task_labels` 不反向 import，0 环 0 越层。✅
- **Q6 测试迁移序**：`rg _normalize_critical_chain_result tests/` 0 命中（测试均黑盒），删旧符号不断测试直引点；但 parity 须**先于**收口落地。序：建 parity（断当前两副本等价）→ 收口 → parity 改断单份==基线。✅
- **判定**：黄。条件 = ① 先建 normalize parity 黄金基线（钉 `available=0→True` + `bool()` 差异）；② 收口保留 support `bool()` 写法；③ support:58/provider:180 禁 return raw；④ 禁误删 `_copy`:104。R11 owner 裁断点（保留哪份写法）并入。

### R12 —— 🟡 黄（A1 收口前置 + 空路径键须双补）

- **修法**：保留 :84 过滤，加 `dropped_count`/`critical_chain_partial` 可观测降级标记（DegradationCollector 范式），注入点 :328-334 + **`_empty_result`:54 也须带 dropped_count**。owner_pending=false。
- **Q4 灵魂线热路径（主透镜核心）**：P4 缺口正解 = 补可观测标记，**不 raise、不删 :84**。第2轮坐实 `_empty_result()` 的 `available:True`（:61）→「全坏行（nodes 空走 :315 `_empty_result`）」这一最该报警场景反而 available:True 无信号，**自相矛盾**。修法**必须同时给 :54 和 :328-334 两条 return 路径加 dropped_count**——只加注入点漏 _empty_result，最严重场景静默。这是计划已标但极易漏的反例。✅（计划覆盖）
- **Q4 裸删 :84 灾难链（禁区）**：第2轮坐实 :114 sort 用 `x.get("start")`、:261-262 `_sink_id` 走 max — 裸删 :84 → None 流入 → `None < datetime` TypeError → 被 :340-341（出口A）/ :358-359（出口B）try/except 接住 → 整链 `available:False` **功能回归**（丢一行坏数据→整链不可用，过度激进）。**:84 禁删**。
- **Q5 收口等价**：R12 非合并两路，是加键；但**白名单穿透等价**要测——两份 `_normalize` 是显式 `return {...}`（第2轮逐字确认），新键 dropped_count/critical_chain_partial **确被剥离**，卡口是 `_normalize`。**修正计划一处过度担心**：contract `:40 return raw` 在 available!=False 时透传（partial-but-available 主场景透过），真卡口只有两份/收口后单份 `_normalize`，contract 不卡（与 R12 dossier §对抗核验「卡口是 _normalize 非 contract」一致）。
- **Q5 _copy 不丢键（修正计划过度担心，重要）**：第2轮读 `_copy`:104-110 实体 = `out = dict(result or {})` 先整体浅拷再覆写 4 键 → **新键 scope/dropped_count 会被 `dict(result)` 自动带过去，_copy 不丢键**。计划/R12·R55 dossier 称「_copy 只复制 4 键会丢 scope，须补」是**误判**——`_copy` 不是卡口，无须为它补键（补了无害但非必需）。真正会吞新键的只有 ① 两份 `_normalize` ② contract unavailable 硬build 分支(:22-39)。
- **Q6 前置**：A1{R11/R63}统一单份 _normalize **必须先于** R12（否则加键改两副本=复活 P5）。Phase1 边 R11→R12 成立。snapshot 测试 :122 subset 检查加键不红（漏网），须主动断言新键存在。
- **判定**：黄。条件 = ① A1 先合并；② :54 与 :328-334 双补 dropped_count；③ :84 禁删；④ scope 名取 `gantt.critical_chain` 勿混 gantt_tasks `gantt.tasks`。**新发现修正**：_copy 不丢键、contract :40 不卡，无须为这两道补键（计划的「穿三道白名单」实为「穿两份/单份 _normalize + contract unavailable 分支」两道）。

### R55 —— 🟡 黄（owner 门控 + None 回退灵魂线禁动 + 反推必错）

- **修法**：加 `scope='filtered'/'full'`，由调用点显式赋值（非 helper 内反推）。owner_pending=true、needs_adversarial=true、verdict=null → 终态待 owner + 怀疑者复核。
- **Q4 灵魂线热路径（主透镜核心）**：第2轮坐实 gantt_service.py:384→:385 `if critical_chain is None`→:386 回退 provider full，support:55-56 `if not filters: return None` 是分流判据 —— 这是**有意降级**（filters 空=看整版，故走 provider full）。**裸删 filtered 过滤 = 把 filtered 视图改成整版 = 反砍业务（违灵魂线「不补反砍」）**；破坏 :385 None 回退或 :55-56 判据 = 炸有意降级。R55 病理是「呈现失真」非新增兜底，修法是补 scope 旁路标记不改算法，**不放大可用性**。✅（方向正确）
- **Q5 收口等价 + 反推必错（黄的根因）**：scope 必须由调用点显式置（support `critical_chain_for_plan_detail_filter` filters 非空→`'filtered'`；provider `get_critical_chain` 无 filter→`'full'`）。**禁在 helper 里靠「filters 空否」反推**——第2轮坐实 provider get_critical_chain 签名（:143）无 filters 参数，full 路径**无 filters 上下文，反推必错**（会把 full 误标 filtered）。helper default `'full'`，filtered 调用点显式覆写。
- **Q5 穿白名单（同 R12 修正）**：scope 落单份 `_normalize`（显式 dict，会吞→须认）+ contract unavailable 分支(:22-39 硬build→会吞，须补/置默认)。**_copy 不丢键**（`dict(result)` 带过去，同 R12 修正），无须为 _copy 补 scope。
- **Q6 前置**：A1{R11/R63}先（scope 落单份 helper，否则两副本各加一遍易分叉）。R12⟂R55 同批一次穿白名单。parity 须断 filtered→`'filtered'`、full→`'full'`、available=False 时 scope 不被 contract 吞、`filters={}`→None 回退不被破坏。
- **判定**：黄。条件 = ① owner + 怀疑者过 PHASE0 §6 三问（None 回退是否有意/裸删 vs 补标记/当下债 vs 在途态）方锁终态；② A1 先；③ scope 调用点显式置禁反推；④ 禁裸删过滤、禁破坏 :385 None 回退 + :55-56 判据；⑤ 单份 _normalize + contract unavailable 分支补 scope，_copy 无须补。

---

## 漏项（本轮新发现，未被计划覆盖 / 计划须修正）

1. **【修正·过度担心】`_copy_critical_chain_result`(:104-110) 不丢键**：实体 `out = dict(result or {})` 先整体浅拷，再覆写 ids/edges/edge_type_stats/reason_code 四键深化容器 —— 新键 scope/dropped_count **会被 `dict(result)` 自动带过去**。计划 + R12/R55 dossier 反复称「_copy 只复制 4 键会丢 scope/dropped_count，须补」是**误判**；_copy 不是白名单卡口。后果：计划「穿三道白名单」实为「穿两道」（两份/单份 `_normalize` + contract unavailable 硬build 分支:22-39）；为 _copy 补键无害但非必需，**别据误判把 _copy 当强制改点**（_copy 是承重缓存浅拷，6 处在用，越改越接近误删风险）。

2. **【修正·过度担心】contract `:40 return raw` 不卡 partial/scope 主场景**：available!=False 时 :40 全透传，dropped_count/critical_chain_partial/scope 在 partial-but-available 主场景**直接透过**。真正吞新键的只有两份/单份 `_normalize`（显式重建）+ contract unavailable 分支(:22-39 硬 build 固定键)。计划把 contract 笼统列「第三道白名单」会误导实现者去改 :40（无须改）。**净结论：新键真卡口 = 单份 `_normalize`（必改）+ contract unavailable 分支（须补 scope/默认，dropped_count 在 unavailable 即 _empty/_unavailable 路径本就该带）。**

3. **【确认·计划已覆盖但最易漏】`_empty_result`(:54) available:True**：第2轮坐实 :61 `"available": True`。R12 必须给 :54 和注入点 :328-334 **两条** return 路径都加 dropped_count，否则「全坏行→nodes 空→走 :315 `_empty_result`」这一最该报警场景 available:True 且无 dropped_count，完全静默。计划 A2 已列，标记为「最易漏反例」加固。

4. **【前置硬门未建】normalize parity 黄金基线测试不存在**（已 ls 确认 tests/regression_gantt_critical_chain_normalize_parity.py 缺）。A1 收口、A2/A3 加键全部门控于此。无此门先动 A1 = 把「`available=0→True`」「`bool()` 包裹」等静默等价点裸奔收口 → 测试绿但护栏已破。**这是本簇唯一会让「测试绿但灵魂线静默失效」的缺失前置**，须在 A1 动手前先建。

5. **【操作精度·非计划缺陷】R10 删后 grep resolve_version:64**：纯删 :60-62 后立即复核 :64 活方法在（scheduler_gantt.py:187 真实消费）。名字均含 version，按行号精删勿按模糊符号匹配，否则静默炸周计划版本解析。

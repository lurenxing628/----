# 逐簇爆炸对抗 r1 · C-GANTT · 透镜【承重误删】

> skeptic 第1轮，只读不改，默认怀疑。成员债 R10/R11/R12/R55/R63。
> 回盘日 2026-06-05，所有行号当前工作区 rg 实证，旧值已弃。
> 主透镜：承重误删（Q1 为重）。本簇 lb=false，无 §5 承重点，但毗邻承重行为（归一对 support 路径承重）+ :84 刻意韧性 + None 有意降级三处「软承重」是误删/裸砍主战场。

---

## 实证回盘汇总（禁区行符号回盘）

| 锚点 | 真实 file:line | 状态 |
|---|---|---|
| R10 死方法 get_latest_version_or_1 | gantt_service.py:60 | 0 调用（rg EXIT=1）|
| R10 活方法 resolve_version（禁误删） | gantt_service.py:64 | 物理隔离，仅 +4 行相邻 |
| R10 stub 镜像 | regression_scheduler_week_plan_summary_observability.py:59 | 死镜像，删 |
| R11/R63 support _normalize | gantt_service_support.py:32（调用:58） | 显式 8 键白名单 |
| R11/R63 provider _normalize | gantt_critical_chain_provider.py:113（调用:180） | 显式 8 键白名单 |
| _copy（禁误删，独立 staticmethod） | provider:104（6 处缓存调用:157/184/188/192/196/199） | 独立于 :113 |
| 收口落点反向 import 核 | gantt_critical_chain.py | rg EXIT=1 = 无环 0 越层 ✔ |
| R12 :84 过滤裸 continue | gantt_critical_chain.py:84 | 受害点 sort:114/134、max:262 实在 |
| R12 注入点 return dict | gantt_critical_chain.py:328-334 | 无 available 键，靠 normalize 补 |
| R12 _empty_result（available:True 无 dropped） | gantt_critical_chain.py:54-64 | 全坏行经 :315 早返回 |
| R55 病灶 filters 构造 / filtered 调用 | gantt_service.py:344 / :384 | :471 是 task-detail 另路 |
| R55 None 回退（有意降级，禁破坏） | gantt_service.py:385-389 | filtered None→fallback provider full |
| R55 分流判据 | gantt_service_support.py:55-56 | if not filters: return None |
| 承重消费点 collect_gantt_degradation_events | gantt_service_support.py:70-71 | 读 available is False / reason_code |
| scope 四文件零命中 | support/provider/critical_chain/contract | rg EXIT=1 债活 |

---

## 逐成员判定

### 🟢 R10（删死方法 :60-62 + stub:59）
六维全过。零调用双证（rg EXIT=1 + callgraph 0 入边）；纯删除不新增 import/兜底（Q2/Q4 干净）；非收口无 parity（Q5 不适用）；唯一操作精度禁区 resolve_version:64 与死方法 :60 相邻仅 +4 行、名字均含 version——**误删 :64 即静默炸周计划版本解析（scheduler_gantt.py:187 svc.resolve_version 唯一真消费）**。防御充分：按 :60-62 行号精删 + 删后 grep `def resolve_version` 复核 :64 在。测试序（Q6）：stub:59 与死方法同 PR 删，stub 通读不被 invoke（实际断言 resolve_calls/row_calls）。**安全。**

### 🟢 R11 ≡ R63（抽单份 _normalize 到 gantt_critical_chain.py，support:58/provider:180 改调）
Q1 主透镜重点核：这是「该 DRY」动作落在毗邻承重上。实证两份逐键等价（已读 provider:113-137 全函数体；support 版同构）；**收口点不反向 import（Q2 无环 0 越层实证 rg EXIT=1）**；**禁区 support:58 禁 `return raw`**——raw 缺 available/edge_type_stats 默认，:58 归一是 support 路径唯一补默认点，下游 support:70 读 `available is False`、:71 读 reason_code 承重，改 return raw → 降级该报不报（Q1/Q4 灵魂线违规）；**禁误删 _copy:104**（独立 staticmethod，6 处缓存浅拷在用，实证）。Q5 收口等价唯一微差：support `bool(is_available)`:48 显式包裹 vs provider:134 裸传，当前等价，收口取 support 写法兜未来 available 非 bool。**条件门控合规则安全，故标 🟢但带硬门**：(F门) **必先建 normalize parity 黄金基线钉 5 边界（{}/非dict/available=0/available="yes"/available=False无code），无 parity 不得收口**。owner_pending：R11=true（裁断点=保留哪份写法）/R63=false，合并单 work item。

---

### 🟡 R12（加 dropped_count/critical_chain_partial）— 条件：A1 先 + 穿真卡口 + _empty_result 同补 + scope 名隔离
Q6 收口前置硬边：**A1{R11≡R63} 必先**，否则 R12 加键改两副本=复活 P5（实证两份 _normalize 各为显式 8 键 dict，:127-137 / support:42-51）。
**条件1（穿白名单）**：唯一真卡口是两份/收口后单份 `_normalize`（:126-137 显式重建 dict，新键被剥离）。**计划对 contract/`_copy` 的告警偏保守需更正**——(a) contract `_public_critical_chain`:40 `return raw` 在 available=True 主场景全透传，R12 partial-but-available 透过，**只 available=False 分支:23-29 重建固定 5 键吞 dropped_count**；(b) provider `_copy`:104 用 `dict(result)`:105 起手浅拷全键，dropped_count **实际会被带过不丢**（计划「_copy 只复制4键会丢」不准，:106-109 只是覆写部分键，dict(result) 已保全部）。→ R12 真正必改只有 _normalize 一道，contract/_copy 是补显式更稳但非 fail 点。
**条件2（_empty_result 同补）**：全坏行经 :315 `_empty_result()` 早返回（实证 :54-64 无 dropped_count），**最该报警场景反而无信号**=自相矛盾，:54 须同补。
**条件3（禁区 :84）**：裸删过滤=灾难链 改:84删→None流入sort:114/134+max:262→`None<datetime` TypeError→出口 try/except:341/:355/:359 接住→整链 available:False=「丢一行回归成全链不可用」功能回归。**禁删，仅旁路记 collector。** scope 取 `gantt.critical_chain` 勿混 gantt_tasks 的 `gantt.tasks`。owner_pending=false。

### 🟡 R55（加 scope=filtered/full）— 条件：A1 先 + 调用点显式赋值禁反推 + 禁裸砍过滤 + 穿卡口 + owner 门
Q1 主透镜命中：「该对齐 makespan」诱惑落在 None 有意降级 + filtered 业务过滤上。
**条件1（A1 先）**：scope 落 A1 单份 helper，否则两副本各加易分叉（filtered 标了 full 漏）。
**条件2（禁反推=灵魂线）**：scope 必须由调用点显式赋值（support filtered 路径覆写 'filtered'，provider full 路径 default 'full'），**禁在 helper 靠「filters 空否」反推**——provider full 路径无 filters 上下文反推必错（Q4 静默推断违灵魂线）。
**条件3（禁裸砍）**：严禁裸删 filtered 过滤=把 filtered 视图改整版反砍业务（Q1 承重误删主形态）；禁破坏 None 回退 gantt_service.py:385-389（实证有意降级）+ 分流判据 support:55-56。
**条件4（穿卡口）**：scope 穿 _normalize（真卡口）；contract unavailable 分支:23-29 会吞 scope 须补/置默认（available=True 走 :40 透传 OK）；_copy 同 R12 靠 dict(result) 带过。
**owner 门（Q 强约束）**：owner_pending=true + needs_adversarial=true + verdict=null → 终态修法（落点写法/本轮是否做）待 owner+怀疑者过 PHASE0§6 三问。**标只标 owner_pending 不给终态。**

---

## 漏项（本轮新发现，计划未覆盖或告警失准）

1. **【计划过度告警，需更正】R12/R55 的 contract 与 _copy 不是 fail 卡口**：实证 contract:40 available=True 主场景 `return raw` 全透传；provider `_copy`:105 `dict(result)` 浅拷全键不丢新键。计划 C-GANTT.md §A2/§A3 + R12 dossier §4/§8、R55 dossier §6 把 contract/_copy 列为「会吞/会丢，必补」**偏保守**——真正会剥离新键的**唯一卡口是 _normalize 显式 8 键 dict**。补 contract/_copy 是「更稳」非「不补即炸」，但 **contract available=False 分支:23-29 确会吞 scope/dropped_count**，对 R12/R55 的 unavailable 场景仍须显式处理（这一支计划是对的）。结论：卡口数从「三道」修正为「一道硬卡口（_normalize）+ 一道半卡口（contract unavailable 分支）+ _copy 非卡口」。

2. **【新发现可观测裂缝】R12 在 unavailable 路径完全无 dropped_count**：`_unavailable_result`:71-76 仅 _empty_result 改 available=False，**不带 dropped_count**；且 compute_critical_chain_from_rows:337-341 整体 try/except 把任何异常压成 _unavailable_result。即「坏行多到触发异常」与「全坏行空 nodes」两条最该报警路径，R12 修法若只补 :328-334 + :54，仍漏 :71 unavailable 路径——建议 R12 修法把 dropped_count 同补进 _unavailable_result:71 或在 :337 try 外先算 dropped_count。计划仅点了 _empty_result:54，**漏 _unavailable_result:71**。

3. **【确认非爆点】R10 ⟂ R55 同文件**：实证 :60 与 :344/:384 相距 280+ 行，R55 按符号定位不受 R10 删 3 行影响，计划「降级软约束」判定正确，非漏项。

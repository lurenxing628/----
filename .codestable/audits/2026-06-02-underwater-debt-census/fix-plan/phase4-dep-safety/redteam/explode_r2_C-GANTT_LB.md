# 逐簇爆炸对抗 r2 · 簇 C-GANTT · 主透镜【承重误删】

> skeptic 第2轮,只读不改。回盘日 2026-06-05,行号 rg 实测当前工作区,不信旧值。
> 成员债 R10 / R11 / R12 / R55 / R63。基线:r1 LB(explode_r1_C-GANTT_LB.md,8678B)+ C-GANTT.md 计划 + 5 dossier + _layer1/2。

> **✅ 2026-06-08 B 执行补登**：A1 `{R11≡R63}` 已 fixed。单份 `_normalize_critical_chain_result` 已收口到 `gantt_critical_chain.py:67-88`；support/provider 旧副本已删，两路调用同一 helper，parity 11 边界已落。本红队文中 A1 的“黄/条件”判断现转为已满足；R12/R55 仍未执行。
> 默认怀疑:多维度存疑即红;不放过「测试绿但护栏已破」的静默失效。

## 0) 本轮独立回盘(全部命中,与计划行号一致,旧值已失真)

| 锚点 | 真实 file:line | 验证 |
|---|---|---|
| R10 死方法 `get_latest_version_or_1` | gantt_service.py:60-62(`return v if v>0 else 0`) | ✅ 名实矛盾坐实(`_or_1`却返0) |
| R10 活方法 `resolve_version`(禁误删) | gantt_service.py:64 | ✅ 紧邻独立,共享 history_repo.get_latest_version 是巧合 |
| R10 stub | regression_scheduler_week_plan_summary_observability.py:59-60 | ✅ |
| R11/R63 support `_normalize` def/调用 | gantt_service_support.py:32 / :58 | ✅ :48 `bool(is_available)` 显式包裹 |
| R11/R63 provider `_normalize` def/调用 | gantt_critical_chain_provider.py:113 / :180 | ✅ :134 裸 `is_available`(微差,运行等价) |
| `_copy_critical_chain_result`(禁误删) | provider:104(+:157/184/188/192/196/199 六处缓存浅拷在用) | ✅ 与 `_normalize`:113 是两独立 staticmethod |
| R12 :84 过滤 | gantt_critical_chain.py:84 裸 continue | ✅ sort:114/:134、max:262、注入:312-334、`_empty_result`:54(available:True,无dropped) |
| R55 filters/调用/None回退 | gantt_service.py:344 / :384 / :385-390 | ✅ None→fallback provider full 真实 |
| 全仓 `def _normalize_critical_chain_result` | 恰 2 处(support:32 + provider:113) | ✅ |
| parity 测试 | tests/regression_gantt_critical_chain_normalize_parity.py | ✅ 不存在(收口安全门前置,符合计划) |

承重禁区行(load_bearing/N1/N2/R03/R05 等)零落本簇五债文件;本簇 lb=false,无 §5 承重清单。主透镜 Q1「承重误删」在本簇转化为:**承重不对称落在「归一补默认/刻意过滤/None有意降级/三道白名单」四处毗邻承重行为**,任何以 DRY/统一/简化名义抹平即红。

## 逐债判定

### 🟢 R10 — 删死方法 `get_latest_version_or_1` + stub
- **证据**:gantt_service.py:60-62 零入边(rg 全仓 0 调用,callgraph 0 入边);活方法 resolve_version:64 物理隔离。
- **判定绿**:纯删孤儿,非收口/非承重/0 越层/无 parity。Q1-Q6 全过。唯一操作精度禁区 resolve_version:64(名字含 version,误删即静默炸周计划版本解析)已锁定,删后 grep `def resolve_version` 复核 :64 在即可。
- **前置**:与 R55 同 gantt_service.py,PHASE0 §3 勿两 PR 并发改(软约束),任意顺序安全。

### 🟡 R11≡R63 — 收口去重单份 `_normalize`(A1)
- **证据**:两份逐字段实测等价(本轮读 support:32-51 / provider:113-137 全体),唯一微差 support:48 `bool(is_available)` vs provider:134 裸传,当前前置分支保证 bool 故运行等价。收口落点 gantt_critical_chain.py 已被两路 import(support:7/provider:19),0 越层 0 环。
- **黄(条件)**:owner_pending(R11=true/R63=false),终态以 R63 修法为准。**放行硬条件 = 先建 parity 黄金基线测试**(对当前两副本断言逐键等价,钉死 5 类边界:`{}`/非dict/`available=0`→现行得True而`bool(0)`得False/`available="yes"`/`available=False`无code→"unknown")。**无 parity 不得收口。**
- **灾难链(若违)**:support:58 改 `return raw`(DRY 简化诱惑)→ raw 缺 available/edge_type_stats 默认 → collect_gantt_degradation_events:70 判 `available is False` 失效 → 降级该报不报(静默,灵魂线违规);且 contract:40 `return raw` 透传非归一 payload 到前端。**承重禁区**:support:58 仅可改调用目标禁 return raw;provider:104 `_copy` 禁误删(独立于 :113);provider:180 禁删归一禁缓存 raw(:141 `_critical_chain_cacheable` 读 available)。
- **顺序**:A1 必先于 A2/A3;禁拆两人各改一份(撞改 support+provider 同两文件,一删一悬空)。

### 🟡 R12 — 加 dropped_count/critical_chain_partial(A2)
- **证据**::84 裸 continue 后无任何 dropped/partial 键(rg NONE_FOUND);`_empty_result`:54 含 available:True 无 dropped;contract 关键链白名单零 dropped/partial(本轮 rg 实测)。
- **黄(条件)**:owner_pending=false 可给终态,但**强前置 A1**(未先合并→改两副本复活 P5)+ **保留 :84 过滤**。
- **灾难链1(裸删 :84)**:start/end=None 流入 sort:114/:134(`x.get("start")`=None)、max:262(`x.get("end")`=None)→ `None < datetime` TypeError → 被 :340(出口A)/:358(出口B)try/except 接住 → `_unavailable_result` → 整链 available:False。**= 把「丢一行仍出链」回归成「一行坏数据全链不可用」**,反砍业务=过度激进。**禁区:84 只补 collector 留痕不删过滤。**
- **灾难链2(新键不穿白名单)**:在两份/收口后单份 `_normalize` 显式 build dict 被静默剥离 → 前端永收不到 partial = 换地方自欺。
- **⚠️ 本轮新发现(计划疏漏,见漏项)**:`_empty_result`:54 须带 dropped_count(全坏行=最该报警却走 :315 早返回无信号)——计划已点;**但 contract unavailable 分支(:22-39 硬 build 固定 5 键)会吞 dropped_count**:R12 计划只说「contract:40 透传不卡」,漏了 available=False 时(若 dropped 行致全坏被标 unavailable)走硬白名单分支会吞 dropped_count。须确认 R12 主场景(partial-but-available 走 :40 透传)是否覆盖「dropped 多到 available=False」的反场景。

### 🟡 R55 — 加 scope=filtered/full(A3)
- **证据**:四关键链文件 rg `scope` 零命中(provider `_database_scope` 缓存键 + DegradationEvent `scope="scheduler.gantt"` 同名异义,已排除);support:54-58 filtered 路径喂子集 rows 给整版算法,无 scope 标记;:385-390 None 有意降级回退真实。
- **黄(条件)**:owner_pending=true + needs_adversarial=true + verdict=null → **终态待 owner + 怀疑者复核三问**(None 回退是否有意/裸删 vs 补标记/当下债 vs 在途态)。强前置 A1。
- **灾难链1(裸删 filtered 过滤)**:把 filtered 视图改整版 → 单设备/单批次看不到本设备链 → 呈现失真不补反砍,违灵魂线。**承重禁区:support:55-56 `if not filters: return None` 分流判据 + gantt_service.py:385 None 回退 禁破坏。**
- **灾难链2(scope 只穿一道)**:provider `_copy`:104-110 当前只复制 ids/edges/edge_type_stats/reason_code(本轮实测,**会丢 scope 须补**)+ contract unavailable:22-39 吞 scope → filtered 又冒充 full,失真换形式复发更难查。
- **灾难链3(helper 里靠 filters 空否反推 scope)**:违静默推断,且 provider full 路径无 filters 上下文反推必错 → scope 须调用点显式赋值。

## 漏项(本轮新发现,计划未充分覆盖)

1. **contract unavailable 分支(:22-39)吞 R12 dropped_count 未被计划明列**:计划 A2 断言「卡口是两份/单份 `_normalize`,contract:40 透传不卡」,但只覆盖 available=True 透传路径。**反场景**:R12 的 dropped_count 在「全坏行/坏行致 available=False」时,结果走 contract :22-39 硬 build 固定 5 键(本轮实测确无 dropped),dropped_count 被吞 → 最该报警场景反而无信号。计划对 R12 的三道白名单清单**缺 contract unavailable 分支这一卡口**(R55 的 scope 计划反而点到了 :22-39,R12 没点)。建议:R12 的 contract 卡口与 R55 scope 一并在 :22-39 补 dropped_count/partial(同批穿白名单)。

2. **A2/A3 同改 `_normalize` 的「两键 vs 默认值」未钉死**:R12 加 dropped_count(默认 0)+ R55 加 scope(默认 'full'),二者同 PR 改同一收口后单份 helper。若先后两轮改 → 第二轮易覆盖第一轮新键的 build 行,或 parity 测试只锁单键。建议 A2/A3 强制同一次改 `_normalize`,parity 测试同时断言两新键穿三道(含 contract :22-39)+ ids/edges/makespan_end/available 既有取值不变。

3. **`_copy_critical_chain_result`:104 的 scope/dropped 复制缺口对缓存命中路径的静默丢键**:provider get_critical_chain 缓存命中(:157)/未命中返回(:184/188/192/199)全经 `_copy`,`_copy` 当前只复制 4 键(实测 :106-109),**新键 scope/dropped_count 在缓存往返中被静默丢**。R55 计划点到 `_copy` 须补 scope;**R12 计划未点 `_copy` 须补 dropped_count**——缓存命中路径的 dropped_count 会丢。这是 R12 计划第二处白名单缺口(与漏项1 contract 并列)。

## 返回串见任务输出

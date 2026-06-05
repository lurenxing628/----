# 逐簇爆炸对抗 r1 — 簇 C-GANTT — 透镜【分层导入环 + 迁移耦合】

> skeptic r1，只读不改。默认怀疑：找不到爆点才算绿。
> 成员债 R10 / R11 / R12 / R55 / R63。主文件 gantt_service.py / gantt_service_support.py / gantt_critical_chain.py / gantt_critical_chain_provider.py / gantt_contract.py。
> 全部行号已 rg 当前工作区回盘（2026-06-05），不信旧值。

---

## 0) 主透镜核验结论（Q2 分层 / Q3 迁移耦合）

**Q2 分层导入环：0 违规，PASS（实测）。**
- 收口落点 `gantt_critical_chain.py` 实测 import 仅两行：`from ._sched_utils import _safe_int`、`from .gantt_task_labels import public_task_label`（:6-7）。
- `rg "gantt_service_support|gantt_critical_chain_provider" gantt_critical_chain.py` → **EXIT=1（0 命中）**，即收口落点**不反向 import** support/provider。
- support:7 / provider:19 已 `from .gantt_critical_chain import compute_critical_chain_from_rows`。把 `_normalize` 下沉到 gantt_critical_chain.py，方向仍是 support/provider → gantt_critical_chain（下游→上游单向），**不成环、不新增 import 边、0 越层**。无 core.models→core.services、无 repo→service 越层（本簇全在 `core/services/scheduler/` 同包平移）。
- R12 借 `DegradationCollector`（core.services.common.degradation）+ `record_bad_time_row`（_sched_display_utils.py:84，同包），均同层，0 新增越层。

**Q3 迁移耦合：本簇与 schema CHECK / v18·v19 DB CHECK 零耦合，PASS。**
- 本簇五债无一触碰 effective_plan_role / source_table / adopted-only 的 v19 DB CHECK；不动迁移、不动 schema。改码不改迁移=启动探针炸的风险**不存在于本簇**。
- 唯一沾边的是 R12 §8 引 `schema.sql` Schedule.start_time/end_time DATETIME NOT NULL 论证「丢行分支近死」——这是**读 schema 当论据**，非改 schema，不构成迁移耦合。

---

## 逐债判定

### 🟢 R10 — 删死方法 get_latest_version_or_1（gantt_service.py:60-62 + stub:59-60）
**判定：绿（安全）。** 实测 rg `get_latest_version_or_1` 全仓仅 2 个 def（gantt_service.py:60 + stub:59），排除 def 后调用点 **EXIT=1（零调用）**。callgraph 0 入边。纯删孤儿，非收口、非承重、不新增 import → Q1/Q2/Q3/Q4/Q5/Q6 全不触发。
- 唯一操作精度禁区：`resolve_version`(:64) 实测在 :64（活方法，唯一真消费 scheduler_gantt.py svc.resolve_version），与死方法 :60-62 物理隔离。**删后必 grep 复核 def resolve_version 仍在 :64**（名字也含 version，误删即静默炸周计划版本解析）。
- 序：与 R55 同居 gantt_service.py，PHASE0 §3 同 PR 物理串行；按符号定位任意顺序安全。

### 🔴 R12 — 关键链 _build_nodes 静默丢坏行无 partial 信号
**判定：红（会炸，但非计划所述路径——计划漏了 contract available=False 分支这一道卡口）。**

灾难链（计划已覆盖的两条，实测成立，是禁区不是爆点）：
1. **裸删 :84 过滤 → None 流入 sort:114（`x.get("start")`=None）/ max:262（`x.get("end")`=None）→ `None < datetime` TypeError → 被 :338-341（compute_from_rows）或 :352-359（compute_critical_chain calc_exception）try/except 接住 → 整链 `_unavailable_result` → available:False 功能回归。** 实测两道出口 try/except 都在，:84 是刻意韧性，**禁删**。R12 领地是 :84 留痕（不删）+ 注入点 :328-334 + _empty_result :54。

**本轮新发现爆点（计划自相矛盾，未覆盖）→ 这是 R12 标红的真因：**
2. **R12 的新键 dropped_count/critical_chain_partial 在 contract `available=False` 分支被静默剥离，而计划只把「两份 _normalize」列为卡口、明示「contract:40 return raw 透传不卡」。** 实测 `_public_critical_chain`(gantt_contract.py:19-40)：当 `raw.get("available") is False`（:22）走 **:23-39 硬重建固定键 dict（available/ids/edges/edge_count/edge_type_stats/cache_hit/reason_code/reason）+ return out**，**dropped_count / critical_chain_partial 被丢**；只有 available=True 才走 :40 `return raw` 透传。
   - 灾难：partial 的关键链**最该报警的场景之一恰恰是降级到 available=False**（坏行多到链路退化/异常被 :340 接住成 unavailable）。计划只修了 `_empty_result`（让全坏行带 dropped_count），却没意识到这个 dropped_count 一旦伴随 available=False，**到 contract :23-39 又被吞掉** → 前端仍收不到 partial 信号 = 「换地方自欺」在 contract 层复发。R55 dossier §6 catch 到了 contract unavailable 吞 scope，R12 dossier §4/§7 却写「真正卡口只有 provider/support 两份 _normalize，contract:40 透传不卡」——**对 available=False 路径是错的**，遗漏 :23-39 这道剥离。

修正建议（前置 + 禁区 + 补卡口）：
- 前置：A1{R11≡R63} 先统一单份 _normalize（强偏序，倒序则改两副本复活 P5，实测两份 def 在 support:32 / provider:113）。
- 禁区：:84 过滤禁删/禁改条件；:114 sort、:262 max 禁动；:338-341 / :352-359 出口 try/except 是 R55/P4 领地，R12 不碰。
- **补卡口（计划缺）**：dropped_count/critical_chain_partial 须在 contract `_public_critical_chain` 的 **available=False 分支（:23-39）也显式保留**（与 R55 scope 同处理），否则降级态 partial 信号在 contract 层蒸发。这道修正必须写进 R12 work item，否则「测试绿（snapshot subset + available=True parity 都过）但护栏已破（available=False 路径无信号）」的静默失效。
- _empty_result(:54) 须带 dropped_count（实测当前 :54-64 available:True 且无该键，「全坏行最该报警却无信号」自相矛盾成立）。
- owner_pending=false，但因上面 contract 缺口，**终态修法须补这一道**再落地。

### 🟡 R11 ≡ R63 — 两份 _normalize 收口去重（A1，同一物理动作）
**判定：黄（有条件可做）。** 收口本身分层/环/越层全绿（Q2 PASS 见上）；条件全在 parity 门与禁区。
- 条件 1（F 门）：动手前必先建 parity 黄金基线 `tests/regression_gantt_critical_chain_normalize_parity.py`（实测不存在），对当前两副本断言逐键等价，**重点钉死 `bool(is_available)` 包裹差异**：实测 support:48 `bool(is_available)` vs provider:134 裸 `is_available`——当前两路前置分支保证 is_available 为 bool，运行时等价；收口须**取 support 的 bool() 写法**（owner 裁断点，R11 owner_pending=true，并入 R63 终态）。Q5 反例：`available=0` 现行 isinstance(0,bool)=False → True；若收口手滑写 `bool(available)` → False，**静默放宽**。parity 必覆盖 available=0/"yes"/False无code/非dict/{} 五边界。
- 条件 2（禁区，Q1 承重不对称）：support:58 `return _normalize_critical_chain_result(raw)` **禁改 return raw**（raw 缺 available/edge_type_stats 默认，归一是 support 路径唯一补默认点；下游 collect_gantt_degradation_events:70-71 读 available/reason_code，改 return raw → 降级该报不报=灵魂线违规静默 fail-open）。仅可改调用目标。
- 条件 3（禁误删，Q1）：provider `_copy_critical_chain_result`(:104-110) 与 `_normalize`(:113) 是**两个独立 staticmethod**，实测 _copy 有 **6 处缓存浅拷在用**（:157/184/188/192/196/199）；A1 只收口 _normalize，**严禁误删 _copy**。
- 条件 4（序）：A1 必须早于 A2{R12}/A3{R55}；R11/R63 禁拆两人派工（撞改 support+provider 同两文件，一删一悬空）。
- 灵魂线：P5 去重不涉 P4，不得借机加兜底/静默回退（Q4 不触发，但禁新增）。

### 🟡 R55 — filtered 关键链冒充整版，补 scope=filtered/full
**判定：黄（有条件可做，且 owner_pending=true + needs_adversarial=true + verdict=null，本轮不锁终态）。** 分层/环 0 风险（纯数据键，不新增 import）。
- 条件 1（PHASE0 §6 三问，怀疑者门未过禁锁终态）：None 回退是否有意（实测 support:55-56 `if not filters: return None` + gantt_service.py 调用点 None → fallback provider full，是有意降级）/ 裸删 vs 补标记 / 当下债 vs 在途态。**严禁裸删 filtered 过滤逻辑**（裸删=filtered 视图变整版=反砍业务=违灵魂线，Q1）。
- 条件 2（前置）：scope 必须落 A1 统一后的单份 _normalize，default 'full'，由 filtered 调用点（support critical_chain_for_plan_detail_filter:54）显式覆写 'filtered'，provider get_critical_chain（无 filter）= 'full'。**禁在 helper 里靠「filters 空否」反推**（Q4 静默推断违灵魂线；provider full 路径无 filters 上下文，反推必错）。
- 条件 3（三道白名单，Q5 收口等价）：scope 须穿 ① 主闸 _normalize（合并后单份）② provider `_copy_critical_chain_result`(:104-110)——实测只复制 ids/edges/edge_type_stats/reason_code，**会丢 scope 须补** ③ contract `_public_critical_chain` available=False 分支（:23-39 实测硬重建固定键，**会吞 scope 须补**；:40 透传分支保留）。R55 dossier §6 已正确 catch ③，与本轮 R12 缺口同源——**R12 与 R55 同批一次穿白名单时，③ 必须同时给 dropped_count + scope 都补上，别只补 scope**。
- 条件 4（禁区，Q3 消费者触发条件勿砍）：跨簇 R21/R44/R72 改 scheduler_gantt.py:345-351 data_kwargs 时须确认 resource_type/resource_id 仍传到 :344（R55 病灶触发条件，R55 只读该消费者，勿顺手砍）。
- 序：A1 先于 R55；与 R10 同 gantt_service.py 物理串行但按符号定位任意序安全。

---

## 漏项（本轮新发现，计划未覆盖的爆点 / 缺失前置）

1. **【高 / R12 标红真因】contract `_public_critical_chain` available=False 分支（gantt_contract.py:23-39）是第三道真卡口，会硬剥离 dropped_count/critical_chain_partial。** 计划（cluster doc B/C 节 + R12 dossier §4/§7）明示「contract:40 return raw 透传不卡，真卡口只有两份 _normalize」——此论断**仅对 available=True 成立，对 available=False 路径错误**。降级态（最该报 partial 的场景）partial 信号在 contract 层蒸发 = 测试绿（available=True parity + snapshot subset 都过）但护栏已破的静默失效。**前置补丁：R12 work item 须把 dropped_count/critical_chain_partial 加进 contract :23-39 unavailable 分支**（与 R55 scope 同处理，同批一次补齐）。R55 因 dossier §6 已 catch contract 吞 scope → 不受此漏项拖累，但二者同批改 :23-39 时必须**同时补 scope + dropped_count + partial 三键**，防只补一类。

2. **【中 / parity 门】R12 的 parity 测试当前只断言 available=True 下新键穿透（dossier §7/§11），未覆盖 available=False 下新键应保留。** 配合漏项 1，parity 必加「available=False + dropped_count>0 → 经 contract 后 dropped_count 仍在」断言，否则修了 contract :23-39 也无回归网钉死。

3. **【低 / 确认无误】R11 收口取 bool() 写法、_copy 禁误删、:84 禁删、resolve_version:64 禁误删、support:58 禁 return raw、None 回退 :55-56 禁破坏——六条禁区行全部实测复核命中，计划标注准确，无新增遗漏。** Q3 迁移耦合本簇全 PASS（不沾 v18/v19 DB CHECK）。Q2 分层 0 违规实测成立（收口落点不反向 import，单向无环）。

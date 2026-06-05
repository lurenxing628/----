# 逐簇爆炸对抗 · 第2轮 · 簇 C-COMPAT-DISPATCH · 主透镜【承重误删】

> 只读不改任何 .py。行号 2026-06-05 rg 实盘回盘,不照抄旧值。
> 成员债:R30 / R33 / R29 / R49 / R50 / R51。
> 主透镜 Q1(承重误删/fail-open/预览冒充正式)为重,六质问点全过。
> 默认怀疑:多数维度存疑即标红,不放过「测试绿但护栏已破」的静默失效。

---

## 总判定速览

| 债 | 判定 | 一句话 |
|---|---|---|
| R30 | 🟡黄 | facade 三常量 re-export(services.common.value_policies:6-8/:24-26)须与删 shared 常量同窗口,漏改=ImportError 打挂 facade 全表面 |
| R33 | 🟡黄 | 删序硬约束(步1迁import先于R30删实现);死保元组 degradation:15 + number_utils:17 + strict_parse:18,只删 :14/:16/:19 |
| R29 | 🟡黄(owner-pending,只标不给终态) | 授权CSV ABSENT 确认;薄壳半截迁移客观在场;走B收敛须先重写monkeypatch为身份测试 |
| R49 | 🟢绿(带定点删红线) | 5行死别名零引用属实;严禁按符号名全局删 `_parse_due_date`(sgs_scoring:34 同名活函数) |
| R50 | 🟢绿 | mean_positive 死函数零生产引用;删 import statistics 安全、保 import math(:78/:95/:128真用) |
| R51 | 🟡黄 | 收口点已loud raise在位;续命测试 :25 兜底断言**必须连退禁迁**(迁=把灵魂线P4兜底钉成契约) |

主透镜结论:**本簇无「以统一/DRY名义抹掉承重不对称」的承重误删**(6债全 load_bearing=false,无 N1/N2/R03/R05/R54/R58 承重点落在簇内文件)。无 A 族「给 execution_review 加形参=预览冒充正式」(execution_review.py 不在本簇)。无「5套guard漏拷一键 fail-open」(R54 五套手维列表不在本簇)。**真正危险面是删除编排序错 + 灵魂线兜底测试被迁移续命**,均为🟡条件可做,非🔴必炸。

---

## R30 — compat date 死切片直删 🟡黄

**判定🟡**:本体是 P6 死分支直删(parse_compat_date 生产调用=0,实盘 rg 仅 shared定义 + services.common壳re-export + 2测试),非承重。但有两个**顺序敏感前置**未做即炸。

**实盘回盘(2026-06-05)**:
- `core/shared/compat_parse.py:198` def parse_compat_date(零漂移)
- `parse_compat_date` 全仓引用 = shared:198 + services.common/compat_parse.py:4/:10(R33壳) + 2测试(emits_degradation:18/:39 + config_contract:411)。**生产调用形态=0,死分支属实**。
- facade 爆点实盘:`core/services/common/value_policies.py:6-8`(import READ_FILTER_ONLY/VALUE_DATE/VALUE_DATETIME)+ `:24-26`(__all__)。

**Q1承重误删**:无。纯直删,非「统一/对齐签名」。同 import 块 float/int/is_blank_input 名字 + :153-195 存活函数体已划禁区,正确。承重不对称无被抹。

**Q5收口行为等价**:N/A。R30 不收口、不统一新旧两路——date 回退语义(invalid_due_date→None)与 float/int(invalid_number)**不可统一**,dossier 反例澄清正确,无误把死分支当「该统一」处理。

**灾难链(漏改 facade,本条最大爆点)**:
删 shared 三常量 `VALUE_DATE/VALUE_DATETIME/READ_FILTER_ONLY`(value_policies.py:12/:16/:17)→ 未同窗口删 `core/services/common/value_policies.py:6-8/:24-26` re-export → 该壳模块 `from core.shared.value_policies import VALUE_DATE` **ImportError** → 打挂**所有** `from core.services.common.value_policies import ...` 的存活方(含矩阵契约测试经此取 READ_FILTER_ONLY)。这是「一处漏改连带打挂 facade 全表面」,但是**响声(ImportError)非静默**,CI 即拦。

**修正建议(前置/顺序)**:
1. 删 shared 三常量 **必须**与 R31/B13 facade 删 re-export(:6-8/:24-26)同一窗口,或 facade 先收。这是 R30↔R31 新增硬序边。
2. R33 步骤1(迁 emits_degradation:18 import)**必须先于** R30 删 parse_compat_date 实现(见 R33)。
3. 禁区行(误删即崩,等同禁区):compat_parse.py:9-17 float/int/is_blank import + :129-195 函数体;value_policies.py:6-11 WRITE_* + :14-15 VALUE_FLOAT/INT + :22-178 FieldPolicy类与13个float/int策略 + :211-227 推导dict/查询函数。

---

## R33 — 三壳 re-export facade 残渣直删 🟡黄

**判定🟡**:三壳 def=0 纯 re-export,生产零消费(`rg core.services.common.(compat_parse|field_parse|value_policies) core/ web/ data/`=0),仅3测试续命,可删。但删序神圣 + 元组死保行有**文档缺口**。

**实盘回盘**:元组 `_SERVICE_COMMON_NEUTRAL_HELPERS`(config_contract:13-19)逐行:
- :14 compat_parse / **:15 degradation(死保)** / :16 field_parse / :17 number_utils / :18 strict_parse / :19 value_policies。
- R33 删壳对应删 :14/:16/:19 三条;degradation:15 是 R29 反例(真承重实现,20+生产直连,非壳)死保。

**Q1承重误删**:无。R33 只删壳+测试,不碰 core.shared 承重点。`degradation` 实测**不是壳是真实现模块**(DegradationCollector/DegradationEvent,20+生产直连),R33 dossier「反例壳」措辞应更正为「反例(真承重实现)」——不影响修法,但执行者须知 degradation 绝不可当 re-export 残渣删。

**Q6测试迁移序(硬)**:
1. **R33步1**(迁 emits_degradation:18 + matrix_contract:18 import 从 services.common→core.shared)**最先**,为 R30 解锁;
2. **R30**(删 shared 实现);
3. **R33步2/3**(删 config_contract:411 身份断言 + 退元组三条 + 删三壳)。
违序后果:R30 先删而步1未迁 → :18 ImportError + :411 AttributeError(**响声非静默**)。

**Q2分层导入环**:0。删壳纯减法,三壳仅 `core.services.common.*→core.shared.*` 合法下沉,不引入越层/导入环。

**灾难链C(误碰 core.shared→炸生产)**:R33 手滑删到 `core.shared.{compat_parse,field_parse,value_policies}` → 生产直连方(schedule_input_builder/external_groups/greedy)全炸。属越界,靠禁区行拦。

**修正建议**:
- 删元组**只删 :14/:16/:19**,死保 :15(degradation)。**补充(dossier 未明说的缺口)**::17 number_utils / :18 strict_parse 也是真模块壳须保留——:355 测试 `test_scheduler_run_uses_shared_parse_and_degradation_helpers` 用此元组做**反向 FORBIDDEN 黑名单**(断言 scheduler_run 可达文件不经壳 import),删条目须与「该壳确已删除」一一对应,不可多删 :17/:18(number_utils 壳因 R29 owner-pending 未删、strict_parse 壳为真模块)。

---

## R29 — number_utils 半截 facade 🟡黄(owner-pending,只标不给终态)

**判定🟡 owner-pending**:不进任何原子删除批。实盘确认:`core/services/common/number_utils.py:5` import + parse_finite_float/int 全量 delegate→`core.shared.strict_parse`(薄壳);授权 CSV 整目录 **ABSENT**(`ls .codestable/**/authorization*.csv` no matches)。半截迁移不对称客观在场。

**Q1承重误删**:本 Layer 只标 owner-pending,**不给终态**(铁律:owner_pending 只标不给终态)。

**修法两选一交 owner**:
- (KEEP)仅补「有意保留半截 facade」显性注释,不写代码,不阻塞任何批次;
- (B收敛/薄壳化)**前置硬约束**:须**先重写 monkeypatch 为身份测试**(config_contract + regression_ortools_warmstart_failure_contract.py:136 经 monkeypatch 续命),否则老路径测试红。

**禁区**:R33 删元组**死保 degradation:15**(R29 反例);若 R29 走 B 收敛触 number_utils.py,与 R04/R28 同文件边激活,须串行避免行号位移。

---

## R49 — 5处死模块别名直删 🟢绿(带定点删红线)

**判定🟢**:5行死别名(dispatch_rules:25 / evaluation:40-41 / ortools:24-25)实盘零漂移、定义后0读取(裸名调用走 due_exclusive(...)/parse_date(...))。纯删,不触灵魂线/分层/承重。A3 的 evaluation/ortools 4行与 dispatch_rules 不同文件可独立删。

**Q1/Q4/Q5**:全 N/A 或安全——直删死赋值,无承重不对称、无兜底、无收口。

**唯一红线(定点删)**:实盘确认 `core/algorithms/greedy/dispatch/sgs_scoring.py:34 def _parse_due_date(..., strict_mode=...)` 是**另一真实活函数**(:223被调),与 R49 的 `_parse_due_date = parse_date` 别名**仅重名**。同理 evaluation.py:26 `_parse_due_date_state` 重前缀活函数(:230被调)。**严禁按符号名全局删,必须按 file:line 定点**——否则误铲活函数 → NameError 炸派工评分(loud,非静默)。

**修正建议**:按 5 个精确 file:line 定点删;import 行(:9/:19)保留(真用)。

---

## R50 — mean_positive 死函数直删 🟢绿

**判定🟢**:mean_positive(dispatch_rules:112-132)生产零引用(rg=0,真实均值在 greedy/dispatch/sgs.py:150 内联 sum/len),仅 regression_dispatch_rules_nonfinite_proc_hours_safe.py:20/62-63 续命。

**Q1承重误删**:无。但实盘确认 `import math`(:3)是**真实承重边**——:78/:95/:128 三处真用(build_dispatch_key 非有限判定 + ATC math.exp + mean_positive内),误删→启动期 ImportError。dossier 正确划禁区。`import statistics`(:4)仅 :132 用,删 mean_positive 后可一并删。

**灾难链**:① 误删 import math → ImportError(响声);② 误删测试 :26-59 build_dispatch_key 回退用例 → 非有限proc_hours回退契约失保护(**静默回归**)。规避:禁区只动 :20 import名 + :61-63,死保 :26-59。

**修正建议**:删函数体先于删 import statistics;math:3保留;同 dispatch_rules.py 三债(R49/R50/R51)同一原子 diff、从大行号往小删避免互撞。

---

## R51 — 两宽容解析器直删+连退测试 🟡黄

**判定🟡**:parse_dispatch_rule(dispatch_rules:28-35)+ parse_strategy(sort_strategies:161-173)生产零引用(__all__ 不导出),严格收口点已 loud raise 在位。但灵魂线红线严苛——**测试连退禁迁**。

**Q4灵魂线热路径**:这两解析器把「非法字符串→静默回退默认枚举」固化为 API(:35 `except ValueError: return default` / :172-173 `except Exception: return default` 更宽),正是灵魂线#1 禁止的坏数据静默兜底。直删=铲兜底,**不改 raise**(收口点已 raise,改 raise 只养死壳)。

**Q5收口行为等价(故意不等价)**:实盘确认收口点 schedule_params.py:277 `SortStrategy(strategy_key)` / :346 `DispatchRule(rule_key)`(经 _require_choice loud raise);optimizer_config.py:166/189 `require_choice`(:64 loud raise)。旧宽容路 unknown→静默default vs 收口路 unknown→raise = **故意不等价**。**不写 parity 钉等价**(钉了=锁死兜底)。

**Q6测试迁移序(灵魂线红线)**:实盘确认两续命测试 :25:
- dispatch_rule_case_insensitive.py:25 `parse_dispatch_rule("unknown", default=DispatchRule.CR) == DispatchRule.CR`
- sort_strategy_case_insensitive.py:25 `parse_strategy("unknown", default=SortStrategy.DUE_DATE_FIRST) == ...`
这两行钉死的正是灵魂线禁止的「坏值静默回退默认枚举」。**严禁保留续命/迁移**——保留=把 P4 兜底钉成契约,复活已铲除的静默兜底。必须随解析器**整体退场**两测试文件。

**灾难链(复活,本债真危险面)**:不删而留死壳 → 未来有人 `from core.algorithms.dispatch_rules import parse_dispatch_rule` 复用 → 把「非法静默回退默认枚举」重新引回派工/排序参数入口,灵魂线 P4 复发**且静默不报错最难发现**。

**修正建议**:删两函数 + **连删**两测试文件(非迁移);禁区:绝不碰 :39 以下 DispatchInputs/build_dispatch_key/mean_positive + schedule_params.py/optimizer_config.py(只读确认收口点在位)。

---

## 漏项(本轮新发现没被计划覆盖的爆点/缺失前置)

1. **R33 死保行文档缺口**:dossier/arch 文档只强调「删 :14/:16/:19 死保 degradation:15」,**未明说 :17 number_utils / :18 strict_parse 也必须保留**。实盘 :355 测试用整个元组做反向 FORBIDDEN 黑名单,且 number_utils 壳因 R29 owner-pending 未删、strict_parse 壳为真模块——若执行者「图省事」把元组删剩 degradation 一条,会让 number_utils/strict_parse 壳脱离守卫。非必炸(测试仍绿),但护栏静默缩小。**建议明文:R33 删元组严格只动 :14/:16/:19,:15/:17/:18 全保留。**

2. **R30↔R31 facade 硬序边为新增**:旧 registry 未把 R31 列入 R30 interference_edges。删 shared 三常量与删 services.common re-export(:6-8/:24-26)须同窗口,这条边须显式登记进 Batch 编排,否则两债分批 merge → ImportError 打挂 facade 全表面。

3. **R33「反例壳」措辞性陷阱**:degradation 实测是真承重实现(20+生产直连)非壳。dossier 多处称「反例壳」,执行者若误读为可删 re-export 残渣 → 删 degradation → 炸 20+ 生产方。建议落地前修正措辞为「反例(真承重实现,非壳)」。

4. **R51 收口点行号软漂**:R51 dossier §6 引 `_resolve_strategy` 为 :266,实盘 :265(差1行,符号命中);schedule_params.py dispatch_rule 严格路径实盘在 :337-346(_resolve_dispatch_rule_enum→:346 DispatchRule)。仅只读软引用,不撼删除结论,但 Batch 编排引收口点行号时按符号名定位不照抄。

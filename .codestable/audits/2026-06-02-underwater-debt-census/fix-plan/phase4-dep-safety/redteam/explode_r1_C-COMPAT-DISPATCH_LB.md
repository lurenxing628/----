# 逐簇爆炸对抗 · C-COMPAT-DISPATCH · 主透镜【承重误删】 · r1

> 只读不改任何 .py。行号经 2026-06-05 当前工作区 rg 独立回盘（不照抄 dossier 旧值）。
> 主透镜 = Q1 承重误删 / fail-open / 预览冒充正式；六质问点全过。
> 成员债：R30 / R33 / R29 / R49 / R50 / R51。

---

## 总判定速览

| 债 | 判定 | 一句话 |
|---|---|---|
| R30 | 🟡 | facade 漏改→ImportError，但只炸测试（两 facade 零生产消费），是响声债非静默 fail-open；须与 R33 步3 同窗口删 facade re-export |
| R33 | 🟡 | 死保 degradation:15 + 不碰 core.shared 三模块全文 + :411 与 R30 同窗口；满足即绿 |
| R29 | 🟡 | owner-pending，KEEP 安全；薄壳化前置错指（见漏项①），且 facade 有 2 个活生产消费者，A4 漏列 |
| R49 | 🟡 | 定点删 5 行安全；按符号名全局删 `_parse_due_date` = NameError 炸 3 个活近亲（比 dossier 多一个） |
| R50 | 🟢 | 纯死叶子直删，import math 已正确划禁区，无承重不对称 |
| R51 | 🟡 | 收口点已 loud raise 在位；红线=两 case_insensitive 测试 :25「未知值→default」断言必须连退，禁迁/禁保留 |

无 🔴（无「按计划改下去会静默 fail-open / 坏数据流入生产」的爆点）。最危的两条（R30 facade、R51 续命测试）均为**响声债**（CI 红，loud），非静默失效——故全簇最高 🟡，不标红。但有 **3 处漏项**（见末节），其中漏项①是真正会让执行者「以为前置已满足、实则没满足」的隐患。

---

## R30 — compat 日期分支死切片直删 🟡

**Q1 承重误删**：✅ 干净。R30 删的是死分支（`parse_compat_date` 生产调用=0，rg 回盘仅 facade re-export + 3 测试命中），非承重不对称。回盘核 `core/shared/value_policies.py`：VALUE_DATE(:16)/VALUE_DATETIME(:17)/READ_FILTER_ONLY(:12) 三常量**仅被将删的 date 三策略用**（:183/:192-193/:202-203），存活的 13 个 float/int 策略只用 VALUE_FLOAT(:14)/VALUE_INT(:15)——删三常量不波及存活策略。禁误删行（compat_parse.py:9-17 float/int import + :129-195 函数体；value_policies.py:14-15 + :43-178 float/int 策略）回盘属实，dossier 字段4/9 列禁区正确。**无以 DRY/统一名义抹承重不对称**。

**Q5 收口等价**：N/A（纯删，非收口）。dossier 字段7 已正确澄清 date 回退语义（invalid_due_date）与 float（invalid_number）不可统一，无误把死分支当「该统一」处理。✅

**爆点（为何 🟡 而非 🟢）**：facade re-export 漏改。回盘 `core/services/common/value_policies.py:6-8`（import READ_FILTER_ONLY/VALUE_DATE/VALUE_DATETIME from shared）+ `:24-26`（__all__）。R30 删 shared 三常量后，**只要这个 facade .py 壳还在**，`import core.services.common.value_policies` 即 ImportError。
**灾难链**：R30 删 shared:12/16/17 → 若 R33 步3（删三 .py 壳）落在**更晚批次**（cluster 说 B13 facade「晚于 B05/B06 收敛」）→ 存在窗口：shared 常量已无、facade 壳仍 re-export → `core.services.common.value_policies` import 即炸 → `config_service_component_contract.py:393`（`from core.services.common import value_policies`）+ `matrix_contract.py:18`（经 facade 取 READ_FILTER_ONLY/get_field_policy）红。
**但降级为 🟡 的关键证据**：rg `from core.services.common.value_policies` 在 core/web/data/scripts **零生产命中**——该 facade 与 compat_parse facade **均无活生产消费者，只有 3 个测试 import**。所以这是 **CI 响声债**（loud ImportError，立即可见），**不是静默 fail-open，坏数据不会流入生产**。cluster/dossier 称「打挂 facade 全表面 / 存活消费者」**夸大**——存活的只有测试面。

**修正建议（顺序/禁区）**：
1. 硬绑定：R30 删 shared 三常量 与 R33 步3 删 value_policies .py 壳 **必须同一 PR/同窗口**，禁跨批（cluster A1 把 R33 步3 排在「之后」是对的，但须强调「同窗口」非「后续批次」）。
2. 删前先做 R33 步1（迁 matrix:18 + emits_degradation:18 import 到 core.shared），否则违序 → :18 ImportError + :411 AttributeError（响声，非灾难）。
3. 禁区行死守 dossier 字段9 清单。

## R33 — 三 re-export 壳直删 🟡

**Q1 承重误删**：✅。三壳回盘 def/class=0（纯 re-export，已 rg 确认）。承重点 `core.shared.{compat_parse,field_parse,value_policies}` 是禁区（R33 绝不碰），手滑删即炸 schedule_input_builder/external_groups 等真直连方——属「越界」，靠禁区铁律拦，非本债动作本身的不对称。

**Q6 测试迁移序 + 静默风险**：⚠ 唯一真静默点 = `_SERVICE_COMMON_NEUTRAL_HELPERS` 元组 :15 `core.services.common.degradation`。回盘确认 degradation **不是壳、是真承重实现**（385B，DegradationCollector 等，:375-383 身份测试在场，20+ 生产直连）。R33 删元组只动 :14/:16/:19，**死保 :15**——若连带删 :15，degradation 中性白名单/身份续命约束丢失（静默：日后 degradation 被误删将无测试拦）。dossier §3「反例壳」措辞瑕疵已被其对抗核验如实标注（应为「反例·真承重实现非壳」），不撼修法。

**修正建议**：①删元组只删 :14/:16/:19，死保 :15 + :355 白名单逻辑 + :375-383 degradation 身份测试；②:411 与 R30 同窗口删；③三 .py 壳删 = R30 删 shared 常量同窗口（见 R30 修正建议1）。满足即 🟢。

## R29 — number_utils delegation facade（owner-pending，只标不给终态）🟡

**Q1 / owner-pending 守则**：✅ 只标不给终态。registry `owner_pending=True` 回盘属实。`core/services/common/number_utils.py` 回盘为全量 delegation-facade（:5-10 import core.shared.strict_parse，:13-40 parse_finite_float/int 薄壳 + allow_none 兼容形态）——半截迁移不对称客观在场。**KEEP（补「有意保留」注释，不写代码）= 安全终态**，不阻塞任何批次。

**爆点（owner 若选薄壳化）**：A4「前置硬约束：先重写 monkeypatch 为身份测试」**指错文件**（见漏项①），且 **facade 有 2 个活生产消费者**（漏项②），A4 全未提。若 owner 按 A4 薄壳化/内联，会漏改这 2 个生产 import 站点 + 误退错误的测试。**本 Layer 只标 owner-pending，不给终态，红线维持。**

## R49 — 5 处死模块别名定点删 🟡

**Q1 承重误删**：✅ 定点删 5 行（dispatch_rules.py:25 / evaluation.py:40-41 / ortools_bottleneck.py:24-25，回盘逐行命中，0 漂移）安全，import 行保留（裸名调用仍活：evaluation.py:257 `due_exclusive(...)` 等）。

**最大爆点 = 同名陷阱（比 dossier 更严重）**：dossier 列 2 个活近亲（sgs_scoring.py:34 `_parse_due_date` + evaluation.py:26 `_parse_due_date_state`）。**我回盘多抓出第 3 个**：`core/algorithms/ordering.py:59 _parse_due_date_for_sort`（:93 被调，且经 `greedy/scheduler.py:20/:49` re-export）。三个活的同前缀/同名函数。
**灾难链**：若按符号名全局删 `_parse_due_date` → 铲掉 sgs_scoring.py:34 活函数 → :223 调用 NameError → 派工评分链炸（loud，启动期）。
**修正建议**：**严禁按符号名删，必须 file:line 定点删 5 行**；禁区 = sgs_scoring.py:34/:223 + evaluation.py:26 + **ordering.py:59/:93（dossier 漏列，补入禁区）** + 三文件 import 行。

**Q2 分层**：✅ 纯删不新增 import，core.shared/algorithms 三解析模块均无 import core.services（已 rg NONE）。

## R50 — mean_positive 死函数直删 🟢

**Q1**：✅ 唯一全簇 🟢。`dispatch_rules.py:112-132` 死函数（生产调用=0，真均值在 greedy/dispatch/sgs.py:169 内联 sum/len），删函数 + 删 `import statistics`(:4，全文件仅 :132 用）安全。**承重边 `import math`(:3) 已被 dossier 正确划禁区**（:78/:95 真用），未误删。外科退测试只动 safe.py:20 import 名 + :61-63，禁区 :26-59 build_dispatch_key 回退活契约。无承重不对称、无 fail-open、无灵魂线触碰。

## R51 — 两宽容解析器直删 + 连退续命测试 🟡

**Q4/Q1 灵魂线**：⚠ 红线在场但方向正确。回盘两测试 :25 = `# 未知值回退 default` + `assert parse_*("unknown", default=X) == X`——**正是灵魂线禁止的「坏值→静默回退 default」P4 兜底**。收口点已 loud raise 在位（schedule_params.py:71/:272/:277/:341/:346 require_choice→Enum；optimizer_config.py:64/:166/:189），回盘逐行命中。
**灾难链（若违红线）**：若为救 CI 保留/迁移这两 :25 断言 → 把 P4 兜底语义钉成契约 → 死壳复活风险（有人 `from ...dispatch_rules import parse_dispatch_rule` 复用，把静默兜底引回派工/排序入口，最难发现）。
**修正建议**：删 `dispatch_rules.py:28-35` + `sort_strategies.py:161-173` 两函数，**两测试整体退场（删文件），禁迁移、禁保留 :25 断言、禁保留函数改 raise**（生产零引用，改 raise 只养死壳；严格入口已 raise）。

**Q6 行号互撞**：R51 删 dispatch_rules.py 首函数(:28-35)使 :39 以下全上移 ~7 行 → R49(:25 在其上，不动)/R50(:112) 须同 diff 按符号名定位，禁跨批盲删旧绝对行号。✅ cluster A2 已覆盖。

---

## 本轮新发现漏项（计划未覆盖的爆点 / 缺失前置）

**漏项①（中危·会误导执行者）**：cluster A4 + corrections E 称 R29 薄壳化前置「先重写 monkeypatch 为身份测试（…regression_ortools_warmstart_failure_contract.py:136 经 monkeypatch 续命）」——**指错文件**。回盘 `regression_ortools_warmstart_failure_contract.py:136` 是 `_install_fake_cp_model` monkeypatch sys.modules['ortools…']，**与 number_utils 无关**。真正 monkeypatch number_utils 续命的是 `tests/regression_number_utils_facade_delegates_strict_parse.py:45-48`（`number_utils.parse_required_float = fake_*` 等 4 处赋值替换 + :67 「未转调 strict_parse 门面」断言）。执行者若按 A4 去改 warmstart 测试，会**以为前置已满足而实则没动真续命点** → 薄壳化后 facade_delegates 测试红。

**漏项②（中危·A4 漏列）**：R29 facade **有 2 个活生产消费者**，A4/E 均称「死壳/半截迁移」未提消费者：`web/routes/domains/scheduler/scheduler_excel_calendar_rows.py:8` + `core/services/common/excel_validators.py:26` 均 `from core.services.common.number_utils import parse_finite_float`。故 R29 是**活 delegation facade**（非死壳）；KEEP 安全，但薄壳化/内联须同步改这 2 个生产 import 站点，A4 缺失此前置 → 漏改即 ImportError 炸生产 Excel 校验/日历行路径。

**漏项③（低危·文档自相矛盾）**：cluster C 节称「新 R30↔R31：旧 registry 未把 R31 列入 R30 interference_edges，补一条」——**与 registry 不符**。回盘 `_registry.json` R30.interference_edges **已含** `{'other':'R31', same_file:True, why:[value_policies.py, compat_parse.py]}`。该边非新增，原已存在；仅「跨桶硬序」框架是新的。不撼安全结论，但 cluster 的「补一条新边」叙述失实，应改为「升级既有 same_file 边为跨桶硬序」。

**附**：R49 禁区 dossier 漏列 `ordering.py:59/:93 _parse_due_date_for_sort`（第 3 个同前缀活函数），已在 R49 段补入——按符号名删的风险面比 dossier 描述大一个函数。

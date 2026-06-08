# 逐簇爆炸对抗 r2 · 簇 C-COMPAT-DISPATCH · 主透镜【灵魂线热路径 + 收口等价】

> skeptic 第 2 轮，只读不改，默认怀疑。回盘时间 2026-06-05，行号全部当前工作区 rg 实证（不信旧值）。
> 成员债：R30 / R33 / R29 / R49 / R50 / R51。主透镜聚焦 Q4(灵魂线热路径)/Q5(收口等价)/Q6(测试迁移序)，兼过 Q1/Q2/Q3。
> R29 dossier 缺失（dossiers/ 仅 5 份，无 R29.md）——见末尾【漏项】。

---

## 逐债判定

### R51 — 删两宽容解析器 + 连退续命测试 🟡黄（有条件，灵魂线红线债，主透镜核心）

**判定 🟡**：本体生产零引用（rg 实证），但**修法本身就是灵魂线手术**，做对则绿、做错则把已铲的 P4 静默兜底复活，故黄不绿。

**当前证据（回盘）**：
- `core/algorithms/dispatch_rules.py:28` `def parse_dispatch_rule`；`:33 return DispatchRule(str(value).strip().lower())`，`:34-35 except ValueError: return default`（静默回退）。
- `core/algorithms/sort_strategies.py:161` `def parse_strategy`；`:172-173 except Exception: return default`（裸 except 吞一切，比 dispatch 更宽）。
- 收口点 loud raise **全部在位**：`schedule_params.py:272/277`（`_require_choice`→`SortStrategy()`）、`:341/346`（→`DispatchRule()`）；`optimizer_config.py:64 require_choice`，`:68/:77/:85 raise ValidationError`，`:166/:189` 收口调用。
- 两续命测试 :25 兜底断言实证：`regression_sort_strategy_case_insensitive.py:25 assert parse_strategy("unknown", default=...) == ...`；`regression_dispatch_rule_case_insensitive.py:25 assert parse_dispatch_rule("unknown", default=...) == ...`——**这正是灵魂线禁止的「坏值静默回退默认枚举」**。

**收口等价核（Q5）**：旧宽容路 vs 严格收口路**故意不等价**——未知值/空串：旧路静默 default，收口 loud raise ValidationError。这是要铲的差异，**严禁写 parity 钉等价**（钉了=把兜底锁死），也**严禁保留/迁移 :25 兜底断言续命**（保留=把 P4 钉成契约）。dossier 红线正确。

**灾难链（条件→红/复活）**：
1. 删函数但**保留/迁移 :25 兜底测试** → 把静默回退默认枚举语义钉成契约，未来有人 `from core.algorithms.dispatch_rules import parse_dispatch_rule` 复用 → P4 静默兜底回流到派工/排序参数入口，**最难发现的灵魂线复发**。
2. 删函数但**未连删两测试** → import 失败 CI 红；或更糟，有人为救 CI 把兜底迁回别处。
3. 误删到收口点 `schedule_params.py:277/346` 或 `optimizer_config.py:166/189` → 生产 string→enum 丢校验，非法枚举静默入排产。

**修正建议**：① 删 `dispatch_rules.py:28-35` + `sort_strategies.py:161-173` 两整函数；② **整体退场**（非迁移、非保留）两续命测试；③ 前置只读确认收口点 loud raise 在位（已确认）；④ 同 A2 原子 diff（见 R49/R50），删后按符号名重盘 R49/R50 行号。

### R69 坏 seq 静默归 0 —— 本簇无此债

R69 不在本簇成员（C-COMPAT-DISPATCH 成员为 R30/R33/R29/R49/R50/R51）。主透镜清单中的 R69「坏 seq 静默归 0」属他簇，本轮不裁。**最接近的同形 sentinel 是 N2**（`operation_execution_event.py:156-163 return 0`），亦不在本簇文件内，本簇不触碰。

### R30 — 删 date 死切片 🟡黄（facade re-export 爆炸点 + 删序耦合）

**判定 🟡**：纯 P6 直删、生产零消费（`parse_compat_date(` 全仓调用=0），**不落灵魂线热路径**（坏日期生产走 `_sched_display_utils.py record_bad_time_row` 独立路径，绕开 value_policies 三策略），故非 Q4 风险。黄的原因是 **facade re-export 删序爆炸点 + import 块误删边界**。

**当前证据（回盘）**：
- `core/shared/value_policies.py:12 READ_FILTER_ONLY` / `:16 VALUE_DATE` / `:17 VALUE_DATETIME`；三 date 策略 `:180 due_date` / `:190 start_time` / `:200 end_time`。
- facade 壳 `core/services/common/value_policies.py:6-8` re-export 三常量 + `:24-26 __all__`——**删 shared 三常量必与删壳同窗口，否则壳 import 即 ImportError 打挂 facade 全表面**（本债最大爆炸点，dossier 字段8第7点）。
- **删序耦合实证**：矩阵契约测试 `regression_value_policies_matrix_contract.py:18 from core.services.common.value_policies import (... READ_FILTER_ONLY ...)`——同时依赖**壳路径**（R33 步骤1 须先迁到 core.shared）+**三常量**（R30 删）。这就是 Q6 的硬序根：R33 步骤1 迁 import → R30 删常量/策略 → R33 步骤2/3 删壳+:411。

**import 块误删边界（Q1 承重误删反例）**：`core/shared/compat_parse.py:9-17` import 块里 `:11 parse_optional_date` / `:14 parse_required_date` 是 date 专用可删，但 `:10 is_blank_input` / `:12 parse_optional_float` / `:13 parse_optional_int` / `:15 parse_required_float` / `:16 parse_required_int` 被存活的 `parse_compat_float(:153)` / `parse_compat_int(:177)` 用——**误删整块即 NameError 炸排产输入解析**。另 `:18-20 from core.shared.value_policies import (READ_COMPAT, VALUE_DATE...)`：删 `VALUE_DATE` import 须精确单行，`READ_COMPAT(:19)` 是 float/int 用，禁连删。

**灾难链**：删三常量但漏改 facade `:6-8/:24-26` → `core.services.common.value_policies` 模块 import 即 ImportError → 连带打挂矩阵契约测试（经此壳取 READ_FILTER_ONLY）+ 任何存活 `from core.services.common.value_policies import` 方。

**修正建议**：① R33 步骤1 必先（迁矩阵+降级两测试 import 到 core.shared）；② R30 删常量须与 R31/B13 facade re-export 删除**同批/同窗口**；③ import 块按行精确删，死保 float/int/is_blank_input/READ_COMPAT；④ 与 R29 同改 value_policies.py 时串行避免行号位移。

### R33 — 删三 re-export 壳 + 迁/退测试 🟡黄（degradation 反例理由须更正 + 三步硬序）

**判定 🟡**：三壳 def=0 纯 re-export、生产零消费（`core.services.common.{compat_parse,field_parse,value_policies}` 生产 grep=0），**不落灵魂线、不收口、纯减法**，故非 Q4/Q5 风险。黄的原因是三步删序神圣 + degradation 死保 + 测试迁序（Q6）。

**重大更正（dossier 第二双眼睛错判，本轮回盘推翻）**：dossier R33 §对抗核验称 `core/services/common/degradation.py` 是「385B **真实现模块**、被 20+ 处生产直连」——**回盘证伪**：该文件实测 **17 行纯 re-export 壳**（`:3-9 from core.shared.degradation import ...` + `:11-17 __all__`），与三壳同性质。`:15 degradation` 元组条目仍须死保，但**正确理由是**：① 它有独立身份测试 `config_contract:375-390 test_services_common_degradation_reexports_shared_identity`；② `:350 test_scheduler_run_uses_shared_parse_and_degradation_helpers` 的 forbidden 白名单靠 `_SERVICE_COMMON_NEUTRAL_HELPERS` 放行 scheduler_run 对 degradation 的合法引用——**不是因为 degradation 是真承重实现**。R33 删元组只动 :14/:16/:19、死保 :15 的结论不变，但执行者不可据「degradation 是真实现」误判其不可删（它同样是壳，只是 R29/本轮不删它）。

**:411 交界行确认**：`config_contract:411 assert service_compat_parse.parse_compat_date is shared_compat_parse.parse_compat_date`——R30 删 parse_compat_date 后此行 AttributeError，须 R33 步骤2 同步删（响声债非静默，CI 即见）。

**forbidden :350 测试行为反转核（Q6 隐患）**：`:355 if imported.startswith(_SERVICE_COMMON_NEUTRAL_HELPERS): violations.append`——该测试断言 scheduler_run **不得** import 三壳。R33 删元组三条**缩小白名单**；当前生产零引用三壳（rg 实证空），故缩白名单不致红。**但若删壳前有任何 scheduler_run 文件偷偷 import 三壳，删元组会使其从「白名单放行」变「violation 红」**——前提是生产零引用，已实证成立，安全。

**修正建议**：① 严守三步硬序 R33步1(迁 emits_degradation:18 + matrix:18 两 import 到 core.shared)→R30(删实现)→R33步2/3(删 :411 身份断言+:14/:16/:19 元组三条+三 .py 壳)；② 死保 :15 degradation + :375-390 身份测试 + :355 forbidden 逻辑；③ 绝不手滑碰 core.shared 三模块全文（生产直连方全炸）；④ dossier owner 顺手更正「degradation 真实现」措辞为「同性质壳，本轮不删」。

### R29 — number_utils 薄壳 owner-pending 🟡黄（只标不给终态，薄壳化前置须先重写 monkeypatch）

**判定 🟡（owner-pending，只标不给终态）**：number_utils 仍全量 delegation-facade 到 core.shared.strict_parse（`:5 from core.shared.strict_parse import` + `:14/:31 parse_finite_float/int` 薄壳）。半截迁移不对称客观在场。授权 CSV：`docs/_panorama_data/phase4_dep_safety/*.csv` 无匹配（ABSENT 证实）。

**薄壳化前置硬约束（Q6，dossier A4 正确但续命点指错——本轮纠正）**：dossier A4/Layer1 称 monkeypatch 续命点是 `regression_ortools_warmstart_failure_contract.py:136`——**回盘证伪**：该文件 monkeypatch 的是 `sys.modules["ortools..."]`（:81-84）与 `builtins.__import__`（:109），**与 number_utils 无关**。真正的 number_utils monkeypatch 续命点是 **`tests/models_domain/test_number_utils_facade_delegates_strict_parse.py:45-48`**（`number_utils.parse_required_float = fake_...` 替换四个 delegate 目标，:50-55 验薄壳真转调 strict_parse）。**薄壳化（收编 number_utils）后这套 monkeypatch 失去 patch 目标会失效，须先把它重写为身份测试**（断言 `number_utils.parse_finite_float is shared.parse_finite_float`），否则老路径测试红。

**修正建议**：本 Layer 只标 owner-pending。(KEEP) 仅补「有意保留半截 facade」显性注释 + 上交 open_question；(B 薄壳化) **前置**先重写 `regression_number_utils_facade_delegates_strict_parse.py` 的 monkeypatch 为身份测试，再收编。**不给终态**。

### R49 — 删 5 行死模块别名 🟢绿（同名陷阱已锁定）

**判定 🟢**：5 行 `_due_exclusive`/`_parse_due_date` 别名定义后 0 读取（rg 实证），纯死赋值直删，不触灵魂线/收口/承重/分层。回盘零漂移：`dispatch_rules.py:25` / `evaluation.py:40-41` / `ortools_bottleneck.py:24-25`。

**唯一红线（已锁定，非风险）**：`sgs_scoring.py:34 def _parse_due_date(value, *, strict_mode)` + `:223` 调用 是**同名活函数**，`evaluation.py:26 _parse_due_date_state` 重前缀活函数——**严禁按符号名全局删，必按 file:line 定点**，否则误铲炸派工评分（loud NameError，非静默）。

**修正建议**：定点删 5 行；import 行（:9/:19）保留（裸名调用 evaluation.py:257 等仍活）；dispatch_rules.py:25 那行卷入 A2 原子 diff，另 4 行（evaluation/ortools）可独立删无序约束。

### R50 — 删 mean_positive + import statistics 🟢绿（math 保留已实证）

**判定 🟢**：`dispatch_rules.py:112 def mean_positive` 生产零消费（真实均值走 `greedy/dispatch/sgs.py:169 sum/len`），纯死代码直删，不触灵魂线。

**收口等价澄清（Q5 反例，非债）**：mean_positive（忽略 Inf/≤0、空→0.0）与 sgs `_average_proc_hours`（sum/len、无样本走 fallback 打点）**故意不等价**，但 mean_positive 零生产调用，差异不进生产路径，故直删不迁语义、不写 parity。

**import 边界实证**：`import statistics(:4)` 仅 mean_positive 用（删函数后可删）；`import math(:3)` **保留**——回盘 `math.` 用在 `:78`（build_dispatch_key 非有限判定）/ `:95`（ATC math.exp）/ `:128`（mean_positive 内），:78/:95 是 mean_positive 外活用量，误删 math → 启动 ImportError（loud）。

**修正建议**：删 `:112-132` 整函数 + `:4 import statistics`；死保 `:3 import math`；外科退测试 `regression_dispatch_rules_nonfinite_proc_hours_safe.py:20`（仅去 mean_positive 一名，留 DispatchInputs/DispatchRule/build_dispatch_key）+ 删 :61-63，**死保 :26-59 build_dispatch_key 回退活契约**（误删=非有限 proc_hours 回退失去回归保护=静默回归）；同 A2 原子 diff。

---

## 簇级编排底线（Q6 测试迁移序汇总）

- **A1 硬序（响声债，违序 CI 红非静默）**：R33步1(迁 matrix:18+emits_degradation:18 import 到 core.shared) → R30(删 shared 实现+三常量，须与 R31/B13 facade 同窗口删 re-export) → R33步2/3(删 :411+元组三条+三壳)。
- **A2 同 diff（行号互撞，非运行期序）**：R49/R50/R51 同改 dispatch_rules.py，按符号名/行号快照一次性删，从大行号往小删。R51 删首函数 :28-35 致下方上移 7~8 行，删后按符号名重盘 R49(:25→上移)/R50(:112→上移)。
- **分层(Q2)**：6 债全纯减法 0 新增 import，0 越层 0 导入环；shared 三模块未 import core.services（实证）。
- **迁移耦合(Q3)**：本簇不碰 schema/v18/v19 DB CHECK，无迁移耦合。
- **承重(Q1)**：6 债全 lb=false，无承重点门控；禁区行=core.shared 三模块全文 / degradation :15+:375-390 / forbidden :355 / import math:3 / compat_parse float-int import 块 / sgs_scoring:34 同名活函数 / 收口点 schedule_params+optimizer_config 全文只读。


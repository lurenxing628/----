# 逐簇爆炸对抗 · C-COMPAT-DISPATCH · 透镜=LAYER(分层导入环+迁移耦合) · 第1轮

> skeptic 只读不改。回盘 2026-06-05 当前工作区。主透镜：Q2 分层导入环 / Q3 迁移耦合为重，六质问全过。
> 成员债 R30 / R33 / R29 / R49 / R50 / R51。锚点全部 rg 实证零漂移（见末尾回盘台账）。

## 主透镜结论（先行）

- **Q2 分层导入环：0 违规，安全。** `core/shared/{compat_parse,value_policies,field_parse}.py` 三模块 import 仅 stdlib/dataclasses（实证 value_policies.py:3 `from dataclasses` 是唯一非 typing import；三文件无任何 `core.services` / `core.algorithms` / `data` / `web`）。本簇 6 债**全是删除动作，不新增任何 import**，只会缩小既有单向边 `core.services.common.* → core.shared.*`，**不可能**造出 `core.models→core.services` / `core.algorithms→core.services` / repo→service 越层或导入环。R29 number_utils 仅 import `core.shared.strict_parse`（合法下沉）。
- **Q3 迁移耦合：本簇不碰 v18/v19 DB CHECK、不碰 schema、不碰 effective_plan_role/source_table。** 6 债全在 `core.shared` / `core.services.common` 壳 / `core.algorithms` 纯函数层 + tests，与 adopted-only v19 CHECK 探针零交集。**无「改码不改迁移=启动探针炸」风险。**
- 真正的爆点不在分层/迁移，而在 **A1 删序**（R30↔R33↔R31 ImportError 链）与 **R51 灵魂线**（连退兜底测试，禁续命）+ **R49 同名陷阱**（sgs_scoring 重名活函数）。

---

## 🟢 R49 — 5 行死模块别名（dispatch_rules:25 / evaluation:40-41 / ortools:24-25）

判定 **🟢绿（A3 的 4 行可独立；dispatch_rules:25 卷入 A2 同 diff）**。
- 证据：`evaluation.py:40-41`、`ortools_bottleneck.py:24-25`、`dispatch_rules.py:25` 五处死别名全命中零漂移；右值 `due_exclusive`/`parse_date` 仍被裸名真调用（evaluation:257、ortools:138/140）→ 删别名不致 import 变死。
- Q2/Q3：纯删 5 行不新增 import、不碰迁移 → 0 越层 0 环 0 探针。
- **唯一红线（已被计划锁死，故仍绿）**：`sgs_scoring.py:34 def _parse_due_date(strict_mode=...)` 是重名活函数、`evaluation.py:26 _parse_due_date_state` 重前缀活函数。**严禁按符号名全局删**，必须 file:line 定点删，否则 NameError 炸派工评分。计划字段3/A2 已明列定点删红线 → 守住即绿。

## 🟢 R50 — mean_positive 死函数 + import statistics（dispatch_rules:112-132 / :4）

判定 **🟢绿（A2 同 diff，建议末尾删）**。
- 证据：`mean_positive`@:112、`import statistics`@:4、`import math`@:3 全命中；wc=132 确认 mean_positive 是文件末函数。`statistics` 仅 :4+:132 两处 → 删函数后可连删 import；`math` 在 :3/:78/:95/:128 有真用 → **:3 必保留**（误删即启动 ImportError）。
- Q2/Q3：纯删不新增 import、不碰迁移 → 安全。
- 禁区：测试 `regression_dispatch_rules_nonfinite_proc_hours_safe.py` 仅退 :20 import 名 + :61-63 用例，**死保 :26-59 build_dispatch_key 回退活契约**（误删→非有限 proc_hours 回退失去回归保护=静默回归）。

## 🟡 R33 — 三 re-export 壳 facade（core/services/common/{compat_parse,field_parse,value_policies}）

判定 **🟡黄（条件：A1 硬删序 + 死保 degradation:15 + 不碰 core.shared）**。
- 证据：三壳 def=0 纯 re-export；生产零消费（scheduler/run 仅 import `core.services.common.build_outcome`，从不碰这三壳，实证）；续命点仅 3 测试（emits_degradation:18 / matrix_contract:18 / config_contract:14/16/19/355/393-411）。
- Q2：删壳纯减法，`core.services.common.*→core.shared.*` 单向下沉，0 新 import 0 环。守卫 `config_contract:355 startswith(_SERVICE_COMMON_NEUTRAL_HELPERS)` 是**禁 run 层碰这三壳的分层闸**——删壳后该断言仍恒真（run 层本就不碰），不破。
- 条件1（删序硬约束）：**R33 步骤1（迁 emits_degradation:18 + matrix_contract:18 import → core.shared）必须最先**，否则 R30 先删 shared 实现→:18 ImportError、:411 AttributeError（响声债非静默，CI 可见）。
- 条件2（静默禁区，本债真危险）：`_SERVICE_COMMON_NEUTRAL_HELPERS:15 degradation` 是 R29 有意保留反例，且 degradation 是**真承重实现（非壳，20+ 生产直连）**。删元组只动 :14/:16/:19，**死保 :15** + 配套身份测试 :375-384。误删=degradation 白名单/身份续命约束静默丢失。
- 条件3：手滑删到 `core.shared.{三模块}` 全文 → 炸生产直连方（schedule_input_builder/external_groups），靠「R33 不碰 core.shared」铁律拦。

## 🟡 R30 — compat date 死切片（shared/compat_parse + shared/value_policies）

判定 **🟡黄（条件：A1 删序 + R31/facade 同窗删 re-export + 禁误删 float/int 同块名）**。
- 证据：`parse_compat_date`@:198 / `_date_fallback`@:143 / date import :11/:14 / 三 FieldPolicy 179-208 / 三常量 :12/:16/:17 全命中零漂移；生产 `parse_compat_date(` 调用=0；三常量真生产消费者=0（仅 shared 自身 + facade re-export，实证）；坏时间生产走 `_sched_display_utils.record_bad_time_row` 绕开三策略。
- Q2/Q3：shared 层删除不新增 import、不碰迁移/CHECK → 0 越层 0 环 0 探针。
- 条件1（A1 删序）：R33 步骤1 先迁 import → R30 删实现 → R33 步骤2 删 :411。违序=测试红（响声非静默）。
- 条件2（**本债最大爆点，facade 漏改→ImportError 打挂全表面**）：删 `READ_FILTER_ONLY/VALUE_DATE/VALUE_DATETIME` 三常量必须与 `core/services/common/value_policies.py:6-8 import + :24-26 __all__`（R31/B13 facade）**同窗删或 facade 先收**，否则 services.common.value_policies 模块导入即 ImportError，连带打挂矩阵契约测试（经此取常量）。回盘 facade re-export 三常量 :6-8/:24-26 在位属实。
- 条件3（禁误删禁区）：同 import 块 `parse_optional_float/required_float/optional_int/required_int/is_blank_input` 服务存活的 `parse_compat_float/int`（:153-195），误删即 NameError 炸排产输入解析。
- Q5 收口等价：R30 是直删非收口，无 parity 义务；date 回退语义（invalid_due_date→None）与 float/int（invalid_number）**不可统一**，禁当「该收口」处理——计划已正确澄清，绿。

## 🔴 R51 — parse_dispatch_rule + parse_strategy 宽容解析器（dispatch_rules:28-35 / sort_strategies:161-173）

判定 **🔴红（灵魂线红线，序错/续命即复活 P4 静默兜底）**。
- 灾难链（Q6 测试迁移序 + Q4 灵魂线）：改X=删两宽容解析器但**保留/迁移 :25 兜底续命测试**（`parse_strategy("unknown", default=X)==X` / `parse_dispatch_rule("unknown")` 静默回退）→ 静默=「坏值→静默回退默认枚举」被钉成契约 → 坏数据流到Y=未来有人 `from core.algorithms.dispatch_rules import parse_dispatch_rule` 复用，把已铲除的 P4 静默兜底重新引回派工/排序参数入口，**坏 dispatch_rule/sort_strategy 静默落默认值进排产，不报错最难发现**。
- 为何标红而非黄：本债是全簇唯一 **medium + 灵魂线违例 + P3 死壳**叠加。证据 `sort_strategies.py:170 if not s: return default` / :172 `except Exception` 裸吞 / :173 `return default`；续命测试 :25 兜底断言实证在位（sort_strategy:25 / dispatch_rule:25）。多维度存疑（删序 + 续命禁令 + 复活面），按默认怀疑标红。
- 收口点已在位（Q5）：`schedule_params.py:277 SortStrategy(_require_choice(...))`、:346 `DispatchRule(...)`、`optimizer_config.py:166/189 require_choice` loud raise，全实证在位 → 删旧宽容路安全的前提成立。
- **强制条件（达成才能转绿）**：① 两续命测试 `regression_dispatch_rule_case_insensitive.py` + `regression_sort_strategy_case_insensitive.py` **整体退场，禁迁移、禁保留 :25 兜底断言**（保留=续命=违灵魂）；② 禁「保留函数只改 except→raise」养死壳；③ A2 同 diff 按符号名定位（删 :28-35 首函数致下方上移 7~8 行，R49:25/R50:112 须重盘）；④ 禁碰 :39 以下 DispatchInputs/build_dispatch_key + schedule_params/optimizer_config 收口点全文。
- Q2/Q3：纯删不新增 import、`__init__.py:14` 只导出 SortStrategy 枚举非 parse_*（实证）→ 删后无 __init__ 孤儿；不碰迁移。分层本身绿，红仅因灵魂线。

## ⏸ R29 — number_utils 全量 delegation-facade（owner-pending，只标不给终态）

判定 **⏸ owner-pending（不进任何删除批；本 Layer 只标不给终态）**。
- 证据：`common/number_utils.py:5 from core.shared.strict_parse import` + `parse_finite_float`(:14/19/23 overload)/`parse_finite_int`(:31/36/40) 全量薄壳 delegate，半截迁移不对称客观在场；生产消费者真实存在（`web/.../scheduler_excel_calendar_rows.py`、`core/services/common/excel_validators.py` 经 facade import parse_finite_float/int）→ 非死壳，不可与三壳同等直删。
- Q2：number_utils 仅 import core.shared.strict_parse（合法下沉），0 越层 0 环。
- 修法两选一交 owner：(KEEP) 仅补「有意保留半截 facade」显性注释，不阻塞任何批；(B 薄壳化) **前置硬约束**：须先重写 monkeypatch 为身份测试（config_contract + warmstart_failure_contract:136 经 monkeypatch 续命），否则老路径测试红。**本 Layer 不给终态。**
- 禁区伴随（非前置）：R33 删元组死保 :15 degradation（R29 反例），degradation 是真承重实现非壳。

---

## 漏项 / 本轮新发现（计划未显式覆盖的爆点 / 缺失前置）

1. **R33 步骤1 漏迁 emits_degradation:19 degradation import**：实证 emits_degradation.py 同时有 :18 compat_parse + **:19 `from core.services.common.degradation import DegradationCollector`**。计划只点 :18 要迁，**未提 :19**。degradation 壳是 R29 有意保留（非 R33/R30 删），故 :19 **不应迁也不应删**——但若执行者机械「把该测试所有 services.common import 都迁走」会误动 :19，破坏 degradation 反例覆盖。需显式标注：**emits_degradation 仅迁 :18，:19 degradation import 死保不动**。
2. **守卫 `config_contract:355` 是分层硬闸，删壳后须确认仍绿但不需迁**：该 FORBIDDEN 白名单（禁 scheduler/run 可达文件 import 这三壳 + degradation）删壳后恒真（run 层本就不碰），但删 :14/:16/:19 元组三条会**缩小白名单**——需确认 :355 断言体 `violations==[]` 不因元组缩短而把某个仍合法的 import 误判为违规（degradation:15 留下，build_outcome 等不在元组内，应安全，但需 Layer4 跑一次该测试自证）。
3. **A1 与 A2 跨子簇无序约束、但同属 Batch-7**：A1{R30,R33}（B06 shared/壳）与 A2{R49,R50,R51}（dispatch_rules 同文件）物理无交集、可并行，但若同一 PR 落地需注意 R31/facade 删 re-export 的窗口对齐（R30 条件2）——R31 不在本簇但是 R30 的硬协同邻居，**缺 R31 的同窗编排=R30 facade 漏改爆点无人兜**。

## 07 · core-models（领域模型 `core/models/`）

**分区健康一句话**：地基总体健康、收口点本身干净自律——两条真护栏（`EvidenceLink.validate()` 严格校验可信来源 + `coercion` 引擎 strict_mode 抛错/否则记可见 degradation 事件）恰是灵魂暗线"不自欺"的正面实现，全分区主病只有一处分量级 P3（配置快照整栈双实现，靠人工锁步同步、当前未漂移属潜伏）、一处活的 legacy 错误串往返桥（P3），外加三处 grep 实证的死代码/死参数（P6）。

> 复核范围：本分区 5 条 finding 涉及的 5 个主文件（`schedule_config_runtime_snapshot.py` / `schedule_config_runtime_coercion.py` / `scheduler_public_errors.py` / `greedy/config_adapter.py` / 服务侧孪生 `config/config_snapshot.py`）经 `git status --porcelain` 核对**均不在本次 modified/added 集合内**（最近改动分别停在 `ef244b9e`/`ed695e79`/`fd520b09`/`8ec5b40b`/`ed695e79`，均为 5 月及更早），修复 agent 未触碰。所有引用行号已逐条回到当前代码 grep 复核，**5 条证据全部仍准**。

---

### 07-1 · 【P3 · medium · ⚠️load_bearing=true】ScheduleConfigSnapshot 配置快照/校正引擎整栈双实现，锁步手工同步

> ⚠️ **承重护栏条目**：这套双实现不是可以一删了之的残渣，它当前真正承重（算法层在跑），删任一侧都会断链。它缺的是"我是故意的"注释——见文末补丁文案。

**位置**（整组 5 文件 + 服务侧孪生整组）：
- 模型栈：`core/models/schedule_config_runtime_snapshot.py`、`schedule_config_runtime_coercion.py`、`schedule_config_runtime_fields.py`、`schedule_config_runtime_read.py`、`schedule_config_runtime_weights.py`
- 服务栈孪生：`core/services/scheduler/config/config_snapshot.py`、`config_field_spec.py`、`config_weight_policy.py`

**引用链（已逐条复核到当前代码）**：
- 数据类逐字节相同：`core/models/schedule_config_runtime_snapshot.py:8` `class ScheduleConfigSnapshot`（字段 `:9-38`）**==** `core/services/scheduler/config/config_snapshot.py:24` `class ScheduleConfigSnapshot`（字段 `:24-55`）。本次用 `diff` 抽两边字段名集合，结果 **IDENTICAL FIELD SETS**：各 30 个 dataclass 字段（27 个进 `to_dict` 的配置字段 + `graph_downstream_weight` 派生字段 + `degradation_events`/`degradation_counters` 两个簿记字段），零漂移。
- 校正引擎孪生：`core/models/schedule_config_runtime_coercion.py:409` `def ensure_schedule_config_snapshot`（文件 499 行）**≈** `core/services/scheduler/config/config_snapshot.py:336` `def ensure_schedule_config_snapshot`（整文件 461 行）。
- 权重归一孪生：`core/models/schedule_config_runtime_weights.py:48` `def normalize_weight_triplet` **==** `core/services/scheduler/config/config_weight_policy.py:57` `def normalize_weight_triplet`（仅形参默认名差异）。
- 字段表孪生:模型侧校正逻辑在 `schedule_config_runtime_coercion.py`(对外经门面 `schedule_config_runtime.py` 导出为 `coerce_runtime_config_field`,内部私有 `_coerce_config_field`)vs 服务 `core/services/scheduler/config/config_field_spec.py:468` `def coerce_config_field`。注:模型侧**无**公开符号名 `coerce_config_field`(按此名 grep 会落空),孪生概念成立但命名不对称。
- 消费侧分流（证明两栈都活）：算法栈 → `core/algorithms/greedy/config_adapter.py:6` `from core.models.schedule_config_runtime import ensure_schedule_config_snapshot`、`core/algorithms/greedy/schedule_params.py:98`（`_build_runtime_snapshot` 内 `from core.models.schedule_config_runtime import ensure_schedule_config_snapshot`）；服务栈（config/summary/run 页）走 `core/services/scheduler/config/config_snapshot.py`。
- 门面再导出：`core/models/schedule_config_runtime.py:5` 再导出 `ensure_schedule_config_snapshot`、`:16` 再导出 `normalize_weight_triplet`。

**为何算债**：同一概念（运行期配置快照 + 严格/降级校正 + 权重归一）两套近乎逐字节相同的实现并存，各约 500 行。表面理由成立——算法层不能 import 服务层（分层红线禁止 `core.algorithms → core.services`），需要一个"中性投影"放在 `core/models`；**但 `core.services → core.models` 是合法边**，服务栈完全可以反过来复用 model 栈，而不是另起炉灶。两份靠人工锁步维护（git 实证：`b82c9a4d` / `ef244b9e` 两个 commit 同时改两份字段表）。当前字段集合 `diff` 为空、无漂移，故是**潜伏债**：任何人给配置页（服务栈）加一个字段而忘了同步 model 栈，算法看到的就是旧默认值，而用户在配置页校验/保存的是新值——两边对"同一份配置"各执一词，且算法侧回落是**静默的**（踩中灵魂暗线：坏/缺数据静默兜成默认）。codemap 自身已把 `coercion.py:409 ensure_schedule_config_snapshot` 标记为 `hardcoded->render/resolve（P1 假冒嫌疑）`。

> 顺带实证（强化本条的"静默默认"风险，非新增债）：`coercion.py:470` 处 `graph_downstream_weight = 0 if 临界=0 且 impact=0 else int(ScheduleConfigSnapshot.graph_downstream_weight)`——该字段根本不从配置读取，而是写死取 dataclass 默认值（1）。这正是"快照里有字段但实际不接配置"的微缩样本，恰好说明双栈+静默默认叠加时债务如何潜伏。

**爆炸半径**：排产正确性。算法实际使用的配置可能与配置页校验/保存的不一致；任一栈新增字段未同步即静默分叉，算法侧吃旧默认值且不报错。当前未漂移，影响为**潜伏**——一旦有人改单侧即引爆。

**处置建议 + 收口到哪个已存在统一点**：
1. 收敛方向是**让服务栈复用 model 栈**（合法边方向），把 `core/services/scheduler/config/config_snapshot.py` 的 `ScheduleConfigSnapshot` / `ensure_schedule_config_snapshot` / `normalize_weight_triplet` / `coerce_config_field`(对应模型侧 `coerce_runtime_config_field`)改为从 `core.models.schedule_config_runtime` 再导出或薄委托，删掉服务侧的字段/校正/权重副本。统一收口点 = **`core/models/schedule_config_runtime.py` 门面**（已存在、已被算法栈消费）。
2. 收敛落地前（潜伏期过渡），**至少加一道锁步守护测试**：断言两份 `ScheduleConfigSnapshot` 字段集合 + 默认值逐字段相等（现有 `tests/regression_sp06_no_duplicate_defs.py` 是路径查重，未做字段集合等价断言），让"单侧加字段忘同步"从静默分叉变成红灯。
3. 在两个 dataclass 头部各补"我是故意的"互指注释（见下）。

> **该补的"我是故意的"注释文案**（贴在两份 `class ScheduleConfigSnapshot` 上方各一份，互相指向）：
> ```python
> # [有意的双实现 / 待收敛] 本快照与 core/models/schedule_config_runtime_snapshot.py
> # 是同一份运行期配置的两套实现：算法层禁止 import 服务层（分层红线），故 model 侧
> # 保留一个中性投影供 greedy/* 消费。两栈字段表/默认值【必须逐字段保持一致】——
> # 任一侧新增/改默认值而不同步另一侧，算法会静默吃到旧默认值（违背"坏数据不静默兜底"）。
> # 长期方向：服务栈反向复用 model 栈（services→models 是合法边），届时删除本副本。
> # 改动前请先看 tests/ 里的字段集合锁步断言。
> ```

**复核结论**：✅ 证据仍准。`schedule_config_runtime_snapshot.py:8`、`coercion.py:409`、`weights.py:48`、`config_adapter.py:6`、`schedule_params.py:98`、服务侧 `config_snapshot.py:24/336`、`config_weight_policy.py:57`、`config_field_spec.py:468` 全部行号精确命中；字段集合 `diff` 为空确认零漂移；两侧文件均未被修复 agent 改动。唯一口径修正：原 finding "27 字段"指的是进 `to_dict` 的 27 个配置字段，dataclass 实际 30 个字段（含 1 派生 + 2 簿记），不影响"逐字节相同"结论。

---

### 07-2 · 【P3 · medium · ⚠️load_bearing=true · needs_adversarial】legacy 错误串正则重解析：把已渲染中文串反解回 code，两代错误体制并存

> ⚠️ **承重护栏条目**：这是一座**活着的** legacy 桥（消费方在排产主路径和 viewmodel 里都在跑），不是死代码。对抗验证结论：live legacy，确为真债。

**位置**：`core/models/scheduler_public_errors.py:62-103`、`218-290`

**引用链（已逐条复核到当前代码）**：
- 正则表 `LEGACY_PUBLIC_PATTERNS`：`:62`（`Tuple[Pattern[str], ...] = (`，模板正则延伸到 `:88`）。
- 前缀映射 `_LEGACY_CODE_PREFIXES`：`:94`（8 条中文前缀 → code 的硬映射，到 `:103`）。
- 反解入口 `legacy_public_error_message`：`:218`（`def`，体内 `:229` 遍历 `LEGACY_PUBLIC_PATTERNS` 做 `fullmatch`）。
- 反解入口 `infer_legacy_public_code`：`:284`（`def`，体内 `:287` 走 `_code_from_suffixes`、`:290` 走 `_LEGACY_CODE_PREFIXES`）。
- 另一代（结构化）：同文件 `make_public_error`：`:175`（产 `schema_version`+`code`+`message` 的结构化 dict）。
- **活消费方（对抗验证用）**：
  - `core/services/scheduler/run/auto_assign_resource_errors.py:6` `from core.models.scheduler_public_errors import infer_legacy_public_code, legacy_public_error_message`；`:42` `public_message = legacy_public_error_message(text)`；`:157` `return infer_legacy_public_code(text) in SGS_AUTO_ASSIGN_RESOURCE_ERROR_CODES`。
  - `web/viewmodels/scheduler_summary_display.py:13` import、`:63` `public_message = legacy_public_error_message(item)`。

**为何算债**：老排产路径发出**渲染好的中文错误串**，下游再用一组正则（`infer_legacy_public_code` / `legacy_public_error_message`）把串反解回结构化 code——从"渲染输出"倒推"结构化身份"，绕过了本应端到端携带 code 的结构化错误收口（`make_public_error`）。两代错误体制（结构化 dict vs 串重解析）在同一文件并存，`legacy_` / `LEGACY_` 命名本身就是过渡桥的自供。正则与一长串中文模板字面强耦合（`:63-88` 内嵌"自制工序未补全设备或人员，无法排产：工序…""排产窗口截止到…超出窗口"等整句模板），**任一文案改一个字就断**。

**对抗验证结论（needs_adversarial=true 已结）**：消费方 `auto_assign_resource_errors.py`（排产 run 子包，主链）与 `scheduler_summary_display.py`（summary viewmodel，用户可见摘要）均为**生产活路径**，非测试续命、非死壳。故这是一座**活着的 legacy 桥**，真债成立、不可直接删。

**爆炸半径**：用户可见错误信息的脱敏与归类。改任一中文错误文案，会**静默**使 legacy 正则失配 → 错误被降级为通用文案 `GENERIC_PUBLIC_ERROR_MESSAGE`（"排产执行遇到问题，请联系管理员查看日志。"），用户丢失具体原因，且无任何编译期/运行期告警（再次踩中"宁可暴露错误也不自欺"的反面）。

**处置建议 + 收口到哪个已存在统一点**：
1. 长期：让老排产路径在**发出错误的源头**就携带结构化 code（直接产 `make_public_error` 的 dict），下游不再串重解析；收口统一点 = 同文件 `make_public_error`（`:175`，已是结构化收口）。逐步淘汰 `LEGACY_PUBLIC_PATTERNS` / `_LEGACY_CODE_PREFIXES` / `infer_legacy_public_code`。
2. 过渡期（删不掉时）：补一个"文案↔正则"的锁步守护测试——对每条 `_LEGACY_CODE_PREFIXES` 用真实模板串跑一遍 `infer_legacy_public_code`，断言能解回预期 code，让"改文案断正则"从静默失配变红灯。
3. 在 `LEGACY_PUBLIC_PATTERNS`（`:62`）上方补"我是故意的"注释（见下）。

> **该补的"我是故意的"注释文案**（贴在 `:62 LEGACY_PUBLIC_PATTERNS` 上方）：
> ```python
> # [有意保留的过渡桥 / 待淘汰] 老排产路径发出的是"已渲染中文错误串"，本组正则负责把串
> # 反解回结构化 code（与 make_public_error 的结构化体制并存）。此为兼容桥，非新代码范式。
> # 风险：这些正则与下方中文模板【逐字耦合】，改任一句错误文案都会让正则静默失配、
> # 错误降级为 GENERIC_PUBLIC_ERROR_MESSAGE（用户丢失具体原因）。改文案必同步改这里，
> # 并跑文案↔code 锁步断言。长期方向：让错误在源头就携带 code，删除本桥。
> ```

**复核结论**：✅ 证据仍准。`:62`/`:94`/`:175`/`:218`/`:284` 五个锚点行号精确命中；消费方 `auto_assign_resource_errors.py:6/42/157`、`scheduler_summary_display.py:13/63` 全部命中且仍是活路径；文件停在 `fd520b09`（5 月，"细化排产资源失败提示"），未被修复 agent 改动。对抗验证落定：live legacy。

---

### 07-3 · 【P6 · low · load_bearing=false】死壳 config_adapter：包在本分区收口点外、零功能调用方

**位置**：`core/algorithms/greedy/config_adapter.py:10-27`（相邻文件，经本分区 facade 追出）

**引用链（已复核）**：
- `:9 @dataclass` / `:10 class CriticalConfigReadResult`（`value`/`missing`/`error` 三字段）
- `:16 def read_schedule_config_value`（体内 `:17` 调 `ensure_schedule_config_snapshot`、`:18` `hasattr` 判 missing、`:20-23 try/except` 把异常吞进 `error` 字段）
- `:26 def read_critical_schedule_config`（仅转发 `read_schedule_config_value`）
- 全仓 grep 三个符号（`read_schedule_config_value` / `read_critical_schedule_config` / `CriticalConfigReadResult`）**排除 def 站点后命中为空**——零功能调用方；唯一引用是 `tests/regression_sp06_no_duplicate_defs.py:15` 把该文件**路径**列进查重清单（不调用其函数）。

**为何算债**：这是包在本分区收口点 `ensure_schedule_config_snapshot` 外面的一层薄封装（读快照 + `getattr` + 吞异常成 `error` 字段），没有任何生产或测试代码真正调用它的函数；唯一引用是一个查重守护测试把它的"路径"列进清单。该 facade 本身（`schedule_config_runtime`）仍活（`schedule_params.py:98` 在用），故死的只是这层 adapter 壳。属本分区收口点对外暴露面上的**死消费者**。

**爆炸半径**：无运行期影响；仅是死代码，徒增"本分区收口点有此用法"的假象（误导后人以为有"读单个配置值并吞异常"的标准用法）。

**处置建议 + 收口到哪个已存在统一点**：直接删除整个 `core/algorithms/greedy/config_adapter.py`，并从 `tests/regression_sp06_no_duplicate_defs.py:15` 的路径清单移除该条。真正的配置读取统一点是 `core/models/schedule_config_runtime.py` 门面的 `ensure_schedule_config_snapshot`（消费方应直接读快照属性，无需经此壳）。

**复核结论**：✅ 证据仍准。`:10`/`:16`/`:26` 行号精确；本次 `grep -rn --include="*.py"` 排除 def 站点后**确认零功能调用方**；`sp06` 测试 `:15` 确为路径清单引用；文件停在 `8ec5b40b`（4 月），未被修复 agent 改动。

---

### 07-4 · 【P6 · low · load_bearing=false】死别名 `_safe_identifier`：注释自称内部用，实则零调用

**位置**：`core/models/scheduler_public_errors.py:163-164`

**引用链（已复核）**：
- `:162` 注释 `# Backward-compatible private alias for callers inside this module.`
- `:163 def _safe_identifier(value, *, max_chars=80)`，`:164` 仅 `return public_safe_identifier(value, max_chars=max_chars)`
- 词边界 grep 全仓 `\b_safe_identifier\b`（排除 `public_safe_identifier`、排除另一模块 `core/infrastructure/migrations/v4_sanitizers.py:37/121/122` 自己的同名函数）→ **仅命中本文件 def 自身**，无任何调用方。
- 不在 `__all__`（`:340-351` 只导出 `public_safe_identifier` 于 `:349`）。
- 模块内 `:197` / `:200`（`make_public_error` 内）以及 `:144`/`:149`（`public_safe_identifier` 自身内）一律直接用 `public_safe_identifier`。

**为何算债**：上方注释写"Backward-compatible private alias for callers inside this module"，但 grep 实证模块内外均无任何调用方，模块内部也一律直接用 `public_safe_identifier`。是 `8efa88d5` 收口改名后遗留的**死面包屑**，注释还在误导"有内部调用方"。

**爆炸半径**：无；纯死函数 + 误导性注释。

**处置建议 + 收口到哪个已存在统一点**：删除 `:162-164`（注释 + `_safe_identifier` 别名）。统一收口点 = 同文件 `public_safe_identifier`（`:142`，已是唯一在用的脱敏入口、已进 `__all__`）。

**复核结论**：✅ 证据仍准。`:163-164` 行号精确；本次词边界 grep **确认仅 def 站点命中**（`v4_sanitizers.py` 的同名是另一模块私有函数、不相关）；不在 `__all__` 已核；文件停在 `fd520b09`，未被修复 agent 改动。

---

### 07-5 · 【P6 · trivial · load_bearing=false】死参数 `raw_value`：`_record_blank_choice_degradation` 收了不用

**位置**：`core/models/schedule_config_runtime_coercion.py:83-98`

**引用链（已复核）**：
- `:83 def _record_blank_choice_degradation(collector, *, scope, field_name, raw_value, fallback)`，其中 `:88 raw_value: Any,`
- 函数体 `:91-98`：`:91 label = display_field_label(field_name...)`，`:92-98 collector.add(...)` 的 `message` 只拼 `label`/`fallback`（`"…没有填写，本次先按默认值 {fallback} 处理。"`），**从不引用 `raw_value`**。
- 两个调用点仍传 `raw_value=raw_value`：`_choice_with_degradation` 内 `:155` 起的调用（`raw_value=raw_value` 在 `:159`）；`_yes_no_with_degradation` 内 `:210` 起的调用（`raw_value=raw_value` 在 `:214`）。
- 服务侧孪生函数甚至没有这个参数（佐证其为冗余）。

**为何算债**：形参 `raw_value` 被声明并由两处调用方传入，但函数体内从未被读取（空白值降级消息里只报 `fallback`）。是签名上的**死参数**，徒增调用噪音；与"孪生函数无此参"对照更显其多余。

**爆炸半径**：无；仅签名冗余。

**处置建议 + 收口到哪个已存在统一点**：从 `:88` 删 `raw_value` 形参，并删两个调用点 `:159`/`:214` 的 `raw_value=raw_value` 实参（三处一起改，保持签名/调用一致）。无外部收口点需对接——纯局部清理。注意与 `_record_invalid_choice_degradation`（`:101`，**确实**用到 `raw_value` 拼"当前值"消息）区分，勿误删后者的同名参数。

**复核结论**：✅ 证据仍准。`def` 在 `:83`、`raw_value` 形参在 `:88`、函数体 `:91-98` 不引用 `raw_value`、两调用点起于 `:155`/`:210`（`raw_value=raw_value` 落在 `:159`/`:214`）——全部精确命中；文件停在 `ed695e79`（5 月），未被修复 agent 改动。

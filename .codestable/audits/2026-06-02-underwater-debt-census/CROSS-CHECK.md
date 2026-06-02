# 全项目水下语义债普查 · 两遍交叉检验

> Pass-1(12 分区 agent 自由取证)× Pass-2(函数级调用图机械嫌疑)交叉。
> 目的:检验用户最担心的"agent 注意力偏差导致大量遗漏"是否兑现成真遗漏。

## 一句话结论

**"大片盲区"假设被证伪。** 机械调用图地毯式扫了 5874 函数、标出 66 条高风险数据流,落在 37 个文件;其中 12 个文件与 Pass-1 双重命中(强互证),25 个文件是 Pass-1 该文件零发现(B−A)。**逐一核实后,B−A 几乎全是图的结构性假阳性,不是真遗漏。** 这是"狗没有叫"式的好消息:无差别的机械方法没扫出 agent 没碰过的新出血,反证 agent 这一遍覆盖扎实。

**唯一真缺口**:`core-models` 与 `core-algorithms` 两个分区 Pass-1 整体失败(StructuredOutput 掉线),是"没扫"而非"扫了没发现"。`core-models` 是归一收口点 `schedule_plan_identity`/`schedule_resource_filter` 的老家,必须由 Pass-2 补扫。

## A∩B:图与 agent 双重命中(12 文件,强互证)

两套完全独立的方法(机械算法 vs LLM 自由探查)收敛到同一批文件 = 互相背书。核心出血一族全在内:

- `core/services/report/execution_review.py` ← 已知出血
- `core/services/scheduler/operation_execution_feedback_service.py` ← 写侧护栏
- `core/services/scheduler/schedule_result_view_context.py` ← default_plan_resolution_dict 私实现
- `core/services/scheduler/schedule_plan_identity_builder.py`
- `core/services/scheduler/gantt_plan_query.py` / `gantt_service.py`
- `core/services/scheduler/resource_dispatch_service.py` / `schedule_delay_diagnosis_service.py`
- `core/models/schedule_config_runtime_coercion.py`
- `data/repositories/schedule_repo.py`
- `web/routes/domains/scheduler/scheduler_navigation_publish.py` / `scheduler_week_plan.py`

## B−A:图标高风险但 Pass-1 该文件零发现(25 文件)

逐类裁决(✓=已人工核实):

### 图的结构性假阳性(非遗漏)

| 文件:行 | 图信号 | 真相(已核实) |
|---|---|---|
| ✓ `web/routes/report_plan_preview.py:95` | hardcoded(ROLE_ADOPTED)→resolve | `or ROLE_ADOPTED` 仅空值兜底,真值来自 `engine.resolve_plan_context` 真解析。与 execution_review 出血**镜像相反**(那个无视解析发布常量,这个先解析后兜底)。**反证出血是孤立的** |
| ✓ `core/services/report/report_plan_helpers.py:154` | sensitive→write(update) | `version_date_range` 纯读方法;`update` 是 dict.update 误判。通篇 resolve/list 只读,且 :140-152 正确处理 preview(标"模拟方案预览") |
| ✓ `core/services/scheduler/config/config_presets.py:56` | hardcoded(BUILTIN_PRESET_DEFAULT)→render | 内置预设**本就该是常量**(声明的策略),非假冒计算值 |
| ✓ `core/services/scheduler/config/config_snapshot.py:232,349` | hardcoded(MISSING_POLICY_FALLBACK_WITH_DEGRADATION)→render | 名字自带 degradation 上报 = 灵魂线"不静默兜底、留痕降级"正面体现 |
| `data/repositories/schedule_candidate_repo.py` / `schedule_adjustment_scenario_repo.py` / `migrations/v7.py` / `migration_state.py` / `run/schedule_*_persistence*.py` | sensitive-identity→write | **repo/persistence/migration 层本就该一边拿身份字段一边写库**,是正经工作非越权。系统性噪声 |
| `tools/capture_networkx_phase0_baseline.py` / `tools/long_gate_fingerprint.py` | sensitive→write | 离线工具脚本,非生产路径 |
| `week_plan_excel.py` / `report_engine.py` / `scheduler_gantt*.py` 等 | preview→render / sensitive→write | 报表/甘特读侧处理 scenario 是其本职;已被 A∩B 的同族文件代表,非新增盲区 |

### 真缺口(必须 Pass-2 补)

| 文件 | 为何是真缺口 |
|---|---|
| `core/models/schedule_plan_identity.py:172`(preview→render) | 所在 `core-models` 分区 Pass-1 **整体失败**,从未被扫。归一收口点老家 |
| `core/models/schedule_plan_resolution.py:64`(preview→render) | 同上。承载方案身份 5 层的核心模型 |
| `core-algorithms` 整区 | Pass-1 整体失败,图信号也稀(算法层少碰身份字段),但需确认无遗漏 |

## 方法论收获(写入 cs-checkup)

1. **两段式有效**:图列机械嫌疑(无差别、消偏差)→ agent/人核验语义(分清"该是常量的常量"vs"假冒计算值")。纯语法工具的天花板正在这里——它分不清 P1 真伪。
2. **"狗没有叫"也是结论**:机械全扫没扫出 agent 漏的新出血,本身就证伪"大片盲区"。负结果有价值。
3. **数据流追踪的已知噪声源**:`sensitive-identity→write` 在 repo/persistence/migration 层系统性假阳性;`hardcoded→render` 在 config/预设/降级策略层系统性假阳性。下次直接按层过滤,只看"层与信号不匹配"的(只读层出现 write、计算层出现 hardcoded)。
4. **agent StructuredOutput 掉线是真风险**:12 路有 2-3 路因未调用 StructuredOutput 失败,且失败的恰是关键分区。补救=失败分区单独重跑(不靠 schema 或放宽 schema)。

## 90 · 承重护栏清单【防屎山核心资产 · 别动我】

> 本节是整份报告**防屎山价值最高**的一节。基准对抗验证确认 **8 处** `load_bearing=true` 承重不对称(LB-A1/A2/A3 + LB-B1/B2/B3/B4 + N1 收口前身);b08162cd 增量再添 **LB-A4/A5/B5** 与正向护栏 **LB-G+**(见下方增量小节),故小结表共列 10 行。行号已在当前 HEAD `b08162cd` 上复核。

### 为什么"承重不对称"是看着像债、实为救命护栏的东西

普通的债(死代码、半截迁移)删错了顶多功能缺失、报错暴露。**承重不对称删错了不报错——它静默地拆掉一道安全不变量,系统继续绿着跑,直到错误数据流到不该去的地方。**

它的共性,也是它危险的根源:

1. **刻意和兄弟不一致** —— execution_review 比 overdue/utilization/downtime 三个兄弟报表少收两个参数;派工不走资源归一收口点;boolean 有两份实现。每一处单看都像"没对齐、该清理的坏味道"。
2. **理由全散在远处** —— "为什么故意"的根据在 schema CHECK、分层规则、UI 文案、导航强制、合同测试里,**唯独发生不一致的那行代码本地零注释**。
3. **改它的动作伪装成无害清理** —— "统一四张报表的参数签名"、"消除魔法字面量方言"、"合并重复实现",在 diff 层面都像正向重构。

**这意味着:未来任何一个 LLM(或人)看到它们,第一反应都是"这是不一致,该统一"——而统一动作本身就是引爆动作。** 这是"失忆债"最危险的形态:不是债本身危险,是**还债的人如果也失忆,还债就是闯祸**。

**本节对每一处的核心交付物 = 一行该补的"我是故意的"注释**。把散在远处的护栏意图,钉回发生不对称的改动点本地——这是对无记忆的 LLM 协作者**唯一有效的本地阻止信号**,也是性价比最高的防屎山动作。

---

### A 族 · execution_review「只复盘正式采用方案」(纵深防御 4 处,守同一条不变量)

> **不变量**:"计划和现场实际"复盘 = 拿**正式采用方案**对账车间现场事实。若放开 `plan_role`/`scenario_id`,模拟方案预览或历史非采用方案会冒充"现场实际复盘"展示给车间,把**没发生的预览当成既成事实**——直接踩中灵魂红线"宁可暴露错误也不自欺"的反面。
>
> 这道墙在 4 个层次设防(web 路由 → 服务签名 → 取数源表 → 写侧反馈),**任何单层都不是冗余,而是纵深防御**:上层守卫可能被某次重构绕过,下层仍需独立挡住。报告把它们合并讲,但强调**不可"合并简化"为一点**。

#### LB-A1 【P2 · high】web 路由层:写死 `adopted`/`None`(reports_page_support + navigation_context)

- **位置(当前 HEAD `b08162cd` 已复核)**:
  - `web/routes/reports_page_support.py:367` — `page_plan_resolution(services.schedule_plan_query_service, version, "adopted", None)`
  - `web/routes/reports_page_support.py:369` — `page_date_range_or_version_span(engine, ..., "adopted", None, ...)`
  - 二者在 `execution_review_page_context()`(`:364`)内
  - `web/navigation_context.py:80-82` — `is_execution_review` 为真时 `plan_role = ROLE_ADOPTED`、`scenario_id = ""`,强制清掉 request 的 role/scenario
  - ⚠️ **行号已变**:普查时为 `:366,:368`,b08162cd 工作台收口(reports_page_support.py +456 行)后微移到 `:367,:369`。债仍在。
- **不对称实锤**:同文件所有兄弟页(overdue/utilization/downtime 经 `_standard_request_context`)全部 `raw_plan_role=request_plan_role()` / `scenario_id=request_scenario_id()` 从 request 读;**唯独 execution_review 写死**。
- **删了会炸什么**:把 `:367/:369` 的 `"adopted", None` 改成 `request_plan_role()/request_scenario_id()`,预览/对比方案即可通过 `?plan_role=&scenario_id=` 冒充正式复盘,污染复盘结论。改动看起来是"消除参数方言"的一致性清理,实为安全回退。
- **动它的前置条件**:(1) 绝不给 core 的 `execution_review()` 加 plan_role/scenario_id 入参——行数据护栏在 core 必须原样保留;(2) 先补缺失的页面级回归 `GET /reports/execution-review?plan_role=baseline_best&scenario_id=xxx`,断言「排产方案」标签仍为正式采用方案、不出现预览/对比文案、发布的 nav context plan_role=adopted 且无 scenario_id;(3) 若只为消除魔法字面量,应抽具名收口(如 `execution_review_plan_context()` 内部强制 adopted/None)替换字面量,而非改成从 request 读;(4) 保留 navigation_context.py:80-82 的 is_execution_review 强制分支(它守未发布 context 的回退路径)。
- **🔧 该补的"我是故意的"注释**(贴在 `:367` 上方):
  ```python
  # 故意写死 adopted/None,不从 request 读 plan_role/scenario_id:这是护栏,不是漏掉的方言。
  # 计划和现场实际只复盘正式采用方案;放开会让模拟预览/对比方案冒充正式复盘展示给车间。
  # 勿为"统一所有报表页从 request 读参数"而改成 request_plan_role()/request_scenario_id()。
  ```

#### LB-A2 【P2 · high/medium】服务签名层:`execution_review()` 形参拒收 plan_role/scenario_id

> 注:本条由 scheduler-plan-identity(LB2)与 core-svc-domain(LB5)两个分区**独立命中同一处**,互证其重要性。合并陈述。

- **位置(当前 HEAD `b08162cd` 已复核)**:
  - `core/services/report/execution_review.py:141` — `execution_review(self, version, *, date_from, date_to, batch_id, resource_type, resource_id)` 形参**刻意不含** plan_role/scenario_id;`export_execution_review_xlsx`(`:178` 附近)同样
  - `:112,123` — `_execution_review_plan_rows` 两分支恒 `plan_role=ROLE_ADOPTED, scenario_id=None`
  - `:153` — 方法体恒 `resolution = host._resolve_plan(v, ROLE_ADOPTED, None)`
  - `:166-167` — 返回 dict 恒 `plan_label=plan_role_label(ROLE_ADOPTED), plan_role=ROLE_ADOPTED`
  - ✅ **证据仍准**:b08162cd 改了本文件(149 行变更,删除了 P1 出血源),但这 5 处硬钉 ROLE_ADOPTED 仍在;grep"故意/刻意/不对称"**仍零命中**——即使刚做完工作台收口,这道护栏的注释依然没人补(失忆债的活样本)。
- **不对称实锤**:`report_engine.py:157 overdue_batches(self, version, plan_role=None, scenario_id=None, ...)`、`:267 utilization(...)`、`:371 downtime_impact(...)` 全部签名带 plan_role+scenario_id 并透传;`overdue_batches` 在 `:168 self._resolve_plan(v, plan_role, scenario_id)` 透传。**唯独 execution_review 拒带。**
- **取数源真随 role/scenario 改变(护栏不是装饰)**:`schedule_plan_query_service.resolve_plan_view` 中 `scenario_id` 非空即转 `_resolve_scenario_plan` → `source_table=SOURCE_ADJUSTMENT_SCENARIO_ROWS`、`is_scenario_preview=True`;非 adopted role 选不同 candidate_id/source_table。所以写死 adopted 是**数据层最后一道把关**。
- **删了会炸什么**:给 execution_review 补 plan_role/scenario_id 透传,模拟预览/对比方案的计划时间会和正式现场反馈拼成"计划 vs 实际"复盘并可导出,污染唯一可信的正式复盘口径;合同测试拦得住一部分,但服务层契约已被破坏。
- **动它的前置条件**:(1) 取数边界保留强制 adopted——继续写死,或加 service 层断言:收到非 adopted role / 任何 scenario_id 时 `raise ValidationError`(loud,不静默回退),返回前校验 `resolution.is_scenario_preview is False`;(2) 给下游 `aggregate_states_by_op_ids` 增加 role/scenario 作用域过滤,让 join 能自卫;(3) 路由入站层加闸门并保留 web 层 forbidden-params 守卫;(4) 用 `regression_plan_vs_actual_review`/`regression_reports_workbench_navigation_contract` 锁死。
- **🔧 该补的"我是故意的"注释**(贴在 `execution_review.py:141` 签名上方):
  ```python
  # 本方法故意只复盘 ROLE_ADOPTED,不收/不透传 plan_role/scenario_id——
  # 与 overdue/utilization/downtime 三兄弟的签名不对称是刻意的护栏,不是遗漏。
  # 勿为"统一四张报表方法签名"而加 plan_role/scenario_id 形参:
  # 会让模拟预览/对比参考方案的明细以"正式现场复盘"身份呈现给车间并可导出。
  ```

#### LB-A3 【P2 · high】写侧反馈层:`operation_execution_feedback_service` 硬拒 + 写死消毒

- **位置(当前 HEAD `b08162cd` 已复核)**:
  - `core/services/scheduler/operation_execution_feedback_service.py:347-356` — `_load_current_official_schedule` 刻意硬拒:`requested_plan_role != ROLE_ADOPTED or effective_plan_role != ROLE_ADOPTED or source_table != SOURCE_SCHEDULE or scenario_id is not None` 即拒
  - `:451-453` — `_build_event_payload` 写死 `"source_table": SOURCE_SCHEDULE, "effective_plan_role": ROLE_ADOPTED, "scenario_id": None`
  - ✅ **证据仍准**:行号与普查一致。
- **守的不变量**:现场反馈只能写在**当前正式采用方案**上,禁止预览/scenario 冒充正式现场记录。`_build_event_payload` 写死常量是 **defense-in-depth 的消毒层**:即便上游校验被绕过,持久化层也绝不落下一条带 candidate/scenario 身份的现场事件。
- **删了会炸什么**:把三个写死常量改成透传 context、或删 `:347-356` 的拒绝分支,现场反馈可被写到候选方案/scenario 预览上,**污染"正式采用方案"的现场执行事实**;下游重排护栏(`schedule_execution_guardrails` 读 `ExecutionFact`)会基于被污染的事实做决策。
- **动它的前置条件**:唯一安全动作是补保护性注释。严禁把 451-453 改成透传 context。若仍要改逻辑必须同时:(a) 保留 348-354 硬拒或等价 can_write_feedback 硬门;(b) `schema.sql:256-258` 三条 CHECK 与 `migration_operation_execution_contract` 启动探针保持不变(最终承重底);(c) 新增 record_event 端到端(非仅 repo 级)回归,证明 scenario/candidate 上下文在任何持久化前被拒。
- **🔧 该补的"我是故意的"注释**(贴在 `:451` 上方):
  ```python
  # 故意写死、故意忽略 context 的同名字段:这是消毒层(defense-in-depth)。
  # 即便上游校验被绕过,持久化也绝不落 candidate/scenario 身份的现场事件——
  # 现场执行事实只能挂在正式采用方案上,否则会污染下游重排护栏的决策依据。
  # 勿改成透传 context.source_table/effective_plan_role/scenario_id。
  ```

---

### B 族 · 各自独立的承重不对称

#### LB-B1 【P5 · medium】`boolean_normalize` 双实现是**分层承重**,不是冗余副本

- **位置**:`core/shared/boolean_normalize.py:33` `normalize_yes_no_wide` vs `core/services/common/normalization_matrix.py:168` `normalize_yes_no_wide_value`(逐行同义)。
- **为什么不能删**:`boolean_normalize` 被 `core.models`/`core.algorithms` 等**下层**模块引用。若以"统一到矩阵"名义删掉它、改指 `core.services.common`,会立刻产生 `core.models → core.services` **越层** + 导入环,**击穿当前 AST 0 违规结构**。所以它的存在是分层承重的。
- **真正该补的**:不是删任一方,是**一条绑定两套等价的契约测试**——断言两者在全 wide 别名集 × 是/否 × default/passthrough/raise/no 全部 unknown_policy 分支上逐一同值(任一单边改动即触发红灯)。
- **若确要消重的唯一合法方向**:让**上层** `normalization_matrix.normalize_yes_no_wide_value` 反过来 delegate 到**下层** `boolean_normalize`(services→shared 是合法下行边),保留 shared 为唯一事实源,删 matrix 内重复逻辑——而非相反。
- **🔧 该补的注释**(贴在 `boolean_normalize.py:33` 上方):
  ```python
  # 这不是 normalization_matrix.normalize_yes_no_wide_value 的冗余副本:
  # core.models/core.algorithms 在下层只能调本函数,删它改指 core.services 会撞分层红线。
  # 两套必须保持语义等价——靠 regression 契约测试绑定,勿单边修改别名集/枚举值。
  ```

#### LB-B2 【P3 · medium】双 `ScheduleConfigSnapshot` 栈:潜伏的静默分叉(Pass-1 漏报、Pass-2 补出)

- **位置**:`core/models/schedule_config_runtime_*.py`(5 文件,snapshot 27 字段)≈ `core/services/scheduler/config/config_snapshot.py`(逐字节相同,ensure_schedule_config_snapshot ~499 行)。
- **为什么是承重/潜伏债**:算法层不能 import 服务层(layer_edges 证实 `core.algorithms → core.services` 不存在),所以需要一个 model 层"中性投影"供算法用。但反过来 `core.services → core.models` 是合法边(42 条),服务栈**本可复用 model 栈而非另起一套**。两份靠人工锁步同步(git 实证 `b82c9a4d`/`ef244b9e` 同时改两份字段表)。
- **删了/疏忽会炸什么**:当前 27 字段在册无漂移,故是**潜伏债**——任何人给配置页(service 栈)加一个字段而忘了同步 model 栈,**算法看到的就是旧默认值,而用户在配置页校验/保存的是新值**,两边对"同一份配置"各执一词,且算法侧回落是静默的(踩灵魂线)。
- **收敛方向(需先补 parity 测试)**:让 service 栈反向复用 model 栈;收敛前必须先补一条 parity 测试断言两栈字段集与默认值逐一相等。
- **🔧 该补的注释**(贴在两栈 snapshot 定义处):
  ```python
  # ⚠️ 本 dataclass 与 core/services/scheduler/config/config_snapshot.py 的 ScheduleConfigSnapshot 必须逐字段同步。
  # 这是分层(算法层不能 import 服务层)被迫的双实现,非随意复制。
  # 加/改字段必须两栈同改,否则算法用旧默认值、配置页存新值,静默分叉污染排产正确性。
  # 收敛前先补 parity 契约测试。
  ```

#### LB-B3 【P3 · medium】legacy 错误串往返桥:两代错误体制并存

- **位置**:`core/models/scheduler_public_errors.py:62-103,218-290`(`LEGACY_PUBLIC_PATTERNS`/`_LEGACY_CODE_PREFIXES`/`legacy_public_error_message`/`infer_legacy_public_code`)。活消费方:`auto_assign_resource_errors.py:42,157` + `scheduler_summary_display.py:63`。
- **为什么算债(needs_adversarial)**:老路径发渲染好的中文错误串,下游用正则把串**反解回结构化 code**——从"渲染输出"倒推"结构化身份",绕过本应端到端携带 code 的 `make_public_error`。正则与一长串中文模板字面强耦合,**任一文案改字就静默失配**,错误降级为通用文案。
- **处置**:这是过渡桥,`legacy_/LEGACY_` 命名是自供。收敛=让老路径也走结构化 `make_public_error` 端到端带 code,届时可删整组正则。**但收敛前改任何相关中文文案都要同步检查正则**——这是它当前的承重点(改文案的人未必知道有正则在依赖文案)。
- **🔧 该补的注释**(贴在 `LEGACY_PUBLIC_PATTERNS:62` 上方):
  ```python
  # ⚠️ 这组正则把已渲染的中文错误串反解回 code,与下方 make_public_error(结构化体制)并存。
  # 它强耦合具体中文模板字面:改任何被 auto_assign_resource_errors 发出的错误文案,
  # 都必须同步更新这里的 pattern,否则错误会静默降级为通用文案。
  # 终态:让老路径也走 make_public_error 端到端带 code,然后删除本组正则。
  ```

#### LB-B4 【P4 · low】`_bool_from_summary` 静默吞坏 JSON(对抗验证**推翻**了其安全危害)

- **位置**:`core/services/scheduler/schedule_plan_identity_builder.py:24-29`(`except (TypeError, ValueError): return False`)。
- **对抗验证的关键纠正**:普查初判它"影响 is_official/可派工"是**被推翻的**。真正的承重护栏是 `result_status='simulated'`(由同一 `ctx.simulate` 原子同写,且在两个消费者里都先于/独立于 summary 被检),所以删/统一**不会**让模拟冒充正式或可派工。
- **但仍不可改 raise**:`latest_executable_official_version` 全量扫历史行,任何一条 legacy/NULL 邻接的损坏 summary 都会让当前方案身份整链抛错——这是**可用性放大事故**而非安全收益。
- **处置**:不改 raise;只补一条非致命的完整性日志(让损坏 summary 可见但不阻断)。属低优先。
- **🔧 该补的注释**(贴在 `:24` 上方):
  ```python
  # 对坏 summary 返回 False 是有意的容忍(legacy/NULL 老库行)——不可改 raise:
  # latest_executable_official_version 全量扫历史,一条坏行会让当前方案身份整链崩。
  # 安全不变量由 result_status='simulated'(原子同写)独立保证,不依赖这处 summary 判定。
  ```

---

### 增量 · b08162cd 工作台收口对承重护栏的影响(详见 §13 第三部分)

> 现状对账:b08162cd 给本清单**新增 1 处承重点、扩展 1 处、并新加 1 道正向护栏**。

| 编号 | 位置(b08162cd) | 守的不变量 | 状态 |
|---|---|---|---|
| **LB-A4**(新增) | `navigation_context.py:42-47,80-82` | execution_review 导航层剥离 plan_role/scenario_id(第 4 个承载点) | ⚠️ b08162cd 新增,靠路由名/路径**字面量匹配**+零注释,**最脆弱**。见 13.N3 注释文案 |
| **LB-A5**(削弱) | `scheduler_navigation_publish.py:79-84` | 写侧 can_write_feedback 仅 formal_adopted 可写 | ⚠️ :83 `context.update` 把 builder 已 gate 的值覆盖回未门控值(当前未被消费,潜伏)。见 13.N5 |
| **LB-B5**(新增承重) | `schedule_resource_filter.py:8,19-24,54/60/66` | 新 collar 只支持 machine/operator,team/empty-id 一律 raise | ⚠️ b08162cd 新增,零注释说明 team 排除是刻意的(collar 表达不了 team 轴,靠 SQL 双 join 两轨并存)。见 13.G2 |
| **LB-G+**(✅正向) | `schedule_plan_identity_builder.py:76-77,61-62,166` | is_superseded → "历史正式方案(已被新版本替代)"标签,防旧正式冒充现行 | ✅ **b08162cd 新加的反自欺护栏**(灵魂线正向补强)。建议补注释说明它是护栏不是装饰 |

> ⚠️ **N1 不是单点护栏,是护栏的"承重字段"被散成 3 抄**:execution_review 放行判定 `_is_formal_adopted_context` 依赖的 plan-guard 字段,被 `reports_workbench.py:40`/`navigation_publish.py:72`/`resource_dispatch.py:63` 三处手维拷贝(键集三样、命名两套),漏拷一键即护栏静默失效。这是比"单处无注释"更危险的承重债——治法是把 guard 字段收口进 `build_workbench_plan_context`(详见 13.N1)。

### 本节小结

| 编号 | 位置(当前 HEAD `b08162cd`) | 守的不变量 | 复核 |
|---|---|---|---|
| LB-A1 | reports_page_support.py:367,369 + navigation_context.py:80-82 | execution_review 只复盘 adopted(web 层) | ⚠️ 行号微移 +1 |
| LB-A2 | execution_review.py:141,112,123,153,166-167 | 同上(服务签名层) | ✅ 仍准,注释仍缺 |
| LB-A3 | operation_execution_feedback_service.py:347-356,451-453 | 现场反馈只挂正式方案(写侧消毒) | ✅ 仍准 |
| **LB-A4** | navigation_context.py:42-47,80-82 | execution_review 导航层剥离方案身份 | ⚠️ b08162cd 新增,最脆弱 |
| LB-B1 | boolean_normalize.py:33 | 分层 0 违规(下层不 import 上层) | ✅ 仍准 |
| LB-B2 | schedule_config_runtime_*.py(5)↔config_snapshot.py | 双配置栈不静默分叉 | ✅ 潜伏 |
| LB-B3 | scheduler_public_errors.py:62-103,218-290 | 改文案不静默失配正则 | ✅ 仍准 |
| LB-B4 | schedule_plan_identity_builder.py:24-29 | (危害已被对抗验证下调)不改 raise | ✅ 仍准(基线b08162cd);⚠️工作树已超前治理为 fail_closed+可见标记,见§13.5 |
| **LB-B5** | schedule_resource_filter.py:8,54/60/66 | 新 collar team/empty-id 一律 raise | ⚠️ b08162cd 新增,零注释 |
| **N1** | reports_workbench:40 / navigation_publish:72 / resource_dispatch:63 | 护栏字段单一来源(现散 3 抄) | ⚠️ 承重字段散落,收口进 builder |

**最高杠杆动作**:把上述注释逐字补进改动点本地(A 族 + LB-A4 navigation_context 是重中之重)。**b08162cd 后新增的 LB-A4(字面量匹配护栏)和 N1(护栏字段散 3 抄)是当前最脆弱的两处**——它们是"刚长出来、还没立约"的接缝。这是把"散在远处的护栏意图"钉回执行现场,对无记忆的 LLM 协作者唯一有效的本地阻止信号——也是本次普查认定的**唯一通向屎山的路(以统一名义抹掉承重不对称)的免疫疫苗**。

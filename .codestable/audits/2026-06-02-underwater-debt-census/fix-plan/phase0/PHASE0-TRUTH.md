# PHASE 0 · 唯一真相源（脚本确定性算出，禁止手敲覆盖）

> 本文件由 `build_truth.py` 读 `findings/_real_debt.json`（72 真债 R01-R72）+ `findings/_load_bearing.json`（8 承重 LB01-LB08 + 27 对抗 verdict）确定性生成。
> **自污染防护**：脚本只读 findings JSON，从不读任何计划草稿。Phase 1/2/3 一律以本文件 + `_all_debts_full.json` + `_bucket_packs.json` 为根基。
> 机器可读副本：`_truth.json` / `_all_debts_full.json` / `_bucket_packs.json`（均在 `fix-plan/phase0/`）。

---

## 0. 复核基线与工作树漂移（最重要的纪律，每个 agent 必读）

- **报告基线 = 提交 `b08162cd`**。当前 HEAD = `c2aa7501`，但 `git diff b08162cd c2aa7501` **只动了 `.codestable/` + `evidence/` + `.gitignore`，零生产代码**。
- **结论：提交态生产代码 ≡ 报告基线 `b08162cd`。** 报告 90/91 节的 `file:line` 对"已提交代码"仍准。
- **真正的行号漂移在 16 个工作树未提交（staged/modified）的生产文件里**（§13.5 的 in-flight 改动）。下一个改代码的人面对的是工作树态，所以**所有 `file:line` 必须 Read/Grep 实际盘上文件复核，不能照抄报告行号**。

### 落在「工作树已漂移文件」上的债 —— 行号几乎一定变了，必须回盘复核

| 债 | 桶 | 病理 | 漂移文件 |
|---|---|---|---|
| **LB03** | B01 | P4 | `schedule_plan_identity_builder.py`（§13.5 实证：`_bool_from_summary` 已被超前治理成 `_parsed_summary_flag_is_true(fail_closed=True)`，债已进入治理） |
| **R23** | B02 | P5 | `schedule_plan_query_service.py` |
| **R42** | B01 | P6 | `scheduler_workbench_links.py` |
| **R44** | B02 | P5 | `scheduler_navigation_publish.py` |
| **R54** | B01 | P5 | `scheduler_navigation_publish.py` + `scheduler_reports_workbench.py` + `scheduler_resource_dispatch.py`（**3 个都在漂移名单**） |
| **R58** | B01 | P2 | `scheduler_navigation_publish.py` |
| **R66** | B01 | P6 | `scheduler_reports_workbench.py` |

> 16 个工作树漂移生产文件全名单：`core/models/schedule_plan_identity.py`、`core/models/schedule_plan_resolution.py`、`core/services/scheduler/schedule_plan_identity_builder.py`、`core/services/scheduler/schedule_plan_query_service.py`、`templates/dashboard.html`、`templates/reports/execution_review.html`、`templates/scheduler/analysis_parts/_action_hub.html`、`web/routes/dashboard.py`、`web/routes/domains/scheduler/scheduler_navigation_publish.py`、`web/routes/domains/scheduler/scheduler_resource_dispatch.py`、`web/routes/reports_plan_template_fields.py`、`web/viewmodels/dashboard_workbench.py`、`web/viewmodels/dashboard_workbench_cards.py`、`web/viewmodels/scheduler_reports_workbench.py`、`web/viewmodels/scheduler_resource_dispatch.py`、`web/viewmodels/scheduler_workbench_links.py`。

---

## 1. 80 条债 partition 校验（✓ 全通过）

- 总债数 = **80**（72 真债 + 8 承重），bucket 分配 = 80。
- **重复（同债落 >1 桶）= 无 ✓**
- **遗漏（无桶）= 无 ✓**
- **越界（桶 id 不在 findings）= 无 ✓**
- **8 承重全覆盖**：LB01-LB08 各恰好一个家。
- 每条债恰好一个家 ✓。**§5.2 的 17 桶切分经脚本验证成立，可直接用。**

---

## 2. 同主文件硬耦合（脚本从 location basename 重算，29 组 ≥2 债）

> 同一文件被多条债命中 = 必须一次性协调改，不能各改各的。**粗体=跨桶**（Phase 2/3 协调点）。

| 文件 | 命中债 | 所属桶 | 跨桶? |
|---|---|---|---|
| navigation_context.py | LB06,R42,R56,R57 | B01 | 同桶 |
| **dispatch_rules.py** | R49,R50,R51 | B05,B06 | **跨桶** |
| **execution_fact_provider.py** | R13,R15,R19 | B06,B11,B13 | **跨桶(3桶)** |
| execution_review.py | LB02,LB05,R62 | B01 | 同桶 |
| gantt_service_support.py | R11,R55,R63 | B08 | 同桶 |
| schedule_config_runtime_coercion.py | LB07,R47,R71 | B03 | 同桶 |
| **scheduler_navigation_publish.py** | R44,R54,R58 | B01,B02 | **跨桶** |
| compat_parse.py | R30,R33 | B06 | 同桶 |
| config_adapter.py | R45,R48 | B03 | 同桶 |
| **config_snapshot.py** | R26,R71 | B03,B13 | **跨桶** |
| **gantt_service.py** | R10,R55 | B08,B14 | **跨桶** |
| **operation_execution_event_repo.py** | R18,R19 | B11,B13 | **跨桶** |
| **operation_execution_feedback_service.py** | LB01,R17 | B01,B11 | **跨桶(LB!)** |
| **operation_execution_feedback_support.py** | R15,R17 | B06,B11 | **跨桶** |
| **operation_execution_state_builder.py** | R15,R16 | B06,B11 | **跨桶** |
| part_repo.py | R38,R39 | B12 | 同桶 |
| ready_queue.py | R25,R52 | B09 | 同桶 |
| reports_page_support.py | LB06,R42 | B01 | 同桶 |
| **resource_dispatch_execution_service.py** | R07,R09 | B01,B05 | **跨桶** |
| schedule_config_runtime_read.py | LB07,R71 | B03 | 同桶 |
| **schedule_payload_contract.py** | R01,R04 | B05,B14 | **跨桶** |
| schedule_repo.py | R34,R35 | B12 | 同桶 |
| scheduler_navigation_links.py | R64,R65 | B17 | 同桶 |
| scheduler_public_errors.py | LB08,R46 | B10 | 同桶 |
| scheduler_reports_workbench.py | R54,R66 | B01 | 同桶 |
| **scheduler_resource_dispatch_execution.py** | R08,R09 | B01,B05 | **跨桶** |
| scheduler_workbench_link_query.py | R42,R60 | B01 | 同桶 |
| **value_policies.py** | R31,R33 | B06,B13 | **跨桶** |

> `__init__.py` 是 basename 假碰撞：R06=`dispatch/__init__.py`，R27=`calendar/`+`batch/__init__.py`，**是不同文件**；但二者经 SP05 拓扑契约耦合（V22 要求 4 个空包 batch/calendar/dispatch/gantt 同提交删 + 同步改 `test_sp05_path_topology_contract.py:309-316`）。

---

## 3. 跨桶同文件边（Phase 3 必须串行化的 13 条硬约束）

这些边意味着两个桶会改同一个文件，**Phase 3 排序必须让它们进同一批次或显式串行**，否则后改的桶会撞前改桶的行号/逻辑：

| 文件 | 债→桶 |
|---|---|
| config_snapshot.py | R26(B13) ↔ R71(B03) |
| dispatch_rules.py | R49(B06),R50(B05),R51(B06) |
| execution_fact_provider.py | R13(B11),R15(B06),R19(B13) |
| gantt_service.py | R10(B14) ↔ R55(B08) |
| operation_execution_event_repo.py | R18(B11) ↔ R19(B13) |
| operation_execution_feedback_service.py | **LB01(B01,承重)** ↔ R17(B11) |
| operation_execution_feedback_support.py | R15(B06) ↔ R17(B11) |
| operation_execution_state_builder.py | R15(B06) ↔ R16(B11) |
| resource_dispatch_execution_service.py | R07(B01) ↔ R09(B05) |
| schedule_payload_contract.py | R01(B14) ↔ R04(B05) |
| scheduler_navigation_publish.py | R44(B02),R54(B01),R58(B01) |
| scheduler_resource_dispatch_execution.py | R08(B01) ↔ R09(B05) |
| value_policies.py | R31(B13) ↔ R33(B06) |

**最危险的边**：`operation_execution_feedback_service.py` 上 **LB01（承重，只补注释）↔ R17（删死键+死导入）** 同文件 —— B01 的承重注释必须先落，B11 删 R17 时不得碰 LB01 的 347-356/451-453 硬拒区。

---

## 4. 收口点 11 族（§5.1b，P5 收敛必须收到这些已存在点，绝不新建）

| 族 | 已存在收口点 | 成员债 |
|---|---|---|
| 正整数 | `parse_finite_int`/`core/shared/number_utils` | R04,R09,R28,R29,R33,R50,LB04 |
| datetime | `core/shared/strict_parse` | R04,R09,R15,R28,R29,R30,R33,R49,R59 |
| 资源筛选 | `ScheduleResourceFilter`/`normalize_schedule_resource_filter` | R05,R34,R55,R67 |
| 方案身份 | `schedule_plan_role.py`/`build_plan_identity`/`SchedulePlanResolution.to_dict` | R07,R08,R14,R21,R22,R23,R34,R44,R54,R56,R57,R60,R72,LB01,LB02,LB03,LB05,LB06 |
| config双栈 | `ScheduleConfigSnapshot`(model栈为源) | R26,R29,R33,R45,R47,R48,R71,LB04,LB07 |
| boolean归一 | `core/shared/boolean_normalize`(下层为源) | R23,R41,LB04 |
| 关键链 | `gantt_critical_chain`(公共落点) | R11,R12,R34,R55,R63 |
| ready_queue/图 | `sgs_graph`(已取代) | R02,R06,R25,R52 |
| error体制 | `make_public_error` | R04,R09,LB08 |
| execution_review护栏 | `build_workbench_plan_context`(guard字段收口) | R07,R08,R21,R42,R44,R54,R56,R57,R58,R60,R62,R66,LB01,LB02,LB03,LB05,LB06 |
| facade残渣 | （删，不收口）SP05冻结的死兼容面 | 23 条，见 B13 |

> **唯一被批准的新建收口点**：R09 的可空正整数簇（`>0 或 None`）→ 新建 `parse_optional_positive_int`（`parse_finite_int` 没有 min_value 表达不了）。**这是唯一例外，不准推广。**

---

## 5. 承重护栏文件 + 落在 LB 文件上的真债（同改高危）

**承重护栏文件（任一 LB finding 引用的 basename）：**
`boolean_normalize.py`、`execution_review.py`、`navigation_context.py`、`operation_execution_feedback_service.py`、`reports_page_support.py`、`schedule_config_runtime_coercion.py`、`schedule_config_runtime_fields.py`、`schedule_config_runtime_read.py`、`schedule_config_runtime_snapshot.py`、`schedule_config_runtime_weights.py`、`schedule_plan_identity_builder.py`、`scheduler_public_errors.py`。

**真债与承重护栏文件同居（动它时绝不能碰 LB 的承重逻辑）：**

| 真债 | 桶 | 同居的承重文件 | 防呆 |
|---|---|---|---|
| R17 | B11 | operation_execution_feedback_service.py(LB01) | 删 EXECUTION_EVENT_EXCEPTION 死键/死导入时，不得碰 347-356 硬拒 + 451-453 写死消毒 |
| R42 | B01 | navigation_context.py(LB06,R56)+reports_page_support.py(LB06) | plan_id 死面包屑清理不得碰 execution_review 强制 adopted 分支 |
| R46 | B10 | scheduler_public_errors.py(LB08) | 删 `_safe_identifier` 死别名不得碰 LEGACY 正则桥 |
| R47 | B03 | schedule_config_runtime_coercion.py(LB07) | 删死参数 raw_value 不得碰双栈锁步字段 |
| R56,R57 | B01 | navigation_context.py(LB06,本桶) | 本桶内协调 |
| R62 | B01 | execution_review.py(LB02,LB05,本桶) | 三档标签压扁清理不得碰写死 ROLE_ADOPTED 的护栏 |
| R71 | B03 | schedule_config_runtime_coercion.py+read.py(LB07) | R71=LB07 配料表本身，收敛前先补 parity 测试 |

---

## 6. 对抗验证映射（27 verdict）+ 4 条缺独立 verdict

**verdict 标题匹配到 23 条债**（5 承重 + 18 真债）。关键 refuted 状态：

- **refuted=False（承重确认，不可删/统一）**：LB01,LB02,LB04,LB05,LB06,R04,R05,R29 → 其中 R04/R05/R29 是 real_debt 里 needs_adversarial 的，verdict 判 `load_bearing`/`depends`，**收口前必须先扩收口点/补契约测试**（R04 要给 parse_finite_int 加 min_value+严格 float 模式；R05 要给 ScheduleResourceFilter 加 team 轴；R29 number_utils 是 KEEP/high 门禁）。
- **refuted=True（真债确认，可收）**：LB03,R02,R07,R08,R09,R11,R12,R14,R20,R22,R24,R25,R26,R27,R32,R33,R34,R43,R44 —— 各有 `precondition_to_change`（见 `_all_debts_full.json` 的 `_verdict` 字段），多数=「先迁测试/补 parity/改 raise，再删」，**不是裸删**。

**⚠️ needs_adversarial=True 但 verdict 数组未收录独立结论的 4 条**（标题未精确匹配）：**LB08, R03, R52, R55**。
- LB08 = 承重（legacy 错误串桥），本就只补注释。
- R03（候选失败态全套死机制）、R52（ready_queue 全量扫描死版）、R55（filtered 关键链冒充整版）→ 对应桶 agent 需**额外谨慎复核**，不能依赖现成对抗结论。

---

## 7. 病理 / 严重度分布（80 条）

**病理**：P6=28、P3=21、P5=17、P2=6、P4=6、P4气味=1、呈现失真=1。
**严重度**：high=4（LB01,LB05,LB06,R54）、medium=25、low=50、trivial=1（R47）。

**按红线归类的修法范式**：
- **P6（28 条·直删类）**：grep 证全仓零引用后直删；多数需同步退 1-2 处测试/SP05 拓扑断言。
- **P5（17 条·收口类）**：收口到 §4 已存在点；R09 唯一例外可新建。
- **P4 + P4气味（7 条·灵魂线）**：改 **loud raise** 或补**可观测降级日志/标记**，**严禁加兜底**。涉 R07,R12,R28,R32,R40,R69,LB03。
- **P2/承重（含 LB01,LB02,LB05,LB06,R56,R58）**：只补"我是故意的"注释 + 绑契约测试，**零删除/统一/透传**。
- **P3（21 条）**：facade/残渣迁移（删，但先迁测试）或半截收口收敛。
- **呈现失真（R55）**：补 `scope=filtered/full` 标记，不裸删过滤。

---

## 8. 五条红线 + 机械检查清单（每条计划条目必过）

1. **灵魂暗线**：任何修法新增兜底/静默回退/`except:pass`/吞错/过度防御 = 作废重写。P4 必须 raise 或补可观测。
2. **承重护栏（load_bearing=true 的 8 条 + R56/R58 等 P2）**：只能①钉"我是故意的"注释（90 节已起草文案，直接复用）+②绑契约测试。**严禁删/合并/统一/透传参数**。LB04（boolean）若消重，唯一合法方向=上层 delegate 到下层。
3. **收口点规则**：P5 收口到 §4 已存在点；为已有概念新建第二模块 = 制造新 P5。唯一例外 = R09。
4. **分层红线**：0 AST 违规。不得引入跨层 import（`core.algorithms→core.services`、`core.models→core.services` 不存在）。删 facade 残渣前先确认消费方（常是测试）已迁走，否则撞 SP05 拓扑契约。
5. **工具标定**：drift 的 AVS ≠ 分层违规；MDS"精确重复"混着真护栏（如 LB04），不能直接删。

---

## 9. 17 桶定义（脚本验证后的最终切分）

| 桶 | 成员 | LB |
|---|---|---|
| B01 | LB01,LB02,LB05,LB06,LB03,R54,R56,R57,R58,R62,R07,R42,R60,R66,R08 | 5 |
| B02 | R22,R23,R72,R21,R44 | 0 |
| B03 | LB07,R71,R47,R45,R48 | 1 |
| B04 | LB04,R41 | 1 |
| B05 | R04,R09,R28,R29,R50,R59 | 0 |
| B06 | R15,R30,R33,R49,R51 | 0 |
| B07 | R05,R67 | 0 |
| B08 | R11,R63,R12,R55 | 0 |
| B09 | R02,R06,R25,R52 | 0 |
| B10 | LB08,R46 | 1 |
| B11 | R13,R14,R16,R17,R18,R24 | 0 |
| B12 | R34,R35,R37,R38,R39,R36 | 0 |
| B13 | R20,R26,R31,R43,R19 | 0 |
| B14 | R01,R10,R03,R27 | 0 |
| B15 | R68,R69,R70 | 0 |
| B16 | R32,R40 | 0 |
| B17 | R64,R65,R61,R53 | 0 |

---

## 10. 已知的全局排序硬约束（Phase 3 起点，Phase 1 需扩展量化）

1. **B01 必须最先落**：承重注释 + N1 guard 字段收口进 `build_workbench_plan_context` + 契约测试。后续任何动 execution_review/navigation_publish/reports_workbench/resource_dispatch 文件的桶（B02,B11）才能动，否则护栏裸奔期出错。
2. **B13 facade 删除必须晚于 B05/B06/B09 收敛**：B13 删 `common/{compat_parse,field_parse,value_policies}`、`config_service` shim、`graph/ready_queue` 等；若 B05(R29 number_utils)、B06(R33 compat/value_policies)、B09(R52 ready_queue)还经老路径走测试，先删 facade 会让测试经老路径红。
3. **同文件桶进同批次或串行**：§3 的 13 条跨桶边。
4. **承重前置（precondition_to_change）先于收口**：R04 扩 parse_finite_int、R05 扩 ScheduleResourceFilter、R22/R17(parity)、LB04 契约测试，必须先于对应收敛动作。
5. **R09 新建 `parse_optional_positive_int` 先于其 3 处复制迁移**（B05 内部）。

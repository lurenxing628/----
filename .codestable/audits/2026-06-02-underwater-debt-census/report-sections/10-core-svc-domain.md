## 分区【core-svc-domain】业务域服务与报表（services/{report,process,...}）

**分区健康一句话**：本分区基本干净、与"宁可暴露错误也不自欺"的灵魂高度一致——report 子域所有错误路径都抛 `ValidationError`/`BusinessError` 暴露给用户，六个业务域子包的 `except`/兜底逐条核验均为"暴露非吞"，codemap 在本分区的 orphan 标记几乎全是假阳性（漏算了 web/routes/plugin/scripts 等消费方）；真正的水下债只有两处：**一处承重护栏散在服务层却零注释（P2，高危，必须保护并补注释）**，一处零生产消费、仅靠契约测试反向续命的 re-export facade 残渣（P3，低危，可安全收口）。

本次复核结论（2026-06-02 回到当前 git modified/added 代码逐条 grep+Read）：**两条债的 file:line 全部仍然精确，无行号漂移，无疑似已修复**。详见每条末尾的"复核结论"。

---

### 债 1 ｜ execution_review 固定"正式采用方案"的承重不对称——服务层文件内零注释保护

- **病理标签**：P2 承重不对称（故意护栏但无注释）
- **严重度**：🟥 **high**
- **load_bearing**：✅ **true（承重护栏，默认不可删、不可"统一签名"）** — 本条是本分区最需要警惕的一条，对抗验证裁定 `load_bearing`、未被反驳。

#### 位置
- `core/services/report/execution_review.py:141` — `ExecutionReviewMixin.execution_review(self, version, *, date_from, date_to, batch_id, resource_type, resource_id)` 刻意**不收** `plan_role`/`scenario_id`。
- `core/services/report/execution_review.py:178` — `export_execution_review_xlsx(...)` 同样刻意不收 `plan_role`/`scenario_id`。
- 服务层内部 **5 处硬钉** `ROLE_ADOPTED` / `scenario_id=None`：
  - `:112` `_list_plan_rows_between(..., plan_role=ROLE_ADOPTED, scenario_id=None, ...)`
  - `:123` `_list_plan_rows_all(..., plan_role=ROLE_ADOPTED, scenario_id=None, ...)`
  - `:153` `host._resolve_plan(v, ROLE_ADOPTED, None)`
  - `:166-167` 输出固定 `"plan_label": plan_role_label(ROLE_ADOPTED)` / `"plan_role": ROLE_ADOPTED`
- **全文件零注释**说明"为何独缺 plan_role/scenario_id"。唯一一行人话注释是 `:70` 的 `# 计划和现场实际复盘`，并不解释这个不对称是故意的。

#### 引用链（护栏的保护证据全散在别处，服务层本体不设防）
1. **对照兄弟报表全部透传**：`core/services/report/report_engine.py:157` `overdue_batches(...)`、`:267` `utilization(...)`、`:371` `downtime_impact(...)` 三个签名全部接收并透传 `plan_role`/`scenario_id`——只有 `execution_review` 一处是钉死的。
2. **host 层完全不设防**：`core/services/report/report_plan_helpers.py:29` `_resolve_plan`、`:56` `_list_plan_rows_between`、`:83` `_list_plan_rows_all` 完整透传并尊重**任意** `plan_role`/`scenario_id`（`:37` `host.plan_query_service.resolve_plan_view(int(version), plan_role, scenario_id)`）。证明 `execution_review.py` 的 5 处硬钉是**唯一的钉死点**，宿主方法不会替它兜底。
3. **统一压力真实存在、范式已落地**：`web/routes/reports_page_support.py:57-58` 从请求读 `raw_plan_role = request_plan_role()` / `scenario_id = request_scenario_id()`，并在 `:404-409` 透传给 `engine.downtime_impact(..., plan_role=request_ctx["raw_plan_role"], scenario_id=request_ctx["scenario_id"])`；overdue/utilization 同构（`:146-147`/`:176-177`/`:233-234`/`:253-254`）。"路由读请求方案再透传"的范式已遍布同文件，**统一四报表签名只差 execution_review 这一处**——这正是未来重构的诱因。
4. **下游 join 无法自卫**：`data/repositories/operation_execution_event_repo.py:267` `aggregate_states_by_op_ids(self, op_ids)` 仅按 `op_id` 聚合现场反馈，**无 role/scenario 过滤**——喂进任何 `op_id` 它都照配。
5. **现场反馈只对正式采用方案存在**：`core/services/scheduler/operation_execution_feedback_service.py:347` `_load_current_official_schedule`：当 `plan_role != ROLE_ADOPTED`、或 `source_table != SOURCE_SCHEDULE`、或 `scenario_id` 非空时，`:354`/`:362` 一律 `raise _conflict("not_current_official_plan")`。即拿非采用/模拟方案的行去配 `op_id` 反馈 = 拿真实施工事实去给一个从未执行的假设方案贴"实际开始/偏差"列。
6. **护栏只活在 web 链接生成层 + 文档**：`web/viewmodels/scheduler_workbench_link_query.py:5` `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS = {...}` 与 `:266` `if target_page == "execution_review" and _text(key) in _EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS:` 拦截；`tests/regression_plan_vs_actual_review.py:350-359` 锁合同；设计文档 `.codestable/features/2026-06-01-reports-workbench-backlink/reports-workbench-backlink-design.md:28`「计划和现场实际只复盘正式采用方案」、`:71`「`ExecutionReviewMixin.execution_review()` 固定使用正式采用方案」、`:234`「非正式上下文不能变成可复盘链接」、`:253`「不把模拟预览和对比参考方案纳入计划和现场实际复盘口径」明文确认这是设计决定。**但这些守卫全在链接/导航/文档层，不在服务、也不在路由入参路径上**——服务签名一旦被"统一"，入站请求路径没有任何 `plan_role` 拒绝逻辑。

#### 为何算债
这是**故意的承重不对称**：计划和现场实际复盘 = 拿正式采用方案对账现场事实。若放开 `plan_role`/`scenario_id`，模拟方案预览（`is_scenario_preview`）或历史非采用方案会冒充"现场实际复盘"展示给车间，把"从未发生的预览/假设"当成既成事实呈现。承重点（对 `ROLE_ADOPTED` 的钉死）散在服务层 5 行里却**无一行注释说明"这是故意的、不要为了统一四个报表签名而加 plan_role"**——护栏只活在 web 层守卫和 roadmap 文档里。未来 LLM 或人以"统一四个报表入参"之名重构服务层时，会**无声抹掉**这个不变量，而服务层本身不会报错。

#### 爆炸半径
- 若被"统一报表签名"重构加回 `plan_role`/`scenario_id`：模拟方案预览 / 历史方案的明细会以"计划和现场实际"（正式复盘）身份呈现给现场——**数据完整性事故**，直接踩中灵魂红线"宁可暴露错误也不自欺"的反面。
- 同时 web 层 `_EXECUTION_REVIEW_FORBIDDEN_EXTRA_PARAMS` 守卫会与"放开后的服务层"产生**认知错位**：web 层还在禁，服务层已经接受，护栏破洞且无人察觉。
- 下游 `aggregate_states_by_op_ids` 不自卫，等于把真实施工反馈贴到从未执行的假设方案上。

#### 处置建议（默认不动；要动必须先补不变量的执行点）
**默认动作 = 不删、不统一、立即补注释。** 把散在别处的不变量可见化到服务层执行现场。最低成本即时动作——在 `:112`/`:123`/`:153` 三处硬钉旁各补一行"我是故意的"中文注释，建议文案：

```python
# 承重不对称(故意):计划和现场实际复盘只对账"正式采用方案"(ROLE_ADOPTED)。
# 现场反馈只对正式采用方案存在(见 operation_execution_feedback_service._load_current_official_schedule),
# 放开 plan_role/scenario_id 会让模拟预览/历史方案冒充"现场实际",把没发生的预览当既成事实。
# 禁止为"统一四个报表签名"而给本方法加 plan_role/scenario_id。要放开须先在本服务对
# 非 ROLE_ADOPTED/非 None scenario_id 显式 raise ValidationError,并给 aggregate_states_by_op_ids 加 role/scenario 过滤。
```

**收口到哪个已存在统一点**：不变量的"真理执行点"应落在 `execution_review` 服务自身（与 `operation_execution_feedback_service._load_current_official_schedule:347` 的硬拒同构——后者已是"现场反馈只认正式采用方案"的权威闸门，可在注释中引为依据）；护栏合同收口到既有的 `tests/regression_plan_vs_actual_review.py:350-359` 与 `tests/regression_reports_workbench_navigation_contract.py`。**若未来确有"允许复盘历史正式版本"的真实需求**，按对抗验证给出的顺序：(1) 在 `execution_review` 服务内对任何非 `ROLE_ADOPTED` 角色 / 非 `None` `scenario_id` 显式 `raise ValidationError`（硬拒、绝不默默回退 adopted），把不变量执行点留在服务层；(2) 给 `aggregate_states_by_op_ids` 增加 role/scenario 作用域过滤让 join 能自卫；(3) 在路由入站层加 `plan_role/scenario_id` 闸门并保留/扩展 web 层 forbidden-params 守卫，消除两层认知错位；(4) 用上述两个 regression 测试锁死。

#### 复核结论
✅ **证据仍准**。`:141`/`:178`/`:112`/`:123`/`:153`/`:166-167` 六处行号在当前代码中**完全精确匹配**，5 处硬钉与签名缺 `plan_role`/`scenario_id` 一字不差；服务层文件本体**仍然零注释**（唯一 `:70` 注释只标题不解释）。引用链全部复核命中：`report_engine.py:157/267/371`、`report_plan_helpers.py:29/37/56/83`、`reports_page_support.py:57-58/404-409`、`operation_execution_event_repo.py:267`、`operation_execution_feedback_service.py:347/354/362`、`scheduler_workbench_link_query.py:5/266` 全部准确。**唯一一处文档行号偏移**：原证据 reference_chain 写「design.md:28/71/164」，实测决定句在 **28/71/234/253**（line 164 与本决定无关，应以 234/253 为准）——不影响结论，证据成立。本条未被修复，仍是高危承重债。

---

### 债 2 ｜ 三个零生产消费的 re-export facade 残渣（compat_parse / field_parse / value_policies），仅测试续命

- **病理标签**：P3 半截迁移残渣
- **严重度**：🟩 **low**
- **load_bearing**：❌ false（删除安全，但需按序保护"坏数据必经降级暴露"的测试覆盖，不能连测一起删光）。对抗验证裁定 `real_debt`、原"可能是有意分层约定"的疑虑已被反驳（`_adv_refuted=true`）。

#### 位置
- `core/services/common/compat_parse.py:1-13` — 纯 re-export，仅 `from core.shared.compat_parse import parse_compat_date/float/int` 再经 `__all__` 转发，无任何逻辑。
- `core/services/common/field_parse.py:1-5` — 纯 re-export，仅转发 `core.shared.field_parse` 的 `parse_field_float`/`parse_field_int`。
- `core/services/common/value_policies.py:1-39` — 纯 re-export，仅转发 `core.shared.value_policies` 的 13 个符号。

#### 引用链（生产侧已大面积绕过该 facade，直连 core.shared）
1. **三者生产引用全部 = 0**：grep `core/ web/ data/ scripts/`（排除三文件自身、排除 tests）对 `services.common.{compat_parse,field_parse,value_policies}` 命中数**均为 0**（本次 2026-06-02 实测复现）。
2. **生产实际走 `core.shared.*` 直连**：例如 `core.shared.field_parse` 被 `core/algorithms/greedy/external_groups.py`、`core/algorithms/greedy/schedule_params.py`、`core/models/schedule_config_runtime_coercion.py`、`core/services/scheduler/run/schedule_input_builder.py` 等直接 import，**绕过 facade**。
3. **唯一续命者是测试**（全仓对这三个 `services.common` 别名的引用仅来自 tests/ 与 codemap 快照 json）：
   - `tests/regression_config_service_component_contract.py:14/16/19` — 三者作为条目写在 `_SERVICE_COMMON_NEUTRAL_HELPERS` 元组（`:13` 起）内；
   - 同文件 `:393-399` `test_services_common_value_policies_reexports_shared_identity`（`:394` `from core.services.common import value_policies as service_value_policies`，断言 `service_value_policies.X is shared_value_policies.X`）；
   - 同文件 `:402-411` `test_services_common_parse_core_reexports_shared_identity`（`:403` `from core.services.common import compat_parse as service_compat_parse`，断言 `is shared_compat_parse.X`）——纯自循环"转发身份正确"断言，正是反向续命这三个空壳的唯一来源；
   - 两个行为测试 `tests/regression_compat_parse_emits_degradation.py:18`（`from core.services.common.compat_parse import parse_compat_date, parse_compat_float`）与 `tests/regression_value_policies_matrix_contract.py:18`（`from core.services.common.value_policies import (...)`）虽经 facade 导入，但其断言的是 `core.shared` 底层的**降级发射 / 策略矩阵行为**，非 facade 特有行为，可平移到 `core.shared`。
4. **包级无再导出、无动态引用**：`core/services/common/__init__.py` 为 **1 字节空文件**，无包级再导出；无 `importlib`/`__import__` 动态引用；codemap `rev_deps.json` 中三者均**不是 key**（零生产被引用）。
5. **对照同目录"真兄弟"facade（被采纳的约定）**——本次实测生产消费数：
   - `services.common.strict_parse` = **4 处**生产消费（`core/services/scheduler/operation_edit_service.py`、`core/services/process/supplier_excel_import_service.py`、`core/services/process/supplier_service.py`、`web/routes/process_excel_suppliers.py`）；
   - `services.common.degradation` = **14 处**生产消费；
   - `services.common.number_utils` = **2 处**生产消费（`core/services/common/excel_validators.py`、`web/routes/domains/scheduler/scheduler_excel_calendar_rows.py`）。
   它们是被采纳的 services 层 re-export 约定；而 compat_parse/field_parse/value_policies 三者是**同一约定下零采纳的空壳**。
6. **不存在"必须经 facade"的强制约定，反而对热路径强制反向**：`tests/regression_config_service_component_contract.py:350` `test_scheduler_run_uses_shared_parse_and_degradation_helpers` 把 `_SERVICE_COMMON_NEUTRAL_HELPERS`（含这三者）列为 run 层的 **FORBIDDEN imports**（`:355` `if imported == "core.services" or imported.startswith(_SERVICE_COMMON_NEUTRAL_HELPERS)`），断言主排产链**必须直连 core.shared**。即体系明确禁止热路径经 services.common facade——这三个空壳没有任何"分层 API 表面"价值。

#### 为何算债
"通用服务底座模块"迁移（commit `5ab57494`）后，生产侧对这三个概念要么直连 `core.shared`、要么根本没用 `services.common` 入口，留下三个**无人（生产）消费的 facade**，只靠一个"断言 facade 转发身份正确"的契约测试反向续命——典型的**迁移收尾未清 + 测试自我循环**。删掉这三个 `.py` 及对应测试断言即可，生产零影响。

#### 爆炸半径
- **保留的运行期爆炸半径 = 0**（无人调用），但会持续误导后人误以为存在"services 层必须经 facade"的强制约定。
- **删除的爆炸半径 = 仅需同步删/改 3 处测试**（见处置）。无任何生产文件受影响。

#### 处置建议（删除安全，但按序保护灵魂暗线"坏数据必经降级暴露、不静默兜底"）
**不能连测一起删光**——两个行为测试是承重的（承重点在 `core.shared`，不在 facade）。按序：
1. 先把两个行为测试的 import 从 `core.services.common.*` **改指 `core.shared.*`**：`regression_compat_parse_emits_degradation.py:18` → `from core.shared.compat_parse import ...`；`regression_value_policies_matrix_contract.py:18` → `from core.shared.value_policies import ...`。保住降级发射与策略矩阵覆盖。
2. 从 `tests/regression_config_service_component_contract.py` 删除三处身份断言：元组内 `:14`/`:16`/`:19` 三个条目、`:393` 起 `test_services_common_value_policies_reexports_shared_identity`、`:402` 起 `test_services_common_parse_core_reexports_shared_identity`。**从 `_SERVICE_COMMON_NEUTRAL_HELPERS` 删条目是安全的**——该元组用于 run 层"禁止导入"白名单，把一个即将不存在的模块从禁止清单移除只会放松对不存在模块的检查，且无任何生产文件导入它。
3. 最后删三个 `.py`。完成后生产运行期零影响、灵魂暗线覆盖无损失。

**收口到哪个已存在统一点**：三个概念的唯一真理已统一在 `core.shared.{compat_parse,field_parse,value_policies}`（生产已直连、`strict_parse`/`degradation`/`number_utils` 为同约定的活样板）；行为测试覆盖收口到 `core.shared` 底层。无需新建统一点，删壳即归一。

#### 复核结论
✅ **证据仍准**。三个 `.py` 当前内容与原证据一字不差（compat_parse `:1-13`、field_parse `:1-5`、value_policies `:1-39` 纯 re-export）；2026-06-02 重跑 grep，三者在 `core/ web/ data/ scripts/`（排除 tests）的生产引用**仍全部 = 0**；续命测试行号全部精确命中（`:14`/`:16`/`:19`/`:393-399`/`:402-411`，行为测试 `:18`/`:18`）；`__init__.py` **仍为 1 字节空文件**；真兄弟 facade 消费数实测 strict_parse=4 / degradation=14 / number_utils=2，与原证据一致。本条未被修复，仍是低危可收口残渣。

## 02 · 分区【scheduler-dispatch】资源派工（resource_dispatch_*）水下语义债

**分区健康一句话**：本分区主体是 5 月底刚落地的"资源派工执行车道"（roadmap 全 done，commit `65870e47`），降级处理（超期标记 degraded/partial 上抛 + 日志）忠实贯彻"坏数据不准静默兜底"灵魂线，绝大多数 `except` 是 anti-P4（重抛或记 degradation），**无两套并行生产实现、无 plan_id 式死透传**；水下债集中在边角——一处承重的资源 scope 列映射双轨漂移（派工绕开收口点，且其中 team 轴是收口点表达不了的真实承重逻辑）、一个误建的空包、一处写后卡片对 schedule 缺失的静默兜底、一个生产不可达的休眠开关 + 死面包屑、一组三处逐字节复制的可空正整数助手。共 **5 条**。

> 本节复核基准：2026-06-02 当前代码（分区内多文件处于 git modified/added，刚随 `65870e47` 落地）。每条结论标注 ✅证据仍准 / ⚠️行号已变 / 🔧疑似已修复。

---

### 02-1 · 派工 scope_type 归一与 operator/machine→列映射绕开 ScheduleResourceFilter 收口点（双轨漂移）

- **病理标签**：P5（第 N 套私有实现）
- **严重度**：medium
- **load_bearing**：⚠️ **承重（关键）**。条目原始字段 `load_bearing=false`，但对抗验证把它**升级为 `load_bearing`**（`_adv_verdict: "load_bearing"`，`_adv_refuted: false`）。原因：operator/machine 那部分列映射确属可复用却没复用的债，但 **team（班组）轴的双 join 是收口点根本表达不了的真实第三轴，是承重逻辑**，不能随"统一"一起塌缩。本条因此是"可约简的 P5 外壳 + 不可约简的承重内核"复合体，需特别醒目对待。

**位置**
- `core/services/scheduler/resource_dispatch_service.py:63`（`_normalize_scope_type`，自校验 `{operator,machine,team}`）
- `data/repositories/schedule_plan_query_repo.py:447-463`（`list_dispatch_rows`，内联列映射；team 双 join 在 461-463）

**引用链（当前代码逐段复核）**
1. `resource_dispatch_service._normalize_scope_type:63-67` 自校验 `{operator,machine,team}` 并自报 `ValidationError("视角类型不正确…")`，**不调用** 收口点 `core/models/schedule_resource_filter.normalize_schedule_resource_filter`（该收口点仅认 `{machine,operator}`）。
2. `get_dispatch_payload`（def 现位于 `resource_dispatch_service.py:350`）在 `:368` 调 `_normalize_scope_type`，于 `:424-433` 调 `plan_query_service.list_plan_dispatch_rows_for_resolution(...)`，其中 `scope_type=normalized_scope_type` 在 `:431`、`scope_id=selected_scope_id` 在 `:432`。
3. `schedule_plan_query_service.list_plan_dispatch_rows_for_resolution:387` → `:399` 转调 `repo.list_dispatch_rows`。
4. `schedule_plan_query_repo.list_dispatch_rows:430` 内联展开 scope（当前精确行）：
   - `:451-453` `operator` + 有 id → `TRIM(COALESCE(s.operator_id,''))=?`
   - `:454-455` `operator` 空 id → `TRIM(COALESCE(s.operator_id,'')) <> ''`（全部人员视图）
   - `:456-458` `machine` + 有 id → `s.machine_id`
   - `:459-460` `machine` 空 id → `<> ''`（全部设备视图）
   - `:461-463` `team` + 有 id → `((o.team_id = ?) OR (m.team_id = ?))`，`params.extend([scope_id_text, scope_id_text])`
5. **另一轨（超期/明细读取）走收口点**：同一 repo 文件 `list_overdue_base_rows`（`:391` `overdue_resource_filter(...)` → `:396` `resource_scope.column_name`）以及 `data/repositories/schedule_resource_sql_filters.py:18-19`（`overdue_resource_filter`）+ `:36`（`append_detail_filters` 用 `s.{resource_filter.column_name}`）。
6. 收口点本体 `core/models/schedule_resource_filter.py`：`:8` `SUPPORTED_SCHEDULE_RESOURCE_TYPES={machine,operator}`；`:19-24` `column_name` 对 team 返回 `''`；`:59-70` 对不支持类型 raise、对缺 id raise。
7. **canonical normalizer 在派工链路零引用**：grep `normalize_schedule_resource_filter` / `column_name` 于 `resource_dispatch_service.py` 与 `schedule_plan_query_service.py` 均 0 命中。

**为何算债**
资源类型→列名这件事项目已有统一收口点（`column_name` 属性 + `normalize_schedule_resource_filter`），但派工读取链路私自实现第 N 套：service 层自校验类型 + repo 层内联列字面量（`s.operator_id` / `s.machine_id`）。后果是 operator/machine 列名规则散在派工与超期两处，改一处忘另一处会让"派工筛选"和"超期筛选"对同一资源口径漂移。**但**：team 班组轴（双 `team_id` join）是收口点 `{machine,operator}` 单列属性结构上表达不了的真实第三轴——这是派工链路不能整体塌缩到现状收口点的合理原因。因此真正可约简的只有 operator/machine 列字面量，team 分支是承重特例。

**对抗验证结论（已证陷阱）**
- `column_name('team') == ''` 而 `has_filter('team') == True`：把 team 路由进收口点，要么 raise（吵闹）、要么静默丢掉 WHERE 子句返回**全部班组数据**（坏数据静默兜底，直接违反灵魂线）。
- 收口点 `:59-70` 对缺 id **强制 raise**（实测 `normalize_schedule_resource_filter('operator','')` → `资源筛选缺少资源编号`），会打断派工的"全部人员/全部设备"（空 id）视图。
- `_normalize_scope_type` 是收口点的**超集校验器**（含 team + 空 id 语义），不是它的重复实现，**不能直接换**。
- `tests/test_scheduler_resource_dispatch_smoke.py:177`（`scope_type=team&team_id=TEAM-OP&team_axis=operator…`）、`:182`（断言"班组轴"）、`:162`（"跨班组"）是活的、被测的生产行为，naive 替换是真实回归而非理论。

**爆炸半径**
- 若有人"统一"把 `_normalize_scope_type` 直接换成 `normalize_schedule_resource_filter`：丢掉 team 轴 → 班组视角整页 500。
- 若强行让 `repo.list_dispatch_rows` 复用 `column_name` 而漏处理 team 分支：team 筛选静默失效返回全量坏数据。
- 任何改动必须**同时保留 team 特例与空 id 全量语义**。

**处置建议 + 收口到哪个统一点**
方向是"先扩容收口点，再谈统一"，**严禁反向把派工塞进现状收口点**。顺序：
1. 给 `ScheduleResourceFilter` / `normalize_schedule_resource_filter` 增加 **team 轴表达能力**——`column_name` 单列属性不够，需新增一个能产出 `((o.team_id=?) OR (m.team_id=?))` 双 join 谓词的接口；并放开"类型有、id 空 = 全量"语义（当前收口点强制非空 id，会打断派工全部人员/全部设备视图）。
2. **先补回归断言**：`scope_type=team` 只返回该 team 的行而非全量（钉死"静默丢谓词"反例），以及"全部人员/全部设备"空 id 视图仍可查。
3. **仅在收口点同时覆盖 team 双轴 join + 空 id 全量语义后**，才可把 repo 的 `s.operator_id` / `s.machine_id` 列字面量和 `_normalize_scope_type` 收敛进去。在此之前两轨必须并存；`test_scheduler_resource_dispatch_smoke.py` 的 team 用例须全程保持绿。

**"我是故意的"注释文案**（建议补在 `schedule_plan_query_repo.py:461` team 分支上方，钉死承重意图）：
```python
# 【承重·勿统一】team（班组）轴是双 join 谓词 ((o.team_id=?) OR (m.team_id=?))，
# core.models.ScheduleResourceFilter.column_name 只能产单列、且 SUPPORTED 只含
# {machine,operator}，结构上表达不了班组轴。此处必须独立内联，不能塌缩进收口点。
# 同理 operator/machine 的空 id 分支（全部人员/全部设备视图）依赖"类型有、id 空=全量"
# 语义，收口点当前对缺 id 强制 raise，也不能直接替换。
# 收敛前置条件见审计 02-1：先给收口点补 team 双 join + 空 id 全量语义。
```
并建议在 `resource_dispatch_service.py:63` `_normalize_scope_type` 上方注明"本校验器是收口点的超集（多 team），不可被 normalize_schedule_resource_filter 替换"。

**复核结论**：✅ 证据仍准。`_normalize_scope_type:63`、repo `list_dispatch_rows:447-463`（team 双 join 精确落在 461-463）、service 调用点 `:424-433`（`scope_type` kwarg 仍在 `:431`）、收口点 `schedule_resource_filter.py:8/19-24/59-70`、超期轨 `schedule_resource_sql_filters.py:18-19/36`、smoke 测试 `:177/182/162` 全部逐行对上。仅 `get_dispatch_payload` 的 def 行随车道落地略有位移（现 `:350`），但条目原始引用的是其内部调用点 `:431`，该行仍精确。

---

### 02-2 · 空包 `core/services/scheduler/dispatch/` 为无关提交误建、零引用残渣

- **病理标签**：P3（半截迁移/脚手架残渣）
- **严重度**：low
- **load_bearing**：false

**位置**：`core/services/scheduler/dispatch/__init__.py`

**引用链（当前代码逐段复核）**
- `ls -la core/services/scheduler/dispatch/` → 目录仅含 `__init__.py`，**0 字节**（`wc -c` = 0），无任何兄弟模块。
- `git log --oneline -- core/services/scheduler/dispatch/` → 唯一提交 `24f4c93e "Implement SP05 path topology guardrails"`（SP05 是图拓扑护栏，与资源派工域**无关**）。
- grep `scheduler\.dispatch` / `scheduler/dispatch`（排除 `resource_dispatch`、`greedy`、`schedule_graph_dispatch`）全仓：**仅** `.codestable/audits/*` 与 `.codestable/checkup/latest/codemap/modules.json` 等审计/codemap 文档命中，**零生产代码引用**（无 `.py` / `.html` / 业务 `.json` 动态 import）。

**为何算债**
迁移/脚手架残渣：一个无关 feature（SP05 图拓扑）顺手建的空 package，命名恰好撞上"dispatch"域，既无内容也无引用，制造"派工还有个 dispatch 子包"的假象，误导后来者去找根本不存在的模块（实际派工代码全在 `core/services/scheduler/` 外层平铺为 `resource_dispatch_*`）。

**爆炸半径**：删除无任何运行时影响（零 import）。唯一风险是若未来有人误以为它是命名空间锚点，但当前无证据。

**处置建议 + 收口到哪个统一点**：直接删除空目录 `core/services/scheduler/dispatch/`（删前再确认无 `importlib` 字符串动态引用，本次 grep 已确认无）。与第一轮地基体检（`.codestable/audits/2026-06-01-foundation-maturity/`）记录的"清空占位目录"一并处理——同源残渣应收到同一次清理 PR。无需新建任何收口点。

**复核结论**：✅ 证据仍准。0 字节、唯一提交 `24f4c93e`、零生产引用三项全部当前复现。

---

### 02-3 · 写后任务卡对 schedule 行缺失静默兜底为"正式采用方案/可写"卡片

- **病理标签**：P4（静默兜底死角）
- **严重度**：low
- **load_bearing**：false（对抗验证 `_adv_verdict: "real_debt"`，`_adv_refuted: true`——"这是防御性回显"的辩护被驳回，确认是真该暴露的缺口）

**位置**：`core/services/scheduler/resource_dispatch_execution_service.py:131-141`

**引用链（当前代码逐段复核）**
- `task_card_for_feedback_context`（def `:124`）在 `:131` `schedule = self.schedule_repo.get(int(context.schedule_id))`。
- `:132 if schedule is None:` → `:133-141` 直接返回 `plan_identity={}`、`plan_identity_label="正式采用方案"`、`can_write_feedback=True`、`feedback_write_enabled=feedback_write_enabled` 的**正常卡片**，不抛错也不降级。
- 对照正常分支 `:142-167`：schedule 存在时才用 `list_plan_dispatch_rows_for_resolution` + `_matching_row` 装配真实"实际/计划对比卡"。
- `context.schedule_id` 来源：routes `_feedback_context` 取自 payload，且写入门禁已在别处校验 op_id+schedule_id+batch_id 在当前计划查询行内——即"计划行内有、`schedule_repo.get` 返 None"是真数据缺口/真不一致。

**为何算债**
项目灵魂线是"坏数据不准静默兜底、宁可暴露错误"。这里 schedule 行查不到（真缺口/真不一致）时，不抛错也不降级提示，直接返回 `can_write=True` 的"正式采用方案"卡，把缺口吞掉。虽是写入成功后的展示路径（写门禁在别处独立强校验，**不构成越权写**），但用户看到的"实际/计划对比卡"建立在已不存在的 schedule 行上，属于自欺式兜底。

**对抗验证结论（分支当前不可达，但兜底写法本身仍是债）**
该 None 分支在生产**不可达**——每条写路径在装卡前已 raise NOT_FOUND：
- legacy 写路径 `operation_execution_feedback_service._load_current_official_schedule`（`:347`）在写事务内 `schedule_repo.get` 为 None 时 raise `AppError(NOT_FOUND)`（`:365`/`:368`），装卡时行已证存在于同一连接。
- 实际记录写路径 `resource_dispatch_actual_record_service._task_ref_from_feedback_context:214` 在 `schedule_repo.get` 为 None 时 raise NOT_FOUND（`:218`）。
- `card.can_write_feedback` 仅 UI 提示——后续每次写都服务端重推 plan identity 并重跑 official/existence 门禁，撒谎的卡片授权不了任何坏写。

**爆炸半径**：仅影响单条写入成功后的回显卡片正确性；不影响写入门禁（门禁独立强校验）。若改为抛错需确认不会把正常写后回显误判失败（happy path 本就不走该分支，故无影响）。

**处置建议 + 收口到哪个统一点**
**不要裸删 `:131-141`**——直接删会让控制落到 `:142`/`:147-148` 的 `schedule.start_time`，在写入已提交后抛 `AttributeError` → 500，谎报写失败。正确做法：把该 None 分支改成**显式 `raise AppError(ErrorCode.NOT_FOUND, …)`**，与灵魂线及同模块既有写门禁口径一致（收口到 `operation_execution_feedback_service:365/368`、`resource_dispatch_actual_record_service:218` 已用的 NOT_FOUND 文案族）；并先确认/锁定两个调用语义：装卡始终发生在写门禁通过之后。补一条"该分支转 raise"的回归测试。改完不影响 happy path（分支本就不可达），不削弱任何写门禁。

**复核结论**：✅ 证据仍准（主位置精确）。`:131` `schedule_repo.get`、`:132-141` 兜底 return 当前逐行对上；不可达性所依赖的 NOT_FOUND raise 仍在（`operation_execution_feedback_service:365/368`、`resource_dispatch_actual_record_service:218`）。⚠️ 附注：条目对抗证据里引用的 routes 调用点行号（`264-265/278-279/200-201`）随车道 `65870e47` 落地已位移——`task_card_for_feedback_context` 的生产调用点现为 `scheduler_resource_dispatch_execution_routes.py:184 / :192 / :201`（三处恒传 `feedback_write_enabled=True`，且卡片严格在写步骤成功返回后构建）。核心结论与处置不变。

---

### 02-4 · `feedback_write_enabled` 休眠开关 + 生产不可达的"保护未开启"提示

- **病理标签**：P6（死代码/死面包屑）
- **严重度**：low
- **load_bearing**：false（对抗验证 `_adv_verdict: "real_debt"`，`_adv_refuted: true`——"它是已接线的未来 toggle"的辩护被驳回）

**位置**：`web/viewmodels/scheduler_resource_dispatch_execution.py:24, 226-227, 361-362`

**引用链（当前代码逐段复核）**
- 唯一数据路径生产者 `resource_dispatch_execution_service.get_execution_context` 把两者设为**同一来源**：`:117` `"can_write_feedback": bool(plan_role_fields.get("can_write_feedback"))`，`:120` `"feedback_write_enabled": bool(plan_role_fields.get("can_write_feedback"))`——同源恒等。`:204` `_empty_context` 两者皆 `False`。主路径只产 `(True,True)`/`(False,False)`，`(True,False)` 不可达。
- viewmodel 常量 `:24` `_FEEDBACK_DISABLED_REASON = "现场记录保护还没开启，暂不能填写现场记录。"`
- `_fill_actual_disabled_reason`（def `:223`）`:224 if not can_write: return _NOT_CURRENT_OFFICIAL_REASON`；`:226-227 if not feedback_write_enabled: return _FEEDBACK_DISABLED_REASON`——仅 `(can_write=True, feedback_write_enabled=False)` 才到。
- `build_execution_payload`（def `:331`）`:359-360 if not can_write` → `_NOT_CURRENT_OFFICIAL_REASON`；`:361-362 elif not feedback_write_enabled` → `_FEEDBACK_DISABLED_REASON`——同样仅该不可达组合才返回。
- `task_card_for_feedback_context`（service `:124`，默认参 `:129 feedback_write_enabled=True`）路径 `can_write_feedback` 恒为 `True`；三处路由调用方 `scheduler_resource_dispatch_execution_routes.py:184/192/201` 恒传 `feedback_write_enabled=True`，故只产 `(True,True)`，同样不可达 `(True,False)`。
- 全仓 grep `feedback_write_enabled`：无任何 `config`/`settings`/特性开关读取它（唯一旁系命中是 `scheduler_workbench_links.py` 的 `can_emit_feedback_write_urls`，是 URL 发射的另一关注点）。

**为何算债**
参数本身被消费（非纯死参），但它守护的状态组合 `(True,False)` 在生产**永不出现**，"现场记录保护还没开启"这句用户可见文案真实用户永远看不到。文案口吻（"还没开启"）像是为未来"反馈保护总开关"预埋的 toggle，却从未接到任何配置/特性开关，成了散布在 viewmodel 多处的死面包屑，制造"有个保护开关在用"的假象。

**对抗验证结论**
- service `:117/120` 同源恒等、`:204` 双 False，证实 `(True,False)` 主路径不可达。
- 真正写入护栏在 `operation_execution_feedback_service:361`（`raise … if not plan_identity.can_write_feedback`）与 `resource_dispatch_actual_record_service:137-149`（`_ensure_context_can_write` 基于 `can_write_feedback`/plan_role/source_table/scenario），**全程不消费 `feedback_write_enabled`**——删该展示分支不削弱任何写入不变量。
- `tests/regression_resource_dispatch_workbench_lane_contract.py:164-174` 传 `(can_write_feedback=False, feedback_write_enabled=False)`，因 `can_write=False` 在 `build_available_actions:234` 与 `_fill_actual_disabled_reason:224` 双重短路，`feedback_write_enabled` 分支根本未被执行；grep 确认全仓无任何对 `现场记录保护`/`FEEDBACK_DISABLED`/`disabled_reason` 的断言。

**爆炸半径**：删除该分支与文案不影响任何生产行为（状态不可达），且不破任何测试（已 grep 确认无人断言该字符串）。

**处置建议 + 收口到哪个统一点**（二选一，均需先向 owner 确认）
- **(A) 只删死分支 + 死文案**：删 viewmodel `:226-227` 与 `:361-362` 的 `feedback_write_enabled` 分支及 `:24` 的 `_FEEDBACK_DISABLED_REASON` 常量，保留参数即可，无测试会断。
- **(B) 彻底收口**：把 `feedback_write_enabled` 参数整体并入 `can_write_feedback`——须同步改 4 处签名：service `:129` 默认参、routes `:184/:192/:201` 三处 kwarg、test 的 `build_task_card` 调用，去掉 kwarg 后再删 viewmodel 分支。
- **前置闸门**：两种做法前都应向刚落地的"resource dispatch execution lane" roadmap（commit `65870e47`）owner 确认：近期不计划在此接缝上线真正的"现场记录保护总开关"配置。若确无该规划，按默认立场收为普通债（推荐 A，改动面最小）。

**复核结论**：✅ 证据仍准。`:24`/`:226-227`/`:361-362` 三处 viewmodel 锚点、service 同源 `:117/120`、`_empty_context:204`、test `:164-174` 全部逐行对上（`_fill_actual_disabled_reason` def 现 `:223`，分支体仍 `:226-227`）。

---

### 02-5 · `_positive_int` 可空正整数助手在执行车道三处逐字节复制

- **病理标签**：P5（第 N 套私有实现）
- **严重度**：low
- **load_bearing**：false（对抗验证 `_adv_verdict: "real_debt"`，`_adv_refuted: true`——"是允许的层内小助手"辩护被驳回，确认是真 P5；但有"换错收口点会更糟"的强约束）

**位置**（三处函数体逐字节相同）
- `core/services/scheduler/resource_dispatch_execution_service.py:23`
- `web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:37`
- `web/viewmodels/scheduler_resource_dispatch_execution.py:32`

**引用链（当前代码逐段复核）**
三处 `def _positive_int(value: Any) -> Optional[int]:` 函数体完全相同（已逐行核对）：
```python
def _positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
```
契约 = "垃圾 → None、非正 → None"（可空跳过，用于遍历可信 DB 行/已校验整数时跳过无 op_id 的行）。调用点全是显示与归属判定：service `_op_ids`/`_matching_row`、viewmodel `build_task_card`/任务列表（`:347` 等）、routes `_row_matches_feedback_target` 比对可信行。

**全仓散布（grep `def _positive_int` / `def _required_positive_int`，当前 10 文件）**：
- 本簇 3 处可空变体（上列）
- **STRICT（raise）变体，契约不同，不在本簇收口范围**：`operation_execution_feedback_support.py:162`（`_positive_int(value, field)` raise）、`data/repositories/operation_execution_event_repo.py:96`（`_required_positive_int` raise）、`core/models/scheduler_public_errors.py`、以及 `graph/input_adapter.py`、`summary/schedule_summary_assembly.py`、`run/auto_assign_resource_errors.py`、`run/schedule_persistence_errors.py` 等。

**为何算债**
同一个"解析正整数"诉求在一个 feature 内复制三份（且全仓十余份），项目本有 `core/shared/number_utils.parse_finite_int` 统一解析收口。但 `_positive_int` 的契约（垃圾静默成 None、过滤非正、用于遍历行时跳过坏行）与 `parse_finite_int`（垃圾抛错）确有差异，故严格说不是直接绕开同一职责，介于 P5（第 N 套私有解析）与可接受的层内小助手之间——对抗验证裁定为真 P5：可空契约本身值得有一个 canonical 收口，三处逐字节复制是不必要的重复。

**对抗验证结论（严禁套错收口点）**
- 收口点 `parse_finite_int` 契约不同：`core/shared/number_utils.py:39` `allow_none=True` 仅短路空白，垃圾仍 raise（`core/shared/strict_parse.py:36/40` 对非数字 `raise ValidationError("…必须是数字")`）。套用会把"跳过坏行"退化为"抛错中断整页"。
- 真正的安全不变量由别处 RAISE 守住，非本助手的静默 None：反冒充归属校验无匹配行时抛 `SCHEDULE_CONFLICT`（routes）；用户输入 `schedule_id` 为 None 时抛 `ValidationError`（routes，fail-closed）；写入边界用 STRICT 变体重新校验并抛错（`operation_execution_feedback_support.py:162`、`operation_execution_event_repo.py:96`，写路径在 `operation_execution_feedback_service:222-224` 调用）。`op_id` 经 Flask `<int:op_id>` 路由转换器已是合法整数。

**爆炸半径**：若强行换成 `parse_finite_int` / `parse_optional_int(allow_none=True)`，遍历行收集 op_id 处会从"跳过坏行"变成"抛错中断整页"，并改变 routes 用户输入 `schedule_id` 的拒绝路径。需新增一个 canonical 的"可空正整数"收口，而非套用 `parse_finite_int`。

**处置建议 + 收口到哪个统一点**
1. 先在 `core/shared`（与 `number_utils.parse_finite_int` 同处）新增一个 canonical 的**可空正整数**收口，契约必须保持「垃圾→None、非正→None」——即 `parse_finite_int` 的兄弟，建议命名 `parse_optional_positive_int`。
2. 把本簇 3 处（及全仓其余 nullable 同体）迁移过去。
3. **严禁**改用 `parse_finite_int` / `parse_optional_int(allow_none=True)`（它们对垃圾值 raise）。
4. **不要动 STRICT 变体**（`operation_execution_feedback_support.py:162`、`operation_execution_event_repo.py:96`、`scheduler_public_errors.py`）——它们契约是 raise，是真正的写入闸门，不在本簇收口范围。

**复核结论**：✅ 证据仍准。三处 `_positive_int` def 当前位于 `service:23 / routes:37 / viewmodel:32`，函数体逐字节相同已核对；收口点 `number_utils.parse_finite_int:39` 与其 raise 链 `strict_parse.py:36/40` 仍在；STRICT 变体 `operation_execution_feedback_support.py:162`、`operation_execution_event_repo.py:96` 仍在。全仓散布现为 10 文件（与条目"5+ 处"一致，更多）。

---

### 本分区复核汇总

| # | 病理 | 严重度 | load_bearing | 复核 |
|---|------|--------|--------------|------|
| 02-1 | P5（含承重内核） | medium | ⚠️ 承重（adv 升级） | ✅ 证据仍准 |
| 02-2 | P3 | low | false | ✅ 证据仍准 |
| 02-3 | P4 | low | false | ✅ 主位置准；附注 routes 调用点行号已移至 184/192/201 |
| 02-4 | P6 | low | false | ✅ 证据仍准 |
| 02-5 | P5 | low | false | ✅ 证据仍准 |

合计 5 条：5 条主位置证据仍准，其中 02-3 的**对抗证据**层 routes 调用点行号随车道 `65870e47` 落地位移（已给新行号 184/192/201），主位置 `resource_dispatch_execution_service.py:131-141` 不变；0 条疑似已修复。承重重点是 02-1 的 team 双 join 轴，必须先扩容收口点、补回归断言，才能收敛 operator/machine 那部分可约简的 P5 外壳。

# Fixed 态确认 + R29 误标复核

> **⚠️ 2026-06-08 A 收官路径终态（B 执行前必读）**：`tests/regression_aps_workbench_flow_contract.py` 已由 A 的 **P5.1（commit `1fa076fb`）合并**入 `tests/web_pages/test_aps_workbench_context_propagation_contract.py`（含 ★R57-PINNED 标记，PIN 断言 `home_query[plan_role]==[baseline_best]` 已逐条迁入）。R57 锚点重指该合并目标，按函数名 `rg` 定位、弃裸行号。详见 `_B_COMPAT_SAFEGUARDS.md §B-6`。


只读核验，grep 回盘当前工作区，确认 6 条 fixed 债 + 复核 R29。
基线对照：committed≡b08162cd；工作树漂移以 `git status --porcelain` 实测为准。

---

## 任务A：6 条「已修」确认

### LB03 — _bool_from_summary 静默吞坏 result_summary（P4 灵魂线，load_bearing=true，owner_pending=true）

**结构性消除：✅ 已确认。**
- 旧符号 `_bool_from_summary`：全仓 grep 零命中（已不存在）。
- 现态 `core/services/scheduler/schedule_plan_identity_builder.py:24` `_parsed_summary_flag_is_true(parsed, key, *, fail_closed=False)`，parse 失败时 `:26 return bool(fail_closed)`；调用处 `:185 _parsed_summary_flag_is_true(summary_parse,"is_simulation",fail_closed=True)`——P4 由静默「安全默认 False（非模拟）」改为 **fail-CLOSED 判模拟**。
- 新增可观测字段 `:233 result_summary_parse_failed=bool(summary_unavailable)`（registry 引 :233-234，盘上 :233 命中，行号微移在容忍内）。
- 守卫测试 `tests/schedule/route_view/test_scheduler_plan_identity_summary_guard.py` 实测 **git status=`A`（已 staged，不再 untracked）**，15502 字节在盘——MEMORY 记的 git clean 删 untracked 风险已被入账消解。

**偏离计划：无（且优于计划）。** verdict 推荐「读边界加非致命完整性标记而非 raise」，现态正落在此方向（fail-closed + parse_failed 标记），未走 verdict 警示的「原地改 loud raise→latest_executable_official_version 全量扫历史一条 legacy 坏行炸全链」可用性放大事故。

**新债/承重削弱：无。** 承重真正落点 `result_status='simulated'` 未被动；fail_closed=True 是收紧非放松。

**残留动作：** 仅缺认账注释——`:24` helper 定义处与 `:185` 调用处零 `#` 注释（grep `我是故意|故意|fail-closed` 均零命中）。需补一行「fail_closed=True 是故意 fail-closed 判模拟，非保守默认 False」。⚠️注释文案勿逐字粘 §90 LB-B4（LB-B4 描述的是治理前 fail-OPEN，与现盘 fail-CLOSED 语义相反）。owner_pending=true：注释文案细节待 owner 裁，暂不分配执行批次。

---

### LB06 — execution-review 页写死 adopted/None 护栏，零注释（P2 承重，load_bearing=true，owner_pending=false）

**结构性保留 + 增强：✅ 已确认。**
- `web/routes/reports_page_support.py` 已重写为 `execution_review_page_context()`（:391）。核心行数据仍硬钉 `"adopted", None`：`:397 page_plan_resolution(...,"adopted",None)` + `:399 page_date_range_or_version_span(...,"adopted",None,...)`——core 行数据承重护栏原样保留，未给 core 加 plan_role/scenario_id 形参（adv_precondition 硬前提 1 守住）。
- 比计划「仅补注释」**更硬**：非 adopted / 带 scenario 的请求经 `:396 execution_review_plan_identity_error(raw_plan_role, scenario_id)` 被显式拦成可见 blocked 报告（`:351 _blocked_execution_review_report` 空行 + `reports_execution_review_context.py:8 blocked_execution_review_plan_resolution` 强制 can_dispatch/can_write_feedback/is_current_executable_official_version=False，标「模拟预览身份」）。
- `web/navigation_context.py:80-82` 的 is_execution_review 强制分支【已删除】——护栏迁到页级（详见 R56/R57）。

**偏离计划：有（结构走向变化，非削弱）。** 计划是「:367/:369 + navigation_context:80-82 补注释」；实盘 navigation_context 强制分支被删、护栏上移到页路由 blocked-override。属高风险结构重定位，但 **fail-CLOSED**（非 adopted→可见 blocked 而非泄漏预览冒充正式）。

**新债/不对称：无新增不对称（反而消除了与兄弟页的方言不一致）。** 注：registry 引 reports_page_support 旧行号 :366/:368 系 off-by-one，新文件已是 :397/:399。

**残留动作：** `:397`/`:399` 上方仍缺逐字「此处故意忽略 request 的 plan_role/scenario_id 是护栏」注释（lb_no_touch 禁区：禁改成从 request 读、禁给 core execution_review() 加形参）。契约由 `tests/operation_execution/test_execution_review_identity_guard.py`（git=`AM`）绑死，下文 R56 列出断言。

---

### R07 — 写后任务卡对 schedule 行缺失静默兜底为「正式采用方案/可写」卡（P4 灵魂线，load_bearing=false）

**结构性消除：✅ 已确认。**
- `core/services/scheduler/resource_dispatch_execution_service.py:142 if schedule is None:` → `:143 raise ValidationError("现场记录对应的排程行不存在，请刷新后重试。", field="schedule_id")`。旧的「返回 plan_identity_label='正式采用方案'、can_write_feedback=True 的伪 adopted 死卡」支路已消除，下游不再返回伪可写卡。
- 写门禁独立强校验仍在：`operation_execution_feedback_service.py:385 raise AppError(ErrorCode.NOT_FOUND, "排程记录不存在，请刷新后重试。")`——证实建卡前 schedule 已在同连接证存在，原 131-141 分支生产不可达，转 raise 不破 happy path。

**偏离计划：有（错误类型 + 文案 + 一致性偏离）。**
- 计划 planned_fix：`raise AppError(ErrorCode.NOT_FOUND, '排程记录不存在，请刷新后重试。', details={'reason':'not_found'})`，对齐 feedback_service.py:365 既有同文案模式，并补 `AppError, ErrorCode` 导入。
- 实盘用 `ValidationError(..., field="schedule_id")`——**错误类**不同（ValidationError vs AppError/NOT_FOUND）、**文案**不同（「现场记录对应的排程行不存在」vs 计划/兄弟门禁的「排程记录不存在」）、**导入未补**（本文件 :5 仍仅 `from core.infrastructure.errors import ValidationError`）。
- 后果：同一文件内 `:185` 已用 ValidationError(field="plan_identity") 表「记录不在当前计划身份」，:143 跟进 ValidationError 在本文件内自洽；但与写门禁 `feedback_service.py:385` 的 AppError/NOT_FOUND 形成**跨文件错误类不对称**——同一「排程行不存在」语义两处两种错误类/两种文案。ValidationError 语义偏轻（暗示「输入校验失败」），NOT_FOUND 更贴「资源不存在」。属语义漂移隐患，非功能 bug。

**新债/承重削弱：无承重（本文件无 LB）。** 灵魂线红线守住（loud raise，非裸删、非加兜底；裸删会落 :147-148 schedule.start_time AttributeError 谎报写失败）。

**残留动作：**（1）owner 裁断错误类是否需统一为 AppError/ErrorCode.NOT_FOUND + 对齐文案，以消跨文件不对称；若改须补 `AppError, ErrorCode` 导入。（2）**缺专项回归**——grep tests/ 对「现场记录对应的排程行不存在」「排程记录不存在」（R07 分支）零命中，需补一条 schedule=None→raise 的回归 PIN 该分支转 raise（现有 `regression_scheduler_candidate_resource_dispatch_contract.py` 仅用 get_execution_context，未覆盖 task_card_for_feedback_context 的该支）。

---

### R56 — navigation_context 的 execution_review 护栏靠 endpoint/path 字面量匹配且零注释（P2 承重，load_bearing=true）

**结构性消除：✅ 已确认（走了计划标注的高风险结构路线而非补注释，但未 fail-open）。**
- `_is_execution_review_request`（字面量匹配）：全仓 grep 零命中，**已删**。
- `web/navigation_context.py` fallback（:73-90）现对 plan_role 仅做 `:79 plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED`（非法 role 兜回 adopted），scenario_id（:80）原样透传——**无 execution_review 专属强制分支**（旧 :80-82 已删）。
- 护栏迁到**页级**（reports_page_support.py `execution_review_page_context`）：非 adopted/scenario 请求经 `execution_review_plan_identity_error`（reports_request_support.py:65）判定，命中即 blocked 报告 + blocked_plan_resolution（can_write_feedback=False / is_current_executable_official_version=False）。
- `web/navigation_context.py` 实测 git=`MM`（工作树漂移），即此结构重定位在场。

**未 fail-open 证明：✅。** `execution_review_plan_identity_error` 逻辑（reports_request_support.py:65）：有 scenario→拦；role 非空且 ≠adopted→拦；返回错误串即触发 blocked。契约测试 `tests/operation_execution/test_execution_review_identity_guard.py`（git=`AM`）实测断言：
- `:59 test_..._direct_candidate_request_is_visible_blocked`：`?plan_role=baseline_best`→「计划和现场实际只复盘正式采用方案」可见 + 无 export links + 无 adopted 续跳链接。
- `:76 test_..._unknown_plan_role_does_not_leak_raw_role`：未知 role 不泄漏 raw（`future_role` 不出现）。
- `:91 test_..._direct_scenario_request_is_visible_blocked`：带 scenario→「模拟预览身份」可见 blocked。
- `:162 test_..._export_rejects_non_formal_identity`：非正式身份 export 直接 400。
即 endpoint/path 字面量匹配脆弱性已不是唯一护栏，护栏锚到「plan_role/scenario_id 值判定 + 页级 blocked」，rename 路由不再静默失效该护栏。

**偏离计划：有（重大）。** 计划 planned_fix_class 明令「P2 承重护栏：仅①补注释②绑契约测试，零删除/统一/透传，严禁因『字面量难看』去重构匹配方式」。实盘**删了 _is_execution_review_request 与字面量匹配本体**，把护栏整体重定位到页级——直接违反 lb_no_touch「只补注释」字面要求。但实质护栏未削弱反增强（页级值判定 + 契约测试比字面量匹配更稳），未 fail-open。属「修法走了红线外的结构路线但结果安全」——需 owner 认账此偏离是否接受（load_bearing=true 的债被结构改动，按铁律3本应只补注释）。

**新债：** 字面量匹配脆弱性已消除；但护栏现依赖「页级 identity_error 判定 + 契约测试」两支，任一被未来重构削弱即失护栏——契约测试 `regression_execution_review_identity_guardrail.py` 必须 git add 入账（实测已 `AM` staged，OK）。

**残留动作：**（1）owner 认账「load_bearing 债走结构重定位而非补注释」是否接受为既成事实。（2）确认 navigation_context.py / reports_page_support.py / reports_execution_review_context.py / 契约测试随同一提交入账（当前 MM/M/新文件/AM 混合态）。

---

### R57 — 导航上下文双构建路径：fallback 直信 raw plan_role/scenario_id（P3，load_bearing=false）

**结构性消除：✅ 已确认（有意分歧由契约钉死）。**
- `web/navigation_context.py:69-72` override 分支先返回（经真实 plan_resolution 的 g 上 `_navigation_context_override`）；fallback（:73-90）对非 adopted 仍原样透传 `_request_arg('plan_role')`/`('scenario_id')`——双路径有意分歧保留。
- 安全网：fallback 从不设 guard 字段（grep navigation_context.py 对 is_current_executable_official_version/is_official_plan 零命中），故 `_is_formal_adopted_context→False`→execution-review 入口在 fallback 页恒 disabled。
- 由 `tests/regression_aps_workbench_flow_contract.py`（git=`A`）锁死：`:335 test_workbench_non_adopted_review_entry_is_disabled_and_plain_chinese` 实测 `:346 'aria-disabled="true"' in html` + `:347「计划和现场实际只复盘正式采用方案」` + `:353 home_query["plan_role"]==["baseline_best"]`（fallback 原样透传是**有意**的，被 PIN）。

**未 fail-open 证明：✅。** fallback 透传 raw plan_role 不等于放行——透传后因缺 guard 字段→入口 disabled（双重独立兜底，与 R56 页级 blocked 互不依赖）。

**偏离计划：基本无（落在计划的降级修法）。** planned_fix_class 给两条路：(A) fallback 收敛经 query_service 求证 plan_role/scenario_id；(B) 若收敛破透传断言则降级为「补注释钉双路径有意分歧 + 绑契约」。实盘走 (B) 降级路线——透传保留 + flow-contract 钉死，符合计划兜底分支。

**新债/承重削弱：无（load_bearing=false）。** 共享行 navigation_context.py:80-82 的旧强制分支已随 R56 删除，R57 fallback 现是纯透传 + 缺-guard-字段兜底，不再有「误删 :80-82 护栏」风险（该护栏已不在此处）。

**残留动作：** 仅缺注释钉双路径有意分歧（override 经 plan_resolution / fallback 原样透传靠缺-guard-字段兜底 disabled 入口）。契约测试已绑（flow-contract git=`A` 入账）。

---

### R16 — _REPORTED_STATUS_BY_EVENT_TYPE 死兜底表 + _current_status 的 or 右支（P6，load_bearing=false）

**结构性消除：✅ 已确认（与计划完全一致）。**
- `_REPORTED_STATUS_BY_EVENT_TYPE`：全仓 grep 零命中，**表已删**。
- `data/repositories/operation_execution_state_builder.py:66 def _current_status(...)` → `:67 return last_event.reported_status`，**or 右支已去**。
- 孤儿导入清理：`:7-11` 仅留 EXECUTION_EVENT_{EXCEPTION,FINISH,PAUSE,RESUME,START} 五个活用导入（:97/:128/:132-134/:242-243 仍用）；五个 EXECUTION_STATUS_* 孤儿导入已全清——与 planned_fix「纯删表 + 简化 :77 + 清孤儿、不加默认」**逐条吻合**。
- 灵魂线红线守住：未在 :67 另加 `or '某默认值'` 防御（schema CHECK + NOT NULL 已是 loud 护栏，纯删即可）。

**新债/承重削弱：无。** 同文件 R15（B06，datetime 收口）共存验证：`:3 from datetime import datetime` + `:37 _parse_time` 仍在（:49/:50 活用），R16 删表未波及 R15 区域，跨桶同文件串行约束未被破坏。

**残留动作：无。** 纯删 P6 死代码，零注释需求，零契约需求（contract_topology_tests=「无」）。已彻底闭环。

---

## 任务B：R29 误标复核

**当前标注：`status_2026_06_05 = not_applicable`，owner_pending=true。**

**复核三点全部坐实「误标」：**

1. **权威 CSV 不在盘（授权链断裂）：** `test -d .codestable/refactors/2026-06-01-test-gate-cleanup` → **DIR ABSENT**；`L3_verdicts.csv` → **CSV ABSENT**。refactors/ 下实有 6 个目录（2026-04-30-techdebt-phase4/phase5、05-07-perf-cache、05-11-quality-gate、05-21-non-win7、05-29-resource-dispatch-js），**无** test-gate-cleanup。报告据以判 KEEP/high 的 `L3_verdicts.csv:174` 仅在审计报告自引用，无法回盘——这恰是 owner-pending 的成因，不是 not_applicable 的依据。

2. **债本体仍在场（结构未消除）：** `core/services/common/number_utils.py` 实测 44 行，`:14/:23 parse_finite_float` + `:31/:40 parse_finite_int` 仍是**全量函数体 delegation-facade**（真有 overload + 函数体，delegate 到 `core.shared.strict_parse` 的 parse_optional/required_*）；4 兄弟 compat_parse/value_policies/degradation/field_parse **全 defs=0**（纯 re-export 壳）。半截迁移的不对称客观存在，债没被消除也没被裁掉。
   - 注：registry current_evidence 说「delegate 到 core/shared/number_utils.py」，实盘 delegate 目标是 `core.shared.strict_parse`（number_utils.py 确存在但本 facade 的 import 指向 strict_parse）；不影响「全量 facade vs 薄壳不对称」结论，仅 delegate 目标模块名需校正。

3. **facade 测试仍在：** `tests/models_domain/test_number_utils_facade_delegates_strict_parse.py` 在盘——薄壳化会击穿其 monkeypatch（与 verdict=depends 一致，需先重写为身份测试）。

**R29 纠正建议：** `not_applicable` → **`planned`（owner-pending 待裁）**。理由：not_applicable 表「债不成立/不适用」，但债客观成立（半截迁移不对称在场）、verdict=depends（非安全单边收口）、且 KEEP vs 收敛的授权 CSV 已不在盘——属「待 owner 裁断该保留 delegation-facade 还是补齐迁移」，正是 planned + owner_pending 的语义，绝非 not_applicable。owner_pending=true 已正确置位，仅 status 字段需从 not_applicable 改 planned。给 owner 两条路：(A) KEEP——补一行「本模块刻意保留 delegation-facade 形态」显性注释；(B) 薄壳化——必先把 facade-delegation monkeypatch 测试重写为 `*_reexports_shared_identity` 身份测试再动，否则测试红。任一路均不在本会话写生产代码（铁律7）。

---

## 返回结论（逐条）

LB03: 确认已修（P4 fail-closed + 可观测标记结构性消除，优于计划，守卫测试已 staged）| 残留动作: :24/:185 补「fail_closed=True 是故意」认账注释（勿粘 §90 LB-B4 反向文案），owner_pending 待裁文案。
LB06: 确认已修（core 行数据仍硬钉 adopted/None，非 adopted 经 identity_error 拦成可见 blocked，比计划更硬，未 fail-open）| 残留动作: :397/:399 补「故意忽略 request、是护栏」逐字注释；禁改成从 request 读 / 禁给 core 加形参。
R07: 确认已修（schedule is None 改 loud raise，伪 adopted 可写卡支路消除，灵魂线红线守住）| 残留动作: ⚠偏离——用 ValidationError(field=schedule_id) 而非计划 AppError/ErrorCode.NOT_FOUND，文案亦异，与写门禁 feedback_service.py:385 跨文件错误类不对称（owner 裁是否统一+补 AppError/ErrorCode 导入）；缺 schedule=None→raise 专项回归测试。
R56: 确认已修（_is_execution_review_request 字面量匹配本体已删，护栏重定位到页级 identity_error+blocked，契约 regression_execution_review_identity_guardrail 钉死非 adopted/scenario 可见 blocked，未 fail-open）| 残留动作: ⚠偏离——load_bearing 债走结构重定位而非铁律3「只补注释」，需 owner 认账此偏离；确认四改动文件随同一提交入账。
R57: 确认已修（双路径有意分歧保留，fallback 透传 raw 但缺 guard 字段→入口恒 disabled 兜底，flow-contract :335 钉死，落在计划降级路线 B，未 fail-open）| 残留动作: 仅补注释钉双路径有意分歧；契约已绑入账。
R16: 确认已修（死兜底表全仓零命中，_current_status :67 简化为 return reported_status，or 右支去，五个 EXECUTION_STATUS_* 孤儿导入清净，与计划逐条吻合，未加默认防御）| 残留动作: 无，已彻底闭环。

R29: 纠正建议——not_applicable 实为误标，应改 planned（owner-pending 待裁）。权威 CSV .codestable/refactors/2026-06-01-test-gate-cleanup 整目录实测 ABSENT；common/number_utils.py 仍全量函数体 delegation-facade（44 行，delegate 到 core.shared.strict_parse）、4 兄弟全 defs=0 薄壳——半截迁移不对称客观在场，verdict=depends，授权链断裂需 owner 拍 KEEP(补显性注释) vs 收敛(先重写 facade 测试为身份测试)。owner_pending=true 已正确，仅 status 字段 not_applicable→planned。本会话不写生产代码。

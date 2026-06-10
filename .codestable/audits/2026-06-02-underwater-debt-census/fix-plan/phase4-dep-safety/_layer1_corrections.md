# Layer1 关键校正（喂给 Layer2/3/4 的种子；均经 dossier + 第二双眼睛 verify 双核）

> 来源：workflow ww7k5dwir（149 agent）。承重误删风险=无（全部承重档案守住「只补注释/收口+parity」）。
> 下列为「与旧 MASTER-PLAN / registry / 报告冲突且经当前代码回盘确认」的项，是本轮相对旧 fix-plan 的增量与纠偏。

## A. 修法被实质推翻（必须改写 MASTER-PLAN 对应批次）

- **R09（重大）**：规范收口点**已存在**=`core/models/operation_execution_scope.py:9 parse_positive_execution_int`（执行重构新建，bool/非数字/<=0 一律 loud raise）。3 个新文件已正确收口（context.py:28 / scope_read.py:21 / tokens.py:13）。**「唯一批准新建 parse_optional_positive_int」前提作废**——收口点已建好。剩 **2 个 baseline 旧 `_positive_int` 内联副本未收编**：`web/viewmodels/scheduler_resource_dispatch_execution.py:33` + `core/services/scheduler/resource_dispatch_execution_service.py:24`。**收编须分两路 parity**：C 路（已收口）对 float/bool 严格→None（5.9→None / True→None），A/B 旧内联宽松（5.9→5 / True→1）；直接把 A/B 收口到收口点会**静默放宽**语义，须先补 parity 钉死差异、owner 裁两种语义取哪个。「第 4 抄」担心被否定（context 文件 wrap 了收口点=合规）。
- **R13**：死字段 last_event_schedule_version/id 被 **3 个测试读活**（reschedule:196 ==1、scope_read_contract:108/190/220）。planned_fix 步骤 3/4 作废。**解除 R13↔R18 强耦合**（event_repo 方法属 R18，R13 是 provider 死字段）。删字段须先改 3 测试 → 升级 owner 二次确认删/留。
- **R18**：registry 全面失真（scope 重构推翻 P6「孤儿」叙事，planned_fix 第(2)(3)步无对象）。callgraph 零入边证生产零调=可删；stub 现 raise，foundation 测试在 :365 断言 raise（非 :172）。
- **R17**：文件已重构，删除位点过时——改删 `:81` 推导式项（非旧 :64 死键两文件）。
- **R03**：`_baseline_missing_or_failed(:267 return True)` 使 **missing 态生产可达**，只 failed 态不可达。**推翻「全死分支」**——须四态 parity；missing 态保留+补不可达注释 vs failed 态收敛，owner 裁。
- **R34**：纯删死方法（非「收敛到 column_name」）。repoint 目标 `get_plan_time_span_for_resolution` **存在**（旧锚 schedule_plan_query_service.py:210；R23 落后现盘为 :206，执行按符号重 rg）——dossier 误判「不存在」，verify 已纠正。R05→R34 降为软约束（不同符号不同文件）。
- **R15**：实际收口去 `parse_operation_event_time`（非 planned 钉的 strict_parse）；`execution_fact_provider.py:85-95` 仍基线未收口（坏值 return None 静默=真 P4 残留，收口须 loud/可观测；区分「空值→None」与「坏值→报错」）。
- **R44**：import 来源实为 `schedule_plan_query_service`（非 view_context）；gantt_plan_query 在 core（非 web）；原报告「web 多兜底」方向反了（core 更防御 None）。
- **R22**：evidence_contract 22 键 superset 抓不到 drift，须升 **24 键 exact** parity。
- **R24**：empty_diagnostic_sections 还在 :83，须**单行剪除非整删**（:82 混合用例）。
- **R01**：删 :67 死簇后 `typing:5 Iterator` 成孤儿 import 须同删。

## B. 干扰图边/簇校正（喂给 Layer2 重建图——这些边要删/改）

- **假边 / 误标 same_file（删边）**：
  - R02↔R25（不同文件：R02=schedule_graph_dispatch_context.py，R25=ready_queue.py；downstream「删 dispatch→matching 边」是懒 import 非模块级）
  - R45↔{LB07,R33,R51}（schedule_params.py 是 core/algorithms/greedy/ 同目录他文件，非 R45 的 config_adapter.py，零碰撞）
  - R20↔{R08,R09,R12}（R20=operation_execution_labels 在 context.py:11，不碰 ..._execution.py/gantt_tasks，三边全假）
  - R32↔R15（os.replace 同名异物：R32=backup os.replace，R15=execution_fact_provider.py:89 str.replace，纯假边）
  - LB04↔{LB07,R33}（不同 primary_file：boolean_normalize.py vs snapshot.py/compat_parse.py；core/algorithms 经 number_utils 引用为假，algorithms 零消费）
  - R26↔R43（scheduler_config.py 是 web/routes/ 非 core/，basename 假碰撞）
  - config_snapshot.py R26↔R71 已知假碰撞（顶层 shim vs config/config_snapshot.py 深实现，不同物理文件，不串行化）
- **解耦**：R13↔R18 强耦合解除。
- **降级**：R05→R34 硬依赖→软约束（保批次先后零成本，非「丢谓词」式硬阻塞）。

## C. 执行重构新引入债（纳入清单，均 owner_pending；本轮相对旧 80 条的增量）

- **N1**：`web/routes/domains/scheduler/scheduler_resource_dispatch_execution_context.py:129-130` `_identity_allows_query_membership_check` 从五连合取收敛成单字段 `can_write_feedback`。**行为安全**（can_write_feedback 经 `_can_write_feedback:89` + `_is_official_plan:70-84` 严格蕴含 adopted+schedule+无 scenario），但承重契约从显式自证退化成隐式远端依赖，**零注释**=新承重不对称（失忆债）。修法=补「我是故意的」注释（钉 can_write_feedback⇒adopted-only 来源链）+绑 parity；禁区 `_can_write_feedback:89-110`/`_is_official_plan:70-84`/本闸:129-130，禁放宽成 or、禁加 preview 旁路。load_bearing 倾向 true。
- **N2**：`core/models/operation_execution_event.py:156-163` `_event_id_for_revision` 末位 `return 0` sentinel（非末位缺 id 已 loud raise）。新承重逻辑无注释；该 0 进 previous_event_id 用于下游 revision 拼接。修法=补注释（末位无后继、其 id 不参与下游拼接故允许 0）+绑「非末位缺 id 必抛错」契约；禁删 `if index<total: raise`。
- **R54 升级为 5 套手维列表**（非报告 3 套 / registry 4 套）：① `dashboard_workbench_context.py:8`（新建）② `scheduler_navigation_publish.py:12` ③ `scheduler_resource_dispatch.py:64` ④ `scheduler_reports_workbench.py:36` ⑤ `scheduler_gantt_task_detail.py:8`。**双分叉**：源键分叉（③同名键 vs ④别名键 requested_role/selected_role/is_official）+ 字段集分叉（④缺 plan_identity_error/blocking_error/blocking_scope 三阻断态字段，走 `reports_execution_review_context.py` overrides 另一注入路径）。收口收到**已存在的** `core/models/schedule_plan_identity.py`（PlanIdentity.to_dict 是真相源），别名映射各 surface 局部保留，**禁统一键名**（改行为）、禁把 reports 两条注入路径并一条（丢阻断态）。
- 真 P4 残留确认（非新增）：`execution_fact_provider.py:85-95`（R15 旧债）。其余传闻「12 处新 except / ≥4 处 return None」经核**几乎全合规**（可观测降级/loud 转译/受控 sentinel/旧债 extract-method 搬家）。

## D. 已修但偏离，需 owner 认账（不是债，是流程/口径问题）

- **R56（load_bearing）**：走高风险结构路线删 `_is_execution_review_request` 字面量匹配本体（违铁律 3「承重只补注释」），护栏重定位到页级 identity_error+blocked，**未 fail-open**，契约 `regression_execution_review_identity_guardrail` 钉死。owner 须认账此偏离 + 确认 navigation_context/reports_page_support/reports_execution_review_context/契约测试同提交入账。
- **R07**：用 `ValidationError(field=schedule_id)` 而非计划 `AppError/ErrorCode.NOT_FOUND`，与写门禁 `feedback_service.py:385` 跨文件错误类不对称；缺 schedule=None→raise 专项回归。owner 裁是否统一错误类（改则补 AppError/ErrorCode 导入）。
- **LB03 / LB06**：仅缺认账注释（LB03 勿粘 §90 LB-B4 反向文案——LB-B4 描述治理前 fail-OPEN，现盘已 fail-CLOSED）。

## E. fixed 态（DAG 前置已完成，重算批次起点）

LB03,LB06,R07,R16,R56,R57 已结构性消除（LB03/LB06 优于计划=更硬；R56 偏离铁律 3；R07 偏离错误类）。**R29 误标 → planned(owner-pending)**（权威 CSV 整目录 ABSENT，common/number_utils.py 仍全量 delegation-facade、4 兄弟全薄壳，半截迁移不对称客观在场）。

## F. verify 抓出的 dossier 自身错误（最终计划以 verify 为准）

- **R43**：dossier 把真相源正确的 roadmap 延期行 **522 反向污染成 521**——以 **522** 为准（verify 已纠）。
- **R47**：parity 测试方法名后缀应为 `_emit_blank_required`（dossier 误写 `_emit_ln`），测试真实存在 @:210/:107。
- **R54**：键数 dossier 计 L1=13/L4=12，verify 纠为 L1=12/L4=16（L2/L4 逐字相同）——不撼 split 与承重结论。
- 其余 R71/R33/R25/R32/R70 为措辞瑕疵，修法结论不变。

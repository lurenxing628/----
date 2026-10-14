# B阶段独立审查返修指令

主对话负责本稿、产品取舍、代码与真实操作验收；B对话 `01a139e1-02ee-7cd0-bebd-ba53c0673b72` 负责实施、相关验证和交接。基线为已推送的 `efe047d3b3816db29f0718ba5999aeeb199669bf`。以下均为独立审查确认并由主对话亲读实际源码后确定的修法。

沿用用户授权：Windows相关测试全部 `deferred_by_user`，20,000工序4／6／8候选2秒目标由C收口。Git由主对话执行；保留README原改动和主调度记录的归属。下列已确定项可立即并行实施，共享文件明确指定一位写入者。新发现先报触发、影响、源码和最小证据，主对话追加具体指令。

## B1 未设置交期的计划导出

事实：`core/services/workbench/plan/export.py:28,47` 对共同交付投影的合法 `not_applicable` 状态缺映射。正式、候选、试调共同导出遇到未填交期批次会抛 `KeyError`，整份CSV／XLSX失败。

- 在该共同导出器 `DELIVERY_RISKS` 增加 `not_applicable: 未设置交期`，保持其他状态的明确映射。沿用共同交付投影，未知日期仍显示已有未知状态。
- 不改交付计算、原任务选择、空值编码及CSV／XLSX写入机制，不引入默认值掩盖未识别枚举。
- 扩展已有 `test_unspecified_candidate_analysis_and_adopted_plan_share_projection` 的已采用计划读取结果，实际写CSV和XLSX，核对完整行数、中文状态、完工时间、交期原值以及截止／拖期空值。已有候选与试调的共同投影用例复用，不新增三入口乘两格式的参数矩阵。

## B2 值班台比较的批次来源统一

事实：`DashboardWorkspace.jsx:125–126` 提供新的问题批次，`DashboardCandidates.jsx:28,52–53` 请求仍读取保留的旧 `choice.batch_ref`，`:98` 说明却读取新prop。实际DC-01→返回分析→DC-02→比较会显示新批次说明和旧批次结果。

- `DashboardCandidates` 的组件选择状态只保留排产、候选和时间范围。`issueBatchRef` 是问题批次范围唯一来源；从初始比较context校验后移除 `batch_ref`，不在本地再保存一份问题批次状态。
- 每次render从上述选择状态与当前 `issueBatchRef` 派生完整比较context。问题批次非空时加入 `batch_ref`，为空时省略；签名、workspace请求、后续baseline／comparison请求、`onState`保存和说明全部使用这同一份派生context。现有AbortController随签名切换，旧结果由签名隔离；无需新增同步effect、重试或缓存。
- 切换排产／候选／时间范围的操作只更新其拥有的选择字段。当前排产、候选和范围在DC-01→DC-02时保留，只有问题批次改变。取消问题范围后读取整次排产范围。通用候选目录的逐批选中仍由父组件 `analysisBatch` 负责高亮，不把高亮变成隐含全局过滤。
- `DashboardWorkspace` 继续持有当前分析批次和条目来源。页面恢复优先使用已经保存的 `analysis_batch_ref`；来自条目详情的批次沿原条目恢复链获取。比较context的 `batch_ref` 仅是保存的请求内容，不重新成为第二个问题批次来源。
- 在现有值班台/已构建甘特JS harness中补一条DC-01→DC-02并返回的行为回归：请求batch_ref、可见说明和最终批次结果一致，已有候选/时间选择保留；覆盖一个先返回的旧请求不会覆盖新结果。复用现有异步机制测试，避免新建测试框架。构建后交主对话用58240同库实页验收这条只读路径。

## B3 跨夜班段保留原班次日期

事实：`core/services/workbench/facts/resource_projection.py:426–433` 已按 `policy_date` 分组，随后却用裁剪后 `first.date()` 覆盖。9月9日22:00—9月10日06:00的夜班，窗口从10日00:00开始时错误标成10日；6小时容量数值本身正确。

- `ResourceTaskIndex.periods(grain="shift")` 遍历 `groups.items()`，将原分组键写入bounds的group，输出 `date` / `group_key` 保持9月9日。`start/end`继续为所选窗口内真实交集，`bucket_key`继续按原有裁剪时刻规则产生。
- 休息／未知占位仍按所在自然日；日／小时／周粒度及所有占用、容量、冲突计算保持。无需新版本号、第二套日期字段或重算历史。
- 使用已有 `_continuations`：左侧原班次日期在当前列范围之外时，10日列显示“班段延续”，打开的仍是该夜班尾段资料；`resource-days`和导出都保留9日归属。不要把这条补成10日新班次，也不新增窗口之外的容量。
- 扩展现有 `test_partial_night_window_splits_days_and_preserves_overlap_identity` 资源API用例的已有夜班数据，将range_start裁到10日零点，核对归属9日、可排6小时、热力图延续入口、详情和一份资源班次原始导出。既有完整夜班和跨自然日数值断言保留并复用。只需一个该缺口场景，不增加设备×人员×格式矩阵。

## B4 完整计划末端零工时导出说明

事实：`PlanWorkspace.jsx` 已按 `data.scope.range_start === null && data.plan_span.end_inclusive === true` 正确说明完整计划末端零工时；`PlanExportUI.jsx:40`和 `plan/export.py:20,40`仍无条件写“不含结束”。数据包含这些工序，说明与实际导出相反。

- 前端将现有计划范围说明收敛到 `PlanGanttModel` 的一个小函数，`PlanWorkspace`和`PlanExportUI`共同使用。完整计划含末端点：明确“包含末端零工时工序”；显式起止筛选和普通完整范围：明确“不含结束时刻”；完整计划只有一个时刻：沿用“计划时刻”的清楚表达。
- 后端导出用同样两个已有事实决定“时间计算方式”单元格：完整末端点为“包含末端零工时工序”，其余为“含起点，不含结束时刻”。列名将“范围终点（不含）”改为中性的“范围终点”，不让列名否定单元格规则；起点列保持，数量/列序/任务行保持。
- API的scope和plan_span契约保持，完整计划查询不增加微秒或伪造结束点；用户显式半开窗口仍排除终点事件。`web/bootstrap/sample_exercise.py`已经导入共同 `HEADERS/export_rows`，随共同导出器自然使用新表头，不另写补偿。
- B1同一导出写入者负责此项。用已有末端点计划夹具核对完整导出含点且说明一致、相同显式半开窗口不含末端点；前端现有JS harness补范围说明的这组真实差异，不为纯中文函数独立建测试文件。

## B5 旧安排选择的返回上下文

事实：`PlanWorkspace.jsx:40–48`保存选择只记录task_ref，恢复只查 `data.tasks`；从正式计划的“查看原安排”离开再返回，会报“要恢复的工序不在当前范围内”。旧安排永久任务编号属于baseline，不能改指当前同工序安排。

- 保存当前选择时增加一个明确侧别 `selected_task_side`，值为 `current` 或 `before`；与 `selected_task_ref`一起从实际 `chosen` 派生。上下文未带侧别的已有记录按 `current` 解释。
- 恢复当前侧仍查 `data.tasks`；恢复before侧从当前已读取的 `data.projections.baseline.items[].before`按同一个task_ref查找，不按业务工序号猜配。恢复后 `selected.before=true`，详情继续显示原安排。原安排在当前范围外时仍可恢复其已有详情，自动甘特定位只对范围内的before条目执行。
- 原安排确实不再存在时保持明确的原选择不可恢复说明。仅消费首次成功读取的恢复目标；后续选计划、改范围、手动选工序和清除选择按现有重置规则一起清理ref及side。
- `remembered`重建时同时移除旧ref和旧side，防止选择消失后遗留；`openResource`若明确跳到当前任务，也明确写current侧，若没有任务则清除两项。其他跨页入口仍用它们已明确的当前侧，避免继承before侧别。
- 扩展已有 `gantt_current_runtime.cjs` 的正式计划返回测试：选择baseline旧安排→保存页面context→重新挂载→保持同一旧task_ref/原安排详情；并复用当前安排恢复的已有断言。无需查询新API或补写数据库。

## B6 全量测试缓存输入范围

问题已确认：`tools/long_gate_manifest.py` 的 `full_test_debt` 漏追踪CJS、前端源文件、编译脚本和部分实际夹具，隔离复算出现内容已改成失败脚本仍复用旧通过。主对话已亲读实际消费者与缓存入口，以下改法立即实施。

- 在 `ENTRY_FULL_TEST_DEBT` 的 `input_scopes` 追加下表，只替换已有单独的 `tests/migration_db/fixtures/schema-v9.sql` 为统一SQL夹具范围；保留其余已有范围。匹配实际内容仍走现有fingerprint，不改缓存schema或行为。

| 追加范围 | 实际读取职责 |
| --- | --- |
| `tests/**/*.cjs` | Python的Node契约、probe和共享harness实际执行/加载的脚本 |
| `tests/**/fixtures/*.sql` | 迁移库及冻结业务归档，包含现有v9和其他版本 |
| `tests/**/fixtures/*.json` | 真实基准响应等静态夹具 |
| `frontend/workbench/app/**/*.js`、`frontend/workbench/app/**/*.jsx` | Node契约直接读取/编译的前端源文件 |
| `frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js` | 现有契约指定的仓内离线Babel |
| `scripts/workbench/*.cjs` | `compile.cjs`及其`ds-projection.cjs`依赖 |
| `docs/**/*.html`、`docs/**/*.css`、`docs/**/*.js` | 离线页面检查实际遍历的三种文本后缀；md已覆盖 |
| `tests/portable_sample/*.ps1`、`packaging/win7/*.ps1`、`packaging/win7/*.cmd` | 已有Windows入口和测试harness的真实执行期输入，本轮仅登记内容，执行仍延期 |

- 收集阶段单独补真实依赖：`ENTRY_PYTEST_COLLECT_ALL.config_scopes` 增加 `开发文档/技术债务治理台账.md`，`tool_scopes`增加 `tools/quality_gate_ledger.py`。依据为 `tests/conftest.py:34`→`active_xfail_entries_by_nodeid`→`load_ledger(required=True)`；收集时已实际解析并校验台账。CJS、前端及执行期夹具无需一并加入collect。
- 当前维护测试未找到读取 `scripts/workbench/build-order.json` 或运行build.py的证据；根目录也没有npm锁文件，故不凭空扩充。已有静态产品产物仍由 `static/**/*`覆盖。local-only历史脚本保持原Git和执行归属；新增内容观察不把它们加入测试入口。
- 在 `tools/host_tests/test_long_gate_content.py`沿现有临时目录/原内容比较方式补一条实质回归：从真实manifest取得entry，在临时树先保存有效结果，修改代表性CJS、JSX、SQL/JSON夹具和编译依赖后必须失效；新增/修改`__pycache__/*.pyc`保持复用；台账改变使collect entry失效。可在一个测试函数内按输入职责逐项改动并恢复，不冻结登记顺序/总数量，不新增缓存验证框架。

禁止直接改成 `tests/**/*`或`scripts/workbench/**/*`：当前fingerprint会把glob的文件系统结果与Git来源合并，忽略规则不能排除glob命中的 `__pycache__`；这会产生与被测内容无关的反复失效。保留原内容比较和现有缓存路径，不新增摘要、哈希或依赖分析框架。

## B7 正式来源试调的完整工序范围

事实：`trial/preparation.py:_contexts`只为候选capture补未安排工序，`trial/projection.py:_unplanned`在正式来源缺少dispositions时直接返回空；同一草稿的交付已保留待料1道，准备需求却显示0／not_applicable且未安排列表为空。正式来源的完整批次、待料批次和工序已经保存在admission事实中，现有`_delivery_origin`使用这些内容。

- 将 `_delivery_origin` 的纯来源解析移到 `trial/origin.py`，由交付、准备上下文和未安排清单共同使用。候选来源仍从保存capture的input范围、原操作和dispositions读取；正式来源从本草稿admission中的原批次、完整BatchOperations、永久身份以及原待料证据读取。既有全批待料补入逻辑和旧待料证据读取路径一并迁移，删除旧私有重复实现。
- 提供共同 `operation_contexts(rows, admission)`：以共同来源中的批次及全部工序建立上下文，已安排行绑定原row；其余保留永久operation_ref、batch_ref、原operation、原execution（有则用）、arranged=false和真实deferred状态。候选永久身份来自GenerationFacts，正式永久身份来自admission保存的WorkbenchPlanSourceRefs；不查询当前表补齐历史，也不制造任务行。
- `preparation_projection` 对这份完整上下文调用现有 `project_operation_effort` / `preparation_summary`。原runtime需求存在则照原记录计算；缺失则保留未知/缺项及已知小计。待料工序属于deferred分组，普通未安排工序属于unplanned；不把缺失需求转换为0或不适用，不从几何跨度反推需求。
- `_unplanned`使用同一上下文的arranged=false项。候选继续保留原disposition的status及前序字段；正式条目使用保存工序的实际status、seq、piece_id和永久身份，候选专属且未记录的处置信息省略，不猜造前序。原因统一明确为“这道工序在基础方案中因待料暂缓安排。”或“这道工序在基础方案中没有安排。”。`scope_complete`继续直接取未安排清单是否为空。
- 草稿一次投影可将已建上下文传给准备和未安排消费者；其他已存在的准备调用从共同函数读取。将正式和候选两条来源差异留在origin内，不在三个下游分别补正式特判。
- `WorkbenchTrialService.scenario` 在原草稿来源存在时，用 `scenario_rows(saved, rows)`、原admission和保存的operation_effort重新投影准备/未安排清单及scope_complete，即使旧保存结果已有preparation_common也如此；保持已保存任务、时间、身份和原数据库JSON不变。原草稿来源缺失时沿用既有来源缺项行为，不用当前库重建旧工序。
- 扩展已有 `test_candidate_trial_retains_explicit_material_deferral_from_run_capture`：同一已采用正式来源的草稿，交付待料数、未安排永久身份和准备deferred需求一致；缺runtime时显示未知；保存再读取仍一致。已有 `test_trial_includes_selected_batch_with_only_material_deferred_operations`和普通未安排工序用例复用，补其缺少的准备/列表核对，保留创建后当前工艺变化不改历史范围的断言。不创建新样例库或额外排列矩阵。

### B7历史读取接线补充

主对话已进一步亲读`history/reading.py:_trial`、`conditions_source.py:_trial_unplanned`和`metrics.py:_trial`。历史读取必须继续保留真正的原始saved/head/rows给采用审计、source_state和快照使用；不要把场景页面重新投影结果换进原始packet，也不要让load_saved_scenario调用页面服务。

- `ConditionSource._trial_unplanned`改为接收完整admission，使用共同 `operation_contexts(self.trial_rows, admission)`的工序集合决定要补入的未安排行，替换“旧saved.unplanned_operations + dispositions + deferred_ids”的独立集合拼装。已安排操作仍取`rows.original`；新增操作和批次仍按当前方法既有的source capture或head.admission.facts建立实际来源路径、original_archive和calendar。这样普通未安排与整批待料都进入同一范围。
- `history.metrics._trial`的准备已经调用preparation_projection，会随B7自然使用完整范围；完成度使用修正后的ConditionSource.operations与共同origin的deferred依据。继续保留project_completion_scope的一致性核对，删除被共同范围替代的重复补集，不从当前表或旧汇总数字猜造成员。无head时现有“保存明细与数量能否互证”的未知规则保持。
- 指标来源路径同步实际依据：有head时应排/待料/普通未安排计数来源指向`head.admission`，已安排计数指向`saved.tasks`；其余已有指标来源路径保持。ConditionSource逐工序路径必须能定位到原capture/admission的实际行。
- 扩展现有 `test_shared_resource_window_uses_saved_capacity_and_keeps_missing_capacity_unknown`末尾已验证packet的纯适配探针：将一份有head、正式来源、普通未安排的旧saved.unplanned_operations置空，仍从admission恢复准确工序集合和计数、未知需求；核对该工序的来源路径指向原admission。与已有无head且空清单时保持未知的断言并列即可，不新增历史fixture或重新生成原归档。

### B7受保护原安排补充

`facts/candidate_projection.py:103`明确允许选定批次之外保留受保护的baseline行；当前`operation_contexts`只遍历delivery的选定批次，会丢掉这些已有任务的上下文，使`apply_preparation`按原工序读取时抛KeyError。共同工序范围应保留全部原安排行，再补本次来源范围中的未安排工序。

- 先遍历全部原始`rows`，用每行`operation_ref`建立context，直接保留该行`original.operation`、`original.execution`、`original.batch_ref`、`original.batch`和`row`，标记`arranged=true`；deferred按共同来源集合判断。已有任务的事实及批次不被capture选定范围过滤或覆盖。
- 再遍历`delivery_origin`返回的批次/全部工序，仅为result中缺少的永久工序建立`arranged=false`上下文，并沿用原来源的operation、execution、disposition及deferred。disposition可按永久工序统一附加；不要将受保护原行误报为未安排。
- `delivery_origin`自身的选定批次范围保持，交付范围没有因此扩大。准备处理所有真实原行，未安排清单只消费新增的缺行工序。
- 复用`test_trial_effort_projection.py`已有保留原任务的用例，补一份最小纯来源探针，验证选定范围外原行仍在contexts且保持原事实、准备投影可读取全部原行、未安排清单只含真正缺行。已有待料/历史原件无需重跑整套矩阵。

### B7保存归档范围补充

主对话已亲读`facts/trial_scenario_archive.py:73–82`：合法待料范围仅从候选dispositions解析，正式来源真实保存为`scope_complete=false`后被归档读取拒绝。保存读取和采用继续共用原有范围校验，范围依据统一到同一immutable来源。

- 将本轮新增的纯来源模块从`trial/origin.py`移至`facts/trial_origin.py`，保留`delivery_origin`和`operation_contexts`的实现及单一职责；更新trial/history消费者。该模块只依赖models及facts已有纯解析工具；`facts/trial_scenario_archive.py`从同层导入，避免facts反向依赖trial。
- `_material_stage_scope`用`operation_contexts(originals, admission)`获得完整来源，`pending`为其中`arranged=false`且`deferred=true`的永久工序集合。合法条件仍要求存在待料缺行、saved.scope_complete严格为false、saved.unplanned_operations条数与唯一ref集合精确等于pending、原安排ref集合精确等于完整contexts减pending。存在普通未安排工序时继续拒绝采用，重复/漏项也继续拒绝。
- 不改`full`旧完整归档路径、task数量/身份、receipt原内容互证、保存JSON或采用事务。移除archive中已被共同来源取代的material_deferred_ids独立解析。
- 扩展已有正式待料试调用例：保留旧空清单归档读取探针；同一fixture另建当前真实投影的正式草稿并保存，直接读取saved scenario和原采用预检路径应走过范围校验。精确核对pending永久ref与安排总数；复用既有普通未安排拒绝用例，不另建数据库或矩阵。

### B7纯待料证据依赖补充

主对话复核最终新增接线发现模块环：`delivery_completeness → trial_scenario_archive → trial_origin → delivery_completeness`。把archive导入移进函数只避开初始化时机，没有消除事实职责相互依赖。

- 将`delivery_completeness.py`内纯归档解析的`archived_deferred_operation_evidence`和`_archived_deferred`原样移到`facts/material_deferral_evidence.py`，后者命名为`archived_deferred_payload_evidence`供已解析payload消费者直接调用；原分支、返回集合/issue code、缺失/无效语义保持。
- 当前四个实际消费者：delivery_completeness、decision_baseline、decision_baseline_source、trial_origin均直接导入该纯模块。delivery_completeness继续拥有数据库/receipt/采用来源追溯，并将load_saved_scenario恢复常规顶部导入。删除旧定义和局部循环导入，不留双份或兼容转发。
- 新纯模块只依赖scheduler_history_parser这一现有models解析器，无数据库或trial调用。此为本轮共同来源接线必要拆分，不引入新业务规则或测试函数；以AST/原内容核对两函数和现有导入检查验证，业务结果复用已通过相关用例。

## B8 工种切换的统计主体与前驱上下文

事实：正式安排为B2→B1、本次仅选B1时，事件计数正确为1→0；`decision_changeovers.py:40–42`和`candidate_tradeoffs.py:35–37`却将B2前驱纳入covered_operation_refs，使两入口隐藏差值。

- 完整设备序列继续用于确定实际相邻前驱，事件仍按next.start裁剪当前半开窗口，保留当前投影的未知和冲突规则。
- 覆盖比较只统计本次被比较工序中、在该侧有实际内制非零安排的永久工序身份；前驱上下文不增加业务范围。工作台使用 `source.operation_refs`作为统计主体；值班台使用`data.batch_refs`对应的完整受理工序范围。窗口外的前驱仍进入序列，不进入主体集合。
- 在 `facts/changeovers.py`抽取一处小型主体安排选择函数，共用永久operation_ref和现有 `task_interval` 的点事件判断；两消费者使用同一函数生成coverage，避免再写两套排除条件。仅调整覆盖来源，不改事件本身，也不取消真正不同工序范围的different_coverage保护。
- 工作台metric的total按主体安排计数，未知数仍保留事件投影已经确认的缺项；原 `max(主体条数, unknown)`下限可继续使用。值班台调用candidate_tradeoffs时传入本次批次的before/after主体或明确的主体refs，完整任务列表继续专供changeover_projection建立相邻关系。
- 在已有切换/旧消费者用例中用一份B2→B1、只选B1案例核对两入口都是reference=1、selected=0、delta=-1且better，事件前驱仍为B2；保留真正缺失主体工序时的范围不一致断言。不要新增事件版本、第二条计数规则或时间重算机制。

## B9 值班台取舍沿指标自身版本

事实：`candidate_tradeoffs.py:57`把资源取舍统一标成准备版本，而`metric_definitions`已给每项正确metric_version；`DashboardCandidateComparisonAPI.js`又固定接受错误准备版本。

- `tradeoff_entry`参数直接使用当前 `definition["metric_version"]`，资源metric_value的版本同样沿该定义；删去仅为错误统一版本存在的导入。
- 前端资源条目（source为archived_resource_calendar）与同响应 `resource_common.metric_version`核对，其余现有条目继续按其准备/通用版本合同核对。复用既有ResourceProjectionContract对resource_common的验证，不新增目录或第二份指标表。
- 扩展现有旧值班台共同资源投影用例：真实资源条目的版本等于共同资源版本，交付/切换条目仍符合其定义；既有前端真实payload probe通过，并拒绝把资源条目改回错误准备版本。无需对每个资源指标参数化复述。

## B10 同步当前操作文档

事实：根README、`DELIVERY_WIN7.md`及`开发文档/系统速查表.md`仍描述已取消的本地交付SHA文件和旧门禁哈希协议。以当前脚本实际行为修正文档。

- 根 `README.md` 的便携交付改为实际ZIP输出；长门禁说明更新为现有schema4原内容绑定、真实workflow触发和缓存机制。删掉已不存在的hash key和自动触发承诺。
- `DELIVERY_WIN7.md`准确说明prepare_win7_offline通过HTTPS下载、检查路径/普通文件及记录大小；不再声称该下载器核对SHA。`setup_win7_build.bat`实际使用 `pip --require-hashes` 安装固定第三方依赖，这是当前安装命令，保持准确；不要把这一真实第三方依赖机制一并写没。
- `开发文档/系统速查表.md`当前便携产物说明同步；当前分组编号语义以实际共同实现说明。历史字段字典中明确保留的旧hash列及历史记录保持，原值不改写。
- 三份当前文档只改已核实的现行说明；`开发文档/README.md`原10行仍由主对话保留。纯文档做差异和引用核对，不补测试。

## B11 工种切换原因使用业务说明

事实：`candidate_metrics.changeovers`将 `issues[0]["code"]`塞入面向用户的reason，值班台直接显示arrangements_unavailable。共同事件投影已有准确中文message。

- 共同适配器的reason直接使用该次投影的业务message（多项时按原顺序合并）；有已知值仍为None。保留内部issue.code在事件事实层，不让展示层再建第二份code文案表。
- 现有值班台比较和摘要继续显示同一reason。缺少正式安排时显示“比较对象缺少保存安排，工种切换次数未知。”，其他工种身份/时间/冲突缺项使用其实际message。
- 与B8同一后端写入者负责candidate_metrics/candidate_tradeoffs，避免冲突；现有缺正式基准的真实payload显示测试核对中文原因即可，不新建文案专用测试文件。

## B12 离线浏览器材料与x64构建入口一致

事实：`packaging/win7/offline-manifest.json`的Chromium条目下载x86 ZIP，`setup_win7_build.bat:17`实际消费x64 ZIP。新的离线准备目录会在copy阶段缺源。主对话只读查询上游发布元数据，已确认x64资产名称、URL和大小，不下载或执行Windows程序。

- 将该条目path改为`tools/ungoogled-chromium_109.0.5414.120-1.1_windows_x64.zip`，URL改为同名x64发布资产，size改为`116550704`，source改为[上游64bit材料说明](https://raw.githubusercontent.com/ungoogled-software/ungoogled-chromium-binaries/master/config/platforms/windows/64bit/109.0.5414.120-1.ini)。版本保持。
- 删除该条目不再对应材料且下载器未使用的旧x86 `sha256`字段，不计算/新增替代摘要。其他第三方依赖及其pip固定安装输入保持。
- 核对清单、setup复制源和既有构建器读到的是同一x64名称；本机已有x64材料的文件大小与上游资产一致。此处静态内容与入口核对足够，不为这次配置修正单独建测试；Windows运行继续统一延期，不执行setup/build/下载。

## B13 运行锁所有修改使用同一排他协议

事实：`launcher_runtime_lock.py:198–210`在重读后按路径remove，重读与remove之间仍会删掉其他进程新建的锁；rollback和release也有同类路径。`launcher_cleanup_result.py:_cleanup_paths`直接把壳锁放入通用删除列表，绕过归属协议。该问题影响同库互斥，主对话确认需在B修复。

- 在运行锁职责内增加一个小型跨进程mutation guard。固定路径为被保护的lock_path加`.guard`，文件不存业务payload、不截断、不删除。使用现有safe_files的安全普通文件打开能力以append方式打开，fd定位0；POSIX使用`fcntl.flock(LOCK_EX | LOCK_NB)`，Windows使用`msvcrt.locking(LK_NBLCK, 1)`，finally解锁并关闭。二者只用标准库；按平台分支导入。guard争用立刻给出“另一启动或退出操作正在处理运行锁，请稍后重试。”，无sleep/轮询/重试。guard文件纳入已有本地运行产物排除规则，不进入产品数据/备份/提交。
- 所有创建、读后判活、陈旧回收、创建失败清理、db锁失败回滚、正常释放都进入对应guard。在持guard时完成一次读取和归属判断再写/删；删除当前“两次循环+0.15秒sleep+重读再删”的补偿。保留壳锁与db-scope锁的既有命名、payload和读取契约。
- 同时只持一把mutation guard；壳锁预约成功后释放其guard，再获取db-scope锁，db失败后再按原payload回滚自己的壳锁。不要把整个程序生命周期改成持fd锁，也不改变已有PID/owner/正式DB身份检查。
- 锁内进程判断只允许本地非等待探针。Windows原生`launcher_win32`可用时走现有native分支；原生不可用则按身份状态未知保留锁并清楚拒启，不在持锁区进入tasklist/PowerShell或health网络调用。POSIX沿现有kill(pid,0)路径。其他只读状态查询职责保持。
- 从通用artifact路径列表删除`RUNTIME_LOCK_FILE`。契约清理必须以调用者已持有的实例身份为目标，并在同一壳锁guard内核对当前归属后清理该实例的契约文件；锁本身由锁模块移除。退出回调使用acquire返回的原payload，stop使用其已有status.lock和status.contract；不在清理时重新认领刚出现的另一实例。
- 清理入口增加明确的expected身份参数并贯通`launcher_contracts`、`launcher_stop_cleanup`、stop和`workbench_run_lifecycle`等实际调用者。对比沿用pid/owner/exe_path/started_at/db_path和现有契约身份字段，不增加令牌/哈希。锁或契约在等待清理期间已经属于新实例时，返回现有cleanup result中的明确归属变化失败并保留新文件；不得继续通用删除。锁已缺失时仍持guard，按旧契约身份核对后清理，避免新启动夹进检查和删除之间。
- 镜像日志目录沿现有匹配契约验证；真正处理每个目录时使用该目录的guard并核对同一实例身份，避免从主目录校验结果直接无条件删除镜像。对外返回继续沿现有RuntimeCleanupResult结构，不新建清理状态机。
- 既有无管理runtime的atexit分支也传当前实例payload，cleanup在release之前完成；停止后台请求/排产线程和退出备份的顺序保持。释放接口的PID参数兼容已有直接调用；内部已知完整payload的路径用完整身份核对。缺来源/无权限按现有明确失败方式处理。
- 在现有`tests/app_runtime/test_runtime_db_scope_lock.py`补一条POSIX真实双进程竞争回归，以事件同步卡住陈旧锁处理点，证明另一进程立即busy、先行进程的新锁及db-scope归属不丢；扩展已有cleanup/运行生命周期测试核对旧实例清理保留新实例锁与契约。复用已有同库/不同日志目录/回滚用例。Windows分支本轮仅源码核对，真实验证仍deferred_by_user。

### B13身份贯通与发布补充

主对话已亲读`_acquire_db_scope_lock`、`_runtime_contract_payload`、`configure_runtime_contract`、`RunRuntimeLockProof`和实际stop status：壳锁、db锁和发布契约各自生成started_at；这三个原身份分别保存，不能相互推算。

- `acquire_runtime_lock`保存实际`_acquire_db_scope_lock`返回值，作为返回claim内的`db_lock`字段传给本进程生命周期。此字段在壳锁/DB锁已经写盘后加入，只是内存中的原取得身份，磁盘payload和只读lock reader格式保持。`RunRuntimeLockProof`继续分别钉住两把原锁，不要求时间戳相等。
- `write_runtime_contract_file`返回`{"path": contract_path, "payload": payload}`，其中payload就是本次构建并实际发布的那个字典；当前实际调用者只有entrypoint。`configure_runtime_contract`返回这份publication，`_publish_runtime_contract`把其payload保存到既有lock_state的`contract`字段。退出使用这些原值，不在退出时读取当前文件补认身份。更新实际依赖注入夹具以匹配内部返回值；公开健康字段和磁盘契约版本保持。
- 将端点triplet与JSON契约合并为同一目录guard内的一次发布：`write_runtime_contract_file`在每个主/镜像目录内依次写triplet和同一个payload。`configure_runtime_contract`删除此前分开的`write_runtime_host_port_files`调用；该旧函数、launcher导出和EntryPointDeps槽位目前没有其他实际调用者，随迁移删除，避免保留一条无身份的发布旁路。主目录和镜像目录分别短暂持guard，不同时持两把。
- 发布前主目录锁核对当前持有的原壳锁claim；镜像目录有锁或契约时，核对归属，活跃的其他实例保留且记录镜像发布失败。镜像仍沿既有best-effort语义，明确记录失败，主目录失败则中止发布。cleanup与发布使用同一路径guard；同一目录不在triplet和JSON之间释放guard。
- `runtime_lock_state`现有payload内携带db_lock，contract保存真实发布payload；管理和非管理runtime的退出链都以这三个值清理/释放。创建失败尚无contract时只按原取得锁回收，不认领后出现的契约。既有线程停止→退出备份→清理/释放顺序保持。
- 外部stop在读取初始status时，根据已读取contract/lock的db_path同时保存该db-scope锁的原读结果，并核对pid/owner/exe/db归属；允许其started_at独立。finalize只使用这次已确认的shell/db/contract身份。若原db锁缺失或归属未知，保持该缺项，不在finalize重新认领当前db锁。
- 将这三份started_at不同的真实情况并入既有生命周期/cleanup用例的数据，确认正常退出能释放自己的两把锁，旧实例的cleanup不能删新实例的契约或锁。与前述双进程竞争回归共同覆盖，无需扩充Windows矩阵。

### B13主发布目录补充

主对话已亲读`entrypoint.py`源码/打包锁范围选择和`launcher_paths.py`目录解析：源码模式原壳锁固定在runtime日志目录，应用LOG_DIR可单独配置。主发布必须锚定实际取得的壳锁目录，不能再次按LOG_DIR重选。

- `write_runtime_contract_file`以`expected_lock["state_dir"]`作为唯一主发布目录；核对其lock路径并在相同guard内发布triplet/JSON。返回path是这个主目录的真实契约路径，退出cleanup沿返回path父目录。
- 镜像候选取真实配置日志目录`resolve_runtime_state_dir(runtime_dir, log_dir)`以及既有`runtime_log_mirror_dir`结果，规范化去重并去掉主目录。每个剩余目录各自持guard，检查所有权后写同一个payload；镜像错误保留原best-effort警告语义。常规同目录没有额外镜像；源码配置分叉时，配置日志目录成为镜像。打包原锁已在配置目录，原有主路径保持。
- payload.runtime_dir、data_dirs.log_dir仍记录各自真实含义；不为主目录选择篡改这些字段。cleanup使用原expected_contract发现其配置/运行日志目录，后续仍在各自guard内核对原身份。
- 复用现有发布/生命周期用例，设置实际壳锁目录与LOG_DIR不同，三份started_at不同，确认主path归属claim目录、两处triplet与JSON一致、退出只清原实例。Windows分支只静态核对，待用户统一实测。

### B13最终类型检查：内部锁状态为必需参数

完整门禁attempt02前11步通过，第12步在entrypoint.py:446报告optional锁状态传入必需Dict。主对话已查实际调用：两内部函数均只有主启动链和本次测试直接调用，全部显式提供同一个runtime_lock_state；publish仅在owns_runtime_resources分支、成功acquire后执行。

- `_acquire_runtime_lock_before_app`的`runtime_lock_state`和`_publish_runtime_contract`的`lock_state`均改为必需`Dict[str, Any]`关键字参数，删除None默认及临时空字典分支。
- publish以`lock_state["payload"]`取已取得的原claim，写入`contract`和按原条件写入`contract_cleanup_dir`均直接对同一状态执行；删除`(lock_state or {}).get`和两处None分支。保留实际acquire结果dict校验、发布归属检查及原异常处理。
- 不加cast/ignore/新检查或新的类型框架；原测试调用已经传入状态无需额外用例。限定ruff/实际主链Pyright后用原dirty命令续跑剩余完整门禁，既有同状态业务及UI证据复用；这次内部参数收敛不要求再为页面重启正常实例。

### B13最终台账位置同步

attempt03前14步通过，第15步旧启动样本127–129失配。主对话AST对照确认`_request_runtime_shutdown`整体函数未改，新增导入使原Exception处理器移至131–133，当前扫描仍为同一observable_degrade/except ordinal 1。

- `tools/quality_gate_shared.py`仅把该样本line_start/end改为131/133；路径、symbol、分类和所有样本/门槛保持。
- 主对话已做台账内存预览：直接refresh会把旧cleanup条目移除，因为同一文件删除失败处理搬到`_remove_contract_artifacts`。该处理仍记录warning并追加RuntimeCleanupFailure；只将state_dir局部名换为log_dir，并取消已要求删除的退出时新建launch_error旁路。它继续是原observable_degrade，不能把移位写成债务消失。
- 先保存台账原文件副本；用现有`sync_debt_ledger`入口模块的load/save及`quality_gate_entries.build_silent_entry`，对这一个主对话明确复核的旧条目按当前scan中的`_remove_contract_artifacts`/ordinal1重定位，existing传原条目。更新仅symbol、原handler_context和实际位置/验证时间；保留原id、source、status、owner、batch、notes、exit_condition及历史legacy字段。该一次重定位说明写fix-note，不新建永久迁移命令或放宽自动匹配规则。
- 随后执行原CLI `scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields`。主对话预览确认最终仍76条，14条发生位置/验证时间更新，其中cleanup另变symbol/context；其他分类段、全部人工字段和旧身份原值一致。按id核对实际差异，不能按列表索引错算大量变动。
- 运行原check后续跑完整dirty门禁；不scan-startup-baseline、不接受新债务、不增测试/改分类或required白名单。

## B14 pre-push执行待推提交的源码

事实：`git_hook_checks.py`按待推SHA计算范围，却在当前checkout执行；cache丢弃local_sha。另经实际pre-commit宿主入口核对，其只向子hook传首个有效ref，首次推新分支还可能没有TO_REF。因此修法必须从Git原始stdin保留完整目标，再在目标源码上执行。该问题归宿主门禁职责，本轮按下列具体路径修复。

- 保留`.pre-commit-config.yaml`原有Ruff、运行产物、commit-msg、死代码提示和日常门禁。新增小型原生pre-push包装入口，只负责完整读取Git stdin、在临时文件保存本次原始ref行、通过明确环境变量`APS_PRE_PUSH_INPUT_FILE`传给原pre-commit链，并将原stdin原样提供给该链。返回原链退出码，finally删除本次临时文件；不写持久push队列，不使用SKIP绕过任何hook。
- 增加`tools/install_git_hooks.py`作为项目唯一说明中的安装命令。仍调用项目Python的pre_commit install生成标准hook，再给pre-push安装上述包装；标准生成的pre-push脚本保存到同目录明确的`pre-push.pre-commit`，由包装转调，pre-commit/commit-msg保持原样。再次安装识别本项目包装并更新其底层生成脚本。非本项目且非pre-commit生成的已有hook先明确报冲突并保留，避免覆盖用户脚本。只管理当前仓库hooks，绝不修改全局Git配置。
- 包装脚本使用安装时已确认的项目Python绝对路径及明确入口，正确引用空格/中文路径。原标准pre-commit脚本继续处理自身依赖与legacy链。安装器/包装器只做这一个职责，不引入常驻进程、第三方依赖或Git调度框架。
- `_pre_push_input_for_hook`优先解析该临时文件的完整原始行，其次支持原生直接调用的stdin。处于真实pre-commit远程push环境却没有原始输入文件时，明确提示用项目安装器更新hook并失败，不把首个ref或当前HEAD猜作全部目标。手动日常检查无push上下文时保持原入口语义。删除ref没有本地提交，继续跳过。
- 按唯一local_sha分组，同一SHA的多个目标ref合并实际changed_paths；不同SHA分别执行。为每个目标用Git建立本次专属的临时detached worktree，使用原项目`.venv`绝对Python运行该目标里的`run_daily_quality_gate.py`。scope文件传真实路径和known/reason，目标脚本自行使用其registry选择用例。每个目标完成后清理自己的临时worktree；不改主checkout、索引、现有分支或其他worktree。
- 目标是当前HEAD时同样以已提交内容为执行对象，避免dirty工作内容替代真正待推源码。所有目标都通过后才记录原有单条aggregate通过缓存；`_daily_ref_contexts_cache_extra`补回local_sha并稳定排序。现有原内容/日志绑定保留，不另建每worktree缓存或摘要。目标任何失败均阻止push并显示实际目标ref及退出码。
- 移除`git_hook_checks.main`对全部子命令无条件切换本目录`.venv`的入口。标准库的check-staged-artifacts/check-commit-msg沿调用者解释器执行；run-ruff、run-quality-gate和各依赖工具入口继续用它们已有的项目解释器选择。这样目标daily调用目标标准库检查时无需复制/链接`.venv`或新增解释器fallback。
- 安装说明由根README更新为`.venv\\Scripts\\python tools/install_git_hooks.py`；`开发文档/README.md`对应命令由主对话更新，B不触碰该文件原改动。B先在临时仓库验证安装器和包装；当前仓库实际安装由主对话在源码验收后、B推送前执行。
- 在现有host hook测试中做一组真实临时Git仓库回归：当前分支的检测脚本成功，另一待推提交的同名脚本失败；安装包装后通过真实原生hook输入传两个ref，证明执行读取各自提交内容并因失败目标阻止、随后改变local_sha不会复用旧通过。用轻量fixture脚本，避免为验证hook嵌套运行整套产品pytest。追加核对首次分支和删除行沿同一stdin解析，原有提交hook实测复用。Windows安装/运行分支保持延期。

## B15 用户追加：候选、收益代价与页面详情的排版

授权与证据：用户在B对话2026-10-14直接提供两张截图，要求处理白空、收益代价错位和展开页面详情。主对话已看两张原图并在正常58240实例只读展开页面详情；原图`evidence/decision-workbench-review/2026-10-14/ui-before/01-page-details.png`。本项随B交付，由主对话设计/实页验收，B实施。保持现有蓝灰工作台语言，以紧凑、对齐和清楚的选中状态解决问题。

用户随后在主对话明确追加：“不要光看我说的那些地方，其他地方有类似问题的话，你检查出来也一并修掉”。因此B15同时覆盖其他页面中实际确认的同类错位、无意义空白、分隔线误命中、选中状态不清与展开详情混排。沿共用样式/组件查消费者，主对话亲自复核并补具体位置/修法；共用组件已有同根因影响一并处理。保留有效信息结构，不自动扩成整站重做。

### 修改位置与根因

- `frontend/workbench/app/styles/36-analysis.css`的`.dy-panel section+section`误中收益/代价内部第二个section，额外给其顶部间距、padding和横线。把通用分节规则收窄到`.dy-panel > section + section`，保留候选比较与后续独立候选列表之间的真实分节；内部块由各自命名类负责。
- `DashboardCandidatePanels.jsx:Tradeoffs`当前复用横排、居中对齐的dy-context且h4没有margin约束，两个部分宽度随文案漂移。改为专属的dy-tradeoffs / dy-tradeoff-grid / dy-tradeoff类，不继续用dy-context承载布局。
- `DashboardWorkspace.jsx`页面详情作为dy-tools的横排子项，展开正文把刷新按钮推到垂直中间。工具操作与展开内容按下面结构分开，沿用原生details状态。

### 最终布局与状态

1. **候选选项。** 保留fieldset/legend与原生radio；每个label新增data-selected，直接取现有choice.candidate_ref。四候选在1280页面为四列等宽、8px间隙；<=1000px两列，<=560px一列，6/8候选自然继续下一行，保留既有列表限高和滚动。选项用1px ui-border、ui-surface-muted、wb-radius-control、12px内边距，最小高度64px，文字块min-width:0；名称一行不下则自然换行，状态/安排数下一行。选中为ui-primary边框+ui-primary-soft底色；hover略加深、focus-visible保留现有清楚轮廓。整块label可点，radio仍显示，不增加第二套按钮/选中状态。
2. **收益和代价。** 标题下12px出现两列等宽grid，gap12px、align-items:stretch；<=700px为一列。两个内部块用div和各自h4，padding12px、1px边框、原有圆角，无固定高度。h4 margin:0 0 8px，标题同一基线；列表去圆点和默认margin，条目使用真实label+text，行距1.55，条目之间8px。有收益时用ui-success-bg/边框及深色成功标题；有代价时用ui-warning-bg/边框及深色警示标题；空项使用中性ui-surface-muted，显示“本范围暂无已确认的收益。”或“本范围暂无已确认的代价。”，不把未知涂成成功。保留共同reason.message、原全部差值与比较依据和关联记录；折叠入口位于卡片下12px，正文原值/未知不变。
3. **基准缺失。** data.baseline.available=false时Tradeoffs不画两张空卡，只在标题下放一条紧凑中性信息“排产时没有正式计划，收益与代价暂无法比较。”，下方仍保留全部差值与原说明。删除DashboardCandidates外层重复的缺基准黄色提示，由这个共同Tradeoffs负责，摘要弹窗同样只出现一次。其他指标继续显示真实未知/缺项。
4. **页面详情。** DashboardWorkspace顶层先是独立dy-page-toolbar，左侧原刷新和上次结果按钮，右侧次要文字“更新于 {原完整日期时间}”；工具栏align-items:center、两侧space-between、可换行。其下是独立全宽原生details.dy-page-evidence，summary保留“页面详情”，默认折叠；不把展开正文塞在按钮横排中。展开内容为一个ui-surface-muted浅底、1px ui-border、12px padding的完整区域：dl两列分别为“资料来源”和“交期统计”，dt为次要小字、dd为正文且margin:4px 0 0/max-width:none，<=700px一列。保留全部真实来源文字和T.delivery_coverage原值，缺范围时沿原条件不显示。正式计划编号仍放区域底部既有WorkbenchReference折叠里。时间仅在工具栏出现一次；不新增按钮、重读请求或详情状态存储。
5. **内容节奏。** Tradeoffs整个区块结束与后面的“批次交付对比汇总”留16px，标题与表格8px；各块使用显式class控制，不再靠任意section相邻影响内部。字体、颜色、间距和圆角沿已有tokens，不新增设计系统、图片、阴影层叠或整页重做。该Tradeoffs同时供主页面和摘要弹窗使用，两处同样对齐。

### B15同类扩查：试调来源详情

主对话与全新只读代理已分别核对`TrialWorkspace.jsx:109–124`和`32-process-trial.css:71/103`：时间范围details.tt-refs是align-items:center工具栏的直接flex项，展开9类长内容且没有换到完整行的规则，与值班台截图同根因。正常只读库当前草稿/试调方案均为空，源码结构已确认，实际最终画面使用既有试调回归的受控输入核对，不向正常库造记录。

- 保留details原生状态、原compactRange summary/title与原Download按钮。仅给此顶层工具栏的tt-refs规定margin:0、min-width:0、max-width:100%；`[open]`取`flex-basis:100%`，让原按钮维持紧凑首行，展开内容完整占下一行。
- 详情正文加tt-source-body浅底/边框/12px内边距；原安排、试调安排、建草稿时正式版本和完整起止/刷新时间用两列dl，dt次要小字、dd正常正文、margin:4px 0 0，<=700px一列。`tt-source-facts > div`明确display:block，覆盖外层wb-ref通用dl子项的横向grid，保证dt上/dd下；内层编号组件原grid保持。交期覆盖作为全宽末行。永久编号改为该body内既有WorkbenchReference entries的一个折叠，草稿/试调方案/来源编号按原条件保留。原安排“创建草稿时保存”、试调当前/已保存状态、日期秒与小数均保留，数据/读写请求/草稿状态不变。
- 正常源码中RunCandidate的source summary/scope已有`details[open]{flex-basis:100%}`，RunHistory的rh-source未居中且能顶部排列，TrialAdoptionHistory的tah-meta为块布局，这三类不改。其他线索经主对话实际核对后再补，避免凭flex或分节样式名称判错。

### B15同类扩查：共同选中态与计划列表空白

主对话已亲读全新代理列出的实际消费者及共同CSS，并在58240真实计划列表核对：radio.checked=true、tr.aria-current=true，但行和冻结首格的computed background均为白色，预期ui-info-bg为#eff6ff；截图`ui-before/02-plan-selected-row.png`。同图只有一条计划，固定180px列表容器留出大片无内容空白。

- 共同选中态根因在`frontend/workbench/prototype/ui_kits/workbench/workbench-ui.css:67–70`：默认行背景与hover带important，而当前选中规则只认aria-selected/.selected/.is-selected。扩展这条既有规则，同时支持`tr[aria-current="true"]`和`tr[data-selected="true"]`，与原选中态使用相同ui-info-bg并在hover之后胜出。保留现有语义标记和状态所有权，不逐个组件新增选中状态或重复important。
- `frontend/workbench/app/styles/21-table-frame.css`既有冻结首尾格选中规则同样加入这两种标记，保证选中色连续覆盖冻结单元格；保留原focus-within轮廓和横滚阴影。选中列标题`thead th[data-selected="true"]`也在共同workbench-ui层用既有ui-info-bg/文字色明确覆盖默认表头important，正文td沿当前规则。无选中标记的表头保持原样。
- 已确认消费者包括候选目录、计划列表（aria-current），值班台风险清单、历史数值表、资源逐日表、计算来源表（data-selected），以及详细候选比较的选中列。仅共同入口修复，无需改这些JSX或为每处各写一份测试。
- `33-plan-gantt.css`的`.plan-workspace .plan-catalog-scroll.wb-table-frame`由`height:180px`改为`height:auto;max-height:180px;min-height:0`，保持overflow和sticky合同。少量行随内容收缩，多行继续在180px内滚动；不改行数、分页、目录开合或列表请求。
- 正式构建后主对话以计划目录亲验选中行/冻结首格的computed颜色及单行高度；另看一份历史或风险列表的data-selected，以及详细比较的选中列表头。复用现有浏览器交互，不新增同规则排列矩阵。

### B15实页扩查：问题批次编号展开

B在实际1280页取证`ui-context-reference-expanded-1280.png`，主对话已亲读`DashboardCandidates.jsx:99`与`WorkbenchReferences.jsx:5–10`：原问题批次说明和原生编号details共同位于dy-context的center横排。编号展开的dl增加高度，把说明拖到中间。

- 在已有`36-analysis.css`的dy-context职责内补`.dashboard-live .dy-context > .wb-ref[open] {flex-basis:100%;}`，让展开编号独占下一行，关闭时仍与简短说明同排。原编号、label、数据、原生details状态与所有请求保持，无需改JSX或全局所有wb-ref。
- 构建后只复验这条展开/收起与窄屏；当前已完成的其他UI截图/交互继续有效。纯CSS不新增测试函数或重启后台，完整门禁按实际已改变输入决定复用，保留运行日志。

### B15主对话实页返修：冻结列选中规则优先级

主对话在新版59615实页发现共同选中规则虽匹配，冻结首格仍白色：row为rgb(239,246,255)，首格为rgb(255,255,255)。单行目录已经正确从180px收至83px。原件`parent-ui-final/06-selected-plan.json/png`。

- `21-table-frame.css`默认冻结格选择器含`[data-sticky-actions] > table.wb-table`，特异性高于当前选中格规则。将选中格规则锚定同一责任路径：`body.aps-workbench .wb-table-frame[data-sticky-actions] > table.wb-table tbody tr:is([aria-selected="true"],[aria-current="true"],[data-selected="true"],.selected,.is-selected) > :is(.wb-col-key,.wb-col-actions)`；background仍用ui-info-bg。
- 以与默认规则相同的结构加选中条件获得明确优先级，不加important或组件补丁。focus shadow/滚动阴影、未选中冻结格与其他表格保持。正式构建后主对话重读这一个实际首格颜色；目录高度与其他已通过路径复用。

### B15主对话实页返修：详细比较表头优先级

主对话在最终CSS1791979264的真实“全部指标”页读取选中表头：data-selected=true，但背景仍为rgb(248,250,252)。CSSOM证明`20-controls.css:490`的`body.aps-workbench table.wb-table thead th`同时使用important，特异性高于新增的无body选中规则。原件`parent-ui-final/11-selected-heading-before.json`。

- 将本轮共同`workbench-ui.css`新增选中表头规则的selector精确改为`body.aps-workbench table.wb-table thead th[data-selected="true"]`，保留ui-info-bg/ui-info-text及既有important。同一基础路径加选中条件，正文td及未选中表头保持；不新增另一份覆盖或改组件。
- 构建后主对话只复验当前已打开的详细比较页表头与正文列颜色。此前Gate04全量726通过/36跳过及其他UI结果按未变职责复用，纯CSS不重跑全量pytest；真实pre-push仍按最终提交检查。

### 验证边界

- 纯布局与文案调整不新增单元测试函数。正式构建并复用已存在值班台异步/真实payload回归，B1/B2业务数据与状态语义保持。
- 在最终同版本冷启后，以原库实际页面核对：1280宽四候选选中卡、页面详情展开/收起、无基准一条说明；选一个已有基准记录看真实收益/代价并打开摘要弹窗，两个标题top一致、行不被裁剪。补一个窄宽单列和键盘radio/summary操作即可，保存前后截图与必要DOM尺寸，不重排/采用/造数据、不另起全矩阵。
- 当前主对话在旧backend+本轮已构建前端混合状态选旧4候选时得到“所选候选的取舍资料缺项”；最终冷启后须核对该路径。若仍失败，再报实际payload与字段证据，按根因处理。

## 验证与交接

- 只补上述真实覆盖缺口，优先扩展既有用例；记录新增测试函数/参数数量和原因。B继续完成原四组独立审查，确认新问题交主对话决策；只读已通过且输入未变的材料复用。
- 分组相关测试通过后构建正式静态资源。主对话随后按B6缓存修复、B7共同来源和B13运行锁的实际影响明确本批收口验证：全部源冻结后执行一次完整dirty门禁`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --long-gate-cache`，沿实际输入复用有效条目，保留Windows延期引起的原失败/skip；不声明clean proof。本批先不再单独执行整批日常测试，真实pre-push将对最终已提交目标执行日常门禁，两者结果分别记录。首轮漏显式dirty参数，在入口因4个未追踪源码exit2、executed0，原日志保留；修正调用参数后执行实际检查，不改变门槛或工作区归属。
- 同库正常实例只读使用；不要为截图重排、采用或造样例。需要重启由实施方统一进行并交付新base_url/PID/库身份、静态资源版本，主对话独立实际验收。所有Windows验证继续延期。
- 代码交接提供明确文件清单、实际测试结果、构建结果及本次正常路径截图/原始导出所在位置；在本目录写一份简短 `decision-workbench-review-fix-note.md`汇总。修复/验收状态仍为in_progress；提交推送待主对话验收后执行。

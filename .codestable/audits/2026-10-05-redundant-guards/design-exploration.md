---
doc_type: audit
audit: 2026-10-05-redundant-guards
created: 2026-10-05
status: explored
scope: 当前代码的数据正文、状态、规则、算法输入、接口、前端派生计算及交付设计
keywords: [冗余设计, 共同事实, 单一职责, 引用链, 历史协议, 无损整数]
---

# 冗余设计：全面探索与引用链判断

仍有值得收敛的设计。最主要的根因是：同一业务规则有多个维护入口，同一历史正文保存多份后再交叉核对，已经核实的事实被转换成旧对象再重新解释，以及实时操作依赖全部历史记录。部分重复已经造成合法数据被拒绝或公开信息丢失；其余主要增加存储、计算和维护工作。

本次对应用户“还有什么冗余设计吗，全面探索”。只读调查，沿用此前“留档”要求保存本报告及索引入口；未修改产品、测试、Schema、交付脚本或基线。以下是当前代码的发现与建议，不是实施结果。之前的修复和验证仍以 [复判后修复记录](../../issues/2026-10-05-redundant-guards/reassessment-fix-note.md) 为准，不改写其历史裁决。

后续实施入口：用户已授权“该修就修，修的过程中确认是否真的需要”。逐项落地、保留理由、独立 review 与实际验证见 [设计修复记录](../../issues/2026-10-05-redundant-guards/design-fix-note.md)。下文保留 2026-10-05 只读探索时的代码位置与判断，部分文件已在实施中移动或删除，不能把旧行号当作现行实现位置。

## 优先判断

- 先处理已经发生规则分叉的地方：无损整数、模板来源合法性、诊断事实投影，以及自动维护的实际驱动缺口。
- 适合直接局部收敛：无人消费的试调 artifact、准确任务定位的第一轮空查询、随后被替换的 profile 排名、正常维护结果跟踪改回原 request key。
- 值得有目的地重构：共同配置定义、候选与试调的正文权威、不可变拓扑、资源投影、物理文件读取，以及 history/scroll 发布职责。
- 必须先定协议或兼容边界：历史正文格式、旧公开接口退役、日期是否接受含时间的 Excel 值、不可变输入与外部注入算法的所有权。不能用简单删字段或删检查代替这些设计。

P2 表示应安排处理的行为问题或反复发生的结构成本；P3 表示局部维护成本、低收益项或仍需权衡的设计。没有实库规模、目标机耗时或磁盘大小证据，不给出实际性能倍率。

## 数据正文与配置

### D01 · P2 · 从候选建立试调时复制无人消费的完整 artifact

[trial/base.py:175](/Users/lurenxing/GitHub/----/core/services/workbench/trial/base.py:175) 把完整候选 artifact 放入 source，189 行放入 admission，再由 [trial_repo.py:49](/Users/lurenxing/GitHub/----/data/repositories/workbench_trial_repo.py:49) 持久化。当前试调真正读取 identity、dispositions 和 capture 的 input/facts_text/execution；没有找到 source.artifact 的生产消费者。

判断：这份正文是真冗余。新 admission 可以停止复制，历史档案保持原样。不能连 capture 一起删；原始输入和执行依据有真实消费者。本项不同于此前已修的“后续 run 再采含旧 capture 的 trial”：当前是每次候选建立草稿时额外保存结果和诊断正文。

### D02 · P2 · 候选安排的同一六字段保存三份

[run_result_repo.py:24](/Users/lurenxing/GitHub/----/data/repositories/workbench_run_result_repo.py:24) 的 engine results、30 行的 validated_payload.schedule_rows 和 70 行的 CandidateTasks.payload_json 都保存 op_id、machine_id、operator_id、start_time、end_time、source。[candidate_tasks.py:84](/Users/lurenxing/GitHub/----/core/services/workbench/facts/candidate_tasks.py:84) 与 [candidate_adoption_validation.py:115](/Users/lurenxing/GitHub/----/core/services/workbench/run/candidate_adoption_validation.py:115) 再读取这些副本并交叉比较。

真实 `_prepare_candidate()` 的纯内存合成探针确认：1000 条任务的这六字段完全相同；一份 JSON 为 138,894 字节，三份为 416,682 字节。这是序列化正文计量，不是实际库文件大小或全部 artifact 大小。

建议新协议明确一份安排正文的权威，优先使用永久任务行；artifact 保留验证结论、指标及 engine 独有追溯字段。任务行的 FK、永久 row/task 身份、顺序、唯一约束及目录计数不能删除。旧档案原字节和完整性合同需要兼容读取。

### D03 · P2 · 保存试调时正文又有三份

[trial/service.py:147](/Users/lurenxing/GitHub/----/core/services/workbench/trial/service.py:147) 生成完整 snapshot；[trial_repo.py:96](/Users/lurenxing/GitHub/----/data/repositories/workbench_trial_repo.py:96) 保存 snapshot_json，103 行逐任务保存 ScenarioRows.payload_json；返回的 snapshot 再进入 [commands.py:105](/Users/lurenxing/GitHub/----/core/services/workbench/commands.py:105) 的命令回执。[trial_policy.py:65](/Users/lurenxing/GitHub/----/core/services/workbench/facts/trial_policy.py:65) 读回副本并比较。

内存 spy 执行真实 save()，1000 条简化任务的 snapshot 为 567,278 字节，回执 data 同样大，永久行正文为 566,000 字节，合计 1,700,556 字节。输入经过简化，数字不能外推到生产数据。

建议新档案采用“元数据及有序 row_ref 清单＋永久行正文”，保留完整性验证和正式计划采用的 row/task/source 绑定。ScenarioRows 当前没有 ordinal，不能删除 snapshot.tasks 后随意排序。trial.save 的不可变场景可用于精确 replay；create/change 的当时投影、时间与令牌不能机械改为重新生成。

### D04 · P2 · 配置语义维护两套，并在 decode 中重新规范化

同一 27 字段规格分别位于 [runtime_fields.py:12](/Users/lurenxing/GitHub/----/core/models/schedule_config_runtime_fields.py:12) 和 [config_field_spec.py:23](/Users/lurenxing/GitHub/----/core/services/scheduler/config/config_field_spec.py:23)；Snapshot、to_dict 和权重规则也有两份。[spec_sync 测试:35](/Users/lurenxing/GitHub/----/tests/config/test_scheduler_config_spec_sync_contract.py:35) 要求两边锁步，说明重复维护真实存在。

[runtime_coercion.py:408](/Users/lurenxing/GitHub/----/core/models/schedule_config_runtime_coercion.py:408) 与 [config_snapshot.py:340](/Users/lurenxing/GitHub/----/core/services/scheduler/config/config_snapshot.py:340) 的 ensure 都重建对象；[schedule_params.py:377](/Users/lurenxing/GitHub/----/core/algorithms/greedy/schedule_params.py:377) 每次 decode 从空 runtime snapshot 开始转换。纯内存探针连续解析同一服务 Snapshot 三次，得到 81 次字段转换。

建议中立的字段规格、Snapshot 和转换核心只维护一份；页面 metadata、错误标签与 legacy omission 策略保留在服务适配层。规范化结果应有明确所有权，不能只用 isinstance 跳过可变对象验证。相邻重复：[run/input.py:88](/Users/lurenxing/GitHub/----/core/services/workbench/run/input.py:88) 已取配置，旧输入缺 hold_window 时 [input_config.py:39](/Users/lurenxing/GitHub/----/core/services/workbench/run/input_config.py:39) 又读全配置；应从原始 Snapshot 分别派生候选 override 和默认窗口。

## 业务规则、资源与导入

### D05 · P2 · 资源列表仍绑定无关全域事实，属于旧 1.4 的剩余范围

[resource/queries.py:69](/Users/lurenxing/GitHub/----/core/services/workbench/resource/queries.py:69) 的读 scope 包含全域计数及 table_refs；[query_repo.py:54](/Users/lurenxing/GitHub/----/data/repositories/workbench_resource_query_repo.py:54) 还聚合 part/material/batch/resource_team 身份。[resources.py:51](/Users/lurenxing/GitHub/----/web/routes/workbench/resources.py:51) 用于分类列表，后续 [read_context.py:31](/Users/lurenxing/GitHub/----/web/routes/workbench/read_context.py:31) 拒绝 scope 变化。

原捕获函数的内存 SQLite 探针把 fingerprint 替换成原输入对象：设备页在增加无关物料后，行、private write-state、指标和 create_snapshot 不变，scope/counts 改变；改无关人员名称时前述页面内容及计数不变，scope/table_refs 改变。每次 capture 计数为 41 条 SELECT，包含 Materials COUNT。没有生成 SHA。

判断：当前列表的新鲜度范围过宽，应绑定当前种类和可见依赖。全站轨道汇总可以拥有自己的全域 scope。此前资源 create scope 已修，不能把此证据写成创建修复无效。

### D06 · P2 · 模板完整性与来源合法性并行定义，legacy 路径已经分叉

[batch/template_validation.py:9](/Users/lurenxing/GitHub/----/core/services/workbench/batch/template_validation.py:9) 检查工种存在，却没有共同的 category/supports_source 规则；[workflow_state.py:111](/Users/lurenxing/GitHub/----/core/services/process/workflow_state.py:111) 检查来源、类别、供应商能力与组关系。批次展示沿 [queries.py:71](/Users/lurenxing/GitHub/----/core/services/workbench/batch/queries.py:71)、同步预览沿 [operations.py:55](/Users/lurenxing/GitHub/----/core/services/workbench/batch/operations.py:55) 使用前者。

真实 legacy 投影的内存探针：自制工序引用外协类别工种、工时有效时，template_status.complete=True 且 diagnostics 为空，而共同来源事实 source_valid=False。[require_template_ready](/Users/lurenxing/GitHub/----/core/services/process/workflow_state.py:417) 的 legacy 分支直接返回，进一步暴露两套规则的差异。

建议共享资料有效性规则，展示、同步和写入分别选择处理方式。legacy 是否需要人工确认是另一项政策，不能因旧资料免确认而允许来源类别错误。

### D07 · P2 · 同一计划的无损整数有多个不一致契约

[candidate_values.py:57](/Users/lurenxing/GitHub/----/core/services/workbench/facts/candidate_values.py:57) 与 [plan/projection.py:102](/Users/lurenxing/GitHub/----/core/services/workbench/plan/projection.py:102) 把超过 JS 安全整数的合法数量发布为字符串。[PlanContract.js:128](/Users/lurenxing/GitHub/----/frontend/workbench/app/PlanContract.js:128) 接受；[FieldContract.js:18](/Users/lurenxing/GitHub/----/frontend/workbench/app/FieldContract.js:18) 和 [ActualGanttContract.js:21](/Users/lurenxing/GitHub/----/frontend/workbench/app/ActualGanttContract.js:21) 只接受 safe number。现场工作区原样转发计划数量，实际甘特也使用这份计划投影。

Node VM：42 三处均通过；字符串 "9007199254740992" 和 "9223372036854775807" 只有计划校验通过。同根问题还在工序号：[actual_gantt_chain.py:42](/Users/lurenxing/GitHub/----/core/services/workbench/execution/actual_gantt_chain.py:42) 比较 SQL int 与公共 str，会把合法相同工序判为不一致；[ActualGanttContract.js:110](/Users/lurenxing/GitHub/----/frontend/workbench/app/ActualGanttContract.js:110) 也只接受 number sequence。

建议共同维护无损整数表示、范围与公共谓词，内部值和公共值比较时统一表示。真实行为是拒绝合法响应或使链不可用，没有证据支持“当前链静默舍入后仍显示错误”。保留未知数量、历史依据和整数范围检查。

### D08 · P2/P3 · 资源的共同解释分散在展示、写状态、指标和 SQL 中

| 子项 | 当前证据 | 判断及边界 |
|---|---|---|
| 人员资格 | [batch/projection.py:67](/Users/lurenxing/GitHub/----/core/services/workbench/batch/projection.py:67) 自己拼技能与 truthiness；[operator_qualification.py:67](/Users/lurenxing/GitHub/----/core/services/personnel/operator_qualification.py:67) 已提供 project_facts | 资格事实应共用纯投影；展示问题与写入拒绝是不同动作。没有把 DDL 已拒绝的 skills_declared=2 算作生产故障。 |
| 写状态结构 | [states.py:48](/Users/lurenxing/GitHub/----/core/services/workbench/resource/states.py:48) 与 [table_states.py:21](/Users/lurenxing/GitHub/----/core/services/workbench/resource/table_states.py:21) 构建同形 machine/operator state；supplier 的独立 pair 为 [suppliers.py:45](/Users/lurenxing/GitHub/----/core/services/workbench/resource/suppliers.py:45) 与 [table_states.py:42](/Users/lurenxing/GitHub/----/core/services/workbench/resource/table_states.py:42) | 共用 assembler；单条查询与批量捕获各有性能职责，不能强制用同一 SQL 路径。现有测试要求结构等价。 |
| 状态分类及写入责任 | [resource/projection.py:16](/Users/lurenxing/GitHub/----/core/services/workbench/resource/projection.py:16)、[metrics.py:62](/Users/lurenxing/GitHub/----/core/services/workbench/resource/metrics.py:62)、[workbench_supplier.py:93](/Users/lurenxing/GitHub/----/core/models/workbench_supplier.py:93)、[query_repo.py:9](/Users/lurenxing/GitHub/----/data/repositories/workbench_resource_query_repo.py:9) 分别解释；Schema reason-reset trigger 后 entities/suppliers 又写回意图 | 当前分类结果未发现正常数据分叉；规则和写入 owner 可以收口。旧 unknown reason 重置政策与新显式原因不同，不能直接删 trigger 或补偿写。 |

### D09 · P2 · 物料工序绑定和到料流水被同一个读写接口捆绑

[batch_material_stage_repo.py:11](/Users/lurenxing/GitHub/----/data/repositories/batch_material_stage_repo.py:11) 的 details 每次查询 stages 和 arrivals；[materials.py:25](/Users/lurenxing/GitHub/----/core/services/workbench/batch/materials.py:25) 逐需求再读，尽管路由 guard 的 BatchFacts 已有这两套事实。批量复制 [batch/bulk.py:125](/Users/lurenxing/GitHub/----/core/services/workbench/batch/bulk.py:125) 经物料仓储加载到料，随后新批次使用空到料，旧到料没有消费者。

[materials.py:124](/Users/lurenxing/GitHub/----/core/services/workbench/batch/materials.py:124) 调 replace；[stage_repo.py:16](/Users/lurenxing/GitHub/----/data/repositories/batch_material_stage_repo.py:16) 总是删除重建两类记录。只改工序绑定也会重写没变的到料及其 id。建议按实际变更分开 binding/arrivals 的捕获和保存，复用 guard facts；保留日期顺序、复核和整笔事务。没有据此认定当前到料数据损坏。

### D10 · P2 · 多份物理 CSV/XLSX reader，日期政策已经不一致

[facts/file_codec.py:34](/Users/lurenxing/GitHub/----/core/services/workbench/facts/file_codec.py:34)、[calendar_files/file_codec.py:88](/Users/lurenxing/GitHub/----/core/services/workbench/resource/calendar_files/file_codec.py:88)、[relation_files/file_codec.py:27](/Users/lurenxing/GitHub/----/core/services/workbench/resource/relation_files/file_codec.py:27) 的 _source_rows 经直接 AST 比较完全相同；物料和工艺 reader 也重复维护解码、首表读取和关闭生命周期。

[excel_validators.py:61](/Users/lurenxing/GitHub/----/core/services/common/excel_validators.py:61) 接受含时间 datetime 并取日期；[calendar_files/file_codec.py:36](/Users/lurenxing/GitHub/----/core/services/workbench/resource/calendar_files/file_codec.py:36) 拒绝非午夜值，尽管注释说与批次一致。含时间 Excel 日期是否允许需要明确政策，不能合并时随意选一边。

建议共同物理 iterator，领域各自保留行结构、错误文案、行数限制和语义。工艺特有 ZIP/XML 检查、公式与维度限制不能因为 reader 合并而消失。不需要建立通用导入框架。

### D11 · P2 · 试调容量重写已有利用率计算

[trial/capacity.py:65](/Users/lurenxing/GitHub/----/core/services/workbench/trial/capacity.py:65) 独立计算 occupied/overlap/available/intersection/utilization；[resource_utilization_metrics.py:62](/Users/lurenxing/GitHub/----/core/services/capacity/resource_utilization_metrics.py:62) 已被计划、报表和候选使用，resource_pressure 也已有适配范例。

判断：共同区间和指标规则应维护一份，试调保留字段映射、segments 和当前精度合同。特别注意试调 overlap_hours 对应共同 span_overlap_hours，而非共同接口另一种 overlap_hours；共同内核的舍入规则也不能直接改变试调输出。当前没有证明公式产生错误结果。

## 排产、报告与入口退役

### D12 · P2 · 工作台报告先产生空旧执行投影，再覆盖大半字段

[workbench/report/facts.py:21](/Users/lurenxing/GitHub/----/core/services/workbench/report/facts.py:21) 继承 ReportEngine，27 行用 state=None 生成 23 字段旧执行复盘；[review_export_labels.py:19](/Users/lurenxing/GitHub/----/core/services/workbench/report/review_export_labels.py:19) 再用 ledger 覆盖 14 字段。实际共用的是其余 9 个计划标签和计划资源字段。

纯内存 3 行探针计数 45 次实际时间、偏差、异常和空资源标签调用，结果随后丢弃。父构造器 [report_engine.py:71](/Users/lurenxing/GitHub/----/core/services/report/report_engine.py:71) 还构造旧诊断与事件服务。建议抽共同计划读取及 planned labels，新报告直接消费 ledger；保留正式计划身份和 Excel 合同。

### D13 · P2 · 已核冻结外协事实仍绕旧对象和旧降级协议

[contracts/external_context.py:47](/Users/lurenxing/GitHub/----/core/services/scheduler/contracts/external_context.py:47) 已要求 native 有限正 total_days；[schedule_template_lookup.py:46](/Users/lurenxing/GitHub/----/core/services/scheduler/run/schedule_template_lookup.py:46) 又造 PartOperation/ExternalGroup，返回永远空的 events、永远 False 的 merge_context_degraded 和无人消费的 strict_mode/scope。[schedule_input_builder.py:106](/Users/lurenxing/GitHub/----/core/services/scheduler/run/schedule_input_builder.py:106) 再建 collector、解析正数并保留坏整组降级为单道的分支，当前冻结生产者先拒绝坏值，无法进入该分支。

建议内部 builder 消费已核冻结事实，旧适配放在真实兼容边界。独立算法 raw 输入与历史 summary 的兼容保留。同次 lookup 的 context_group_key 已取得却再次计算，可以复用已有值；本轮没有为此运行哈希。

### D14 · P2 · repair/IG 每次建立 profile 排名后全部替换

[graph/candidates.py:91](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/graph/candidates.py:91) 先 context_for_profile，[repair_neighbors.py:85](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/graph/repair_neighbors.py:85) 随后完整替换 priority map；[iterated_greedy.py:328](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/graph/iterated_greedy.py:328) 和 [repair.py:378](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/graph/repair.py:378) 反复走这条链。

3 工序内存探针发生一次 v2 normalization、三次 profile key 计算，最终 decoder 只消费显式 operation/batch rank。建议直接构造最终决策 context；保留 profile 来源、参数签名、准入与预算检查。

### D15 · P2 · 只改顺序仍复制全部工序，所有权没有表达清楚

[repair_decisions.py:58](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/graph/repair_decisions.py:58) 无条件复制全部工序，实际修改只有 64/66 行的资源覆盖。空 override 的 3 工序探针仍复制 3 个对象，IG 每个 decode 重复这一工作。

建议明确 native decoder 的只读输入，分享未变工序，只复制 override 工序。但现有 [test_graph_repair_decisions.py:63](/Users/lurenxing/GitHub/----/tests/algorithm/test_graph_repair_decisions.py:63) 要求隔离；未知注入 schedule_fn 可能修改输入，必须在适配边界保留隔离。不能直接删 copy 并宣称行为不变。

### D16 · P2 · 不可变图拓扑与每次 decode 的可变状态一起重建

[schedule_graph_report.py:174](/Users/lurenxing/GitHub/----/core/services/scheduler/run/schedule_graph_report.py:174) 生成 edges 后，analysis_service 又从同 nodes 生成；[graph/ready.py:205](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/graph/ready.py:205) 已核图，每次 [sgs_graph.py:44](/Users/lurenxing/GitHub/----/core/algorithms/greedy/dispatch/sgs_graph.py:44) decode 又 remap、建方向邻接并查环。

4 节点、3 次仅优先级变化的内存探针：optimizer 建 2 次 links、查环 1 次，decoder 又建 6 次 links、查环 3 次。建议共同持有不可变 topology/node/scope，frontier、剩余前驱、结束时刻和 priority 每次重新创建。公开 raw 输入、不同 scope 和未知注入入口仍须独立校验。当前 comparison 内 NetworkX 核心缓存已经正确，不能重复报为逐候选重建分析。

### D17 · P2/P3 · 退役页面留下完整服务图及冻结打包锚

[legacy_page_contract.py:49](/Users/lurenxing/GitHub/----/web/routes/workbench/legacy_page_contract.py:49) 已退役配置页，53 行退役派工页。ConfigPageSave/preset 工作流以及 ResourceDispatchService/ExecutionService/ActualRecordService 没有 family 外的生产执行 caller，主要剩内部调用、测试、lazy exports 和 [_frozen_import_anchor.py:22](/Users/lurenxing/GitHub/----/web/bootstrap/_frozen_import_anchor.py:22)。

判断：可按真实产品入口退役这些 workflow，先核定旧公开 API 兼容边界，迁移仍使用的共同能力，再同步 exports、冻结锚和测试。ConfigService 的 setter 仍被 [baseline 工具:65](/Users/lurenxing/GitHub/----/tools/capture_networkx_phase0_baseline.py:65) 使用，严格日历读取、报表日期常量和 critical-chain 算法也仍存活。旧 start/pause/resume 语义不能硬改成新数量报工。

## 维护与结果协议

### D18 · P2 · 实时维护准入依赖所有历史 journal

[RestoreStatusTransport:54](/Users/lurenxing/GitHub/----/web/bootstrap/workbench_system_restore_status.py:54) 查询 host；[restore_host:92](/Users/lurenxing/GitHub/----/web/bootstrap/workbench_system_restore.py:92) 读全部 journal 后判断 pending；[system_journal.py:81](/Users/lurenxing/GitHub/----/core/services/workbench/facts/system_journal.py:81) 逐份读取、解析及验证终态历史。N 份历史意味着每个进入该路径的普通请求读 N 份记录，系统页面还有自身捕获。

建议拆清实时 admission 与历史查询，或请求内复用一份观察。启动前、维护接受前和恢复过程的阻断有实际用途；不能靠跨请求长期缓存隐藏新的恢复状态。这比已修的“单次 records 多次枚举”更上一层：当前每次请求仍需要全部过去的终态记录。

### D19 · P2/P3 · 正常结果跟踪从 request 精确查询切成全历史 job 查询

[SystemMaintenanceWorkspace.jsx:22](/Users/lurenxing/GitHub/----/frontend/workbench/app/SystemMaintenanceWorkspace.jsx:22) 已保留原 request key，拿到 job_ref 后却改传 job；[SystemMaintenanceAPI.js:223](/Users/lurenxing/GitHub/----/frontend/workbench/app/SystemMaintenanceAPI.js:223) 改用 /jobs/。[system_actions.py:56](/Users/lurenxing/GitHub/----/web/routes/workbench/system_actions.py:56) 和 [停止宿主查询:97](/Users/lurenxing/GitHub/----/web/bootstrap/workbench_system_restore_status.py:97) 因而全读 journal，而 /results/<request_key> 已支持只读一份文件。

判断：正常跟踪可以始终用原 request key，避免 1→N 文件读取及无关坏记录干扰查询。手工输入 job 编号的查询保留，无需新增反向索引框架。

### D20 · P2/P3 · 创建/删除备份还计算无比较消费者的整文件 SHA

[system/files.py:49](/Users/lurenxing/GitHub/----/core/services/workbench/system/files.py:49) 删除前读取整份备份，111 行创建后读取整份备份，摘要只进入展示字段。真正的 _require_source 比较位于 [system/restore.py:29](/Users/lurenxing/GitHub/----/core/services/workbench/system/restore.py:29)，后续恢复签发自己的新来源摘要，不使用创建/删除记录的摘要。

建议按动作定义 target：普通 create/delete 保留文件身份、选中签名与结果，恢复保留真实 target/protection 内容比较。此前已删除的恢复终态整库 SHA 不再算新问题。本轮未计算任何新 SHA。

### D21 · P3 · 单次系统结果签发无人回传的 query token

[system_context.py:92](/Users/lurenxing/GitHub/----/web/routes/workbench/system_context.py:92) 对配置、维护结果和 job 查询计算完整 data 指纹，注册 900 秒 query context。resolve_context 的实际消费者只有 config/create/file/backup，没有 query。[SystemMaintenanceAPI.js:221](/Users/lurenxing/GitHub/----/frontend/workbench/app/SystemMaintenanceAPI.js:221) 结果跟踪用 request/job，返回 data 后丢弃 meta；配置保存使用另一个真实 write_token。

停止/恢复模式已在 [workbench_system_restore_status.py:70](/Users/lurenxing/GitHub/----/web/bootstrap/workbench_system_restore_status.py:70) 使用简单 request ref。建议统一 point 结果 metadata，删除无消费者的 registry 状态。集合分页、导出、配置写入 token 和 restore generation 各有消费者，保留。

## 前端读取、派生计算与状态发布

### D22 · P2 · 现场准确任务定位先读一份无人使用的第一页

[FieldAPI.js:23](/Users/lurenxing/GitHub/----/frontend/workbench/app/FieldAPI.js:23) 删去 task/operation 先读第一页，29 行再读目标页。实际入口 [FieldWorkspace.jsx:7](/Users/lurenxing/GitHub/----/frontend/workbench/app/FieldWorkspace.jsx:7) 不消费第一份数据；[execution.py:42](/Users/lurenxing/GitHub/----/web/routes/workbench/execution.py:42) 已支持一次查询定位任务所属页，并核对工序。

建议准确任务深链接一次定位，保留目标归属和范围验证。只有页码、没有准确任务的第 2 页以上恢复仍需先建立快照，不能机械去掉所有首轮查询。本项不同于此前修复的单次 cohort 内部重读。

### D23 · P2 · 任意滚动触发全站数字控件扫描和刷新

[main.jsx:196](/Users/lurenxing/GitHub/----/frontend/workbench/app/main.jsx:196) 全站挂载数字控件；[WorkbenchNumberControls.jsx:158](/Users/lurenxing/GitHub/----/frontend/workbench/app/WorkbenchNumberControls.jsx:158) 捕获全部滚动，123 行查询整个 body，131 行无条件刷新所有输入的控件、位置、标签及步进值。

纯 Node VM：100 个数字框，一次无关表格滚动触发一次全 body 扫描和 100 次刷新。建议区分控件登记与位置/值刷新，滚动只处理相关已登记控件。动态挂载、原生步进、直接输入和尺寸变化处理保留；未测实机滚动帧率。

### D24 · P2 · 工作区 history 写入绕过公共滚动节流

[main.jsx:120](/Users/lurenxing/GitHub/----/frontend/workbench/app/main.jsx:120) 使用 [WorkbenchNavigation.js:198](/Users/lurenxing/GitHub/----/frontend/workbench/app/WorkbenchNavigation.js:198) 的 200ms 节流；[ReportWorkspace.jsx:35](/Users/lurenxing/GitHub/----/frontend/workbench/app/ReportWorkspace.jsx:35) 每帧更新位置，再经 [WorkbenchPageContext.jsx:5](/Users/lurenxing/GitHub/----/frontend/workbench/app/WorkbenchPageContext.jsx:5) 直接 replaceContext/replaceState。实际甘特 120/272 行同样更新，108 行发布快照。

Navigation 的纯 VM：60 次位置快照更新，在公共 timer 执行前已直接 replaceState 60 次，flush 再写 1 次。建议统一发布 owner 和节流，保留业务选择、精确视口恢复、导航和 pagehide 前立即保存，不能删除工作区状态来减少写入。

### D25 · P2 · 实际甘特重复计算不变的布局与指标

[ActualGanttWorkspace.jsx:106](/Users/lurenxing/GitHub/----/frontend/workbench/app/ActualGanttWorkspace.jsx:106) 的 useMemo 依赖整个 view；[ActualGanttModel.js:38](/Users/lurenxing/GitHub/----/frontend/workbench/app/ActualGanttModel.js:38) 和 73 行只需要筛选、分组、折叠。关闭 onlySelected 时，选中任务、报工详情、详情和链开关不影响布局，但仍重新计算。

VM 的 1000 任务在仅改这些显示状态后布局完全相同，两次均重新遍历 1000 次点任务检查。Workspace 186 行每次 render 又调用 metrics(data)；Model 175 行对同一数据做 3 次 filter，1000 任务一次计算读取 execution_state 3000 次，滚动/悬停 render 也再次调用。

建议收窄布局依赖，指标按 data 身份 memo，当前响应内共用标签和任务索引。无需跨响应长期缓存。

### D26 · P2/P3 · 逐行查同一数组，响应内部缺少共同索引

| 入口 | 重复 | 收敛边界 |
|---|---|---|
| [TrialContract.js:120](/Users/lurenxing/GitHub/----/frontend/workbench/app/TrialContract.js:120) | 每条历史 tasks.find；任务上限 10000，历史全部返回 | 一份响应内 task Map，保留 owner 归属 |
| [BatchContract.js:72](/Users/lurenxing/GitHub/----/frontend/workbench/app/BatchContract.js:72) | 批量每行 refs.includes；5000 条完整成员约 1250 万次元素比较 | 一份 input Set，仍完整核对成员 |
| [PlanContract.js:260](/Users/lurenxing/GitHub/----/frontend/workbench/app/PlanContract.js:260) | 每项占用重新找 calendar.resources | 本份班表 index，保留容量依据 |
| [ProcessContract.js:88](/Users/lurenxing/GitHub/----/frontend/workbench/app/ProcessContract.js:88) | groupCycle 每次 groups.find，提交与显示多个消费者调用 | 本份 entity group Map，保留来源/周期规则 |

ResourceTableFilter 目前已使用 memo Set；它未使用的 checked() 不算真实热路径。不能把每个 find 都独立建一层缓存。

## 宿主门禁与交付设计

### D27 · P2 · 同一 command 协议有四套 normalization，规则已经分歧

[quality_gate_shared.py:450](/Users/lurenxing/GitHub/----/tools/quality_gate_shared.py:450)、[long_gate_manifest.py:95](/Users/lurenxing/GitHub/----/tools/long_gate_manifest.py:95)、[long_gate_fingerprint.py:305](/Users/lurenxing/GitHub/----/tools/long_gate_fingerprint.py:305) 和 [run_quality_gate.py:382](/Users/lurenxing/GitHub/----/scripts/run_quality_gate.py:382) 分别解释 command。真实消费者为 manifest/receipt、分类 entry、fingerprint、失败续跑及完整计划。

纯 AST 探针：缺 output_policy 时前三者为 exact，runner 为 normalized；" NORMALIZED " 在 runner 不转小写；非法值在 shared/manifest 回 exact，fingerprint/runner 保留非法值。当前正式 plan 显式写明 policy，没有确认正式门禁因此失败。

判断：身份语义已经不统一，新增字段规则要同步四处。建议现有共同入口规范化一次，分类、执行、receipt、fingerprint 消费同一 canonical command；不同缓存身份、scope 与输出策略继续保留。

### D28 · P2 · 两份 Inno 关键实现靠同步清单和验证脚本补偿

[aps_win7.iss:70](/Users/lurenxing/GitHub/----/installer/aps_win7.iss:70) 与 [aps_win7_legacy.iss:68](/Users/lurenxing/GitHub/----/installer/aps_win7_legacy.iss:68) 分别维护数据目录、迁移、停机和清理。逐行比较主文件 800 行、legacy 796 行，787 行相同。[SYNC_CHECKLIST.md:7](/Users/lurenxing/GitHub/----/installer/SYNC_CHECKLIST.md:7) 要求逐字同步，[verify_installer_iss_sync.py:20](/Users/lurenxing/GitHub/----/tests/gate_meta/verify_installer_iss_sync.py:20) 又逐例程核对；[package_win7.ps1:542](/Users/lurenxing/GitHub/----/.limcode/skills/aps-package-win7/scripts/package_win7.ps1:542) 和 603 行都实际编译。

建议共享 Inno include/主体，两个入口只定义包名、输出名、浏览器停止与文案差异。legacy 卸载停止内置浏览器、主包不停止独立浏览器是实际差异，必须保留。

### D29 · P2/P3 · 四个主题 proof 重复维护共同执行事实协议

[run_quality_gate.py:1772](/Users/lurenxing/GitHub/----/scripts/run_quality_gate.py:1772)、[1838](/Users/lurenxing/GitHub/----/scripts/run_quality_gate.py:1838)、[1929](/Users/lurenxing/GitHub/----/scripts/run_quality_gate.py:1929)、[2023](/Users/lurenxing/GitHub/----/scripts/run_quality_gate.py:2023) 分别构造 startup、required、ledger、static proof。AST 核对四个生产器共 272 行，共享 27 个顶层字段，重复构造 run/index、command、fingerprint、退出状态和日志身份。

[2173](/Users/lurenxing/GitHub/----/scripts/run_quality_gate.py:2173) 真实准备这些文件；[long_gate_cache.py:400](/Users/lurenxing/GitHub/----/tools/long_gate_cache.py:400)、[428](/Users/lurenxing/GitHub/----/tools/long_gate_cache.py:428) 主要消费整文件完整性和声明路径，多数共同字段没有另一套独立判定消费者。

建议共同执行事实只构造一次，各主题补目标列表、台账计数等差异。先保留输出路径及缓存失效合同。本项是多份生产协议，不能直接删 proof 文件或删真实输出核对。

## 调查中发现的相邻真实问题

这些不是“删掉多余保护”即可解决的问题，应按职责修复。

### B01 · P2 · 诊断重复投影丢失已确认事实

[schedule_delay_diagnosis_service.py:261](/Users/lurenxing/GitHub/----/core/services/scheduler/schedule_delay_diagnosis_service.py:261) 生成 ConfirmedFact.text；[delay_diagnosis_presentation.py:61](/Users/lurenxing/GitHub/----/core/services/report/delay_diagnosis_presentation.py:61) 的 _public_item 不带 confirmed_facts，114 行 _check_info 却读取它。真实 DTO 的内存探针给定事实和建议，导出“核对信息”只有建议，事实不在导出行。

建议公开诊断表达包含事实文本，页面与导出共用。不能因为后续没读到，就删除原本有用途的 ConfirmedFact。报告 trace_meta 的多个字段也由同一 DTO 链生成后丢弃，应逐消费者整理。

### B02 · P2 · 自动维护配置仍显示生效，但驱动跳过工作台

[factory.py:368](/Users/lurenxing/GitHub/----/web/bootstrap/factory.py:368) 是 run_if_due 唯一生产 caller，明确跳过 workbench.* 和 /api/workbench；static/health 318 行提前返回。三个运行期任务仍在 [system_maintenance_service.py:80](/Users/lurenxing/GitHub/----/core/services/system/system_maintenance_service.py:80)。[SystemMaintenanceConfig.jsx:45](/Users/lurenxing/GitHub/----/frontend/workbench/app/SystemMaintenanceConfig.jsx:45) 却告诉用户打开页面会检查备份和清理。

判断：工作台 API 请求不会驱动这三个任务，旧地址的跳转请求却可能触发；运行期自动维护责任没有跟随页面退役迁移。应交给实际 runtime 的明确维护 owner，并同步真实生效说明；正常退出备份是另一项职责。未进行真实库自动维护实验。

### B03 · P2 · 通用 multipart 工具对新输入沿用固定历史验收背书

[portable_delivery.py:49](/Users/lurenxing/GitHub/----/scripts/portable_delivery.py:49) 接受任意 payload/volumes/sevenzip，仅检查实际包体。生成 README 的 [111](/Users/lurenxing/GitHub/----/scripts/portable_delivery.py:111) 行固定宣称与 d1307cb8、2026-09-27 已验收程序完全相同，117 行固定 7-Zip 26.03，121/131 行写到新交付材料。

判断：再次用通用 CLI 包装新程序或其他解压工具，就会继承不成立的旧验收声明。默认 PS portable 流程不调用它，不能据此判当前默认 ZIP 已出错。建议通用部署说明只表达操作与实际材料，历史验收保留历史归属，新包引用自身验收记录；无需添加哈希或版本保护框架。

## 低优先收敛项与需要保留的取舍

| 编号 | 证据 | 判断 |
|---|---|---|
| S01 · P3 · lineage 出生状态两份 | [lineage_repo.py:162](/Users/lurenxing/GitHub/----/data/repositories/workbench_template_lineage_repo.py:162) instance_snapshot 与出生事件完整 STATE_COLUMNS；[template_lineage_query.py:58](/Users/lurenxing/GitHub/----/core/services/scheduler/template_lineage_query.py:58) 比较 | 新证据版本可以出生事件为正文权威；origin 保留 birth_event_id、来源绑定和完整性摘要。模板快照、变更链、撤回和资格不能删。 |
| S02 · P3 · 校准 suggestion 重复 | [adoption_evidence.py:42](/Users/lurenxing/GitHub/----/core/services/workbench/calibration/adoption_evidence.py:42) snapshot 已含；[adoption_repo.py:64](/Users/lurenxing/GitHub/----/data/repositories/workbench_calibration_adoption_repo.py:64) 顶层再存 | 同一 durable evidence 位置收口；样本、前后状态和锁定审计被报工撤销检查实际消费，保留。 |
| S03 · P3 · 校准旧索引 | [template_lineage_calibration.py:14](/Users/lurenxing/GitHub/----/core/services/workbench/calibration/template_lineage_calibration.py:14) samples_by_part 只有两个内部测试使用 | 当前产品使用 samples_by_template/unbound_samples_by_part。可删旧索引；只是列表引用，不是完整样本正文复制。 |
| S04 · P3 · 试调采用 header 两读 | [adoption_validation.py:43](/Users/lurenxing/GitHub/----/core/services/workbench/trial/adoption_validation.py:43) → trial_policy.load_scenario → [trial_scenario_archive.py:30](/Users/lurenxing/GitHub/----/core/services/workbench/facts/trial_scenario_archive.py:30) 再读相同 header | 不可变场景的 header/snapshot 可内部共享；永久行及历史回执核对保留。 |
| S05 · P3 · Dashboard States 历史投影 | [dashboard_repo.py:65](/Users/lurenxing/GitHub/----/data/repositories/workbench_dashboard_repo.py:65) 与 History 双写；[dashboard/policy.py:52](/Users/lurenxing/GitHub/----/core/services/workbench/dashboard/policy.py:52) 每次读取仍对 history tails | 当前 state 可从历史推出，但 materialized state 有索引访问和完整性价值；正常写路径未发现漂移。只有明确查询收益和历史完整性替代后才考虑迁移，不能直接判整张表无用。 |
| S06 · P3 · preview/download 多个同形类 | [workbench_material_file.py:136](/Users/lurenxing/GitHub/----/core/models/workbench_material_file.py:136)、[workbench_resource_action.py:46](/Users/lurenxing/GitHub/----/core/models/workbench_resource_action.py:46) 同形 envelope；[resource_action_context.py:161](/Users/lurenxing/GitHub/----/web/routes/workbench/resource_action_context.py:161) 只消费 download 四字段 | 共用小型 envelope/download value 即可；各领域行、action namespace 和错误文案仍分开，不加泛型框架。 |
| S07 · P3 · v2 basis 两轮准备 | [v2_features.py:62](/Users/lurenxing/GitHub/----/core/services/scheduler/run/optimizer/graph/v2_features.py:62) 的两个 builder 重复 opmap、duration、family、ranks、seed | 同份基础事实可一次构建；不同 offset、due、window 基准保留。 |
| S08 · P3 · stats 快照再 merge 双 deepcopy | [algo_stats.py:21](/Users/lurenxing/GitHub/----/core/algorithms/greedy/algo_stats.py:21) snapshot 复制，77 行 merge 再复制 | 明确 owned transfer 的组合入口少复制一次；公开 snapshot 的独立副本合同保留。 |
| S09 · P3 · 恢复结果丢失后用可变旁路补回 | [backup_restore.py:30](/Users/lurenxing/GitHub/----/core/services/system/backup_restore.py:30) 失败只给 message/category；[system/restore.py:14](/Users/lurenxing/GitHub/----/core/services/workbench/system/restore.py:14) 保存 restore_result/rollback_result，57 行三路选择 | 每条 outcome 携实际结果，去掉补偿旁路；未发现当前错误放行。阶段留痕及 target/protection 验证保留。 |
| S10 · P3 · 普通请求生命周期多份 | [TrialSession.js:4](/Users/lurenxing/GitHub/----/frontend/workbench/app/TrialSession.js:4)、[RunCandidateWorkspace.jsx:5](/Users/lurenxing/GitHub/----/frontend/workbench/app/RunCandidateWorkspace.jsx:5) 及 RunHistory/Report/Calibration/System/RunBaseline Controls 独立写 useQuery；[RunCandidateAPI.js:226](/Users/lurenxing/GitHub/----/frontend/workbench/app/RunCandidateAPI.js:226) 等独立写 exchange | 共用取消、超时、MIME 和清理等小职责。领域验证、unknown commit、恢复、拒绝语义分开；没有因此多发请求的证据。 |
| S11 · P3 · Blob 保存重复 | [ReportAPI.js:88](/Users/lurenxing/GitHub/----/frontend/workbench/app/ReportAPI.js:88)、[CalibrationAPI.js:136](/Users/lurenxing/GitHub/----/frontend/workbench/app/CalibrationAPI.js:136)、[MasterOverviewAPI.js:54](/Users/lurenxing/GitHub/----/frontend/workbench/app/MasterOverviewAPI.js:54)、[SystemMaintenanceAPI.js:247](/Users/lurenxing/GitHub/----/frontend/workbench/app/SystemMaintenanceAPI.js:247)、[FieldContract.js:99](/Users/lurenxing/GitHub/----/frontend/workbench/app/FieldContract.js:99)、[ResourceMaterialContract.js:131](/Users/lurenxing/GitHub/----/frontend/workbench/app/ResourceMaterialContract.js:131) | URL、临时链接和 revoke 可以共用；MIME、文件内容、身份、范围、行数留在领域边界。未证实下载故障。 |
| S12 · P3 · 空样式组件 | [PlanLayout.jsx:3](/Users/lurenxing/GitHub/----/frontend/workbench/app/PlanLayout.jsx:3)、TrialStyles、TrialAdoptionHistoryStyles、WorkbenchCaption 及多份 Controls.Styles 返回 null 且无副作用，仍挂载/发布 | 当前样式已由 CSS/模板发布，可清理空调用、导出和 build-order。WorkbenchControlStyles 维护主题 CSS 变量，必须保留。 |
| S13 · P3 · API 内信封重复校验 | [DashboardAnalysisAPI.js:26](/Users/lurenxing/GitHub/----/frontend/workbench/app/DashboardAnalysisAPI.js:26)→43；[TrialAPI.js:47](/Users/lurenxing/GitHub/----/frontend/workbench/app/TrialAPI.js:47)→[TrialAdoptionHistoryAPI.js:6](/Users/lurenxing/GitHub/----/frontend/workbench/app/TrialAdoptionHistoryAPI.js:6) | API 内一次 envelope，领域数据和查询归属继续核对。旧 7.5 的 [DashboardCandidates.jsx:47](/Users/lurenxing/GitHub/----/frontend/workbench/app/DashboardCandidates.jsx:47)/54 仍重做整份 workspace，应归原问题残留，不能删 run_ref 归属检查。 |
| S14 · P3 · 同页 pending 发布又读存储 | [TrialAdoptionState.js:22](/Users/lurenxing/GitHub/----/frontend/workbench/app/TrialAdoptionState.js:22)→52、[CalibrationAdoptionState.js:23](/Users/lurenxing/GitHub/----/frontend/workbench/app/CalibrationAdoptionState.js:23)→44、[DashboardSession.js:19](/Users/lurenxing/GitHub/----/frontend/workbench/app/DashboardSession.js:19)→26、[OutsourcingSession.js:26](/Users/lurenxing/GitHub/----/frontend/workbench/app/OutsourcingSession.js:26)→33、[RunAdoptionAPI.js:97](/Users/lurenxing/GitHub/----/frontend/workbench/app/RunAdoptionAPI.js:97)→[RunAdoptionAction.jsx:19](/Users/lurenxing/GitHub/----/frontend/workbench/app/RunAdoptionAction.jsx:19) | 已 readback 的值可随同页事件发布；跨 tab 新读、写前 compare/readback 保留。DashboardSession:61 连续 read 两次可合并；归旧 7.6 共同语义扩展。 |
| S15 · P3 · 旧辅助与重复小规则 | [runtime_log_reader.py:219](/Users/lurenxing/GitHub/----/core/services/system/runtime_log_reader.py:219) 的 raw ZIP 未找到生产 caller；[SystemJobStateQueryService:12](/Users/lurenxing/GitHub/----/core/services/system/system_job_state_query_service.py:12) 的 op_logger 无消费；[readiness.py:16](/Users/lurenxing/GitHub/----/core/services/workbench/resource/readiness.py:16) 重验共同 workflow；[BatchMaterialService:60](/Users/lurenxing/GitHub/----/core/services/material/batch_material_service.py:60) 旧写方法剩测试/导出；[operations.py:18](/Users/lurenxing/GitHub/----/core/services/workbench/batch/operations.py:18) 与 [lineage.py:59](/Users/lurenxing/GitHub/----/core/models/workbench_template_lineage.py:59) 重写同一 operation code 公式 | 按真实引用退役或共用。脱敏日志窗口、诊断读取、公开兼容约束与内部 backup 失败阻止 cleanup 继续保留。 |

## 已核对而不应按冗余删除

- admission 与 current 是不同时间事实；原始与调整安排、before/after、历史模板、样本防撤销和 awaiting_reconciliation 各有职责。
- command replay 在锁前和锁内的两次查询解决真实竞态；最终采用前后两个 guard、独立公开 API/未知 adapter 的检查有不同边界。
- read_snapshot 的 write stamp、data_version 及 retry 不是同一个条件。不能删其中之一伪称“一次检查够了”。
- Schema 的复合父键 UNIQUE 支持复合 FK；机器主工种与额外 MachineOpTypes、供应商 legacy 与 explicit capability、库存与到料及日期阶段分别有语义。当前 v38 结构未发现新的完全重复索引。
- 正式计划/执行时钟、tombstone、source/row/task 身份保护不同历史和新鲜度。RunJob 加 terminal receipt 承担恢复，不是可随意合并的两套状态。
- 文件 journal 与 SQLite 审计、双进程身份、HTTP 与 worker 停止屏障、保护副本、隔离验证与原子替换承担不同职责。
- draft 与服务器结果、最后成功响应与刷新状态、pending 与确认回执、甘特视口与页面滚动分别有用途。前后端各自验证、跨 tab 保护及已明确的历史兼容不能整体移除。
- Calendar policy、segments 与 prefix cache，计时、native witness、IG 有界缓存、solution pool、decode 与候选容量上限有实际使用。
- thin re-export/facade、冻结模块可达性与真正业务 implementation 不等价。不能因 facade 文件多就认定执行两遍。
- 当前 receipt/log 与持久缓存 log 保留周期不同，下一轮会清理当前日志，不能把缓存共指到将被删除的路径。daily/final 的精确 HEAD 缓存与 long-gate 按输入跨 HEAD 复用也有不同用途。
- quality_gate_support 是稳定外观而非第二份实现；schema2 历史读取、真实文件/日志/输出/cache 绑定保留。fingerprint 镜像字段与 source/version 清单最多是 P3 整理项，未确认漏检，不为合表扩大失效范围。
- BAT/PS 的 Main_Setup 渠道可作 P3 入口收敛；README 已区分 BAT 部分构建与 PS 完整验收，不能把已有 build-only 入口报成验收失败。

## 覆盖、证据与交付边界

- 全项目从 core、data、web、frontend/workbench/app、scripts、tools 入口做目录盘点、AST/文本检索和引用链追踪。盘点为 1534 个源目录文件：core 952、data 100、web 147、frontend 243、scripts 20、tools 72；这不表示逐行读完了全部文件。
- 数据结构分区核对当前 v38：86 张表、84 个 named index、208 个 trigger，并追查父键、永久身份和写入消费者。算法分区覆盖算法、optimizer、scheduler、report/common/shared 的模式与疑点链；前端覆盖全部 app JS/JSX 的静态模式及生产视图入口，API 子分区细查 44 个脚本。
- 宿主分区核对 quality-gate 计划、执行/续跑、proof/cache/summary、hook、台账及 Windows 打包/安装主链。command 规则通过纯 AST 探针核对，Inno 通过文本逐行比较；未运行编译或门禁。
- 对确认点运行纯内存 Python/SQLite spy、AST 对比及 Node VM 计数。重复字节是合成对象序列化计量；SQL 次数不是物理磁盘次数；DOM/history 调用次数不是实机延迟。没有证据证明当前数据库已经达到 64 MiB 档案上限。
- 没有运行真实排产、迁移、恢复、业务数据库写入、安装发布、重建 static、全量门禁或浏览器验收；没有新增 SHA、hash 清单、证明缓存或测试脚本。生成静态/vendor 文件、外部消费的旧 API、实际 Win7 运行效果未做独立动态验收。
- 本次文档验证只覆盖 frontmatter、引用路径/行号及报告差异。工作区已有此前修复的改动，不声明 clean-worktree proof，也不把之前验证冒充此次新方案实施通过。

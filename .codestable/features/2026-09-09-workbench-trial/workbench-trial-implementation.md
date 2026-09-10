---
doc_type: feature
status: implemented
created: 2026-09-09
feature: workbench-trial
summary: 持久试调草稿与真实约束后端，按已批准跨模块合同第7节实施
tags: [workbench, trial]
---

# 接入合同

## v27 DDL 已冻结

`objects()` 共18对象：5表、1索引、12触发器。对其运行
`sha256(json.dumps(objects(), sort_keys=True, separators=(',', ':')).encode())`
得到 `f025c779d645c7a39666681c0c285eddf119a172cb93e339809e44282b972164`。
主线负责真实26到27迁移；本slice不改schema.sql/版本/迁移注册。后续如需变DDL必须先通知主线。

## 后端与前端 Hook

- 独占新增文件；不修改旧 scheduler、shared、plan、candidate、adoption、UI、registry、build。
- `core.infrastructure.workbench_trial_schema`: `objects()`、`contract_issues(conn)`、`install(conn)`；主线在统一迁移事务安装，不自动修表、不改版本。
- `core.services.workbench.trial.WorkbenchTrialService`: `preview_create(input)`、`create(input, write_token, request_key)`、`get(draft_ref)`、`change(draft_ref, input, write_token, request_key)`、`save(...)`、`discard(...)`、`scenario(scenario_ref)`、`lookup(request_key)`。
- `web.routes.workbench.trial.register_trial_routes(bp)`，前缀 `/api/workbench/v1/trial`。依赖原 `g.db`、`issue_write_context`、`validate_write_context`，不自行注册主应用。
- 创建输入：`{base:{plan_ref:永久引用}|{candidate_ref:永久引用},scope?:{range_start?,range_end?,batch_refs?,resource_type?,resource_ref?,query?}}`。scope保存原页面范围，完整基础计划任务始终保留，不按显示范围截断。
- 调整输入：`{task_ref,machine_ref,operator_ref,start}`。两种资源必须显式提供；外协显式null；工时与身份不接受前端覆盖。
- 草稿task_ref/row_ref独立且永久；source_task_ref保留原正式任务，candidate只有source_row_ref，绝不冒充plan_ref/task_ref。
- 保存 `{name}`，放弃 `{confirm:true}`；场景只读快照与正式版本分离。草稿保存后关闭；冲突草稿可继续编辑或保存冲突场景，不能采用。
- Validation的`constraints_status`说明真实业务检查；`status=blocked,can_adopt=false`另列`scenario_adoption_not_connected`。本slice不挂旧publish。
- 结果未知只查询原request_key，未查到回执不证明尚在途请求不会完成，不自动重新执行。

## HTTP 接口

| 方法 | `/api/workbench/v1/trial` 下的路径 | 请求与用途 |
| --- | --- | --- |
| POST | `/drafts/preview` | 裸创建input，返回创建write_context，不创建草稿 |
| GET | `/drafts` | 有界持久草稿目录，浏览器记录丢失后仍可发现原草稿 |
| GET | `/scenarios` | 有界已存场景目录，不依赖手输永久引用 |
| POST | `/drafts` | CommandInput，创建完整持久草稿 |
| GET | `/drafts/<draft_ref>` | 原草稿及实时Validation；可选snapshot_ref，不接受重筛选 |
| POST | `/drafts/<draft_ref>/change` | CommandInput，原task_ref及显式设备/人员/开工 |
| POST | `/drafts/<draft_ref>/save` | CommandInput，`{name}`，返回永久scenario_ref与只读preview_target |
| POST | `/drafts/<draft_ref>/discard` | CommandInput，`{confirm:true}`，仅改变指定草稿状态 |
| GET | `/scenarios/<scenario_ref>` | 保存当时的完整只读场景，不用当前计划替换 |
| GET | `/commands/<request_key>` | `committed`或`not_observed`，不自动重做 |

## DTO 补充

- 根字段：`draft_ref/status/base/base_identity/scope/baseline/tasks/task_count/tasks_complete/unplanned_operations/scope_complete/validation/validation_at_last_write/write_context/resources/comparison/capacity/change_history/time_scope`。
- `tasks`含永久任务与行/源任务引用、operation_ref、批次/零件/工序/分件、source、原目标量与批次数量、优先级/交期、设备/人员/开完工、原安排、原工时依据、前序任务与工序引用、创建时/当前唯一执行投影、edit_context、issues/data_gaps。
- `comparison.basis=draft_original`，对比的是完整原试调基础，不把候选冒充当前正式基线。真实交期使用due_exclusive，坏交期/冲突/未排完整不得算按期；换型为null并说明未评估。
- `capacity`基于真实CalendarEngine/OperatorShiftCalendar，含夜班窗口、停机、资源占用并行段；表示selected_trial_only，不冒充全厂利用率。超过50000资源日时只把容量标unavailable并解释，原任务不截断。
- `change_history`保留每次原子变更前后资源/时间、Validation、永久change_ref和本机操作者；场景自身不产生正式采用记录。
- 草稿完整上限10000任务、单快照64 MiB，冲突超过50000条明确拒绝，不截断。分件用执行ledger给出的target_quantity，未知量/工时、零时长或不能无损表示的秒以下时长明确阻断。

## 有界目录增补

- 两个目录仅增加GET方法，现有写接口名称、输入字段与核心DTO稳定。仍使用同一`register_trial_routes(bp)`，目前共10个路由方法。
- 参数`page`默认1、`size`默认20且最大50、`status`默认all、成对`base_kind/base_ref`、可选`snapshot_ref`。draft状态支持editing/saved/discarded/all；scenario支持saved/all。
- `items`含display_name、status、base/base_display_name、created_at/updated_at、task_count、local_operator、open_target、detail_target；场景保留用户保存的名称和source_draft_ref。
- `page={number,size,total,pages}`统计完整筛选范围；scope绑定条件及size、不绑定页码，使同一snapshot_ref可跨页。目录有变化则snapshot_stale，不在分页时静默换范围。
- `selection=null`，不自动选最新草稿或把candidate_ref换成plan_ref。摘要只读永久头信息，不读取大份admission/snapshot JSON，也不调用live计划重建。
- `validation_state=not_evaluated`，目录不宣称约束已通过。打开指定草稿才执行其当前真实校验；已存场景读取保存时原快照。
- 完整目录超过100000头记录或32 MiB摘要，明确要求按状态/原来源筛选，不返回截断目录。实现不增加或改动任何DDL。

## 主线接点

- DDL与路由已交付主线；未改`schema.sql`、SchemaVersion、migration注册、registry、build或主UI。
- 现有`core/services/workbench/run_jobs_facts.py:capture_run_facts`采全库事实，试调表/receipt也会改变原候选facts_hash。试调写入可能使原候选普通采用报snapshot_stale；本slice未修改或绕过该共享检查。若需排除独立试调台账，由主线统一调整。
- 完整scenario正式采用由后续slice实现；本slice没有adopt/publish端点，也没有调用旧GanttAdjustmentPublishService或普通candidate adopt冒充场景采用。

# 验证进度

- 已完成旧草稿/场景/采用与symbol_locator调用核查，确认旧表缺少候选身份和完整快照合同。
- 持久层、真实日历/执行校验和路由已实施。
- Python 3.8.10下最终专属明确清单56项全部通过（34.98秒）：原生命周期/边界/原子/容量42项，加目录与冷进程恢复14项。
- 冷进程测试从持久目录发现原草稿、恢复同一draft_ref/task_ref和原安排，旧进程write_token失效；新连接`total_changes=0`。无需浏览器缓存或手输技术引用。
- 1000/10000任务的创建预览、创建、单步调整、新连接恢复均保留全部原行与引用。早期容量独立运行分别2.524/18.144秒；最终源码加入容量DTO后整套清单31.20秒。
- 旧甘特/执行/班次扩展回归76项通过；3项旧版迁移夹具受当前全仓迁移联动影响失败，已报告主线：v11残留execution触发器、v12无触发器旧断言、v13夹具lineage触发器引用被移除的表。本slice未改旧测试。
- Ruff、Python3.8语法、产品文件复杂度/大小扫描通过。完整质量门禁未运行：本任务为独占slice，共享工作区有大量在途改动，门禁生成的共享evidence/registry及迁移联动由主线统一负责。本结果不是clean-worktree proof。

最终本域命令（明确清单，不包含主线独占的trial_lineage迁移测试）：

```bash
.venv/bin/python -m pytest tests/workbench/test_trial_lifecycle.py tests/workbench/test_trial_validation.py tests/workbench/test_trial_edges.py tests/workbench/test_trial_atomic.py tests/workbench/test_trial_api_schema.py tests/workbench/test_trial_scale.py tests/workbench/test_trial_catalog.py -q --tb=short
```

## 交付边界

- 后端创建预览/创建/读取/变更/保存/放弃/场景读取/回执查询，以及两个有界目录均已可接合；17个新增产品文件，8个本域测试/support文件。
- 仍需主线完成UI接合、完整项目门禁与最终离线交付验收；完整场景正式采用保持明确blocked，不属于本slice已完成范围。
- 本任务未动预览进程或生产数据库，未stage/commit，未改旧scheduler/shared/plan/candidate/adoption/主UI/registry/build。

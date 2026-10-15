---
doc_type: refactor-apply-notes
refactor: 2026-10-15-single-pass-workflow
status: complete
validation_status: platform_deferred
created: 2026-10-15
baseline: 8096bdbbf3c04ef17ec24fa2cd19bfc71fa678b8
---

# 实施记录

- 初始 HEAD 与方案一致；已有 `开发文档/README.md` 10 行入口增补，保留且不纳入本轮提交。
- 已授权完整 P1–P8，按互不重叠的职责并行实施，完成后由原对话验收。后续明确授权本轮本地提交，用户原 README 修改保留在工作区，推送暂缓。
- 普通启动、事务事实、搜索、token、领域写入、输出和显示各归其现有拥有者。已通过且相关输入未变的验证复用。

## 已执行验证

- 命令回执迁移：`.venv/bin/python -m pytest tests/workbench/test_commands.py -q`，2 passed。后续若输入变化则重验。

## 实施状态

- P1–P7 职责、真实调用者及对应测试已接线，原对话七条独立验收轨确认的漏项已修复；产品源码与正式静态包已冻结。
- P8 已核对 72 个原编号、N1–N14 和 8 个附带口径；代表流程、真实浏览器及原生 PDF 验收已完成。全面复审与后续 IAB 确认的问题已修复，最后 Actual 关键链接入既有节点索引，全部选定独立功能已完成真实验收。
- 最终完整门禁为 **903 项收集、867 通过、0 失败、36 跳过、0 收集错误**，第 1–16 步通过；第 17 步因 15 项必需 Windows/PowerShell 启动器回归在当前平台跳过而失败，正式 manifest 保持 `failed`，平台延期。首轮 877 项/841 通过、修复前 899 项/860 通过/3 失败，以及后续 902 项/866 通过均为历史状态，分别保留，最终结果见本文末节。

## P1 已完成职责与当时验证

- 排产 DTO 移入 `run/schedule_input_contracts.py`；编排器只计算。退役 collector/persistence/candidate persistence、旧配置装配与 phase0 PoC，`ScheduleService` 保留实际工序编辑。
- 旧 resource_dispatch/GanttService/desktop PoC 与报表诊断壳退出；保留 critical_chain/task_labels、当前利用率/停机计算和 XLSX。报表消费上游已有 resolution；详情窄 DTO 与前端一起迁移。
- 以下组合有重叠，数量不相加；后续 P2/P3/P5 接线变化由整合验证覆盖，不将本批通过当作最终门禁。

```bash
.venv/bin/python -m pytest tests/algorithm/test_due_exclusive_consistency.py tests/algorithm/test_schedule_persistence_auto_assign_contract.py tests/algorithm/test_optional_ready_constraint.py tests/calendar_maintenance/test_freeze_window_bounds.py tests/schedule/service/test_schedule_service_reschedulable_contract.py tests/schedule/service/test_frozen_external_seed_metadata_integration.py tests/schedule/service/test_unselected_execution_resource_guardrails.py tests/scheduler_graph/test_scheduler_graph_cycle_policy_contract.py tests/scheduler_graph/test_scheduler_graph_report_mode_service_contract.py -q --tb=short
# 53 passed in 0.97s
.venv/bin/python -m pytest tests/workbench/test_run_jobs_atomic.py tests/workbench/test_run_candidate_adoption_atomic.py tests/workbench/test_run_compute_integration.py tests/config tests/excel_data_io/test_operator_machine_exception_paths.py -q --tb=short
# 25 passed in 3.38s
.venv/bin/python -m pytest tests/schedule/service tests/algorithm/test_due_exclusive_consistency.py tests/algorithm/test_schedule_persistence_auto_assign_contract.py tests/algorithm/test_optional_ready_constraint.py tests/calendar_maintenance/test_freeze_window_bounds.py tests/scheduler_graph/test_scheduler_graph_cycle_policy_contract.py tests/scheduler_graph/test_scheduler_graph_report_mode_service_contract.py tests/workbench/test_scheduler_execution_ledger_guards.py tests/config -q --tb=short
# 71 passed in 3.24s
python3 -m pytest -q tests/scheduler_analysis/test_plan_vs_actual_review.py tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py
# 8 passed，8 条既有 sqlite datetime deprecation warnings
node --check frontend/workbench/app/ReportAPI.js
node tests/workbench/ui_refinement_reports_review_contract.cjs
# reports-review display contracts passed
.venv/bin/python -m pytest -q tests/workbench/test_plan_task_identity_contract.py tests/workbench/test_legacy_plan_range.py tests/gantt tests/operation_execution/test_operation_execution_state_revision.py tests/operation_execution/test_operation_execution_state_flow.py tests/workbench/test_execution_ledger_commands.py tests/workbench/test_field_workspace_api.py tests/workbench/test_import_source_content.py
# 32 passed（P1 当时状态；P5 后续继续迁报工）
```

## 整合进展

- P1 已由原对话三条独立轨复核；冷启动测试移除退役服务锁转导出，保留真实运行消费者共享锁断言，相关 33 项通过。
- P2 捕获/来源/批次/工艺及报工依赖复用已接；P8 又补齐试调 configuration/checks、ledger 作用域和 C13 准入 IDs 直交 completion。
- P3 已退出 graph cache、origins、报告结果重扫与平行父代；原生准备、资源增量和全部解码消费者已迁，原始输入验收通过。
- P4 token、来源对象、历史锚点和总览当前读取已接；真实独立 TTL、读token到期后仍有效的写上下文、写锁等待期间到期拒绝均有回归。试调采用目录同样收成永久身份/已有时钟；二次批量签发的共享组定位已提升到本次签发拥有者。
- P5 回执直接使用实际编码结果，worker 直接消费 claim/finish 的实际时间与 ref；试调逻辑 64 MiB 与物理列限制已统一；资源/工艺/物料/外协/日历均已完成。
- P6 全部 Plan/Actual/Dashboard/Candidate/Baseline 的准备/筛选/布局和共用 Canvas 已迁；21 项 Node/分件契约通过，正式 chrome109 静态包已构建，真实浏览器验收通过。
- P7 v43、启动/恢复/SQL 及 C25 共享结构已完成。Dashboard 结构捕获从 5 次降为 1 次，采用也是 1 次；迁移默认 fresh 保留。既有平台项 15 skipped，需 PowerShell/原生 Windows。旧纯测试 WorkbenchRunFactsRepository 已删，归档日历测试改消费当前 ProductionFactsCapture，8 项通过。
- 测试登记现 6 组 143 个 required 文件；两条已退出职责的旧 fixed 测试债务通过原写入口退役，历史保留，3 fixed/2 retired/0 active；治理一致性通过。

### HTTP 最终出口补漏与实际验证

- 最终 UTF-8 信封由 `web/api_responses.py` 编码一次并直接发送；内部 execution_workspace 门槛退出，各真实端点与文件量实际产物。回执读取直接严格解码，不再 dump 自证。
- 原对话复核发现的外协 preview 缺 8 MiB 和候选 export 丢弃 JSON 预演均已关闭，错误码、scope/token 和下载 headers 保留。
- `.venv/bin/python -m pytest tests/workbench/test_run_candidate_api.py::test_full_app_explicit_registration_only_temporary_connections tests/workbench/test_outsourcing_atomic.py::test_http_preview_enforces_its_actual_utf8_envelope_limit -q`：2 passed in 0.79s。候选现有完整应用用例验证禁止 JSON 预演及实际 CSV 字节上限；外协真实超大中文预览验证 413、零业务写入。
- `.venv/bin/python -m pytest tests/workbench/test_commands.py tests/workbench/test_dashboard_api.py tests/workbench/test_execution_plan_read_scope.py -q`：17 passed in 2.81s（后续回执严格解码和计划已解析时间交接另有相关 15 项通过）。

最终完整命令已在全部产品源码冻结后执行，真实结果见本文末节。该阶段保留用户原 README 10 行增补、尚未提交；后续本地提交授权及最终交付状态见本文末段。

### P3/P5 独立验证与整合类型收口

以下为已执行结果的集中记录，组合之间有重叠，数量不相加。

```bash
.venv/bin/python -m pytest -q tests/algorithm tests/candidate/test_shared_optimizer.py tests/candidate/test_shared_schedule_archive.py tests/candidate/test_optimizer_process_evidence.py --disable-warnings --maxfail=1
# 110 passed in 14.30s；其后仅无消费者 import 清理、局部命名及准确类型声明，行为结果复用。
.venv/bin/python -m pytest -q tests/calendar_maintenance/test_calendar_periods.py tests/calendar_maintenance/test_calendar_effective_segments.py tests/workbench/test_calendar_file_api.py tests/workbench/test_operator_calendar_api.py tests/workbench/test_calendar_period_defaults.py tests/workbench/test_archived_calendar.py tests/algorithm/test_execution_calendar_certified_overlay.py tests/candidate/test_graph_ready_capacity_facts.py tests/workbench/test_run_compute_integration.py tests/workbench/test_dashboard_read_reuse.py tests/workbench/test_resource_projection.py
# 51 passed in 2.64s；覆盖一天一个规范模型、确认重读当时事实、只取新增回执 ref、file 不取无消费者 ref、公共 policy 一次及人员覆盖。
.venv/bin/python -m pyright -p pyrightconfig.gate.json --outputjson
# 1255 files，0 errors / 0 warnings；输出 /tmp/aps-p1-annotations-pyright.json。
.venv/bin/python -m pytest -q tests/workbench/test_execution_ledger_commands.py tests/workbench/test_field_workspace_api.py tests/scheduler_analysis/test_plan_vs_actual_review.py
# 15 passed in 1.84s；准确表达已有只读作用域和选中计划合同，无新增运行检查。
```

- 原始 `SimpleNamespace` 入口由现有 `run_optimizer_proof_harness()` 实际执行：`status=passed`、1 case、`blockers=[]`，证明原始输入入口在共享准备迁移后仍可用。
- 最终类型收口发现分件确认把 `BatchCommandOutcome` 覆盖为 `BatchMaterial` 的真实错误。修为各自具名结果，实际分件 API 回归覆盖预检、确认、回执、源/子批数量、物料守恒和工序绑定，相关 11 项通过；局部正式 Pyright、Ruff 与差异检查通过。

### P8 独立验收回修

- **批量 token：** 原登记表的共享反向索引由本次 issuer 定位一次，批次列表与同工序报工/任务两个真实批量入口共用；逐行只查 subject/actions 小键。100 行、第二份内容相同但对象不同的事实，实际输出 `shared_facts_equalities=1`、`tokens_reused=true`；空索引组沿原清理退出，独立到期与 LRU 保持。
- **工艺导出：** 直接持有 document 与 `ReadBinding`。原列表 token 在 1000 签发、导出在 1800 签发，1901 下载 route/hours 成功；导出自身在 2701 过期继续拒绝。退出 binding JSON 和下载时重新解析旧列表 token。
- **报工依赖与拒绝：** 去重 missing 后按 `MAX_OPERATIONS=10000` 分块，同一账本快照供各块消费。真实 SQLite 两批各 6000 依赖加 2 个目标的读取组为 `[2, 10000, 2000]`，无重复工序、当前计划读取 1 次，预览无报工写入。`ledger_read_snapshot` 只翻译进入账本快照时的拒绝，业务 `execution_protected` 原样交回；账本自身读取错误仍由 adapter 翻译。
- **试调资格：** 当前 capture 的 `CapturedResourceFacts` 直接交 `TrialValidator`；同 O1/M1 跨 T1/T2 的四态与原 SQL 服务逐任务对照，校验中禁止再次调用技能/授权 SQL。实际历史资源继续豁免当前已撤销的资格/授权。
- **解码与批序：** 保持机器判空、工时、人员资格的原顺序；固定资格仍由同一准备对象按实际机器懒准备。批序直接消费 `native_preparation.batches`，退出第二次规范化。
- **日历身份与旧试调大小：** 人员日历新增回执两处复用原 `entity_key`，真实 `OP:1`/`OP%1` 创建均成功。旧 pretty 包装只在已识别旧布局分支规范计量任务；恰好逻辑上限通过、少 1 字节拒绝。新规范片段继续累计原字节，回归禁止对新格式重编码或自比较。
- **界面事实与打印：** IME 组合输入的 Enter 保留输入法行为，普通 Enter/按钮提交保持；资料详情移除旧 selected 证据重复块，只展示本次 detail 事实。显式 printing 时 Canvas 挂载/更新同步绘制并取消待执行屏幕帧，屏幕绘制继续合帧。19 项现有 Node 契约通过，最终静态包 `built / files=10 / target=chrome109`。

本批已执行的相关组合如下，后续完整门禁另列，不累加重复节点：

```bash
.venv/bin/python -m pytest tests/workbench/test_direct_page_snapshot.py tests/workbench/test_batch_actions.py tests/workbench/test_field_workspace_api.py tests/workbench/test_process_file_api_transactions.py tests/workbench/test_preflight_api.py tests/workbench/test_run_jobs_atomic.py tests/workbench/test_execution_ledger_commands.py tests/workbench/test_field_report_void_api.py -q --tb=short
# 42 passed in 5.95s。
.venv/bin/python -m pytest -q tests/workbench/test_execution_ledger_commands.py tests/operation_execution tests/workbench/test_field_workspace_api.py tests/workbench/test_field_report_void_api.py tests/workbench/test_scheduler_execution_ledger_guards.py
# 21 passed in 4.49s；此前 ledger commands + trial protected 节点 10 passed in 2.38s。
.venv/bin/python -m pytest -q tests/algorithm/test_auto_assign_fixed_operator_respects_op_type.py tests/algorithm/test_sgs_internal_scoring_matches_execution.py tests/algorithm/test_decode_checkpoint_content_evidence.py tests/candidate/test_shared_optimizer.py --disable-warnings --maxfail=1
# 18 passed in 2.11s。
.venv/bin/python -m pytest -q tests/calendar_maintenance/test_calendar_periods.py tests/calendar_maintenance/test_calendar_effective_segments.py tests/workbench/test_calendar_file_api.py tests/workbench/test_operator_calendar_api.py tests/workbench/test_calendar_period_defaults.py tests/workbench/test_archived_calendar.py
# 22 passed in 1.89s。
```

- 试调资格相关组合 20 项通过，原 `execution_protected` 失败节点在 adapter 收口后通过；试调存读/工时/采用组合 13 项通过（2.86s）。所有相关产品文件均按正式配置完成局部 Pyright、Ruff 和差异检查。
- 本轮新场景均扩充现有已登记测试文件，真实新增节点随 full pytest 收集；不为审计编号另建测试套件。


## 代表流程

- 在 P3 解码负责人确认源码冻结后，仅执行一次 858 工序代表流程。原件为 `evidence/mac-four-candidate-run-20261013/initial.db`，以 `mode=ro` 源连接执行 SQLite backup 到独立临时库；现场核对 31 零件、93 批、858 工序全部 pending，正式计划、候选、报工与试调均为空。副本经正常 Schema 39 → 43 迁移，原件和历史 evidence 保持。
- 复用保存的 93 批输入（2026-10-12 至 2026-12-06），保持 `improve`、`min_overdue`、30 秒、graph on 等实际设置。当前生产 preflight 响应/token、preview、accept 与同步 `WorkbenchRunWorker` 共提交一次，未采用候选；计算和保存继续经过正式约束验证。运行前后配置内容相同。
- 从发起 preflight 至完整结果保存共 **14.516 秒**：preflight 0.088、preview 0.124、accept 0.205、worker 14.099 秒；其中 worker compute 14.016、persist 0.063 秒。计时含轻量调用计数，排除副本准备/迁移、服务启动和终态后的回读；本次未启动 HTTP 服务或后台 runtime，全部连接已关闭。
- 30 秒共享预算正常以 `stagnation` 结束，搜索实际 13.737 秒，超预算 0 秒，首次完整结果 0.528 秒。保存 **2 个永久业务代表**，各 858 道唯一工序、93 批完整，缺失/失败/超期均为 0；交期代表同时代表 `min_overdue`/`min_tardiness`，总工期 848.6 小时、127 次换型；`min_changeover` 代表总工期 920.5 小时、120 次换型。
- 现有过程统计为 26 次真实解码、19 个新决策、2 次决策复用、0 次解码失败；真实执行分类为 19 `new_decision`、4 `capture_checkpoints`、3 `trial_decode`。graph 准备实计 **1 次**；preflight、preview、accept、worker compute、worker persist 各持一份 capture，每份实际读取 71 张表，每表均只读 1 次。
- 本次结果只证明当前代表耗时、真实保存与准备次数。旧 31.463 秒来自 `0df8fc48` 的四候选 HTTP/轮询语义；既有 unified-30 前测来自 `7b2697a5` dirty 工作区且包含 HTTP 轮询，均未形成 `8096bdbb` 同源码/同计时边界的前后配对，因此不计算本轮加速比。
- 本次 run_ref：`657d4d55a13ade2ac76e6bf531d178f037f3fabb2c789053`；数据库记录 accepted/start/finish：`2026-10-15T16:51:51.571017` / `2026-10-15T16:51:51.655446` / `2026-10-15T16:52:05.741938`。原始脚本、stdout、结果与独立数据库保留在 `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-single-pass-858-20261015-cpnnto7o`（`run-representative.py`、`stdout.log`、`result.json`、`aps.db`）。


## 真实浏览器验收

- 使用最终 `files=10 / target=chrome109` 静态包和本机 headed Chromium，在独立 SQLite backup 副本上完成真实 UI 交互。858 工序来源是既有已保存候选；副本采用后生成正式计划，未重新排产。点事件和密集行复用现有 trial/production-report fixture，经真实采用、报工入口建立；历史候选/冻结基线另复制既有 decision 工作库。所有数据库与原资料隔离。
- Plan 858 搜索 `D261029-2` 即时得 11/858，资源分组总数一致；选择/定位、F 适配、放大、滚动、悬浮与浅深主题通过。Actual 858 同范围得 11 道工序、3 次报工、已知 0.25 小时、2 条工时待补；折叠后定位重新展开，超期筛选得 1/858，汇总同步。上述本地交互均无新增 HTTP 读取。
- Plan 密集夹具同一行 101 个区间加独立零工时点；Canvas Home/End 改变匹配任务，实际绘制区悬浮命中，缩放后 DOM/Canvas 切换、点事件选择、主题重绘和 print 媒体重绘通过。Actual 60 个分次区间加基线共 61 色块，Home/End/Enter、报工悬浮、放大/适配和打印通过，另实际点击零工时/报工时刻标记。两页打印截图与 PDF 已保存，Canvas 像素均非空。
- Dashboard 真实分析时间轴完成工序定位、任务悬浮、放大、F 适配、滚动后清除提示、深色主题与停机分析切换；定位/缩放/滚动均为本地操作，新增 HTTP 读取为 0。
- 已保存候选 31 道任务与冻结基线 15 道共同显示；operation_ref 精确搜索后候选和基线各 1，道数及原安排明细同步。基线开关、只看变化（该工序无变化，结果 0）、Canvas 键盘首末选择、缩放、打印及关联工序定位通过；关联定位清空原精确搜索并展示目标。独立正式归档页搜索 `DC-05` 得 3/15，定位与键盘通过；这些本地交互新增 HTTP 读取均为 0。
- 资料总览列筛选输入观察 650 ms 均为 0 请求；Enter 与“应用列筛选”分别提交 1 次正确 scope。空列表时导出保持可用：页面显示 0 条后，在该独立副本加入 1 条匹配零件，再直接导出，响应 `X-Workbench-Row-Count=1`，CSV 含新增行；此时旧列表仍显示 0 条。随后刷新列表显示 1 条并读到当前详情。
- 原始交互结果、截图、打印 PDF、CSV、Trace 与实例身份位于 `output/playwright/single-pass-20261015/`。关键文件：`plan-final.json`、`actual-final.json`、`plan-canvas-final.json`、`actual-canvas-final.json`、`dashboard-final.json`、`candidate-final.json`、`candidate-related-final.json`、`archived-baseline-final.json`、`master-column-filter-final.json`、`master-export-final.json`、`browser-trace.zip`。最终控制台读取为 0 errors / 0 warnings。初轮交互及模拟 print 媒体截图已目视核对；后续原生打印发现并修复的问题与同步事件证据见下。调试期间的定位器未命中记录保留原始状态，最终结果以这些 `*-final.json` 为准。
- Playwright 会话 `single-pass-p8` 已关闭；本轮临时服务 PID 77532、81302、92071、3222 全部退出，56194、56666、58205、59843 均无监听。未启动 managed run runtime，未持有用户实例锁；身份及清理结果保存在 `instance.json`。本节为 dirty 工作区定向浏览器验证，完整门禁见本记录末段。


### 原生 beforeprint 同步绘制与分页尺寸复核

- 复核使用 Chromium 原生 `Page.printToPDF`，调用前清除媒体覆盖（`media: null`）；页面后注册的 `beforeprint` 监听器直接在该同步事件内读取 DOM、像素及 Canvas 图像，无等待帧。Plan 密集页先放大至屏幕 Canvas 为 0，事件内已同步挂载 1 个非空 Canvas（80,494 个非透明像素）、2 行与 102 条任务明细；858 页从屏幕 9 行切成打印 78 行，事件内任务明细为 858。候选/冻结基线从屏幕 8 个 Canvas 切成打印 9 个，新增 1 个，全部非空；31 条候选明细、15 道基线及独立零工时点完整。
- 原生 PDF 复核发现并定量定位了共同 Canvas 入口的分页缩放问题：Chrome 打印媒体阶段 `getBoundingClientRect()` 返回纸面缩放后的尺寸。候选行 rect 为 421×28，布局 client 为 842×56、DPR 为 2；以 rect 建缓冲区得到 842×56，完整行高绘制被裁半后再放大。Plan 同样复现 rect 414×27.5、client 828×55。P6 在共同 `useCanvasPaint` 改用未缩放的 `clientWidth/clientHeight`，绘图坐标和缓冲区保持同一份布局尺寸，同时保留打印同步 draw 和取消待绘 RAF。
- 最终包原生复验：候选普通行缓冲区为 1684×112、基线为 1684×60；Plan 为 1656×110，均等于 client 尺寸乘 DPR。真实 PDF 渲染图中，候选“铣削”色块两行文字及条形完整，纵向裁切消失；Plan 密集条形完整。Actual 的现有 61 色块 Canvas 在 `beforeprint` 内同步 draw 1 次，缓冲区 1168×174、非透明像素 1,122；该项验证现有已挂载行打印，Actual 当前没有全量行打印布局能力。
- 最终证据仍在 `output/playwright/single-pass-20261015/`：`plan-native-beforeprint-final.json`、`plan858-native-beforeprint-final.json`、`candidate-native-beforeprint-final.json`、`actual-native-beforeprint-final.json`；`plan-native-geometry-fixed.json` 与 `candidate-native-geometry-fixed.json` 保存真实打印媒体阶段的 rect/client/buffer/DPR。实际 PDF 为 `plan-native-beforeprint.pdf`、`plan-858-native-beforeprint.pdf`、`candidate-native-beforeprint.pdf`、`actual-native-beforeprint.pdf`；关键目视图为 `plan-native-beforeprint-fixed-pdf-01.png`、`candidate-native-beforeprint-fixed-pdf-2.png`。修复前 PDF/几何证据保留为 `*-pre-fix*` 及原 `*-native-geometry.*`；执行脚本已同目录保存。
- 本次补充服务 PID 22222、22238、22273 全部退出，62998、63001、63006 均无监听，浏览器会话 `single-pass-print` 已关闭；清理状态追加在既有 `instance.json`。除本应用记录外，打印验收代理未修改产品文件。


## 首轮整合门禁（全面复审前）

- 最终运行命令：`.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --no-long-gate-cache`。原续跑协议检测到测试与 Canvas 源码发生变化，自动执行完整命令计划；没有调整复用判据、债务或基线。
- 最终运行身份：`8096bdbbf3c04ef17ec24fa2cd19bfc71fa678b8:2026-10-15T17:21:35`。使用项目 `.venv/bin/python`、Python 3.8.10；HEAD 仍为方案基线，工作区保留本轮改动和用户原 README 10 行。manifest 的 `tracked_drift_detected=false`，运行期间源码保持冻结。
- **第 1–16 步全部通过。** 包括 Ruff、生产/含测试导入环、全量收集、YAML、Python 3.8 兼容扫描、路由说明一致性、两套正式 Pyright、治理台账和完整 full-test-debt。
- **全量实际结果：877 个节点，841 passed、0 failed、36 setup skipped、0 collection errors。** pytest exitstatus=0；full-test-debt 状态 `passed`，active xfail=0、fixed=3、retired=2、unexpected failure=0。第 16 步耗时 181.7 秒。
- **第 17 步失败，正式 manifest 状态为 `failed`。** `verify_required_regressions_from_full_test_debt.py` 要求必需节点通过，其中 15 个启动器节点因平台条件缺失在 setup 跳过；该命令返回 1，runner 返回 2。保留实际失败状态和原平台延期。

| 跳过原因 | 节点数 | 第 17 步必需范围 |
|---|---:|---|
| PowerShell runtime is needed to execute launcher behavior | 12 | 是 |
| Native Windows direct process creation | 1 | 是 |
| Native CMD quoting and Windows PowerShell entry | 2 | 是 |
| Actual Windows PowerShell and cached offline 7-Zip are required | 1 | 否 |
| Windows exclusive listener semantics | 5 | 否 |
| Host PowerShell 7 is unavailable | 15 | 否 |

- 原始结果保存在 `evidence/QualityGate/v4/quality_gate_manifest.json`、`current_full_test_debt.json`、`full_test_debt_summary.json` 及对应 receipts/logs；总日志为 `/tmp/aps-single-pass-quality-gate.log`。第 17 步实际失败日志是 `evidence/QualityGate/v4/logs/17_python-tools-verify_required_regressions_from_fu.stderr.log`。
- 前一轮全量发现的两个夹具漏迁已关闭：Gantt 详情显式消费 `PlanGanttModel.prepare`，候选采用实际 prepare/group/select/layout；process projection 的 9 处观察复用既有 `_observe_decoded`。原只读点击、弹窗、CSV、真实目标及一次 run 断言保留。最终相关 Node/Gantt 组合 21 passed（4.30s），过程投影单文件 1 passed（0.36s）；本次完整运行均已通过。前轮原始失败结果保留 `/tmp/aps-single-pass-pre-print-gate.log` 与 `/tmp/aps-single-pass-pre-print-full-tests.json`。
- 原对话七条独立验收轨及明确回修项已收口；72 个原编号、14 个新增发现、8 个附带口径齐全。P1–P8 实施完成，V1–V7 通过，V8 记录 `deferred_platform`。平台项继续按既有 Windows/Win7 验收安排执行。
- 首轮验收时架构说明、开发说明、测试登记、设计与清单已同步。该批临时浏览器服务及会话关闭；当时未提交、推送、发布或安装，原业务数据库保持。

## 全面复审后的修复与 IAB 压力验收

2026-10-15，按新增授权重新分配全部 603 个变更路径，完成 15 组独立只读复审；原对话逐项核对后批准修复确认项 1–10，并同步过时说明 D。候选筛选保留完整分组的稳定轨道及重叠事实；两项语义不同的派生合并和跨请求字符串共享本轮保留原职责。上节全量门禁对应复审前版本，本节定向验证与后续 IAB 证据对应修复后版本。

| 项目 | 已完成的修复与实际验证 |
|---|---|
| 1 计划详情 | 对照任务使用已准备的 `beforeTime/afterTime`，普通任务使用现有 `taskIndex`。统一静态构建 `10 files / chrome109` 成功，现有真实 bundle 测试 3 项通过，覆盖范围外原安排、双向切换及普通任务。 |
| 2 令牌过期 | 签发与解析均在原锁内采时；实际等待跨过 expiry 后拒绝并零写入，已提交回执在过期后重放仍保持幂等。四文件相关组合 20 项通过，局部正式 Pyright 与 Ruff 通过。 |
| 3 日历分钟 | 共同构造先选择实际时段表示；合法新 periods 覆盖旧工时，极小正工时拒绝，明确 0 工时保留空结束，真实请求冲突继续拒绝。17 个唯一相关节点分次通过，局部正式 Pyright、Ruff 通过。 |
| 4 工艺性能入口 | 真实 caller 迁到 `read_snapshot → checked_facts → prepare_review → affected`。既有 CLI `--counts 1` 实际成功，14 阶段与报告齐全，`source_contents_unchanged=true`；结果 `/tmp/aps-single-pass-review-20261015/process-stage-scale-fixed/report.json`。 |
| 5 优化器计数 | 新解码与复用合并本轮优化器计数和本次参数计数；复用不带入旧档案的参数桶。11 项定向测试通过，覆盖缺 priority/due、计数不翻倍、清除旧请求值；局部正式 Pyright、Ruff 通过。 |
| 6 资源导出 | 外层 reader 交给文件服务，匹配、准备与导出共用事实/身份。三种范围真实 CSV 内容正确，预览及下载的四张资源表各只读一次；相关组合 11 项通过，Ruff 通过。 |
| 7 排产日历 | 同一 CalendarEngine、个人覆盖、周期班次、默认时段和原断点签名直接消费 capture。真实 compute 中七张日历表各读一次，后续日期/人员/profile/pattern SQL 为零；下个事务修改后开工从 09:00 更新到 11:00，签名同步变化。相关 40 项通过，局部正式 Pyright、Ruff 通过。 |
| 8 看板结构 | 完整 `load → project` 从现有 memo 提取 schema SQL；未接入与不可用语义保留。完整公开读链一次结构读取，相关 13 项通过。 |
| 9 启动 journal | 按既有 key 判断是否准备，空 records 同样直接消费；独立 caller 仍准备一次。真实 lifecycle、普通冷启动和恢复共 6 个唯一相关节点通过。 |
| 10 点事件与 D | 来源直接保留原 candidate/tasks/GenerationFacts，点事件退出第二次候选加载；公共 workspace 的候选范围准备实计一次、witness 与任务身份正确。相关 16 项通过；baseline 说明改为实际行数/输出字节职责，甘特说明补明完整分组的轨道归属。 |

上述节点复用有效结果，不累加重叠组合。该批记录时 HEAD 为 `8096bdbbf3c04ef17ec24fa2cd19bfc71fa678b8`，用户原 `开发文档/README.md` 10 行增补保持，当时未提交。

日历两项的精确命令及实际输出如下，cwd 为本仓库。原结果保留在本轮工具 stdout，未另存磁盘日志；下列为既有执行结果摘录，没有为补证据重新运行。

```bash
.venv/bin/python3.8 -m pytest tests/calendar_maintenance/test_calendar_periods.py tests/calendar_maintenance/test_calendar_effective_segments.py tests/workbench/test_calendar_file_api.py tests/workbench/test_operator_calendar_api.py tests/workbench/test_calendar_period_defaults.py -q
# 1 failed, 16 passed in 1.60s。新增 personal 用例缺必填 type，报“请选择这一天是上班还是休息。”；仅补测试 fields.type=work，产品未再改。
.venv/bin/python3.8 -m pytest tests/calendar_maintenance/test_calendar_periods.py::test_explicit_periods_replace_legacy_nonminute_hours -q
# 2 passed in 0.19s。复用首跑其余16个成功节点，17个唯一节点全部有成功结果。
.venv/bin/python3.8 -m pytest -q tests/workbench/test_run_compute_integration.py tests/calendar_maintenance/test_calendar_effective_segments.py --tb=short
# 11 passed in 0.60s，exit 0。
.venv/bin/python3.8 -m pytest -q tests/calendar_maintenance/test_calendar_periods.py tests/workbench/test_calendar_period_defaults.py tests/workbench/test_operator_calendar_api.py tests/algorithm/test_execution_calendar_certified_overlay.py tests/algorithm/test_decode_checkpoint_content_evidence.py::test_calendar_content_cache_does_not_reuse_rolled_back_transaction tests/workbench/test_run_scope_execution_admission.py --tb=short
# 29 passed in 3.83s，exit 0。
```

修复整合检查：全仓 `ruff check core data web tools scripts tests` 通过，两套正式配置 `pyrightconfig.gate.json`、`pyrightconfig.tools.json` 均为 0 errors / 0 warnings；`git diff --check` 通过。整合时仅调整一处新增测试的 import 排序。

后续新增验收使用可见 Codex IAB，由本聊天单一浏览器 owner 串行操作。导航与边界只读盘点已完成，覆盖 12 个侧栏入口和 15 个保留 view；准备工作尚未计为功能通过。正常入口的运行锁/契约随源码目录定位，现已从本轮当前工作区复制运行必需源码、新文件及最终 static 到 `output/iab/single-pass-20261015/{empty,main858,large20k}/runtime`，各自的 DB、日志、journal、备份均隔离，复用原项目 Python 3.8.10 解释器，执行正常 `app_new_ui.py`。

运行身份及启动入口记录在 `output/iab/single-pass-20261015/instances.json`：empty 为 `127.0.0.1:59231`，main858 为 `127.0.0.1:59229`，large20k 为 `127.0.0.1:59230`。三者 `/system/health` 均为 ok，返回的 PID、db_path 与 instance_id 已逐一核对。858 初始库用于真实业务链；20k 存档库用于大规模读取与交互，其既有候选由受控存档构造，测试记录保留这一来源区别。此段记录准备阶段，后续 IAB 实际结果和未完成项见下文及原覆盖表。

### IAB 发现：排产查询信封与前端合同

- main858 首次真实受理 93 批、858 工序后，IAB 自动和手动查询均显示失败。隔离库与日志确认后台在 `2026-10-15T18:43:33.929750` 至 `18:43:48.415320` 正常完成（14.485570 秒），仅 1 个 job / 1 个受理回执，两个候选各 858 道任务；双击确认没有重复受理。
- 共同 `scheduling_jobs._query` 把 48/52 字符的实体定位字段当成 `meta.snapshot_ref`，真实 HTTP 200 响应被原 `RunJobAPI` 的 32 字符合同拒绝。旧 API 测试只取 data，前端测试手造合法 meta，遗漏真实信封联测。
- 原对话批准后，只在共同响应出口使用 `uuid4().hex` 和原 `as_of`，删除无用途 scope 参数及三个调用者字典。前端、worker 和数据库保持，未恢复读绑定登记、序列化预演或新增重试。现有真实 worker 测试把 preview、GET runs、GET requests 交给原前端合同解析，覆盖 complete / failed，修复前 2 项失败、修复后相关 13 项通过；Ruff、正式主链 Pyright 和定向差异检查通过。
- 三个隔离实例均通过正常 `--runtime-stop` 退出，更新上述路由后按原正常入口重新启动，健康身份重新核对并记入 `instances.json`。IAB 重载原 main858 页面后从原请求自动恢复完整候选结果，未重新受理。修复前现场为 `screenshots/run858-query-retry-failed.jpg`，回验为 `screenshots/run858-original-request-recovered.jpg`。

### IAB 发现：完整来源、范围恢复与统一关系图

- **实际发现与批准范围。** large20k 的合法存档候选已通过真实采用生成正式 v1，200 批、20000 条 Schedule、成功采用回执 1 条。原 PlanReadContext、catalog、baseline、delivery、calendar 的整源 10000 条资格及截断使该计划不可选，缩至一日 200 条仍被拒绝。`exports/large20k-formal-plan-capacity-baseline-readonly-proof.json` 保留修复前 Plan/Actual 失败及与基线一致的源码；原对话批准同时调整完整来源与展示范围职责。
- **后端收口。** PlanReadContext 持有一次完整 raw 安排，detail 从同一安排行补齐去重后的工序、批次、供应商和资源关联，原始安排不再重复查询。catalog/selected、采用基线、交付和日历退出对完整安排源的 10000 条资格与 SQL 截断，目录自身分页保留；独立 `context=None` 的采用/历史读取保留一次直接读取。公开 Plan workspace 在范围筛选后执行 10000 条安排限制，出口 Plan 8 MiB、Candidate/Actual 32 MiB 保持；试调完整基础来源 10000 条、ledger 10000 工序/50000 事实行、Actual 50000 报工保持。
- **Actual 筛选顺序。** 原时间重叠、计划完工日期和批次先筛计划安排，再投影 ledger；计划、实际、已记录剩余安排的资源并集仍在 ledger 后筛选。全局/关联关键链直接消费同一 context 的完整安排、任务投影及 parsed intervals，退出 execution_workspace 重建。真实 SQLite 20k 回归证明一日 200 条、单批 100 条、重叠窗口 10 条均返回 200，完整关键链保留 20000 条，每请求完整安排读取 1 次；不设范围仍由 ledger 10000 条上限明确拒绝。
- **图与显示共同协议。** Plan/Candidate/Actual 统一以完整 `nodes[].predecessor_operation_refs` 保留所有原始前驱，包括未安排前驱；公开 `edges` 和 `process_order.items` 退出，process_order 仅保留 state/basis/issues，完整 critical refs/edges 保留。三个现有 model.prepare 各建一次索引，甘特、详情及 GanttRouteList 透传同一索引，PlanProcessOrder 及其构建登记退役。范围外节点使用完整图中的原始区间，一次 workspace 请求完成定位；点事件按规范微秒文本加 1 微秒，保留极短正区间和跨秒/年/闰日进位。
- **完成态文案。** FieldFiles 仅在 `command.phase !== 'done'` 时显示旧预检“尚未写入”句；预检表、数量及原 Feedback 保留，由已确认回执表达真实保存结果。导入请求与写入协议未改。
- **测算的证据边界。** `exports/large20k-shared-graph-protocol-size-proof.json` 是批准前的只读内存方案测算：完整图 20000 nodes、19800 工艺关系、100 critical refs/99 critical edges 保留；删除重复关系后，一日 200 任务的拟议 Plan 信封为 7864340 B，原 8 MiB 不变。它用于选择协议，实际 HTTP/IAB 结果见下，不能把该测算当成实页通过。

定向验证已完成，以下为实施 owner 本轮已执行命令与原工具输出摘录；本次文档同步没有重跑测试。重叠用例不重复累计。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3.8 -m pytest -q tests/workbench/test_plan_read_context.py tests/workbench/test_plan_query_api.py tests/workbench/test_gantt_graph.py tests/workbench/test_plan_adoption_baseline_api.py tests/workbench/test_delivery_projection.py tests/workbench/test_adoption_source_read_reuse.py tests/workbench/test_delivery_trial_projection.py
# 39 passed in 15.28s
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3.8 -m pytest -q tests/scheduler_analysis/test_plan_vs_actual_review.py
# 5 passed in 0.53s
.venv/bin/python3.8 -m pytest tests/workbench/test_execution_plan_read_scope.py tests/workbench/test_point_downstream_api.py tests/workbench/test_piece_downstream_api.py -q
# 12 passed in 7.90s
node tests/workbench/gantt_graph_contract.cjs
node tests/workbench/runtime_reuse_contract.cjs
node tests/workbench-format.cjs
node tests/workbench/piece_downstream_contract.cjs
node tests/workbench/decision_comparison_contract.cjs
node tests/workbench/decision_preparation_contract.cjs
node tests/workbench/plan_transport_probe.cjs
# 7 组源码 CJS 验证通过；覆盖完整/未安排前驱、三个 prepare 各建一次、索引透传、范围外单次读取、微秒进位与 FieldFiles 完成态。
.venv/bin/python scripts/workbench/build.py
# built / files=10 / target=chrome109；本组统一构建一次。
.venv/bin/python -m pytest -q tests/gantt/test_gantt_adapter_contract.py tests/gantt/test_gantt_graph_rendering.py --tb=short
# 7 passed in 0.63s
```

相关范围 Ruff、正式 gate 配置的局部 Pyright（0 errors / 0 warnings / 0 informations）及源码、测试、生成物的 `git diff --check` 通过。首次实际包测试只发现测试夹具变量重名及简化 DTO 缺 gantt_graph，修正测试后通过；构建后的产品源码和静态包未变，复用有效源码验证并未重复构建。

**真实 IAB 已完成与待完成：**

- 前一批已完成候选完整范围 413 后直接手动缩窗恢复 13000 任务、13k CSV 实体核对；试调 3 处“新安排准备/加工标准工时”标签重载及正式 858 计划范围外 before/after 双向详情已通过。原件为 `screenshots/large20k-direct-recovery13000-passed.jpg`、`exports/candidate13000-file-proof.json`、`screenshots/trial-new-arrangement-labels-fixed.jpg`、`screenshots/formal-v2-before-detail-narrow-scope.jpg`、`screenshots/formal-v2-after-detail-outside-scope.jpg`。
- 最新三实例已同步本组源码及统一静态包，经正常 stop/restart 后逐一核对 health、PID、db_path、instance_id，记录在 `output/iab/single-pass-20261015/instances.json`。所有后续实页操作由原对话单一可见 IAB owner 执行。
- 同一已采用 20k 正式库：Actual 完整范围由 ledger 10000 条限制明确拒绝，范围控件仍可用；手动选 2026-01-01 同日完工范围恢复 HTTP 200 / 200 任务，清日期后选 P8-B156 单批恢复 HTTP 200 / 100 任务。Plan 目录当前正式计划可选，完整范围明确拒绝“本次安排超过 10000”，手动选 2026-01-01 至 2026-01-02 恢复 HTTP 200 / 200 任务。
- Plan 一日范围选择 P8-B156 第 1 序后显示完整 100 道路线、其中 99 道在窗外；点击窗外第 2 序，按目标 2026-01-02 08:00–08:15 单次 workspace GET 200，标题及详情为第 2 序、M157/O157、0.25 小时。实际 CSV 已下载为 `exports/formal20k-scope200.csv`。终态截图包括 `large20k-formal-plan-day200-recovered.jpg`、`large20k-actual-date200-recovered.jpg`、`large20k-actual-one-batch100-recovered.jpg`、`large20k-plan-day200-full-route100-before-locate.jpg`、`large20k-plan-outside-task-single-range-success.jpg`，均位于同根 screenshots；访问日志、截图与实体导出统一回写原 `coverage.md` 及 exports 原始证据。
- **点事件实页失败与回修。** empty 实例在 20:16:00 发出 1 次 workspace GET，目标时间由 `.003600` 精确到 `.003601`，HTTP 200，UI 随后在 PlanContract 拒绝真实 DTO。完整响应诊断确认范围、任务、基线、日历、交付、资源和图均通过，失败来自 occupancy 的 1 微秒正容量被 round6 写成 0、比例仍为 0。原失败截图及 `exports/point1us-plan-workspace-contract-diagnosis.json` 保留，实际源头修复和最终 IAB 通过结果见下。

### IAB 回验补充：微秒投影、保留资源与文件维护闭环

- **微秒精度已从共同投影修复。** `core/services/workbench/plan/occupancy.py` 使用已有 `precision=None` 并直接输出真实小时值；`core/services/capacity/plan_calendar_windows.py` 按秒累计后统一换小时，停机小时值保持真实；`core/services/workbench/facts/archived_calendar.py` 的总量直接累加日值。三个产品文件和两个既有测试文件已冻结，`ResourceUtilizationMetrics` 默认报表精度、前端合同和界面实现保持。
- **45 个唯一节点通过。** 以下精确命令及结果来自实施 owner 已有工具 stdout，未另建日志、未重跑取数；前一组与后续仅影响归档总量的改动无关，按有效范围复用。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3.8 -m pytest -q tests/workbench/test_point_downstream_api.py tests/workbench/test_plan_query_api.py tests/workbench/test_plan_adoption_baseline_api.py tests/workbench/test_resource_projection.py tests/calendar_maintenance/test_calendar_periods.py tests/calendar_maintenance/test_calendar_effective_segments.py
# 29 passed in 3.25s
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python3.8 -m pytest -q tests/workbench/test_archived_calendar.py tests/workbench/test_legacy_resource_projection.py
# 16 passed in 2.52s
```

真实 point 1us 完整 HTTP 响应通过原 Node probe 的全部投影契约；归档回归覆盖 machine 2us/operator 3us 六字段、日值与总量一致，以及 1us 停机和真实正占用/重叠/短缺值。最终三个产品文件的正式 gate 配置局部 Pyright 为 0 errors / 0 warnings / 0 informations，五文件 Ruff、`git diff --check` 通过。

| 本轮最终 IAB 结果 | 原始证据（同根 `output/iab/single-pass-20261015/`） |
|---|---|
| 范围外点事件完整链定位通过：20:32:33 恰好 1 次目标 workspace GET 200，窗口 `2026-10-16T00:30:00.003600` 至 `.003601`；1998 个点、完整 2000 道路线，最终第 3 序目标量 1、0 工时、不占设备人员，前端合同通过。 | `exports/point1us-final-single-target-get-proof.json`；`screenshots/formal-point-one-microsecond-final-locate-success.jpg`、`formal-point-one-microsecond-final-detail.jpg`。 |
| Actual 原选 M100 后切 P8-B156，结果 0 items，资源控件明确显示“已选资源（当前范围无记录）”；再次应用仍保留同一 machine ref。20:33:57、20:34:03 两次真实 GET 均为同一 ref/类型/批次，清除日期后 HTTP 200。 | `exports/actual-retained-resource-two-get-proof.json`；`screenshots/actual-retained-M100-outside-batch-placeholder.jpg`。 |
| FieldFiles 导出已有 3 条报工后原样回导，预检 3 条重复、0 变化、0 问题；确认到 done 后旧预检“尚未写入”句消失，原 Feedback 真实结果与逐行表仍在。只读核对仍只有原 3 条、数量各 1、工时及 revision 未变。 | `exports/field-long2000-existing3.xlsx`、`calendar-relation-field-final-readonly-proof.json`；`screenshots/field-file-final-unchanged-done-no-preview-copy.jpg`。 |
| 三个独立文件闭环均完成：公共日历 2026-10-19 导入新增 1 行并确认，再导出同日 CSV 1 行；OP:1/MC:IAB%1 关系导入不变 1 行并确认，再导出全部人员关系 CSV 1 行；批次筛选 `IAB-B-` 实际下载 XLSX 5000 条。 | `exports/calendar-one-day20261019.csv`、`operator-machine-existing-one.csv`、`batches-filtered5000.xlsx`；`final-independent-files-and-system-proof.json` 核对实体分别为 1/1/5000 数据行。 |
| 帮助实际定位 5.7 日历章节锚点，下载 Markdown 199943 B 并返回工作台。系统日志 CSV 6 条、诊断 ZIP 内 logs.csv 与已下载 CSV 字节内容相同，页面诊断 JSON 可解析。日志时间问题另列下段。 | `screenshots/help-calendar-chapter-anchor.jpg`；`exports/workbench-manual.md`、`system-operations6.csv`、`system-diagnostics.zip`、`system-page-diagnostics.json`、`final-independent-files-and-system-proof.json`。 |
| 正常备份恢复链已通过：新增 60661760 B SQLite 备份、完整性检查通过并实际下载；配置 61→62 后恢复该备份，生成 before_restore 保护副本，终态 succeeded/verified。维护期间业务 503；正常 host-stop 后按原配置重启 empty，PID 3136、health 为同一 DB，IAB 配置已恢复为 61。 | `exports/system-restore-diagnostic.json`；`screenshots/system-backup-created-integrity-passed.jpg`、`system-before-restore-config62.jpg`、`system-restore-completed-restart-required.jpg`、`system-restored-after-normal-restart-config61.jpg`；最新实例身份见 `instances.json`。 |
| 临时备份独立删除通过：204004 临时备份已删除，目录仅保留恢复源与 before_restore 保护副本；恢复源配置 61、保护副本 62，restore/delete journal 均为 succeeded。只读核当前 5001 批、2000 唯一正式安排、报工 3 条/修订合计 3/撤销 0，配置间隔 61、保留 8；正常重启 PID 3136。 | `exports/system-backup-restore-final-readonly-proof.json`；`screenshots/system-restored-config61-visible.jpg`、`system-temporary-backup-delete-completed.jpg`。 |

本段记录时，已完成的独立功能实测与有效定向验证按原覆盖范围保留；当时 Dashboard 时间轴旧通过结论对新源码失效。该历史覆盖状态为 171 条中 118 项实测、15 项复用、37 项未选、1 项待修回验。后续真实修复、补验和最终分类见本文末节及现有 `coverage.json/md`，不将历史排列重复累计为实测次数。

### UTC 修复与原日志回验已完成

- `core/services/workbench/facts/system_reads.py` 与 `core/services/workbench/system/maintenance_records.py` 复用现有 `stored_utc_text` 转换 OperationLogs，列表、详情、筛选与导出使用同一工厂本地时间；`core/services/system/maintenance/cleanup_task.py` 的操作日志 cutoff 改用 UTC，备份清理沿用其本地时间职责。3 个产品文件与 2 个既有测试文件已冻结。
- 10 个唯一测试节点最终通过。首轮清理用例因 fixture 缺少必填字段失败，补齐后该节点单独通过，其余 9 项有效结果复用；Ruff、正式 gate 配置的局部 Pyright、差异检查通过。以下为 owner 已执行命令，本次文档同步没有重跑：

```bash
.venv/bin/python3.8 -m pytest -q tests/workbench/test_system_maintenance_restore.py::test_utc_operation_logs_use_one_local_time_for_lists_details_filters_and_export tests/calendar_maintenance/test_exit_backup_maintenance.py::test_operation_log_cleanup_uses_utc_boundary_and_keeps_limits tests/web_pages/test_system_runtime_logs_page.py tests/workbench/test_display_keys.py::test_system_display_keys_use_file_metadata_and_event_identity_with_read_state_migration
.venv/bin/python3.8 -m pytest -q tests/calendar_maintenance/test_exit_backup_maintenance.py::test_operation_log_cleanup_uses_utc_boundary_and_keeps_limits
.venv/bin/python3.8 -m ruff check core/services/workbench/facts/system_reads.py core/services/workbench/system/maintenance_records.py core/services/system/maintenance/cleanup_task.py tests/workbench/test_system_maintenance_restore.py tests/calendar_maintenance/test_exit_backup_maintenance.py
.venv/bin/python3.8 -m pyright -p pyrightconfig.gate.json core/services/workbench/facts/system_reads.py core/services/workbench/system/maintenance_records.py core/services/system/maintenance/cleanup_task.py
git diff --check -- core/services/workbench/facts/system_reads.py core/services/workbench/system/maintenance_records.py core/services/system/maintenance/cleanup_task.py tests/workbench/test_system_maintenance_restore.py tests/calendar_maintenance/test_exit_backup_maintenance.py
```

- 原 empty 实例正常重启后，IAB 以原操作日志 `id=6` 回验：同范围列表和详情显示 20:29，实际 CSV 1 行、813 B，精确时间均为 `20:29:55`；原数据库 UTC `12:29:55` 保持。原失败截图保留，最终证据为 `screenshots/system-original-log6-final-local2029-detail.jpg` 与 `exports/system-original-log6-local.csv`，覆盖项 `system.02/system.03` 通过、`IAB-UI-005` 关闭。

### 历史：899 项门禁实际失败与当时待修（现已修复）

- 第 15 步先因 lifecycle 台账 `line_start` 位置陈旧失败；使用已有 `refresh-auto-fields` 仅更新自动位置字段后，该项 check 通过，随后重跑原 runner。
- 第 16 步全量实际收集 899 项：**860 通过、36 跳过、3 失败**；第 17 步未运行。此前 841 和 877 项结果各属于当时版本；此处保留该次真实失败，原件位于 `evidence/QualityGate/v4/history/20261015-single-pass-before-dashboard-fix/`。
- 两项既有 CJS 失败来自 `DashboardTimelineModel.prepare → PlanGanttModel.prepare`：Dashboard analysis 的真实 DTO 没有 `gantt_graph`，通用 Plan prepare 却要求它。main IAB 点击“资源压力 37”实际进入错误边界，原件为 `screenshots/dashboard-resource-pressure-timeline-before-fix-failed.jpg`；当时 `dashboard.02` 转待修回验、`IAB-UI-006` 打开，最终已修复回验关闭。
- 第三项失败确认同一 Dashboard 请求读取 Machines 两次：`dashboard.raw` 已有完整设备事实，后续 `read_plan_delivery → detail_rows → enrich_arrangements` 又 SELECT 同一设备名称。该历史节点两项根因已确认并由原对话裁定共同职责修法；最终实现和验证见下。
- 该次失败后的待办现已完成；其他有效结果按原范围复用，Windows 平台延期保持。失败记录及门禁要求保留，该历史阶段尚未提交或推送。

## 最终收口：共同图索引、独立入口与 903 项集成结果

### 最终职责修复

- **Dashboard、Plan、Actual 共用既有图拥有者。** 三个 model 只准备任务显示事实，PlanWorkspace、RunCandidateWorkspace、ActualGanttWorkspace 各自在原 useMemo 内建立一次 GanttGraph 索引；甘特、完整路线和详情直接消费。PlanGantt、RunCandidateGantt 的下游补建分支退出，原直接渲染测试通过同一准备接线。
- **已有设备事实直接交接。** Dashboard 的完整 Machines capture 按同一对象引用传给 PlanReadContext 与安排详情富化；空 capture 和缺编号按已取得事实表达，保留只有未提供 capture 的真实入口自行查询。相关 139 个定向节点通过，最终整合再次覆盖。
- **Actual 计划关键链最后漏接已修复。** `ActualGanttWorkspace.jsx` 给 Chain 传与 GanttRouteList 同一 `index`；`ActualGanttControls.jsx` 使用 `index.nodes`，退出每次 render 从完整 `graph.nodes` 重建 Map。可见成员集合和 critical_edges 的入边准备继续承担本次显示职责。实际调用者以这两个前端源文件及全仓引用定位核对。
- `tests/gantt/test_gantt_graph_rendering.py` 只补一项真实包回归：先建立原索引，再禁止 Chain 读取原始 nodes；连续以完整、空和部分可见任务渲染，核对节点、边原因、范围外提示与点击回传。首跑该用例的点击 fixture 缺 `currentTarget`，补齐事件后该节点通过，复用同轮其他 7 项通过结果。

```bash
.venv/bin/python3.8 scripts/workbench/build.py
# built，10 files，target=chrome109
.venv/bin/python3.8 -m pytest -q tests/gantt/test_gantt_adapter_contract.py tests/gantt/test_gantt_graph_rendering.py --tb=short
# 首跑 7 passed / 1 fixture failed；产品与包未改
.venv/bin/python3.8 -m pytest -q tests/gantt/test_gantt_graph_rendering.py::test_actual_critical_chain_reuses_prepared_nodes_across_renders --tb=short
# 补齐 fixture 事件后 1 passed；本组 8 个唯一节点最终均通过
node tests/workbench/runtime_reuse_contract.cjs
# passed，复用既有 Actual 工作区一次建图和范围读取契约
.venv/bin/python3.8 -m ruff check tests/gantt/test_gantt_graph_rendering.py
# All checks passed
git diff --check
# passed
```

正式静态包热同步至三个隔离实例，无须重启 main858/large20k。真实 Actual v3 读取 874 道工序，完整关键链为 23 道；末端 `D261024-3 / 50` 定位到 11 月 16 日，2× 缩放后仍为 23 道。搜索 `D261008-1` 后为 7/23 可见，其余带“当前视图外”；从完整链点击首端 `D261030-1 / 5`，详情和时间轴定位到 10 月 12 日。原件为 `screenshots/actual-chain-final-index-{last-locate,zoom2,filter-outside,first-locate}.jpg`。

### 最终 Dashboard 与补充独立功能

所有相对产物路径以下均以 `output/iab/single-pass-20261015/` 为根；原截图、下载和只读回读保留在既有覆盖表中。

| 功能 | 实际操作、结果与原始证据 |
|---|---|
| Dashboard 共同影响分析 | 实际点击资源压力卡（37），按 `DashboardPanels.jsx` 的现有 `onAnalysis('delivery')` 接线进入交期风险下的共同影响分析。显示 725 道自制任务及 70 项正式资源，首尾工序双向定位、2× 缩放有效；切停机影响的分析显示 4 条例行保养时段和 13 道计划工序，直接重叠为 0，登记依据及浅深主题可读。图为 `dashboard-resource-pressure37-final-rendered.jpg`、`dashboard-final-timeline-locate-*.jpg`、`dashboard-final-downtime-*.jpg`。IAB-UI-006 最终关闭。 |
| stage 与 strict 同事实对照 | 选择现有 `IAB-SPLIT-6` 和 `D261029-1`，日期 10 月 12–31 日、齐套检查开启、缺资源自动分配。strict 实际预检后取消计算；切 stage 重新预检并实际计算，2 批 14 道全部排齐、1 个候选，预算 5 秒，处理用时 2.161784 秒。seq10/20 外协为 10 月 12 日 00:00→15 日 00:00；seq30 用料 20 日到货，安排为 20 日 08:00→08:30。与 strict 三道均等待 20 日的原只读预检事实一致，stage 前序确实提前放行。 |
| 非空不重排时段 | 与上述 stage 共用一次真实运行，窗口为 10 月 12 日 08:00–08:06；`D261029-1 / op763 / seq2 领料` 的起止、`ST-QG-02 / QG-02` 与正式 v3 逐字段一致，候选 `locked=true`。正式版本仍为 v3，该运行无采用回执。两项追加在既有 `exports/process-groups-material-split-readonly-proof.json` 的 `final_stage_and_hold_ui_readback`，20 项核验全部通过；图为 `run-stage-hold14-accepted-running.jpg`、`run-stage-hold14-external-early-detail.jpg`、`run-stage-hold14-preserved-original-op2.jpg`。`confirm5seconds` 图保留输入草稿阶段，最终 5 秒依据为已受理记录与持久化参数。 |
| 公共日历恢复默认 | empty 无业务影响的 10 月 27 日由默认 8 小时设为调休 0 小时，保存后重新打开；再清除单独设置、确认恢复默认，重新打开显示 08:00–12:00、13:00–17:00、8 小时、100%、普通件和急件允许、备注未填写。只读核该日显式行已无，原 15/16/19 日及 17/18 日规则保持。图为 `global-calendar-custom-day-before-reset.jpg`、`global-calendar-default-restored-oct27.jpg`。 |
| 空白模板下载 | 批次导入与工艺路线导入面板各实际下载一份 XLSX。`exports/batch-blank-import-template.xlsx` 为 9099 B、主表 10 列；`exports/process-blank-route-template.xlsx` 为 8163 B、主表 4 列。两份主表都只有表头、0 数据行，并有说明页；实体列已由只读解析核对，图为 `batch-blank-template-downloaded.jpg`、`process-blank-template-downloaded.jpg`。 |
| 维护结果手填双编号 | 正常重启后的页面无入口重开原 warm 表单，先如实记录可达性；获明确授权后，仅在 empty 对当前新备份 `aps_backup_20261015_214926_manual_106d19204e0d.db` 正常恢复一次以重入维护页。新恢复为 succeeded/verified 并生成保护副本。实际手填旧成功恢复的操作编号，21:51:13 发出 `/system/results/{request_key}` GET 200；切维护记录编号手填旧 job_ref，21:51:24 发出 `/system/jobs/{job_ref}` GET 200。两次均显示同一旧 20:38 成功记录、旧选定备份和历史记录提示。图为 `system-manual-request-reference-old-success.jpg`、`system-manual-job-reference-old-success.jpg`；请求来自既有 empty `launch.stdout.log`，回读追加原 `exports/system-backup-restore-final-readonly-proof.json` 的 `final_manual_reference_reentry`。 |

维护双编号查询后，使用正常 `--runtime-stop` / host-stop 退出并以原配置启动 empty，PID 为 65983、instance_id 为 `715556e298c4497bb15b8c79733d87d2`；health 核对同一隔离 DB，IAB 重新检查启动状态并确认恢复回执后，业务配置恢复可操作，仍为间隔 61 / 保留 8。只读回读当前 5001 批、2000 唯一正式安排、3 条报工/3 个修订/0 撤销，新备份关键数与当前相等；旧、新两次恢复 journal 均为 succeeded/verified/selected_backup。图为 `system-reference-query-normal-restart-config61.jpg`。main858 PID33495、large20k PID33523 保持，三个 health 均正常；最新身份保存在原 `instances.json`。

### 最终完整门禁与交付状态

```bash
.venv/bin/python3.8 scripts/run_quality_gate.py --allow-dirty-worktree --no-long-gate-cache
# 2026-10-15 21:41:12 至 21:44:57，runner exit 2
# 第 1–16 步通过；第 16 步 903 collected / 867 passed / 36 setup skipped / 0 failed / 0 collection errors
# pytest exitstatus=0，full-test-debt passed，unexpected failure=0
# 第 17 步：15 个 required Windows/PowerShell 启动器节点 setup skipped，returncode=1
```

最终原件为 `evidence/QualityGate/v4/quality_gate_manifest.json`、`current_full_test_debt.json`、`full_test_debt_summary.json` 及第 16/17 步 receipt、stdout/stderr。正式 manifest 保持 `failed`；原 15 项 Windows 平台验收延期，待 Windows 环境按既有门禁执行。原 899 项失败原件保留在既有 history 目录，902/866 轮次的统计和修复先后保留于本记录及原覆盖表历史字段。后续补验只改变隔离实例数据与验收记录，产品源码和静态包保持该次最终门禁状态，有效结果复用。

最终覆盖为原 171 条中 **124 项选定实测、13 项共同入口复用、34 项风险未选**；另 5 个独立文件入口和 2 份空白模板下载均实测完成，独立 UI 待验为 0，IAB-UI-001 至 006 全部修复回验关闭。原 `coverage.json/md` 收录 257 个产物：192 张截图、31 份实际下载、34 份只读支持，缺引用 0、未映射 0。stage 回读 20 项和系统重入/双编号查询追加回读 13 项核验均为 true；结果类型继续区分实际功能、共同入口复用和风险未选。

该次门禁在 dirty 工作区执行，前后内容相等、`tracked_drift_detected=false`；执行时 HEAD 为 `8096bdbbf3c04ef17ec24fa2cd19bfc71fa678b8`。P1–P8 实施与选定独立 IAB 功能已完成，验证状态为 `platform_deferred`，Windows 15 项必需启动器验收延期和正式门禁失败记录保持，未形成 clean-worktree proof。

后续按用户明确授权，将本轮代码、测试、正式静态包、架构说明及本目录三份设计/实施/清单形成一次本地提交。用户原 `开发文档/README.md` 增补 10 行、删除 0 行留在工作区；推送暂缓。原始 coverage、门禁产物和隔离数据库依仓库规则继续保留本机，三个隔离实例保留供验收。

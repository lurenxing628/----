# f4b4c18 之后提交深度引用链审查

- 审查日期：2026-06-10
- 审查范围：`f4b4c18a696e92bc73fdcb55186d3f2ddcf32789..HEAD`
- 范围规模：20 个提交，188 个文件，4623 行新增，1214 行删除
- 审查方式：主线程 + 12 个 Sub Agent 并行切片 + NetworkX 调用图
- NetworkX 工具：`.codestable/checkup/scripts/callgraph_extract.py`
- 调用图规模：5984 个函数，22601 条边，其中 8175 条确信边；70 条风险数据流，60 个高扇入点，789 个关节点

## Findings

### P1-1 延期诊断没有吃到资源/批次/日期筛选条件

- 位置：
  - `web/routes/reports_page_support.py:235`
  - `core/services/report/report_engine.py:193`
  - `core/services/report/report_engine.py:206`
  - `core/services/scheduler/schedule_delay_diagnosis_service.py:54`
- 引用链：
  - 页面：`_raw_delay_diagnosis -> ReportEngine.overdue_delay_diagnosis_context -> ScheduleDelayDiagnosisService.diagnose_resolved_plan_overdue`
  - 导出：`export_overdue_xlsx -> _overdue_diagnosis_export_rows -> diagnose_resolved_plan_overdue`
- 根因：
  - 主延期列表已经把 `resource_type/resource_id/batch_id` 用于过滤。
  - 但诊断上下文只传 `version/plan_role/scenario_id`，诊断服务再去读取整套方案数据。
  - 导出侧也只是最后按 `batch_id` 裁剪诊断行，不是在底层取数阶段用同一组筛选条件。
- 影响：
  - 用户页面表格可能只看某台设备、某个人员或某个批次，但“为什么延期”的解释可能参考了筛选范围外的工序。
- 建议：
  - 给 `overdue_delay_diagnosis_context`、`_overdue_diagnosis_export_rows`、`diagnose_resolved_plan_overdue` 补齐资源、批次、日期参数。
  - 下推到 `list_plan_overdue_base_rows_for_resolution` 和 `list_plan_detail_rows_all_for_resolution`。
  - 补一条页面和导出同筛选条件的回归测试。

### P1-2 手动备份完整性检查执行失败会变成 500

- 位置：
  - `core/infrastructure/backup.py:334`
  - `web/routes/system_backup.py:108`
  - `web/error_handlers.py:100`
- 引用链：
  - 用户点击创建备份 -> `backup_create` -> `BackupManager.backup`
  - `PRAGMA integrity_check` 执行失败后抛 `RuntimeError`
  - `backup_create` 只捕获 `MaintenanceWindowError`
  - 最后落到全局 500
- 根因：
  - 完整性检查从 warning 放行改成 loud raise 是对的，但手动备份入口没有同步把新错误转成用户可见的中文失败提示。
- 影响：
  - 系统不会落坏备份，这是对的；但用户只看到“服务器内部错误”，看不到真正原因。
- 建议：
  - `backup_create` 捕获备份失败，记录日志并 `flash` 明确中文错误。
  - 加路由级测试：模拟 `BackupManager.backup()` 抛完整性检查失败，断言不是 500。

### P2-1 恢复前保护快照失败时根因被包成通用恢复失败

- 位置：
  - `core/infrastructure/backup.py:418`
  - `core/infrastructure/backup.py:431`
  - `web/routes/system_backup_actions.py:27`
- 引用链：
  - 用户点击恢复备份 -> `run_backup_restore` -> `BackupManager.restore`
  - 恢复前先 `self.backup(suffix="before_restore")`
  - 如果完整性检查失败，`restore()` 的宽泛 `except Exception` 返回 `restore_failed`
- 根因：
  - 恢复前备份失败和真正恢复文件失败被合并成同一个错误码和同一句话。
- 影响：
  - 系统会停止恢复，这是安全的；但用户不知道是“恢复前保护快照失败，所以没有继续恢复”。
- 建议：
  - 给恢复前快照失败单独 code，例如 `before_restore_backup_failed`。
  - 页面展示“恢复前备份完整性检查失败，数据库未恢复”。

### P2-2 工序 `seq` 坏值会冒泡成普通 `ValueError`

- 位置：
  - `core/services/scheduler/run/schedule_input_contracts.py:10`
  - `core/services/scheduler/run/schedule_input_runtime_support.py:209`
  - `core/services/scheduler/run/schedule_execution_persistence_guard.py:200`
  - `web/routes/domains/scheduler/scheduler_run.py:43`
  - `web/routes/domains/scheduler/scheduler_week_plan.py:432`
- 引用链：
  - 正式排产/插单模拟 -> `ScheduleService.run_schedule`
  - `collect_schedule_run_input` 或写库前护栏使用 `_op_seq`
  - `_op_seq` 对 `seq="abc"` 这类坏值抛普通 `ValueError`
  - 两个页面入口只捕获 `AppError`
- 根因：
  - 这次把坏 `seq` 从静默归 0 改成 loud raise 是合理方向，但错误类型没有接入项目统一业务错误体系。
- 影响：
  - 脏工序数据会让用户入口变成 500，而不是中文提示“某条工序序号不合法”。
- 建议：
  - `_op_seq` 或上层调用把坏值转成 `ValidationError/AppError`。
  - 测试要覆盖真实路由或 `ScheduleService.run_schedule` 入口，而不只测 `_op_seq` 单函数。

### P2-3 延期诊断坏数值仍会静默变 0 或被跳过

- 位置：
  - `core/services/scheduler/schedule_delay_diagnosis_utils.py:16`
  - `core/services/scheduler/schedule_delay_diagnosis_service.py:159`
  - `core/services/common/overdue_calculations.py:50`
- 引用链：
  - `ReportEngine.overdue_delay_diagnosis_context -> diagnose_resolved_plan_overdue -> compute_overdue_buckets`
- 根因：
  - `float_or_default` 遇到坏数字返回 `0.0`。
  - 坏到期时间会跳过，坏完成时间会被当成未完成处理。
- 影响：
  - 用户可能看到“延期 0 小时”或缺少部分延期诊断，而不是看到数据问题。
- 建议：
  - 用户可见报表链路中，坏值要转成明确中文数据问题，不要静默改 0。

### P2-4 新增契约测试没有完整接入日常门禁

- 位置：
  - `tools/test_registry_data.py:68`
  - `tools/test_registry_groups_scheduler.py:312`
- 未接入 required/group 的测试：
  - `tests/candidate/test_baseline_missing_or_failed_four_state_parity.py`
  - `tests/material/test_material_repo_stock_qty_loud_contract.py`
  - `tests/migration_db/test_backup_integrity_check_contract.py`
  - `tests/schedule/service/test_op_seq_loud_contract.py`
  - `tests/schedule/summary/test_meta_bool_state_parity_contract.py`
- 根因：
  - 新增防回归测试文件落地后，没有同步加入 required registry 和对应 group。
- 影响：
  - 全量跑测试能覆盖；但日常增量门禁按改动路径选测时，这些新测试不会自动参与拦截。
- 建议：
  - 把 5 个测试加入 `QUALITY_GATE_GUARD_TESTS`。
  - 同步加入对应 required regression group。
  - 给 registry 元测试补“新增契约测试必须 required 且 grouped”的断言。

### P2-5 顶层 scheduler 路由壳删除缺少等价守护

- 位置：
  - `tests/gate_meta/test_sp05_path_topology_contract.py:59`
  - `tests/gate_meta/test_sp05_path_topology_contract.py:62`
  - `tests/gate_meta/test_sp05_path_topology_contract.py:85`
  - `tests/gate_meta/test_sp05_path_topology_contract.py:454`
  - `tools/test_registry_groups_scheduler.py:122`
  - `tools/test_registry_groups_scheduler.py:223`
  - `tools/test_registry_groups_misc.py:27`
  - `tools/test_registry_groups_misc.py:160`
- 根因：
  - 9 个顶层 `web/routes/scheduler_*.py` wrapper 已删除，但 SP05 的 `ROUTE_COMPAT_MODULES` 清空后，旧 import loud 失败检查也随之空跑。
  - 测试 registry 里还残留旧 `web/routes/scheduler_*.py` 路径。
- 影响：
  - 当前运行时代码没有旧 import，页面 URL 也正常。
  - 但以后有人重新加回旧壳或误导门禁 scope，现有自动检查不一定第一时间红。
- 建议：
  - 在 SP05 增加 `REMOVED_ROUTE_WRAPPERS`，断言文件不存在、旧 import loud 失败。
  - 清理 registry 旧路径，只保留 `web/routes/domains/scheduler/...`。

### P3-1 缺失对比方案时 fallback 到正式方案的链路仍容易误解

- 位置：
  - `core/services/scheduler/schedule_plan_query_service.py:123`
  - `tests/candidate/test_scheduler_candidate_reports_contract.py:392`
  - `web/routes/reports_page_support.py:226`
- 根因：
  - 请求的 `plan_role` 不存在时，系统返回 `fallback_to_adopted` 并展示正式方案。
  - 页面已有提示，但导出链接和部分上下文仍保留用户请求的 `plan_role`。
- 影响：
  - 用户可能以为导出/跳转仍是在看原请求方案，实际内容是正式采用方案。
- 建议：
  - 如果产品允许 fallback，需要把“实际生效方案”写进导出链接和页面上下文。
  - 如果不允许 fallback，报表和导出应直接返回清楚错误。

### P3-2 文档和台账仍有旧状态残留

- 位置：
  - `.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety/PHASE4-SAFE-BATCH-PLAN.md:104`
  - `.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety/clusters/C-COMPAT-DISPATCH.md:40`
  - `.codestable/audits/2026-06-02-underwater-debt-census/fix-plan/phase4-dep-safety/clusters/C-CONFIG-DUAL.md:33`
  - `开发文档/系统速查表.md:58`
  - `开发文档/开发文档.md:4351`
- 根因：
  - 主 registry 和部分终态说明已经更新，但速查行、cluster 文档、开发文档没有同步。
- 影响：
  - 维护者可能误以为已删除的兼容入口仍保留，或误以为已 fixed 的债还在待处理。
- 建议：
  - 同步 cluster、速查、开发文档。
  - 给 `_check_status_consistency.py` 增加 `fixed` 不应继续 `owner_pending=true` 的检查。

## 已核对未发现阻塞问题的切片

- 配置收口：旧 `config_service/config_snapshot/config_validator` 顶层壳删除后，没有运行时代码继续引用旧路径。
- `compat_parse/value_policies/boolean_normalize`：旧 `core.services.common.*` 三个壳没有活引用，新 shared 入口可用。
- 候选运行和执行事实护栏：候选基线四态、写库前护栏、kwargs contract 未发现断链。
- 摘要与降级：`_meta_bool_state` 已收口到单源，summary 测试覆盖通过。
- 资源派工：资源筛选、现场写入入口、内部字段屏蔽链路未发现阻塞问题。
- 枚举与内部字段：用户可见中文标签、候选/正式方案写权限、日志展示未发现泄露阻塞。
- 删除接口残留总扫：已删旧模块没有运行时代码、测试 import、路由注册、打包脚本继续引用。

## 验证记录

- NetworkX 调用图已重跑并用于风险链路定位。
- 子代理定向测试汇总：
  - backup/material/resource dispatch 基础链路：39 passed + 7 passed。
  - 排产候选/执行事实相关：64 passed + 6 passed + 43 passed。
  - 路由注册/topology/url_for：17 passed。
  - 资源派工：401 passed + 34 passed + 8 passed。
  - 摘要/降级/页面展示：123 passed + 72 passed + 12 passed + 39 passed。
  - 配置/strict/preset：56 passed + 18 passed + 12 passed。
  - 枚举/plan_role/request scope：7 passed。
  - 延期诊断/报表候选：28 passed。
  - 门禁/E2E/Python 3.8 扫描：36 passed；新增测试文件 50 passed；Python 3.8 兼容发现 0。
- 主线程补充复核：
  - `git diff --check`：无输出。
  - registry 对账：5 个新增契约测试为 `NOT_REQ GROUPS=NO_GROUP`，`test_scheduler_plan_role_arg_contract.py` 为 `REQ GROUPS=scheduler_analysis_gantt_reports_week_plan`。

## 工作区说明

- 审查过程中 NetworkX 工具重写了 `.codestable/checkup/latest/callgraph/*.json`。
- `evidence/DeepReview/reference_trace.md` 也出现了审查/测试生成的差异。
- 本报告为本次新增审计产物。

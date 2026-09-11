# H10: 防回潮候选与精确改名计划

## Main 已接受，等待 GO

- Main 已接受本方案的 36 个同目录 helper/CLI 改名、7 句 docstring，以及 target、别名、AST 和配对 nodeid 保持规则。
- **尚未授权执行机械迁移。** D-P003 与 E 报表恢复仍在实施；必须等全部源稳定、Main 完成 Git 前置快照，并收到 Main 唯一明确 GO 后再执行。
- 当前正常收尾，不再广域重扫。E 的 `test_final_execution_rejections.py` 稳定后，与 D/E 随后新增的真实测试统一做一轮小增量登记，再封版。
- 当前 131 项 supplemental 仅是登记状态，不是最终门禁通过。本报告的“已接受”不等于已改名、已补模块说明、已完成配对 collect 或最终 clean proof。

## 结论与权限

- **只交计划，未搬动文件，未补 docstring，未改 Git、门禁规则、ignore 或 baseline。** 唯一额外源码操作是 Main 明确授权的两份静态分析辅助脚本 import 排序。
- 完整候选集不是 `git diff --diff-filter=A`：取当前存在的 tracked 与非忽略 untracked Python 路径并集，减去 `d4589d77d9b642fe3b16a891fe4f40f9aede1f93` 原有路径集。
- 交付前扫描共 **2142 个 Python 候选**，其中 1156 个符合测试文件名规则、656 个产品源文件；同一门禁 AST 规则命中 **36 个缺 test 函数、7 个缺模块 docstring、0 个 scope 漏盖、0 个测试 AST 解析失败**。36 个中 4 个 tracked、32 个 untracked；7 个中 6 个 tracked、1 个 untracked。
- 全部 36 个目标均完成同目录存在性、大小写折叠、Git 可见路径、baseline 路径及计划内重复检查，**零冲突**。不覆盖或合并现有文件。
- 最新引用扫描覆盖 5242 个文本文件，得到 **594 处可执行源码引用，涉及 263 个文件**；另有 2784 处文档或回执引用单独列出，不能全局替换。仅排除本次生成的三个 H10 报告，避免自引用；未排除产品或测试源码。

## 证据边界

- 原始扫描 `prospective-complete`：HEAD `4b418d1784947abb7eef5e2747cd05b5c83b171f`，2134 个 Python 候选；36 + 7 命中，3643 个纳入观察的源码/配置前后 SHA 一致。
- 中间刷新 `prospective-refresh`：HEAD `21134f739c192aca45cee9356d13138f1c658953`，候选增至 2140，命中集合不变；期间 4 个外部施工文件变化留在原始 `prospective-refresh/result.json`，不作冻结证明。
- 交付扫描 `prospective-delivery`：同一 `21134f73` HEAD，2142 个候选，36 + 7 命中不变；3657 个源码/配置前后 SHA 一致。配套 JSON 的 `scan_result` 指向本轮。
- 最新引用扫描 `h10-reference-delivery`：3657 个源码/配置前后 SHA 一致，36 个待改名文件均与交付扫描 SHA 一致。先前 `test_calibration_support.py` 的外部变动已重新绑定。
- 调用的是现有 `is_collected_test_path`、`scan_missing_test_function`、`scan_missing_docstring`、`scan_uncovered_source(load_scope_globs())`；没有修改扫描器。prospective 实际 exit 1 正确表示存在命中，不冒充通过。
- 早先 `collect-all` 实际收集 15505 项，这 36 个文件贡献 0 个 nodeid；这是历史收集证据，不是改名前后的配对收集，也不是 15505 项测试通过。

## 精确映射

除 R01 位于 `tests/app_runtime/` 外，其余均留在 `tests/workbench/`。下表旧路径精确到文件，新文件名在同一目录；完整 old/new 模块路径、SHA、定义位置、冲突检查和逐条引用保存在配套 JSON。不移动 CJS 文件，不改 fixture 名称或运行行为。

| ID | 旧路径 | 同目录新文件名 | 真实角色 |
| --- | --- | --- | --- |
| R01 | `tests/app_runtime/test_runtime_stop_draining_support.py` | `runtime_stop_draining_support.py` | 真实 HTTP 停机、在途写入及锁测试的自启动子进程支持 |
| R02 | `tests/workbench/test_actual_gantt_live_server.py` | `actual_gantt_live_server.py` | 临时 SQLite 的实际甘特 Flask 测试服务器 |
| R03 | `tests/workbench/test_actual_gantt_support.py` | `actual_gantt_support.py` | 实际甘特的临时库、数据种子和 API fixture |
| R04 | `tests/workbench/test_batch_execution_ledger_support.py` | `batch_execution_ledger_support.py` | 批次执行台账的隔离 fixture 与命令辅助 |
| R05 | `tests/workbench/test_calibration_support.py` | `calibration_support.py` | 校准链路 fixture、损坏注入及只读断言辅助 |
| R06 | `tests/workbench/test_execution_ledger_support.py` | `execution_ledger_support.py` | 真实临时 SQLite 执行台账 fixture |
| R07 | `tests/workbench/test_field_workspace_support.py` | `field_workspace_support.py` | 现场工作台的隔离 Flask/API fixture |
| R08 | `tests/workbench/test_final_master_acceptance.py` | `final_master_acceptance_cli.py` | 整工作台浏览器及停机重启验收 CLI，不是 pytest 测试模块 |
| R09 | `tests/workbench/test_master_overview_support.py` | `master_overview_support.py` | 主数据总览的临时库/API fixture |
| R10 | `tests/workbench/test_piece_adoption_support.py` | `piece_adoption_support.py` | 逐件采纳的底层真实槽位/排产结果 fixture |
| R11 | `tests/workbench/test_piece_chain_support.py` | `piece_chain_support.py` | 逐件链路的真实 worker、SQLite 和采纳辅助 |
| R12 | `tests/workbench/test_plan_adoption_baseline_support.py` | `plan_adoption_baseline_support.py` | 计划采纳基线的真实引擎/双版本临时库辅助 |
| R13 | `tests/workbench/test_preflight_support.py` | `preflight_support.py` | 预检 API 临时库及只读/拒绝写入辅助 |
| R14 | `tests/workbench/test_process_file_hours_support.py` | `process_file_hours_support.py` | 工艺工时文件 fixture 与存储保留断言 |
| R15 | `tests/workbench/test_report_ledger_widgets_server.py` | `report_ledger_widgets_server.py` | 报表台账组件测试的临时 Flask 服务器 |
| R16 | `tests/workbench/test_request_lifecycle_support.py` | `request_lifecycle_support.py` | 请求生命周期的 HTTP、临时库和调用方锁 fixture |
| R17 | `tests/workbench/test_resource_file_support.py` | `resource_file_support.py` | 资源文件 fixture、字节与业务保留断言 |
| R18 | `tests/workbench/test_round1_field_piece_files_probe.py` | `round1_field_piece_files_probe.py` | 修改实际下载模板及检查导出的 CLI probe |
| R19 | `tests/workbench/test_round1_field_piece_files_support.py` | `round1_field_piece_files_support.py` | R1 现场逐件文件 HTTP fixture 和 XLSX 操作辅助 |
| R20 | `tests/workbench/test_round1_piece_point_support.py` | `round1_piece_point_support.py` | R1 逐件/时点链路的私有库与托管 worker fixture |
| R21 | `tests/workbench/test_run_candidate_adoption_support.py` | `run_candidate_adoption_support.py` | 候选采纳 fixture、完整存储快照和失败注入 |
| R22 | `tests/workbench/test_run_candidate_baseline_support.py` | `run_candidate_baseline_support.py` | 候选基线的临时库、真实 worker 与 API 辅助 |
| R23 | `tests/workbench/test_run_candidate_support.py` | `run_candidate_support.py` | 候选任务的当前 schema 临时库及真实引擎 fixture |
| R24 | `tests/workbench/test_run_candidate_widgets_support.py` | `run_candidate_widgets_support.py` | 候选组件的真实引擎种子及只读 HTTP 服务器支持 |
| R25 | `tests/workbench/test_run_compute_support.py` | `run_compute_support.py` | 计算链路的真实 SQLite、台账及排产 fixture |
| R26 | `tests/workbench/test_run_history_support.py` | `run_history_support.py` | 任务历史的当前 schema 临时库与回执损坏辅助 |
| R27 | `tests/workbench/test_run_jobs_support.py` | `run_jobs_support.py` | 后台任务临时文件库与真实输入 fixture |
| R28 | `tests/workbench/test_run_runtime_support.py` | `run_runtime_support.py` | 任务运行时的真实磁盘库、启动锁和暂停计算 fixture |
| R29 | `tests/workbench/test_scheduler_execution_ledger_support.py` | `scheduler_execution_ledger_support.py` | 显式安装执行台账的真实排产 SQLite fixture |
| R30 | `tests/workbench/test_system_maintenance_support.py` | `system_maintenance_support.py` | 系统维护的可丢弃文件、库及 API fixture |
| R31 | `tests/workbench/test_system_restore_entrypoint_legacy_support.py` | `system_restore_entrypoint_legacy_support.py` | 在实际恢复控制器上复用旧恢复断言的 fixture |
| R32 | `tests/workbench/test_system_restore_entrypoint_process_support.py` | `system_restore_entrypoint_process_support.py` | 真实入口、工厂、服务、锁与退出处理的子进程驱动 |
| R33 | `tests/workbench/test_system_restore_entrypoint_support.py` | `system_restore_entrypoint_support.py` | 恢复入口的调用方私有进程、临时目录与端口支持 |
| R34 | `tests/workbench/test_system_restore_host_support.py` | `system_restore_host_support.py` | 恢复宿主的真实工厂、SQLite、启动锁 fixture |
| R35 | `tests/workbench/test_template_lineage_batch_support.py` | `template_lineage_batch_support.py` | 批次回归可显式选择的 lineage DDL pytest 插件 |
| R36 | `tests/workbench/test_template_lineage_support.py` | `template_lineage_support.py` | 批次、模板和台账的真实临时库 fixture |

R35 本次未发现可执行引用；保留其 fixture 及插件内容，不顺手删除、不自动启用。R08 当前只有文档/回执引用；未来有效命令为 `.venv/bin/python -B -m tests.workbench.final_master_acceptance_cli --phase <原值>`，已有旧命令回执保持原样。

## 必须同步的引用

- 594 处代码引用均在 [逐文件位置索引](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/full-gate/H10-executable-reference-index-20260910.md) 和 [完整 JSON](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/full-gate/H10-prospective-rename-plan-20260910.json)。JSON 同时给出旧文本、路径替换预览和 Python AST 导入/字符串位置；不允许对整个仓库盲目替换。
- 保留导入别名和 fixture 绑定：例如 `test_run_runtime_recovery.py:18` 的 `as support`、`final_operations_host.py:20` 的 `as driver` 必须原样保留。这里改模块路径，不改调用方变量名、参数、fixture scope、autouse、mark 或参数化 ID。
- 自启动/子进程字符串：R01 自身 `:52` 的 `-m`；`test_actual_gantt_ui.py:29`；`test_report_ledger_widgets.py:54`；R33 原文件 `:60` 的进程模块名；`test_run_runtime_recovery.py:115` 起的内嵌 Python 脚本也包含 R27 导入。
- CJS：`test_round1_field_piece_files_browser.cjs:11` 的 `tests.workbench.test_round1_field_piece_files_probe` 改为 `tests.workbench.round1_field_piece_files_probe`；同步 `test_workbench_round1_registry_contract.py:303` 的精确脚本文本断言。CJS 文件本身不改名。
- Registry 路径：`tools/test_registry_groups_workbench.py` 的精确 helper 输入项、`test_workbench_registry_contract.py`、`test_workbench_round1_registry_contract.py`、`workbench_round1_registry_support.py`、`test_long_gate_manifest.py` 的路径及指纹断言同步改为新路径。`scripts/workbench/profile_dense_resources.py:27,55` 的 fixture 导入也在清单内。
- `piece_main_seed.py:54` 的当前 fixture 来源说明同步改名；SQL fixture 内容、历史来源 SHA、过去的执行命令、归档报告和冻结回执不改写。未来实际仍使用的文档命令经 Main 确认为操作指引后更新，不能把旧回执改成仿佛运行过新命令。
- 同目录移动保持 `__file__.parent` / `parents` 的目录语义。未发现需要兼容 shim 的证据，不留下 `test_` 空壳，不新增假测试或 `__test__ = False`。

## Registry 保持项

- 已只读推演全部 48 组，含 33 required、15 supplemental；36 个文件均不是当前 required/startup/supplemental 的执行 target。
- 对精确 helper 输入路径应用 old/new 映射后，原有 scope owner 无丢失；泛型目录 glob 不扩大、不修改。机器结果 `helper_target_hits=[]`、`lost_scope_owners=[]`。
- 保留当前 583 项 required、17 项 startup 的原顺序，以及全部 48 组的执行 target 原顺序；本次不增减执行覆盖，不把 helper/CLI 升为 target。
- 当前 required hash 为 `9fcaf09048aedf041aca8e7b3e4b8460481fb99bbe02dd56b6702d5929a14495`；全部 48 组 target hash 为 `fb2dbd5c2ad9b5afaf1636abb1ee10b084159ab1ade643fb1ca826ed331121ad`。这是 H9 原授权补入最后 5 个真实测试后的观察值，不是允许覆盖历史 582/85 集合断言的新基线；H10 改名本身不增减任何 target。

## 缺失 Docstring

以下是逐文件真实用途建议，**尚未写入文件**。插入模块开头并置于 `from __future__ import annotations` 之前；不修改函数、断言或测试标记。前六个是原 tracked 命中，第七个是扩展后发现的 untracked 文件。

| 文件 | 建议的一句模块 docstring |
| --- | --- |
| `tests/algorithm/test_dispatch_callback_binding_contract.py` | `Verify dispatch callback binding failures preserve error classification and strict-call contracts.` |
| `tests/algorithm/test_dispatch_callback_signature_cache.py` | `Verify callback signature caches are bounded, mutation-aware and do not retain bound instances.` |
| `tests/algorithm/test_dispatch_callback_types_contract.py` | `Verify callback protocols match scheduler, fallback and auto-assignment keyword contracts.` |
| `tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_contract.py` | `Verify production elite repair preserves budgets, feasibility, strict improvement and audit reporting.` |
| `tests/algorithm/test_optimizer_graph_ready_v2_elite_repair_neighbors.py` | `Verify bounded reproducible elite-repair neighbors preserve graph precedence and fixed operations.` |
| `tests/schedule/summary/test_summary_build_context_typing.py` | `Verify SummaryBuildContext typing, dataclass semantics and dependency boundaries.` |
| `tests/workbench/test_report_export.py` | `Verify CSV/XLSX report exports cover the filtered cohort, preserve snapshots and reject stale scope.` |

配套 JSON 的 `docstring_plan.test_evidence` 给出每文件对应测试定义及行号；不是从文件名猜用途。

## 冻结后实施条件

1. Main 停止并行写入并明确授权统一机械迁移；重新记录 HEAD、index、源码 SHA，再用相同候选集算法扫描一次，复核新增候选、36 个源文件及其引用是否变化。任一目标出现冲突即停止该迁移，不覆盖、不合并。
2. 迁移前用私有临时目录跑全量 `pytest --collect-only -q -p no:cacheprovider tests`，保存真实退出码及完整 nodeid 多重集合。不能用旧的 15505 项收集记录替代这一步。
3. 在授权写集中同目录改名，并同步本报告代码引用；需要补模块说明时仅补上述说明。对改动执行反向路径归一化后的 AST 比较，保留 fixture 装饰器、别名、参数与业务断言；逐条审查动态字符串。禁止空测试、ignore、白名单或旧路径空壳。
4. 同一冻结输入、同一环境再跑完全相同的 collect 命令，比较全部 nodeid 多重集合，而不只比较总数。应无新增、无丢失、无重复、无 import/fixture 收集错误；若因模块身份或动态构造导致变化，先定位，不接受数字凑齐。
5. 跑受影响 registry/manifest 元测试并比较 required/startup/各组 target 原集合与顺序；候选 helper 新路径必须仍被原 owner 的输入 scope 覆盖。单独核对 CJS `-m` 命令及实际 CLI 路径，不能用空收集宣称 CLI 行为验证完成。
6. 重跑同口径 prospective AST/docstring/scope 扫描、Ruff、项目 Python 3.8 检查；Main 在最终入 Git 后跑正式门禁。源码仍 dirty 时只报告局部证据，不称 clean-worktree proof。

## 本轮辅助格式操作

- 仅对 `.codestable/issues/2026-09-10-fe-static-integration/analyze_evidence.py`、`capture_check.py` 运行 `ruff check --select I --fix --no-cache`，3 个 I001 全部清除；完整 diff 只含 import 排序。
- 导入绑定集合与非导入 AST 对比均相同，未运行这两份脚本的业务入口。证据为 `/tmp/aps-task-h-integration-20260910.l7JCYN/auxiliary-format-proof.json`。
- 紧随格式操作的全树 Ruff 只剩 `tests/workbench/final_operations_host.py:16` 的 I001，3650 个源码/配置前后 SHA 一致；随后 F 自行处理。最后 `ruff-delivery` 转为新到达的 `test_final_execution_rejections.py:22,62` 两个 F811，原 I001 不再命中；H 未代改 E/F 文件，完整时点见 H9 报告。

原始过程证据位于 `/tmp/aps-task-h-integration-20260910.l7JCYN`；配套 JSON 保留每份原始输入的完整 SHA。报告不是最终冻结后的迁移授权，也不是已完成迁移的声明。

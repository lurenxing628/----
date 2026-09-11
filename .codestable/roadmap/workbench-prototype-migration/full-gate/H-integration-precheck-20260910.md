# H: 当前源码集成预检

## H9/H10 交付状态

Main 已接受 H10 方案，并要求本轮正常收尾、停止原广域重扫。机械迁移继续等待源稳定、Main 的 Git 前置快照及唯一明确 GO；E 拒绝测试稳定后，与 D/E 后续新增真实测试合并做一次小增量登记。当前 131 项 supplemental 不作为最终门禁通过结论。

下面的首轮内容保留为历史，**不能再把首轮 SQL/仓储/循环/类型结果当作最新状态**。当前产品、测试仍在并行施工；每项结论仅绑定对应独立命令及 SHA，没有完整 19 步门禁或最终 clean-worktree proof。

- H10 的完整 prospective 命中、36 个精确改名计划、594 处可执行引用及 7 句 docstring 建议已单独落在 [H10 计划](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/full-gate/H10-prospective-rename-plan-20260910.md)。**未执行改名或补模块说明。**
- 全部命令、真实 exit code、源码前后变化、JUnit 失败原文与原始文件 SHA 已索引到 [H9/H10 过程证据](/Users/lurenxing/GitHub/----/.codestable/roadmap/workbench-prototype-migration/full-gate/H-integration-evidence-20260910.json)。原始目录仍为 `/tmp/aps-task-h-integration-20260910.l7JCYN`。
- H 没有执行 Git add/commit、产品修改、baseline/ignore 调整、业务容量或整应用浏览器。Main 的 `4b418d17` 及随后观察到的 `21134f73` 都是外部提交，不是 H 提交。

## 最新静态回执

| 检查 | 实际结果 | SHA 与时点边界 |
| --- | --- | --- |
| Product Pyright | `pyright-product-post-h10`: 1179 files，0 errors / 0 warnings，exit 0 | 3650 个纳入源码/配置前后 SHA 一致；已覆盖新增 actual_gantt_chain 和原链引擎 keyword 改动。旧的 4 个 Optional 诊断不再保留为未修复。 |
| Tools Pyright | `pyright-tools-delivery`: 62 files，0 errors / 0 warnings，exit 0 | 3658 个纳入源码/配置前后 SHA 一致，已绑定最后 40 个登记版本。 |
| 生产 import cycles | `import-prod-post-h10`: 1260 modules，exit 0 | 新目录/文件环、圈内边、动态未解析增量全空，parse_errors=[]；仍有 baseline 内 8 个文件环与 5 个动态未解析点。 |
| 含测试 import cycles | `import-tests-post-h10`: 2676 modules，exit 0 | 同样所有增量为空，parse_errors=[]；baseline 内 8 个文件环、43 个动态未解析点。两套 baseline SHA 保持原值，未刷新。 |
| 架构/规模 | `architecture-post-h10`: 20 passed / 1 failed，exit 1 | 3652 个源码/配置前后 SHA 一致，包含技术债务台账。SQL/仓储越层及 F 域旧 3 个复杂度问题均已清除；规模检查通过。 |
| Ruff | `ruff-delivery`: 2 个 F811，exit 1 | 3658 个源码/配置前后 SHA 一致。原 I001 已全部不再命中；新到达的 `test_final_execution_rejections.py:22,62` 重定义了 `:13` 导入的 fixture 名。交 E/Main，不代改。 |
| 正式 Python 3.8 范围 | `py38-gate-scope`: exit 0 | 使用正式 `scan_aps_three_gap_py38_scope --base-ref d4589d77` 的限定范围，不能与下方扩展扫描告警混为一谈。 |

截至架构补扫，仍需 Main/E 处理的是以下 **3 处复杂度**，不是运行时错误结论：

| 位置 | 复杂度 | 绑定源码 |
| --- | ---: | --- |
| `core/services/workbench/actual_gantt.py:90 workspace` | 16 | `34b01feba22dab22da0ea13c08f09c8493cee5867e43118cbe9cd7acc026f472` |
| `core/services/workbench/actual_gantt_chain.py:56 _result_valid` | 26 | `50cb449efa67784d74d51b6f5e638e188c47e8e9d4e07f9f73ee0696d67d017a` |
| `core/services/workbench/actual_gantt_chain.py:78 plan_chain` | 21 | 同一 `50cb449e...`；增加 mapping 判空后由先前 20 变为 21，不能沿用旧数。 |

旧链引擎文件本次观察 SHA 为 `abd6ee8660cceb211c40ff6d0f1ac8c04792adf4cf95a9e36be119944d8286e0`。只读 diff 可确认 `target_id` 是 keyword-only 且默认 `None`；默认分支仍建立完整原控制图、调用 `_sink_id` 后原样回溯，显式目标只改变 sink 选择。原默认调用路径未在 diff 中改成新算法；这是静态代码审查，不等于本轮重新运行算法行为回归。

## H9 登记收尾

- 在原授权 3 文件内，共显式接入 **40 个真实测试文件**：35 个既有本轮接入，加后来抵达的校准表、资源分页、旧报表日期、运维异常边界、运维在途恢复 5 个文件。最后 5 个唯一 owner 均为 `workbench_browser` supplemental。
- 当前 required 保持 583 项、33 组，startup 17 项；supplemental 131 项、15 组。移除仅这 40 个明确新增项后，原全部 48 组 target 顺序/hash 与 H9 起始观察一致，没有丢 target、降 owner 或改变历史 582/85 合同。
- 新增 6 个环境指纹键：`FINAL_E_PARENT`、`FINAL_E_SHARED_BUILD`、`FINAL_E_SHARED_BUILD_ID`、`FINAL_OPERATIONS_BUILD`、`FINAL_PLANNING_BUILD`、`FINAL_PLANNING_TEMP_PARENT`。三份 action/capability JSON 及容量组真实产品输入闭包已纳入；没有为 nonexistent glob 建新例外。
- 验证按真实版本分开：34 个接入时完整两文件 **1025 passed**；35 个接入时定向 **46 passed**；最后 40 个接入时 **51 passed / 980 deselected**，源码前后 SHA 一致。**没有在最后 40 个版本上再声称完整 1025 项通过。**
- 另有 asset script-scope **17 passed**，仅 Babel/脚本作用域，不是实际 UI build；环境指纹 **12 passed**。全 tests collect-only **15505 collected**，不是 15505 passed，也不是改名配对证明。
- 最后 51 项验证以后又出现 `tests/workbench/test_final_execution_rejections.py`：在交付索引的独立发现快照中尚未登记，且该版本有上述 F811。它不属于已经通过的 40 个接入清单，待 E 文件稳定后下一轮接入；不隐瞒这个新增尾项。

## H 本轮写集

- Registry：`tools/test_registry_groups_workbench.py`、`tests/gate_meta/test_workbench_registry_contract.py`、`tests/gate_meta/workbench_round1_registry_support.py`，只做显式 owner、输入/环境指纹及对应合同测试。
- Main 在 H10 另行授权的两份辅助脚本：`.codestable/issues/2026-09-10-fe-static-integration/analyze_evidence.py`、`capture_check.py`，只运行 import formatter；导入绑定集合及非导入 AST 均不变。
- 本报告、过程证据 JSON 与三份 H10 计划/引用产物。以上仍是工作区未提交内容；H 未接管其他人的 staged、unstaged 或 untracked 文件。

## Modal 与观察限制

- Modal 的既有唯一 owner 仍是 `workbench_browser_opt_in`，ResourceControls.jsx 与 modal_focus_probe.cjs 已被输入范围覆盖，无重复登记。
- Main 后续给出的 ResourceControls SHA `1bed5a0d7e1afd6164064683e73d3998def9720c99e03ead1e49a360d40f6ac1` 和 ResourceTableFilter SHA `b6d6f18afaec9147b9d13422efcd9d4c622ce47aefbb308c3febea746537eb42` 已只读核验。80/64 结果仅标注为 Main 提供的 component simulated-adapter 结果，不是 H 运行，也不是 app/DB 证明。
- 旧四组合回执保持绑定旧字节，不改造成新版 80/64 证据。首轮 architecture 的观察集合没有包含非代码债务台账；后续 `architecture-bound` 与 `architecture-post-h10` 已明确纳入，不能补造首轮冻结声明。
- 工作区持续变化，多个独立“命令执行前后 SHA 相同”并不拼成一个跨所有命令的冻结快照。最终改名须 Main 授权及配对 collect；最终完整 19 步仍留待最终 HEAD。

---

以下为首轮历史记录，留作问题收敛过程证据。

## 第一轮结论

- 工作区 HEAD 观察为 `4b418d1784947abb7eef5e2747cd05b5c83b171f`；原工作区 dirty，以下不是 Main 私有目标的 clean proof，也不是最终 HEAD 全门禁。
- 没有启动完整 19 步门禁、业务容量、浏览器或完整构建；各独立命令都在私有目录记录源码前后 SHA、真实退出码和完整输出。
- 首轮证据目录：`/tmp/aps-task-h-integration-20260910.l7JCYN`。每项检查都有 `sources.before.json`、`sources.after.json`、`result.json`、`stdout.txt`、`stderr.txt`。

## Main 产品待办

| 检查 | 精确位置 | 事实与处置边界 |
| --- | --- | --- |
| Import cycles | `web/routes/workbench/legacy_navigation_plan.py:21` | 顶层依赖 `web.routes.report_plan_preview`，导致现存目录 SCC 新增 workbench 成员。生产/含测试扫描都 exit 1，新增目录签名 `.|web/bootstrap|web/routes|web/routes/workbench`。没有新增硬文件环/圈内边/动态未解析点；不是已证实的运行时 ImportError。 |
| 路由直接 SQL | `web/routes/workbench/legacy_navigation.py:82` | 路由层直接 SELECT；迁回所属服务/仓储边界，不改检测规则。 |
| 路由导入仓储 | `web/routes/workbench/legacy_navigation.py:12` | 直接导入 WorkbenchIdentityRepository。 |
| 路由导入仓储 | `web/routes/workbench/legacy_navigation_plan.py:18`、`:19` | 直接导入 ScheduleHistoryRepository / WorkbenchPlanIdentityRepository。 |
| 复杂度 | `core/services/workbench/dashboard_analysis.py:76` | `_downtimes` 19，门限 15。 |
| 复杂度 | `core/services/workbench/dashboard_resource_metrics.py:49` | `daily_resource_pressure` 26，门限 15。 |
| 复杂度 | `web/routes/workbench/system_backup_export.py:16` | `_selected_bytes` 16，门限 15。 |

H 不修改这些产品文件，不增加 baseline、allowlist 或 ignore。架构适应度实际为 **18 passed / 3 failed**；其中文件规模门限检查通过。

## Ruff 待办

首轮 **9 个 I001 / 8 个文件**，真实 exit 1；执行前后当时纳入的 3603 个源码/配置文件 SHA 一致。

- `.codestable/issues/2026-09-10-fe-static-integration/analyze_evidence.py:3`、`:16`
- `.codestable/issues/2026-09-10-fe-static-integration/capture_check.py:3`
- `tests/workbench/test_final_execution_controls.py:3`
- `tests/workbench/test_piece_downstream_api.py:122`
- `tests/workbench/test_round1_field_piece_files.py:3`
- `tests/workbench/test_round1_field_piece_files_browser.py:3`
- `tests/workbench/test_round1_field_piece_files_contract.py:3`
- `tests/workbench/test_round1_field_piece_files_support.py:3`

这些文件不在本轮 H 原授权登记写集内，交 Main 协调。不得把真实本地模块标成 third-party，也不跳 hook。

## 类型与兼容

- 正式 product Pyright：1173 files，**0 errors / 0 warnings**。执行期间 `frontend/workbench/app/ResourceTableFilter.jsx` 发生修改，单独保留前后 SHA，不能声称全源码冻结。
- 正式 tools Pyright：62 files，**0 errors / 0 warnings**。
- 扩展到完整产品/测试/工具目录的 Python 3.8 扫描：2654 files，8 个 PEP585 告警，均 `future_annotations=true`。这是扩展扫描结果，不直接升级为新运行时故障，也不冒充正式 19 步中限定范围的扫描结论。
- 8 个位置：`core/services/common/build_outcome.py:47`；`core/services/scheduler/config/config_page_save_policy.py:33,42,78`；`config_page_save_service.py:55`；`config_read_service.py:480`；`web/viewmodels/system_backup_page.py:180,231`。

## 防回潮

`tools/scan_anti_regression_gate.py --base-ref d4589d77` 实际 exit 1：

- 缺 test 函数：`tests/workbench/test_master_overview_support.py`、`test_process_file_hours_support.py`、`test_resource_file_support.py`、`test_template_lineage_batch_support.py`。
- 缺模块 docstring：`tests/algorithm/test_dispatch_callback_binding_contract.py`、`test_dispatch_callback_signature_cache.py`、`test_dispatch_callback_types_contract.py`、`test_optimizer_graph_ready_v2_elite_repair_contract.py`、`test_optimizer_graph_ready_v2_elite_repair_neighbors.py`、`tests/schedule/summary/test_summary_build_context_typing.py`。
- 不以新增 ignore 或把 helper 冒充测试的方式消除告警。

## 登记处理中

- 完整两份 registry 元测试 **979 passed / 1 failed**；唯一失败为 31 个真实 pytest 文件缺少 owner。H 在授权写集内补登记，保留全部旧 target 和历史 582/85 合同，结果稍后追加。
- helper / CLI / CJS probe 不按文件名假造 pytest target。登记不意味着这些域测试已经执行。
- Registry 执行期间新增的 `legacy-retirement/factory-tests/factory_messages_worker.py` 已记录为外部施工漂移，不计入 H 修改。

## Modal 证据

- Main 提供的产品 SHA 已核对：`996b7e3f5d3cb4614f5b969521c89e47ca31bbdd55a357972bdb6779a85ae59c`。
- `test_modal_focus_browser.py` 现有唯一 owner 为 `workbench_browser_opt_in`，ResourceControls.jsx 与 modal_focus_probe.cjs 均已受依赖范围覆盖，无需重复登记。
- Main 的四组合结果仅按 component simulated-adapter 收录，未运行全 app / DB；H 不改写为整应用证明。

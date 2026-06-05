# L3 全量逐文件裁决报告（2026-06-05 重做）

> 配套：`GOVERNANCE.md`（总纲）、`BASELINE.md`、`L3_verdicts.csv`（机器可读全量裁决）、`test_inventory.csv`（L2 结构清单）、`raw_verdicts/`（12 批原始裁决）。
> 方法：12 路 SubAgent 并行，对**当前 645 个测试文件逐个 Read 精读**（非抽样，每文件读实际断言 + Grep 追被测对象），产出逐文件裁决。完成 645/645，0 遗漏。
> 本版基于当前仓库（645 文件），替换 6-01 旧版（607 文件，已因 +38 文件过时）。

---

## 一、全量裁决分布

### 按文件数（645）
| 裁决 | 文件数 | 含义 |
|---|---|---|
| **KEEP** | 427 | 真实业务逻辑/算法/边界，原样保留 |
| **KEEP_TRIM** | 123 | 逻辑有价值但夹脆性快照尾巴，保留逻辑删尾 |
| **MERGE** | 39 | 同契约参数化合并（11 多文件簇 + 6 单文件挂靠）|
| **DROP** | 38 | 纯快照/死代码/测第三方，整删 |
| **ISOLATE_PERF** | 8 | 性能基准/重 E2E，标记隔离非删 |
| **DROP_WITH_TOOL** | 7 | 门禁自指，随对应工具删除 |
| **REWRITE** | 3 | 测保留工具但断言脆，重写为非脆性 |

> ※ **B-COMPAT 调整后真值（2026-06-05，见 `_B_COMPAT_SAFEGUARDS.md` §6）**：因与 80 债交接，csv 微调 3 个文件 → **KEEP 429**（+2：architecture_fitness、sort_priority）、**MERGE 37**（-2）、**DROP_WITH_TOOL 6**（-1：architecture_fitness 移出）、新增 **`HOLD_FOR_R51` 1**（sort_strategy 绑 R51 退场）。上表为 L3 原始裁决快照，总数 645 不变。

### 按代码行数（161986）
| 裁决 | 行数 | 占比 |
|---|---|---|
| KEEP | 96991 | 59.6% |
| **KEEP_TRIM** | **45778** | **28.2%** |
| MERGE | 6662 | 4.1% |
| DROP | 4658 | 2.9% |
| ISOLATE_PERF | 5121 | 3.2% |
| DROP_WITH_TOOL | 2031 | 1.3% |
| REWRITE | 1390 | 0.9% |

### 关键结论：直接删除空间小，价值在剪尾 + 提速 + 转范式

- **直接可删（DROP+DROP_WITH_TOOL+MERGE）= 8.2% 行 / ~9% 文件**。按文件数清理后约 589（-9%）。
- **KEEP_TRIM 占 28.2% 行**——这是"真测试 + 脆性快照尾巴"的混合体，剪尾才是行数收益大头，且直接消除"改文案/CSS 就红"。
- **真实删除空间不大 = 测试整体在测真东西**，冗余主要是"啰嗦写法（main-style 样板）+ 脆性尾巴 + 门禁自指"，不是"大量无用测试"。

---

## 二、安全删除清单（DROP，38 个）

完整清单：`L3_verdicts.csv` 筛 `verdict=DROP`。已逐一对账：无一落入第五章 load-bearing 清单。分三类：

### 2.1 纯模板/CSS/JS 字符串快照（约 24 个，病根：把快照当契约）
命名多带 "contract" 伪装，实则断言 `aps-xxx` class / grid-template / 像素值 / JS 符号出现在源码中，改个 class 名就红：
```
regression_action_card_button_layout_contract.py    regression_calendar_layout_contract.py
regression_dashboard_workspace_layout_contract.py   regression_equipment_downtime_batch_layout_contract.py
regression_gantt_layout_contract.py                 regression_material_batch_info_layout_contract.py
regression_reports_layout_contract.py               regression_scheduler_config_layout_contract.py
regression_scheduler_run_entry_layout_contract.py   regression_system_logs_layout_contract.py
regression_table_layout_readability_contract.py     regression_ui_contract_table_overflow_guard.py
regression_ui_layout_risk_contract.py               regression_stable_form_layout_allowlist.py
regression_responsive_min_width_contract.py         regression_page_header_plain_purpose_contract.py
regression_scheduler_page_header_contract.py        regression_frontend_common_interactions.py
regression_scheduler_ui_range_feedback_contract.py  regression_scheduler_analysis_template_parts.py
regression_new_ui_strict_mode_controls_present.py   regression_mirror_template_sync.py
regression_ui_copy_plain_language.py                regression_frontend_manual_blueprint_contract.py
```

### 2.2 反向结构守卫（把 lint 写成测试，约 5 个）
断言"某符号**不**出现在源码"或 AST 查重，本质是 lint：
```
test_phase6_no_result_summary_route_parser.py   test_phase6_no_route_version_parser.py
regression_sp05_followup_contracts.py           regression_sp06_no_duplicate_defs.py
test_sp05_path_topology_contract.py
```
> 建议：有价值的约束转成 ruff 规则或 `quality_gate_scan` 扫描项，不占测试位。

### 2.3 文档/常量快照 + 死代码（剩余）
```
test_quality_workflow_cache.py            # 断言 quality.yml 的 action SHA/cache-key 字面量
test_evidence_audit_entrypoints.py        # 断言 README 硬编码日期/文案
regression_excel_entry_consolidation.py   # 断言 ~20 页精确中文子导航文案
regression_unit_excel_converter_facade_binding.py  # getsource 类计数+hasattr 重构残留守卫
regression_excel_batch_template_default_ready_date.py  regression_gantt_simulation_entry_shell.py
regression_scheduler_candidate_py38_contract.py    regression/regression_collection_contract.py
verify_installer_vendor_dir.py            # 门禁实际失效:vendor/.gitkeep 已提交,hard-fail 分支永不触发
```

---

## 三、随工具删除清单（DROP_WITH_TOOL，7 个）

门禁自指测试，**与 GOVERNANCE P2 门禁瘦身绑定**：删对应工具时一起删（grep 证明 core/web/app 对 tools/ 零引用）。
```
check_quickref_vs_routes.py                          # 门禁工具本体(非测试),比对 docs vs url_map
regression_quality_gate_registry_split_scope_contract.py  # 门禁注册表自指簿记
test_codestable_architecture_contract.py             # 测 .codestable/tools 基建
test_architecture_fitness.py                         # 注意:虽列此,但它验证业务架构合规(route不直连SQL等),应 KEEP/保留——见下注
test_post_change_check_contract.py                   # 测 .limcode post_change_check gate runner
test_regression_main_isolation_contract.py           # 测 conftest 子进程收集机制(P3 删 collector 后随之处理)
test_run_full_selftest_report_metadata.py            # 测 selftest runner + proof-manifest
```
> ⚠️ **裁决修正（已在 csv 落实）**：`test_architecture_fitness.py` 被 agent 归入 DROP_WITH_TOOL，但它验证的是**业务代码架构合规**（route 不直连 SQL、viewmodel 不 import flask/service/repo、无循环依赖），即使门禁缓存层被砍仍有独立价值；它还是 **B 全批次 go-no-go 门禁载体**（承载 STARTUP_SAMPLE_EXPECTATIONS + R28 白名单 + silent_fallback 台账）。**`L3_verdicts.csv:620` 已就地改回 `KEEP`**（消除 B-11 埋雷，与本正文一致）——严禁裸筛 csv `DROP_WITH_TOOL` 后 `git rm`。`test_regression_main_isolation_contract.py` 在 P3 移除 main-style collector 后失去对象，届时一并清理。

---

## 四、合并簇（MERGE，39 文件 → 11 多文件簇 + 6 单挂靠，净减 11）〔L3 原始快照；B-COMPAT 解散 sort_strategy 簇后真值 = MERGE 37 / 10 多文件簇 + 6 单挂靠 / 净减 9，见 §1 脚注〕

### 4.1 多文件簇（11 个，每簇独立 commit）
| 簇 | 文件 |
|---|---|
| `excel_import_apply_defense`(6) | test_{machine,op_type}_excel_import_apply_defense / test_operator_excel_import_normalization / test_part_operation_hours_import_apply_defense / test_part_operation_hours_import_apply_mixed_rows / test_supplier_excel_import_remark_normalization |
| `gantt_degradation_surface`(4) | regression_gantt_{bad_time_rows_surface_degraded,calendar_load_failed_degraded,invalid_summary_surfaces_overdue_degraded,partial_overdue_summary_surfaces_warning} |
| `seed_results_dedup`(4) | regression_seed_results_{dedup,drop_duplicate_op_id_and_bad_time,freeze_missing_resource,invalid_op_id_dedup} |
| `workbench_context_propagation`(3) | regression_aps_workbench_{first_round_flow_contract,flow_contract,report_row_links_contract} |
| `request_services`(3) | regression_request_services_{contract,failure_propagation,lazy_construction} |
| `real_db_replay_e2e`(3) | run_real_db_replay_{check,e2e,smoke}（⚠️ e2e 是 load-bearing，保留 e2e、删 check/smoke）|
| `batch_service_strict_mode_template`(2) | regression_batch_service_{legacy_template_resolver_rejects_strict_mode,strict_mode_template_autoparse} |
| `workbench_links_viewmodel`(2) | regression_scheduler_workbench_{link_guardrails,links_contract} ⚠**B-2：禁对 guard 四态断言去重（R54/LB02/LB05），与 B 的 G04/G05 错开窗口，见 `_B_COMPAT_SAFEGUARDS.md`** |
| `route_parser_supplier_default_days`(2) | regression_route_parser_supplier_default_days_zero_trace / regression_supplier_effective_selection_contract |
| ~~`sort_strategy_case_insensitive`(2)~~ **已解散** | 🔴**B-1 BLOCKER**：`regression_sort_strategy_case_insensitive.py`→`HOLD_FOR_R51`（绑 B-R51 灵魂线整体退场，A 不合并·不剪·不删，:25 坏值兜底断言保留=焊死 P4）；`regression_sort_strategies_priority_case_insensitive.py`→独立 `KEEP`（StrategyFactory 存活算法，与 parse_strategy 无关，两文件契约不同原合并判定有误）。见 `_B_COMPAT_SAFEGUARDS.md` B-1 |
| `scheduler_route_registration`(2) | test_scheduler_route_registration_contract / test_scheduler_routes_still_registered_by_factory |

### 4.2 单文件挂靠（6 个，并入已有 KEEP 锚点）
```
regression_config_validator_relaxed_contract.py        -> config_validator_contract
regression_process_excel_part_operation_hours_import.py -> process_excel_part_op_hours
regression_reports_material_weekplan_pages_smoke.py    -> reports_route_smoke
regression_resource_dispatch_partial_overdue_summary_surfaces_warning.py -> resource_dispatch_overdue_surface
test_transaction_boundary.py                           -> transaction
test_version_resolution_contract.py                    -> version_resolution
```

### 4.3 做法
每簇：抽公共 fixture → `@pytest.mark.parametrize` 收差异 → 合并 → `git rm` 原文件 → 跑定向测试 → 核对断言条数 ≥ 合并前之和（去重）。

---

## 五、KEEP_TRIM（123 个，28.2% 行）—— 剪脆性尾收益大头

逻辑有价值但夹脆性快照尾巴。处理：保留真实断言，删脆性尾（JS 源 grep / CSS 像素 / 整页文案 / openpyxl 布局 / 精确中文 exact-match→改"含关键片段"或 ErrorCode）。

**行数最大、剪尾收益最高的 12 个**：
```
2970行 test_run_quality_gate.py（门禁自测,断言 CI action SHA + 硬编码 nodeid 清单）
1987行 regression_gantt_critical_outline_sync.py
1919行 test_win7_launcher_runtime_paths.py（~22 个对 .iss/.bat/.ps1 源码 grep）
1449行 test_full_test_debt_registry_contract.py
1154行 regression_scheduler_config_route_contract.py
1117行 test_greedy_refactor_contracts.py
 988行 regression_page_manual_registry.py（100+ 行精确中文文案）
 970行 test_git_hook_checks.py
 909行 test_scheduler_run_view_result_contract.py
 845行 regression_frontend_ui_language_polish.py（文案黑白名单）
 843行 regression_excel_template_contracts.py
 781行 run_complex_case_and_export_gantt.py
```

---

## 六、ISOLATE_PERF（8 个）—— 标记隔离非删

性能基准/重 E2E，时间阈值/重浏览器，应标 `@pytest.mark.perf` 或 `@pytest.mark.slow`，从 push 路径剔除、CI 独立 job（避免抖动 + 不拖 push）：
```
scheduler_graph/test_graph_performance.py（2000-5000节点ms阈值）
regression_scheduler_candidate_performance_guard.py（EXPLAIN QUERY PLAN索引断言）
regression_ui_browser_geometry_smoke.py（真浏览器,19.37s 最慢）
run_complex_excel_cases_e2e.py（随机fuzz E2E）  smoke_e2e_excel_to_schedule.py（全链路happy-path）
benchmark_sgs_large_resource_pool.py  benchmark_fjsp.py（FJSP基准）  run_synthetic_case.py
```

---

## 七、REWRITE（3 个）

测保留的工具但断言脆，重写为非脆性：
```
long_gate_cache_helpers.py（共享脚手架,无test函数,P3抽fixture时整理）
regression_excel_routes_no_tx_surface_hidden.py（源码grep守卫,转lint或断行为）
generate_conformance_report.py（grep源码中文串/默认值,改断行为）
```

---

## 八、务必保留的高价值锚点（KEEP，427 个中的核心）

各 agent 实读确认的真实业务护栏（删了会漏真 bug）：
- **调度核心**：schedule_summary_v11_contract、schedule_orchestrator_contract、freeze_window_bounds/fail_closed、ortools_warmstart_failure_contract、sgs_scoring_fallback_unscorable、optimizer_seed_boundary、greedy_ordering_contract
- **数据域**：calendar_shift_start_rollover（跨天工时）、calendar_invalid_shift_window（NaN/Inf/bool 边界）、excel_import_executor_status_gate、excel_failure_semantics_contracts、unit_excel_converter_merge_steps（换算算法）、supplier_effective_selection、operation_execution_state_revision（状态机+threading 并发）
- **系统域**：migrations（v14/v15 不丢行+约束）、migrate_v4_sanitizers（SQL 注入防护）、transaction_savepoint_nested、maintenance_window_mutex（线程互斥）、backup_restore_pending_verify_code、factory_request_lifecycle_observability
- **架构守卫**：`test_architecture_fitness.py`（业务架构合规，见三章修正）
- **graph 子目录**：17 文件整体保留（仅 test_graph_performance 隔离）

### 不可删 load-bearing 脚本（禁止 git rm）
- `run_complex_case_and_export_gantt.py`（被 regression_gantt_critical_outline_sync importlib 加载）
- `run_complex_excel_cases_e2e.py` / `run_real_db_replay_e2e.py`（被 regression 测试 import + 门禁扫描契约依赖）
- `tools/full_test_debt_shards.py`（被多处依赖）

---

## 九、伪装成业务测试的快照文件（专项提醒）

L3 揪出的"名字像业务测试、实则快照"——按文件名永远发现不了：
| 文件 | 伪装 | 真相 |
|---|---|---|
| `test_quality_workflow_cache.py` | 像缓存策略 | quality.yml 的 YAML 快照（action SHA） |
| `regression_new_ui_strict_mode_controls_present.py` | 像 strict-mode 行为 | grep 模板宏调用 |
| `regression_sp05_followup_contracts.py` | 带 "contracts" | grep 源码 helper 名 |
| `verify_installer_vendor_dir.py` | 像构建防护 | 门禁实际失效（永不触发）|
| `test_evidence_audit_entrypoints.py` | 像审计入口 | README 文案/日期快照 |

---

## 十、机器可读产物
- `L3_verdicts.csv`：645 行，字段 `file,verdict,value,reason,merge_cluster,batch`。
- `test_inventory.csv`：L2 结构清单（行数/函数数/断言数/断言类型/被测模块/分类）。
- `raw_verdicts/B*.csv`：12 批原始裁决（防 /tmp 丢失的备份）。
- `summary.json` / `baseline.json`：统计与基线。

执行各 Phase 时从 `L3_verdicts.csv` 取对应 verdict 文件清单，reason 列附 file:line 证据。

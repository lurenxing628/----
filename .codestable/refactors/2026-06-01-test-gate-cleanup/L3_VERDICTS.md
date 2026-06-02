# L3 全量逐文件裁决报告

> 配套：`PLAN.md`（计划）、`BASELINE.md`（度量）、`L3_verdicts.csv`（机器可读全量裁决）、`test_inventory.csv`（L2 结构清单）
> 方法：12 个 SubAgent 并行,**逐个精读全部 597 个测试文件**（非抽样,每个文件 Read 实际断言 + Grep 追被测对象到 core/web/）,产出逐文件裁决。
> 完成：2026-06-01。597/597 文件全部有裁决,0 遗漏。

---

## 一、全量裁决分布

| 裁决 | 文件数 | 含义 |
|---|---|---|
| **KEEP** | 362 | 真实业务逻辑/算法/边界,原样保留 |
| **KEEP_TRIM** | 77 | 逻辑有价值但夹带脆性快照尾巴,保留逻辑、删快照断言 |
| **MERGE** | 105 | 与同簇文件测同一契约,参数化合并（→48 个簇） |
| **DROP** | 32 | 纯快照/测第三方库/文案逐字匹配/死代码,可删 |
| **DROP_WITH_TOOL** | 18 | 门禁自指测试,Phase 2 删对应工具后随之消失 |
| **REWRITE** | 2 | 测保留的工具但断言脆,需重写为非脆性 |
| **ISOLATE_PERF** | 1 | 性能基准,标 `@pytest.mark.perf` 隔离而非删 |

价值分布：high 346 / mid 174 / low 52 / self-ref 25。

### 关键修正：L3 比 L1 抽样保守

| 估算来源 | 清理后文件数预测 |
|---|---|
| L1 域级抽样 | ~370（-39%） |
| **L3 全量精读** | **~490（-18%）** |

**为什么 L3 更保守 = L3 更可信**：逐文件读完后发现,调度核心（134 文件,0 个 DROP）和系统域（74 文件,1 个 DROP）几乎全是真实业务覆盖,抽样时按"同主题文件名"高估了可删量。**L3 精读防止了过度删除——这正是你要求精读的价值。** 真实可净减约 107 文件（DROP 32 + DROP_WITH_TOOL 18 + MERGE 净减 57）,再扣除 D-1 决策保留的 smoke（11 个不删）,净减约 96 文件 → **约 500 文件**。

> 注：文件数降幅不大,但**真正的体验收益在另外三处**:① KEEP_TRIM 的 77 个文件删掉脆性快照尾巴后,改文案/CSS 不再误报红;② DROP_WITH_TOOL 18 个 + Phase 2 脚手架瘦身,删掉 ~16000 行门禁自指代码;③ Phase 3 把 196 个子进程转 pytest,省 ~45s 墙钟。文件计数只是表象,**脆性消除 + 代码瘦身 + 跑得快**才是实质。

---

## 二、安全删除清单（DROP，32 个）

已逐一对账：**无一个落入第 8 章 load-bearing 清单**。分三类：

### 2.1 纯模板/CSS/JS 字符串快照（18 个，病根三铁证）
全部命名带 "contract" 伪装成契约,实则断言 `aps-xxx` class / grid-template / 像素值 / JS 函数名出现在源码中,改个 class 名就红、抓不到 bug：
```
regression_action_card_button_layout_contract.py
regression_calendar_layout_contract.py
regression_dashboard_workspace_layout_contract.py
regression_equipment_downtime_batch_layout_contract.py
regression_frontend_common_interactions.py
regression_gantt_layout_contract.py
regression_material_batch_info_layout_contract.py
regression_new_ui_strict_mode_controls_present.py
regression_page_header_plain_purpose_contract.py
regression_reports_layout_contract.py
regression_responsive_min_width_contract.py
regression_scheduler_config_layout_contract.py
regression_scheduler_page_header_contract.py
regression_scheduler_run_entry_layout_contract.py
regression_scheduler_ui_range_feedback_contract.py
regression_stable_form_layout_allowlist.py
regression_system_logs_layout_contract.py
regression_table_layout_readability_contract.py
regression_ui_contract_table_overflow_guard.py
regression_ui_copy_plain_language.py
regression_ui_layout_risk_contract.py
```
> 这些是 Phase 1.5「删 CSS 视觉快照」的扩大版——L3 发现整文件都是快照,可整文件删而非只删断言行。

### 2.2 反向结构守卫（把 lint 写成测试，3 个）
断言"某函数/字符串**不**出现在源码中",本质是 lint 规则,改实现即误报：
```
regression_excel_routes_no_tx_surface_hidden.py   # grep 源码确认 _no_tx( 不出现
regression_sp05_followup_contracts.py             # grep py/html 确认 helper 名存在
test_phase6_no_result_summary_route_parser.py     # grep 确认 json.loads 不出现
test_phase6_no_route_version_parser.py            # grep 确认 version-parser 已移除
```
> 建议：若这些约束有价值,转成 ruff 自定义规则或 `quality_gate_scan` 扫描项,不要占测试位。

### 2.3 文档/常量快照 + 死代码（剩余）
```
regression_frontend_manual_blueprint_contract.py  # 逐字校验 docs md + git commit hash 552b2916
regression_excel_entry_consolidation.py           # 断言 ~20 页精确中文子导航文案
test_evidence_audit_entrypoints.py                # 断言 README 硬编码日期 2026-05/2026-04-25
regression_unit_excel_converter_facade_binding.py # getsource 类计数 + hasattr 重构残留守卫
benchmark_fjsp.py                                 # 700 行基准生成器,urllib 下载外网数据集,无断言
tests/regression/__init__.py                      # 仅 docstring
tests/regression/regression_collection_contract.py # main() return 0 收集探针
```

---

## 三、随工具删除清单（DROP_WITH_TOOL，18 个）

这些是"门禁测门禁自己"的纯自指测试（value 全部 self-ref,0 个 high）。**与 Phase 2 门禁瘦身绑定**：删对应工具时一起删,业务零影响（grep 证明 core/web/app 对 tools/ 零引用）。
```
check_quickref_vs_routes.py（注:这本身是工具不是测试,0个test_函数）
test_check_quickref_vs_routes.py
test_architecture_scan_cache.py        ← Phase 2 删 architecture_scan_cache.py
test_check_full_test_debt.py
test_collect_full_test_debt_sharded.py
test_full_test_debt_shards.py
test_benchmark_full_test_debt_shards.py
test_report_full_test_debt_durations.py  ← Phase 1 已删
test_verify_required_regressions_from_full_test_debt.py  ← Phase 2 M4 删工具
test_long_gate_cache.py
test_long_gate_cli_controls.py
test_long_gate_full_test_debt_cache.py  （4052 行,单文件最大）
test_long_gate_manifest.py
test_long_gate_summary_output.py
test_git_hook_checks.py
test_run_quality_gate.py                （2969 行,断言钉死 CI action SHA + 80 条硬编码 nodeid）
test_run_daily_quality_gate.py
test_sync_debt_ledger.py                （2756 行,~30 处 pytest.raises 精确中文文案）
```
> ⚠️ 这 18 个不是无脑删——取决于 Phase 2 对每个工具的最终处置（删/简化/保留）。工具保留则其测试改 REWRITE（去脆性）;工具删则测试随之删。`regression_quality_gate_scan_contract.py` 是唯一例外（KEEP）——它测的 `quality_gate_scan` 即使缓存层被砍仍保留,且验证业务架构合规。

---

## 四、合并簇全图（MERGE，105 文件 → 48 簇，净减 57）

### 4.1 多文件簇（33 个，按可消除文件数排序）

| 簇 | 文件数 | 决策对账 |
|---|---|---|
| `smoke_phase_suite` | 9 | ⚠️ **D-1 已决定保留 smoke,不合并**。L3 建议合并但与决策冲突,以决策为准 |
| `long_gate_entry_cache_template` | 5 | ✅ Phase 2.A 主目标,参数化合 1 |
| `app_new_ui_bootstrap` | 4 | ✅ Phase 3 转 pytest 时顺便合并 |
| `gantt_degradation_surface` | 4 | ✅ Phase 4.3,退化引擎下沉 service |
| `optimizer_multistart_contract` | 4 | ✅ Phase 4.1,共用 _RecordingScheduler |
| `route-parser-supplier-fallback` | 4 | ✅ Phase 4.2 |
| `dispatch_degradation_surface` | 3 | ✅ Phase 4.3,与 gantt 簇合成矩阵 |
| `dispatch_rules_contract` | 3 | ✅ Phase 4.1,同文件 3 个 test |
| `summary_result_contract` | 3 | ✅ Phase 4.1 |
| `sgs_unscorable_reject` | 3 | ✅ Phase 4.1,共用 _StubScheduler |
| `request_services` | 3 | ✅ Phase 4.4 / Phase 2 |
| `real_db_replay` | 3 | ⚠️ e2e 是 load-bearing 保留,仅 check/smoke 走 Phase 1 删除 |
| 其余 21 个 2-文件簇 | 各 2 | 见 L3_verdicts.csv |

### 4.2 单文件 MERGE（15 个，并入已有 KEEP 锚点）
这些是"单个文件应并入某个保留的契约文件",不新建簇。完整清单见 `L3_verdicts.csv` 的 merge_cluster 列,例如：
- `regression_ortools_warmstart_skip_nonfinite.py` → `ortools_warmstart_validation`（已是 failure_contract 子集）
- `test_version_resolution_contract.py` → `version_resolution`（route_normalizers 超集）
- `regression_schedule_summary_end_date_type_guard.py` → `summary_result_contract`

### 4.3 与已有决策的冲突点（执行时务必对账）
1. **`smoke_phase_suite`(9) + `smoke_web_phase_suite`(2)**：L3 建议合并,但 **D-1 已决定保留 smoke**。→ 以 D-1 为准,这 11 个不动。
2. **`real_db_replay`(3)**：`run_real_db_replay_e2e.py` 是 load-bearing（第 8 章）。→ e2e 保留,check/smoke 按 Phase 1 删（与 L3"保留 e2e 删其余"一致）。

---

## 五、KEEP_TRIM 清单（77 个）—— 体验收益的隐藏大头

这 77 个文件**逻辑有价值但夹带脆性快照尾巴**。处理方式：保留真实断言,删掉尾巴。典型尾巴模式（来自各 agent 实证）：
- 在 JS 源文件里 grep 字符串顺序/片段（`gantt_boot.js`/`gantt_ui.js` 源序断言）
- 模板/CSS class 快照尾
- 整页中文文案 in/not-in 断言
- openpyxl 布局断言（freeze_panes/number_format/列宽/font.bold）
- 精确中文错误文案 exact-match（应降级为"含关键片段"或断言 ErrorCode）

重点大文件（剥离快照后逻辑下沉）：
- `regression_frontend_ui_language_polish.py`(844行) / `regression_excel_template_contracts.py`(842行)：保留 excel 模板服务行为,剥离文案黑白名单
- `regression_scheduler_batches_degraded_visibility.py`：保留 build_summary_display_state 行为,删模板 grep
- `test_win7_launcher_runtime_paths.py`(77 test)：保留 launcher 状态机/锁,删 ~22 个对 .iss/.bat/.ps1 的源码 grep
- `regression_config_manual_markdown.py`(765行) / `regression_config_field_spec_contract.py`：删说明书措辞 not-in 断言群

> KEEP_TRIM 不减文件数,但**直接消除"改文案/CSS 就红"的误报**——这是日常开发体验最痛的点。

---

## 六、务必保留的高价值锚点（KEEP，346 个 high 中的核心）

各域 agent 实读确认的真实业务护栏（删了会漏真 bug）：

**调度核心（134 文件,0 DROP）**：schedule_summary_v11_contract、schedule_orchestrator_contract、freeze_window_fail_closed/bounds、ortools_warmstart_failure_contract、sgs_scoring_fallback_unscorable、optimizer_seed_boundary、metrics_to_dict_nonfinite_safe、greedy_ordering_contract

**数据域**：calendar_shift_start_rollover（跨天工时）、calendar_invalid_shift_window（NaN/Inf/bool 边界）、excel_import_executor_status_gate（OVERWRITE/APPEND/REPLACE 引擎）、excel_failure_semantics_contracts、unit_excel_converter_merge_steps（换算算法）、supplier_effective_selection、operation_execution_state_revision（状态机+threading 并发）

**系统域**：migrations（v14/v15 不丢行+约束）、migrate_v4_sanitizers（SQL 注入防护）、transaction_savepoint_nested、maintenance_window_mutex（线程互斥）、backup_restore_pending_verify_code、factory_request_lifecycle_observability、config_service_active_preset_custom_sync（44 用例原子回滚）

**架构守卫**：`test_architecture_fitness.py`（route 不直连 SQL/service 不 import flask.request/无循环依赖）、`test_regression_main_isolation_contract.py`（conftest 子进程隔离契约）

**graph 子目录**：17 文件确认整体保留,仅 `test_graph_performance.py` 标 ISOLATE_PERF（时间阈值断言用 @pytest.mark.perf 隔离避免 CI 抖动）

---

## 七、伪装成业务测试的快照文件（专项提醒）

L3 精读专门揪出了"名字像业务测试、实则是快照"的伪装文件——这类最危险,因为按文件名永远发现不了：
| 文件 | 伪装 | 真相 |
|---|---|---|
| `regression_models_numeric_parse_hybrid_safe.py` | 像数字解析算法 | 含 41 条字符串断言（L2 已揪出） |
| `regression_sp05_followup_contracts.py` | 带 "contracts" | grep 源码 helper 名快照,1 处真断言 |
| `regression_responsive_min_width_contract.py` | 带 "contract" | CSS 字面量快照 |
| `regression_new_ui_strict_mode_controls_present.py` | 像 strict-mode 行为 | grep 模板宏调用 |
| `test_quality_workflow_cache.py` | 像缓存策略 | quality.yml 的 YAML 快照（action SHA/cache-key） |
| `test_evidence_audit_entrypoints.py` | 像审计入口 | README 文案/日期快照 |
| `verify_installer_vendor_dir.py` | 像构建防护 | 门禁实际失效（vendor/.gitkeep 已提交,hard-fail 分支永不触发） |

---

## 八、机器可读产物

- **`L3_verdicts.csv`**：597 行,字段 `file,verdict,value,reason,merge_cluster,batch`。可在 Excel 按 verdict/value/cluster 筛选。
- **`test_inventory.csv`**：L2 结构清单（行数/函数数/断言数/断言类型/被测模块/分类）。
- 两者可 join（file 列）做交叉分析。

执行各 Phase 时,从 `L3_verdicts.csv` 取对应 verdict 的文件清单直接操作,reason 列给出每个判断的 file:line 证据。

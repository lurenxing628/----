---
doc_type: audit-finding
audit: 2026-06-30-test-suite-redundancy
finding_id: "maintainability-01"
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-refactor
status: open
---

# Finding 01:约 41 组同文件结构重复,应参数化合并(可省约 600 行,零覆盖损失)

## 速答

`tests/` 里有约 **41 组**测试,每组内的多个函数**逻辑骨架完全相同、只是输入数据或被测对象沿一个维度变化**——典型的"本该用 `@pytest.mark.parametrize` 却复制成了 N 个独立函数"。逐组实读确认:合并成参数化后**覆盖零损失**,仅消除重复代码,预计减少 **约 600 行**。这是行为不变的重构,**不是删测试**。

## 怎么合并(通用形态)

把组内每个函数差异的那一两个值抽成 parametrize 参数,函数体留一份;并用 `pytest.param(..., id="语义名")` 把原函数名承载的场景语义落到用例 id 上,保住失败时的可定位性。

## 完整清单(可逐组勾选)

> 路径前缀统一为仓库根。信心 = 该组判定置信度;★ = 各模块里最干净、最该先做的。

### gate_meta(13 组,约省 190 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| ★M01 | `tests/gate_meta/test_long_gate_cache.py:740 / :867 / :1088 / :1192 / :1204` | parametrize(被改字段, 新值, 期望 reason) | ~35 | high | 同文件已有同款 parametrize 先例 |
| M02 | `tests/gate_meta/test_long_gate_collect_cache.py:143 / :170 / :184` | parametrize(目标文件, 初值, 改后值) | ~25 | high | 157 行同款可一并纳入 |
| M03 | `tests/gate_meta/test_long_gate_cache.py:382 / :475 / :544` | parametrize(entry_id, version_key) | ~20 | high | 475/544 仅 entry_id 不同,是双入口合理覆盖,非漏改 |
| M04 | `tests/gate_meta/test_long_gate_cache.py:806 / :818 / :830` | parametrize(pop 掉的必填字段) | ~18 | high | — |
| M05 | `tests/gate_meta/test_long_gate_cache.py:395 / :488 / :557` | parametrize(entry_id, v2 输出名) | ~16 | high | — |
| M06 | `tests/gate_meta/test_run_daily_quality_gate.py:301 / :348 / :373` | parametrize(scope, changed_path) | ~22 | high | **勿卷入 324 行反例** `test_governance_ledger_doc_is_not_docs_only` |
| M07 | `tests/gate_meta/test_sync_debt_ledger.py:2404 / :2497` | 两张 parametrize 表合并到同一函数 | ~18 | medium | 二者本身已 parametrize;用 id 保留两类语义标签 |
| M08 | `tests/gate_meta/test_long_gate_cache.py:770 / :782` | parametrize(坏内容, 期望子串) | ~12 | medium | 794 行 non-utf8 变体需区分文本/二进制写法,可只合这 2 条 |
| M09 | `tests/gate_meta/test_long_gate_cache.py:1112 / :1124` | parametrize(schema 字段名) | ~10 | high | 两字段触发同一 reason |
| M10 | `tests/gate_meta/test_long_gate_cache.py:464 / :534` | parametrize(entry_id) × 现有 env_key | ~10 | high | 二者已 parametrize env_key |
| M11 | `tests/gate_meta/test_long_gate_cache.py:890 / :901` | parametrize(stdout/stderr log path) | ~10 | high | — |
| M12 | `tests/gate_meta/test_quality_gate_registry_split_scope_contract.py:218 / :229` | parametrize(test_path, input_scope) | ~9 | medium | 该文件十几个同型成员资格测试,建议统一规划而非零散合 |
| M13 | `tests/gate_meta/test_quality_gate_registry_split_scope_contract.py:167 / :356` | parametrize(test_path, group_name) | ~7 | medium | 同 M12,建议与之并轨设计 |

### algorithm(2 组,约省 18 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| ★M14 | `tests/algorithm/test_optimizer_proof_harness_contract.py:219 / :235` | parametrize(被污染字段, 值) | ~12 | high | 断言对象就是被污染字段本身,零风险 |
| M15 | `tests/algorithm/test_schedule_optimizer_cfg_snapshot_contract.py:143 / :149 / :155` | parametrize(cfg 形态, 期望 objective) | ~6 | medium | 期望值要按 cfg 配对,勿统一常量(否则丢 min_weighted_tardiness 覆盖) |

### scheduler_graph(2 组,约省 42 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| ★M16 | `tests/scheduler_graph/test_scheduler_graph_on_mode_contract.py:858 / :894` | parametrize(int 映射 / str 映射) | ~30 | medium | **必须 `ids=["int_map","str_map"]`** 保住"字符串 op-id 归一化"意图 |
| M17 | `tests/scheduler_graph/test_graph_dispatch_context.py:176 / :190` | parametrize(缺失端边, token, 中文消息) | ~12 | medium | from/to 两分支消息不同,作 param 带上 |

### schedule(5 组,约省 68 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| ★M18 | `tests/schedule/route_view/test_scheduler_batches_page_viewmodel.py:516 / :556` | 拼接两组 parametrize 数据 | ~12 | high | 函数体逐字相同;用 id 保留 unknown / incomplete |
| M19 | `tests/schedule/service/test_schedule_input_builder_strict_hours_and_ext_days.py:32 / :58 / :84` | parametrize(字段 override, 期望 field, 中文标签) | ~22 | high | 须保留 internal/external 两种 source 形态;勿并入 110 行 legacy 用例 |
| M20 | `tests/schedule/route_view/test_scheduler_ops_update_route_contract.py:79 / :104` | parametrize(post_data, 期望 saved) | ~14 | medium | "空设备→None、空工时→空串"是 by-design,两套期望完整保留 |
| M21 | `tests/schedule/route_view/test_scheduler_historical_plan_label_contract.py:145 / :158` | parametrize(url) | ~8 | medium | 单一标签断言,合并干净;用 id 标 resource_dispatch / report_filter |
| M22 | `tests/schedule/route_view/test_scheduler_run_view_result_contract.py:222 / :325` | parametrize(result, 期望 warning) | ~12 | medium | summary 计数(failed_ops 0 vs 2)不同,须随 param 一起带 |

### candidate(5 组,约省 76 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| ★M23 | `tests/candidate/test_scheduler_candidate_analysis_links_contract.py:364 / :385` | parametrize(注入的 plan_role stub) | ~18 | high | 用 id 标 detail_broken / drift |
| M24 | `tests/candidate/test_scheduler_candidate_plain_language.py:313 / :328` | parametrize(status, 期望 in/not-in) | ~14 | high | not-in 断言也随 param 变 |
| M25 | `tests/candidate/test_scheduler_candidate_health_contract.py:136 / :154` | parametrize(graph_metrics) | ~14 | high | 两者期望完全相同,最干净 |
| ★M26 | `tests/candidate/test_scheduler_candidate_runner_contract.py:520 / :544` | parametrize(异常类型, 消息) | ~18 | high | TypeError/RuntimeError 传播,边界清晰 |
| M27 | `tests/candidate/test_scheduler_candidate_plain_language.py:343 / :357` | parametrize(第二条 event 的 count, 期望 detail) | ~12 | high | 坏计数 vs 累加两文案随 param 带 |

### scheduler_analysis(1 组,约省 10 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| M28 | `tests/scheduler_analysis/test_scheduler_analysis_read_context.py:164 / :175` | parametrize(url:默认 / ?version=latest) | ~10 | medium | 用 id 保留 default / latest_keyword |

### web_pages(5 组,约省 112 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| ★★M29 | `tests/web_pages/test_page_manual_registry.py:903 / :910 / :917 / :924 / :931 / :938 / :953 / :960 / :967` | parametrize(9 个 `_assert_*` helper) | ~48 | high | **全套最大最干净**;勿并入 945 行(多读一文件,形态不同) |
| M30 | `tests/web_pages/test_plan_context_capsule.py:199 / :205 / :211 / :262` | parametrize(路由 url) | ~18 | high | 192 行 gantt_capsule 多一条断言,单列别丢 |
| M31 | `tests/web_pages/test_system_logs_presenter_contract.py:10 / :31` | parametrize(输入码组, 期望 label) | ~12 | high | 同文件 52 行已有 parametrize,风格一致 |
| M32 | `tests/web_pages/test_history_summary_parser.py:35 / :80` | parametrize(raw, 期望 reason) | ~8 | high | 可与 43 行既有 non-finite 参数化并轨 |
| M33 | `tests/web_pages/test_dashboard_cockpit_hero.py:144 / :200 / :310(+217 / :234)` | 整个 overdue_clue 族 parametrize(summary, 期望/禁止子串) | ~26 | medium | 该族还有 161/168/186/251/266 等,**要做就整族一起收**,逐条子串搬全 |

### app_runtime(2 组,约省 23 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| M34 | `tests/app_runtime/test_win7_launcher_runtime_paths.py:578 / :603` | parametrize(写哪个文件, 期望 host/port 状态) | ~15 | high | 宜把 628 行 blank 变体一并纳入 |
| M35 | `tests/app_runtime/test_ui_geometry_html_contract.py:92 / :104` | parametrize(html, 期望关键词) | ~8 | medium | 负例(反误报)语义更重,用 id 标 normal_shell / error_title |

### config(1 组,约省 11 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| M36 | `tests/config/test_config_service_strict_blank_contract.py:46 / :60` | parametrize(payload, 期望中文 field) | ~11 | high | 74 行 time_budget 变体可选并入(断言形态略不同) |

### gantt(2 组,约省 18 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| M37 | `tests/gantt/test_gantt_chain_walk_js_contract.py:124 / :139` | parametrize(方向, seed, 期望文案) | ~9 | medium | 内嵌 JS 需模板化,两条方向文案("上一道"/"下一道")都保留 |
| ★M38 | `tests/gantt/test_gantt_execution_visuals_contract.py:79 / :86` | parametrize(status:not_started / weird_code) | ~9 | high | 两条断言一字不差,与同文件正例循环参数化对称 |

### calendar_maintenance(1 组,约省 18 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| ★M39 | `tests/calendar_maintenance/test_freeze_window_fail_closed_contract.py:577 / :667 / :687` | parametrize(repo 工厂, ops) | ~18 | high | **ids 写明 duplicate/missing_prefix/invalid_range**;勿并入 relaxed 兄弟(597/707) |

### migration_db(1 组,约省 14 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| ★M40 | `tests/migration_db/test_backup_integrity_check_contract.py:135 / :147 / :159` | parametrize(conn 工厂, 期望子串) | ~14 | high | 135/147 子串相同但覆盖 execute/fetchall 两个异常点,都要留;159 走 else 分支带各自子串 |

### resource_dispatch(1 组,约省 12 行)

| 组 | 成员 `file:line` | 合并成 | 省行 | 信心 | 注意 |
|---|---|---|---|---|---|
| M41 | `tests/resource_dispatch/test_resource_dispatch_actual_import.py:49 / :66` | parametrize(sheet 标题, 表头, 期望文案) | ~12 | high | 勿顺手并入同文件 oversize(83)/duplicate(98)等不同分支 |

## 影响

- 纯可维护性收益:~41 组合并后约减 **600 行**重复测试代码,降低后续改一处契约要同步改 N 个复制体的维护成本。
- 不影响产品运行,不减少测试覆盖(每个差异值都作为 parametrize 用例保留)。

## 修复方向

走 `cs-refactor`,**分模块小批次**进行;每合并一组,在该组涉及的测试文件上跑一次 `pytest <file>` 自证行为不变,再进下一组。优先做 ★ 标记的高收益低风险组。

## 建议动作

`cs-refactor`,因为这是"行为不变、只改测试结构"的重构,符合 refactor 的定义;不属于新需求或 bug 修复。

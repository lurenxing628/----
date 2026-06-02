---
doc_type: architecture
slug: BOUNDARY-CHARTER
scope: 项目边界总册 —— 一张表看全 APS 所有边界约束，标注每条是否被门禁/测试强制守护，可回溯
summary: 把散落在架构文档/技术决定/契约测试里的所有边界收拢成单一可信清单，区分"有保镖（焊死，放心）"和"无保镖（靠自觉，加功能要当心）"
status: current
created: 2026-06-02
last_reviewed: 2026-06-02
tags: [aps, architecture, boundary, charter, guardrail, contract]
depends_on: [ARCHITECTURE]
implements: []
---

# APS 项目边界总册（Boundary Charter）

> **这份文档的用途**：你加任何功能前，先看这一份。它把项目所有的边界约束收成一张清单，每条标注"谁在守它"。
>
> **怎么读**：
> - **🛡️ 有保镖** = 有门禁/契约测试焊死。你就算忘了这条边界、手滑想违反，跑测试会立刻变红拦住你。**这些边界物理上不会腐烂，加功能放心。**
> - **⚠️ 无保镖** = 只写在文档/决定里，靠自觉。**这些才是你加功能时真正要手动当心的少数。**
>
> **核心事实**：项目有 **182 个契约测试 + 22 条架构适应度规则**在自动守边界，且 AST 全量扫描**分层红线 0 违规**。你过去定的边界大多数已焊进测试——你不需要记住它们，门禁替你记着。

---

## 第一部分：交付硬边界（最高优先级，违反 = 交付失败）

| # | 边界（大白话） | 来源 | 守护 |
|---|---|---|---|
| D1 | **Win7 x64 离线交付**：目标机不装 Python、不联网 | ARCHITECTURE §5、AGENTS.md | 🛡️ `test_win7_launcher_runtime_paths.py`、`verify_installer_vendor_dir.py` |
| D2 | **Python 3.8 语法**：不用 3.9+ 语法（`list[X]`/`X|Y`/`X|None` 等） | ARCHITECTURE §5、pyproject ruff UP006/UP007/UP045 关 | 🛡️ `test_scan_py38plus_syntax.py` + `scan_py38plus_syntax.py`（门禁跑） |
| D3 | **页面不依赖外部资源**：不引 CDN、外链字体、外链脚本，静态资源随应用本地交付 | ARCHITECTURE §2、各 requirements | 🛡️ `regression_frontend_offline_static_assets.py` |
| D4 | **Chrome 109 兼容**：不用更新浏览器才支持的前端能力 | 前端 roadmap §5.8 | ⚠️ 仅靠浏览器几何 smoke，无硬门禁锁版本 |
| D5 | **面向用户默认简体中文** | AGENTS.md、ARCHITECTURE §5 | ⚠️ 靠 review，无自动检查 |

## 第二部分：分层架构红线（AST 全量验证 0 违规 —— 地基最硬的一块）

| # | 边界（大白话） | 守护 |
|---|---|---|
| L1 | **算法层不碰 service**：`core/algorithms` 不反向依赖 `core.services` | 🛡️ codemap AST 全量 0 违规 + fitness 隐含 |
| L2 | **模型层不碰上层**：`core/models` 不依赖 services/data/web | 🛡️ codemap AST 0 违规 |
| L3 | **ViewModel 是纯数据变换**：不导入 flask/service/repository/routes | 🛡️ `test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes` |
| L4 | **路由不直连 Repository**：必须经 Service 中转 | 🛡️ `test_routes_do_not_import_repository`、`test_web_helpers_do_not_import_repository` |
| L5 | **路由不直接执行 SQL** | 🛡️ `test_routes_do_not_execute_sql_directly` |
| L6 | **Service 不导入 flask.request**（Web 对象不下沉到服务层） | 🛡️ `test_services_do_not_import_flask_request` |
| L7 | **Service 之间无循环依赖**（含 A→B→C→A） | 🛡️ `test_no_circular_service_dependencies` |
| L8 | **SQL 只在 repository/infrastructure**：service 层零裸 SQL | 🛡️ 第一轮审计 grep 验证成立 + L5 |
| L9 | **Service 不用 assert 做运行期保障**（python -O 会移除） | 🛡️ `test_services_do_not_use_assert_for_runtime_guards` |
| L10 | **核心目录禁止 `import *`** | 🛡️ `test_no_wildcard_imports` |

## 第三部分：用户安全边界（内部字段不泄露 / 非正式方案不可写）

| # | 边界（大白话） | 守护 |
|---|---|---|
| S1 | **内部字段不露给用户**：`scenario_id`/`plan_role`/`source_table`/`candidate_id` 不进页面正文、按钮、导出列、公开 payload（可留 URL/隐藏字段/日志） | 🛡️ `regression_excel_hidden_payload_contract`、`regression_resource_dispatch_public_output_contract`、`test_domain_model_internal_source_contract`、`regression_page_header_plain_purpose_contract` |
| S2 | **工序内部定位字段不露**：`op_id`/`schedule_id`/`state_revision`/`execution_snapshot_revision` 不进用户可见处；跨页定位用批次/设备/人员/日期 | 🛡️ `regression_resource_dispatch_public_output_contract`、`regression_resource_dispatch_viewmodel_public_output_contract` |
| S3 | **甘特图只读**：任务条不能拖动/拉伸成假修改，不开放拖拽写库 | 🛡️ `regression_gantt_readonly_mode_contract` |
| S4 | **非正式方案不可写现场记录**：候选方案/模拟预览/历史正式方案不下发写入入口、Excel 导入地址、模板下载地址 | 🛡️ `regression_scheduler_workbench_link_guardrails`、`regression_scheduler_dispatch_plan_identity_guardrails` |
| S5 | **现场记录只写当前正式采用方案** | 🛡️ `regression_scheduler_reschedule_execution_minimum_guardrails` + S4 |
| S6 | **Excel 导出只展示中文业务字段**：矩阵表+日历明细，不展示内部追踪字段 | 🛡️ `regression_excel_*_contract`（4个）、`regression_resource_dispatch_public_output_contract` |
| S7 | **现场状态变化时拒绝重排写入**（执行快照复算，冲突给中文提示不写库） | 🛡️ `regression_scheduler_reschedule_execution_minimum_guardrails`、`freeze_window_fail_closed_contract` |

## 第四部分：能力边界（"明确不做"的事 —— 防止范围失控）

> 这些大多 ⚠️ 无硬门禁（属产品范围承诺，不是代码规则），但写在 requirements 里可回溯。加功能前对照，避免悄悄越界做成"半个 MES"。

| # | 不做什么 | 来源 |
|---|---|---|
| C1 | 不重写排产算法 | 前端 roadmap §2 |
| C2 | 不做完整 MES/ERP/WMS/PLM/IoT 实时采集、扫码枪、电子签名、工资计件、质量追溯 | shop-floor-execution-feedback |
| C3 | 不做甘特拖拽正式写库、不做拖动保存 | gantt-readonly-result-view |
| C4 | 候选方案第一版只承诺代表三方案，不展示全部 3/5/7 档明细、不支持任意两方案自由对比 | candidate-comparison-business-view |
| C5 | 延期诊断：没数据时只说缺口，不编造根因，不承诺自动判断唯一根因 | schedule-delay-diagnosis |
| C6 | 报表只支持设备和人员资源筛选；班组/未知/半截资源筛选直接拒绝 | scheduler-daily-workbench |
| C7 | 停机影响第一版只做设备级，不做任务级明细 | scheduler-daily-workbench |
| C8 | 资源派工不做热力图/复杂折叠/新大屏分析 | resource-dispatch-calendar-readable-output |
| C9 | 短期不做：反馈人必填、多人现场账号、Excel 导入预览/二次确认 | 前端 roadmap 变更日志 |
| C10 | 计划和现场实际复盘只对照正式采用方案，模拟/候选不进复盘口径 | shop-floor-execution-feedback |

## 第五部分：代码规约边界（防腐蚀）

| # | 边界 | 守护 |
|---|---|---|
| R1 | 核心目录文件名 snake_case | 🛡️ `test_file_naming_snake_case` |
| R2 | 单文件不超 500 行（未登记的新文件） | 🛡️ `test_file_size_limit` + 台账白名单 |
| R3 | 函数圈复杂度不超阈值（未登记的新函数） | 🛡️ `test_cyclomatic_complexity_threshold` |
| R4 | core/ 不新增局部解析 helper（_safe_int 等） | 🛡️ `test_no_new_local_parse_helpers` |
| R5 | 静默回退必须登记台账，启动链新增命中先登记 | 🛡️ `test_no_silent_exception_swallow`、`test_startup_silent_fallback_samples` |
| R6 | 退化原因码必须纳入 STABLE_DEGRADATION_CODES | 🛡️ `test_stable_degradation_codes_cover_actual_usages` |
| R7 | 质量门禁入口以 `scripts/run_quality_gate.py` 为准 | 🛡️ 门禁自身 |

---

## ⚠️ 你加功能时真正要当心的（无保镖边界汇总）

把上面所有 ⚠️ 收拢到这里——**这就是你"心惊胆战"应该收缩到的全部范围**，其余都有保镖：

- **D4 Chrome 109 兼容**：大改前端能力时手动确认不用新浏览器 API（有浏览器几何 smoke 兜底，但不锁版本）。
- **D5 中文优先**：新页面/新文案靠自己把关用中文。
- **C1-C10 能力边界**：加功能前对照"明确不做"清单，确认没悄悄把范围扩成 MES/自由对比/任务级停机等。这是**范围纪律**，不是代码规则，门禁管不了，只能靠这份清单。

**就这些。** 其余 30+ 条边界全部有门禁/契约测试焊死，你破坏不了。

---

## 怎么用这份总册（你的新工作流）

1. **加功能前**：扫一眼第四部分（能力边界），确认没越界做"明确不做"的事。
2. **改代码时**：不用记其余边界——有保镖的，违反了门禁会红。
3. **门禁报错时**：对照本表找到对应行，就知道你踩了哪条边界、为什么。
4. **定新边界时**：如果是重要约束，给它配一个契约测试（让它变成 🛡️），并在本表加一行。**这是把"脑子里的决定"变成"焊死的边界"的标准动作——以后就不会再忘、再和自己打架。**

> 本表的边界→测试映射在第二轮 Workflow 深钻后会补充函数级证据。当前映射已由 grep + 第一轮 AST 验证。

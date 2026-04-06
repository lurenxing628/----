## APS 深度架构体检 + 全面体检（后续 Phase2~Phase6 执行 Runbook）

> 目的：你将另开一个对话继续推进。本文件把**后续所有要做的内容**写成“可复制执行”的步骤，确保新对话可以完全照此执行。
>
> 约束：
> - **不要编辑**：`c:\Users\lurenxing\.cursor\plans\aps体检闭环_02b319d0.plan.md`（计划文件本身不动）。
> - 严格遵守仓库的分层/变更范围规则：一次只闭环一个模块，不做“顺手修”。
> - 若出现必须改 schema 的 P0 问题：按“迁移+文档联动”单独开一个闭环批次，不在本 runbook 里混改。

---

## 0) 你现在处于什么状态（新对话的起点）

### 已完成（Phase0 + Phase1 scheduler 两批闭环）

- Phase0 基线 evidence 已产出：`evidence/DriftDetect/*`、`evidence/ArchAudit/*`、`evidence/DeepReview/*`
- Phase1（scheduler）两批闭环已完成，且以下门禁已通过：
  - `python -m pytest tests/test_architecture_fitness.py -v` → 9/9 PASSED
  - `python tests/generate_conformance_report.py` → 通过（MAJOR=0）
  - `python tests/smoke_phase6.py` → OK（报告：`evidence/Phase6/smoke_phase6_report.md`）

### 当前遗留体检结论（仍 FAIL 的原因）

最新 `evidence/ArchAudit/arch_audit_report.md` 显示（重点关注可“模块化清理”的项）：

- 文件超限：0（已清零）
- 分层违反：0（OK）
- 仍需治理：
  - 裸字符串枚举：83（大量分布在 routes + 各域 services）
  - 圈复杂度超标（>15）：53（多处为历史遗留）
  - 缺少 `from __future__ import annotations`：24（散布在多个入口/包 `__init__`）
  - 公开方法缺返回类型注解：6
  - 潜在死代码公开方法：10（需人工核对，避免误删）

### 本轮 scheduler 留痕（供回溯）

- 基线审阅/台账：`audit/2026-02/20260228_1415_drift_detect_review.md`
- scheduler 两批闭环审阅：`audit/2026-02/20260228_1452_scheduler_batch1_batch2_review.md`

---

## 1) 新对话开始后的“统一开场动作”（每个 Phase 都遵循）

### 1.1 环境/仓库现状确认（必做）

- `git status --short`（确认没有“意外改动/大批未追踪文件”混入本次闭环）
- 如果你打算提交：先不要 commit，先把本 Phase 闭环跑完（证据齐全再决定）。

### 1.2 基线门禁（建议每个 Phase 开始/结束都跑一次）

> 注意：部分 regression_*.py 是**脚本型回归**（没有 pytest 测试函数），要用 `python tests/xxx.py` 跑。若 `pytest` 显示 “no tests ran”，改为直接 `python` 运行。

- 架构适应度函数：
  - `python -m pytest tests/test_architecture_fitness.py -v`
- 一致性对标：
  - `python tests/generate_conformance_report.py`
-（可选）综合体检（会跑 ruff 全量、架构审计、文档新鲜度等）：
  - `python .cursor/skills/aps-drift-detect/scripts/drift_detect.py`
  - 控制台中文可能乱码（Windows code page）；**以 `evidence/*` 文件内容为准**。

### 1.3 引用链追踪（建议每批次改动后跑）

你之前遇到过编码报错，统一用 UTF-8：

```powershell
$env:PYTHONIOENCODING='utf-8'
python .cursor/skills/aps-deep-review/scripts/reference_tracer.py --commit HEAD~1
```

产物：`evidence/DeepReview/reference_trace.md`

### 1.4 本仓库的“模块闭环”定义（强制）

每个 Phase/模块都按同一闭环推进：

- **范围冻结**：先写清本批次只动哪些文件（2~6 个为宜）
- **体检**：arch_audit + fitness +（必要时）reference_trace
- **修复**：只修 P0/P1 + 与该模块强相关的历史遗留（容量 70/30）
- **回归**：最小回归集（脚本回归 + smoke + 关键路径）
- **留痕**：`audit/YYYY-MM/` 下写一份审阅报告（包含证据路径、取舍、残留项）

---

## 2) Phase2：Excel 导入链路闭环（推荐新对话从这里继续）

### 2.1 Phase2 范围（建议先拆 2~3 个小批次）

优先入口（先基础设施，再域服务，再 routes）：

- 基础设施（P0/P1 优先）：
  - `core/services/common/excel_import_executor.py`
  - `core/services/common/excel_validators.py`
  - `core/services/common/excel_audit.py`（留痕键一致性）
- 域导入服务（按依赖面）：
  - `core/services/equipment/machine_excel_import_service.py`
  - `core/services/personnel/operator_excel_import_service.py`
  - `core/services/process/op_type_excel_import_service.py`
  - `core/services/process/supplier_excel_import_service.py`
  - `core/services/scheduler/calendar_service.py`（日历导入）
  - `core/services/scheduler/batch_service.py`（批次导入，已拆分，但仍要做链路核对）
- 路由（只在必要时动；避免“顺手改 UI”）：
  - `web/routes/*excel_*.py`（confirm/preview）

### 2.2 Phase2 目标（要“测得出来”）

- **事务边界清晰**：preview/confirm 的写入应可整体回滚；禁止在外层事务里隐式 commit 破坏原子性。
- **导入状态门禁稳定**：不引入新的 `skip/update/create` 计数漂移。
- **模板字段一致性**：列名、必填/可空、枚举容错（大小写/空白）一致。
- **用户可见错误一致**：ValidationError 提示能定位到字段；不会吞异常。
- **裸字符串枚举收敛（与 Excel 强相关）**：
  - `yes/no/workday/holiday/weekend` 等在 validators 与导入服务内尽量收敛到 `core/models/enums.py` + normalize 入口（保持输入兼容）。

### 2.3 Phase2 建议小批次拆法（可直接照做）

#### Batch2-1：`excel_import_executor.py`（只动 executor）

- 目标：确保统计口径、错误样本、skip gate 不漂移；保证执行器“只负责编排+事务”。
- 回归：
  - `python tests/regression_excel_import_executor_status_gate.py`
  - `python tests/run_complex_excel_cases_e2e.py --out evidence/ComplexExcelCases --repeat 1`

#### Batch2-2：`excel_validators.py`（只动 validators/normalize）

- 目标：枚举容错统一；Optional 返回值都被调用方正确处理（参考 reference_trace ⚠）。
- 回归：
  - `python tests/regression_excel_validators_yesno_mixed_case.py`
  - `python tests/regression_models_numeric_parse_hybrid_safe.py`（若涉及数字容错）

#### Batch2-3：某一个域导入服务 + 对应路由（闭环 1 条链路）

- 例：operator 导入：
  - 服务：`core/services/personnel/operator_excel_import_service.py`
  - 路由：`web/routes/personnel_excel_operators.py`
  - 回归：跑对应 regression + `python tests/smoke_phase3.py`

### 2.4 Phase2 退出标准（必须满足）

- `python -m pytest tests/test_architecture_fitness.py -v`：9/9 PASSED（尤其复杂度/静默吞异常门禁）
- `python tests/generate_conformance_report.py`：通过（至少 MAJOR=0）
- complex excel cases / 相关 regression：通过
- ruff：对改动文件 `ruff check` 全绿
- `audit/YYYY-MM/`：写一份 Phase2 审阅报告（含证据路径、残留项）

---

## 3) Phase3：业务域服务闭环（process → personnel → equipment）

> 原则：每次只闭环一个域（或一个子域），不要三域混改。

### 3.1 Process（建议先做）

优先文件（体量/影响面大）：

- `core/services/process/part_service.py`
- `core/services/process/route_parser.py`
- `core/services/process/op_type_service.py`
- `core/services/process/supplier_service.py`
- 对应 routes：`web/routes/process_*.py`

回归建议：

- `python tests/smoke_phase2.py`
- 相关 regression（根据改动点挑选跑，不要全量一次性）

### 3.2 Personnel

优先文件：

- `core/services/personnel/operator_service.py`
- `core/services/personnel/operator_machine_service.py`（复杂度高）
- 对应 routes：`web/routes/personnel_*.py`

回归建议：

- `python tests/smoke_phase3.py`
- `python tests/regression_excel_operator_calendar_cross_midnight.py`（涉及日历/班次边界时）

### 3.3 Equipment

优先文件：

- `core/services/equipment/machine_service.py`
- `core/services/equipment/machine_downtime_service.py`
- 对应 routes：`web/routes/equipment_*.py`

回归建议：

- `python tests/smoke_phase4.py`
- `python tests/regression_downtime_overlap_skips_invalid_segments.py`

### 3.4 Phase3 的“通用治理点”（每个域都要看）

- 枚举收敛：status/category/day_type/yesno 等
- Optional 返回值处理：reference_trace ⚠ 指向的调用点逐条核对
- 事务边界：写入操作必须在 Service 层事务内；Route 不写业务判断
- 公开方法签名：不随意变更；若变更必须跑 reference_tracer + 对应 routes/模板核对

---

## 4) Phase4：Route 边界 + 模板/前端契约

目标：把“路由层的业务判断/拼装逻辑”逐步下沉到 service，模板保持渲染职责；同时清理 UI 契约漂移风险。

### 4.1 Route 层（web/routes）

优先关注：

- 复杂度最高/业务逻辑最重的路由（参考 arch_audit 的复杂度列表）
- 裸字符串枚举集中区（`scheduler_bp.py`、`*_bp.py`、`*_utils.py` 等）

回归建议：

- `python tests/regression_frontend_common_interactions.py`
- `python tests/smoke_web_phase0_6.py`（或自测 runner 里 web smoke）

### 4.2 templates/static

目标：不在模板里写业务规则；JS 只处理交互，不引入 XSS 风险。

回归建议：

- `python tests/regression_gantt_url_persistence.py`
- `python tests/regression_gantt_offset_range_consistency.py`
- `python tests/run_xss_excel_to_gantt_popup_check.py`

---

## 5) Phase5：Repository/SQL 与数据层一致性（含 schema/migration 协议）

### 5.1 不改 schema 的清理（优先）

- SQL 全参数化（`?` + params），禁止 f-string 拼 SQL
- Repository 只负责数据访问；不引入 service/web 依赖
- `from_row()` 与 SELECT 字段一致

### 5.2 如果必须改 schema（单独闭环，不要夹带）

一旦触发必须改：

- 同步完成：
  - `schema.sql` 更新
  - `core/infrastructure/migrations/` 新增迁移（版本递增）
  - `开发文档/开发文档.md` 数据模型章节更新
  - `开发文档/系统速查表.md` 字段字典更新
  - 若涉及枚举：全局搜索引用点并逐一适配

---

## 6) Phase6：全量验证与收口（里程碑执行）

### 6.1 全量自测（不打包）

- `python .cursor/skills/aps-full-selftest/scripts/run_full_selftest.py`
- 产物：`evidence/FullSelfTest/full_selftest_report.md`

### 6.2 复跑综合体检（对比 Phase0 趋势）

- `python .cursor/skills/aps-drift-detect/scripts/drift_detect.py`
- `python -m pytest tests/test_architecture_fitness.py -v`
- 引用链追踪（按里程碑范围）：

```powershell
$env:PYTHONIOENCODING='utf-8'
python .cursor/skills/aps-deep-review/scripts/reference_tracer.py --commit HEAD~20
```

### 6.3 最终收口产物（必须写到 audit）

- `audit/YYYY-MM/YYYYMMDD_HHMM_final_health_review.md`（建议结构）：
  - 事实（证据路径 + 关键指标变化）
  - 结论（P0/P1/P2 取舍）
  - 下一轮优先级（Top10 文件/问题）

---

## 7) 历史遗留项治理策略（新对话必须遵守）

- **不回避遗留**：但只修“当前模块强相关”遗留项（避免范围爆炸）。
- **容量配比**：每个模块批次里，70% 解决当期问题，30% 清同模块遗留。
- **退出规则**：
  - 禁止新增：分层违反 / 静默吞异常 / 复杂度门禁违反 / 文件超限
  - 每个 Phase 结束时，遗留项数量要**净下降**（哪怕只下降一点）

---

## 8) 快捷命令清单（PowerShell）

- 架构审计（报告）：`python .cursor/skills/aps-arch-audit/scripts/arch_audit.py`
- 架构适应度：`python -m pytest tests/test_architecture_fitness.py -v`
- 一致性对标：`python tests/generate_conformance_report.py`
- 全量自测：`python .cursor/skills/aps-full-selftest/scripts/run_full_selftest.py`
- 改动后快检：`python .cursor/skills/aps-post-change-check/scripts/post_change_check.py`
- 引用链追踪（UTF-8）：见上文 `$env:PYTHONIOENCODING='utf-8' ...`


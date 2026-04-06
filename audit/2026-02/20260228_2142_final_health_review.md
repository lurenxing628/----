# 里程碑最终收口报告（Phase2~6）

- 时间：2026-02-28 21:42
- 范围：按 `aps体检闭环_phase2-6补强_892a73a0.plan.md` 完成 Phase2~6 的闭环与证据收口（不含打包）。

## 证据清单（可复现）

- 全量自测汇总：`evidence/FullSelfTest/full_selftest_report.md`
- 综合体检（漂移检测）：`evidence/DriftDetect/drift_report.md`
- 架构合规审计：`evidence/ArchAudit/arch_audit_report.md`
- 一致性对标：`evidence/Conformance/conformance_report.md`
- 架构适应度函数：`python -m pytest -q tests/test_architecture_fitness.py`（9 passed）
- 引用链追踪：`evidence/DeepReview/reference_trace.md`

## 事实摘要（来自 evidence）

### 1) 全量自测

- 结论：**PASS**（见 `evidence/FullSelfTest/full_selftest_report.md`）
- 覆盖：smoke phases、web smoke、FullE2E、regression_*、complex excel cases（runner 记录数 109）

### 2) 综合体检（drift_detect）

- 结论：**需要修复**（见 `evidence/DriftDetect/drift_report.md`）
- Conformance：PASS
- Ruff：FAIL（78 errors）
- 文档新鲜度提示（可能需更新）：`开发文档/开发文档.md`、`开发文档/面板与接口清单.md`、`开发文档/阶段留痕与验收记录.md`

### 3) 架构合规审计（ArchAudit）

见 `evidence/ArchAudit/arch_audit_report.md` 的“总结”段落：

- 分层违反：0；Route 越层导入 Repository：0；Service 循环依赖：0
- 裸字符串枚举：52
- 潜在死代码公开方法：10
- 圈复杂度超标（>15）：36
- 结论：FAIL（仍有遗留项，适合作为下一轮 Backlog 收敛）

### 4) 引用链追踪（DeepReview）

见 `evidence/DeepReview/reference_trace.md` 顶部“跨层边界风险”：

- 发现若干 `Route → Repository` 直连调用线索（例如 `OperatorMachineRepository.*` 被 Route 直接调用）。该报告为启发式匹配，建议下一轮按线索逐条回到源码核对并收敛到 `Route → Service → Repository`。

## 已闭环批次留痕（audit/2026-02）

- Phase2：Excel 基础设施 + unit_excel 工具链 + personnel operator 导入链路闭环
- Phase3：process/personnel/equipment 域服务闭环
- Phase4：scheduler_analysis/system_logs 边界清理 + 高复杂度 excel confirm 下沉
- Phase5：batch_material_service 直连 SQL 下沉到 repository

（逐批次细节见本目录下对应 `phase*_batch*_*_closeout.md` 留痕文件）

## 下一轮优先级（建议 Backlog）

- P1：Ruff 78 errors 分批清零（优先改动文件周边；避免一次性全仓自动修复引入噪音 diff）
- P1：继续收敛裸字符串枚举（优先 Route bp/入口处的 `'active'/'inactive'/'workday'/'pending'...` 比较）
- P1：按 `reference_trace.md` 线索排查并修复潜在 `Route → Repository` 直连（若属实则纳入 Phase4/Phase5 风格的小批次）
- P2：复杂度遗留项（>15）按模块逐批拆分（Route confirm 与 scheduler_run/weekly_plan 等）
- P2：潜在死代码（10 项）按“确认无引用 + 有回归覆盖”策略处理；否则保留并持续记账


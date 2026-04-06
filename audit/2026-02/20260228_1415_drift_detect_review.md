# 漂移检测（综合体检）审阅报告（LLM）

- 时间：2026-02-28 14:15
- 证据：
  - `evidence/DriftDetect/drift_report.md`
  - `evidence/ArchAudit/arch_audit_report.md`
  - `evidence/Conformance/conformance_report.md`
  - `evidence/DeepReview/reference_trace.md`

## 事实摘要（来自 evidence）

- 综合结论：**需要修复**（架构审计 FAIL；一致性对标 FAIL；Ruff FAIL）
- 架构适应度函数：**9/9 PASSED**（无“新增架构违反”）

### 架构合规审计（`evidence/ArchAudit/arch_audit_report.md`）

- 总问题数：195
- 关键项：
  - 文件超限：4（全部位于 `core/services/scheduler/`）
  - 圈复杂度超标（>15）：56（其中 E/F 合计 14）
  - 裸字符串枚举：93（`yes/no/workday` 等散落在 scheduler/route/service）
  - 潜在死代码公开方法：12
  - 缺少 `from __future__ import annotations`：24
  - 公开方法缺返回类型注解：6

### 一致性对标（`evidence/Conformance/conformance_report.md`）

- MAJOR：1
  - **排产落库+留痕（Schedule + ScheduleHistory + OperationLogs[action=schedule/simulate]）不一致**：在 `core/services/scheduler/schedule_service.py` 未匹配到 `action=schedule/simulate` 的留痕写入线索。
- MINOR：1
  - 核心目录文件行数约束：4 个 scheduler 文件超过 500 行。

### 引用链追踪线索（`evidence/DeepReview/reference_trace.md`）

- scheduler 相关的风险线索（需回到源码逐条核对）：
  - `normalize_text()` / `normalize_hhmm()` 等返回 `Optional`，部分调用者未做 `None` 保护（包含 `schedule_service.py`、`config_service.py`、`calendar_admin.py` 等）。
  - 报告中出现若干 “Route 直调 Repository” 的 ⚠ 线索（需要与 `arch_audit` 结果对照核实，防误报）。

## 结论与取舍（本轮按模块闭环推进）

### 必须改（P0/P1：本轮 scheduler 闭环）

- **P0**：补齐排产留痕/事务原子性（`schedule/simulate` → `OperationLogs` + `ScheduleHistory`，并确保与排产落库同事务）。
- **P1**：拆分 scheduler 4 个超大文件（目标：每个文件 < 500 行；按职责拆分，不做行为变更）。
- **P1**：收敛 scheduler 相关裸字符串枚举（`yes/no/workday` 等）到 `enums.py`/normalize 入口，避免散落字符串导致语义漂移。
- **P1**：补齐 scheduler 内 Optional 返回值调用点的 `None` 处理（转为明确的校验失败/默认值/分支处理）。

### 建议改（P2：后续按模块逐步清理）

- Ruff 全量问题：89（按模块闭环推进时逐步清零本模块新增/相关项）。
- `from __future__ import annotations` 缺失：24（随模块收口统一补齐）。
- 公开方法返回类型注解：6（优先修复被广泛调用的公共入口）。

## 遗留问题台账（首批：scheduler）

| 项 | 严重度 | 位置（模块） | 证据 | 建议 | 成本 |
|---|---|---|---|---|---|
| 排产落库+留痕缺失（action=schedule/simulate） | MAJOR | `core/services/scheduler/schedule_service.py` | `evidence/Conformance/conformance_report.md` | 在排产落库同事务内写入 `OperationLogs`，并与 `ScheduleHistory` 对齐 | M |
| scheduler 文件超 500 行（4 个） | 质量（MINOR） | `batch_service.py` / `config_service.py` / `schedule_optimizer.py` / `schedule_service.py` | `evidence/ArchAudit/arch_audit_report.md` | 按职责拆分为 `*_query_service.py` / `*_validators.py` / `*_utils.py` 等（避免行为变更） | L |
| `yes/no/workday` 等裸字符串枚举散落 | 质量 | scheduler + routes | `evidence/ArchAudit/arch_audit_report.md`（[ENUM]） | 统一走枚举/normalize；对外部输入仍允许大小写/空白容错 | M |
| Optional 返回值未检查（线索） | 风险线索 | scheduler | `evidence/DeepReview/reference_trace.md`（⚠） | 逐处回到源码核对：加 `None` 保护/抛 `ValidationError`/采用安全默认值 | S-M |


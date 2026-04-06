# Scheduler 模块闭环审阅报告（Batch1+Batch2）

- 时间：2026-02-28 14:52
- 范围：Phase1 Scheduler（两批闭环）
- 证据：
  - `evidence/Conformance/conformance_report.md`
  - `evidence/ArchAudit/arch_audit_report.md`
  - `evidence/Phase6/smoke_phase6_report.md`
  - `tests/test_architecture_fitness.py`（执行输出）
  - （回归脚本）`tests/regression_*.py`（执行输出）

## 目标（按计划口径）

- 将 scheduler 关键超大文件按职责拆分到 <500 行（不改变外部接口/行为为前提）。
- 修复对标 MAJOR：排产落库+留痕（Schedule + ScheduleHistory + OperationLogs[action=schedule/simulate]）一致性。
- 每批次完成：体检→修复→回归→留痕闭环，避免引入新架构违反/新回归。

## 事实摘要（来自 evidence/测试）

### 1) 一致性对标（Conformance）

- 结论：通过（BLOCKER=0，MAJOR=0）。
- 关键项：
  - 排产落库+留痕检查已通过（留痕落点在 `core/services/scheduler/schedule_persistence.py`）。
  - 文件行数约束检查已通过（核心目录 >500 行文件数：0）。

### 2) 架构适应度函数

- `tests/test_architecture_fitness.py`：9/9 PASSED（含复杂度门禁）。

### 3) Scheduler 冒烟

- `tests/smoke_phase6.py`：PASS（报告：`evidence/Phase6/smoke_phase6_report.md`）。

### 4) 架构合规审计（ArchAudit）

- 文件超限：0（已清零）
- 其它遗留仍存在：裸字符串枚举 / 复杂度 D-F / future annotations 等（见 `evidence/ArchAudit/arch_audit_report.md`）

## 本轮关键改动点（按“职责拆分 + 不改行为”）

### Batch1（schedule_service/schedule_optimizer）

- `core/services/scheduler/schedule_optimizer.py`
  - 抽取 `_run_ortools_warmstart`/`_run_multi_start` 到 `schedule_optimizer_steps.py`，主文件降到 <500 行。
- `core/services/scheduler/schedule_service.py`
  - 抽取模板/外部组回查到 `schedule_template_lookup.py`，主文件降到 <500 行。
- `core/services/scheduler/schedule_persistence.py`
  - `BatchOperationStatus.SCHEDULED` 等使用枚举，避免裸字符串状态漂移。
- `tests/generate_conformance_report.py`
  - 将“排产落库+留痕”检查定位到 `schedule_persistence.py`（符合当前职责拆分后的真实落点）。

### Batch2（config_service/batch_service）

- `core/services/scheduler/config_service.py`
  - 抽取 preset 相关逻辑到 `config_presets.py`，主文件降到 <500 行。
- `core/services/scheduler/batch_service.py`
  - 抽取 3 块高噪逻辑到独立模块，主文件降到 <500 行：
    - Excel 导入编排：`batch_excel_import.py`
    - 批次复制：`batch_copy.py`
    - 模板生成批次工序：`batch_template_ops.py`

## 回归执行（本轮跑过的关键脚本）

- 架构/对标：
  - `python -m pytest tests/test_architecture_fitness.py -v`
  - `python tests/generate_conformance_report.py`
- Scheduler 回归脚本（节选）：
  - `python tests/regression_freeze_window_bounds.py`
  - `python tests/regression_scheduler_apply_preset_reject_invalid_numeric.py`
  - `python tests/regression_batch_import_unchanged_no_rebuild.py`
  - `python tests/regression_scheduler_enforce_ready_default_from_config.py`
  - `python tests/regression_scheduler_accepts_start_dt_string_and_safe_weights.py`
  - `python tests/regression_scheduler_reject_nonfinite_and_invalid_status.py`
- 冒烟：
  - `python tests/smoke_phase6.py`

## 残留项（未在本轮处理，供后续排期）

- 裸字符串枚举：仍较多（本轮仅收敛了部分 scheduler 内 `yes/no` 语义，未全局清理）。
- 复杂度超标函数：仍存在（本轮保证“无新增违反”，未系统性拆分高复杂度函数）。
- future annotations/类型注解缺失：仍存在。


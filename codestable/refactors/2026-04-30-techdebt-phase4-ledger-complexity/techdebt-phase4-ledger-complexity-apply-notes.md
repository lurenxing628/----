---
doc_type: refactor-apply-notes
refactor: 2026-04-30-techdebt-phase4-ledger-complexity
status: in-progress
tags: [techdebt, oversize, complexity, quality-gate]
---

# techdebt phase4 ledger complexity apply notes

## 步骤 1：记录阶段 4/5 开工基线

- 完成时间：2026-04-30
- 改动文件：
  - `audit/2026-05/phase4_phase5_baseline.txt`
  - `codestable/refactors/2026-04-30-techdebt-phase4-ledger-complexity/*`
- 验证结果：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=841。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，oversize_count=8，complexity_count=29，silent_fallback_count=153，test_debt_count=5，accepted_risk_count=5。
- 偏离：无。

## 步骤 2：拆分 scheduler summary 与配置字段校验

- 完成时间：2026-04-30
- 改动文件：
  - `core/services/scheduler/summary/schedule_summary.py`
  - `core/services/scheduler/summary/summary_size_guard.py`
  - `core/services/scheduler/summary/summary_runtime_state.py`
  - `core/services/scheduler/config/config_field_spec.py`
  - `core/services/scheduler/config/config_field_coercion.py`
  - `开发文档/技术债务治理台账.md`
- 改动内容：
  - `schedule_summary.py` 保留原导入路径和 `__all__`，把摘要大小保护、运行状态、告警和冻结状态拼装拆到新模块。
  - `config_field_spec.py` 保留字段注册表和旧入口，把字段值兼容读取、选择项校验、数字/布尔/时间清洗拆到 `config_field_coercion.py`。
  - 台账通过受控刷新移除两个已达标的超长文件登记，`oversize_count` 从 8 降到 6；同步更新的 fallback 行号来自本批修改的 `schedule_summary.py::serialize_end_date`，不是无关启动链漂移。
- 已完成验证：
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check ...`：通过。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_sp05_path_topology_contract.py ... tests/regression_config_service_component_contract.py`：53 passed。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.gate.json`：0 errors，6 个既有 warning。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py`：passed，active_xfail_count=0，fixed_count=5，collected_count=841。
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check`：通过，oversize_count=6，complexity_count=29，silent_fallback_count=153。
- 偏离：无业务语义偏离；本批只拆文件和刷新已达标台账项。

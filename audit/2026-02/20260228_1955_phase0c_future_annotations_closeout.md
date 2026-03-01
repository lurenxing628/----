# Phase0c 收口留痕：future annotations 机械清零

- 时间：2026-02-28 19:55
- 目标：将 `arch_audit_report` 中“缺少 `from __future__ import annotations`”计数清零，不夹带业务逻辑改动。

## 本次机械改动范围（24 个文件）

- `web/routes/dashboard.py`
- `web/routes/equipment.py`
- `web/routes/excel_demo.py`
- `web/routes/personnel.py`
- `web/routes/process.py`
- `web/routes/scheduler.py`
- `web/routes/system.py`
- `core/services/common/openpyxl_backend.py`
- `core/services/common/tabular_backend.py`
- `core/services/equipment/__init__.py`
- `core/services/material/__init__.py`
- `core/services/personnel/__init__.py`
- `core/services/process/__init__.py`
- `core/services/process/unit_excel/__init__.py`
- `core/services/report/__init__.py`
- `core/services/scheduler/__init__.py`
- `core/services/system/__init__.py`
- `core/services/system/maintenance/__init__.py`
- `data/repositories/__init__.py`
- `core/models/__init__.py`
- `core/infrastructure/backup.py`
- `core/infrastructure/database.py`
- `core/infrastructure/logging.py`
- `core/infrastructure/transaction.py`

## 退出证据（以 evidence 为准）

- 复跑架构审计：`python .cursor/skills/aps-arch-audit/scripts/arch_audit.py`
- 最新报告：`evidence/ArchAudit/arch_audit_report.md`（生成时间：2026-02-28 19:34:10）
  - `缺少 future annotations：0`
  - 总问题数：176 → 152（净减少 24）

## 备注

- 本批次仅增加 future import 与必要空行；未做任何重命名、逻辑调整或接口变更。


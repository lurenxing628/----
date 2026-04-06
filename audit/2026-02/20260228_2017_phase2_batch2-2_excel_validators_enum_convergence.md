## Phase2 / Batch2-2 留痕：excel_validators 口径收敛（枚举 .value）

- 时间：2026-02-28 20:17
- 目标：按枚举映射表，把 Excel validators 中的关键枚举口径（优先级/齐套/工作日历/yes-no）统一到 `core/models/enums.py`，减少裸字符串比较与散落常量。
- Schema 变更：无
- 开发文档回填：未触发（未改 Route/模板列名/用户可见文案）

### 影响域（实际改动文件）

- `core/services/common/excel_validators.py`
  - 引入 `BatchPriority/ReadyStatus/CalendarDayType/YesNo` 并统一返回值为 `.value`；
  - 将 `== "workday"` 等裸字符串比较替换为与枚举 `.value` 的比较（输出字符串保持一致）。

> 备注：按计划 Batch2-1（`core/services/common/excel_import_executor.py`）已快速复核其作为通用导入执行器的职责与类型注解，未发现需调整点，因此未产生代码变更。

### 结果与证据

- **ArchAudit**
  - 裸字符串枚举：80 → 78
  - 枚举集合比较（INFO）：86 → 72
  - `evidence/ArchAudit/arch_audit_report.md` 已更新（生成时间 20:17 左右）
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；`evidence/Conformance/conformance_report.md` 显示 MAJOR=0

### 下一步（按计划）

- 进入 **Batch2-3（Process unit_excel 工具链）**：`core/services/process/unit_excel/` + `core/services/process/unit_excel_converter.py`


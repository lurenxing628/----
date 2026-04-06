## Phase2 / Batch2-3 留痕：Process unit_excel 工具链闭环

- 时间：2026-02-28 20:27
- 目标：闭环 `core/services/process/unit_excel/` 工具链（解析 → 转换模板 → 导出），并把高复杂度/裸字符串枚举按既定映射表收敛为可维护形态。
- Schema 变更：无
- 开发文档回填：未触发（本批次不改 Route/模板列名/用户可见文案）

### 影响域（实际改动文件）

- `core/services/process/unit_excel/template_builder.py`
  - 将 `UnitTemplateBuilder.build()` 拆分为一组私有 helper（单函数复杂度降到阈值内，避免新增复杂度门禁违例）。
  - 输出行中 `active/internal/external` 等值统一引用 `core/models/enums.py` 的 `.value`（输出字符串保持不变）。
  - 去除裸字符串比较（例如外协筛选不再写死 `"external"`）。
- `core/services/process/unit_excel/parser.py`
  - 将 `UnitExcelParser.parse()` 拆分为私有 helper（更新/创建 `PartContext`、追加 `StepRecord`），单函数复杂度降到阈值内；解析语义保持不变。

### 结果与证据

- **ArchAudit**
  - `evidence/ArchAudit/arch_audit_report.md` 已更新：
    - 圈复杂度超标（>15）：44 → 42（移除 unit_excel 的 `build/parse` 两项超标）
    - 裸字符串枚举：78 → 77（unit_excel 内的 `"external"` 裸比较已收敛）
- **UnitExcel 回归脚本（关键契约）**
  - `python tests/regression_unit_excel_converter_facade_binding.py`：OK
  - `python tests/regression_unit_excel_converter_duplicate_part_rows_no_override.py`：OK
  - `python tests/regression_unit_excel_converter_merge_steps_and_classify.py`：OK
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；`evidence/Conformance/conformance_report.md` 显示 MAJOR=0

### 下一步（按计划）

- 进入 **Batch2-4（闭环一条域导入链路）**：选定 1 条“域 service + route + template”链路做端到端闭环（建议从 Personnel 域开始）。


## Phase3 / Batch3-P2 留痕：Process ExternalGroupService（typehint + 枚举收敛 + 复杂度拆分）

- 时间：2026-02-28 20:47
- 目标：闭环 `ExternalGroupService` 的基础质量缺口：补齐公开方法返回类型注解、消除 `external` 裸字符串比较、拆分 `set_merge_mode()` 以降低单函数复杂度与重复逻辑。
- Schema 变更：无
- 开发文档回填：未触发（未新增/删除 Route；未变更模板列名；未新增枚举）

### 影响域（实际改动文件）

- `core/services/process/external_group_service.py`
  - `list_by_part()` / `set_merge_mode()` 补齐返回类型注解（`List[ExternalGroup]` / `ExternalGroup`）。
  - 组内外协工序筛选：`source == "external"` 收敛为 `SourceType.EXTERNAL.value`（输出/落库字符串保持不变）。
  - 将 `set_merge_mode()` 拆分为若干私有 helper（外协工序筛选、组表字段更新、merged/separate 两分支落库），减少嵌套与重复。

### 结果与证据

- **回归（merge_mode 大小写兼容）**
  - `python tests/regression_external_group_service_merge_mode_case_insensitive.py`：OK
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 下一步（按计划）

- 继续 Phase3：进入 Personnel 域（优先 `operator_machine_service.py` 的复杂度与 Excel 关联链路闭环）。


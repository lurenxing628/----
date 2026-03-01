## Phase3 / Batch3-P1 留痕：Process 外协删除规则（枚举口径收敛 + 复杂度拆分）

- 时间：2026-02-28 20:44
- 目标：把 Process 域“外部工序删除规则”链路纳入同一口径（`internal/external`、`active/deleted`），并对 `DeletionValidator.can_delete()` 做可维护性拆分（不改变业务规则与中文提示语义）。
- Schema 变更：无
- 开发文档回填：已回填（新增 `PartOperations.status` 枚举说明，属于新增枚举联动）

### 影响域（实际改动文件）

- `core/models/enums.py`
  - 新增 `PartOperationStatus`：`active/deleted`，作为 `PartOperations.status` 的唯一事实来源。
- `core/services/process/deletion_validator.py`
  - `internal/external` 比较统一改为 `SourceType.*.value`；
  - `active/deleted` 比较统一改为 `PartOperationStatus.*.value`；
  - 将 `can_delete()` 拆分为若干私有 helper（校验目标/剩余集检查/断档检测），降低单函数圈复杂度并便于复用。
- `core/services/process/part_service.py`
  - 将 `PartOperations.source/status` 的比较与写入值统一改为引用 `SourceType/PartOperationStatus`；
  - 将 `route_parsed`（yes/no）校验与写入值改为引用 `YesNo.*.value`；
  - 将 `ExternalGroups.merge_mode` 默认值写入改为引用 `MergeMode.SEPARATE.value`（字符串落库保持不变）。
- `开发文档/系统速查表.md`
  - 补充 `PartOperations.status`：`active/deleted` 的枚举说明。

### 结果与证据

- **回归（DeletionValidator）**
  - `python tests/regression_deletion_validator_source_case_insensitive.py`：OK
- **Smoke（Phase5 中覆盖外协组删除/规则判定）**
  - `python tests/smoke_phase5.py`：OK；产物：`evidence/Phase5/smoke_phase5_report.md`
- **Architecture Fitness**
  - `python -m pytest tests/test_architecture_fitness.py -v`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 下一步（按计划）

- 继续 Phase3-Process：进入 `core/services/process/external_group_service.py`（缺失 typehint + `external` 裸比较 + 高复杂度 `set_merge_mode`）的小批次闭环。


## Phase5 / Batch5-1 留痕：BatchMaterialService 直连 SQL 下沉到 Repository

- 时间：2026-02-28 21:33
- 目标：修复 `core/services/material/batch_material_service.py` 的 Service 直连 SQL（JOIN 查询），保证分层方向为 `Service → Repository → DB`；SQL 保持参数化，字段契约不漂移。
- Schema 变更：无
- 开发文档回填：未触发（未新增/删除 Route；未变更 Schema/模板列名/用户可见文案）

### 影响域（实际改动文件）

- `data/repositories/batch_material_repo.py`
  - 新增 `list_with_material_details_by_batch(batch_id)`：封装 `BatchMaterials` JOIN `Materials` 的查询（`?` 参数化）。
- `core/services/material/batch_material_service.py`
  - `list_for_batch()` 改为调用 `BatchMaterialRepository.list_with_material_details_by_batch()`，移除 `self.conn.execute(...).fetchall()`。

### 结果与证据

- **Architecture Fitness**
  - `python -m pytest -q tests/test_architecture_fitness.py`：9 passed
- **Conformance**
  - `python tests/generate_conformance_report.py`：OK；产物：`evidence/Conformance/conformance_report.md`

### 备注

- Phase5 的“可选基础设施一致性批次”（`core/infrastructure/`）本轮未纳入；如后续触发 schema/迁移或出现 infra 级门禁失败，再按影响域单独开批次闭环。


# Service 层直连 SQL 盘点与分流（Phase2~6）

- 时间：2026-02-28 19:45
- 目的：盘点 `core/services/` 中的 `conn.execute()/fetch*()` 直连 SQL 点，按模块闭环策略分流到对应 Phase/Backlog，避免 Phase5 范围爆炸。

## 扫描方法（只读）

- 扫描范围：`core/services/**/*.py`
- 关键模式：
  - `self.conn.execute(` / `conn.execute(`
  - `.fetchall(` / `.fetchone(`
- 说明：本清单用于“分流与排期”；实际修复时仍需回到源码上下文确认语义与事务边界。

## 直连 SQL 清单（去重后）

| 文件 | 行号（命中） | 直连 SQL/用途（摘要） | 分流归属 | 预期修复方式（后续批次） |
|---|---:|---|---|---|
| `core/services/scheduler/gantt_service.py` | 74 | `PRAGMA database_list`（推导 DB 文件路径用于 critical_chain cache key） | Phase1b（Scheduler 残留） | 抽到 repository/infrastructure 查询；或提供统一 DB scope 获取函数，Service 不直连 SQL |
| `core/services/equipment/machine_service.py` | 205-208, 247-249 | 删除前校验：`BatchOperations` 是否引用 `machine_id`（`SELECT 1 ... LIMIT 1`） | Phase3-Equipment | 由 repository 提供 `exists_*` 查询（如 `BatchOperationRepository.exists_for_machine()`），Service 只调用 repo |
| `core/services/process/part_service.py` | 156 | 删除/校验：`Batches` 是否引用 `part_no`（`SELECT 1 ... LIMIT 1`） | Phase3-Process | 由 repository 提供 `exists_*` 查询（如 `BatchRepository.exists_by_part_no()`），Service 只调用 repo |
| `core/services/personnel/operator_machine_service.py` | 199-201, 357-359 | Excel 导入预览：读取 `OperatorMachine` 现有关联（`SELECT ... FROM OperatorMachine`） | Phase3-Personnel | 扩展 `OperatorMachineRepository`：提供读取现有关联/字段的查询方法，Service 只做编排与校验 |
| `core/services/personnel/operator_machine_service.py` | 370 | Excel 导入应用：清空 `OperatorMachine`（`DELETE FROM OperatorMachine`） | Phase3-Personnel | 由 repository 提供批量删除方法；确保在 Service 事务内执行并写入操作留痕 |
| `core/services/material/batch_material_service.py` | 47-57 | 列表查询：`BatchMaterials` join `Materials`（用于 `list_for_batch`） | Phase5-RepoSQL（固定纳入） | 把 SQL 下沉到 `BatchMaterialRepository`（参数化 `?`），Service 仅负责校验/事务/留痕 |
| `core/services/system/maintenance/cleanup_task.py` | 58, 65, 75-86 | 自动清理：统计/删除 `OperationLogs`（分批 DELETE） | Backlog（system maintenance） | 若纳入 Phase5（infra）则下沉到 repository；否则保留为 Backlog，后续单独闭环 system 域 |
| `core/services/report/queries.py` | 11-28, 40-51 | 报表取数：逾期清单/停机区间查询（JOIN/区间重叠） | Backlog（report） | report 域后续闭环时统一迁移到 repository（或 report repo），避免 service 直连 SQL |

## 分流原则（执行约束）

- 仅在当前模块闭环批次内修复该模块的直连 SQL；其它模块点位仅登记到 Backlog。
- 迁移 SQL 到 repository 时必须保持：
  - SQL 参数化（`?` + params）
  - `from_row()`/字段契约不漂移
  - Service 事务边界不变（Service 层 `TransactionManager` 管理）


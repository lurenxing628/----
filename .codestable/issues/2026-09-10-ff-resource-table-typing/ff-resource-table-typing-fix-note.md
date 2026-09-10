---
doc_type: issue-fix
issue: 2026-09-10-ff-resource-table-typing
path: fast-track
fix_date: 2026-09-10
tags: [workbench, resource-table, pyright, readonly, FF]
---

# FF resource table 查询类型配对修复

下文先保留第一块两诊断修复的实测记录；扩大授权后的最终 FE-01 状态见末节。

## 根因与实际修复

- 原 `resource_table_queries.py:102:37` 的 `page(query)` 和 `108:38` 的 `metrics(query)` 将独立推导的 reader union 与 request union 配在一起。`kind == "material"` 无法让类型检查器恢复两者的对应关系。
- `web/routes/workbench/resource_table_queries.py:95` 保留 `_scope` 的输入和未知 kind 校验、翻页必须携带快照的校验，再按具体请求类型分派。
- `:104` 的 `_material_table_query(query: MaterialPageRequest, token)` 只构造物料 reader；`:119` 的 `_resource_table_query(query: ResourcePageRequest, token)` 只构造对应资源 reader。
- 两条路径都在原 `read_snapshot()` 事务内完成快照绑定、分页、越界拒绝、实体投影、指标、create context 和响应。物料继续单独读取 `metrics(query)`；资源继续使用 `page.pop("metrics")`，不额外重算资源指标。
- `_scope`、`_reader`、facet/facet-selection、只读错误包装、POST 路由不变。未加 `ignore`、`cast`，未改资源服务、公共 controls、registry 或 pyright 配置。

## 手工写集

1. `web/routes/workbench/resource_table_queries.py`：原先就是未跟踪文件，在当前内容上做定点修复。
2. `tests/workbench/test_resource_table_domain_pairing.py`：新增独立专属测试，21 个参数化用例。
3. 本修复记录。

## 实测结果

运行环境：仓库 `.venv/bin/python`，Python 3.8.10。

```text
.venv/bin/python -m pyright -p pyrightconfig.gate.json
before: 230 errors, 15 warnings, 0 informations; exit 1
after:  228 errors, 15 warnings, 0 informations; exit 1
```

逐条比较诊断行：仅删除上面两个 reportArgumentType；新增 0；目标产品模块剩余诊断 0。其他 228 errors 未处理，完整产品静态检查仍失败。

```text
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/workbench/test_resource_table_domain_pairing.py \
  tests/workbench/test_resource_table_api.py \
  tests/workbench/test_resource_table_queries.py \
  tests/workbench/test_material_queries.py \
  tests/workbench/test_material_api.py \
  tests/workbench/test_resource_api.py
224 passed in 36.13s; exit 0

.venv/bin/python -m ruff check --no-cache \
  web/routes/workbench/resource_table_queries.py \
  tests/workbench/test_resource_table_domain_pairing.py
All checks passed!; exit 0
```

- 新增 21 用例覆盖物料与资源两领域的六个视图、具体请求与 reader 配对、同事务分页/指标、列筛选、菜单选择、原快照续页、过时页码、变化范围及混用 token 拒绝。
- 覆盖物料 page/metrics 和资源 page 注入失败仍返回 `storage_failure`、`committed=false`，以及未知 kind / 非表格目录 kind 在三个 POST 入口仍为 404。
- 新 fixture 在所有请求上安装 SQLite authorizer，只允许 SELECT/READ/FUNCTION/TRANSACTION/SAVEPOINT；21 用例均无被拒绝的写入尝试，前后全量 stored_state（含业务、永久引用、receipts、SchemaVersion、total_changes）一致，事务已退出。因此这是实际 0 writes 证据，不是仅检查响应文字。
- 原生产 Flask resource table API/快照/筛选回归全部保留且通过，含 10000 筛选值的 HTTP 用例。未运行整仓 quality gate：工作区 dirty、其他静态诊断仍存在，且完整门禁会写共享产物。本结果仅为局部 dirty-worktree 验证，不是 clean proof。

原始日志隔离于 `/tmp/aps-ff-resource-table.Qo7QvG/`：`pyright-before.log`、`pyright-after.log`、`pytest.log`。

## 源文件 SHA-256

```text
before product:
d6a46c974e59420883fe4b888e2410f1fa158bea5a96093701b5e194c1a2900c
after web/routes/workbench/resource_table_queries.py:
a4ae49b30cab14ae59d831ecce0bacd66ada05a85c83ac1c9df727c195a51b83
tests/workbench/test_resource_table_domain_pairing.py:
4e12e37bdc61e9b82ed202eb14f3b85deb52b5f1568201a7f8109d1b37d0cd4c
unchanged pyrightconfig.gate.json:
8c7e7f40351235c9e0ca919bdc90f6afbb697e2c1a428fee028c5b437a85b8c1
```

## 边界偏差与交接

- 起步执行用户要求的 `python3 -m tools.symbol_locator whereis/callers/callees resource_table_query` 时，工具检测过期并自动重建 `.codestable/checkup/latest/callgraph/`。这一工具副作用违反了不触碰全局静态产物的边界，必须单独披露，不能宣称只有上述三文件受到写入。
- 自动产物为 `functions.json`、`edges.json`、`dynamic_unresolved.json`、`dataflow_nodes.json`、`risk_dataflow.json`、`high_fan_in.json`、`summary.json`、`cycles.json`、`islands.json`、`articulation_points.json`。这些文件起步已 dirty；没有回滚、清理或用 HEAD 覆盖，避免破坏其他代理内容。后续未再启动重建。
- 未 stage/commit；未启动、停止或访问 53144 等预览。未手工修改其他代理文件。pyright 与 pytest 日志均未写入共享门禁证据目录。
- FD 登记交接：新增 `tests/workbench/test_resource_table_domain_pairing.py`，21 用例；请加入 workbench required 测试登记。FF 不改 registry。当前任务工具列表未暴露 FD 的独立通信入口，将此登记请求交给主线转 FD，不把转交请求写成登记完成。

## FE-01 扩展阶段：完成并冻结

用户随后授权 `dispatch-plan.json` 的 FE-01 五文件，并明确本阶段完成后停止。现已完成这一范围；不继续其他诊断，不新增公共域修改，不 stage/commit。

### 最终产品写集与位置

- `web/routes/workbench/resource_table_queries.py:95/104/119`：第一块具体领域配对保持不变。
- `core/models/workbench_resource_table_query.py:18`：`category is None` 显式得到空扩展列；现有 internal/external 列、未知归属拒绝和未知 kind 行为保持。
- `core/services/workbench/resource_table_facts.py:74`：真正未绑定的可选关系仍为空；关系成员若缺失编号，显式 `storage_failure`，不跳过或伪装未绑定；`:94` 显式处理空 policy mode，保留既有枚举和旧原值标签。
- `web/routes/workbench/resource_file_exports.py:26/35`：route 只处理 HTTP 字段存在性及调用文件服务，不再导入或读取 repository；原 query_scope、snapshot_ref、source、服务器 binding 文档、导出下载校验与响应头未动。
- `core/services/workbench/resource_files.py:125`：新增领域方法 `preview_export()`，在已验证快照事务内核对选中永久引用、工种归属及全量/筛选数量；保留 selected 次序、显式空选中和 all 的 category 限制。既有 `export()` 与导入实现不改。

### 最终验证

```text
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/workbench/test_fe01_resource_static_contract.py \
  tests/workbench/test_resource_table_domain_pairing.py \
  tests/workbench/test_resource_table_queries.py \
  tests/workbench/test_resource_table_api.py \
  tests/workbench/test_resource_files.py \
  tests/workbench/test_resource_file_api.py \
  tests/workbench/test_material_queries.py \
  tests/workbench/test_material_api.py \
  tests/workbench/test_resource_api.py
327 passed in 49.26s; exit 0

.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/gate_meta/test_architecture_fitness.py::test_routes_do_not_import_repository
1 passed in 0.43s; exit 0
```

- `tests/workbench/test_fe01_resource_static_contract.py` 单独先跑：31 passed in 1.36s。五资源视图的 all/filtered/selected 实际 HTTP 下载全部走服务；测试锁住 source/snapshot/as_of/顺序/归属以及 refs 缺省和显式 null 的不同拒绝结果。
- 两个新增文件共 52 用例。所有涉及读取的专属 fixture 使用 SQLite authorizer 拒绝任何非只读操作，并核对 stored_state/total_changes/事务退出，均为 0 writes。
- 原配置 `.venv/bin/python -m pyright -p pyrightconfig.gate.json` 再跑后为 `91 errors, 15 warnings, 0 informations`，exit 1。与初始日志按 FE-01 五文件筛选比较：原 7 条诊断全部消失，五文件剩余诊断 0。全局从 230 到 91 的其他下降来自共享工作区的并行改动，不能归功于 FF，也不代表整仓通过。
- `ruff check --no-cache` 五产品文件加两专属测试全部通过。五文件 `radon cc -s` 中所有函数/方法不超过 15；新增 `preview_export` 复杂度 8，没有引入超阈值函数。
- 本阶段 symbol_locator 使用 `CHECKUP_CALLGRAPH=/tmp/aps-ff-resource-table.Qo7QvG/callgraph` 隔离产物；一次同目录并行重建导致 JSON 暂读失败，已串行重试成功，未再写全局 callgraph。第一块全局副作用仍保留前述披露，不作无损回滚的虚假保证。
- 原始日志：`/tmp/aps-ff-resource-table.Qo7QvG/fe01-focused.log`、`fe01-regression.log`、`fe01-route-boundary.log`、`pyright-fe01-after.log`。仍只有 dirty-worktree 定点验证，不是整仓 clean proof。

### 冻结 SHA-256

```text
a4ae49b30cab14ae59d831ecce0bacd66ada05a85c83ac1c9df727c195a51b83  web/routes/workbench/resource_table_queries.py
c3adf71f5c7a5f492542028acb4f904fc996f2e324f525d1f3a23cc4dab3b49d  core/models/workbench_resource_table_query.py
094b8170407fa082b2d44f0343aaf8f9f6abb699278aad1af3d225fc692cd056  core/services/workbench/resource_table_facts.py
58836c052efdf3ef451485c0b59179ab58e9015753ef80b83e52d97931ffca9a  web/routes/workbench/resource_file_exports.py
8ab69ce476c520dfbdce463209cad8adb26d32f309c41008d9d00d486634f7b5  core/services/workbench/resource_files.py
a8e78da57dd4d23b7ce95e4152f7c224cd9f03e2a7cc2c61e68d57fb31f7240f  tests/workbench/test_fe01_resource_static_contract.py
4e12e37bdc61e9b82ed202eb14f3b85deb52b5f1568201a7f8109d1b37d0cd4c  tests/workbench/test_resource_table_domain_pairing.py
8c7e7f40351235c9e0ca919bdc90f6afbb697e2c1a428fee028c5b437a85b8c1  pyrightconfig.gate.json (unchanged)
```

### 主线与 FD 交接

- 第一块完成通知已通过任务工具交给主线，并请求转 FD 登记 21 用例文件。
- 最终冻结通知同时交接 `tests/workbench/test_fe01_resource_static_contract.py` 的 31 用例。FD 负责两个文件的 registry 登记；FF 不改 registry，不宣称登记已完成。
- 最终手工写集为上述五产品文件、两专属测试和本记录，均保持未提交。没有额外公共域实施。用户要求的本阶段工作结束，不继续 FE-02 或其他簇。

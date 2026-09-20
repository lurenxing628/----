---
doc_type: roadmap
slug: foundation-boundary-governance
status: active
created: 2026-09-20
last_reviewed: 2026-09-20
tags: [architecture, data-boundary, schema, package-structure, quality-gate, refactor]
related_requirements: []
related_architecture: [ARCHITECTURE, service-scheduler, workbench-shell]
---

# 地基边界治理路线

## 1. 背景

2026-09-20 的全仓架构评估结论是：宏观分层不需要再动。显式导入边的 SCC 为 0，层级倒置只剩两处 `TYPE_CHECKING` 注解，路由、服务、视图模型的边界都有适应度测试锁着。真正的债集中在三处，都发生在 2026-09-10 到 09-11 的工作台冲刺期之后：

1. **服务层 SQL 泄漏**。`core/services/workbench` 有 49 个文件直接 `conn.execute`，共 107 条语句（80 SELECT、11 写、8 PRAGMA、8 变量拼接，其中 25 条动态拼接）。同时边界是双向糊的：`data/repositories` 有 17 个工作台仓储在 raise 带用户文案和 HTTP 码的 `WorkbenchCommandRejected`，`workbench_trial_raw_repo.read_raw_table` 是按表名整表读的通用逃生口。服务层绕过 `BaseRepository.execute` 的 sqlite3 到 AppError 翻译，数据库错误直接落成 Flask 500。
2. **表结构两份手抄没有对账**。`core/infrastructure/workbench_*_schema.py` 是新表 DDL 的唯一来源，迁移调用它们；但 `schema.sql`（78 表，新库路径）手抄同样 DDL。运行期只比表名加一份手写的（表，列）清单，没有“新库 vs 逐版迁移”的整库对账测试；v1 迁移只补列，不能从空库起步。
3. **包内平铺没有接缝**。workbench 233 个文件平铺、scheduler 根 85 个加 `run/` 124 个（81 个 `optimizer_*`）、`web/routes/workbench` 73 个。500 行门禁把文件切碎，但跨模块导入私有符号 workbench 41 处、scheduler 51 处、web 43 处，说明切分没有命名接缝；簇之间还有 plan↔run、plan↔trial、piece↔run、dashboard↔run、calibration↔template 五对双向依赖。

次级事实：治理代码约 52k 行占产品代码 35%，门禁清单没有分步耗时记录；`core.infrastructure.errors` 兼容路径仍被约 140 个生产文件和 179 个测试文件引用；`request_service_direct_assembly` 规则的原始对象（请求级容器）已随旧路由层删除；含父包 `__init__` 隐式加载边的生产基线仍有 1 个目录环（`.`⇄`web/bootstrap`⇄`web/routes`）和 8 个包门面型文件环。

本路线把上述全部收进一条“先止血、再排水、再重塑、最后立规”的顺序。

## 2. 范围与明确不做

### 本 roadmap 覆盖

- 三条棘轮门禁：服务层不写 SQL、仓储层不做裁决、不跨模块导入私有符号；一条整库 schema 对账测试；门禁分步耗时产物。
- 把工作台服务层 107 条 SQL 按风险顺序全部排回 `data/repositories` 与 `core/infrastructure`，退役通用逃生口和仓储内裁决。
- workbench 按业务簇分子包，scheduler 切 `run/optimizer/graph` 与根目录业务族，批次族移出 scheduler，删除只服务测试的根目录垫片。
- `schema.sql` 改为由“v4 起点加迁移链”生成的产物并由门禁对账；手写列清单改为派生。
- 尾项：错误合同旧路径一次性收口；web 目录环消除；`core/models` 反向注解；`request_service` 规则并入 web helper 规则。
- 把边界政策写成决策文档。

### 明确不做

- 不引入 DI 容器、事件总线、动态插件发现或 ORM/迁移框架（单机离线、Python 3.8、PyInstaller 冻结交付）。
- 不做垂直特性切片（把 repo、model、service 按功能重新分层），保持现有 `core/models → data/repositories → core/services → web` 分层。
- 不改排产算法结果、候选排序、公开页面载荷、路由地址、导出内容。
- 不改新库安装路径的运行行为（新库仍由 `schema.sql` 一次建成，不改成现场跑 32 步迁移）。
- 不重写门禁工具链，不删弱现有 `test_architecture_fitness.py` 规则；新增门禁机制遵守“进一退一”。
- 前端 `frontend/workbench/app` 213 个平铺文件暂不分目录：构建脚本只 glob 顶层，且 aps-frontend-fusion 路线仍在改前端。
- 不做全量门禁实跑（用户裁决：只跑定向测试）。

## 3. 模块拆分（概设）

```text
地基边界治理
├── G 棘轮门禁：三条基线只减不增的适应度规则 + schema 对账 + 门禁耗时
├── S SQL 排水：把服务层 SQL 按写语句 → 自省 → 仓储形类 → 余下 SELECT → 逃生口的顺序排回 data/infrastructure
├── P 包重塑：workbench 簇层次与子包、scheduler 业务族子包与垫片清理
├── D schema 事实源：schema.sql 生成化 + 手写列清单派生化
├── T 尾项：errors 路径、web 目录环、models 反向注解、request_service 规则
└── C 政策：把边界规则写成决策文档
```

### G · 棘轮门禁
- **职责**：用“基线 JSON + 适应度测试”把三条边界规则和 schema 对账做成机器可判的合同；基线条目只能减少，新增即红。给门禁回执补分步耗时。
- **承载的子 feature**：sql-boundary-ratchet、private-import-ratchet、schema-parity-test、gate-step-timing
- **触碰的现有代码**：`tools/scan_*.py`（新增扫描器）、`.codestable/checkup/*_baseline.json`（新增基线）、`tests/gate_meta/`（新增测试）、`tools/test_registry_groups_misc.py`（登记）、`scripts/run_quality_gate.py` 与 `tools/long_gate_manifest.py`（回执耗时字段）

### S · SQL 排水
- **职责**：SQL 文本只允许出现在 `data/repositories` 和 `core/infrastructure`；服务层保留裁决，仓储层只返回事实。
- **承载的子 feature**：sql-drain-writes、sql-drain-introspection、sql-drain-storage-classes、sql-drain-remaining-selects、sql-drain-hatch-and-policy
- **触碰的现有代码**：`core/services/workbench/*.py`（49 个泄漏文件）、`data/repositories/workbench_*.py`（新增或扩方法）、`core/infrastructure/`（新增连接守卫与快照读取）

### P · 包重塑
- **职责**：把平铺文件按业务簇收进子包，子包之间只允许单向依赖，共享叶子单独成包；删除只服务测试的垫片。
- **承载的子 feature**：workbench-cluster-layering、workbench-subpackages、scheduler-family-subpackages
- **触碰的现有代码**：`core/services/workbench/`、`core/services/scheduler/`、所有 import 这些模块的生产与测试文件、`core/services/scheduler/_frozen_import_anchor.py`

### D · schema 事实源
- **职责**：`schema.sql` 成为生成物，DDL 模块与迁移链是唯一手写源；运行期结构校验从手写清单改为与 `schema.sql` 声明结构比对。
- **承载的子 feature**：schema-sql-generated
- **触碰的现有代码**：`schema.sql`、`tools/generate_schema_sql.py`（新增）、`core/infrastructure/migration_state.py`、`core/infrastructure/database_bootstrap.py`

### T · 尾项
- **职责**：四件互相独立的小收口。
- **承载的子 feature**：errors-path-consolidation、web-dir-cycle-removal、models-service-annotation-inversion、request-service-rule-fold
- **触碰的现有代码**：约 320 个 import `core.infrastructure.errors` 的文件、`web/routes/workbench/system_actions.py`、`system_runtime.py`、`web/bootstrap/workbench_request_lifecycle_wsgi.py`、`core/models/workbench_run_compute.py`、`tools/quality_gate_shared.py`

### C · 政策
- **职责**：把 schema 事实源、子包规则、门禁进退规则、测试往接缝收四条政策写成 `cs-decide` 决策文档。
- **承载的子 feature**：boundary-policy-decisions
- **触碰的现有代码**：仅 `.codestable/compound/`

## 4. 模块间接口契约 / 共享协议（架构层详设）

### 4.1 棘轮基线文件格式

**方向**：G 的扫描器 → G 的适应度测试；S/P 各条子 feature 在退役条目时改基线。
**形式**：JSON 文件，`.codestable/checkup/{rule}_baseline.json`。

```
{
  "schema_version": 1,
  "rule": "sql_boundary" | "data_policy" | "private_import",
  "scope_roots": ["core", "web", "data"],
  "note": "一句话说明规则与退役方式",
  "entries": [ { "path": "core/services/workbench/trial.py", "kind": "conn_execute", "count": 3 } ]
}
```

**约束**：
- 比较口径按 `(path, kind)`：当前扫描出现基线没有的键 → 失败（新增债务）；基线有而当前没有的键 → 失败并提示“请从基线移除”（棘轮）；同键 `count` 增加 → 失败，减少 → 允许且提示刷新。
- 刷新只允许通过 `python -m tools.scan_<rule> --refresh`，测试不得自动改写基线。
- 路径以仓库根为基准、正斜杠、`git ls-files` 可见。

### 4.2 三条边界规则的判定口径

**方向**：G → S/P（作为硬约束）。
**形式**：AST 扫描器，`tools/scan_sql_boundary.py`、`tools/scan_private_imports.py`；CLI 与 `tools/scan_import_cycles.py` 同风格：`--json`、`--refresh`、`--fail-on-new`、`--quiet-when-clean`。

```
规则 sql_boundary（扫描 core/services、core/algorithms、core/models、core/plugins、web）：
  kind=conn_execute   调用 .execute/.executemany/.executescript/.fetchone/.fetchall，
                      接收者是 Name/Attribute 且末段匹配 {conn, connection, db, cursor, cur} 或以 ".conn" 结尾
  kind=sqlite_connect 调用 sqlite3.connect(...)
  kind=schema_probe   字符串常量含 "sqlite_master" 或以 "PRAGMA " 开头
  允许目录：data/repositories/**、core/infrastructure/**

规则 data_policy（扫描 data/**）：
  kind=policy_import  import 名为 reject / inconsistent / fail / WorkbenchCommandRejected / WorkbenchCommandUncertain
  kind=policy_raise   raise WorkbenchCommandRejected(...) 或调用 reject(/inconsistent(/fail(
  kind=identifier_param  函数形参名出现在含 "FROM " / "INTO " / "UPDATE " / "JOIN " 的 BinOp/JoinedStr SQL 中（按表名读表的逃生口）

规则 private_import（扫描 core、web、data）：
  kind=private_symbol  `from <模块> import _name`（模块不是当前包的父包 __init__ 且 _name 不是 __all__ 中的名字）
  豁免：`_frozen_import_anchor`、以 `_` 开头的模块名本身、tests/ 目录
```

**约束**：
- 服务层持 `conn` 只能做两件事：传给仓储构造函数，交给 `core.infrastructure.transaction` 的事务管理器。
- 仓储返回 dict / list / tuple / int / bool / None，允许抛 `AppError`（含 `NotFoundError`），不得抛业务拒绝。

### 4.3 排水后的仓储与基础设施接口

**方向**：S 各条 → 现有服务层调用方。
**形式**：函数调用。

```
# 仓储：一表一仓储或一读模型一查询仓储，均继承 BaseRepository
class WorkbenchRunHistoryQueryRepository(BaseRepository):
    def directory_capacity(self) -> Dict[str, Dict[str, int]]   # {table: {"rows": n, "bytes": n, "max_document_bytes": n}}
    def orphan_probe(self) -> Dict[str, bool]                    # {"receipts_without_job": bool, ...}
    def list_jobs(self) -> List[Dict[str, Any]]
    def list_candidates(self) -> List[Dict[str, Any]]
# 服务层：拿到事实后自己 reject()/inconsistent()

# 写语句：一律进已有主数据仓储
PartOperationRepository.clear_external_group(part_no: str, group_id: str) -> int
PartOperationRepository.mark_deleted(op_id: int) -> int
PartOperationRepository.update_fields(op_id: int, fields: Dict[str, Any]) -> int   # 列名白名单在仓储内
PartRepository.update_route(part_no: str, route_raw: str) -> int
ExternalGroupRepository.delete(part_no: str, group_id: str) -> int
ExternalGroupRepository.update_total_days(group_id: str, total_days: int) -> int
WorkbenchRunRepository.finish_with_error(run_ref: str, state: str, finished_at: str, error_json: str) -> int

# 基础设施
core/infrastructure/connection_guards.py
    @contextmanager def query_only(conn) -> Iterator[None]        # 进入置 PRAGMA query_only=ON，退出还原
    def foreign_keys_enabled(conn) -> bool
core/infrastructure/schema_probe.py
    def table_exists(conn, name: str) -> bool                      # 复用 migration_common.table_exists
    def table_names(conn) -> Set[str]
    def schema_objects(conn) -> List[Tuple[str, str, str, str]]    # (type, name, tbl_name, sql) 有序
    def table_columns(conn, name: str) -> List[str]
    def main_database_path(conn) -> str
core/infrastructure/snapshot_connection.py
    @contextmanager def open_readonly_immutable(path: str) -> Iterator[sqlite3.Connection]
    def ddl_columns(create_table_sql: str) -> List[str]           # 用临时内存库解析已知 DDL 的列名
```

**约束**：
- SQL 原样带参数搬移，不改语义；每个新仓储方法配一条 SQLite 夹具测试。
- `read_raw_table` 退役后不得再有任何“按表名读表”的公开函数。

### 4.4 schema 对账与生成协议

**方向**：G3 → D1；D1 → 运行期版本快进判定。
**形式**：pytest 合同 + 生成器 CLI。

```
起点：tests/migration_db/fixtures/schema-v4.sql（冻结，不再编辑）
路径 A：空库 ← schema.sql（ensure_schema 新库路径）
路径 B：空库 ← schema-v4.sql ← migrate v4→CURRENT_SCHEMA_VERSION
规范化结构 = 对每张表 PRAGMA table_info（name,type,notnull,dflt_value,pk）
           + PRAGMA index_list/index_info（含 unique、列序）
           + sqlite_master 中 type in (trigger, view) 的 sql（压空白、去 IF NOT EXISTS）
合同：结构(A) == 结构(B)，差异逐项列出（表/列/索引/触发器）
生成：python -m tools.generate_schema_sql [--check | --write]
      输出 = 路径 B 得到的库按 sqlite_master 顺序导出的 DDL + 固定头（PRAGMA foreign_keys、SchemaVersion 初始行）
      --check 与已提交 schema.sql 逐字节比较，不等退出 1
运行期：current_schema_contract_issues(conn) 改为“live 表列集合 ⊇ schema.sql 声明表列集合”，不再维护手写 needed 清单
```

**约束**：
- 新表只写一次：DDL 模块或迁移；`schema.sql` 由生成器产出后提交。
- 发现 A/B 不等时，修法方向固定为“补迁移让 B 追上 A”，不允许删 A 的表来凑齐。

### 4.5 子包规则

**方向**：P 各条 → 后续所有新代码。
**形式**：目录约定 + 适应度测试。

```
core/services/workbench/
├── __init__.py            只保留显式 import 的公开门面，禁止 __getattr__ 懒导出
├── facts/                 叶子：zero_duration*、preflight_checks、*_values、plan_fact_serialization 等；只依赖 core.models/data/core.infrastructure
├── plan/  run/  trial/  dashboard/  report/          排产结果侧，允许方向：facts ← plan ← run ← trial ← {dashboard, report}
├── process/  resource/  material/  batch/  calibration/  outsourcing/  system/  execution/   主数据与现场侧，允许方向：facts ← process ← resource ← batch；calibration ← template(并入 calibration)；其余只依赖 facts
└── commands.py  write_context 等跨簇协调件留在根
core/services/scheduler/
├── run/optimizer/graph/   46 个 optimizer_graph_* 迁入
├── gantt/  resource_dispatch/  calendar/   根目录业务族
└── batch 族迁出为 core/services/batch/
```

**约束**：
- 分包前先解掉五对双向依赖，方法只有三种：共享部分下沉到 `facts/`、合并成一个簇、显式接口注入。
- 不留兼容垫片；调用方（含测试）用 codemod 一次改完。`_frozen_import_anchor` 的静态清单随 scheduler 懒门面同步。
- 现有目录环门禁（`tools/scan_import_cycles.py`）在分包后自动覆盖簇间环，基线按“只减不增”刷新。

### 4.6 门禁回执耗时字段

**方向**：`scripts/run_quality_gate.py` → `tools/long_gate_manifest.py` → 汇总输出。

```
command_receipts[i] 新增：
  started_at: ISO8601 本地时间
  finished_at: ISO8601 本地时间
  duration_seconds: float（perf_counter 差值，保留 3 位）
print_long_gate_manifest 新增“耗时 Top 10”段，按 duration_seconds 降序
```

**约束**：字段只增不删，旧回执缺字段时视为 `duration_seconds=None`，不影响恢复匹配（命令身份仍按 `command_hash`）。

### 4.7 web 目录环消除接口

```
web/api_responses.py（web 根，只依赖 flask）：failure(...)、query_success(...) 由 web/routes/workbench/api_responses.py 迁入；
    路由层 api_responses 只留 api_endpoint / _domain_failure，41 个导入方直接改路径，不做 re-export
web/runtime_host.py（web 根）：RUNTIME_HOST_EXTENSION / RESTORE_HOST_EXTENSION / RESTORE_HOST_GUARD 键名、
    SystemRestoreHost 抽象契约、install_runtime_host(app, request_shutdown=...)、request_shutdown(app, logger)、restore_host(app)
app.extensions["aps.runtime_host"] = {"request_shutdown": Callable[[logger], bool]}   由 factory 在建 app 时写入
routes 只经 web.runtime_host 读 current_app.extensions，任何位置不 import web.bootstrap；
web/bootstrap 里只有 factory.py 可 import web.routes（装配蓝图）；web/*.py 根辅助模块不 import routes/bootstrap
根目录 config.py 迁入 web/bootstrap/app_config.py（BASE_DIR 向上两级），不留根目录垫片
```

## 5. 子 feature 清单

1. **sql-boundary-ratchet** — 服务层不写 SQL、仓储层不做裁决两条棘轮规则，含扫描器、基线、测试与门禁登记
   - 所属模块：G
   - 依赖：无
   - 状态：done（2026-09-20）
2. **private-import-ratchet** — 禁跨模块导入私有符号的棘轮规则
   - 所属模块：G
   - 依赖：无
   - 状态：done（2026-09-20）
3. **schema-parity-test** — 新库与 v4 起点迁移链的整库结构对账测试；发现差异按“补迁移”修
   - 所属模块：G
   - 依赖：无
   - 状态：done（2026-09-20）。实测两条路径结构完全一致，仅三张表列物理顺序不同，不比较
4. **gate-step-timing** — 门禁回执补分步耗时并在汇总里输出 Top 10
   - 所属模块：G
   - 依赖：无
   - 状态：dropped（2026-09-20）。机制已存在：回执已有 started_at/duration_s，`tools/long_gate_summary.py` 已有 Slow entries 排名；评估时看到的是 environment_blocked 的空回执运行
5. **errors-path-consolidation** — `core.infrastructure.errors` 旧路径一次性 codemod 到 `core.errors`，删垫片，加禁用规则
   - 所属模块：T
   - 依赖：无（先做，避免后续新文件继续用旧路径）
   - 状态：done（2026-09-20）
6. **sql-drain-writes** — 11 条写语句进主数据仓储
   - 所属模块：S
   - 依赖：sql-boundary-ratchet（基线存在才能退役条目）
   - 状态：done（2026-09-20）。实际 18 处（工艺工作流确认表另有 6 处），新增 WorkbenchProcessWorkflowRepository；写语句经仓储后 sqlite 错误统一翻译为 AppError 并保留 cause
7. **sql-drain-introspection** — PRAGMA、sqlite_master、快照连接、内存库 DDL 解析归 `core/infrastructure`
   - 所属模块：S
   - 依赖：sql-boundary-ratchet
   - 状态：done（2026-09-20）。三个基础设施模块 + 20 处调用点；sql_boundary 基线 297→242
8. **sql-drain-storage-classes** — 14 个持 `self.conn` 的仓储形类整体下沉为查询仓储，服务层留裁决薄壳
   - 所属模块：S
   - 依赖：sql-drain-writes、sql-drain-introspection（避免同文件并发改动）
   - 状态：done（2026-09-20）。14 个仓储形类改薄壳，SQL 原样进 data/repositories；与第 9 条合并为按业务簇的四批提交
9. **sql-drain-remaining-selects** — 余下自由函数 SELECT 按 run、plan、trial、process 簇归入仓储
   - 所属模块：S
   - 依赖：sql-drain-storage-classes
   - 状态：done（2026-09-20）。core+web 服务层 SQL 命中 332→0，基线收紧为空；新增仓储 24 个、扩方法 13 个，全部有合同测试并登记门禁
10. **sql-drain-hatch-and-policy** — 退役 `read_raw_table`，把 17 处仓储内裁决上提到服务层
    - 所属模块：S
    - 依赖：sql-drain-remaining-selects
    - 状态：done（2026-09-20）。data_policy 命中 0，基线收紧为空；仓储只返回事实，裁决上提到服务层策略模块，错误码/状态/文案逐字不变；残留 `workbench_plan_identity_repo` 的 `WorkbenchPlanReferenceError` 与 36 条上提文案的词表 allow 见 items.yaml
11. **workbench-cluster-layering** — 画 workbench 簇层次图，解五对双向依赖，共享件下沉 `facts/`
    - 所属模块：P
    - 依赖：private-import-ratchet、sql-drain-storage-classes
    - 状态：done（2026-09-20）。设计见 `workbench-cluster-layering.md`；`facts/` 落地 30 个模块，跨簇违规 31→0，适应度测试进门禁；搬迁工具 `tools/move_modules.py`
12. **workbench-subpackages** — 按簇分子包，一簇一提交，codemod 全部调用方
    - 所属模块：P
    - 依赖：workbench-cluster-layering、sql-drain-hatch-and-policy
    - 状态：done（2026-09-20）。14 簇全部进子包，根只剩 `commands.py`/`messages.py`；9 个提交、243 个模块、约 640 个调用方文件；适应度测试改按目录判簇
13. **scheduler-family-subpackages** — `run/optimizer/graph` 子包、根目录业务族分包、批次族迁出、删 4 个根垫片与 `analysis/`
    - 所属模块：P
    - 依赖：private-import-ratchet
    - 状态：done（2026-09-20）。四个提交：垫片退役+锚点搬家、run/optimizer(+graph)、gantt/resource_dispatch/calendar、batch 迁出；根垫片实际 7 个；细节见 items.yaml
14. **schema-sql-generated** — `schema.sql` 生成化与 `--check` 门禁；`current_schema_contract_issues` 改为派生比对
    - 所属模块：D
    - 依赖：schema-parity-test
    - 状态：done（2026-09-20）。生成器、声明结构解析、派生比对、参数贯通与死代码删除均落地；schema.sql 已由生成器重写
15. **web-dir-cycle-removal** — 三条边改向，消除唯一生产目录环
    - 所属模块：T
    - 依赖：无
    - 状态：done（2026-09-20）。实际硬环是 `.`⇄`web/bootstrap`（factory→根目录 config.py），config.py 搬入 `web/bootstrap/app_config.py`；三条 routes⇄bootstrap 延迟边按 §4.7 改向；生产环基线刷新为 0 目录环
16. **models-service-annotation-inversion** — `core/models/workbench_run_compute.py` 去掉对服务层的注解依赖
    - 所属模块：T
    - 依赖：无
    - 状态：done（2026-09-20）。改为模型层 Protocol，服务层结构满足
17. **request-service-rule-fold** — 并入 web helper 规则，删容器专用清单
    - 所属模块：T
    - 依赖：无
    - 状态：done（2026-09-20）。规则范围收成 `web/*.py`，容器专用清单与过滤删除
18. **boundary-policy-decisions** — 四条政策落 `cs-decide`
    - 所属模块：C
    - 依赖：schema-sql-generated、workbench-subpackages
    - 状态：done（2026-09-20）。四份决策文档：`2026-09-20-decision-schema-single-source-of-truth`、`-ratchet-gate-lifecycle`、`-service-subpackage-layering`、`-tests-at-seams`

**最小闭环**：第 1 条 `sql-boundary-ratchet` 做完后，任何新的服务层 SQL 或仓储内裁决在定向测试里立刻变红，止血生效。

## 6. 排期思路

先止血再排水：四条 G 门禁便宜、彼此独立，做完之后所有后续搬移都有“只减不增”的量化验收。errors 收口提前，是为了新建的仓储和基础设施文件一开始就用新路径。SQL 排水按风险排：写语句可损坏数据且丢失约束错误翻译；自省与快照连接不属于业务仓储；仓储形类占大头语句且几乎原样可搬；余下 SELECT 随簇处理。分包放在排水之后，因为 14 个仓储形类搬走后 workbench 先瘦一圈，分包时目录更清楚。schema 生成化放在对账测试之后，对账先证明两条路径等价，再把其中一条变成生成物。决策文档最后写，写已经落地的规则。

## 7. 观察项

- 背景里“`database_bootstrap` 有非空库缺表按 schema.sql 补齐的修补逻辑”需更正：`bootstrap_missing_tables_from_schema` 及 `database._bootstrap_missing_tables_from_schema` 在生产代码里没有调用方，只有 `tests/migration_db/test_database_migration_runner_delegation.py` 的委托测试引用；迁移器只用 `missing_schema_tables` 组装错误信息，不做静默修补。该死代码已在 schema-sql-generated 条目里删除（2026-09-20）。
- 背景里“门禁清单没有分步耗时记录”需更正：回执已有 `duration_s`，长门禁汇总已有 Slow entries；gate-step-timing 因此 drop。

- `.codestable/architecture/ARCHITECTURE.md` 与 `service-scheduler.md` 在分包落地后需要按 `cs-arch update` 刷新目录地图；本路线不改它们。
- `2026-06-29-module-architecture-health` 审计里“数据层收口 ✅”只核了 web 层，未核服务层；本路线 G1 落地后该审计结论应加注。
- 前端 `frontend/workbench/app` 分目录留待 aps-frontend-fusion 触碰构建脚本时一并处理。
- 测试往接缝收（工作台 493 个测试文件对 233 个模块）是长期政策，不是单条可完成的 feature，只在 C1 决策里写规则。

## 8. 变更日志

- 2026-09-20：new 模式创建。
- 2026-09-20：sql-boundary-ratchet、private-import-ratchet、schema-parity-test 完成；gate-step-timing 因机制已存在 drop；boundary-policy-decisions 依赖去掉 gate-step-timing；观察项补两条事实更正。
- 2026-09-20：S 模块（SQL 排水七批）、P 模块（工作台簇层次 + 14 簇分包、排产包四步分包）、D 模块（schema 生成化）、T 模块四条、C 模块四份决策全部完成；18 条子 feature 17 done / 1 dropped。

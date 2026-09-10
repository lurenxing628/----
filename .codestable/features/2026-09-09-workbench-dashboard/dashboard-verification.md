# CR 后端验证与交接

## 结论与边界

- 已实现真实风险读取、目录/详情/历史、原子处置/关闭/重开、永久来源与原值快照、幂等回执及 unknown 查询路径；DTO 与路由已向 CY 冻结交付。
- 验证范围是 CR 独占后端，不是整页移植、主线完整 factory、发布包或 Win7 真机验收。没有运行生产库、旧预览、stage、commit 或版本注册。
- 验证环境为 macOS、仓库 `.venv/bin/python` Python 3.8.10；记录时 HEAD 为 `de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`，工作区有大量既有及并行改动，本轮23个代码/测试文件均未跟踪。没有 clean-worktree proof。

## 最终结果

- 明确后端清单：**223 passed，24.93秒**。其中 Dashboard 9个测试文件共77项，其余146项是计划交期、执行旧事实、普通命令、资源占用和运行历史回归。没有使用通配符纳入 CY 在途测试。
- 原始 JUnit：`dashboard-tests.xml`，223个 testcase，0 failure、0 error。
- Ruff 定点检查：13个产品文件、9个测试文件和1个独占 support，`All checks passed!`。
- Pyright 1.1.406，`--pythonversion 3.8` 定点覆盖13个产品文件：`0 errors, 0 warnings`；没有升级提示中的新版本。
- 使用仓库 `tools.quality_gate_scan.scan_complexity_entries/scan_oversize_entries`：两项均为空；未增加复杂度/大小豁免。
- 真实临时文件SQLite：2000个当前计划工序，完整得到4002条风险，返回页100条，单次读取1.3802秒。10001个计划工序、超8MiB原值明确拒绝，不返回截断“成功”。该耗时不是p95或Win7容量认证。

## 关键证据

| 边界 | 测试/代码证据 |
| --- | --- |
| 正式身份、混合晚交/齐套/执行/停机、GET无业务写入 | `tests/workbench/test_dashboard_reads.py:11`，query_only连接及typed原表对照 |
| 失败最新正式不换旧版或候选、未知不算0、不创报警 | `tests/workbench/test_dashboard_reads.py:29`；`test_dashboard_candidates.py:11`实际worker产4候选但仍无正式 |
| closed只读、独立reason重开、旧完成时间/结果/凭据保留 | `tests/workbench/test_dashboard_commands.py:11` |
| 无变化不重复留史、同键重放与异载荷冲突 | `tests/workbench/test_dashboard_commands.py:33` |
| 真正两个文件库连接竞争、WAL、回滚、丢失提交应答查原回执 | `tests/workbench/test_dashboard_atomic.py:18`、`:45`、`:59` |
| 同号批次/停机替换不继承旧ref，原值类型变化使旧令牌失效 | `tests/workbench/test_dashboard_atomic.py:81`、`:96`、`:110` |
| 重启后原回执/ref保留，旧写令牌失效 | `tests/workbench/test_dashboard_atomic.py:148` |
| UPDATE/DELETE及recursive_triggers=OFF的REPLACE不抹证据 | `tests/workbench/test_dashboard_atomic.py`的永久历史与REPLACE参数化用例 |
| 旧完工仍complete，工时未知而非0，旧BLOB备注/时间永久保留 | `tests/workbench/test_dashboard_legacy.py:24` |
| 实际get_connection的日期/NULL/BLOB读取、详情及transition | `tests/workbench/test_dashboard_host_connection.py:19`；真实PARSE_DECLTYPES及PARSE_COLNAMES，两者均未禁用或换全局converter |
| schema未装GET/POST明确503、未写回执或自动建表 | `tests/workbench/test_dashboard_host_connection.py:62` |
| 真实version=28基础库，CO/Dashboard两种安装顺序、整笔回滚、完整性/外键检查、原表类型保留 | `tests/workbench/test_dashboard_schema.py:82`；JUnit中的base_schema_version=28 |

生产连接专项不是普通sqlite连接替身：测试直接调用 `core.infrastructure.database.get_connection`，Spy检查每次实际connect的两项detect_types标志，并通过DATE列和`[date]`列名探针确认转换确实启用。Dashboard原值读取用同一连接上的CASE表达式绕过读取转换，未改全局连接政策。GET/详情/POST都通过每请求生产连接，原业务字段按NULL/integer/real/text/BLOB类型和值比较；不据此声称完整main factory、所有DATE异常或Win7宿主均已验证。

## 冻结与注册

- DTO/路由/前端文件加载顺序见 `dashboard-handoff.md`。没有额外confirmed字段。已直接向CY任务同步；不等待CY收尾，也未修改CY专属文件。
- Dashboard DDL：21对象，`objects/contract_issues/install`；ASCII规范化objects SHA-256为 `623ec4c193f30535df5848acd335159471738924c5e0fc08a08629b796d03e03`。
- CO DDL仍为9对象，指纹 `ecdbd579d6518bdf6c6f281705816865cf9cd6cae52a546f3ae51bc0d14757c3` 未变；共30对象且无重名。主线可先注册Dashboard路由，未装DDL时503；v29安装及版本注册由主线实施，不修改冻结v28。
- 本轮23个源文件SHA-256在 `dashboard-source-sha256.txt`。这是CR文件快照，不覆盖全部共享依赖，更不替代整仓HEAD绑定证明。

## 承重实现

- `core/models/workbench_dashboard.py:45`：目录筛选与分页；`workbench_dashboard_input.py:24/:79`：严格输入、独立状态转换。
- `core/services/workbench/dashboard.py:73/:157`：统一读取、目录；`dashboard_facts.py`：当前正式计划和唯一执行投影；`dashboard_projection.py`：交期/齐套；`dashboard_execution.py`：执行偏差；`dashboard_downtime.py`：停机区间交集；`dashboard_catalogs.py`：现有资源压力与真实运行目录。
- `core/services/workbench/dashboard_commands.py:19`：原子guard/处置/历史/回执；不写基础计划、执行或供应商周期。
- `data/repositories/workbench_dashboard_source_repo.py`：有界同连接原值读取；`workbench_dashboard_repo.py:88/:109`：历史与追加写入。
- `core/infrastructure/workbench_dashboard_schema.py:9/:85`：对象声明与显式安装；`web/routes/workbench/dashboard.py:122`：主线可调用的注册hook。

## 复跑命令

在仓库根目录执行，不使用会扫到CY文件的通配符：

```bash
.venv/bin/python -m pytest -q \
  tests/workbench/test_dashboard_reads.py \
  tests/workbench/test_dashboard_commands.py \
  tests/workbench/test_dashboard_atomic.py \
  tests/workbench/test_dashboard_api.py \
  tests/workbench/test_dashboard_schema.py \
  tests/workbench/test_dashboard_legacy.py \
  tests/workbench/test_dashboard_capacity.py \
  tests/workbench/test_dashboard_candidates.py \
  tests/workbench/test_dashboard_host_connection.py \
  tests/workbench/test_plan_delivery.py \
  tests/workbench/test_execution_ledger_legacy.py \
  tests/workbench/test_commands.py \
  tests/workbench/test_plan_occupancy.py \
  tests/workbench/test_run_history_queries.py \
  -o junit_family=xunit1 \
  --junitxml=.codestable/features/2026-09-09-workbench-dashboard/dashboard-tests.xml
```

## 尚未验证

- 完整 `scripts/run_quality_gate.py` 未运行：dirty多人工作区，入口会写共享manifest并清理共享证明，含启动检查；不越过本轮独占边界。因此以上只是局部验证，不是clean/full gate证明。
- 主线路由联合注册、真实用户实例、CY浏览器交互、v29正式迁移/回退、最终打包和Win7真机仍归集成阶段。
- 实际外协发出/回厂仍为后续slice：external返回not_connected/null/disabled；没有改默认供应周期伪造回厂。凭据文字未冒充已核验附件。

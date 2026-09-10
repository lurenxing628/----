---
doc_type: fix-note
date: 2026-09-10
status: completed
tags: [workbench, outsourcing, round1, R1-F, pyright]
---

# R1-F 第一轮外协补漏

## 结论与范围

- 本轮指定四个产品文件的原始 15 项类型错误已消除；连同专属测试定点 Pyright 为 0 error / 0 warning。
- 最终本域定点回归 190 passed，Python 3.8.10；其中专属真实 factory 合同测试 21 passed。
- 只改指定四个产品文件，新增 `tests/workbench/test_round1_outsourcing_contract.py` 和本记录。同职责 helper 均留在原文件。
- 工作区入场已有大量 dirty，四个产品文件本来均是 untracked。本轮以独立 `/tmp` 副本对比改动，没有清理、覆盖、stage 或 commit。
- 唯一 staged `tests/gate_meta/test_frozen_bundle_contract.py` 未改，入场/收尾工作文件 SHA-256 均为 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`。收尾 index blob 为 `3a75549413489ac9de33181b6f490cbe3cd49730`。
- 本轮没有创建其他代理，没有操作生产 DB、前端、registry、全局配置、依赖、build 或预览服务。

## 原始证据

| 证据 | SHA-256 / 结论 |
| --- | --- |
| `output/workbench-migration/verification/point-main-20260910/stage-pyright.json` | `28d369da0fec3db24f1c8159dc1ae008ed5e1786ed26be8359991a53783ededd` |
| `output/workbench-migration/verification/round1-20260910/architecture-before.log` | `79837f1725886cd60d3a469fccdbe55303ebeffc46297f4fe18eab396dd66d72` |
| 原始类型分布 | input 3、commands 1、source repository 1、routes 10，共 15 |
| 原始架构日志 | 有 4 项全局失败；超复杂清单没有本写集，不改别域，不调整基线或阈值 |
| 原始四文件副本 | `/tmp/aps-r1f-outsourcing.YVAHsX/`，路由副本名为 `outsourcing_routes.py` |

已先读 `AGENTS.md`、`.codestable/attention.md`、`.codestable/reference/system-overview.md` 和项目 `cs-issue` 入口，按已授权局部修复执行。

产品编辑前用 `CHECKUP_CALLGRAPH=/tmp/aps-r1f-outsourcing.YVAHsX/callgraph python3 -m tools.symbol_locator` 查询 `next_values`、`factory_time`、`normalize_input`、`operation`、`_arguments`，并用 `rg` 核对当前源码。静态图不包含 tests，存在动态调用盲区；不冒称完整精确调用证明。工具只支持裸名，初次使用 `callers --at` / 限定类名失败后已改为裸名，并逐项核对输出所属文件。

## 根因与修改

| 文件与位置 | 根因与处理 |
| --- | --- |
| `core/models/workbench_outsourcing_input.py:17` | 间接调用未标注 NoReturn 的 reject 导致成功解析也被推断为 datetime 或 None。严格检查对象类型、秒级工厂本地时间格式及真实日期，失败直接抛相同 code/status 的业务拒绝；成功才返回 datetime，没有补 0、补时间或返回 null。 |
| `core/models/workbench_outsourcing_input.py:40` | 输入包含目标对象和文字，不是纯字符串字典。返回边界明确为 `Dict[str, object]`；继续逐字段真实验证，不使用 Any 或 cast。 |
| `core/models/workbench_outsourcing_input.py:58` | 提取事实字段校验；`next_values` 对合并后的完整 values 再校验，旧的非法 confirmedState 不能借稀疏更正被当作有效事实。 |
| `core/models/workbench_outsourcing_input.py:73` | 提取带明确 datetime/Optional[datetime] 参数的时间先后校验，保留未来实际时间拒绝和 returned/state 联动。normalize_input 复杂度 14→7，next_values 15→9。 |
| `core/services/workbench/outsourcing_commands.py:55` | 创建目标和已有登记引用分别经过实际校验，命令主体必须为有效文字永久引用，不能对混合值直接字符串下标或用空值兜底。实际本机操作人原 guard 保留。 |
| `data/repositories/workbench_outsourcing_source_repo.py:45` | 先明确拒绝缺失源工序/原始批次映射，再访问该行，保持 identity_missing/409 和原实例边界。 |
| `web/routes/workbench/outsourcing.py:30` | 页码和每页数量解析为整数；字符串筛选字典不再混入 int。未知/重复参数、缺少翻页快照、无效页码和范围仍拒绝。_arguments 复杂度 13→8。 |

四产品文件最终最大函数复杂度 11；专属测试最大 13，均不超过原门槛 15。没有迁移、台账消噪、全局 suppress、ignore、修改原测试或降低业务门槛。

## 事实与写表证明

专属测试通过真实 `create_app_core()`、实际注册的 route、实际 `get_connection()`，只使用 `db_env` 创建的私有临时库；不启动监听端口。每个请求核对 DB 文件路径、FK=1、声明 DATE 返回 `datetime.date`，请求结束后执行 SQL 必须报 closed database。

`FactoryCase.send` (`tests/workbench/test_round1_outsourcing_contract.py:53`) 在每个 HTTP 请求前后比较全部表的 storage type/value、DDL，结合 `total_changes` 验证。GET 和 preview 同时启用连接级 `query_only=ON`；写命令不启用此限制，避免用数据库写保护掩盖领域拒绝缺失。

| 操作 | 实际改变的精确表集合 |
| --- | --- |
| targets / receipts / detail / history / 命令回执查询 / preview | 空集合，total_changes=0 |
| 已提交同 key 重放 / 不同输入同 key 冲突 / 无效输入 / 无效实际操作人 | 空集合，total_changes=0；失败没有包装成成功 |
| 当前 schema 新登记 | `WorkbenchOutsourcingReceipts`、`WorkbenchOutsourcingMembers`、`WorkbenchOutsourcingFacts`、`WorkbenchCommandReceipts`、`WorkbenchDashboardExternalItems`，最后一表来自现有 v31 映射触发器 |
| 回厂登记 / 更正 / 同值重新确认 | `WorkbenchOutsourcingFacts`、`WorkbenchCommandReceipts` |
| 外协处置 close / reopen | `WorkbenchDashboardExternalStates`、`WorkbenchDashboardExternalHistory`、`WorkbenchCommandReceipts` |

- 专属 `:141` 参数化单工序与 merged；保留原完整成员数量 1/2、原工厂批数量 10 的 typed source_facts、原 header/member/首条 fact 全字段及原 command receipt 结果；更正仅追加，previous_fact_ref 链完整，清空 returned 必须同步状态，未提供时间保持原值，同值重新确认仍有新事实。
- 专属 `:181` 的真实 Dashboard close/reopen 验证：关闭处置后仍是 `in_transit` 且 returned=None；重开追加历史、原关闭历史保持不变，回厂登记与处置不同账。物流、Batches/BatchOperations、生产报工、OperationExecutionEvents 均不改。
- 专属 `:99` / `:105` / `:216` / `:235` 验证：日期对象、None/0/bool、错误日期、时区/小数秒、未来实际时间、逆序时间、returned/state 不匹配、空资源引用、无效分页、声明人/实际本机操作人缺失均不变成有效事实或成功写入。
- 专属 `:141` 验证真实连接关闭后另开连接，全库 storage 等价、FK 无问题；各次 HTTP 本身也逐请求独立开关真实连接。
- 旧 frozen v29 + 显式 DI extension 的现有回归与当前 schema factory 回归均通过。旧 fixture 未修改，其固定 DDL SHA 为 `d303a3b004546845c214d3907e1dc27c8c630132da2096feaaa15ed374333648`；没有把 current schema 改版本号冒充旧库。

## 命令与结果

所有命令在 `/Users/lurenxing/GitHub/----` 执行，解释器为 `.venv/bin/python`，版本 3.8.10。`.venv/bin/pyright` / `radon` 脚本 shebang 仍指向旧 Documents checkout，直接调用报 127；本轮改用 `python -m` 成功运行，未改环境或安装依赖。

```bash
.venv/bin/python -m pyright core/models/workbench_outsourcing_input.py core/services/workbench/outsourcing_commands.py data/repositories/workbench_outsourcing_source_repo.py web/routes/workbench/outsourcing.py tests/workbench/test_round1_outsourcing_contract.py --outputjson
.venv/bin/python -m ruff check core/models/workbench_outsourcing_input.py core/services/workbench/outsourcing_commands.py data/repositories/workbench_outsourcing_source_repo.py web/routes/workbench/outsourcing.py tests/workbench/test_round1_outsourcing_contract.py
.venv/bin/python -m radon cc -s -j core/models/workbench_outsourcing_input.py core/services/workbench/outsourcing_commands.py data/repositories/workbench_outsourcing_source_repo.py web/routes/workbench/outsourcing.py tests/workbench/test_round1_outsourcing_contract.py
.venv/bin/python -m pytest tests/workbench/test_round1_outsourcing_contract.py tests/workbench/test_outsourcing_facts.py tests/workbench/test_outsourcing_atomic.py tests/workbench/test_outsourcing_api.py tests/workbench/test_outsourcing_identity.py tests/workbench/test_outsourcing_targets_labels.py tests/workbench/test_outsourcing_schema.py tests/workbench/test_outsourcing_identity_migration.py tests/workbench/test_dashboard_external_reads.py tests/workbench/test_dashboard_external_handling_api.py tests/workbench/test_dashboard_external_handling_commands.py tests/workbench/test_dashboard_external_handling_atomic.py -q -o cache_dir=/tmp/aps-r1f-outsourcing.YVAHsX/pytest-cache --basetemp=/tmp/aps-r1f-outsourcing.YVAHsX/final-tests --junitxml=/tmp/aps-r1f-outsourcing.YVAHsX/final.xml
```

| 检查 | 真实结果 / 产物 |
| --- | --- |
| Pyright 1.1.406 | 五文件 0 error / 0 warning，`/tmp/aps-r1f-outsourcing.YVAHsX/pyright-final.json` |
| Ruff | All checks passed |
| Radon | 本写集和专属测试均 <=15，`/tmp/aps-r1f-outsourcing.YVAHsX/complexity-final.json` |
| 首批 5 个现有外协测试文件 | 104 passed in 21.01s，`existing.xml` |
| 专属测试 | 21 passed in 12.13s，`contract-v3.xml` |
| 最终 12 个本域/相邻文件 | 190 passed in 82.67s，`final.xml` |

上述 XML 均位于 `/tmp/aps-r1f-outsourcing.YVAHsX/`。初版专属测试失败也保留：`contract-initial.xml` / `contract-v2.xml`。初版误把 SQLite `pragma_table_info()` 准备阶段对 sqlite_master 的授权回调当成实际写入，最小 `:memory:` 实验在 `query_only=ON` 下重现相同回调且 actual_changes=0 / DDL 不变，因此改用真实写保护、total_changes 和全库逐表对比，不豁免业务表。另修正测试自身对已存在的平铺回执响应和 size=1 分页的错误预期，未改产品接口或删断言。

## 最终源绑定

| 路径 | 入场 SHA-256 | 完成 SHA-256 |
| --- | --- | --- |
| `core/models/workbench_outsourcing_input.py` | `821b77e24fe34d47e65a0d5a234a273075c59fe73ddd82c0ef8aeda0430017bf` | `b6c3f496e288865ebcb892d24793cbc0808a66ca01da0076828484cfb4f928b2` |
| `core/services/workbench/outsourcing_commands.py` | `52b5354975619deeea620224c91a1f5ec3f04dc92ad41c849daa64aa4185bcc8` | `56fad4469ef9086dfb5bcccde9d1eea92b79ef22cb08f8d86f22c1661fed966e` |
| `data/repositories/workbench_outsourcing_source_repo.py` | `843c0013d27c0cf25ccedd42d7c5e9c68a05e119dcb21d21383eac24d7c77a32` | `cdbf65bfeafa4ec1996ecf88ac944fa09c35f9ca0e8a6303a1aa59a6236ccbee` |
| `web/routes/workbench/outsourcing.py` | `ed9d819681cd8045bb02c1a0e5347561356f95233ab8dd2456996940d65430a5` | `41f4ea77a97e3dc8454f2f2a790f330ec5c4a2834856fe8b603171e0cf4814ad` |
| `tests/workbench/test_round1_outsourcing_contract.py` | 本轮新增 | `a10ac7e701200e21cc85d3eecda5d4f130bf9d5bb200268ca70f698a6eb51805` |

## 未做与移交

- 本轮 R1-F 的授权补漏已完成并停止。四个产品文件、专属测试和本记录均未 stage/commit；其他代理的 dirty 原样保留。
- 主线已分别收到类型+原回归闭环，以及真实 factory 专属闭环 handoff；最终 190 项结果及本记录继续移交主线统一收口。
- 未运行全局质量门禁、全站验收、5000 压测、Win7 实机或发布、旧 UI 下线；本轮不具有这些方面的验证证据。
- 没有新增测试 registry 登记，遵守本轮禁止触碰 registry 的范围；后续是否统一登记由主线决定。
- 收尾 HEAD 为 `de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`，但大量 dirty 仍在。以上只是实际当前源哈希绑定的本域局部证据，不是 HEAD / clean-worktree proof，不证明全仓类型或架构门禁通过。

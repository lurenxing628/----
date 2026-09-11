---
doc_type: issue-fix
issue: 2026-09-08-critical-chain-cache-content
path: fast-track
fix_date: 2026-09-08
tags: [D03, gantt, critical-chain, cache, snapshot]
---

# D03 关键链缓存内容身份修复

## 1. 结论与范围

碰撞及必需的旧测试集成已完成：影响面 **318 项全部通过**，首次阶段的 314 passed / 4 failed 已收拢；6 类运行时 mutation 全部被测试检出。最新门禁快速预检通过，完整门禁未执行；本记录不是 clean-worktree proof。首次阶段证据保留在第 4 节，本次集成结果见第 7 节。

本问题按明确授权单线程实施，没有启动代理，没有提交，没有打开业务真实数据库。保留原有大量 dirty；累计人工编辑下列 9 个文件，不改业务仓储、前端、启动打包或共享台账。本次追加授权只修改两个旧测试文件及本记录，不修改 A18 公开投影文件；shared support 仅只读复用，具体路径已在实施前告知。

| 文件 | 本轮动作 |
| --- | --- |
| `core/services/scheduler/gantt_critical_chain_provider.py` | 在已有 dirty 上修复读数、缓存键和回填时序，保留 LRU、锁、结果副本和错误码合同 |
| `core/services/scheduler/gantt_critical_chain_snapshot.py` | 新增专属明细快照与内容指纹 helper |
| `tests/gantt/test_gantt_critical_chain_cache_fingerprint.py` | 将原未跟踪测试升级为真实内容碰撞回归，保留稳定命中、失效、指纹失败绕过和容量合同 |
| `tests/gantt/gantt_critical_chain_cache_support.py` | 新增专属临时 SQLite 造数与直接计算对照 |
| `tests/gantt/test_gantt_critical_chain_cache_snapshot.py` | 新增来源边界、错误、单次读数、缓存生命周期及并发覆盖 |
| `tests/gantt/test_gantt_critical_chain_cache_transactions.py` | 新增事务、并发读写、恢复与同路径重连覆盖 |
| `tests/gantt/test_gantt_critical_chain_provider.py` | 追加授权：补 adopted 明细接口，以真实计算器 spy 区分读取与重算，强化来源/数据库隔离和数据 mutation |
| `tests/gantt/test_gantt_critical_chain_cache_thread_safe.py` | 追加授权：保留 OrderedDict 并发探针，改为真实临时 SQLite 每线程连接，验证读取/重算计数及同聚合值 mutation |
| 本文件 | 修复及实际验证记录 |

启动已读取 AGENTS、attention、system-overview、项目版 cs-issue-fix，并搜索 compound。已执行 symbol_locator 的 `whereis get_critical_chain`、`callers get_critical_chain`、`callees get_critical_chain`；调用方静态结果有 ambiguous 边，补读 `gantt_service.py:353`。首次查类名不受定位工具支持，且 callers/callees 不接受 `--at`，随后按受支持命令重跑，没有把失败查询当成定位成功。

## 2. 根因与修改前证据

修改前 provider 的三条 SQL 只有 `COUNT(*) / MAX(id) / MAX(created_at)`。这些是行集统计量，不是内容身份：同秒重写机器、人员、工序或起止时间可以全部保持不变；BatchOperations、Batches 等 JOIN 数据变化也完全不在这三项统计量内。

同时，先查指纹、后重新查询计算行，会给两次 SQL 留出读到不同状态的窗口。

修改前现场源码 SHA-256：

```text
01230caff00035a2b34be49fa8e30e19a414a4e1edc6e9dc3e8c50b6df6792ae
```

已将该份原始 dirty 源码在内存中加载为临时模块，使用真实 `schema.sql`、仓储和计算器复跑；没有切换工作区文件或修改真实库。三种来源均得到相同证据：

| 来源 | 恢复前 | snapshot 恢复后同秒同 count/id 重写 | 旧缓存返回 | 实际直接计算 |
| --- | --- | --- | --- | --- |
| adopted / schedule | `[A, B]` | B 改为 M2，全部旧聚合值相同 | `[A, B]`, cache_hit=true | `[B]` |
| candidate_rows | `[A, B]` | 同上 | `[A, B]`, cache_hit=true | `[B]` |
| adjustment_scenario_rows | `[A, B]` | 同上 | `[A, B]`, cache_hit=true | `[B]` |

查阅 schema、排程仓储、恢复路径及 scheduler 内 revision 引用后，未找到覆盖全部关键链输入、且恢复后可靠的统一 revision。现有 execution revision 面向执行反馈/快照，不覆盖任意排程改写、工序/批次标签修改，不能替代这里的内容身份。没有新增 TTL、聚合统计字段或依赖恢复通知的失效补丁。

## 3. 修复合同

1. Provider 先按已解析的来源读取完整明细。adopted/schedule 仍调用 `ScheduleRepository.list_by_version_with_details`；其他来源仍调用 `list_plan_detail_rows_all_for_resolution`，不重新选择当前代表方案。见 provider 的 `_load_plan_rows_snapshot`。
2. 生产侧这两个 loader 都以一条完整 SQL 读取明细和 JOIN，分别复用 `schedule_repo.py:84`、`schedule_plan_query_repo.py:348`、`schedule_detail_query.py:100` 的现有查询，不另抄 SQL/字段/筛选条件。
3. `CriticalChainSnapshot.fingerprint` 对返回的全部列逐行做确定性 JSON 编码与 SHA-256。列名排序，行序保留，换行使用 JSON 转义并分隔记录；NULL、数字、字符串不混为一谈。保留行序是因为重复 task ID 的后行会覆盖前行。缓存键继续隔离数据库、version、role、source_table、candidate_id、scenario_id。
4. 缓存未命中时，直接使用同一批已加载的行计算，不再读库。adopted 通过只返回这些行的专属快照适配已有 `compute_critical_chain`，保留 `calc_exception` 语义；candidate/scenario 使用现有 rows 计算器。
5. 不主动 BEGIN、COMMIT、ROLLBACK 或 SAVEPOINT，不接管外层事务。调用方已有读事务时，响应遵守该事务可见快照；未提交写入可以生成对应内容缓存，但其他连接仍按自身可见内容寻址，回滚后不命中错误状态。
6. 读取失败返回明确 unavailable/reason_code，不读写成功缓存；包括仓储翻译后的 AppError。内容不能编码时记录 warning 并绕过缓存，仍仅计算已读快照，不用旧指纹或统计量兜底。计算不可用继续不缓存。
7. clear_cache 的 epoch 在读数开始前捕获，使清理期间正在加载或计算的请求不能重新填回已清空的缓存。LRU 及结果副本继续在原锁保护下操作。

## 4. 实跑验证

实际运行环境：macOS arm64，仓库 `.venv/bin/python` 为 **Python 3.8.10**，SQLite **3.35.5**。专属测试只使用 `:memory:` 或 pytest `tmp_path`，使用真实 schema/查询/关键链计算。测试关闭 master-data FK 造数，保留排程唯一约束；不是主数据 FK 完整性测试。

### 修改前基线

```bash
.venv/bin/python -m pytest -q tests/gantt/test_gantt_critical_chain_cache_fingerprint.py tests/gantt/test_gantt_critical_chain_provider.py tests/gantt/test_gantt_critical_chain_cache_thread_safe.py tests/gantt/test_gantt_critical_chain_unavailable.py
```

结果：**26 passed in 0.57s**。原用例没有检测同秒聚合碰撞，不能作为 D03 已修复证明。

### 修复后专属回归

```bash
.venv/bin/python -m pytest -q tests/gantt/test_gantt_critical_chain_cache_fingerprint.py tests/gantt/test_gantt_critical_chain_cache_snapshot.py tests/gantt/test_gantt_critical_chain_cache_transactions.py
```

最终结果：**90 passed in 1.15s**。

覆盖三种来源的真实 backup/restore、同秒同 AUTOINCREMENT 序列重写、机器/人员/时间/工序变动、JOIN 工序字段及 fallback 标签、工艺/人员边、坏时间丢弃统计、scenario status/base_version 谓词、角色/来源/候选/scenario/数据库隔离、无关计划不失效、错误不缓存、稳定命中、LRU、结果隔离和并发。

事务回归包括未提交写入不污染另一连接、SAVEPOINT 与全事务回滚、外层 WAL 读事务、指纹后写入（冷/热缓存）、fetchall 中途写入并修改 JOIN 数据、恢复同文件路径并重连、错误路径保留调用方事务，以及 clear_cache 发生在 load/compute 两个阶段。

### 首次阶段扩大回归与历史未通过项

```bash
.venv/bin/python -m pytest -q tests/gantt tests/gate_meta/test_test_support_dependency_boundary.py --tb=short
```

首次阶段结果：**314 passed, 4 failed in 23.50s**，现已由第 7 节的 318 passed 替代。此前一次完整 Gantt 运行（补入最后 6 个事务测试之前）为 305 passed, 4 failed。以下历史失败是必要的读数合同变化暴露出的旧测试不兼容，不伪称为修改前已有失败：

| 原测试位置 | 失败原因 | 授权范围内替代覆盖 |
| --- | --- | --- |
| `test_gantt_critical_chain_cache_thread_safe.py:157` | DummyConn 只支持聚合 SQL，不支持真正明细读取；新实现正确返回 repo_exception，不能用这种桩证明二次命中 | 新 snapshot 测试的真实每线程连接并发测试、LRU 与单次查询/命中测试 |
| `test_gantt_critical_chain_provider.py:104` | DummyScheduleRepo 没有明细方法，而且断言旧计算入口收到原仓储对象；新实现必须先物化真实明细 | 新 snapshot 测试的 adopted 单次查询/只计算一次、fingerprint 真实恢复测试 |
| `test_gantt_critical_chain_provider.py:334` | 两次同内容调用仍断言明细只查询一次；与每次验证内容的要求冲突 | 新 snapshot 测试的来源隔离与两请求两查询一次计算 |
| `test_gantt_critical_chain_provider.py:373` | 同上，数据库隔离的返回值及命中断言已通过，最后查询次数断言失败 | 新 snapshot 测试的真实数据库隔离 |

首次阶段这两个当时范围外的测试文件以及 `test_gantt_critical_chain_unavailable.py` 已以启动时 SHA-256 核对，内容未变。随后用户明确授权扩写上述两个旧测试文件，第 7 节记录实际集成；没有为了让旧桩通过而增加不读真实明细的后门或重新信任聚合值。

### 首次阶段静态及门禁

- 对本轮 6 个 Python 文件运行 `python -m ruff check`：通过。
- 对 provider/helper 运行 `python -m pyright`：0 errors, 0 warnings。
- 对本轮 6 个 Python 文件运行 `tools/scan_py38plus_syntax.py --fail-on-hit`：6 文件，读取失败 0，语法/注解风险 0。
- `python -m radon cc -s`：provider 最大复杂度 12，helper 方法最大复杂度 2；低于项目阈值 15。provider 230 行、helper 27 行，低于文件阈值 500。
- `git diff --check` 对本轮已有路径通过。
- 首次阶段运行 `scripts/run_quality_gate.py --fast-precheck`：exit 1，有 8 个范围外错误，涉及 optimizer-candidate-efficiency/benchmark_evidence.py、sgs-probe-reuse/measure.py、paired_measure.py、optimizer_quality_matrix_cases.py、optimizer_quality_matrix_compare.py 的 I001/B007/UP032，未修改这些文件。本次集成重跑已通过，不能继续把这 8 项作为当前失败。
- 完整质量门禁未执行：工作区 dirty 且并发其他修改仍在变化，快速预检和上述旧桩已有明确阻塞；不生成整仓或 clean proof，不刷新共享台账/基线。

## 5. 成本实测

没有假装缓存命中仍是廉价 COUNT 查询。现在每个请求都加载本方案完整 JOIN 明细并计算内容摘要，只省关键链节点、前驱关系、排序和回溯计算。

实测为上述 Python 3.8.10 / SQLite 3.35.5 / macOS arm64 的临时内存库，使用 schema.sql 和真实 loader。分别生成 1,000 / 10,000 道工序，同机器、相邻 5 分钟时段；每项独立运行 5 次取中位数。数据已预热，结果不是 Win7 或真实磁盘上的性能承诺。

| 来源 | 行数 | 明细查询 ms | 指纹 ms | 纯链计算 ms | 命中整次请求 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| schedule | 1,000 | 4.124 | 3.696 | 11.706 | 8.443 |
| schedule | 10,000 | 43.584 | 38.194 | 119.558 | 89.119 |
| candidate_rows | 1,000 | 4.130 | 3.660 | 11.444 | 8.525 |
| candidate_rows | 10,000 | 43.448 | 38.505 | 126.564 | 99.402 |
| adjustment_scenario_rows | 1,000 | 3.964 | 3.734 | 11.411 | 8.492 |
| adjustment_scenario_rows | 10,000 | 41.852 | 38.398 | 119.235 | 87.824 |

指纹时间随完整明细的编码字节数线性增长；行物化临时内存随明细大小增长，JSON 按行编码，不额外构建整表 JSON 字符串。查询仍承担既有 JOIN/ORDER BY 成本。类级 LRU 只保存摘要键和计算结果，不保留完整快照；上限仍是 64 项。

## 6. 剩余限制与交付状态

- 要求的碰撞场景及事务/恢复边界已有实测，追加授权的 4 项旧测试集成已完成；影响面全部通过，不等于全仓通过。
- SHA-256 是内容摘要，不宣称数学上绝无哈希碰撞。对非 JSON 可编码的异常注入值采用显式日志和不缓存策略；没有采用 `default=str` 混淆类型。
- 对本算法未使用、但查询返回的其他明细列也做指纹，可能多算一次；这保证不漏已有/新增返回字段，不承诺最小失效集合。
- 返回值对应本次读取可见的完整快照，不承诺响应发送时包含随后提交的数据。外层长读事务会继续看到其旧快照；结束事务后才看到新提交。
- 未在 Win7 实机或用户真实数据量上测试；没有改动运行时、依赖、schema 或仓储契约。
- 全部本问题修改未提交。暂存 diff 与启动时相同；全仓期间另有多处内容变化，未回滚/清理，不声称全工作区只有本问题 9 个文件变化。

## 7. 追加授权的必需集成（2026-09-08）

### 具体修改

仅修改 `tests/gantt/test_gantt_critical_chain_provider.py`、`tests/gantt/test_gantt_critical_chain_cache_thread_safe.py` 和本记录。原有其他测试及产品修改均保留。

- adopted 桩新增 `list_by_version_with_details`，返回可被真实关键链计算器处理的 A/B 明细并记录 version。计算器只用 `Mock(wraps=...)` 计数，不再伪造结果。冷读/命中各读一次但只计算一次，改变 B 的 machine 后结果由 `[A, B]` 变为 `[B]`，下一次稳定命中且不重算；初次快照不被后续源行 mutation 污染，并仍禁止走 plan query 选源。
- source_table/数据库分桶测试以**完全相同的明细内容**开始，要求两个 scope 各自首次 miss、分别计算，防止内容不同的指纹意外遮住分桶键缺失。随后只改变一份数据，验证该 scope miss/重算，另一份仍 hit 且结果未变。每阶段同时检查 query 参数序列、结果、cache_hit 和真实计算器调用次数，不是只把旧次数加一。
- 并发测试保留 `ConcurrencyProbeOrderedDict` 对 get/move/set/pop/len 的重叠探针和 10 线程 × 80 请求。移除仅支持聚合的 DummyConn，改为 pytest 临时文件库、每线程独立连接、真实 `ScheduleRepository` 和计算器；用 SQLite trace 计数实际明细 SELECT。并发阶段精确读取 800 次，不锁定允许重复计算的并发数量。串行校验阶段精确断言 4 次请求对应 4 次读取/2 次计算，覆盖命中副本 mutation 和同 COUNT/MAX(id)/MAX(created_at) 的机器变更。
- 已事先告知只读复用 `/Users/lurenxing/GitHub/----/tests/gantt/gantt_critical_chain_cache_support.py`；未改该 helper，也未修改 `tests/_support/`。

### 实跑结果

实施前重新运行两个旧文件：**10 passed, 4 failed in 0.40s**，确认失败仍是原四项。实施后同命令：**14 passed in 0.60s**。

```bash
.venv/bin/python -m pytest -q tests/gantt tests/gate_meta/test_test_support_dependency_boundary.py --tb=short
```

结果：**318 passed in 23.37s**。保持原用例集合，不删测试、不加 skip/xfail，也没有减少影响面。

- 两个修改测试文件的 Ruff：通过。
- 两个文件的 Python 3.8 语法/注解风险扫描：2 文件、0 风险。
- `git diff --check`：通过。
- `.venv/bin/python scripts/run_quality_gate.py --fast-precheck`：**exit 0，通过**；仍只是快速静态预检，不能当完整门禁。

### Mutation 证据

每类 mutant 在独立 Python 子进程里运行时替换 provider 方法，再用 pytest 执行指定原用例；没有修改/替换产品源码文件，进程结束即丢弃。正常代码已经全部通过，以下各项均以**断言失败、退出码 1**检出，非 collection/import 错误。

| mutant | 注入方式 | 检出用例 | 结果 |
| --- | --- | --- | --- |
| constant_fingerprint | `_plan_rows_fingerprint` 固定返回 constant | 本次修复的全部 4 项原测试 | 4/4 失败，0.59s |
| drop_source_key | 从 `_critical_chain_cache_key` 返回 tuple 删去 source_table 项 | source_tables_separate | 1/1 失败，0.39s |
| drop_database_scope | `_database_scope` 固定返回 one-database | database_scopes_separate | 1/1 失败，0.39s |
| always_recompute | `_lookup_cached_critical_chain` 总返回无命中，让 store 仍可复用缓存但多做计算 | 本次修复的全部 4 项原测试 | 4/4 失败，0.60s |
| reuse_old_rows_without_read | `_load_plan_rows_snapshot` 缓住首次快照，后续不读取 | adopted_critical_chain_uses_schedule_repo | 1/1 失败，0.39s |
| unlocked_lookup | lookup 执行相同 get/move/copy，但移除锁 | cache_thread_safe | 1/1 失败，0.56s |

汇总：**6/6 mutants 检出，12/12 mutant/测试组合按预期失败**。同时保留首次阶段 90 项真实数据、恢复及事务回归，不用 mutation 替代正常验证。

### 并发其他工作与证明边界

本次 318 项影响面运行未出现需要单列的并发其他失败；快速预检也已通过。首次阶段那 8 个范围外静态错误本次未再出现，未将其他工作修复归功于 D03。没有额外扫描或修改主线程 A18 公开投影。

完整质量门禁未执行：当前仍是大量 dirty 且其他任务持续修改的现场，本次授权收口 D03 影响面，不做整仓冻结/全量归属证明，也不触碰共享台账和门禁基线。Win7 实机与整仓 clean proof 仍不在此次验证结果内。

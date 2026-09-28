# Win7 压力验收：SQLite 锁竞争引发重放失败和排产执行器停用

> 历史记录归档（2026-09-27）：本文保留初始调查、验收失败及当时的判断；正文中的“未修复”“未提交”“尚未安装”等描述均为记录时的状态。后续修复已提交于 `0b9a682f` 至 `d1307cb8`，原 Win7 的安装、复验和交付结果以[最终验收记录](2026-09-26-win7-fixes-acceptance.md)为准。打包验收脚本及两份专测已包含在 `0b9a682f` 中。本文原存于 `codestable/`，现归档至 `.codestable/`；引用的本机日志、数据库和截图不随 Git 上传。

状态：验收发现，未修复。记录日期：2026-09-26。源码版本：`4df78c5330f8c0cb819ecf5a8678dc46b1340e58`。本记录不修改产品、测试、数据库或 SQLite 配置。

实际 Win7 SP1 x64（4 个逻辑 CPU、8 GiB 内存，无 Python）运行该版本的冻结程序。在 100 批次、1000 工序、4 路混合读取并行排产场景下，原请求受理成功，第一次相同 `request_key` 重放成功，第二次重放耗时 5781 ms 后返回 HTTP 500 / `storage_failure`。首次压力采集在 23.531 秒时停止，共 58 个请求、1 个错误，未完成计划中的 300 秒与 3 轮，因此该轮验收结果为失败。

- 接口：`POST /api/workbench/v1/scheduling/runs`
- `request_key`：`win7stress-8721e4aa350344638231cd45c5ac72a7`
- `request_ref`：`b953023825a44ffa9e4f2722966fdbeb`
- `run_ref`：`f795440dc38fc525c9a49a32515bbeb4a23da293efc4264e`
- [HTTP 汇总](../../evidence/Win7Acceptance/20260926/stress/level-1000-run01/http/summary.json)、[逐次请求](../../evidence/Win7Acceptance/20260926/stress/level-1000-run01/http/requests.jsonl)、[启动参数与边界](../../evidence/Win7Acceptance/20260926/stress/level-1000-run01/invocation.json)。

## 已确认的失败点与范围

[来宾错误日志](C:/Users/lurenxing/AppData/Local/Temp/aps-win7-acceptance-20260926/target-pressure1000-storage-failure/aps_error.log) 的 `2026-09-26 16:17:34` 调用栈为：`WorkbenchCommandService.execute` 退出事务 → `_transaction_scope` → `_commit_scope` → `_commit_outer_transaction` 的 `conn.commit()` → `sqlite3.OperationalError: database is locked`。随后被转换成 `WorkbenchCommandUncertain`，接口返回“提交结果不确定”和原请求查询入口。失败点是这次重放的 COMMIT；没有证据表明失败发生在 BEGIN、排产计算或 worker 候选结果落盘。

只读检查正常退出后导出的数据库，`PRAGMA journal_mode` 为 `delete`。生产 [get_connection](../../core/infrastructure/database.py) 第 92–97 行未覆盖连接超时；同版本 Python 3.8 连接默认 `busy_timeout` 为 5000 ms，与本次约 5.8 秒失败相符。[命令服务](../../core/services/workbench/commands.py) 第 49–57 行对已有回执重放仍启动 `BEGIN IMMEDIATE`，读取并校验回执后仍提交该写事务；[事务管理](../../core/infrastructure/transaction.py) 第 152–162 行在 COMMIT 失败后回滚并重新抛出，日志未显示二次回滚失败。

同一时间窗的 [来宾应用日志](C:/Users/lurenxing/AppData/Local/Temp/aps-win7-acceptance-20260926/target-pressure1000-storage-failure/aps.log) 记录批次 GET 耗时约 4.7–6.2 秒、首页 GET 约 7.66 秒。批次 [read_snapshot](../../core/services/workbench/batch/facts.py) 第 40–47 行让读事务覆盖指纹计算、页面投影和授权上下文；[列表路由](../../web/routes/workbench/batches.py) 第 47–54 行和 [查询投影](../../core/services/workbench/batch/queries.py) 第 28–55 行在切分页之前投影全部匹配批次。这提供了长读事务的代码路径证据，但现有日志没有逐连接 SQL 跟踪，无法指定究竟哪条读连接持有本次阻塞锁。

SQLite 官方说明 `BEGIN IMMEDIATE` 立即开启写事务，其他连接持有读事务时 COMMIT 可能返回 `SQLITE_BUSY`；与实际栈和 DELETE 日志模式一致。[SQLite 事务说明](https://www.sqlite.org/lang_transaction.html)。据此将其归为产品并发可用性缺陷，不能用宿主 CPU 未满或排产最终完成把 500 视作通过，也不能归因于 VMware 网络转发。

## 数据完整性与用户影响

原任务在 `16:17:27` 受理，`16:17:28` 开始，`16:17:45` 完成。采集器保留原 key，以只读查询恢复核对，未更换 key 重提。正常退出命令返回 0，用时 2445 ms。导出数据库 SHA256：`6FDE3AA611A55CA6CB860841FD0AA04F1866C0BE7B9FBCB467262E062799AEAE`。

[离线核对](../../evidence/Win7Acceptance/20260926/stress/level-1000-run01/offline-diagnostic.json) 通过：原 key 唯一作业/受理回执，4 个候选各 1000 工序，工序先后及资源无重叠，71 张业务表基线不变，`integrity_check=ok`，外键检查为空。状态为 `complete/finished`，候选总计 4000 行。未发现本轮重复排产或业务数据损坏；这仅证明原任务可恢复核实，不证明失败的重放成功。

用户在重复确认或网络不确定后的同 key 重放时，可能看到“结果不确定”，需要按原请求查询结果。批次及首页读取也会明显变慢。该缺陷会降低高负载下的响应可靠性；现有一次样本不能推导长期错误率或容量上限。

## 安全续测与修复建议

保留本轮失败报告、日志和数据库快照。由原任务负责人同库重启，先按原 key/run_ref 只读核对，再开始独立续测报告；后续维持约定并发和时长，所有 500 继续计作失败。提交结果不确定时仅查询原 key，只有已核实终态及候选后才可开始新的业务意图；存在未决任务时停止新写入。不得通过现场切换 WAL、延长超时、删锁、清空数据库或把 500 改为成功来掩盖本次结果。续测和后续 5000 工序验收由总报告记录，本问题不预先宣告其结果。

建议先修复 [WorkbenchCommandService.execute](../../core/services/workbench/commands.py)：在无外层事务前提下，对不可变的已提交回执增加短只读重放路径，仍校验 `action/context_ref/input_hash`；查不到时结束只读事务，再进入 `BEGIN IMMEDIATE`，在持有写锁的事务内再次查询并执行现有 guard/mutate。不能删除事务内的二次查重，不能放宽同 key 内容冲突，也不能遇到 COMMIT 错误就重做业务写入。已有回执 [仓库定义](../../data/repositories/workbench_command_repo.py) 明确为不可变，与业务变化原子保存。

另应缩短批次列表读事务：在一致快照内一次读取所需事实，之后以完整内存事实完成纯计算、指纹和页面投影；任何仍需读库的步骤都必须先纳入快照，防止用缩短锁的方式引入跨版本数据。只延长 busy timeout 不能解决不必要的写锁或长读事务。

修复需补定向回归：DELETE 模式下，另一连接持续持有读事务时，既有回执同 key 重放应成功且不新增作业/回执；同 key 不同内容仍拒绝；并发首次提交仍只产生一个结果；COMMIT 真正不确定时继续保持原 key 查询恢复契约。现有 [12 路首次同意图并发测试](../../tests/workbench/test_run_jobs_concurrency.py) 和 [原子失败测试](../../tests/workbench/test_run_jobs_atomic.py) 应继续保留。最后必须重新构建冻结包并复验真实 Win7 压力场景。本次仅定位与记录，未实施修复。

## 追加证据：1000 工序完整观察再次复现

[独立续测报告](../../evidence/Win7Acceptance/20260926/stress/level-1000-continuation01/http/summary.json) 保留首轮失败，另起 3 个预先声明的实验意图。实际 4 并发读取持续 300.531 秒，1965 个请求、1 个错误，3 轮均确认终态。`observation_completed=true` 仅表示完成采集，`passed=false` 始终保留。第 3 轮第 3 次重放耗时 7203 ms 后出现 `storage_failure`，`request_ref=dd94f4ce21e14073b90a6f7a03138bff`。

[续测来宾错误日志](C:/Users/lurenxing/AppData/Local/Temp/aps-win7-acceptance-20260926/target-pressure1000-continuation-storage-failure/aps_error.log) 的 `16:33:03` 栈再次指向命令重放事务 COMMIT 的 `database is locked`，与首次 1000 工序故障相同。该结果表明失败不是只出现一次的 HTTP 观察偶发错误；仍不能凭两次样本推出固定错误率。

## 追加证据：5000 工序任务在计算前中断，执行器持续停用

以下是 `16:47:34` 实时日志快照对应的确定事实；完整 600 秒观察及停机后的数据库检查由最终验收报告补齐。数据为 100 批次、5000 工序、8 并发。应用进程继续运行，采集器不操作虚拟机或应用生命周期。

- 原任务：`run_ref=0791c38df34340ce3096588c1bf60fe22a4ac159270fc5d0`，`request_key=win7stress-28e36418123e4e1bb5924ad9585d37b4`。
- 首次受理返回 202；首次同 key 重放耗时 9593 ms 返回 500，`request_ref=d16d713bc22a44348a4f5f320fdf938e`。
- 同窗首页 GET 耗时 10203 ms 返回 500，`request_ref=58dca92ee22d4f1ea0996f9e286950de`。
- [第 1 轮记录](../../evidence/Win7Acceptance/20260926/stress/level-5000-run01/http/run-1.json) 确认 `accepted_at=16:45:09`、`finished_at=16:45:31`、`started_at=null`、`state=interrupted`、`result_persisted=false`、候选为空。
- [第 2 轮记录](../../evidence/Win7Acceptance/20260926/stress/level-5000-run01/http/run-2.json) 在授权预览阶段得到 `run_worker_not_connected`，未提交受理请求；第 3 轮未开始。读取观察继续，不能称为完成了 3 轮排产。

[5000 工序来宾错误日志](C:/Users/lurenxing/AppData/Local/Temp/aps-win7-acceptance-20260926/target-pressure5000-interrupted-live-20260926-164734/aps_error.log) 给出三个不同的失败位置：

1. `16:45:27`，重放从 `commands.py:50` 进入事务时，在 `transaction.py:95` 执行 `BEGIN IMMEDIATE` 失败。**这次是 BEGIN 锁超时，不能套用 1000 工序的重放 COMMIT 栈。**
2. `16:45:28`，首页在 [dashboard schema 检查](../../core/infrastructure/workbench_dashboard_schema.py) 第 79 行执行 `SELECT name,sql FROM sqlite_master` 时被锁，随后返回 `storage_failure`。
3. `16:45:31`，worker 在 [领取任务事务](../../core/services/workbench/run/worker.py) 第 46–55 行退出时，`conn.commit()` 抛出 `database is locked`。随后一条日志明确记录 runtime disabled，原因是 `awaiting_reconciliation: 0791…`。调用栈尚未到第 57 行 `_compute`，因此不能解释成算法计算超时或候选落盘失败。

失败后的状态链可以由源码和实际返回相互印证：

- claim 的 `UPDATE WorkbenchRunJobs SET state='running',stage='computing',executor_ref=?,started_at=?` 在提交失败后回滚，所以持久化作业仍是 queued，`started_at` 为空。
- [runtime._run_one](../../web/bootstrap/workbench_run_runtime.py) 第 169–191 行用新连接核对原作业，见其还未终态，调用 `_disable`、`_stop.set()`、`_recover()`。`_disable` 经第 60–72 行移除 dispatcher，并关闭排产、候选采用、标定采用等运行能力开关。
- [worker_recovery](../../core/services/workbench/run/worker_recovery.py) 第 40–45 行在确认无活动执行器、无候选后，原子写入 `interrupted` 终态与回执。该保护逻辑没有重新计算或伪造候选。
- `_recover()` 成功返回也不会在这条异常路径重新开启 dispatcher；worker 线程在 `_stop` 后结束。故 API 仍可读，但新排产预览持续不可用。后续 GET 恢复 200 不代表排产执行器恢复。

“未领取任务失败后对账并停用执行器”已有明确的 [生命周期测试](../../tests/workbench/test_run_runtime_lifecycle.py) 第 119–134 行，说明停用是保守恢复策略。此次产品缺陷在于实际 5000 工序的并发读取可以触发领取事务锁超时，从而把一个已受理的正常排产变成中断，并使后续排产能力持续不可用。不是虚拟机关闭、整个应用崩溃，也没有证据表明是 Python/Chrome 兼容错误。

同窗 [应用日志](C:/Users/lurenxing/AppData/Local/Temp/aps-win7-acceptance-20260926/target-pressure5000-interrupted-live-20260926-164734/aps.log) 的批次 GET 约 7.5–16.5 秒，符合长读事务和等待写入之间的竞争。日志可确认异常位置和上述恢复链，但没有逐连接锁跟踪，不能确定每一次锁冲突的唯一持锁者，也不能把 9–10 秒 HTTP 总耗时等同于 SQLite 忙等待本身。实时目录没有 WAL/SHM；活动数据库的实际模式及完整性以安全停机后的只读检查为准。

这项新增影响不能被“原 key 已核实”抵消：原请求确实产生了一个失败终态，**没有任何完整候选供用户使用**，新排产预览还显示泛化的“功能尚未开通”。只修复幂等重放的多余写事务不足以证明解决了 worker claim 与批次读取的竞争。

安全恢复边界：完成当前只读观察并封存日志后，由虚拟机负责人正常停止、导出数据库，核对原 key 唯一受理/中断回执、候选确实为空、业务基线与 SQLite/FK；再同库重新启动、回读原终态并检查 dispatcher 可用性。重启不得把原 interrupted 作业当成完成，旧 key 也不得重新执行；如另做排产验证，必须作为单独的新实验保留新 key 和报告。不得为了继续跑而直接清除 stop 状态、删锁或改写原作业状态。

修复建议需覆盖这一独立边界：优先缩短读取持锁时间；区分“尚未进入计算、领取事务已确认回滚”和“计算/结果 COMMIT 不确定”。若引入重试，只能在新连接确认原作业仍 queued、无执行器/候选、受理回执一致且运行锁所有权有效后，对原任务做有上限的领取重试；不能对任意 worker 异常重新计算。即使继续采用保守停用，也应给出准确的故障和恢复入口，而非仅提示尚未开通。回归必须验证真实 DELETE 模式长读冲突下的 claim 提交、失败终态、运行能力状态和重启后的恢复，保留既有避免重复计算的保护约束。

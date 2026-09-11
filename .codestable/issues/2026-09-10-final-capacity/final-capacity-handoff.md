# 任务 B：5000 同资源容量交接

## 结论和边界

- Main 独占窗口 `r2-final-5000-20260910-v1` 正式通过。原 180 秒目标保留，未开 cProfile，未改算法、策略、预算、候选数或输出明细。
- 实际数据库为 **100 批，每批 50 道，共 5000 道**；只有 M1/O1 一组设备人员，quantity=3、setup_hours=0、unit_hours=0.001，原默认日历和日期范围不变。
- baseline、graph_w1_of_3、graph_w2_of_3、graph_w3_of_3 各 **5000 条**，完整落库共 **20000 条**。不是根据 CLI 的 `50` 或数组长度推测容量。
- 本次证明绑定窗口内的 build 和产品源。Main 已恢复其他域工作，后续 shell/下载/旧 UI 退役与最终 HEAD 的变化**不自动继承此证明**；是否再跑一次 final-bound 容量，由 Main 决定。
- 这是 macOS/Python 3.8.10 单机受管 HTTP 的容量证据，不是 Win7 真机、打包、最终发布或 clean-worktree proof。整仓门禁/Git/最终归档仍由 Main 负责。

## 正式命令与输出

工作目录：`/Users/lurenxing/GitHub/----`。

```bash
env TMPDIR=/tmp/aps-final-capacity-B.bk32eh PYTHONPYCACHEPREFIX=/tmp/aps-final-capacity-B.bk32eh/pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/workbench/verify_final_capacity.py --output /tmp/aps-final-capacity-B.bk32eh/formal-5000-r2-v1 --operations 50 --batches 100 --exclusive-window r2-final-5000-20260910-v1 --asset-root /private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-t34sja_l/full-build/static/workbench
```

真实退出码 0；`complete=true`、`formal_capacity_passed=true`。窗口由 Main 在 2026-09-10 11:37:02 UTC 发出；数据库受理/开始时间为本机 19:38:32，完成终态 19:40:34。

- 结果目录：`/tmp/aps-final-capacity-B.bk32eh/formal-5000-r2-v1/`。
- 当前保留的私有运行 root：`/private/tmp/aps-final-capacity-B.bk32eh/formal-5000-r2-v1/aps-workbench-live-nz5iurpx`。
- `run_ref=501be599396e32487fc439002b3df221cf8b8d859684bf4d`。
- 初始会话 `7f08e36f471c49f2852c42c81a87d1bd`；重启会话 `80cc029019d44f318987646cc5821e14`。
- 原 SQLite、完整候选 payload、每次 HTTP 原始 JSON、客户端请求日志、worker 阶段记录、完整业务前后快照、源哈希、退出备份、所有失败小档均原样保留；未清缓存或抹日志。

## 耗时与内存

| 实测阶段 | 秒 | 该阶段结束时进程峰值 RSS，bytes |
| --- | ---: | ---: |
| HTTP 202 受理 | 1.373051250 | 不适用 |
| 输入准备 | 0.400772000 | 309608448 |
| 真实四候选引擎 | 119.754998333 | 385941504 |
| 完整结果序列化 | 0.520143458 | 442826752 |
| 数据快照+准备+计算+序列化 | 120.869860500 | 442826752 |
| 四候选完整持久化 | 0.371078000 | 442826752 |
| worker 总计 | 121.342296000 | 453558272 |
| 受理至客户端读到完整终态 | 122.728285375 | 不适用 |
| 第一次正常停机 | 1.427592542 | 604520448 |
| 重启读取后的正常停机 | 1.526147042 | 672530432 |

阶段有包含关系，**不能相加**。引擎阶段峰值约 368.06 MiB，worker 阶段峰值约 432.55 MiB；初始/重启 host 整个验证生命周期峰值分别约 576.52/641.38 MiB。后两者包含全量 HTTP 工作区、验证用业务快照和退出证据读取，不冒充纯算法内存；这里测的是对应 server 进程 RSS，不是整机内存或所有进程峰值之和。

实际四候选各自计时约 3.289502、38.372018、38.613973、39.267950 秒。原配置 `time_budget_seconds=600` 是候选比较/优化预算，候选之间检查截止，非任意位置硬抢占；它不是调度整体 SLA，也不包含 HTTP 预检、受理、序列化/落库与关闭过程。**180 秒是这次独立容量目标**，本次没有调整或豁免。

## 请求可达与延迟

初始会话总计 115 次真实 HTTP 请求，113 个 200、两个 202（受理与同 key 重放）。状态轮询实读 queued=1、running=34、complete=1；不是根据睡眠或 mock worker 判断“正在运行”。运行中原 request_key 查询与真正的资源汇总请求均成功。

分位数采用 nearest-rank：排序后取 `ceil(n*p)-1`，单位为秒；计入本地 HTTP 往返及客户端 JSON 解析，不计浏览器 DOM 渲染。

| 请求 | n | P50 | P95 | P99 | 最大 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 运行状态，含首次 queued 和最后 complete | 36 | 0.670891 | 0.816298 | 0.867510 | 0.867510 |
| 原 request_key 查询，queued/running 阶段 | 35 | 0.693279 | 0.876234 | 0.913381 | 0.913381 |
| resources/summary，queued/running 阶段 | 35 | 2.363755 | 3.261825 | 3.349389 | 3.349389 |
| 上述轮询合计 | 106 | 0.745071 | 2.921503 | 3.261825 | 3.349389 |

资源汇总有秒级等待，**只能说可达，不能说即时响应**。未为通过而删掉这些请求或扣除其对计算的影响。精确未舍入值见 [latency-summary.json](latency-summary.json)。原 trace SHA256 为 `7d19172b35a75426e0dbc84963ac63abf990014cc8bf8783a59b297e2cb64a0d`。

复核分位数的实际计算方法：读取初始会话 `client-requests.json`，按 GET 且 path 等于 `/scheduling/runs/<run_ref>`、`/scheduling/requests/<request_key>`、`/resources/summary` 分组，对 `elapsed_seconds` 排序，再使用 `values[math.ceil(len(values)*p)-1]`。合计组是这三个互不重叠分组的串联；不混入 POST 受理、候选工作区或重启阶段请求。

## 完整输出、refs 与业务保留

- 精确核对数据库 Batches 的 100 个原批号、每个 BatchOperations 分组的 50 条、5000 个 op_id 及所有正工时/唯一资源。每条 ScheduleRow 只通过 `op_id` 回查批次与原序列，不假定不存在的 batch_id 字段。
- 四候选顺序/键均为原定义，每候选 5000 个工序、5000 条正时长安排、原批内链不重排、M1/O1 不重叠、无 out_of_scope_op_ids、无 validation_errors。
- 每条持久化 task 的 operation_ref 与原永久来源一一对应，row_ref 唯一，ordinal 连续；payload 必须与完整验证后原结果加原 locked 值逐字段相等。
- 四个真实 HTTP 工作区各返回完整 5000 条；重启后再次读取，完整 data 指纹相同。候选目录未用分页、截断或只返回图形数组掩盖丢行。
- 第一次计算前后 **72 个非运行表逐行不变**。仅 WorkbenchCommandReceipts、WorkbenchRunJobs、WorkbenchRunReceipts、WorkbenchRunCandidates、WorkbenchRunCandidateTasks 这 5 个本来为空的运行表新增合法受理/终态和完整结果。
- 正常重启精确新增一条 `plugins/load` 启动审计及其 OperationLogs 自增序号，原日志和其他业务行/无关序列全部保持。启动后所有 GET 和退出备份零数据库写入。相关负测拒绝修改旧日志、额外日志、业务变动、GET 写入、插件内容漂移或错误序列。
- 重启后 run_ref、receipt_ref、candidate_ref、row_ref、operation_ref、完整候选 artifact、20000 明细、全部 payload 和正式业务表保留；完成运行未重新排产。
- `PRAGMA integrity_check=ok`，`foreign_key_check=[]`。

| 内容 | SHA256 |
| --- | --- |
| 四候选完整 payload，规范化 JSON | `66e66fd1bea4cb681dbc87f762d4a68d0273fc3297926680637e2d569f137b5f` |
| 5000 个原 operation refs 映射 | `44ecd2e13e54c0c0b6035e83536c69be761f1634c924f69895ab3012be630082` |
| 完整终态回执 | `73e0a961f835f5002df8d2a4e5e8bebc81c5ff3f3337805ac7e824ec13595446` |
| baseline 完整 payload | `0778314d6a1d78b1203dd2da9e3a99549719a37f8f8d5a52d6cb19cebe11c785` |
| 三个 graph 候选各自完整 payload | `14bdd59409e00e2c54676bea5621692eefa5b417560f2369b29d6a83a2e234e0` |

三个 graph 候选的 payload 相同只是这份对称种子的实际结果；候选键、引用和 3x5000 明细分别存在，不合并候选或减少计算。

## 退出与隔离证明

- 驱动 PID49278、初始 host PID49279、重启 host PID49732 均结束。unified exec 返回 0；两份 host 过程证据 returncode 均为 0。收尾 `ps -p` 三个 PID 均只返回表头，未找到进程。
- 两次 host 的真实事件顺序相同：`launcher_locks_acquired -> factory_schema_ready -> real_runtime_ready -> http_stopped -> runtime_shutdown_joined -> exit_backup_complete_under_lock -> launcher_locks_released`。
- 两次 runtime.closed=true、pending=[]，原 launcher lock 和 db lock 文件都不存在；没有强制 kill 或 forced-stop 记录。
- 连接路径只在自己的 root 内或真实 worker 自带的 SQLite Backup API `:memory:` 计算快照；原始数据、受理、四候选和全部明细均在真实文件 SQLite 上，并通过受管 HTTP 工作，不是只测内存数组。isolation_violations 两次均为空。
- 未连接、重启或修改旧 preview53144/PID73298/root aps-workbench-live-l0tgvgp8，也未操作生产库。

## 源与 build 绑定

- 本次 build ID：`e09173b0bc08b022e9a365d516f555338a4a4cd2fc8f2a983ae012328abbe6cf`。
- manifest SHA256：`75ae60c204d088463174af0f2dcaaed2969b4d1708e32cceea2046ce7f79ffde`。指定 Main asset-root 的 211 个文件逐文件 bytes/SHA256 验证，303 个输入也全部匹配，source_differences=[]；冻结的是这份 build，不是 global stale 资产。
- 全部根目录 Python、core/data/web/plugins 的 Python/SQL/JSON，加 frontend/workbench 与 templates/workbench，共 **1472 个产品输入**。前后清单文件 SHA256 相同：`03ce03fb9705385e641ed359b314c213cec06c37c8a7f3e427e38110d93590ee`，差异为空。
- 开始前相同映射的规范化 JSON 指纹为 `11e537e63eb6dca93ee26a0a34c5070a032807d9f3e7568280e7e6bd9d70f2f1`。它与上一行的带缩进清单文件哈希口径不同，不能混用。
- 期间每秒检查路径、inode、size、mtime_ns、ctime_ns，132 次检查无漂移；观察线程累计 4.252046 秒，**未从计量中扣除**。收尾还检查元数据，可识别内容改后还原；另有实际加载 Python 模块的前后/跨重启逐文件 SHA 验证。
- 该机制是 Main 协调暂停写入加指纹/元数据证据，不声称提供操作系统层面的写保护。原始前后清单保留在 private output，不因之后 Main 恢复产品改动而重写。
- 验证器的 10 个 Python 文件 SHA256 见 [source-hashes.sha256](source-hashes.sha256)，本轮正式运行期间未改这些文件。

## 改动范围和验证

仅新增 10 个专属 Python 文件和本 issue 记录；产品代码零改动：

- `scripts/workbench/verify_final_capacity.py:14`：显式 CLI、规模/窗口/asset-root，禁用正式 cProfile。
- `tests/workbench/final_capacity_support.py:14`、`:89`、`:111`：真实种子和全部原始/持久化/批内序列断言；`:61` 精确重启保留。
- `tests/workbench/final_capacity_probe.py:31`、`:115`、`:160`、`:195`：真实 HTTP、自有子进程关闭、全量读取、重启和源绑定。
- `tests/workbench/final_capacity_server.py:24`：实际 factory/runtime，只覆盖测试种子和指定资产来源，不覆盖产品算法。
- `tests/workbench/final_capacity_observation.py:23`：调用原方法的阶段观察，原异常继续抛出。
- `tests/workbench/final_capacity_assets.py:12`：逐 manifest 文件冻结 Main build；`final_capacity_sources.py:31`：全部产品输入漂移守卫。
- `tests/workbench/test_final_capacity_contract.py:26`、`:33`、`:74`、`:132`：规模/窗口/陈旧构建/完整输出/重启负测。
- `tests/workbench/test_final_capacity_managed.py:6`：真实 200 工序受管 HTTP 回归。
- `tests/workbench/test_final_capacity_inputs.py:35`、`:45`、`:68`：资产文件/路径/manifest 漂移、源码改后还原的文件级测试。

实际命令结果分别保留，不把有重叠的组相加：

1. 早期 200 全链 + 完整性/重启边界联合：`21 passed in 9.54s`，证据 `/tmp/aps-final-capacity-B.bk32eh/final-capacity-small.xml`。
2. 后增 asset-root/源码冻结/陈旧构建及窗口输入的文件级测试：`12 passed, 16 deselected in 0.91s`，证据 `/tmp/aps-final-capacity-B.bk32eh/input-contract.xml`；没有调用排产重任务。
3. 10 个新增 Python 文件定点 `-m ruff check --no-cache` 全通过；正式窗口关闭后相同 10 文件 `-m pyright` 为 `0 errors, 0 warnings`。未升级依赖，始终使用 `.venv/bin/python` 3.8.10 和 `-m pyright`，私有 pycache。
4. 正式 5000 命令返回 0，完整结果及退出检查如上。Main 不要求本轨再跑一轮；当前没有再次执行容量或算法优化。

Main 待登记测试文件是 `test_final_capacity_contract.py`、`test_final_capacity_managed.py`、`test_final_capacity_inputs.py`。support 不作为测试文件注册；5000 显式 CLI 由 Main 安排独占窗口，不自动混入有并行污染的普通 pytest run。

## 关键文件取证

相对目录以下均为 `/tmp/aps-final-capacity-B.bk32eh/formal-5000-r2-v1/`：

| 文件 | SHA256 |
| --- | --- |
| `result.json` | `5cda5d6ee0e52dcdadb042c3046f99f982782ab822ebcf9461f46e660d35c00e` |
| `candidate-payloads.json`，带缩进完整文件 | `85acf5967fdad4fd2b21661f393641647fc3f0d8ac5ad905f90aeb31d9368d93` |
| `product-inputs-before.json` / `product-inputs-after.json` | `03ce03fb9705385e641ed359b314c213cec06c37c8a7f3e427e38110d93590ee` |
| `aps-workbench-live-nz5iurpx/db/aps-live.db`，正常退出后的原库 | `c5a8dbd4173ab73a429ac0651c97098af95db20d4f1dc8004cf1aceb3457683e` |
| 初始会话 `server-final.json` | `3e390d9012a5118585727423037537a9aed82299bb8e8d547132d0c2d21fd1e0` |
| 重启会话 `server-final.json` | `7ba42c611625ac716690eaceff93353f02fe43a98350a704322a713b14363f96` |
| 第一次正常退出备份 `aps_backup_20260910_194036_run_fixture_exit_7f08e36f471c49f2852c42c81a87d1bd.db` | `db56d737583613c19226755d7e1e5dc52a477ef3e37b1418aac4776136e619d6` |
| 重启后正常退出备份 `aps_backup_20260910_194042_run_fixture_exit_80cc029019d44f318987646cc5821e14.db` | `316c802a251bc671f2bfc4f8415751150f38f46febfc4a5af36407a716350222` |

备份与原库的文件哈希不要求相同，SQLite Backup API 的物理布局可能不同；本轮的业务保留由完整行/refs/payload 检查证明，不以“备份文件哈希一样”替代逻辑验证。

## 剩余事项

- 本轨未执行 Git add/commit/reset/checkout/清缓存。原 source-RauBC6、pre-retirement-LqHg4q 归档和唯一既有 staged 测试未被本轨写入；Main 的独立 Git 动作由 Main 记录。未回退任何 prior dirty。
- 结果完整性与容量已在本次窗口验收，没有待修算法问题被隐藏。资源汇总最大 3.349389 秒的真实响应代价保留为边界，不另开优化。
- 当前交付后 freeze，等待 Main 通知。最终测试登记、代码归档、完整门禁、最新预览、旧 UI 退役及最终 HEAD 是否补跑容量，均由 Main 统筹。Win7 包/真机/最终发布排除在本轮范围外。

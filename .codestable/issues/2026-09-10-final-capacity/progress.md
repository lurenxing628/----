---
doc_type: issue
status: completed
date: 2026-09-10
scope: final-5000-single-resource-managed-http
---

# 5000 同资源容量闭环

## 阶段结论

任务 B 已完成真实 cProfile 复核、200 工序完整 payload 等价，以及 Main 独占窗口 `r2-final-5000-20260910-v1` 的正式 5000 容量闭环。引擎 119.754998333 秒，受理至完整终态 122.728285375 秒，四候选各 5000 条、共 20000 条持久化明细，重启/全部 refs/payload/业务保留/退出锁及源码绑定通过。完整可审交接见 [final-capacity-handoff.md](final-capacity-handoff.md)。

Main 已核对结果并关闭正式窗口。本轨停止新重测试和产品改动；后续源码合入 HEAD 后是否再跑 final-bound 正式容量，由 Main 决定。下文保留的是小档阶段和失败历史，不冒充正式窗口结果。

产品算法暂不改。用户已同意只新增验证脚本、专属 support/测试与本目录记录。没有改排产策略、四候选数量、600 秒原配置优化预算、180 秒原容量目标或现有基线；没有修改 schema、DTO、构建入口及 planning206 能力基线。

## 根因与已有证据复核

- 原 5000 同资源用例在 340.33 秒中断，未走到四候选完整性或耗时成功断言。这条失败保留，不由分散 100 资源组的另一项 5000 测试替代。
- 已有忙段跳过优化针对连续已占用时段的重复日历估算；历史 200 工序旧单跳 33.140 秒、新路径 3.661 秒，完整 payload 字节一致；1000 为 24.201 秒。来源：`.codestable/issues/2026-09-10-dense-busy-skip/progress.md` 与其 `proof.json`。
- 本轮当前源码真实 cProfile 1000：25.020506375 秒，285150 次 SGS 内部候选评分，累计约 22.211 秒；289150 次真实时隙估算累计约 16.859 秒。仍是 SGS 逐候选评分热点，不是 SQLite 持久化采样。没有据此外推 5000 通过或加入新缓存。
- 本轮纯计算 200：3.931013541 秒、4x200；1000：4x1000。两档数据库原行与 `total_changes` 不变，各采样子进程正常结束。
- 当前 busy_block_skip、downtime、internal_slot、calendar_service 与 profile_dense_resources 的 SHA256 仍匹配历史 `proof.json`。当前 200 完整文件另经 `cmp` 与历史旧单跳文件逐字节一致，不仅比较行数或最终状态。
- 200 payload SHA256：`72edcfc767a042d54ba4afb17222643beff1a94541e015bd14f7b9199f04c9b0`。
- 1000 payload SHA256：`d47139632920b7b1313ff44bcd8f37d4349ea600f33408a0444ee107b084a1d9`。

以上耗时均是共享主机探索。cProfile 本身及其他轨的负载都可能影响耗时，不作为正式容量或 Win7 性能结论。

## 新增验证路径

| 文件 | 责任 |
| --- | --- |
| `scripts/workbench/verify_final_capacity.py` | 显式 CLI；默认 100x2 小档；100x50 正式档必须有 Main 独占窗口 ID，禁用 cProfile |
| `tests/workbench/final_capacity_support.py` | 同资源正时长真实 SQLite 种子；业务旧行、全部候选/任务/refs/payload 精确核对 |
| `tests/workbench/final_capacity_observation.py` | 包装并原样调用真实 worker，记录准备、引擎、序列化、持久化、总耗时及 RSS；异常原样抛出 |
| `tests/workbench/final_capacity_server.py` | 复用真实 factory/受管 runtime/隔离 HTTP server；只替换测试种子，不替换算法或生产持久化 |
| `tests/workbench/final_capacity_probe.py` | 真实 POST 预检/预览/受理，202 后轮询、其他请求、全量四候选读取、同 key 重放、退出、全新进程重启 |
| `tests/workbench/test_final_capacity_contract.py` | 不允许未协调大档、profile 冒充正式、错误规模、截断/重复/零时长/重叠/错误资源/批内乱序、启动变化冒充全表不变 |
| `tests/workbench/test_final_capacity_managed.py` | 200 工序真实 HTTP 全链回归，包含固定完整 payload 等价证明 |

所有测试库、日志、退出备份、进程锁、pycache、调用图和过程证据都在 `/tmp/aps-final-capacity-B.bk32eh/` 私有目录。未连接生产数据库，未连接或停止旧 preview 53144/PID73298，未使用其 root。未自行派生代理。真实子代理工具当前不可调用，协调使用现有 Main 任务消息。

## 小档受管 HTTP 结果

完整通过目录：`/tmp/aps-final-capacity-B.bk32eh/managed-200-third/`。

- 100 批 x 每批 2 道，共 200；全部固定 M1/O1，quantity=3、setup_hours=0、unit_hours=0.001。
- 四个原候选：baseline、graph_w1_of_3、graph_w2_of_3、graph_w3_of_3，各 200 行，共 800 条持久化任务。
- 验证全部工序 ID、正时长、不重叠、原批次与原序列；ScheduleRow 通过 `op_id` 回查批次/序列，不假定有不存在的 `batch_id` 字段。
- 每条 task 的 `row_ref` 唯一，`operation_ref` 对应原数据库永久来源，ordinal 精确连续，完整 payload 等于验证后原结果加原 locked 字段。
- 202 受理约 0.081683 秒；受理至完整终态约 2.251683 秒。真实 worker 引擎约 1.966492 秒；准备 0.031804 秒、序列化 0.024920 秒、持久化 0.015362 秒、worker 总计 2.069843 秒。记录的是并行污染探索值。
- 运行中观察到真实运行状态、原 request_key 查询、`/api/workbench/v1/resources/summary` 均可达；不是 mock 的健康检查。
- 四个完整候选 HTTP 工作区返回全部 200 条任务，没有分页截断伪装为完整。
- 正常停机约 0.776388 秒，重启后再次正常停机约 0.790461 秒；worker 完成、退出备份在锁内完成、锁释放、两次子进程返回 0。
- 重启的 run_ref、receipt_ref、candidate_ref、row_ref、operation_ref、全部候选/任务/完整 payload 均保持；完成运行未被重新计算。
- 所有旧业务行保留。重启仅追加一条既有 `plugins/load` 正常启动日志及其 OperationLogs 自增值；日志内容除时间外与前次一致，其他序列完全不动。启动后的全部 GET 和退出备份均零数据写入。
- 原构建文件未变；两次进程之间已加载源码的逐文件 SHA256 未变。完整来源哈希、原 SQLite、HTTP 响应、阶段计量、退出备份和会话快照均保留在私有目录。

该小档复制的是旧静态 build `67229ad0b232830132f049095e8c8c8b80ba29296df7b3668a128af1ebec5c78`。其 manifest 报告 theme.js、FieldFiles.jsx、main.jsx、build-order.json 四项源差异。这是后台 HTTP 探索证据，不是最新预览或全站验收。正式入口遇到 source_differences 非空会在受理/计时前拒绝。

## 已保留的失败

1. `managed-200-first`：真实四候选落库和进程退出已完成，验证器误读不存在的 ScheduleRow.batch_id，KeyError。改为用 op_id 回查真实批内顺序；没有改算法或删除完整性要求。
2. `managed-200-second`：计算、落库、全量工作区与重启结果相同，但验证器误要求正常启动审计也全表不变。逐表 diff 仅 OperationLogs 新增一条 plugins/load 与 sqlite_sequence 对应 +1；来源为 `web/bootstrap/plugins.py` 的 OperationLogger.info。改成精确追加合同，旧日志、业务行、无关序列及 GET 写入均有负测拦截，不做泛化豁免。
3. 最初定点 Ruff 检出两处 `.format` 与一次长 import，已按项目格式修正。没有调规则或阈值。
4. Main 通知 19:23+08 的 Git 钩子曾短暂 stash/恢复 tracked unstaged。以上两次验证器失败有明确字段/审计差异，不归因于该钩子；没有把短时源码变化当作产品根因。

## 真实命令与验收边界

共同环境前缀：

```bash
env TMPDIR=/tmp/aps-final-capacity-B.bk32eh PYTHONPYCACHEPREFIX=/tmp/aps-final-capacity-B.bk32eh/pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B
```

- `scripts/workbench/profile_dense_resources.py --output /tmp/aps-final-capacity-B.bk32eh/profile-current-1000 --batches 100 --operations 10 --deadline 60`：returncode 0、25.020506375 秒、4x1000。
- 同入口 `--output /tmp/aps-final-capacity-B.bk32eh/profile-current-200 --batches 100 --operations 2 --deadline 60`：returncode 0、3.931013541 秒、4x200。
- `cmp /tmp/aps-final-capacity-B.bk32eh/profile-current-200/candidate-payloads.json output/workbench-migration/verification/dense-busy-skip-20260910/aps-dense-200-oracle-20260910/candidate-payloads.json`：returncode 0。
- `scripts/workbench/verify_final_capacity.py --output /tmp/aps-final-capacity-B.bk32eh/managed-200-third --operations 2`：returncode 0、complete=true、formal_capacity_passed=false。
- `-m pytest -q -p no:cacheprovider --basetemp=/tmp/aps-final-capacity-B.bk32eh/pytest-final --junitxml=/tmp/aps-final-capacity-B.bk32eh/final-capacity-small.xml tests/workbench/test_final_capacity_contract.py tests/workbench/test_final_capacity_managed.py`：21 passed / 9.54 秒。之后新增一条正式构建陈旧拒绝测试，其后续结果另记，不冒充已包含在这 21 项中。
- 七个新增 Python 文件定点 Ruff 通过；前六个文件定点 `-m pyright` 为 0 errors / 0 warnings。未升级 pyright 或任何依赖。

Main 正式独占命令，窗口 ID 必须由 Main 提供：

```bash
env TMPDIR=/tmp/aps-final-capacity-B.bk32eh PYTHONPYCACHEPREFIX=/tmp/aps-final-capacity-B.bk32eh/pycache PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/workbench/verify_final_capacity.py --output /tmp/aps-final-capacity-B.bk32eh/formal-5000-新窗口 --operations 50 --exclusive-window Main给出的窗口ID
```

180 秒是原容量验收目标，不是产品自动取消承诺。600 秒是本种子沿用的可配置候选优化预算，不含 HTTP 预检、受理、准备/序列化/落库或停机；源码在候选之间检查总预算，并不提供任意运行点的硬抢占。脚本分别记录引擎、worker、受理到终态的真实耗时，完整检查四候选，没有减少候选或删除输出换时间。

本轨 B=真实后端小档通过，P=真实新进程重启通过；K/V 不属于这个后台容量脚本的动作，不替代 Main 的浏览器实际输入/点击或目视验收，不减少全站动作分母。Win7 打包、真机及最终发布排除在本轮之外。

本轨未执行 Git add/commit/reset/checkout/清缓存，未操作原源码归档和唯一既有 staged 文件；Main 的独立提交/钩子动作由 Main 记录。整仓质量门禁和最终源码归档由 Main 统一运行，本报告仅为 dirty 工作区局部证据，不能称 clean-worktree proof。

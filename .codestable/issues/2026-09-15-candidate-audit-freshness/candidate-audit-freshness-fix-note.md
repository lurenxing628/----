---
doc_type: issue
slug: candidate-audit-freshness
status: fixed
created: 2026-09-15
last_reviewed: 2026-09-15
related_roadmap: workbench-manual-remediation
validation_status: targeted-passed-manual-recheck-pending
---

# 启动审计日志导致候选误报输入变化

## 现场证据

5005 手动验收原候选 `214ffd732ef40989a6509a2fcbc88c32144d97e6e634c8ea` 的接受时间为 `2026-09-15T21:30:09`。修复齐套日期类型后重启服务，采用预检出现 `snapshot_stale`。

使用 SQLite URI `mode=ro` 和正式日期类型转换选项比较原始存档与当前数据库：Schema 完全一致，所有业务表完全一致，仅以下两项变化：

- `OperationLogs` 从 13398 行增加至 13399 行：`2026-09-15 22:00:47` 的 `plugins/load` 启动记录。
- `sqlite_sequence` 中 `OperationLogs` 的计数从 13398 变为 13399。

该记录来自 `web/bootstrap/plugins.py:253` 的 `OperationLogger.info`，不修改排产输入。旧 `capture_run_facts` 全存档 SHA 被 Worker 和采用预检直接当作业务版本使用，因此重启、备份审计等纯日志写入会误使候选失效。

## 修复边界

完整 `facts_json` 及其 SHA 继续原样存档。新增 `run_jobs_facts.run_facts_unchanged`：先验证存档文本确实匹配其原始 SHA，再比较排产输入。此处理也支持已经存在的旧候选，不改历史存档、不重算候选，不补默认业务值。

| 内容 | 当前比较规则 |
| --- | --- |
| `OperationLogs` 行内容 | 纯审计，忽略其增删改对业务新旧判断的影响；记录本身仍在数据库和完整历史存档内 |
| `sqlite_sequence` 中 `OperationLogs` 行 | 仅此审计计数不参与业务新旧判断 |
| 所有其他表及计数 | 保留原来的严格比较，包括未来新增的未知表，不通过表名猜测并忽略业务数据 |
| 全部 Schema | 原样比较，包括日志表自身的结构、索引、触发器 |
| 候选自己的四张运行账本及 `scheduling.run` 回执 | 沿用现有捕获规则；本项没有扩大此排除范围 |
| 原始存档 SHA | 始终先校验，不因只发生审计变化而接受存档被篡改 |

规范 JSON 比较保留标量类型差异，不使用 Python 的宽松数值相等来比较业务值。

调用点统一为 `run_worker.py:32` 的计算前/保存前检查及 `run_candidate_adoption_storage.py:73` 的采用前检查。正式版本、执行投影、工序资源、材料齐套、日历工时等其它独立校验全部保留。

## 定向验证

新增重启审计 API 回归先在旧代码下复现 `snapshot_stale`，修后通过。测试通过独立 Python 进程、正式 `get_connection` 和实际 `OperationLogger` 写入与启动相同的 `plugins/load` 记录，随后预检成功；预检之后再追加备份审计，采用仍成功，旧 `facts_json/facts_hash` 不变，两条审计记录均保留。

Worker 回归分别在接受后、实际计算完成但保存前追加审计，候选计算和保存均成功，存档不变。负例锁住配置变化、业务自增计数、Schema 索引变化和未知业务表变化仍返回 `snapshot_stale`。原有设备、人员、授权、工时、齐套、报工、正式版本漂移和事务故障用例同时通过。

```text
.venv/bin/python -m pytest -q \
  tests/workbench/test_run_jobs.py \
  tests/workbench/test_run_candidate_adoption_api.py \
  tests/workbench/test_run_candidate_adoption_boundaries.py \
  tests/workbench/test_run_jobs_restart.py \
  tests/workbench/test_run_jobs_atomic.py \
  tests/workbench/test_run_candidate_adoption_atomic.py
70 passed in 15.62s
```

以上均为已注册专项文件内的新增用例，没有新增注册项。`git diff --check` 对本项文件通过。

现场只读复核两个旧 74 工序候选 `a86a1998a3aa4c90bda7f28c21c85994c70d87d18237d192` 与 `214ffd732ef40989a6509a2fcbc88c32144d97e6e634c8ea`：完整存档 SHA 与当前全库 SHA 不同、业务输入比较相同、完整采用验证均 valid、基准仍 v14、连接 `total_changes=0`。主代理负责加载补丁后的手动采用复验；本代理未写入现场业务数据。

按用户要求未运行任何全门禁或整仓测试。保留大量既有未提交修改；本项不提交、不清理其他文件，不声称 clean-worktree proof。

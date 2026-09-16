---
doc_type: issue
slug: candidate-adoption-manual
status: fixed
created: 2026-09-15
last_reviewed: 2026-09-15
related_roadmap: workbench-manual-remediation
validation_status: targeted-passed-manual-recheck-pending
---

# 完整候选采用被日期类型误拒绝

## 现场与根因

手动验收环境 `http://127.0.0.1:5005` 的候选 `a86a1998a3aa4c90bda7f28c21c85994c70d87d18237d192` 已完整安排 27 批、74 道工序，但采用预检显示 `candidate_constraint_unproven`。正式计划仍为 v14。

`core/infrastructure/database.py:94` 的正式连接启用 `sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES`，因此 SQLite DATE 列读出为 `datetime.date`。`batch_model` 校验后保留原值；原 `run_candidate_adoption_constraints.py:77` 却直接执行 `datetime.fromisoformat(batch.ready_date)`，触发 `TypeError: fromisoformat: argument must be str`，被外层完整复核错误处理转成上述业务阻塞。

普通 SQLite 连接不启用日期转换时同一候选会通过；本轮先观察到该差异，再以正式连接选项重现原异常。`calculations.py` 的 `parse_dt` / `overlap_seconds` re-export 在 20:42:56 已恢复，早于 5005 进程 20:51:03 启动；它们不是本次采用阻塞原因。未通过重启猜测或放宽业务约束掩盖问题。

## 修改

- `core/services/workbench/run_candidate_adoption_constraints.py:79` 复用 `preflight_checks.stored_date`，将合法 DATE 对象或规范 ISO 文本转换成同一种日期表示后比较。`piece_adoption.py:146` 已使用这一共享解析规则。
- `batch_model` 对非法日期的拒绝、早于齐套日期的拒绝、齐套开关、资源冲突、日历工时和既有正式范围约束均保留。没有改数据库或候选内容。
- `tests/workbench/test_run_candidate_adoption_api.py:44` 在既有专项文件内增加 3 个 API 回归，明确使用正式 `get_connection`，确认实际读到 `date` 对象，再验证预检、采用和早排拒绝。无需新增测试注册条目。

## 验证

修前新增测试首先失败，日志为 `fromisoformat: argument must be str`。修后运行：

```text
.venv/bin/python -m pytest -q \
  tests/workbench/test_run_candidate_adoption_api.py \
  tests/workbench/test_run_candidate_adoption.py \
  tests/workbench/test_run_candidate_adoption_boundaries.py \
  tests/workbench/test_run_candidate_adoption_atomic.py
50 passed in 12.19s
```

3 个新用例分别证明齐套日早于开工日、等于开工日能够通过预检并采用；将候选开工移到齐套日前一天仍返回 `candidate_before_ready_date` 且不签发写入令牌。预检前后全表快照一致。`git diff --check` 对本项两个代码文件通过。

修后对现场数据库 `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-manual-reports-5005-mas98q0a/db/aps.db` 使用 URI `mode=ro` 并启用正式日期转换选项，再调用完整 `validate_adoption`：

| 候选 | 结果 | 工序数 | 原正式版本 | 本连接写入变化 |
| --- | --- | --- | --- | --- |
| `a86a1998a3aa4c90bda7f28c21c85994c70d87d18237d192` | valid | 74 | 14 | 0 |
| `214ffd732ef40989a6509a2fcbc88c32144d97e6e634c8ea` | valid | 74 | 14 | 0 |

本代理未重启服务、未构建静态资源、未操作浏览器、未写入任何现场业务数据。主代理重启 5005 加载补丁后，继续用原候选完成手动预检和采用验收。

按用户要求，未运行任何全门禁或整仓测试。工作区有大量既有修改，本项只修改上述两个代码文件并新增本说明，不提交、不清理其他改动；上述结果属于专项验证，不是 clean-worktree proof。

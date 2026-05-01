# evidence/（验收证据归档目录）

> 用途：保存功能验收、质量门禁、失败复现和排障留痕。这里的文件只负责留证据，不负责替代当前代码和测试结果。

## 目录结构

- `current/`：当前有效证明入口，只放索引和判断口径，不放大日志。
- `failures/`：失败复现、失败日志摘录、失败截图和失败 SQL 片段。
- `archive/`：历史证据索引或已经不代表当前状态的证明材料。
- `Phase*/`、`Baseline/`、`DeepReview/`、`QualityGate/` 等旧目录：保留为历史材料，不代表当前通过状态。

## 当前状态判断规则

判断当前分支是否通过，只看这些入口：

1. `python scripts/run_quality_gate.py --require-clean-worktree`
2. `python tools/check_full_test_debt.py`
3. `python scripts/sync_debt_ledger.py check`
4. `evidence/current/README.md`
5. 最新 `audit/YYYY-MM/` 入口

## 建议存放内容

- 截图：页面功能、预览状态、关键中文提示。
- 日志摘录：从 `logs/aps.log`、`logs/aps_error.log` 复制关键片段，不直接提交完整 `logs/` 目录。
- SQL 查询结果：例如 `OperationLogs` 最近记录、关键表行数等。
- 导入/导出文件：模板、导出的 Excel、用于复现问题的最小样例，提交前必须脱敏。

## 命名建议

- `YYYY-MM-DD_Px-yy_说明.png`
- `YYYY-MM-DD_Px-yy_log_excerpt.txt`
- `YYYY-MM-DD_Px-yy_sql.txt`

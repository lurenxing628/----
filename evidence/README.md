# evidence/（验收证据归档目录）

> 用途：每实现一个功能/完成一个步骤，都要做最小测试、打点日志、核对留痕，并把“证据”归档到这里，便于复盘与用户排障。

---

## 建议存放内容
- **截图**：页面功能、预览状态（NEW/UPDATE/ERROR 等）、关键提示（必须中文）。
- **日志摘录**：从 `logs/aps.log`、`logs/aps_error.log` 复制出来的关键片段（不要直接提交整个 logs 目录）。
- **SQL 查询结果**：例如 `OperationLogs` 最近记录、关键表行数等（可保存为 `.txt/.md`）。
- **导入/导出文件**：模板、导出的 Excel、用于复现问题的最小样例（注意脱敏）。

---

## 推荐目录结构（任选其一）
- 按阶段：
  - `Phase0_M0/`
  - `Phase1_Excel/`
- 按步骤ID：
  - `P0-12/`
  - `P1-03/`
- 按日期：
  - `2026-01-20/`

---

## 推荐命名
- `YYYY-MM-DD_Px-yy_说明.png`
- `YYYY-MM-DD_Px-yy_log_excerpt.txt`
- `YYYY-MM-DD_Px-yy_sql.txt`


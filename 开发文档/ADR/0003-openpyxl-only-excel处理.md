# ADR-0003: Excel 处理采用 openpyxl-only，业务层统一 List[Dict]

- **状态**：已采纳
- **日期**：2026-01-10（项目启动）
- **决策者**：项目负责人

## 背景

系统需要大量 Excel 导入导出功能（批次、工艺路线、人员技能、设备停机等）。需要选定 Excel 处理库。

## 决策

- V1 仅使用 openpyxl 3.0.10 处理 Excel，不引入 pandas/numpy。
- 业务层统一使用 `List[Dict[str, Any]]` 作为数据交换格式。
- 通过 `TabularBackend` 抽象接口解耦，V1 实现 `OpenpyxlBackend`，预留 `PandasBackend` 扩展点。

## 理由

- 减少依赖数量，降低 Win7 打包风险（pandas 依赖链长）。
- `List[Dict]` 是 Python 原生结构，不绑定任何第三方库。
- Backend 抽象使未来迁移到 pandas 时无需修改业务代码。

## 被拒绝的替代方案

- 直接使用 pandas：依赖链长（pandas -> numpy -> ...），Win7 兼容风险高。
- 业务层使用 DataFrame：绑定实现库，违反依赖反转原则。

## 后果

- 业务代码禁止出现 `import pandas`、`DataFrame` 等。
- 大数据量场景性能可能不如 pandas，但 V1 数据量（千级批次）足够。
- 未来引入 pandas 只需实现新的 Backend，不改业务层。

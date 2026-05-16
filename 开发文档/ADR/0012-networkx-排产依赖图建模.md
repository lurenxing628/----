# ADR-0012: NetworkX 用于排产依赖图建模

- **状态**：已采纳
- **日期**：2026-05-16
- **版本锁定**：networkx==3.1
- **环境约束**：Windows 7 x64 + Python 3.8.x
- **关联路线图**：`.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-roadmap.md`

## 背景

当前 APS 排产主链已经支持批次、工序、设备、人员、日历、外协、冻结窗口、SGS 派工、自动分配、`summary/result_summary` 和 `OperationLogs` 留痕。后续需要更清楚地分析工序之间的前后依赖、环、拓扑层级、关键路径和影响范围。

本次引入 NetworkX 的目的不是替代现有排产算法，而是在现有算法旁边增加一层内部图分析能力。第一阶段只做 report 模式，分析并写摘要，不改变排产结果。

## 决策

引入 NetworkX 作为排产工序依赖图的内部分析引擎，版本锁定为：

```text
networkx==3.1
```

NetworkX 3.1 是最后一个支持 Python 3.8 的 NetworkX 版本。

## 引入目的

- 工序依赖图建模。
- 环检测。
- 拓扑排序。
- 拓扑层级分析。
- 关键路径分析。
- 工序影响范围分析。
- 后续 ready 队列生成。
- 后续可选资源匹配分析。

## 非目标

- 不替代现有贪心排产算法。
- 不在第一阶段改变排产结果。
- 不引入 OR-Tools 作为本次图分析方案。
- 不引入 NumPy、SciPy、Pandas、Matplotlib、pydot、pygraphviz。
- 不安装 `networkx[default]`。
- 不安装 `networkx[all]`。
- 不使用 NetworkX drawing/layout 功能。
- 不暴露 `nx.Graph` / `nx.DiGraph` 给 Controller、页面、数据库、Excel 导出层。
- 不把完整节点边明细写入 OperationLogs。
- 不在第一版做前端图展示。
- 不在第一版做最小费用流精排。

## 架构边界

- NetworkX 仅限 `core/services/scheduler/graph/` 内部使用。
- 对外只返回 dataclass、dict、`List[Dict]` 和 JSON 可序列化结构。
- `graph_analysis_mode=off` 时，不要求环境安装 NetworkX。
- `graph_analysis_mode=report/on` 时，才检查 NetworkX 是否存在且版本为 3.1。
- 图模块不得把数据库连接、Repository、模型原对象、datetime 原对象或 NetworkX 对象放入 `result_summary`。
- 写入 JSON 前必须转换为可序列化结构。

## 接入策略

### 第一阶段：report 模式

只做分析和记录，不改变排产结果。

允许：

- 读取本次排产输入。
- 读取本次优化结果。
- 构建内部 `nx.DiGraph`。
- 计算图指标。
- 写入 `result_summary["algo"]["graph_analysis"]` 小摘要。
- 写入 `result_summary["diagnostics"]["graph_analysis"]` 采样诊断。

禁止：

- 改变 `algo_ops_to_schedule`。
- 改变排序。
- 改变 SGS 候选集合。
- 改变 `seed_results`。
- 改变冻结窗口语义。
- 改变 `schedule_rows`。
- 把完整 nodes/edges 写入 OperationLogs。

### 第二阶段：on 模式

在配置显式开启后，图 ready 队列可以参与候选工序筛选。

### 第三阶段：评分接入

关键路径、影响范围和后续关键分钟可以作为 SGS 评分分量，但必须保留现有交期、优先级、批次顺序、工序顺序和资源约束语义。

## result_summary 边界

公开摘要：

```text
result_summary["algo"]["graph_analysis"]
```

只放用户可见小摘要，例如：

```json
{
  "mode": "report",
  "status": "available",
  "node_count": 120,
  "edge_count": 118,
  "is_dag": true,
  "critical_path_minutes": 960,
  "warning_count": 0
}
```

内部诊断：

```text
result_summary["diagnostics"]["graph_analysis"]
```

只放采样诊断，例如：

```json
{
  "topological_order_sample": ["op:1", "op:2", "op:3"],
  "critical_path": ["op:1", "op:2", "op:3"],
  "cycle_edges": [],
  "warnings": []
}
```

OperationLogs 只允许记录小摘要，不允许写完整节点和完整边。

## 依赖策略

阶段 0 不修改主 `requirements.txt`，也不把 NetworkX 安装进当前项目 venv。阶段 0 只保存 before_networkx 依赖和排产结果基线。

可选依赖从阶段 1 开始放入独立文件：

```text
requirements-optimizer-lite-win7.txt
```

内容锁定：

```text
networkx==3.1
```

不得使用：

```text
networkx[default]
networkx[all]
```

如果需要在阶段 0 做兼容探针，只允许使用隔离临时 venv，且不得覆盖 `evidence/baseline_pip_freeze_before_networkx.txt`。

## Python 3.8 代码约束

生产代码必须继续兼容 Python 3.8：

- 使用 `List[str]`，不使用 `list[str]`。
- 使用 `Optional[str]`，不使用 `str | None`。
- 使用 `Dict[str, Any]`。
- 使用 `from typing import Any`。
- 写入 JSON 的 datetime 必须先转字符串。
- 调用 `topological_sort` / `dag_longest_path` 前必须确认是 DAG。
- 不能把 NetworkX 底层异常直接抛给页面。

## 回滚策略

如果依赖验证失败：

- 不修改 `requirements.txt`。
- 保持 `graph_analysis_mode=off`。
- 不启用 report/on 模式。

如果 report 模式导致排产结果与阶段 0 基线不一致：

- 立即关闭 `graph_analysis_mode`。
- 保留阶段 0 基线作为回归证据。
- 回退 report 接入点，不影响现有贪心排产主链。

如果 OperationLogs 或 `result_summary` 被图明细撑大：

- 收紧摘要采样。
- 移除完整节点边输出。
- 历史 `result_summary` 走兼容解析，不直接删除历史数据。

## 后果

正面影响：

- 可以在不改变排产结果的前提下分析工序依赖图。
- 后续可以逐步把 ready 队列和关键路径评分纳入 SGS。
- 可通过阶段 0 基线证明 report 模式是只读旁路。

代价：

- 新增一个可选依赖。
- 需要维护 Win7/Python 3.8 兼容验证。
- 需要严格控制 `result_summary` 和 OperationLogs 的体积。

---
doc_type: roadmap
slug: networkx-scheduler-graph-introduction
status: active
created: 2026-05-08
last_reviewed: 2026-05-16
tags: [scheduler, graph, networkx, win7, python38]
related_requirements: []
related_architecture: [.codestable/architecture/ARCHITECTURE.md]
---

# NetworkX 排产工序图分析引入路线

## 背景

这份文档用于后续直接照着改仓库。它承接原始方案里的全部执行细节，并把已经核实到的当前仓库事实补进去。

这次导入 NetworkX，不是为了马上替代现有排产算法，而是先给现有算法加一层“图分析能力”。大白话说，就是先把工序之间“谁必须在谁前面”“哪条链最长”“哪道工序一拖会拖多少后续工序”算清楚，先只写报告，不动现在的排产结果。等证明稳定之后，再逐步让它参与候选工序队列、关键路径评分和资源匹配。

当前仓库有几条硬约束必须从一开始就写死：

- 当前目标仍是 Windows 7 x64 离线场景，开发和打包仍按 Python 3.8 口径处理。
- 主 `requirements.txt` 仍是轻量运行依赖，当前明确是 Flask + openpyxl + python-dateutil，没有 NumPy、Pandas、SciPy 这类重依赖。
- 排产主链已经拆到 `core/services/scheduler/run/` 和 `core/algorithms/greedy/`；不能再按旧的大文件想象去改。
- 现有排产已经有 `readiness_gate_enabled`、冻结窗口 `seed_results`、SGS 智能派工、批次顺序派工、summary/result_summary 合同、OperationLogs 审计摘要等语义，新图分析不能把这些绕开。
- `nx.DiGraph` 只能留在图分析模块内部，不能流到 Controller、页面、数据库、Excel 导出层。

## 官方资料复核

已按 2026-05-08 复核 NetworkX 官方资料：

- NetworkX 3.1 发布说明写明支持 Python 3.8、3.9、3.10、3.11，并且它是最后一个支持 Python 3.8 的 NetworkX 版本。来源：[NetworkX 3.1 release notes](https://networkx.org/documentation/stable/release/release_3.1.html)。
- NetworkX 官方安装页把 `pip install networkx[default]` 和 `pip install networkx` 区分开；如果不想安装 NumPy、SciPy 等额外依赖，可以只安装 `networkx`。来源：[NetworkX install docs](https://networkx.org/documentation/stable/install.html)。
- DAG 相关能力包括 `is_directed_acyclic_graph`、`topological_sort`、`topological_generations`、`ancestors`、`descendants`、`dag_longest_path`、`dag_longest_path_length`。来源：[Directed Acyclic Graphs](https://networkx.org/documentation/stable/reference/algorithms/dag.html)。
- `topological_sort` 只适用于有向无环图；如果不是 DAG，会抛 `NetworkXUnfeasible`。来源：[topological_sort](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.topological_sort.html)。
- `dag_longest_path` 使用边上的 `weight` 属性来算 DAG 最长路径，所以本项目需要把“工序节点时长”转换成“进入该节点的边权重”。来源：[dag_longest_path](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.dag_longest_path.html)。
- 二分图最大匹配可以用 `nx.bipartite.maximum_matching`；返回字典会同时包含左右两侧映射，所以业务层要只保留工序侧映射。来源：[Bipartite algorithms](https://networkx.org/documentation/stable/reference/algorithms/bipartite.html)。
- `min_cost_flow` 是后续增强，不放第一版；官方也提醒浮点权重/需求可能有溢出和舍入问题，必要时要转成整数成本。来源：[min_cost_flow](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.min_cost_flow.html)。

## 当前仓库事实

### 现有排产主链

当前排产从服务入口到算法大致是：

```text
core/services/scheduler/schedule_service.py
  ScheduleService.run_schedule()
    ↓
  _run_schedule_impl()
    ↓
core/services/scheduler/run/schedule_input_collector.py
  collect_schedule_run_input()
    ↓
core/services/scheduler/run/schedule_orchestrator.py
  orchestrate_schedule_run()
    ↓
core/services/scheduler/run/schedule_optimizer.py
  optimize_schedule()
    ↓
core/algorithms/greedy/scheduler.py
  GreedyScheduler.schedule()
    ↓
core/algorithms/greedy/scheduler.py
  _run_dispatch()
    ↓
core/algorithms/greedy/dispatch/batch_order.py
  dispatch_batch_order()
或
core/algorithms/greedy/dispatch/sgs.py
  dispatch_sgs()
```

所以第一轮 `report` 模式最安全的接入点不是排产循环内部，而是：

```text
core/services/scheduler/run/schedule_orchestrator.py
  orchestrate_schedule_run()
```

更具体地说，是 `optimizer_outcome` 已经算完、`SummaryBuildContext` 还没组装之前。这个位置已经拿得到完整输入和完整结果，但还没有写摘要、落库、返回页面。只读分析放这里，最不容易改变排产结果。

### 现有数据字段

当前原始批次工序模型 `BatchOperation` 的关键字段是：

```text
id
op_code
batch_id
piece_id
seq
op_type_id
op_type_name
source
machine_id
operator_id
supplier_id
setup_hours
unit_hours
ext_days
status
created_at
```

真正喂给算法的对象是 `OpForScheduleAlgo`，在 `core/services/scheduler/run/schedule_input_builder.py` 中定义，关键字段是：

```text
id
op_code
batch_id
seq
op_type_id
op_type_name
source
machine_id
operator_id
supplier_id
setup_hours
unit_hours
ext_days
ext_group_id
ext_merge_mode
ext_group_total_days
merge_context_degraded
merge_context_events
```

当前 `Batch` 的关键字段是：

```text
batch_id
part_no
part_name
quantity
due_date
priority
ready_status
ready_date
status
remark
created_at
updated_at
```

所以图输入文档里的字段要按当前仓库修正：

- 使用 `source`，不要把正式字段写成 `source_type`。
- 当前没有 `planned_minutes` 字段，也没有算法输入自带的 `proc_hours` 字段。
- 自制工序耗时要由 `setup_hours + unit_hours * Batch.quantity` 得到总小时，再换算分钟。
- 普通外协耗时用 `ext_days`。
- 合并外协组耗时用 `ext_group_total_days`。
- `machine_id` / `operator_id` 是固定资源字段；候选资源来自 `resource_pool`，不是单个工序自带字段。

### 外协组合并事实

外协组合并不是直接存在 `BatchOperation` 表字段里。当前代码会通过 `Batch.part_no + BatchOperation.seq` 回查 `PartOperation`，再通过 `PartOperation.ext_group_id` 找 `ExternalGroup`。

对图分析来说，第一版不需要把外协组合并压成一个图节点。更稳的做法是：

- 仍然按每道工序建节点。
- 同一批次内按 `seq` 建 `prev -> next` 依赖边。
- 如果某道外协工序处于有效合并组内，节点上带 `ext_group_id`、`ext_merge_mode`、`ext_group_total_days`。
- `ext_merge_mode == "merged"` 且 `ext_group_id` 有效时，组内工序共享同一个 `(batch_id, ext_group_id)` 时间块。
- 普通外协或合并上下文降级时，用单道 `ext_days`；非严格模式下空外协天数仍沿用当前算法默认 1 天的语义，不在图模块另造新默认值。

### 配置链路事实

图分析配置要走当前配置系统，不建议只写环境变量。要新增的主字段建议叫：

```text
graph_analysis_mode
graph_block_on_cycle
graph_critical_weight
graph_impact_weight
graph_debug_export
```

需要同步的位置包括：

- `core/services/scheduler/config/config_field_spec.py`：新增 `_FIELD_SPECS`。
- `core/services/scheduler/config/config_snapshot.py`：新增 `ScheduleConfigSnapshot` 字段和 `to_dict()` 输出。
- `core/services/scheduler/config/config_constants.py`：同步 `CONFIG_PAGE_FIELDS` / `CONFIG_PAGE_WRITE_FIELDS`。
- `web/routes/domains/scheduler/scheduler_config_display_state.py`：同步页面可见配置字段。
- `web/routes/domains/scheduler/scheduler_config.py`：表单收集要能读到新字段。
- `core/models/schedule_config_runtime_fields.py` 和 `core/models/schedule_config_runtime_snapshot.py`：同步旧运行期兼容层。

### result_summary 和 OperationLogs 边界

图分析摘要建议写两层：

```text
result_summary["algo"]["graph_analysis"]
  放用户可见的小摘要。

result_summary["diagnostics"]["graph_analysis"]
  放诊断采样和内部统计。
```

OperationLogs 不适合写完整图分析。它是“谁做了什么”的审计留痕，不是排产结果明细仓库。OperationLogs 里最多放小摘要：

```text
graph_analysis_mode
graph_analysis_status
node_count
edge_count
warning_count
time_cost_ms
```

不要把全部节点、全部边、完整关键路径诊断都塞进 OperationLogs。否则每次排产日志会被图明细撑大，页面日志也会变慢。

### Python 3.8 写法边界

生产代码必须继续兼容 Python 3.8：

- 用 `List[str]`，不要用 `list[str]`。
- 用 `Optional[str]`，不要用 `str | None`。
- 用 `Dict[str, Any]`，不要把 JSON 结构写成难读的 `Dict[str, object]`。
- 代码里用了 `Any` 必须 `from typing import Any`。
- 写进 JSON 的 `datetime` 必须先转字符串，例如 `dt.isoformat()`。
- `dag_longest_path`、`topological_sort` 调用前必须先确认图是 DAG；不是 DAG 时返回业务可读 warning 或错误，不能把 NetworkX 底层异常直接丢给页面。

## 总目标

最终目标分四级：

```text
第 1 级：只构建工序依赖图，不改变排产结果
第 2 级：做环检测、拓扑排序、关键路径、影响范围分析，并写入日志/摘要
第 3 级：ready 队列参与排产，保证后工序不会排到前工序前面
第 4 级：关键路径、后续影响范围、资源匹配结果进入评分函数
```

大白话就是：

```text
先知道哪些活能干；
再知道哪些活最危险；
再知道这个活会拖多少后续工序；
最后再决定先排谁。
```

## 范围

本路线图覆盖：

- 引入 `networkx==3.1` 的依赖边界。
- Win7 + Python 3.8.10 + 离线 wheel + PyInstaller 4.10 的验证步骤。
- `core/services/scheduler/graph/` 内部图分析模块设计。
- 图输入数据结构、节点 ID、工序依赖边、环检测、拓扑排序、关键路径、影响范围、ready 队列、资源匹配。
- report 模式接入到 `ScheduleHistory.result_summary`。
- on 模式逐步接入 SGS 候选队列和候选评分。
- 新增测试、性能记录、打包验证、回滚点。

本路线图明确不做：

- 不马上替代现有贪心排产算法。
- 不马上让 NetworkX 进入主 `requirements.txt`。
- 不安装 `networkx[default]`。
- 不引入 NumPy、SciPy、Pandas、Matplotlib、pydot、pygraphviz。
- 不使用 NetworkX drawing / layout 功能。
- 不把 `nx.Graph` / `nx.DiGraph` 暴露给 Controller、页面、数据库、Excel 导出层。
- 不在第一版做前端图展示。
- 不在第一版做最小费用流精排。
- 不新增静默兜底、宽泛 fallback、宽泛吞错。
- 不改变 `readiness_gate_enabled=False` 时齐套和齐套日期不影响排产的语义。
- 不把冻结窗口 `seed_results` 里的工序重新放回待排候选队列。
- 不把 `gantt_critical_chain` 展示链路误当成排产评分链路。

## 整体执行顺序

建议分 13 个 PR 或小阶段推进。每个阶段都能单独提交，方便回滚。

| 阶段 | 目标 | 是否改变排产结果 | 风险 |
| -: | --- | ---: | -: |
| 0 | 建分支、记录基线、落 ADR 和依赖决策 | 否 | 很低 |
| 1 | 加可选依赖文件、安装验证和离线 wheel 流程 | 否 | 很低 |
| 2 | 加配置开关和迁移，默认 off | 否 | 低 |
| 3 | 建目录和 NetworkX 懒加载层 | 否 | 低 |
| 4 | 定义图输入数据结构和节点 ID 规范 | 否 | 低 |
| 5 | 实现工序依赖图构建 | 否 | 低 |
| 6 | 实现图校验：环、孤立、重复 seq | 否 | 低 |
| 7 | 实现指标：拓扑顺序、层级、关键路径、影响范围 | 否 | 低 |
| 8 | 接入 report 模式，写 result_summary 小摘要 | 否 | 低 |
| 9 | 调试导出和性能记录 | 否 | 低 |
| 10 | ready 队列参与 SGS 候选 | 是 | 中 |
| 11 | 关键路径评分参与 SGS 打分 | 是 | 中 |
| 12 | 资源匹配 report-only 分析 | 部分 | 中 |
| 13 | 打包、离线、回归、验收、归档 | 否/可控 | 中 |

## 阶段 0：建分支、记录 before_networkx 基线、落 ADR

阶段 0 只做“引入前”的决策和证据留痕，不安装 NetworkX，不新增图分析代码，也不改变任何排产业务逻辑。

### 0.0 阶段目标

```text
1. 建立独立分支，保护当前主线。
2. 记录未引入 NetworkX 前的 Git、Python、pip freeze、关键配置和核心文件 hash。
3. 用 3 组代表性排产案例保存可对比 JSON。
4. 落地 ADR-0012，明确 NetworkX 只作为内部图分析引擎、版本锁定、Win7/Python 3.8 边界和非目标。
5. 不修改 requirements.txt。
6. 不把 networkx 安装进当前项目 venv；如需兼容探针，只允许隔离临时 venv。
```

### 0.1 工作树保护与分支

先检查当前工作树：

```bash
git status --short --branch
```

验收规则：

```text
1. 如果工作树干净，可以直接建分支。
2. 如果有无关改动，不要 stash、不要 reset、不要删除。
3. 先记录当前状态，并让负责人确认是否继续。
```

保存状态证据：

```bash
mkdir -p evidence/scheduler_baseline
git status --short --branch > evidence/scheduler_baseline/00_git_status_before_networkx.txt
git rev-parse HEAD > evidence/scheduler_baseline/00_git_commit_before_networkx.txt
```

建分支：

```bash
git switch -c feature/networkx-scheduler-graph
# 或旧 Git：git checkout -b feature/networkx-scheduler-graph
```

验收：

```text
当前分支不是 main。
git status --short --branch 能看到 feature/networkx-scheduler-graph 或 codex/networkx-scheduler-graph。
工作树里已有的无关改动不被误删、不被重置。
```

### 0.2 Python、pip freeze 与文件 hash 基线

必须在安装 NetworkX 之前执行：

```bash
python --version | tee evidence/scheduler_baseline/01_python_version_before_networkx.txt
python -c "import sys; print(sys.version)" > evidence/scheduler_baseline/01_python_full_version_before_networkx.txt
python -m pip freeze > evidence/baseline_pip_freeze_before_networkx.txt
cp evidence/baseline_pip_freeze_before_networkx.txt evidence/scheduler_baseline/02_pip_freeze_before_networkx.txt
```

如果当前命令行默认 Python 不是项目/打包口径 Python 3.8.x，必须优先使用项目 venv 或打包机 Python 再生成正式基线；默认 Python 版本可以另存为辅助证据，但不能冒充 Win7/Python 3.8 基线。

检查当前环境是否已含 NetworkX 或重依赖：

```bash
grep -i "networkx" evidence/baseline_pip_freeze_before_networkx.txt || true
grep -Ei "numpy|scipy|matplotlib|pandas" evidence/baseline_pip_freeze_before_networkx.txt || true
python - <<'PY'
try:
    import networkx  # noqa
except Exception:
    print("OK: current env has no networkx")
else:
    print("WARN: current env already has networkx; phase0 baseline must record this explicitly")
PY
```

记录关键文件 hash：

```bash
python - <<'PY'
import hashlib
from pathlib import Path

paths = [
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "schema.sql",
]

out = []
for item in paths:
    p = Path(item)
    if not p.exists():
        out.append(f"{item}	MISSING")
        continue
    out.append(f"{item}	sha256={hashlib.sha256(p.read_bytes()).hexdigest()}")

Path("evidence/scheduler_baseline/03_core_file_hashes_before_networkx.txt").write_text(
    "
".join(out) + "
",
    encoding="utf-8",
)
PY
```

验收：

```text
evidence/baseline_pip_freeze_before_networkx.txt 存在。
evidence/scheduler_baseline/02_pip_freeze_before_networkx.txt 存在。
evidence/scheduler_baseline/03_core_file_hashes_before_networkx.txt 存在。
requirements.txt 的 hash 在阶段 0 后不应变化。
纯净基线中不应出现 networkx；如果开发机已有 networkx，必须在 README 中标注该 freeze 不是纯净打包环境证据。
```

### 0.3 阶段 0 禁止事项

阶段 0 明确不做：

```text
[ ] 不安装 networkx 到当前项目 venv
[ ] 不新增 requirements-optimizer-lite-win7.txt
[ ] 不修改 requirements.txt
[ ] 不新增 core/services/scheduler/graph/
[ ] 不改 schedule_orchestrator.py
[ ] 不改 schedule_optimizer.py
[ ] 不改 schedule_persistence.py
[ ] 不新增迁移
[ ] 不新增配置字段
[ ] 不改页面
[ ] 不跑 PyInstaller 打包
```

原因：阶段 0 是 before_networkx 证据采集阶段。如果先安装依赖或改排产代码，后续就无法证明 report 模式没有改变原排产结果。

例外：如果负责人坚持阶段 0 就做 NetworkX 兼容探针，必须使用临时隔离 venv，不能污染当前项目 venv：

```bash
python -m venv /tmp/aps_nx_probe_py38
/tmp/aps_nx_probe_py38/bin/python -m pip install "networkx==3.1"
/tmp/aps_nx_probe_py38/bin/python -c "import networkx as nx; print(nx.__version__); assert nx.__version__ == '3.1'"
rm -rf /tmp/aps_nx_probe_py38
```

### 0.4 三组排产基线

基线原则：

```text
1. 每组使用固定 batch_ids。
2. 每组使用固定 start_dt。
3. 每组使用固定排产配置。
4. 避免使用 improve 随机搜索模式作为精确对比基线。
5. 禁用 freeze_window，除非该案例专门用于冻结窗口。
6. 使用复制库或临时库，不要直接污染生产库。
7. simulate=True 也会写 Schedule / ScheduleHistory / OperationLogs，因此仍然会改变 DB；必须使用复制库。
```

推荐三组：

```text
case_001_normal：普通内部排产。至少 1~2 个 ready=yes 的普通批次，工序均为 internal，machine_id/operator_id 已明确，不依赖 auto_assign。
case_002_urgent：急件/优先级案例。至少 2 个批次，一个 urgent/critical，一个 normal，资源有竞争，freeze_window=no。
case_003_external：含外协案例。至少 1 个含 external 工序的批次，内部前后工序资源明确，记录 ext_group 事实。
```

推荐输出：

```text
evidence/scheduler_baseline/case_001_normal_result.json
evidence/scheduler_baseline/case_002_urgent_result.json
evidence/scheduler_baseline/case_003_external_result.json
```

每个 JSON 至少包含：

```json
{
  "baseline_schema_version": "networkx_phase0_scheduler_baseline.v1",
  "case_id": "case_001_normal",
  "created_at": "2026-05-16T...",
  "repo": {
    "branch": "feature/networkx-scheduler-graph",
    "commit": "...",
    "dirty_status": "..."
  },
  "python": {
    "version": "3.8.x"
  },
  "run_input": {
    "batch_ids": ["B001", "B002"],
    "start_dt": "2026-02-02 08:00:00",
    "simulate": true,
    "created_by": "networkx_phase0"
  },
  "config": {
    "algo_mode": "greedy",
    "strategy": "due_date_first",
    "dispatch_mode": "batch_order",
    "dispatch_rule": "slack",
    "auto_assign_enabled": "no",
    "freeze_window": "no"
  },
  "run_return": {},
  "schedule_rows": [],
  "history": {
    "version": 1,
    "strategy": "due_date_first",
    "result_status": "success",
    "result_summary_core": {}
  },
  "operation_log": {
    "action": "simulate",
    "target_id": "1",
    "detail_core": {}
  },
  "future_compare_ignore": [
    "repo.dirty_status",
    "run_return.version",
    "schedule_rows[].version",
    "history.version",
    "history.result_summary_core.time_cost_ms",
    "operation_log.id",
    "operation_log.detail_core.time_cost_ms",
    "history.result_summary_core.algo.graph_analysis",
    "history.result_summary_core.diagnostics.graph_analysis"
  ]
}
```

后续 report 模式必须严格比较：

```text
op_id
batch_id
op_code
seq
source
machine_id
operator_id
supplier_id
start_time
end_time
lock_status
```

不比较：

```text
version
time_cost_ms
ScheduleHistory.id
OperationLogs.id
新增 graph_analysis 字段
```

### 0.5 阶段 0 可新增的只读/留痕工具

允许新增：

```text
tools/capture_networkx_phase0_baseline.py
```

它只用于基线采集，不接触业务主链，不 import NetworkX，不新增图分析模块。职责：

```text
1. 按环境变量读取复制库路径、case 参数和配置。
2. 在复制库上设置确定性配置：algo_mode=greedy、freeze_window=no、指定 strategy/dispatch/auto_assign。
3. 调用 ScheduleService.run_schedule(simulate=True)。
4. 查询本次 version 的 Schedule / ScheduleHistory / OperationLogs。
5. 输出 case_xxx_result.json。
```

### 0.6 基线目录结构

阶段 0 完成后建议得到：

```text
evidence/
├── baseline_pip_freeze_before_networkx.txt
└── scheduler_baseline/
    ├── 00_git_status_before_networkx.txt
    ├── 00_git_commit_before_networkx.txt
    ├── 01_python_version_before_networkx.txt
    ├── 01_python_full_version_before_networkx.txt
    ├── 02_pip_freeze_before_networkx.txt
    ├── 03_core_file_hashes_before_networkx.txt
    ├── README.md
    ├── case_001_normal_result.json
    ├── case_002_urgent_result.json
    └── case_003_external_result.json
```

`README.md` 必须写明捕获时间、目的、对比规则、三组案例和环境告警：如果当前开发环境已装 NetworkX 或 Python 不是 3.8.x，必须显式标注。

### 0.7 ADR-0012

新增文件：

```text
开发文档/ADR/0012-networkx-排产依赖图建模.md
```

ADR 必须明确：

```text
- 状态：已采纳
- 版本锁定：networkx==3.1
- NetworkX 3.1 是最后一个支持 Python 3.8 的 NetworkX 版本
- Windows 7 x64 + Python 3.8.x 环境约束
- NetworkX 只作为 core/services/scheduler/graph/ 内部图分析引擎
- 第一阶段 report 模式只写摘要，不改变排产结果
- graph_analysis_mode=off 时不要求安装 NetworkX
- 不安装 networkx[default] / networkx[all]
- 不引入 NumPy、SciPy、Pandas、Matplotlib、pydot、pygraphviz
- 不暴露 nx.Graph / nx.DiGraph 到 Controller、页面、数据库、Excel 导出层
- result_summary["algo"]["graph_analysis"] 只放用户可见小摘要
- result_summary["diagnostics"]["graph_analysis"] 只放采样诊断
- OperationLogs 只写小摘要，不写完整 nodes/edges
```

验收：

```bash
test -f "开发文档/ADR/0012-networkx-排产依赖图建模.md"
grep -q "networkx==3.1" "开发文档/ADR/0012-networkx-排产依赖图建模.md"
grep -q "networkx\[default\]" "开发文档/ADR/0012-networkx-排产依赖图建模.md"
grep -q "不暴露" "开发文档/ADR/0012-networkx-排产依赖图建模.md"
grep -q "graph_analysis_mode=off" "开发文档/ADR/0012-networkx-排产依赖图建模.md"
```

### 0.8 阶段 0 自检与 Definition of Done

```text
[ ] 当前分支不是 main
[ ] git status 已在 evidence/scheduler_baseline/00_git_status_before_networkx.txt 留痕
[ ] 当前 commit 已在 evidence/scheduler_baseline/00_git_commit_before_networkx.txt 留痕
[ ] Python 版本已记录，且正式基线使用 Python 3.8.x 或明确标注开发机差异
[ ] pip freeze 已在安装 NetworkX 前记录
[ ] requirements.txt 未修改
[ ] 未新增 NetworkX 到主运行依赖
[ ] 三组排产基线 JSON 已生成并可 json.loads
[ ] 三组基线均包含 schedule_rows
[ ] 基线 comparison ignore 规则已写清
[ ] ADR-0012 已创建
[ ] ADR 明确 networkx==3.1
[ ] ADR 明确不安装 networkx[default]
[ ] ADR 明确不暴露 nx.DiGraph
[ ] ADR 明确 graph_analysis_mode=off 时不要求安装 NetworkX
[ ] ADR 明确 report 模式不改变排产结果
[ ] ADR 明确 OperationLogs 只写小摘要
[ ] 未改排产主链代码
[ ] 未新增 graph 模块
[ ] 未新增迁移
```

变更范围理想情况下只应出现：

```text
开发文档/ADR/0012-networkx-排产依赖图建模.md
evidence/baseline_pip_freeze_before_networkx.txt
evidence/scheduler_baseline/...
```

如果决定新增基线捕获工具，则额外允许：

```text
tools/capture_networkx_phase0_baseline.py
```

不应出现：

```text
requirements.txt
requirements-optimizer-lite-win7.txt
core/services/scheduler/run/schedule_orchestrator.py
core/services/scheduler/run/schedule_optimizer.py
core/services/scheduler/run/schedule_persistence.py
core/services/scheduler/graph/
schema.sql
```

## 阶段 1：依赖导入与安装验证，但先不改主 requirements

### 1.1 新增可选依赖文件

新增文件：

```text
requirements-optimizer-lite-win7.txt
```

内容：

```txt
# Windows 7 x64 + Python 3.8.10
# NetworkX 3.1 is the last NetworkX release supporting Python 3.8.
# Do not install networkx[default]; keep this optional dependency pure Python and lightweight.
networkx==3.1
```

暂时不要改：

```text
requirements.txt
```

原因：

```text
当前主线交付仍是轻量运行依赖。
第一阶段只让 NetworkX 做可选旁路分析。
等 report 模式稳定后，再决定是否把它合并进主 requirements。
```

### 1.2 本机安装验证

阶段 1 才允许做 NetworkX 安装验证。执行前必须确认阶段 0 的 `baseline_pip_freeze_before_networkx.txt` 和三组排产 JSON 已经落盘。

推荐先使用隔离临时 venv 验证，避免污染当前项目 venv：

```bash
python -m venv /tmp/aps_nx_probe_py38
/tmp/aps_nx_probe_py38/bin/python -m pip install -r requirements-optimizer-lite-win7.txt
/tmp/aps_nx_probe_py38/bin/python -c "import networkx as nx; print(nx.__version__); assert nx.__version__ == '3.1'"
/tmp/aps_nx_probe_py38/bin/python -m pip check
rm -rf /tmp/aps_nx_probe_py38
```

如需在项目 venv 安装，必须另存 after_networkx 的 pip freeze，不能覆盖 before_networkx 基线：

```bash
python -m pip install -r requirements-optimizer-lite-win7.txt
python -c "import networkx as nx; print(nx.__version__); assert nx.__version__ == '3.1'"
python -m pip check
python -m pip freeze > evidence/baseline_pip_freeze_after_networkx.txt
```

验收：

```text
输出 3.1。
无 ImportError。
无 DLL load failed。
python -m pip check 通过。
baseline_pip_freeze_before_networkx.txt 未被覆盖。
```

NetworkX 不是 OR-Tools 那类 C++ 求解器绑定；它是用于创建、操作和研究复杂网络结构的 Python 包。`networkx==3.1` 支持 Python 3.8，并且是最后一个支持 Python 3.8 的版本，所以它比直接上 OR-Tools 更适合先做轻量图分析试点。

### 1.3 离线 wheel 准备

在有网机器上执行：

```bat
mkdir vendor\wheels
python -m pip download --only-binary=:all: --dest vendor\wheels networkx==3.1
```

在离线 Win7/Python 3.8.10 机器上执行：

```bat
python -m pip install --no-index --find-links=vendor\wheels networkx==3.1
python -c "import networkx as nx; print(nx.__version__)"
```

验收：

```text
vendor/wheels 中存在 networkx-3.1-py3-none-any.whl。
记录该 whl 文件名和 SHA256。
离线安装成功。
输出 3.1。
```

### 1.4 先不要安装 extras

不要执行：

```bat
pip install networkx[default]
pip install networkx[all]
```

只执行：

```bat
pip install networkx==3.1
```

原因：

```text
当前目标是保持 Win7 交付轻量。
不要顺手带入 NumPy、SciPy、Matplotlib、pydot、pygraphviz 等额外依赖。
```

## 阶段 2：加配置开关和迁移

### 2.1 配置字段

原始方案使用了环境变量风格：

```python
APS_SCHEDULER_GRAPH_ANALYSIS = "off"
APS_SCHEDULER_GRAPH_BLOCK_ON_CYCLE = "no"
APS_SCHEDULER_GRAPH_CRITICAL_WEIGHT = 500
APS_SCHEDULER_GRAPH_IMPACT_WEIGHT = 10
APS_SCHEDULER_GRAPH_DEBUG_EXPORT = "no"
```

当前仓库更合适的做法是走排产配置快照字段：

```text
graph_analysis_mode:
  off     完全不用 NetworkX
  report  只分析，不改变排产结果
  on      参与排产

graph_block_on_cycle:
  no      有环只记录警告
  yes     有环直接阻止排产

graph_critical_weight:
  关键路径加分权重

graph_impact_weight:
  后续影响范围加分权重

graph_debug_export:
  是否输出图 JSON 调试文件
```

第一版默认：

```text
graph_analysis_mode=off
graph_block_on_cycle=no
graph_critical_weight=500
graph_impact_weight=10
graph_debug_export=no
```

等 report 模式稳定后可改成：

```text
graph_analysis_mode=report
```

最终成熟后才考虑：

```text
graph_analysis_mode=on
graph_block_on_cycle=yes
```

### 2.2 需要同步的文件

新增配置字段时，至少同步：

```text
core/services/scheduler/config/config_field_spec.py
core/services/scheduler/config/config_snapshot.py
core/services/scheduler/config/config_constants.py
core/models/schedule_config_runtime_fields.py
core/models/schedule_config_runtime_snapshot.py
web/routes/domains/scheduler/scheduler_config.py
web/routes/domains/scheduler/scheduler_config_display_state.py
```

### 2.3 迁移建议

当前配置默认行不是直接写死在 `schema.sql` 里，但老库可能已有 `ScheduleConfig` 和 preset JSON。建议新增迁移：

```text
core/infrastructure/migrations/v9.py
```

迁移职责：

```text
给已有非空库插入或补齐 graph_analysis_mode=off。
补齐 graph_block_on_cycle=no。
补齐 graph_critical_weight=500。
补齐 graph_impact_weight=10。
补齐 graph_debug_export=no。
修补 preset.* JSON，避免老库页面显示“配置缺失/已降级”。
```

同时更新：

```text
core/infrastructure/migration_state.py
core/infrastructure/migrations/__init__.py
schema.sql
```

验收：

```text
默认 off 时，系统不需要安装 NetworkX 也能启动。
默认 off 时，现有排产结果不变。
旧库迁移后页面能看到默认 off。
配置页面选择 report/on 后能进入 snapshot。
配置字段同步测试通过。
```

## 阶段 3：建目录结构和懒加载层

### 3.1 新增目录

新增目录：

```text
core/services/scheduler/graph/
```

新增文件：

```text
core/services/scheduler/graph/__init__.py
core/services/scheduler/graph/nx_runtime.py
core/services/scheduler/graph/types.py
core/services/scheduler/graph/id_policy.py
core/services/scheduler/graph/input_adapter.py
core/services/scheduler/graph/precedence_builder.py
core/services/scheduler/graph/validators.py
core/services/scheduler/graph/metrics.py
core/services/scheduler/graph/ready_queue.py
core/services/scheduler/graph/scoring.py
core/services/scheduler/graph/resource_matching.py
core/services/scheduler/graph/exporter.py
core/services/scheduler/graph/analysis_service.py
```

每个文件职责：

```text
nx_runtime.py          NetworkX 懒加载，避免 mode=off 时启动失败
types.py               图输入/输出 dataclass
id_policy.py           节点 ID 规范
input_adapter.py       把现有算法输入对象转成图节点
precedence_builder.py  构建工序依赖图
validators.py          环检测、孤立节点、重复 seq 检查
metrics.py             拓扑顺序、层级、关键路径、影响范围
ready_queue.py         当前可排工序计算
scoring.py             图指标转 SGS 打分加成
resource_matching.py   二分图资源匹配，后续增强
exporter.py            图转 JSON/dict
analysis_service.py    统一服务入口
```

验收：

```text
目录和文件全部存在。
此时还不接入排产服务。
运行现有测试应全部通过。
core/services/scheduler/graph 外部没有直接 import networkx。
```

### 3.2 新建 nx_runtime.py

```python
from __future__ import annotations

import importlib
from typing import Any


_EXPECTED_VERSION = "3.1"


class NetworkXUnavailable(RuntimeError):
    pass


def import_networkx() -> Any:
    """
    懒加载 NetworkX。

    目的：
    - graph_analysis=off 时，不要求环境安装 networkx
    - graph_analysis=report/on 时，再检查 networkx 是否存在
    """
    try:
        nx = importlib.import_module("networkx")
    except Exception as exc:
        raise NetworkXUnavailable(
            "缺少可选依赖 networkx==3.1；请先安装 requirements-optimizer-lite-win7.txt"
        ) from exc

    version = str(getattr(nx, "__version__", "") or "").strip()
    if version != _EXPECTED_VERSION:
        raise NetworkXUnavailable(
            "NetworkX 版本不兼容：当前 {}，期望 {}".format(version or "unknown", _EXPECTED_VERSION)
        )

    return nx
```

### 3.3 为什么不用顶层 import

不要在这些文件最顶层写：

```python
import networkx as nx
```

第一阶段都通过：

```python
nx = import_networkx()
```

这样做的原因是：

```text
mode=off 时，即使现场没安装 networkx，也不影响主程序启动。
mode=report/on 时，才要求依赖存在。
```

这也符合仓库里“可选重依赖不要顶层 import”的基本思路。

### 3.4 测试

新增：

```text
tests/scheduler_graph/test_nx_runtime.py
```

测试点：

```python
def test_import_networkx_version():
    from core.services.scheduler.graph.nx_runtime import import_networkx

    nx = import_networkx()
    assert nx.__version__ == "3.1"
```

还要补一个不依赖 NetworkX 的启动合同测试：

```text
graph_analysis_mode=off 时，不 import networkx，也不调用 import_networkx()
```

验收：

```text
安装 networkx==3.1 时测试通过。
未安装 networkx 且 graph_analysis=off 时系统仍能启动。
```

## 阶段 4：定义节点 ID 和图输入/输出数据结构

### 4.1 新建 id_policy.py

```python
from __future__ import annotations

from typing import Any


def make_operation_node_id(batch_id: str, op_code: str, row_id: Any = None) -> str:
    """
    生成工序图节点 ID。

    优先使用 BatchOperations.id。
    如果没有 row_id，则使用 batch_id + op_code。
    """
    if row_id is not None and str(row_id).strip():
        return "op:{}".format(row_id)

    return "op:{}:{}".format(str(batch_id).strip(), str(op_code).strip())


def make_machine_node_id(machine_id: str) -> str:
    return "machine:{}".format(str(machine_id).strip())


def make_operator_node_id(operator_id: str) -> str:
    return "operator:{}".format(str(operator_id).strip())


def display_id(node_id: str) -> str:
    """
    把内部节点 ID 转回更容易看的形式。
    """
    if node_id.startswith("op:"):
        return node_id[3:]
    if node_id.startswith("machine:"):
        return node_id[8:]
    if node_id.startswith("operator:"):
        return node_id[9:]
    return node_id
```

节点 ID 原则：

```text
工序节点：op:<BatchOperations.id>
设备节点：machine:<machine_id>
人员节点：operator:<operator_id>
```

如果暂时没有数据库 `id`，才退回：

```text
op:<batch_id>:<op_code>
```

注意：

```text
row_id 为 None、空字符串、0、False 时，不应该当成有效数据库主键。
如果后续沿用 SGS 的 positive id 语义，bool 也不能被当成 id。
```

测试：

```python
def test_make_operation_node_id_with_row_id():
    assert make_operation_node_id("B001", "B001_10", 123) == "op:123"


def test_make_operation_node_id_without_row_id():
    assert make_operation_node_id("B001", "B001_10") == "op:B001:B001_10"


def test_machine_node_id():
    assert make_machine_node_id("CNC-01") == "machine:CNC-01"
```

验收：

```text
所有节点 ID 都带类型前缀。
工序/设备/人员不会混淆。
```

### 4.2 新建 types.py

字段按当前仓库修正后建议这样写：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OperationGraphNode:
    node_id: str
    batch_id: str
    op_code: str
    seq: int
    name: str
    duration_minutes: int
    part_no: Optional[str] = None
    priority: str = "normal"
    source: str = "internal"  # internal / external
    status: str = "pending"
    due_date: Optional[str] = None
    op_type_id: Optional[str] = None
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    supplier_id: Optional[str] = None
    ext_group_id: Optional[str] = None
    ext_merge_mode: str = ""
    ext_group_total_days: Optional[float] = None
    merge_context_degraded: bool = False
    candidate_machine_ids: List[str] = field(default_factory=list)
    candidate_operator_ids: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OperationGraphEdge:
    from_node_id: str
    to_node_id: str
    kind: str = "precedence"  # precedence / external_lag / explicit
    lag_minutes: int = 0
    note: str = ""


@dataclass
class GraphWarning:
    code: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphAnalysisSummary:
    node_count: int
    edge_count: int
    is_dag: bool
    cycle_edges: List[Dict[str, Any]]
    topological_order: List[str]
    critical_path: List[str]
    critical_path_minutes: int
    warnings: List[GraphWarning]
```

字段解释：

```text
node_id:
  图内部唯一 ID。

batch_id:
  批次号。

op_code:
  展示用工序编码，例如 B001_10。

seq:
  工序顺序号。

duration_minutes:
  图分析用的预计时长，关键路径计算需要。
  该字段是 adapter 派生结果，不是当前 BatchOperation 原始字段。

source:
  internal / external。

candidate_machine_ids:
  候选设备，用于后续资源匹配，来自 resource_pool。

candidate_operator_ids:
  候选人员，用于后续双资源匹配，来自 resource_pool。

raw:
  原始业务数据快照，只放 JSON 可序列化字段。
```

注意事项：

```text
types.py 不 import networkx。
不要把数据库连接、repo、模型原对象、datetime 原对象、NetworkX 对象放进 raw。
raw 必须能 json.dumps(..., ensure_ascii=False)。
```

验收：

```text
types.py 不 import networkx。
所有 dataclass 都是业务友好的纯 Python 结构。
Python 3.8 下类型注解通过 ruff/pyright。
```

## 阶段 5：把现有业务数据转成图节点

### 5.1 新建 input_adapter.py

第一版不要一上来绑定数据库 repo。输入可以支持两种：

```text
List[OpForScheduleAlgo] + batches map
List[Dict[str, Any]] + batches map
```

核心目标是把现有算法输入转成 `OperationGraphNode`。

建议代码：

```python
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .id_policy import make_operation_node_id
from .types import OperationGraphNode


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _text(value: Any) -> str:
    return str(value or "").strip()


def _batch_quantity(batch: Any) -> float:
    if batch is None:
        return 0.0
    if isinstance(batch, dict):
        return _as_float(batch.get("quantity"), 0.0)
    return _as_float(getattr(batch, "quantity", None), 0.0)


def _batch_field(batch: Any, field: str, default: Any = None) -> Any:
    if batch is None:
        return default
    if isinstance(batch, dict):
        return batch.get(field, default)
    return getattr(batch, field, default)


def _row_field(row: Any, field: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(field, default)
    return getattr(row, field, default)


def _duration_minutes(row: Any, batch: Any) -> int:
    source = _text(_row_field(row, "source", "internal")).lower() or "internal"
    if source == "external":
        merge_mode = _text(_row_field(row, "ext_merge_mode", "")).lower()
        group_days = _as_float(_row_field(row, "ext_group_total_days", None), 0.0)
        ext_days = _as_float(_row_field(row, "ext_days", None), 0.0)
        days = group_days if merge_mode == "merged" and group_days > 0 else ext_days
        return int(round(max(days, 0.0) * 24 * 60))

    setup_hours = _as_float(_row_field(row, "setup_hours", 0.0), 0.0)
    unit_hours = _as_float(_row_field(row, "unit_hours", 0.0), 0.0)
    quantity = _batch_quantity(batch)
    return int(round(max(setup_hours + unit_hours * quantity, 0.0) * 60))


def build_operation_nodes_from_rows(
    rows: Iterable[Any],
    *,
    batches: Optional[Dict[str, Any]] = None,
    resource_pool: Optional[Dict[str, Any]] = None,
) -> List[OperationGraphNode]:
    result: List[OperationGraphNode] = []
    batches = dict(batches or {})
    resource_pool = dict(resource_pool or {})
    machines_by_op_type = dict(resource_pool.get("machines_by_op_type") or {})

    for row in rows:
        batch_id = _text(_row_field(row, "batch_id"))
        op_code = _text(_row_field(row, "op_code"))
        row_id = _row_field(row, "id")
        batch = batches.get(batch_id)

        node_id = make_operation_node_id(batch_id=batch_id, op_code=op_code, row_id=row_id)
        op_type_id = _text(_row_field(row, "op_type_id", "")) or None
        source = _text(_row_field(row, "source", "internal")).lower() or "internal"
        machine_id = _text(_row_field(row, "machine_id", "")) or None
        operator_id = _text(_row_field(row, "operator_id", "")) or None

        candidate_machine_ids = []
        if machine_id:
            candidate_machine_ids.append(machine_id)
        elif op_type_id:
            candidate_machine_ids.extend([_text(item) for item in machines_by_op_type.get(op_type_id, []) if _text(item)])

        node = OperationGraphNode(
            node_id=node_id,
            batch_id=batch_id,
            op_code=op_code,
            seq=_as_int(_row_field(row, "seq"), 0),
            name=_text(_row_field(row, "op_type_name", "")),
            duration_minutes=_duration_minutes(row, batch),
            part_no=_text(_batch_field(batch, "part_no", "")) or None,
            priority=_text(_batch_field(batch, "priority", "normal")) or "normal",
            source=source,
            status=_text(_row_field(row, "status", "pending")) or "pending",
            due_date=_text(_batch_field(batch, "due_date", "")) or None,
            op_type_id=op_type_id,
            machine_id=machine_id,
            operator_id=operator_id,
            supplier_id=_text(_row_field(row, "supplier_id", "")) or None,
            ext_group_id=_text(_row_field(row, "ext_group_id", "")) or None,
            ext_merge_mode=_text(_row_field(row, "ext_merge_mode", "")),
            ext_group_total_days=(
                _as_float(_row_field(row, "ext_group_total_days", None), 0.0)
                if _row_field(row, "ext_group_total_days", None) not in (None, "")
                else None
            ),
            merge_context_degraded=bool(_row_field(row, "merge_context_degraded", False)),
            candidate_machine_ids=list(dict.fromkeys(candidate_machine_ids)),
            candidate_operator_ids=[operator_id] if operator_id else [],
            raw={
                "id": row_id,
                "batch_id": batch_id,
                "op_code": op_code,
                "seq": _row_field(row, "seq"),
                "source": source,
                "op_type_id": op_type_id,
                "ext_group_id": _text(_row_field(row, "ext_group_id", "")) or None,
                "ext_merge_mode": _text(_row_field(row, "ext_merge_mode", "")),
            },
        )
        result.append(node)

    return result
```

### 5.2 验收数据样例

输入：

```python
rows = [
    {
        "id": 1,
        "batch_id": "B001",
        "op_code": "B001_10",
        "seq": 10,
        "op_type_name": "下料",
        "source": "internal",
        "setup_hours": 1,
        "unit_hours": 0.5,
    },
    {
        "id": 2,
        "batch_id": "B001",
        "op_code": "B001_20",
        "seq": 20,
        "op_type_name": "外协热处理",
        "source": "external",
        "ext_days": 2,
    },
]
batches = {"B001": {"batch_id": "B001", "quantity": 10, "priority": "normal", "due_date": "2026-05-20"}}
```

期望：

```text
生成 2 个 OperationGraphNode。
node_id 分别为 op:1、op:2。
第一道自制工序 duration_minutes = (1 + 0.5 * 10) * 60 = 360。
第二道外协工序 duration_minutes = 2 * 24 * 60 = 2880。
source 分别为 internal、external。
```

### 5.3 测试文件

新增：

```text
tests/scheduler_graph/test_input_adapter.py
```

验收：

```text
空时长不会报错，转成 0。
缺 source 时默认 internal。
缺 priority 时默认 normal。
自制工序按 setup_hours + unit_hours * batch.quantity 算分钟。
普通外协按 ext_days 算分钟。
merged 外协按 ext_group_total_days 算分钟。
raw 能 json.dumps。
```

## 阶段 6：构建工序依赖图

### 6.1 新建 precedence_builder.py

第一版只做最稳的：同一批次内按 `seq` 串成线性工艺路线。

```python
from __future__ import annotations

from typing import Iterable, List

from .nx_runtime import import_networkx
from .types import OperationGraphEdge, OperationGraphNode


def build_linear_edges_by_batch(nodes: Iterable[OperationGraphNode]) -> List[OperationGraphEdge]:
    grouped = {}

    for node in nodes:
        grouped.setdefault(node.batch_id, []).append(node)

    edges: List[OperationGraphEdge] = []

    for batch_id, batch_nodes in grouped.items():
        ordered = sorted(batch_nodes, key=lambda item: (item.seq, item.op_code, item.node_id))

        for prev_node, next_node in zip(ordered, ordered[1:]):
            kind = "precedence"
            if prev_node.source == "external":
                kind = "external_lag"

            edges.append(
                OperationGraphEdge(
                    from_node_id=prev_node.node_id,
                    to_node_id=next_node.node_id,
                    kind=kind,
                    lag_minutes=0,
                    note="batch={} seq {} -> {}".format(batch_id, prev_node.seq, next_node.seq),
                )
            )

    return edges


def build_precedence_graph(
    nodes: Iterable[OperationGraphNode],
    edges: Iterable[OperationGraphEdge],
):
    nx = import_networkx()
    graph = nx.DiGraph()

    for node in nodes:
        graph.add_node(
            node.node_id,
            batch_id=node.batch_id,
            op_code=node.op_code,
            seq=node.seq,
            name=node.name,
            duration_minutes=node.duration_minutes,
            part_no=node.part_no,
            priority=node.priority,
            source=node.source,
            status=node.status,
            due_date=node.due_date,
            op_type_id=node.op_type_id,
            machine_id=node.machine_id,
            operator_id=node.operator_id,
            supplier_id=node.supplier_id,
            ext_group_id=node.ext_group_id,
            ext_merge_mode=node.ext_merge_mode,
            ext_group_total_days=node.ext_group_total_days,
            merge_context_degraded=node.merge_context_degraded,
            candidate_machine_ids=list(node.candidate_machine_ids),
            candidate_operator_ids=list(node.candidate_operator_ids),
            raw=dict(node.raw),
        )

    for edge in edges:
        graph.add_edge(
            edge.from_node_id,
            edge.to_node_id,
            kind=edge.kind,
            lag_minutes=edge.lag_minutes,
            note=edge.note,
        )

    return graph
```

### 6.2 测试

新增：

```text
tests/scheduler_graph/test_precedence_builder.py
```

测试 1：单批次线性

```text
B001_10 -> B001_20 -> B001_30
```

期望：

```text
3 个节点。
2 条边。
边方向正确。
```

测试 2：两个批次互不相连

```text
B001_10 -> B001_20
B002_10 -> B002_20
```

期望：

```text
4 个节点。
2 条边。
B001 不连到 B002。
```

测试 3：外部工序边类型

```text
B001_10 internal
B001_20 external
B001_30 internal
```

期望：

```text
B001_20 -> B001_30 的边 kind = external_lag。
```

验收：

```text
第一版只表达同批次 seq 前后依赖。
不引入跨批次依赖。
不把资源冲突当成 precedence 边。
```

## 阶段 7：图校验

### 7.1 新建 validators.py

```python
from __future__ import annotations

from typing import Any, Dict, List

from .nx_runtime import import_networkx
from .types import GraphWarning


def find_cycle_edges(graph) -> List[Dict[str, Any]]:
    nx = import_networkx()

    try:
        cycle = nx.find_cycle(graph, orientation="original")
    except nx.NetworkXNoCycle:
        return []

    result = []
    for item in cycle:
        u = item[0]
        v = item[1]
        result.append(
            {
                "from": u,
                "to": v,
                "from_op_code": graph.nodes[u].get("op_code", u),
                "to_op_code": graph.nodes[v].get("op_code", v),
            }
        )
    return result


def is_dag(graph) -> bool:
    nx = import_networkx()
    return bool(nx.is_directed_acyclic_graph(graph))


def find_isolated_nodes(graph) -> List[str]:
    return [
        node_id
        for node_id in graph.nodes
        if graph.in_degree(node_id) == 0 and graph.out_degree(node_id) == 0
    ]


def find_duplicate_seq_warnings(graph) -> List[GraphWarning]:
    grouped = {}

    for node_id, data in graph.nodes(data=True):
        key = (data.get("batch_id"), data.get("seq"))
        grouped.setdefault(key, []).append(node_id)

    warnings = []
    for key, node_ids in grouped.items():
        batch_id, seq = key
        if batch_id and seq is not None and len(node_ids) > 1:
            warnings.append(
                GraphWarning(
                    code="DUPLICATE_SEQ",
                    message="同一批次存在重复工序顺序号：batch_id={}, seq={}".format(batch_id, seq),
                    data={"batch_id": batch_id, "seq": seq, "node_ids": node_ids},
                )
            )

    return warnings


def collect_graph_warnings(graph) -> List[GraphWarning]:
    warnings: List[GraphWarning] = []

    for node_id in find_isolated_nodes(graph):
        data = graph.nodes[node_id]
        warnings.append(
            GraphWarning(
                code="ISOLATED_OPERATION",
                message="发现孤立工序：{}".format(data.get("op_code", node_id)),
                data={"node_id": node_id, "op_code": data.get("op_code")},
            )
        )

    warnings.extend(find_duplicate_seq_warnings(graph))

    return warnings
```

### 7.2 测试

新增：

```text
tests/scheduler_graph/test_validators.py
```

测试 1：无环

```text
A -> B -> C
```

期望：

```text
is_dag=True
cycle_edges=[]
```

测试 2：有环

```text
A -> B -> C -> A
```

期望：

```text
is_dag=False
cycle_edges 非空。
```

测试 3：孤立节点

```text
A
B -> C
```

期望：

```text
A 被识别为孤立节点。
```

测试 4：同批次重复 seq

```text
B001 seq=10
B001 seq=10
```

期望：

```text
出现 DUPLICATE_SEQ warning。
```

验收：

```text
NetworkX 的 topological_sort 只对 DAG 有效。
调用拓扑排序和关键路径前必须先做 DAG 校验。
有环时不能继续算关键路径。
```

## 阶段 8：拓扑排序、层级、关键路径、影响范围

### 8.1 在 metrics.py 写基础指标

```python
from __future__ import annotations

from typing import Dict, List, Set, Tuple

from .nx_runtime import import_networkx


def get_topological_order(graph) -> List[str]:
    nx = import_networkx()
    return list(nx.topological_sort(graph))


def get_topological_generations(graph) -> List[List[str]]:
    nx = import_networkx()
    return [list(group) for group in nx.topological_generations(graph)]


def get_generation_index(graph) -> Dict[str, int]:
    result: Dict[str, int] = {}

    for index, group in enumerate(get_topological_generations(graph)):
        for node_id in group:
            result[node_id] = index

    return result
```

含义：

```text
topological_order:
  给出一个合法的工序顺序。

topological_generations:
  给出“第几层工序”。
  第 0 层是没有前置的工序。
  第 1 层是只依赖第 0 层的工序。
```

官方定义里，拓扑排序要求如果有边 `u -> v`，那么 `u` 必须出现在 `v` 前面；这刚好对应“前工序必须早于后工序”。

### 8.2 关键路径计算

NetworkX 的 `dag_longest_path` 是按边权重算最长路径。当前工时在“工序节点”上，所以要把节点工时转成边权重。

在 `metrics.py` 里新增：

```python
def _duration_of(graph, node_id: str) -> int:
    return int(graph.nodes[node_id].get("duration_minutes", 0) or 0)


def build_duration_weighted_graph(graph):
    nx = import_networkx()

    weighted = nx.DiGraph()
    source = "__SOURCE__"

    weighted.add_node(source)

    for node_id, data in graph.nodes(data=True):
        weighted.add_node(node_id, **dict(data))

    for node_id in graph.nodes:
        if graph.in_degree(node_id) == 0:
            weighted.add_edge(source, node_id, weight=_duration_of(graph, node_id))

    for u, v, data in graph.edges(data=True):
        lag_minutes = int(data.get("lag_minutes", 0) or 0)
        weighted.add_edge(u, v, weight=_duration_of(graph, v) + lag_minutes)

    return weighted


def get_critical_path(graph) -> Tuple[List[str], int]:
    nx = import_networkx()

    weighted = build_duration_weighted_graph(graph)

    path = nx.dag_longest_path(weighted, weight="weight")
    minutes = nx.dag_longest_path_length(weighted, weight="weight")

    path = [node_id for node_id in path if node_id != "__SOURCE__"]

    return path, int(minutes)
```

验收：

```text
关键路径计算只在 DAG 图上执行。
有环时不计算关键路径，只返回 warning。
```

### 8.3 影响范围计算

在 `metrics.py` 新增：

```python
def get_upstream_operations(graph, node_id: str) -> Set[str]:
    nx = import_networkx()
    return set(nx.ancestors(graph, node_id))


def get_downstream_operations(graph, node_id: str) -> Set[str]:
    nx = import_networkx()
    return set(nx.descendants(graph, node_id))


def get_impact_count(graph, node_id: str) -> int:
    return len(get_downstream_operations(graph, node_id))


def get_downstream_critical_minutes(graph, node_id: str) -> int:
    nx = import_networkx()

    node_ids = {node_id}
    node_ids.update(nx.descendants(graph, node_id))

    subgraph = graph.subgraph(node_ids).copy()
    _path, minutes = get_critical_path(subgraph)
    return int(minutes)


def build_node_metrics(graph):
    critical_path, _critical_minutes = get_critical_path(graph)
    critical_set = set(critical_path)
    generation_index = get_generation_index(graph)

    result = {}

    for node_id in graph.nodes:
        result[node_id] = {
            "is_on_critical_path": node_id in critical_set,
            "impact_count": get_impact_count(graph, node_id),
            "generation_index": generation_index.get(node_id, 0),
            "downstream_critical_minutes": get_downstream_critical_minutes(graph, node_id),
        }

    return result
```

含义：

```text
upstream:
  这个工序前面欠了哪些工序。

downstream:
  这个工序后面影响哪些工序。

impact_count:
  这个工序会影响多少道后续工序。

downstream_critical_minutes:
  从这个工序开始，后面最长还要多久。
```

性能提醒：

```text
get_downstream_critical_minutes 对每个节点都算一次子图关键路径，2000 节点时可能变慢。
第一版性能如果超过目标，可以先只算 critical_path、impact_count、generation_index。
downstream_critical_minutes 留到后续优化。
```

### 8.4 测试

新增：

```text
tests/scheduler_graph/test_metrics_topology.py
tests/scheduler_graph/test_metrics_critical_path.py
tests/scheduler_graph/test_metrics_impact.py
```

拓扑测试：

```text
A -> B -> C

期望：
topological_order = [A, B, C]
generation_index[A] = 0
generation_index[B] = 1
generation_index[C] = 2
```

并行层级测试：

```text
A -> C
B -> C

期望：
A 和 B 都在第 0 层
C 在第 1 层
```

关键路径线性测试：

```text
A(10) -> B(20) -> C(30)

期望：
critical_path = [A, B, C]
critical_path_minutes = 60
```

关键路径分叉测试：

```text
A(10) -> B(100) -> D(10)
A(10) -> C(20)  -> D(10)

期望：
critical_path = [A, B, D]
critical_path_minutes = 120
```

外协等待测试：

```text
A(10) -> B(20), edge lag_minutes=1440

期望：
critical_path_minutes = 1470
```

影响范围测试：

```text
A -> B -> C
A -> D

期望：
A downstream = {B, C, D}
B downstream = {C}
C downstream = {}
A impact_count = 3
```

## 阶段 9：图导出和统一分析服务入口

### 9.1 新建 exporter.py

```python
from __future__ import annotations

from typing import Any, Dict, List


def graph_to_plain_dict(graph) -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    for node_id, data in graph.nodes(data=True):
        item = dict(data)
        item["id"] = node_id
        nodes.append(item)

    for u, v, data in graph.edges(data=True):
        item = dict(data)
        item["from"] = u
        item["to"] = v
        edges.append(item)

    return {
        "nodes": nodes,
        "edges": edges,
    }


def graph_summary_to_dict(summary) -> Dict[str, Any]:
    return {
        "node_count": summary.node_count,
        "edge_count": summary.edge_count,
        "is_dag": summary.is_dag,
        "cycle_edges": summary.cycle_edges,
        "topological_order": summary.topological_order,
        "critical_path": summary.critical_path,
        "critical_path_minutes": summary.critical_path_minutes,
        "warnings": [
            {
                "code": warning.code,
                "message": warning.message,
                "data": warning.data,
            }
            for warning in summary.warnings
        ],
    }
```

测试：

```python
import json

payload = graph_to_plain_dict(graph)
json.dumps(payload, ensure_ascii=False)
```

验收：

```text
能 json.dumps。
不包含 nx.DiGraph 对象。
不包含 datetime 原对象。
不包含数据库连接对象。
不包含元组 key。
```

### 9.2 新建 analysis_service.py

```python
from __future__ import annotations

from typing import Iterable, Tuple

from .metrics import get_critical_path, get_topological_order
from .precedence_builder import build_linear_edges_by_batch, build_precedence_graph
from .types import GraphAnalysisSummary, GraphWarning, OperationGraphNode
from .validators import collect_graph_warnings, find_cycle_edges, is_dag


class ScheduleGraphAnalysisService:
    """
    工序图分析服务。

    对外不暴露 NetworkX。
    """

    def build_graph_for_linear_batches(
        self,
        nodes: Iterable[OperationGraphNode],
    ):
        node_list = list(nodes)
        edges = build_linear_edges_by_batch(node_list)
        return build_precedence_graph(node_list, edges)

    def analyze_linear_batches(
        self,
        nodes: Iterable[OperationGraphNode],
    ) -> Tuple[object, GraphAnalysisSummary]:
        graph = self.build_graph_for_linear_batches(nodes)

        cycle_edges = find_cycle_edges(graph)
        dag_ok = is_dag(graph)

        warnings = collect_graph_warnings(graph)

        topological_order = []
        critical_path = []
        critical_path_minutes = 0

        if dag_ok:
            topological_order = get_topological_order(graph)
            critical_path, critical_path_minutes = get_critical_path(graph)
        else:
            warnings.append(
                GraphWarning(
                    code="GRAPH_HAS_CYCLE",
                    message="工序依赖图存在循环，无法计算拓扑顺序和关键路径。",
                    data={"cycle_edges": cycle_edges},
                )
            )

        summary = GraphAnalysisSummary(
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
            is_dag=dag_ok,
            cycle_edges=cycle_edges,
            topological_order=topological_order,
            critical_path=critical_path,
            critical_path_minutes=critical_path_minutes,
            warnings=warnings,
        )

        return graph, summary
```

验收：

```text
业务层只需要调用 ScheduleGraphAnalysisService。
除 core/services/scheduler/graph/ 外，其他核心业务文件不直接 import networkx。
```

## 阶段 10：接入 report 模式，不改变排产结果

### 10.1 接入原则

这是最重要的低风险接入点。

`report` 模式只能：

```text
读取 schedule_input.algo_ops_to_schedule。
读取 schedule_input.batches。
读取 schedule_input.resource_pool。
生成 graph_analysis 摘要。
写入 result_summary 和小日志摘要。
```

`report` 模式不能：

```text
改变 sorted_ops。
改变 batch_order。
改变 dispatch_sgs 候选集合。
改变 SGS 评分。
改变 seed_results。
改变冻结窗口。
改变落库 schedule_rows。
```

### 10.2 在排产入口加旁路分析

当前仓库建议放在：

```text
core/services/scheduler/run/schedule_orchestrator.py
  orchestrate_schedule_run()
```

伪代码：

```python
def maybe_analyze_schedule_graph(schedule_input, graph_mode: str):
    if graph_mode not in ("report", "on"):
        return None

    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
    from core.services.scheduler.graph.exporter import graph_summary_to_dict
    from core.services.scheduler.graph.input_adapter import build_operation_nodes_from_rows

    nodes = build_operation_nodes_from_rows(
        schedule_input.algo_ops_to_schedule,
        batches=schedule_input.batches,
        resource_pool=schedule_input.resource_pool,
    )
    service = ScheduleGraphAnalysisService()
    _graph, summary = service.analyze_linear_batches(nodes)

    return graph_summary_to_dict(summary)
```

接入时要把 `graph_analysis` 带进 `SummaryBuildContext`，然后由 summary 组装层放入：

```text
result_summary["algo"]["graph_analysis"]
result_summary["diagnostics"]["graph_analysis"]
```

### 10.3 写入 result_summary

公开小摘要建议：

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

诊断采样建议：

```json
{
  "topological_order_sample": ["op:1", "op:2", "op:3"],
  "critical_path": ["op:1", "op:2", "op:3"],
  "cycle_edges": [],
  "warnings": []
}
```

注意：

```text
result_summary 有 size guard，诊断信息要采样。
OperationLogs 只放小摘要，不放完整节点边。
```

### 10.4 report 模式验收

对阶段 0 保存的三个 case 重新跑：

```text
graph_analysis_mode=report
```

验收：

```text
case_001 排产结果与 baseline 完全一致。
case_002 排产结果与 baseline 完全一致。
case_003 排产结果与 baseline 完全一致。

但 result_summary["algo"]["graph_analysis"] 里多了图分析小摘要。
diagnostics.graph_analysis 里有采样诊断。
OperationLogs 只有小摘要，不包含完整 nodes/edges。
```

如果这一步排产结果变了，说明图分析误接入了算法，应立即回退。

## 阶段 11：有环时的处理策略

### 11.1 report 模式

```text
发现有环：
  只记录 warning。
  不阻止排产。
  不改变结果。
  不计算拓扑顺序。
  不计算关键路径。
```

### 11.2 on 模式

当：

```text
graph_analysis_mode=on
graph_block_on_cycle=yes
```

发现有环时：

```python
if graph_analysis["is_dag"] is False and block_on_cycle:
    raise ValidationError(
        "工序依赖存在循环，无法排产。",
        field="graph_analysis",
    )
```

错误 details 建议：

```python
exc.details = {
    "reason": "schedule_graph_cycle",
    "cycle_edges": graph_analysis["cycle_edges"],
}
```

用户看到的文案建议：

```text
工序依赖存在循环，无法排产：
B001_20 -> B001_30 -> B001_20
```

不要只显示：

```text
Graph has cycle
```

验收：

```text
report 模式：有环只提示。
on + block=yes：有环阻止排产。
on + block=no：有环不阻止，但不能使用拓扑/关键路径评分。
```

## 阶段 12：ready 队列参与排产

这一阶段开始改变排产行为，所以必须在 `graph_analysis_mode=on` 之后才启用。

### 12.1 新建 ready_queue.py

```python
from __future__ import annotations

from typing import Iterable, List, Set


def get_ready_operations(
    graph,
    unscheduled_node_ids: Iterable[str],
    completed_or_scheduled_node_ids: Iterable[str],
) -> List[str]:
    unscheduled: Set[str] = set(unscheduled_node_ids)
    done: Set[str] = set(completed_or_scheduled_node_ids)

    ready = []

    for node_id in unscheduled:
        predecessors = set(graph.predecessors(node_id))
        if predecessors.issubset(done):
            ready.append(node_id)

    return ready
```

### 12.2 当前仓库接入点

当前 SGS 的候选收集在：

```text
core/algorithms/greedy/dispatch/sgs_scoring.py
  _collect_sgs_candidates()
```

它现在的 ready 语义是：

```text
每个批次只拿下一道工序。
```

不是完整 DAG ready 队列。所以文档和实现都不能直接说“现有就是 DAG ready”。应当写成：

```text
在 graph_analysis_mode=on 时，把现有 SGS 候选队列改造成图 ready 队列。
ready 队列只决定“哪些工序有资格被选”。
具体选哪个，仍交给原来的排序/评分策略。
```

### 12.3 改造排产主循环的目标形态

原逻辑类似：

```python
for op in sorted_pending_ops:
    schedule(op)
```

或 SGS 当前类似：

```text
每轮从每个 batch 拿 next_idx 对应的下一道工序。
```

目标形态：

```python
unscheduled = set(all_node_ids)
scheduled = set(already_fixed_node_ids)

while unscheduled:
    ready_node_ids = get_ready_operations(
        graph=graph,
        unscheduled_node_ids=unscheduled,
        completed_or_scheduled_node_ids=scheduled,
    )

    if not ready_node_ids:
        raise ValidationError(
            "没有可排工序：可能存在循环依赖或前置工序状态异常。",
            field="graph_analysis",
        )

    selected_node_id = choose_best_ready_operation(ready_node_ids)
    schedule_one_operation(selected_node_id)

    unscheduled.remove(selected_node_id)
    scheduled.add(selected_node_id)
```

### 12.4 冻结窗口和 seed_results 注意点

这是当前仓库特别重要的边界：

```text
freeze_window 会先从上一版排程生成 seed_results。
冻结工序会从 algo_ops_to_schedule 里剔除。
图 ready 队列不能把冻结工序重新放回待排候选队列。
```

建议规则：

```text
待排节点：来自 schedule_input.algo_ops_to_schedule。
已固定节点：来自 seed_results / frozen_op_ids。
已固定节点可以作为前置已完成条件，但不能被再次排。
```

### 12.5 测试

新增：

```text
tests/scheduler_graph/test_ready_queue.py
```

测试 1：线性

```text
A -> B -> C
done = {}
ready = [A]
```

测试 2：

```text
done = {A}
ready = [B]
```

测试 3：

```text
done = {A, B}
ready = [C]
```

测试 4：输入顺序反过来

```text
输入顺序 C, B, A
依赖 A -> B -> C
```

期望：

```text
实际可排顺序仍然是 A, B, C。
```

测试 5：冻结窗口

```text
A -> B -> C
A 已在 seed_results / frozen_op_ids
unscheduled = {B, C}
done = {A}
ready = [B]
```

验收：

```text
graph_analysis_mode=report 时，不参与 ready 队列。
graph_analysis_mode=on 时，ready 队列不违反前后置。
冻结窗口 seed 工序不被重复排。
```

## 阶段 13：关键路径评分接入

### 13.1 新建 scoring.py

```python
from __future__ import annotations

from typing import Any, Dict


def graph_score_bonus(
    node_metric: Dict[str, Any],
    critical_weight: int = 500,
    impact_weight: int = 10,
    downstream_minutes_weight: int = 1,
) -> int:
    score = 0

    if node_metric.get("is_on_critical_path"):
        score += int(critical_weight)

    score += int(node_metric.get("impact_count", 0) or 0) * int(impact_weight)

    downstream_minutes = int(node_metric.get("downstream_critical_minutes", 0) or 0)
    score += downstream_minutes * int(downstream_minutes_weight)

    return int(score)
```

### 13.2 当前仓库接入点

当前 SGS 候选评分主入口：

```text
core/algorithms/greedy/dispatch/sgs.py
  _score_candidates()
  _score_candidate()
```

内外协分别进入：

```text
core/algorithms/greedy/dispatch/sgs_scoring.py
  _score_external_candidate()
  _score_internal_candidate()
```

最终排序 key 由：

```text
core/algorithms/dispatch_rules.py
  build_dispatch_key()
```

所以图分数不应该绕开 `build_dispatch_key()` 直接改 `batch_order`。更稳的方式是：

```text
先在 SGS 候选评分里拿到 node_metric。
把 graph_score_bonus 转成一个“越重要越靠前”的评分分量。
保持现有 SLACK / CR / ATC、换型、优先级、交期、批次顺序、工序顺序语义。
```

### 13.3 接入原评分函数

假设原来有：

```python
base_score = calc_priority_score(op) + calc_due_date_score(op)
```

改成：

```python
base_score = calc_priority_score(op) + calc_due_date_score(op)

if graph_mode == "on":
    node_metric = graph_metrics.get(node_id, {})
    base_score += graph_score_bonus(
        node_metric=node_metric,
        critical_weight=config.graph_critical_weight,
        impact_weight=config.graph_impact_weight,
    )
```

但当前仓库实际是 tuple key 越小越优先，所以实现时要注意方向。图 bonus 如果越大越优先，放进 tuple 前可能要转成负数：

```python
graph_priority = -float(graph_score_bonus(...))
dispatch_key = (graph_priority,) + tuple(existing_key)
```

这一步必须通过测试证明，不要靠感觉。

### 13.4 第一版权重建议

```text
critical_weight = 500
impact_weight = 10
downstream_minutes_weight = 1
```

这只是初值。上线前用历史案例调参。

### 13.5 测试

构造两个批次：

```text
批次 A：A1(10) -> A2(10)
批次 B：B1(10) -> B2(100) -> B3(10)
```

如果：

```text
A1 和 B1 同优先级、同交期、同状态
```

期望：

```text
B1 得分高于 A1。
```

因为 B1 后续关键工作量更长。

验收：

```text
graph_mode=report 时，评分不变。
graph_mode=on 时，关键路径工序得分更高。
所有评分明细能写入 diagnostics，便于解释为什么选它。
```

## 阶段 14：资源匹配第一版

这一步不是必须马上做，但如果要进一步优化设备/人员分配，可以用 NetworkX 二分图先做“可行匹配”。

第一版只做 report-only：

```text
ready 工序数量
最大可匹配数量
未匹配工序
瓶颈设备
```

不要马上用匹配结果改排产。

### 14.1 新建 resource_matching.py

```python
from __future__ import annotations

from typing import Dict, Iterable, List

from .id_policy import make_machine_node_id
from .nx_runtime import import_networkx


def build_operation_machine_graph(
    operation_node_ids: Iterable[str],
    operation_to_machine_ids: Dict[str, List[str]],
):
    nx = import_networkx()
    graph = nx.Graph()

    op_set = set(operation_node_ids)

    for op_node_id in op_set:
        graph.add_node(op_node_id, bipartite="operation")

        for machine_id in operation_to_machine_ids.get(op_node_id, []):
            machine_node_id = make_machine_node_id(machine_id)
            graph.add_node(machine_node_id, bipartite="machine")
            graph.add_edge(op_node_id, machine_node_id)

    return graph, op_set


def max_operation_machine_matching(
    operation_node_ids: Iterable[str],
    operation_to_machine_ids: Dict[str, List[str]],
) -> Dict[str, str]:
    nx = import_networkx()

    graph, op_set = build_operation_machine_graph(
        operation_node_ids=operation_node_ids,
        operation_to_machine_ids=operation_to_machine_ids,
    )

    matching = nx.bipartite.maximum_matching(graph, top_nodes=op_set)

    return {
        op_node_id: machine_node_id
        for op_node_id, machine_node_id in matching.items()
        if op_node_id in op_set
    }
```

### 14.2 测试

新增：

```text
tests/scheduler_graph/test_resource_matching.py
```

测试：

```text
O1 可用 M1, M2
O2 可用 M2
O3 可用 M2
```

期望：

```text
最多匹配 2 个工序。
不会把同一台机器同时分给多个工序。
返回值只保留工序侧映射。
```

## 阶段 15：最小费用流作为后续增强

如果后续要让资源选择考虑成本，例如：

```text
等待时间
换型惩罚
人员熟练度
设备负荷
急件惩罚
```

可以用 `min_cost_flow` 做小窗口局部优化。

但这一步放第二轮，因为它比 ready 队列和关键路径评分更容易引入行为变化。

第一轮只做：

```text
最大匹配分析
不做最小费用流排产
```

第二轮再做：

```text
某一天
某设备组
20~50 个 ready 工序
小窗口局部精排
```

注意：

```text
min_cost_flow 不建议用浮点权重。
如果要用等待时间、换型惩罚、人员熟练度，要转成整数成本。
```

## 阶段 16：调试输出

### 16.1 调试 JSON 文件

如果配置：

```text
graph_debug_export=yes
```

则每次排产输出：

```text
logs/schedule_graph/<schedule_id>_graph.json
logs/schedule_graph/<schedule_id>_summary.json
```

内容：

```json
{
  "node_count": 120,
  "edge_count": 118,
  "is_dag": true,
  "critical_path": ["op:1", "op:2", "op:3"],
  "critical_path_minutes": 960,
  "warnings": []
}
```

验收：

```text
debug_export=no 时不写文件。
debug_export=yes 时写入 logs/schedule_graph/。
文件能 json.loads。
不包含 nx.DiGraph。
不包含 datetime 原对象。
```

### 16.2 调试接口

可以后续加管理员接口：

```text
GET /admin/debug/schedule-graph/<schedule_id>
```

返回：

```json
{
  "summary": {},
  "nodes": [],
  "edges": []
}
```

验收：

```text
普通用户看不到该接口。
接口返回 JSON 可序列化。
不返回 nx.DiGraph。
```

## 阶段 17：测试目录完整规划

新增目录：

```text
tests/scheduler_graph/
```

完整文件：

```text
tests/scheduler_graph/test_nx_runtime.py
tests/scheduler_graph/test_id_policy.py
tests/scheduler_graph/test_input_adapter.py
tests/scheduler_graph/test_precedence_builder.py
tests/scheduler_graph/test_validators.py
tests/scheduler_graph/test_metrics_topology.py
tests/scheduler_graph/test_metrics_critical_path.py
tests/scheduler_graph/test_metrics_impact.py
tests/scheduler_graph/test_exporter.py
tests/scheduler_graph/test_analysis_service.py
tests/scheduler_graph/test_ready_queue.py
tests/scheduler_graph/test_resource_matching.py
```

核心回归测试建议放根层：

```text
tests/regression_scheduler_graph_config_contract.py
tests/regression_scheduler_graph_report_mode_contract.py
tests/regression_scheduler_graph_on_mode_contract.py
tests/regression_scheduler_graph_operation_logs_contract.py
tests/regression_scheduler_graph_summary_contract.py
tests/regression_scheduler_graph_migration_contract.py
```

原因：

```text
pytest 会收集 tests/ 子目录，所以 tests/scheduler_graph/ 是可行的。
但当前质量门禁关键测试清单多是显式列根层文件。
核心合同放根层更容易被后续维护者看到和加入门禁。
纯图算法样例放 tests/scheduler_graph/ 更清楚。
```

### 17.1 每个测试文件的核心用例

`test_nx_runtime.py`

```text
networkx==3.1 能加载。
版本不等于 3.1 时应报错。
graph_analysis=off 时不需要加载 networkx。
```

`test_id_policy.py`

```text
工序节点 ID 正确。
设备节点 ID 正确。
人员节点 ID 正确。
display_id 正确。
0/None/bool 不被误当成有效工序 row_id。
```

`test_input_adapter.py`

```text
dict 能转 OperationGraphNode。
OpForScheduleAlgo 能转 OperationGraphNode。
缺字段时使用默认值。
空工时转 0。
自制耗时按 setup_hours + unit_hours * quantity 算。
外协耗时按 ext_days 算。
merged 外协耗时按 ext_group_total_days 算。
raw 可 JSON 序列化。
```

`test_precedence_builder.py`

```text
单批次线性建边。
多批次不串线。
外部工序边 kind 正确。
```

`test_validators.py`

```text
无环图通过。
有环图识别。
孤立节点识别。
重复 seq warning。
```

`test_metrics_topology.py`

```text
拓扑顺序正确。
层级正确。
并行分支层级正确。
```

`test_metrics_critical_path.py`

```text
线性关键路径。
并行关键路径。
外协 lag 计入关键路径。
有环图不算关键路径。
```

`test_metrics_impact.py`

```text
upstream 正确。
downstream 正确。
impact_count 正确。
downstream_critical_minutes 正确。
```

`test_exporter.py`

```text
graph_to_plain_dict 可 JSON 序列化。
summary 可 JSON 序列化。
不包含 NetworkX 对象。
```

`test_analysis_service.py`

```text
analyze_linear_batches 返回 graph + summary。
有环时 summary.is_dag=False。
无环时有 critical_path。
```

`test_ready_queue.py`

```text
done 为空时只返回起点工序。
完成前置后返回下一层工序。
无 ready 时能识别异常。
冻结窗口 seed 节点可作为 done，不再进入 unscheduled。
```

`test_resource_matching.py`

```text
最大匹配数量正确。
同一机器不会重复匹配。
无候选设备的工序不会匹配。
```

`regression_scheduler_graph_config_contract.py`

```text
配置字段 registry/default/snapshot/to_dict 同步。
页面保存 off/report/on 能进入 snapshot。
旧 runtime 层认识新字段。
```

`regression_scheduler_graph_report_mode_contract.py`

```text
report 模式不改变排产结果。
report 模式写入 graph_analysis。
NetworkX 不可用时 report 模式给可读降级，不把底层 ImportError 丢给页面。
```

`regression_scheduler_graph_on_mode_contract.py`

```text
on 模式不违反前后置。
on + block_on_cycle=yes 时有环阻止排产。
```

`regression_scheduler_graph_operation_logs_contract.py`

```text
OperationLogs 只写 graph_analysis 小摘要。
不把 nodes/edges 全量写进日志。
```

`regression_scheduler_graph_summary_contract.py`

```text
algo.graph_analysis 是公开小摘要。
diagnostics.graph_analysis 是采样诊断。
页面不会展示内部异常原文。
```

`regression_scheduler_graph_migration_contract.py`

```text
旧库没有 graph_analysis_mode 时，迁移后默认 off。
preset JSON 也有默认 off。
```

## 阶段 18：性能测试

新增：

```text
tests/scheduler_graph/test_graph_performance.py
```

### 18.1 构造数据

```text
100 个批次
每批 20 道工序
总节点 2000
总边 1900
```

### 18.2 测试内容

```text
构建节点耗时
构建图耗时
DAG 校验耗时
拓扑排序耗时
关键路径耗时
影响范围指标耗时
```

### 18.3 第一版验收阈值

先不要拍脑袋写死太严格。可以先记录：

```text
evidence/scheduler_graph/performance_2000_nodes.txt
```

内容：

```text
build_nodes_ms=
build_graph_ms=
validate_dag_ms=
critical_path_ms=
impact_metrics_ms=
```

跑 3 次取平均。

如果一定要先设阈值，建议：

```text
2000 节点 + 1900 边，完整 report 分析 < 2 秒。
```

如果超过，先不要接入逐节点 `downstream_critical_minutes`，因为这个最容易慢；可以先只算：

```text
critical_path
impact_count
generation_index
```

## 阶段 19：排产服务接入点建议

### 19.1 找“加载待排工序”的位置

当前位置：

```text
core/services/scheduler/run/schedule_input_collector.py
  collect_schedule_run_input()
```

这里会整理：

```text
batch_ids
batches
operations
reschedulable_operations
algo_ops
algo_ops_to_schedule
seed_results
frozen_op_ids
downtime_map
resource_pool
```

第一版图节点建议使用：

```text
schedule_input.algo_ops_to_schedule
schedule_input.batches
schedule_input.resource_pool
```

不要用全部 `operations`，否则可能把冻结窗口已经 seed 的工序又算回待排图。

### 19.2 找“排序策略”的位置

批次排序位置：

```text
core/algorithms/ordering.py
  build_batch_sort_inputs()
```

SGS 候选评分位置：

```text
core/algorithms/greedy/dispatch/sgs.py
  _score_candidates()
  _score_candidate()

core/algorithms/greedy/dispatch/sgs_scoring.py
  _score_external_candidate()
  _score_internal_candidate()
```

以后图评分应该加在 SGS 候选评分里，而不是绕过这些函数改 `batch_order`。

### 19.3 找“真正写入排程”的位置

当前位置：

```text
core/services/scheduler/run/schedule_persistence.py
```

这里负责：

```text
校验 optimizer_outcome.results
构造 ValidatedSchedulePayload
写 ScheduleHistory
写 Schedule
更新工序状态
按 auto_assign_persist 条件写回资源
写 OperationLogs 小摘要
```

report 模式不应该改这里的业务校验，只在日志小摘要里带 graph_analysis 小字段。

### 19.4 第一轮接入位置

只在 orchestrator/summary 附近加：

```python
if graph_mode in ("report", "on"):
    graph_analysis = analyze(...)
    result_summary["algo"]["graph_analysis"] = small_summary
    result_summary["diagnostics"]["graph_analysis"] = sampled_diagnostics
```

不要马上动排序和写入。

## 阶段 20：提交顺序建议

建议每个小阶段一个 commit，方便回滚。

```text
commit 1: record before_networkx branch, dependency and scheduler baselines
commit 2: add ADR-0012 and update roadmap/items for phase 0 boundary
commit 3: add optional networkx requirements and isolated install/wheel docs
commit 4: add graph config fields default off
commit 5: add graph module skeleton and lazy networkx loader
commit 6: add graph dataclasses and id policy
commit 7: add input adapter and precedence graph builder
commit 8: add validators and topology metrics
commit 9: add critical path and impact metrics
commit 10: add graph exporter and analysis service
commit 11: add report-mode scheduler integration
commit 12: add debug export and performance evidence
commit 13: add ready queue integration behind feature flag
commit 14: add critical-path scoring behind feature flag
commit 15: add resource matching report-only analysis
commit 16: add packaging and Win7 evidence
```

每个 commit 后执行：

```bat
pytest
```

如果测试很多，可以先执行：

```bat
pytest tests/scheduler_graph
pytest tests/regression_scheduler_graph_report_mode_contract.py
```

再跑全量或质量门禁。

本仓库常用最终门禁：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_full_test_debt.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

注意：

```text
--require-clean-worktree 需要工作树干净。
如果有用户未提交改动或本任务外脏文件，不能把 clean gate 说成已经通过。
```

## 阶段 21：打包和 Win7 验证

### 21.1 打包前验证

```bat
python -c "import networkx as nx; print(nx.__version__)"
pytest tests/scheduler_graph
pytest
```

### 21.2 PyInstaller 验证

如果 NetworkX 仍是可选依赖，建议先做两个包：

```text
包 A：不安装 NetworkX，graph_analysis_mode=off
包 B：安装 NetworkX，graph_analysis_mode=report
```

包 A 验收：

```text
exe 能启动。
普通排产能执行。
不会因为缺 networkx 报错。
```

包 B 验收：

```text
exe 能启动。
普通排产能执行。
日志/result_summary 有 graph_analysis。
```

### 21.3 如果 PyInstaller 漏收

一般 NetworkX 这种纯 Python 包比 OR-Tools 简单很多，但如果遇到漏收，可以先在 spec 或命令里加：

```bat
--hidden-import networkx
```

如果仍然失败，再加：

```bat
--collect-submodules networkx
```

验收：

```text
Win7 实机或虚拟机启动 exe 成功。
graph_analysis_mode=off/report/on 三种模式都测过。
```

当前仓库正式要求仍是 Win7 x64、Python 3.8.x x64、PyInstaller 4.10。正式双包交付要走现有 Win7 打包脚本和安装包说明，不要只跑最小 exe 验收脚本就说交付闭环完成。

### 21.4 离线安装验收清单

```text
[ ] 用 Python 3.8 x64 下载 networkx==3.1 wheel
[ ] 记录 wheel 文件名
[ ] 记录 wheel SHA256
[ ] 离线 Win7 SP1 x64 干净环境安装成功
[ ] python -c "import networkx as nx; print(nx.__version__)" 输出 3.1
[ ] 构造 DAG 调用 dag_longest_path 成功
[ ] 构造有环图，业务层返回可读错误或 warning
[ ] graph_analysis_mode=off 时卸载 NetworkX 仍能启动
[ ] graph_analysis_mode=report 时安装 NetworkX 后能写摘要
```

## 阶段 22：回滚点

每个阶段都要能回滚，不能只写“出问题就回滚代码”。

### 22.1 依赖回滚

触发条件：

```text
Python 3.8 环境 import networkx 失败。
Win7 离线 wheel 安装失败。
pip check 失败。
PyInstaller 打包后 exe 启动失败。
```

回滚动作：

```text
删除或停止使用 requirements-optimizer-lite-win7.txt。
从 wheelhouse 移除 networkx wheel。
graph_analysis_mode 保持 off。
不改 requirements.txt。
```

### 22.2 report 模式回滚

触发条件：

```text
report 模式让排产结果与 baseline 不一致。
report 模式让 result_summary 过大。
report 模式把底层异常暴露到页面。
OperationLogs 被完整节点边撑大。
```

回滚动作：

```text
graph_analysis_mode 改回 off。
保留代码但关闭配置。
若 result_summary 合同已污染历史，补迁移或兼容解析，不直接删历史数据。
```

### 22.3 on 模式回滚

触发条件：

```text
on 模式违反前后置。
冻结窗口 seed 工序被重复排。
SGS 排序出现无法解释的大幅变化。
关键路径权重导致急件/交期语义被压过。
```

回滚动作：

```text
graph_analysis_mode 改回 report 或 off。
保留 report 分析能力。
撤回 ready 队列/评分接入 commit。
继续用现有 GreedyScheduler 和 SGS 主链。
```

### 22.4 打包回滚

触发条件：

```text
Win7 安装包启动失败。
Chrome109 启动链失败。
域账户启动失败。
共享目录不可写。
第二账户阻止进入失败。
无 wmic 场景误报成功。
```

回滚动作：

```text
恢复到未引入 NetworkX 的上一版安装包。
恢复上一份 wheelhouse。
卸载主程序时不要默认清共享数据。
保留用户现场数据库和共享目录数据。
```

## 最小可执行版本

如果只想先做一个最小可用版本，建议只做下面这些文件：

阶段 0 最小闭环只包含 ADR、before_networkx 证据和基线捕获工具；下面列表从阶段 1/后续 report 模式开始。

```text
requirements-optimizer-lite-win7.txt
开发文档/ADR/0012-networkx-排产依赖图建模.md

core/services/scheduler/graph/__init__.py
core/services/scheduler/graph/nx_runtime.py
core/services/scheduler/graph/types.py
core/services/scheduler/graph/id_policy.py
core/services/scheduler/graph/input_adapter.py
core/services/scheduler/graph/precedence_builder.py
core/services/scheduler/graph/validators.py
core/services/scheduler/graph/metrics.py
core/services/scheduler/graph/exporter.py
core/services/scheduler/graph/analysis_service.py
```

第一版只交付这些能力：

```text
1. 构建工序依赖图
2. 检查是否有环
3. 计算拓扑顺序
4. 计算关键路径
5. 写入 graph_analysis 摘要
6. 不改变排产结果
```

第一版不要做：

```text
资源匹配
最小费用流
调参
前端图展示
NetworkX drawing
Matplotlib
```

## 第一版完成后的验收清单

```text
[ ] 阶段 0 已生成 before_networkx pip freeze 和三组排产基线 JSON
[ ] 阶段 1 起 requirements-optimizer-lite-win7.txt 存在，内容为 networkx==3.1
[ ] 主 requirements.txt 暂时未改变
[ ] 未使用 networkx[default]
[ ] 未引入 numpy/scipy/matplotlib
[ ] 开发文档/ADR/0012-networkx-排产依赖图建模.md 存在
[ ] ADR 明确写了 Win7 + Python 3.8.10
[ ] graph_analysis_mode=off 时，未安装 NetworkX 也能启动
[ ] graph_analysis_mode=report 时，能加载 NetworkX 3.1
[ ] 图模块没有向外暴露 nx.DiGraph
[ ] 工序节点 ID 有统一规范
[ ] 同一批次按 seq 能生成线性依赖边
[ ] 多批次不会误连边
[ ] 有环能检测出来
[ ] 有环时不调用 topological_sort / dag_longest_path
[ ] 无环能算拓扑顺序
[ ] 能算关键路径
[ ] 能算影响范围
[ ] graph_analysis 能写入 ScheduleHistory.result_summary
[ ] OperationLogs 只写小摘要，不写完整 nodes/edges
[ ] report 模式下，三组基线排产结果完全不变
[ ] on 模式下，后工序不会排到前工序前面
[ ] seed_results / frozen_op_ids 不会被重复排
[ ] PyInstaller onedir 在 Win7 上能启动
[ ] 离线 wheel 安装流程验证通过
[ ] tools/check_full_test_debt.py 通过
[ ] scripts/sync_debt_ledger.py check 通过
[ ] scripts/run_quality_gate.py --require-clean-worktree 在干净工作树上通过
```

## 最终落地形态

等全部稳定后，目录大概是：

```text
core/services/scheduler/
├── graph/
│   ├── __init__.py
│   ├── nx_runtime.py
│   ├── types.py
│   ├── id_policy.py
│   ├── input_adapter.py
│   ├── precedence_builder.py
│   ├── validators.py
│   ├── metrics.py
│   ├── ready_queue.py
│   ├── scoring.py
│   ├── resource_matching.py
│   ├── exporter.py
│   └── analysis_service.py
└── 原有排产服务文件
```

排产流程最终变成：

```text
加载待排工序
    ↓
转 OperationGraphNode
    ↓
构建 nx.DiGraph
    ↓
校验 DAG / 环
    ↓
计算拓扑顺序、关键路径、影响范围
    ↓
report 模式：只写 result_summary / diagnostics，不改变排产
on 模式：
    ↓
    每轮取 ready 工序
    ↓
    用原排序 + 关键路径加分 + 影响范围加分
    ↓
    选择工序
    ↓
    分配设备/人员
    ↓
    写入排程
```

这个路线比直接上 OR-Tools 稳得多，也更符合当前 Win7/Python 3.8.10/离线交付的实际约束。


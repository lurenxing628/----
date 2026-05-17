---
doc_type: roadmap
slug: networkx-scheduler-graph-introduction
status: active
created: 2026-05-08
last_reviewed: 2026-05-17
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

建议按下面这些 PR 或小阶段推进。每个阶段都能单独提交，方便回滚；正文后面的详细阶段是执行时的准绳。

| 阶段 | 目标 | 是否改变排产结果 | 风险 |
| -: | --- | ---: | -: |
| 0 | 建分支、记录基线、落 ADR 和依赖决策 | 否 | 很低 |
| 1 | 加可选依赖文件、安装验证和离线 wheel 流程 | 否 | 很低 |
| 2 | 加配置开关和迁移，默认 off | 否 | 低 |
| 3 | 建目录和 NetworkX 懒加载层 | 否 | 低 |
| 4 | 定义图输入数据结构和节点 ID 规范 | 否 | 低 |
| 5 | 把现有业务数据转成图节点 | 否 | 低 |
| 6 | 构建工序依赖图 | 否 | 低 |
| 7 | 实现图校验：环、孤立、重复 seq | 否 | 低 |
| 8 | 实现指标：拓扑顺序、层级、关键路径、影响范围 | 否 | 低 |
| 9 | 图导出和统一分析服务入口 | 否 | 低 |
| 10 | 接入 report 模式，写 result_summary 小摘要 | 否 | 低 |
| 11 | 有环时的处理策略 | 否 | 低 |
| 12 | ready 队列参与 SGS 候选 | 是 | 中 |
| 13 | 关键路径评分、资源匹配、调试导出和最终打包验收 | 是/可控 | 中 |

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

Phase 4.5 追加约束：主配置规格与 runtime 规格必须用测试锁住 key 集合、`field_type`、`default`、`min_value`、`min_inclusive`、`choices` 一致，避免图配置只写一边。

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
```

Phase 4.5 修正：不要把 graph 默认行直接写入 `schema.sql`。新库应继续先建空结构并通过 `ConfigService.ensure_defaults()` 填默认配置，避免破坏空库 SchemaVersion fast-forward / `is_truly_empty_db()` 语义。

验收：

```text
默认 off 时，系统不需要安装 NetworkX 也能启动。
默认 off 时，现有排产结果不变。
旧库迁移后页面能看到默认 off。
配置页面选择 report/on 后能进入 snapshot。
配置字段同步测试通过。
v9 迁移必须幂等。
坏 preset JSON 必须 fail fast，不可静默跳过。
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
from typing import Any, Dict, List, Mapping, Optional, Tuple


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
    candidate_machine_ids: Tuple[str, ...] = field(default_factory=tuple)
    candidate_operator_ids: Tuple[str, ...] = field(default_factory=tuple)
    raw: Mapping[str, Any] = field(default_factory=dict)


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
  Phase 4.5 起必须是 Tuple[str, ...]，不能保留可变 list。

candidate_operator_ids:
  候选人员，用于后续双资源匹配，来自 resource_pool。
  Phase 4.5 起必须是 Tuple[str, ...]，不能保留可变 list。

raw:
  原始业务数据快照，只放 JSON 可序列化字段。
  Phase 4.5 起必须冻结为不可变 JSON-like 快照，同时仍可被 json.dumps(asdict(node), ensure_ascii=False) 序列化。
```

注意事项：

```text
types.py 不 import networkx。
不要把数据库连接、repo、模型原对象、datetime 原对象、NetworkX 对象放进 raw。
raw 必须能 json.dumps(..., ensure_ascii=False)。
OperationGraphNode 内部不能保留调用方传入的可变 list/dict 引用。
GraphWarning / GraphAnalysisSummary 当前仍是纯 Python 汇总 DTO，不承载 nx.DiGraph。
```

验收：

```text
types.py 不 import networkx。
所有 dataclass 都是业务友好的纯 Python 结构。
Python 3.8 下类型注解通过 ruff/pyright。
candidate_machine_ids / candidate_operator_ids 为 Tuple[str, ...]。
OperationGraphNode.raw 不可变且可 JSON 序列化。
```

## 阶段 4.5：图基础设施硬化

本阶段只加固阶段 0–4 已经允许存在的基础设施，不进入阶段 5 及之后的图构建、校验、指标、分析服务、ready 队列、评分或排产接入。

### 4.5.1 边界声明

```text
允许：
- graph 包骨架、懒加载 NetworkX wrapper、节点 ID 策略、纯值对象。
- 图配置字段、v9 迁移、fresh DB ensure_defaults 合同。
- 配置页面如实提示 report/on 当前只保存配置。
- 回写 roadmap / ADR。

禁止：
- input_adapter.py
- precedence_builder.py
- validators.py
- metrics.py
- analysis_service.py
- nx.DiGraph 构建或对外暴露
- result_summary 图分析接入
- scheduling / ready queue / scoring 集成
```

### 4.5.2 ID 策略硬化

```text
make_operation_node_id 不得生成 op::。
make_machine_node_id 不得生成 machine:。
make_operator_node_id 不得生成 operator:。
bytes / bytearray 不得静默 decode 成 ID。
row_id 只接受正整数语义：1、"1"、"001"、"1.0"、1.0。
row_id 拒绝 None、空白、0、bool、负数、科学计数、非整数小数、bytes。
```

### 4.5.3 值对象硬化

```text
OperationGraphNode 必须 frozen=True。
candidate_machine_ids: Tuple[str, ...]
candidate_operator_ids: Tuple[str, ...]
raw: Mapping[str, Any]
raw 内部递归冻结，不能被调用方后续修改污染。
json.dumps(asdict(node), ensure_ascii=False) 必须可用。
types.py 不 import networkx。
```

### 4.5.4 配置 / 迁移 / UI 合同

```text
主 config_field_spec 与 runtime_config_fields 必须保持 key 集合和字段元数据一致。
Fresh DB 不在 schema.sql 直接插入 graph 配置行，而由 ConfigService.ensure_defaults() 补齐。
v9 只负责已有库：补 ScheduleConfig 默认行，并补 preset.* JSON。
v9 必须幂等。
坏 preset JSON 必须 fail fast。
report/on 当前只能保存配置，页面必须提示不执行图分析、不改变排产结果。
graph_analysis_mode=off 不需要安装 NetworkX。
```

### 4.5.5 验收清单

```text
[ ] make_operation_node_id 不生成 op::。
[ ] make_machine_node_id 不生成 machine:。
[ ] make_operator_node_id 不生成 operator:。
[ ] bytes / bytearray 不被静默解码。
[ ] OperationGraphNode.candidate_machine_ids / candidate_operator_ids 为 Tuple[str, ...]。
[ ] OperationGraphNode.raw 不可变且 JSON 可序列化。
[ ] 主配置规格与 runtime 规格同步测试通过。
[ ] fresh DB + ensure_defaults 插入 graph 默认配置。
[ ] v9 迁移幂等。
[ ] report/on UI 明确说明当前版本只保存配置、不执行图分析、不改变排产结果。
[ ] graph 模块仍不静态 import networkx。
```

## 阶段 5：把现有业务数据转成图节点

本阶段的目标很窄：只把现有排产输入里的工序、批次、资源池信息转换成 `OperationGraphNode`。这一阶段不构图、不校验 DAG、不算关键路径、不写 `result_summary`、不接 SGS，也不改变任何排产结果。

### 5.0 整体实现要求

本阶段必须把下面这些实现原则当成硬约束写进设计和验收里：

```text
优雅简洁：
- input_adapter.py 只做“业务输入 -> OperationGraphNode”的转换，不做图算法、不查数据库、不读配置、不写日志、不调用排产。
- 辅助函数只保留字段读取、显式解析、时长计算、候选资源整理这几类；不要写万能转换器。
- 一个函数只管一件事，函数名要直接说明业务目的。

不做过度兜底：
- 不允许 broad except Exception 后悄悄给 0、空字符串、internal、normal 这类默认值。
- 只有当前排产链路已经明确存在的默认语义，才可以沿用；例如外协天数的“非严格模式默认 1 天”已经在 schedule_input_builder 层处理，input_adapter.py 不再重复造一个默认。
- 缺少必需字段时要给出清楚错误，不能把坏数据悄悄变成空节点继续往下跑。

不做静默回退：
- source 缺失或不是 internal/external，不在本阶段猜测，应抛 GraphInputContractError。
- 当前老排产链路里，历史数据缺 source 或 source 异常时，部分入口可能会按 internal 继续跑；阶段 5 的图输入合同要比老链路更严格，只吃已经整理好的 OpForScheduleAlgo。
- seq、duration、quantity 这类影响图结果的字段不合法，应抛 GraphInputContractError。
- resource_pool 缺少某个映射时，可以得到空候选集合，但必须保持“空”这个事实，不允许回退成“全量设备/全量人员”。

不做过度防御性编程：
- 本阶段的输入来源是当前排产链路整理后的 OpForScheduleAlgo、batches map、resource_pool，不为任意外部 JSON 做复杂兼容。
- 不要同时支持十几种字段别名；字段名必须按当前仓库事实走：source、setup_hours、unit_hours、ext_days、ext_group_total_days。
- 不在 adapter 里吞掉上游数据质量问题；如果上游合同不清楚，先补上游合同或测试。

高内聚低耦合：
- input_adapter.py 可以 import id_policy.py 和 types.py。
- input_adapter.py 不 import networkx，不 import nx_runtime.py，不 import precedence_builder.py，不 import validators.py。
- input_adapter.py 不 import Flask route、repo、db session、ConfigService、ScheduleService、GreedyScheduler。
- 对外只返回纯 Python dataclass 列表；后续阶段要构图时再把这些节点交给 precedence_builder.py。
```

### 5.1 新建 input_adapter.py

新增文件：

```text
core/services/scheduler/graph/input_adapter.py
```

第一版对外只暴露这两个名字：

```python
class GraphInputContractError(ValueError):
    pass


def build_operation_nodes_from_rows(
    rows: Iterable[Any],
    *,
    batches: Mapping[str, Any],
    resource_pool: Optional[Mapping[str, Any]] = None,
) -> List[OperationGraphNode]:
    ...
```

输入边界：

```text
rows:
  首选 List[OpForScheduleAlgo]。
  测试里可以用 List[Dict[str, Any]]，但只能使用当前仓库真实字段名。

batches:
  batch_id -> Batch 或 dict。
  这是必传参数，不允许默认为空 dict。

resource_pool:
  来自当前 resource_pool_builder 的结果。
  本阶段只读 machines_by_op_type、operators_by_machine、machines_by_operator。
  缺失时只会导致候选集合为空，不会回退成全量资源。
```

禁止事项：

```text
不要在 input_adapter.py 里 import networkx。
不要在 input_adapter.py 里调用 import_networkx()。
不要在 input_adapter.py 里查数据库。
不要在 input_adapter.py 里重新计算外协组合并上下文。
不要在 input_adapter.py 里修改传入的 rows、batches、resource_pool。
不要返回 dict 节点；统一返回 OperationGraphNode。
```

### 5.2 字段映射合同

每个 `OperationGraphNode` 的字段来源必须按下面这张表执行。表里写“必需”的字段，缺失或非法时直接抛 `GraphInputContractError`。

| 节点字段 | 来源 | 要求 |
| --- | --- | --- |
| `node_id` | `make_operation_node_id(batch_id, op_code, id)` | `id` 可以缺失；缺失时 `batch_id + op_code` 必须可生成稳定 ID |
| `batch_id` | row.batch_id | 必需，不能为空 |
| `op_code` | row.op_code | 必需，不能为空 |
| `seq` | row.seq | 必需，必须能转成整数 |
| `name` | row.op_type_name | 可为空，空时保留空字符串 |
| `duration_minutes` | 本阶段派生 | 必需，不能为负数 |
| `part_no` | batch.part_no | 可为空 |
| `priority` | batch.priority | 可为空；为空时使用 `OperationGraphNode` 自身默认值，不在 adapter 里另造复杂优先级 |
| `source` | row.source | 必需，只允许 `internal` 或 `external` |
| `status` | row.status | 可为空；为空时使用节点默认值 |
| `due_date` | batch.due_date | 可为空；如为日期对象，必须显式转 `isoformat()` 字符串 |
| `op_type_id` | row.op_type_id | 可为空 |
| `machine_id` | row.machine_id | 可为空 |
| `operator_id` | row.operator_id | 可为空 |
| `supplier_id` | row.supplier_id | 可为空 |
| `ext_group_id` | row.ext_group_id | 可为空 |
| `ext_merge_mode` | row.ext_merge_mode | 可为空 |
| `ext_group_total_days` | row.ext_group_total_days | 可为空；非空时必须大于 0 |
| `merge_context_degraded` | row.merge_context_degraded | 布尔值；只做 bool 归一，不据此另造时长默认 |
| `candidate_machine_ids` | row.machine_id 或 resource_pool.machines_by_op_type | 去重后转 Tuple[str, ...] |
| `candidate_operator_ids` | row.operator_id 或 resource_pool.operators_by_machine | 去重后转 Tuple[str, ...] |
| `raw` | row 的少量源字段 | 只放 JSON 可序列化快照，不放模型对象、repo、db session、datetime 原对象 |

### 5.3 时长计算规则

时长只在这里做一件事：把当前排产输入已经收口好的小时/天数转换成分钟。

```text
自制工序：
  duration_minutes = round((setup_hours + unit_hours * batch.quantity) * 60)

普通外协：
  duration_minutes = round(ext_days * 24 * 60)

合并外协：
  当 source == external 且 ext_merge_mode == merged 且 ext_group_total_days 非空时：
    duration_minutes = round(ext_group_total_days * 24 * 60)
  其他外协情况：
    duration_minutes = round(ext_days * 24 * 60)
```

必需校验：

```text
setup_hours、unit_hours、quantity 不能为负数。
普通外协 ext_days 必须大于 0。
merged 外协 ext_group_total_days 必须大于 0。
source == internal 时，setup_hours、unit_hours、batch.quantity 必须可读。
source == external 且不是有效 merged 总天数时，ext_days 必须可读。
duration_minutes 最终不能为负数。
```

特别注意：

```text
不要在 input_adapter.py 里给 ext_days 缺失补 1 天。
如果现有非严格模式需要“外协天数缺失按 1 天继续”，这个语义必须继续由 schedule_input_builder.py 负责。
如果输入来自 OpForScheduleAlgo，setup_hours 和 unit_hours 已经在上游排产输入构建阶段收口成数字；input_adapter.py 只消费这个结果，不再自己把缺失值补成 0。
adapter 只消费已经进入 OpForScheduleAlgo 的结果，不能自己再造一套兜底规则。
```

### 5.4 显式解析助手

建议只写下面这种窄助手，避免万能解析和静默吞错：

```python
def _read_field(row: Any, field: str) -> Any:
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field, None)


def _require_text(row: Any, field: str, *, scope: str) -> str:
    value = _read_field(row, field)
    text = str(value or "").strip()
    if not text:
        raise GraphInputContractError("{} 缺少必填字段 {}".format(scope, field))
    return text


def _require_int(row: Any, field: str, *, scope: str) -> int:
    value = _read_field(row, field)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise GraphInputContractError("{} 字段 {} 不是整数：{!r}".format(scope, field, value)) from exc


def _require_nonnegative_float(value: Any, *, field: str, scope: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise GraphInputContractError("{} 字段 {} 不是数字：{!r}".format(scope, field, value)) from exc
    if number < 0:
        raise GraphInputContractError("{} 字段 {} 不能为负数：{!r}".format(scope, field, value))
    return number


def _require_positive_float(value: Any, *, field: str, scope: str) -> float:
    number = _require_nonnegative_float(value, field=field, scope=scope)
    if number <= 0:
        raise GraphInputContractError("{} 字段 {} 必须大于 0：{!r}".format(scope, field, value))
    return number
```

实现要求：

```text
只捕获 TypeError / ValueError，不捕获 Exception。
错误信息必须带 scope，例如 graph_input.op[123] 或 graph_input.batch[B001].seq[10]。
解析失败时抛 GraphInputContractError，不返回默认值。
自制工序的 setup_hours、unit_hours、quantity 用 _require_nonnegative_float。
普通外协 ext_days、merged 外协 ext_group_total_days 用 _require_positive_float。
```

### 5.5 候选资源整理

候选资源只表达“图分析看到的候选范围”，不在这里做派工选择。

设备候选：

```text
先读取：
  fixed_machine = row.machine_id
  fixed_operator = row.operator_id
  op_type_id = row.op_type_id
  machines_by_op_type = resource_pool["machines_by_op_type"]
  machines_by_operator = resource_pool["machines_by_operator"]
  operators_by_machine = resource_pool["operators_by_machine"]

如果 fixed_machine 有值：
  先得到 candidate_machine_ids = (fixed_machine,)
  如果 op_type_id 在 machines_by_op_type 里有明确候选池：
    再把 fixed_machine 和这个候选池取交集。
    如果 fixed_machine 不在该工种候选池里，candidate_machine_ids = ()。
否则如果 fixed_operator 有值：
  先从 machines_by_operator[fixed_operator] 取候选设备。
  如果 machines_by_operator 里没有，再按当前 auto_assign 口径从 operators_by_machine 反查这个人员能操作的设备。
  如果 op_type_id 在 machines_by_op_type 里有明确候选池，再和这个候选池取交集。
否则如果 op_type_id 有值且 machines_by_op_type 里有这个工种：
  candidate_machine_ids = machines_by_op_type[op_type_id] 去重后结果。
否则：
  candidate_machine_ids = ()
```

人员候选：

```text
如果 fixed_operator 有值：
  如果 candidate_machine_ids 非空：
    candidate_operator_ids = fixed_operator 和每台候选设备 operators_by_machine[machine_id] 的交集。
    如果固定人员不在候选设备可用人员里，candidate_operator_ids = ()。
  否则：
    candidate_operator_ids = (fixed_operator,)
否则如果 candidate_machine_ids 非空：
  candidate_operator_ids = 这些设备在 operators_by_machine 下的人员并集，按原顺序去重。
否则：
  candidate_operator_ids = ()
```

边界说明：

```text
阶段 5 只整理图分析能看见的候选范围，不计算最优人机组合。
阶段 5 不看当前时间轴、不看设备停机、不看人员停机、不看冻结窗口、不做 probe_only 自动分配。
如果后续要让图分析候选和排产可行性完全一致，应在后续阶段复用 auto_assign 的候选解析 helper，不能在 input_adapter.py 里复制一套复杂派工器。
resource_pool 本身可能已经按 resource_pool_builder 的既有口径带着更宽的映射；adapter 不再额外回退成全量设备或全量人员。
```

禁止：

```text
不要因为找不到 op_type_id 对应设备，就把所有设备塞进 candidate_machine_ids。
不要因为找不到设备对应人员，就把所有人员塞进 candidate_operator_ids。
不要在 adapter 里调用 auto_assign_internal_resources。
不要在 adapter 里考虑 machine downtime、operator downtime、冻结窗口、当前时间轴占用。
```

### 5.6 raw 快照规则

`raw` 只用于后续调试和诊断采样，不是第二份业务模型。

建议只放：

```text
id
batch_id
op_code
seq
source
op_type_id
machine_id
operator_id
supplier_id
ext_group_id
ext_merge_mode
merge_context_degraded
```

要求：

```text
raw 必须能 json.dumps(dict(raw), ensure_ascii=False)。
raw 会被 OperationGraphNode.__post_init__ 递归冻结，调用方后续修改原始 row 不应污染节点。
raw 不放 Batch / BatchOperation / OpForScheduleAlgo 原对象。
raw 不放 datetime 原对象；如必须放日期，先转 isoformat 字符串。
```

### 5.7 验收数据样例

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
        "op_type_id": "cut",
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
batches = {
    "B001": {
        "batch_id": "B001",
        "quantity": 10,
        "priority": "normal",
        "due_date": "2026-05-20",
    }
}
resource_pool = {
    "machines_by_op_type": {"cut": ["M01", "M02"]},
    "operators_by_machine": {"M01": ["U01"], "M02": ["U02"]},
    "machines_by_operator": {"U01": ["M01"], "U02": ["M02"]},
}
```

期望：

```text
生成 2 个 OperationGraphNode。
node_id 分别为 op:1、op:2。
第一道自制工序 duration_minutes = (1 + 0.5 * 10) * 60 = 360。
第一道自制工序 candidate_machine_ids = ("M01", "M02")。
第一道自制工序 candidate_operator_ids = ("U01", "U02")。
第二道外协工序 duration_minutes = 2 * 24 * 60 = 2880。
source 分别为 internal、external。
raw 可 JSON 序列化，并且不被原始 rows 后续修改影响。
```

错误样例：

```text
缺 batch_id：抛 GraphInputContractError。
缺 source：抛 GraphInputContractError。
source = "unknown"：抛 GraphInputContractError。
seq = "abc"：抛 GraphInputContractError。
source = internal 且 batch.quantity 缺失：抛 GraphInputContractError。
source = external 且 ext_days 缺失、也没有有效 merged ext_group_total_days：抛 GraphInputContractError。
```

### 5.8 测试文件

新增：

```text
tests/scheduler_graph/test_input_adapter.py
```

核心用例：

```text
test_build_internal_operation_node_duration:
  自制工序按 setup_hours + unit_hours * batch.quantity 算分钟。

test_build_external_operation_node_duration:
  普通外协按 ext_days 算分钟。

test_build_merged_external_operation_node_duration:
  merged 外协按 ext_group_total_days 算分钟。

test_candidate_resources_from_resource_pool:
  没有固定设备和固定人员时，按 op_type_id 从 machines_by_op_type 取候选设备。
  没有固定人员时，按候选设备从 operators_by_machine 取候选人员。

test_fixed_resources_win_over_pool_candidates:
  row.machine_id / row.operator_id 有值时，固定资源优先，但仍按 op_type_id 候选池过滤明显不匹配的设备。

test_fixed_operator_resolves_machine_candidates:
  row.operator_id 有值但 row.machine_id 为空时，先用 machines_by_operator 找候选设备；缺失时按 operators_by_machine 反查。

test_missing_required_field_raises_contract_error:
  batch_id、op_code、seq、source 缺失或非法时抛 GraphInputContractError。

test_invalid_source_raises_contract_error:
  source 不是 internal/external 时抛 GraphInputContractError。

test_missing_duration_inputs_raise_contract_error:
  缺 quantity、setup_hours、unit_hours、ext_days 时不静默转 0。
  ext_days=0 或 ext_group_total_days=0 时抛 GraphInputContractError。

test_raw_snapshot_is_json_serializable_and_frozen:
  json.dumps(dict(node.raw), ensure_ascii=False) 可用；
  修改原始 row 后 node.raw 不变化。

test_input_adapter_does_not_import_networkx:
  import core.services.scheduler.graph.input_adapter 不触发 networkx import。
```

### 5.9 阶段验收清单

```text
[ ] 新增 core/services/scheduler/graph/input_adapter.py。
[ ] input_adapter.py 只 import id_policy.py 和 types.py 以及标准库 typing，不 import networkx / repo / db / scheduler。
[ ] build_operation_nodes_from_rows 返回 List[OperationGraphNode]。
[ ] 缺少必需字段时抛 GraphInputContractError，不静默补默认值。
[ ] source 只接受 internal / external。
[ ] 自制、普通外协、合并外协三类时长计算都有测试。
[ ] 候选资源来自固定资源或 resource_pool，不回退成全量资源。
[ ] raw 快照 JSON 可序列化、不可被原始输入后续修改污染。
[ ] OperationGraphNode.candidate_machine_ids / candidate_operator_ids 最终是 Tuple[str, ...]。
[ ] tests/scheduler_graph/test_input_adapter.py 通过。
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_input_adapter.py tests/scheduler_graph/test_graph_types.py tests/scheduler_graph/test_id_policy.py
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/graph tests/scheduler_graph
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/graph
[ ] 如果 pyright 仍被 graph/types.py 里的既有 FrozenDict 方法签名问题挡住，本阶段收尾必须一并修掉；不能只说 input_adapter 自己测试通过。
```

## 阶段 6：构建工序依赖图

本阶段的目标很窄：只把阶段 5 已经整理好的 `OperationGraphNode` 连成“同一批次内的前后顺序边”，再把节点和边装进内部 `nx.DiGraph`。这一阶段不是图校验、不是关键路径分析、不是 ready 队列、不是 SGS 评分，也不是 `result_summary` 接入。

大白话说，阶段 6 只做“把干净节点接成最小依赖图”。坏输入要清楚报错，合法输入要稳定建图；重复 `seq`、孤立节点、环、关键路径这些分析交给阶段 7 和阶段 8。

### 6.0 整体实现要求

本阶段必须把下面这些实现原则当成硬约束写进设计和验收里：

```text
优雅简洁：
- precedence_builder.py 只做两件事：把 OperationGraphNode 生成 OperationGraphEdge；把 OperationGraphNode + OperationGraphEdge 装进内部 nx.DiGraph。
- 文件内函数保持窄职责：分组排序、边生成、节点属性复制、边属性复制、图输入合同校验，各管各的。
- 不新增 graph_edges.py；第一版边对象已经在 types.py，边生成逻辑放 precedence_builder.py 就够清楚。
- 不在本阶段引入 GraphBuildResult、分析服务、导出格式或页面字段，避免把后续阶段提前揉进 builder。

不做过度兜底：
- 不允许 broad except Exception 后跳过坏节点继续建图。
- 不允许重复 node_id 被 NetworkX 静默覆盖。
- 不允许 edge 指向不存在的 node_id 后让 NetworkX 自动补空节点。
- 不允许 lag_minutes 为负数时悄悄改成 0。
- 不允许因为资源候选为空就补资源边或补全量资源。

不做静默回退：
- 阶段 6 只接收 OperationGraphNode 和 OperationGraphEdge，不接收 dict、ORM 对象、BatchOperation、OpForScheduleAlgo 原始对象。
- 阶段 6 不重新生成 node_id、不重新解析 row、不重新计算 duration_minutes、不重新整理 candidate_machine_ids / candidate_operator_ids。
- 同批次重复 seq 不在本阶段伪装成“业务顺序已经确定”；本阶段只用 (seq, op_code, node_id) 保证输出稳定，阶段 7 必须产出 DUPLICATE_SEQ warning。
- 外协边的 external_lag 只表达“外协工序完成后才能进入下一道工序”，第一版不额外增加等待时间。

不做过度防御性编程：
- 不兼容十几种字段别名，不为任意外部 JSON 做适配。
- 不在 builder 里查数据库、读配置、读 Flask request、访问 repo、调用 ScheduleService、调用 GreedyScheduler。
- 不提前处理环、孤立节点、重复 seq 报告、拓扑排序、关键路径、影响范围。

高内聚低耦合：
- precedence_builder.py 可以 import nx_runtime.py 和 types.py。
- precedence_builder.py 不 import input_adapter.py、validators.py、metrics.py、analysis_service.py、ready_queue.py、scoring.py。
- precedence_builder.py 不 import Flask route、数据库、summary、OperationLogs、SGS、dispatch_rules。
- nx.DiGraph 只能留在 core/services/scheduler/graph/ 内部流转，不能流到 Controller、页面、数据库、Excel 导出、summary 外层或 SGS。
- 阶段 6 不改变 algo_ops_to_schedule、seed_results、frozen_op_ids、batch_order、sorted_ops、SGS 候选集合和任何排产结果。
```

### 6.1 新建 precedence_builder.py

本阶段只新增 / 实现：

```text
core/services/scheduler/graph/precedence_builder.py
```

第一版对外只暴露下面这些名字：

```python
class GraphBuildContractError(ValueError):
    pass


def build_linear_edges_by_batch(nodes: Iterable[OperationGraphNode]) -> List[OperationGraphEdge]:
    ...


def build_precedence_graph(
    nodes: Iterable[OperationGraphNode],
    edges: Iterable[OperationGraphEdge],
):
    ...
```

输入边界：

```text
nodes:
  必须是阶段 5 产出的 OperationGraphNode。
  函数内部先转换成 node_list = list(nodes)，避免 Iterable 被消费一次后后续建图丢节点。
  不接受 dict / ORM / OpForScheduleAlgo / BatchOperation 原始对象。

edges:
  必须是 OperationGraphEdge。
  build_linear_edges_by_batch 生成的边可直接传入 build_precedence_graph。
  未来如果要加入跨批次显式边，也必须先变成 OperationGraphEdge，再进入 builder。
```

输出边界：

```text
build_linear_edges_by_batch:
  返回 List[OperationGraphEdge]。
  不 import NetworkX。
  不做图校验、不算指标、不写日志。

build_precedence_graph:
  返回内部 nx.DiGraph。
  函数签名不要把 NetworkX 类型写进对外注解，避免把可选依赖暴露到 graph 包外层。
  只能通过 import_networkx() 懒加载 NetworkX，不能在模块顶层 import networkx。
```

禁止事项：

```text
不要在 precedence_builder.py 顶层 import networkx。
不要在 precedence_builder.py 里调用 build_operation_nodes_from_rows。
不要在 precedence_builder.py 里查数据库或读取配置。
不要在 precedence_builder.py 里调用 validators / metrics / analysis_service。
不要在 precedence_builder.py 里写 result_summary / diagnostics / OperationLogs。
不要在 precedence_builder.py 里接入 schedule_orchestrator、SGS、dispatch_rules。
```

### 6.2 边生成规则

第一版只做最稳的：同一批次内按 `seq` 串成线性工艺路线。

```python
from __future__ import annotations

from typing import Dict, Iterable, List

from .types import OperationGraphEdge, OperationGraphNode


def build_linear_edges_by_batch(nodes: Iterable[OperationGraphNode]) -> List[OperationGraphEdge]:
    grouped: Dict[str, List[OperationGraphNode]] = {}

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
```

执行规则：

```text
1. 按 node.batch_id 分组。
2. 每个 batch 内按 (seq, op_code, node_id) 排序。
3. 相邻两个节点生成一条 prev -> next 的 OperationGraphEdge。
4. prev_node.source == "external" 时，edge.kind = "external_lag"。
5. 其他情况 edge.kind = "precedence"。
6. 第一版 lag_minutes 固定为 0，不从外协天数、资源占用、冻结窗口里派生额外等待。
7. edge.note 写清 batch_id 和 seq 变化，方便后续导出采样时看懂。
```

重复 `seq` 的处理口径：

```text
阶段 6 不负责判断重复 seq 是不是业务错误，否则会把“构图”和“校验”揉在一起。
阶段 6 只用 (seq, op_code, node_id) 保证输出稳定，不偷偷改 seq，也不跳过重复 seq 节点。
阶段 7 必须通过 DUPLICATE_SEQ warning 把这个问题暴露出来。
后续 analysis_service 串联阶段 6 + 阶段 7 时，不能把重复 seq 当成完全正常状态吞掉。
```

外协边的含义：

```text
external_lag 不是“新增等待时间”，只是“上一道外协完成后才能进入下一道工序”的边类型标签。
外协组合并信息保留在节点属性 ext_group_id / ext_merge_mode / ext_group_total_days / merge_context_degraded 上。
阶段 6 不把同一外协组压成一个节点，不改变阶段 5 已经生成的 OperationGraphNode。
```

明确不做：

```text
不引入跨批次依赖。
不把设备冲突、人员冲突、供应商冲突建成 precedence 边。
不处理冻结窗口 seed_results / frozen_op_ids。
不决定 ready 队列。
不计算关键路径。
不计算资源匹配。
```

### 6.3 图构建规则

`build_precedence_graph` 负责把节点和边装进内部 `nx.DiGraph`。

```python
def build_precedence_graph(
    nodes: Iterable[OperationGraphNode],
    edges: Iterable[OperationGraphEdge],
):
    node_list = list(nodes)
    edge_list = list(edges)

    _validate_unique_node_ids(node_list)
    _validate_edges_reference_existing_nodes(edge_list, node_list)

    nx = import_networkx()
    graph = nx.DiGraph()

    for node in node_list:
        graph.add_node(node.node_id, **_node_attrs(node))

    for edge in edge_list:
        graph.add_edge(edge.from_node_id, edge.to_node_id, **_edge_attrs(edge))

    return graph
```

建议内部窄助手：

```text
_validate_unique_node_ids(nodes):
  发现重复 node_id 时抛 GraphBuildContractError。
  错误信息包含重复 node_id 和样本 op_code。

_validate_edges_reference_existing_nodes(edges, nodes):
  edge.from_node_id / edge.to_node_id 必须都存在于 node_id 集合。
  缺失时抛 GraphBuildContractError。
  不能让 NetworkX 自动补空节点。

_validate_edge(edge):
  from_node_id / to_node_id 不能为空。
  kind 第一版只允许 precedence / external_lag / explicit。
  lag_minutes 必须 >= 0。

_node_attrs(node):
  只复制 OperationGraphNode 上已经存在的事实字段。
  不派生分析字段，不写 predecessor_ids / successor_ids / in_degree。

_edge_attrs(edge):
  只复制 kind / lag_minutes / note。
```

节点属性第一版必须保留：

```text
batch_id
op_code
seq
name
duration_minutes
part_no
priority
source
status
due_date
op_type_id
machine_id
operator_id
supplier_id
ext_group_id
ext_merge_mode
ext_group_total_days
merge_context_degraded
candidate_machine_ids
candidate_operator_ids
raw
```

属性复制口径：

```text
candidate_machine_ids / candidate_operator_ids 进入 graph 属性时转成 list，方便后续 JSON 导出。
raw 进入 graph 属性时使用 dict(node.raw)，保持可序列化快照。
不要把 OperationGraphNode 原对象挂到 graph node 属性里。
不要把 Batch / BatchOperation / OpForScheduleAlgo 原对象挂到 graph node 属性里。
不要在属性复制时修改 node 自身。
```

边属性第一版必须保留：

```text
kind
lag_minutes
note
```

为后续阶段预留但本阶段不生成的内容：

```text
ready queue 后续会需要 predecessor_ids / successor_ids / in_degree，但阶段 6 不生成这些业务输出。
关键路径后续会使用 duration_minutes 和 lag_minutes，但阶段 6 不调用 dag_longest_path。
report 模式后续会写 node_count / edge_count / warning_count / sample_edges，但阶段 6 不写 result_summary。
```

### 6.4 错误处理合同

阶段 6 的错误要少而清楚。只要发现下面这些情况，就抛 `GraphBuildContractError`：

```text
重复 node_id。
edge.from_node_id 为空。
edge.to_node_id 为空。
edge.from_node_id 不在节点集合里。
edge.to_node_id 不在节点集合里。
edge.kind 不在 precedence / external_lag / explicit 里。
edge.lag_minutes < 0。
传入对象不是 OperationGraphNode 或 OperationGraphEdge。
```

不要做：

```text
不要跳过坏节点。
不要跳过坏边。
不要给缺失端点生成临时节点。
不要因为某条边坏了就只返回部分图。
不要捕获 GraphBuildContractError 后改成空图。
不要捕获 NetworkXUnavailable 后改成普通 dict 图。
```

NetworkX 缺失或版本不对时：

```text
继续沿用 nx_runtime.NetworkXUnavailable。
不要在 precedence_builder.py 里重新包装成别的错误。
graph_analysis_mode=off 不会调用 build_precedence_graph，所以 off 模式仍不要求安装 NetworkX。
```

### 6.5 测试文件


新增：

```text
tests/scheduler_graph/test_precedence_builder.py
```

测试 1：单批次线性边

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

测试 3：输入顺序打乱仍按 seq 排边

```text
输入顺序：B001_30, B001_10, B001_20
```

期望：

```text
边仍然是 B001_10 -> B001_20 -> B001_30。
```

测试 4：重复 seq 保持稳定排序但不伪装成校验通过

```text
B001 seq=10 op_code=B001_A
B001 seq=10 op_code=B001_B
```

期望：

```text
阶段 6 按 (seq, op_code, node_id) 稳定输出边。
测试说明重复 seq 的业务 warning 属于阶段 7，不在阶段 6 吞掉或改写。
```

测试 5：外部工序边类型

```text
B001_10 internal
B001_20 external
B001_30 internal
```

期望：

```text
B001_20 -> B001_30 的边 kind = external_lag。
```

测试 6：图节点属性复制

```text
构建包含 duration_minutes、source、batch_id、candidate_machine_ids、candidate_operator_ids、raw 的节点。
```

期望：

```text
graph.nodes[node_id] 里字段齐全。
candidate_machine_ids / candidate_operator_ids 是 list。
raw 是普通 dict。
没有把 OperationGraphNode 原对象挂进 graph。
```

测试 7：图边属性复制

```text
传入 kind=external_lag、lag_minutes=0、note=...
```

期望：

```text
graph.edges[from_id, to_id] 里 kind / lag_minutes / note 保持一致。
```

测试 8：重复 node_id fail fast

```text
两个 OperationGraphNode 使用同一个 node_id。
```

期望：

```text
build_precedence_graph 抛 GraphBuildContractError。
错误信息包含重复 node_id。
```

测试 9：未知边端点 fail fast

```text
edge.from_node_id 或 edge.to_node_id 不在 nodes 集合中。
```

期望：

```text
build_precedence_graph 抛 GraphBuildContractError。
不会让 NetworkX 自动补空节点。
```

测试 10：非法边合同 fail fast

```text
edge.kind = "resource_conflict"
edge.lag_minutes = -1
```

期望：

```text
分别抛 GraphBuildContractError。
```

测试 11：模块导入不触发 NetworkX

```text
import core.services.scheduler.graph.precedence_builder
```

期望：

```text
模块导入不 import networkx。
只有调用 build_precedence_graph 时才通过 import_networkx() 懒加载。
```

测试 12：不接排产主链

```text
测试不需要真实数据库、Flask app、ScheduleService、GreedyScheduler。
```

期望：

```text
test_precedence_builder.py 只构造 OperationGraphNode / OperationGraphEdge。
```

### 6.6 阶段验收清单

```text
[ ] 实现 core/services/scheduler/graph/precedence_builder.py。
[ ] 新增 tests/scheduler_graph/test_precedence_builder.py。
[ ] precedence_builder.py 只 import nx_runtime.py、types.py 和标准库 typing / collections，不 import networkx。
[ ] build_linear_edges_by_batch 返回 List[OperationGraphEdge]。
[ ] build_precedence_graph 只通过 import_networkx() 懒加载 NetworkX。
[ ] 同批次只按 seq 前后连边，不引入跨批次依赖。
[ ] 外协前置边使用 kind=external_lag，lag_minutes 第一版仍为 0。
[ ] 重复 node_id 抛 GraphBuildContractError，不被 NetworkX 覆盖。
[ ] edge 端点不存在时抛 GraphBuildContractError，不被 NetworkX 自动补空节点。
[ ] 非法 edge.kind / 负 lag_minutes 抛 GraphBuildContractError。
[ ] 重复 seq 不在阶段 6 修复或跳过；阶段 7 必须继续保留 DUPLICATE_SEQ warning 计划。
[ ] 不修改 validators.py、metrics.py、analysis_service.py、ready_queue.py、scoring.py。
[ ] 不修改 schedule_orchestrator.py、schedule_optimizer.py、SGS、dispatch_rules、summary、OperationLogs、页面和数据库。
[ ] tests/scheduler_graph/test_precedence_builder.py 通过。
[ ] 阶段 5 已有 graph 基础测试继续通过。
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_precedence_builder.py tests/scheduler_graph/test_input_adapter.py tests/scheduler_graph/test_graph_types.py tests/scheduler_graph/test_id_policy.py tests/scheduler_graph/test_nx_runtime.py
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/graph tests/scheduler_graph
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/graph
```

验收口径：

```text
第一版只表达同批次 seq 前后依赖。
不引入跨批次依赖。
不把资源冲突当成 precedence 边。
不改变任何排产结果。
不写 result_summary。
不把 nx.DiGraph 暴露到 graph 包外层。
```

## 阶段 7：图校验

本阶段的目标也很窄：只检查阶段 6 产出的内部 `nx.DiGraph` 有没有环、有没有孤立工序、有没有同一批次重复 `seq`。这一阶段只暴露问题，不修图、不改节点、不删边、不接排产、不写 `result_summary`。

大白话说，阶段 7 只负责“把图里看得见的问题讲清楚”。如果图有环，就把环上的边列出来；如果有孤立工序，就给 warning；如果同一批次有重复顺序号，就给 warning。后续到底要不要阻止排产，留给阶段 11；拓扑排序、关键路径、影响范围，留给阶段 8。

### 7.0 整体实现要求

本阶段必须把下面这些实现原则当成硬约束写进设计和验收里：

```text
优雅简洁：
- validators.py 只做三类校验：DAG / cycle、isolated node、duplicate seq。
- 每个函数只回答一个问题：是否 DAG、环边列表、孤立节点列表、重复 seq warning、汇总 warning。
- 输出用 GraphWarning 和普通 dict，不新增复杂结果对象；阶段 9 统一分析服务再负责组装 GraphAnalysisSummary。
- 有环时只给出可读证据，不提前决定 report / on 模式怎么处理。

不做过度兜底：
- 不允许 broad except Exception 后返回“无环”或“无 warning”。
- 不允许 NetworkX 不可用时伪装成校验通过。
- 不允许因为图为空就随便补一个“正常”结果；空图如果出现，应由调用方明确决定是否允许。
- 不允许发现坏数据后自动删除节点、删除边、重连边或重排 seq。

不做静默回退：
- 阶段 7 只接收阶段 6 产出的内部 nx.DiGraph。
- 阶段 7 不接收 OperationGraphNode 列表重新构图，不接收 dict / ORM / OpForScheduleAlgo 原始对象。
- 重复 seq 只返回 DUPLICATE_SEQ warning，不在 validators.py 里重排、不改 seq、不跳过其中一个节点。
- 孤立节点只返回 ISOLATED_OPERATION warning，不在 validators.py 里补边。

不做过度防御性编程：
- 不兼容十几种节点字段别名，只读取阶段 6 已经写进 graph node 的 batch_id / op_code / seq。
- 不在 validators.py 里查数据库、读配置、读 Flask request、访问 repo、调用 ScheduleService、调用 GreedyScheduler。
- 不提前实现 topological_sort、topological_generations、dag_longest_path、descendants、ancestors。

高内聚低耦合：
- validators.py 可以 import nx_runtime.py 和 types.py。
- validators.py 不 import precedence_builder.py、metrics.py、analysis_service.py、exporter.py、ready_queue.py、scoring.py。
- validators.py 不 import Flask route、数据库、summary、OperationLogs、SGS、dispatch_rules。
- nx.DiGraph 仍只在 core/services/scheduler/graph/ 内部流转，不能流到 Controller、页面、数据库、Excel 导出、summary 外层或 SGS。
- 阶段 7 不改变 algo_ops_to_schedule、seed_results、frozen_op_ids、batch_order、sorted_ops、SGS 候选集合和任何排产结果。
```

### 7.1 新建 validators.py

本阶段只实现：

```text
core/services/scheduler/graph/validators.py
```

第一版对外只暴露下面这些名字：

```python
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .nx_runtime import import_networkx
from .types import GraphWarning


def _node_sort_key(graph, node_id: str) -> Tuple[str, int, str, str]:
    data = graph.nodes[node_id]
    return (
        str(data.get("batch_id") or ""),
        int(data.get("seq") or 0),
        str(data.get("op_code") or ""),
        str(node_id),
    )


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
        edge_data = graph.edges[u, v]
        result.append(
            {
                "from": u,
                "to": v,
                "from_op_code": graph.nodes[u].get("op_code", u),
                "to_op_code": graph.nodes[v].get("op_code", v),
                "kind": edge_data.get("kind", "precedence"),
            }
        )
    return result


def is_dag(graph) -> bool:
    nx = import_networkx()
    return bool(nx.is_directed_acyclic_graph(graph))


def find_isolated_nodes(graph) -> List[str]:
    return [
        node_id
        for node_id in sorted(graph.nodes, key=lambda item: _node_sort_key(graph, item))
        if graph.in_degree(node_id) == 0 and graph.out_degree(node_id) == 0
    ]


def find_duplicate_seq_warnings(graph) -> List[GraphWarning]:
    grouped: Dict[Tuple[str, int], List[str]] = {}

    for node_id, data in graph.nodes(data=True):
        batch_id = data.get("batch_id")
        seq = data.get("seq")
        if not batch_id or seq is None:
            continue
        key = (str(batch_id), int(seq))
        grouped.setdefault(key, []).append(node_id)

    warnings: List[GraphWarning] = []
    for key in sorted(grouped):
        batch_id, seq = key
        node_ids = sorted(grouped[key], key=lambda item: _node_sort_key(graph, item))
        if len(node_ids) <= 1:
            continue
        op_codes = [
            str(graph.nodes[node_id].get("op_code") or "")
            for node_id in node_ids
        ]
        warnings.append(
            GraphWarning(
                code="DUPLICATE_SEQ",
                message="同一批次存在重复工序顺序号：batch_id={}, seq={}".format(batch_id, seq),
                data={
                    "batch_id": batch_id,
                    "seq": seq,
                    "node_ids": list(node_ids),
                    "op_codes": op_codes,
                },
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
                data={
                    "node_id": node_id,
                    "op_code": data.get("op_code"),
                    "batch_id": data.get("batch_id"),
                    "seq": data.get("seq"),
                },
            )
        )

    warnings.extend(find_duplicate_seq_warnings(graph))

    return warnings
```

输入边界：

```text
graph:
  必须是阶段 6 build_precedence_graph() 产出的内部 nx.DiGraph。
  validators.py 不负责构图，也不负责把业务 row 转成节点。
  函数签名不要把 NetworkX 类型写进对外注解，避免把可选依赖暴露到 graph 包外层。
```

输出边界：

```text
is_dag:
  返回 bool。

find_cycle_edges:
  返回 List[Dict[str, Any]]。
  没有环时返回 []。
  有环时只返回环上的边，不继续展开全图。

find_isolated_nodes:
  返回 List[str]，里面是 node_id。

find_duplicate_seq_warnings / collect_graph_warnings:
  返回 List[GraphWarning]。
  warning.data 必须只放 JSON 可序列化值。
```

禁止事项：

```text
不要在 validators.py 顶层 import networkx。
不要在 validators.py 里调用 build_linear_edges_by_batch / build_precedence_graph。
不要在 validators.py 里调用 metrics / analysis_service / exporter。
不要在 validators.py 里写 result_summary / diagnostics / OperationLogs。
不要在 validators.py 里接入 schedule_orchestrator、SGS、dispatch_rules。
```

### 7.2 DAG 和环检测规则

`is_dag(graph)` 只做一件事：

```text
通过 import_networkx() 懒加载 NetworkX。
调用 nx.is_directed_acyclic_graph(graph)。
返回 bool(...)。
```

`find_cycle_edges(graph)` 只做一件事：

```text
通过 import_networkx() 懒加载 NetworkX。
调用 nx.find_cycle(graph, orientation="original")。
如果抛 nx.NetworkXNoCycle，返回 []。
如果找到环，把环上的边转成业务可读的小字典。
```

环边输出字段第一版固定为：

```text
from
to
from_op_code
to_op_code
kind
```

字段来源：

```text
from / to:
  NetworkX 返回的 node_id。

from_op_code / to_op_code:
  graph.nodes[node_id].get("op_code", node_id)。

kind:
  graph.edges[from_id, to_id].get("kind", "precedence")。
```

有环时仍然不做：

```text
不调用 topological_sort。
不调用 dag_longest_path。
不调用 metrics.py。
不在本阶段阻止排产。
不把环拆掉继续分析。
```

NetworkX 异常处理口径：

```text
只捕获 nx.NetworkXNoCycle，因为它表示“没有环”这个正常结果。
不要捕获 NetworkXUnfeasible、NetworkXError、Exception 后改成空列表。
如果传入的图对象不符合 NetworkX 预期，让异常暴露给调用方或测试；不要在 validators.py 里吞掉。
```

### 7.3 孤立节点 warning

孤立节点判断标准：

```text
graph.in_degree(node_id) == 0
graph.out_degree(node_id) == 0
```

返回规则：

```text
find_isolated_nodes(graph):
  返回按 (batch_id, seq, op_code, node_id) 排序后的 node_id 列表。

collect_graph_warnings(graph):
  对每个孤立节点生成 GraphWarning(code="ISOLATED_OPERATION", ...)
```

warning 内容：

```python
GraphWarning(
    code="ISOLATED_OPERATION",
    message="发现孤立工序：{}".format(op_code),
    data={
        "node_id": node_id,
        "op_code": op_code,
        "batch_id": batch_id,
        "seq": seq,
    },
)
```

孤立节点的业务口径：

```text
孤立节点不一定是错误；单工序批次在第一版图里可能就是孤立节点。
所以阶段 7 只把它作为 warning 暴露出来，不抛异常、不阻止 report 模式、不改排产结果。
如果后续产品决定单工序批次不应提示 warning，需要先回 roadmap 更新口径，再改测试。
```

### 7.4 同批次重复 seq warning

重复 `seq` 判断标准：

```text
按 (batch_id, seq) 分组。
batch_id 不能为空，seq 不能是 None。
同一组 node 数量大于 1 时，生成 DUPLICATE_SEQ warning。
```

排序规则：

```text
每个重复组内的 node_id / op_code 按 (op_code, node_id) 排序。
所有 warning 按 (batch_id, seq) 排序。
```

warning 内容：

```python
GraphWarning(
    code="DUPLICATE_SEQ",
    message="同一批次存在重复工序顺序号：batch_id={}, seq={}".format(batch_id, seq),
    data={
        "batch_id": batch_id,
        "seq": seq,
        "node_ids": node_ids,
        "op_codes": op_codes,
    },
)
```

重复 `seq` 的业务口径：

```text
阶段 6 已经用 (seq, op_code, node_id) 保证边生成稳定。
阶段 7 必须继续把重复 seq 暴露出来，不能因为阶段 6 能稳定排序就把它当正常状态吞掉。
阶段 7 不判断谁先谁后才是业务正确顺序，不写自动修复。
```

### 7.5 collect_graph_warnings 汇总规则

`collect_graph_warnings(graph)` 第一版只汇总两类 warning：

```text
ISOLATED_OPERATION
DUPLICATE_SEQ
```

汇总顺序：

```text
1. 先按稳定顺序加入孤立节点 warning。
2. 再按稳定顺序加入重复 seq warning。
```

明确不放进 warnings 的内容：

```text
cycle_edges 不放进 warnings。
is_dag 不放进 warnings。
拓扑排序失败不放进 warnings，因为阶段 7 不运行拓扑排序。
关键路径失败不放进 warnings，因为阶段 7 不运行关键路径。
```

原因：

```text
cycle_edges 是更高优先级的结构结果，后续阶段 11 会根据 graph_block_on_cycle 决定 report / on 模式怎么处理。
warning 只放“不一定阻止继续分析，但必须让人看见”的图质量提示。
```

JSON 序列化要求：

```text
GraphWarning.data 中只能放 str / int / float / bool / None / list / dict。
node_ids 和 op_codes 必须是 list，不能是 set 或 tuple。
后续 exporter / analysis_service 可直接 json.dumps(asdict(warning), ensure_ascii=False)。
```

### 7.6 测试文件

新增：

```text
tests/scheduler_graph/test_validators.py
```

测试 1：模块导入不触发 NetworkX

```text
import core.services.scheduler.graph.validators
```

期望：

```text
模块导入不 import networkx。
只有调用 is_dag / find_cycle_edges 时才通过 import_networkx() 懒加载。
```

测试 2：无环

```text
A -> B -> C
```

期望：

```text
is_dag=True
cycle_edges=[]
```

测试 3：有环

```text
A -> B -> C -> A
```

期望：

```text
is_dag=False
cycle_edges 非空。
cycle_edges 里的每条记录都有 from / to / from_op_code / to_op_code / kind。
```

测试 4：孤立节点

```text
A
B -> C
```

期望：

```text
A 被识别为孤立节点。
collect_graph_warnings 返回 ISOLATED_OPERATION。
warning.data 包含 node_id / op_code / batch_id / seq。
```

测试 5：同批次重复 seq

```text
B001 seq=10
B001 seq=10
```

期望：

```text
出现 DUPLICATE_SEQ warning。
warning.data 包含 batch_id / seq / node_ids / op_codes。
node_ids 和 op_codes 顺序稳定。
```

测试 6：不同批次相同 seq 不报警

```text
B001 seq=10
B002 seq=10
```

期望：

```text
不出现 DUPLICATE_SEQ warning。
```

测试 7：warning 可 JSON 序列化

```text
json.dumps([asdict(warning) for warning in warnings], ensure_ascii=False)
```

期望：

```text
不报错。
输出里没有 set / tuple / dataclass 原对象。
```

测试 8：校验函数不修改原图

```text
先记录 graph.nodes(data=True) 和 graph.edges(data=True)。
调用 is_dag / find_cycle_edges / collect_graph_warnings。
再比对节点、边和属性。
```

期望：

```text
节点、边、属性不被修改。
```

测试 9：有环时不调用阶段 8 指标

```text
构造 A -> B -> A。
只调用阶段 7 函数。
```

期望：

```text
能拿到 cycle_edges。
测试不需要 metrics.py，不需要 topological_sort，不需要 dag_longest_path。
```

测试 10：和阶段 6 builder 串起来

```text
用 OperationGraphNode -> build_linear_edges_by_batch -> build_precedence_graph -> validators。
```

期望：

```text
正常线性批次 is_dag=True。
重复 seq 仍能通过阶段 6 建图，但阶段 7 返回 DUPLICATE_SEQ warning。
```

### 7.7 阶段验收清单

```text
[ ] 实现 core/services/scheduler/graph/validators.py。
[ ] 新增 tests/scheduler_graph/test_validators.py。
[ ] validators.py 只 import nx_runtime.py、types.py 和标准库 typing / collections，不在顶层 import networkx。
[ ] is_dag 只调用 nx.is_directed_acyclic_graph，不做额外业务判断。
[ ] find_cycle_edges 只捕获 nx.NetworkXNoCycle，不 broad except。
[ ] find_cycle_edges 输出 from / to / from_op_code / to_op_code / kind。
[ ] find_isolated_nodes 按稳定顺序返回 node_id。
[ ] collect_graph_warnings 返回 ISOLATED_OPERATION 和 DUPLICATE_SEQ。
[ ] DUPLICATE_SEQ 按 (batch_id, seq) 分组，不跨批次误报。
[ ] warning.data 全部 JSON 可序列化。
[ ] 有环时阶段 7 只检测，不运行拓扑排序、关键路径或影响范围。
[ ] 阶段 7 不改 graph 节点、边和属性。
[ ] 不修改 metrics.py、analysis_service.py、exporter.py、ready_queue.py、scoring.py。
[ ] 不修改 schedule_orchestrator.py、schedule_optimizer.py、SGS、dispatch_rules、summary、OperationLogs、页面和数据库。
[ ] tests/scheduler_graph/test_validators.py 通过。
[ ] 阶段 5 / 阶段 6 已有 graph 基础测试继续通过。
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_validators.py tests/scheduler_graph/test_precedence_builder.py tests/scheduler_graph/test_input_adapter.py tests/scheduler_graph/test_graph_types.py tests/scheduler_graph/test_id_policy.py tests/scheduler_graph/test_nx_runtime.py
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/graph tests/scheduler_graph
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/graph
```

验收口径：

```text
阶段 7 完成后，系统仍然不改变任何排产结果。
阶段 7 完成后，graph_analysis_mode=off 仍不要求安装 NetworkX，因为 validators.py 只在被调用时懒加载。
阶段 7 完成后，后续阶段 8 必须先确认 is_dag=True，再做 topological_sort、topological_generations、dag_longest_path。
阶段 7 完成后，阶段 11 才能根据 graph_block_on_cycle 决定 report / on 模式遇到环时怎么处理。
```

## 阶段 8：拓扑排序、层级、关键路径、影响范围

本阶段的目标仍然很窄：只在 `core/services/scheduler/graph/metrics.py` 里计算“图指标”。它读取阶段 6 已经建好的内部 `nx.DiGraph`，默认调用方已经先用阶段 7 确认 `is_dag=True`，然后输出拓扑顺序、层级、关键路径和每个节点的影响范围。

大白话说，阶段 8 只回答“这张工序图里谁应该在谁前面、哪条链最长、某道工序会影响后面多少工序”。它不修图、不决定要不要阻止排产、不接入 `result_summary`、不改变 SGS 候选和打分，也不因为图有问题就悄悄返回空结果。

### 8.0 整体实现要求

本阶段必须把下面这些实现原则当成硬约束写进设计和验收里：

```text
优雅简洁：
- metrics.py 只做四类指标：拓扑顺序、层级 generation、关键路径、影响范围。
- 拓扑顺序和 generation 使用同一套稳定排序口径，避免两个函数看起来都对但顺序不一致。
- 关键路径只在一个内部加权图里处理“节点工时转边权重”，不要把这套转换逻辑散落到多个函数。
- build_node_metrics 只组装每个节点的指标小字典，不引入 GraphAnalysisSummary；统一摘要留给阶段 9 analysis_service。
- 不新增 graph_metrics_service.py、critical_path_builder.py、impact_analyzer.py 这类过早拆分文件；第一版一个 metrics.py 足够清楚。

不做过度兜底：
- 不允许 broad except Exception 后返回空拓扑、空关键路径或 0 分钟。
- 不允许有环时吞掉 NetworkXUnfeasible，再假装“没有关键路径”。
- 不允许 duration_minutes 缺失或异常时随手用业务猜测补时长；阶段 6 已经把节点属性写进图，本阶段只读取合同字段。
- 不允许 lag_minutes 为负数时悄悄改成 0；阶段 6 已经 fail fast，阶段 8 不重复兜底。

不做静默回退：
- 阶段 8 只接收阶段 6 产出的内部 nx.DiGraph。
- 阶段 8 不接收 OperationGraphNode 列表重新构图，不接收 dict / ORM / OpForScheduleAlgo 原始对象。
- 阶段 8 不在发现环时改走“只算一部分节点”的降级路径；调用方必须先用阶段 7 判断 DAG。
- 如果后续 2000 节点性能验证发现 downstream_critical_minutes 太慢，不允许在代码里静默关闭字段；要停止并回 roadmap 决定是优化缓存、拆阶段，还是调整验收字段。

不做过度防御性编程：
- 不兼容十几种字段别名，只读取阶段 6 已经写进 graph node / edge 的 duration_minutes、batch_id、seq、op_code、lag_minutes。
- 不在 metrics.py 里查数据库、读配置、读 Flask request、访问 repo、调用 ScheduleService、调用 GreedyScheduler。
- 不在 metrics.py 里调用 validators.py、analysis_service.py、exporter.py、ready_queue.py、scoring.py，避免图指标层反向依赖上层编排。
- 不为 Python 3.10+ 语法图省事；仓库仍要兼容 Python 3.8，所以不要使用 itertools.pairwise、list[str]、dict[str, int] 这类 3.9/3.10 之后才稳的写法。

高内聚低耦合：
- metrics.py 可以 import nx_runtime.py 和标准库 typing。
- metrics.py 不 import precedence_builder.py、validators.py、analysis_service.py、exporter.py、ready_queue.py、scoring.py。
- metrics.py 不 import Flask route、数据库、summary、OperationLogs、SGS、dispatch_rules。
- nx.DiGraph 仍只在 core/services/scheduler/graph/ 内部流转，不能流到 Controller、页面、数据库、Excel 导出、summary 外层或 SGS。
- 阶段 8 不改变 algo_ops_to_schedule、seed_results、frozen_op_ids、batch_order、sorted_ops、SGS 候选集合和任何排产结果。
```

### 8.1 新建 / 实现 metrics.py

本阶段只实现：

```text
core/services/scheduler/graph/metrics.py
```

第一版对外只暴露下面这些名字：

```python
from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from .nx_runtime import import_networkx

_SOURCE_NODE_ID = "__GRAPH_METRICS_SOURCE__"


def _node_sort_key(graph: Any, node_id: str) -> Tuple[str, int, str, str]:
    data = graph.nodes[node_id]
    return (
        str(data.get("batch_id") or ""),
        int(data.get("seq") or 0),
        str(data.get("op_code") or ""),
        str(node_id),
    )


def get_topological_order(graph) -> List[str]:
    return [
        node_id
        for group in get_topological_generations(graph)
        for node_id in group
    ]


def get_topological_generations(graph) -> List[List[str]]:
    nx = import_networkx()
    return [
        sorted(list(group), key=lambda node_id: _node_sort_key(graph, node_id))
        for group in nx.topological_generations(graph)
    ]


def get_generation_index(graph) -> Dict[str, int]:
    result: Dict[str, int] = {}

    for index, group in enumerate(get_topological_generations(graph)):
        for node_id in group:
            result[node_id] = index

    return result


def build_duration_weighted_graph(graph):
    ...


def get_critical_path(graph) -> Tuple[List[str], int]:
    ...


def get_upstream_operations(graph, node_id: str) -> Set[str]:
    ...


def get_downstream_operations(graph, node_id: str) -> Set[str]:
    ...


def get_impact_count(graph, node_id: str) -> int:
    ...


def get_downstream_critical_minutes(graph, node_id: str) -> int:
    ...


def build_node_metrics(graph) -> Dict[str, Dict[str, Any]]:
    ...
```

输入边界：

```text
graph:
  必须是阶段 6 build_precedence_graph() 产出的内部 nx.DiGraph。
  调用拓扑、generation、关键路径、影响范围前，调用方必须先用阶段 7 确认 is_dag=True。
  metrics.py 不负责构图，也不负责把业务 row 转成节点。
  函数签名不要把 NetworkX 类型写进对外注解，避免把可选依赖暴露到 graph 包外层。

node_id:
  get_upstream_operations / get_downstream_operations / get_impact_count / get_downstream_critical_minutes 接收图里已有的 node_id。
  node_id 不存在时，让 NetworkX 的错误直接暴露，不要返回空集合伪装成“没有影响”。
```

输出边界：

```text
topological_order:
  返回 List[str]，里面是 node_id。
  顺序按 generation 从小到大，同一 generation 内按 (batch_id, seq, op_code, node_id) 稳定排序。

topological_generations:
  返回 List[List[str]]。
  第 0 层是没有前置的工序，第 1 层是只依赖前面层级的工序。

generation_index:
  返回 Dict[str, int]，key 是 node_id，value 是 generation 序号。

critical_path:
  返回 Tuple[List[str], int]。
  List[str] 是关键路径上的 node_id。
  int 是关键路径总分钟数。

upstream / downstream:
  返回 Set[str]，只用于内部计算和测试断言，不直接写 JSON。

node_metrics:
  返回 Dict[str, Dict[str, Any]]。
  第一层 key 是 node_id。
  第二层字段必须是 JSON 可序列化值，后续 exporter / analysis_service 可以直接取用。
```

官方定义里，拓扑排序要求如果有边 `u -> v`，那么 `u` 必须出现在 `v` 前面；这刚好对应“前工序必须早于后工序”。

禁止事项：

```text
不要在 metrics.py 顶层 import networkx。
不要在 metrics.py 里调用 build_linear_edges_by_batch / build_precedence_graph。
不要在 metrics.py 里调用 validators / analysis_service / exporter。
不要在 metrics.py 里写 result_summary / diagnostics / OperationLogs。
不要在 metrics.py 里接入 schedule_orchestrator、SGS、dispatch_rules。
不要在 metrics.py 里捕获 NetworkXUnfeasible 后返回空结果。
```

### 8.2 拓扑顺序和层级规则

拓扑顺序和层级必须共用 `get_topological_generations` 这一套稳定输出：

```text
1. 通过 import_networkx() 懒加载 NetworkX。
2. 调用 nx.topological_generations(graph)。
3. 每一层内部按 (batch_id, seq, op_code, node_id) 排序。
4. get_topological_order 只把 generation 摊平成一维列表。
5. get_generation_index 只根据 get_topological_generations 的结果填 index。
```

这样做的目的：

```text
同一张图里，topological_order 和 generation_index 不会各用一套顺序规则。
同层并行工序的顺序稳定，测试和后续摘要不会因为 NetworkX 内部迭代顺序抖动。
```

有环时的口径：

```text
nx.topological_generations 会抛 NetworkXUnfeasible。
metrics.py 不捕获它。
analysis_service 阶段 9 必须先用 validators.is_dag(graph) 判断，只有 DAG 才调用阶段 8 指标。
阶段 8 单测要证明有环时不会被吞成空拓扑。
```

### 8.3 关键路径计算

NetworkX 的 `dag_longest_path` 是按边权重算最长路径。当前工时在“工序节点”上，所以要把节点工时转成边权重。

在 `metrics.py` 里实现：

```python
def _duration_of(graph, node_id: str) -> int:
    return int(graph.nodes[node_id]["duration_minutes"])


def build_duration_weighted_graph(graph):
    nx = import_networkx()

    weighted = nx.DiGraph()
    weighted.add_node(_SOURCE_NODE_ID)

    for node_id, data in graph.nodes(data=True):
        weighted.add_node(node_id, **dict(data))

    for node_id in graph.nodes:
        if graph.in_degree(node_id) == 0:
            weighted.add_edge(_SOURCE_NODE_ID, node_id, weight=_duration_of(graph, node_id))

    for u, v, data in graph.edges(data=True):
        lag_minutes = int(data["lag_minutes"])
        weighted.add_edge(u, v, weight=_duration_of(graph, v) + lag_minutes)

    return weighted


def _path_weight(graph, path: List[str]) -> int:
    total = 0
    for from_node_id, to_node_id in zip(path, path[1:]):
        total += int(graph.edges[from_node_id, to_node_id]["weight"])
    return total


def get_critical_path(graph) -> Tuple[List[str], int]:
    nx = import_networkx()

    weighted = build_duration_weighted_graph(graph)

    raw_path = nx.dag_longest_path(
        weighted,
        weight="weight",
        topo_order=get_topological_order(weighted),
    )
    minutes = _path_weight(weighted, raw_path)

    path = [node_id for node_id in raw_path if node_id != _SOURCE_NODE_ID]
    return path, minutes
```

关键规则：

```text
节点工时：
  graph.nodes[node_id]["duration_minutes"]。
  缺字段、None、非数字时直接暴露 KeyError / TypeError / ValueError，不在 metrics.py 里改成 0。

边等待时间：
  graph.edges[u, v]["lag_minutes"]。
  第一版阶段 6 生成的边通常是 0，但阶段 8 要保留这个字段，让后续显式等待边能自然参与计算。
  缺字段或非数字时直接暴露错误，不在 metrics.py 里补默认等待时间。

虚拟起点：
  _SOURCE_NODE_ID 只存在于 build_duration_weighted_graph 返回的新图里。
  它不写回原图，不出现在最终 critical_path 里。

权重转换：
  无前置节点：_SOURCE_NODE_ID -> node 的 weight = node.duration_minutes。
  普通边 u -> v 的 weight = v.duration_minutes + edge.lag_minutes。

总分钟数：
  用最终选中的 raw_path 上各条边 weight 相加。
  不用 itertools.pairwise，因为本仓库要兼容 Python 3.8。
```

关键路径并列时的口径：

```text
先用 get_topological_order(weighted) 给 dag_longest_path 一个稳定 topo_order。
同样长度的路径如果存在并列，第一版接受 NetworkX 在稳定拓扑顺序下选出的那一条。
不要为了“看起来更聪明”额外写复杂并列评分。
```

明确不做：

```text
不把资源冲突、人员冲突、设备冲突转成关键路径边。
不根据交期、优先级、冻结窗口调整关键路径。
不把外协天数重新折算成等待时间；阶段 6 第一版 lag_minutes 已经固定为 0。
不修改原始 graph 的节点、边和属性。
```

### 8.4 影响范围计算

在 `metrics.py` 实现：

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


def build_node_metrics(graph) -> Dict[str, Dict[str, Any]]:
    critical_path, _critical_minutes = get_critical_path(graph)
    critical_set = set(critical_path)
    critical_rank = {
        node_id: index
        for index, node_id in enumerate(critical_path)
    }
    generation_index = get_generation_index(graph)

    result: Dict[str, Dict[str, Any]] = {}

    for node_id in graph.nodes:
        result[node_id] = {
            "is_on_critical_path": node_id in critical_set,
            "critical_path_rank": critical_rank.get(node_id),
            "impact_count": get_impact_count(graph, node_id),
            "generation_index": generation_index[node_id],
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

node_metrics 字段第一版固定为：

```text
is_on_critical_path:
  bool，当前节点是否在全图关键路径上。

critical_path_rank:
  当前节点在关键路径上的序号；不在关键路径上则为 None。

impact_count:
  当前节点后面会影响多少个节点。

generation_index:
  当前节点在第几层。

downstream_critical_minutes:
  从当前节点开始往后看，最长链路还需要多少分钟。
```

性能口径：

```text
get_downstream_critical_minutes 会对每个节点的下游子图再算一次关键路径，小图阶段可以接受。
阶段 8 不做缓存优化，先把语义写准、测试锁住。
阶段 18/PR-4 做 2000 节点性能记录时，如果这个字段明显拖慢，不能静默关闭；要回到 roadmap 明确改成缓存版或拆成后续优化项。
```

### 8.5 测试文件

新增：

```text
tests/scheduler_graph/test_metrics_topology.py
tests/scheduler_graph/test_metrics_critical_path.py
tests/scheduler_graph/test_metrics_impact.py
```

测试 1：模块导入不触发 NetworkX

```text
import core.services.scheduler.graph.metrics
```

期望：

```text
模块导入不 import networkx。
只有调用指标函数时才通过 import_networkx() 懒加载。
```

测试 2：线性拓扑顺序

```text
A -> B -> C

期望：
topological_order = [A, B, C]
generation_index[A] = 0
generation_index[B] = 1
generation_index[C] = 2
```

测试 3：并行层级稳定排序

```text
A -> C
B -> C

期望：
A 和 B 都在第 0 层
C 在第 1 层
同层节点按 (batch_id, seq, op_code, node_id) 稳定排序。
```

测试 4：有环时不吞异常

```text
A -> B -> A
```

期望：

```text
get_topological_order 或 get_topological_generations 抛 NetworkXUnfeasible。
metrics.py 不返回 []、不返回 0、不把有环图伪装成正常 DAG。
```

测试 5：线性关键路径

```text
A(10) -> B(20) -> C(30)

期望：
critical_path = [A, B, C]
critical_path_minutes = 60
```

测试 6：分叉关键路径

```text
A(10) -> B(100) -> D(10)
A(10) -> C(20)  -> D(10)

期望：
critical_path = [A, B, D]
critical_path_minutes = 120
```

测试 7：边等待时间参与关键路径

```text
A(10) -> B(20), edge lag_minutes=1440

期望：
critical_path_minutes = 1470
```

测试 8：单节点图关键路径

```text
A(10)
```

期望：

```text
critical_path = [A]
critical_path_minutes = 10
generation_index[A] = 0
impact_count[A] = 0
downstream_critical_minutes[A] = 10
```

测试 9：影响范围

```text
A -> B -> C
A -> D

期望：
A downstream = {B, C, D}
B downstream = {C}
C downstream = {}
A impact_count = 3
```

测试 10：上游范围

```text
A -> B -> C
D -> C
```

期望：

```text
C upstream = {A, B, D}
A upstream = {}
```

测试 11：build_node_metrics 汇总字段

```text
A(10) -> B(100) -> D(10)
A(10) -> C(20)  -> D(10)
```

期望：

```text
每个 node_id 都有 is_on_critical_path / critical_path_rank / impact_count / generation_index / downstream_critical_minutes。
B 在关键路径上。
C 不在关键路径上，critical_path_rank is None。
A impact_count = 3。
D downstream_critical_minutes = 10。
```

测试 12：指标函数不修改原图

```text
先记录 graph.nodes(data=True) 和 graph.edges(data=True)。
调用 get_topological_order / get_critical_path / build_node_metrics。
再比对节点、边和属性。
```

期望：

```text
原图节点、边、属性不被修改。
build_duration_weighted_graph 返回的新图可以包含 _SOURCE_NODE_ID，但原图不能出现这个虚拟节点。
```

测试 13：metrics 不反向依赖上层模块

```text
导入 metrics.py 后检查 sys.modules。
```

期望：

```text
不导入 validators.py。
不导入 analysis_service.py。
不导入 exporter.py。
不导入 ready_queue.py。
不导入 scoring.py。
不导入 schedule_orchestrator.py。
```

测试 14：缺合同字段不静默补 0

```text
构造缺 duration_minutes 的节点。
构造缺 lag_minutes 的边。
```

期望：

```text
get_critical_path 直接暴露 KeyError / TypeError / ValueError。
不要返回 0 分钟。
不要返回空 critical_path。
不要把缺字段解释成“没有工时”或“没有等待”。
```

### 8.6 阶段验收清单

```text
[ ] 实现 core/services/scheduler/graph/metrics.py。
[ ] 新增 tests/scheduler_graph/test_metrics_topology.py。
[ ] 新增 tests/scheduler_graph/test_metrics_critical_path.py。
[ ] 新增 tests/scheduler_graph/test_metrics_impact.py。
[ ] metrics.py 只 import nx_runtime.py 和标准库 typing，不在顶层 import networkx。
[ ] metrics.py 不 import validators.py / analysis_service.py / exporter.py / ready_queue.py / scoring.py。
[ ] get_topological_order / get_topological_generations / get_generation_index 使用同一套稳定 generation 口径。
[ ] 有环图调用拓扑或关键路径时异常暴露，不返回空结果。
[ ] build_duration_weighted_graph 用虚拟起点把节点工时转成边权重，不修改原图。
[ ] critical_path_minutes 包含节点 duration_minutes 和边 lag_minutes。
[ ] 缺 duration_minutes / lag_minutes 时不静默补 0。
[ ] get_upstream_operations / get_downstream_operations 使用 NetworkX ancestors / descendants。
[ ] build_node_metrics 输出 is_on_critical_path / critical_path_rank / impact_count / generation_index / downstream_critical_minutes。
[ ] build_node_metrics 输出值全部 JSON 可序列化。
[ ] 阶段 8 不写 result_summary / diagnostics / OperationLogs。
[ ] 阶段 8 不修改 schedule_orchestrator.py、schedule_optimizer.py、SGS、dispatch_rules、summary、页面和数据库。
[ ] tests/scheduler_graph/test_metrics_topology.py 通过。
[ ] tests/scheduler_graph/test_metrics_critical_path.py 通过。
[ ] tests/scheduler_graph/test_metrics_impact.py 通过。
[ ] 阶段 5 / 阶段 6 / 阶段 7 已有 graph 基础测试继续通过。
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_metrics_topology.py tests/scheduler_graph/test_metrics_critical_path.py tests/scheduler_graph/test_metrics_impact.py tests/scheduler_graph/test_validators.py tests/scheduler_graph/test_precedence_builder.py tests/scheduler_graph/test_input_adapter.py tests/scheduler_graph/test_graph_types.py tests/scheduler_graph/test_id_policy.py tests/scheduler_graph/test_nx_runtime.py
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/graph tests/scheduler_graph
[ ] PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/graph
```

验收口径：

```text
阶段 8 完成后，系统仍然不改变任何排产结果。
阶段 8 完成后，graph_analysis_mode=off 仍不要求安装 NetworkX，因为 metrics.py 只在被调用时懒加载。
阶段 8 完成后，有环图仍由阶段 7 / 阶段 11 的策略处理；阶段 8 不自己兜底。
阶段 8 完成后，阶段 9 可以直接调用 metrics.py 组装 GraphAnalysisSummary，不需要重新设计指标字段。
```

## 阶段 9：图导出和统一分析服务入口

阶段 9 是 PR-2 图核心模块的最后一段，不接排产主链，不写 `result_summary`，不碰页面、数据库、SGS、ready queue 或评分。它只把阶段 5 到阶段 8 已经做好的零件串成一个清楚入口，并提供纯 Python / 纯 JSON 友好的导出结果。

大白话说，前面阶段已经能把工序变成节点、把同一批次工序连成边、检查图有没有问题、算拓扑和关键路径。阶段 9 要做的是把这些能力收成两个清楚工具：

```text
analysis_service.py：
  给后续阶段 10 调用的统一图分析入口。
  它负责串联建图、校验、指标和摘要组装。

exporter.py：
  给测试和后续 debug/export 用的普通 dict 导出工具。
  它只把 graph / summary 转成 JSON 可序列化数据，不做业务判断。
```

### 9.0 整体实现要求

本阶段必须把下面这些实现原则当成硬约束写进设计、代码和验收里：

```text
优雅简洁：
- analysis_service.py 只做编排，不重新实现 input_adapter、precedence_builder、validators、metrics 里的逻辑。
- exporter.py 只做导出，不判断排产是否可继续、不读配置、不接数据库、不写日志。
- 阶段 9 可以做一个很小的类型补齐：如果要把阶段 8 的 build_node_metrics 放进摘要，就在 GraphAnalysisSummary 增加 node_metrics 字段；不要为了这一点新增复杂结果对象。
- 第一版不要新增 graph_analysis_result.py、summary_builder.py、export_schema.py 这类过早拆分文件；两个占位文件加必要的 types.py 小补齐即可。

不做过度兜底：
- 不允许 broad except Exception 后返回空摘要。
- 不允许 NetworkX 未安装、版本不对、输入合同错误时伪装成“没有图数据”。
- 不允许 duration_minutes / lag_minutes / seq 缺失或异常时在阶段 9 里偷偷补 0。
- 不允许有环时继续调用 topological_sort、topological_generations、dag_longest_path 或 build_node_metrics。
- 不允许 exporter 写万能清洗器，把任意对象 str() 之后塞进 JSON；如果上游把 datetime 原对象、数据库对象、tuple key 传下来，应该暴露问题并回前置阶段修。

不做静默回退：
- 图输入坏了就暴露 GraphInputContractError / GraphBuildContractError / NetworkX 版本错误等明确错误，不吞掉。
- DAG 有环是业务图质量结果，返回 is_dag=False、cycle_edges 和明确 warning；这不是异常，也不是“无数据”。
- 如果未来性能验证发现 node_metrics 太慢，不允许在代码里悄悄跳过；要回 roadmap 决定是优化、拆阶段，还是调整字段。

不做过度防御性编程：
- analysis_service.py 只接收 Iterable[OperationGraphNode]，不兼容 dict、ORM、OpForScheduleAlgo、BatchOperation 等多种原始对象；这些对象必须先经过 input_adapter.py。
- exporter.py 只导出阶段 6/8/9 明确承诺的字段，不为未知字段做猜测转换。
- 不写“如果字段 A 没有就试字段 B/C/D”的兼容分支。
- 不使用 Python 3.9+ 写法；生产代码和示例都继续用 List / Dict / Optional / Tuple / Any 这类 Python 3.8 兼容注解。

高内聚低耦合：
- analysis_service.py 可以 import precedence_builder.py、validators.py、metrics.py、types.py。
- exporter.py 可以 import dataclasses.asdict 和 types.py；JSON 校验放在测试里做。
- precedence_builder.py、validators.py、metrics.py 不反向 import analysis_service.py / exporter.py。
- analysis_service.py / exporter.py 顶层不直接 import networkx；NetworkX 仍只能通过 nx_runtime.import_networkx() 懒加载。
- nx.DiGraph 仍只在 core/services/scheduler/graph/ 内部流转，不能流到 Controller、页面、数据库、Excel 导出、summary 外层或排产主链。
- 阶段 9 不改变 algo_ops_to_schedule、seed_results、frozen_op_ids、batch_order、sorted_ops、SGS 候选集合和任何排产结果。
```

### 9.1 阶段目标与上下游合同

阶段 9 的输入来自阶段 5：

```python
from typing import Iterable

from core.services.scheduler.graph.types import OperationGraphNode

nodes: Iterable[OperationGraphNode]
```

阶段 9 的核心输出是：

```python
from core.services.scheduler.graph.types import GraphAnalysisSummary

summary: GraphAnalysisSummary
```

后续阶段 10 只能拿 `GraphAnalysisSummary` 或 `graph_summary_to_dict(summary)`，不能拿内部 `nx.DiGraph`。

阶段 9 允许内部短暂持有 `graph`：

```text
OperationGraphNode 列表
  ↓
build_linear_edges_by_batch()
  ↓
build_precedence_graph()
  ↓
validators.is_dag() / find_cycle_edges() / collect_graph_warnings()
  ↓
如果 is_dag=True，再调用 metrics.py
  ↓
GraphAnalysisSummary
```

阶段 9 不允许跨到阶段 10：

```text
不改 schedule_orchestrator.py。
不改 schedule_summary_assembly.py。
不改 schedule_persistence.py。
不写 result_summary["algo"]["graph_analysis"]。
不写 result_summary["diagnostics"]["graph_analysis"]。
不写 OperationLogs。
不新增页面入口。
```

### 9.2 必要类型补齐

阶段 8 已经产出 `build_node_metrics(graph)`，里面包含每个节点是否在关键路径、影响多少后续节点、所在层级等字段。阶段 9 要让这些指标进入统一摘要，所以允许在 `core/services/scheduler/graph/types.py` 做一个最小补齐：

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class GraphAnalysisSummary:
    node_count: int
    edge_count: int
    is_dag: bool
    cycle_edges: List[Dict[str, Any]]
    topological_order: List[str]
    critical_path: List[str]
    critical_path_minutes: int
    node_metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    warnings: List[GraphWarning] = field(default_factory=list)
```

补齐规则：

```text
node_metrics:
  第一层 key 是 node_id。
  第二层固定使用阶段 8 build_node_metrics 的字段：
    is_on_critical_path
    critical_path_rank
    impact_count
    generation_index
    downstream_critical_minutes
  所有值必须可 json.dumps(..., ensure_ascii=False)。

warnings:
  可以改成 default_factory=list，方便有环和空 warning 场景。
  不要改变 GraphWarning 的 code/message/data 结构。
```

测试要求：

```text
tests/scheduler_graph/test_graph_types.py 继续通过。
新增或补充一条 GraphAnalysisSummary 可 json.dumps(asdict(summary), ensure_ascii=False) 的测试。
```

禁止事项：

```text
不要把 nx.DiGraph 放进 GraphAnalysisSummary。
不要把 OperationGraphNode / OperationGraphEdge 原对象列表放进 GraphAnalysisSummary。
不要为了阶段 9 新增复杂嵌套 DTO；阶段 10 需要小摘要时从 summary 再投影。
```

### 9.3 实现 exporter.py

实现文件：

```text
core/services/scheduler/graph/exporter.py
```

第一版只暴露三个函数：

```python
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from .types import GraphAnalysisSummary, GraphWarning


def graph_to_plain_dict(graph: Any) -> Dict[str, Any]:
    ...


def graph_warning_to_dict(warning: GraphWarning) -> Dict[str, Any]:
    ...


def graph_summary_to_dict(summary: GraphAnalysisSummary) -> Dict[str, Any]:
    ...
```

`graph_to_plain_dict(graph)` 输出结构固定为：

```json
{
  "nodes": [
    {
      "id": "op:B001:OP10:123",
      "batch_id": "B001",
      "op_code": "OP10",
      "seq": 10,
      "duration_minutes": 120
    }
  ],
  "edges": [
    {
      "from": "op:B001:OP10:123",
      "to": "op:B001:OP20:124",
      "kind": "precedence",
      "lag_minutes": 0
    }
  ]
}
```

节点排序规则：

```text
按 (batch_id, seq, op_code, id) 稳定排序。
如果节点缺少这些属性，让 KeyError / TypeError 暴露，不在 exporter.py 里猜默认值。
```

边排序规则：

```text
按 (from_batch_id, from_seq, from_op_code, from, to) 稳定排序。
如果 from/to 节点不在图里，让 NetworkX 或 KeyError 暴露；阶段 6 已经负责边合同。
```

`graph_warning_to_dict(warning)` 输出结构固定为：

```json
{
  "code": "DUPLICATE_SEQ",
  "message": "同一批次存在重复工序顺序号：batch_id=B001, seq=10",
  "data": {
    "batch_id": "B001",
    "seq": 10,
    "node_ids": ["op:B001:OP10:123"]
  }
}
```

`graph_summary_to_dict(summary)` 输出结构固定为：

```json
{
  "node_count": 3,
  "edge_count": 2,
  "is_dag": true,
  "cycle_edges": [],
  "topological_order": ["op:B001:OP10:123", "op:B001:OP20:124"],
  "critical_path": ["op:B001:OP10:123", "op:B001:OP20:124"],
  "critical_path_minutes": 240,
  "node_metrics": {
    "op:B001:OP10:123": {
      "is_on_critical_path": true,
      "critical_path_rank": 0,
      "impact_count": 1,
      "generation_index": 0,
      "downstream_critical_minutes": 240
    }
  },
  "warnings": []
}
```

导出验收：

```python
payload = graph_summary_to_dict(summary)
json.dumps(payload, ensure_ascii=False)

graph_payload = graph_to_plain_dict(graph)
json.dumps(graph_payload, ensure_ascii=False)
```

禁止事项：

```text
不要在 exporter.py 顶层 import networkx。
不要在 exporter.py 里 import input_adapter.py、schedule_orchestrator.py、summary、数据库、Flask。
不要在 exporter.py 里修改 graph。
不要把 graph_to_plain_dict 输出直接塞进 OperationLogs 或公开 result_summary；完整 nodes/edges 只给测试和后续 debug/export 使用。
不要写递归万能 sanitizer；导出失败说明前置合同坏了。
```

### 9.4 实现 analysis_service.py

```python
from __future__ import annotations

from typing import Iterable

from .metrics import build_node_metrics, get_critical_path, get_topological_order
from .precedence_builder import build_linear_edges_by_batch, build_precedence_graph
from .types import GraphAnalysisSummary, GraphWarning, OperationGraphNode
from .validators import collect_graph_warnings, find_cycle_edges, is_dag


class ScheduleGraphAnalysisService:
    """
    工序图分析服务。

    对外不暴露 NetworkX。
    """

    def _build_graph_for_linear_batches(
        self,
        nodes: Iterable[OperationGraphNode],
    ) -> object:
        node_list = list(nodes)
        edges = build_linear_edges_by_batch(node_list)
        return build_precedence_graph(node_list, edges)

    def analyze_linear_batches(
        self,
        nodes: Iterable[OperationGraphNode],
    ) -> GraphAnalysisSummary:
        graph = self._build_graph_for_linear_batches(nodes)

        cycle_edges = find_cycle_edges(graph)
        dag_ok = is_dag(graph)
        warnings = collect_graph_warnings(graph)

        topological_order = []
        critical_path = []
        critical_path_minutes = 0
        node_metrics = {}

        if dag_ok:
            topological_order = get_topological_order(graph)
            critical_path, critical_path_minutes = get_critical_path(graph)
            node_metrics = build_node_metrics(graph)
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
            node_metrics=node_metrics,
            warnings=warnings,
        )

        return summary
```

实现细节：

```text
_build_graph_for_linear_batches:
  私有方法，只给 analyze_linear_batches 用。
  负责 list(nodes)、build_linear_edges_by_batch、build_precedence_graph。
  不对外返回给排产主链。

analyze_linear_batches:
  唯一稳定入口。
  接收 Iterable[OperationGraphNode]。
  返回 GraphAnalysisSummary。
  不返回 graph。
  不导出 dict；需要 dict 时由调用方显式调用 exporter.graph_summary_to_dict(summary)。

有环处理：
  find_cycle_edges(graph) 先拿到 cycle_edges。
  is_dag(graph) 为 False 时，不调用 metrics.py。
  topological_order / critical_path / node_metrics 保持空结构。
  critical_path_minutes 保持 0。
  warnings 追加 GRAPH_HAS_CYCLE。

无环处理：
  调用 get_topological_order(graph)。
  调用 get_critical_path(graph)。
  调用 build_node_metrics(graph)。
  这些调用只能发生在 dag_ok=True 分支里。
```

为什么有环时允许空结构：

```text
这是明确状态，不是静默回退。
summary.is_dag=False 和 cycle_edges 已经告诉调用方“这张图不能算拓扑和关键路径”。
阶段 11 / on 模式再决定是否阻止排产；阶段 9 不做这个业务决定。
```

错误暴露口径：

```text
nodes 不是 OperationGraphNode：
  由 build_linear_edges_by_batch / build_precedence_graph 暴露 GraphBuildContractError。

字段缺失或类型不对：
  OperationGraphNode 自己的构造、阶段 5 input_adapter、阶段 6 builder 已经 fail fast；阶段 9 不补字段。

NetworkX 没安装或版本不等于 3.1：
  由 nx_runtime.import_networkx() 暴露明确错误。

DAG 有环：
  不是 Python 异常，返回 GraphAnalysisSummary(is_dag=False)。
```

依赖方向：

```text
analysis_service.py -> precedence_builder.py
analysis_service.py -> validators.py
analysis_service.py -> metrics.py
analysis_service.py -> types.py

禁止反向：
precedence_builder.py 不 import analysis_service.py。
validators.py 不 import analysis_service.py。
metrics.py 不 import analysis_service.py。
exporter.py 不 import analysis_service.py。
```

禁止事项：

```text
不要在 analysis_service.py 顶层 import networkx。
不要在 analysis_service.py 里调用 input_adapter.py；阶段 10 接入时再由 orchestrator 侧先把业务 row 转成 OperationGraphNode。
不要在 analysis_service.py 里 import schedule_orchestrator.py、schedule_optimizer.py、GreedyScheduler、SummaryBuildContext、OperationLogs、数据库、Flask。
不要在 analysis_service.py 里写 graph_analysis_mode 判断；配置开关属于阶段 10 接入层。
不要在 analysis_service.py 里捕获所有异常后返回空 summary。
不要在 analysis_service.py 里改排产输入、排序、资源、seed 或冻结窗口。
```

### 9.5 测试文件和用例

阶段 9 新增：

```text
tests/scheduler_graph/test_exporter.py
tests/scheduler_graph/test_analysis_service.py
```

`test_exporter.py` 必须覆盖：

```text
测试 1：graph_to_plain_dict 可 JSON 序列化
输入：
  用 OperationGraphNode + OperationGraphEdge 建一张两节点一边的图。
断言：
  payload 有 nodes / edges。
  json.dumps(payload, ensure_ascii=False) 成功。
  nodes 按 (batch_id, seq, op_code, id) 稳定排序。
  edges 有 from / to / kind / lag_minutes。
  payload 里没有 nx.DiGraph 对象。

测试 2：graph_summary_to_dict 可 JSON 序列化
输入：
  构造 GraphAnalysisSummary，带 node_metrics 和 GraphWarning。
断言：
  json.dumps(payload, ensure_ascii=False) 成功。
  warnings 被转成 code/message/data。
  node_metrics 原样保留为普通 dict。

测试 3：graph_to_plain_dict 不修改 graph
输入：
  调用前后记录 graph.number_of_nodes() / graph.number_of_edges() 和节点属性。
断言：
  导出函数只读，不新增节点、不删边、不改属性。

测试 4：导出字段不夹带完整业务对象
输入：
  使用阶段 6 graph node attrs。
断言：
  不出现数据库连接、ORM 对象、datetime 原对象、nx.DiGraph。
```

`test_analysis_service.py` 必须覆盖：

```text
测试 1：analyze_linear_batches 返回 GraphAnalysisSummary
输入：
  同批次三道线性工序。
断言：
  node_count=3。
  edge_count=2。
  is_dag=True。
  topological_order 正确。
  critical_path 正确。
  critical_path_minutes 正确。
  node_metrics 包含每个 node_id。
  warnings 至少是 list。

测试 2：多批次不串线
输入：
  两个批次各两道工序。
断言：
  edge_count=2，而不是 3。
  每个批次内部按 seq 连边。

测试 3：有环时不调用 metrics
做法：
  可以 monkeypatch analysis_service 模块里的 get_topological_order / get_critical_path / build_node_metrics，让它们一旦被调用就抛 AssertionError。
输入：
  直接通过 build_precedence_graph 或 monkeypatch _build_graph_for_linear_batches 构造一张有环图。
断言：
  summary.is_dag=False。
  cycle_edges 非空。
  topological_order=[]。
  critical_path=[]。
  critical_path_minutes=0。
  node_metrics={}。
  warnings 里有 GRAPH_HAS_CYCLE。
  被 monkeypatch 的 metrics 函数没有被调用。

测试 4：坏输入不被吞掉
输入：
  analyze_linear_batches([object()])。
断言：
  抛 GraphBuildContractError 或清晰合同错误。
  不返回空 summary。

测试 5：analysis_service 顶层不直接 import networkx
做法：
  沿用 tests/regression_scheduler_graph_lazy_runtime_contract.py 的口径，或在本文件里断言 import analysis_service 不触发 networkx 加载。
断言：
  graph_analysis_mode=off 的启动合同不被阶段 9 破坏。
```

### 9.6 阶段 9 实施顺序

建议按下面顺序开工，避免写着写着把范围带到阶段 10：

```text
1. 补 GraphAnalysisSummary.node_metrics 默认字段，并跑 graph_types 测试。
2. 实现 exporter.graph_warning_to_dict 和 graph_summary_to_dict。
3. 实现 exporter.graph_to_plain_dict 的稳定排序和只读导出。
4. 新增 tests/scheduler_graph/test_exporter.py。
5. 实现 ScheduleGraphAnalysisService.analyze_linear_batches。
6. 新增 tests/scheduler_graph/test_analysis_service.py。
7. 跑 tests/scheduler_graph 全目录。
8. 跑 ruff / pyright。
9. 确认没有改到排产主链、summary、persistence、页面、数据库。
```

如果第 1 步发现补 `node_metrics` 会影响大量已有测试，先停下来回看阶段 8 和 types.py 合同，不要用兼容字段或双结构绕过去。

### 9.7 阶段 9 验收清单

```text
[ ] GraphAnalysisSummary 已补齐 node_metrics，字段为 Dict[str, Dict[str, Any]]，默认是空 dict。
[ ] warnings 默认是空 list，GraphWarning 结构不变。
[ ] exporter.py 只负责 graph / summary / warning 转普通 dict。
[ ] exporter.py 顶层不直接 import networkx。
[ ] exporter.py 不 import 排产主链、summary、数据库、Flask、页面。
[ ] graph_to_plain_dict 输出 nodes / edges，且顺序稳定。
[ ] graph_summary_to_dict 输出 node_count、edge_count、is_dag、cycle_edges、topological_order、critical_path、critical_path_minutes、node_metrics、warnings。
[ ] exporter.py 导出的 payload 可以 json.dumps(..., ensure_ascii=False)。
[ ] exporter.py 不修改 graph。
[ ] analysis_service.py 只负责串联 build_linear_edges_by_batch、build_precedence_graph、validators、metrics 和 GraphAnalysisSummary。
[ ] analysis_service.py 顶层不直接 import networkx。
[ ] analysis_service.py 不 import input_adapter.py。
[ ] analysis_service.py 不 import schedule_orchestrator.py、schedule_optimizer.py、GreedyScheduler、SummaryBuildContext、OperationLogs、数据库、Flask。
[ ] analyze_linear_batches 返回 GraphAnalysisSummary，不返回 nx.DiGraph。
[ ] analyze_linear_batches 只接收 Iterable[OperationGraphNode]。
[ ] DAG 图会计算 topological_order、critical_path、critical_path_minutes、node_metrics。
[ ] 有环图会返回 is_dag=False、cycle_edges 和 GRAPH_HAS_CYCLE warning。
[ ] 有环图不会调用 get_topological_order、get_critical_path、build_node_metrics。
[ ] 坏输入直接暴露合同错误，不返回空 summary。
[ ] NetworkX 不可用或版本不对时错误显式暴露，不伪装成“没数据”。
[ ] 新增 tests/scheduler_graph/test_exporter.py 并通过。
[ ] 新增 tests/scheduler_graph/test_analysis_service.py 并通过。
[ ] 阶段 5 到阶段 8 已有 tests/scheduler_graph 回归继续通过。
[ ] regression_scheduler_graph_lazy_runtime_contract.py 继续通过。
[ ] ruff check core/services/scheduler/graph tests/scheduler_graph 通过。
[ ] pyright core/services/scheduler/graph 通过。
[ ] 阶段 9 完成后仍不修改 schedule_orchestrator.py、schedule_summary_assembly.py、schedule_persistence.py、SGS、summary、页面、数据库。
[ ] 阶段 9 完成后仍不写 result_summary，不写 OperationLogs，不改变排产结果。
```

推荐验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph/test_graph_types.py tests/scheduler_graph/test_exporter.py tests/scheduler_graph/test_analysis_service.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_lazy_runtime_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/graph tests/scheduler_graph
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/graph
```

PR-2 最终收尾前还要在干净工作区跑：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

注意：

```text
--require-clean-worktree 必须等阶段 9 代码、测试和文档全部提交后再跑。
如果工作区还有未提交文件，不能把它说成 clean-worktree proof。
```

### 9.8 明确不做

阶段 9 明确不做：

```text
[ ] 不改 schedule_orchestrator.py。
[ ] 不改 schedule_optimizer.py。
[ ] 不改 schedule_summary_assembly.py。
[ ] 不改 schedule_persistence.py。
[ ] 不写 result_summary["algo"]["graph_analysis"]。
[ ] 不写 result_summary["diagnostics"]["graph_analysis"]。
[ ] 不写 OperationLogs。
[ ] 不接 graph_analysis_mode 配置判断。
[ ] 不接 report 模式。
[ ] 不接 ready_queue.py。
[ ] 不接 scoring.py。
[ ] 不接 resource_matching.py。
[ ] 不接 SGS 候选集合。
[ ] 不改变 sorted_ops / batch_order / seed_results / frozen_op_ids。
[ ] 不新增页面、按钮、调试接口。
[ ] 不做完整 nodes/edges 落库。
[ ] 不做性能缓存。
[ ] 不做 PyInstaller / Win7 打包验证。
```

阶段 9 完成后的交接话术必须写清：

```text
阶段 9 只完成图模块内部的统一分析入口和导出合同。
PR-2 仍然没有把图分析接入排产结果摘要。
阶段 10 / PR-3 才能开始 report 模式，把 graph_summary_to_dict(summary) 投影成 result_summary 小摘要。
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
    summary = service.analyze_linear_batches(nodes)

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
analyze_linear_batches 返回 GraphAnalysisSummary，不返回 nx.DiGraph。
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

## 变更记录

- 2026-05-17：实施阶段 9，补齐 `GraphAnalysisSummary.node_metrics`、`exporter.py` 普通 dict 导出、`analysis_service.py` 统一分析入口，以及 `test_exporter.py` / `test_analysis_service.py`；本阶段仍只停留在图模块内部，没有进入阶段 10 / PR-3，没有写 `result_summary` 或 OperationLogs。
- 2026-05-17：细化阶段 9，把 `exporter.py`、`analysis_service.py`、`GraphAnalysisSummary.node_metrics` 补齐、DAG/有环处理口径、禁止静默回退、禁止过度兜底、测试用例、实施顺序和验收命令写到可执行程度；同时明确阶段 9 仍只做图模块内部统一入口和普通 dict 导出，不接 report 模式、不写 `result_summary`、不写 OperationLogs、不改变排产结果。
- 2026-05-17：细化阶段 8，把 `metrics.py` 的拓扑顺序、层级、关键路径、影响范围、节点指标、错误暴露、测试用例和验收命令补到可执行程度；同时明确阶段 8 只做图指标，不接 report、不接 SGS、不写 `result_summary`，并把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成硬要求。
- 2026-05-17：细化阶段 7，把 `validators.py` 的目标边界、整体实现要求、输入输出合同、DAG/环检测、孤立节点 warning、重复 `seq` warning、汇总规则、测试用例和验收命令补到可执行程度；同时明确阶段 7 只暴露图质量问题，不修图、不静默回退、不接排产、不写 `result_summary`，并把“优雅简洁、不做过度兜底、不做过度防御性编程、高内聚低耦合”写成硬要求。
- 2026-05-17：细化阶段 6，把 `precedence_builder.py` 的职责、输入输出合同、边生成规则、图构建规则、错误处理、测试用例和验收命令补到可执行程度；同时把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成阶段 6 的硬要求，并同步整体执行顺序表中阶段 5/6/7 的口径，避免后续按错阶段执行。
- 2026-05-17：执行阶段 5，新增 `core/services/scheduler/graph/input_adapter.py` 和 `tests/scheduler_graph/test_input_adapter.py`，把已整理好的排产输入转换为 `OperationGraphNode`；同时修复 `FrozenDict` 只读方法的 pyright 签名问题。阶段 5 仍只做输入转换，不构建 `nx.DiGraph`，不接入排产，不写 `result_summary`，不改变排产结果。
- 2026-05-17：细化阶段 5，把 `input_adapter.py` 的职责、输入合同、字段映射、时长计算、候选资源、raw 快照、错误处理、测试用例和验收命令补到可执行程度；同时把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成阶段 5 的硬要求；按只读核实结果补准固定人员/固定设备候选资源口径、外协天数必须大于 0、source 严格合同和 pyright 收尾要求。

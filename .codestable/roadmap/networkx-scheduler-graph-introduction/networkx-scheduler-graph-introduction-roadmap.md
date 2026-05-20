---
doc_type: roadmap
slug: networkx-scheduler-graph-introduction
status: active
created: 2026-05-08
last_reviewed: 2026-05-20
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
- 多权重候选方案试跑时，第一版时间到达上限就采用已完成候选里的最好结果；真正“继续补跑剩余方案”放到后续增强。

本路线图明确不做：

- 不马上替代现有贪心排产算法。
- 不马上让 NetworkX 进入主 `requirements.txt`。
- 不安装 `networkx[default]`。
- 不引入 NumPy、SciPy、Pandas、Matplotlib、pydot、pygraphviz。
- 不使用 NetworkX drawing / layout 功能。
- 不把 `nx.Graph` / `nx.DiGraph` 暴露给 Controller、页面、数据库、Excel 导出层。
- 不在第一版做前端图展示。
- 不在第一版做最小费用流精排。
- 不在第一版做候选方案续跑。
- 不新增静默兜底、宽泛 fallback、宽泛吞错。
- 不改变 `readiness_gate_enabled=False` 时齐套和齐套日期不影响排产的语义。
- 不把冻结窗口 `seed_results` 里的工序重新放回待排候选队列。
- 不把 `gantt_critical_chain` 展示链路误当成排产评分链路。

## 已确认产品口径

下面是 2026-05-17 和用户逐条讨论后确认的产品口径。后续实现如果发现这里和旧阶段文字冲突，以本节为准；要改也先回路线图更新，不要在代码里偷偷换口径。

### 默认行为

```text
正式交付给业务用户时，关键链排产默认开启。
off / report 仍然保留给开发验证、回滚和排障，不作为普通用户默认入口。
```

大白话就是：

```text
既然做这个功能，真正排产时就应该默认考虑关键链。
但系统还要留一个关掉或只看报告的办法，方便出现问题时退回来。
```

### 候选方案池

第一版排产时不要只跑一套结果，而是跑一组候选：

```text
1. 原算法候选必须先跑，作为兜底和对照。
2. 关键链候选默认跑 5 档权重。
3. 权重档数允许在高级设置里改，例如 3 / 5 / 7 档。
4. 每档具体权重由系统给，普通用户不手填每个权重数字。
5. 第一版只在当前用户选择的排序规则、派工规则下面调关键链权重。
6. 第一版不把所有排序规则、所有派工规则、所有关键链权重做笛卡尔积暴力全跑。
```

这样做的原因：

```text
用户不需要理解每个权重是什么意思。
系统自己多试几套，再把最好的拿出来。
原算法仍然保留，防止关键链方案在某些案例里反而更差。
```

### 自动择优

第一版对普通用户默认自动择优：

```text
系统跑完候选方案后，默认展示最终采用方案。
最终采用方案通常是现有评分最高的方案。
但如果原算法和关键链方案评分很接近，而关键链健康明显更好，可以用平衡规则选择关键链方案。
```

评分规则先复用当前系统已有目标，不新增一套完全独立的新评分体系：

```text
继续使用当前优化目标和已有 objective_score / metrics。
关键链健康只作为平衡择优的补充判断，不直接替代原评分。
```

平衡规则第一版口径：

```text
failed_ops 不能变差。
超期批次数默认最多允许多 1 个，后续可在高级设置里改成 0 / 1 / 2。
总拖期时长默认允许 10% 容差，后续可在高级设置里改成 5% / 10% / 20%。
关键链健康对用户展示成“更健康 / 差不多 / 更差”，不要把一堆内部指标直接甩给普通用户。
```

关键链健康内部可以参考：

```text
关键链等待时间是否减少。
高影响工序是否更早启动。
关键链完工时间是否提前。
关键链余量是否更安全。
```

### 候选结果保存

第一版不能只保存最终结果，否则用户后面没法比较“原算法最好方案”和“关键链最好方案”。

保存口径：

```text
所有候选方案都保存摘要。
完整排产明细只保存代表方案。
代表方案至少包括：最终采用方案、原算法最好方案、关键链最好方案。
如果三者有重复，只保存一份明细并建立引用关系。
代表方案不应该伪装成多条正式排产历史版本；它们属于同一次排产下面的候选方案。
```

大白话就是：

```text
用户打开这次排产记录时，要能看见系统到底比较了哪些方案。
但数据库不需要把每个候选都当成一次正式排产塞进去。
```

### 前端展示

第一版默认展示最终采用方案，同时提供代表方案切换：

```text
默认视图：最终采用方案。
可切换：最终采用方案 / 原算法最好方案 / 关键链最好方案。
```

需要支持切换的结果页：

```text
甘特图
周计划
资源派工
超期分析
利用率分析
停机影响分析
优化分析页
```

第一版不要做复杂并排对比，先做同一页面内切换代表方案。

如果最终采用的是原算法：

```text
页面提示：已比较关键链方案，本次原算法更优。
```

如果最终采用的是关键链方案，但它不是原始评分第一：

```text
普通结果页只说简单原因：评分接近，关键链健康更好。
优化分析页再展示详细解释。
```

### 时间上限和进度

第一版复用当前 `time_budget_seconds` 作为候选试跑时间上限：

```text
排产执行前可以让用户临时调整本次时间上限。
长期默认值仍放在高级设置里。
原算法候选必须先跑，保证时间再短也有兜底结果。
时间到了就停止继续新增候选，从已完成候选里选最好结果。
页面记录 planned_candidate_count、completed_candidate_count、time_budget_reached。
```

第一版进度展示只做轻量提示：

```text
正在试跑第几套方案。
本次计划几套。
当前已完成几套。
```

第一版不做实时评分、不做后台续跑、不做停止后自动接着跑。

### 并发和数据库

第一版候选试跑先串行执行：

```text
不换语言。
不要求 Python 多线程提速。
不在 Win7 第一版里引入多进程并行。
不让候选试跑过程中的子任务直接写正式排产明细。
```

数据库第一版继续使用当前数据库能力：

```text
不为这个功能引入 PostgreSQL 等新数据库。
优先在现有数据库里补候选方案表、摘要字段、代表方案明细和清理策略。
未来如果要长期保存大量候选明细，再考虑数据库能力升级。
```

## 整体执行顺序

后续实施以 `networkx-scheduler-graph-introduction-items.yaml` 里的 PR 顺序为准；正文里的“阶段 0 / 阶段 11 / 阶段 16”是技术章节编号，不再代表线性执行顺序。大白话说：不能从阶段 11、12、13 一路顺着做，因为有些后写的章节已经被收进前面的 PR 加固包里了。

当前推进指针：

```text
PR-0 到 PR-6 已完成。
PR-7a 已完成。
PR-7b 已完成。
PR-7c 已完成。
PR-7d 已完成。
PR-7e 已完成。
下一步是 PR-8。
PR-8 可以继承 PR-7a 到 PR-7e 已证明的候选表、候选运行、同事务保存、代表方案切换、默认配置收口、清理和性能守卫；但不能继承资源匹配 report-only 分析、最大匹配诊断或资源瓶颈说明的证明。
```

| PR / items.yaml 条目 | 对应技术章节 | 目标 | 是否改变排产结果 | 状态 |
| --- | --- | --- | ---: | --- |
| PR-0 `networkx-compatibility-decision` | 阶段 0 | 建分支、记录基线、落 ADR 和依赖决策 | 否 | done |
| PR-1 `scheduler-graph-config-default-off` | 阶段 1-2 | 加可选依赖验证、配置开关和迁移，默认 off | 否 | done |
| PR-2 `scheduler-graph-core-module` | 阶段 3-9 | 图核心模块：懒加载、节点、输入转换、建图、校验、指标、导出、分析服务 | 否 | done |
| PR-3 `scheduler-graph-report-mode` | 阶段 10 | 接入 report 模式，写 result_summary 小摘要和 diagnostics 采样 | 否 | done |
| PR-4 `scheduler-graph-debug-performance` | 阶段 10.9 + 阶段 16 + 阶段 17 相关测试 + 阶段 18 | 性能护栏、diagnostics 加固、真实集成证明；受控 debug export 只是附属能力 | 否 | done |
| PR-5 `scheduler-graph-ready-queue-on-mode` | 阶段 11 + 阶段 12 | 先做有环安全门，再让 ready 队列参与 SGS 候选 | 是 | done |
| PR-6 `scheduler-graph-critical-score-on-mode` | 阶段 13 | 关键路径、影响范围、后续关键工作量进入评分 | 是/可控 | done |
| PR-7a 到 PR-7e | 阶段 13.6 | 多权重候选试跑、自动择优、同事务落库、代表方案切换和配置收口 | 是/可控 | done |
| PR-8 `scheduler-graph-resource-matching-report` | 阶段 14-15 | 资源匹配 report-only 分析：首波 ready 工序 × 候选设备最大匹配，输出可见瓶颈/未匹配诊断；最小费用流只留后续增强 | 否 | planned |
| PR-9 `scheduler-graph-win7-package-closeout` | 阶段 21 | Win7 离线打包和最终验收 | 否/可控 | planned |
| PR-10 `scheduler-graph-candidate-resume-later` | 阶段 23 | 后续增强：候选方案续跑 | 否/可控 | planned |

执行规则：

```text
1. 做事看 PR，不看阶段号顺序。
2. 每个 PR 仍然可以单独提交，方便回滚。
3. 阶段章节只作为该 PR 内部的技术细节说明。
4. 如果某个阶段章节和 items.yaml 的 PR 拆分冲突，以 items.yaml 的 PR 拆分为准，并回本节同步修正。
5. 不允许因为“阶段 11 写在阶段 10 后面”就跳过 PR-4 直接做有环安全门；PR-5 必须等 PR-4 完成。
```

## 后续产品边界：从继续堆算法收敛到排产诊断与影响分析

PR-0 到 PR-7e 已经把 NetworkX 这条线从“能不能引入”推进到了“已经能在受控条件下参与排产”。继续往后走，最重要的不是再加更多算法，而是把产品边界收住。

这一节专门写清楚 PR-8 之后的方向，避免后续开发 Agent 误把 NetworkX 做成第二套排产器。

核心结论：

```text
NetworkX 后续主要做“排产诊断与影响分析”。
它是排产结果体检医生，不是第二套排产大脑。
它可以解释问题、提示风险、说明影响范围。
它不能偷偷替代现有排产算法，也不能自动改排产结果。
```

### 为什么要收敛

前面 PR-0 到 PR-7e 已经证明了几个事实：

```text
1. NetworkX 可以作为可选依赖进入 Win7 / Python 3.8 离线口径。
2. graph_analysis_mode=off 时系统仍然不要求 NetworkX。
3. report 模式可以只写小摘要和 diagnostics 采样，不改变排产结果。
4. on 模式已经能在受控条件下参与 ready 队列、关键链评分和候选方案比较。
5. PR-7a 到 PR-7e 已经把候选方案、自动择优、同事务保存、页面按方案查看和配置收口做完。
```

这说明图分析方向可行，但也说明复杂度已经不低。后续如果继续沿着“还有什么图算法能加”的方式做，系统会很快变复杂：

```text
后端模块会越来越多。
result_summary 字段会越来越多。
diagnostics 采样会越来越难控。
页面入口会越来越分散。
测试矩阵会越来越大。
Win7 离线交付风险会越来越高。
调度员也会越来越难看懂系统到底做了什么。
```

所以后续不是“有价值就加”，而是只保留最能帮助调度员看懂排产的部分。

推荐判断标准：

```text
如果一个功能能回答“这版排产哪里有问题、为什么有风险、会影响谁”，可以考虑进入后续路线图。
如果一个功能开始自动改派工、自动改顺序、自动建议重排，就先放 future / backlog / 后续研究。
```

### 后续统一定位

NetworkX 后续定位写死为：

```text
只读辅助解释层。
排产诊断层。
影响分析层。
```

不要把它描述成：

```text
新排产器。
新优化器。
自动派工大脑。
自动调度建议系统。
局部重排引擎。
```

原因是当前 APS 的主排产链已经有自己的排产算法、候选方案、自动择优、正式 adopted 方案和页面展示合同。NetworkX 后续应该服务于这些结果，帮助解释这些结果，而不是绕开它们另起一套。

大白话说：

```text
现有排产算法负责“排出一版结果”。
PR-7 候选比较负责“在几版候选里选一版正式采用”。
NetworkX 后续诊断负责“告诉用户这版结果哪里健康、哪里危险、哪里会卡”。
```

### 推荐产品形态：排产诊断中心

后续如果要把更多 NetworkX 分析展示到页面上，建议统一收进一个入口，暂定名：

```text
排产诊断中心
```

这里的“中心”是产品组织方式，不代表 PR-8 必须新增页面。具体是新页面、分析页增强，还是系统历史详情里的一个诊断区，留到后续 feature-design 再决定。当前 roadmap 只先锁定一个原则：诊断按业务问题组织，不按算法名字分散到各处。

不建议这样做：

```text
甘特图里塞一块图分析。
周计划里塞一块图分析。
资源派工里塞一块图分析。
分析页再塞一块图分析。
报表页又塞一块图分析。
每个页面都有一点，但每个页面都讲不完整。
```

建议这样做：

```text
保留现有甘特图、周计划、资源派工、分析页的原职责。
后续统一设计“排产诊断中心”或等价统一入口。
排产诊断按调度员关心的问题组织，而不是按算法组织。
```

第一版“排产诊断中心”只回答三个问题：

```text
1. 这版排产有没有明显问题？
2. 这版排产最卡在哪里？
3. 这版排产为什么可能延期？
```

页面上不要出现太多算法词。调度员不需要先理解什么是中心性、最大匹配、最长路径、最小割。页面应该直接讲：

```text
哪些批次风险高。
哪些设备最卡。
哪些工序资源选择太少。
哪些关键工序一拖会影响很多后续工序。
哪些问题只是提醒，哪些问题已经会影响当前排产。
```

### 结果展示原则

后续所有诊断展示都遵守以下原则：

```text
1. 先给结论，再给证据。
2. 先讲业务影响，再讲指标。
3. 只展示小摘要，不展示完整图对象。
4. diagnostics 只做采样和排障，不当业务决策依据。
5. 所有失败、降级、不可用都要明说，不能假装成功。
```

页面展示状态可以使用这类大白话口径：

```text
正常：这版排产没有发现明显结构问题。
提醒：发现 3 道工序候选设备为空，需要人工确认。
部分可用：资源匹配只分析了设备，人员匹配本版暂不支持。
不可用：当前未启用图分析，无法生成排产诊断。
错误：工序关系存在异常，无法生成可靠诊断。
```

代码内部不一定直接使用这些展示词。现有图分析内部已有 `available` / `unavailable` / `input_error` / `build_error` 等合同，后续实现时要做明确映射，不能随手替换既有字段含义。

不要这样写给用户看：

```text
匹配率 0。
中心性 0.87。
critical_path_minutes=1260。
graph_analysis_status=degraded。
```

要翻译成调度员看得懂的话。

## PR-8 边界：资源匹配仍然只做 report-only

PR-8 是下一步，但 PR-8 不应该承载“排产诊断中心”的全部内容。PR-8 只做资源匹配 report-only 分析。

PR-8 的核心目标：

```text
分析首波 ready 工序和 candidate_machine_ids 之间，能不能找到一组可行设备匹配。
```

PR-8 可以做：

```text
1. 读取首波 ready 工序。
2. 读取这些工序的 candidate_machine_ids。
3. 构造“待排工序 × 候选设备”的二分图。
4. 使用 NetworkX 二分图最大匹配。
5. 只保留工序侧匹配结果。
6. 输出 matched / unmatched / bottleneck 小摘要。
7. diagnostics 只保留采样。
8. OperationLogs 只看到 public 小摘要。
```

PR-8 不做：

```text
1. 不改 SGS 候选排序。
2. 不改资源分配。
3. 不落候选表。
4. 不新增页面入口。
5. 不做人员匹配。
6. 不做最小费用流。
7. 不自动换设备。
8. 不新增配置字段。
9. 不新增 schema。
10. 不改排产结果。
```

PR-8 的失败和降级也必须可见：

```text
没有 candidate_machine_ids：显示 unavailable 或 warning，不能默默塞全量设备。
ready 工序为空：显示 no_ready_operations，不要假装有匹配结果。
NetworkX 不可用：显示 unavailable，不要吞掉。
图增强不可用：显示 degraded 或 unavailable，不要假装成功。
存在有环：显示 cycle_related_warning 或 graph_unavailable，不要继续输出误导结果。
匹配结果为空：要区分“确实没有可匹配设备”和“输入为空 / 分析失败”。
```

PR-8 最小 public 摘要建议只放这种级别：

```text
resource_matching:
  status: warning
  ready_operation_count: 12
  matched_operation_count: 9
  unmatched_operation_count: 3
  bottleneck_machine_count: 2
  unmatched_samples:
    - op_id: 101
      op_code: OP-101
      reason: candidate_machine_ids_empty
    - op_id: 128
      op_code: OP-128
      reason: no_available_candidate_machine
  bottleneck_samples:
    - machine_id: M01
      matched_ready_operation_count: 5
    - machine_id: M03
      matched_ready_operation_count: 4
```

不建议 public 摘要放这些：

```text
完整 nodes。
完整 edges。
完整 matching 字典。
完整 candidate_machine_ids 列表。
完整 ready 工序列表。
完整 diagnostics。
nx.Graph / nx.DiGraph 对象。
```

PR-8 完成后，它应该成为后续“资源覆盖报告”的基础证据，而不是直接变成派工器。

## 第一批后续方向：看清当前这版排产

第一批目标：

```text
看清当前这版排产。
```

这批功能只回答“当前排出来的这版有没有问题、哪里最卡、为什么可能延期”。它不处理“异常发生后怎么重排”，也不做自动建议。第一批可以作为 PR-8 之后的后续规划候选，但是否拆进 items.yaml、拆成几个 PR，要等用户确认后再做。

建议第一批拆成四块：

```text
1. 排产体检报告。
2. 瓶颈雷达。
3. 资源覆盖报告。
4. 交期风险清单。
```

这四块可以进入后续路线图方向，但不建议全部塞进 PR-8。PR-8 只先做设备资源匹配 report-only。

### 第一批 1：排产体检报告

排产体检报告回答：

```text
这版排产有没有明显结构问题？
```

它不是为了优化，也不是为了重排，而是先告诉调度员“这版结果有没有基础健康问题”。

建议检查项：

```text
1. 工序关系有没有成环。
2. 工序链有没有断链。
3. 有没有孤立工序。
4. 同一批次内有没有重复 seq。
5. 同一批次内 seq 是否能形成清晰顺序。
6. 有没有工序没有候选设备。
7. 有没有工序没有候选人员。
8. 有没有关键工序候选资源过少。
9. 有没有超长关键链批次。
10. 有没有明显交期余量不足的批次。
```

建议输出按严重程度分组：

```text
严重问题：
会导致分析不可信，或者可能影响排产正确性。

风险提醒：
当前能排出结果，但后续执行风险较高。

普通提示：
不一定有问题，但值得调度员关注。
```

示例文案：

```text
严重问题：
- 批次 B202605-001 的工序关系存在成环，系统无法判断稳定的前后顺序。

风险提醒：
- 有 4 道工序没有候选设备，后续自动派工可能失败。
- 批次 B202605-018 的关键链较长，交期余量不足。

普通提示：
- 有 2 道外协工序处于关键链上，请关注外协回厂时间。
```

建议 public 摘要字段：

```text
schedule_health:
  status: warning
  issue_count: 7
  severe_count: 1
  warning_count: 4
  info_count: 2
  cycle_detected: true
  missing_resource_count: 4
  risky_batch_count: 2
  issue_samples:
    - severity: severe
      type: cycle_detected
      message: 批次 B202605-001 的工序关系存在成环
    - severity: warning
      type: candidate_machine_empty
      message: 工序 OP-128 没有候选设备
```

不建议字段：

```text
完整 topological_order。
完整 cycle_edges。
完整 node_metrics。
完整 graph。
```

内部可以算得细，但 public 只留可解释小摘要。

### 第一批 2：瓶颈雷达

瓶颈雷达回答：

```text
这版排产最卡在哪里？
```

这里的“卡”不要只按一个指标判断。建议综合几类证据：

```text
1. 设备负荷：哪台设备排得最满。
2. 工序类型负荷：哪类工序最集中。
3. 批次关键链：哪个批次链最长、余量最小。
4. 关键工序：哪些工序在关键链上。
5. 影响范围：哪些工序一拖会影响很多后续工序。
6. 资源覆盖：哪些关键工序候选资源很少。
```

页面上建议分成三块：

```text
设备瓶颈：
告诉用户哪台设备最紧张。

批次瓶颈：
告诉用户哪个批次最容易拖。

工序瓶颈：
告诉用户哪些工序值得重点盯。
```

示例文案：

```text
设备瓶颈：
- 设备 M01 是当前主要瓶颈，未来 7 天负荷最高，并且承担了 5 道关键链工序。

批次瓶颈：
- 批次 B202605-018 的关键链最长，交期余量不足，建议优先关注。

工序瓶颈：
- 工序 OP-128 在关键链上，且后续影响 12 道工序，一旦延误会扩大影响。
```

建议 public 摘要字段：

```text
bottleneck_radar:
  status: warning
  top_machine_bottlenecks:
    - machine_id: M01
      reason: 高负荷且承担关键链工序
      risk_level: high
  top_batch_bottlenecks:
    - batch_id: B202605-018
      reason: 关键链长且交期余量不足
      risk_level: high
  top_operation_bottlenecks:
    - op_id: 128
      op_code: OP-128
      reason: 位于关键链且后续影响范围大
      risk_level: high
```

这里可以借鉴中心性思路，但不要直接告诉用户“中心性高”。中心性最多是内部辅助指标，页面要翻译成：

```text
影响范围大。
后续牵连多。
处在关键链交汇处。
```

重要边界：

```text
中心性高不等于一定延期。
关键链长不等于一定失败。
设备负荷高不等于一定要换设备。
```

这些都只能作为诊断提示，不能直接变成自动调度动作。

### 第一批 3：资源覆盖报告

资源覆盖报告回答：

```text
哪些工序资源选择太少，容易卡住？
```

这块和 PR-8 最贴近。PR-8 先做设备匹配；后续第一批可以把它扩展成更完整的资源覆盖报告。人员覆盖属于资源覆盖报告增强，不进入 PR-8 第一版。

建议检查项：

```text
1. 哪些工序候选设备为空。
2. 哪些工序只有 1 台候选设备。
3. 哪些关键链工序只有 1 台候选设备。
4. 哪些工序候选人员为空。
5. 哪些工序只有 1 个候选人员。
6. 哪些关键链工序只有 1 个候选人员。
7. 首波 ready 工序里，有多少能找到设备匹配。
8. 首波 ready 工序里，有多少找不到设备匹配。
9. 哪些设备在首波匹配中被过度争抢。
```

资源覆盖报告最好区分两种风险：

```text
资源为空：
没有候选资源，这是更严重的问题。

资源太少：
有资源，但选择太少，任何停机、请假、占用都可能导致风险。
```

示例文案：

```text
严重问题：
- 工序 OP-128 没有候选设备，当前无法判断可派给哪台设备。

风险提醒：
- 工序 OP-203 只有 1 台候选设备 M01，且 M01 已经是当前瓶颈设备。
- 批次 B202605-018 的关键链上有 3 道工序只有单一候选设备。
```

建议 public 摘要字段：

```text
resource_coverage:
  status: warning
  machine_empty_count: 3
  machine_single_candidate_count: 8
  operator_empty_count: 2
  operator_single_candidate_count: 5
  critical_chain_resource_risk_count: 4
  ready_matching:
    status: warning
    ready_operation_count: 12
    matched_operation_count: 9
    unmatched_operation_count: 3
  samples:
    - type: machine_empty
      op_id: 128
      op_code: OP-128
      message: 这道工序没有候选设备
    - type: machine_single_candidate
      op_id: 203
      op_code: OP-203
      machine_id: M01
      message: 这道工序只有 1 台候选设备
```

必须写死的边界：

```text
没有候选设备时，不能默默塞全量设备。
没有候选人员时，不能默默塞全量人员。
资源匹配失败时，要显示 warning / degraded / unavailable。
不能把匹配失败包装成 matched=0 的正常成功。
```

原因很简单：资源覆盖报告的价值就是暴露资源数据问题。如果系统偷偷兜底，调度员看到的就是假健康。

### 第一批 4：交期风险清单

交期风险清单回答：

```text
哪些批次最可能延期？为什么？
```

它不能只是按 overdue 排序，也不能只给一个风险分。调度员需要知道风险原因。

建议风险来源至少分成几类：

```text
1. 设备风险：关键设备负荷过高、关键工序集中在瓶颈设备上。
2. 人员风险：候选人员为空或过少。
3. 物料风险：物料未齐、缺料或 ready_date 晚。
4. 外协风险：外协工序在关键链上，外协周期长。
5. 关键链风险：链条长、交期余量小。
6. 资源覆盖风险：关键工序候选资源少。
7. 候选方案切换风险：本版采用方案和 baseline 差异明显。
```

第一版不一定所有风险来源都有数据。如果某类数据没有接入，要明确显示“暂不分析”，不要假装有结论。

示例文案：

```text
批次 B202605-018：高风险
原因：
- 关键链较长，交期余量不足。
- 关键链上有 2 道工序只支持设备 M01。
- M01 同时也是当前设备瓶颈。

批次 B202605-021：中风险
原因：
- 有外协工序位于关键链上。
- 外协周期占总链路时间比例较高。

批次 B202605-030：低风险
原因：
- 当前未发现结构问题。
- 交期余量相对充足。
```

建议 public 摘要字段：

```text
due_date_risk:
  status: warning
  high_risk_batch_count: 2
  medium_risk_batch_count: 5
  low_risk_batch_count: 18
  top_risk_batches:
    - batch_id: B202605-018
      risk_level: high
      reasons:
        - critical_chain_long
        - machine_bottleneck
        - resource_coverage_low
      message: 关键链长，且关键工序集中在瓶颈设备 M01
    - batch_id: B202605-021
      risk_level: medium
      reasons:
        - external_operation_on_critical_chain
      message: 外协工序位于关键链上，请关注外协回厂时间
```

注意：

```text
交期风险清单不是承诺一定延期。
它只说明“这版排产里哪些批次最值得提前关注”。
```

页面文案要避免绝对化，比如不要写：

```text
该批次一定延期。
系统判断必须换设备。
系统建议必须加班。
```

可以写：

```text
该批次延期风险较高。
建议调度员重点关注。
如需调整，请人工结合现场情况判断。
```

## 第二批后续方向：看清异常会影响谁

第二批目标：

```text
看清异常会影响谁。
```

第一批看的是“当前这版排产”。第二批看的是“如果发生某个异常，会影响哪些批次、工序、订单和交期”。

第二批仍然只读分析，不自动改排产。

建议第二批拆成三块：

```text
1. 停机影响分析。
2. 缺料影响分析。
3. 版本差异影响报告。
```

### 第二批 1：停机影响分析

停机影响分析回答：

```text
某台设备停机一段时间，会影响谁？
```

用户输入：

```text
设备。
停机开始时间。
停机结束时间。
可选：只看当前排产版本，还是和上一版对比。
```

系统输出：

```text
1. 直接受影响的工序。
2. 受影响工序所在批次。
3. 这些工序是否在关键链上。
4. 后续会被拖住的工序。
5. 可能受影响的交期。
6. 影响等级：高 / 中 / 低。
```

示例文案：

```text
设备 M01 在 2026-05-21 08:00 到 2026-05-21 18:00 停机会影响 6 道工序。
其中 2 道工序在关键链上。
受影响最明显的是批次 B202605-018，后续 4 道工序需要重点关注。
```

建议 public 摘要字段：

```text
downtime_impact:
  status: warning
  machine_id: M01
  downtime_start: "2026-05-21 08:00"
  downtime_end: "2026-05-21 18:00"
  directly_affected_operation_count: 6
  critical_operation_count: 2
  affected_batch_count: 3
  affected_due_date_count: 1
  top_impacts:
    - batch_id: B202605-018
      affected_operation_count: 4
      risk_level: high
      message: 关键链工序受停机影响，后续工序需要重点关注
```

第一版不做：

```text
不自动换设备。
不自动插入停机日历。
不自动重排。
不自动建议加班。
不自动改 adopted 方案。
```

停机影响分析只回答“影响谁”。除非后续接入模拟或重排能力，否则不要承诺一定能算出精确延期小时。

### 第二批 2：缺料影响分析

缺料影响分析回答：

```text
某个物料缺了，会卡住谁？
```

用户输入：

```text
物料编码。
可选：预计到料时间。
可选：只看未开始工序，还是包含进行中工序。
```

系统输出：

```text
1. 直接需要该物料的工序。
2. 会被卡住的批次。
3. 后续被影响的工序链。
4. 受影响订单。
5. 是否影响关键链。
6. 如果有预计到料时间，提示可能影响到哪里。
```

示例文案：

```text
物料 MAT-001 缺料会影响 4 个批次。
其中批次 B202605-018 的首道关键工序依赖该物料，后续 6 道工序需要重点关注。
```

建议 public 摘要字段：

```text
material_shortage_impact:
  status: warning
  material_code: MAT-001
  directly_blocked_operation_count: 5
  affected_batch_count: 4
  affected_order_count: 3
  critical_chain_affected_count: 2
  top_impacts:
    - batch_id: B202605-018
      blocked_operation_count: 1
      downstream_operation_count: 6
      risk_level: high
      message: 首道关键工序缺料，后续链路需要重点关注
```

第一版不做：

```text
不自动修改 ready_date。
不自动冻结工序。
不自动重排。
不自动替换物料。
不自动给采购建议。
```

缺料影响分析只解释影响范围。除非后续接入模拟或重排能力，否则不要承诺一定能算出精确延期小时。

### 第二批 3：版本差异影响报告

版本差异影响报告回答：

```text
为什么这次排产变了？
```

这块对调度员很重要。排产结果每次变化后，用户通常不是先问“算法分数是多少”，而是问：

```text
为什么这个订单提前了？
为什么那个订单延后了？
为什么这台设备突然排满了？
是不是因为我改了配置？
是不是因为候选方案切换了？
```

建议比较对象：

```text
本版 adopted 方案。
上一版 adopted 方案。
可选：本版 baseline_best。
可选：本版 critical_best。
```

输出内容：

```text
1. 哪些订单提前了。
2. 哪些订单延后了。
3. 哪些批次开始时间变化明显。
4. 哪些批次完工时间变化明显。
5. 哪些关键工序换了时间或资源。
6. 变化可能来自设备、物料、外协、关键链，还是候选方案切换。
```

示例文案：

```text
和上一版相比，订单 O202605-001 预计提前 6 小时。
可能原因：本版 adopted 方案优先处理了它所在批次的关键链工序。

订单 O202605-009 预计延后 4 小时。
可能原因：设备 M01 被更多关键链工序占用，且该订单工序候选设备较少。
```

建议 public 摘要字段：

```text
version_diff_impact:
  status: ok
  base_version: 12
  current_version: 13
  advanced_order_count: 5
  delayed_order_count: 3
  unchanged_order_count: 22
  top_advanced:
    - order_id: O202605-001
      delta_hours: -6
      message: 预计提前 6 小时，可能和关键链工序更早开始有关
  top_delayed:
    - order_id: O202605-009
      delta_hours: 4
      possible_reasons:
        - machine_bottleneck
        - candidate_plan_switch
      message: 预计延后 4 小时，可能和瓶颈设备占用增加有关
```

注意边界：

```text
版本差异报告只能说“可能原因”。
不要冒充已经证明的唯一原因。
不要把候选方案切换解释成一定更优或一定更差。
```

## 第三批先暂缓：只放 future / backlog / 后续研究

第三批不是没有价值，而是现在不应该进入正式开发主线。

第三批包括：

```text
1. 加急订单插单模拟。
2. 自动调度建议卡片。
3. 小窗口局部重排。
4. 最小费用流自动改派工。
5. 自动建议换设备。
6. 自动建议加班。
7. 自动建议调整顺序。
```

这些功能和第一批、第二批的区别很大。

第一批和第二批做的是：

```text
解释问题。
提示风险。
说明影响范围。
```

第三批开始做的是：

```text
系统参与改排产。
系统提出动作建议。
系统可能改变计划责任边界。
```

所以第三批复杂度明显更高。

### 为什么第三批暂缓

#### 1. 需要场景副本

只要做插单模拟、局部重排、自动改派工，就不能直接拿正式 adopted 方案乱改。必须先有场景副本。

需要回答：

```text
模拟场景保存在哪里？
模拟场景和正式版本怎么关联？
模拟失败是否影响正式排产？
用户能否回到模拟前状态？
多个用户同时模拟怎么办？
```

这些都不是 PR-8 或第一批诊断能顺手解决的。

#### 2. 需要模拟链路

诊断只需要读当前结果。模拟需要跑一套“假设条件下”的排产链路。

例如：

```text
如果插入一个加急订单，要冻结哪些已开工工序？
哪些未开工工序允许挪？
是否允许换设备？
是否允许改外协？
是否允许突破日历？
是否允许加班？
```

如果这些边界不清楚，自动建议会变成黑箱。

#### 3. 需要建议可信度

系统如果给出建议卡片，用户会自然理解成“系统建议我这么做”。这时就必须解释：

```text
为什么建议换设备？
为什么建议加班？
为什么建议调整顺序？
这个建议会让哪些订单提前？
又会让哪些订单延后？
有没有副作用？
```

没有这些解释，建议卡片容易变成误导。

#### 4. 需要责任边界

自动改排产涉及现场责任。尤其是：

```text
换设备可能影响工艺能力。
加班可能影响人工成本。
调整顺序可能影响订单承诺。
外协调整可能影响供应商交期。
```

这些不能由图算法自动拍板。

#### 5. 测试矩阵会爆炸

第三批功能会把测试从“只读分析是否正确”扩展成：

```text
模拟结果是否正确。
正式结果是否不被污染。
建议是否可解释。
回滚是否安全。
并发是否安全。
页面交互是否清晰。
导出是否区分正式 / 模拟。
OperationLogs 是否记录责任边界。
```

这比第一批、第二批复杂很多。

### 第三批在 roadmap 里的写法

第三批不要写成近期 planned。

推荐写法：

```text
future / backlog / deferred / 后续研究。
```

并且要明确：

```text
当前不承诺开发。
当前不进入 PR-8。
当前不进入 Win7 第一版交付范围。
当前不允许开发 Agent 顺手实现。
```

如果后续真的要研究第三批，建议先单独开 roadmap，而不是塞进当前 NetworkX 引入路线。

## 外部资料口径

外部资料只能作为启发，不作为照搬依据。

### JobShopLib

参考：

```text
https://job-shop-lib.readthedocs.io/en/stable/api/job_shop_lib.graphs.html
```

启发：

```text
把工序、设备、工单做成图，是成熟方向。
工序之间的先后关系、工序和机器之间的关系，都可以用图表达。
```

边界：

```text
不要直接搬整库。
不要引入它的整套对象模型。
不要为了贴近外部库而重写当前 APS 的数据结构。
当前项目只借鉴“图表达”这个思路。
```

### NeurIPS JSSP 图强化学习论文

参考：

```text
https://proceedings.neurips.cc/paper/2020/file/11958dfee29b6709f48a9ba0387a2431-Paper.pdf
```

启发：

```text
析取图和图神经网络可以学习派工规则。
这说明“图 + 排产”不是拍脑袋方向。
```

边界：

```text
当前项目不引入 PyTorch。
当前项目不引入 Gym。
当前项目不做强化学习。
当前项目不训练模型。
当前项目重点是可解释、可离线交付、Win7 可跑。
```

大白话说：

```text
论文可以证明方向有研究价值，但不能证明当前 APS 应该马上上图神经网络。
```

### Maximum Flow of Complex Manufacturing Networks

参考：

```text
https://www.sciencedirect.com/science/article/pii/S2212827120300056
```

启发：

```text
制造网络可以借助最大流思路分析产能上限和瓶颈。
```

边界：

```text
可以借鉴“用流看瓶颈”的思路。
但当前不要直接拿最大流结果改派工。
最大流适合做瓶颈报告，不适合作为当前排产器。
```

### NetworkX Flow 文档

参考：

```text
https://networkx.org/documentation/stable/reference/algorithms/flow.html
```

启发：

```text
最大流、最小割、最小费用流适合表达供需、瓶颈、容量约束。
```

边界：

```text
min_cost_flow 不进当前主线。
不要把 min_cost_flow 当当前排产器。
如果后续研究 min_cost_flow，要先解决整数成本、业务成本定义、失败解释和责任边界。
```

特别注意：

```text
最小费用流看起来像能自动改派工，但它不是当前项目的近期目标。
```

### NetworkX Bipartite 文档

参考：

```text
https://networkx.org/documentation/stable/reference/algorithms/bipartite.html
```

启发：

```text
二分图最大匹配适合 PR-8 的待排工序 × 候选设备匹配。
```

边界：

```text
maximum_matching 返回字典通常会包含两侧映射。
业务层只保留工序侧映射。
不要把完整 matching 原样丢到 summary、页面或 OperationLogs。
```

### NetworkX Centrality 文档

参考：

```text
https://networkx.org/documentation/stable/reference/algorithms/centrality.html
```

启发：

```text
中心性可以做“影响面提示灯”。
```

边界：

```text
中心性高不等于一定延期。
中心性高不等于系统应该自动调它。
中心性必须和关键路径、资源负荷、日历、交期余量一起解释。
```

页面上不要写：

```text
该工序中心性最高。
```

页面上应该写：

```text
这道工序后续牵连较多，一旦延误可能影响更多工序。
```

## 技术边界清单

后续所有 PR 都必须遵守下面这些边界。

### 1. NetworkX 不替代现有排产算法

不能让 NetworkX 变成第二套排产器。

允许：

```text
只读分析。
风险提示。
影响范围计算。
小摘要展示。
report-only 诊断。
```

不允许：

```text
直接用 NetworkX 结果覆盖 SGS。
直接用 NetworkX 结果改 adopted 方案。
直接用 NetworkX 结果改资源分配。
直接用 NetworkX 结果改工序顺序。
```

### 2. nx.Graph / nx.DiGraph 只留在图模块内部

不允许流到：

```text
Controller。
页面。
数据库。
Excel。
OperationLogs。
候选表。
result_summary public 摘要。
```

允许图模块内部使用：

```text
nx.DiGraph。
二分图。
内部临时 matching。
内部临时 metrics。
```

对外必须转成普通 Python 小结构：

```text
dict。
list。
str。
int。
float。
bool。
None。
```

### 3. diagnostics sample 不能当业务决策依据

diagnostics 只是排障采样，不是完整业务结果。

不能这样做：

```text
页面根据 diagnostics sample 做完整统计。
导出 diagnostics sample 当正式报告。
OperationLogs 记录完整 diagnostics。
用户根据 sample 判断全部工序健康。
```

应该这样做：

```text
public summary 放稳定小摘要。
diagnostics 只辅助开发排查。
diagnostics 要有采样数量和截断标记。
```

### 4. 不做静默兜底

不允许：

```text
NetworkX 不可用时假装分析成功。
资源为空时默默塞全量设备。
图有环时假装 DAG。
指标算不出来时填 0。
匹配失败时填 matched=0 但 status=ok。
候选数据缺失时假装有完整对比。
```

必须：

```text
失败就显示失败。
降级就显示降级。
不可用就显示不可用。
不确定就显示 warning。
```

### 5. 资源匹配失败必须可见

资源匹配可能失败或不可用。必须有明确状态：

```text
ok。
warning。
degraded。
unavailable。
error。
```

这些是展示层建议词，后续实现时要映射到既有 graph_analysis public 合同，不能随手破坏已存在的 `status` / `reason` 口径。

示例：

```text
candidate_machine_ids 为空：warning 或 unavailable。
ready_nodes 为空：ok + no_ready_operations，或者 unavailable，按业务口径固定。
NetworkX 未安装：unavailable。
图增强不可用：degraded。
匹配结果不能覆盖所有 ready 工序：warning。
```

### 6. 没有候选资源不能默默塞全量资源

这是硬边界。

不能这样做：

```text
如果 candidate_machine_ids 为空，就默认所有设备都能做。
如果 candidate_operator_ids 为空，就默认所有人都能做。
```

原因：

```text
这会掩盖主数据问题。
这会让资源覆盖报告失去意义。
这会让调度员以为资源充足。
```

正确做法：

```text
明确提示候选资源为空。
把它记为资源覆盖风险。
只在 diagnostics 里放采样。
不要自动补资源。
```

### 7. min_cost_flow 不进当前主线

min_cost_flow 只能放后续研究。

当前不允许：

```text
用 min_cost_flow 自动改派工。
用 min_cost_flow 自动换设备。
用 min_cost_flow 自动调整顺序。
用 min_cost_flow 当排产器。
```

后续如果研究，必须先单独解决：

```text
成本怎么定义。
设备切换成本怎么定义。
延期成本怎么定义。
加班成本怎么定义。
整数成本怎么转换。
失败结果怎么解释。
和现有 SGS / 候选方案怎么对齐。
用户是否能理解和接受。
```

### 8. 不新增近期不必要重依赖

当前仍然坚持 Win7 / Python 3.8 / 离线交付口径。

近期不引入：

```text
PyTorch。
Gym。
Graphviz。
pygraphviz。
SciPy。
Pandas。
NumPy 作为强依赖。
外部前端 CDN。
新的前端资源下载链路。
```

NetworkX 继续锁定：

```text
networkx==3.1
```

`graph_analysis_mode=off` 时仍然不要求 NetworkX。

### 9. PR-8 继续不改排产结果

PR-8 的底线：

```text
不改排产结果。
不改资源分配。
不改 SGS 排序。
不落候选表。
不新增页面入口。
不新增 schema。
```

PR-8 的价值是补诊断证据，不是补自动派工能力。

## 后续落地顺序建议

建议后续不要一次性把所有诊断都做完。可以按下面顺序推进。

### 近期：PR-8

目标：

```text
资源匹配 report-only 分析。
```

只做：

```text
首波 ready 工序 × 候选设备。
二分图最大匹配。
matched / unmatched / bottleneck 小摘要。
diagnostics 采样。
OperationLogs 小摘要。
```

不做：

```text
人员匹配。
页面入口。
最小费用流。
自动派工。
自动排序。
```

### PR-8 之后：第一批诊断方向

可以考虑拆成 2 到 4 个小 PR，而不是一个大 PR。

建议拆法：

```text
PR-A：排产体检报告。
PR-B：资源覆盖报告增强，承接 PR-8。
PR-C：瓶颈雷达。
PR-D：交期风险清单。
```

这些只是后续拆分建议，不等同于已经写入 items.yaml 的正式 planned 条目。真正进入开发前，仍要由用户确认，并通过 roadmap update 拆成具体 items。

如果想更小，可以先把页面入口延后，只先把 summary 小摘要打稳。

优先级建议：

```text
1. 资源覆盖报告，因为最贴近 PR-8。
2. 排产体检报告，因为能发现明显数据和结构问题。
3. 瓶颈雷达，因为需要整合关键链、负荷和影响范围。
4. 交期风险清单，因为需要把多类风险解释成人话。
```

### 第一批稳定之后：第二批影响分析

建议第二批不要和第一批混做。

第二批需要用户输入条件，比如设备停机、物料缺料、版本对比。它更像“问一个假设，系统告诉你影响谁”。

建议拆法：

```text
PR-E：停机影响分析。
PR-F：缺料影响分析。
PR-G：版本差异影响报告。
```

这些同样只是后续拆分建议，不等同于已经写入 items.yaml 的正式 planned 条目。第二批继续只读，不自动重排。

### 第三批：只保留研究入口

第三批不要排近期计划。

可以在 future / backlog / deferred 里保留：

```text
自动建议。
插单模拟。
局部重排。
最小费用流派工。
自动换设备。
自动加班建议。
自动调顺序。
```

但要写清楚：

```text
不在当前 NetworkX 引入路线主线实现。
不在 PR-8 实现。
不在 Win7 第一版交付范围内实现。
需要单独 roadmap 和责任边界评审。
```

## 验收口径总表

后续每个诊断类 PR 都要能回答下面的问题。

| 问题 | 必须回答 |
| --- | --- |
| 是否改变排产结果 | 默认不改变，除非 roadmap 明确进入新的可控排产 PR |
| 是否写数据库 | 诊断类第一版默认不新增 schema，不写候选表 |
| 是否需要 NetworkX | off 模式不需要；report/on 按既有懒加载合同处理 |
| 是否能失败可见 | 必须可见，不能静默兜底 |
| 是否进 OperationLogs | 只进 public 小摘要 |
| 是否暴露完整图 | 不暴露 |
| 是否暴露 diagnostics 完整内容 | 不暴露，只采样 |
| 是否新增页面入口 | 第一批可规划为统一诊断入口，PR-8 不新增 |
| 是否引入重依赖 | 不引入 |
| 是否支持 Win7 / Python 3.8 | 必须支持 |

## 本节结论

后续 NetworkX 路线要按下面这条线走：

```text
PR-8：资源匹配 report-only，补资源覆盖证据。
第一批：排产诊断中心，看清当前这版排产。
第二批：影响分析，看清异常会影响谁。
第三批：自动建议和局部重排暂缓，只放后续研究。
```

最重要的边界再重复一遍：

```text
NetworkX 是排产结果体检医生，不是第二套排产大脑。
PR-8 仍然 report-only，不改排产结果。
第一批和第二批都优先做只读解释。
第三批涉及系统参与改排产，当前先不承诺开发。
```

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
core/algorithms/greedy/dispatch/ready_queue.py
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
graph/ready_queue.py   兼容导出算法层 ready_queue helper，不放真实调度逻辑
dispatch/ready_queue.py 当前可排工序计算，PR-5 的真实实现位置
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

阶段 10 是 PR-3 的主工作：把阶段 9 已经完成的图分析入口接到排产主链旁边，先只做 `report` 模式。它不是新算法阶段，也不是 `on` 模式阶段。

大白话说，排产照旧先跑完，排产结果先定下来；图分析只在旁边看一眼这些工序关系，然后把“看出来的摘要”写进本次排产结果里，方便人判断工序链路有没有风险。它不能反过来影响排产顺序、候选集合、评分、冻结窗口或落库明细。

阶段 10 的前置条件：

```text
1. PR-2 / scheduler-graph-core-module 已经完成并提交。
2. core/services/scheduler/graph/input_adapter.py 已能把完整 algo_ops 转成 OperationGraphNode，并能给 frozen 工序打固定标记。
3. core/services/scheduler/graph/analysis_service.py 已能返回 GraphAnalysisSummary。
4. core/services/scheduler/graph/exporter.py 已能把 GraphAnalysisSummary 转成普通 dict。
5. graph_analysis_mode / graph_block_on_cycle / graph_debug_export 等配置字段已经走完 config snapshot 和页面保存链路。
```

如果前置条件不满足，先回阶段 9 或 PR-2 收尾，不要在阶段 10 里补图核心模块的旧账。

### 10.0 整体实现要求

本阶段必须把下面这些实现原则当成硬约束写进设计、代码和验收里：

```text
优雅简洁：
- 阶段 10 只做“排产主链旁路接入 + summary 投影 + 日志小摘要合同 + 回归测试”。
- schedule_orchestrator.py 只负责判断 graph_analysis_mode、调用图分析服务、拿到 public / diagnostics 两个普通 dict。
- summary 组装层只负责把 public 放进 result_summary["algo"]["graph_analysis"]，把 diagnostics 放进 result_summary["diagnostics"]["graph_analysis"]。
- OperationLogs 不新增一套图日志写入器；继续沿用现有 result_summary_obj.get("algo") 小摘要路径。
- 第一版不要新建 graph_report_pipeline.py、graph_summary_repository.py、graph_observer.py 这类过早抽象；如果需要 helper，先放在 orchestrator 或 summary 附近的小函数里，保持调用链短而清楚。

不过度兜底：
- 不允许 broad except Exception 后返回空 graph_analysis。
- 不允许 NetworkX 缺失、版本不对、图输入合同错误时伪装成 status="available" 或“没有图数据”。
- 不允许因为 report 是旁路能力，就吞掉 GraphInputContractError / GraphBuildContractError 的原因。
- 不允许发现 diagnostics 太大时悄悄删字段；必须按本阶段写死的采样规则输出，并由测试验证 size guard。
- 不允许为了兼容脏输入，在阶段 10 里补默认 source、默认 duration、默认 seq、默认 batch。

不做静默回退：
- graph_analysis_mode=off 时不 import graph 模块，不调用 NetworkX，不写 graph_analysis 字段。
- graph_analysis_mode=report 时，如果 NetworkX 不可用，必须写出 status="unavailable"、reason="networkx_unavailable" 和业务可读 message；这不是静默回退，因为结果里明确告诉用户“图分析没跑起来”。
- graph_analysis_mode=report 时，如果图输入合同错误，必须写出 status="input_error" 或 status="build_error" 和明确 reason；不能把错误吞掉当作正常空图。
- 未知异常不要捕获成空报告；未知异常说明实现有 bug，应暴露给测试和开发者处理。
- 有环不是 Python 异常；应保留 status="available"、is_dag=false、cycle_edge_count 和 warning_count，是否阻止排产留到阶段 11。

不过度防御性编程：
- maybe_analyze_schedule_graph 只接收 ScheduleRunInput，不兼容 dict、Flask request、数据库 row、Excel row。
- 图输入只来自 schedule_input.algo_ops / algo_ops_to_schedule 计数 / batches / resource_pool / frozen_op_ids / seed_results 计数，不重新查数据库。
- 不在阶段 10 里重新实现 input_adapter、analysis_service、exporter 的字段映射和图算法。
- 不写“字段 A 没有就试 B/C/D”的多套兼容分支；字段合同由阶段 5 到阶段 9 保证。
- 继续使用 Python 3.8 兼容写法：Dict / List / Optional / Tuple / Any，不使用 list[str] / str | None。

高内聚低耦合：
- schedule_orchestrator.py 可以在 graph_analysis_mode 为 report/on 时局部 import input_adapter、analysis_service、exporter、nx_runtime 和图合同错误类型；off 模式不能触发这些 import。
- core/services/scheduler/graph/ 不能反向 import schedule_orchestrator.py、schedule_summary_assembly.py、schedule_persistence.py、ScheduleService、Flask、数据库或页面。
- SummaryBuildContext 只新增普通 dict 字段，不承载 nx.DiGraph、GraphAnalysisSummary 原对象、OperationGraphNode 列表、完整 nodes/edges。
- result_summary 和 OperationLogs 不能出现 nx.DiGraph、完整 node_metrics、完整 topological_order、完整 nodes/edges 或 raw 原始对象。
- 阶段 10 不改变 optimizer_outcome.results、best_order、attempts、batch_order、sorted_ops、seed_results、frozen_op_ids、validated_schedule_payload 和 schedule_rows。
```

### 10.1 阶段目标与上下游合同

阶段 10 的输入来自当前排产编排层已有的 `ScheduleRunInput`：

```python
from core.services.scheduler.run.schedule_input_collector import ScheduleRunInput

schedule_input: ScheduleRunInput
```

本阶段只读取这些字段：

```text
schedule_input.cfg.graph_analysis_mode
schedule_input.algo_ops
schedule_input.algo_ops_to_schedule
schedule_input.batches
schedule_input.resource_pool
schedule_input.frozen_op_ids
schedule_input.seed_results
```

这些字段已经在 `ScheduleRunInput` 中存在，阶段 10 不需要新增输入收集逻辑，也不需要重新查仓库。

阶段 10 的输出只允许是两个普通 dict：

```python
from typing import Any, Dict, Optional, Tuple

GraphAnalysisProjection = Tuple[
    Optional[Dict[str, Any]],  # public
    Optional[Dict[str, Any]],  # diagnostics
]
```

输出去向固定：

```text
public:
  result_summary["algo"]["graph_analysis"]
  OperationLogs.detail["algo"]["graph_analysis"] 也会跟随现有 algo 小摘要出现

diagnostics:
  result_summary["diagnostics"]["graph_analysis"]
  不进入 OperationLogs
```

阶段 10 的模式口径：

```text
graph_analysis_mode=off:
  不分析。
  不 import graph 模块。
  不写 graph_analysis 字段。
  不要求安装 NetworkX。

graph_analysis_mode=report:
  运行只读图分析。
  写 result_summary 小摘要和采样诊断。
  不改变排产结果。

graph_analysis_mode=on:
  阶段 10 先按 report 同等处理，只写摘要和诊断。
  不接 ready 队列。
  不接关键路径评分。
  不接资源匹配。
  真正改变候选队列和评分留到阶段 12 / 阶段 13。
```

为什么 `on` 在阶段 10 先按 `report` 处理：

```text
配置项已经允许 on，但阶段 10 还没有实现 ready 队列和评分。
为了不让用户误以为 on 已经改变排产，本阶段必须在 public 摘要里写清 effective_mode="report_only"。
后续阶段 12 接 ready 队列时，再把 on 的行为真正切过去。
```

### 10.2 在排产入口加旁路分析

接入位置固定在：

```text
core/services/scheduler/run/schedule_orchestrator.py
  orchestrate_schedule_run()
```

更具体的位置：

```text
1. optimize_schedule_fn(...) 已经返回 optimizer_outcome。
2. build_validated_schedule_payload(...) 已经验证排产结果可落库。
3. SummaryBuildContext(...) 还没创建。
4. build_result_summary_fn(...) 还没调用。
```

这样做的目的：

```text
排产结果已经由原算法算完。
落库 payload 已经按原规则验证。
图分析只在 summary 组装前补一份报告。
如果图分析写错，测试能直接证明它有没有碰到结果、候选、落库行。
```

建议新增一个小函数：

```python
from typing import Any, Dict, Optional, Tuple

from .schedule_input_collector import ScheduleRunInput


def maybe_analyze_schedule_graph(
    schedule_input: ScheduleRunInput,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    mode = _graph_analysis_mode(schedule_input.cfg)
    if mode == "off":
        return None, None

    return _build_schedule_graph_analysis_projection(schedule_input, mode=mode)
```

`_graph_analysis_mode(cfg)` 的规则：

```text
读取 cfg.graph_analysis_mode。
只接受 off / report / on。
如果 cfg 已经过 config snapshot 校验，这里不再做第二套兜底。
如果读到未知值，抛 ValueError 或合同错误；不要静默改成 off。
```

`_build_schedule_graph_analysis_projection(...)` 的核心伪代码：

```python
def _build_schedule_graph_analysis_projection(
    schedule_input: ScheduleRunInput,
    *,
    mode: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    from core.services.scheduler.graph.analysis_service import ScheduleGraphAnalysisService
    from core.services.scheduler.graph.exporter import graph_summary_to_dict
    from core.services.scheduler.graph.input_adapter import (
        GraphInputContractError,
        build_operation_nodes_from_rows,
    )
    from core.services.scheduler.graph.nx_runtime import NetworkXUnavailable
    from core.services.scheduler.graph.precedence_builder import GraphBuildContractError

    started = time.time()
    try:
        nodes = build_operation_nodes_from_rows(
            schedule_input.algo_ops,
            batches=schedule_input.batches,
            resource_pool=schedule_input.resource_pool,
            frozen_op_ids=schedule_input.frozen_op_ids,
        )
        summary = ScheduleGraphAnalysisService().analyze_linear_batches(nodes, metrics_mode="basic")
        payload = graph_summary_to_dict(summary)
    except NetworkXUnavailable as exc:
        return _graph_unavailable_projection(mode=mode, exc=exc, started=started)
    except GraphInputContractError as exc:
        return _graph_contract_error_projection(
            mode=mode,
            status="input_error",
            reason="graph_input_contract_error",
            exc=exc,
            started=started,
        )
    except GraphBuildContractError as exc:
        return _graph_contract_error_projection(
            mode=mode,
            status="build_error",
            reason="graph_build_contract_error",
            exc=exc,
            started=started,
        )

    return _project_graph_analysis_payload(
        mode=mode,
        payload=payload,
        elapsed_ms=_elapsed_ms(started),
    )
```

禁止事项：

```text
不要把 import 放到模块顶层导致 off 模式也 import graph 模块。
不要在 except 里捕获 Exception。
不要在这里调用 schedule_optimizer.py、GreedyScheduler、dispatch_sgs、summary builder、persistence、repo、Flask request。
不要在这里修改 schedule_input.algo_ops、schedule_input.algo_ops_to_schedule、schedule_input.resource_pool、schedule_input.seed_results。
不要把 graph_summary_to_dict(summary) 原样全量塞进 public 或 diagnostics。
```

### 10.3 graph_analysis 投影字段

`graph_summary_to_dict(summary)` 是阶段 9 的完整普通 dict，不等于阶段 10 能直接写入 `result_summary` 的内容。阶段 10 必须从它投影出两份更小、更稳定的结构。

公开小摘要 `public` 固定结构：

```json
{
  "mode": "report",
  "effective_mode": "report",
  "status": "available",
  "node_count": 120,
  "edge_count": 118,
  "is_dag": true,
  "critical_path_minutes": 960,
  "critical_path_node_count": 8,
  "warning_count": 0,
  "cycle_edge_count": 0,
  "time_cost_ms": 12
}
```

当配置是 `on`、但仍处于阶段 10 时：

```json
{
  "mode": "on",
  "effective_mode": "report_only",
  "status": "available",
  "node_count": 120,
  "edge_count": 118,
  "is_dag": true,
  "critical_path_minutes": 960,
  "critical_path_node_count": 8,
  "warning_count": 0,
  "cycle_edge_count": 0,
  "time_cost_ms": 12
}
```

NetworkX 不可用时的公开小摘要：

```json
{
  "mode": "report",
  "effective_mode": "report",
  "status": "unavailable",
  "reason": "networkx_unavailable",
  "message": "缺少可选依赖 networkx==3.1；请先安装 requirements-optimizer-lite-win7.txt",
  "time_cost_ms": 1
}
```

图输入合同错误时的公开小摘要：

```json
{
  "mode": "report",
  "effective_mode": "report",
  "status": "input_error",
  "reason": "graph_input_contract_error",
  "message": "graph_input.op[123] 字段 source 只允许 internal/external：'bad'",
  "time_cost_ms": 2
}
```

诊断采样 `diagnostics` 固定结构：

```json
{
  "topological_order_sample": ["op:B001:OP10:123", "op:B001:OP20:124"],
  "topological_order_count": 120,
  "topological_order_truncated": true,
  "critical_path_sample": ["op:B001:OP10:123", "op:B001:OP20:124"],
  "critical_path_count": 8,
  "critical_path_truncated": false,
  "cycle_edges_sample": [],
  "cycle_edge_count": 0,
  "warnings_sample": [],
  "warning_count": 0,
  "node_metrics_sample": [
    {
      "node_id": "op:B001:OP10:123",
      "is_on_critical_path": true,
      "critical_path_rank": 0,
      "impact_count": 3,
      "generation_index": 0,
      "downstream_critical_minutes": 960
    }
  ],
  "node_metrics_count": 120,
  "node_metrics_truncated": true
}
```

采样上限建议写成常量，不要散落魔法数字：

```python
_GRAPH_TOPOLOGICAL_SAMPLE_LIMIT = 20
_GRAPH_CRITICAL_PATH_SAMPLE_LIMIT = 50
_GRAPH_WARNING_SAMPLE_LIMIT = 20
_GRAPH_CYCLE_EDGE_SAMPLE_LIMIT = 20
_GRAPH_NODE_METRIC_SAMPLE_LIMIT = 20
```

采样规则：

```text
topological_order_sample:
  取 topological_order 前 20 个。

critical_path_sample:
  取 critical_path 前 50 个。

cycle_edges_sample:
  取 cycle_edges 前 20 个。

warnings_sample:
  取 warnings 前 20 个，每条只保留 code / message / data。

node_metrics_sample:
  优先按 topological_order 前 20 个节点取 node_metrics。
  如果 topological_order 为空，就按 node_id 字符串排序取前 20 个。

*_count:
  保留原始总数。

*_truncated:
  原始总数大于 sample 上限时为 true。
```

禁止字段：

```text
public 不放 topological_order_sample。
public 不放 critical_path_sample。
public 不放 node_metrics_sample。
diagnostics 不放完整 topological_order。
diagnostics 不放完整 node_metrics。
diagnostics 不放 nodes / edges。
diagnostics 不放 raw。
任何位置都不放 nx.DiGraph。
```

### 10.4 SummaryBuildContext 和 summary 组装接入

在 `core/services/scheduler/summary/schedule_summary_types.py` 的 `SummaryBuildContext` 增加两个可选字段：

```python
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SummaryBuildContext:
    ...
    graph_analysis_public: Optional[Dict[str, Any]] = None
    graph_analysis_diagnostics: Optional[Dict[str, Any]] = None
```

字段规则：

```text
graph_analysis_public:
  只能是 public 小摘要 dict。
  None 表示 off 模式或未启用图分析。

graph_analysis_diagnostics:
  只能是 diagnostics 采样 dict。
  None 表示 off 模式、图分析不可用、或没有诊断信息。
```

在 `core/services/scheduler/run/schedule_orchestrator.py` 创建 `SummaryBuildContext` 前调用：

```python
graph_analysis_public, graph_analysis_diagnostics = maybe_analyze_schedule_graph(schedule_input)

summary_ctx = SummaryBuildContext(
    ...
    graph_analysis_public=graph_analysis_public,
    graph_analysis_diagnostics=graph_analysis_diagnostics,
)
```

在 `core/services/scheduler/summary/schedule_summary_assembly.py` 里接入：

```python
def _algo_dict(state: AlgorithmSummaryState) -> Dict[str, Any]:
    ...
    if state.ctx.graph_analysis_public is not None:
        algo["graph_analysis"] = dict(state.ctx.graph_analysis_public)
    return algo
```

`diagnostics` 合并规则：

```python
public_algo, optimizer_diagnostics = project_public_algo_summary(_algo_dict(algorithm_state))
diagnostics = dict(optimizer_diagnostics or {})
if ctx.graph_analysis_diagnostics:
    diagnostics["graph_analysis"] = dict(ctx.graph_analysis_diagnostics)
...
if diagnostics:
    result_summary["diagnostics"] = diagnostics
```

注意：

```text
不要改变 summary_schema_version。
不要让 optimizer_public_summary.py 为 graph_analysis 写特殊过滤逻辑；public 小摘要本身已经是公开安全结构。
不要把 graph_analysis_diagnostics 先塞进 algo 再让 project_public_algo_summary 拆出来；这样边界绕远了。
不要把 diagnostics.graph_analysis 写进 ScheduleSummaryContract 的顶层字段之外。
```

### 10.5 OperationLogs 小摘要合同

当前 `core/services/scheduler/run/schedule_persistence.py` 的 OperationLogs detail 会写：

```text
detail["algo"] = result_summary_obj.get("algo")
```

所以阶段 10 不需要新增 OperationLogs 写入入口。它只需要保证：

```text
result_summary_obj["algo"]["graph_analysis"] 本身就是小摘要。
diagnostics.graph_analysis 不进入 OperationLogs。
完整 nodes / edges 不进入 OperationLogs。
完整 node_metrics 不进入 OperationLogs。
完整 topological_order 不进入 OperationLogs。
```

OperationLogs 允许看到的字段：

```json
{
  "algo": {
    "graph_analysis": {
      "mode": "report",
      "effective_mode": "report",
      "status": "available",
      "node_count": 120,
      "edge_count": 118,
      "is_dag": true,
      "critical_path_minutes": 960,
      "critical_path_node_count": 8,
      "warning_count": 0,
      "cycle_edge_count": 0,
      "time_cost_ms": 12
    }
  }
}
```

OperationLogs 禁止看到的 key：

```text
nodes
edges
raw
topological_order
node_metrics
topological_order_sample
critical_path_sample
warnings_sample
cycle_edges_sample
```

如果后续用户需要看完整图，只能走阶段 13 的 debug export 或后续受控调试接口，不能在阶段 10 偷偷把全量图塞进日志。

### 10.6 report 模式错误和 warning 口径

阶段 10 的错误分三类：

```text
1. 图分析没启用：
   graph_analysis_mode=off。
   不输出 graph_analysis。

2. 图分析启用了，但可选依赖或图输入合同不满足：
   输出 public graph_analysis，status 明确为 unavailable / input_error / build_error。
   不输出 diagnostics 或只输出很小的 error 诊断。
   不改变排产结果。

3. 图分析自身遇到未知异常：
   不捕获成空报告。
   让异常暴露，让测试和开发者修实现问题。
```

已知错误状态：

```text
NetworkXUnavailable:
  status="unavailable"
  reason="networkx_unavailable"

GraphInputContractError:
  status="input_error"
  reason="graph_input_contract_error"

GraphBuildContractError:
  status="build_error"
  reason="graph_build_contract_error"
```

有环图的口径：

```text
有环图不是 input_error。
只要图成功建成，status 仍是 available。
public.is_dag=false。
public.cycle_edge_count > 0。
public.warning_count > 0。
diagnostics.cycle_edges_sample 给出采样。
阶段 10 不阻止排产。
阶段 11 再决定 on + block_on_cycle=yes 时是否阻止。
```

为什么 NetworkX 不可用不直接阻止 report 模式排产：

```text
report 模式的承诺是“不改变排产结果，只增加可见报告”。
如果现场少装可选依赖就阻止排产，等于 report 模式反而改变了业务结果。
所以这里允许排产继续，但必须把 status="unavailable" 明确写进结果摘要。
这不是静默回退，因为用户和测试都能看到图分析没有实际运行。
```

### 10.7 测试文件和用例

阶段 10 至少新增或补齐三份回归测试：

```text
tests/regression_scheduler_graph_report_mode_contract.py
tests/regression_scheduler_graph_summary_contract.py
tests/regression_scheduler_graph_operation_logs_contract.py
```

`regression_scheduler_graph_report_mode_contract.py` 必须覆盖：

```text
测试 1：off 模式不 import graph 模块、不要求 NetworkX
做法：
  复用 regression_scheduler_graph_lazy_runtime_contract.py 的思路。
断言：
  graph_analysis_mode=off 时不出现 result_summary.algo.graph_analysis。
  import schedule_orchestrator 不触发 networkx import。

测试 2：report 模式不改变 optimizer_outcome 和 validated_schedule_payload
做法：
  构造固定 schedule_input 和假 optimize_schedule_fn。
  记录 optimize 返回的 results / best_order / attempts。
  跑 orchestrate_schedule_run。
断言：
  outcome.results 与 optimize 返回对象一致或值一致。
  outcome.best_order 不被重排。
  outcome.validated_schedule_payload.schedule_rows 与关闭 graph 时一致。

测试 3：report 模式读取完整 algo_ops 并保留 frozen/seed scope
做法：
  monkeypatch build_operation_nodes_from_rows，记录入参。
断言：
  rows 是 schedule_input.algo_ops。
  batches 是 schedule_input.batches。
  resource_pool 是 schedule_input.resource_pool。
  frozen_op_ids 是 schedule_input.frozen_op_ids。
  public scope 里记录 total_algo_op_count / reschedulable_unfrozen_op_count / frozen_node_count / seed_result_count。
  不调用 repo / db / Flask。

测试 4：NetworkXUnavailable 可见但不改排产结果
做法：
  monkeypatch ScheduleGraphAnalysisService 或 import_networkx 触发 NetworkXUnavailable。
断言：
  outcome.result_summary_obj["algo"]["graph_analysis"]["status"] == "unavailable"。
  reason == "networkx_unavailable"。
  outcome.results / schedule_rows 仍与关闭 graph 时一致。

测试 5：GraphInputContractError / GraphBuildContractError 可见但不伪装成功
断言：
  status 分别是 input_error / build_error。
  reason 分别是 graph_input_contract_error / graph_build_contract_error。
  不返回 status="available"。
  不返回空 dict 冒充成功。

测试 6：未知异常不被吞掉
做法：
  monkeypatch 图分析函数抛 RuntimeError("boom")。
断言：
  orchestrate_schedule_run 抛出 RuntimeError。
  不生成 status="available" 或 status="unavailable" 的假报告。
```

`regression_scheduler_graph_summary_contract.py` 必须覆盖：

```text
测试 1：algo.graph_analysis 是公开小摘要
断言：
  result_summary_obj["algo"]["graph_analysis"] 包含 mode / effective_mode / status / node_count / edge_count / is_dag / critical_path_minutes / warning_count / time_cost_ms。
  不包含 topological_order_sample / node_metrics_sample / nodes / edges / raw。

测试 2：diagnostics.graph_analysis 是采样诊断
断言：
  result_summary_obj["diagnostics"]["graph_analysis"] 包含 topological_order_sample / critical_path_sample / warnings_sample / node_metrics_sample。
  各 sample 长度不超过本阶段常量。
  有 *_count 和 *_truncated 字段说明是否被截断。

测试 3：diagnostics 与 optimizer diagnostics 能共存
做法：
  构造 optimizer attempts 产生 diagnostics.optimizer。
  同时开启 graph report。
断言：
  diagnostics.optimizer 仍存在。
  diagnostics.graph_analysis 也存在。
  两者没有互相覆盖。

测试 4：summary size guard 不靠全量图硬扛
做法：
  构造超过 sample limit 的 graph payload。
断言：
  graph diagnostics 已先采样。
  apply_summary_size_guard 后 result_summary 仍可 json.dumps。
  不出现完整 node_metrics。
```

`regression_scheduler_graph_operation_logs_contract.py` 必须覆盖：

```text
测试 1：OperationLogs 只写 graph_analysis 小摘要
做法：
  跑一次 report 模式排产或直接调用 persist_schedule 相关路径。
断言：
  OperationLogs.detail["algo"]["graph_analysis"] 存在。
  只包含 public 小摘要字段。

测试 2：OperationLogs 不写完整图
断言：
  OperationLogs.detail JSON 递归搜索不到 nodes / edges / raw / node_metrics / topological_order。
  也搜索不到 topological_order_sample / critical_path_sample / warnings_sample / cycle_edges_sample。

测试 3：simulate 和正式排产日志口径一致
断言：
  simulate=True 时 action="simulate"，graph_analysis 仍是小摘要。
  simulate=False 时 action="schedule"，graph_analysis 仍是小摘要。
```

建议同步补充或复跑这些已有测试：

```text
tests/regression_schedule_orchestrator_contract.py
tests/regression_schedule_service_facade_delegation.py
tests/regression_scheduler_summary_result_summary_contract.py
tests/regression_schedule_summary_size_guard_large_lists.py
tests/regression_scheduler_graph_lazy_runtime_contract.py
tests/scheduler_graph
```

### 10.8 阶段 0 基线对比口径

阶段 10 必须重新跑阶段 0 保存的三个 case：

```text
case_001_normal
case_002_urgent
case_003_external
```

运行配置：

```text
graph_analysis_mode=report
graph_debug_export=no
graph_block_on_cycle=no
```

对比目标：

```text
case_001 排产结果与 before_networkx baseline 完全一致。
case_002 排产结果与 before_networkx baseline 完全一致。
case_003 排产结果与 before_networkx baseline 完全一致。
```

允许不同的字段：

```text
version
schedule_time / created_at / updated_at
time_cost_ms
history id / log id
result_summary.algo.graph_analysis
result_summary.diagnostics.graph_analysis
```

不允许不同的字段：

```text
Schedule 行数
每条 Schedule 的 op_id / batch_id / machine_id / operator_id / supplier_id
每条 Schedule 的 start_time / end_time
summary.total_ops / scheduled_ops / failed_ops
best_order
selected_batch_ids
freeze_window.frozen_op_count
resource_pool 公开状态
```

如果这些不允许不同的字段发生变化：

```text
立即停止。
不要继续补更多兼容逻辑。
先回 schedule_orchestrator.py 检查图分析是否误改了输入、候选、排序或落库 payload。
```

### 10.9 实施顺序

建议按下面顺序开工：

```text
1. 先补 tests/regression_scheduler_graph_summary_contract.py，写清 public / diagnostics 字段形状。
2. 在 SummaryBuildContext 增加 graph_analysis_public / graph_analysis_diagnostics 两个可选 dict 字段。
3. 在 schedule_summary_assembly.py 把 public 写进 algo.graph_analysis，把 diagnostics 合并进 diagnostics.graph_analysis。
4. 跑 summary 合同测试，确认不影响现有 optimizer diagnostics。
5. 在 schedule_orchestrator.py 增加 _graph_analysis_mode 和 maybe_analyze_schedule_graph。
6. 在 schedule_orchestrator.py 增加 public / diagnostics 投影 helper，off 模式保持零 graph import。
7. 补 tests/regression_scheduler_graph_report_mode_contract.py，锁住 off/report/on 阶段 10 行为。
8. 补 tests/regression_scheduler_graph_operation_logs_contract.py，锁住日志只写小摘要。
9. 复跑 tests/scheduler_graph，确认阶段 5 到阶段 9 图模块合同没有被阶段 10 反向污染。
10. 对阶段 0 三个 baseline case 做 report 模式对比。
11. 跑 ruff / pyright。
12. 提交后在干净工作区跑最终 quality gate。
13. 回填本 roadmap、items.yaml 和对应 CodeStable feature/acceptance 记录。
```

注意：

```text
第 5 步之前，不要先改 schedule_optimizer.py 或 core/algorithms/greedy/。
第 6 步如果发现 off 模式 import 了 graph 模块，先修 import 边界，不要靠测试里 monkeypatch 掩盖。
第 10 步如果 baseline 有差异，先停下来找误接入点，不要通过放宽对比规则过关。
```

### 10.10 阶段验收清单

```text
[x] graph_analysis_mode=off 时不 import graph 模块，不要求 NetworkX，不写 graph_analysis。
[x] graph_analysis_mode=report 时调用 build_operation_nodes_from_rows、ScheduleGraphAnalysisService.analyze_linear_batches、graph_summary_to_dict。
[x] graph_analysis_mode=on 在阶段 10 只按 report_only 输出摘要，不接 ready 队列、不接评分。
[x] maybe_analyze_schedule_graph 只读取 schedule_input.cfg / algo_ops / algo_ops_to_schedule 计数 / batches / resource_pool / frozen_op_ids / seed_results 计数。
[x] schedule_orchestrator.py 不修改 optimizer_outcome.results、best_order、attempts、seed_results、frozen_op_ids。
[x] SummaryBuildContext 只新增 graph_analysis_public / graph_analysis_diagnostics 普通 dict 字段。
[x] result_summary["algo"]["graph_analysis"] 是 public 小摘要。
[x] result_summary["diagnostics"]["graph_analysis"] 是采样诊断。
[x] public 小摘要不包含 topological_order_sample、critical_path_sample、node_metrics_sample、nodes、edges、raw。
[x] diagnostics 只包含 sample/count/truncated，不包含完整 topological_order、完整 node_metrics、nodes、edges、raw。
[x] OperationLogs.detail["algo"]["graph_analysis"] 只有 public 小摘要。
[x] OperationLogs.detail 中没有 diagnostics.graph_analysis。
[x] OperationLogs.detail 递归搜索不到 nodes / edges / raw / node_metrics / topological_order。
[x] NetworkXUnavailable 会输出 status="unavailable" 和 reason="networkx_unavailable"。
[x] GraphInputContractError 会输出 status="input_error" 和 reason="graph_input_contract_error"。
[x] GraphBuildContractError 会输出 status="build_error" 和 reason="graph_build_contract_error"。
[x] 未知异常不会被 broad except 吞成空报告。
[x] 有环图在 report 模式只写 warning / cycle_edges_sample，不阻止排产。
[x] 阶段 0 三个 baseline case 在 report 模式下排产结果不变，只新增 graph_analysis 摘要。
[x] tests/regression_scheduler_graph_report_mode_contract.py 通过。
[x] tests/regression_scheduler_graph_summary_contract.py 通过。
[x] tests/regression_scheduler_graph_operation_logs_contract.py 通过。
[x] tests/regression_schedule_orchestrator_contract.py 继续通过。
[x] tests/regression_schedule_service_facade_delegation.py 继续通过。
[x] tests/regression_scheduler_summary_result_summary_contract.py 继续通过。
[x] tests/regression_schedule_summary_size_guard_large_lists.py 继续通过。
[x] tests/regression_scheduler_graph_lazy_runtime_contract.py 继续通过。
[x] tests/scheduler_graph 全目录继续通过。
[x] ruff check 通过。
[x] pyright 通过。
[ ] 最终 clean-worktree quality gate 在提交后通过。
```

推荐验证命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_schedule_orchestrator_contract.py tests/regression_schedule_service_facade_delegation.py tests/regression_scheduler_summary_result_summary_contract.py tests/regression_schedule_summary_size_guard_large_lists.py tests/regression_scheduler_graph_lazy_runtime_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/summary core/services/scheduler/graph tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/summary core/services/scheduler/graph
```

PR-3 最终收尾前还要在干净工作区跑：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

注意：

```text
--require-clean-worktree 必须等阶段 10 代码、测试、roadmap / items.yaml / feature 记录全部提交后再跑。
如果工作区还有未提交文件，不能把它说成 clean-worktree proof。
```

### 10.11 明确不做

阶段 10 明确不做：

```text
[ ] 不改 schedule_optimizer.py。
[ ] 不改 core/algorithms/greedy/scheduler.py。
[ ] 不改 core/algorithms/greedy/dispatch/sgs.py。
[ ] 不改 core/algorithms/greedy/dispatch/sgs_scoring.py。
[ ] 不新增 ready_queue.py 的主链调用。
[ ] 不新增 scoring.py 的主链调用。
[ ] 不新增 resource_matching.py 的主链调用。
[ ] 不改变 sorted_ops。
[ ] 不改变 batch_order。
[ ] 不改变 dispatch_sgs 候选集合。
[ ] 不改变 SGS 评分。
[ ] 不改变 seed_results。
[ ] 不改变冻结窗口。
[ ] 不改变 validated_schedule_payload。
[ ] 不改变落库 schedule_rows。
[ ] 不改变 ScheduleHistory 行生成规则，除了 result_summary 多 graph_analysis 摘要。
[ ] 不改变 summary_schema_version。
[ ] 不把完整图写进 result_summary。
[ ] 不把完整图写进 OperationLogs。
[ ] 不新增页面、按钮、调试接口。
[ ] 不做 graph_debug_export 文件导出。
[ ] 不做 2000 节点性能证据。
[ ] 不做 PyInstaller / Win7 打包验证。
```

阶段 10 完成后的交接话术必须写清：

```text
阶段 10 只完成 report 模式旁路分析和结果摘要。
PR-3 仍然没有让图分析改变排产候选、评分、冻结窗口或落库 schedule_rows。
阶段 11 才处理有环阻止策略。
阶段 12 / 阶段 13 才能开始 on 模式的 ready 队列和评分接入。
```

如果这一步排产结果变了，说明图分析误接入了算法，应立即回退本阶段改动，先找误接入点，不要通过放宽测试或新增兜底逻辑让它“看起来通过”。

### 10.9 阶段 10 图报告加固后的 PR-4 / PR-5 承接

2026-05-18 复审后，阶段 10 的图报告不只需要“字段能写进去”，还需要补足后续 on 模式之前的证据边界。

本轮已修并纳入追踪的问题：

```text
P1:
- basic metrics：public 小摘要必须稳定写出 node_count、edge_count、is_dag、critical_path、warning_count、cycle_edge_count、time_cost_ms 等基础指标。
- frozen / seed scope：report 模式只读待排范围；seed_results / frozen_op_ids 只能作为后续 on 模式的已固定前置，不能重新进入待排候选。
- known graph error 顶层 warning：已知图输入/构建错误必须在 public 顶层 status / reason / message 可见，不能只藏在 diagnostics。

P2:
- warning.data 深层采样：warning 里的 data 必须深层保持 JSON 可序列化。
- diagnostics 采样：topological_order、critical_path、cycle_edges、warnings、node_metrics 只放 sample / count / truncated，不放完整图。
- OperationLogs：仍只拿 algo.graph_analysis public 小摘要，不写 diagnostics 或完整图。

P3:
- exporter：只导出已承诺字段，不做万能清洗器，不把未知对象 str() 后塞进 JSON。
- config：继续走 graph_analysis_mode / graph_block_on_cycle / graph_debug_export 已有配置链路，不另开绕过配置的入口。
- fail-fast：未知异常不吞成空报告；合同错误必须明确暴露成可识别 status/reason。
```

因此 PR-4 调整为：

```text
PR-4 = 性能护栏 + diagnostics 加固 + 真实集成证明。
```

PR-4 必须先证明：

```text
[x] 2000 节点规模的 report 分析耗时有记录，并已有阈值护栏。
[x] diagnostics.graph_analysis 只含采样、总数、截断标记和 JSON 可序列化 warning.data。
[x] known graph error 在 public 顶层可见，用户或日志小摘要能看懂失败原因。
[x] 真实排产链路里 report 模式仍不改变 rows、best_order、selected_batch_ids、freeze_window、resource_pool、seed_results、frozen_op_ids。
[x] config 默认 off、report/on 保存、fail-fast 和 exporter 边界都有测试或证据。
[x] graph_debug_export 本阶段未实现，已确认它只是后续附属能力，不能替代上面的证据。
```

#### PR-4 可执行细化：先证据，后导出

PR-4 的定位是“report 模式进入 on 模式前的证据关口”。大白话说，就是先证明这套图分析只是旁边看一眼、记一笔，不会偷偷改变排产；也要证明数据量变大时不会把摘要撑爆、不会慢到不可用。只有这些证据都稳了，后面的 PR-5 才能放心把图 ready 队列接到 SGS 候选集合。

PR-4 不是“把 NetworkX 接进排产决策”的 PR，也不是“先弄一个调试 JSON 文件看看”的 PR。调试导出只是最后的附属工具，不能拿它代替性能、diagnostics 和真实链路证明。

整体实现要求必须写进 PR-4 feature design，并在验收时逐条对照：

```text
1. 优雅简洁：只补当前证据关口需要的代码，不为了“以后可能会用”提前铺大框架。
2. 高内聚低耦合：run 层只负责调用和投影，graph 层只负责图构建/指标/普通 dict 导出，summary 层只负责合并 public/diagnostics，OperationLogs 只记录 public 小摘要，config 只走已有配置链路。
3. 不做过度兜底：不能为了让测试绿，给每层都加一套 fallback。
4. 不做静默回退：性能不达标、debug export 写失败、diagnostics 投影异常，都不能悄悄变成“成功但少字段”。
5. 不做过度防御性编程：只捕获已知图错误；未知异常必须暴露，不能被 broad except 吞成空报告。
6. 不自动关闭慢指标：如果 2000 节点性能不达标，必须回 roadmap 明确选择 basic report、缓存优化或拆后续 feature，不能在代码里偷偷变更输出口径。
```

PR-4 的文件边界：

```text
核心允许改：
- core/services/scheduler/run/schedule_graph_report.py
- core/services/scheduler/graph/exporter.py
- core/services/scheduler/graph/metrics.py
- tests/scheduler_graph/test_graph_performance.py
- tests/regression_scheduler_graph_report_mode_contract.py
- tests/regression_scheduler_graph_report_mode_service_contract.py
- tests/regression_scheduler_graph_summary_contract.py
- tests/regression_scheduler_graph_operation_logs_contract.py
- evidence/scheduler_graph/performance_2000_nodes.txt

按需触碰，但不能扩业务语义：
- core/services/scheduler/config/
- web/routes/domains/scheduler/scheduler_config.py
- web/routes/domains/scheduler/scheduler_config_display_state.py

默认不要碰：
- core/services/scheduler/schedule_service.py
- core/services/scheduler/run/schedule_optimizer.py
- core/algorithms/greedy/scheduler.py
- core/algorithms/greedy/dispatch/sgs.py
- core/algorithms/greedy/dispatch/sgs_scoring.py
- core/services/scheduler/graph/ready_queue.py
- core/services/scheduler/graph/scoring.py
```

为什么默认不要碰这些文件：

```text
PR-4 只证明 report 模式稳。
schedule_optimizer.py / GreedyScheduler / SGS / ready_queue / scoring 是排产决策链。
这些文件一动，就很容易从“只读报告”滑到“改变排产候选或评分”。
那是 PR-5 / PR-6 的范围，不属于 PR-4。
```

PR-4 执行顺序：

```text
1. 先补性能测试 tests/scheduler_graph/test_graph_performance.py。
   - 构造 100 个批次，每批 20 道工序。
   - 得到 2000 个节点、1900 条同批次前后置边。
   - 分别记录 build_nodes_ms、build_graph_ms、validate_dag_ms、critical_path_ms、impact_metrics_ms。
   - 跑 3 次取平均，写入 evidence/scheduler_graph/performance_2000_nodes.txt。

2. 明确 PR-4 的 report 默认指标口径。
   - 当前 report 模式默认 metrics_mode="basic"。
   - basic report 必须能写 node_count、edge_count、is_dag、critical_path_minutes、critical_path_node_count、warning_count、cycle_edge_count、time_cost_ms。
   - PR-4 默认不强行计算完整 node_metrics / downstream_critical_minutes。
   - diagnostics 里 node_metrics_count=0 且 node_metrics_status="skipped_basic_report" 是明确合同，不是静默降级。

3. 加固 diagnostics 采样合同。
   - diagnostics.graph_analysis 只能放 sample / count / truncated / status。
   - topological_order、critical_path、cycle_edges、warnings、node_metrics 都必须是采样。
   - warning.data 必须能 json.dumps。
   - 遇到 list / dict 过大要写 count/truncated。
   - 遇到不支持对象要标 unsupported_value_type 或 unsupported_data_type，不能 str() 后伪装成正常数据。
   - 禁止 nodes、edges、raw、完整 topological_order、完整 node_metrics 进入 diagnostics。

4. 加固 known graph error 口径。
   - NetworkXUnavailable -> public.status="unavailable" / reason="networkx_unavailable"。
   - GraphInputContractError -> public.status="input_error" / reason="graph_input_contract_error"。
   - GraphBuildContractError -> public.status="build_error" / reason="graph_build_contract_error"。
   - 这些已知错误只进入 public 顶层小摘要，不写 diagnostics 全量细节。
   - 未知异常继续暴露，不能吞成空报告。

5. 补真实服务级集成证明。
   - 优先沿用 tests/regression_scheduler_graph_report_mode_service_contract.py。
   - 同一套真实服务级案例对比 off / report / on。
   - off 不 import graph 模块，不写 graph_analysis。
   - report 写 graph_analysis，但 rows、summary counts、best_order、selected_batch_ids、freeze_window、resource_pool、seed_results、frozen_op_ids 不变。
   - on 在 PR-4 仍然只输出 effective_mode="report_only"，不能提前进入 ready 队列或评分。
   - 带 frozen/seed 的案例必须断言 total_algo_op_count、reschedulable_unfrozen_op_count、frozen_node_count、seed_result_count 正确。

6. 补 OperationLogs 泄漏检查。
   - OperationLogs 只允许看到 result_summary.algo.graph_analysis 的 public 小摘要。
   - 递归检查没有 diagnostics、nodes、edges、raw、完整 node_metrics、完整 topological_order。

7. 最后再考虑 graph_debug_export。
   - graph_debug_export=no 时不写任何 logs/schedule_graph 文件。
   - graph_debug_export=yes 时只能写普通 JSON 文件，不能写 nx.DiGraph、datetime 原对象、数据库连接、repo、模型原对象或 raw runtime 对象。
   - 测试要用临时目录，不污染真实 logs/。
   - 如果文件名需要 schedule_id / version，必须在 version 已知之后写；不能为了调试文件提前移动 allocate_next_version，也不能把写文件塞进排产决策链或落库事务里。
   - PR-4 不做管理员 HTTP 调试接口，不新增页面按钮。

8. 收尾回填。
   - 更新本 roadmap 和 networkx-scheduler-graph-introduction-items.yaml。
   - 如果开了对应 feature 文档，回填 feature design / checklist / acceptance。
   - PR-4 完成后，PR-5 才能开始有环安全门和 ready 队列。
```

PR-4 的验收命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_graph_performance.py
test -f evidence/scheduler_graph/performance_2000_nodes.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/scheduler_graph/test_exporter.py tests/scheduler_graph/test_analysis_service.py tests/scheduler_graph/test_metrics_critical_path.py tests/scheduler_graph/test_metrics_impact.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/regression_graph_config_bootstrap_contract.py tests/regression_migrate_v9_graph_config_defaults.py tests/regression_scheduler_config_spec_sync_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/graph tests/scheduler_graph tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/graph
```

PR-4 最终提交后，如果要给 clean-worktree proof，再跑：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

注意：

```text
--require-clean-worktree 必须等 PR-4 代码、测试、evidence、roadmap / items.yaml / feature 记录全部提交后再跑。
如果工作区还有未提交文件，不能把它说成 clean-worktree proof。
```

PR-4 明确不做：

```text
[ ] 不实现阶段 11 有环安全门。
[ ] 不实现阶段 12 ready 队列。
[ ] 不实现阶段 13 图评分。
[ ] 不改 schedule_optimizer.py。
[ ] 不改 GreedyScheduler 排产行为。
[ ] 不改 SGS 候选集合。
[ ] 不改 SGS 评分。
[ ] 不改 sorted_ops / batch_order。
[ ] 不改 seed_results / frozen_op_ids 语义。
[ ] 不改 validated_schedule_payload。
[ ] 不改落库 schedule_rows。
[ ] 不让 graph_analysis_mode=on 真正改变排产行为。
[ ] 不把 debug export 当成性能或真实集成证明。
[ ] 不做管理员 debug HTTP 接口。
[ ] 不新增页面按钮。
[ ] 不为了调试导出重排 version 分配、事务或持久化主链。
```

PR-4 的完成口径：

```text
看到性能文件，不代表完成。
看到 debug JSON，不代表完成。
只有性能护栏、diagnostics 采样、known graph error 顶层可见、frozen/seed scope、真实服务级 off/report/on 对比、OperationLogs 不泄漏、配置链路验证和必要 lint/type 检查都通过，才算 PR-4 可以移交 PR-5。
```

PR-4 实际完成记录：

```text
2026-05-18 已完成 PR-4：
- 新增 2000 节点 basic report 性能护栏和 evidence/scheduler_graph/performance_2000_nodes.txt。
- 明确 basic report 不计算完整 node_metrics / downstream_critical_minutes，diagnostics 写 node_metrics_status="skipped_basic_report"。
- diagnostics 增加长 warning message / 长字符串 warning.data 截断合同。
- 真实服务级 off/report/on 对比覆盖普通场景和 frozen/seed 场景，确认 rows、best_order、selected_batch_ids、freeze_window、resource_pool 不变。
- OperationLogs 增加 known graph error 小摘要检查，继续不写 diagnostics 或完整图。
- 本阶段未实现 graph_debug_export；它仍只是后续可选附属能力，不能替代 PR-4 证据。
- 本阶段未实现 PR-5 有环安全门、ready 队列或 PR-6 图评分。
```

PR-5 现在承接这些证据：

```text
PR-5 不能只承接“PR-3 已经有 graph_analysis 字段”。
PR-5 必须承接 PR-4 已经证明的性能、diagnostics、warning 顶层可见性、frozen/seed scope 和真实集成链路，再开始把图 ready 队列接进 SGS 候选集合。
```

### PR-5 总体实现要求

PR-5 是这条路线第一次让图分析真正影响排产候选集合，所以整体要求要比 report 模式更硬：

```text
1. 优雅简洁：
   只围绕“有环安全门”和“ready 资格过滤”做事，不趁机铺评分、候选池、页面、落库或导出大框架。

2. 高内聚：
   graph 模块负责把工序图整理成可用的普通数据。
   run / orchestrator 负责模式判断、错误口径和把图上下文传进 optimizer。
   GreedyScheduler / SGS 只消费 ready 上下文来收集候选，不反向理解 NetworkX。

3. 低耦合：
   NetworkX 图对象、NetworkX 异常、完整 nodes/edges 只能留在 `core/services/scheduler/graph/` 内部。
   `core/algorithms/greedy/` 只能看到普通 Python 结构，例如 op_id、前置 op_id 集合、后继 op_id 集合、已固定 op_id 集合。

4. 不过度兜底：
   `graph_analysis_mode=on` 时，如果图不可用、输入坏、建图坏或有环且 block=yes，必须明确失败或明确禁用图增强。
   不能用“空 ready”“空 graph context”“except Exception”把合同错误藏成旧 SGS 正常结果。

5. 不静默回退：
   只有 `graph_analysis_mode=off/report` 才能自然不接 ready 队列。
   `on + block=no + 有环` 可以继续旧 SGS，但 public 摘要必须写出图增强没有启用。
   `on + DAG` 如果按旧 SGS 跑了，必须是测试能抓出来的错误。

6. 不过度防御性编程：
   对本项目自己生成的字段直接按合同读，字段缺失就让测试失败。
   不写多层 `get(..., default)` 把投影字段缺失伪装成业务分支。

7. PR-5 只交给 PR-6 一个东西：
   “哪些工序现在有资格进入候选集合”。
   PR-5 不证明关键路径工序会更优先，不证明图评分方向，也不改变 SLACK / CR / ATC 等评分语义。
```

## 阶段 11：有环时的处理策略

阶段 11 的定位是“有环安全门”。它不负责实现 ready 队列，也不负责关键路径评分，只负责把阶段 7/9/10 已经能发现的“工序依赖有环”变成清楚、稳定、可测试的运行策略。

大白话说：图里如果出现“20 工序要等 30 工序，30 工序又要等 20 工序”这种绕圈，图算法就不能拿来决定谁先排。report 模式只把问题讲出来，不影响排产；真正进入 on 模式后，要么明确阻止排产，要么明确跳过图增强继续走原排产，不能半推半就地拿一张有问题的图去改 SGS 候选或评分。

### 11.0 阶段目标与前置条件

```text
目标：
  把 graph_analysis_mode / graph_block_on_cycle / is_dag=false 三者的关系写进代码合同。
  明确 report、on + block=yes、on + block=no 三种场景怎么处理。
  给用户可读中文错误或 warning。
  给阶段 12 ready 队列一个明确准入条件：只有可用 DAG 才能进入图 ready 队列。

前置：
  PR-4 已完成 report 模式性能护栏、diagnostics 采样、known graph error 顶层可见、frozen/seed scope 和真实集成证明。
  graph_analysis_public / graph_analysis_diagnostics 已由 maybe_analyze_schedule_graph() 生成。
  analysis_service 已经保证有环时不计算 topological_order、critical_path、node_metrics。

所属实现窗口：
  作为 PR-5 的第一步做。
  先落有环安全门和测试，再开始阶段 12 ready_queue.py。
```

### 11.1 整体实现要求

本阶段必须保持优雅简洁：

```text
1. 高内聚：
   有环决策只收在 graph report / orchestrator 附近的一个小 helper 里。
   graph 模块继续只负责“发现有环并给出分析结果”，不反向 import 排产主链。

2. 低耦合：
   不让 nx.DiGraph、NetworkX 异常、完整 nodes/edges 泄漏到 Controller、页面、数据库或 OperationLogs。
   阶段 12 / 13 只读取“图是否可用于排产”的明确结果，不重新解析 diagnostics。

3. 不过度兜底：
   不写 except Exception 把未知图错误吞成 warning。
   未知错误继续按阶段 10 合同暴露，测试继续锁住。

4. 不静默回退：
   on + block=no 且有环时，可以继续走原排产，但必须写出“图增强已禁用”的可见原因。
   不能悄悄不用图，又让用户以为关键链已经参与了排产。

5. 不过度防御性编程：
   helper 只接收本项目自己生成的 graph_analysis_public / diagnostics。
   对已承诺字段使用明确字段名，不写一堆模糊 get + 默认值把合同错误藏起来。
   如果字段缺失，让测试失败，回头修投影合同。
```

### 11.2 复用已有接口，不新造一套图错误系统

阶段 11 只复用现有接口：

```text
core/services/scheduler/graph/validators.py
  is_dag(graph)
  find_cycle_edges(graph)
  collect_graph_warnings(graph)

core/services/scheduler/graph/analysis_service.py
  ScheduleGraphAnalysisService.analyze_linear_batches(...)

core/services/scheduler/graph/types.py
  GraphWarning
  GraphAnalysisSummary

core/services/scheduler/graph/exporter.py
  graph_summary_to_dict(summary)

core/services/scheduler/run/schedule_graph_report.py
  maybe_analyze_schedule_graph(schedule_input)
```

现状已经成立：

```text
有环时：
  GraphAnalysisSummary.is_dag = False
  GraphAnalysisSummary.cycle_edges 保留环边
  warnings 追加 code="GRAPH_HAS_CYCLE"
  topological_order = []
  critical_path = []
  critical_path_minutes = 0
  node_metrics = {}
```

不要新增：

```text
GraphAnalysisError
GraphAnalysisWarning
新的 cycle detector
新的 warning 投影器
新的完整 graph 导出结构
```

### 11.3 配置和模式矩阵

阶段 11 按下面矩阵执行：

| graph_analysis_mode | graph_block_on_cycle | 图分析结果 | 处理方式 | 是否允许阶段 12 使用图 ready 队列 |
|---|---|---|---|---|
| off | 任意 | 不运行图分析 | 不写 graph_analysis，不加载 graph 模块 | 否 |
| report | no/yes | status=available, is_dag=true | 只写 report 摘要，不改变排产 | 否 |
| report | no/yes | status=available, is_dag=false | 只写 warning / cycle_edges_sample，不阻止排产 | 否 |
| report | no/yes | status!=available | 沿阶段 10 known graph error 顶层 warning，不改变排产 | 否 |
| on | no | status=available, is_dag=true | 图可用于后续 ready 队列 | 是 |
| on | yes | status=available, is_dag=true | 图可用于后续 ready 队列 | 是 |
| on | no | status=available, is_dag=false | 不阻止排产，但必须可见地禁用图增强 | 否 |
| on | yes | status=available, is_dag=false | 阻止排产，抛中文 ValidationError | 否 |
| on | no/yes | status!=available | 不按“有环”处理；沿阶段 10 已知错误口径，后续 on 模式启用前另立合同 | 否 |

注意：

```text
report 模式永远不因为 graph_block_on_cycle=yes 阻止排产。
graph_block_on_cycle 只在 graph_analysis_mode=on 且 status=available 且 is_dag=false 时生效。
status!=available 不是“有环”，不要伪装成 schedule_graph_cycle。
```

### 11.4 接入位置和最小 helper

当前真实接入顺序是：

```text
orchestrate_schedule_run()
  optimize_schedule_fn(...)
  build_validated_schedule_payload(...)
  _merge_summary_warnings(...)
  maybe_analyze_schedule_graph(schedule_input)
  allocate_next_version()
  build_result_summary(...)
  persist_schedule(...)
```

阶段 11 的阻止判断必须放在：

```text
maybe_analyze_schedule_graph(schedule_input)
之后
allocate_next_version()
之前
```

原因：

```text
on + block=yes + 有环时，本次排产不应分配正式 version。
不应写 ScheduleHistory。
不应写 OperationLogs。
不应生成“排产成功但图有环”的历史记录。
```

建议新增小 helper，优先放在 `core/services/scheduler/run/schedule_graph_report.py`：

```python
from typing import Any, Dict, Optional


def ensure_graph_cycle_policy_allows_schedule(
    cfg: Any,
    graph_analysis_public: Optional[Dict[str, Any]],
    graph_analysis_diagnostics: Optional[Dict[str, Any]],
) -> None:
    if graph_analysis_public is None:
        return

    mode = _graph_analysis_mode(cfg)
    block_on_cycle = str(cfg.graph_block_on_cycle).strip().lower() == "yes"

    if mode != "on":
        return
    if graph_analysis_public["status"] != "available":
        return
    if graph_analysis_public["is_dag"] is not False:
        return
    if not block_on_cycle:
        return

    raise _build_graph_cycle_validation_error(
        graph_analysis_diagnostics=graph_analysis_diagnostics,
    )
```

这里的判断只做一件事：`on + block=yes + 可用图分析明确发现有环` 时阻止排产。不要在这个 helper 里处理 ready 队列、评分、debug export、候选方案或资源匹配。

如果后续觉得名字太长，也可以用：

```text
enforce_graph_cycle_policy(...)
```

但不要拆成很多小函数。阶段 11 要的是清楚的安全门，不是新的小框架。

注意阶段 11 和阶段 12 的关系：

```text
阶段 11 单独落安全门时，可以先复用现有 maybe_analyze_schedule_graph() 后置投影，在 allocate_next_version() 前阻止错误历史落库。
但阶段 12 真正接 ready 队列时，不能继续只依赖 optimizer 之后的 report 投影。
PR-5 最终形态必须在 optimize_schedule_fn(...) 之前准备图调度上下文，并把同一份图分析结论继续交给后面的 result_summary 使用，避免前后两次建图口径不一致。
```

### 11.5 cycle_edges 来源和用户可读 details

阶段 10 之后字段边界是：

```text
result_summary["algo"]["graph_analysis"]
  public 小摘要
  有 is_dag / cycle_edge_count
  没有完整 cycle_edges

result_summary["diagnostics"]["graph_analysis"]
  采样诊断
  有 cycle_edges_sample / cycle_edge_count
  有 warnings_sample / warning_count
```

所以阶段 11 不能再写：

```python
graph_analysis["cycle_edges"]
```

应该使用 diagnostics 里的采样：

```python
cycle_edges_sample = graph_analysis_diagnostics["cycle_edges_sample"]
cycle_edge_count = graph_analysis_diagnostics["cycle_edge_count"]
```

用户看到的文案建议：

```text
工序依赖存在循环，无法排产：
B001_20 -> B001_30 -> B001_20
```

错误 details 建议：

```python
exc = ValidationError(
    "工序依赖存在循环，无法排产。请检查工艺路线里前后工序是否互相引用。",
    field="graph_analysis",
)
exc.details = {
    "field": "graph_analysis",
    "reason": "schedule_graph_cycle",
    "cycle_edge_count": cycle_edge_count,
    "cycle_edges_sample": cycle_edges_sample,
}
raise exc
```

`cycle_edges_sample` 只放采样，不放完整图。每条边沿用现有字段：

```text
from
to
from_op_code
to_op_code
kind
```

页面或接口可以用 `from_op_code -> to_op_code` 拼中文提示；如果后续需要更漂亮的路径文案，只做展示层格式化，不回头改 graph 核心结构。

不要只显示英文底层错误：

```text
Graph has cycle
```

### 11.6 report 模式有环口径

report 模式下发现有环时：

```text
不阻止排产。
不改变 rows / best_order / selected_batch_ids / freeze_window / resource_pool / seed_results / frozen_op_ids。
不写 result_summary["errors"]。
不分配新的图增强状态给 SGS。
不调用 ready_queue.py。
不调用 scoring.py。
```

写入结果：

```text
algo.graph_analysis.status = "available"
algo.graph_analysis.is_dag = false
algo.graph_analysis.cycle_edge_count > 0
algo.graph_analysis.warning_count > 0

diagnostics.graph_analysis.cycle_edges_sample 有采样边
diagnostics.graph_analysis.warnings_sample 有 GRAPH_HAS_CYCLE
```

如果要把有环提示放到顶层 `result_summary["warnings"]`，必须满足：

```text
只追加中文 warning。
不追加 errors。
不改变排产状态。
不复制完整 cycle_edges。
```

推荐 warning 文案：

```text
工序图分析发现循环依赖，本次仅记录提示，排产结果未受图分析影响。
```

### 11.7 on + block=yes 阻止排产口径

当同时满足：

```text
graph_analysis_mode=on
graph_block_on_cycle=yes
graph_analysis_public["status"] == "available"
graph_analysis_public["is_dag"] is False
```

必须阻止排产：

```text
抛 ValidationError。
中文 message 直接说明“工序依赖存在循环，无法排产”。
details.reason = "schedule_graph_cycle"。
details.cycle_edges_sample 只放 diagnostics 采样。
在 allocate_next_version() 之前失败。
不写 ScheduleHistory。
不写 OperationLogs。
不落库候选方案。
```

这不是“兜底失败后继续跑”，而是明确的业务校验失败。

### 11.8 on + block=no 可见禁用图增强口径

当同时满足：

```text
graph_analysis_mode=on
graph_block_on_cycle=no
graph_analysis_public["status"] == "available"
graph_analysis_public["is_dag"] is False
```

不阻止排产，但必须明确：

```text
本次图不可用于排产增强。
阶段 12 的 ready 队列不得启用。
阶段 13 的关键路径评分不得启用。
继续使用原 SGS / 原排序 / 原资源匹配。
result_summary 或 graph_analysis public 小摘要里要能看出禁用原因。
```

建议 public 增加：

```python
{
    "graph_enhancement_allowed": False,
    "graph_enhancement_disabled_reason": "schedule_graph_cycle",
    "graph_enhancement_message": "工序图存在循环，本次跳过图增强，继续使用原排产逻辑。",
}
```

无环时建议 public 增加：

```python
{
    "graph_enhancement_allowed": True,
    "graph_enhancement_disabled_reason": None,
}
```

这里的 `graph_enhancement_allowed` 是给阶段 12/13 读的硬合同。阶段 12 不要自己重新判断 `cycle_edges_sample`，只看这个准入结果。

### 11.9 交给阶段 12 的准入合同

阶段 12 开始前必须能回答这个问题：

```text
这次排产能不能让图影响候选集合？
```

唯一允许进入 ready 队列的条件：

```text
graph_analysis_mode=on
graph_analysis_public["status"] == "available"
graph_analysis_public["is_dag"] is True
graph_analysis_public["graph_enhancement_allowed"] is True
```

任何一个条件不满足：

```text
不得调用 get_ready_operations(...)
不得把图 ready 队列接入 SGS 候选集合
不得计算图评分 bonus
不得改变 schedule_rows
```

### 11.10 测试用例

新增或扩展测试时，优先新增一份独立合同测试：

```text
tests/regression_scheduler_graph_cycle_policy_contract.py
```

至少覆盖：

```text
测试 1：report + 有环
  构造或 monkeypatch 出 is_dag=false 的 GraphAnalysisSummary。
  断言不抛 ValidationError。
  断言排产 payload 签名和 off 模式一致。
  断言 algo.graph_analysis.is_dag=false。
  断言 diagnostics.graph_analysis.cycle_edges_sample 有值。
  断言 result_summary["errors"] 为空。

测试 2：report + graph_block_on_cycle=yes + 有环
  断言仍不阻止排产。
  断言 graph_block_on_cycle 不在 report 模式生效。

测试 3：on + block=yes + 有环
  断言抛 ValidationError。
  断言 message 是中文业务文案。
  断言 details.reason == "schedule_graph_cycle"。
  断言 details.cycle_edges_sample 只包含采样边。
  断言 history_repo.allocate_next_version() 没有被调用。
  断言 persist_schedule() 没有被调用。

测试 4：on + block=no + 有环
  断言不阻止排产。
  断言 graph_enhancement_allowed=false。
  断言 graph_enhancement_disabled_reason="schedule_graph_cycle"。
  断言后续 ready 队列准入函数返回 false。

测试 5：on + block=yes + 无环
  断言不阻止。
  断言 graph_enhancement_allowed=true。

测试 6：known graph error
  NetworkXUnavailable / GraphInputContractError / GraphBuildContractError 仍沿阶段 10 合同输出。
  不把这些错误伪装成 schedule_graph_cycle。

测试 7：unknown graph error
  RuntimeError 继续抛出。
  不被 except Exception 吞掉。

测试 8：OperationLogs
  成功场景仍只写 algo.graph_analysis public 小摘要。
  不写 diagnostics.graph_analysis。
  不写完整 cycle_edges / topological_order / node_metrics / nodes / edges / raw。
  阻止场景不写 OperationLogs。
```

图有环的测试构造建议：

```text
图模块单测可以用 build_precedence_graph + 显式反向边构造环。
主链回归测试不要为了造环去改 build_linear_edges_by_batch() 正常规则。
主链可以 monkeypatch ScheduleGraphAnalysisService 或 maybe_analyze_schedule_graph() 返回有环投影。
```

### 11.11 实施顺序

```text
1. 先补红灯测试：report 有环、on+block=yes 有环、on+block=no 有环。
2. 在 schedule_graph_report.py 增加最小有环策略 helper。
3. 在 orchestrate_schedule_run() 的 maybe_analyze_schedule_graph() 后、allocate_next_version() 前调用 helper。
4. 给 public 小摘要补 graph_enhancement_allowed / graph_enhancement_disabled_reason。
5. 补 result_summary 顶层 warning 时，只加中文提示，不写 errors。
6. 补 OperationLogs 合同测试，确认不泄漏 diagnostics 和完整图。
7. 复跑阶段 10 report 合同，确认 report 模式仍不改变排产结果。
8. 再进入阶段 12 ready_queue.py。
```

### 11.12 验收命令

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_cycle_policy_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph/test_analysis_service.py tests/scheduler_graph/test_validators.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/run/schedule_orchestrator.py tests/regression_scheduler_graph_cycle_policy_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/run/schedule_orchestrator.py
```

如果本阶段提交前工作树已经干净，还要跑：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

如果工作树不是干净的，只能如实说这是 targeted proof，不要把它说成 clean-worktree proof。

### 11.13 明确不做

阶段 11 不做：

```text
不实现 ready_queue.py。
不把图 ready 队列接入 SGS。
不实现 graph_score_bonus。
不改变 build_dispatch_key()。
不改变 frozen_op_ids / seed_results 语义。
不改 schedule_rows 生成规则。
不做候选方案表。
不做 graph_debug_export。
不把完整图写入 result_summary。
不把 diagnostics 写入 OperationLogs。
不引入新的 graph 错误类。
不写宽泛 except Exception 兜底。
```

### 11.14 阶段交接话术

阶段 11 完成后，交给阶段 12 的结论必须写清：

```text
当前 on 模式如果图是 DAG，允许进入图 ready 队列。
当前 on 模式如果图有环：
  block=yes 时排产被阻止，用户能看到中文错误和采样环边；
  block=no 时排产继续，但图增强被明确禁用。
report 模式仍然只提示、不改变排产。
未知图错误仍然不被吞掉。
```

## 阶段 12：ready 队列参与排产

这一阶段开始改变排产行为，所以必须在 `graph_analysis_mode=on` 且图已经通过阶段 11 准入之后才启用。

大白话说：report 模式只是“看一眼图，写一段报告”；阶段 12 是“这张图真的决定哪些工序现在能被拿来候选”。所以这里不能靠 optimizer 之后的报告投影硬凑，必须在排产前准备一份给 SGS 用的 ready 上下文。

### 12.0 阶段目标和非目标

目标：

```text
1. 实现 ready 队列 helper，让它能根据前置关系算出当前 ready 工序；当前真实实现放在 `core/algorithms/greedy/dispatch/ready_queue.py`，`core/services/scheduler/graph/ready_queue.py` 只保留兼容导出。
2. 在 optimizer / SGS 之前准备图调度上下文。
3. 把 ready 上下文沿 `optimize_schedule()` -> `GreedyScheduler.schedule()` -> `dispatch_sgs()` 传下去。
4. `graph_analysis_mode=on + DAG` 时，SGS 候选集合来自图 ready 队列。
5. frozen / seed 工序只作为已固定前置，不允许重新进入待排候选。
6. 保持原评分、原资源匹配、原 dispatch key 语义不变。
```

非目标：

```text
不实现 graph_score_bonus。
不接关键路径评分。
不改 build_dispatch_key()。
不改 SLACK / CR / ATC / 批次优先级 / 交期排序含义。
不做候选方案池。
不做候选落库。
不做页面切换。
不做 debug export。
不把 ready_status / ready_date 当成图 ready 队列。
```

### 12.1 整体实现要求

阶段 12 的代码要求和 PR-5 总要求一致，执行时按下面口径落到 feature design：

```text
1. ready_queue.py 保持纯净：
   可以接收普通 Python 映射、集合、列表。
   不在模块导入时 import NetworkX。
   不 import orchestrator、optimizer、GreedyScheduler 或 SGS。

2. graph 预处理保持高内聚：
   从 schedule_input.algo_ops + batches + resource_pool + frozen_op_ids 构建图。
   只在 `core/services/scheduler/graph/` 内部接触 nx.DiGraph。
   输出给排产链的是普通上下文，不是图对象。

3. SGS 保持低耦合：
   dispatch_sgs() 只多接一个可选 graph_ready_context。
   没有 graph_ready_context 时，旧 `_collect_sgs_candidates()` 路径完全不变。
   有 graph_ready_context 时，只替换“候选资格集合”，不替换评分、资源匹配和实际派工。

4. 不静默回退：
   `graph_analysis_mode=on + DAG` 时，graph_ready_context 必须存在并生效。
   如果 context 丢了、字段缺了、op_id 映射不上，应该失败并被测试抓住，不能悄悄走旧 SGS。

5. 不过度兜底：
   ready 为空不自动回旧 SGS。
   如果图已经声明 DAG，但调度过程中出现无 ready 且仍有未排工序，这是合同错误，应抛清楚的 ValidationError。
```

### 12.2 当前仓库事实和必须修正的误区

当前 report 图分析位置是：

```text
core/services/scheduler/run/schedule_orchestrator.py
  optimize_schedule_fn(...)
  build_validated_schedule_payload(...)
  maybe_analyze_schedule_graph(schedule_input)
```

这个位置对 report 模式是对的，因为 report 只需要看最终输入并写摘要。但它对 ready 队列不够早，因为 SGS 候选集合已经在 `optimize_schedule_fn(...)` 里算完了。

PR-5 必须改成下面这个目标顺序：

```text
orchestrate_schedule_run()
  prepare_schedule_graph_for_dispatch(schedule_input)
    -> graph_analysis_public
    -> graph_analysis_diagnostics
    -> graph_ready_context 或 None
  optimize_schedule_fn(..., graph_ready_context=graph_ready_context)
  build_validated_schedule_payload(...)
  allocate_next_version()
  build_result_summary(..., graph_analysis_public, graph_analysis_diagnostics)
  persist_schedule(...)
```

这样做的目的：

```text
1. SGS 能在排产前拿到 ready 上下文。
2. result_summary 继续使用同一份图分析结果，不重复建图、不前后口径漂移。
3. on + block=yes + 有环可以在 optimizer 前失败，不浪费一次排产尝试，也不产生半成品。
```

当前 SGS 候选收集在：

```text
core/algorithms/greedy/dispatch/sgs_scoring.py
  _collect_sgs_candidates(...)
```

现有语义是：

```text
每个批次只拿 next_idx 指向的下一道工序。
```

这不是完整 DAG ready 队列。PR-5 不能把旧 `next_idx` 说成图 ready；也不能一刀切删掉它。正确口径是：

```text
graph_ready_context is None:
  继续使用旧 `_collect_sgs_candidates()`。

graph_ready_context 存在:
  从图 ready 上下文取本轮可候选 op_id。
  再映射回 `(batch_id, op)` 交给现有 `_score_candidates()`。
  `_score_candidates()`、`_score_candidate()`、`_dispatch_selected()` 继续沿用原逻辑。
```

### 12.3 图调度上下文合同

建议新增一个小的准备入口，优先放在 `core/services/scheduler/run/schedule_graph_report.py` 或同目录很窄的 helper 文件里；如果 `schedule_graph_report.py` 继续变大，再拆成 `core/services/scheduler/run/schedule_graph_dispatch.py`。

建议名字：

```text
prepare_schedule_graph_for_dispatch(schedule_input)
```

返回值建议是一个小 dataclass，字段只放 PR-5 必需内容：

```python
@dataclass(frozen=True)
class ScheduleGraphDispatchPreparation:
    graph_analysis_public: Optional[Dict[str, Any]]
    graph_analysis_diagnostics: Optional[Dict[str, Any]]
    graph_ready_context: Optional[Any]
```

`graph_ready_context` 只能包含普通 Python 数据，建议字段：

```text
enabled: bool
disabled_reason: Optional[str]
schedulable_op_ids: Set[int]
fixed_op_ids: Set[int]
predecessor_op_ids_by_op_id: Dict[int, Set[int]]
successor_op_ids_by_op_id: Dict[int, Set[int]]
```

说明：

```text
schedulable_op_ids 只来自 schedule_input.algo_ops_to_schedule。
fixed_op_ids 来自 frozen_op_ids / seed_results 对应的 op_id。
predecessor_op_ids_by_op_id 可以包含 fixed_op_ids，因为固定工序能释放后继。
successor_op_ids_by_op_id 用于排成功后释放后续工序。
不要把 node_id 当成算法层主键；算法层继续按 op_id 找工序对象。
不要把 nx.DiGraph 放进 graph_ready_context。
```

如果实现时确实需要排序稳定性，ready 队列返回结果按下面顺序排序：

```text
batch_order
seq
op_id
```

这样能保证同一批数据多次运行候选顺序稳定，也方便测试。

### 12.4 on 模式准入矩阵

阶段 12 开始后，`on` 模式不能再长期停在 `effective_mode="report_only"`。按下面矩阵执行：

| graph_analysis_mode | 图分析结果 | graph_block_on_cycle | graph_ready_context | 排产行为 |
|---|---|---|---|---|
| off | 不运行 | 任意 | None | 完全旧排产，不写 graph_analysis |
| report | available / unavailable / input_error / build_error | 任意 | None | 只写报告，不改变排产 |
| on | available + is_dag=true + graph_enhancement_allowed=true | no/yes | 必须存在 | SGS 使用图 ready 队列 |
| on | available + is_dag=false | yes | None | optimizer 前抛 ValidationError，不分配 version |
| on | available + is_dag=false | no | None | 继续旧 SGS，但 public 明确写图增强禁用原因 |
| on | unavailable / input_error / build_error | no/yes | None | 抛中文 ValidationError，不允许静默走旧 SGS |

最后一行是阶段 11 “后续 on 模式启用前另立合同”的补齐口径。原因很简单：PR-5 之后 `on` 已经代表“图 ready 队列要参与排产”，如果 NetworkX 不可用或图输入坏了还悄悄走旧 SGS，用户会以为关键链已经参与，实际没有参与。

建议错误 reason：

```text
graph_enhancement_unavailable
graph_input_contract_error
graph_build_contract_error
schedule_graph_cycle
```

建议 public 字段：

```python
{
    "effective_mode": "graph_ready_queue",
    "graph_enhancement_allowed": True,
    "graph_enhancement_disabled_reason": None,
    "ready_queue_enabled": True,
}
```

有环且 block=no 时：

```python
{
    "effective_mode": "sgs_without_graph_ready_queue",
    "graph_enhancement_allowed": False,
    "graph_enhancement_disabled_reason": "schedule_graph_cycle",
    "ready_queue_enabled": False,
    "graph_enhancement_message": "工序图存在循环，本次跳过图 ready 队列，继续使用原 SGS 候选逻辑。",
}
```

### 12.5 ready_queue.py 的职责

当前真实实现放在 `core/algorithms/greedy/dispatch/ready_queue.py`，`core/services/scheduler/graph/ready_queue.py` 只做兼容导出，避免算法层反向依赖 scheduler service。这个 helper 不是新的调度器。

建议职责：

```text
1. 根据 predecessor 映射和 completed/fixed op_id，算当前 ready op_id。
2. 排除已经 scheduled、failed_blocked、not_schedulable 的 op_id。
3. 按稳定 key 排序 ready op_id。
4. 提供 mark_scheduled(op_id) 或返回新集合的纯函数式更新方式。
```

建议核心函数形态：

```python
def get_ready_operation_ids(
    *,
    schedulable_op_ids: Iterable[int],
    completed_or_fixed_op_ids: Iterable[int],
    blocked_op_ids: Iterable[int],
    predecessor_op_ids_by_op_id: Mapping[int, Set[int]],
    sort_key_by_op_id: Mapping[int, Tuple[int, int, int]],
) -> List[int]:
    ...
```

实现要求：

```text
不接收 nx.DiGraph。
不读 cfg。
不读数据库。
不读 schedule_input。
不调 estimate_internal_slot。
不调 _score_candidate。
不判断 graph_analysis_mode。
只做“哪些 op_id ready”这一个问题。
```

### 12.6 SGS 接入方式

`dispatch_sgs()` 增加可选参数：

```python
graph_ready_context: Optional[Any] = None
```

传递链路必须覆盖：

```text
core/services/scheduler/run/schedule_orchestrator.py
  optimize_schedule_fn(..., graph_ready_context=...)

core/services/scheduler/run/schedule_optimizer.py
  optimize_schedule(..., graph_ready_context=...)

core/services/scheduler/run/schedule_optimizer_steps.py
  _schedule_with_optional_strict_mode(..., graph_ready_context=...)
  _run_multi_start(..., graph_ready_context=...)
  _run_ortools_warmstart(..., graph_ready_context=...)

core/services/scheduler/run/optimizer_local_search.py
  run_local_search(..., graph_ready_context=...)

core/algorithms/greedy/scheduler.py
  GreedyScheduler.schedule(..., graph_ready_context=...)

core/algorithms/greedy/dispatch/sgs.py
  dispatch_sgs(..., graph_ready_context=...)
```

SGS 内部规则：

```text
graph_ready_context is None:
  原 `_collect_sgs_candidates()` 保持不变。

graph_ready_context 存在:
  不再按“每个 batch 下一道工序”收候选。
  每轮从 ready_context 拿 ready_op_ids。
  ready_op_ids 映射回当前 ops_by_batch 里的 op。
  映射不到说明上下文和待排集合不一致，应抛 ValidationError 或合同错误，不静默忽略。
  评分仍走 `_score_candidates()`。
  排成功后把 op_id 加入 completed/scheduled，再释放后继。
  排失败并 block 时，不释放后继工序。
```

不要改的地方：

```text
_score_external_candidate()
_score_internal_candidate()
_dispatch_key()
build_dispatch_key()
estimate_internal_slot()
auto_assign_resources()
```

### 12.7 frozen / seed 边界

这是 PR-5 最容易出错的地方，必须写成测试：

```text
图输入：schedule_input.algo_ops，包含 frozen 节点和待排节点。
待排候选：只能来自 schedule_input.algo_ops_to_schedule。
已固定前置：frozen_op_ids / seed_results 对应 op_id。
```

规则：

```text
固定节点可以让后继工序变 ready。
固定节点不能进入 schedulable_op_ids。
固定节点不能出现在 SGS candidates。
固定节点不能再次写入新的 schedule_rows。
固定节点的资源占用继续沿用现有 seed_results 逻辑，不在 ready_queue.py 里重算资源。
```

如果 frozen_op_ids 里有一个 op_id，但图输入没有对应节点：

```text
不在 ready_queue.py 里兜底补节点。
由 graph input adapter / preparation 阶段暴露合同错误或 warning。
```

### 12.8 测试用例

新增或扩展：

```text
tests/scheduler_graph/test_ready_queue.py
tests/regression_scheduler_graph_on_mode_contract.py
```

ready_queue.py 单测至少覆盖：

```text
测试 1：线性 A -> B -> C
  done = {}
  ready = [A]

测试 2：A 完成后释放 B
  done = {A}
  ready = [B]

测试 3：A、B 完成后释放 C
  done = {A, B}
  ready = [C]

测试 4：输入顺序反过来
  输入 C, B, A，依赖 A -> B -> C。
  ready 输出仍按 batch_order / seq / op_id 稳定排序。

测试 5：分叉
  A -> B, A -> C。
  done = {A}
  ready = [B, C]，顺序稳定。

测试 6：汇合
  A -> C, B -> C。
  done = {A}
  C 不 ready。
  done = {A, B}
  C ready。

测试 7：冻结窗口
  A -> B -> C。
  A 已在 frozen_op_ids / seed_results。
  schedulable = {B, C}
  fixed = {A}
  ready = [B]。
  A 不能出现在 ready。

测试 8：失败不释放后继
  A 派工失败且 batch 被 block。
  B 仍不 ready。

测试 9：坏 op_id 映射
  predecessor 里出现 schedulable 集合外且 fixed 集合外的 op_id。
  抛清楚的合同错误，不能忽略。
```

主链回归至少覆盖：

```text
测试 1：off 模式
  不准备 graph_ready_context。
  不 import graph 模块。
  schedule_rows / best_order / selected_batch_ids 与旧口径一致。

测试 2：report 模式
  只写 graph_analysis。
  不调用 ready_queue。
  不改变 schedule_rows。

测试 3：on + DAG
  graph_ready_context 被传进 dispatch_sgs。
  SGS 候选不违反前后置。
  后工序不会排到前工序之前。
  public.effective_mode="graph_ready_queue"。

测试 4：on + cycle + block=yes
  optimizer 前抛 ValidationError。
  不调用 allocate_next_version。
  不调用 persist_schedule。

测试 5：on + cycle + block=no
  不启用 ready_queue。
  继续旧 SGS。
  public.effective_mode="sgs_without_graph_ready_queue"。
  public.graph_enhancement_disabled_reason="schedule_graph_cycle"。

测试 6：on + graph unavailable / input_error / build_error
  抛中文 ValidationError。
  不能静默走旧 SGS。

测试 7：frozen/seed
  frozen 工序释放后继。
  frozen 工序不进入 candidates。
  frozen 工序不重复写 schedule_rows。

测试 8：无 graph context 的 SGS
  `_collect_sgs_candidates()` 旧行为保持。
  `tests/test_sgs_internal_scoring_matches_execution.py` 和 `tests/test_sgs_total_hours_cache.py` 继续通过。
```

### 12.9 实施顺序

按下面顺序做，避免先改 SGS 后发现安全门没定：

```text
1. 先补阶段 11 cycle policy 测试，并让红灯说明当前 on+cycle 没有安全门。
2. 落阶段 11 helper 和 orchestrator 调用，确保 on+block=yes 不分配 version。
3. 在 `ready_queue.py` 写纯函数 ready 计算和单测。
4. 新增 graph dispatch preparation：构建图、产出 public/diagnostics、产出 plain graph_ready_context。
5. 把 orchestrator 改为 optimizer 前准备图上下文，后续 summary 复用同一份 public/diagnostics。
6. 沿 optimizer / scheduler / dispatch_sgs 传递 graph_ready_context。
7. 只在 dispatch_sgs 候选收集处接 graph_ready_context，其余评分和派工函数不改。
8. 补 on 模式主链回归，证明 DAG 才启用 ready 队列，有环或图错误不会静默回退。
9. 复跑 PR-3 / PR-4 report 合同，证明 off/report 仍不改变排产。
10. 回填 feature / roadmap / items.yaml，写清 PR-6 只能继承 ready 资格，不能继承评分证明。
```

### 12.10 验收命令

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_cycle_policy_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph/test_ready_queue.py tests/regression_scheduler_graph_on_mode_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sgs_internal_scoring_matches_execution.py tests/test_sgs_total_hours_cache.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/run/schedule_optimizer.py core/services/scheduler/run/schedule_optimizer_steps.py core/services/scheduler/run/optimizer_local_search.py core/services/scheduler/graph/ready_queue.py core/algorithms/greedy/scheduler.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py tests/regression_scheduler_graph_cycle_policy_contract.py tests/scheduler_graph/test_ready_queue.py tests/regression_scheduler_graph_on_mode_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/run/schedule_graph_report.py core/services/scheduler/run/schedule_orchestrator.py core/services/scheduler/run/schedule_optimizer.py core/services/scheduler/run/schedule_optimizer_steps.py core/services/scheduler/run/optimizer_local_search.py core/services/scheduler/graph/ready_queue.py core/algorithms/greedy/scheduler.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml --yaml-only
```

如果 PR-5 代码、测试、feature 文档、roadmap 和 items.yaml 都已经提交，工作树干净后再跑：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

如果工作树不是干净的，只能说 targeted proof 通过，不能说 clean-worktree proof。

### 12.11 阶段完成口径

阶段 12 完成后必须能对 PR-6 说清：

```text
PR-5 已证明：
  DAG 可用时，SGS 候选集合来自图 ready 队列。
  ready 队列不违反前后置。
  frozen / seed 工序不会重复排。
  off / report 不改变排产结果。
  on + 有环 / 图不可用不会静默伪装成图增强成功。

PR-5 未证明：
  关键路径工序更优先。
  graph_score_bonus 方向正确。
  SLACK / CR / ATC 和图分数如何合并。
  多权重候选试跑、自动择优、候选落库或页面切换。
```

## 阶段 13：PR-6 关键路径评分接入

PR-6 是第一个真正把图分析结果放进 SGS 候选评分的 PR。大白话说，PR-5 已经做到“只从前置工序都完成的 ready 工序里挑候选”，PR-6 才开始决定“这些 ready 候选里，关键路径更重、影响后续更多、后续关键工作量更大的工序是否应该更靠前”。

PR-6 只能继承 PR-5 已经证明的 ready 资格：

```text
可以继承：
  on + DAG 时，SGS 候选集合已经由 graph_ready_context 筛过。
  ready 队列不会放出前置未完成的工序。
  frozen / seed 工序只作为已固定前置，不会重复进入候选。
  有环 / 图不可用 / 图输入错误不会被伪装成图增强成功。

不能继承：
  关键路径工序一定更优先。
  graph_score_bonus 方向正确。
  SLACK / CR / ATC 和图分数合并后仍符合原语义。
  多权重候选试跑、自动择优、候选落库或页面切换。
```

### PR-6.1 总体目标

PR-6 只做一件事：在 `graph_analysis_mode=on`、图是 DAG、`graph_enhancement_allowed=true` 时，把图指标转成 SGS 候选排序里的一个可解释分量。

这一步做完后，系统应该能说清：

```text
1. 哪个工序因为在关键路径上而被提前。
2. 哪个工序因为影响更多后续工序而被提前。
3. 哪个工序因为后续关键工作量更大而被提前。
4. 这个提前只发生在 on + DAG + 图增强允许的 SGS 候选评分里。
5. off / report / on 但图增强未允许时，仍按 PR-5 或更早的旧逻辑排。
```

### PR-6.2 整体实现要求

PR-6 的实现要求写死在计划里，后续 feature-design 和代码实现都要按这里验：

```text
优雅简洁：
  只在图模块算图分数，只在 SGS 候选评分拼接图分量。
  不把图评分逻辑散落到 orchestrator、optimizer、页面、数据库或持久化里。

不做过度兜底：
  on 模式需要图评分却拿不到 node_metrics 时，不允许悄悄当 0 分继续。
  权重为 0 是用户配置出来的真实含义；缺字段、坏字段不是 0，必须暴露为合同错误。

不做静默回退：
  on + graph_enhancement_allowed=true 时，评分上下文缺失、op_id 对不上、指标字段缺失，都不能假装回到旧评分。
  如果业务决定本次不能启用图评分，必须在 public 小摘要里写清 disabled reason，而不是让用户以为图增强生效。

不做过度防御性编程：
  不到处铺宽泛 try/except。
  不写“能转就转、转不了给默认值”的宽松解析。
  只在边界入口校验一次合同，内部使用清楚的普通 Python 结构。

高内聚低耦合：
  core/services/scheduler/graph/scoring.py 只负责图分数纯计算。
  core/services/scheduler/run/schedule_graph_report.py 只负责把图分析结果准备成普通 Python 调度上下文。
  core/algorithms/greedy/dispatch/sgs.py 只负责把上下文传到候选评分。
  core/algorithms/greedy/dispatch/sgs_scoring.py 只负责把图分量拼进现有排序 key。
  core/algorithms/dispatch_rules.py 继续负责原 SLACK / CR / ATC key，不把 NetworkX 或 graph DTO 引进去。
```

### PR-6.3 明确不做

下面这些都不是 PR-6 范围，后续不要顺手做：

```text
1. 不做 PR-7 的多权重候选试跑。
2. 不做自动择优。
3. 不新增候选表、候选仓库、候选落库事务。
4. 不改 schema.sql。
5. 不新增页面按钮、甘特图切换、周计划切换或导出切换。
6. 不把 nx.DiGraph、完整 node_metrics、完整关键路径、完整拓扑序写进 Controller、页面、数据库、Excel 或 OperationLogs。
7. 不绕过 build_dispatch_key() 直接改 batch_order、best_order、selected_batch_ids 或最终落库 rows。
8. 不让 report 模式改变排产结果。
9. 不把 graph_critical_weight / graph_impact_weight 之外的新配置临时塞成环境变量。
```

### PR-6.4 当前仓库接入点

PR-6 实施前先复核这些真实入口，不能按旧草图凭感觉改：

```text
core/services/scheduler/run/schedule_graph_report.py
  _build_schedule_graph_analysis_projection()
  _build_graph_ready_context()
  _project_graph_analysis_payload()

core/services/scheduler/graph/analysis_service.py
  ScheduleGraphAnalysisService.analyze_linear_batches(metrics_mode="basic" / "full")

core/services/scheduler/graph/metrics.py
  build_node_metrics()
  get_critical_path()
  get_impact_count()
  get_downstream_critical_minutes()

core/services/scheduler/graph/scoring.py
  PR-6 新增图评分纯函数。

core/algorithms/greedy/dispatch/sgs.py
  dispatch_sgs()
  _score_candidates()
  _score_candidate()
  _prepare_graph_ready_state()

core/algorithms/greedy/dispatch/sgs_scoring.py
  _dispatch_key()
  _score_external_candidate()
  _score_internal_candidate()

core/algorithms/dispatch_rules.py
  build_dispatch_key()
```

当前 `build_dispatch_key()` 的排序合同是“tuple 越小越优先”。PR-6 不能把这个方向改掉；图分数越大越重要时，放进排序 key 之前必须转成“越小越靠前”的图排序分量。

### PR-6.5 图指标准备合同

当前 report 链路为了性能护栏使用：

```python
summary = ScheduleGraphAnalysisService().analyze_linear_batches(nodes, metrics_mode="basic")
```

`basic` 只算公开小摘要，不算完整 `node_metrics`。PR-6 要求：

```text
1. off 模式仍然不 import graph 模块，不准备图指标。
2. report 模式继续使用 basic，不为了评分去计算完整 node_metrics，不改变排产结果。
3. on + DAG + graph_enhancement_allowed=true 时，才允许计算 full node_metrics。
4. on + 有环 / 图不可用 / 图输入错误 / graph_enhancement_allowed=false 时，不准备图评分上下文。
5. full node_metrics 只转成普通 Python 调度上下文，不把 nx.DiGraph 或 GraphAnalysisSummary 原对象传到 SGS。
```

建议把 `graph_ready_context` 扩成同一个高内聚的普通 dict，而不是再造一条平行上下文：

```python
{
    "enabled": True,
    "disabled_reason": None,
    "schedulable_op_ids": set(...),
    "fixed_op_ids": set(...),
    "predecessor_op_ids_by_op_id": {...},
    "successor_op_ids_by_op_id": {...},
    "sort_key_by_op_id": {...},
    "score_enabled": True,
    "score_weights": {
        "critical_weight": 500,
        "impact_weight": 10,
        "downstream_minutes_weight": 1,
    },
    "node_metrics_by_op_id": {
        101: {
            "is_on_critical_path": True,
            "critical_path_rank": 0,
            "impact_count": 3,
            "downstream_critical_minutes": 120,
        },
    },
}
```

字段要求：

```text
schedulable_op_ids：
  只能包含本次真正要排的 op_id。

fixed_op_ids：
  frozen_op_ids + seed_results 的 op_id，只作为已固定前置。

node_metrics_by_op_id：
  key 必须是正整数 op_id。
  value 必须包含 is_on_critical_path、critical_path_rank、impact_count、downstream_critical_minutes。
  只允许包含 schedulable_op_ids 或 fixed_op_ids 能解释的节点。
  对本次 schedulable_op_ids 中每个候选必须有指标。

score_enabled：
  只有 on + DAG + graph_enhancement_allowed=true + full node_metrics 准备完成时才是 True。
```

如果 `score_enabled=True`，但 `node_metrics_by_op_id` 缺候选指标，应该报合同错误，不能把缺指标当 0 分。

### PR-6.6 新建 graph/scoring.py 纯函数

`core/services/scheduler/graph/scoring.py` 只放图评分纯函数，不读数据库、不读配置、不 import NetworkX、不接触排产状态。

建议接口：

```python
from __future__ import annotations

from typing import Any, Dict, Tuple


class GraphScoringContractError(ValueError):
    pass


def graph_score_bonus(
    node_metric: Dict[str, Any],
    *,
    critical_weight: int,
    impact_weight: int,
    downstream_minutes_weight: int = 1,
) -> int:
    ...


def graph_priority_key_component(
    node_metric: Dict[str, Any],
    *,
    critical_weight: int,
    impact_weight: int,
    downstream_minutes_weight: int = 1,
) -> Tuple[float, ...]:
    ...
```

字段校验要求：

```text
is_on_critical_path：
  必须存在，必须是 bool。

critical_path_rank：
  可以是 None；如果不是 None，必须是非负整数。

impact_count：
  必须存在，必须是非负整数。

downstream_critical_minutes：
  必须存在，必须是非负整数。

critical_weight / impact_weight / downstream_minutes_weight：
  必须是非负整数。
  0 表示该分量不参与评分，是正常配置。
```

计算建议：

```text
graph_score_bonus 越大，表示越应该提前。

bonus =
  is_on_critical_path ? critical_weight : 0
  + impact_count * impact_weight
  + downstream_critical_minutes * downstream_minutes_weight

graph_priority_key_component 返回 (-bonus, critical_path_rank_or_large_number)
```

为什么要返回负数：当前 SGS 用 `min()` 挑 tuple，tuple 越小越优先。图 bonus 越大越重要，所以要变成负数才能排到更前。

为什么带 `critical_path_rank`：两个候选 bonus 一样时，关键路径上更靠前的节点应更早释放后续工序。非关键路径节点用一个稳定大数放后面。

### PR-6.7 SGS 接入规则

PR-6 只允许在 SGS 候选评分里加图分量：

```text
1. _prepare_graph_ready_state() 负责校验 graph_ready_context 基本合同。
2. 校验通过后，把 node_metrics_by_op_id、score_weights、score_enabled 放进 graph_state。
3. _score_candidates() 把 graph_state 传给 _score_candidate()。
4. _score_candidate() 根据 op.id 取 node_metric。
5. _score_external_candidate() 和 _score_internal_candidate() 继续产出旧 base_key。
6. 只在 base_key 外层拼接 graph_priority_key_component。
7. 没有 graph_state 时，旧评分 key 完全不变。
```

推荐拼接位置：

```python
base_key = _score_internal_candidate(...)
if graph_score_enabled:
    graph_key = graph_priority_key_component(...)
    return tuple(graph_key) + tuple(base_key)
return base_key
```

这样做的含义是：在已经被 ready 队列放出的候选里，先看图关键程度，再看原 SLACK / CR / ATC。PR-6 必须用测试证明这不会让前置未完成的工序被放进候选，因为候选资格仍由 PR-5 ready 队列控制。

如果评审认为图分量不应该压过原规则，可以改成：

```python
return (base_key[0],) + tuple(graph_key) + tuple(base_key[1:])
```

但只能选一种，并用 `tests/regression_scheduler_graph_on_mode_contract.py` 证明方向。不能在代码里做“有时放前面、有时放后面”的隐式策略。

### PR-6.8 配置和页面说明同步

PR-6 不新增配置项，只让已有配置真正生效：

```text
graph_critical_weight
graph_impact_weight
```

需要同步检查：

```text
core/services/scheduler/config/config_field_spec.py
core/services/scheduler/config/config_snapshot.py
core/models/schedule_config_runtime_fields.py
templates/scheduler/config.html
web/viewmodels/scheduler_config_panel.py
```

当前这些字段如果还写着“预留、不改变排产结果”，PR-6 要改成业务用户能看懂的话：

```text
关键路径权重：
  graph_analysis_mode=on 且工序图可用时，关键路径上的工序会更靠前。

影响范围权重：
  graph_analysis_mode=on 且工序图可用时，影响更多后续工序的工序会更靠前。
```

不要新增环境变量，不要新增隐藏配置，不要在页面上做 PR7 的候选方案开关。

### PR-6.9 result_summary 和 OperationLogs 口径

PR-6 可以在公开小摘要里补“图评分是否启用”的小字段，但不能塞完整指标：

```text
允许放进 result_summary["algo"]["graph_analysis"]：
  score_enabled: true / false
  score_weight_summary: {"critical_weight": 500, "impact_weight": 10}
  score_metric_status: "available" / "disabled" / "unavailable"
  score_disabled_reason: None 或短字符串

允许放进 result_summary["diagnostics"]["graph_analysis"]：
  少量 graph_score_sample，例如前 10 个 node 的 op_id、bonus、is_on_critical_path、impact_count。
  graph_score_sample_count / graph_score_sample_truncated。

禁止：
  完整 node_metrics。
  完整 topological_order。
  完整 critical_path。
  完整 edges / nodes / raw graph。
  nx.DiGraph 或 GraphAnalysisSummary 原对象。
```

OperationLogs 继续只吃公开小摘要，不吃 diagnostics。PR-6 如果要让日志能看出“本次图评分生效”，只能通过 `algo.graph_analysis.score_enabled` 这类小字段体现。

### PR-6.10 测试用例清单

必须新增或扩展：

```text
tests/scheduler_graph/test_graph_scoring.py
  - critical_path=True 时 bonus 增加 critical_weight。
  - impact_count 按 impact_weight 增加。
  - downstream_critical_minutes 按 downstream_minutes_weight 增加。
  - 权重为 0 时该分量不参与评分。
  - 缺 is_on_critical_path / impact_count / downstream_critical_minutes 抛 GraphScoringContractError。
  - impact_count / downstream_critical_minutes 为负数抛 GraphScoringContractError。
  - graph_priority_key_component 返回值方向为“bonus 越大，tuple 越小”。

tests/regression_scheduler_graph_on_mode_contract.py
  - on + DAG + graph_enhancement_allowed=true 时，关键路径候选排在同条件非关键候选前。
  - on + DAG 下，impact_count 更大的同条件候选更靠前。
  - on + DAG 下，downstream_critical_minutes 更大的同条件候选更靠前。
  - graph_critical_weight=0 且 graph_impact_weight=0 时，结果等价 PR-5 ready 队列行为。
  - on + cycle + block=no 时，ready 队列和图评分都不启用，public 写明 disabled reason。
  - on + graph unavailable / input_error / build_error 时，不伪装成 score_enabled=true。

tests/test_sgs_internal_scoring_matches_execution.py
  - 内部工序评分明细和实际执行顺序仍一致。
  - 图分量接入后，测试不要只断言旧 key，要断言新 key 和执行选择一致。

tests/test_sgs_total_hours_cache.py
  - total_hours_by_op_id 缓存仍被内部候选评分复用，图评分不能破坏原性能缓存。

tests/regression_scheduler_graph_summary_contract.py
  - public 只新增 score_enabled / score_metric_status 等小字段。
  - diagnostics 只有采样，不出现完整 node_metrics。

tests/regression_scheduler_graph_operation_logs_contract.py
  - OperationLogs 不出现 diagnostics、完整 node_metrics、nodes、edges、raw graph。

tests/regression_scheduler_config_spec_sync_contract.py
tests/regression_scheduler_config_route_contract.py
  - 配置说明文字和字段规格仍同步。
```

三种 dispatch rule 都要覆盖：

```text
SLACK：
  原 slack 越小越优先的方向不反。

CR：
  原 cr 越小越优先的方向不反。

ATC：
  原 atc 已通过负值变成 tuple 越小越优先，PR-6 不再二次反向。
```

### PR-6.11 最小业务样例

构造两个同等候选：

```text
批次 A：A1(10) -> A2(10)
批次 B：B1(10) -> B2(100) -> B3(10)
```

前置条件：

```text
A1 和 B1 都已经 ready。
A1 和 B1 同优先级、同交期、同来源、同状态。
设备和人员都可用。
dispatch_rule 分别用 SLACK / CR / ATC 跑。
graph_analysis_mode=on。
graph_critical_weight > 0 或 graph_impact_weight > 0。
```

期望：

```text
B1 比 A1 更靠前。
原因是 B1 的后续关键工作量更长，或 impact_count / downstream_critical_minutes 更大。
```

同时要构造反例：

```text
graph_analysis_mode=report 时，A1 / B1 顺序仍由旧规则决定。
graph_critical_weight=0 且 graph_impact_weight=0 时，on 模式不应因为空图权重改变旧顺序。
```

### PR-6.12 实施顺序

按下面顺序执行，不要跳：

```text
1. 只读复核 PR-5 现状：
   - graph_ready_context 当前字段。
   - schedule_graph_report.py 里 basic/full metrics_mode 位置。
   - SGS 当前评分 key 形状。

2. 新增 tests/scheduler_graph/test_graph_scoring.py：
   - 先写纯函数测试，锁定 bonus 方向和坏字段报错。

3. 实现 core/services/scheduler/graph/scoring.py：
   - 只做纯函数。
   - 不 import NetworkX。
   - 不读配置、不读数据库、不接日志。

4. 扩展 graph_ready_context：
   - 只在 on + DAG + graph_enhancement_allowed=true 时计算 full node_metrics。
   - 把 node_metrics 转成 node_metrics_by_op_id。
   - 校验 schedulable_op_ids 都能找到指标。

5. 接 SGS 评分：
   - _prepare_graph_ready_state 校验 score 字段。
   - _score_candidates / _score_candidate 传入 graph_state。
   - 在旧 base_key 外拼 graph_priority_key_component。

6. 同步配置说明：
   - 把“预留、不改变排产结果”改成“on 模式图评分生效”。
   - 不新增配置项。

7. 补 summary / OperationLogs 合同：
   - public 小字段说明 score 是否启用。
   - diagnostics 只采样。

8. 跑 PR-6 targeted proof：
   - 先跑新增图评分测试。
   - 再跑 on/report/ready/SGS 回归。
   - 最后跑 ruff、pyright、items.yaml 校验。

9. 回填 CodeStable：
   - 创建或更新 feature 记录。
   - items.yaml 的 PR-6 status 在 acceptance 时再从 planned 改 done。
   - roadmap 变更记录写清 PR-6 已证明什么、没证明什么。
```

### PR-6.13 验收命令

PR-6 至少跑：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/scheduler_graph/test_graph_scoring.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_on_mode_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_cycle_policy_contract.py tests/scheduler_graph/test_ready_queue.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_graph_report_mode_contract.py tests/regression_scheduler_graph_report_mode_service_contract.py tests/regression_scheduler_graph_summary_contract.py tests/regression_scheduler_graph_operation_logs_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_sgs_internal_scoring_matches_execution.py tests/test_sgs_total_hours_cache.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_scheduler_config_spec_sync_contract.py tests/regression_scheduler_config_route_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/regression_mirror_template_sync.py tests/regression_config_field_spec_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold tests/test_architecture_fitness.py::test_file_size_limit tests/test_architecture_fitness.py::test_greedy_refactor_files_stay_under_quality_gate_limits tests/test_greedy_refactor_contracts.py::test_refactored_files_and_entry_functions_stay_under_quality_gate
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ruff check core/services/scheduler/graph/scoring.py core/services/scheduler/run/schedule_graph_report.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py core/algorithms/dispatch_rules.py tests/scheduler_graph/test_graph_scoring.py tests/regression_scheduler_graph_on_mode_contract.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright core/services/scheduler/graph/scoring.py core/services/scheduler/run/schedule_graph_report.py core/algorithms/greedy/dispatch/sgs.py core/algorithms/greedy/dispatch/sgs_scoring.py core/algorithms/dispatch_rules.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml --yaml-only
```

如果要对外说 clean-worktree proof，还必须在本地提交后、工作区干净时跑：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --require-clean-worktree
```

如果工作树不干净，只能说 PR-6 targeted proof 通过，不能说 clean-worktree proof。

### PR-6.14 完成口径

PR-6 完成后必须能对 PR-7 说清：

```text
PR-6 已证明：
  on + DAG + 图增强允许时，SGS ready 候选会按图关键程度参与排序。
  图分数方向经过测试，bonus 越大越靠前。
  graph_critical_weight / graph_impact_weight 为 0 时可回到 PR-5 ready 队列行为。
  SLACK / CR / ATC 原排序合同没有被改反。
  report / off / on 但图增强未允许时不改变排产结果。
  summary 和 OperationLogs 只暴露小摘要，不泄漏完整图数据。

PR-6 未证明：
  多权重候选哪一档最好。
  自动择优能稳定选 adopted。
  候选摘要、候选明细、代表方案切换和同事务落库。
  页面切换最终采用 / 原算法最好 / 关键链最好。
```

## 阶段 13.6：PR-7 多权重候选试跑、自动择优和代表方案对比

阶段 13.6 是用户已经确认要做的“真正可用形态”。它不只是把关键路径分数塞进一次排产，而是让系统自动多跑几套候选，再把最合适的一套展示给用户。

本阶段从 2026-05-18 起采用 **强一致优先方案**。大白话说，就是系统如果承诺“我比较了多套方案”，那数据库、页面、导出、历史记录就必须一起说同一件事，不能出现“正式排产成功了，但候选对比丢了、页面打不开另一套方案”的半成品状态。

#### 13.6.1 强一致总原则

PR-7 实现前先把下面这些原则写死，后续代码和测试都按这里走：

```text
1. 同一个正式 version 只代表一次排产。
2. Schedule 只保存最终采用方案，也就是 adopted。
3. ScheduleCandidate 保存所有候选摘要。
4. ScheduleCandidateRows 只保存非 adopted 的代表方案明细。
5. ScheduleCandidateSelection 把 adopted / baseline_best / critical_best 映射到候选。
6. adopted 的明细永远从 Schedule 读，不在 ScheduleCandidateRows 里重复保存。
7. 所有页面、接口、导出通过统一 SchedulePlanQueryService 按 plan_role 读取。
8. 正式排产、ScheduleHistory、候选摘要、代表明细、角色映射必须同事务落库。
9. 候选落库失败时，整次正式排产回滚，不写“正式成功但候选丢失”的历史。
10. OperationLogs 只写候选对比极小摘要，不复制完整 result_summary.algo。
```

不能采用的做法：

```text
不能把最终采用、原算法最好、关键链最好三套明细都塞进 Schedule 同一个 version。
不能为了保存候选方案，偷偷新增多个正式 version，让用户误以为自己排了多次。
不能先把正式 Schedule 落库成功，再在后面单独写候选；第一版不走候选失败 degraded 的路线。
不能只保存 result_summary 摘要，因为用户后面没法打开另一套方案的甘特图、周计划、资源派工和报表。
```

#### 13.6.2 候选方案生成

第一版候选方案池：

```text
候选 0：baseline，原算法，不加关键链权重。
候选 1-N：critical_chain，关键链权重候选，默认 5 档。
```

权重档数：

```text
默认 5 档。
允许高级设置改成 3 / 5 / 7。
每档具体权重由系统生成，不让普通用户填写每个权重值。
不使用随机数，同一套配置每次生成的候选 key 和权重都一致。
```

第一版只变化关键链权重：

```text
冻结用户当前选择的排序规则。
冻结用户当前选择的派工模式。
冻结用户当前选择的派工规则。
不把所有排序规则、派工模式、派工规则和关键链权重做笛卡尔积试跑。
```

这条非常重要：当前 `optimize_schedule()` 在 `algo_mode == "improve"` 时会扩展多排序策略、多派工模式。PR-7 候选试跑必须新增 `candidate_trial_mode=True` 或等价的单候选模式，让候选比较只比较“关键链权重”，不要把现有 improve 的多起点搜索混进来。

#### 13.6.3 运行顺序和全局时间预算

运行顺序必须保证有兜底：

```text
1. baseline 永远第一个启动。
2. baseline 完成后，再按系统预设顺序跑关键链权重候选。
3. time_budget_seconds / run_time_budget_seconds 是整次候选比较的总预算，不是每个候选各用一次。
4. 每个候选启动前检查整次 deadline 的剩余时间。
5. 达到 deadline 后，不再启动新的候选。
6. 已经完成的候选参与择优。
7. 未启动的候选标 skipped / not_run，不能伪装成 completed。
8. 已经启动的候选第一版允许自然完成，不做强杀。
```

运行期时间上限：

```text
长期默认值继续来自高级设置 time_budget_seconds。
排产执行前新增 run_time_budget_seconds，只影响本次排产，不写回 ScheduleConfig。
run_time_budget_seconds 为空时使用长期默认值。
run_time_budget_seconds 必须 >= 1。
result_summary.algo.candidate_comparison 记录本次实际使用的 run_time_budget_seconds。
```

页面和摘要需要记录：

```text
planned_candidate_count
completed_candidate_count
time_budget_reached
skipped_candidate_labels
baseline_missing_or_failed
```

提示文案示例：

```text
本次时间到了，只比较了 3/6 套方案，已采用已完成方案里的最好结果。想比较完整，可以提高本次时间上限后重新排产。
```

第一版不做续跑；续跑放到 PR-10 / 后续增强。

#### 13.6.4 候选失败规则

失败要分类，不要把所有异常都吞成“某个候选失败”：

```text
输入错误 / 配置错误 / 数据范围错误：
  终止整次排产，不写 Schedule / ScheduleHistory / Candidate 表。

baseline 调度执行失败：
  记录 baseline failed。
  继续跑关键链候选。
  不允许 balanced 用“关键链更健康”来反超。
  只能从 completed 候选里按 raw score 选择。
  result_summary 标记 baseline_missing_or_failed。

单个关键链候选执行失败：
  记录 failed + failure_reason。
  继续后续候选。

全部候选都 failed / skipped / not_run：
  整次排产失败，不写正式历史，不写候选表。
```

#### 13.6.5 自动择优规则

先复用当前系统已有评分，不新做一套完全独立的评分体系：

```text
raw_score = (failed_ops,) + objective_score(objective_name, metrics)
score tuple 越小越好。
```

`objective_score()` 里如果当前目标用到了换型次数等已有字段，就继续沿用当前逻辑；PR-7 不在 roadmap 里重新定义一套目标函数。候选摘要和页面核心展示统一使用当前仓库已有小时字段：

```text
overdue_count
total_tardiness_hours
weighted_tardiness_hours
makespan_hours
failed_ops
```

如果页面要显示分钟，只能在展示层换算，内部择优和 summary 合同统一使用小时口径，不能同时混用分钟口径和小时口径。

自动择优策略：

```text
score_only：
  直接采用 raw_score_best。

balanced：
  先找 raw_score_best。
  再找 critical_best。
  只有关键链健康明显更好，且没有明显牺牲超期和拖期，critical_best 才能反超。
```

balanced 允许关键链反超的硬条件：

```text
1. critical_best 存在且 completed。
2. baseline_best 存在且 completed。
3. critical_best.failed_ops <= raw_score_best.failed_ops。
4. critical_best.overdue_count <= raw_score_best.overdue_count + graph_overdue_tolerance_count。
5. critical_best.total_tardiness_hours <= raw_score_best.total_tardiness_hours * (1 + graph_tardiness_tolerance_ratio)。
6. critical_best.critical_chain_health.state == "better"。
```

如果不满足：

```text
采用 raw_score_best。
如果 raw_score_best 是 baseline，页面提示“已比较关键链方案，本次原算法更优”。
如果 raw_score_best 是关键链，页面提示“本次关键链方案评分排名更好”。
```

选择原因内部枚举：

```text
raw_score_best
score_only_raw_score_best
balanced_critical_health_better
baseline_failed_raw_score_best
critical_failed_baseline_adopted
failed_ops_worse_rejected
overdue_tolerance_exceeded
tardiness_tolerance_exceeded
critical_health_not_better
```

页面文案从枚举映射，不在业务逻辑里到处拼长中文。

#### 13.6.6 关键链健康计算

关键链健康必须是落库前的纯函数，不能依赖已经写入数据库的甘特图关键链分析：

```python
compute_candidate_health(
    baseline_results,
    critical_results,
    graph_metrics,
    impact_ops,
) -> Dict[str, Any]
```

内部状态建议用英文枚举，页面翻译成中文：

```text
better：更健康
same：差不多
worse：更差
unavailable：指标不足
```

第一版健康指标统一使用小时：

```text
critical_chain_finish_hours_delta
critical_chain_wait_hours_delta
top_impact_ops_avg_start_hours_delta
critical_chain_slack_hours_delta
```

评分口径：

```text
critical_chain_finish 更早 5% 以上：+1。
critical_chain_wait 减少 5% 以上：+1。
top impact 工序平均开始更早：+1。
critical_chain_finish 更晚 5% 以上：-1。
critical_chain_wait 增加 5% 以上：-1。
总分 >= 2：better。
总分 <= -2：worse。
其他：same。
```

指标不足时：

```text
state = "unavailable"
页面展示“关键链健康指标不足，未作为反超依据”
balanced 不允许用 unavailable 反超 raw_score_best
```

甘特图当前的关键链高亮缓存也要同步改造。缓存 key 不能只按 version，必须带上 `plan_role / source_table / candidate_id`，否则用户切方案后可能看到上一套方案的关键链高亮。

#### 13.6.7 数据库表设计

PR-7 新增一次迁移，例如 `core/infrastructure/migrations/v10.py`，同时更新迁移注册和 `core/infrastructure/migration_state.py` 里的当前 schema 版本。迁移只新增候选对比表、索引、约束和 PR-7 配置默认值，不改旧历史语义。

新增表 1：`ScheduleCandidate`

```sql
CREATE TABLE IF NOT EXISTS ScheduleCandidate (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    version               INTEGER NOT NULL,
    candidate_key         TEXT NOT NULL,
    candidate_label       TEXT NOT NULL,
    candidate_kind        TEXT NOT NULL CHECK(candidate_kind IN ('baseline', 'critical_chain')),
    status                TEXT NOT NULL CHECK(status IN ('completed', 'failed', 'skipped', 'not_run')),
    graph_enabled         TEXT NOT NULL DEFAULT 'no' CHECK(graph_enabled IN ('yes', 'no')),
    weight_level          INTEGER,
    weight_count          INTEGER,
    critical_weight       INTEGER,
    impact_weight         INTEGER,
    downstream_weight     INTEGER,
    sort_strategy         TEXT,
    dispatch_mode         TEXT,
    dispatch_rule         TEXT,
    objective             TEXT,
    score_json            TEXT,
    metrics_json          TEXT,
    health_json           TEXT,
    summary_json          TEXT,
    selection_reason      TEXT,
    failure_reason        TEXT,
    detail_saved          TEXT NOT NULL DEFAULT 'no' CHECK(detail_saved IN ('yes', 'no')),
    elapsed_ms            INTEGER,
    started_at            DATETIME,
    finished_at           DATETIME,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(version, candidate_key),
    UNIQUE(id, version)
);
```

字段大白话说明：

```text
candidate_key：稳定内部编号，例如 baseline、graph_w1_of_5。
candidate_label：页面显示名，例如“原算法”“关键链 3/5”。
candidate_kind：baseline / critical_chain。
status：只表示运行状态，不能包含 adopted。
graph_enabled：这套候选有没有关键链参与。
score_json：当前系统评分 tuple，越小越好。
metrics_json：failed_ops、overdue_count、total_tardiness_hours、weighted_tardiness_hours、makespan_hours 等核心指标。
health_json：关键链健康状态和支撑指标。
summary_json：页面候选表需要的小摘要。
detail_saved：这套候选有没有保存完整排产明细。
```

新增表 2：`ScheduleCandidateRows`

```sql
CREATE TABLE IF NOT EXISTS ScheduleCandidateRows (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    version          INTEGER NOT NULL,
    candidate_id     INTEGER NOT NULL,
    op_id            INTEGER NOT NULL,
    machine_id       TEXT,
    operator_id      TEXT,
    start_time       DATETIME NOT NULL,
    end_time         DATETIME NOT NULL,
    lock_status      TEXT DEFAULT 'unlocked',
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(candidate_id, version) REFERENCES ScheduleCandidate(id, version) ON DELETE CASCADE,
    UNIQUE(candidate_id, op_id)
);
```

新增表 3：`ScheduleCandidateSelection`

```sql
CREATE TABLE IF NOT EXISTS ScheduleCandidateSelection (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    version         INTEGER NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('adopted', 'baseline_best', 'critical_best')),
    candidate_id    INTEGER NOT NULL,
    source_table    TEXT NOT NULL CHECK(source_table IN ('schedule', 'candidate_rows')),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(candidate_id, version) REFERENCES ScheduleCandidate(id, version) ON DELETE CASCADE,
    UNIQUE(version, role)
);
```

`source_table` 规则：

```text
adopted：
  source_table = schedule
  明细从 Schedule 读
  不写 ScheduleCandidateRows

baseline_best / critical_best：
  如果指向 adopted 同一个 candidate：
      source_table = schedule
      不写重复 rows
  如果不是 adopted：
      source_table = candidate_rows
      写 ScheduleCandidateRows
```

索引：

```sql
CREATE INDEX IF NOT EXISTS idx_schedule_candidate_version
ON ScheduleCandidate(version);

CREATE INDEX IF NOT EXISTS idx_schedule_candidate_version_kind
ON ScheduleCandidate(version, candidate_kind);

CREATE INDEX IF NOT EXISTS idx_schedule_candidate_rows_version_candidate
ON ScheduleCandidateRows(version, candidate_id);

CREATE INDEX IF NOT EXISTS idx_schedule_candidate_rows_time
ON ScheduleCandidateRows(start_time, end_time);

CREATE INDEX IF NOT EXISTS idx_schedule_candidate_selection_version
ON ScheduleCandidateSelection(version);
```

不要把 `ScheduleCandidate.version` 外键到 `ScheduleHistory(version)`。当前 `ScheduleHistory.version` 不是唯一键，候选数据的主约束先以 `version + candidate_key` 和同事务落库保证一致。

#### 13.6.8 持久化和主链接入顺序

当前 `persist_schedule()` 自己开事务。PR-7 要先拆成可复用的事务内核心函数，再增加总入口：

```text
build_schedule_rows_for_persistence(...)
persist_schedule_core_in_tx(...)
persist_candidate_comparison_core_in_tx(...)
persist_schedule_run_with_candidates(...)
```

PR-7 主链顺序固定为：

```text
collect_schedule_run_input()
run_candidate_comparison()              # 只在内存里跑，不写 DB
select_candidate_plan()                  # 选 adopted / baseline_best / critical_best
build_validated_schedule_payload(adopted.results)
maybe_analyze_schedule_graph()
allocate_next_version()
build_result_summary(candidate_comparison 小摘要)
persist_schedule_run_with_candidates()   # Schedule + ScheduleHistory + Candidate 表同事务写入
write_operation_log_small_summary()      # 事务后写极小日志
```

同事务里写入顺序：

```text
1. 写 Schedule adopted rows。
2. 正式排产时更新 BatchOperations / Batches 状态；simulate=True 不更新状态。
3. 写 ScheduleHistory。
4. 写 ScheduleCandidate 所有候选摘要，并拿到 candidate_id map。
5. 对 baseline_best / critical_best 里非 adopted 的代表方案写 ScheduleCandidateRows。
6. 写 ScheduleCandidateSelection 三个角色。
```

硬性要求：

```text
候选运行阶段禁止写 DB。
Schedule / ScheduleHistory / ScheduleCandidate / ScheduleCandidateRows / ScheduleCandidateSelection 必须同事务写入。
候选对比持久化失败时，整次正式排产回滚。
OperationLogs 在事务后写，并且只写极小摘要。
bulk_create_candidates 不要依赖 executemany 的 lastrowid；要么逐条插入拿 id，要么插入后按 (version, candidate_key) 查回 id map。
```

#### 13.6.9 result_summary 和 OperationLogs 合同

`result_summary["algo"]["candidate_comparison"]` 只放小摘要：

```json
{
  "enabled": true,
  "planned_candidate_count": 6,
  "completed_candidate_count": 4,
  "time_budget_reached": true,
  "skipped_candidate_labels": ["关键链 4/5", "关键链 5/5"],
  "run_time_budget_seconds": 120,
  "adopted_candidate_key": "graph_w2_of_5",
  "baseline_best_candidate_key": "baseline",
  "critical_best_candidate_key": "graph_w2_of_5",
  "raw_score_best_candidate_key": "baseline",
  "selection_policy": "balanced",
  "selection_reason_code": "balanced_critical_health_better",
  "selection_reason": "评分接近，关键链健康更好",
  "baseline_missing_or_failed": false,
  "candidates": []
}
```

`candidates` 里每条只放小字段：

```json
{
  "candidate_key": "graph_w2_of_5",
  "label": "关键链 2/5",
  "kind": "critical_chain",
  "status": "completed",
  "score": [0, 2, 12.5, 18.0],
  "metrics": {
    "failed_ops": 0,
    "overdue_count": 2,
    "total_tardiness_hours": 12.5,
    "weighted_tardiness_hours": 18.0,
    "makespan_hours": 70.0
  },
  "critical_chain_health": {
    "state": "better",
    "label": "更健康",
    "reason": "关键链等待更少，高影响工序更早开始"
  },
  "detail_saved": true,
  "roles": ["adopted", "critical_best"]
}
```

禁止进入 summary：

```text
ScheduleResult rows
完整 nodes
完整 edges
raw graph
完整 node_metrics
完整 attempts 超长列表
```

当前 `_log_schedule_operation()` 会直接放入 `result_summary_obj.get("algo")`。PR-7 必须改成只写极小摘要：

```json
{
  "algo": {
    "mode": "improve",
    "objective": "due_date",
    "candidate_comparison": {
      "enabled": true,
      "planned_candidate_count": 6,
      "completed_candidate_count": 4,
      "time_budget_reached": true,
      "adopted_candidate_key": "graph_w2_of_5",
      "selection_policy": "balanced",
      "selection_reason_code": "balanced_critical_health_better"
    }
  }
}
```

OperationLogs 不写 candidates 列表，不写 candidate rows，不写 nodes / edges / raw graph。

#### 13.6.10 统一方案查询服务

新增：

```text
core/services/scheduler/schedule_plan_query_service.py
data/repositories/schedule_plan_query_repo.py
```

`SchedulePlanResolution` 返回结构：

```python
SchedulePlanResolution(
    version: int,
    requested_role: str,
    selected_role: str,
    source_table: str,
    candidate_id: Optional[int],
    candidate_key: Optional[str],
    status: str,
    message: str,
    available_roles: List[SchedulePlanRoleOption],
)
```

服务入口：

```python
resolve_plan(version: int, role: Optional[str]) -> SchedulePlanResolution
list_plan_roles(version: int) -> List[SchedulePlanRoleOption]
get_plan_time_span(version: int, role: Optional[str])
list_plan_detail_rows_between(version: int, role: Optional[str], start_time, end_time)
list_plan_detail_rows_all(version: int, role: Optional[str])
list_plan_dispatch_rows(version: int, role: Optional[str], start_time, end_time, scope_type, scope_id)
list_plan_report_rows(version: int, role: Optional[str], report_type: str, filters: Dict[str, Any])
```

解析规则：

```text
role 为空：
  role = adopted

没有 ScheduleCandidateSelection：
  requested_role 是 adopted：正常读 Schedule。
  requested_role 不是 adopted：fallback_to_adopted，提示“当前版本没有候选对比，已显示最终采用方案”。

有 Selection，但 requested_role 不存在：
  fallback_to_adopted，提示“本次没有保存这套方案明细，已显示最终采用方案”。

role 存在：
  source_table=schedule：读 Schedule。
  source_table=candidate_rows：读 ScheduleCandidateRows。
```

`schedule_detail_query.py` 不能继续写死 `FROM Schedule s`。推荐改成统一 plan rows CTE：

```sql
WITH plan_rows AS (
    SELECT id AS schedule_id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version
    FROM Schedule
    WHERE version = ?

    -- 或 candidate rows:
    SELECT id AS schedule_id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version
    FROM ScheduleCandidateRows
    WHERE version = ? AND candidate_id = ?
)
SELECT ...
FROM plan_rows s
LEFT JOIN BatchOperations bo ON bo.id = s.op_id
...
```

这样甘特图、周计划、资源派工和报表都能读同一套字段，不需要每个页面各自复制 SQL。

#### 13.6.11 页面、接口、导出范围

统一 query 参数：

```text
plan_role=adopted
plan_role=baseline_best
plan_role=critical_best
```

必须接入 `plan_role` 的页面、接口和导出：

```text
甘特图页面和 /scheduler/gantt/data
周计划页面和周计划导出
资源派工页面、data 接口和导出
优化分析页
超期分析独立报表
利用率分析独立报表
停机影响分析独立报表
相关报表导出和操作日志 filters
```

当前仓库事实：超期、利用率、停机影响不只是 `analysis.html` 里的小区块，它们在 `web/routes/reports.py` 里有独立入口，报表服务也按正式 version 查数据。PR-7d 不能只写“analysis 页覆盖”，必须把 `web/routes/reports.py`、`core/services/report/report_engine.py` 和相关 viewmodel / export 一起列入计划。

页面控件：

```text
在版本选择附近增加“查看方案”下拉。
选项文案固定为：最终采用 / 原算法最好 / 关键链最好。
当前版本没有候选对比时，不显示该下拉。
某个角色没有明细时，该选项置灰或隐藏，并显示“本次没有保存这套方案明细”。
非 adopted 页面明确提示“当前查看的是对比方案，不是本次正式采用结果”。
```

链接保留规则：

```text
甘特图设备/人员切换保留 plan_role。
甘特图上周/下周/日期范围保留 plan_role。
甘特图 JS 请求 /gantt/data 必须带 plan_role。
周计划查询和导出保留 plan_role。
资源派工查询、data 和导出保留 plan_role。
报表页面和导出保留 plan_role。
优化分析页跳甘特图、周计划、资源派工时带 version + plan_role。
系统历史里的旧链接默认不带 plan_role，相当于打开 adopted。
```

导出口径：

```text
页面预览和导出必须读同一个 plan_role。
导出文件名或 Excel 摘要要标明“最终采用 / 原算法最好 / 关键链最好”。
导出日志 filters 记录 requested_plan_role 和 effective_plan_role。
```

#### 13.6.12 配置字段和页面设置

PR-7 需要补齐这些长期配置字段：

```text
graph_candidate_weight_count
graph_selection_policy
graph_overdue_tolerance_count
graph_tardiness_tolerance_ratio
```

默认值：

```text
graph_candidate_weight_count = 5
graph_selection_policy = balanced
graph_overdue_tolerance_count = 1
graph_tardiness_tolerance_ratio = 0.10
```

可选值：

```text
graph_candidate_weight_count：3 / 5 / 7
graph_selection_policy：balanced / score_only
graph_overdue_tolerance_count：0 / 1 / 2
graph_tardiness_tolerance_ratio：0.05 / 0.10 / 0.20
```

必须同步的位置：

```text
core/services/scheduler/config/config_field_spec.py
core/services/scheduler/config/config_snapshot.py
core/services/scheduler/config/config_constants.py
core/models/schedule_config_runtime_fields.py
core/models/schedule_config_runtime_snapshot.py
web/routes/domains/scheduler/scheduler_config.py
web/routes/domains/scheduler/scheduler_config_display_state.py
web/viewmodels/scheduler_config_panel.py
templates/scheduler/config.html
core/services/scheduler/config/config_presets.py
core/services/scheduler/config/config_preset_service.py
```

默认开启口径：

```text
新库默认 graph_analysis_mode=on。
旧库如果用户已有 graph_analysis_mode，不覆盖。
旧库没有该配置时，迁移插入 on。
开发、灰度和排障仍可手动切 off / report。
页面文案要从“只读报告”改成“关键链默认参与排产，可切 off/report 排障”。
```

旧 preset 处理：

```text
历史 preset JSON 缺少 PR-7 新字段时，迁移或应用 preset 前补默认值。
补字段不能覆盖用户已经保存过的值。
不能因为老 preset 缺字段就拒绝应用整套配置。
```

#### 13.6.13 权重档位生成规则

第一版权重必须稳定、可复现，不使用随机数。

基准值来自配置：

```text
base_critical_weight = graph_critical_weight
base_impact_weight = graph_impact_weight
base_downstream_weight = 1
```

档位倍数：

```text
3 档：0.50 / 1.00 / 1.50
5 档：0.50 / 0.75 / 1.00 / 1.25 / 1.50
7 档：0.40 / 0.60 / 0.80 / 1.00 / 1.20 / 1.40 / 1.60
```

取整规则：

```text
critical_weight = round(base_critical_weight * multiplier)
impact_weight = round(base_impact_weight * multiplier)
downstream_weight = round(base_downstream_weight * multiplier)
关键链候选的 downstream_weight 最小为 1
baseline 的 three weights 全部为 0
```

候选 key 示例：

```text
baseline
graph_w1_of_5
graph_w2_of_5
graph_w3_of_5
graph_w4_of_5
graph_w5_of_5
```

#### 13.6.14 内部值对象和 Python 3.8 语法

新增内部值对象，使用 Python 3.8 写法：

```python
@dataclass(frozen=True)
class CandidateRunSpec:
    candidate_key: str
    label: str
    kind: str
    graph_enabled: bool
    weight_level: Optional[int]
    weight_count: Optional[int]
    critical_weight: int
    impact_weight: int
    downstream_weight: int


@dataclass
class CandidatePlan:
    spec: CandidateRunSpec
    status: str
    results: List[ScheduleResult]
    summary: Any
    metrics: Optional[ScheduleMetrics]
    score: Tuple[float, ...]
    health: Dict[str, Any]
    elapsed_ms: int
    failure_reason: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]


@dataclass
class CandidateComparisonOutcome:
    candidates: List[CandidatePlan]
    planned_count: int
    completed_count: int
    time_budget_reached: bool
    skipped_candidate_labels: List[str]
```

语法边界：

```text
用 List[str]，不要用 list[str]。
用 Optional[str]，不要用 str | None。
用了 Any 必须 import Any。
不引入 NumPy / SciPy / Pandas。
不引入新数据库驱动。
不引入外部 CDN 前端资源。
```

#### 13.6.15 清理策略

候选明细可能比正式 Schedule 大，PR-7 要同时补清理策略：

```text
保留最近 N 个 ScheduleHistory version 的候选数据。
N 默认跟现有排产历史保留策略一致。
删除旧 ScheduleCandidate 时通过 FK cascade 删除 rows / selection。
删除旧候选不能删除正式 ScheduleHistory。
旧 version 没候选数据时，页面不显示方案切换，直接 adopted。
```

#### 13.6.16 PR-7 拆分

PR-7 不要一次把数据库、算法、页面、导出全揉在一起，拆成 5 个小 PR：

```text
PR-7a：数据库、仓库、查询服务
  schema、迁移、候选仓库、plan query repo、schedule_detail_query CTE、SchedulePlanQueryService。

PR-7b：候选生成、运行、择优、健康纯逻辑
  CandidateRunSpec、CandidatePlan、候选 runner、candidate_trial_mode、global deadline、score_only / balanced、health。

PR-7c：主链和同事务持久化
  orchestrator 接入、persist_schedule 拆分、persist_schedule_run_with_candidates、summary 小摘要、OperationLogs 极小摘要。

PR-7d：页面、接口、导出、报表 plan_role 切换
  甘特、周计划、资源派工、优化分析、独立报表、导出、前端链接和 JS 请求。

PR-7e：配置、临时时间上限、清理策略、Win7/Python 3.8/性能收口
  配置链路、run_time_budget_seconds、旧 preset、清理策略、性能证据、Python 3.8 语法门禁。
```

#### 13.6.17 测试清单

PR-7 至少新增或补齐这些测试：

```text
tests/regression_scheduler_candidate_schema_contract.py
  - 三张候选表、索引、CHECK、UNIQUE、cascade、生效。
  - 旧 ScheduleHistory 没候选数据时不影响旧页面。

tests/regression_scheduler_candidate_generation_contract.py
  - 默认 baseline + 5 个 critical_chain。
  - 3 / 5 / 7 档稳定生成。
  - baseline 永远第一个。
  - 候选 key 稳定，不使用随机数。

tests/regression_scheduler_candidate_runner_contract.py
  - baseline 先跑。
  - 全局 deadline 到达后后续 skipped。
  - 单个关键链候选失败后续继续。
  - baseline 调度失败后仍可从 completed 候选 raw score 选择。
  - 输入错误 / 配置错误终止整次排产。
  - candidate_trial_mode 不扩展 sort_strategy / dispatch_mode / dispatch_rule。
  - run_time_budget_seconds 只影响本次，不写回配置。

tests/regression_scheduler_graph_auto_selection_contract.py
  - score_only 采用 raw_score_best。
  - balanced 在容差内且关键链更健康时采用 critical_best。
  - failed_ops / overdue_count / total_tardiness_hours 变差时不能反超。
  - baseline failed 时不允许 balanced 反超。
  - score tuple 越小越好。

tests/regression_scheduler_candidate_health_contract.py
  - finish 更早、wait 减少、top impact 更早 => better。
  - finish 更晚、wait 增加 => worse。
  - 指标不足 => unavailable，不能作为反超依据。
  - 指标单位统一使用 hours。

tests/regression_scheduler_candidate_persistence_contract.py
  - Schedule 只保存 adopted。
  - ScheduleCandidate 保存所有候选摘要。
  - ScheduleCandidateRows 只保存非 adopted 的代表候选明细。
  - adopted / baseline_best / critical_best selection 正确。
  - 候选持久化失败时 Schedule / ScheduleHistory / Candidate 全部回滚。
  - OperationLogs 在事务后写，且不包含 candidate rows。

tests/regression_scheduler_candidate_plan_query_contract.py
  - resolve_plan(None/adopted) 读 Schedule。
  - baseline_best / critical_best 按 source_table 读 candidate rows。
  - 缺失角色 fallback adopted 并返回 message。
  - get_plan_time_span 按当前 plan_role 算。
  - candidate rows join BatchOperations / Batches / Machines / Operators 字段完整。
  - critical chain cache key 包含 plan_role / candidate_id。

tests/regression_scheduler_candidate_gantt_plan_role_contract.py
  - 页面下拉选中当前 plan_role。
  - /gantt/data 带 plan_role 读对应 rows。
  - 设备/人员视图、上周/下周、日期范围保留 plan_role。
  - 非 adopted 显示对比方案提示。

tests/regression_scheduler_candidate_week_plan_contract.py
  - 页面预览和导出读同一 plan_role。
  - 导出日志 filters 记录 plan_role。
  - 非 adopted 文件名或摘要标明对比方案。

tests/regression_scheduler_candidate_resource_dispatch_contract.py
  - 页面、data、export 都保留 plan_role。
  - operator / machine / team scope 过滤 candidate rows 正确。
  - 导出日志 filters 记录 plan_role。

tests/regression_scheduler_candidate_reports_contract.py
  - 超期、利用率、停机影响独立报表按 plan_role 读数据。
  - 报表导出和日志记录 requested/effective plan_role。
  - 缺失角色 fallback adopted。

tests/regression_scheduler_candidate_analysis_contract.py
  - analysis 页显示 candidate_comparison 表。
  - adopted / baseline_best / critical_best 角色标签正确。
  - 跳甘特 / 周计划 / 资源派工带 version + plan_role。

tests/regression_scheduler_candidate_summary_contract.py
  - result_summary.algo.candidate_comparison 只有小摘要。
  - metrics 字段使用小时口径字段，不使用分钟口径字段。
  - OperationLogs 只有极小摘要，不包含 candidates 列表和 rows。

tests/regression_scheduler_candidate_config_contract.py
  - 新库默认 graph_analysis_mode=on。
  - 旧库已有 off 时迁移不覆盖。
  - 新配置字段默认值、可选值、snapshot、页面保存、旧 preset 补字段正确。

tests/regression_scheduler_candidate_py38_contract.py
  - 新代码不出现 list[str] / str | None。
  - 不引入重依赖、新数据库驱动、外部 CDN。

tests/regression_scheduler_candidate_performance_guard.py
  - 1000 条 adopted rows 和 1000 条 candidate rows 查询性能可接受。
  - list_plan_roles 不扫描 CandidateRows 明细。
  - get_plan_time_span 使用索引。
```

回归必须继续通过：

```text
tests/regression_scheduler_graph_on_mode_contract.py
tests/regression_scheduler_graph_summary_contract.py
tests/test_sgs_internal_scoring_matches_execution.py
tests/test_sgs_total_hours_cache.py
```

#### 13.6.18 阶段验收清单

```text
[ ] graph_analysis_mode=on 时默认启用候选对比。
[ ] baseline 永远先跑。
[ ] 默认生成 5 档关键链候选。
[ ] 档数可配置为 3 / 5 / 7。
[ ] time_budget_seconds / run_time_budget_seconds 是整次候选比较总预算。
[ ] 候选试跑冻结当前 sort_strategy / dispatch_mode / dispatch_rule。
[ ] result_summary 写 planned_candidate_count / completed_candidate_count / time_budget_reached。
[ ] 自动择优复用当前 objective_score，score tuple 越小越好。
[ ] balanced 规则按 failed_ops、overdue_count、total_tardiness_hours、关键链健康共同判断。
[ ] Schedule 只写最终采用方案。
[ ] ScheduleCandidate 保存所有候选摘要。
[ ] ScheduleCandidateRows 只写非 adopted 的代表方案明细。
[ ] ScheduleCandidateSelection 正确映射 adopted / baseline_best / critical_best。
[ ] Schedule / ScheduleHistory / Candidate 表同事务落库，候选持久化失败会整体回滚。
[ ] OperationLogs 只写候选对比极小摘要。
[ ] 甘特图、周计划、资源派工、优化分析页都能切换代表方案。
[ ] 超期、利用率、停机影响独立报表和导出都能按 plan_role 读取。
[ ] 非最终方案页面明确提示“当前查看的是对比方案，不是本次正式采用结果”。
[ ] 单个候选失败不影响其他候选继续。
[ ] 候选全部失败时，给出可见错误，不写伪成功历史。
[ ] 第一版不做后台续跑、不做实时评分、不做多进程并行、不引入新数据库。
```

## 阶段 14：资源匹配第一版

本阶段对应 PR-8 `scheduler-graph-resource-matching-report`。它只做“资源可行匹配诊断”，不做自动派工，不改变排产结果。

大白话说：前面 PR-5 / PR-6 已经能知道哪些工序 ready、哪些工序更关键；PR-8 只回答一个更窄的问题——“首波 ready 工序里，按当前图输入看到的候选设备，最多能同时匹配多少道工序，哪些工序没有设备可匹配，哪些设备是瓶颈”。

### 14.0 PR-8 边界和整体要求

第一版只分析设备维度，不分析人员维度的二次匹配；原因是当前 `OperationGraphNode` 已经有 `candidate_machine_ids` 和 `candidate_operator_ids`，但真实内部派工还会考虑日历、停机、冻结窗口、当前时间轴、固定人员、外协等约束。PR-8 如果试图在 report-only 阶段复制整套 `auto_assign_resources`，会制造第二套派工器，后续很难对齐。

本阶段的硬要求：

```text
1. 优雅简洁：resource_matching.py 只做二分图最大匹配和摘要投影，不写万能资源优化器。
2. 高内聚低耦合：只依赖 graph/types.py、id_policy.py、nx_runtime.py，不反向 import scheduler run / optimizer / SGS / repo / Flask。
3. 不允许静默回退：NetworkX 不可用、输入合同错误、候选设备缺失都必须以 status/reason/warning 明确可见；不能把坏输入当成“匹配数量 0 且一切正常”。
4. 不允许过度兜底：没有候选设备就是没有候选设备，不能回退成全量设备；没有 ready 工序就是 empty_ready_set，不能随手拿全部待排工序替代。
5. 不允许吞错：调用方只捕获已有图链路明确允许的 NetworkXUnavailable / GraphInputContractError / GraphBuildContractError；未知异常继续暴露，不包成 degraded 成功。
6. 不做过度防御性编程：输入来源只接受 PR-5 已准备的 OperationGraphNode + OperationGraphEdge；不兼容任意 JSON、数据库 row、Excel row 或 nx.DiGraph。
```

PR-8 只允许写：

```text
result_summary["algo"]["graph_analysis"]["resource_matching"]
result_summary["diagnostics"]["graph_analysis"]["resource_matching"]
```

禁止写：

```text
Schedule rows
ScheduleCandidate / ScheduleCandidateRows / ScheduleCandidateSelection
schedule_optimizer.py / GreedyScheduler / dispatch_sgs 资源选择逻辑
resource_dispatch_service.py 的方案明细
schema.sql / migrations
配置新增项
页面新增按钮或路由
```

### 14.1 分析输入口径

PR-8 复用 PR-5 的 ready 资格口径，不重新发明 ready 队列：

```text
nodes:
  build_operation_nodes_from_rows(schedule_input.algo_ops, batches, resource_pool, frozen_op_ids)

edges:
  build_linear_edges_by_batch(nodes)

ready_op_ids:
  从 build_graph_ready_context(...) 得到首轮 ready 集合：
    schedulable_op_ids = algo_ops_to_schedule 的 op_id
    fixed_op_ids = frozen_op_ids + seed_results.op_id
    predecessor_op_ids_by_op_id = build_predecessor_successor_maps(nodes, edges)
    ready = 前置全部在 fixed_op_ids 内、且自身属于 schedulable_op_ids 的工序

candidate machines:
  使用 OperationGraphNode.candidate_machine_ids
```

如果 `graph_analysis_mode=report`，本阶段仍可计算 report-only 资源匹配，但 ready 口径必须显式写为 `first_wave_ready_from_fixed_predecessors`，只代表“按冻结/seed 视为已固定后的首波 ready”。

如果 `graph_analysis_mode=on` 且 DAG 可用，本阶段的 ready 口径仍与 PR-5 图 ready 队列一致；但匹配结果仍只写报告，不参与 SGS 候选排序或资源选择。

有环或图增强未允许时：

```text
resource_matching.status = "skipped"
resource_matching.reason = "graph_not_dag" 或已有 graph_enhancement_disabled_reason
不运行 maximum_matching
不写伪 matching_count=0 作为正常结果
```

### 14.2 resource_matching.py 接口契约

`core/services/scheduler/graph/resource_matching.py` 保持纯图分析模块，只提供普通 Python DTO 和纯函数。

建议接口：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Tuple

from .id_policy import display_id, make_machine_node_id
from .nx_runtime import import_networkx
from .types import OperationGraphNode


class GraphResourceMatchingContractError(ValueError):
    pass


@dataclass(frozen=True)
class OperationMachineMatch:
    operation_node_id: str
    machine_node_id: str
    operation_id: str
    machine_id: str


@dataclass(frozen=True)
class ResourceMatchingSummary:
    status: str
    reason: str
    ready_operation_count: int
    operation_with_candidate_count: int
    machine_count: int
    edge_count: int
    matched_operation_count: int
    unmatched_operation_ids: Tuple[str, ...] = field(default_factory=tuple)
    bottleneck_machine_ids: Tuple[str, ...] = field(default_factory=tuple)
    matches: Tuple[OperationMachineMatch, ...] = field(default_factory=tuple)
    warnings: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
```

字段口径：

```text
status:
  available / skipped / empty / error。
  resource_matching.py 自身正常分析只返回 available 或 empty。
  skipped 由调用方在非 DAG / 图增强不可用时投影。
  error 只用于已知合同错误的 public 投影，不掩盖未知异常。

reason:
  ok / empty_ready_set / graph_not_dag / graph_enhancement_disabled / graph_resource_matching_contract_error / networkx_unavailable。

ready_operation_count:
  输入 ready 节点数量。

operation_with_candidate_count:
  ready 节点中 candidate_machine_ids 非空的工序数量。

machine_count:
  ready 节点候选设备去重数量。

edge_count:
  operation-machine 二分边数量。

matched_operation_count:
  maximum_matching 选中的工序数。

unmatched_operation_ids:
  ready 工序中没有被匹配的 operation 展示 ID，按 ready 输入顺序输出。

bottleneck_machine_ids:
  候选边数大于 1、且至少参与一个未匹配工序候选集的设备展示 ID，按边数降序再按 ID 排序；只做诊断提示，不代表真实负荷。

matches:
  只保留工序侧映射；NetworkX 返回的机器侧反向映射必须过滤掉。

warnings:
  只放结构化、JSON 可序列化的小 warning，例如 ready 工序无候选设备。
```

核心函数：

```python
def summarize_operation_machine_matching(
    ready_nodes: Iterable[OperationGraphNode],
) -> ResourceMatchingSummary:
    """Return report-only maximum matching summary for first-wave ready operations."""


def resource_matching_summary_to_public_dict(summary: ResourceMatchingSummary) -> Dict[str, Any]:
    """Return small result_summary.algo.graph_analysis.resource_matching payload."""


def resource_matching_summary_to_diagnostics_dict(summary: ResourceMatchingSummary) -> Dict[str, Any]:
    """Return sampled diagnostics payload; never returns nx.Graph."""
```

内部 helper 可以有：

```python
def _build_operation_machine_graph(ready_nodes: List[OperationGraphNode]):
    nx = import_networkx()
    graph = nx.Graph()
    operation_node_ids = {node.node_id for node in ready_nodes}
    ...
    return graph, operation_node_ids, machine_edge_counts
```

合同要求：

```text
ready_nodes 必须是 OperationGraphNode；传 dict / nx node / 任意对象直接 GraphResourceMatchingContractError。
OperationGraphNode.node_id 必须非空且唯一；重复 node_id 直接报错。
candidate_machine_ids 已由 input_adapter 规范化；这里不再做全量资源兜底。
candidate_machine_ids 为空的 ready 工序进入 unmatched_operation_ids，并产生 warning code="graph_resource_no_candidate_machine"。
nx.Graph 不从函数返回，不进入 summary，不进入 diagnostics。
```

### 14.3 最大匹配和瓶颈诊断规则

最大匹配规则：

```text
1. 左侧节点：ready OperationGraphNode.node_id。
2. 右侧节点：make_machine_node_id(machine_id)。
3. 边：每个 ready 工序到自己的 candidate_machine_ids。
4. 调用 nx.bipartite.maximum_matching(graph, top_nodes=operation_node_ids)。
5. 只保留 key 属于 operation_node_ids 的映射。
6. machine_node_id 用 display_id 还原成业务 machine_id，便于 public / diagnostics 展示。
```

未匹配规则：

```text
unmatched = ready_operation_ids - matched_operation_ids
输出按 ready_nodes 输入顺序，不按 NetworkX 返回顺序。
```

瓶颈设备规则必须简单、可解释：

```text
1. 对所有二分边统计 machine_id -> candidate_edge_count。
2. 找出未匹配工序的候选设备集合。
3. bottleneck_machine_ids = 同时满足：
   - candidate_edge_count > 1
   - machine_id 出现在至少一个未匹配工序候选集中
4. 排序：candidate_edge_count 降序，再 machine_id 升序。
5. 默认最多 public 展示 10 个，diagnostics 可采样 50 个。
```

这不是设备负荷优化，不考虑时间、停机、日历、换型、人员可用性；文案里必须写清“仅按候选设备集合估算”。

### 14.4 接入 schedule_graph_report.py

接入位置在 `_build_schedule_graph_analysis_projection()` 中，必须复用已经构建好的 `nodes`、`edges` 和 `payload`：

```text
build_operation_nodes_from_rows(...)
build_linear_edges_by_batch(nodes)
analyze_linear_batches(...)
payload = graph_summary_to_dict(summary)
build_graph_score_projection(...)
build_graph_ready_context(...)
build_graph_resource_matching_projection(...)
project_graph_analysis_payload(..., resource_matching_public, resource_matching_diagnostics)
```

建议在 `core/services/scheduler/run/schedule_graph_dispatch_context.py` 新增一个小 helper，避免 `schedule_graph_report.py` 继续膨胀：

```python
def build_graph_resource_matching_projection(
    *,
    mode: str,
    is_dag: bool,
    graph_enhancement_allowed: bool,
    nodes: List[Any],
    graph_ready_context: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    ...
```

这个 helper 只做投影协调：

```text
1. mode=off 不会走到这里。
2. is_dag=False 时返回 skipped / graph_not_dag。
3. graph_ready_context is None 且 mode=on 时返回 skipped / graph_enhancement_disabled。
4. report 模式可用同一套 predecessor/fixed/schedulable 口径临时构造首波 ready，不启用 SGS。
5. 得到 ready_nodes 后调用 summarize_operation_machine_matching(ready_nodes)。
6. public 只放小摘要；diagnostics 只放采样。
```

public 字段示例：

```json
{
  "status": "available",
  "reason": "ok",
  "ready_operation_count": 3,
  "operation_with_candidate_count": 3,
  "machine_count": 2,
  "edge_count": 4,
  "matched_operation_count": 2,
  "unmatched_operation_count": 1,
  "bottleneck_machine_count": 1,
  "unmatched_operation_sample": ["101"],
  "bottleneck_machine_sample": ["M2"]
}
```

diagnostics 字段示例：

```json
{
  "matches_sample": [
    {"operation_id": "100", "machine_id": "M1"}
  ],
  "matches_count": 2,
  "matches_truncated": false,
  "unmatched_operation_ids_sample": ["101"],
  "unmatched_operation_count": 1,
  "bottleneck_machine_ids_sample": ["M2"],
  "bottleneck_machine_count": 1,
  "warnings_sample": [],
  "warning_count": 0
}
```

采样限制沿用小常量，不允许把完整匹配图、完整节点、完整候选资源池塞进 `result_summary`。

### 14.5 OperationLogs 和页面边界

OperationLogs 仍只能通过现有 `detail["algo"]` 看到 public 小摘要，因此 PR-8 不需要新增日志写入点。

允许 OperationLogs 看到：

```text
graph_analysis.resource_matching.status
graph_analysis.resource_matching.reason
ready_operation_count
matched_operation_count
unmatched_operation_count
bottleneck_machine_count
```

禁止 OperationLogs 看到：

```text
matches_sample
完整 unmatched_operation_ids
完整 bottleneck_machine_ids
nx.Graph
OperationGraphNode.raw
完整 resource_pool
```

页面层第一版不新增入口；后续如果要展示，只读取 `result_summary.algo.graph_analysis.resource_matching` 的小摘要，不直接调用 graph 模块。

### 14.6 测试

新增或补齐：

```text
tests/scheduler_graph/test_resource_matching.py
tests/regression_scheduler_graph_resource_matching_report_contract.py
tests/regression_scheduler_graph_operation_logs_contract.py
```

`tests/scheduler_graph/test_resource_matching.py` 至少覆盖：

```text
1. O1 可用 M1/M2，O2 可用 M2，O3 可用 M2：最多匹配 2 个工序，同一机器不会重复匹配。
2. 返回 matches 只保留工序侧映射，不包含机器侧反向映射。
3. 无候选设备的 ready 工序进入 unmatched_operation_ids，并产生 graph_resource_no_candidate_machine warning。
4. 空 ready_nodes 返回 status=empty、reason=empty_ready_set，不调用方伪造成功。
5. 重复 OperationGraphNode.node_id 直接 GraphResourceMatchingContractError。
6. 传入非 OperationGraphNode 直接 GraphResourceMatchingContractError。
7. summary/public/diagnostics 可 JSON 序列化，且不包含 nx.Graph。
8. bottleneck_machine_ids 按“参与未匹配候选 + 边数大于 1”规则输出，并按边数降序排序。
```

`tests/regression_scheduler_graph_resource_matching_report_contract.py` 至少覆盖：

```text
1. graph_analysis_mode=report 时，排产 rows / best_order / selected_batch_ids / freeze_window / resource_pool 不变，但 result_summary.algo.graph_analysis.resource_matching 有小摘要。
2. graph_analysis_mode=on + DAG 时，ready 队列和图评分既有字段不变，并额外写 resource_matching 小摘要；匹配结果不参与资源分配。
3. 有环且 block=no 时，resource_matching.status=skipped，不运行 maximum_matching，不写伪 matched=0。
4. NetworkX 不可用时沿用已有 graph_analysis unavailable 口径，不单独吞错成 resource_matching empty。
5. diagnostics.graph_analysis.resource_matching 只有采样，没有完整 resource_pool、raw、nx.Graph。
6. OperationLogs 只看到 public 小摘要，不泄漏 diagnostics.matches_sample。
```

### 14.7 实施顺序

```text
1. 先写 tests/scheduler_graph/test_resource_matching.py，锁住纯函数合同。
2. 实现 resource_matching.py：DTO、合同错误、最大匹配、public/diagnostics 投影。
3. 在 schedule_graph_dispatch_context.py 增加 build_graph_resource_matching_projection 小 helper。
4. 在 schedule_graph_report.py 接入 helper，并把 resource_matching public/diagnostics 合并进现有 graph_analysis 投影。
5. 补 regression_scheduler_graph_resource_matching_report_contract.py，证明 report/on 都不改变排产结果。
6. 补 OperationLogs 回归断言，只允许 public 小摘要。
7. 跑 PR-8 targeted tests、PR-3/4/5/6 图回归、ruff、pyright。
8. 回填 roadmap/items 和验收记录。
```

### 14.8 阶段验收清单

```text
[ ] resource_matching.py 不在模块 import 时 import networkx。
[ ] resource_matching.py 不 import scheduler run / optimizer / SGS / repo / Flask。
[ ] 最大匹配只返回工序侧映射。
[ ] 无候选设备不回退成全量设备。
[ ] 空 ready、有环、图增强不可用、NetworkX 不可用都有明确 status/reason。
[ ] report/on 模式只新增 result_summary graph_analysis 小摘要和 diagnostics 采样，不改变排产 rows / best_order / selected_batch_ids / resource_pool。
[ ] OperationLogs 不泄漏 diagnostics、matches_sample、完整 resource_pool、raw 或 nx.Graph。
[ ] 不新增配置、不改 schema、不改候选表、不改资源派工逻辑、不改页面路由。
[ ] ruff / pyright 通过。
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

## 阶段 16：受控调试输出

阶段 16 不再单独代表 PR-4 的全部范围。PR-4 的首要目标已经调整为“性能护栏 + diagnostics 加固 + 真实集成证明”；调试 JSON 文件只是这些证明通过后的附属能力。

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
性能护栏、diagnostics 加固和真实集成证明已经通过。
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

PR-4 执行时按下面口径处理：

```text
1. PR-4 默认性能护栏先测 basic report。
2. basic report 是明确合同：它不计算完整 node_metrics / downstream_critical_minutes。
3. 如果要测 full metrics，只能作为单独子用例或后续优化证据，不能影响 report 默认输出。
4. 如果 full metrics 慢，不允许代码自动把 full 改成 basic 后继续说“成功”；必须把选择写回 roadmap 或 feature design。
5. performance_2000_nodes.txt 要写清楚本次测的是 basic 还是 full，避免后续把两种耗时混用。
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
commit 12: add performance guardrails, diagnostics hardening, real integration proof, then controlled debug export
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

## 阶段 23：候选方案续跑作为后续增强

这一阶段不是第一版必做。第一版多权重试跑先采用更轻的做法：

```text
1. 原算法候选先跑，保证一定有兜底结果。
2. 关键链权重候选按系统预设档位继续跑。
3. 如果时间上限没到，就尽量跑完所有档位。
4. 如果时间上限到了，就停止继续新增候选。
5. 从已经完成的候选里选最好结果。
6. 页面告诉用户“本次跑完了几套 / 总共计划几套”。
```

第一版不做“继续补跑剩余方案”按钮，原因是它不是简单地接着算一下。真正续跑必须先解决下面这些问题：

```text
冻结当时的订单、工序、设备、人员、日历和配置快照。
保存候选方案队列：哪些已完成，哪些还没跑。
保存每个候选的摘要、代表性明细和选择理由。
保证续跑时仍然使用原始快照，不能混入后来被用户改过的数据。
支持页面展示“继续补跑剩余方案”的状态、结果和失败原因。
```

后续如果做 B，目标形态是：

```text
用户第一次排产只跑完 3/5 套方案。
系统已采用这 3 套里的最好结果，并记录剩余 2 套没跑。
用户在结果页或分析页点击“继续补跑剩余方案”。
系统基于第一次排产冻结的快照补跑剩余候选。
补跑完成后，只更新本次排产的候选对比和推荐结果，不偷偷改历史输入。
```

续跑的硬性边界：

```text
不能用当前最新订单重新拼接旧排产。
不能让子进程或后台任务直接写正式排产明细。
不能把未完成候选伪装成完整比较结果。
不能因为补跑失败就覆盖第一次已经可用的排产结果。
```

建议落地顺序：

```text
1. 先把第一版“时间到了就用已完成候选”的记录字段做稳。
2. 再加候选方案快照表或等价持久化结构。
3. 再加续跑入口和状态页。
4. 最后再考虑后台任务、取消、失败重试和自动清理旧候选。
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
│   ├── ready_queue.py        # 兼容导出算法层 ready_queue helper
│   ├── scoring.py
│   ├── resource_matching.py
│   ├── exporter.py
│   └── analysis_service.py
└── run/
    └── 原有排产服务文件

core/algorithms/greedy/dispatch/
├── ready_queue.py            # PR-5 真实 ready 队列实现
└── sgs.py                    # SGS 接入 ready 候选
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
    用原排序 + 关键路径加分 + 影响范围加分 + 后续关键工作量加分
    ↓
    选择工序
    ↓
    分配设备/人员
    ↓
    写入排程
```

这个路线比直接上 OR-Tools 稳得多，也更符合当前 Win7/Python 3.8.10/离线交付的实际约束。

## 变更记录

- 2026-05-19：完成 PR-7e `scheduler-graph-candidate-config-closeout`：新增候选档数、择优方式、超期批次数容差、拖期比例容差和本次候选比较时间上限链路；新库默认 `graph_analysis_mode=on`，旧库已有 `off/report/on` 不覆盖，旧 preset 缺字段会补默认值但保留用户已保存值。正式排产 `on` 默认运行 baseline + 5 档重点工序优先候选，`off/report` 仍是单方案排障；主链保留 `on + block=yes + 有环` 的提前阻断合同，`block=no` 时仍允许候选试跑但图增强降回普通排法。分析页只在候选摘要和明细完整时显示“最终采用 / 原算法最好 / 重点工序优先方案最好”，没有开启或记录不完整时明确提示，不生成假切换链接；周计划、资源排班等沿 PR-7d 的 plan_role 入口查看代表方案。新增 v11 时间索引和孤儿候选清理，性能守卫证明真实 `get_plan_time_span` SQL 走索引、`list_plan_roles` 不扫候选明细。浏览器临时库验证配置页、分析页、旧历史提示、代表方案页面和 30 批 120 工序压力排产；第一版仍不并行、不续跑、不换数据库。

- 2026-05-18：完成 PR-7c `scheduler-graph-candidate-transaction-persistence`：正式排产主链保留内存候选比较接入点，但在 PR-7e 配置字段落地前默认不启用，避免 `off/report/on` 既有排产合同被候选试跑改变；启用后只采用 `selection.selected_plan` 作为最终 adopted 方案，且 adopted payload 校验通过后才分配正式 `version`；新增候选小摘要投影和候选持久化 helper，让 `Schedule`、状态更新、`ScheduleHistory`、`ScheduleCandidate`、非 adopted 代表 `ScheduleCandidateRows`、`ScheduleCandidateSelection` 在同一个事务里写入，候选写入失败时正式排产和历史一起回滚；`result_summary.algo.candidate_comparison` 只保留小摘要，summary 超限后的最小摘要仍保留 adopted key、代表 key、候选数量、时间预算和选择原因这些极小字段，`OperationLogs` 只写极小日志字段，不泄漏候选列表、排产行、图节点边、raw graph 或完整 diagnostics。PR-7c 没有实现 PR-7d 页面/接口/导出/报表 `plan_role` 切换，也没有实现 PR-7e 配置收口、默认启用、候选清理或性能守卫。

- 2026-05-18：完成 PR-7d `scheduler-graph-plan-role-pages-reports`：甘特图、周计划、资源派工、分析页、超期清单、资源负荷与利用率、停机影响统计页面和导出统一接入 `plan_role`，旧链接默认 `adopted`，合法缺失角色可见 fallback adopted，未知角色直接校验错误；页面预览、JSON data、Excel 导出和 OperationLogs filters 使用同一套 requested/effective/status/candidate 小字段，不写 rows 或完整候选列表。甘特关键链 adopted 保留旧 `compute_critical_chain(schedule_repo, version)` 入口，候选方案从当前 plan rows 计算并按 role/source_table/candidate_id 隔离缓存。PR-7d 未实现 PR-7e 配置收口、候选清理或性能守卫，也未改 PR-8 report-only 资源匹配计划。

- 2026-05-18：完成 PR-7b `scheduler-graph-candidate-runner-selection`：新增候选规格生成、关键链健康纯函数、自动择优和内存候选 runner，默认生成 baseline + 5 档关键链候选并支持 3 / 5 / 7；runner 不走正式总编排、不分配正式 version、不写库，每个候选先用临时 cfg 准备图 ready 上下文，再把 `graph_ready_context` / `graph_dispatch_mode_override` 传给优化器；trial 模式显式锁住当前排序策略、派工方式和派工规则，避免把关键链权重比较混进 improve 多起点组合搜索；`score_only` 只看 raw score，`balanced` 只在关键链健康 better 且失败/超期/拖期没有明显变差时允许反超；`ValidationError` 一律原样抛出，不把图上下文、输入、配置或数据范围错误吞成候选失败后继续选 baseline。PR-7b 没有实现 PR-7c 主链同事务落库、PR-7d 页面/报表 `plan_role` 切换，也没有实现 PR-7e 配置收口。

- 2026-05-18：完成 PR-7a `scheduler-graph-candidate-schema-query`：新增 `ScheduleCandidate` / `ScheduleCandidateRows` / `ScheduleCandidateSelection` 和 v10 迁移，SchemaVersion 当前版本升到 10；候选表只保存候选摘要和非 adopted 代表方案明细，不把 `ScheduleCandidate.version` 外键到 `ScheduleHistory(version)`；新增候选模型、候选仓库、`SchedulePlanQueryService` 和 plan query repo，让 adopted 永远从 `Schedule` 读，合法但旧历史缺 selection 时可见 fallback 到 adopted，未知 `plan_role` 直接报错；selection 指向 `candidate_rows` 时必须 `detail_saved=yes` 且实际存在候选明细，否则直接报错，避免空结果被误当成功。PR-7a 没有实现 PR-7b 的候选生成/运行/自动择优，没有实现 PR-7c 主链同事务落库，没有实现 PR-7d 页面切换，也没有实现 PR-7e 配置收口。

- 2026-05-18：细化 PR-8 `scheduler-graph-resource-matching-report` 到可执行级：把阶段 14 从二分图草图扩成 report-only 资源匹配诊断方案，明确只分析首波 ready 工序 × `candidate_machine_ids` 的设备最大匹配，不做人员匹配、不做最小费用流、不改 SGS 候选排序、不改资源分配、不落候选表、不新增配置/schema/页面；补齐优雅简洁、不静默回退、不吞错、不过度兜底/防御的硬要求，写清 `resource_matching.py` DTO/纯函数合同、ready 输入口径、matched/unmatched/bottleneck 规则、`schedule_graph_dispatch_context.py` 小 helper 接入、public/diagnostics/OperationLogs 投影边界、测试用例、实施顺序和验收清单；同步 items.yaml 的 PR-8 description、primary_paths、forbidden_paths、exit_checks 和 notes。

- 2026-05-18：完成 PR-6 `scheduler-graph-critical-score-on-mode`：新增 `graph/scoring.py` 纯函数和纯函数测试，证明图 bonus 越大排序 tuple 越小，缺字段/坏字段/坏权重直接报合同错误；`schedule_graph_report.py` 在 `on + DAG + 权重大于 0` 时计算 full `node_metrics` 并预先转成 `graph_priority_key_by_op_id`，权重全 0 时显式写 `score_weights_zero` 并保持 PR-5 ready 队列行为；SGS 只拼普通 tuple，保留 `score_penalty` 第一位，不让算法层反向依赖 service，SLACK / CR / ATC 方向保持；配置页、summary、OperationLogs、2000 节点 full/on-score 性能证据和架构现状已同步。PR-6 没有实现 PR-7 的候选池、多权重试跑、自动择优、候选落库、页面切换或 schema 迁移。
- 2026-05-18：细化 PR-6 `scheduler-graph-critical-score-on-mode` 到可执行级：补齐 PR-6 承接 PR-5 的边界，明确只继承 ready 资格、不继承图评分方向证明；把阶段 13 从草图扩成完整执行计划，写清整体实现要求必须优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、保持高内聚低耦合；补齐图指标准备合同、`graph/scoring.py` 纯函数、SGS 接入位置、配置说明同步、summary / OperationLogs 小摘要口径、测试用例、实施顺序、验收命令和 PR-7 交接边界；同步 items.yaml 的 PR-6 description、primary_paths、forbidden_paths、exit_checks 和 notes。
- 2026-05-18：补充复验 PR-5 `scheduler-graph-ready-queue-on-mode`：修正 `on + block=no + 有环` 的 public 摘要和真实 dispatch mode 口径，改为通过 `graph_dispatch_mode_override="sgs"` 继续旧 SGS 候选逻辑，但保持 `graph_ready_context=None`，确保图 ready 队列不启用；补强 ready_queue / SGS 边界的图对象误传、嵌套前后置图对象、字符串/bool sort key 合同；把 SGS 前后置映射标准化结果写回运行态，确保校验和失败后继阻断使用同一口径；补 `graph_ready_context + 非 SGS` 直接报错和 `graph_dispatch_mode_override` 合法值校验，避免 ready 队列被悄悄忽略。复跑 PR-5 targeted tests、ruff、pyright 和 items.yaml 校验均通过；当前仍是 dirty worktree targeted proof，不是 clean-worktree proof。
- 2026-05-18：完成 PR-5 `scheduler-graph-ready-queue-on-mode`：阶段 11 实现有环安全门，`report` 有环只提示，`on + block=yes` 在 version 分配前阻止并返回中文业务错误，`on + block=no` 继续旧 SGS 候选逻辑并在 public 摘要写明图增强未启用；阶段 12 实现纯 Python `ready_queue.py`，在 optimizer 前准备 plain `graph_ready_context`，排产和 `result_summary` 共用同一份图分析结论，并沿 optimizer / GreedyScheduler / `dispatch_sgs` 传递；`on + DAG` 时强制 SGS 并用 ready 队列筛候选，无 graph context 时旧 SGS 候选逻辑保持；frozen / seed 只作为已固定前置，前置失败时图后继不释放并计入失败说明。PR-5 未实现图评分、候选池、多权重试跑、自动择优、落库或页面按钮；PR-6 只能继承 ready 资格，不能继承图评分方向证明。
- 2026-05-18：细化 PR-5 `scheduler-graph-ready-queue-on-mode` 到可执行级：补齐 PR-5 总体实现要求，明确优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合；把阶段 12 从草图扩成完整执行计划，要求在 optimizer 前准备图调度上下文，沿 optimizer / GreedyScheduler / dispatch_sgs 传入 plain graph_ready_context，只在 DAG 且 graph_enhancement_allowed=true 时启用 ready 队列；补齐 on 模式不可用/有环矩阵、frozen/seed 边界、SGS 接入规则、测试用例、实施顺序、验收命令和 PR-6 交接边界；同步 items.yaml 的 PR-5 description、primary_paths、forbidden_paths、exit_checks 和 notes。
- 2026-05-18：完成 PR-4 `scheduler-graph-debug-performance`：新增 2000 节点 basic report 性能测试和 `evidence/scheduler_graph/performance_2000_nodes.txt`，补 diagnostics 长文本截断合同、真实服务级 off/report/on 普通与 frozen/seed 对比、OperationLogs known graph error 小摘要检查，并创建 `.codestable/features/2026-05-18-scheduler-graph-debug-performance/` 验收记录。PR-4 没有实现 `graph_debug_export`、PR-5 有环安全门、ready 队列或 PR-6 图评分，`graph_analysis_mode=on` 仍然只是 `report_only`。
- 2026-05-18：细化 PR-4，把“性能护栏 + diagnostics 加固 + 真实集成证明”写成可执行计划：明确 PR-4 先证据后导出，补齐整体实现要求、文件边界、实施顺序、basic report 性能口径、diagnostics 采样/JSON 安全投影、known graph error 顶层可见、真实服务级 off/report/on 对比、OperationLogs 不泄漏、受控 debug export、验收命令和明确不做；同时把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成 PR-4 的硬要求。
- 2026-05-18：细化阶段 11，把“有环时的处理策略”写成 PR-5 开始前的可执行安全门：明确阶段目标、前置条件、整体实现要求、复用现有 graph 分析接口、不新造错误系统、配置/模式矩阵、接入位置、cycle_edges 采样来源、report / on+block=yes / on+block=no 三种处理口径、阶段 12 准入合同、测试用例、实施顺序、验收命令和明确不做；同时把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成阶段 11 的硬要求。
- 2026-05-17：补齐用户讨论后形成的完整产品口径：正式交付默认开启关键链；排产时原算法先跑作为兜底，关键链默认 5 档权重且档数可配置；系统复用现有评分自动择优，并在评分接近时用关键链健康做平衡判断；所有候选保留摘要，代表方案保留明细；甘特图、周计划、资源派工、分析页等主要结果页默认展示最终采用方案，并支持切换最终采用 / 原算法最好 / 关键链最好；第一版串行试跑，不做实时评分、多进程、续跑或新数据库。
- 2026-05-17：根据用户确认，把多权重试跑的时间上限策略定为第一版先不做续跑；时间到了就从已完成候选里选择最好结果并提示完成数量。真正“继续补跑剩余方案”作为阶段 23 后续增强，要求先冻结输入快照、保存候选队列和代表性明细，再提供续跑入口。
- 2026-05-17：实施阶段 10，接入 `graph_analysis_mode=report` 的旁路图分析：排产和落库 payload 算完后才生成 `algo.graph_analysis` 小摘要，并把采样诊断写入 `diagnostics.graph_analysis`；`off` 模式仍不 import graph 模块，`on` 在本阶段只标成 `effective_mode="report_only"`。补齐三份 report/summary/OperationLogs 回归测试，复跑阶段 10 建议测试、`tests/scheduler_graph`、ruff、pyright，并用阶段 0 三个 baseline case 验证 report 模式不改变排产结果。提交后 clean-worktree 门禁先发现 orchestrator 文件大小和 summary 函数复杂度踩线，已把图报告 helper 收到 `schedule_graph_report.py` 并拆出 summary 小函数，两个 architecture fitness 节点复验通过；clean-worktree quality gate 需在 amend 后重新跑完整链路。
- 2026-05-17：细化阶段 10，把 PR-3 report 模式接入写到可执行程度：明确前置条件、整体实现要求、旁路接入点、SummaryBuildContext 字段、public / diagnostics 投影、OperationLogs 小摘要合同、错误与 warning 口径、测试用例、实施顺序、验收命令和明确不做；同时把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成阶段 10 的硬约束。
- 2026-05-17：实施阶段 9，补齐 `GraphAnalysisSummary.node_metrics`、`exporter.py` 普通 dict 导出、`analysis_service.py` 统一分析入口，以及 `test_exporter.py` / `test_analysis_service.py`；本阶段仍只停留在图模块内部，没有进入阶段 10 / PR-3，没有写 `result_summary` 或 OperationLogs。
- 2026-05-17：细化阶段 9，把 `exporter.py`、`analysis_service.py`、`GraphAnalysisSummary.node_metrics` 补齐、DAG/有环处理口径、禁止静默回退、禁止过度兜底、测试用例、实施顺序和验收命令写到可执行程度；同时明确阶段 9 仍只做图模块内部统一入口和普通 dict 导出，不接 report 模式、不写 `result_summary`、不写 OperationLogs、不改变排产结果。
- 2026-05-17：细化阶段 8，把 `metrics.py` 的拓扑顺序、层级、关键路径、影响范围、节点指标、错误暴露、测试用例和验收命令补到可执行程度；同时明确阶段 8 只做图指标，不接 report、不接 SGS、不写 `result_summary`，并把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成硬要求。
- 2026-05-17：细化阶段 7，把 `validators.py` 的目标边界、整体实现要求、输入输出合同、DAG/环检测、孤立节点 warning、重复 `seq` warning、汇总规则、测试用例和验收命令补到可执行程度；同时明确阶段 7 只暴露图质量问题，不修图、不静默回退、不接排产、不写 `result_summary`，并把“优雅简洁、不做过度兜底、不做过度防御性编程、高内聚低耦合”写成硬要求。
- 2026-05-17：细化阶段 6，把 `precedence_builder.py` 的职责、输入输出合同、边生成规则、图构建规则、错误处理、测试用例和验收命令补到可执行程度；同时把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成阶段 6 的硬要求，并同步整体执行顺序表中阶段 5/6/7 的口径，避免后续按错阶段执行。
- 2026-05-17：执行阶段 5，新增 `core/services/scheduler/graph/input_adapter.py` 和 `tests/scheduler_graph/test_input_adapter.py`，把已整理好的排产输入转换为 `OperationGraphNode`；同时修复 `FrozenDict` 只读方法的 pyright 签名问题。阶段 5 仍只做输入转换，不构建 `nx.DiGraph`，不接入排产，不写 `result_summary`，不改变排产结果。
- 2026-05-17：细化阶段 5，把 `input_adapter.py` 的职责、输入合同、字段映射、时长计算、候选资源、raw 快照、错误处理、测试用例和验收命令补到可执行程度；同时把“优雅简洁、不做过度兜底、不做静默回退、不做过度防御性编程、高内聚低耦合”写成阶段 5 的硬要求；按只读核实结果补准固定人员/固定设备候选资源口径、外协天数必须大于 0、source 严格合同和 pyright 收尾要求。

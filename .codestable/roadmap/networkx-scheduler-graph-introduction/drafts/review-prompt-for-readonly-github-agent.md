# 给只读 GitHub Agent 的审阅提示词

你是一个只读 GitHub 仓库审阅 Agent。请不要改代码、不要提交、不要 push，只做审阅并输出问题清单。

## 审阅目标

请审阅当前分支 `feature/networkx-scheduler-graph` 上的 NetworkX 排产工序图路线图，重点判断：

1. 方案是否符合当前仓库真实结构。
2. PR-7“多权重自动择优和代表方案对比”是否可实现。
3. 数据库表、排产主链、结果页切换、评分择优和测试计划有没有明显漏洞。
4. 有没有遗漏用户已经确认的决策。
5. 有没有会破坏 Win7、Python 3.8、SQLite、本地离线交付的设计风险。

## 必读文件

请至少阅读：

```text
.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-roadmap.md
.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml
schema.sql
core/services/scheduler/run/schedule_orchestrator.py
core/services/scheduler/run/schedule_optimizer.py
core/services/scheduler/run/schedule_optimizer_steps.py
core/services/scheduler/run/schedule_persistence.py
core/services/scheduler/gantt_service.py
core/services/scheduler/resource_dispatch_service.py
data/repositories/schedule_repo.py
data/repositories/schedule_history_repo.py
templates/scheduler/gantt.html
templates/scheduler/week_plan.html
templates/scheduler/resource_dispatch.html
templates/scheduler/analysis.html
```

重点阅读路线图里的这些段落：

```text
已确认产品口径
阶段 13.6：多权重候选试跑、自动择优和代表方案对比
阶段 23：候选方案续跑作为后续增强
items.yaml 里的 scheduler-graph-auto-selection-comparison
items.yaml 里的 scheduler-graph-candidate-resume-later
```

## 用户已经确认的 20 个选择

下面是用户和方案制定者逐题讨论后的选择。请用这些选择作为审阅标准，检查路线图有没有遗漏、误解或自相矛盾。

| 序号 | 问题 | 用户选择 | 应落地结论 |
| -: | --- | --- | --- |
| 1 | 多套排产结果要怎么给普通用户看？ | B | 默认展示系统选出的最好方案，其他方案作为备选能看，避免用户自己一套套研究。 |
| 2 | 自动择优按什么目标来选？ | A | 先沿用系统现有评分和优化目标，不另做一套用户看不懂的新评分体系。 |
| 3 | 默认跑几档关键链权重？ | 默认 5 档 | 默认跑 5 档；跑几档允许人工设置。 |
| 4 | 权重是随机给，还是系统固定几档？ | 系统固定几档 | 第一版不随机；每档权重由系统根据默认基准生成。 |
| 5 | 是否把所有排序规则、派工规则、关键链权重全部组合跑？ | 先 A | 第一版只在当前用户选择的规则下跑原算法 + 关键链权重；后续再考虑深度组合试跑。 |
| 6 | 数据库能力怎么处理，要不要换新数据库？ | 先不换库 | 第一版继续用当前数据库，补候选表、摘要和清理策略；数据规模变大后再考虑数据库升级。 |
| 7 | 候选方案第一版要不要并行跑？ | 先 B，后期考虑 C | 第一版串行试跑，先保证 Win7 / PyInstaller / SQLite 下稳定；后期再考虑并行和后台任务。 |
| 8 | 某一套候选方案失败怎么办？ | B | 单个候选失败只记录失败原因，其他候选继续；不能因为一套失败让整次排产失败。 |
| 9 | 关键链功能默认开不开？ | 默认开启 | 正式交付默认开启关键链参与排产；off / report 保留给开发、排障和回滚。 |
| 10 | 候选结果只保留摘要，还是也保留排产明细？ | B | 所有候选保存摘要；代表方案保存完整明细，至少包括最终采用、原算法最好、关键链最好。 |
| 11 | 关键链方案超过原算法时，要设哪些硬条件？ | B，但别太重 | failed_ops 不能变差；超期批次数默认最多多 1 个，可在高级设置改 0 / 1 / 2；拖期容差可调。 |
| 12 | 关键链健康怎么展示？ | D | 用户侧显示“更健康 / 差不多 / 更差”；内部指标支撑，不把一堆数字直接甩给普通用户。 |
| 13 | 如果最终采用原算法，要不要展示关键链结果？ | B | 要展示已比较关键链方案，并保留关键链最好方案可查看。 |
| 14 | 如果最终采用关键链，但它不是原始评分第一，怎么解释？ | B | 普通页面说“评分接近，关键链健康更好”；优化分析页展示详细原因。 |
| 15 | 甘特图里要不要能切换方案？ | B | 甘特图支持最终采用 / 原算法最好 / 关键链最好切换。 |
| 16 | 是不是只有甘特图能切换，其他页面不管？ | C | 所有主要结果页都要支持代表方案切换，避免用户只能看到一部分数据。 |
| 17 | 排产过程中要不要显示实时评分？ | B | 第一版只显示正在试跑第几套、已完成几套，不做实时评分滚动刷新。 |
| 18 | 时间不够，5 档没跑完怎么办？ | A | 不强制跑完；从已完成候选里选最好结果。 |
| 19 | 时间上限怎么处理？ | A，并补充排产前临时调整 | 复用当前时间上限配置；排产执行前允许临时设置本次时间上限，不必只藏在高级设置里。 |
| 20 | 要不要第一版就做续跑？ | 先 A，路线图后面加 B | 第一版不做续跑；后续路线图加“继续补跑剩余方案”。 |

## 审阅重点

请重点检查这些风险点：

1. `Schedule` 当前有 `version + op_id` 唯一约束，路线图新增 `ScheduleCandidate / ScheduleCandidateRows / ScheduleCandidateSelection` 是否足以支撑代表方案对比。
2. “正式 `Schedule` 只保存最终采用方案，代表候选明细存在候选表”这个设计会不会和甘特图、周计划、资源派工、优化分析页的现有查询方式冲突。
3. `plan_role=adopted / baseline_best / critical_best` 的方案切换是否覆盖了页面链接、导出、数据接口和缺失角色回退。
4. 候选试跑放在 `orchestrate_schedule_run()` 前后的位置是否合理，是否会破坏现有 `persist_schedule()`、`ScheduleHistory`、`OperationLogs`、模拟排产和正式排产语义。
5. 自动择优规则是否有漏洞，例如现有 `objective_score` 字段不足、指标名不一致、`failed_ops` / 超期批次 / 拖期时长取值来源不清。
6. “关键链健康”指标是否能从已有或计划中的 graph metrics 和最终排产结果里稳定计算。
7. 单候选失败继续跑的规则是否和当前异常处理、事务边界冲突。
8. 时间上限与当前 `time_budget_seconds` 的关系是否清楚；原算法先跑是否一定能保证兜底结果。
9. 第一版串行试跑在性能上是否可接受，尤其是 Win7 + Python 3.8 + SQLite 场景。
10. 新增配置字段、迁移、旧配置方案 preset、默认开启关键链之间是否有升级风险。
11. `result_summary` 和 `OperationLogs` 的摘要大小是否可能超限。
12. `items.yaml` 的 PR 拆分、依赖顺序、测试清单是否合理。
13. 路线图里是否还有“第一版不做续跑”和“后续做续跑”的表述冲突。
14. 是否遗漏了超期报告、利用率分析、停机影响分析等用户要求支持方案切换的页面或服务入口。
15. 是否有不符合项目约束的设计：Python 3.9+ 语法、外部前端资源、新数据库、NetworkX 重依赖、静默兜底、宽泛吞错。

## 输出要求

请用中文输出，优先列问题，不要只写总结。

请按这个格式输出：

```text
结论：
- 可以继续 / 需要补充后再继续 / 风险较大不建议继续

严重问题：
1. [问题标题]
   - 证据：文件路径 + 行号或代码位置
   - 为什么是问题：
   - 建议怎么改：

中等问题：
1. ...

轻微问题 / 文档可读性问题：
1. ...

遗漏问题：
1. 用户 20 个选择里有没有没落进路线图的：
2. 还有哪些实现前必须问用户：

建议补充的测试：
1. ...

总体评价：
- 用大白话说明这个方案现在够不够进入实现阶段。
```

如果你认为方案中某处其实是合理的，也可以说明“这里我认为没问题”，但请把主要精力放在找风险和遗漏上。

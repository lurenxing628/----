# 本机精细计算启用与容量复测

状态：本机配置启用完成；5000 工序容量验收未通过，独立启用验证通过。没有把两种结果合并为通过。

## 根因与修复

源码的 `algo_mode` 默认 improve 不会覆盖旧库保存的 greedy。工作台沿用已保存计算模式，原进程也早于算法修改，导致新增图 IG 搜索没有在该实例启用。本轮通过现有 ConfigService 切换到 improve，保留原 20 秒预算，并正常停止旧进程、以 APS_ENV=production 加载当前源码。用户已明确允许必要时终止；旧服务正常关闭，无需强杀。

实际库严格构建工作台配置时另外发现四个缺失的注册项。通过现有 `bootstrap_registered_defaults` 仅新增 `graph_candidate_weight_count=5`、`graph_selection_policy=balanced`、`graph_overdue_tolerance_count=1`、`graph_tardiness_tolerance_ratio=0.1`；全部原有配置行保持不变。配置切换与补齐均在事务内追加操作日志，没有改写严格校验或静默回退。

## 本机验证

- SQLite Backup API 已保留原库；77 张表中 74 张业务/其他表不变，只变化 ScheduleConfig、OperationLogs、sqlite_sequence。
- 原 13,390 条操作日志逐行保留，数据库结构、既有业务数据不变；没有创建生产排产作业。
- 最新受管进程 PID 60571，127.0.0.1:5000，健康接口 ok；真实库 candidate_config 严格读取通过：improve、20 秒、一次运行图模式 on、图候选档数 5。
- 当前 Python 3.8 执行完成，未改产品源码或新增依赖。源码和构建文件 4,163 项与基准冻结时一致。

## 实验与限制

用户要求继续跑原 180 秒 benchmark。本轮保留 5000 工序和四套完整结果门槛，将原夹具切为 improve + 实际 20 秒预算：受理后 37.1832 秒返回 partial，完成 2/4 套、持久化 10,000 条任务，其余预算不足被跳过。首个图方案解码耗时 28.8022 秒，图 IG 尚未构造或启动；本轮容量失败，不能与之前四套完整结果的 91.4294 秒计算提速比例。

另用相同源码、同样 improve + 20 秒运行独立的 40 工序启用验证：8.6229 秒完成四套/160 条任务，图 IG 实际 400 次解码、21 轮迭代；正常退出、重启读取和数据保留通过。该小规模结果仅证明启用链路，不替代容量结果。

180 秒是外层验收上限，20 秒是内部搜索预算。本机图候选默认 5 档，原四候选基准夹具固定 3 档，不能将该夹具称为本机全部配置的镜像。剩余大实例瓶颈是首次 SGS 解码与预算衔接；其他 Win7 部署包未检查或更新。

证据：`evidence/Benchmarks/2026-09-15-optimizer-production-activation/README.md` 与 `evidence/Benchmarks/2026-09-15-capacity-improve-20s/README.md`，含源码、原始结果、事务改动、数据保留和逐文件归档核验。

按用户明确要求不跑全门禁；本轮只做以上定点验证，保留原有 dirty worktree，未提交，不能称为 clean-worktree proof。

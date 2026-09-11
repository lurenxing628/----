---
doc_type: refactor-design
refactor: 2026-07-19-summary-build-context-typing
status: approved
scope: SummaryBuildContext 及两个直接消费者的静态类型
summary: 复用 domain 类型和轻量 Metrics Protocol，不改运行时结构或业务计算
---

# U01 执行设计

## 范围与授权

- 承接 `plan-draft.md` 的字段调查，本轮用户已授权后端实施，无需重复走审批。
- 写集为 `contracts/schedule_summary_types.py`、`summary/schedule_summary_assembly.py`、`summary/summary_runtime_state.py`，以及专属测试和本目录记录。
- 不改 `evaluation.py`、`scheduler/run/*`、`due_risk_items.py`、其他 summary 业务计算、公共 registry、基线或 roadmap；不暂存、提交、推送。
- 两个消费者已有 dirty 业务修改。本轮修改以前置文件副本为比较基准，不把已有修改算作 U01，也不回退它们。

## 字段裁决

| 字段 | 收敛类型 | 使用点及边界 |
|---|---|---|
| end_date | Optional[Union[date, str]] | 输入采集返回 date；结束日期合同保留 str；datetime 是 date 子类。不增加解析。 |
| batches | Dict[str, Batch] | ScheduleRunInput 的批次字典；runtime_state 和风险载荷只读透传。 |
| operations | List[BatchOperation] | ScheduleRunInput.operations；冻结批次、缺资源样本、自动分配失败归因。 |
| results | List[ScheduleResult] | OptimizationOutcome.results；seed coercion 确实构造同一 domain 类；完工时间与已排工序集合。 |
| summary | Optional[ScheduleSummary] | 主生产结果以及候选结果；None 已有降级处理，继续保留 getattr 容错。 |
| used_strategy | SortStrategy | assembly 直接读取 .value；不把非法 None 变成默认策略。 |
| input_build_outcome | Optional[BuildOutcome[List[Any]]] | 对齐 ScheduleRunInput.algo_input_outcome；插件/算法输入元素暂不强定类型。 |
| best_metrics | Optional[SummaryMetrics] | 只要求现有 to_dict() -> Dict[str, Any]；诊断属性经 getattr 可缺省，不虚构必填属性。 |

- D1：不加 schema、`__post_init__` 或新的 `isinstance` 校验，不做任何强转/cast。
- D2：Protocol 就放在现有 contracts 叶子，只有 typing 依赖；不反向导入 algorithms，连 TYPE_CHECKING 也不引。
- D3：`warning_merge_status` 继续用 `Dict[str, Any]`。生产者 `_merge_summary_warnings` 返回普通 Dict，下游 `_summary_degradation_state` 接收可变 Dict；单端改 TypedDict 会造成静态不兼容，需要越出授权写集，故采用草案保守默认。
- `cfg` 保留 Any：dict、属性对象、config 层真实快照是已存在的输入生命周期；不把 models 的同名类冒充真实实例。
- 其他异构字典和 trace 保留 Any，不凭空补齐跨模块 schema。
- D4：新增专属合同测试，锁注解、字段顺序/默认值、对象保留、Python 3.8 导入与正负静态样例；不改公共测试登记。

## 执行顺序

1. 前置刻画（M-L1-04）：读取现场、运行 symbol_locator 并以 rg 补齐 dataclass 构造；记录 pytest/pyright 基线。
2. 参数对象合同补齐（M-L2-07 的已有参数对象收敛）：只改注解及必要类型导入，贯通两个消费者，不改变其函数体。
3. 合同刻画与验证（M-L1-04）：新增测试，运行相关 pytest、pyright gate/default/tools、ruff、Python 3.8 语法检查和 A1/A3 依赖检查。保留整仓既有失败，不改基线消噪。

## 验收与风险

- 本任务仅后端类型，无目视验收。用类型移除后的 AST 比较验证两个消费者业务语句未变，并检查 dataclass 字段名称/顺序/默认值保持。
- IDE 配置包含旧测试中的 SimpleNamespace 假对象，domain 注解会暴露静态不匹配；不以 cast 掩盖，也不为 IDE 数量降低生产类型精度。记录增量并区分运行时回归结果。
- 共享 dirty 工作区、其他代理并行修改，所有结果只代表当时工作区，不能称 clean-worktree proof。完整门禁写共享 manifest 且要求稳定工作区，交主代理统一汇总执行。
- 回退只撤销本轮精确补丁；不执行 git revert/reset/checkout，不覆盖此前 dirty 业务修改。

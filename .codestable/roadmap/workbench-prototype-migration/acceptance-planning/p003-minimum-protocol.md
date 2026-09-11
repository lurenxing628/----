# D-P003 最小协议提案

- 原提案时间：2026-09-10 22:30。Main 后续已明确批准，且于 23:50 确认新叶加载顺序和 G 的 shared parser 已接纳。2026-09-11 实现与第一批四组合证据见 p003-implementation-note.md；此处保留原决策依据，不再等待批准。
- 范围：冻结的 `WBP-GANTT-003.predecessors` 与 `WBP-GANTT-004.trial-link`，不是扩大业务能力。

## 现有证据

1. `core/services/workbench/plan_projection.py:191` 的 `project_tasks()` 只发布 task/operation/plan refs、展示信息、资源及时间，没有原计划前后序事实。不能拿当前 BOM 或列表前一行猜历史计划依赖。
2. `core/services/workbench/trial_base.py:47` 的 `_row()` 已保存 `source_task_ref`、`source_row_ref`、`operation_ref`；`frontend/workbench/app/TrialContract.js:60` 已检查这些原始引用。所以无需新增写 API，也无需把正式 task_ref 当草稿 task_ref 使用。
3. `frontend/workbench/app/TrialContract.js:24` 只接受 draft/scenario/base/scope；`web/routes/workbench/navigation_boot.py:147` 对 trial 入口使用严格白名单。主线必须参与新增导航定位字段，D 不擅自修改这些 shared 入口。

## 最小新增

1. 在现有 plan workspace 返回增加下面的 `projections.process_order`。使用同一读取事务中的原采用审计、候选受理快照或保存场景原始快照；原证据缺失返回 unavailable 和原因，不创建引用、不用当前同号记录兜底。尺寸沿现有完整返回上限，不能截断装成功。
2. 仅在试调导航 target 增加 `task_origin: {plan_ref, operation_ref, task_ref}`；三项都是明确原来源，不是可写票据。允许与 base 或指定 draft_ref 共存，禁止与候选 base、scenario_ref 或不同的 base.plan_ref 共存。字段不进入 `trial.create`、`trial.change`、`trial.save` 或 adopt 请求。
3. 打开试调后仍由用户明确新建完整草稿或选择同一原计划的已有草稿。读取成功后要求 `data.base.plan_ref === task_origin.plan_ref`，并且唯一任务同时满足 `operation_ref` 与 `source_task_ref`。仅用匹配出的新 `task_ref` 选中详情；无匹配/多匹配/来源不一致则可见报错，不选第一条或同序号任务。
4. 搜索/时间范围只作为显示上下文；创建和采用始终完整计划，不能用所选任务改写 scope 或直接改正式计划。URL 和刷新保留原定位时由 Main 的 shared validator 接纳有型字段。

### 返回结构

```text
process_order = {
  state: "available" | "unavailable",
  basis: "run_admission" | "trial_creation" | null,
  items: [{ task_ref, operation_ref, predecessor_operation_refs: [operation_ref, ...] }, ...],
  issues: [{code, message}, ...]
}
```

- `items` 覆盖这份计划的完整安排身份，不受当前时间切片影响；引用均为 48 位已有永久 ref。一个工序若有多个安排片段，保留多个 task_ref，不用 operation_ref 去重掉任务。
- 前序来自冻结来源；后序由该有向关系反查，避免再维护第二套矛盾边。空前序数组只表示已核实无前序，不能代表证据缺失。
- `available` 要求完整安排身份和冻结关系均核实；否则 `unavailable`、`basis=null`、`items=[]`、`issues` 非空。该投影及私有事实一并进入 workspace 原 fingerprint，不独立发可写票据。
- 前端将关系 ref 与当前 `data.tasks` 相交。范围外安排只显示“在当前读取范围外”，由用户明确打开同一 plan_ref 的完整范围后定位；同工序多个安排逐条展示，不默认取第一条。
- 若冻结前序没有这份计划的安排，明确显示“前序未在本计划安排”，不把别的版本、当前同序号或同资源任务当作前序。

### 导航结构

```text
{base: {plan_ref}, scope?: 原有只读显示条件,
 task_origin: {plan_ref, operation_ref, task_ref}}
或
{draft_ref, task_origin: {plan_ref, operation_ref, task_ref}}
```

`task_origin` 严格三键且不能部分缺失；base 情况须 plan_ref 相同。已有草稿情况等待真实读取再核实 base 与 source_task_ref；导航字段不传给创建/修改/保存/采用服务。恢复地址采用 Main 既有规范，不发明新的引用命名空间。

## 拟验证

- 原采用计划的共同、分件、零时长点和正工时前后序；原依赖缺失禁用并说明。
- 新建/打开既有完整草稿后，原三项身份到草稿 task_ref 唯一映射；错 plan、错 operation、错 task 不能混用。
- 当前列表搜索或时间切片不缩小草稿与采用任务集合；刷新仍定位同一草稿。
- 真实完整 factory/受管 worker/私有 SQLite 链复测，原所有正式行和执行事实保留。

Main 已注册 `PointContract.js -> PlanProcessOrder.js -> PlanContract.js`；D 未修改 shared navigation、factory 或数据库 schema，G 的导航 parser 为独立交付。

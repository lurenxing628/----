# 合法小数工时生成的候选无法正式采用，交付分析误判时间无效

> 历史记录归档（2026-09-27）：本文保留初始调查、验收失败及当时的判断；正文中的“未修复”“未提交”“尚未安装”等描述均为记录时的状态。后续修复已提交于 `0b9a682f` 至 `d1307cb8`，原 Win7 的安装、复验和交付结果以[最终验收记录](2026-09-26-win7-fixes-acceptance.md)为准。打包验收脚本及两份专测已包含在 `0b9a682f` 中。本文原存于 `codestable/`，现归档至 `.codestable/`；引用的本机日志、数据库和截图不随 Git 上传。

日期：2026-09-26。状态：**验收发现，未修复**。级别：**P2，业务流程限制**。
基线提交：`4df78c5330f8c0cb819ecf5a8678dc46b1340e58`。发现环境：原 Win7 x64 虚拟机、Chrome 109、独立合成数据浏览器验收槽。

## 现象与复现

数量为 `3` 的批次，自制工序换型工时为 `0`、单件工时为 `0.001` 小时，效率为 `100%`，资源与可用班段充足。该输入合法，总工时为 `0.001 × 3 × 3600 = 10.8` 秒；从整秒开始时，结束时间包含小数秒。排产可以生成候选，但采用预检返回 `candidate_time_precision_unsupported`、`can_adopt=false`，不签发写入令牌。

实际 `CAP-001` 验收候选包含 10 道安排，首轮业务检查在采用步骤失败。预检 HTTP 200 表示请求被处理，不表示允许采用。原响应见[浏览器失败报告第 21203 行](</C:/Users/lurenxing/AppData/Local/Temp/aps-win7-external-acceptance-20260926/actual-win7-business/report.json:21203>)；界面见[采用被阻断截图](</C:/Users/lurenxing/AppData/Local/Temp/aps-win7-external-acceptance-20260926/actual-win7-business/screenshots/failed-adopt-real-candidate.png>)。

用户提示为：“这个候选方案的时间精确到了秒以下，正式计划存不了这么细，没有采用。请重新排产后再试。”对于相同工时、数量、效率及班段，再次排产仍会产生小数秒；提示没有定位具体工序或给出有效恢复办法。

## 契约核查

| 环节 | 当前行为与源码证据 |
| --- | --- |
| 输入 | 工艺页面允许 `step="any"`；后端接受有限非负工时，不限制小数位。[ProcessHoursEditor.jsx:74](</D:/Github/----/frontend/workbench/app/ProcessHoursEditor.jsx:74>)、[workbench_process_commands.py:29](</D:/Github/----/core/models/workbench_process_commands.py:29>)。排产输入同样没有整秒可表示性检查：[run_input_rows.py:57](</D:/Github/----/core/services/workbench/facts/run_input_rows.py:57>)。 |
| 计算与归档 | 引擎按换型工时加单件工时乘数量、再除以效率计算；日历和候选归档保留小数秒。[internal_slot.py:77](</D:/Github/----/core/algorithm_runtime/internal_slot.py:77>)、[internal_slot.py:247](</D:/Github/----/core/algorithm_runtime/internal_slot.py:247>)、[engine.py:364](</D:/Github/----/core/services/scheduler/calendar/engine.py:364>)、[workbench_run_job.py:58](</D:/Github/----/core/models/workbench_run_job.py:58>)。 |
| 正式采用 | 任意一行起止时间带微秒部分即阻断整个候选，避免正式计划的秒级格式截断已验证时间。[candidate_adoption_validation.py:40](</D:/Github/----/core/services/workbench/run/candidate_adoption_validation.py:40>)、[schedule_payload_contract.py:35](</D:/Github/----/core/services/scheduler/run/schedule_payload_contract.py:35>)、[_sched_display_utils.py:28](</D:/Github/----/core/services/scheduler/_sched_display_utils.py:28>)。 |
| 现有测试 | 已有测试设置 `unit_hours=0.001`，执行真实候选计算，明确期待同一阻断码；默认数量正是 `3`、换型工时 `0`。[test_run_candidate_adoption_boundaries.py:235](</D:/Github/----/tests/workbench/test_run_candidate_adoption_boundaries.py:235>)、[run_compute_support.py:18](</D:/Github/----/tests/workbench/run_compute_support.py:18>)。本次只读核查没有重跑测试。 |

因此，**采用保护符合现有契约，应当保留**；问题是合法输入、候选生成与正式采用之间缺少一致的时间精度规则。不能归为 Win7 崩溃，也不能通过删掉保护或直接舍入候选时间来“修复”。影响范围是最终生成非整秒起止时间的输入组合，不是所有三位小数工时；例如 `0.001 × 5 × 3600 = 18` 秒本身不会触发该限制。

## 恢复路径与边界

结束前的真实只读 API 核对确认：`CAP-001` 的 `protected=false`、`plan_reference_count=0`、`batch.operation_update=true`，10 道工序均 `editable=true`，单件工时仍全部为 `0.001`。证据见[结束检查报告的 cap_batch_detail](</C:/Users/lurenxing/AppData/Local/Temp/aps-win7-external-acceptance-20260926/actual-win7-finish/report.json:15399>)。**本例没有被候选锁定，普通编辑途径可用**；可通过真实编辑调整合适的工时后重新排产，但本轮没有执行 `.005` 修改或该场景的重新采用，因此不能称恢复已验证。

一般边界：新 `WorkbenchRunCandidateTasks` 与旧 `ScheduleCandidateRows` 是不同存储。若其他批次已有旧候选、正式计划或执行引用，才可能触发禁止编辑、删除及改数量的保护，见 [facts.py:15](</D:/Github/----/core/services/workbench/batch/facts.py:15>)、[facts.py:75](</D:/Github/----/core/services/workbench/batch/facts.py:75>)、[batches.py:23](</D:/Github/----/web/routes/workbench/batches.py:23>)。公开候选路由没有删除或清理入口，且新运行账本禁止删除；这些是一般契约，不是本例不可编辑的证据：[run_candidates.py:109](</D:/Github/----/web/routes/workbench/run_candidates.py:109>)、[workbench_run_schema.py:50](</D:/Github/----/core/infrastructure/workbench_run_schema.py:50>)。

后续验收可用另外的整秒工时合成批次继续验证其他业务链路，但不能把原场景记为通过；不得直接改数据库、删候选账本、伪造令牌或绕过引用保护。

## 建议修复方向

统一输入、排产计算、候选证明、正式存储、时间查询及界面展示的精度契约：可以评估完整支持小数秒，或在计算前采用明确的时间粒度规则并重新验证资源冲突、工时与前后序约束。不能只在采用时截断结果。提示应标出受影响工序、原因和可行处理方式；若允许纠正受保护批次，还需设计保留历史证明的正式修订流程。

后续回归应覆盖合法小数工时、非整数效率、跨班段、多个候选、受保护批次，以及成功采用后的持久化和重启一致性。当前仅记录发现与修复建议，未修改生产代码、测试、候选数据或虚拟机。

## 追加实证：5000 工序完整候选的交付分析不可用

5000 工序重压中断后，原机正常重启，在没有并行读取压力的新实验中成功计算出候选。这个低负载恢复实验不是原压力测试通过。实际候选 `74e842c759e2fe261e1bf4e867504675f643d421fcb850bc` 属于运行 `9cabfcba8ed52a37081d0a17a16dbf0e6499908d195dc2b5`，5000 道任务完整，可浏览、分页和导出；但“交付风险”页所有批次的候选完工均为“暂无数据”，预计超期批次与总拖期为未知。

原始证据：[完整 workspace](../../evidence/Win7Acceptance/20260926/browser/actual-win7-stress5000-quiet-recovery-ui-r2/workspace.json)、[候选 analysis HTTP 响应](../../evidence/Win7Acceptance/20260926/browser/actual-win7-stress5000-quiet-recovery-ui-r2/analysis-response.json)、[第 5 页界面截图](../../evidence/Win7Acceptance/20260926/browser/actual-win7-stress5000-quiet-recovery-ui-r2/screenshots/pressure-delivery-page-5.png)、[停机数据库一致性检查](../../evidence/Win7Acceptance/20260926/stress/level-5000-quiet-recovery01/mixed-state-offline.json)。结构检查通过不代表风险数值正确。

只读检查保存的 HTTP 数据和已停止实例的数据库，没有发送新请求或执行产品源码，得到：

| 项目 | 实际结果 |
| --- | --- |
| 候选任务 | 5000 行均能按本地 ISO 时间解析，且起点早于终点。 |
| 小数秒范围 | 4000 行起点带小数秒，4000 行终点带小数秒；5000 行均至少有一端带小数秒。 |
| 示例 | `CAP-057` 第 1 道工序从 `2026-09-29T08:33:00` 到 `2026-09-29T08:33:10.800000`，是合法的 10.8 秒安排。 |
| 交付分析 | 100 批次 `after.risk` 全为 `unknown`；每批 `invalid_task_count=50`、已安排工序 50、未安排工序 0；全部 `planned_finish=null`。 |
| 问题码 | 100 批次均有 `schedule_time_invalid` 和 `part_label_missing`；两者原因不同，见下文。 |
| 正式基准 | 受理时 `baseline.version=null`、`rows=[]`，HTTP 返回 `no_admission_baseline`。这只解释基准及变化指标未知。 |

### 交付风险未知的确定原因

数据链路是 [candidate_delivery.py:19](</D:/Github/----/core/services/workbench/run/candidate_delivery.py:19>) 将候选任务的 `start/end` 原值映射到 `start_time/end_time`，随后 [candidate_delivery.py:99](</D:/Github/----/core/services/workbench/run/candidate_delivery.py:99>) 调用 [delivery_projection.task_intervals:11](</D:/Github/----/core/services/workbench/plan/delivery_projection.py:11>)。这个函数使用 [overdue_calculations.parse_dt:7](</D:/Github/----/core/services/common/overdue_calculations.py:7>)，后者只接受秒、分钟或日期格式，没有 `%f`。原始字符串保留小数秒时无法匹配，5000 行区间因此全部被判无效。

这与候选本身允许小数秒的 [local_time:29](</D:/Github/----/core/models/workbench_run_candidate.py:29>) 不一致。`_schedule_completion` 发现无效区间后加入 `schedule_time_invalid`，使 `schedule_complete=false`；于是 `_finish_fields` 不给出候选完工时间，`_delivery_risk` 输出未知。[delivery_projection.py:64](</D:/Github/----/core/services/workbench/plan/delivery_projection.py:64>)、[delivery_projection.py:86](</D:/Github/----/core/services/workbench/plan/delivery_projection.py:86>)。

[candidate_analysis.py:27](</D:/Github/----/core/services/workbench/run/candidate_analysis.py:27>) 的 `after` 直接使用候选 workspace 的 `delivery_risks`，不是从基准推出来的。因此缺少正式基准不能解释或豁免候选侧完工、超期数和拖期总量也失效。`before`、调整工序数、换设备数及变化量在没有正式基准时未知是合理边界；候选侧合法时间被当作无效是另一个明确的产品问题。只出现“未知”文字且没有浏览器异常，不能判为完整功能通过。

### `part_label_missing` 是测试数据缺失，不是映射丢失

离线快照为 `C:\Users\lurenxing\AppData\Local\Temp\aps-win7-acceptance-20260926\target-db-snapshots\pressure5000-4df78c53-20260926-170959-728\aps.db`，SHA256 为 `fb7c61096972a71c7c39ece18c19b8896a7e59424e7289e76e2150da145c4f57`。受理归档 `facts_json` 的计算哈希与 `facts_hash` 一致。其中 100 个 `Batches.part_name` 全部为 NULL，当前数据库也相同；归档 `Parts.P1.part_name` 是 `Dense capacity part`。

这是合成种子的真实状态：[final_capacity_support.py:26](</D:/Github/----/tests/workbench/final_capacity_support.py:26>) 填写 Parts 名称，但它调用的 [RunCase.batch:18](</D:/Github/----/tests/workbench/run_compute_support.py:18>) 没有给 `Batches.part_name` 赋值。任务列表的 5000 个 `part_label` 均正确显示 `Dense capacity part`，因为 [candidate_tasks.py:58](</D:/Github/----/core/services/workbench/facts/candidate_tasks.py:58>) 从同一受理归档中的 Parts 取名；交付投影则明确采用归档 Batches 的历史名称，并在缺失时保留缺失标记，不猜测补齐。[delivery_projection.py:51](</D:/Github/----/core/services/workbench/plan/delivery_projection.py:51>)。

因此，交付页“名称未填写”和任务页有零件名来自两个不同但明确的归档字段，没有证据表明已有批次名称在传输或映射时丢失。也不能把这条测试数据缺失算成 Win7 字体或渲染错误。`part_label_missing` 在 `_schedule_completion` 返回后才添加，仅影响完整性标记；它本身不会使已有有效区间的 `schedule_complete` 变假。本例候选风险全未知的直接原因仍是小数秒解析失败。

### 修复与补验边界

前述时间精度规则应同时覆盖交付投影和汇总指标；不要只修正式采用入口。候选读取已经接受合法小数秒，交付分析不得使用不兼容的时间解析器，也不得为让页面有数字而截断或舍入任务时间。补验应覆盖单端/双端小数秒、跨日与交期边界、零时长点任务、合法但无法采用的候选、无正式基准时仍能计算候选自身指标，以及缺少批次历史名称时其他有依据的指标仍可用。

后续完整资料的交付分析用例应显式填写批次历史名称，同时保留本次原始失败数据和空名称边界；不得补写这份旧候选的受理归档来改写验收结果。本次仅核实根因并追加记录，未修改产品、测试、数据或虚拟机。

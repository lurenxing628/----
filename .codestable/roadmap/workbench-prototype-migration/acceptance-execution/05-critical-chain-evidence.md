# 实际甘特关键链真实接入

## 范围与授权

- 能力：`WBP-FG-011`，错误/不可用边界关联 `WBP-FG-012`。
- 修复前 `core/services/workbench/actual_gantt.py:114` 固定返回无引擎证据。这是产品未实现，不是样本覆盖不足。
- Main 明确允许复用原只读引擎；随后明确追加授权 `core/services/scheduler/gantt_critical_chain.py` 的 keyword-only 目标终点扩展。默认全局行为必须不变，不改 Greedy、SGS 或求解策略。
- 不使用原型静态 `computed-example`，不将 `graph_analysis` 的截断诊断样本冒充完整结果，不在 fixture 注入关键链结果。

## 已核实来源

| 来源 | 事实与边界 |
|---|---|
| `core/services/scheduler/gantt_critical_chain.py` | `compute_critical_chain_from_rows` 是原甘特只读计算器。全量明细构造工艺、设备、人员前驱，选择控制前驱，再回溯终点；不运行排产 |
| `core/services/scheduler/gantt_critical_chain_provider.py:187` | 原 provider 的正式/候选/场景路径已经实际调用此计算器。新的实际甘特适配不复用跨请求缓存，当前事务重新物化明细 |
| `frontend/workbench/prototype/ui_kits/workbench/field-gantt-current-chains.js:4` | 原型声明同一函数，但加载的是静态样例结果，只能作为能力与语义来源 |
| `core/services/scheduler/run/schedule_graph_report.py` | 是排产图分析/派工准备的另一条路径，其 diagnostics 中 critical_path 等有 sample/truncated 字段；本次不作为完整链数据源 |

## 调用合同

```python
compute_critical_chain_from_rows(rows, *, target_id=None)
```

- `None` 保持原全局终点、字段和计算规则。显式目标仍用同一完整 rows 构造控制图，只改变回溯起点。
- 显式空目标、未知目标、零时长/非法时间目标和冲突任务键分别返回 `target_invalid`、`target_not_found`、`target_time_unavailable`、`target_identity_conflict`。不回退到全局终点。
- `gap_minutes` 为 `(目标计划开始 - 前驱计划结束)` 向下取整的分钟。合并/并行工艺可能为负间隔，不改称实际等待。`makespan_end` 为该链终点的计划结束时刻，不是有效加工小时或剩余预测。
- 本域 `actual_gantt_chain.py` 在当前只读事务中核对同一 `plan_ref` 的全量原明细与已有任务引用，严格映射原引擎任务键。原引擎输入 rows 不按 hover 对象或当前筛选裁剪。
- `engine_evidence_ref` 绑定源函数、计划引用、计划内容指纹、目标任务和原结果；页面查询的 `snapshot_ref` 另绑定原计划与执行快照。
- `GET /api/workbench/v1/actual-gantt/chain` 要求原查询范围、`snapshot_ref`、明确 `target_task_ref`；输出区分 `global`/`related`。错快照拒绝，不读取“最新计划”替代。
- 页面任务 hover 请求该任务终点；资源/批次组 hover 选择该可见组计划最晚结束任务作为明确终点，再由后端在完整图回溯。它不是对组内 rows 重新造图。
- 共同工序与分件跨组依赖仍为原算法明确不支持。正时长与零时长点混合时标部分结果；全是点时不可用，不延长点、不补造边。

## 实际验证

- `/tmp/aps-final-e-drills.gcR8We/chain-backend-01.xml`：**53 passed / 1 deselected / 7.66s**。含 13 个本域/目标边界用例及原 normalize/provider/scope/unavailable 回归。deselected 是需要完整构建的单独浏览器用例，不是删除要求。
- 真实当前 factory 的五道计划明细推导出四节点全局链，边依次为工艺/设备/人员，间隔 `0/30/30` 分钟；另一个不在全局链上的独立任务，其真实 related 链为自身单节点。跨设备目标回溯仍包含其他设备的前驱。
- 本域测试核对全部数据库表无写入；修改本私有 fixture 计划结束时间后旧 token 拒绝，新内容指纹变化。异常返回 `None`、列表、字符串、整数不会触发未处理 `AttributeError`。
- `/tmp/aps-final-e-chain.6pMv2z/chain-browser-01.xml`：**4 passed / 3 failed / 120.72s**。现场完整流程、现场/实际甘特/报表只读往返通过；链全局开关、三边理由、实/虚线与连线独立开关通过，但关联 hover 被加载区高度变化反复触发鼠标离开而取消。保留失败现场 `aps-workbench-live-deemfeg0/final-chain-initial.json`，不算相关动作通过。
- 已将链区域固定为 160px，加载/结果不移动任务行；正在 `/tmp/aps-final-e-chain-stable.h5VxP8` 重跑完整入口与真实进程重启。当前文档不宣称最终通过。

## 同期结果

- `/tmp/aps-final-e-drills.gcR8We/drills-01.xml` 中校准图号打开现成只读零件详情、原模板定位、关闭原位返回、采用事务、文件字节及真实重启均已完成；整条测试仍因 `WBP-CALIB-002` 表头筛选/列宽未补而失败。
- 同轮复盘的三种事实下钻、设备/人员页签、资源名/柱下钻及精确返回已通过，数据库无写入。资源超过六组分页和 `WBP-REPORT-010` 跨页面定位仍待完成。
- Main 新的 `ResourceControls` 可见 Modal 文档滚动锁已在后续 fresh 全量构建中随真实源 manifest 验证，不沿用旧构建冒充最终 source proof。

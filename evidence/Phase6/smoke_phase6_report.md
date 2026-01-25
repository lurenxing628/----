# Phase6（Scheduler：批次/工序/日历/配置）冒烟测试报告

- 测试时间：2026-01-24 14:37:15
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 0. 测试环境
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase6_z_t9pebl`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase6_z_t9pebl\aps_phase6_test.db`

## 1. 准备基础数据（工艺模板/资源）

## 1.1 批次创建：模板缺失时自动解析 route_raw
- 自动解析：PartOperations=2 BatchOperations=2（期望均 > 0）

## 2. 批次创建事务：失败回滚（不留脏数据）
- 触发预期异常：code=1003 message=数据已存在，不能重复添加（唯一性约束冲突）。
- 回滚校验：BFAIL 批次存在=False（期望 False），BFAIL 工序数=0（期望 0）

## 3. 正常创建批次并生成工序（op_code 规则）
- 批次：B001 图号=A1234 数量=50 工序数=2（期望 2）
- op_code：['B001_05', 'B001_35']

## 4. 工序补充：内部工序（设备/人员/工时）
- 维护设备不可用：设备“MC002”当前状态为“maintain”，不可用于排产。
- 停用人员不可用：人员“OP002”当前状态为“inactive”，不可用于排产。
- 写入后：machine=MC001 operator=OP001 setup=0.5 unit=0.2
- 人机不匹配限制生效：人员“OP001”未被配置为可操作设备“MC003”（工序 B001_05 / ID=4）。请先在【人员管理】或【设备管理】中维护人机关联（OperatorMachine）后再排产。
- 清空后：machine_id=None operator_id=None（期望均为 NULL）

## 5. 工序补充：外部工序（合并周期限制）
- merge_hint：{'is_external': True, 'template_ext_group_id': 'A1234_EXT_1', 'merge_mode': 'merged', 'group_total_days': 3.0}
- merged 限制生效：该外部工序属于“合并周期”外部组，不能逐道设置周期。请在工艺管理中设置该组的合并周期（当前：3.0 天）。

## 6. 排产配置：默认值/更新/校验
- 默认：{'sort_strategy': 'priority_first', 'priority_weight': 0.4, 'due_weight': 0.5, 'ready_weight': 0.1}
- 更新后：{'sort_strategy': 'weighted', 'priority_weight': 0.4, 'due_weight': 0.5, 'ready_weight': 0.1}
- 权重总和校验：权重总和应为 1（或 100%）

## 7. 工作日历：upsert + 工作时间计算
- add_working_hours：start=2026-01-21 08:00:00 hours=3 end=2026-01-23 09:00:00（期望跨天到 2026-01-23 09:00）

## 结论
- 通过：Phase6（Scheduler 基础能力）冒烟测试通过（事务/工序补充/日历/配置）。
- 总耗时：1632 ms

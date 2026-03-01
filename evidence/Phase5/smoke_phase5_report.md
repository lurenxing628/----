# Phase5（工艺管理模块）冒烟测试报告

- 测试时间：2026-02-28 21:33:18
- Python：3.8.10 (tags/v3.8.10:3d8993a, May  3 2021, 11:48:03) [MSC v.1928 64 bit (AMD64)]
- 项目根目录（自动识别）：`D:\Github\APS Test`

## 0. 测试环境
- 临时目录：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase5_tgodyd9j`
- 测试 DB：`C:\Users\LURENX~1\AppData\Local\Temp\aps_smoke_phase5_tgodyd9j\aps_phase5_test.db`

## 1. Schema 检查（Phase5 相关表）
- 是否存在 OpTypes：True
- 是否存在 Suppliers：True
- 是否存在 Parts：True
- 是否存在 PartOperations：True
- 是否存在 ExternalGroups：True

## 2. 工艺路线解析器：预处理/识别/连续外部组
- 解析状态：success
- 统计：{'total': 6, 'internal': 3, 'external': 3, 'unknown': 0}
- 连续外部组数量：1（期望 1）
- 分隔符兼容（->/>/→）解析状态：success
- 分隔符兼容 operations：[(5, '数铣'), (10, '钳'), (20, '数车'), (35, '标印')]

## 2.1 工艺路线解析器：边界用例（validate_format/重复工序号/未识别工种）
- validate_format(空)：ok=False msg='工艺路线不能为空'
- validate_format(无工序号)：ok=False msg='格式无效：必须以工序号开头'
- validate_format(正常)：ok=True msg='格式有效，识别到 1 道工序'
- 重复工序号解析状态：partial
- 重复工序号 warnings：['工序号 5 重复出现，将保留第一个']
- 重复工序号 operations：[(5, '数铣'), (10, '数车')]
- 未识别工种解析状态：partial
- 未识别工种统计：{'total': 2, 'internal': 1, 'external': 1, 'unknown': 1}
- 未识别工种 warnings：['工种“未知工种”未在系统中配置，已默认标记为外部工序']

## 3. 零件模板保存：解析后写 PartOperations + ExternalGroups
- 保存后解析状态：success
- 工序数量：6（期望 6）
- 外部组数量：1（期望 1）
- 外部组ID：A1234_EXT_1

## 4. 连续外部工序合并周期：separate/merged 存储规则
- 切换 merged：merge_mode=merged total_days=3.0
- 组内 ext_days：[None, None, None]（期望均为 None）
- 切换 separate：merge_mode=separate total_days=None
- 组内 ext_days：[1.0, 1.0, 1.0]（期望均有值）

## 5. 外部工序删除规则：中间外部组禁止，尾部外部组允许
- 中间外部组删除：code=5004 message=不允许删除：仅首部/尾部连续外部工序组可删除，中间外部组不可删除。
- 尾部外部组删除：{'message': '可以删除', 'deleted_seqs': [15, 20], 'result': 'allowed'}
- 删除后外部组剩余：0（期望 0）
- 删除后外部工序剩余：0（期望 0）

## 5.1 外部工序删除规则：首部外部组允许
- 首部外部组删除：{'message': '可以删除', 'deleted_seqs': [5, 10], 'result': 'allowed'}
- 删除后外部组剩余：0（期望 0）
- 删除后外部工序剩余：0（期望 0）

## 5.2 外部工序删除规则：全部外部工序（warning 分支）
- 全部外部工序删除：{'message': '删除后将没有任何工序，确定继续？', 'deleted_seqs': [5, 10], 'result': 'warning'}

## 结论
- 通过：Phase5（工艺管理模块）冒烟测试通过（解析器/边界用例/模板保存/合并周期/删除规则）。
- 总耗时：1108 ms

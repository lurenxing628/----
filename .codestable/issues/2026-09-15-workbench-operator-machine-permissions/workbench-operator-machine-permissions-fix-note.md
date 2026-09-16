---
doc_type: issue-fix-note
status: fixed
date: 2026-09-15
title: 人员可操作设备编辑与排产资格闭环
roadmap_item: wbfix-operator-machine
---

## 范围与结果

执行总方案 5.5/B1。人员详情新增“编辑可操作设备”，支持查找设备、添加/解除关联、技能等级和主操设备修改。使用完整目标关系集合预览，展示新增、解除和字段变化；确认保存复用工作台命令回执、单事务和既有 OperatorMachineService。

“解除关联”仅移除人员设备关系，不删除设备；ResourceForms 的真正删除入口、确认按钮、删除弹窗图标统一为 trash-2 并保留文字。其他页面的删除由共享控件分工统一处理。

## 合同与数据保留

- 详情 `relationships.machine_permissions` 返回全部关联的永久设备引用、编号、名称、原始 skill_level 和 is_primary。普通列表与高级筛选列表使用同一授权快照形状，不产生可读却无法保存的不同上下文。
- `POST /entities/operator/<ref>/machine-permissions/preview` 接收完整目标集合和原人员编辑 token。预览前校验旧编辑上下文，防止页面打开后新增的隐藏关系被无意移除。
- 确认输入仅 `preview_ref`；使用 `operator.machine_permissions` 命令在 BEGIN IMMEDIATE 内重读人员、设备和完整旧关系，预览失效时整笔拒绝。预览只读；失败时关联和回执一起回滚。
- 继续使用 `OperatorQualificationService` 和原排产资源池；新增技能不会自动授予设备权限，编辑姓名/技能不会改设备关联。移除关联影响之后的资源分配，既有计划、批次工序及开工事件原样保留。
- 同一目标集合最多一台主操；新增或改变的字段只允许现有枚举。`preserve_unchanged=True` 只保留与该行当前原值相等的字段，不放宽新增/改值校验。主操切换只更改需要改变的主操行，避免把未编辑的旧格式/空值改成默认值；原记录 id 和 created_at 保留。旧调用默认行为保持不变。
- 没有修改数据库结构，没有写真实业务数据库。没有运行迁移或清洗旧授权。修改基于已有 dirty 工作区，未提交。

## 文件

- 新服务：`core/services/workbench/operator_machine_permissions.py`。
- 路由：`web/routes/workbench/operator_machine_permissions.py`，由 resource_actions 注册。
- 状态/投影：resource_states、resource_table_states、resource_projection。
- 既有服务兼容扩展：`core/services/personnel/operator_machine_service.py`。
- UI：`OperatorMachinePermissions.jsx`、ResourceForms、ResourceWorkspace；作用域样式在 styles/31-batches-resources.css。920px 弹窗避免默认 580px 挤压设备名称、选项和操作文字。
- 传输：resource-api 的 operator.machine_permissions 分支，pending 继续保存人员永久引用和操作编号，不保存写 token。
- 构建入口由主代理统一加入 build-order；组件必须早于 ResourceWorkspace，Feedback 由宿主传入，避免反向依赖 ResourceForms。

## 验证

1. `.venv/bin/python -m pytest tests/workbench/test_resource_api.py tests/workbench/test_resource_entities.py -q`：254 passed。
2. `.venv/bin/python -m pytest tests/workbench/test_operator_machine_permissions.py tests/workbench/test_operator_qualification.py tests/workbench/test_resource_table_domain_pairing.py tests/excel_data_io/test_operator_machine_exception_paths.py tests/excel_data_io/test_operator_machine_detail_readside_normalization.py -q`：97 passed（此批运行时新授权文件为 10 项）。
3. 最终 `.venv/bin/python -m pytest tests/workbench/test_operator_machine_permissions.py tests/workbench/test_operator_machine_permissions_widgets.py tests/workbench/test_resource_transport.py -q -s`：13 passed；其中授权 SQL/API 11 项、组件 1 项、传输 1 项。
4. 新组件在 Chromium109、1392×924 与 1280×720、明暗主题四组完成添加、主操切换、解除、完整集合预览和确认；保留旧枚举值，确认后禁止重复修改。截图已人工查看，宽度内无水平溢出，操作文字可见。组件使用 mock adapter，不冒充真实数据库手动验收。
5. 新 Python 文件与服务改动可按 Python 3.8 语法解析。用户随后明确严禁运行全质量门禁；统一构建及真实浏览器手动综合验收由主代理执行，不在此声称通过。

截图及组件结果：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-permissions-controls-qsl46e_k/`。

## 删除反馈补充修正

主代理手动验收发现资源删除成功却显示“保存已完成”。ResourceForms.Feedback 现在按显式 action 或 command.intent.kind/action 区分动作；单条删除、资源/工艺批量删除及对应恢复查询使用“删除”，不根据按钮中文或结果里的名称猜测。人员设备关联保存、解除关联和日历配置清除保留各自动词。结果为 unchanged 或 partial 时不声称全部删除成功。

ResourceForms 表单显式传当前动作；ResourceWorkspace 外部结果保留 delete/import/save 动作标记，在只有回执没有 intent 时也能准确显示。批次批量确认兼有更新、复制与删除，由 BatchForms 预览显式传删除/保存动作；恢复场景按后端已有回执 data.action 字段区分，尚未取得回执时仅称“批次操作”，不猜动作。

仅运行 `.venv/bin/python -m pytest tests/workbench/test_resource_feedback.py tests/workbench/test_resource_transport.py -q`，2 passed。新反馈测试编译当前 JSX，覆盖至少 30 个动作/状态判断，无浏览器、数据库、构建产物写入；未运行全门禁。

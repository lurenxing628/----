---
doc_type: feature-design
feature: wb-process-template-workflow
status: approved
created: 2026-09-09
summary: 保持原型三步布局，接入真实工艺身份、解析预检、逐序确认、工时与文件事务
tags: [workbench, process, persistence]
roadmap: workbench-prototype-migration
roadmap_item: wb-process-template-workflow
approval_basis: 已批准总体迁移与D06，本项在原工艺能力范围内实施
---

# 工艺模板三阶段

## 0. 术语与来源

沿用总体合同的EntityRef、WriteContext、CommandInput。template_operation_ref指实际PartOperations行的持久身份，不是批次operation_ref；template_external_group_ref指模板外协组，不是排程资源组。来源见PartService、RouteParser及原型plana-logic.js的三步、路线录入和工时页面；完整能力仍为WBP-PROC-002/004..012/021/022与工艺相关的SH-007、DETAIL-002。

## 1. 范围与约束

- 交付真实零件搜索/阶段/分页/逐列表头、选择/批删、新增、三步详情、两种路线录入、逐序归属及待建工种、定额工时、路线/工时CSV和XLSX导入导出。不是只读页或旧模板换皮。
- 复用现有解析器和领域保护，不直接调用删除重建式reparse_and_save冒充阶段确认。原有工序、外协组、自制工时和隐藏字段必须先读出差异，未经明确操作不覆盖。
- 存量source/0工时不构成人工确认记录；无确认记录明确显示未确认，现存模板的旧领域使用规则不因GET改变。新增未完成工作流不能绕过阶段条件自动补建模板。
- 小时为有限非负数，明确0保留并提示复核，空值不填0；外协使用真实正数周期，缺失不自动填1天。不能把逐序自制/外协选择改成全局工种类别修改。
- 明确不做：不改排产算法，不反写已有批次/计划，不提前退役旧页，不伪造确认人/时间/历史建议，不恢复原型没有的旧高级选项。

## 2. 编排与挂载

现状：part已有永久引用；模板工序和外协组没有。普通创建、解析、逐条工时保存不是一个完整工作流事务。界面目前工艺节点尚未接入。

```text
模板永久引用 -> 真实列表/详情/存量状态
  -> 文字或逐行输入 -> 服务端只读解析、完整差异与错误
  -> 路线确认 -> 逐序归属确认及未知工种建档 -> 工时确认
  -> 真实可用模板/阶段审计 -> 批次使用同一模板事实源
  -> 文件预检/原子确认/同范围导出 -> 复杂浏览器及保留验证
```

- `core/infrastructure/workbench_process_schema.py`独立提供模板身份对象和安装合同，编号与schema.sql由主代理统一集成。普通GET不补引用，缺失明确失败。
- `GET /api/workbench/v1/entities/part`及`.../<part_ref>`读取统一Entity形状和workflow投影；内部行号、revision不出现在普通DTO。
- `POST /api/workbench/v1/process/<part_ref>/route-preview`为只读JSON，`{mode:"text",route_raw}`或`{mode:"rows",rows:[{seq,op_type_name}]}`；预检返回识别、未知、诊断和旧模板差异。预检不调用创建/重解析/保存。
- 同一读事务包含Parts、模板工序/外协组、工种、供应商及v21能力关系；并发关系变化使旧快照失效。后续确认复用命令回执服务，不能把多个独立POST当成一次保存。
- 视图通过ResourceWorkspace.renderPart挂入现有产能链，保持原型表格/三段进度和居中详情。全部交互沿已统一的公共控件；未挂接写动作明确不可执行，不回退内存样例。

## 3. 验收契约

- v21升级后所有旧业务行/字段不变；模板引用重启稳定、删除重建不复用、同号重建不指错对象、读请求零写入。
- 列表过滤排序在分页前，计数/表格/导出同范围；失效、空值、坏资料不猜正确值。未知工种、重复/非法序号、尾部缺名必须有明确诊断。
- 取消及预检零业务写入；阶段确认与回执同事务，失败回滚，超时按原请求键核实；重导不覆盖已有人工确认和未展示外协规则。
- 两种尺寸、浅深主题逐项输入/点击及截图；2000/10000工序规模，完整CSV/XLSX字节与范围校验；旧批次、计划、设备授权等无无意修改。

## 4. 依赖与推进

资源实体、供应商能力、引用/命令协议已完成本项需要的基础合同。资源feature尚未结束的物料引用零件、设备/人员计划导航依赖本项或计划项，属于后续跨页验收，不阻塞本项基础接入；它们仍保留待验，不能将资源feature假标done。总体19项范围与最终完整门禁不变。

## 5. 阶段接入细化

- 显式确认存入v23的`WorkbenchProcessWorkflow`、`WorkbenchProcessOperationConfirmations`；按永久零件/工序引用和实际字段签名重验。未经过此工作流的存量保留旧使用规则；进入工作流后，前一步未确认或事实变更则不能生成新的批次工序。没有真实确认人时保存null，不伪造姓名。
- 当前命令入口为`POST /process/<part_ref>/route_confirm`、`source_confirm`、`hours_confirm`，外层统一`CommandInput`。路线确认必须使用当前路线预检的令牌；归属确认先经`POST /process/<part_ref>/stage-preview`只读检查；工时确认使用当前详情令牌。前两者绑定准确输入，解除外协组的勾选不改变已预检的路线/归属内容。
- 路线及归属预检返回`affected_groups`完整原规则。只有明确提交准确的`discard_group_refs`才能解除受影响的外协组；未涉及的工序身份、人工字段、组周期及备注保留。
- 逐行输入是结构化序号/名称，名称含空格或数字时保留原值，不再为了旧整条文字解析而删改或拒绝。整条文字有歧义仍阻止确认，提示改用逐行输入。
- 合并外协组以正数总周期为权威；其成员原有逐序周期可为空或正数，不能强迫补造逐序周期。非合并外协序仍必须填写正数周期；自制单件0需要明确复核，换型0正常保留。
- 阶段输入上限10000条，路线预检仍2000条/256 KiB；HTTP阶段载荷上限4 MiB，超限明确拒绝。页面工序分页只限制当前渲染量，不缩小保存范围或丢弃非当前页草稿。

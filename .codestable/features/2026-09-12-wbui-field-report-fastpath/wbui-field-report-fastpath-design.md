---
doc_type: feature-design
feature: 2026-09-12-wbui-field-report-fastpath
status: approved
summary: 报工建议时间、受限复制、确认后自动重读和连续报工，接入共享字段和草稿保护。
tags: [workbench, ui, execution]
roadmap: workbench-ui-refinement
roadmap_item: wbui-field-report-fastpath
---

## 0. 术语约定

“上一条”仅指同任务、同工序、当前有效逐次报工中的最近实际完工记录。“建议时间”只用于新建，明确标注，可编辑和清除；空白仍作为未知写入，不补造事实。

## 1. 决策与约束

依据用户批准的 implementation-20260912.md 实施。复杂度中等，保留 FieldContract 的领域输入白名单与 APSResourceSession 原请求状态机。仅改 Field 前端域、对应 CSS 和测试，不改领域 API、台账规则、分页档位。

## 2. 名词与编排

### 2.1 名词层

现状：FieldEditor 使用 FieldContract.draft，数量和时间可留空；FieldWorkspace 按任务缓存编辑草稿。变化：FieldDraftModel 生成可清除建议和复制字段白名单；retained 保存原始草稿基线及建议标记，例如 actual_start=上一条有效完工、actual_end=本机当前时间。

### 2.2 编排层

新建 → 建议提示/用户核对 → 原请求提交 → sending/pending 保留 → done → 自动重新读取任务 → 新 write_context 核验 → 可继续新建。普通保存也自动重读。补齐、更正、旧完工事实和 retained 不应用新时间默认值。拒绝、待核实、重读失败、任务变更或工序已完工均不打开下一张草稿。

### 2.3 挂载点

FieldEditor 负责表单与完成意图；FieldWorkspace 负责所有已缓存草稿守卫与重读编排；FieldDetail 从新查询结果核验下一张草稿条件。FieldTable/FieldFilters 使用共享空态、分页和格式展示。已选详情位于任务表及分页器之后的独立全宽区域，避免编辑器被表格滚动高度裁住；打开后自动滚入可见区域。

### 2.4 推进策略

先锁住草稿和输入合同，再接 UI 与重读状态，最后编译、定向测试与主线程统一浏览器验收。

### 2.5 结构健康度

独立 FieldDraftModel 承载建议/复制/继续条件，避免把 UI 便捷规则并入领域接口；独立 FieldEditorFields 承载表单呈现。样式归 styles/35-field.css；不增加后端能力。

## 3. 验收契约

- 新建时间有可见来源提示和清空按钮；清空后提交 null。补齐、更正、retained、legacy 不自动填时间。
- 上一条不跨任务/工序；复制仅保留可编辑业务值，不携带身份、版本、请求键和旧 write_context。
- 非法数量/时间、时间倒置、补齐修改已知事实显示对应字段错误并聚焦。
- done 后自动重读；pending 不生成新请求；继续仅接受不同的新 write_token、相同任务工序且仍可 create。
- 所有任务缓存草稿参与离开守卫，取消明确确认；命令 pending 不允许离开。
- 1280/1366 宽度下表格内部滚动、吸顶表头、操作列可达；分页档位保持 10/20/50/100。

## 4. 项目文档关系

主线程统一回写 UI 路线图、当前架构和需求，子任务仅记录实际实现和定向证据。浏览器截图与 build_id 使用本轮统一构建，旧验收截图不复用为当前通过证据。

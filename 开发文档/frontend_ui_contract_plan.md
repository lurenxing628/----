# 前端 UI 设计语言收口执行说明

## 1. 为什么要做这次收口

当前前端不是单个页面不好看，而是新旧 UI 写法混在一起。旧的 `base.css` 还保留按钮、表单、表格、标签、提示条等基础样式；新的 `ui_contract.css` 又承担设计规范、暗色主题补丁、页面级修补和排产页专用布局。继续靠页面选择器补样式，会让 `ui_contract.css` 越来越像临时补丁仓库。

本轮目标是把已经形成的 UI 契约继续下钻成更稳定的 token、基础类、组件宏和 viewmodel 展示数据，让模板少做判断，页面少写临时结构。

## 2. UI 分层

本仓库前端按四层理解：

- Design Tokens：颜色、间距、字号、圆角、阴影、状态语义、暗色主题。
- Primitives：按钮、输入框、表格、卡片、标题、链接、标签、只读值。
- Components：Page Hero、Card Header、Notice、Empty State、Summary Grid、Toggle Row、Table 类型。
- Feature Composition：排产执行、排产配置、系统备份、系统日志、物料批次、Excel 导入等业务页面。

新增样式时先判断它属于哪一层。能用 token 表达的，不写组件硬编码颜色；能用组件表达的，不写页面 ID 样式。

## 3. 模板规则

- 不新增业务状态判断型 `{% if status == 'xxx' %}` / `{% elif ... %}`。
- 允许保留必要渲染条件，例如有数据/无数据、可操作/不可操作、是否显示分页。
- 状态文案、状态 tone、勾选属性、禁用属性优先由 viewmodel 产出。
- 模板只消费 `label / value / desc / tone / checked_attr / disabled_attr / items`。
- 不在模板里用 `.get(key, "未知")` 或 `.get(key, "-")` 悄悄兜底未知业务状态。
- 布局组件可以允许“没有按钮”“空列表”这类可选内容为空；这不等于允许业务状态、错误原因、展示文案在模板里悄悄兜底。
- 业务页面原则上只调用 `ui.toggle(toggle)`，也就是消费 viewmodel 已经算好的 `UiToggleRow`。
- `ui.toggle_row(...)` 只给底层组件和测试夹具使用；业务模板不要直接传 `checked_attr`、`disabled_attr`、`submitted_value`，避免把开关提交规则重新散落到模板里。

## 4. 表单规则

开关类表单字段必须保持这个顺序：

```html
<input type="checkbox" name="xxx" value="yes">
<input type="hidden" name="xxx" value="no">
```

原因是后端多处使用 `request.form.get(...)` 读取同名字段。checkbox 在前、hidden 在后时，勾选状态能读到 `yes`；顺序反过来时，勾选也可能读成 `no`。

禁用开关要特别处理。浏览器不会提交 disabled checkbox，所以禁用且已勾选的开关必须让同名 hidden input 提交当前真实值，不能默认提交 `no`。

## 5. 表格规则

表格按内容模型加类型类名：

- `aps-table--fixed`：普通列表，单行、省略号、稳定列宽。
- `aps-table--multiline`：日志、错误、详情类表格，允许多行换行。
- `aps-table--editable`：单元格里有 input、select、button、form。
- `aps-table--actions-nowrap`：操作列不换行。

表格内的一行轻量开关可以保留原生 checkbox。比如扩展功能状态表这类“一个单元格内有 checkbox、保存按钮和说明”的紧凑操作，不强制套页面级大 toggle；但表格本身要用 `aps-table--editable` 这类内容模型表达它是可编辑表格。

表格列宽合同必须保留：

- `data-col-resize="1"`
- `data-table-key="..."`
- `data-col-key="..."`
- `data-default-w="..."`
- `data-min-w="..."`

## 6. 暗色主题规则

暗色主题优先覆盖 token，不优先覆盖具体组件。只有组件确实有无法通过 token 解决的特殊结构时，才写组件级暗色补丁。

本轮禁止引入这些 Chrome 109 不稳定或不支持的写法：

- `:has()`
- CSS nesting
- `color-mix()`
- `oklch()` / `lab()` / `lch()`
- `subgrid`
- `@scope`

## 7. 测试规则

本轮先稳住静态合同测试和质量门禁，不把浏览器几何测试强制加入门禁。新增 UI 基础能力时，要补测试锁住：

- tone 只能是 `neutral / info / success / warning / danger`。
- `checked_attr` 只能是空字符串或 `checked`。
- `disabled_attr` 只能是空字符串或 `disabled`。
- checkbox 必须在同名 hidden input 前面。
- 日志表多行换行要靠 `.aps-table--multiline`，不靠 `#systemLogsTable td` 页面 ID 特例。

Codex 浏览器插件 smoke 属于本地人工验收：用于确认真实页面没有明显横向撑破、开关文字没有压住轨道、暗色主题下主要提示和摘要仍可读。它不写进 `tools/test_registry.py`，也不新增仓库级浏览器依赖。

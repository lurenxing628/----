---
doc_type: issue-fix-note
status: fixed
updated: 2026-09-09
scope: 资源详情布局与资料重新核对提示
---

# 资源详情与操作提示

## 根因与修复

- `ResourceForms.jsx` 原 `CurrentFields` 按后端字段插入顺序渲染，直接使用编辑表单网格，并把所有数字右对齐。导致备注先于规格、库存与单位分离、数字靠近相邻列。现在按照字段定义排序，以只读 `dl/dt/dd` 展示；物料库存与单位同组，备注全宽后置。
- 编号、名称及状态明确分组，长内容自动换行；使用现有主题色和轻分隔线，不加嵌套卡片、白色高亮边框或额外阴影。已有关系、旧状态、设备授权、问题提示及读取时间继续显示。
- 资料审阅改用中性底色，提示已填写内容保留；两个按钮统一为“重新读取最新资料”“已核对，继续编辑”。同类目录、日历和后端错误消息一并去掉“上下文”等内部表达，未改内部标识、token、请求类型、校验或合并规则。
- `ResourceControls.jsx` 修复共享弹窗底栏被 `wb-actions` 自动左边距收窄的问题，使按钮区背景与分隔线覆盖整个弹窗。

## 修改范围

- 主修：`frontend/workbench/app/ResourceForms.jsx`、`ResourceControls.jsx`。
- 文案：同目录 `resource-contract.js`、`ResourceWorkspace.jsx`、`ResourceMaterialActions.jsx`、`ResourceCatalog.jsx`、`ResourceMaterialContract.js`、`CalendarDayDialog.jsx`。
- 后端仅消息：`web/routes/workbench/write_context.py`、`materials.py`、`calendars.py`；`core/services/workbench/commands.py`。
- 新增：`tests/workbench/resource_detail_layout_probe.cjs`、`test_resource_detail_layout.py`。
- 同步现有测试：`resource_forms_probe.cjs`、`resource_stock_modal_probe.cjs`、`resource_table_live_probe.cjs`、`resource_conflicts_probe.cjs`、`catalog_widgets_probe.cjs`、`calendar_widgets_probe.cjs`、`material_actions_widgets_probe.cjs`、`resource_file_widgets_probe.cjs`。
- 构建输出为 `static/workbench/`，仍有 78 份本地 payload；原型源文件未修改。

## 验证

- 最终构建：`850ac61126e77448dd343bd84c5dc74182dd58fdcca261f9baff8888f497615c`，目标仍为 Chrome 109，没有新增依赖或外部资源。
- 新布局：Chromium 109.0.5414.46，1920x1080 与 1392x924、深浅色四组合，48 场景、1068 断言、96 截图通过。涵盖五类资源、字段乱序、长内容、库存零值/未知、关系与历史字段、主题文字对比、底栏全宽及新建审阅保留输入。此项为内存组件夹具，不冒充真实数据库证据。
- 真实 Flask + 隔离数据库：`test_resource_live_browser.py` 224 场景、1260 次命令请求、464 截图通过；测试结束后种子业务数据恢复一致，命令回执逐项核对、备份和模板不变、无隔离违规，测试服务正常退出。
- 主线程手动操作实际 Chromium 109：两种桌面窗口和主题下查看 MAT-001；在新建及编辑中填写名称、重新读取、确认核对、取消，确认输入仍保留，未点保存。截图在 `output/playwright/resource-detail-20260909/`。
- 表单组件 84 场景、库存/弹窗组件 92 场景、详情导航 24 场景、资源文件组件 204 场景通过。另有目录 52、物料操作 68、日历四组回归通过。
- 后端针对性 pytest 175 项通过。资产/入口/详情/文件联合测试 35 通过、1 项缺浏览器环境跳过；随后带实际浏览器重新运行资产文件，18 项全部通过，包含原跳过项。上述范围重叠，不相加作为整仓用例总数。
- 首次重跑旧表单 probe 时，发现它漏加载已新增表头/关联组件，且用 `textContent` 读到了内联样式。已补齐测试依赖，改为可见文字及标题定位，最终 84 场景通过；没有为旧断言改变产品行为。失败报告保留。

## 交付边界

- 本轮新开两个子代理，文案修复与布局回归并行，均已完成并关闭。
- 新隔离预览：`http://127.0.0.1:51733/workbench?view=process`；原 `52155` 预览保持运行，未刷新或清理其用户输入/数据。已请求应用打开新预览，工具返回 queued。
- 新预览 PID 76417，根目录 `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-live-eyjwwim0`；中间验证预览 58801 已停止，文件保留。
- 证据归档：`output/workbench-migration/verification/resource-detail-language-20260909/verification-manifest.json`。
- 全部修改未提交；保留工作区已有脏改和他人暂存。未运行整仓质量门禁，未验证 Win7 真机，不是 clean-worktree proof。当前整体后端迁移任务仍未完成，本记录仅关闭这两项界面反馈。

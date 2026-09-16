# 共用控件与全页面删除图标实施记录

- 范围：用户批注 1、2、4、6、13 及最新“所有页面删除都统一垃圾桶”；保留关闭、取消、缩小、清除选择、解除关联的原语义。
- 当前状态：产品源实现和专项组件验证已完成；生成静态资源、组合门禁与最终手动验收由主代理统一集成，不能将本记录当作全功能通过。
- 起步工作区已有 545 项未提交内容。本条未提交、未改真实数据库、未直接编辑 `static/workbench/`，未修改冻结原型或其 manifest。

## 实现

1. `ResourceControls.jsx` 提供唯一 `trash-2` 本地 SVG，补 `chevron-up`、`arrow-left`、`copy`、`filter` 的缺失图形。已有 `chevron-down` 使用本地图标表；关闭 `x`、缩小 `minus` 保留。
2. 共享 Search 带真实搜索 SVG；工序搜索和排产批次搜索接入。齐套筛选改为独立标签/输入组，刷新范围保留可见文字。
3. `styles/20-controls.css` 统一 linkbtn 图文对齐及筛选、搜索几何；`21-table-frame.css` 为 `.wb-table--editable` 提供竖向分隔和 36 px 输入高度。
4. `ProcessStageEditor.Groups`、`ProcessRouteEntry` 改成单层 frame 直接包 table，接入 sticky 表头。删除已失去调用者的逐行核对提示函数 `unconfirmed`。
5. 基础资料、物料、目录/班制、工艺、批次、路线逐行、系统备份的单行、批量及确认删除使用垃圾桶和可见“删除”。`SystemMaintenanceControls` 原来错误地把 `trash-2` 映射成 `x`，已移除这条映射。
6. `ProcessWorkspace`、`BatchDetail/BatchForms`、`ResourceForms` 由各领域代理同步修改，跨文件盘点已纳入它们的结果。

## 全页面范围证据

- [删除动作声明清单](shared-controls-delete-inventory.json) 是当前 app 源码中的 **17 处动作声明**，不是运行时按钮总数；资源类别、列表行和弹窗会复用这些声明。
- 系统管理的“管理样例”当前可达：`SystemLive.jsx` 的数据来源单选和 sample 分支显示 `SMRecords`。该样例中禁用的“删除备份”也已使用垃圾桶，专项浏览器测试直接渲染该组件验证，并未把它当作真实删除能力。
- 冻结原型中的 `SMDisabled`、`SMRecords`、`SMConfiguration` 迁到现行 `app/SystemSampleControls.jsx`，保持样例数据行为。三者同模块，避免 foundation 反向依赖后加载的 app。主代理须移除 build-order 中这三项旧 foundation declarations，并将新模块排在 `SystemLive.jsx` 之前、`ResourceControls.jsx` 之后。原型快照不改。
- `web/routes/workbench/legacy_page_contract.py:9` 明确登记旧 GET 入口；`legacy_dispatch.py:84` 校验并替换已注册处理器。旧设备、人员、物料、工艺、批次、系统页面走重定向或退役展示，不能把不可达原型按钮计入现行页面。
- 全部现存 `templates/**/*.html` 已盘点，无删除控件。保留的说明书、打印、旧导入结果页面分别是 `templates/workbench/manual.html`、`print.html`、`legacy_result.html`，动作是返回/下载/打印/确认写入，没有遗漏仍可点击的旧删除按钮。
- 本条未改“移除外协选择”“缩短班制末尾天数”“清除日历配置”“报工撤销”等不同语义操作。

## 专项验证

- `.venv/bin/python -m pytest tests/workbench/test_shared_controls_widgets.py tests/workbench/test_workbench_delete_icons.py -q -s`
- 最终专项结果：`2 passed in 12.70s`。组件截图与输入哈希：`/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-workbench-shared-controls-0phdb4q0/`。本条文件的 `git diff --check` 通过。
- `shared_controls_probe.cjs` 使用当前源独立编译，Chromium 109，15 个组件合同：非空图标、备份及样例禁用删除、关闭/缩小不变、图文居中、工序搜索图标、齐套标签间距、单层滚动/编辑列竖线，以及原有无障碍/焦点/草稿保护。
- 齐套布局覆盖浅/深主题 × 1392×924、1366×768、1280×720，生成 6 张截图。fixture 同真实 main 挂载 `WorkbenchControlStyles`；否则 select/summary 的 SVG mask 变量未初始化会产生假黑方块，不能据此判断真实页面图标缺失。
- 删除 AST 合同遍历所有 app JSX，验证可见删除动作采用共享垃圾桶且保留可见文字，含描述表生成的批量动作。它是声明覆盖检查；真实浏览器只对上述专项组件交互与几何提供证据，最终仍须在集成页面人工回看。
- 定位：已调用 `python3 -m tools.symbol_locator whereis ResourceControls`，该工具未索引此 JSX 符号；随后用 `rg` 和 Babel AST 明确调用点。没有将定位失败伪称完整静态调用链证明。

本记录只说明当前脏工作区的源代码与专项验证，不提供 clean-worktree proof、Win7 真机证明或全功能验收结论。

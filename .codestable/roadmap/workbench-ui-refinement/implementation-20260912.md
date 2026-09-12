# 2026-09-12 并行实施与验收协调

用户已授权：按审查意见修订并并行实施整个路线图，持续完成验证。导航分组、术语和视图合并采用主文档默认方向。Win7 发布、旧界面退役、领域 API 和业务规则仍不在本次范围。

## 已固定的实施前现场

- HEAD：`afc0551ed15ac0d8aceca63f1d950ebe8f9b0e8b`。工作区原有调度优化改动，包含他人暂存内容；本轮不得覆盖、暂存或提交它们。
- `/tmp/aps-wbui-implementation-20260912/` 保存初始状态、tracked diff、474 个源文件的哈希及源归档，另保留原审查 69 张截图。该截图是历史审查素材，不冒充完整当前版本基线。
- 所有工作区编辑开始前，验证任务负责冻结当前构建并采集可重跑的当前基线；后续证据注明源码及 build_id。

## 对草稿合同的批准修订

1. 分页只统一呈现。`Pager` 的 `sizes` 由消费者显式传入，遵守各领域 API；游标分页使用独立模式，不虚构 total/pages。
2. `WorkbenchFormat.dateTime/date` 处理工厂本地文本；新增 `instant(value, {seconds=false})` 处理明确带时区的时刻并显示本机本地时间。不能把 UTC 截成本地文本，空值与非法输入仍分开。
3. `WorkbenchGuards` 必须覆盖 SPA navigate、同文档前进后退、表单关闭/取消及外部离开。拒绝离开时 URL/视图/草稿一致；确认弹窗不再触发自身守卫，多编辑器按作用域登记。业务命令 pending 状态沿用既有保护。
4. 表格采用有视口高度预算的内部滚动框，表头相对该框 `top:0`，关键列和操作列固定；不能在自然高度 overflow 容器中期待表头跟随整页吸顶。页面布局采用同一策略后验证双向滚动。
5. 基线采集先于修改；几何探针先测量，再逐条启用阻断。每个暂未修复的断言必须有 owner、对应条目和移除条件，最终验收不保留豁免。几何验证同时覆盖局部裁切、重叠和点击可达，不能仅看根页面宽度。
6. 新的工作台几何检查采用独立、显式的本地验收/门禁入口；不得默默改变既有旧页面真实浏览器 smoke 的 manual/CI skip 合同。应提供 daily gate 的显式 opt-in 调用并在本轮实际执行，默认无浏览器机器的现有 gate 政策保持可解释。
7. 导航 `nav_groups/view_aliases/help_url` 共三个 boot 字段。帮助优先复用现有只读手册 URL。菜单渲染期望可派生，15 个支持视图和旧 URL/context 的可达性独立锁定；12 项菜单不等于删除 3 个视图。
8. 计划默认选择只在没有显式计划/恢复上下文时执行，失败不改选当前正式；实际甘特仅改显示视窗，保留 axis_span/as_of/点工序语义，最小命中区域不伪造持续时长。
9. 报工默认时间作为用户可见、可清除的建议，仅用于新建；不覆盖补齐、更正或已保留草稿。“上一条”为同任务同工序有效报工；复制不携带引用、版本、请求键。保存并继续只在回执确认且重读取到新 write_context 后启用。
10. 每项验收记录本次源码/build_id、受影响工作区与需重跑的动作；旧截图和旧点击记录不能自动升级到新版本。最终统一构建、浏览器验证与质量门禁后回写真实状态。
11. 格式层不新增业务取值约束：percent只接受有限数值并乘100显示，是否允许负值或超过1由原DTO/领域校验决定，避免合法利用率被显示层拒绝。
12. 禁用原因默认可见：共享Button的reasonDisplay默认inline；显式title只供同处已有可见原因的消费者。最终几何检查覆盖原因文本加入后的布局，不能只实现新prop而让旧调用继续只靠悬停。

## 并行所有权

主线程负责本路线图、items 状态、集成计划、`build-order.json` 的 live 登记、统一构建产物、质量门禁、最终报告和跨任务争议。

- 样式基座：build.py/构建辅助与清单合同、app/styles 基础层、WorkbenchControlStyles；不改业务 JSX。
- 导航：main.jsx/WorkbenchNavigation.js/pages.py/导航测试；同时集成 Guards API。
- 共享控件：ResourceControls/ResourceForms/WorkbenchControls、Field/EmptyState/Pager/DetailPanel；集成 Modal guard。
- 草稿守卫：WorkbenchGuards 及 Trial/Process 编辑器接入；main/ResourceControls 的集成由对应 owner 完成。
- 格式与术语：WorkbenchFormat/WorkbenchTerms 及独立合同测试；工作区接入由对应 owner 完成。
- 批次与资源：Batch*、Resource*（不含上面共享控件及 Workbench*）、Calendar*、Outsourcing*。
- 计划与实际甘特：Plan*、ActualGantt*、PointGantt*。
- 排产：Preflight*、Run*、SchedulingWorkspace；不改后端调度。
- 报工：Field*。
- 分析与详情：Dashboard*、Report*、Review*、MasterOverview*、Calibration*。
- 系统：System*、维护恢复模板。
- 验证：独立基线/几何工具与样式/合同检查、证据收集；不改上述产品文件。

每位 owner 可以写自己名下的工作区 CSS（如 `styles/31-batches.css`），不得共同编辑 `30-workspaces.css`。新增脚本及 CSS 依赖顺序发送主线程统一登记。static 构建由主线程执行。只提交测试结果与源差异，不运行 git add/commit，不修改他人的暂存状态。

## 收口规则

依赖代表集成和验收前置；用户已授权并行，允许各项依据共同合同同时开发，前置实现尚未到位时不得伪记测试通过。每项先有简明 design/checklist，再实施；独立结果写对应 feature acceptance，真实浏览器和总门禁由主线程统一补齐。

当前状态：21项实现完成；最终浏览器矩阵、每日门禁及唯一失败的定向修复复测通过。完整门禁保留最后一次实际运行结果，按下述用户范围决定不再重跑，不宣称全量全绿。

## 门禁收口辅助修复

完整门禁第7步已收集17073个测试，但旧输出规范化对262143位数字测试参数发生二次方正则回溯，卡在收据生成。仅为数字匹配添加前导数字边界，保持原输出结果并补等价与长输入回归；不改变门禁标准。实测2534963字节原始collect日志在Python3.8规范化耗时0.095秒。记录见`../../issues/2026-09-12-quality-gate-output-normalization/quality-gate-output-normalization-fix-note.md`。

原工作区门禁因新增guard测试未跟踪而在预检拒绝。完整验证改在`/tmp/aps-wbui-implementation-20260912/verification-checkout`隔离副本内登记本次快照并执行`--allow-dirty-worktree`；原暂存区哈希已核对不变，不生成提交。该结果仍属于隔离脏快照验证，不能叫clean-worktree proof。

## 最终验证范围决定

2026-09-12用户明确要求：不因唯一已修复的小问题再花约一小时重跑完整门禁。最后一次e696全量实际结果为16503 collected、16491 passed、1 failed、11 skipped；唯一失败是系统维护KB显示测试仍期待旧的不分组格式。随后只修正该测试文件，完整受影响模块1 passed、37真实动作及16份数据库/备份保留检查通过。产品的350个构建输入和258个资产未改变；最终每日门禁与60页面/8交互/4密度矩阵均通过。

本次按上述实证完成实施与文档交付，不再启动完整门禁，不将原失败结果改写为通过。涉及最终full全绿的清单项记录验证限制与用户关闭重跑要求；这不修改项目通用门禁规则。统一事实、源码前后差异及原始日志见`evidence/workbench-ui/2026-09-12-final/final-gate-results-e696.json`。

# 旧 UI 退役：Main / A 最小评审路径矩阵

- 状态：2026-09-10，任务 G 的只读现状核对与待应用设计。未实施退役、未切换入口、未运行验收；不得写成迁移通过。
- 应用顺序：方案 17 全站动作与同资源 5000 容量通过后，Main 核对源码快照并决定应用 18。G 不接管 Git、schema/DTO、构建入口或正式性能窗口。
- 实读现场：用 `.venv/bin/python` 3.8.10 在空 Flask 上调用现行 `_register_all_blueprints`，不调用 `create_app`，不发 HTTP。进程 audit hook 拒绝文件写入、SQLite 连接、网络、子进程。实际注册 356 条规则：203 条旧业务规则（90 GET、113 POST）、152 条 workbench 规则、1 条 static 规则。自动 HEAD/OPTIONS 不另算能力。
- 两个分母不得合并：本清单覆盖实际路由；`options-matrix.md` 保留 LEG-001..081 全部编号。冻结 planning 206 族仍在原 `workbench-capabilities.json`，不改写，不借历史原型 passed 抵扣验收。

## 1. 先解决的三个前置点

1. **旧 URL 上下文转换仍是前置。** 提交窗口后重读 Main 新增的 `frontend/workbench/app/WorkbenchNavigation.js:9` / `:12`：已集中恢复工作区 context/滚动位置，但 URL 仍只读取 `view`，业务 context 来自 `history.state.workbench`。`web/routes/workbench/pages.py:62` 的 boot 未带旧查询身份。不是缺少导航组件，而是旧 version/plan_role/filter 尚无转换入口；A / Main 增补这个合同后，以下“等价重定向”才可应用。
2. **POST 不只返回重定向。** Excel preview / confirm 等旧 POST 可能直接 render 旧模板。不能仅拦 GET 后删除模板；必须逐端点保留解析、事务和结果语义，把结果呈现换成新样式，不能留测试专用旧模板开关。
3. **打印有旧共享样式；错误页不能误删。** 实读 `templates/scheduler/week_plan_print.html:12` / `:13` 仍用旧 tokens/print CSS；`templates/error.html:1` 只继承独立 `error_base.html`，不依赖 `base.html`。保留错误能力并做同风格呈现；仅换业务首页无法证明全部旧资源已不可达。

另一个限制是新报表的 `core/services/workbench/report_facts.py:38` 只接受当前正式身份；候选/历史/不支持的筛选不得直接跳到新目录。保留旧下载合同，页面给出新样式不等价说明。

## 2. 最小路由方案

下表是拟实施去向，不代表当前已等价。详细规则逐条登记于 `routes-matrix.md`；合法参数只有经过严格转换且目标确实消费才能算“保留”。

| 当前实际入口 | 拟处置 | 目标 / 条件 | 不得误删的邻接能力 |
| --- | --- | --- | --- |
| `/` | 等价重定向候选 | `/workbench?view=dashboard`；version / role / 范围须转成真实计划身份 | 值班台查询服务、历史与执行事实 |
| `/scheduler/` | 基础入口等价，旧专属筛选说明 | `/workbench?view=run`；preset/status/only_ready/start_dt 等未等价项不得忽略 | run、simulate POST、配置与严格检查 |
| `/scheduler/batches`、`/scheduler/batches/<batch_id>` | 等价重定向候选 | batches 及稳定批次引用；不跳到无选择列表 | 新增、更新、复制、生成工序、三种导入模式 |
| `/scheduler/gantt`、`/scheduler/analysis` | 有边界的重定向候选 | gantt / analysis，必须保留请求与有效身份、范围和明确选择 | gantt/data JSON、候选 / 历史查询、试调服务 |
| `/reports/`、四个专题 HTML | 等价重定向候选 | reports 目录 / 指定报表类型；scope 同身份、同日期、同资源 | 四个 `/export`、正式复盘、不可评估状态 |
| `/process/`、工种 / 供应商 / 设备 / 人员列表及详情、`/material/materials` | 有边界的重定向候选 | process 对应节点及稳定业务对象引用；隐藏字段不清空 | 所有写接口、授权、主操、班组、物料与外协关系 |
| `/scheduler/calendar` | 有边界的重定向候选 | process 日历节点；既有 shift_start/end 及跨夜配置不重写 | 日历命令及 Excel 下载 / 解析 |
| `/scheduler/excel/batches` | 等价导入入口 | batches 文件弹窗，overwrite / append / replace 全保留 | preview/confirm、引用保护、取消/失败无副作用 |
| 其他旧 Excel 向导 HTML | 按具体能力映射或退役说明 | 只有新页存在同业务同模式才重定向；额外 append/replace 不伪称等价 | template/export GET，preview/confirm POST |
| `/scheduler/config` | 新样式退役说明 | 明示旧配置编辑 UI 退役、已保存参数继续生效 | preset/default/update 等 POST、ScheduleConfig 全部字段 |
| `/scheduler/config/manual` | 新样式文档呈现 | 保留帮助内容，不继续旧导航外壳 | manual/download 及真实文档资源 |
| `/scheduler/week-plan` | 新样式退役说明 | 新甘特/CSV 不等于周计划 XLSX；给保留下载/打印能力的明确链接 | `/week-plan/export`、`/week-plan/print` 查询和正式警示 |
| `/scheduler/week-plan/print` | 保留能力、重做呈现 | 新样式打印；同组别、日期、角色及“不得下发执行”警示 | 周计划服务；不能直接 410 取消打印能力 |
| `/scheduler/resource-dispatch` | 新样式退役说明 | 现场记录不是旧人机双表 / 班组维度的等价页 | data/export/execution JSON 与写接口 |
| 人员个人日历、授权向导、班组、批量停机、批次物料需求旧页 | 新样式退役说明 | 原数据仍保留；不得跳到看似相似但改变语义的新页 | 个人日历、授权、班组、停机、BatchMaterials 服务/路由 |
| `/system/`、`/system/backup`、`/system/logs`、`/system/runtime-logs` | 有边界的重定向候选 | system 对应来源 / 明细 / 筛选；高级 module/action/limit 等未等价项说明 | 备份、删除、恢复、插件、审计与文件日志服务 |
| `/system/history` | 新样式退役说明 | 排产历史详情不是候选列表；不得静默转 latest | ScheduleHistory、真实 adopted / candidate 身份与诊断 |
| `/excel-demo/` | 新样式退役说明 | 演示入口不进入正式新导航 | 既有模板下载、preview/confirm 的返回合同分别核对 |
| `/system/health`、`/system/runtime/shutdown`、诊断包 GET | 原合同保留 | 不经过页面退役拦截，不引入 HTML 替代 JSON/ZIP | launcher 健康、锁、drain、关停与诊断 |
| `/api/workbench/v1/*`、`/static/*` | 原合同保留 / 精确资源裁剪 | 禁止泛前缀 catch-all；静态移除只以审核后的资源闭包为准 | 当前 manifest 中的新 UI 资源、字体、license |

## 3. 给 Main / A 的评审点

- Main：是否接受“显式 endpoint+method 清单 + 统一新样式退役响应 + 独立上下文转换”的最小路径；不禁用整块旧 blueprint，不改变业务服务/schema，不增加可返回旧 UI 的运行开关。
- A：上下文转换应走现有身份解析 / public ref，明确范围不能支持时显示说明；不能硬设 adopted、latest、默认日期，不能只在 Location 留参数而目标忽略。
- 81 项批准口径以本轮用户指令为准；旧 disposition 文档里历史 pending 不改写为新验收结果。
- 后续矩阵和测试计划需同时证明：旧 UI 在候选交付树不再可达，JSON/POST/下载等能力与新数据没有被删。代码回退与数据恢复分开演练，未做演练一律 `not_run`。

## 4. 本轮边界

- 初始矩阵阶段只写本目录。后续用户另行授权 G 实现 `navigation_boot.py` 和 test_final_navigation/support，已按该范围实施；退役本身仍仅为本目录待应用 patch，不挂载、不删资源。不改构建、规划基线或共享调用图。
- 不使用生产库；不接触 53144 / PID 73298 / `aps-workbench-live-l0tgvgp8`。不运行 Win7 打包、真机或发布。
- 入场 staged patch SHA256：`952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`，当时唯一 staged 为 `tests/gate_meta/test_frozen_bundle_contract.py`。19:23 Main 完成 `c00972784ccc129957f650836dd2a423792f7049` 后 index 已空，是 Main 提交的结果，不是 G 改动。G 不 add/commit/reset/checkout/清缓存。

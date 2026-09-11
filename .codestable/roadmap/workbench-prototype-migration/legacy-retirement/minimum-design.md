# 18 旧 UI 退役最小实施设计

- 状态：Main退役仍未挂载或改交付。后续明确授权的规范nav、纯SELECT查询叶、纯日期叶和旧GET转换已实施；dispatcher/结果/打印/手册/错误patch已在私有V4源码真实应用并通过factory专项。详见 `factory-acceptance.md`；未获17正式挂载许可，不宣布17/18完成。
- 硬顺序：17 全动作与同资源容量通过，Main 核对最新代码快照和授权时机，才应用本设计到全新候选交付树。Win7 包/真机/最终发布不在本轮范围。
- 选择：只增加显式页面适配边界、严格导航上下文与新样式说明/回执；保留既有 blueprint 的命令/查询注册，不移动业务服务，不改 schema，不新增运行时依赖。

## 1. 现状与改动落点

| 所有者 / 拟改面 | 责任与限制 | 现读依据 |
| --- | --- | --- |
| Main：factory/入口 | 原 GET endpoint 保留名字，逐项接页面适配器；51 页以矩阵为输入，非页面不拦截。候选入口仍由同一 Flask 提供 | `web/bootstrap/factory.py:239`；`routes-matrix.json` |
| G 实现、Main 接线：旧 GET 上下文适配 | 已新增 `web/routes/workbench/legacy_navigation.py`、`legacy_navigation_plan.py`、`legacy_page_contract.py`；只 SELECT，复用旧 parser 与永久 ref，不从前端猜业务身份 | `legacy-navigation-contract.md`；`data/repositories/workbench_plan_identity_repo.py:1` |
| Main：规范导航 DTO / boot | 新 URL 可表达、可重读的严格上下文进入 boot，再由现有视图合同验证；不扩充共享 schema | `web/routes/workbench/pages.py:62`；`frontend/workbench/app/WorkbenchNavigation.js:12` |
| Main：前端恢复接点 | 复用新 `WorkbenchNavigation`，不要建立第二套 context/滚动记录；区分显式 URL 目标与同一页面 history 恢复，不让旧 state 覆盖显式新对象 | `WorkbenchNavigation.js:32` / `:43`；`frontend/workbench/app/main.jsx:54` |
| 分域实现、Main 集成：说明/回执 | 拟新增 `templates/workbench/retired.html`、`legacy_result.html`、`manual.html`、`print.html`；共用新风格，保留无 JS/资源缺失时可读的本地说明 | `assets-matrix.json` 的模板/POST 正向依赖 |
| Main：候选资源/构建入口 | 仅收录核准的新 manifest 闭包、必要模板/下载资源；68 个旧模板及旧静态消费者迁完后排除，不在当前树直接清理 | `build_win7_onedir.bat:66` / `:93`；`scripts/workbench/build-order.json:15` |
| Main：测试登记/统一门禁 | 逐条替换旧 UI 形状合同为退役证明，保留原业务断言；最终门禁跑实际候选内容，不能启用测试专用旧 UI | `test-plan.md` |

实际文件/待Main应用文件区分及SHA见handoff。G未改共享schema/DTO、build-order或Main factory/pages/JS；原 `report_plan_preview.py` 仅按本轮明确授权改为纯core日期函数兼容导出。模板和dispatcher在draft-payload及私有候选source中，Main旧适配器仍未挂载。

## 2. 页面决策合同

建议由单一函数负责决策，handler 只呈现，不执行业务动作：

```python
# 已实现，未挂载。不要先用dict丢弃重复query。
resolve_legacy_get(connection, LegacyGetRequest(endpoint, tuple(args.items(multi=True)), path_values))
# -> LegacyGetDecision(kind='redirect'/'retired'/'restyle')
# -> None (非页面endpoint，继续原handler)
# -> LegacyNavigationInvalid(400) / NotFound(404) / 原存储错误
```

- lookup 键必须是 **endpoint + method**，不得是大路径前缀。51 个页面 GET 与自动 HEAD 同规则；其余 305 条注册不受该页面映射拦截。OPTIONS/405、健康、静态、API 错误边界维持真实合同。
- `redirect` 只用于参数集合和业务口径全部可等价承接的请求。采用临时 302、`Cache-Control: no-store`，避免验证阶段永久缓存指向。Location 不得丢合法身份或筛选，也不得写入后端状态。
- `retired` 返回新风格 HTML 410，列明具体 LEG ID、原来能力、已退的是控件/外壳、保留数据和可用的新入口/真实下载。对“父页面等价、子控件已退”的无参数入口，新视图显示适当退役说明，不暗藏原控件。
- 参数非法/重复/无法解析、对象不存在、存量身份损坏继续返回相应明确 400/404/领域错误；不伪称“已迁移”。`retired` 不是吞错总兜底。
- 页面 GET 及 HEAD 的适配不触发导入、预设切换、排产、补建引用、备份、删除、恢复、重建工序、插件启停；只读快照的 SQL trace/数据库变化测试锁住此边界。

## 3. 合法旧上下文如何保留

1. **先解析旧语义。** 按原端点认可的参数和 path values 解析 `version/plan_role/scenario_id/plan_context_token`、日期/周偏移、业务对象、筛选、分页和返回地址。检查 MultiDict 重复值，保留字段来源。不能把所有 P/D/R 分组一律作为所有路由的 allowlist。
2. **精确映射身份。** 用当前 `WorkbenchPlanIdentityRepository` 的只读 `get_plan_ref` / `resolve_plan` 与现有领域身份解析，确认版本、角色、scenario 三元组及有效身份。缺永久 ref 不自动创建；`candidate` 不改 `adopted`，历史不改 latest。显示名不是 key。
3. **形成可刷新规范 URL。** 最小建议是 `/workbench?view=<view>&nav=<URL 编码的严格 JSON>`，`nav` 只包含版本化的目标上下文（例如 `{version: 1, view: 'gantt', context: {plan_ref, range_start, range_end}}`）。采用现有 canonical JSON 和视图字段校验，不再引入另一套存储表或进程内随机导航 token。精确字段、字符串/请求长度限制沿已有合同由 Main 定义，不放宽既有阈值。这里的 version=1 是导航载荷版本，不是排产版本。
4. **目标确实消费。** `_host` 验证 nav 的 view 与页面一致，输出规范 boot；`WorkbenchNavigation.read` 在显式 nav 出现时核对/初始化对应 state，交给现有 `PlanContract/ResourceWorkspace.navigation/ReportAPI.scope` 等合同。不允许只保留 URL 字符串、组件却读 `{}` 或默认对象。复制链接、新标签、刷新与同版本重启都重新校验永久 ref。
5. **不等价就说明。** 旧 report 的事件日期不转成计划完工日期；旧班组范围不转显示组；资源/批次 ID 不转模糊搜索；不支持的 `gantt_*` 纯查看偏好逐项显示退役原因，不改业务参数。不自动截短日期、缩页、扩大 cohort 或忽略未知参数。
6. **特殊 token 边界。** 现有 `plan_context_token` 是进程内 12 小时脱敏映射。转换成功后新规范链接使用永久 ref；已过期或在主机重启后尚未转换的旧 token 明确报入口失效，不能保证原本不具备的永久有效，也不能回退其他版本。
7. **返回路径与可见内容。** 原 `back_to` 只在原先合法的同本机目标范围内规范化；旧 scenario/内部 key 不直接铺到用户文案。说明页显示公开名称、请求范围和错误原因，不把客户端 query 当已认可的业务事实。

该 nav 是评审建议；Main 若采用等价的显式 query schema，只要同样满足可刷新、无状态丢失、目标消费和严格拒绝，可以不引入 JSON 参数。无需重新批准“保留合法上下文”这一已定要求。

## 4. 必须显式处理的非等价子集

- **报表**：`report_facts.py:38` 和 `report_catalog.py:36` 只接当前正式计划。默认目录 `ReportCatalog.jsx:6` 选 overdue；需要新增“指定目录项 + 统计窗口”的受控初始化。旧历史/候选、事件时间、批次/资源过滤若当前目录无法表达，页面给 410 说明及保留的原 `/reports/*/export` 精确范围链接；不得为了重定向放松当前正式 guard。
- **计划甘特**：旧批次/资源 filter 与新 PlanWorkspace 的搜索只影响图且导出全量，二者不等价。当前无法精确承接的过滤请求给说明，或由 Main 在明确范围内增加真筛选合同；不能用旧名称填搜索框冒充完成迁移。
- **系统**：`SystemLive.jsx:6` 自建 tab/source，main 目前不把 initialContext 传入 system。正确承接日志来源、filter/filename/详情需要显式 props/恢复合同，否则给说明。sample 与 production 不互换。
- **工艺/资料**：新 `ResourceWorkspace.navigation` 认可 source/kind/永久实体引用及少量节点属性；仅等价字段通过，旧备注/班组/授权/个人逐日配置属于保留数据而非隐式回填新表单。
- **周计划与派工**：旧页面退役不取消 XLSX、打印、派工导出/JSON、执行事实接口。周打印用新样式与原页眉/分组/警示，保留真实打印能力，不是把 print GET 改 410。

## 5. 旧 POST / 下载如何不带回旧界面

- 113 个 POST 保留原 URL、方法、服务调用、事务和成功/失败边界。12 个旧导入渲染 helper 至少由 24 个 preview/confirm POST 可达，名单已列入 routes/assets 矩阵。
- helper 的业务工作不改，仅把结果呈现转到新 `legacy_result.html`：明确业务、原模式、解析/预检/确认状态、真实错误/警告、逐项结果和是否已提交；未确认不说成功。继续保留原 pending/基线和 confirm 合同，但不渲染旧整套编辑器、旧导航、旧 JS，也不让 GET 自动提交。
- 已确认结果的响应、回退链接和 flash 提示必须在新回执/目标页可见，防止旧“redirect + flash”变成成功/失败都不显示。失败下载的回页也需同样处理。
- JSON、下载、健康、诊断和关停仍走原 handler。不用 JSON 包一段旧 HTML，不用反向代理或 iframe 继续展示旧页，不扫描替换所有 render_template，不根据测试环境恢复旧模板。
- generic error 模板保留，变成简洁同风格但零业务路由/JS依赖的错误页；`workbench/recovery.html` 保留独立维护日记读取，不能因新资源坏掉而失去恢复诊断能力。

## 6. 执行顺序与停止条件

1. Main 确认 17 的动作级 B/K/V/P、复杂业务、同资源 5000 容量证据和源 hash；当前 source 有后改则相应证据重跑。
2. Main 记录源码快照、HEAD、dirty/staged、candidate 正向清单和数据保护计划。不能拿旧 preview 当 candidate，也不覆盖本工作区。
3. 先实现导航解析/说明/POST 新回执/新打印，保持其余业务合同，再执行候选文件移除。每小步跑对应合同，入口未等价不得切换。
4. 在候选树运行全部旧 URL 的路由结果、资源无旧载荷、保留接口和新数据测试；实际浏览器点击、下载、截图与刷新重启不可由 AST 代替。
5. Main 安排统一完整门禁与归档。任何影响源/asset/DTO 的后改使对应 hash 失配时重新冻结；不降阈值、不刷新基线、不删断言消红。

停止：上下文会换身份/扩大范围、保留 POST 仍需旧模板、新打印/错误不可用、旧资源仍被请求、数据有未解释差异、源/包证据不一致、17 未通过。停止代表不应用 18，不能把未实施写成 passed。

## 7. 代码回退与新数据保护分开的演练路径

| 演练 | 私有材料/操作顺序 | 必须验证 | 本轮状态 |
| --- | --- | --- | --- |
| R0 归档可读取 | 读 Main 的 `pre-retirement-LqHg4q/manifest.json` 与 source.tar.gz；新临时目录按完整清单恢复，不覆盖工作区 | 5384 文件逐项 hash/size；归档 SHA256 与 Main 清单一致；源备份不混数据库 | G 只读取目录与 manifest；未新算归档 hash、展开或启动 |
| R1 代码单独回退 | 私有 D0 fixture 跑退役前代码；候选只改 UI；用真实新界面产生报工/更正、候选采用、trial/外协/维护记录等 D1；对 D1 做一致性保护快照；退役前代码在另一私有实例打开 D1 的副本 | 相同 schema/业务数据仍可读；D1 新主键、修订链、永久 ref、采用历史、journal 全保留；旧代码无隐式迁移/清洗/重放命令 | not_run |
| R2 旧代码不兼容 D1 | 构造明确不兼容/缺身份的私有副本，以旧代码只读/拒绝路径验证 | 明确停止；保留 D1 及保护副本；不自动降 schema、不恢复 D0 吞掉新增事实 | not_run |
| R3 独立数据恢复 | 只在私有 fixture 上另行选定恢复目标、确认差量，使用现有 Backup API/受控 restore；恢复前再次保护 D1，并记录 DB/WAL/SHM 一致性处理 | 原子替换、停写/drain、保护备份、失败回滚、结果未知不重试、最新新增数据可回到 D1；每一步 journal 可查 | not_run |
| R4 代码再向前 | 在 D1 副本上重新启动相同候选内容，用同一永久链接/请求标识查询，不重发未知结果写命令 | 新数据/身份不变，刷新重启不换对象，退役资源仍不可达 | not_run |

- R0 的源码可还原不等于运行已通过，也不等于数据库被备份；原 manifest 已明确 `database_backed_up=false`、`product_runtime_verified=false`。主线已有恢复检查记录只能按其真实范围引用。
- 代码回退优先保留升级后 D1，不把“源码旧版本”与“数据库旧快照 D0”捆绑。若必须回到 D0，先列出 D0→D1 新增/修改/删除/修订差量并单独获准，不自动合并行或调用业务命令重放。
- 本任务无生产库操作授权、无部署操作；以上都是 Main 后续私有演练步骤。源码备份完整并不能跳过 R1..R4，也不能写 passed。

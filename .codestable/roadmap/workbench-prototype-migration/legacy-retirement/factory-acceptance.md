# G 私有 Factory 验收

日期：2026-09-10。结论：本轮授权的 SELECT 分层、日期纯叶拆环和私有 factory 验证已完成；Main 未正式挂载，浏览器/发布/17/18 未放行。

本报告是V4封存版本，不包含随后批准的D-P003 `task_origin` 解析overlay。后续两文件源码/hash/51项局部回归另见 `task-origin-overlay.json` 和对应feature-ff-note；原V4源和运行回执不改写、不冒充覆盖新增输入。

## 源与补丁

| 对象 | 文件 / bytes | Aggregate SHA256 |
| --- | --- | --- |
| V4 baseline | 3919 / 92,926,072 | `a2920c5e43ab655f5b8e82897df3f4a8af3b25e8eeebc66d484afcd072b4240f` |
| V4 candidate | 3927 / 92,948,312 | `e74e6dce3c8a196433692084dbdc4d94f3f9c4b79e952bc352c0e7ed8714b85b` |

- 私有根为 `/private/tmp/aps-g-retirement-candidate-u8YnDE`。逐文件 SHA、mode、声明范围在两个 `*-manifest.json`；所有测试数据、HTML、SQL 回读、XLSX、日志在 `runs/`。
- V3 从 Main 冻结3918文件，aggregate `8863c896ef00ee6dc1f8042d696390914d2648e547971a36b395e94030c55b0c`。V4继承并核对全部3918文件，仅补原治理台账作为正常 pytest 事实源；candidate 再实际应用原24目标 patch，不是仅内存替换模板。
- 原 patch SHA `a6c1a20dce70b241046b09ecfcd349fd7c8dddb7a6f00ee0ea644d916fabd0e2`，24 preimage/postimage全部相符，14个旧renderer除模板字符串外AST相同。
- 2681个 candidate Python 文件静态可解析，声明范围内缺少的 repo 模块清单为空；运行时检查所有模块的 `__file__`、全部 `__path__` 和 custom alias，不仅检查 core/data/web/tests。原 checkout 非依赖文件的读取被拦截。
- 根 `common/` 实际不存在；`core/services/common/overdue_calculations.py` 在最早3554文件清单中已存在，SHA `bf485f4b96359ff999d77c58df50a0fb07dd5b2860f067aff0c6b78603a1d713`。此前附和“遗漏 common 根目录”不准确。后续实际补齐的是动态发现的 desktop/docs/audit 等 Python 根，以及正常 conftest 的非 Python 台账。
- Python静态盘点使用宿主3.14；所有应用/pytest运行使用现有3.8.10。标准库及显式 `.venv/site-packages` 作为依赖保留，不允许从 Main 导入产品源码。源/文件模式在运行前后均相等；harness也冻结并绑定 SHA。
- 这证明声明的源码、已检查静态导入和实际加载/读取路径；不把未测试的任意动态文件引用宣称为完备。缺项应像本轮台账一样 fail closed，再建绑定，不回落原目录。

## 两个根因修复

1. `core/services/workbench/legacy_navigation_queries.py` 承接 SELECT/Repository。web传递已解析的版本、角色、方案和业务键，仅决定 HTTP。查询要求读snapshot、保留已有外层事务；缺源/身份不补建、不修复、不改选，无 Flask/werkzeug/web依赖。
2. `core/services/report/date_input.py` 原样承接 `validate_ymd_date` 与 `validate_explicit_report_date_range`。旧 web 保留公开导出，legacy直接依赖纯core，去除 workbench→旧 reports 模块的顶层回边。两函数与原剩余7函数AST均相同，默认日期、错误信息、斜杠日期、非补零容忍度及62天上限均未改变。

生产和含 tests 的正式 `--fail-on-new-cycle` 扫描均 exit 0。不是“无任何环”：仍有1个原基线内目录环。基线前/后/快照SHA均一致：

| 基线 | SHA256 |
| --- | --- |
| production | `78d0ae16c6a11543d56b94e4e1a20bd1406731e0dd9a2728d164f5ed25fd799d` |
| include-tests | `2878a55393510e524f2259f918142199d187d3097e6a3292e521cf8090571d19` |

日志在最终私有根的 `V4-production-cycles.log`、`V4-with-tests-cycles.log`。原新增目录SCC的失败日志保存在 WQooWU 的 `before-production-cycles-module.log`。未加 baseline、ignore、lazy import 或日期语义分支消红。

## 实际结果

| 分组 | 实测结果 |
| --- | --- |
| 正常 pytest | 46 passed，0 failed；nav12 + legacy19 + layering4 + 日期配对8 + 原架构适应度3。保留正常 conftest/治理台账，无 noconftest 或 xfail 覆盖；加载1006个repo模块路径通过守卫 |
| 源守卫负向测试 | 2 passed：未加载的common模块静态入册/缺模块报告、原模块/namespace/插件别名回落拒绝、文件mode变化失败 |
| 12组导入 | baseline 12/12、candidate 12/12；人员、人员设备关联、设备人员关联、设备、工种、供方、路线、工时、批次、日历、人员日历、示例 |
| 51 页面 GET/HEAD | 两侧逐条真实请求；candidate 不引用旧css/js，合法退役入口410，HEAD状态相同且零body |
| 39 非页面 GET/HEAD | 原函数保留；两侧状态/MIME无差异，HEAD行为一致 |
| 113 原 POST | 两侧逐条真实空表单请求，原函数身份保留；状态/MIME/JSON无差异，零5xx。每次从同一私有seed恢复，并非113条完整业务交易 |
| 报表日期 HTTP | candidate26、baseline24次：斜杠、恰好62天、缺一端、非法/反向/超限，以及candidate两端冲突别名；拒绝不换默认范围 |
| 打印/手册 | 两侧实际查询并渲染采用/对照两角色，真实批次/日期/筛选范围/备注/打印动作，非正式警示保留；手册原md下载字节相同 |
| 真实消息 | 设备修改事务后沿旧详情跳转，正常canonical、非法nav400、真实缺资产503三路径；提交值不丢，消息刷新只消费一次 |
| 静态 | 13实际源码/测试 Pyright零错误/警告；这些文件及全部factory harness Ruff通过 |

每组导入实际提交 XLSX、解析该 confirm form 自身隐藏字段，验证 preview不写业务数据、刷新载荷一致、无效行/过期基线/坏确认被拒绝、原confirm提交、精确SQL/FK与新连接回读、确认重放不重复写入、原模板字节和导出工作簿。日历首次初始化原配置通过原服务作为明确fixture准备，未冒充导入副作用消失。

这些结果不覆盖每个import mode/replace/部分事务失败组合，也不把HTTP回执、boot消息或临时DB重开等同于浏览器/Win7/应用重启全链。原51/39/113与81选项矩阵的分母没有缩小；未伪填81行 B/K/V/P。

## 失败记录保留

- CzTalo早期SQLite URI bytes守卫、datetime证据序列化、冷库ScheduleConfig初始化和批次confirm表单字段合并错误，分别保留失败回执。冷库行为在baseline也复现；修正夹具后两侧R3导入12/12。旧轮仅作历史局部证据，不升级其源码闭包强度。
- WQooWU报表R1的最大日期窗口不含测试排程，原export正确返回无数据400；补测夹具改为覆盖真实排程并加入停机记录，产品未放宽。
- WQooWU pytest先因默认日志写 `/dev/null` 被私有写守卫阻止，后因缺原治理台账停止收集。分别改为私有日志路径、V4补原台账；未弱化守卫或绕过正常conftest。
- V4复制准备阶段曾被完整性检查拒绝尚未完成的副本。等待复制结束、核对全部继承文件和24preimage/postimage后才接受最终manifest并运行；没有在该不完整状态形成通过结论。
- CzTalo、FtCvUw、WQooWU三轮目录、旧manifest、payload和运行回执未删除；前一阶段文档也另存 `stage-history/2026-09-10-pre-factory/`。

## 不放行项

- 当前快照自带 build_id `67229ad0b232830132f049095e8c8c8b80ba29296df7b3668a128af1ebec5c78`。产物hash自洽，但302个inputs中49个与源不匹配，不能做本轮浏览器验收。详情见私有根 `V4-asset-source-binding.json`。
- 仍待 F/Main 的完整匹配构建并绑定新snapshot，验证真实前端导航/flash/确认交互/打印外观。Main pages/main.jsx/unavailable原消费者已在HTTP验证中复用，G没有改它们。
- Main checkout未应用/挂载、未删旧资产。最终整站17/退役18、发布包旧资源负向缺席、Win7、完整门禁和D1回退演练均未通过本轮替代。
- 本轮没有生产库/原preview操作、Git stage/commit/reset或持续服务。工作区是多方dirty状态；本轮源hash专项证明不是clean-worktree proof。

机器可读证据、原始结果路径/哈希、测试脚本哈希及13个实际文件精确行号见 [factory-verification.json](factory-verification.json)；正式接线见 [handoff.md](handoff.md)。

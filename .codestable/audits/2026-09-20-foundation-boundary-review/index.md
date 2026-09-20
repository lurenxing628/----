---
doc_type: audit-index
audit: 2026-09-20-foundation-boundary-review
scope: 基础边界治理路线图（97850695..b227f3a2，29 个提交）的对抗复审——仓储不裁决 / SQL 排水 / 工作台与排产分包 / schema 单一事实源 / 门禁基线；三条只读子代理轨 + 主代理修复与复验
created: 2026-09-20
status: closed
total_findings: 21 + R4 复审修复批次 5
subagents_used: 4
verified_by: 主代理定向测试（每个修复提交单独跑定向用例，累计约 4200 例）+ pyright 门禁 0 错 + sync_debt_ledger check 通过；未跑全量门禁（用户明令）
---

# 基础边界治理对抗复审（2026-09-20）

## 复审方式

三条只读 Fable 5.1 子代理轨并行：R1 定向复审（已知合同与修复点）、R2 盲审 A（数据流 / SQL 排水 / schema）、R3 盲审 B（导入期 / 冻结打包 / 门禁与注册表）。主代理汇总后按严重度修复，每组修复单独提交并跑定向测试；随后再派一轮定向复审只看修复。

## 发现与处置

| # | 轨 | 级别 | 发现 | 处置 | 提交 |
|---|---|---|---|---|---|
| 1 | R1/R3 | blocker | pyright 门禁 HEAD 41 错 / 基线 0 错：仓储返回 Optional 后服务层直接下标，`workbench_outsourcing.reject` 缺 NoReturn | 补 NoReturn 与显式 None 裁决 7 处；pyright 归零 | ab7ebd94 |
| 2 | R1 | blocker | `scripts/sync_debt_ledger.py check` 因 factory.py 行号漂移而红 | 受控 `refresh --mode refresh-auto-fields` | 97ac0ae1 |
| 3 | R2 | blocker | 工艺就绪度 `except (RuntimeError, sqlite3.DatabaseError)` 接不住仓储翻译后的 AppError，降级分支失效变 500 | 补 AppError；新增经真实仓储注入 OperationalError 的回归测试 | da7278ca |
| 4 | R3 | major | config.py 搬到 web/bootstrap/app_config.py 后 31 个分组 input_file_scopes 失效，6 个分组在日常门禁增量选组时被静默跳过 | 作用域改到 app_config；合同测试锁住 31 个分组 | 97ac0ae1 |
| 5 | R1/R3 | major | `.codestable/semantics` 语义雷达套件仍 import 已删的 core.infrastructure.errors | 改 core.errors；目录加进错误合同扫描根 | 97ac0ae1 |
| 6 | R2 | major | 四处整表读取从逐行迭代变成 fetchall（历史 Schedule 全版本、日历、指纹整表、回执目录） | BaseRepository.iter_rows；四个方法流式产出；仓储测试锁"不是 list" | 3316638d |
| 7 | R2 | major | `_canonical_sql` 列序不比较后，存档行仍按本模块 DDL 列序解码，迁移链库的存档会静默错位；`--` 注释剥离不认引号 | 按存档 DDL 文本取物理列序（不执行存档 SQL）；引号感知去注释；5 个合同用例 | 0577a3a1 |
| 8 | R2 | major | 六个上提的拒绝码全仓零测试引用 | 24 个策略层用例逐 raise 点锁码 / 状态 / 文案 | 9f8a4172 |
| 9 | R1 | major | move_modules 行号映射用 str.splitlines，换页符 / U+2028 会写坏文件 | 只按 \n 切行；写盘前 ast.parse，失败整批放弃 | 0351ab84 |
| 10 | R1 | major | move_modules globs 替换不看语法上下文，非列表位置会变元组 / SyntaxError | 只在 list/tuple 元素位置替换，其它位置阻断 --apply | 0351ab84 |
| 11 | R1 | major | move_modules 新建子包会遮蔽同名未搬模块 | Plan 校验拒绝 | 0351ab84 |
| 12 | R1 | major | 决策文档"facts/ 业务裁决一律不进"与代码相反 | 改为"只读事实 + 对事实的薄裁决 + 纯助手，写操作不进"并写明理由 | 文档提交 |
| 13 | R3 | minor | 死代码孤岛基线漂移：本轮搬迁改名 9 条；另有 108 条 2026-09-18 旧路由层删除后长出的新条目（quick 口径，64 条有生产引用、25 条 dunder/协议、9 条全仓零引用、7 条仅测试引用） | 第一版 --refresh 把 108 条一并吸收（R4 判为违反 ratchet 决策），已改为只吸收 9 条改名、剔除 25 条已消失项（86→70）；108 条留给旧路由层删除的责任方分诊 | 97ac0ae1 → R4 收口提交 |
| 14 | R3 | minor | 簇分层测试 `_targets` 不认 `import a.b as c` | 补分支 + 单测 | 0351ab84 |
| 15 | R3 | minor | 排产子包间无方向表，已有少量反向边 | 路线图 §4.5 写明"暂不约束方向"，留待另立 | 文档提交 |
| 16 | R1/R3 | minor/nit | 决策文档数字失真（141/385、233 模块、7 个垫片、database_bootstrap 措辞）；ARCHITECTURE / service-scheduler / desktop / .limcode / AGENTS 示例残留旧路径；冻结锚与冻结合同 docstring 过期；pyright gate include 根 config.py | 全部修正（AGENTS.md 为 skip-worktree，仅本地改） | 文档提交 / 97ac0ae1 |
| 17 | R3 | nit | 恢复宿主键名裸字符串；runtime_host 接缝无直接单测 | 改用 RESTORE_HOST_EXTENSION；新增 3 例 | 97ac0ae1 |
| 18 | R2 | minor | `execution_ledger_adapter` 直接读 `repo.clock()` 绕过 `revision_clock()` 裁决 | 改走 `revision_clock()` | 文档提交同批 |
| 19 | R1 | minor | 两处拒绝顺序边缘差异（read_events 先算字节再查行数；append_handling 先查大小） | 码 / 状态不变，仅极端场景文案先后不同，记录不改 | — |
| 20 | R2 | minor | `gantt/adjustment_publish_service.py:109` 嵌套 begin_immediate 静默降级；写语句 rowcount 未核对 | 基线即如此、无生产调用方，不在本轮范围，记录 | — |
| 21 | R3 | minor | `legacy_blueprints ⇄ manual_page ⇄ system_runtime` 新增一条延迟环（正向副作用：说明书页模块在冻结包里由不可达变可达） | 加载顺序正确、环基线只比硬环；未加合同，记录 | — |

## R4：修复批次的定向复审（b227f3a2..6dd36682）

只读复审 8 个修复提交；对 7 组新测试做了反向验证（临时撤销修复后全部变红），move_modules 在 /tmp 仓库实跑 `--apply`，3351 条真实 DDL 老/新规范化结果逐条相同，日常门禁 `_build_impact_plan` 干跑确认 app_config 改动选中 6 个无兜底分组。blocker 0。

| # | 级别 | 发现 | 处置 |
|---|---|---|---|
| R4-1 | major | 死代码基线 --refresh 吸收 108 条与本轮无关的新条目，未按 ratchet 决策分诊 | 基线改为 b227f3a2 版只吸收 9 条改名、剔除已消失项（见 #13） |
| R4-2 | minor | `.codestable/semantics/tests/test_semantic_snapshots.py` 两个快照的字源随旧路由层删除，套件 13/2 | 两个快照测试与快照文件退役，语义漂移账本记一条 |
| R4-3 | minor | 就绪度 `except AppError` 结构上过宽（当前不可达） | 收窄为只吞 `DB_QUERY_ERROR`，其它 AppError 上抛 |
| R4-4 | minor | `calendar_rows` 是生成器函数，错误在首次 next 才翻译 | 改为调用时执行两条语句 |
| R4-5 | 记录 | `iter_rows` 迭代期 sqlite 错误不翻译（与原 fetchall 一致） | 不改 |

## 复审遗留清理（用户裁决"这俩干了吧，其它该修的修"）

| # | 项 | 处置 |
|---|---|---|
| C1 | 47 条旧路由层时代的失效分组作用域（templates/scheduler、static/js、web/routes/*_excel_*、web/viewmodels/scheduler_* …）+ 已删 unit_excel_converter.py | 全部删除；甘特/报表组与界面布局组补现行 workbench 路由 / 前端等价作用域；`.codestable/**/*.yml` 两条属前瞻覆盖保留并显式放行；合同 `test_every_required_group_input_scope_matches_an_existing_path` |
| C2 | 死代码孤岛 108 条新条目 | 逐条 grep 归类：删 9 处真死代码（4 零引用 + 5 仅测试引用），基线吸收 99 条并在提交说明写明类别（67 生产引用误报 / 25 dunder 钩子 / 3 闭包 / 3 测试接缝 / 1 HTMLParser 钩子）；老 Excel 导入簇（`ExcelService` 生产无调用方 + `build_existing_for_excel` + `tests/excel_data_io` 8 份 + smoke_phase3/4）整簇是否退役留给用户裁决 |
| C3 | 8 个只能 ImportError 的脚本（7 个 e2e/冒烟 + `scripts/convert_rotary_shell_unit_excel.py`） | 删除；仓内无工具/注册表/现行文档引用 |
| C4 | `run/optimizer → run` 的 TYPE_CHECKING 反向边 | `SchedulerLike` 协议落到 `contracts/scheduler_like.py`；排产子包方向表立为 `test_scheduler_subpackage_layering.py`（登记进 scheduler_run_core 与守卫清单） |
| C5 | R3-m2 说明书蓝图延迟导入无合同 | 冻结合同新增 (f)：`register_legacy_blueprints` 必须字面 import，全文件无 import_module |
| C6 | 系统速查表 / 开发文档.md / .limcode ownership_matrix 旧路径 | 按搬迁计划映射逐条改到现行路径（14 处）；阶段留痕类文档不改 |
| C7 | R2-m1 嵌套 `begin_immediate` 静默降级 | 用户裁决不改：一人一机，真正会嵌套的 `record_event` 外层本就是 IMMEDIATE，最坏后果是一次可见报错而非坏数据 |
| C8 | 老 Excel 导入簇 | 用户裁决退役死的一半：删 `ExcelService` 类、两个 `build_existing_for_excel`、一份专测与三个开发期冒烟脚本；类型与 `excel_import_executor` 仍被批次 / 日历 / 人员设备导入使用，原地保留；`TabularBackend` 三件套是插件框架示例能力，是否连插件示例退役另议 |
| C9 | `GanttAdjustmentPublishService.publish_scenario` 生产无调用方 | 退役：删服务与两份测试、账本守卫里 3 个驱动它的用例，门面 `_EXPORTS` / 冻结锚 / 懒导出合同 / 注册表 / 三缺口文档与路线图条目同步；同族 Draft / Scenario / Validation 三个服务同样无生产调用方（约 1.5k 行 + 46 份测试引用），整族退役另议 |
| C10 | 甘特调整族 Draft / Scenario / Validation + 投影 + 草稿仓储 | 用户裁决退役：删 3 服务、`adjustment_projection.py`、`ScheduleAdjustmentRepository`，模型只留 `ScheduleAdjustmentScenario`；`ScheduleAdjustmentScenarioRepository` 只留 `list_catalog_rows`（`build_plan_catalog` 仍调用，但该函数生产无调用方、只被两份工作台测试当私有目录合同使用，超出本次裁决未动）；`tests/_support/gantt_scenario.py` 的 `_saved_scenario` 改为按退役服务的真实产物直插两张方案表；`ScheduleAdjustmentDraft` / `ScheduleAdjustmentChange` 两张表不再有写入方，是否 drop 属数据裁决未动 |
| C11 | `TabularBackend` / `OpenpyxlBackend` / `PandasBackend` / `excel_backend_factory` + `plugins/pandas_backend_plugin.py` | 用户裁决退役：`ExcelService` 删除后四个后端模块与 pandas 插件示例在生产里无消费方，整簇删除；`SOURCE_ROW_NUM_KEY` / `SOURCE_SHEET_NAME_KEY` 落回 `excel_service.py`；插件框架三份测试改用合成能力键（`probe.*` / `demo.*`）与仓内唯一真实插件 `ortools_probe`；`openpyxl` 后端专测覆盖的软 / 硬链接拒绝与公式清洗分别由 `tests/app_runtime/test_fixed_file_security.py` 与工作台导出测试保留；直接装配扫描器去掉两条只匹配已删符号的规则（`excel_service` / `get_excel_backend`）；pyright 两份配置去掉 pandas 后端排除项 |
| C12 | 工作台私有计划目录层（`build_plan_catalog`、`build_history_plan_page` / `build_scenario_plan_page`）生产无调用方，只给 43 + 17 + 4 个测试当 oracle；独占 `_check_detail_times` 回退分支、`SchedulePlanDetailTimeRepository` 与 `ScheduleAdjustmentScenarioRepository` | 用户裁决按建议做：三个入口与两个冻结页数据类搬到 `tests/workbench/plan_catalog_oracle_support.py`（用退役探针的同一条 SQL 实现 `validate_detail_times`，测试语义与 SQL 计数不变），生产删 `workbench_plan_page.py`、两个仓储、回退分支；`_check_detail_times` 只剩显式 `validate_detail_times` 一条路，仓储缺方法直接 RuntimeError——fail-loud 立刻抓出研究时漏判的一处生产调用：试调采用历史 `trial/adoption_history.py` 一直用普通目录仓储走回退探针（探针把零工时行判为无效，与工作台目录的 Point 语义不一致），已改为与目录 API 同一个 `PointPlanCatalogRepository`，并加合同测试锁住；三个工作台消费方改从 `core.services.common.bounded_plan_query` 取 `_PagePlanQueryService`；round1 依赖合同去掉对已删模块的公开面钉子 |
| C13 | `tests/gantt/gantt_legacy_schema_support.py` + 三份冻结旧库 DDL 夹具随 4 份甘特测试删除后无人导入 | 删除，注册表 4 条作用域同步 |
| C14 | R5 三轨复审（定向 fork + 两条盲审，均 Fable）对 d21cc76b..3f154727 五个提交：无 blocker；major 3 / minor 4 | 按用户裁决修：oracle 模块改名 `plan_catalog_oracle_support.py` 落进 `tests/workbench/*_support.py` 作用域、`tests/_support/gantt_scenario.py` 加进计划组作用域（日常门禁影响计划实测两者都选中 workbench_plans）；补零工时正式计划在采用历史里可看的行为测试（managed run → 采用 → 试调 → 采用 → 读历史）；补 `write_fixed_bytes` 既有软 / 硬链接拒绝直接用例；`scip-pyrightconfig.json` 清掉已删 pandas 后端排除项；补场景预览行读取 + 缺场景报错的小合同；`test_plan_catalog` 坏时间行断言改为 code 而非 oracle 自己的文案。降级不修：v12 / v13 迁移旧行保留断言随冻结夹具消失（v4→当前结构回放仍由 `test_schema_parity.py:185` 守着，两步迁移只有 CREATE）；记录不修：采用历史每条回执多两次整行读（1 万行约 +0.2 s / +10 MB）、`GanttService.get_gantt_tasks` 生产无调用方待裁决、历史文档仍提旧 Excel 后端 |

## 未做 / 证据不足

- 全量门禁、`tests/workbench` 全目录、三个拒绝 xdist 的算法矩阵测试：按用户明令未跑。
- Windows 打包机真实 PyInstaller Analysis：本机无 PyInstaller，冻结可达性只做了 AST 近似（R3）。
- `.limcode/contracts/ownership_matrix*.json`、`开发文档/` 阶段留痕里的旧路径：历史契约与阶段记录，未改。

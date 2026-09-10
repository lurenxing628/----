# 第二轮源码归属与验收分母审计

- 日期：2026-09-10；任务 A。只读 Git、源码及归档，仅写本任务指定的三份审计文件。
- 最新授权：Main 在用户原分支受控写 index/commit，随后独立 clean worktree 验证该 HEAD；不覆盖原 dirty。本代理不执行 Git 写入。
- 当前状态：Main 已完成10个本地提交；最新为 G04-system `0cab59b6970a86393f610a2838feed9efc7523b2`。v21已按Main实际source-plan回填G05固定959源，只记captured，未收到本次stage/commit/test回执；旧MEMBER_ONLY小名单不改。没有把定点结果记为完整门禁通过。
- 起始 HEAD：`de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`。

## 已提交首批

唯一 staged 冻结包测试已随最小冻结导入底座提交，没有整文件夹带 factory 的工作台接线。提交前现工作区 6 passed 由 Main 告知，本任务没有重跑，不能转记为隔离 HEAD 已通过。

建议提交：`fix(build): close frozen scheduler import contract`。

Main 已提交 `c00972784ccc129957f650836dd2a423792f7049`，实际为以下四路径、257 insertions / 1 deletion。factory cached SHA 已与下述虚拟值一致；独立 clean HEAD 的测试结果由 Main 另记录，本任务不代写通过。

```text
tests/gate_meta/test_frozen_bundle_contract.py
core/services/scheduler/_frozen_import_anchor.py
build_win7_onedir.bat
web/bootstrap/factory.py
```

- 前三份文件可取当前内容：本任务逐字节确认与 `source-RauBC6/restore-check/` 一致，均属于迁移前已有 dirty，不宣称迁移原创。
- `factory.py` 以起始 HEAD 的版本为底，仅做下面两个锚点变更。当前版本还混有工作台注册、恢复前维护、请求连接排空、退出备份与配置装配，不能整文件归进这个小提交。
- 在 `from core.services.common.excel_templates import ExcelTemplateError, ensure_excel_templates` 后新增 `from core.services.scheduler import _frozen_import_anchor as _scheduler_services_import_anchor`。
- 把 `_PYINSTALLER_IMPORT_ANCHORS = (_scheduler_import_anchor,)` 改为 `_PYINSTALLER_IMPORT_ANCHORS = (_scheduler_import_anchor, _scheduler_services_import_anchor)`。
- 上述虚拟 factory 内容已在内存计算，未写共享工作区：20,724 bytes，SHA-256 `fb62f50c0e896d2d0b06dcbda5c7b3f5870d524827132c7bd98c583d59219981`。
- 测试 SHA-256：`c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`。
- 锚点 SHA-256：`e03b4b69f97525e43300d32e91a6a2ed1b029285e497eb482ee3fb2cfe5dc41f`。
- bat SHA-256：`1e971bc00352564ecf09234dbb798c234854f9bd1f4c7e5d7ca8e899e2b11196`。
- 静态闭合检查：锚点直接 import 的 14 个第一方模块全部存在于起始 HEAD。此检查不替代运行导入、6 项测试或完整门禁。
- 测试登记可在后续统一门禁提交整文件收口；本批不应整份带入 `tools/test_registry_data.py`，其当前内容依赖尚未提交的工作台注册组和众多新测试。

隔离树验收命令，临时目录由 Main 提供且必须是私有路径：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$PRIVATE/pycache" "$SOURCE/.venv/bin/python" -m pytest -p no:cacheprovider tests/gate_meta/test_frozen_bundle_contract.py --basetemp="$PRIVATE/pytest"
```

该源码合同提交不涉及 Win7 打包、真机或发布，也不为这些未做项目给出通过结论。


## 现在可执行的职责批次

机器入口：`round2-source-scope.json.execution_groups`。每组直接提供 `id/title/source/source_root/paths/paired_tests/test_support_paths/depends_on`；每个路径的 SHA-256、bytes、mode 位于同 ID 的 `commit_groups[].source_entries`。

G01、四个G02历史组、G03、G04-master、G04-execution、G04-trial-reports与G04-system已由Main提交，共10批；各自只具有回执明确限定的定点记录。trial145与system112的postbound均已同步，首次失败仍保留。G05取E sealed06产品/基础测试、对应223份真实资产及Main另行冻结的original exact overlay，不抓变化中的原树hash。

| 组 ID | 内容来源 | 产品或工具 | 测试文件 | 辅助文件 | 总路径 |
| --- | --- | ---: | ---: | ---: | ---: |
| G02-runtime | source-RauBC6 | 43 | 24 | 2 | 69 |
| G02-algorithm | source-RauBC6 | 72 | 51 | 17 | 140 |
| G02-imports | source-RauBC6 | 34 | 6 | 0 | 40 |
| G02-reports | source-RauBC6 | 24 | 18 | 2 | 44 |

后续是五个基础/业务组，各自带本域产品、前端和测试：

| 组 ID | 职责 | 测试文件 | 总路径 |
| --- | --- | ---: | ---: |
| G03 | 工作台身份 schema DTO 共享查询与事务 | 14 | 163 |
| G04-master | 工作台主数据 工艺 日历与批次 | 88 | 362 |
| G04-execution | 工作台执行事实 正式计划与排产运行 | 77 | 311 |
| G04-trial-reports | 工作台试调采用 报表分析与校准 | 35 | 145 |
| G04-system | 工作台值班台 外协与系统维护 | 28 | 112 |

- `G05`：source_entries现为Main实际固定959条，逐项与source-plan73045ad0完全一致；638 sealed06、97 precise original test overlays、224生成资产。旧695保留为历史recipe，不再充当取源依据。Main声明的216个验证目标含177个本cohort文件与39个既有底座文件，不是216个已通过文件。
- `G07`：registry/cache/import-scanner 全局合同，仅 12 个测试文件；技术债务治理台账纳入本组。
- `G08`：迁移证据索引与阶段文档。`G09` 的旧 UI 退役删除列表仍由 Main 另给，不阻塞历史依赖先归档。
- 表内数字是**源文件数**，不是selector或通过用例数。已完成的中间HEAD只按对应定点回执记结果；完整G05集成与最终门禁仍由Main在最终独立树验证。
- 混合路径先在 G02 保存原版，后在其领域组叠加当前版；`overlay_after_this_group` 和 `files[].original_commit_group` 保留这条关系。
- 不把原有 .limcode 技能、流程说明、共享调用图、dirty dead-code 基线、缓存、运行 DB/日志/备份夹带进去。
- 清单 hash 是读取快照。Main/C/D/E/F 后来新增或修改的已授权文件须在最终冻结时补入，不因旧清单遗漏而丢交付；此处不重新全树扫描。

读取Main实际G05固定959成员；原MEMBER_ONLY小文件只保留为先行交接证据：

```bash
jq -r '.commit_groups[0].source_entries[].path' /Users/lurenxing/GitHub/----/output/workbench-migration/verification/round2-20260910/G05-main-source-plan.json
```

### v3 定点归属修正

- `tests/gate_meta/test_test_support_dependency_boundary.py` 从 G02-runtime 移至 G07：该全域支持边界合同依赖后续 Gantt/resource-dispatch helpers。保留 source-RauBC6 原版/hash，G07 的单路径 source_overrides 明确覆盖组默认 current。
- `tests/web_pages/test_routes_a4_dependency_boundary.py` 从 G02-runtime 移至 G02-reports：全域调用方迁移合同须等四个历史组的调用方到齐；旧 wrapper 保持兼容不等于调用方迁移已完成。源/hash仍是原归档。
- Main 实报：26目标首次collect失败；移出全局support合同后的25files suite为222passed/1failed，唯一失败为A4的全域调用方依赖。两次失败记录保留，不删除断言或最终登记。
- 修正后 G02-runtime 为69路径/24测试文件，G02-reports 为43路径/16测试文件，G07 为29路径/12测试文件。这是执行顺序调整，不是修改后的24目标已重跑通过；实际验证由Main继续。

### Main 已完成 runtime 归档

- G02-runtime 已提交：5a9ac29c6ef78b9f7d1287e044c1d44471e6ada0。Main 实报提交后独立 clean worktree 的24目标为220 passed / 9.55s，全部hooks PASS；这是该组定点证明，不是完整门禁。
- Main 实报原工作区69文件前后hash相等、nonselected index entries完全相等、cached为空，原HEAD已CAS快进；未覆盖原工作文件。原报告证据引用为 output/.../round2-20260910/advance-5a9ac29c6ef7.json/index-before，本任务未独立重跑。
- 下一组为 G02-algorithm，仍按source-RauBC6原始hash归档，不换用当前新产品变更。

### v4 算法与报表配对修正

- `core/services/common/overdue_calculations.py` 的原归档版本从G02-reports前移G02-algorithm，共用交期/max due合同与相应用例同组，保留原SHA。
- 两份 `test_downtime_impact_missing_machine_degradation.py` / `test_downtime_impact_overlap_merge_degradation.py` 从G02-algorithm移到G02-reports，随其真实report/downtime_impact.py和report_degradation.py产品依赖归档。
- Main实报首次53目标为912passed/7failed/41.83s；失败日志保留。本次仅调整来源与执行顺序，不改修复代码、测试、断言或登记，也不声称调整后已复跑通过。
- 当前algorithm为140路径/51测试文件，reports为44路径/18测试文件；三条源hash均仍来自source-RauBC6。

### v5 已提交算法与导入，G08最终刷新

- Main实报algorithm提交8c89efdff33a9d277cadf2fbcff0a1ff300c9407，postclean51目标913 passed / 66.93s。pre41.18s负载不同，不作性能证据。
- Main实报imports提交2bc4851623f93b3147470975eed64a2374eebde7，40路径、postclean6目标224 passed、hooks PASS；首次223passed/1failed日志保留。本任务未重跑。
- `scripts/convert_rotary_shell_unit_excel.py` 原版补入imports，原SHA `3ed43e240a70fedd592074d800903f50e6955d4eb40657596a1b2a0b0ba32672`；current SHA `812d2106d224c648d7c6dc58c664452e3c3c743147397a618546cd5a8c5c3ee6` 确有后续差异，G05 overlay保留。不以current替换历史原版。
- 下一组reports保持44路径/18目标。G08纳入Main更新的ARCHITECTURE/workbench-shell/VISION及生产流程需求和其明确引用的foundation合同；commit_ready=false，全部文档需最终从current重新抓精确hash，早期source_entries hash不得直接用于G08提交。

### v6 current来源约定与历史组完成

- Main实报reports已提交f454b3bf7eeab831fd2695b2284fe0f208bb725c，44路径、postclean18目标198 passed / 9.67s、hooks PASS；原working bytes和无关index保留。本任务未重跑；四个历史组完成不等于完整门禁通过。
- 下一组G03逐文件使用 `source_entries[].source=current_snapshot`；source_root是原仓库。外层 `source=current` 只是简写，不能传给仅接受original的stage_archive，更不能将current改名伪装成original。
- `original_restore_check` 取source-RauBC6/restore-check原manifest同版；`Main_rebuilt_payload_required` 取Main最终构建并核对manifest的payload。完整机器约定见source_key_contract。
- current组需先逐文件hash自检并冻结，差异必须明确记录；G08全部重新取最终current hash。readctx/helper按Main实际collect缺项前移具体文件，不扩大搬迁、不增加修复代码。

### v7 G03被动包与叶支持

- Main实报161个current源hash匹配，15目标首次7个collect错误仅缺叶支持。依实际读取把 `test_foundation_dependency_scope.py` 移G05，随scripts/workbench与prototype的build analyzer依赖归档。
- 前移G03的六文件：core/services/workbench/__init__.py、web/routes/workbench/__init__.py、read_context.py、write_context.py，以及tests/workbench/execution_ledger_migration_support.py和plan_catalog_support.py。前两个包仅被动docstring，后四个是已有publicregistry/coremodels或SQLite/schema支撑的叶。
- G03现166路径/14测试文件，全部保留current_snapshot来源和原已登记SHA。不前移registration、factory或wholeweb。本任务只改归属元数据，未复测Main测试，也不把新清单称为已通过。

### v8 精确expiry与EOF观察

- `web/public_token_registry.py` 的current overlay由G05前移G03：write_context需要`issue_public_token_with_expiry`。v7提到的已有registry不足以提供该current API；原G02-runtime归档版本和SHA原样保留，只更新后续overlay指向。
- G03现167路径/14目标，G05现533路径/68目标。Main报告的collect问题按依赖配对记录，本任务未复测。
- Main执行diff --cached --check仅有3处new blank EOF：core/models/workbench_trial_adoption.py, tests/migration_db/fixtures/schema-v4.sql, tests/workbench/plan_identity_support.py。按要求保留源文件原样，特别是schema-v4历史DDL；记录为未通过diffcheck，不写成PASS，不当作runtime错误，不改规则。

元数据自检同时把历史条目的后续overlay指针对齐到现行files归属，消除旧G04/G06及pending_assignment名称。该对齐不改变任何组的pathspec、测试目标或源hash；entrypoint仍留G05，只有current registry前移G03。

### v9-v10 已完成G03，刷新领域current

- 四个未被G03测试使用的helper按Main实际依赖后移：process_commands_support.py、process_identity_support.py到G04-master；run_schema_migration_support.py到G04-execution；outsourcing_identity_migration_support.py到G04-system。不改imports排序、Ruff配置、断言或源文件。
- Main已提交G03 830a58e69faaa64a39d7a238ba2a0a0cd5c9047c，163路径。仅G03-postcommit-bound.log作为本组clean绑定证明：HEAD before/after同830a58e6、git clean before/after，14目标419 passed / 59.29s，hooks PASS。较早G03-postcommit.log与提交时机交叠的额外419passed不作clean proof；本任务未代跑。
- 原HEAD CAS、逐163 index附接、working bytes与nonselected index保留由Main报告，非本任务Git写入。
- 按Main要求仅刷新四个明确领域组：G04-master 399路径/9变化；G04-execution 361路径/13变化；G04-trial-reports 178路径/11变化；G04-system 109路径/9变化。共1047路径，读取期间每组size/mtime/inode稳定；不是全仓扫描，不是测试通过证明。
- 新增 frontend/workbench/app/ProcessReadView.js 归G04-master，1586 bytes，SHA-256 21e69a0e00188c429e710a59b2a1763ddfe1228ddd2970d0f3c79f515e99b559。G04-master当前399路径/116测试文件，不使用旧v2 current指纹。
- 采集结束UTC：2026-09-10T12:42:50.624561+00:00至2026-09-10T12:42:51.126693+00:00。全部本次新sha256/bytes/mode已同步source_entries与files，并在current_source_capture保留旧新变化表。
- G05共享宿主/构建及G08文档仍须Main在其最终冻结时刷新；本次不声称这些组已拥有最新全量hash。
- files副索引和历史overlay指针按唯一current source_entries归属对齐，修正先前短上下文补丁错位；组成员只按Main给出的helper移动及新ProcessReadView变化。写入采用全文精确替换，随后核对写后内容。

### v11 主数据领域依赖归属矫正

本节407为历史尝试，已由下方v12的405基准替代；保留当时快照和失败过程，不再作为当前提交清单。

- Main实报G04-master399首批21targets collect为9errors，缺少 `core/services/process/workflow_state.py`；前移7个process服务后仅 `api_responses.py` 导致2errors。Main补齐第8个纯共享叶后再验证21targets，本任务未代跑，不转记通过。
- G05的7个 `core/services/process/` 当前入口/服务整体前移G04-master：`__init__.py`、`part_operation_hours_excel_import_service.py`、`part_service.py`、`quota_protection.py`、`route_parser_constraints.py`、`unit_excel/__init__.py`、`workflow_state.py`。第8个是 `web/routes/workbench/api_responses.py`，SHA-256 `4a3d69d49e614ee662c3ee8b091a9d4342176df26ba869bcf7f9568eca8d1f92`。
- 当前基准407=原399+8，本任务新test delta为0；G04-master407路径/116测试文件，G05为525路径/68测试文件。原399及这8条均保留已登记SHA/bytes/mode，不把后续新增probe/test并入这次已拍快照commit。
- 7个process当前路径于UTC 2026-09-10T13:14:33.205575+00:00、api_responses于UTC 2026-09-10T13:16:22.808866+00:00只读核对，均与已登记指纹一致。
- 原G02全部冻结source_entries及SHA/bytes/mode原样保留；这8条current从G05删除重复交付位置，并在G04-master、files副索引及execution_groups保留，不删除retained overlays。
- 按此前授权同时刷新现有G04-execution361路径（3变化）与G04-trial-reports178路径（1变化），采集结束UTC分别为2026-09-10T13:16:22.796378+00:00、2026-09-10T13:16:22.808810+00:00。读取期间两组文件stat稳定，旧/新指纹表保留；这是时间点快照，不是已测试或全final声明。
- 新C final_master probe/test只列在 `pending_supplemental_current_files` 后续队列，不进入master407。Main的WorkbenchCaption/PageContext/Boundary/Navigation、navigation_boot与final_foundation/navigation、容量CLI补充明确列G05待最终抓取；F13新叶仍施工，其他跨域final测试等Main配对，未假称commit-ready。
- 最终API集成与fullgate待G05完整接线后由Main执行，不强求每个中间HEAD全站可运行。本任务仅维护指定职责文档，无Git、产品、测试、host或生产库操作。

### v12 包公共导入面随调用点后移

本节405为历史中间基准，现由v13的364基准替代；两个init留G05的决定继续有效。

- 当前提交基准为405=原399+5个process实际业务叶+api_responses，后续delta当前为0。G04-master405路径/116测试文件；G05为527路径/68测试文件。新增probe/test继续单列后续补充，不并入本次cohort。
- 将 `core/services/process/__init__.py` 和 `core/services/process/unit_excel/__init__.py` 两个 `current_snapshot` 原登记版本从G04-master放回G05；它们收紧的是公共导入面，须与Main报告的web/bootstrap/request_services、equipment等5个调用点同期交付，不能提前套在旧调用方上。本任务未重新枚举该5处，不虚构完整path列表。
- Main实报：21个测试文件收集后，autouse factory因旧OpTypeService导入入口消失产生1907 setup errors，没有业务assertion失败；完整失败log保留。消息未提供精确log路径，本任务未代跑，不转记为独立复核或测试通过。
- Main仅恢复私有staged副本中的两个init为已有HEAD版本，不碰原树、产品代码或测试。G05最后仍apply原登记的收紧版本；本任务不为中间HEAD篡改产品导出接口或测试断言。
- 两个当前init的SHA/bytes/mode完整保留在G05，另6个前移叶留G04-master；source_entries、files归属、pathspec、execution_groups与计数同步。原G02的293条冻结源记录原样不变，所有后续overlay继续保留。
- v11执行域/试调报表域的时间点指纹和新文件后续队列保留；本次v12只修正包入口归属。最终API集成与fullgate仍待G05由Main完成。

### v13 跨域闭包后移与最终待归档队列

本节364为历史中间基准，已由v14的362替代；41项留G05与本节时间点later_queue继续有效。

- 按Main只读依赖分析，将41个tests/workbench Python文件整体从G04-master移G05：27个测试target、14个support。采用 `G04-master-staging.json#deferred_integration_source_entries` 精确版本，41条SHA/bytes/mode均与此前登记一致；不根据当前树擅换版本。分析SHA `488eae5212fd7db31d3ec9d67d3018e39eea162bc7de30baa72903b4f2e727c6`，暂存回执SHA `f4fb1b153cd0b855e741237ad9ef3a4a27951ab16613f6921b7a32251159710d`。
- 当前G04-master为364路径/89测试文件，G05已登记568路径/95测试文件；两组target并集原样保留。18个Ruff I001由Main识别为后续execution/calibration/host缺位导致第一方导入分类变化，不把它们伪格式化成thirdparty，不改测试、忽略或最终登记。原G02的293条冻结记录与两个G05 init原样不动。
- 四个精确同路径delta（H的process_v22_migration_support.py/test_process_workflow_schema.py、C的ProcessWorkspace.jsx/MasterOverviewWorkspace.jsx）只保存Main已验证私有暂存回执；实际commit hash尚未收到，未刷新这四条正式source_entries。
- 资源API两节点保留在 `pending_main_execution_receipts.deferred_api_nodes`：`test_unrelated_bad_capability_does_not_block_real_crud_and_supplier_repair`、`test_bad_skill_can_be_selected_and_repaired_through_real_api`，均位于tests/workbench/test_resource_metrics.py。它们要在G05完整factory与最终门禁执行；中间HEAD的404不写成当前完整产品bug。1196passed是Main阶段进展，不是364全组、原116targets或最终门禁通过；18纯域与3混合API分账继续，A未代跑。
- 本次有边界的源码读取于UTC 2026-09-10T13:43:08.488330+00:00结束，3468路径读取期间stat稳定；这是并行施工中的时间点观察，不是最终冻结。发现111个新路径、57个已登记后的current差异、2个原HEAD文件的新增overlay。没有修改这些源文件，也没有用观察值重写其他source_entries。
- `later_queue.entries` 共215条、每路径唯一delivery_group和负责任务：G05 199、G07 12、等待Main实际commit回执的G04四条4。负责任务是交付/复核责任，不猜测作者；新增41条跨域文件也在队列中标明“已按暂存版搬组”，不会二次交付。
- 门禁AST读取为583 required、91 supplemental，共674唯一路径，重复owner为0。final命名且有静态测试定义的35文件中，7已唯一登记，28明确排队等域交接后由Main/H处理；不是A自动登记或通过。test_final_master_acceptance.py实际是命令行验收器，无pytest测试定义，不误算target；Python helper和CJS probe分别保留。
- 7个含已归档历史版本且当前又有差异的路径、H两个此前未进入清单的懒导出文件均已保留后续位置，不因旧commit完成而漏掉。详见 `G05_final_boundary.current_diffs_after_archived_versions` 和later_queue；旧版本指针保留，最终需Main确认新版本与配对回归。
- G05当前可投影691条候选路径（包含已有568），另预留12个当前build-order新增编译输出槽位；均不是commit-ready。最终必须用Main实际manifest补齐/替换content-addressed资产，不能拿原212份生成物hash冒充最新payload。G07的12条registry/gate增量是明确另批，不会从最终交付中消失。
- 已覆盖最新navigation/layout、G旧入口解析和F的dashboard analysis/candidate服务/API/UI、系统备份下载等边界。最新读取已见dashboard.py导入并注册dashboard_analysis.py，早先“尚未找到接线”的观察不再当当前结论；静态出现接线仍不等于真实API/浏览器已通过。后续新建或变化须再按final current manifest与Main回执对账。

### v14 操作工资质测试随执行域归档

- 将 `tests/workbench/test_operator_qualification.py` 整文件及唯一helper `tests/workbench/operator_qualification_support.py` 从G04-master移至G04-execution，保留原source/sha256/bytes/mode与采集时间。当前Master362路径/88测试文件；execution363路径/128测试文件。Main纯域验证子集18→17，与整个组的测试文件数分开记录。
- 测试真实使用GreedyScheduler（test文件:8）、ScheduleService（:17）、run_schedule（:85/:162）和手工操作（:180/:184）；helper也依赖ScheduleService（:23/:79/:86/:97）。所需 `core/services/scheduler/operation_edit_service.py` 与 `core/services/scheduler/run/schedule_input_runtime_support.py` 本就在G04-execution，未提前搬产品入口。
- 静态检索tests/core/web/scripts/tools，仅在test_operator_qualification.py:20找到该helper的直接引用；未发现其他直接引用，不声称穷尽动态加载。execution现有依赖已包含G04-master，不新扩依赖边。
- Main报告1415passed后，旧手工consumer返回ValidationError，而本测试期待OperatorQualificationError；记录为中间HEAD分组依赖，未据此断言当前完整原树存在产品故障。本任务未代跑，不改断言、Ruff分类或产品接口。
- G05既有41项闭包、95个测试文件、全部最终登记和defer节点均保持；其他source_entries不变。原G02与两个deferred init不动。四个H/C私有delta仍仅引用暂存回执，等实际commit hash再刷新正式指纹；G04和最终门禁均未标通过。

### v15 固定Master提交与下一执行快照

- G04-master已真实提交 `4b418d1784947abb7eef5e2747cd05b5c83b171f`，362文件。实际 `G04-master-staging.json` 的copied362加verified_source_refresh5条是本次源指纹权威；本任务逐362个私有文件核对SHA/bytes/mode全部一致。包含后来明确的test_resource_schema.py第五条刷新，不遗漏，也不把后续共享UI改写进提交证明。
- 已读取postcommit-bound JSON/log：前后同HEAD且私有工作区状态为空，17文件1666passed/51.78s；提交前1666passed/52.86s与正常Ruff/artifact/commitmsg hooks由Main报告。这里只是17文件定点证据，不是本组88文件、原116目标、完整门禁或最终HEAD全站通过；原分支附接完成状态不由A猜测。
- 本批G04-execution固定为312文件：175产品/工具、77个有pytest定义的测试文件、60支持文件。机器入口仍为 `execution_groups[id=G04-execution]`，逐路径source/sha256/bytes/mode在对应source_entries；快照UTC 2026-09-10T14:21:25.840749+00:00，Main冻结私有副本时必须精确匹配。不再追逐后续D/E新UI增量。
- 永久配回8个已有产品叶：现场报工production_report的3文件、field_report_files的4文件本属执行事实，另trial_adoption_storage仅提供已存场景读取/校验，直接支撑plan_projection/point/baseline。不是临时未提交deps；其余trial/adoption流程不提前。D的run_candidate_delivery与当前actual_gantt直接导入的actual_gantt_chain两新叶已在这一已闭合快照中，之后新叶另入later_queue，不再扩大本批。
- 61个未来域/HOST/浏览器Python文件（49原测试文件、12支持文件）连调用者闭包移G05，精确原因见execution.dependency_closure。包括sys.path之后的本地test_live_browser引用，未只看全限定import。原41项G05闭包和两项qualification→execution配对保留，未改代码/断言/registry/忽略。
- 当前312集合对初始HEAD加已观察提交版本的1994个Python模块作静态依赖核对，未来产品/测试模块缺项均为0。早期静态具名导入也未发现缺名；动态导出、真实运行和hook仍须Main验证。preflight的create_app确认是自己的Flask/Blueprint隔离fixture，不误作生产factory。
- 首轮可执行纯域列表为 `commit_groups[id=G04-execution].verification_plan.first_domain_targets` 的69文件；另3个既有纯域文件和5个容量supplemental文件单列，不自动复跑正式5000容量。test_actual_gantt_live_server.py与test_round1_field_piece_files_probe.py没有pytest定义，归support而不虚计测试目标，源码继续保留。
- ResourceControls.jsx（996b7e3f...）、ResourceTableFilter.jsx（c4f1c48b...）及modal_focus_probe.cjs/resource_table_header_probe.cjs/test_resource_table_header_widgets.py的当前差异单列 `post_master_shared_overlays` 与G05队列。四路径确在Master362，modal_focus_probe.cjs原已属G05；不把它伪称Master提交内容。已提交362条保持固定源hash。
- 只维护授权JSON与本说明；独立ledger的base64/string和此前已提交各批source记录保持值完全一致。没有A的Git、产品、测试、构建、host或生产DB操作；recipe依赖闭包不是测试通过声明。

### v16 固定缓存与归档基础

- 最终机械输入改以Main已暂存的 `G04-execution-main-source-plan.json#commit_groups[0].source_entries` 为准，manifest SHA `873748cc314a4eb28fb948f2b90c73236f4c30d5b0acbc92a3d7f5d06e5856d9`；311条逐项与G04-execution-staging.json的source/SHA/bytes/mode一致。未再次读取源码重算hash。Main已私有暂存并运行正常Ruff/69验证，未提交、未标passed。
- 本批可stage：311=21条 `pre_retirement_restore_check` +290条原值 `current_snapshot`，69个首轮纯域目标完全不变。
- 21条从 `output/workbench-migration/baselines/pre-retirement-LqHg4q/restore-check` 实读SHA/bytes/mode；包括20个指定耦合基础与preflight_browser_probe.cjs。该probe为12611 bytes、mode 420、SHA `e3de5eed8b2e4c4160e0eb275e196bee476c563792007e70bc1941f62419f25f`。
- 290条字典值完整保持v15原样，current根改用 `/private/tmp/aps-r2-execution-current-qvXGNT`，作为Main helper第三CLI参数。cache manifest SHA为 `76eb75fba63c24006de6e27860791159763bf939636809ccb07ff64392630d10`；未重读原树刷新这些SHA。
- actual_gantt_chain.py移G05；21个current版本和之后D/E增量同样保留为G05最终overlay，旧观察SHA不得冒充已保存字节，最终只提交实际差异。归档版actual_gantt的5项第一方导入最小核对闭合，且不导入新chain；没有重开全量依赖扫描。
- 已提交362及其他已提交批次记录、独立ledger全部base64/string在机械JSON写入前后严格相等。只改授权JSON和本说明；原working、Git、测试、registry、host/DB均未操作。实际stage与69文件测试由Main执行，不预记通过。

### v17 下一试调报表组准备

- 只读取Main固定根 `/private/tmp/aps-r2-trial-reports-current-wttgi1`；manifest SHA `db82d27fa0063515e50a05b7d1d3fcb06b85a721aaf5555add64a192e0e46849`。170份实际缓存字节均与manifest的SHA/bytes/mode一致，分析前后无变化；未用v16旧指纹或变化中的原树代替。
- 以私有HEAD 4b418d17和已暂存311文件为依赖底座，缺3个本域固定产品叶：`core/services/workbench/calibration_table.py`、`web/routes/workbench/calibration_read_context.py`、`web/routes/workbench/calibration_table.py`。Main补入同一cache并更新manifest后才可完成产品闭包；A不复制原树或修改private checkout。
- `trial_reports_preparation` 已保存32文件的G05拟分流闭包（23测试、9支持）及逐项依赖；剩35测试分为32个首轮纯域目标和3个规模目标。当前stage_ready=false，未提前改现有source_entries或把尚缺产品的批次记为可stage。
- 执行311/69仍由Main验证；3个formatter SHA没有抢写，未记commit/pass。其余批次、ledger字符串和ownership矩阵均未动，未新建runner或执行测试。

### v19 按Main实际回执对齐（历史状态，后续由v20补齐）

- **唯一机械输入为Main实际142份plan，不再采用临时小交接。** `output/workbench-migration/verification/round2-20260910/G04-trial-reports-main-source-plan.json` SHA `ef683aa5bfbbfc5bec05c472fd765e0bce5101064e858fd93414722c0c6a2ee8`；实际staging.copied142逐条匹配。此前计数保护阻止的尝试未复制、未stage源码，不是产品测试失败。
- 固定174份中，32个未来域/host导入闭包文件移G05；本批保留142份：82产品/工具、35测试文件、25支持文件。5份ledger测试及其helper、3份gantt混合源码都留在本域，仅延期相应运行；没有从最终registry删除目标。此前136/38等临时分组已由实际回执取代。
- 首轮实际46个非规模selector为24个整文件、另1个整文件、21个纯函数前缀，2个规模文件单列。精确顺序在Main plan中；源码组的35个完整测试文件单独保留，selector数不是用例数。
- 模型 `core/models/workbench_calibration.py` 作为G03后续overlay，固定SHA `fa2e274d1764da99ce19a0dc2cd617b5a399a30664163c633d7518f673eeda0c`、5108 bytes、mode 420。原G03 SHA `a1f77bbc8a468c7a1653467e2beb69246027197128be45d5df9e85cbe9321519` 没有改写，其余170份原树源码未在本次同步中重取。
- **首次运行失败，原JSON/log/XML全部保留：332 passed / 11 failed / 46 errors，61.87s。** 证据为 `G04-trial-reports-precommit-1.*`；JSON SHA `e9478c8c8e012e12433180a205fe94b55c2e660b7ef5f1a94dd986d410d4cf86`。前后同21134f73与status指纹，但不是clean或source-guard proof。
- 46个setup error来自fixture仍patch `calibration.datetime`，与产品提取 `calibration_read_context` 后失配。Main已在staging.verified_source_refresh记录唯一helper：SHA `3747c8b4a116d685a5e7700a3781e2c7f0a27826de3c7f23d47ec994212475c4`、4584 bytes、mode 420。source_entries采用copied加这1条已批准刷新，初始copied和旧SHA仍是首次失败来源。
- Main随后4个校准文件（含scale）85 passed / 14.19s，见 `G04-trial-reports-calibration-2.*`。仅为staged树的校准定点结果，不覆盖46-selector全套，也不是commit/clean证明。3个历史gantt迁移fixture由H最小修复，仍等回执；不改schema、不弱化旧断言。
- 8个failure来自 `test_trial_predecessor_labels.py` 经Node调用G05的 `scripts/workbench/compile.cjs`，暴露原静态分类漏掉非Python入口。源码留本域，仅延期中间运行，最终整文件运行。先前静态Python具名缺项0不代表实测闭包0缺项或全部纯域通过。
- G05须整文件复跑本批5份ledger、3份gantt及predecessor labels，共9份；另保留G04-execution的2份混合full_app文件整文件复测义务。Main当前142仍未commit；A没有测试、fixture、原源码或Git操作。
- 三份文档同步为v19，G05为683路径/167测试文件；原G02/G03已提交源记录、独立ledger以及原206规划和1052条建议动作状态保留。这里只更新来源、实际回执及下述独立范围决定。

### v20 第9、10批实际提交与G05小交接

- **trial实际145文件已提交 `3f26925edf3935c960ef73e475f2430011ffa4dd`。** 源码为staging.copied142加3条verified_source_refresh及3份历史SQL；与 `/private/tmp/aps-r2-trial-reports-final-AjT0rd/capture-manifest.json` 的145条元数据一致。staging SHA `4d9c4442a0ac9efdaf451cb97b299dee41255421070aea24ea98daff6162dba5`；本轮未重读产品/fixture字节。
- 最终49个selector pre **399 passed / 119.06s**，同组post **399 passed / 122.25s**；post JSON前后同3f26925、clean_before/after与same_head均true，pre/post用例标识一致。post JSON SHA `12ebddf0ccda12b01206bd898b97a6b5658b0a46afec900c384f0a40c437fb10`。初次332/11/46、校准85的局部记录及Node/full-host完整文件义务全部保留，未改记为35个源测试文件或全门禁通过。
- **system实际112文件已提交 `0cab59b6970a86393f610a2838feed9efc7523b2`，不是初stage124。** 65产品/工具、28测试文件、19支持文件，逐条采用 `G04-system-staging.json.effective_source_entries` 与 `G04-system-final-source-plan.json`；后者SHA `3dad2fd19bae11823725e6f4feb02e8166bf0d8b55952201eb654e746fd0df22`。
- 同一staging的12个deferred条目完整移入G05，10测试加2支持；保留初124固定cache及 `/private/tmp/aps-r2-system-deferred-FOHoga`。10个Ruff I001原文件在完整F13-source9通过的Main回执及逆向闭包决定保留，不格式化、不ignore、不删最终目标。
- system相同22个整文件 pre **277 passed / 55.63s**，post **277 passed / 52.28s**；277个用例标识一致，post前后同0cab且clean均true。3条record_property/xunit2兼容warning未过滤。post JSON SHA `c1d90117edbeee60c547b8ef209728e1fbde9a606ba5455598e12cae5a225478`。**原38个测试文件全部保留最终G05整文件复跑要求**，不是本次22文件已经覆盖全部38。
- 两批正常hooks通过由Main提供，A未重跑；`advance-3f26925edf39.json` 与 `advance-0cab59b6970a.json` 均记录CAS附接、原工作文件保留、无关index保留、original_working_files_written=false。这里引用历史回执，不宣称当前共享dirty为clean。
- system的 `core/models/workbench_system.py` 只追加本阶段query_input_type/status choices overlay；原G03源记录完全保留。原G01/G02/G03/master/execution记录、独立ledger所有字串、206族及1052条建议动作状态均逐项保持不变。
- **先行小交接已独立落盘：[round2-G05-member-only.json](round2-G05-member-only.json)**，SHA `2c3d4e97b79196940206fa2b4d175655aebfaf634aa3ae2fa6c4f2d402b55327`，状态仅MEMBER_ONLY：255产品/工具加384基础测试取E sealed06；96个D/C/B/H测试及支持候选待Main精确冻结原树overlay；G04四批全部146个deferred路径已校验无遗漏。新D PlanProcessOrder与Main build-order、E/F重新进入/恢复差异、Main nav/shell/CLI、H typing、B guard和C新测试均有成员索引。
- 产品/基础源根为 `/private/tmp/aps-final-e-sealed-read-after-20260911-06/source`。资产只取其 `reentry-final-01/full-build/static/workbench`：223个manifest payload成员加1份asset-manifest.json，实际文件名集合无缺项；build ID `86bae55877b7574a7dbccad0a61c2f4b714a3105500908d614b531ae31f90a2e`。A只核对成员，不冒称重做payload逐字节校验，不使用current original旧构建。
- G07的29个独立gate/registry成员另列，不因小名单混入G05产品提交。6个尚未进入sealed06的原树测试/支持新路径显式列为overlay候选；取源优先级和精确指纹由Main固定回执确定，大JSON旧hash不得反向决定源。
- 本次只新增小JSON并同步原三份文档；未执行Git、应用导入、测试、构建、宿主、产品/资产/fixture写入或数据库操作。v20源清单SHA `5255f780f760573ad86a186da52ee0b9be19fb0ea061bead12ddaf3cd221064c`，ownership SHA `b7063531b12a040d2954e43918e5997202103bc1edf3451cc97818857417c0e9`。最终G05、完整门禁及能力验收仍未记通过。

### v21 Main实际固定959源回填

- **G05唯一实际取源计划**：`output/workbench-migration/verification/round2-20260910/G05-main-source-plan.json`，SHA `73045ad0ba333ecdbb269a3cbb2078b9d84fbe00f1ef2297eabc0b7483b37d9b`；固定capsule为 `/private/tmp/aps-r2-G05-frozen-1Ebhk8`，parent为0cab59b6970a。本轮source_entries保留Main原959条字典，path/source/SHA/bytes/mode及顺序完全一致，不添加猜测的source枚举或从原树重新取字节。
- 实际 **638 sealed + 97 precise original test overlays + 224 generated assets**，其中资产是223份payload加asset-manifest.json。Main计划记录315 build inputs与combined private0cab底座匹配、source_changed_during_capture为空、original_working_tree_written=false。A核对实际回执元数据，不冒称重跑源守卫或build输入验证。
- 与先行小名单相比路径集合不变；唯一明确取源变化为 `tests/workbench/final_execution_source_binding.py`，由sealed转为original exact overlay，Main解释为derive CLI-only delta，未改产品input。原小名单的639/96与SHA `2c3d4e97b79196940206fa2b4d175655aebfaf634aa3ae2fa6c4f2d402b55327` 原样保留；实际源以638/97回执为准。
- Main计划声明216个验证目标，177个在959源cohort内，39个已在此前提交底座。后39个目标全部能在原10个commit的源码记录中对应，不为它们扩写959，也不把新test目录成员默认当作已经选中/通过。原146个G04延期成员及system38整文件义务全部保留。
- 原G05的695条观察源保留为历史recipe；旧 `static/workbench/assets/foundation-c6054c2ae97a14f0.js` 不在实际新manifest，其原index/source metadata转存 `historical_superseded_file_records`。A没有删除原资产文件或修改任何旧证据。
- 326条已有later_queue候选已对入这份固定capture并保留原观察内容，不改记commit或验收通过。后续D/C及其他授权小delta必须另给Main精确overlay回执，不混入原959 source-plan，不抓moving original hash。
- 本轮只继续维护原三份文档；其余10个已提交group、独立ledger字串、206族及1052条建议动作状态完全未变。状态为 **captured，不是已stage/commit/测试通过**；完整G05及最终门禁尚无本次通过声明。
- v21 source-scope SHA `0cbf81076fd02e172627a6d2b5b72d94f8cebbb5ad66a897178533f29320e236`；ownership SHA `523d892091d069068be10bbc8554f217b1ac61baa1dbd11c153903bf6cef4b5a`。

### DETAIL-008 独立范围决定

- 根据Main自有[范围决定](round2-main-decisions.md#wbp-detail-008)，`WBP-DETAIL-008` 为 `not_applicable_confirmed_unreachable`。只适用于冻结原始前端设计14工作区加trial-sample的15入口及其可达关联闭包，不外推任意历史页或未来版本。
- 该1族及ID独立保留，不删除原206规划，不计入其他205族的生产passed。ownership只解决适用范围pending；1052条建议动作B/K/V/P没有改成通过。Main保留的1条历史启动错误也未被省略成原型完全无错误。
- A本次只读Main决定文件并引用其证据，没有再次读raw、看图或运行浏览器，也没有自动退役或新增入口。

## 台账独立保存

`开发文档/技术债务治理台账.md` 不在两份 source.tar 的原始源码树里，不能声称 5384 已包含。已在 `round2-source-scope.json#/independent_ledger_preservation` 保存可还原的 base64 原字节副本：

- 当前台账：89,128 bytes，SHA-256 `417cc9a398fc0ab847511471434ce5864138f252774683c5336b6088787625cd`。
- 既有 Round1-before 台账：72,871 bytes，SHA-256 `ff48b185d7a9cc45e3d0092405c4b7ca4d10f48d4ff6c70135f655f4135634db`；同时保留已有 `ledger-preservation-proof.json` 内容。
- Round1-before 不冒称 source-RauBC6 采集时刻的完整台账。原迁移前 patch 仍在旧归档的 `unstaged.patch`。
- 本任务只读取并写入指定 JSON，没有改原台账，也没有把副本还原到生产或共享 dirty 路径。

## 非阻塞后续

- `round2-capability-ownership.json` 已保留 206 族：Main 9、C 58、D 37、E 69、F 33；1052 条为拆解**建议**而非已批准分母或通过数。
- 原 planning JSON 未改；历史 feature 证据只作为入口，不转记 passed。
- `DETAIL-008` 已引用Main限定15入口的独立 `not_applicable_confirmed_unreachable` 决定解决pending；保留ID与原206规划，不计生产passed、不自动退役，不外推其他范围。
- 正式容量结果由 Main 报告：5000x4=20000 rows、admission_to_terminal 122.728285375s、runtime 121.342296s、1472 inputs 前后 hash 一致及重启保留。本任务未重跑，未将其扩写成最终 fullgate 通过。
- 本任务无产品写入、Git 写入、生产库/旧 preview 操作。只维护这三份文件；完整门禁、最终 source/payload hash 与新增在途文件由 Main 统一冻结。

## 两代归档现场核验

本任务用 Python 3.8.10 标准库只读执行 SHA-256、文件集合、大小与 mode 核验，没有重新解包、导入 app 或打开业务库：

| 归档 | 文件数 | 压缩包 bytes | SHA-256 | 现有 restore-check |
| --- | ---: | ---: | --- | --- |
| source-RauBC6 | 2273 | 20386110 | `5cf4ecc190bcafc11fb80bdccb40733e0e93624d86d8c2fc45854a224b900b3b` | 集合、逐文件大小/mode/hash 全部匹配 |
| pre-retirement-LqHg4q | 5384 | 70721290 | `8e0bb6b9f56132745d4095ea906a91d15a8f0b56eee47de32d239b4043feecf5` | 集合、逐文件大小/mode/hash 全部匹配 |

19:13:52 +08:00 读取时：原 2273 文件中当前 2173 未变、100 修改、0 删除；新归档 5384 文件全部与当前内容一致。旧归档未覆盖的新树不能一律称为迁移新增。

原 staged patch SHA-256 在本任务起始核验时为 `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`；后续 Main 受控提交导致 index 改变是已授权动作，不应误报为本任务破坏。

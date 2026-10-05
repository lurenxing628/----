---
doc_type: audit-reassessment
audit: 2026-10-05-redundant-guards
created: 2026-10-05
status: reviewed
scope: 上轮24组整体未修项、14组部分修复残留及3项门禁失败
implementation: completed
---

# 未修与部分保留项重新判断

2026-10-05 用户随后明确授权“该修的修，该 review 的 review”。已完成本文应修项的实施与交叉 review；最新落地结果、保留理由和验证状态见 [复判后修复记录](../../issues/2026-10-05-redundant-guards/reassessment-fix-note.md)。下文保留的是实施前复判证据与当时的只读边界。

## 结论

上轮把“现有设计”“当前合同”“低频”“HEAD 已有”过多地当作保留理由，部分裁决需要纠正。具体保护语义值得保留，不代表目前取得事实、编码、写入及暂存的方式都合理。本次重新沿真实调用者、输出字段和事务/时钟边界核验，下面明确区分应修、低收益可排后、必要保留和原主张不成立。

延续用户此前“留档”的授权，本次只追加复判记录，没有改代码、测试、业务库或治理基线。旧索引的“最终处置”是上轮实施结束时的历史判断；未修部分以本记录的最新判断为准。本次没有重新运行完整门禁，没有生产耗时测量，也不改写上轮测试结果。

## 最应先处理

1. **恢复终态不应依赖纯诊断整库 SHA。** `_perform` 已经确定成功、回滚或未改变后，强制 SHA 读取仍可能在终态 journal 写入前抛错。主代理纯内存故障注入确认：模拟恢复已成功，诊断读失败，终态写入为 0 次。取消强制计算，保留目标/保护备份的实际一致性比较及已确定结果落盘。
2. **单条写上下文 scope 过宽导致真实误失效。** 看板条目、报工工序、资源创建需要各自的相关事实，不能靠全域变化使一切操作失效。收窄 scope，同时保留完整来源、该工序全部历史和所选关系的 revision；不直接删除并发保护。
3. **试调结果被损坏页签记录隐藏。** 错误只影响采用历史筛选/分页，不应挡住已经合法加载的交付、任务和约束结果。保留局部错误、场景归属和明确清理入口。
4. **共同入口尚未迁移完整。** trial 存档双编码、双方 hash 仅为相等、工艺 guard 后重复读取、导入 checked 行再读取、报工原文件确认重解析、portable launcher 第二写入者均有真实残留。

## 24组整体未修项

| 编号 | 最新判断 | 证据、影响及合理边界 |
|---|---|---|
| 1.2 | 应修 scope，P2 | [dashboard/service.py:202](/Users/lurenxing/GitHub/----/core/services/workbench/dashboard/service.py:202)把全来源指纹放入单条 snapshot。无关资源/运行变化会使处置 stale。改为该条目的完整 `_facts`、来源、身份及评估状态；集合分页仍可绑全看板，不能只留下显示字段。 |
| 1.3 | 应修 scope，P2 | [execution/ledger.py:52](/Users/lurenxing/GitHub/----/core/services/workbench/execution/ledger.py:52)没有自身 reports/voids，却绑全局 clock。别的工序报工使本工序 stale；直接删 clock 又会漏自身新增/更正/撤销。用已加载的自身完整历史及当前 task/plan/旧事实绑定；全局 clock 仍供全计划消费者使用，无需新时钟表。 |
| 1.4 | 应修创建 scope，P2 | [resources.py:56](/Users/lurenxing/GitHub/----/web/routes/workbench/resources.py:56)、[85](/Users/lurenxing/GitHub/----/web/routes/workbench/resources.py:85)复用全域列表指纹；无关物料/批次变化能阻止新增人员。按 kind 保留真正所选工种、设备组、班次等关系并发保护，唯一性在写事务中复核；不要换成空状态 token。 |
| 1.5 | 应修误阻断，P2 | [TrialResults.jsx:47](/Users/lurenxing/GitHub/----/frontend/workbench/app/TrialResults.jsx:47)因匹配场景 history 中分页/筛选坏值隐藏全部结果。错误局限采用历史页，合法结果继续显示。localStorage 无法读取已经能显示默认结果，原“所有偏好失败都隐藏”说法不成立。 |
| 3.2 | 应收敛当前版本启动链，P2 | [database.py:194](/Users/lurenxing/GitHub/----/core/infrastructure/database.py:194)、[203](/Users/lurenxing/GitHub/----/core/infrastructure/database.py:203)在当前 v37 路径两次完整合同；中间只确保已有版本表，无业务结构迁移。统一事务边界后一次检查；新库/真实迁移后验证保留。内存显式 execute 计数一轮185、启动376；整目录 SELECT 20/40。 |
| 3.3 | 应共享同次结构事实，P2 | [migration_state.py:248](/Users/lurenxing/GitHub/----/core/infrastructure/migration_state.py:248)的聚合合同多次取相同目录、列、FK。一次结构快照供子合同消费，独立入口自取当前事实，不跨迁移缓存。查询次数不等于物理磁盘读取。 |
| 3.4 | 应清理3个完全重复索引，P2 | [schema.sql:214](/Users/lurenxing/GitHub/----/schema.sql:214)、[v13.py:48](/Users/lurenxing/GitHub/----/core/infrastructure/migrations/v13.py:48)、[schema.sql:515](/Users/lurenxing/GitHub/----/schema.sql:515)分别重复 OperatorCalendar PK、scenario source_draft UNIQUE、事件七列 UNIQUE。内存删除后查询仍使用等价自动索引，无 INDEXED BY 名字依赖。具名合同也应按语义收敛；需正常新迁移清理存量并重新生成 schema，保留历史迁移。 |
| 4.1 | 当前报工热路径主张不成立；旧链可另行收窄 | 旧写 caller 在 [resource_dispatch/actual_record_service.py:364](/Users/lurenxing/GitHub/----/core/services/scheduler/resource_dispatch/actual_record_service.py:364)，当前 web 无入口，当前报工使用新服务。反射导出/打包 anchor 证明暴露，不能证明实际使用。旧 start/pause/resume 与数量报工语义不同；先收窄旧写 surface/保留历史读职责，单独优化旧扫描优先级低。 |
| 4.13 | 无消费者 probe 应删，P3 | [batch/service.py:393](/Users/lurenxing/GitHub/----/core/services/batch/service.py:393)前置 probe 的 has_template_ops 没有消费，事务内重新读取模板。保留公开创建及事务内模板检查，删除无消费读取/传参；没有当前 UI 热路径不等于这种读取必须留。 |
| 5.3 | 应区分孩子变化与父齐套变化，P2 | [batch/materials.py:95](/Users/lurenxing/GitHub/----/core/services/workbench/batch/materials.py:95)把子需求变化并入父 changed，随后同值更新父表。到料0.4→1、父仍partial的内存探针使父revision 1→2。当前计划 DTO/计算不读这些物料子表，任务量来自冻结来源；[plan/queries.py:231](/Users/lurenxing/GitHub/----/core/services/workbench/plan/queries.py:231)还绑完整公共 data/projection facts。可直接父最终ready真变才写，孩子真变仍 committed；完整批次写 token 仍包含子事实。 |
| 6.1 | 应合并预览上下文，P2 | [resource_action_context.py:64](/Users/lurenxing/GitHub/----/web/routes/workbench/resource_action_context.py:64)已有随机、scope、expiry及不可变文档，第二 write token 重绑同ref/intent，无独立认证或新生产事实。一个共同预览上下文承担这些职责，字段shape可以保留；确认重建当前 proposal、operation绑定、replay先行保留。 |
| 7.3 | 请求内根目录 resolve 应合并，P3；长期缓存暂缓 | [assets.py:42](/Users/lurenxing/GitHub/----/web/routes/workbench/assets.py:42)每条路径重复 resolve 同一根目录。当前268入口，计数536次resolve可收为269。每目标路径存在/逃逸检查保留；整清单读取只在新页/刷新，未测到需要长期缓存的用户延迟。 |
| 7.6 | 同页事件重读应合并，P3；readback可暂缓 | [TrialViewState.js:112](/Users/lurenxing/GitHub/----/frontend/workbench/app/TrialViewState.js:112)同页两个hook都重新读取已保存值。Node计数4 getItem/1 setItem可收为2/1，保留写前合并、真实跨tab监听、失败重试。同页事件传已验证值。写后readback仅捕捉狭窄抢写，不证明落盘；删它收益小。 |
| 8.6 | 同权威对象的自摘要应收敛，P2 | [quality_gate_shared.py:1286](/Users/lurenxing/GitHub/----/tools/quality_gate_shared.py:1286)、[1038](/Users/lurenxing/GitHub/----/tools/quality_gate_shared.py:1038)、[1343](/Users/lurenxing/GitHub/----/tools/quality_gate_shared.py:1343)完整对象相等后再核其自摘要。内存探针显示仅过旧派生摘要仍拒绝同对象。新格式收敛；真正文件、日志、输出、缓存身份及差异解释摘要保留，历史证据不改。 |
| 9.2 | 三种职责保留 | [check_win7_build.py:15](/Users/lurenxing/GitHub/----/scripts/check_win7_build.py:15)核固定环境/冲突，vendored wheel冻结来源，[build_win7_onedir.bat:23](/Users/lurenxing/GitHub/----/build_win7_onedir.bat:23)实际import核可用性。metadata不能证明模块完整或来自固定材料。未找到应删的重复职责。 |
| 9.3 | t+x保留；100魔数应删，P3 | [Install.ps1:54](/Users/lurenxing/GitHub/----/packaging/win7/Install.ps1:54)写目标前验证和实际解压职责成立；[62](/Users/lurenxing/GitHub/----/packaging/win7/Install.ps1:62)的100下限没有清单生产者依据，不能证明完整性。逐文件、实际数量、禁止用户数据和唯一launcher检查保留。未确认当前包会触发此阈值。 |
| 10.1 | 缓存保留，SHA键可简化，P3 | [schema_declaration.py:73](/Users/lurenxing/GitHub/----/core/infrastructure/schema_declaration.py:73)只把SHA作为进程内8条解析缓存键，无持久/安全消费者。直接用schema文本键，字符串内容等价仍成立。按当前文本大小8份约2.46MiB，无需新依赖。 |
| 10.2 | 强制诊断指纹应清理，P3 | [schedule_delay_diagnosis_utils.py:94](/Users/lurenxing/GitHub/----/core/services/scheduler/schedule_delay_diagnosis_utils.py:94)每批及总报告计算；唯一生产页面/导出不消费。摘要只含证据行标识/排序文本，不含实际物料或停机值，无法证明完整输入相同。保留真实来源/时间/证据和判断过程，不换别的无用哈希。旧roadmap要求不证明当前价值。 |
| 10.3 | 两个字段可删，一个有人工用途 | [long_gate_collect.py:42](/Users/lurenxing/GitHub/----/tools/long_gate_collect.py:42)的generated_from_stdout_sha256无人读取；[vendor_react.py:54](/Users/lurenxing/GitHub/----/scripts/workbench/vendor_react.py:54)的tarball_sha256未消费且同bytes已经固定npm integrity校验。删新生成字段，保留独立nodeid、integrity与来源合同。candidate_payload_sha256在显式开发画像及旧重构人工前后比较中实际使用，非生产热路径；保留可选比较用途，历史证据不重写。 |
| 10.4 | 应取消强制终态整库SHA，优先修 | [system/files.py:97](/Users/lurenxing/GitHub/----/core/services/workbench/system/files.py:97)只供展示/诊断，位于已完成操作之后、confirm_host和终态journal之前。读取失败会阻断真实结果落盘。主代理故障探针验证终态record 0次。兼容返回null/历史值，目标/保护备份的实际一致性摘要保留。 |
| 10.5 | 真重复，低收益可排后 | [field_parse.py:82](/Users/lurenxing/GitHub/----/core/shared/field_parse.py:82)坏值先严格失败再兼容重解析，计数为原值2次再fallback1次；可复用失败判断，保留policy/原因码/默认值合法性。旧 [part_service.py:244](/Users/lurenxing/GitHub/----/core/services/process/part_service.py:244)路线格式与正式解析重复预处理，当前工作台不走该热路径；可共用结构，保持错误合同，不加跨请求cache。 |
| 10.6 | 假想列兼容可删；UDF注册收窄，P3 | 当前与12份历史schema/迁移未定义Suppliers/ExternalGroups.updated_at，也无业务消费者；[external_group_repo.py:75](/Users/lurenxing/GitHub/----/data/repositories/external_group_repo.py:75)每更新PRAGMA并吞探测异常。允许额外列不承诺维护假想列。时间UDF本身必要，[base_repo.py:35](/Users/lurenxing/GitHub/----/data/repositories/base_repo.py:35)11仓库注册11次却仅5类消费；共同机制限实际时间仓库，保持plain conn，不用全局connection-id缓存。 |
| 10.7 | 两种保护保留，暂存可合一，P3 | [sqlite_integrity.py:51](/Users/lurenxing/GitHub/----/core/infrastructure/sqlite_integrity.py:51)系统临时目录完整写/校验后删除；[migration_backup.py:63](/Users/lurenxing/GitHub/----/core/infrastructure/migration_backup.py:63)再写同payload供原子替换。在DB父目录建隔离子目录，写一次、关闭只读验证连接后替换同一stage，可同时满足WAL隔离和同文件系统。保留坏备份不动目标、sidecar处理、锁重试和失败清理。 |
| 10.8 | 三个子项都应拆开收敛，P3 | [v37.py:40](/Users/lurenxing/GitHub/----/core/infrastructure/migrations/v37.py:40)早FK是fail-fast，末尾FK在同事务覆盖全部且失败回滚，不能据中间数据变就称双检查必要。v8同值UPDATE探针计入total_changes 1，可加真实变更谓词。v4 run(logger=None)取sample后丢弃，独立helper返回和真实日志保留；跳过取样仍需保持pk_expr验证。 |

## 14组部分修复的保留段与残留

| 编号 | 最新判断 | 具体残留与必要边界 |
|---|---|---|
| 2.6 | 应继续修 | [workbench_trial_repo.py:42](/Users/lurenxing/GitHub/----/data/repositories/workbench_trial_repo.py:42)、47、80仍dump()+fingerprint()同值，现成dump_and_fingerprint未全部接入。change写后load_draft可复用已核验且触发器禁止修改的admission/original，保留最新head/current/行数；create首次权威回读仍必要。 |
| 2.7 | 应继续迁移 | [adoption_baseline_values.py:39](/Users/lurenxing/GitHub/----/core/services/workbench/plan/adoption_baseline_values.py:39)、[adoption_history_evidence.py:70](/Users/lurenxing/GitHub/----/core/services/workbench/trial/adoption_history_evidence.py:70)、77仅为相等计算双方hash。共用现成lossless canonical same，保留bool/int/float/BLOB等原语义及持久摘要。 |
| 4.2 | 条件性可收敛，当前最终重核保留 | 真实adopt preparation/guard同SQL快照重复collect执行事实，但每次投影现取datetime.now，未来事件合法性及data_gaps进入revision。同SQL快照不是同输入。先明确共同as_of或只复用raw再以最终时间投影；旧公开guard和跨写时点合同继续保留，不能直接借prepared事实跳过。 |
| 4.3 | 原schema/clock剩余说法纠正；header P3 | [ledger_reader.py:106](/Users/lurenxing/GitHub/----/core/services/execution/ledger_reader.py:106)共同snapshot已经间接修掉wrapper的schema/clock重复，没编辑wrapper不表示没生效。find_report单号header后再按ref读一次header可共用；没有生产caller，优先级低，保留独立历史查询职责。 |
| 4.5 | 前后读保留；死摘要可删，P3 | 已共用每时点raw/normalized，写后返回需新值；[system/config.py:35](/Users/lurenxing/GitHub/----/core/services/workbench/system/config.py:35) after,_仍计算丢弃的fingerprint，可让共同snapshot按消费者产出。 |
| 4.9 | 写前重复应修，P2 | [process_writes.py:87](/Users/lurenxing/GitHub/----/web/routes/workbench/process_writes.py:87)guard已加载事实，[process/mutations.py:116](/Users/lurenxing/GitHub/----/core/services/workbench/process/mutations.py:116)、121尚无写入就再次取snapshot/workflow。内部写入口消费checked facts；真实工艺改变后的签名重读保留。 |
| 4.10 | 当前工作台N+1不成立；旧parser可排后 | 工作台_OpTypeSnapshot.get是内存查找，旧parser真实8供应商list1/get8。旧路径可用同次工种index共用，保留missing/mapping/category诊断，不加跨请求cache。 |
| 4.12 | guard内重读应修，P2 | [operator_calendars.py:88](/Users/lurenxing/GitHub/----/web/routes/workbench/operator_calendars.py:88)month已包含目标日row/ref/revision/history，93又snapshot(day)。直接从已核month取得该日。公开apply独立检查、global range确认第一次读取当前DB都保留。 |
| 5.6 | ledger无变化写仍存在，P3 | [sync_debt_ledger.py:250](/Users/lurenxing/GitHub/----/scripts/sync_debt_ledger.py:250)refresh仍save；[quality_gate_ledger.py:184](/Users/lurenxing/GitHub/----/tools/quality_gate_ledger.py:184)始终写整份MD。[finalize:653](/Users/lurenxing/GitHub/----/tools/quality_gate_ledger.py:653)已有语义相等保留timestamp，却未免写。主代理mock writer确认同ledger两次save产生完全相同文本的两次写调用；相同内容可短路。vendor/build此前已处理。 |
| 6.3 | 当前DB重预检保留，已检查行再读应修 | 物料confirm先重建proposal，再公开apply查同identity/raw；资源同族。复用已检查row.expected的内部写入口，公开apply自核。关联导入同人多行可能改变主操，不能机械缓存整批写前关系。与4.7同根因合并实施。 |
| 6.5 | 剩余源文件确认SHA/解码应复用 | [execution_files.py:76](/Users/lurenxing/GitHub/----/web/routes/workbench/execution_files.py:76)、81又摘要/解码同一服务器留存不可变bytes。沿已有content槽保留首次parsed source/digest，BG-X算法与首次文件身份保持；确认仍重建当前cohort/items/snapshot，不新增缓存体系。 |
| 8.8 | 单ref分支应继续收敛 | [git_hook_checks.py:289](/Users/lurenxing/GitHub/----/tools/git_hook_checks.py:289)仅多ref消费已算scope，单ref传同SHA子进程重算；内存计数diff两次。沿已有supplied-path协议，仍刷新本地dirty范围，独立CLI能力保留。 |
| 9.5 | portable launcher第二写入者应迁完 | [portable_release.py:52](/Users/lurenxing/GitHub/----/scripts/portable_release.py:52)仍assets→dist读/比/必要覆写，而onedir已投放。prepare消费共同build产物并核必需入口，不在后续阶段另写launcher；烟测后清理新runtime材料保留。 |
| 10.9 | 判空可删，兼容解包合并 | [machine_service.py:165](/Users/lurenxing/GitHub/----/core/services/equipment/machine_service.py:165)在validator非partial已保证后再判None，未找实际override；不可达。backup_task/cleanup_task的_unpack_due_info相同，tuple2/4兼容有真实消费者，集中共同辅助保持行为。 |

## 仍有明确用途的已修项保留段

- 2.1 历史档案字节/摘要；2.2 独立prepared跨时间重核；2.5一次档案完整性与当前事实检查；3.1业务准入维护审计。
- 4.5 写后新值；4.9业务改变后新签名；4.12公开入口和range当前事实；6.3确认当前DB；6.4stamp变化重算以及提交refs/actor/时间；6.6共同后端拒绝gate。
- 7.4/7.5 UI跨响应归属与未知adapter边界，默认API当前已完整校验一次；8.7真实receipt文件/日志/输出身份；9.1首次外部材料验证；9.4交付字段及实际ZIP/7za来源比较。
- 9.2固定构建环境/来源/import；9.3解压前完整包检查与实际解压；10.3显式画像的人工比较；10.7sidecar隔离、坏源保护、原子替换、锁重试。

## 3项门禁失败

“HEAD已有”只说明来源。本次源文件确实逐字等于HEAD，但三项都值得按职责处理。

| 项目 | 判断及最小方向 |
|---|---|
| 私有跨模块导入 | [runtime_server.py:13](/Users/lurenxing/GitHub/----/web/bootstrap/runtime_server.py:13)共享_candidate_ports已经服务两个模块，直接公开命名candidate_ports并迁移实际caller/测试，无wrapper或白名单。 |
| 监听handler登记 | [entrypoint.py:300](/Users/lurenxing/GitHub/----/web/bootstrap/entrypoint.py:300)有错误日志、退出16和finally清理。保留失败边界，补第二个observable_degrade的有据登记，不接受吞错豁免。 |
| 函数复杂度17 | [entrypoint.py:321](/Users/lurenxing/GitHub/----/web/bootstrap/entrypoint.py:321)服务分流可提为有实际职责的_serve_selected_endpoint；内存AST/radon探针主函数17→15、helper3，生命周期/监听/finally仍由主函数负责。 |

## 邻近真实缺陷

**v4 TRIM清洗漏掉纯首尾空格。** [v4_sanitizers.py:85](/Users/lurenxing/GitHub/----/core/infrastructure/migrations/v4_sanitizers.py:85)比较LOWER(TRIM(x))与TRIM(x)，输入小写 `' yes '`不满足更新谓词，实际内存存储不变、changed=0。与明确TRIM+LOWER目标冲突。这是具体清洗bug，应修谓词及一致取样；对已升级数据库若要清理同类存量值，走明确前向迁移，不能假设重跑v4。

## 本轮证据边界

- 七个独立分区重判，主代理复核关键源码、实际caller、两个存量启动源文件与HEAD相等，及恢复终态/ledger无变化写两个故障/计数探针；低收益不等于虚构问题。
- 仅纯内存SQLite、Node VM、AST/radon、writer stub及读取计数，无真实排产、业务库恢复、安装或完整门禁重跑。
- SQL execute/SELECT计数、total_changes、bytes流向均不代表实际磁盘耗时；Mac页面约11ms只属于该机该次读取。
- 4.2已因时间输入反证收窄判断；5.3已补核计划输出/计算全部相关事实，确认父同值写可省，不只以批次写token论证。
- 不生成新摘要/证明清单，不重新生成历史验收指纹；本轮实现尚未开始。

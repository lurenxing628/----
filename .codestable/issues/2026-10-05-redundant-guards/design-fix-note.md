---
doc_type: issue-fix-note
issue: 2026-10-05-redundant-guards
created: 2026-10-06
status: fixed
review: completed
verification: targeted-review-and-daily-stage-complement-passed
---

# 冗余设计修复、实施中复判与 review

本记录对应用户“该修就修，修的过程中确认是否真的需要”，落实 [设计探索 D01–D29、B01–B03、S01–S15](../../audits/2026-10-05-redundant-guards/design-exploration.md)。此前两轮修复及其失败、补验保持原记录，本次不改写历史裁决。

实施判断是：同一事实和规则应由共同职责提供；不同时间、独立入口、可变输入、历史协议和恢复屏障仍然需要核验。已删除无消费者的正文、摘要、令牌、辅助状态和空组件，收敛共同配置、文件读取、资源解释、算法准备及前端状态发布。下面逐项说明实际落地与保留边界，不把混合项整体记为删除。

## 授权与工作区

- 本轮开始已有 386 个 dirty path、0 staged，不覆盖此前修复。当前全部 dirty path 不是本轮修改数量。
- 修改前保存 [可恢复源码与文档快照](/Users/lurenxing/GitHub/----/evidence/2026-10-05-redundant-guards/design-fix-start-20261005-235120.tar.gz)，对应路径记录为同名 JSON；394 个路径，包含既有改动和审计资料，没有生成额外指纹。
- S12 空组件批量清理前的源码快照保存在 `evidence/2026-10-05-redundant-guards/design-s12-before/`。
- 产品定位先使用 `tools.symbol_locator`，再核对真实调用、数据与消费者。子代理分模块实施及独立 review，根代理负责去重、共同入口和统一验证。
- 没有提交、推送、发布或操作实际业务数据库；数据库验证使用独立临时库，浏览器使用隔离实例。产品保持 Windows 7 x64、Python 3.8、离线单机目标。

## D01–D29 的实施裁决

| 编号 | 实际修改 | 实施中确认需要保留的职责 |
|---|---|---|
| D01 | 新试调 admission 不复制候选 artifact。 | identity、dispositions、capture input/facts/execution 有消费者；历史记录不重写。 |
| D02 | 新候选采用 `candidate_tasks_v1`：永久任务行为安排正文权威，artifact 只保留 engine 独有追踪、验证结论和作用域。 | 写前核 engine 与 validated 安排相等；永久 row/task 身份、FK、ordinal、计数、锁定、零时长原始见证及采用重验证保留。旧格式仍执行原副本一致性核验。 |
| D03 | 新试调采用 `permanent_rows_v1`：snapshot 保存元数据与有序永久行引用，任务正文由 ScenarioRows 提供。正文副本从三份降到两份。 | 完整命令回执提供精确 replay 和独立来源核验，继续保存；不会在历史查询时重建当时可变令牌。Schema 和旧记录字节不变。 |
| D04 | 中立层维护唯一字段规格、Snapshot、读取/转换/权重规则；服务只加页面 metadata、标签和 legacy omission 政策。run/input 只读取一次基础配置，分别派生 override 与默认 hold window。 | Snapshot 可变，decode 仍重新规范化；没有用 isinstance 跳过校验或建立跨请求缓存。服务的独立公开入口仍可自行读取配置。 |
| D05 | 资源列表新鲜度只绑定当前种类、实际展示/写入依赖与相关永久引用；取消无关全域计数和资料身份。 | 全站汇总拥有自己的 scope；人员私有写状态仍含授权设备、班次等实际依赖。此前创建 scope 修复保持。 |
| D06 | 模板展示、同步与工艺确认共用来源合法性，包括类别、能力和组关系。 | legacy 免人工确认和空模板自动解析是独立政策，保留；错误来源类别不因 legacy 而放行。 |
| D07 | Plan/Field/Actual 共用 lossless int64 契约，实际关键链比较统一 wire 值。超 JS 安全整数的合法数量正确展示。 | 报工输入、剩余量和执行目标仍受自身 safe-number 业务合同约束；不扩大写入范围。真实 SQLite→HTTP→JS 三个整数边界已核验。 |
| D08 | 资源单条/批量投影、资格解释和状态词汇在共同职责提供，展示与 SQL 使用同一语义。 | 捕获时点不同的单条和批量读取保留；旧 reason-reset trigger 与显式 reason 写入服务不同写入者，保留。 |
| D09 | 物料工序绑定与到料流水读取/修改分开，复制仅读所需绑定，数量拆分保留原绑定。 | 守卫仍取得当前相关事实；真实到料修改、审核、齐套及数量约束继续执行。 |
| D10 | 五类 CSV/XLSX 物理读取复用 `facts/file_source.py`，统一文件生命周期和 Excel 单元格翻译。 | 领域表头、行数/字节限制、错误文案、ZIP/XML 检查保留；日历仍拒绝非午夜日期，不擅自修改日期政策。整工作簿/选定 sheet 的不同读取合同保留。 |
| D11 | 试调容量与报告利用率共用计算内核。 | 试调用 precision=None，保持原精度、segments 与 span_overlap；报告舍入政策独立。 |
| D12 | 工作台直接读取真实执行台账，去掉空旧执行投影、字段覆盖和 ReportReadEngine 可变旁路；旧 ReportEngine 按需创建诊断/反馈服务。 | 旧报告有效计算和公开 API 保留；原计划字段和新执行字段各由真实事实提供。 |
| D13 | 已冻结外协事实直接构造执行上下文，使用共同 group_key。 | 旧 lookup adapter 的参数、形状和错误语义保留；不将任意注入对象认作已冻结事实。 |
| D14 | profile 准入特征与排名分开；repair/IG 直接生成最终优先级，省去随后整体替换的排名。 | profile 的特征 admission 和实际候选范围校验仍执行。 |
| D15 | 经 package-owned native witness 认证的只读算法输入只复制有 override 的工序。 | 公共入口、未知函数/方法/对象类型仍完整隔离复制，不改变调用者输入。native 认证通过公开职责函数提供，不跨层取私有见证。 |
| D16 | 同一 evaluator 复用不可变 PreparedGraphReadyTopology；v2 共同基础事实一次准备。 | 类型、内容、作用域必须匹配；每次 decode 的进度和优先级独立；未知 producer/raw 图仍检查坏 ID、边、排序与环。 |
| D17 | 退役 dispatch 服务从启动 eager anchor 移到 Win7 构建两条 hidden-import 分支。 | 公开 Python API、冻结包兼容、旧历史/范围/关键链读取继续保留。没有声称删除全部服务或缩小包体。 |
| D18 | 普通/status/static/config 准入使用当前 owner 状态，不扫描全部历史；启动、文件接纳、历史查询和真正到期维护才新读 journal。 | 未知 journal、未完成维护、ACK、忙锁处理和恢复接纳保持；到期自动维护在同一 maintenance window 新读历史，disabled/not-due/throttle 不扫描。 |
| D19 | 正常维护结果按原 request_key 精确查询 /results。 | 手动 job 查询 /jobs 及历史查看保留，不混用两种身份。 |
| D20 | 普通备份创建/删除不计算无比较消费者的整文件 SHA。 | 恢复 target/protection 比较、阶段记录和历史 nullable 字段兼容保留。 |
| D21 | 单次系统结果不再签发无人回传的 query token。 | 集合、分页、generation、写入和命令回执的真实归属绑定保留。 |
| D22 | 准确任务定位只请求实际定位结果，删除第一轮无消费页；共同 Python/JS Unicode trim 语义。 | 后续独立分页仍取得自己的首个快照，任务/计划归属继续核对。 |
| D23 | 数字控件注册、数值更新和位置更新分开；滚动只更新实际受影响的已注册控件。 | 控件注册/卸载及输入变更仍完整处理；不通过缓存旧数值省工作。 |
| D24 | context/history/scroll 共用一个 200 ms 发布 owner；导航/pagehide 刷新最新状态。 | 恢复途中只存 context、不覆盖原 scroll；Back/Forward 按确切 entry 读取，分支导航清理旧 Forward 快照。 |
| D25 | 实际甘特缩小布局依赖，指标 memo 且单次遍历；标签和任务索引由同一响应准备。 | 真实筛选、布局和执行事实变化仍重算，没有跨响应旧索引。 |
| D26 | Trial ownerMap、Batch selectedSet、Plan calendarMap、Process groupIndex 由共同响应一次建立，UI 复用。 | 归属和值合同继续检查；不缓存跨请求身份。 |
| D27 | runner、receipt、manifest 和 fingerprint 共用 command normalization。 | 缺省/无效 output_policy 采用 exact 精确输出比对；显式命令规范化和 schema2 历史 receipt/cache 合同保留。 |
| D28 | 两个 Inno 入口包含同一 `aps_win7_shared.iss`，取消逐例程手工同步，SYNC_CHECKLIST 改为共同主体说明。 | AppId、路径、迁移、清理及 payload 保持；legacy browser-stop 的渠道差异仍由明确 flag 控制。 |
| D29 | 四主题 proof 共用执行事实构建与写入。 | 主题字段、路径、schema 和实际日志/输出/缓存绑定各自保留；不是合成新的自摘要。 |

## 相邻 bug 和小项

| 编号 | 当前结果 |
|---|---|
| B01 | 诊断页面和导出发布已确认事实，不再经旧重复投影丢失事实说明。 |
| B02 | 工作台运行在 managed runtime、owner ready 条件下驱动真正到期自动维护；进入业务事务前执行，只读配置不写默认值。实施 review 后补齐到期维护的新鲜 journal 阻断，不确定历史不创建备份、不写 DB audit。 |
| B03 | 通用 multipart README 去掉固定历史版本、日期与验收背书，默认通用名可自定义；历史验收材料保持历史归属。 |
| S01 | **保留** lineage 出生两份状态。现有固定证据版本、NOT NULL snapshot、完整性核验和校准比较都有消费者；删除须新增迁移、sentinel 与历史分支，P3 收益不足以承担该复杂度。 |
| S02 | 校准新 evidence 只在 snapshot 中保存 suggestion；样本、前后状态和锁定审计保留，旧读取者不需要新增格式分支。 |
| S03 | 删除无人生产消费的 samples_by_part；两内部测试迁移到真实 unbound 消费入口。 |
| S04 | 试调加载同时返回 header/snapshot，采用复用同一不可变场景 header；永久行和历史回执核对保留。 |
| S05 | **保留** Dashboard States。它是有索引的当前状态与完整性支点；正常写路径未找到漂移，删除需要实际查询收益和完整性替代证据。 |
| S06 | preview/download 共用小型值对象及算法；领域 frozen 子类、isinstance、action namespace 和错误文案保留，没有新增泛型框架。 |
| S07 | 两个 v2 basis 共用 opmap、duration、family、rank、seed；不同 offset、due、window 基准保留。 |
| S08 | 组合统计使用一次 owned capture；公开 snapshot 继续返回独立深副本。 |
| S09 | 每个恢复 outcome 直接携实际结果，删除 manager 可变结果旁路及回填选择；target/protection 与失败阶段保留。 |
| S10 | 五类普通前端读取及系统读取复用现有 useQuery；保留 RunBaseline 同步取消、重试/超时和领域 exchange/unknown-commit 差异。共享 hook review 后修复卸载时排队 Promise 未结束的真问题。 |
| S11 | Blob 保存共用现有 transport.saveBlob；领域 MIME、内容、身份、范围和行数检查保留。 |
| S12 | 删除 6 个独立空组件文件、15 个空 Styles 定义及一个空 delegate，同时迁移 mount/export/fixture/build-order。真实 WorkbenchControlStyles 的主题变量、监听和卸载恢复保留。 |
| S13 | API 内一次 envelope/最终响应验证，UI 不重扫已验证 workspace；注入 API 合同、run_ref 和领域归属仍核对。 |
| S14 | 同页 pending 事件发布已 readback 的值；跨 tab 新读、写前 compare/readback 和失败处理保留。 |
| S15 | 删除无人调用 raw ZIP、无消费 op_logger 和重复 workflow DTO 检查，共用 operation_code；脱敏日志窗口、坏 DB/计数/读失败诊断及公开兼容入口继续保留。 |

## review 真问题与反证

- **旧档案摘要输入回归已修**：旧 codec 核验解析后的 packed JSON；不得 unpack 后再重编码。现在一次解析保留 packed/unpacked 视图，旧格式核原 packed，新 compact 格式核重建快照。有限 hex、INF、NaN、等价 base64 四种回归使用 stub 摘要输入比较，未新建哈希。早先“旧原始字节空白不同”的 review 判断已撤回。
- **外部 rank cache 的原料覆盖兼容已修**：旧 scoring 把 cache 覆盖到自身 metric 副本后校验；显式决策准入最初只转换 float，可能漏检负值覆盖。现在共用 cache 装配并仅写 owned 副本，继续不生成弃用 rank/jitter，四项实际缺陷回归锁定该边界。
- **history 分支和恢复发布回归已修**：试调采用历史统一走主 navigate，避免 Back 后看 B 却复用 A 快照；pagehide 在滚动恢复中保存最新 context 且保留旧 scroll。
- **共享 query 卸载悬空等待已修**：卸载清空未启动队列并以 AbortError 结束所有等待；3 类等待实测全部结束，未启动 loader 调用 0 次。
- **模板正向夹具本身非法**：既有 OT1 只支持 internal，而测试模板标 external。正向同步夹具显式设 both，来源阻断测试仍执行；没有放宽工种类别或 ledger freshness。
- **报工正向夹具本身非法**：原 point/浏览器种子使后道早于已完成前道，真实 upstream_time_conflict 已存在于 HEAD。调整种子时序、保留前后道 guard；浏览器种子核得 66 任务/132 计划小时、27 报工/6 legacy events、7.5 已知小时/1 未知小时，FK 无问题。
- **跨模块浏览器探针过期假定**：重进页面会恢复只读详情，当前月份已变。探针使用正常关闭和真实月份按钮；没有清存储、强点 disabled 或绕过 pending。
- **自动维护状态误失效已修**：真实自动备份写 SystemJobState 及其 allocator，原排产事实守卫将其误认为输入变化，worker 保存候选报 snapshot_stale。核对维护状态的全部生产/消费链后，在共同 NON_INPUT_TABLES/non_input_row 中沿 OperationLogs 的口径排除内容和自增序列；Schema 及真实业务输入仍参与检查。恢复用例继续证明响应/worker 停止后才做保护副本，并证明自动备份发生过、候选正确保存。 没有整体排除 SystemConfig：它还保存 `plugin.<id>.enabled`，启动插件具有实际消费，不能把整表当作纯维护状态。
- **自动维护异常不再继续服务**：factory 只对已知维护准入/忙锁拒绝返回 503 并关闭连接；未知 driver 异常沿现有外层清理传播到 500。owner 将未知 journal 读取错误转为带 cause 的明确阻断；日志在接纳边界记录，未吞错。旧 factory 真正“未知异常后继续”的治理登记已按官方 API 精确退役，未刷新全部条目；重复 handler 的扫描 ordinal 随删除发生位移，只同步同一现存记录的身份元数据，总数 76→75，没有新增豁免。
- **日常旧结构断言迁移**：候选日期测试读永久任务行；容量测试显式传原两小时窗口；XLSX 测试核真实共同 reader 并经公开日历接口验证 90%→90；scanner 用实际 import 表达式位置，避免把历史行号当协议。私有跨层调用改为真实公开职责，未扩白名单或刷新基线。

## 实际验证

模块测试批次有交集，不相加冒充独立总量。配置 197 passed；候选相关 129/37/50 passed；试调相关 156、35 passed；业务来源/物料/容量 658 passed；共同 reader 536 passed；资源 231/479/138/18 passed；报告 100/9/116/70 passed；系统最终 134 passed；门禁工具 566 passed（两 registry fixture 后定点通过）；校准 71 passed；installer 6 passed。具体失败、修正和补验以保存日志与下面统一范围为准。

- 独立配置差分：8,964 组 coercer、1,208 组 Snapshot、54 组 weight，零差异；两种 v2 basis 490 组正常/NaN 输入对照无差异。
- 根代理 archive/file/batch 回归 101 passed，覆盖 packed-tag 历史兼容；native/hold/point 63 passed。既有 formal checks 的有效结果按相同代码状态复用。
- 前端计数探针：60 次 context 更新为 0 次即时/1 次尾部 history 写；100 控件的无关滚动为 0 次扫描/0 次值刷新；1,000 任务指标为 1,000 次状态读取。这是行为计数，不是目标机耗时。
- 合成 3,000 节点×5 decode：raw 68.22 ms、复用 29.88 ms。仅说明相同事实少做工作，不当作真实排产加速倍率。
- Chrome109 目标构建完成，270 个发布文件；static 与实际 build-order 同步。初始 opt-in 3 passed/2 failed，失败探针/种子修复后 reports_review 1 passed、cross_module_maintenance 1 passed；原 modal_focus 和 az_contrast 有效通过项复用。日志保存在 design-browser*，浏览器运行保持隔离。
- 正式 Pyright：产品 `pyrightconfig.gate.json --pythonplatform Windows` 最终 1,208 文件 0 errors/0 warnings；宿主 `pyrightconfig.tools.json` 61 文件 0 errors/0 warnings。首次误用默认 config 纳入未类型化测试的探索输出单独保存，不当作正式门禁；相关产品诊断已修。
- 日常第一次 collection 因已删除 helper 的测试 import 失败，已迁移到实际 SQLite 损坏边界（30 passed）。第二次 collection 17,290 项成功，parallel 11,879 passed/29 failed/1 skipped（608.10 秒）；29 项逐条处理，原退出 1 和失败日志保留。
- parallel 原 29 个失败节点已逐项修复，统一补验 30 passed/12.95 秒（额外包含第三个引用解析变体）；私有职责/引用/导航/native 补验 90 passed，实际关键链 API 23 passed。候选单行职责拆分后完整采用相关 105 passed。
- serial 补齐第一次为 982 passed/3 failed（214.24 秒），失败对应新增回退分类、报告文件长度及四函数复杂度；已按真实职责拆分和明确失败传播，没有修改门禁阈值或增加豁免。已将共同计划标签提到公开 plan_labels 叶子，执行复盘保留实际/身份/导出职责（512→465 行）；source_issues 17→5、bulk.apply 16→4、候选 _rows 18→6（单行验证 13）、显式决策准入 21→5，均保留原检查顺序。报告 94+5、来源/批量 119 及 2,048 组有序诊断差分、候选采用 105 的定点验证通过。显式决策 118 passed、IG 35 passed、cache 5 passed，各批有交集；1,147 个准入/scoring 错误契约差分一致，10 次失败钩子确认不生成弃用 rank/jitter。
- serial 三类失败修正后，完整 architecture/boundary/CodeStable 三文件 37 passed/12.57 秒；system/factory/owner 38 passed/18.64 秒，真实忙锁、unknown driver、请求连接关闭与 optional path 一次读取均覆盖。根代理复核台账 76→75，仅退役一条；同一清理记录只改 id/except_ordinal/line_start/line_end，其余治理字段与所有其它 section 完全相等。
- focused 第一次 5 passed/2 failed（4.42 秒）：失效路径对应已删空组件的影响面清单，已删除无人消费条目并保留现行 source/build/manifest 覆盖；文档一致性 reader 改为比较共同注册表、实际服务常量与文档四字段，差异仍阻断为 MAJOR；三种来源漂移反例和相关回归 10 passed。失效路径/manifest 两文件 159 passed/23.98 秒。
- 最终 focused 7 passed/4.51 秒；正式产品 Pyright（Windows）1,208 文件和宿主 tools Pyright 61 文件均为 0 errors/0 warnings。全仓 Ruff、diff-check 通过；diff-check 仅提示已有 BAT 行尾按 Git 规则将转 CRLF，没有差异错误。
- 统一 daily 原命令的失败记录保留，交付口径是有效通过项复用、失败定点复验及 serial/focused 剩余阶段补齐，未再跑整条 daily，也未把其原退出码改写为 0。没有执行 full-test-debt 或最终 clean gate。

统一证据：[parallel 原日志](/Users/lurenxing/GitHub/----/evidence/2026-10-05-redundant-guards/design-daily-gate-recheck.log)、[29 失败补验](/Users/lurenxing/GitHub/----/evidence/2026-10-05-redundant-guards/design-daily-failed-recheck.log)、[serial 原日志](/Users/lurenxing/GitHub/----/evidence/2026-10-05-redundant-guards/design-daily-stage-complement.log)、[架构最终补验](/Users/lurenxing/GitHub/----/evidence/2026-10-05-redundant-guards/design-daily-architecture-focused-recheck.log)、[focused 最终](/Users/lurenxing/GitHub/----/evidence/2026-10-05-redundant-guards/design-daily-focused-final.log)、[产品类型检查](/Users/lurenxing/GitHub/----/evidence/2026-10-05-redundant-guards/design-pyright-gate-final.json)、[宿主类型检查](/Users/lurenxing/GitHub/----/evidence/2026-10-05-redundant-guards/design-pyright-tools-final.json)。

## 提交前 review（2026-10-06）

用户授权 review 全部修改、分批提交并推送远端。分模块独立核对基础设施/仓储、算法/配置、工作台业务与路由、前端/发布产物、维护恢复/launcher、门禁工具/离线交付，主代理去重复核证据及文档口径。修前 inventory 为725个修改/新建/删除路径，暂存区为空；远端 main 与基线 b64c1a10 一致。

确认并修复四处问题：

- 自动维护的 `SystemJobState` 漏入试调生产事实，导致已保存方案误报 `trial_facts_changed`。沿现有 `BOOKKEEPING_TABLES` 和新旧档案比较机制排除维护记账，不改历史字节/摘要；设备等真实变化仍阻断。新旧档案、备份/清理记账与真实漂移的回归连同现有试调三文件共50 passed。
- 批次物料从同快照复用到料时，对全库到料排序；其他批次合法SQLite BLOB日期会错误阻断本批操作。限定本批需求后按SQLite的TEXT/BLOB顺序排序，保留目标批坏来源诊断与显式移除。批次物料、分期到料与拆批四文件31 passed。
- 注入的 `ActualGanttAPI.related` 原合同返回裸chain，新adapter误将其当envelope。原生和注入reader共用 `relatedChain`，原生继续验证envelope，均保持裸chain返回；计划、范围、目标、snapshot和内部链检查保留。真实SQLite→HTTP→JS合法及坏链验证24 passed；重新构建Chrome109发布资源270条。
- 门禁预计算scope将每个修改路径放进argv，本轮Windows命令长50,397字符，超过CreateProcess限制。改为自动清理的UTF-8范围文件传递，子进程仍合并fresh dirty paths，unknown scope仍执行全组，不重新计算相同ref diff。同链路原本的pytest全靶命令也超过限制（旧HEAD 33,581字符，本轮34,370字符），现仅在Windows超长pytest执行时使用原生 `@argsfile`，短命令、计划、marker和返回码保持原路。当前pytest8.3.5现场支持；开发依赖声明最低8.2，对应[官方原生参数文件支持版本](https://docs.pytest.org/en/stable/how-to/usage.html#read-arguments-from-file)。真实子进程验证范围文件/fresh dirty合并、33k参数、含空格路径、parallel/serial及deselect，门禁相关67项通过；tools Pyright61文件0 errors/0 warnings。

另修正性能报告口径：0.89秒是factory启动加业务流程的整体缩短，业务链本身缩短0.78秒；原始测量数据与阶段耗时不变。

本轮独立storage定点76 passed，与上述试调验证有交集，不将它们相加为独立覆盖。产品正式Pyright（Windows）0 errors/0 warnings，全仓Ruff和diff-check通过。完整full-test-debt/final clean gate及实际Inno/Win7原机验收未执行。

## 交付范围

现行 workbench-shell、service-scheduler 架构和系统速查表已同步共同配置、正文权威、owner/自动维护、前端发布和旧 API 兼容边界；探索报告仍保存修前证据，并链接本实施记录。

没有实际 Inno 编译及 Windows 7 原机安装、升级、卸载证据，不能据静态 include 核对声称这些通过。没有运行 full-test-debt/final clean gate；当前 dirty 工作区不构成 clean-worktree proof。未发现的业务规模或性能事实不推算成真实收益。

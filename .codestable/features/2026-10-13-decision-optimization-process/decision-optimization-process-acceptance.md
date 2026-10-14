---
doc_type: feature-acceptance
feature: decision-optimization-process
status: passed
created: 2026-10-13
roadmap: scheduling-decision-workbench
roadmap_item: decision-optimization-process
requirement: candidate-comparison-business-view
implementation_acceptance: passed
parent_acceptance: passed
operator_ui_repair: passed
---

# 第6阶段优化过程实施验收

## 2026-10-14 当前验收与入口

**第6阶段已完成：步骤均为done，实施验收、母验收及操作者界面返修均为passed。** 主对话已亲自验收最终正常实例；第7阶段也为passed。按用户决定先推进A/B，第8的A产品按已通过的功能、数据和非Windows验证范围冻结收口，2秒概览目标移交C正式待办；范围和owner见[第8设计](../2026-10-14-decision-integration-acceptance/decision-integration-acceptance-design.md#5-2026-10-14-已批准的操作者界面返修)。

当前实例为 `http://127.0.0.1:58240`／PID3143，Python3.8.10、Schema40，同原数据库 `/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`；组合资产为 `main.js=1791956005`／`workbench.css=1791956823`。现行入口使用[第8阶段的9个当前链接](../../../evidence/prototype-integration/2026-10-14/current-links.json)，实例身份见[当前运行记录](../../../evidence/decision-integration-acceptance/2026-10-14/runtime.json)。主对话实际读取8候选卡、4候选受理正式v1基准及12批／48工序、15条历史记录与真实缺口、当前帮助正文，并核对health与运行合同的PID／owner／数据库／instance_id一致；console警告和错误为空，业务写入、计算、采用及导出均为0，见[最终正常实例母验收](../../../evidence/decision-stage-acceptance/stage-08/final-cold-runtime/parent-review.json)。

Gate09前16步通过，全量实际758收集／722 passed／36 skipped／0 failed；第17步因15条Windows启动器setup:skipped未核销而实际failed，[原始核销失败](../../../evidence/decision-integration-acceptance/2026-10-14/full-gate/attempt09-v4/logs/17_python-tools-verify_required_regressions_from_fu.stderr.log)及此前失败原件保留。用户已明确全部Windows验证延期到大改完成后统一执行，包含这15条用例与Win7实机；门禁登记和失败状态沿原记录保持。

4／6／8候选summary真实HTTP为3.6246／4.6823／5.2835秒，2秒目标尚未达到；该目标及上述真实范围移交C正式待办。A按已通过的功能、数据和非Windows验证范围收口，全部Windows验证按用户决定延期到大改完成后统一执行。最终HEAD与clean-worktree证明随A/B交接收口，当前阶段通过结果按上述实际范围记录。

## 历史验收与交接事实

以下保留早期返修、失败、旧cold和旧证据原文；各段中的“当前”“本轮”“最终”均指对应历史验收时点。现行状态、实例和入口以上方记录为准。

## 历史事实：2026-10-14 母验收六项增量返修

实施验收 **passed**，母验收 **passed**。P2-06-10—14及P3-06-15均已完成；末次复验发现的热图未知提示密度与旧已知全集兼容也已关闭。当前产品源码、组合产物与实例冻结，第7已恢复先前派发，按主方案7.2连续实施，第8沿原顺序推进，母验收文件及Git由主对话维护。

- **最终实例。** `http://127.0.0.1:53871`／PID44499／session96013，Python3.8.10，同原`decision.sqlite`；实际HTTP与磁盘的`main.js=1791922970`／`workbench.css=1791920118`一致。该整页接入累计4次正常cold，最后一次载入公共过程兼容及帮助；原owner正常202退出、exit0，恢复无pending／recovered，cold新增运行／样例／采用0。
- **资源提示及键盘。** 同一`cellPresentation`按当前显示侧提供数值、颜色、明确警报和title／ARIA；主格突出true，null依据保留原值及详情／提示。母精确454f graph3／原算法、阈值90%的加工中心10/14为85.2%／6.815小时，before高负荷false／after true，主格无错侧标记与重复待确认，格高68（此前84.89）。Enter开详情、键盘关闭后回到原资源与小时bucket；原格消失时回同资源入口。
- **过程集合及无改善。** collector保存真实`evaluation_scope.incomplete_batch_ids`，成员变化独立于phase／visit／segment。共同投影沿旧`all_batches`且未排齐批次数0的实际事实规范化`[]`；部分覆盖缺身份仍null。真实同集合跨阶段连续，B1→B2同基数断线；旧存档未回写。最终53871亲看7736原算法4/4实线、graph3的6/7采样虚线及ac9真实30／251ms两点平线，均一个line group；无改善入口禁用、全过程与Home／End真实首末保持。
- **资源汇总及原件。** 已知保留跨度沿同一精确区间索引求交后转换小时，6分钟＋42分钟／第三天班表缺失的原最小输入得到已知占用0.8、已知班表外跨度0，整体未知保持null。共同出口的整窗日峰只一组，时段占用与日峰分别输出；真实跨夜受控场景43.75%／50%由既有用例锁定。宿主独立oracle同步当前v4字段、真实filters、20／50分页集合、指标版本及9列附表。
- **必要验证。** 日常136目标、498 passed／20 skipped／83.70s、全Ruff通过，覆盖六项首次修正与宿主oracle。随后仅旧全集兼容与主格密度变化：既有兼容节点1 passed／1.00s及两文件Ruff、最后comparison CJS0.7740s／资源CJS0.2647s、Chrome109 built10、最终离线资产3 passed／0.78s、一次正常cold和上述四项实际回验补充。浏览器6组全部passed；小时原件24检查、同格焦点和此前未变的23项页面结果复用。修正全部扩展既有测试函数，返修新增文件／函数0；整页接入先前新增3个Python函数继续承担粒度、班内冲突及显示窗导出。
- **原生文件与保全。** 返修新增8份原件：既有11资源整窗／23天明细4份共128业务行，小时格CSV／XLSX2份95唯一列，ac9过程CSV／六表XLSX2份36业务行／4836格；Root亲自打开代表原件，两个真实进步事件的排除集合均为`[]`，原archive仍没有该新增字段且保存all_batches／0未排齐。小时格两比例现场同为100%，不同数值的正确映射沿既有跨夜场景证明，窗口／scope各自保留。最后cold后的九表原1249行／7869字段和类型、34配置170字段及正式v1／15行保持，clock仍158；返修运行／样例／采用／试调均0。此前84表不变及clock110→158的授权48新工序归属证明继续单列，strict85表失败原件保留。

证据：[统一摘要](../../../evidence/prototype-integration/2026-10-14/integration-summary.json)、[最终六组UI](../../../evidence/prototype-integration/2026-10-14/mother-repair-ui/verification-summary.json)、[最后正常cold](../../../evidence/prototype-integration/2026-10-14/root-mother-repair-full-scope-cold.json)、[资源原件oracle](../../../evidence/prototype-integration/2026-10-14/mother-repair-resource-oracle/export-verification.json)、[过程原件](../../../evidence/prototype-integration/2026-10-14/mother-repair-process-native/export-verification.json)、[Root资源原件](../../../evidence/prototype-integration/2026-10-14/root-mother-repair-original-inspection.json)、[Root过程原件](../../../evidence/prototype-integration/2026-10-14/root-mother-repair-process-original-inspection.json)、[当前入口](../../../evidence/prototype-integration/2026-10-14/current-links.json)。当前为累计dirty阶段验收，最终HEAD／clean proof及整体门禁按第8阶段完成。

## 此前 2026-10-14 第二版整页接入及四份不同结果

本轮实施验收 **passed**，主对话独立验收 **changes_requested／进行中**；主对话维护母验收记录及Git。第7在本阶段主验收通过后继续，第8沿依赖推进。当前产品源码与49394实例已冻结，原型正式接入、P2-06-09候选卡及窄屏返修均已完成。

- **当前实例。** `http://127.0.0.1:49394`／PID8243／session39765，Python3.8.10，同一独立数据库 `/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`。HTML与磁盘一致：`main.js=1791917435`、`workbench.css=1791920118`，Chrome109离线构建10项。该轮两次正常cold，最后一次只载入帮助文案；原owner正常202退出，恢复记录无pending/recovered，两次cold本身新增排产／样例／采用均为0。此前58440页面／原件按未变行为复用。
- **真实四方案。** 新运行 `ac9ca5c1428c9b76b12b120abc9e5d1daf1a63df8e7354db` 使用授权DQ4-样例12批／48道工序，四候选均completed、无复用，共保存192条安排；六对变化工序数48／48／48／12／24／32。一次样例导入、两次真实受理：首次缺维护机既定`networkx==3.1`失败，原失败归档保留；补齐依赖后第二次成功。34配置／170字段逐值恢复，正式采用与新试调均0。

| 实际候选 | 累计拖期（小时） | 总跨度（小时） |
| --- | ---: | ---: |
| 原算法 | 1587 | 293.5 |
| 重点工序优先方案1/3 | 2090 | 265 |
| 重点工序优先方案2/3 | 2092 | 265 |
| 重点工序优先方案3/3 | 2112 | 265 |

原算法在此样例拖期较少，三档重点工序方案跨度较短；准备24小时、加工144小时为共同真实需求。原件独立核对192条工序元数据、设备／人员资格、144对批内前后关系、班表与停机均成立。工序93的19.5小时安排跨度由3.5小时作业和16小时夜休构成，详情继续表达原跨度及工作窗。

- **整页行为。** 当前查看、固定对照、保存推荐各自保持；交期与未排按当前风险优先，差异页按真实工序变化，单一全宽详情保留选中批次。DC-02批末相同而首道开工变化可见；DP-STAGE的08:00／13:15变化以原算法对graph1核对，graph1对graph2无该工序变化。准备／切换、52指标、采用预检和原明细入口保留。
- **资源与过程。** 小时、真实班段、天、周共用归档日历；周按占用合计／容量合计并保留日峰及高负荷时段，小时筛选和精确格子导出使用实际窗口。班内冲突与自然保留跨度、已知休息与缺项各自表达，资源版本`decision-resource-v4`逐指标保存。过程独立页签用真实累计耗时，同事件流切指标、阶梯实线／采样缺口和保存点吸附；完整尝试与图读取全体，20／50分页只裁剪记录表。旧7736的4/4及6/7继续验证完整／采样。
- **卡片及窄屏。** 名称、身份、指标和操作分区，公共按钮host参与伸展，四卡指标y340.5、footer y443.171875一致；已知小计突出、全未知和真实0分别显示，待确认集中提示，完整依据保留。1392／1920、6／8及原生125／150%通过。360初次384px溢出由页签宽度造成，最后仅媒体CSS修正为横排按钮自然换行及110px摘要列，复验360／360、8入口完整、三摘要两行。桌面和原生缩放按未受影响范围复用。
- **真实操作与原件。** 增量23条记录通过，当前候选、固定候选基准及只读正式基准三次甘特返回上下文逐字段相同；实际Job→15条排产记录→重开四候选通过。UI实际下载6份CSV／XLSX，Root打开原件和代表截图直接核对；小时格原件另23项检查通过，精确08:00—09:00、双方占用1小时／100%、零差值保持数值类型，实际工作片段`not_recorded`原样保留。
- **必要验证。** 日常136目标、498 passed／20 skipped／87.26s、Ruff通过；此结果覆盖最后卡片语义和公共host，后续纯窄屏CSS及帮助文案由最后Chrome109构建、3项离线资产（0.71s）、实际360检查、Python3.8 AST／fresh payload import／Ruff及两个真实帮助HTTP页面补充。新增测试文件0、Python测试函数3，分别锁定四粒度工作窗／周权重、权威班内冲突、小时显示窗和同窗导出；原495到498由这3项独立行为增加，纯排版新增函数0。既有事务、采样和未变数值原件继续复用。
- **数据保全。** 九表原1249行／7869字段在最后cold后仍逐值及类型一致；34参数和正式v1／15行保持。最后帮助cold前的完整库检查中，84表原1911行／13976字段不变，唯一原字段变化为身份计数110→158，与授权插入48条新工序的原触发器一致。strict85表“全相同”失败原件保留，业务保全与预期元数据增量单独记录；当前Jobs15、Receipts15、Candidates54、Tasks1177，新记录明确归属本轮。

证据：[本轮统一摘要](../../../evidence/prototype-integration/2026-10-14/integration-summary.json)、[真实四份安排与六对比较](../../../evidence/prototype-integration/2026-10-14/four-different-strategies/four-results-proof.json)、[浏览器增量](../../../evidence/prototype-integration/2026-10-14/verification-summary.json)、[Root原件检查](../../../evidence/prototype-integration/2026-10-14/root-original-inspection.json)、[最后正常cold及原字段](../../../evidence/prototype-integration/2026-10-14/root-final-help-cold.json)、[业务保全](../../../evidence/prototype-integration/2026-10-14/protected-business-data-preservation.json)、[当前入口清单](../../../evidence/prototype-integration/2026-10-14/current-links.json)。当前为累计dirty工作区的阶段交付，最终HEAD／clean proof及整体门禁归第8阶段，A／B的Git由主对话按用户顺序执行。


## 此前进度与交付记录

以下保留此前实际实施、返修与暂缓记录；本轮状态及入口见上节。

> 2026-10-14 用户已明确恢复实施，按第二版原型正式接入APS。当前第6阶段整页返修进行中，实施验收尚未完成、主对话验收changes_requested；第7在本阶段主验收后继续、第8等待派发。原型采用真实记录作交互依据，产品继续读取共同归档服务。


> 当前用户要求先讨论整页信息架构并对标成熟APS／项目管理系统，推荐区／结果页局部施工与第7开发已暂缓，当前改动原样保留。推荐卡两份源码及既有CJS已更新，22:19:15 Chrome109构建完成／资产3 passed，实际54526返回main.js1791901155；本增量1392／1920／窄屏视觉验收尚未执行。结果页及第7产品代码尚未修改，当前仅完成只读来源核对。 [实际暂停状态](../../../evidence/decision-recommendation/phase-06/repair-01/whole-page-design-pause-state.json)。


> 2026-10-13 用户追加推荐卡排版返修：原主因固定320px窄列、短清单大空白及行距过密；当前重排为全宽主因、下方收益／代价两栏，并增加正文行距和指标间隔。上一轮数学、事实、事务、原始文件与功能证据保持有效；本次结构构建及受影响页面验收进行中。第7已正式派发，先交此处更新预览再继续历史趋势。


## 2026-10-13 历史实施验收

第6阶段返修实施验收passed。代表尝试真实事实、共同页面布局与现场文案已完成；主对话在最终54526实例实测全部最后页面返修通过，并查看原生两档原图和最终CSV／XLSX人类表头。当前保留实施验收与主对话最终材料验收两项状态：implementation_acceptance=passed、parent_acceptance=passed；母stage-acceptance.md由主对话维护。第7阶段已正式派发，第8阶段planned、等待派发。[本轮返修](decision-optimization-process-repair-01-fix-note.md)和[返修验证摘要](../../../evidence/decision-recommendation/phase-06/repair-01/quality-summary.json)记录当前证据与复用范围。

方案：[已批准设计](decision-optimization-process-design.md)。清单：[执行与验收清单](decision-optimization-process-checklist.yaml)。证据：[当前验证摘要](../../../evidence/decision-recommendation/phase-06/quality-summary.json)。

## 1. 接口契约核对

- 共同collector位于`optimizer/process_evidence.py`，通过真实report评估、接受、拒绝及阶段入口接入；Outcome／CandidatePlan随原artifact保存，新过程使用`optimization-process-v1`。repository在分配候选永久引用后映射复用来源。
- process GET使用独立`process_candidate_ref`、`record_kind=attempts|progress`、稳定排序和20／50分页；snapshot绑定共同scope与实际回填filters，页码和页容量分别控制显示。当前查看、基准、保存推荐和复用来源各有独立身份。
- 新严格改善、旧含同分的最好解更新和七类实际计数分别表示；`source.profile`使用真实安全公开配置。旧档缺完整事件数、首末、耗时和接受情况保留null。保存完整未完整集合可直接计数，样例列表保持样例职责。
- 旧档显式未知目标或未知目标评分策略时，原排序占位值只承担排序来源，公共主值和目标评分分量为null，保留首项失败工序数及原字段位置；已完整批次子集的已知0、缺范围字段的旧普通保存值延续。新增纯投影场景1 passed／0.49s，见[未知范围增量](../../../evidence/decision-recommendation/phase-06/quality/backend-unknown-scope.json)。
- CSV与四类XLSX业务表使用同一selector，候选计算的拒绝理由以`rejection_reason`行保存原生数字；过程单成员导出与完整比较的全部同次成员范围分别明确。
- 实现位置与公开字段：[CORE清单](../../../evidence/decision-recommendation/phase-06/quality/core-manifest.json)、[后端清单](../../../evidence/decision-recommendation/phase-06/quality/backend-manifest.json)、[前端清单](../../../evidence/decision-recommendation/phase-06/frontend-manifest.json)。

## 2. 行为与决策核对

- 五处轨迹写入口的前200条截断及最终前缀投影已统一迁到完成时采样。321次实际collector评估／319次严格改善的用例保留首次完整事件211及后半程最后最佳值，真实总耗时分桶与固定锚点符合方案。
- 运行期保存有效变化的小事件，完成artifact每候选最多200点；原代表尝试排名与12条保留规则延续。评估、接受与严格改善按各自真实记录点计数，未核验尝试保留自己的工作统计。
- 未开始的投入为已知0，已开始预算中断与失败的缺完整过程为未知；复用候选自身为0、来源求解保留实际原永久引用。源头和真实临时worker API已核对。
- 挂载反向检查覆盖共同report／阶段、Outcome／Plan、原完成事务、process路由与导出、现有比较入口及build-order。内部helpers保持原分层；拔除推演按上述入口逆序移除，其他业务能力继续沿原选择、健康、排程和采用入口工作。
- 当前默认四候选主区域上方布局保持，过程区在候选表后默认折叠；指定成员按需读取。1392×924及1920×1080深浅主题、Chrome原生125／150%并恢复100%、成员／记录／页容量／键盘操作及独立过程候选甘特返回均通过；旧部分复用来源和合法0、当前P5首屏四候选也核对通过。

## 3. 首次实施验收的有效证据

下表保留首次交付时的实际结果，返修checklist C01—C08均passed。一次新运行保存44条尝试，主代理308字段／264差值与主对话385字段／264差值核对通过。当前最后两份相关Node通过，未变资源契约复用；Chrome109最后构建21:41:42及资产3 passed／0.60s。过程原件7083格、主代理6589业务格与原16／18表未变值分别记录。当前54526／PID27118／main.js1791898902，1119完整旧行／7201字段及34参数、正式v1／15行保持，只新增唯一run的130行。

当前C06依据主对话真实最后复验：1392×924四行bottom为674.26／741.65／809.04／876.43，正文13px；固定推荐主因保留两项45.905小时改善和原交期代价，切当前基准后逐字一致；四处共同文案、合法已知0和全部未知工序均正确。正式1280／1100工具行、资源往返、基准32／29／2行及显式详情、Process整行可读、原生125／150与100恢复各按未变源码复用。[主因与固定基准](../../../evidence/decision-stage-acceptance/stage-06-repair-01/balanced-positive-final-fixed.json)、[四行实际坐标](../../../evidence/decision-stage-acceptance/stage-06-repair-01/balanced-positive-final-geometry.json)、[合法0与未知](../../../evidence/decision-stage-acceptance/stage-06-repair-01/zero-versus-unknown-final-fixed.json)及[最终原行](../../../evidence/decision-recommendation/phase-06/repair-01/root-final-copy-cold-retention.json)可直接核对。

| 编号 | 当前结果 | 实际证据 |
| --- | --- | --- |
| C01 | passed | 五个采集用例覆盖>200、后半改善、三锚点、零耗时重合及独立分桶oracle；[采集日志](../../../evidence/decision-recommendation/phase-06/quality/core-process-tests.log)。 |
| C02 | passed | 接受／严格改善、阶段重访及真实耗时、拒绝原因、未知与未核验分支；原9项回归延续；[CORE回归](../../../evidence/decision-recommendation/phase-06/quality/core-regressions.log)。 |
| C03 | passed | 原事务保存、永久来源及复用零投入；真实临时worker过程与API读取、失败／跳过覆盖；[后端记录](../../../evidence/decision-recommendation/phase-06/quality/backend-tests.log)。 |
| C04 | passed | 已保存旧档27点的20+7／50、null及离散；代表尝试原保存序号与排名、缺耗时／接受；同后端记录。 |
| C05 | passed | 独立anchor、scope/snapshot、kind／排序／分页，原第三查看与甘特返回、取消与迟到响应；[Node原始结果](../../../evidence/decision-recommendation/phase-06/node-comparison.json)。 |
| C06 | passed | 新过程两种宽度×深浅主题4场景、原生125／150%并恢复100%、4过程成员、类别及20↔50切换、真实末页禁用、键盘首末／相邻及点选择通过；graph2真实甘特返回原graph3／基准／窗口／完整过程叶。旧部分复用离散主值0与当前P5四候选首屏通过。[矩阵](../../../evidence/decision-recommendation/phase-06/browser/matrix-final.json)、[原生控制](../../../evidence/decision-recommendation/phase-06/browser/native-controls-final.json)、[实际往返](../../../evidence/decision-recommendation/phase-06/browser/gantt-roundtrip-final.json)。 |
| C07 | passed | 真实过程CSV133列／28行、过程XLSX6表、完整XLSX16表，共3个文件／771业务行／38006单元格逐值及原生类型核对通过；来源、profile、拒绝数字、null／0／false及共同38字段一致。[原始文件核对](../../../evidence/decision-recommendation/phase-06/exports/export-verification.json)、[主代理直接读取](../../../evidence/decision-recommendation/phase-06/exports/root-original-inspection.json)。逐日18表由既有临时API契约覆盖。 |
| C08 | passed | 日常136目标495 passed／20 skipped及必要局部增量、Chrome109最新构建及构建后3项资产通过。一次新run实际保存4候选／124任务；九表989条完整旧行保持，只新增该run130行，34参数全字段及正式v1／15行保持，读取total_changes=0。[保全记录](../../../evidence/decision-recommendation/phase-06/retention-final.json)、[主代理原行核对](../../../evidence/decision-recommendation/phase-06/root-evidence-review.json)。 |

## 4. 术语一致性

`candidate_ref`、`source_candidate_ref`、`process_candidate_ref`分别负责成员、来源和独立过程锚点；`detail_queries.process`保留一个查询叶。曲线使用`primary_value`和真实`elapsed_ms`，完整score只在详情阅读。阶段、接受、严格改善、代表排名、旧含同分更新和覆盖有明确不同含义。

## 5. 架构归并

- [调度架构](../../architecture/service-scheduler.md)已写入共同真实采集、等宽采样、完整计数、原事务永久来源、新旧投影及四grain导出。
- [工作台架构](../../architecture/workbench-shell.md)已写入按需挂载、真实主目标／时间、已知比较段、单查询叶、原上下文恢复及本地构建。
- 两份架构各按自身职责说明；当前52项目录、选择／健康和正式采用规则保持原职责。

## 6. requirement回写

[候选比较需求](../../requirements/candidate-comparison-business-view.md)保持current，新增过程用户故事、真实来源与覆盖边界和本阶段实现／日志。[完整使用手册](../../../static/docs/scheduler_manual.md)及当前帮助主题同步候选过程、数值表、返回与导出；[系统速查表](../../../开发文档/系统速查表.md)新增process路由，255／255双向缺项0，见[对账](../../../evidence/decision-recommendation/phase-06/quality/quickref-vs-routes.md)。

## 7. roadmap回写

第5阶段独立返修复验passed；第6阶段done／implementation_acceptance=passed／parent_acceptance=passed，最后实际页面返修均passed，主对话整体验收passed且母记录已更新。items及主文档同步当前状态；第7已派发，第8等待。

## 8. attention候选盘点

本轮稳定约束已归并到调度／工作台架构及本阶段设计。现有attention中的Win7 x64、Python3.8、离线、单机、原完成事务和读取协议继续适用，未增加重复全局规则。

## 9. 遗留与证据边界

本阶段一次实际新运行保存4个completed候选，整轮partial来自原待料范围；旧42候选均completed，2个失败旧运行无候选。失败／未开始／预算中断用现有API与collector场景核对。现场曲线4—6点、代表尝试11条，真实单页就是末页；多页协议由旧档API27点20+7／50和既有CJS45点／21尝试证明，200点与后半程采样由321次collector事件证明。三项证据各按自身真实范围成立。

日常495通过／20跳过后，后端未知范围、既有Node、离线构建及3项资产、宿主验证脚本和帮助文字的必要增量分别有当前证据；原失败日志和截图保留。P6新增Python测试函数8个，后续修正扩展既有用例。三份原始导出已独立读取；文档核对关闭公开链接误放内部查询叶问题。最终HEAD、clean-worktree、Win7实机与整体性能按第8阶段完成。

本轮提交、推送、发布均为0；源HEAD `0df8fc48ad32124cb0384688f511a679d121cf72`，工作区为累计dirty状态。

首次交付索引：[19项历史证据](../../../evidence/decision-recommendation/phase-06/verification-final.json)、[历史入口](../../../evidence/decision-recommendation/phase-06/current-links.json)。当前返修材料位于`evidence/decision-recommendation/phase-06/repair-01/`，以[最后质量摘要](../../../evidence/decision-recommendation/phase-06/repair-01/quality-summary.json)、[54526当前入口](../../../evidence/decision-recommendation/phase-06/repair-01/current-links.json)及[当前交接](decision-optimization-process-handoff.md)为准；此前实例、失败和全部历史材料保留。

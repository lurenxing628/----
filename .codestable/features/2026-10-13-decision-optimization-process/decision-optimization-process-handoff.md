---
doc_type: feature-handoff
feature: decision-optimization-process
status: passed
created: 2026-10-13
implementation_acceptance: passed
parent_acceptance: passed
operator_ui_repair: passed
---

# 第6阶段优化过程交接

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


## 2026-10-13 历史交接

第6阶段返修实施验收passed，最后页面与主因已由主对话在54526实例实际复验通过；主对话整体阶段验收passed且已更新母记录。代表尝试真实事实、计划相关页面布局与分钟展示、共同现场文案已完成。[当前返修记录](decision-optimization-process-repair-01-fix-note.md)和[返修验证摘要](../../../evidence/decision-recommendation/phase-06/repair-01/quality-summary.json)分别记录实施、当前及历史证据。第7阶段已正式派发，第8阶段planned、等待派发。

## 1. 读取入口与身份

**最终组合实例已通过实际返修回验。** 当前`http://127.0.0.1:54526`／PID27118／exec session84133，实际HTTP返回JavaScript版本1791898902。最后共同文案的两份相关CJS通过，未变资源契约复用；Chrome109最终构建完成于2026-10-13 21:41:42，构建后3项离线资产检查通过（0.60s）。当前包含按实际贡献值说明的balanced主因和最后四处共同文案。原50499／PID79273正常关闭、exec exit0；数据库仍为原`decision.sqlite`，本轮正常cold共3次、实际新运行1次。可从[当前入口清单](../../../evidence/decision-recommendation/phase-06/repair-01/current-links.json)进入各代表页、原cb290和本轮新运行。过程原件7083格、主代理6589业务格及基准／详情／整行比较均passed，原生125／150控件与100恢复按未变界面复用。主对话最后亲自确认1392四完整行／13px、固定主因和四处文案、已知0与未知工序正确。[当前实例](../../../evidence/decision-recommendation/phase-06/repair-01/runtime-final-copy.json)、[本次冷启旧行](../../../evidence/decision-recommendation/phase-06/repair-01/root-final-copy-cold-retention.json)、[前一组合实例](../../../evidence/decision-recommendation/phase-06/repair-01/runtime-before-final-copy.json)、[即时工具栏预览](../../../evidence/decision-recommendation/phase-06/repair-01/runtime-toolbar-preview.json)和[首波冷启](../../../evidence/decision-recommendation/phase-06/repair-01/runtime-first-preview.json)各自保留。

以下64480实例及cb290产生过程保留为首次交付记录；本轮完成后另列新事实运行的永久引用和最终入口。

首次交付隔离实例为 `http://127.0.0.1:64480` / PID98520 / session66833，同数据库 `/private/tmp/aps-decision-workbench-20261013/db/decision.sqlite`。本轮已正常退出；旧65050和本阶段60906的原验收证据保留。当时JavaScript版本为1791881744。

[打开真实新运行的方案对比](http://127.0.0.1:64480/workbench?view=analysis&nav=%7B%22version%22%3A1%2C%22view%22%3A%22analysis%22%2C%22context%22%3A%7B%22run_ref%22%3A%22cb290bffcd82d59594e4d629023df19e3b5fd375e9cca4ca%22%2C%22candidate_ref%22%3A%225c49d2b6a3c6e1803490eb74657bc9c2be8e645044c98348%22%2C%22reference_candidate_ref%22%3A%22f5a2d13a79dc585cda1077bae3da88ca84c3fd1857655764%22%2C%22comparison_mode%22%3A%22candidates%22%2C%22range_start%22%3A%222026-10-13T00%3A00%3A00%22%2C%22range_end%22%3A%222026-10-17T00%3A00%3A00%22%2C%22comparison_tab%22%3A%22overview%22%2C%22metric_view%22%3A%22all%22%2C%22resource_view%22%3A%22selected_batches%22%7D%7D)：当前查看graph3、基准baseline，资源窗口10月13日00:00至17日00:00；外层显示全部4候选，推荐身份按原保存选择展示。进入后原生展开“优化过程”，选择过程成员graph2查看已验证的曲线；过程成员、记录类别和20／50页容量独立选择，再进入该候选甘特并返回。

```text
run_ref: cb290bffcd82d59594e4d629023df19e3b5fd375e9cca4ca
baseline: f5a2d13a79dc585cda1077bae3da88ca84c3fd1857655764
graph_w1_of_3: 9e51ec6e14136f2d4b20a6a9650d94163d6f519474d5dc9c
graph_w2_of_3: cfbce13666e97ac09783980f57c7dfbd728a0d50c5fd343d
graph_w3_of_3: 5c49d2b6a3c6e1803490eb74657bc9c2be8e645044c98348
```

实际运行为既有11批／32工序的同范围优化，4候选全部completed，整体partial保留原待料范围。原参数只临时改algo_mode=improve、time_budget_seconds=4，graph on／3档及原目标min_overdue保持；当前34参数包含updated_at已逐行恢复。

公开输入没有外层预算字段。本次验证宿主只在原worker的实际准备对象设置现有内部run_time_budget_seconds=30；原claim／事实核验／只读计算／完成事务延续，回执保存的实际整轮预算为30秒。HTTP服务只读取归档，CLI worker PID75893分别记录。本阶段两次正常cold：首次载入采集实现，第二次载入旧档未知范围修复；一次实际新运行、新增业务样例0，采用0。

4候选实际均为graph_ready，iterations为原通用字段0；每候选实际评估468次、严格改善2／4／5／4次、进步点4／5／6／6、8个保存阶段。改善由图候选搜索产生，主目标为超期批次数；曲线值来自原业务指标，完整score的failed_ops只在详情承担完成性优先。

## 2. 行为与事实来源

本轮唯一真实运行`7736ba758459a2078fac74f947f45d15af4667263e1fff0d`已完成，worker PID9391，原11批／32工序范围、候选4秒／整轮30秒、4候选completed，原缺料范围保持partial。34参数完整行与宿主临时prepare设置已恢复。四候选各保存11条代表尝试，共44条，均保存真实耗时及当时比较对象；5条接受、39条未接受，代表记录与全过程累计计数分别读取。四曲线保存点为4／6／6／6，共22点。主代理直接复算264项当时差值、对照308个raw→public事实，并核对44条旧尝试真实缺项仍为null。[本轮事实](../../../evidence/decision-recommendation/phase-06/repair-01/new-run/newrun-source-proof.json)、[主代理直接核对](../../../evidence/decision-recommendation/phase-06/repair-01/root-attempt-fact-review.json)。新运行入口在本轮current-links的`repair_new_run`，查看第三候选／原算法基准，展开优化过程后选择第二候选。

- 共同collector流式累计真实工作统计，在完成时按总耗时等宽采样；固定首个有效、首个应排完整与final，重合点合并，最多200点。代表尝试继续保留原排名及12条规则。
- 独立process_candidate_ref保留当前查看、基准、固定推荐及复用来源。新过程、旧离散记录、真实未开始零投入、预算中断／失败未知分别表达。
- 图形与数值表共用保存点，已知且同来源／阶段／完成性／目标范围的已核验相邻点才能连线。score只在详情；旧缺耗时点保留键盘详情，全部缺耗时的旧档明确使用保存事件顺序。
- 过程GET与CSV／XLSX共用scope、snapshot、anchor和筛选。四业务表为候选计算、进步事件、搜索阶段、代表尝试；候选计算内拒绝原因用稀疏数字行。完整XLSX普通16表／逐日18表，页码只限制屏幕。

## 3. 精确修改范围

本轮返修范围按领域清单核对：[实际尝试记录](../../../evidence/decision-recommendation/phase-06/repair-01/core-manifest.json)、[共同过程投影／导出](../../../evidence/decision-recommendation/phase-06/repair-01/backend-manifest.json)、[后端业务文案](../../../evidence/decision-recommendation/phase-06/repair-01/backend-copy-manifest.json)、[真实health主因](../../../evidence/decision-recommendation/phase-06/repair-01/backend-copy-health-manifest.json)、[正式计划界面](../../../evidence/decision-recommendation/phase-06/repair-01/formal-ui-manifest.json)、[试调／值班台](../../../evidence/decision-recommendation/phase-06/repair-01/trial-dashboard-manifest.json)、[共同词表／时间格式](../../../evidence/decision-recommendation/phase-06/repair-01/shared-copy-manifest.json)、[帮助／手册](../../../evidence/decision-recommendation/phase-06/repair-01/help-docs-manifest.json)。[前端最终清单](../../../evidence/decision-recommendation/phase-06/repair-01/frontend-final-copy-manifest.json)列出21条累计源码路径，其中最后7条共同渲染入口；新增`RunOperationEffort.jsx`统一工时说明，既有`RunBaselineControls.jsx`承担简洁新旧来源。下方26项为首次P6交付源码范围。

三份实施manifest列出的P6生产与编排源共26个，当前帮助主题另修改 `web/viewmodels/page_manuals_scheduler_outputs.py`；实际范围按manifest及本文核对。

```text
core/services/scheduler/run/optimizer/graph/ready.py
core/services/scheduler/run/optimizer/graph/reporting.py
core/services/scheduler/run/optimizer/graph/stage_scheduler.py
core/services/scheduler/run/optimizer/grasp_ig_candidates.py
core/services/scheduler/run/optimizer/local_search_round.py
core/services/scheduler/run/optimizer/outcome.py
core/services/scheduler/run/optimizer/process_evidence.py
core/services/scheduler/run/optimizer/search_report.py
core/services/scheduler/run/optimizer/search_state.py
core/services/scheduler/run/optimizer/step_report_hooks.py
core/services/scheduler/run/schedule_candidate_dedup.py
core/services/scheduler/run/schedule_candidate_plan.py
core/services/scheduler/run/schedule_candidate_runner.py
core/services/scheduler/run/schedule_optimizer.py
core/services/workbench/facts/candidate_process.py
core/services/workbench/run/decision_export.py
core/services/workbench/run/decision_process.py
core/services/workbench/run/decision_process_export.py
data/repositories/workbench_run_result_repo.py
frontend/workbench/app/RunDecisionAPI.js
frontend/workbench/app/RunDecisionComparison.jsx
frontend/workbench/app/RunDecisionProcess.jsx
frontend/workbench/app/RunDecisionProcessChart.jsx
frontend/workbench/app/styles/34-run.css
scripts/workbench/build-order.json
web/routes/workbench/run_decision.py
```

测试由新增collector文件、process API文件、4个既有导出名单与既有comparison CJS承担；原始准确清单：[CORE](../../../evidence/decision-recommendation/phase-06/quality/core-manifest.json)、[后端](../../../evidence/decision-recommendation/phase-06/quality/backend-manifest.json)、[前端](../../../evidence/decision-recommendation/phase-06/frontend-manifest.json)。本轮还修改验证宿主脚本、两项required登记、方案／清单／验收、需求、两份架构、两类手册、速查及主路线图／items；母stage-acceptance.md保持主对话维护。

## 4. 实际验证

本轮相关增量已完成：CORE8个既有用例通过、后端2个既有用例最终有效、共同文案26个既有函数及后续4节点有效通过（重合分别记录）；缺料原因、摘要小数与过程范围各扩展既有节点，正式资源导航既有节点1 passed／0.31s。真实health分项筛选的既有节点先复现失败、修复后1 passed／0.32s。三份现有Node在组合源码通过，最后仅受影响comparison／preparation增量两项通过，资源契约复用；最后Chrome109 built10及构建后资产3 passed／0.60s。试调两字段绑定的既有用例1 passed／0.78s按未变源头复用。帮助Python／Markdown的限定静态完成，最后实际推荐标题与对象覆盖两段Markdown同步并限定差异核对。本轮新增测试文件／函数均为0，原失败与必要重跑保留。[返修质量摘要](../../../evidence/decision-recommendation/phase-06/repair-01/quality-summary.json)说明当前结果与复用范围。

下列为首次交付的原有效结果：

- 采集5项与既有9项共14个唯一相关用例通过；后端7项唯一相关用例有最终有效通过结果；初始失败和修正过程保留原日志。
- 136目标日常495 passed／20 skipped、79.35s，Ruff通过；Node过程／原比较契约及评价范围增量通过；Chrome109离线构建built10，评价范围增量重新构建built10；最新构建后的3项资产检查通过（0.61s）。
- 后端最后两次局部校准覆盖预算文案及旧档显式未知目标；未知范围纯投影1项0.49s、现有Node与离线资产3项覆盖最终状态，原字段、评分顺序和合法子集0保留。
- 日常启动后后端预算文案最后校准两个文件，纯投影1项0.82s及后端10路径Ruff／Python3.8AST／diff覆盖最终状态。构建后资产原命令首次路径误写的0执行失败也保留。
- >200、后半程改善和固定三锚点由321次真实collector事件用例锁定；临时API旧档27点20+7／50及CJS代表尝试21／曲线45条锁定多页协议。本次真实新曲线只有4—6点，现场分页按实际数量说明。
- P6新增Python测试函数共8个（collector5、process API3），后续修正扩展既有用例；495为日常实际执行通过数。全项目新增与重复测试的汇总清理沿第8阶段及母对话独立审查。
- 三份原始导出和9表旧行已实际验证；两宽／深浅、原生125／150%、甘特返回及旧部分结果均通过。当前帮助主题Ruff／Python3.8AST及独立文档链接／字段核对通过。
- 当前接口对账255／255，双向缺项0。日常、局部增量、当前构建和现场验证分别记录各自覆盖范围。

[验证摘要](../../../evidence/decision-recommendation/phase-06/quality-summary.json)、[原始新运行与参数恢复](../../../evidence/decision-recommendation/phase-06/new-run/newrun-source-proof.json)、[当前冷启实例](../../../evidence/decision-recommendation/phase-06/runtime-final.json)、[实施验收](decision-optimization-process-acceptance.md)。

## 5. 现场与后续状态

本轮最后实际返修均passed：主因显示总时长与等待各减少45.905小时，原1批／17.24小时代价及313.071上限保持，切当前基准后主因逐字相同；1392×924四行末端674.26／741.65／809.04／876.43且正文13px。DP-STAGE两侧缺料／完工未知、工时未生成、真实阶段停止／拒绝、新旧来源、确认对象粒度与合法已知0均由主对话实际核对。母独立证据在`evidence/decision-stage-acceptance/stage-06-repair-01/`；实施方只整理最终材料。[固定主因](../../../evidence/decision-stage-acceptance/stage-06-repair-01/balanced-positive-final-fixed.json)、[首屏](../../../evidence/decision-stage-acceptance/stage-06-repair-01/balanced-positive-final-geometry.json)、[0与未知](../../../evidence/decision-stage-acceptance/stage-06-repair-01/zero-versus-unknown-final-fixed.json)。

本轮原1119行／7201字段逐项相等，34参数与正式v1／15行保持，只新增7736运行的130行，当前47批／91工序／13运行／50候选／985任务。一次必要新run、业务样例与采用0；最终过程原件2个／7083格，主代理直接读6589业务格，首次两原件继续保留。后续最后文案和balanced主因修复沿相同原字段、数学及7736原文件复用。正常cold3次各载入实际Python源码增量；主对话优先要求的工具栏即时构建与原Node／采集工具失败均保留。

以下为首次交付的历史现场记录：

两宽×两主题4场景、Chrome原生125／150%并恢复100%、4成员／2记录类别／4次20↔50切换、键盘首末／相邻和点选择、独立graph2甘特返回原graph3完整上下文通过。旧部分复用自身0／来源0.001秒、离散主值0及未知计数正确；P5当前单点回验四候选和当前操作可见，原8场景布局证据复用。

现场曲线4—6点、每候选代表尝试11条，单页就是末页，上一页／下一页均按真实条数禁用；没有补造多页。三份原始导出共771业务行／38006数据单元格，CSV133列、过程XLSX6表、完整XLSX16表与public source逐值及类型对应，并经独立原文件读取。

九表989条完整旧行／6533字段逐主键原值相同，只增加本次run的1job、1receipt、4candidate、124task，共130行；当前47批／91工序／12运行／12回执／46候选／861任务，34参数全字段与正式v1／15行保持，RO读取total_changes=0。旧42候选全部completed，旧2个失败运行没有候选；新4候选也全部completed，失败／未开始／预算中断分支由明确API与collector用例覆盖，现场状态没有补造。

第6阶段当前done／implementation_acceptance=passed／parent_acceptance=passed；主对话整体阶段验收passed且母记录已更新。第7阶段历史趋势已正式派发；第8阶段最终HEAD、clean-worktree、Win7实机和整体性能等待派发。本轮源HEAD `0df8fc48ad32124cb0384688f511a679d121cf72`，累计dirty工作区；提交／推送／发布0。

现场证据：[矩阵](../../../evidence/decision-recommendation/phase-06/browser/matrix-final.json)、[原生控制](../../../evidence/decision-recommendation/phase-06/browser/native-controls-final.json)、[甘特返回](../../../evidence/decision-recommendation/phase-06/browser/gantt-roundtrip-final.json)、[125%](../../../evidence/decision-recommendation/phase-06/browser/native-125-final.json)、[150%](../../../evidence/decision-recommendation/phase-06/browser/native-150-final.json)、[恢复100%](../../../evidence/decision-recommendation/phase-06/browser/native-100-restored.json)、[旧部分复用](../../../evidence/decision-recommendation/phase-06/browser/legacy-partial-final.json)、[原文件独立核对](../../../evidence/decision-recommendation/phase-06/exports/original-files-independent.json)、[九表保全](../../../evidence/decision-recommendation/phase-06/retention-final.json)、[文档核对](../../../evidence/decision-recommendation/phase-06/document-verification.json)。

现场最终索引：[19项实际证据](../../../evidence/decision-recommendation/phase-06/verification-final.json)、[当前有效入口](../../../evidence/decision-recommendation/phase-06/current-links.json)。

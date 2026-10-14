---
doc_type: feature-acceptance
feature: decision-history-trends
status: done
created: 2026-10-14
roadmap: scheduling-decision-workbench
roadmap_item: decision-history-trends
requirement: candidate-comparison-business-view
implementation_acceptance: passed
parent_acceptance: passed
summary: 四来源历史、条件判断、保存指标、原生文件及原资料保全通过
tags: [aps, history, workbench, win7]
operator_ui_repair: passed
---

## 2026-10-14 当前操作者界面返修

第7阶段实施验收、主对话独立验收及操作者界面返修均为 **passed**，对应步骤已完成。当前正常实例的实页复验见[Parent验收原件](../../../evidence/decision-stage-acceptance/stage-08/final-cold-runtime/parent-review.json)；数据、数学、事务和原件按未变职责复用。下方原交付、初次失败及补验记录完整保留。第6、7阶段主对话亲验已通过，第8此前因2秒性能目标与交接记录为 **changes_requested**。用户最新决定先推进A/B，A按已通过的功能、数据及非Windows验证收口；2秒性能目标正式移交[C待办原件](../../../evidence/decision-stage-acceptance/stage-08/performance-c-handoff.json)，保留原4／6／8候选、100天、全部资源及每候选20,000工序测量范围，范围见[第8设计](../2026-10-14-decision-integration-acceptance/decision-integration-acceptance-design.md#5-2026-10-14-已批准的操作者界面返修)。


# 第7阶段历史走势实施验收

实施验收与主对话独立验收均为 **passed**。P2-07-01—03／05／07、P3-07-04／06／08及帮助与数量导出缺口已关闭。本报告保留原第7交付事实并同步当前返修验收；整体门禁和最终HEAD／clean proof由主对话按实际状态分别记录。

原第7交付的历史实例为`http://127.0.0.1:52705`／PID82711／session78307，Python3.8.10，同原`decision.sqlite`。该次实际HTML与磁盘一致：`main.js=1791934561`、`workbench.css=1791933089`；Chrome109离线构建10项。第7累计3次正常cold，最后焦点增量仅更新JS；恢复记录pending／recovered均为空。该次导航和实例原件见[历史review-link.json](../../../evidence/decision-history-trends/2026-10-14/review-link.json)与[历史runtime.json](../../../evidence/decision-history-trends/2026-10-14/runtime.json)。

当前正常实例为`http://127.0.0.1:58240`／PID3143，Python3.8.10／Schema40，`main.js=1791956005`、`workbench.css=1791956823`。当前元数据见[第8 canonical runtime.json](../../../evidence/decision-integration-acceptance/2026-10-14/runtime.json)，实页复验见[Parent验收原件](../../../evidence/decision-stage-acceptance/stage-08/final-cold-runtime/parent-review.json)。第7移动入口[start-url.txt](../../../evidence/decision-history-trends/2026-10-14/start-url.txt)与[当前9个复验入口](../../../evidence/prototype-integration/2026-10-14/current-links.json)均指向58240，原第6阶段上下文继续保留。

## 1. 接口契约核对

- 两个GET统一使用`decision-history-v1`、现有响应及只读预算：`decision_history.py:decision_history/decision_history_export`→`queries.read_decision_history/read_history_all`→目录、保存来源、共同指标与条件→图表和原生文件。
- 四类事件分别保留运行、候选采用、试调采用、旧正式记录的永久引用、真实时间、实际来源与版本；同run多采用是多个采用事件和一次运行。
- 查询持有时间线、模式、事件日期、明确基准、选中项、指标、资源共同窗口、状态、排序、20／50分页及快照。`scope.batch_quantity`保留件数、已知小计、真实覆盖批次和`Batches.quantity`出处；90列原生条目文件覆盖同一字段。
- 挂载已实际核对：registration两路由、RunHistoryWorkspace共同入口、build-order离线登记、navigation_boot查询校验；候选、试调、正式甘特与返回组件消费共同上下文。接口明细见[公共合同](../../../evidence/decision-history-trends/2026-10-14/public-contract.json)。

## 2. 行为与决策核对

- 业务走势保留当时实际值与规模；同条件对照逐实体比较八类生产事实，算法参数独立为实验维度。相同计数且成员不同仍为变化；已知0、False、适用null及明确空集合保留原义。
- 生产条件、实际目标和评分顺序、指标单位／版本／范围／真实覆盖及共同窗口充分一致时，提供具体改善；变化与缺项保留原因、原值及断点。外协合法空工时不适用，内制NULL和真缺列保持未知。
- 试调跨度复用保存任务区间；切换按后序开始进入共同窗口，待料与普通未排沿保存身份拆分。无结果事件从原受理归档恢复已知应排数；真实失败事件原范围19道、待料1道、应排18道，已排保持未知。
- 事件目录先生成完整运行序号再筛选／分页；两对同秒运行分别为第2／3次、第4／5次。空筛选仅清日期与状态，保留阅读条件；越页回第1页保原快照。三组页签主题可见；共同Choices读取时沿既有按钮可聚焦禁用态保持键盘焦点，主动移走后保持用户的新焦点。
- 原运行／候选／试调／正式计划与甘特共用返回上下文。帮助完整说明在6.3，历史走势打开analysis、运行记录打开run章节，返回工作台视图。所有历史读取、文件与对照使用保存资料；排产、保存、采用仍由既有业务入口执行。

## 3. 验收场景核对

| 清单 | 实际验证与结果 |
| --- | --- |
| H01 | 四来源双时间线、同run多采用、真实采用身份与时间、失败及未完成事件；原API用例及主对话源修复定点通过。 |
| H02 | 实体字段及永久成员、配置独立、缺列与合法空值、旧目标回执适用性；真实454f自比1286 equal／0 unknown，图权重5→7仍条件相同而配置变化。 |
| H03 | 实际目标min_changeover→min_overdue返回different_objective；保存试调08→11为3小时、4小时保存环境为75%；窗口切换事件为0；无草稿时缺字段为未知、明确空集合为0；原用例补验通过。 |
| H04 | 51条筛选全集、20／50分页、153指标行×90唯一列、全目录标签第2→52、数量原生值及旧摘要空值／出处、409快照失效；最终单节点1 passed／5.01s。 |
| H05 | 两时间线／两模式、图点与表格键盘、候选分析→甘特→历史、正式甘特→历史完整上下文；空筛选及越页恢复、双主题页签及帮助通过。最后4次方向键GET200，busy仍BUTTON焦点；第4次主动Tab移走后保持新焦点。 |
| H06 | Python3.8针对性验证、Chrome109 built10、离线资产和真实界面；原85表2633行／20444字段值及类型保全，84表行集完全相同，日志表只追加3次正常cold对应插件加载审计。 |

## 4. 术语一致性

运行与采用事件、保存推荐与实际采用、业务观测与同条件改善、未知与零、整段跨度与有效班表容量分别表达。试调资源读取保存采用环境，原工作内容读取原草稿／场景。页面、图表与文件使用同一条目label、指标单位、覆盖、窗口和来源。

## 5. 架构归并

已同步[共同服务](../../architecture/service-scheduler.md#2026-10-14-历史事件保存来源与同条件指标)与[工作台](../../architecture/workbench-shell.md#2026-10-14-历史走势与同条件对照)。目录、请求内归档恢复、指标、条件、查询和文件各保留自己的职责；前端只消费共同值与阅读状态。帮助、注册和构建已同步；完整变更归属见[文件清单](../../../evidence/decision-history-trends/2026-10-14/implementation-files.json)。

## 6. Requirement回写

已将历史能力、真实批次数量与出处、稳定标签、空筛选恢复及完整来源返回写入[candidate-comparison-business-view](../../requirements/candidate-comparison-business-view.md)，保留既有愿景并追加本阶段实际交付日志。共同资源当前版本同步为`decision-resource-v4`。

## 7. Roadmap回写

第7条目done／implementation_acceptance=passed／parent_acceptance=passed／operator_ui_repair=passed，feature清单5步done、H01—H06 passed。第6、7阶段主对话亲验已通过，第8此前的changes_requested记录保留。用户最新决定将2秒性能目标及原4／6／8测量范围正式移交C，先推进A/B，A按已通过的功能、数据和非Windows验证收口。主方案、items、stage-acceptance及最终Git流程由主对话维护，本对话同步第7实施资料。

## 8. Attention候选盘点

当前attention中的Python3.8产品／Python3.14宿主分工、SymbolLocator及门禁口径继续适用。本阶段的具体来源、CSV文本保护、浏览器捕获与验证边界保存在feature和evidence中。

## 9. 验证记录与遗留

### 原第7交付验证记录

- 日常首轮137目标：501 passed／20 skipped／2 failed，Ruff通过，87.42s。新增路由顶层导入历史投影破坏延迟加载；导入移到实际接口读槽后，原cold2节点2 passed／1.39s、既有API4节点4 passed／5.50s。初次失败与误用Python3.14环境的setup errors均保留。后源修正H01—03为3 passed／1.68s，最后H03缺字段边界1 passed／1.14s；最后标签／数量H04为1 passed／5.01s。以上为同一日常结果的修复与相关增量，API4与原501有重叠，分别记录。
- 新增API测试函数4、CJS场景函数4；母返修扩原函数，新增测试函数0。原CJS最后0.111s通过，帮助导航沿既有runtime用例通过。最终焦点built10／最后JS资产节点1 passed／0.77s；前一组合资产3 passed／0.73s的未变入口与CSS结果复用。
- Root亲自检查最终浏览器CSV30行、XLSX主业务619行／六张表，条目90唯一列2700格直接对实际API；364原生数值、738空值。其余五表533／56／52／41／28行与此前亲验原件逐语义字段及类型保持，读取编号／时间按各次快照区分。受控四来源资源原件的3小时／4小时／75%与旧摘要空值证明继续有效。原件和初次检查器签名／数字显示预期错误分别保留。
- 窄屏720、真实Chrome125／150%及实际设置／几何证明按未变布局复用；原生缩放裁图偏移记录保留。最后100%浅深完整页和零筛选截图已亲看。主对话另实测360宽、三表1000／920／700横向滚动，以及日期、选择、基准、指标和size50的正式甘特完整往返。
- 数据保全原有85表2633行、20444字段值／SQLite类型及schema全部成立。当前2636行：OperationLogs原28行保持，新增29—31恰为06:13:30／06:39:11／07:15:53三次正常cold的plugins.load；其自增28→31，其余分配器保持。首次严格全行集相等在该表失败的原证据保留；按实际追加启动审计逐行归属，业务增量0。

### 当前状态与遗留

- 第7功能与操作者界面返修均已通过。第8此前的changes_requested记录保留；2秒性能目标及原4／6／8测量范围已正式移交C待办，A按已通过的功能、数据和非Windows验证推进交接；整体dirty门禁和最终HEAD／clean proof由主对话按实际状态分别记录。
- 当前Gate09第1—16步通过：758 collected／722 passed／36 skipped／0 failed；第17步实际failed，15项Windows launcher setup skips尚未核销。用户已明确将本轮Windows验证延期至大改完成后统一测试，该延期按真实状态保留。

证据：[日常原结果](../../../evidence/decision-history-trends/2026-10-14/daily.json)、[懒加载补验](../../../evidence/decision-history-trends/2026-10-14/repair-evidence.json)、[源修复](../../../evidence/decision-history-trends/2026-10-14/temporary-api/mother-source-regressions.json)、[H04最后单节点](../../../evidence/decision-history-trends/2026-10-14/browser-final/h04-quantity-label-final.json)、[最后焦点构建](../../../evidence/decision-history-trends/2026-10-14/build-final-focus.json)、[五组实页及最后键盘](../../../evidence/decision-history-trends/2026-10-14/browser-final/record.json)、[Root原件逐格](../../../evidence/decision-history-trends/2026-10-14/root-final-native-inspection.json)、[原资料保全](../../../evidence/decision-history-trends/2026-10-14/data-preservation-final.json)、[母最后键盘](../../../evidence/decision-stage-acceptance/stage-07/final-keyboard-focus.json)。

---
doc_type: feature-handoff
feature: decision-history-trends
status: done
created: 2026-10-14
implementation_acceptance: passed
parent_acceptance: passed
summary: 共同历史入口、来源原件和主对话独立验收入口
tags: [aps, history, workbench, win7]
operator_ui_repair: passed
---

## 2026-10-14 当前操作者界面返修

第7阶段实施验收、主对话独立验收及操作者界面返修均为 **passed**，对应步骤已完成。当前正常实例的实页复验见[Parent验收原件](../../../evidence/decision-stage-acceptance/stage-08/final-cold-runtime/parent-review.json)；数据、数学、事务和原件按未变职责复用。下方原交付、初次失败及补验记录完整保留。第6、7阶段主对话亲验已通过，第8此前因2秒性能目标与交接记录为 **changes_requested**。用户最新决定先推进A/B，A按已通过的功能、数据及非Windows验证收口；2秒性能目标正式移交[C待办原件](../../../evidence/decision-stage-acceptance/stage-08/performance-c-handoff.json)，保留原4／6／8候选、100天、全部资源及每候选20,000工序测量范围，范围见[第8设计](../2026-10-14-decision-integration-acceptance/decision-integration-acceptance-design.md#5-2026-10-14-已批准的操作者界面返修)。


# 第7阶段实施交接

原第7交付的实施验收及主对话独立验收均为passed，源码与原件已冻结。该次历史实例为52705／PID82711／main1791934561／CSS1791933089，Python3.8.10，3次正常cold。主对话已派发第8阶段；本对话维护实施记录，主对话维护`stage-acceptance.md`与Git。

## 阅读入口

共同“排产记录”入口保留运行记录，并增加历史走势。可选运行／正式采用、业务走势／同条件对照，查询指标、事件日期、资源共同窗口、状态和20／50分页；选中条目及基准保留完整永久身份。

当前实例为58240／PID3143，Python3.8.10／Schema40，`main.js=1791956005`、`workbench.css=1791956823`，元数据见[第8 canonical runtime.json](../../../evidence/decision-integration-acceptance/2026-10-14/runtime.json)。第7移动入口[start-url.txt](../../../evidence/decision-history-trends/2026-10-14/start-url.txt)已指向58240；[当前9个复验入口](../../../evidence/prototype-integration/2026-10-14/current-links.json)保留原第6阶段上下文。原52705的[runtime.json](../../../evidence/decision-history-trends/2026-10-14/runtime.json)与[review-link.json](../../../evidence/decision-history-trends/2026-10-14/review-link.json)作为历史元数据和导航原件保留，原历史截图、文件和验证继续保留。

## 共同职责

| 责任 | 实际来源 |
| --- | --- |
| 历史筛选与纯值 | `core/models/workbench_decision_history.py` |
| 四来源事件目录 | `history/catalog.py`、`workbench_history_catalog_repo.py` |
| 请求内归档恢复 | `history/reading.py`、`conditions_source.py` |
| 保存指标与比较门槛 | `history/metrics.py`、`conditions.py` |
| 排序分页与图点投影 | `history/queries.py`、`projection.py` |
| 筛选全集原生文件 | `history/export.py` |
| 薄路由与共同入口 | `web/routes/workbench/decision_history.py`、`RunHistoryWorkspace.jsx` |
| 页面、图、表及返回 | `DecisionHistoryAPI.js`、三个历史组件、共同导航与原有结果／甘特入口 |

接口及页面读取已保存资料；来源缺失和损坏沿原有明确错误路径，旧资料缺项在原值与原因中保留。资源容量使用各来源保存的有效环境，试调采用保存环境与原工作内容分别读取。无新业务表、二次历史归档或密码学摘要。

## 独立验收场景

1. 原现场15次运行及1次正式采用，两条时间线；正式v1的实际采用来源与保存推荐不同，本地采用日和UTC提交日分别保留。
2. 实际生产条件相同、图权重5→7，条件equal且算法配置different；实际目标min_changeover→min_overdue时保留值并显示目标变化。
3. 受控独立四来源含同一运行两次候选采用、真实保存试调采用和旧正式摘要。班表8→4小时、保存任务3小时的共同窗口按4小时环境计量；旧摘要缺资源值保留空值。
4. 历史→候选分析→候选甘特→历史、历史→正式甘特→历史，恢复原查询及选择；图点键盘、数值表、窄屏、原生125／150%和主题受影响位置。
5. 现场CSV与六表XLSX同查询全集，核对真实数字、空值、来源、条件、窗口和快照；完整临时库逐表、逐字段及类型保全。

原现场验收库的运行／样例／试调／采用增量为0。受控测试沿已有fixture独立生成及保存资料，其来源和纯适配probe分别记录。第8阶段已由主对话派发，A／B阶段提交推送由主对话执行。

## 原第7交付的最终修正、原件与保全

- 主四项源问题、空筛选、页签选中、同秒标签与最后键盘焦点均关闭。Choices复用现有tooltip禁用原因保持原生可聚焦，读取时挡动作；连续方向键保持焦点，主动移走后保持新焦点。
- 最后H04单节点1 passed／5.01s，新增测试函数0；原API4节点、后H01—03、H03边界与CJS分别复用和增量记录，日常501 passed／20 skipped／2初次失败按原cold补验闭环。
- 实际新CSV30×90、XLSX主3分区619行／六表；2700条目格直接对同快照API，五附表533／56／52／41／28行原值及类型保持。原quantity15列、真实来源和未知空值均通过，最后focus只改JS，文件证明复用。
- 原85表2633行／20444字段值和SQLite类型全部保留，84表完整行集相同；OperationLogs新增3条对应3次正常启动，原28条保持，当前2636行，业务运行／样例／试调保存／采用增量0。

原第7交付证据：[完整实施验收](decision-history-trends-acceptance.md)、[Root原件](../../../evidence/decision-history-trends/2026-10-14/root-final-native-inspection.json)、[数据库保全](../../../evidence/decision-history-trends/2026-10-14/data-preservation-final.json)、[真实UI](../../../evidence/decision-history-trends/2026-10-14/browser-final/record.json)、[母验收](../../roadmap/scheduling-decision-workbench/stage-acceptance.md)。

当前Gate09第1—16步通过：758 collected／722 passed／36 skipped／0 failed；第17步实际failed，15项Windows launcher setup skips尚未核销。用户已明确将本轮Windows验证延期至大改完成后统一测试。第8此前的changes_requested记录保留；2秒性能目标及原4／6／8测量范围正式移交C，A按已通过的功能、数据和非Windows验证推进交接。累计dirty阶段验收及最终HEAD／clean proof由主对话按实际交付状态分别记录。

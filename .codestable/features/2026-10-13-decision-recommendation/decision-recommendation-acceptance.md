---
doc_type: feature-acceptance
feature: decision-recommendation
status: done
implementation_acceptance: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第5阶段固定推荐、共同完成集合、当前取舍、真实支撑及分行导出验收
tags: [aps, workbench, recommendation, completion, tradeoff]
---

# 第5阶段实施验收

第5阶段第一轮返修实施完成：P2-05-01首屏四候选与真实主因／当前基准、P2-05-02完整批次集合与精确剩余入口、P3-05-03交接映射均已修复并通过必要验证。实施验收passed，主对话独立复验passed，第6阶段已派发，第7—8阶段等待派发。此前有效的固定选择、52项差值、SHA清理及原文件证据继续复用；本轮记录见 [repair-01](decision-recommendation-repair-01-fix-note.md)。

返修前第5阶段实施验收通过。固定选择证据、三类推荐、三轴完成性、共同完成批次的交付取舍、主要3+3与全部52项差值、旧实际消费者、真实支撑与推荐三表已完成。工序取样、基准侧来源和浮点展示问题已修复；用户追加的全仓无用SHA及临时编号清理通过当时日常与冷读核验。

依据为[设计](decision-recommendation-design.md)与[执行清单](decision-recommendation-checklist.yaml)。本阶段接续第0—4阶段的累计未提交工作区；主对话的独立[阶段验收](../../roadmap/scheduling-decision-workbench/stage-acceptance.md)由主对话维护。

## 1. 接口契约核对

- 保存推荐固定来自完成事务；目标评分最优与健康比较原方案分别保存。第三查看候选、查看基准、正式模式只改变当前比较。选择规则仍为`candidate-selection-v1`，精确选择/健康证据分别为`candidate-selection-evidence-v1`／`candidate-health-evidence-v1`。
- 共同52项目录沿用`decision-preparation-v4`；新增推荐读模型为`decision-recommendation-v1`。旧`recommendation.reason_code/selection_basis/benefits/costs`继续由同一事实派生。
- 推荐包含`complete/schedulable_scope/partial`三类，搜索覆盖、可排工序、业务全链交付分别呈现。当前采用状态使用既有预检和事务复验；查看记录保持只读。
- 部分候选按精确完整批次集合分组；推荐和当前查看基准的交付取舍采用`common_completed_batches`交集。整次受理的未知交付保持原范围，空交集、未指定交期、非法交期与缺项分别表达。
- 概览返回数量及最多3个支撑样例；完整集合用独立completion_candidate_ref按20／50分页，all／complete／unfinished／ordinary／deferred／unknown六类按共同事实读取。组内各成员分别读取剩余需求；准备页work_scope=remaining与原批次／设备／归属筛选取交集，页面及导出沿同一筛选与快照。
- 推荐CSV为96列唯一宽表头，XLSX“推荐说明／完成集合／剩余需求”为39／36／59列，加“口径／比较范围”共5表。完整比较为12表；单资源逐日入口增加2表，共14表。数字保持原生、null留空、比率导出使用%数值；实际选择原证据继续保留原始ratio。

## 2. 行为与决策核对

- 完整评分、实际主目标与完整评分并列、baseline／sequence／输入顺序裁决在选择入口保存；嵌套临时候选key由完成事务映射为永久ref。
- balanced四项检查、实际检查对象、限制、容差、接受与真正覆盖标记来自当次选择；健康分量保留原值、实际容差、贡献、总分与共同时间原点。
- 当前主要取舍按完成性、交付、资源、准备／切换、稳定性、时间的业务顺序确定，最多3项收益和3项代价；单位各自评价，52项差值完整展开。
- 未排或暂缓使准备需求减少时显示“少安排的准备需求”，方向中性，并指向具体剩余工作。完成集合相同的候选归一组，集合不同的部分候选分组。
- 新记录展示精确证据；历史缺少细分裁决／健康原分量时列出具体缺项，保留原固定身份、评分、策略与原容差。已知0、不适用和未知分别显示。
- 值班台取舍消费共同后端文本与差值，当前所选候选明确；试调“保存后先预检”和当前采用预检状态沿用原提交／查询回调。
- 页面原生展开选择依据、全部差值与支撑；复用候选可展开本候选及来源候选的实际策略记录。选择数值使用6位展示并在title保留原始值，%容差按正确单位显示。

## 3. 验收场景与实际证据

| 场景 | 当前结果 | 实际证据 |
| --- | --- | --- |
| C01 固定选择与当前取舍 | passed | 实际三次查询切第三查看、原算法／另一关键链查看基准及正式模式，完整selection_basis与原收据相等；当前查看身份独立、每次52项差值。 |
| C02 主要取舍与全部差值 | passed | 业务排序、3+3、全部52项、微小非零值和%百分点用例通过；真实混合交期原推荐相对关键链算法加权拖期减少45.7h、算法切换增加38次；原第4阶段一天窗口交付减少17.24h与1个超期批次，同时两类资源CV增加0.097869、调整工序增加21道。 |
| C03 分类、完成集合与剩余需求 | passed | 共同领域7项及三类DTO延续通过；新增完成集合公开GET按独立候选分页，四anchor各列出完整A/B两批、完成集合互补，21批实际20+1与50同内容／快照／as_of。普通推荐剩余仅DD-P-A一道未排；合法待料及未知0行／未知无已知剩余分别由真实接口和必要API／领域用例覆盖。 |
| C04 并列、复用与balanced | passed | 真实新run主目标4候选并列、完整评分1个最优，实际secondary_score第2索引裁决；四容差通过且actual override=true，健康3分。既有6／8候选展开核对双方16个策略字段、4个永久引用，全部相等。 |
| C05 新旧来源、消费者与预检 | passed | 新精确证据及历史缺项通过；两个旧消费者pytest各1项、交付包41项通知合同通过。恢复原目标后当前采用预检返回source_context_changed／409，确认入口禁用，正式v1／15行保持。 |
| C06 紧凑布局、支撑与返回 | passed | 原五类支撑及两层甘特回跳证明延续；新增集合、类别、remaining→基准甘特→remaining→原第三比较完整往返。双宽／双主题及3cost八组合均13px、四完整候选、真实主因与基准关系／3+3／当前操作完整；Chrome原生125／150%新增区筛选、入口和局部滚动通过，零alerts。 |
| C07 原始CSV／XLSX | passed | 3代表场景6文件及正式模式完整12表XLSX，共7文件、2315业务行、137525单元格原始回读通过；96列与39／36／59列、6973数字、717布尔、46JSON单元格及null、scope、snapshot、双方来源逐项核对。14表合同由既有接口用例覆盖。 |
| C08 日常、离线与资料 | passed | Python3.8.10日常487 passed／20 skipped、134目标、Ruff全通过，77.06s；随后局部UI的comparison Node、10项Chrome109构建及2项离线资产增量通过。API9份原GET、最终页面及资料核对通过；同库一次冷启动65050／PID41829，9表完整行集、34参数及正式v1／15行与修复前相等，读取total_changes=0。 |

真实balanced运行`454f75ffaa01ad531eceaa8454f14b7d139677015b36c0f3`：11批／32工序，4候选各31安排，含1道合法待料暂缓。保存推荐`11c2be4c3a18ee08c7964c8de61601bc2e236cdf8f806a1e`为重点工序优先1/3；raw最优及健康基准均为原算法`fb57f70b77acb5beb87c53e62f1277fe306f76d9fd25fe64`。实际算法工种切换主目标3对3，超期2→3、上限3；总拖期284.61→301.85h，增加17.24h／约6.0574%，上限313.071h、容差10%。健康跨度与等待各减少45.905h，重点工序平均开始提前1.586315789h，三项各贡献1分；原始数、阈值和评分保留。

原始证据根：`evidence/decision-recommendation/aps-decision-workbench-20261013/`。

- [原收据](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/balanced-run/original-receipt.json)、[候选原证据](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/balanced-run/original-candidate-artifacts.json)、[固定依据核对](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/fixed-basis-verification.json)
- [正式及参数保全](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/balanced-run/retention-verification.json)、[四首屏布局](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/browser/layout-verification.json)
- [日常原日志](../../../evidence/decision-recommendation/quality/daily-final.log)
- [浏览器核验](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/browser/verification.json)、[原始导出核验](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/exports/export-verification.json)、[有效证据索引](../../../evidence/decision-recommendation/aps-decision-workbench-20261013/evidence-index.json)。旧工序取样失败及3张未就绪／截图偏移图片保留原记录，并在索引中单列排除。
- [当前质量摘要](../../../evidence/decision-recommendation/quality/quality-summary.json)、[清理范围及保留用途](../../../evidence/sha256-cleanup/summary.json)、[清理时日常](../../../evidence/sha256-cleanup/daily-repaired.log)、[清理时冷读](../../../evidence/sha256-cleanup/cold-read-final.json)。原P5业务矩阵与7份导出的事实保持，清理后的范围／来源／新键另有增量证据。
- [返修最终验证](../../../evidence/decision-recommendation/repair-01/verification-final.json)、[最终8组合](../../../evidence/decision-recommendation/repair-01/layout-final.json)、[原生125／150%](../../../evidence/decision-recommendation/repair-01/browser/native-zoom-final.json)、[最终逐行保全](../../../evidence/decision-recommendation/repair-01/final-retention-verification.json)、[当前实例](../../../evidence/decision-recommendation/repair-01/runtime-final.json)。原布局失败及中间主因隐藏状态保留，最终保存真实主因、可视当前基准关系及13px／3+3均通过。

清理初轮日常为482 passed／2 failed／20 skipped：失败分别为测试仍引用已删除的摘要函数、校准页面假hook槽位过时。两处测试夹具更新后，最终日常退出0。实际Master普通null恢复偏移已修，源变化后重新构建；SGS签名非空类型在构造器校验后绑定，单文件Pyright最终0 errors。原失败与修后记录均保留，未添加新的生产保护层。

## 4. 术语一致性

保存推荐、目标评分最优、健康比较原方案、当前查看和当前查看基准分别表达。推荐取舍为保存推荐减当前基准；候选矩阵与明细为各候选减当前基准。算法保存拖期／切换与业务完整批次交付／真实事件保持各自来源。采用预检为当前状态；保存推荐是当次事实。

## 5. 架构归并

选择与健康事实由源头保存，推荐纯投影解释事实；共同完成集合和交付算术由领域入口提供。请求内复用交付／准备／资源缓存，推荐与旧实际取舍入口／导出消费共同差值。支撑沿现有明细及真实甘特drill，内部返回上下文沿现有SPA导航保存。

## 6. Requirement 回写

`candidate-comparison-business-view`同步三类推荐、三轴完成性、共同完成范围、当前取舍、真实支撑和同源导出；当前52项目录及第0—4阶段能力保留。手册区分推荐取舍和所选候选明细；接口速查同步推荐及导出。

## 7. Roadmap 回写

第4、5阶段主对话独立验收passed；第5阶段返修实施结果与主对话独立复验分别记录。第6阶段已派发并进入实施，第7—8阶段保持planned。母阶段验收记录由主对话维护。

## 8. Attention候选盘点

现行Win7 x64／Python3.8／离线单机、永久身份、完成保存事务及采用约定继续适用。新增事实合同已进入需求、架构、手册和速查表。

## 9. 遗留与交付边界

- 当前同库47批／91工序／11运行／42候选／737任务，正式v1／15行及原32张表中的旧记录保留，34项参数恢复。新增1批／1工序及1次balanced运行，采用仅预检。
- 当前为第0—5阶段累计dirty工作区，源HEAD为`0df8fc48`，保留README原有并发新增；本轮无提交／推送／发布。最终HEAD、clean-worktree、Win7实机与整体边界性能按第8阶段验收。
- 第一轮返修实施验收passed，主对话独立复验passed；第6阶段已派发，第7—8阶段等待派发。
- 当前只读预览为`http://127.0.0.1:65050`／PID41829，同一临时数据库；四案例、三项代价及正式辅助入口见交接和链接身份文件。清理及本轮返修新增排产、业务样例、采用和重复导出均为0。

主对话独立复验已通过：在65050实例实测四完整候选、真实主因／可视基准／13px／3+3、四成员互补全集、21批同快照分页和精确剩余往返；原始证据在`evidence/decision-stage-acceptance/stage-05-repair-01/`。母`stage-acceptance.md`由主对话维护，本记录仅同步其通过结论。

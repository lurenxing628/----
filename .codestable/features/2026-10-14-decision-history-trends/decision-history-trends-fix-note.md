---
doc_type: fix-note
feature: decision-history-trends
status: done
created: 2026-10-14
summary: 日常冷启动、四组源头问题、三项界面与最后键盘焦点全部闭环
tags: [aps, history, source-projection]
---

# 第7阶段真实问题修正

| 问题 | 原因与影响 | 处理位置／状态 |
| --- | --- | --- |
| 日常2项cold-start smoke失败 | 新薄路由顶层导入历史查询，沿试调投影提前加载`scheduler.schedule_service`，破坏未使用时延迟加载约定 | `decision_history.py`在实际接口读槽内导入；Python3.8.10的原2个冷启动及4个API节点通过 |
| P2-07-01 外协合法空工时 | 条件字段统一要求非空，将外协不适用的准备／单件工时判为未知，阻断自身同条件判断 | `conditions.py`已修；真实454f自比1286 equal／0 unknown，自制未知及实际缺列继续未知 |
| P2-07-02 试调指标缺口 | 历史适配漏安排总时长，切换读取全期，未安排集合未按保存待料身份拆分 | 已沿保存安排、共同切换窗口及完成性投影完成；3小时跨度、窗口0切换、待料／普通未排及缺字段边界通过 |
| P2-07-03 旧目标评分口径漏读 | 只读新增选择字段，漏旧回执已保存的目标与评分顺序 | 已沿核验候选身份、实际目标及评分维度恢复`receipt.summary.algo`；旧6字段已知，真缺项及不适用目标继续未知 |
| P3-07-04 无结果事件应排数未知 | 无候选时返回空指标，受理capture已知范围丢失 | 已完成；真实原范围19、明确待料1、应排18，已排未知；原归档逐工序核对通过 |
| 页帮助裁切缺历史说明 | 历史入口属于analysis视图，说明段放在6.2，analysis帮助按6.3截取 | 完整历史说明移入6.3，6.2保留运行步骤及入口；现场analysis／全文／run正文与导航已通过 |

扩展既有H01／H02／H03及真实fixture，主四项源修正已在项目Python3.8下3 passed／1.68s；保存缺档边界最终1 passed／1.14s。不增加每字段测试函数，不重跑未变化的第6阶段矩阵。第一次日常失败、宿主环境setup错误和修复后的正确环境结果分别保存。

证据：[薄路由正确环境补验](../../../evidence/decision-history-trends/2026-10-14/repair-evidence.json)、[真实条件与旧目标probe](../../../evidence/decision-history-trends/2026-10-14/source-fixes/conditions.json)、[原H01—03补验](../../../evidence/decision-history-trends/2026-10-14/temporary-api/mother-source-regressions.json)、[帮助实际HTTP](../../../evidence/decision-history-trends/2026-10-14/help-rendered-check.json)。最终冷启、界面及原件结果在验收记录与证据摘要中同步。

## 最后界面与原生字段修正

| 问题 | 原因与处理 | 最终结果 |
| --- | --- | --- |
| P2-07-07 零匹配工作区报错 | filtered空态原action为false；共同清除日期／状态入口保留阅读条件，越页返回1沿原快照 | 正式10/12为0→清除恢复1，page99→1，实际UI及原CJS通过 |
| P2-07-05 三组页签选中不可辨 | 局部样式沿系统info与选中色、字重和边框；共同focus样式保留 | 浅／深、360宽及三个组均主验收通过 |
| P3-07-06 同秒运行不可区分 | 全目录先按受理时间／永久ref生成第N次运行，所有消费者读取label，日期独立显示 | 第2/3及第4/5次同秒可区分；51条20/50分页标签不变 |
| P3-07-08 读取后键盘焦点落BODY | busy传通用Button使原生disabled并blur；Choices复用既有tooltip reason，使aria-disabled且原生可聚焦，阻止忙碌动作 | 最后4实际切换GET200，焦点保持；主动Tab移走后保持新焦点，母验收passed |
| 批次原数量漏原生列 | scope已有完整数量值，ENTRY_FIELDS未输出 | 补15列与共同缺项记录；H04单节点1 passed／5.01s，90列原件2700格对实际API通过 |
| 帮助章节与当前主题不一致 | 完整历史说明移6.3，共同helpUrl依history_topic选择analysis／run | 正文与返回视图实页通过，原runtime导航回归通过 |

所有问题实施与主对话验收均passed。最后main1791934561／CSS1791933089，CSV30行／XLSX主业务619行；最后焦点为JS增量，原件与数学证明复用。原85表2633行全部保留；3次正常启动的3条plugins.load追加审计另列，当前2636行。首轮日常／H04字符串保护预期／Root原件检查器及严格日志行集的失败原证据分别保留，实际闭环见[实施验收](decision-history-trends-acceptance.md)。第8已派发。

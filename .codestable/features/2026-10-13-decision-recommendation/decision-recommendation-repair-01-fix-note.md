---
doc_type: issue-fix-note
issue: decision-recommendation-repair-01
feature: decision-recommendation
status: done
implementation_acceptance: passed
parent_acceptance: passed
created: 2026-10-13
summary: 第5阶段第一轮两项P2和一项交接P3返修
---

# 第5阶段第一轮返修

范围按主对话派发的P2-05-01、P2-05-02及P3-05-03。母阶段独立验收由主对话维护；本记录保存返修实现、实际证据与复验入口。

- P2-05-01：推荐标题／正文／覆盖重复及布局占用使1392×924仅2个完整候选。实际修前229px面板、table top671.1875，4行bottom826.125／911.875／997.625／1083.375。合并重复表达，调整推荐、3+3主项、当前操作及候选表层级，维持13px正文和完整展开证据，6/8项正常滚动。
- P2-05-02：共同CompletionScope已有精确全集合，公开DTO和UI只给数量／3样例，剩余drill没有membership筛选。以独立候选anchor接现有20/50分页，完整／未完成批次及普通缺排／合法暂缓／未知各按共同事实；每批仅返回真实计数、公共需求指标和精确剩余drill。准备页work_scope=all|remaining与原batch／machine／allocation交集，真实空集保持空，未知且已排齐不编造剩余；请求内缓存和原全范围summary复用。
- P3-05-03：已以清理后实际冷读候选label复核，graph2=148ac438fbc8284dd264db62f2cf560797aa76fb52b4e875、graph3=552b2a3f4a985dffd85577fc0141e3b69753f2978540674c；handoff映射已修正。

本轮沿用实际选择／健康策略、52项算术及原运行与正式v1；新增完整批次分页和精确剩余筛选。概览保持有界，组内每个成员分别读取剩余需求。原母复验已通过的固定选择、balanced容差、原CSV/XLSX及SHA清理按未变事实复用。

证据目录为`evidence/decision-recommendation/repair-01/`；原状态与两轮实际布局失败均保留。当前源码、静态资源和验证冻结，三个返修项实施验收passed，主对话独立复验passed；第6阶段已派发，第7—8阶段等待派发。

接口速查已按新增完成集合路由核对：文档与实现各254项，双向缺项0，命令exit0。实际对账见[quickref-vs-routes](../../../evidence/decision-recommendation/repair-01/quickref-vs-routes.md)，[原日志](../../../evidence/decision-recommendation/repair-01/quickref.log)保留。


## 当前实现与已完成验证

- 默认区显示原保存解释生成的一条真实选择主因；两张主要取舍卡的短列头显示保存推荐相对实际当前基准。完整原值、全部52项、完成性和支撑按需展开。局部链接按钮通过共同控制高度变量及局部padding覆盖达到24px，卡片／面板／条目余白收紧，正文维持13px和完整3+3。
- 后端7个源码及2个相关测试的职责与4个有效用例见[backend-manifest](../../../evidence/decision-recommendation/repair-01/backend-manifest.json)。27批次公开GET按20+7／50取全；改变候选、类别、排序会拒绝旧快照。普通剩余与CSV/XLSX保留同一筛选及快照，空交集为0行；未知且已安排齐保留0个已知剩余与空钻取，未产出来源保持null和原因。
- [日常](../../../evidence/decision-recommendation/repair-01/daily-final.json)：Python3.8.10、134目标，487 passed／20 skipped、77.06s，Ruff全通过。日常后只有局部UI变化：[最终UI修正及comparison Node／构建](../../../evidence/decision-recommendation/repair-01/build-tradeoff-correction.json)、[两项离线资产](../../../evidence/decision-recommendation/repair-01/assets-final.log)实际通过；后台／准备／资源的未变验证复用。
- [真实GET](../../../evidence/decision-recommendation/repair-01/api-readback.json)及9份raw：四个候选各完整列出DD-P-A／B，两组完成批次互补；保存推荐剩余只有DD-P-A的57267…一道普通未排。21批实际20+1与50逐行、顺序及永久引用相同，snapshot_ref和as_of相同；[root原始读取复核](../../../evidence/decision-recommendation/repair-01/root-api-inspection.json)保留。
- [最终8组合首屏](../../../evidence/decision-recommendation/repair-01/layout-final.json)及[root原始坐标与像素复核](../../../evidence/decision-recommendation/repair-01/root-layout-inspection.json)：balanced／真实3cost各在1392×924、1920×1080深浅主题均4完整候选、13px、当前操作与真实主因／基准关系可见。1392的第4行bottom分别907.03125／890.4375，余16.96875／33.5625px；1920分别887.03125／870.4375。三项代价完整可见。
- [真实剩余往返](../../../evidence/decision-recommendation/repair-01/browser/recommended-remaining-roundtrip.json)：剩余仅一道→基准DD-P-A实际08:00—14:00工序→remaining仍一道→原第三比较。候选、基准、范围、全部detail_queries、成员、类别、页码及展开状态与原上下文逐项相等。
- [实际页面分页](../../../evidence/decision-recommendation/repair-01/browser/mixed-completion-paging.json)：21批完整集合按20+1与50读取，API对象与DOM顺序分别完全相同，同一snapshot_ref／as_of及当前查看／参考身份保持。主代理已读取三份原响应和行数；[合法暂缓／未知空类别](../../../evidence/decision-recommendation/repair-01/browser/legal-deferred-unknown.json)显示DD-S-01合法待料1道、普通未排0道，未知类别0行，切回暂缓仍为原一批。
- [Chrome原生125／150%](../../../evidence/decision-recommendation/repair-01/browser/native-zoom-final.json)：真实缩放设置、DPR分别1.25／1.5，cssZoom=1。主因和可视基准关系、4个集合控件及批次正文维持13px，普通未完整筛选仍精确为推荐成员DD-P-A一批，表内水平滚动、页面无横向溢出及零alerts；恢复100%后原上下文保持。主代理读取两份raw并目视两张集合截图。
- [最终逐行保全](../../../evidence/decision-recommendation/repair-01/final-retention-verification.json)：SQLite mode=ro／query_only=1，9表完整行集和列与修复前相等，34参数、正式v1／15行保持，connection_total_changes=0。[最终实例](../../../evidence/decision-recommendation/repair-01/runtime-final.json)为65050／PID41829，同库一次冷启动、最终main.js1791871190；[当前链接身份](../../../evidence/decision-recommendation/repair-01/current-links.json)为原四案例加三项代价；[最终验证索引](../../../evidence/decision-recommendation/repair-01/verification-final.json)记录原证据及复用边界。
- [最终材料核对](../../../evidence/decision-recommendation/repair-01/document-verification.json)：状态、完整清单、当前6入口、graph2／graph3、487当前与476／484历史来源一致，80个Markdown本地目标、29个JSON证据路径全部有效。累计240项dirty工作区、151 tracked／89 untracked／0 staged，HEAD0df8fc48、README原10／0保留；无提交／推送／发布。

修前仅2行，初次紧凑版仅3行；移除主因的中间版虽让balanced首屏4行，3cost仍超出26.6875px且缺默认主因。最终实现保留主因和可见基准，通过实际控制尺寸与余白同时满足两个场景；相关失败与中间截图继续保留并明确区分。

主对话独立复验已通过：在65050实例实测四完整候选、真实主因／可视基准／13px／3+3、四成员互补全集、21批同快照分页和精确剩余往返；原始证据在`evidence/decision-stage-acceptance/stage-05-repair-01/`。母`stage-acceptance.md`由主对话维护，本记录仅同步其通过结论。

---
doc_type: audit-verification
audit: 2026-06-24-core-algorithm-deep-review
verifies: final-report.md
status: completed
created: 2026-06-24
method: cs-audit-verify (确定性 file:line 真相源 + 12 个窄上下文 subagent 逐条下钻调用链 + 主线程全局对账)
baseline: git HEAD e8ba50b3 @ ci/install-networkx-win（业务代码 core/web/tools/tests 工作树干净）
---

# 深度 Review 12 条发现 · 核实对账报告

## 一句话总裁定

**12 条发现全部"代码事实属实",无一证伪——报告的 file:line(86 条唯一引用机械核查全 OK)、引用内容、调用链机制描述都对得上当前 HEAD。**
**真正的问题在严重度:6 个 P1 里只有 2 个(F-02 停机、F-04 候选绕 improve)是无前置/后置校验兜底的真 P1,其余 4 个 P1 被算法后段校验、不可达前提或产品合同兜住,应降级。** 整体呈"机制真实、严重度系统性偏高"。

核查方式:每条发现派一个只读 subagent,不止核 file:line,而是从入口下钻调用链到"坏结果"落点,主动找报告漏看的守卫/前置校验/产品合同;主线程对 5 个降级裁定(F-01/F-03/F-06/F-11 + ScheduleSummary 构造)亲自读码复核。

## 逐条对账

| ID | 报告 | 核实裁定 | 严重度复核 | 关键修正 / 根因 |
|---|---|---|---|---|
| F-01 | P1 | **部分成立** | **P1→P2(产品确认项)** | partial 写正式版本 + 跳甘特图属实,但全程 `success=False`/`PARTIAL`/warning,**非假装成功**,且被两测试正面锁定为预期合同 → 是 by-design 产品取舍,非缺陷。报告证据#9"两测试口径冲突"=**误读**(一处陈旧 docstring,实测断言不冲突)。 |
| F-02 | P1 | **成立** | **维持 P1** | 停机硬约束加载失败 → 空 downtime_map + 仅 warning + 摘掉 hard_constraints 声明,**全路径无阻断**,算法空停机段=零避让,任务可排进真实停机段。报告漏看 gantt 校验有停机 blocker,但它只管**人工拖拽调整**,不管算法自动排产 → 缺口仍真实。 |
| F-03 | P1 | **部分成立** | **P1→P2** | 坏工时非 strict 默认被吃成 0.0 进算法属实;但零时长结果(start==end)被 `payload_contract.py:174 start<end` **100% 拦截,绝不写脏库**(报告"不一定落库"实为"一定不落库")→ 是**可用性/可诊断缺陷**(坏输入未在入口报错),非数据完整性缺陷。 |
| F-04 | P1 | **成立** | **维持 P1** | 候选被 `_candidate_cfg` 无条件 `replace(algo_mode="greedy")` + `VALID_ALGO_MODES=("greedy",)` 锁死,improve 的 OR-Tools 预热/本地搜索被 `algo_mode!="improve"` 门控全跳过,选中 greedy 候选直接成落库方案,无并行 improve 结果、无回退、无告警。**修正:触发开关是 `graph_analysis_mode=="on"`,非报告暗示的独立"候选对比"开关**(与 algo_mode 正交)。 |
| F-05 | P1 | **成立** | **P1→P2** | balanced 覆盖判定 `selection.py:156-169` 硬编码 failed/overdue/tardiness 三维容差,**不看随 objective 变化的 score 主维**(min_changeover→changeover_count 等)→ 在这两类目标下确可静默选"当前目标更差"方案。**修正:`raw_score_best` 本身是按当前 objective 选的,只是"覆盖那一步"不看主维;报告勿读成"系统完全不看目标"**。触发需 graph on + 存在 HEALTH_BETTER 关键链候选。 |
| F-06 | P1 | **部分成立** | **P1→P3(防御债)** | 裸 `int()`、调用顺序、persistence、测试盲区全属实;但 **`ScheduleSummary` 全仓唯一构造点 `scheduler.py:463`,三计数字段全由 int 计数器派生(run_state 70/74-75/99),坏字符串当前不可达** → 崩溃/不一致实际触发不了,是"未来上游被改坏才暴露"的防御债。附带真盲区:测试用 `total_ops=True`(`int(True)=1` 不抛错),根本测不出字符串崩溃分支。 |
| F-07 | P2 | **成立** | **维持 P2** | 有环+block=no 顶层硬写 `status="available"`,而 `graph_analysis_summary_warning` 以 available 为"无需告警"判据返 None,且降级字段(effective_mode 等)**在前端分析页零渲染入口** → 两条用户可见路径都看不到"图增强已退化"。**不夸大**(用词"弱化"非"丢失",准确)。不违架构,体验/可观测债。 |
| F-08 | P2 | **成立** | **维持 P2** | 服务入口 simulate=不落库(置回调 None) vs 底层 simulate=写 Schedule/History 模拟版只跳正式状态,语义确相反;但**底层带 simulate=True 的调用方全是 tests,生产唯一入口在模拟时直接 `persist_schedule_fn=None`,生产不可触发** → 命名/边界债,无数据安全风险。**修正:报告把底层证据行号 287-317 挂在 `persist_schedule` 名下,实际属 `persist_schedule_core_in_tx`**。 |
| F-09 | P2 | **成立** | **维持 P2(偏 P3)** | 两条调度路径(batch_order 逐工序命中 blocked、SGS 用 remaining_failed 一次性累计)对同批次后续跳过工序**只加 failed_count、不补 state.errors 明细**,唯图依赖阻断路径补了明细形成对比;`success=(failed_count==0)` 不会假成功。纯诊断/可观测债。 |
| F-10 | P2 | **部分成立** | **维持 P2(偏 P3)** | 派工/SGS 异常被压成泛化文案、摘要与操作日志缺结构化根因属实,且非静默吞错(logger 带 traceback)。**修正两处报告自我低估:① OR-Tools 路径实际带原始异常对象+limit=10 堆栈,是诊断最强一处,报告写成"只计数+logger"偏轻;② 降级事件已带 `code/scope/field` 结构化标签,真正缺结构化根因的只是"派工/SGS 异常类"**。 |
| F-11 | P2 | **部分成立(偏夸大)** | **P2→P3** | 未知字符串→no→跳齐套门禁、web 有保护,事实全对;但**公开签名 `run_schedule(..., enforce_ready: Optional[bool]=None)` 声明的不是 str**,字符串仅被运行期 `isinstance(str)` 容错分支吞下,且**该分支全仓零活体调用方**(51 处调用,生产 2 个 route 入口都经 `form_optional_toggle_bool` 转 bool/None)→ 谈不上"服务层合同风险"。且齐套门禁归 no 是**放宽排产**非误锁。 |
| F-12 | P2 | **成立** | **维持 P2** | required 白名单 `QUALITY_GATE_GUARD_TESTS` 是**纯字面量枚举、无任何 glob/前缀/分组通配**,verify 脚本以精确路径相等核销;点名 4 文件(graph_on_mode / sgs_scoring_fallback / candidate_runner / candidate_persistence)经 grep 确认**真实存在且全不在列表** → 真实纵深防护缺口(full pytest 仍跑,但 required 强核销没钉住)。 |

## 跨节对账(全局一致性)

1. **F-04 与 F-05 触发门相同**:两个独立 subagent 都判定候选对比的实际开关是 `graph_analysis_mode=="on"`(而非一个独立"候选对比"开关)。两条互相印证,无矛盾。**建议:报告 F-04/F-05 措辞统一改为"开启图分析候选对比(graph_analysis_mode=on)时"**,避免读者以为是常开行为。
2. **F-01 / F-03 / F-06 在 persistence-payload 链上自洽**:F-03 的零时长行=invalid row → 若全是 invalid 则 no_actionable、若尚有 ≥1 合法行则 partial(F-01),F-06 的计数恒为 int 与 F-01 的 `scheduled_ops>0` 整数判定一致。三条无冲突。
3. **严重度分布重算**:报告称 6 P1 + 6 P2。核实后建议分布 = **真 P1: 2 条(F-02, F-04);P2: 6 条(F-01 产品确认 / F-03 / F-05 / F-07 / F-08 / F-12);P3: 3 条(F-06, F-09, F-11);F-10 介于 P2/P3**。无一条证伪,降级集中在"被后段校验或不可达前提兜住"的项。

## file:line 机械核查

- 报告(final-report.md + phase-2)共抽出 **86 条唯一 `path:line` 引用,basename 解析真实路径后全部 OK**(文件存在 + 行号在范围),无 MISSING / OUT_OF_RANGE / 歧义。
- 仅 2 处"行号/归属"瑕疵(不影响结论):F-03 `schedule_service.py:204-205` 中 strict_mode 实际在 205 行(204 是 enforce_ready);F-08 底层证据 287-317 实际属 `persist_schedule_core_in_tx` 而非 `persist_schedule`。

## 报告自身建议订正项(本体未改,待拍板)

| 处 | 问题 | 建议 |
|---|---|---|
| F-01 证据#9 | "两测试文件口径冲突"=误读,实为一处陈旧 docstring | 改为"低优先级文档债",从风险升级理由里移除 |
| F-03 判断 | "不能证明零时长一定落库" | 收紧为"零时长行必被 `start<end` 拒,绝不落库;真实危害是坏输入未在入口报错" |
| F-04/F-05 | 暗示存在独立"候选对比"开关 | 统一改"图分析候选对比(graph_analysis_mode=on)开启时" |
| F-05 大白话 | 易读成"系统完全不看目标" | 补"raw_score_best 本身按目标选,缺口在覆盖判定那一步不看目标主维" |
| F-06 | 写成现实风险 | 标注"当前不可达(计数恒为 int),属防御债";测试盲区证据改用 `scheduled_ops="bad"+success=False` |
| F-08 | 底层行号挂错函数名 | 归属改为 `persist_schedule_core_in_tx` |
| F-10 | OR-Tools 写成"只计数+logger";降级事件称"纯通用文案" | 更正为"OR-Tools 带原始异常+堆栈;降级事件已有 code/scope/field;缺口仅在派工/SGS 异常类" |

## 给用户的下一步建议(按真实优先级)

1. **先处理 2 条真 P1**:F-02(停机硬约束失败应在 strict/正式排产入口阻断,不在算法层补)、F-04(候选继承原 algo_mode,或在 UI/摘要明示"候选仅 greedy 试算")。
2. **F-03/F-05 降 P2 但值得修**:F-03 在正式排产入口对坏工时 fail-loud(治本在解析层,非动 payload 校验);F-05 给 balanced 覆盖判定加"当前 objective 主维不显著劣化"护栏,或对 min_changeover/min_weighted_tardiness 退回 score_only。
3. **F-06/F-11 降 P3**:若修,治本点是 `ScheduleSummary.__post_init__` 收口(而非各消费点散补 parse) / `_resolve_enforce_ready_effective` 对未知字符串抛 ValidationError;不急。
4. **F-12 维持 P2**:把点名 4 个合同测试登记进 `QUALITY_GATE_GUARD_TESTS`,并补一条 registry 自检元测试防再漏登记。

> 本核查只读不改业务代码,也未改原审计报告本体;以上订正与降级建议待用户逐条拍板。

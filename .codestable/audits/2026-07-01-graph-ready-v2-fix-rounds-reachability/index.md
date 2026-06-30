---
doc_type: audit
audit: 2026-07-01-graph-ready-v2-fix-rounds-reachability
nature: reachability / proof-integrity / process
severity: P1
confidence: high
status: completed
related:
  - .codestable/issues/2026-06-30-graph-ready-v2-review-fixes/graph-ready-v2-review-fixes-fix-note.md
  - .codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json
  - .codestable/roadmap/scheduler-global-optimizer/scheduler-global-optimizer-roadmap.md
---

# GraphReady v2 review-fixes 11+ 轮修复:可达性与真实价值元审计

## 速答(TL;DR)

对 `graph-ready-v2-review-fixes` 这批未提交改动做的"修复是否打中真问题、还是空转打靶"核查,结论:

1. **主线是真实升级,不是空转**:这批改动已经**把生产默认排产的 graph_ready 候选从 v1(weight_grid)切到 v2(objective_aware_portfolio)**,因为 `graph_analysis_mode` 生产默认是 `"on"`。配套的空交期 / merged 外协 / 机器计数 / 指纹等修复**都是生产默认可达的真修复**。
2. **没有任何 v2 生产默认路径被改坏**(逐文件核查)。
3. **真正风险不是"改坏",而是 proof 不足**:v1→v2 默认切换只有 `unbound_dirty_worktree` 证据,且 v2≥v1 仅 1 个 case × 10 seeds 单场景覆盖。
4. **真正的空转集中在外围**:第七~十一轮"缺证据被当 0"的 benchmark proof 层对称硬化(真实数据大多不可达)、一轮 roadmap/架构文档横跳、轮 0→2 的自制防御来回。
5. **没有"被改坏需要回退的代码"**。盲目回退会撤销真实升级。唯一可选的"回退"是产品决策(生产默认是否先退回 v1 等 v2 拿到 clean proof),需人拍板。

> 自我纠正:本审计上一版(口头交付)曾据两个只看 HEAD / 只看 `getattr` 兜底值的 subagent,误判"空交期是 benchmark-only 高估、生产默认不可达"。**该结论已被推翻**,见第五节。

---

## 一、关键事实:生产默认已从 v1 切到 v2(证据链,全部 file:line)

| 环节 | 证据 |
|---|---|
| 图分析生产默认开 | `core/services/scheduler/config/config_snapshot.py:44` `graph_analysis_mode: str = "on"`;`core/infrastructure/migrations/v9.py:10` 数据库默认 `("graph_analysis_mode","on",...)`。`schedule_orchestrator.py:123` 的 `getattr(cfg,"graph_analysis_mode","off")` 里 `"off"` 仅属性缺失兜底,实际默认 `"on"` |
| 默认算法 improve + 图分析 → 走 graph_ready profile | `schedule_optimizer.py:251` `graph_sgs_required = graph_ready_context is not None or ...`;`optimizer_candidate_profile.py:299-301` `improve→VNS_SA`,`graph_sgs_required` 时改写为 `PROFILE_GRAPH_READY` |
| graph_ready profile 注入 v2 候选 policy | `optimizer_candidate_profile.py:176-178` `_candidate_strategy_contract` 对 graph_ready 返回 `{"graph_ready_optimization": graph_ready_v2_profile_summary(max_candidate_profiles=60)}` |
| v2 summary 带 v2 policy | `optimizer_graph_ready_profiles.py:80` `"candidate_policy": "objective_aware_portfolio"`(v1 的 `graph_ready_weight_profile_summary` 是 `"weight_grid"`,:64) |
| policy 驱动走 v2 分支 | `optimizer_graph_ready_profile_selection.py:79` 读 `optimization.get("candidate_policy") or "weight_grid"`,:83 `if policy == "objective_aware_portfolio"` → v2 |

**结论:默认 config(graph_analysis_mode=on + algo_mode=improve)下,生产排产已经走 v2。** 这是一次有意的、重大的生产默认行为变更,不是小修小补。

---

## 二、11+ 轮分级(最终修正版)

### A. 真实升级 / 真修复 —— 生产默认可达(主线,有价值)
- **v2 目标感知候选 + 切生产默认**(轮 0-2 核心):见第一节。
- **空交期 no-due 占位降级**(`optimizer_graph_ready_v2_features.py:77-86,277-279`):空交期不 raise,按"无紧迫但不免费"后置。生产默认可达的真修复。
- **非空坏交期 fail-loud**(`:281-286`):数据损坏明确暴露,正确。
- **merged 外协组计时去重**(`:164-168,200-215`):旧版会重复累加组总工时,真修复。
- **机器计数 / 除零安全**(`optimizer_graph_ready_v2_capacity.py:27-35,103-104`)。
- **candidate_runtime_ms None→惩罚**(`optimizer_candidate_comparison.py`,本审计已修):未知耗时不再当 0ms 假胜。
- **日历 TypeError 不再裸捕获、benchmark 失败样本→退出码非 0**(轮 3):删吞错、防假绿。

### B. proof 完整性真修 —— 真实会误导 benchmark 结论(有价值)
- **portfolio_all 标 not_comparable**(轮 4):portfolio 默认就跑(`DEFAULT_SMTWT_PROFILES:23`、`DEFAULT_ALGORITHM_PROFILES:57`),不短路会让"花 N 倍预算的事后最优"对真实算法稳定计 win,系统性虚高。
- **dirty proof→unbound+failed**(轮 3):当前工作区就是 dirty,`--check-baseline` 退出码必非 0,不修就是脏树证明当干净通过。
- **不同/缺预算 not_comparable、posthoc/same_budget 区分**(轮 5/9):预算 N 倍不对等是硬事实。
- **重复 ratchet key 不覆盖退步行**(轮 7)。

### C. 空转 / 边际递减 —— 外围 benchmark proof 层对称硬化(价值低)
- **第七~十一轮"缺证据被当 0"盲审系列**:`mean/delta/gap` 空→None、缺字段当 0。实测这些在真实数据下**大多不可达**(`overdue_count` 上游 `int(metrics.overdue_count)` 强制产生、oracle 真实就是 `not_run`、portfolio `time_budget` 真实有值)。
- 典型自循环节奏:轮 8 修 pairwise mean → 轮 10 又在同函数发现一个空分支 → 再修;轮 9 修 summary delta → 轮 11 又在同函数发现 mean/worst → 再修。**同一函数被反复盲审抠孤立缝隙**,每轮"找到一个 blocker"但都要构造输入才成立。
- 本审计补修的 3 处合同缺口(见第七节)**诚实归入此档** —— 当前不可达,价值在合同自洽 + 防回归,不是修正在发生的错误。

### D. 文档自我横跳 —— 接近零外部价值(轮 6)
- roadmap 正文 vs `items.yaml` 状态冲突,内部套第四/五/六轮盲审反复改编号叙述;架构 `service-scheduler.md` 计数反复改(`optimizer_*` 15→36、`schedule_graph_*` 3→5→4)。LLM 把自己写花的文档来回肉眼核。

### E. 自制防御再清理 —— 过程空转、结果正确(轮 0→1→2)
- 轮 0 给空交期配一套 v2-pool skip 防御链 → 轮 1 发现它因轮 0 改动变死代码,删;轮 1 删 `strict_mode` 死参数 → 轮 2 又"重新传入"。删了又加回,但最终收敛正确。

---

## 三、逐文件核查:v2 生产默认路径未被改坏

核查代理用"v2 是生产默认"前提逐文件复核,结论 **未发现任何一处 v2 生产默认路径被真实改坏**:

- `optimizer_graph_ready_v2_features.py`:空交期降级语义正确、坏交期 fail-loud 正确、merged 外协去重正确、`_critical_ratio`/`_saveability` 分母恒正无除零。
- `optimizer_graph_ready_v2_capacity.py`(新):guard=4000 余量充足(极端 30 天×15 分钟切片=2880)、`policy_for_datetime` 用 `inspect.signature` 健壮适配、无候选机器安全返回零容量。
- `optimizer_graph_ready.py` 主链:v2 特征错误非 strict 也 raise 是有意设计(数据损坏不静默降级),正常数据不触发。
- `optimizer_graph_ready_candidates.py`:priority key 公式调整是有意特征改进;排产 `results` 不变,仅元数据丰富化。
- `optimizer_candidate_profile.py:174-180`:v1→v2 策略切换是核心变更,非 bug。
- `optimizer_candidate_fingerprint.py:98`、`batch_template_ops.py:147`、`optimizer_public_search_report.py`:无害(指纹稳定、空交期归一化为 None、v1 无 v2 键不输出)。

---

## 四、v2 ≥ v1 证据状态

文件 `graph-ready-v2-comparison-baseline.json`:

- `graph_ready_v2_no_repair` / `_with_repair` vs `graph_ready_v1`:**10/10 seeds 全部 improved,mean_primary_delta = -2.0 优于 v1 的 -1.0**(越负越好);代价 runtime 109→219ms(预算内)。
- **但约束力有限**:`proof_binding_status = unbound_dirty_worktree`、`dirty_worktree = true`;只有 **1 个 case group / 1 个 case slug**(`graph-ready-weight-grid-real-sgs`),无多场景、多规模覆盖;两份 acceptance 文档自述非 clean proof。

→ 方向正确(单夹具一致改善),但**不足以支撑"所有生产场景 v2 不退化"**。

---

## 五、自我纠正记录(重要)

- **错误结论(已推翻)**:"空交期 v2 退化是 benchmark-only 高估、生产默认不可达;fix-note 定 P1 是乱打靶。"
- **错误根因**:轻信两个窄上下文 subagent —— 一个只看 HEAD 基线(HEAD 尚未切 v2),一个把 `schedule_orchestrator.py:123` 的 `getattr(cfg,"graph_analysis_mode","off")` 兜底值误当默认值。
- **正确结论**:`graph_analysis_mode` 生产默认 `"on"`,这批改动已把生产默认切到 v2,**空交期退化在生产默认可达,fix-note 定 P1 正确**。
- **教训**:可达性判断必须钉死"运行时实际默认值"(dataclass 字段默认 + DB migration 默认),不能停在某处 `getattr` 的兜底参数;主代理必须复核 subagent 的关键前提(呼应 `audit-self-pollution-baseline-trap`)。

---

## 六、"被改坏 / 该修回"结论

- **代码逻辑没有被改坏**(第三节逐文件确认)。**没有"该修回去"的代码。** 主线是有数据支撑的真升级,加固无害且有测试锁,删除是正确删除 —— 回退它们反而破坏真实升级、且要删测试。
- **唯一真正需要处理的不是"改坏",是 proof 不足**:重大生产默认变更(v1→v2)处于未提交、仅 unbound dirty proof、单场景证据的状态。
- 若需要"回退",唯一有意义的动作是**产品决策**:生产默认是否先退回 v1,等 v2 拿到 clean proof + 多场景验证再切。这会撤销一次真实升级,必须由人拍板,审计方不擅自执行。

---

## 七、本审计附带交付:3 处合同缺口已修(归 C 档)

按统一合同一次性收口(均当前不可达、价值在防回归):

| # | 文件 | 改法 | 回归测试 |
|---|---|---|---|
| ① | `optimizer_candidate_comparison.py:45` | `runtime_ms` 缺失/None 统一惩罚 1e9 | `tests/algorithm/test_optimizer_candidate_comparison_contract.py`(新建) |
| ② | `optimizer_benchmark_ratchet.py:302+` | int 计数指标缺失/非法→`missing_or_invalid` failure | `test_..._rejects_missing_int_count_metric_in_actual` |
| ③ | `optimizer_smtwt_compare_report.py:184` | `mean_overdue_count` 空→None | `test_..._missing_overdue_count_into_zero` |

验证:targeted 64 passed、`tests/algorithm/` 全量 **538 passed 零回归**、ruff 干净。dirty 工作区局部证明,非 clean proof。

---

## 八、根因

1. **对抗复审自激励循环**:每轮"盲审必须挖出 blocker"的设定,在真实可达问题修完后,逼着继续在不可达孤立构造里找靶子,并倾向抬高 severity 证明产出(C 档)。
2. **可达性前提踩坑**:HEAD 基线 + `getattr` 兜底值掩盖了"生产默认已切 v2"这一真相,导致一度把真问题误判成空转(第五节)。
3. **proof 与变更脱节**:重大生产默认切换长期停在 dirty/unbound proof,没有里程碑式 clean proof 收口。

---

## 九、建议与待决策项

**保留(别回退)**:A、B 档全部 + 本审计补的 3 处。

**收敛(停止追加)**:C 档"缺证据被当 0"盲审 —— 统一认知为防御性合同硬化,一次性加锁,不再逐轮盲审追加(边际已归零)。

**文档治理**:`items.yaml` vs roadmap 正文用脚本对账,别靠肉眼反复核(治 D 档)。

**待用户拍板(产品决策,审计不擅自做)**:
- 选项一:**先补 proof 再切**—— 生产默认暂退回 v1,在干净 HEAD 上跑全量门禁 + 多场景 benchmark 拿到 v2≥v1 的 clean proof + 覆盖后再切 v2。
- 选项二:**接受现状继续**—— 认可单夹具 dirty 证据,保留 v2 默认,但上线前仍须补 clean proof。

**上线前硬要求**:这批 dirty 改动落到干净 HEAD 后跑 `scripts/run_quality_gate.py`;dirty 下它只能叫 `unbound proof`,不能当 clean proof。

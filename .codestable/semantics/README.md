# Semantic Debt Radar(语义债务雷达)

针对"LLM 反复生成导致概念在不同地方悄悄分叉"的治理旁路。**不替换**现有 ruff/pyright/pytest 门禁,
是加在旁边的一条语义债务旁路。本目录全部为**审计资产**,不属交付运行代码。

## 为什么用隔离的 .venv-semantic(Python 3.14)
- 交付运行环境是 Win7 / Python 3.8,`requirements.txt` 不得污染。
- drift-analyzer 需 Python ≥3.11、hypothesis/syrupy 需 ≥3.10,无法进 3.8 的交付/开发环境。
- 本项目 3.8 代码在 3.14 下 import 正常(已核验),故一个隔离 3.14 venv 即可承载全部审计工具。
- 语义测试**刻意放在 `tests/` 之外**:交付门禁 `testpaths=["tests"]` 跑 3.8 `.venv`(无 hypothesis),
  若放进 `tests/` 会让当前全绿的 3.8 门禁在 import hypothesis 时崩。已验证 0 泄漏。

## 一次性建环境
```bash
python3.14 -m venv .venv-semantic
.venv-semantic/bin/pip install -r .codestable/semantics/requirements-semantic.txt
```

## 日常用法
```bash
# 1) 语义守卫(property + snapshot),用隔离 3.14 venv
python .codestable/semantics/run_semantic_guards.py
# 重建快照基线(语义有意变更时):
APS_UPDATE_SEMANTIC_SNAPSHOTS=1 python .codestable/semantics/run_semantic_guards.py

# 2) 概念账本 vs 真代码一致性(交付 3.8 venv 也能跑,只需 PyYAML)
python .codestable/semantics/tools/check_concept_registry.py

# 3) drift 结构腐蚀扫描(只读,写 evidence/SemanticDebt/drift/)
.venv-semantic/bin/python .codestable/semantics/run_drift_scan.py
```

## 重生成 drift agent brief
`run_drift_scan.py` 写出 `evidence/SemanticDebt/drift/drift-baseline.{json,md}`。
agent brief(含 A∩B 交叉核验 + 工具口径校准)在 `evidence/SemanticDebt/agent/drift-agent-brief.md`,
由分析脚本基于 baseline.json 生成(逻辑见 git 历史中的生成步骤)。

## 目录
```
.codestable/semantics/
  concept-registry.yaml          # 概念身份证中心(plan_role / graph_analysis_mode / fallback_degradation)
  semantic-drift-ledger.md       # 漂移台账(SEM-0001 ADR-0012 stale_doc 等)
  concepts/                      # 每个关键概念的身份证 md
  tests/                         # 语义守卫:hypothesis 性质 + json snapshot(隔离运行)
  tools/                         # snapshot helper + 概念账本校验器
  run_semantic_guards.py         # 守卫总控
  run_drift_scan.py              # drift 扫描总控
  requirements-semantic.txt      # 审计工具依赖(只进 .venv-semantic)
evidence/SemanticDebt/
  drift/drift-baseline.{json,md} # drift 结构扫描产物
  agent/drift-agent-brief.md     # 待 Agent 分类的 triage 简报(已含交叉核验)
```

## ⚠️ 两条铁律(读 drift 结果前必看)
1. **drift 的 AVS 不是本项目的"分层违规"**。drift AVS = Martin 不稳定度耦合指标(`A.py -> B.py`),
   不是有向越层;本项目 AST 全量分层违规仍是 **0**。别把 154 条 AVS 当 154 处越层。
2. **drift 的 MDS"重复"里有真护栏**。如 `normalization_matrix._merge_aliases` ↔ `boolean_normalize`
   正是审计 §90 **LB-B1 承重双实现**——drift 叫你删,删它会撞分层红线。
   **drift 结果必须过 Agent 语义法医,不能直接修。**

## 落地阶段(本次完成 Phase 1+2 子集)
- ✅ **Phase 1 基线**:隔离 3.14 venv、concept-registry、2 个概念身份证、drift baseline、agent brief。
- ✅ **Phase 2 守卫(首批)**:plan_role 性质、config 字段性质、graph/plan_role snapshot、概念账本校验器。
- ⬜ Phase 3 Agent 审计闭环:逐条分类 brief 里的 MDS/PFS,写回台账 + 配守卫。
- ⬜ Phase 4 CI report-only:semantic-py 与 drift job 上传 evidence,不挡主线。
- ⬜ Phase 5 新增漂移阻断:旧债登记免责,新增 high semantic_drift / 用户可见泄漏 fail。

完整方案见对话记录;主审计报告见 `.codestable/audits/2026-06-02-underwater-debt-census/REPORT.md`。

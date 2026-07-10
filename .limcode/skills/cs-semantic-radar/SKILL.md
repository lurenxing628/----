---
name: cs-semantic-radar
description: APS 项目专属——治"语义漂移债/失忆债":同一个词在不同地方被 LLM 悄悄改出两个意思。概念身份证 + Hypothesis/snapshot 守卫 + drift 扫描。触发：用户说"漂移债"、"失忆债"、"语义漂移"、"概念跑偏没"、"同一个词是不是长出两个意思了"、"这俩地方说的是一回事吗"、"plan_role 到处不一样"、"扫一下有没有自相矛盾"、"加个守卫钉住这个概念"、"跑一下 drift"、"语义雷达"、"cs-semantic-radar"。仅用于本 APS 项目。
---

# cs-semantic-radar（APS 项目专属语义债务雷达）

## 这个 skill 干什么

普通 lint 抓单文件坏味道；cs-audit 抓代码债；cs-checkup 体检地基。但有一类债它们都接不住：**LLM 反复生成后，同一个概念（plan_role / graph_analysis_mode / 降级语义…）在不同地方悄悄长出第二种含义**——这就是"失忆债 / 语义漂移债"。

cs-semantic-radar 补这块。核心不是"自动改代码"，是建一套**长期资产 + 持续守卫**：

```
确定性工具先抓可疑点(drift) → Agent 做语义法医判是不是真漂移
   → 写进概念账本和漂移台账 → 把确认的固化成 Hypothesis/snapshot 守卫
```

大白话：**工具抓现场，Agent 断案，台账记案底，测试防止同一个词再长出第二个意思。**

**专属**：剧本里写死了本项目的真收口点和真概念（见下）。不要拿去别的项目。

产出（已在 2026-06 首次落地，本 skill 让它可重放）：
- `.codestable/semantics/concept-registry.yaml`（概念身份证中心）
- `.codestable/semantics/concepts/*.md`（每个关键概念的身份证）
- `.codestable/semantics/semantic-drift-ledger.md`（漂移台账，SEM-NNNN）
- `.codestable/semantics/tests/`（Hypothesis 性质 + JSON snapshot 守卫）
- `evidence/SemanticDebt/drift/`（drift 结构腐蚀基线）+ `agent/drift-agent-brief.md`（triage 简报）

---

## 启动必读

开始任何动作前：
1. 读 `.codestable/attention.md`（项目注意事项）。
2. 读 `.codestable/semantics/README.md`（若存在）——它记了隔离环境、跑法、两条工具铁律。缺失说明是首次落地，按 Phase 1 建。
3. 确认隔离审计环境 `.venv-semantic`（Python 3.14）在位：`.venv-semantic/bin/python --version`。缺失按"环境"一节重建。

---

## 不可动摇的环境纪律（这是本 skill 的命门）

- **隔离 `.venv-semantic`（Python 3.14）跑全部审计工具**，绝不污染交付 `.venv`（3.8）/`requirements.txt`。本项目 Win7/Python3.8 离线交付，运行包只服务交付不服务审计。
- **语义测试刻意放 `tests/` 之外**（在 `.codestable/semantics/tests/`）。交付门禁 `testpaths=["tests"]` 跑 3.8 venv（无 hypothesis），放进 tests/ 会让当前全绿的 3.8 门禁在 import hypothesis 时崩。已验证 0 泄漏，别破坏这个隔离。
- **工具只进 `.codestable/semantics/requirements-semantic.txt`**：hypothesis / syrupy / drift-analyzer。
- 重建环境：`python3.14 -m venv .venv-semantic && .venv-semantic/bin/pip install -r .codestable/semantics/requirements-semantic.txt`。

---

## 两条工具铁律（读 drift 结果前必看，已被血泪验证）

1. **drift 的 AVS「Architecture Violation」≠ 本项目分层违规**。drift AVS 是 Martin 不稳定度耦合指标（`A.py -> B.py`），不是有向越层；本项目 AST 全量分层违规仍是 **0**。别把上百条 AVS 当上百处越层。
2. **drift 的 MDS「Exact duplicates」里有真护栏**。它会把 `normalization_matrix._merge_aliases ↔ boolean_normalize`（=审计 §90 LB-B1 承重双实现）标成"删重复"——而删它撞分层红线。**drift 结果必须过 Agent 语义法医，不能直接采信"删重复"。**

---

## 本项目的真收口点 / 真概念（判 P5、写身份证用）

- **plan_role**：唯一收口 `core/models/schedule_plan_role.py`（PLAN_ROLE_LABELS / plan_role_label / VALID_PLAN_ROLES）。⚠️ 严禁为满足测试在 `core/services/scheduler/` 新建第二个 plan_role 模块——那就是它要治的 P5。严格校验在 `schedule_plan_query_service.resolve_plan_view`。
- **graph_analysis_mode**：`config_field_spec.py`（enum, default 'on', choices off/report/on）；当前现状 `ARCHITECTURE.md` 第6节（on 已接入 ready 队列+图评分，与旧 ADR-0012 冲突 = SEM-0001 stale_doc）。
- **数值解析收口点**：`core/shared/strict_parse.py`（parse_finite_int / parse_required_*）。
- **资源归一收口点**：`normalize_schedule_resource_filter` / `report_context_filters.normalize_report_resource_filter`。
- **降级语义**：灵魂线"坏数据不准静默兜底、宁可暴露错误也不自欺"。

---

## 工作流

### Phase 0：定模式 + 算增量

- 首次落地（无 `.codestable/semantics/`）→ 跑 Phase 1+2 全套建资产。
- 已有资产 → 默认只跑"扫描 + 守卫复跑 + 增量 triage"（Phase 3-5），不重建身份证。
- 给用户一句确认：**"语义雷达已建。本次：重跑 drift 基线 + 跑 12 个守卫 + triage 新增 MDS/PFS。OK 吗？"**

### Phase 1：建概念身份证（首次 / 新概念）

1. 对每个要纳管的概念，回真代码核验它的收口点/默认值/合法值集/失败语义（务必 import 真模块确认，别凭记忆——首次落地时方案里 3 个假设 API 全是幻觉）。
2. 写 `concept-registry.yaml`（含 allowed_values / failure_policy / canonical_resolver / forbidden_meanings）。⚠️ YAML Norway 坑：`off`/`on`/`yes`/`no` 裸键会被解析成布尔，必须加引号 `"off":`。
3. 每个概念写一份 `concepts/{concept}.md` 身份证。

### Phase 2：建守卫（首次 / 新守卫）

1. Hypothesis 性质测试打在**已存在的真收口点**上（plan_role 标签稳定性、config 默认值自洽、未知值 raise）。
2. JSON snapshot 锁对外语义形状（中文标签映射、graph 配置默认值）。首次 `APS_UPDATE_SEMANTIC_SNAPSHOTS=1` 建基线。
3. 写概念账本校验器 `tools/check_concept_registry.py`（账本 vs 真代码一致性，3.8/3.14 都能跑）。
4. **负向验证每个 snapshot 守卫**：篡改→必须红，还原→绿。守卫不会红就是没用。

### Phase 3：drift 结构腐蚀扫描

1. `.venv-semantic/bin/python .codestable/semantics/run_drift_scan.py`（drift exit 0/1 均正常，1=有 findings）。
2. 产出 `evidence/SemanticDebt/drift/drift-baseline.{json,md}`。

### Phase 4：Agent triage（语义法医）

1. 从 baseline.json 提 MDS/PFS（真"AI 分叉"信号），其余信号多是噪音。
2. 做 A∩B 交叉核验：drift 命中的文件 ∩ 审计/承重清单已知点 → 强互证；只 drift 命中 → 多为误报或微重复。
3. 每条判 6 类之一：consistent / pure_refactor_debt / naming_debt / stale_doc / semantic_drift / insufficient_evidence。
4. 高置信 semantic_drift / stale_doc 写进 `semantic-drift-ledger.md`（SEM-NNNN，带退出条件）。

### Phase 5：跑守卫 + 收口

1. `python .codestable/semantics/run_semantic_guards.py`（应全绿）。
2. `python .codestable/semantics/tools/check_concept_registry.py`（账本未腐烂）。
3. 发现的真债**只登记不顺手改**；要改走 cs-issue/cs-refactor，等用户确认。

---

## 与相邻技能的边界

| 技能 | 触发 | cs-semantic-radar 怎么对待 |
|---|---|---|
| `cs-audit` | 主动扫代码债 | audit 扫通用债；radar 专扫"概念分叉/语义漂移"，更专 |
| `cs-checkup` | 地基体检全景图 | checkup 看结构/决定/健康度；radar 看概念语义一致性 |
| `cs-audit-verify` | 核查报告真实性 | radar 产出 drift 基线，verify 可拿它做第三方交叉核验信源 |
| `cs-issue`/`cs-refactor` | 修债 | radar 只登记+建守卫，修走它们 |

---

## 守护规则

- **隔离环境不可破**——绝不把审计工具装进交付 .venv/requirements.txt；语义测试绝不放进 tests/（会炸 3.8 门禁）。
- **守卫打在真收口点，不造新模块**——为满足测试新建一个已存在概念的模块=制造 P5，本末倒置。
- **drift 结果必过 Agent 法医**——不准直接采信 drift 的"删重复"（含承重墙）；AVS 不当越层。
- **概念身份证回真代码核验**——allowed_values/默认值/失败语义必须 import 真模块确认，不准凭记忆（首次踩过 3 个幻觉 API）。
- **snapshot 变更须解释**——不准无脑 `APS_UPDATE_SEMANTIC_SNAPSHOTS=1` 刷掉红灯；先问"语义变化是否合理、概念账本是否同步"。
- **只登记不顺手改**——radar 不出代码改动。

---

## 分模式（带参数）

- `/cs-semantic-radar`（无参）→ 已有资产则跑 Phase 3-5（扫描+triage+守卫）；无资产则全套 Phase 1-5
- `/cs-semantic-radar 建` → 只 Phase 1-2（建/补概念身份证 + 守卫）
- `/cs-semantic-radar 扫` → 只 Phase 3-4（drift 扫描 + triage）
- `/cs-semantic-radar 守卫` → 只 Phase 5（跑守卫 + 账本校验，省 token）

---

## 退出条件

- [ ] `.venv-semantic` 在位，三工具可 import
- [ ] concept-registry.yaml 通过 check_concept_registry.py（账本未腐烂）
- [ ] 12 个守卫全绿（Hypothesis + snapshot）
- [ ] drift 基线已重生，MDS/PFS 已 triage
- [ ] 高置信 semantic_drift/stale_doc 已登记进 ledger（带退出条件）
- [ ] 发现的真债只登记未改代码

---

## 相关文档

- `reference.md` — concept-registry/身份证/ledger 模板 + runner 脚本清单 + 首次落地样板
- `.codestable/semantics/README.md` — 环境+跑法+两条铁律（本 skill 的运行手册）
- `.codestable/semantics/` — 首次落地的完整产物，本 skill 的样板

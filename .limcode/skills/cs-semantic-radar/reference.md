# cs-semantic-radar 参考模板与脚本清单

## 产物布局

```
.codestable/semantics/
  concept-registry.yaml          # 概念身份证中心
  semantic-drift-ledger.md       # 漂移台账(SEM-NNNN)
  README.md                      # 环境+跑法+两条铁律(运行手册)
  requirements-semantic.txt      # hypothesis / syrupy / drift-analyzer(只进 .venv-semantic)
  concepts/{concept}.md          # 每个关键概念的身份证
  tests/conftest.py              # sys.path 注入 + hypothesis profile(放 tests/ 之外!)
  tests/test_*_properties.py     # Hypothesis 性质守卫
  tests/test_semantic_snapshots.py
  tests/__snapshots__/*.json     # snapshot 基线
  tools/snapshot_json.py         # 自写 py3.8-safe snapshot helper
  tools/check_concept_registry.py# 账本 vs 真代码一致性校验
  run_semantic_guards.py         # 守卫总控(用 .venv-semantic)
  run_drift_scan.py              # drift 扫描总控
evidence/SemanticDebt/
  drift/drift-baseline.{json,md} # gitignore 大 json,保留 md
  agent/drift-agent-brief.md     # triage 简报 + A∩B 交叉核验
  agent/drift-mds-blindspot.json # 盲区明细(_meta 是数字唯一真相源)
```

gitignore：`.venv-semantic/`、`**/__pycache__/`、`evidence/SemanticDebt/drift/drift-baseline.json`(4.9MB 大文件)。

## concept-registry.yaml 模板（单个概念）

```yaml
schema_version: 1
updated_at: "{YYYY-MM-DD}"
concepts:
  - id: {concept_id}
    canonical_name: {中文名}
    status: current
    owner_area: {领域}
    definition: >
      {一句话规范定义}
    allowed_values:
      "{value}":           # ⚠️ off/on/yes/no 裸键会被 YAML 当布尔，必须加引号
        user_label: {中文标签}
        ...
    failure_policy:
      missing_value: {缺失怎么办}
      unknown_value: {未知怎么办——raise 还是容忍}
    canonical_resolver:
      {唯一收口点 file::symbol}
    source_of_truth:
      - {真理之源文件}
    stale_or_historical_sources:
      - {已过期来源 # 关联 ledger SEM-NNNN}
    forbidden_meanings:
      - "{禁止的理解，尤其'别新建第N套实现'}"
```

## semantic-drift-ledger.md 条目模板

```markdown
## SEM-NNNN {标题}（{stale_doc/semantic_drift/...}）
- 状态: open
- 严重度: {medium/high/low}
- 概念: [{concept}](concepts/{concept}.md)
- 发现来源: {人工 / drift {信号} / A∩B}
### 漂移证据(逐行核验)
- {旧口径 file:line 原文}
- {当前事实 file:line 原文}
### 风险 / 处理建议(只登记) / 退出条件
```

## runner 脚本要点

- `run_semantic_guards.py`：定位 `.venv-semantic/bin/python` → `pytest .codestable/semantics/tests/`；缺环境给重建命令；`HYPOTHESIS_PROFILE` 默认 semantic_fast。
- `run_drift_scan.py`：`.venv-semantic/bin/drift analyze --repo . --format json --progress none -o evidence/.../drift-baseline.json`；exit 0/1 都算成功（1=有 findings）；再出 markdown。
- `check_concept_registry.py`：读 yaml + import 真模块，比对 plan_role 值集/标签、graph choices；不一致 exit 1。3.8/3.14 都能跑（只依赖 PyYAML + 项目代码）。
- `snapshot_json.py`：normalize（排序+易变键占位）→ `APS_UPDATE_SEMANTIC_SNAPSHOTS=1` 写基线否则断言；缺 snapshot 一律失败（不静默通过）。

## drift triage 6 类裁定

consistent / pure_refactor_debt / naming_debt / stale_doc / semantic_drift / insufficient_evidence。
只 semantic_drift（高置信）+ stale_doc 进 ledger；其余进 backlog 或不动。

## 样板

`.codestable/semantics/` 整套 = 2026-06 首次落地产物，本 skill 的活样板。

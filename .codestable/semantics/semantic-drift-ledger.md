# 语义漂移债务台账

> 每条 = 一个被工具发现、经证据确认的语义漂移。状态 open 的旧债允许存在(已登记)，
> 门禁阶段只阻断**新增**高置信 semantic_drift / user_visible_leak。

---

## SEM-0001 graph_analysis_mode：ADR-0012 旧口径与当前行为冲突(stale_doc)

- **状态**: open
- **类型**: stale_doc
- **严重度**: medium
- **概念**: [graph_analysis_mode](concepts/graph-analysis-mode.md)
- **发现来源**: 人工 + drift DIA 信号佐证 + 本次基线核验

### 漂移证据(逐行核验)
- 旧口径 `开发文档/ADR/0012-networkx-graph-foundation-boundary.md:16`：
  > 当前 `report/on` 只保存配置，不执行图分析，不改变排产结果。
- 旧口径同文件 `:26`：
  > UI 必须向用户明确说明：当前 `report/on` 不会执行图分析，也不会改变排产结果。
- 当前事实 `.codestable/architecture/ARCHITECTURE.md:78`：
  > `graph_analysis_mode=on` 当前已经接入 PR-5 ready 队列和 PR-6 图评分……候选方案链路已经接入 3/5/7 档权重试跑、自动选择、候选落库和代表三方案页面切换。
- 当前默认值 `core/services/scheduler/config/config_snapshot.py:43`：`graph_analysis_mode: str = "on"`。

### 风险
- 后续 LLM/人按 ADR-0012 旧口径理解，会误以为 `on` 不改变排产结果，从而在改图相关代码时做出错误假设。
- 人工排障时可能据旧 ADR 误判。

### 处理建议(非本次执行范围，仅登记)
1. 给 ADR-0012 加 `superseded_by: .codestable/architecture/ARCHITECTURE.md#6-排产工序图分析现状` 头，标历史状态(不删，留作决策考古)。
2. concept-registry.yaml 已固化当前口径(本次已做)。
3. 后续可加 `scan_doc_code_drift.py` 把"report/on 不改变排产结果"列为禁止短语。

### 退出条件
- ADR-0012 被标历史/superseded。
- 文档不再出现"on 不改变排产结果"的现行陈述。

---

## SEM-LB-NOTE drift-analyzer 把承重双实现误报为"可删重复"(工具口径，非新债)

- **状态**: noted(纪律提醒，非待办债)
- **类型**: tool_calibration
- **概念**: [fallback_degradation] / 见主审计 §90 LB-B1

### 内容
drift-analyzer 的 `MDS`(Exact duplicates)在 `core/services/common/normalization_matrix.py:138 _merge_aliases` 命中，related 指向 `core/shared/boolean_normalize.py`，建议"删重复"。
**但这正是主审计 §90 LB-B1 的承重双实现**：`boolean_normalize` 被 core.models/core.algorithms 下层引用，删它改指 services 会撞分层红线(产生 core.models→core.services 越层)。

### 纪律
任何针对 normalization 重复的"消重"PR，必须先读 §90 LB-B1 与本条；正确方向是让上层 matrix **反向 delegate** 到下层 boolean_normalize，而非相反。这是 drift 结果**必须过 Agent 语义法医、不能直接修**的活样本。

---

## 待 Agent 分类队列

见 `evidence/SemanticDebt/agent/drift-agent-brief.md`：1606 条 drift findings 已按信号分布 + A∩B 交叉核验整理；
MDS/PFS 高分近似重复 top 15 待逐条判 consistent / refactor_debt / naming_debt / stale_doc / semantic_drift。

---

## 扫描日志（增量核验，不是新债）

> 每条 = 一次"在旧基线上做了改动后，有没有长出新漂移"的复查留痕。结论为"无新债"时也记，作为回归证据。

### 2026-06-23 增量扫描：基线 `4d71856a`(6/9) → HEAD，结论 **无新增语义漂移债**

- **改动规模**：210 文件 +6779/−2407，大头在 `web/viewmodels`(dashboard 驾驶舱/工作台重构、甘特负荷条、plan_context_capsule)与 `web/routes`(`system_ui_mode.py` 删除＝双 UI 退役)。
- **守卫层**：15 个语义守卫全绿；`check_concept_registry.py` 账本与真代码一致(plan_role / graph_analysis_mode / result_status / strategy)。A∩B 复核：`VALID_PLAN_ROLES`/`PLAN_ROLE_LABELS` 唯一字源未破(命中全为消费点)；graph 默认值未分叉；新文件 `core/services/report/report_degradation.py` delegate 到收口 `core.services.common.degradation`，非第二套降级语义。
- **结构层(drift delta)**：Drift Score 稳 0.5；AI 归因 5%→4%↓；概念分叉信号全持平或降——MDS 27→23↓、SMS 14→12↓、PFS/NBV/DIA 持平。28 条"新增 key"中 PFS 20 条＝重构 churn(模块级聚合指标随 dashboard 拆分挪位，净值不变、不碰领域概念)，SMS 6 条＝新文件首次 import(`__future__`/openpyxl/flask)噪音。
- **法医层(唯一净新增信号 ECM exception_contract_drift 0→2)**：
  - `core/services/report/exporters/xlsx.py`：3 个导出函数**删除了 `except Exception: pass`** 静默吞错 → 异常如实上抛。
  - `web/routes/system_backup.py`(commit `cd95b8b0`)：`os.remove`→`remove_fixed_file(allow_symlink=False)`，异常拆成显式 `FileNotFoundError`/`UnsafeFixedFileError`/`OSError`；`backup_create` 新增「完整性检查失败 loud 不静默」「磁盘满给具体提示、ProgrammingError 必须 loud 透 500」分支。
  - **判定 `consistent`**：ECM 仅机械检测到异常 profile 形状变化，实质是降级诚实灵魂线被**加固**，方向与漂移相反。**不登记为债**。
- **运维副产(非语义)**：仓库从 `~/Documents/GitHub` 搬到 `~/GitHub` 后，`.venv-semantic/bin/drift` 控制台脚本 shebang 写死旧绝对路径 → exec FileNotFoundError 静默失效；已将 `run_drift_scan.py` 改走 `python -m drift`(对搬迁免疫)并验证跑通。

---
name: aps-deep-review
description: 深度代码审查：引用链追踪、跨层边界检查、影响面评估、回归风险分析。适用于重要改动、跨模块影响面分析、合并前深审、Schema 或公开 Service 签名变更等场景；普通代码审查优先使用 `requesting-code-review`。
---

# APS 深度代码审查

## 与其他检查 skill 的区别

| Skill | 深度 | 方法 | 适用场景 |
|-------|------|------|---------|
| `aps-post-change-check` | 浅层 | 正则模式匹配 | 每次改完快速扫一眼 |
| `aps-arch-audit` | 中层 | 全项目正则扫描 | 定期架构体检 |
| **`aps-deep-review`（本 Skill）** | **深层** | **AST 提取定义 + 文本搜索调用点（启发式） + Agent 语义分析** | **重要改动、排查故障、合并前审查** |

## Quick start

```bash
# Step 1: 运行引用链追踪脚本（自动化部分）
python .limcode/skills/aps-deep-review/scripts/reference_tracer.py

# 也可以以某个 base revision 为起点分析（常用：最近一次提交）
python .limcode/skills/aps-deep-review/scripts/reference_tracer.py --commit HEAD~1

# 也可以分析指定文件
python .limcode/skills/aps-deep-review/scripts/reference_tracer.py --file core/services/scheduler/batch_service.py
```

> 说明：`reference_tracer.py` 的“调用点”来自文本匹配（非完整调用图），请把输出当作审查线索并回到源码核对。

```bash
# Step 2: Agent 按照下面 5 个阶段，逐项完成深度审查（人工智能部分）
```

## 适用场景（触发词）

- 用户提到：**深度 review / 深度审查 / 引用链检查 / 影响面分析 / 这个改动安全吗 / 合并前检查 / 改了XXX会不会影响YYY / 跨模块影响面 / 公开 Service 签名变更 / Schema 变更复核**
- 建议：每次涉及 Service 公开方法签名变更、Schema 变更、跨模块改动时必须运行

## 落盘约定

- 默认把深审结论写入：`.limcode/review/YYYY-MM-DD_<主题>_review.md`
- `audit/YYYY-MM/` 只用于“取舍型审阅报告 / 排期建议 / 审计归档”

换句话说：

- **深审主结果** → `.limcode/review/`
- **取舍型审阅报告** → `audit/`

## 子代理模型约束

涉及子代理协作式深度审查时，统一遵循 `.limcode/skills/_shared/subagent-compat.md`，并执行本技能的更强约束：

- 主代理只做 leader / coordinator，尽量把可并行的审查任务拆给子代理，自己负责汇总、去重、交叉验证和最终判断。
- 所有深度审查、独立审核、对抗审核子代理必须使用 `gpt-5.5`，reasoning effort 必须使用 `xhigh`。
- 如果宿主通用子代理工具支持显式模型字段，调度时必须传入 `model: "gpt-5.5"` 与 `reasoning_effort: "xhigh"`。
- 如果当前宿主只能使用 LimCode 原生子代理，则必须确认对应 `limcode.toolsConfig.subagents` 渠道已经绑定等价 GPT-5.5 / xhigh 能力；不能确认时，在审查结论中标注“模型能力证据不足”。
- 如果当前宿主无法提供 GPT-5.5 / xhigh，禁止静默降级；必须明确说明实际限制，并把该限制纳入审查可信度评估。

## 五阶段深度审查方法论

### Phase 1: 变更影响图谱（自动化 + Agent）

**目标**：搞清楚"改了什么"和"谁受影响"。

**执行步骤**：

1. 运行引用链追踪脚本：
   ```bash
   python .limcode/skills/aps-deep-review/scripts/reference_tracer.py
   ```
2. 阅读输出报告 `evidence/DeepReview/reference_trace.md`，重点关注：
   - 每个变更函数有多少**调用者**（调用者越多，影响面越大）
   - 是否有**跨层边界风险**（报告会标 ⚠）
   - 是否有**无外部调用者**的公开方法（可能是死代码）

3. Agent 补充脚本无法覆盖的分析：
   - 对每个变更函数，用 `rg`（ripgrep）或 IDE 全局搜索其在 **模板文件**（`templates/`）中的引用
   - 对每个变更函数，用 `rg`（ripgrep）或 IDE 全局搜索其在 **测试文件**（`tests/`）中的引用
   - 绘制影响面总结表：

   ```markdown
   | 变更函数 | 调用者数 | 涉及层 | 模板引用 | 测试覆盖 | 风险 |
   |---------|---------|--------|---------|---------|------|
   | BatchService.create() | 3 | Route+Service | batches.html | smoke_phase3 | 中 |
   ```

### Phase 2: 引用链逐条深审（Agent 核心工作）

**目标**：沿着每条引用链，从调用者追到被调用者，检查**每个边界**是否一致。

**对每个变更函数的每个调用者，逐条检查**：

1. **参数一致性**：
   - 调用者传的参数类型是否匹配函数签名？
   - 如果函数新增了参数（即使有默认值），所有调用者的语义是否仍然正确？
   - 如果参数类型从 `str` 改为 `int`，所有调用者是否做了转换？

2. **返回值处理**：
   - 函数返回 `Optional[X]` → 调用者是否处理了 `None` 的情况？
   - 函数返回 `List[X]` → 调用者是否处理了空列表的情况？
   - 函数的返回结构变了（比如 dict 多了/少了字段）→ 调用者是否使用了受影响的字段？

3. **异常传播**：
   - 函数新增了可能抛出的异常类型 → 调用者是否能正确处理？
   - 如果是 Route 层调用 Service，异常通常由全局 errorhandler 处理，确认 errorhandler 能覆盖。

4. **事务边界**：
   - 数据修改操作是否在事务内？
   - 调用链中有没有"Service A 在事务中调用 Service B，但 B 内部又开了新事务"的嵌套事务问题？

**输出格式**：
```markdown
#### 引用链：scheduler_batches.py:23 → BatchService.create()
- [x] 参数一致性：route 传 Batch 对象，签名匹配
- [x] 返回值处理：route 使用返回的 Batch 做 flash，正确
- [ ] ⚠ 异常传播：create() 可能抛 DUPLICATE_ENTRY，但 route 没有单独处理重复提示
- [x] 事务边界：create() 内部使用 tx_manager
```

### Phase 3: 数据流追踪（Agent）

**目标**：追踪数据从用户输入到数据库存储的完整流动路径，检查每一步的转换是否正确。

**选择涉及数据修改的变更函数，追踪以下路径**：

```
用户输入 (form/JSON) 
  → Route 参数解析 (request.form.get / request.json)
    → Service 业务处理 (验证、转换、计算)
      → Repository SQL 执行 (参数化查询)
        → Database 存储
```

**逐步检查**：

1. **Route → Service 边界**：
   - `request.form.get()` 返回的是 `Optional[str]`，Service 期望什么类型？
   - 是否有 `.strip()` 去空格？
   - 数字字段是否做了 `int()` / `float()` 转换？转换失败时是否有 catch？

2. **Service → Repository 边界**：
   - Service 传给 Repository 的数据类型是否与 SQL `?` 占位符匹配？
   - `UPDATE` 操作的 `allowed` 白名单是否包含了所有应该可更新的字段？
   - 新增的字段是否在 `INSERT` 语句中？

3. **Repository → Database 边界**：
   - SQL 的字段顺序是否与 `VALUES (?, ?, ...)` 的参数顺序一致？
   - `from_row()` 是否能正确解析 SELECT 返回的所有列？
   - 新增的数据库字段是否在 `schema.sql` 中定义？

### Phase 4: 边界条件与回归风险（Agent）

**目标**：识别变更可能引入的边界条件 bug 和回归风险。

**对每个变更函数，检查以下场景**：

1. **空值穿透**：
   - 函数的所有输入参数，逐一假设为 `None`，代码是否能正确处理？
   - 数据库查询结果为空时，后续逻辑是否会 NoneType error？

2. **类型不匹配**：
   - 前端可能传来的非预期类型（如数字字段传了带逗号的字符串 `"1,000"`）
   - SQLite 弱类型导致的问题（如 `INTEGER` 字段存了 `"123"` 字符串）

3. **并发安全**：
   - 快速双击提交：是否会创建重复记录？
   - 排产执行中的并发保护（`threading.Lock`）是否覆盖了变更代码？

4. **回归测试覆盖**：
   - 用 `rg`（ripgrep）或 IDE 全局搜索 `tests/` 目录，找到覆盖变更函数的测试文件
   - 评估现有测试是否覆盖了变更的逻辑分支
   - 列出需要新增或修改的测试用例

**输出格式**：
```markdown
## 回归风险评估

| 风险项 | 严重度 | 现有测试覆盖 | 建议 |
|--------|--------|-------------|------|
| batch.quantity 为 0 时排产结果 | 高 | smoke_phase3 未覆盖 | 新增边界测试 |
| 重复 batch_id 创建 | 中 | DB 唯一约束保护 | 已有保护，可接受 |
```

### Phase 5: 审查结论与行动项（Agent）

**目标**：汇总所有发现，给出结论和建议。

**输出模板**：

```markdown
# 深度审查结论

## 变更概要
- 变更文件：N 个
- 变更函数/方法：N 个
- 影响调用者：N 处

## 引用链完整性
- [x] 所有调用者的参数传递正确
- [ ] ⚠ scheduler_batches.py:23 未处理 DUPLICATE_ENTRY 异常
- [x] 所有返回值处理正确

## 跨层边界一致性
- [x] Route → Service 参数类型匹配
- [x] Service → Repository 数据类型匹配
- [ ] ⚠ schedule_repo.py 的 INSERT 缺少 new_field 字段

## 边界条件
- [x] None 输入已处理
- [x] 空列表已处理
- [ ] ⚠ quantity=0 的情况未处理

## 回归风险
- 高风险：N 项
- 中风险：N 项
- 建议补充测试：（列出具体用例）

## 行动项
1. 修复：XXX
2. 补充测试：XXX
3. 确认无需改动：XXX
```

## 约束

- Phase 1 的脚本部分是自动化的，Phase 2-5 需要 Agent 主动读代码、分析、判断。
- Agent 在做引用链深审时，**必须实际读取每个调用者的代码上下文**（至少 ±10 行），不能仅凭函数名猜测。
- 如果发现问题，列出来让用户决定是否修复，不要自动修改（除非用户明确要求）。
- 对于大型变更（超过 5 个文件），可以只深审**公开方法**和**跨层调用**，私有方法做快速扫描。

## 审阅报告归档（audit/，LLM）

当用户要求“审计/留痕/评估要不要改、改哪些更值”，或深度审查发现 **P0/P1 风险** 时，Agent 需要基于以下证据生成一份“取舍型审阅报告”，并写入仓库根目录一级目录 `audit/`，用于后续审计与排期。

- **目录**：`audit/YYYY-MM/`
- **文件命名**：`YYYYMMDD_HHMM_deep_review.md`
- **建议证据清单**：
  - `evidence/DeepReview/reference_trace.md`
  - 本次变更文件列表（`git diff --name-only`）
  - 关键调用链上下文（只截取必要片段，避免塞满原始日志）

**强制规则（防止幻觉/跑偏）**：

- 只基于证据做判断；每条“风险/结论”必须能定位到证据文件与片段。
- 把 **事实** / **判断** / **建议** 分开写；不得把建议写成事实。
- 报告只给行动建议，不自动修改代码（除非用户明确要求）。

**审阅报告模板（建议）**：

```markdown
# 深度审查审阅报告（LLM）

- 时间：YYYY-MM-DD HH:MM
- 证据：
  - evidence/DeepReview/reference_trace.md
  - （其他）

## 事实摘要（来自证据）
- 变更文件：...
- 公开方法变更：...
- 跨层边界风险：...

## 结论与取舍（LLM）

### 必须改（P0/P1）
- [ ] <问题>（证据：...）| 建议：... | 成本：S/M/L | 回归风险：低/中/高

### 建议改（P2）
- [ ] ...

### 不建议改 / 暂缓
- [x] ...（原因：误报/ROI 低/需更大重构才值）

## 行动项
- [ ] ...
```

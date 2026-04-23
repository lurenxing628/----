## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [ ] 确定静默回退的统计口径、可观测性等级和风险分级  `#phase-0-rules`
- [ ] 全量扫描 core/ 中的候选回退点并按层级建立候选清单  `#phase-1-scan`
- [ ] 精读 algorithms/infrastructure/plugins 热点文件并确认方法级与实现点级记录  `#phase-2-review-algo-infra`
- [ ] 精读 models/services/common 与其余 services 目录并完成分类去重  `#phase-3-review-services`
- [ ] 生成正式 Markdown 审计报告，包含汇总表、热点表、方法级表和实现点级表  `#phase-4-write-report`
<!-- LIMCODE_TODO_LIST_END -->

# core/ 静默回退审计与明细 MD 输出计划

## 1. 任务目标

围绕 `core/` 目录，系统研究并回答下面 4 个问题：

1. **到底有多少“静默回退”的方法/函数？**
2. **到底有多少“静默回退”的实现点/分支？**
3. **这些回退分别分布在哪些层、哪些文件、哪些方法中？**
4. **这些回退是“完全静默”“弱可观测”还是“显式可观测降级”？它们的业务风险分别是什么？**

本次交付目标不是改代码，而是输出一份**足够详细、可追溯、可复核**的 Markdown 审计文档，建议后续落地到：

- `audit/2026-03/20260331_core_静默回退审计.md`

---

## 2. 预扫描基线（已完成的前置盘点）

基于当前工作区的初步扫描，已经得到以下基线：

- `core/` 范围内约 **160 个文件 / 19 个目录**
- 仅按宽口径正则扫描 `except Exception...`，已发现 **324 处**广义异常吞并/兜底捕获点
- 以 `回退 / 兜底 / 降级 / 不阻断 / 已忽略 / 默认 / 跳过` 等关键词检索，已发现 **177 处**显式回退语义标记
- 初步高热点文件包括：
  - `core/algorithms/greedy/dispatch/sgs.py`
  - `core/infrastructure/database.py`
  - `core/infrastructure/backup.py`
  - `core/plugins/manager.py`
  - `core/infrastructure/logging.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `core/services/common/enum_normalizers.py`
  - `core/models/_helpers.py`
  - `core/services/scheduler/gantt_tasks.py`
  - `core/services/scheduler/freeze_window.py`

这些基线**不是最终结论**，但足以说明：`core/` 中存在大量“异常后回退/降级/默认值替代/吞并错误继续运行”的实现，需要按层和按方法详细拆账。

---

## 3. 审计口径：什么算“静默回退”

为了避免最后的统计口径混乱，正式报告会先声明并固定如下定义。

### 3.1 计数单位

正式报告会同时给出两种统计口径：

- **方法数**：包含至少 1 个回退实现点的函数/方法数量
- **实现点数**：具体的回退分支/回退语句数量

说明：

- 同一个方法里如果出现 3 个不同的 `except -> return default`，则：
  - 方法数记 **1**
  - 实现点数记 **3**
- 这样才能同时回答用户关心的“写了多少方法”和“写了多少实现”。

### 3.2 认定为“回退/降级”的情形

以下情形纳入统计：

1. **异常吞并后返回默认值**
   - 例如：`except Exception: return None / False / 0 / default`
2. **异常吞并后直接跳过**
   - 例如：`except Exception: continue / pass`
3. **输入非法时改用保守默认值**
   - 例如：非法枚举回落到 `normal/no/internal/active`
4. **可选能力失败后降级主流程**
   - 例如：OR-Tools 失败后回到 greedy；插件失败后禁用该插件；停机约束失败后忽略停机约束
5. **后端/依赖不可用时切换到备选实现**
   - 例如：pandas backend 失败后回退 openpyxl
6. **非关键副作用失败后不阻断主流程**
   - 例如：日志写入失败、telemetry 写入失败、清理动作失败但主流程继续

### 3.3 不纳入“静默回退”主统计、但会在附录说明的情形

以下情形会从“主表”中剔除，或在附录中单列，不与真正的静默回退混算：

1. **显式抛出业务异常/校验异常**
   - 如 `raise ValidationError/BusinessError/AppError`
2. **纯正常默认值，不是异常路径**
   - 如参数默认值、页面默认筛选值
3. **仅为资源释放的 best-effort 清理**，且对业务语义影响极低
   - 例如 `handler.close()`/`wb.close()` 失败时 `pass`
   - 这类仍会保留在附录或“低风险清理类回退”分类中，但不应与业务规则降级等量齐观

### 3.4 可观测性分级

最终报告会把每个实现点按可观测性分成三档：

- **A. 完全静默**
  - 既不抛异常，也不记录 warning/error，也不把 warning 返回给上层
  - 典型形式：`except Exception: return default/pass/continue`
- **B. 弱可观测**
  - 不抛异常，但会通过 `warnings.append(...)`、状态字段、返回码等方式暴露
  - 调用方若不查看返回体，仍然容易忽略
- **C. 显式可观测降级**
  - 不抛异常，但会写 `logger.warning/error` 或明确写审计日志
  - 这类属于“非阻断降级”，不是严格意义的“纯静默”，但必须纳入总账并单独分类

### 3.5 风险等级

每条回退还会附带风险等级：

- **高风险**：可能影响排产正确性、资源约束、工序顺序、数据一致性
- **中风险**：可能影响配置生效、功能开关、导入结果、可视化结果
- **低风险**：主要影响日志、清理、缓存、观测性，不太改变业务结果

---

## 4. 分阶段实施方案

本任务会按“先定口径、再全量扫描、再逐层精读、再汇总成表”的方式推进。

### 阶段 0：建立审计规则与输出模板

**目标**：先把“什么算静默回退、怎么计数、怎么分级、怎么落表”固定下来，避免后续越审越乱。

**执行内容**：

- 固定“方法数 / 实现点数 / 文件数”三种口径
- 固定“完全静默 / 弱可观测 / 显式可观测降级”分级标准
- 固定“高 / 中 / 低风险”打标标准
- 固定最终 Markdown 报告的章节结构与表头字段

**阶段产物**：

- 统一口径说明
- 明细表模板
- 汇总表模板

---

### 阶段 1：全量候选扫描与初步分桶

**目标**：先把 `core/` 所有疑似回退点“兜一遍”，形成候选清单。

**扫描规则**：

1. 广义异常吞并：
   - `except Exception`
   - `except:`（若存在）
2. 典型回退行为：
   - `return default / None / False / 0 / [] / {}`
   - `continue`
   - `pass`
3. 显式语义词：
   - `回退 / 兜底 / 降级 / 不阻断 / 已忽略 / 默认 / 跳过`
4. 可选依赖/备选实现：
   - backend/provider/plugin/ortools 等失败后切换路径

**本阶段的输出不是最终结论**，而是形成一个“候选总表”，再进入人工复核。

**阶段产物**：

- 按文件整理的候选点总表
- 初步热点文件排序
- 初步按目录分桶（algorithms / infrastructure / models / services / plugins）

---

### 阶段 2：算法层精读（`core/algorithms/**`）

**重点原因**：算法层的回退最容易影响“排产正确性”而又不一定直接报错，是高风险区。

**重点关注文件**：

- `core/algorithms/greedy/dispatch/sgs.py`
- `core/algorithms/greedy/scheduler.py`
- `core/algorithms/greedy/schedule_params.py`
- `core/algorithms/greedy/seed.py`
- `core/algorithms/greedy/auto_assign.py`
- `core/algorithms/dispatch_rules.py`
- `core/algorithms/priority_constants.py`
- `core/algorithms/sort_strategies.py`
- `core/algorithms/ortools_bottleneck.py`
- `core/algorithms/greedy/config_adapter.py`
- `core/algorithms/greedy/date_parsers.py`

**重点审计模式**：

- 非法数值回退为 `0 / 1.0 / avg_proc_hours / normal`
- 评分失败时退化为“最差但可比较”的 key
- 缺资源时降级为不可估算候选而非阻断
- OR-Tools 缺失/失败时直接回到主流程
- 策略、派工规则、权重参数非法时回退默认值

**预期高风险样本**：

- `sgs.py` 中评分/估算阶段的大量 try/except 与惩罚 key 退化
- `schedule_params.py` 中策略/规则/开关的默认回退
- `ortools_bottleneck.py` 中“失败即降级为 None”的可选能力路径

**阶段产物**：

- 算法层方法级清单
- 算法层实现点级清单
- 算法层高风险 TOP 明细

---

### 阶段 3：基础设施层与插件层精读（`core/infrastructure/**`、`core/plugins/**`）

**重点原因**：这部分代码会大量出现“best effort”，其中有些是合理兜底，有些会遮蔽真实异常，必须与业务层回退区分开。

**重点关注文件**：

- `core/infrastructure/database.py`
- `core/infrastructure/backup.py`
- `core/infrastructure/transaction.py`
- `core/infrastructure/logging.py`
- `core/infrastructure/migrations/*.py`
- `core/infrastructure/errors.py`
- `core/plugins/manager.py`
- `core/plugins/runtime.py`

**重点审计模式**：

- 数据库迁移/恢复/回滚时的 best-effort 清理与 fallback_log
- 维护锁、文件句柄、sidecar 删除失败后的吞并
- 日志写入失败后不阻断业务
- 插件路径非法/加载失败/注册失败时的跳过与禁用
- 配置获取失败后回落默认启用状态

**特别说明**：

这部分会区分两类回退：

1. **安全性导向的保护性回退**：例如迁移失败后从备份恢复、路径非法直接跳过
2. **观测性压制型回退**：例如 logger 再次失败时 `pass`，可能让真正问题更难定位

**阶段产物**：

- 基础设施层回退清单
- 插件层回退清单
- “业务安全型回退”与“静默吞并型回退”的分层结论

---

### 阶段 4：模型/通用服务层精读（`core/models/**`、`core/services/common/**`）

**重点原因**：这层决定“非法输入是报错还是默认吞掉”，对整套系统的风格影响很大。

**重点关注文件**：

- `core/models/_helpers.py`
- `core/services/common/enum_normalizers.py`
- `core/services/common/normalize.py`
- `core/services/common/excel_backend_factory.py`
- `core/services/common/excel_service.py`
- `core/services/common/excel_templates.py`
- `core/services/common/openpyxl_backend.py`
- `core/services/common/pandas_backend.py`
- `core/services/common/excel_validators.py`
- `core/services/common/datetime_normalize.py`

**重点审计模式**：

- `parse_int/parse_float/get` 这类通用 helper 的默认值吞并
- 枚举/状态值的自动规范化与未知值回退
- backend provider 调用失败后切到 openpyxl
- Excel 导出/预览/比较时的静默兜底
- NaN/空值/非法格式的处理策略

**阶段产物**：

- 通用 helper 的“静默回退方法数”统计
- 规范化器（normalizer）类回退的统一归类
- 低层通用函数对上层影响面的说明

---

### 阶段 5：业务服务层精读（`core/services/**` 其余目录）

**重点原因**：这部分直接影响导入、排产、甘特图、冻结窗口、资源池、工艺解析等业务行为。

**重点关注目录与典型文件**：

- `core/services/process/route_parser.py`
- `core/services/process/part_service.py`
- `core/services/scheduler/resource_pool_builder.py`
- `core/services/scheduler/freeze_window.py`
- `core/services/scheduler/gantt_tasks.py`
- `core/services/scheduler/gantt_service.py`
- `core/services/scheduler/schedule_service.py`
- `core/services/scheduler/schedule_optimizer_steps.py`
- `core/services/scheduler/schedule_optimizer.py`
- `core/services/scheduler/calendar_admin.py`
- `core/services/system/maintenance/*.py`
- 以及 `equipment / personnel / material / report` 下的容错实现

**重点审计模式**：

- 工艺路线未知工种默认外部、默认周期 1 天
- 零件创建后自动解析失败但不阻断创建
- 资源池/停机约束加载失败后降级为关闭或忽略
- 冻结窗口读取失败时降级为不冻结
- 甘特图构建异常时返回空数组，避免整页 500
- OR-Tools 高质量起点失败时已忽略并继续主流程
- 假期默认效率等配置读取失败时回退常量默认值

**阶段产物**：

- 业务服务层回退全表
- 高影响业务回退热点清单
- “结果正确性风险”专项说明

---

### 阶段 6：去重、复核、汇总成正式 Markdown

**目标**：把阶段 2~5 的结果统一去重、统一定义、统一格式，产出最终 MD 报告。

**去重规则**：

1. 同一实现点不能重复记账
2. 同一方法多个实现点要拆开统计，但方法数只算 1
3. 单纯 logger 二次失败的 `pass` 与业务回退要分列，避免污染主风险判断
4. `warnings.append(...)` 类需要与“完全静默”分开
5. `默认值` 如果是正常业务约定、非异常触发，不并入“静默回退主表”

**交叉复核规则**：

- “方法级统计”之和必须能回溯到“实现点明细”
- “目录级汇总”之和必须能回溯到“文件级汇总”
- 高风险条目必须带行号与证据片段
- 对热点文件至少做一次人工复核，不只靠关键字搜索

**最终产物**：

- 一份正式 Markdown 报告
- 至少 4 张主表 + 若干附表
- 每条记录可追到文件/方法/行号/证据/风险/建议

---

## 5. 最终 Markdown 报告结构设计

正式输出文件建议采用如下结构：

### 5.1 文档章节

1. **审计目标与范围**
2. **判定标准与统计口径**
3. **总体结论摘要**
4. **按层级统计总表**
5. **按类型统计总表**
6. **按可观测性统计总表**
7. **高风险热点文件 TOP 表**
8. **方法级明细表**
9. **实现点级明细表**
10. **结论与治理建议**
11. **附录：排除项与边界说明**

### 5.2 主汇总表（层级维度）

| 层级/阶段 | 文件数 | 方法数 | 实现点数 | 完全静默 | 弱可观测 | 显式可观测降级 | 高风险 | 中风险 | 低风险 | 代表文件 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|

### 5.3 类型汇总表（机制维度）

| 类型 | 判定规则 | 方法数 | 实现点数 | 常见动作 | 代表样例 |
|---|---|---:|---:|---|---|
| 异常吞并返回默认值 | except 后 return default/None/False/0 |  |  |  |  |
| 异常吞并跳过 | except 后 continue/pass |  |  |  |  |
| 非法输入回退默认枚举/状态 | unknown -> normal/no/internal/active |  |  |  |  |
| 可选能力降级 | OR-Tools/插件/backend 失败后回主链路 |  |  |  |  |
| 非关键副作用失败不阻断 | logger/telemetry/cleanup 失败但继续 |  |  |  |  |

### 5.4 高热点文件表

| 排名 | 文件 | 方法数 | 实现点数 | 主要回退模式 | 可观测性特征 | 风险说明 |
|---:|---|---:|---:|---|---|---|

### 5.5 方法级明细表

| 序号 | 层级 | 文件 | 方法/函数 | 行号范围 | 回退实现点数 | 可观测性主类型 | 风险等级 | 说明 |
|---:|---|---|---|---|---:|---|---|---|

### 5.6 实现点级明细表（核心表）

| 序号 | 层级 | 文件 | 方法/函数 | 行号 | 触发条件 | 回退动作 | 返回/影响 | 可观测性 | 风险 | 证据片段 | 建议 |
|---:|---|---|---|---|---|---|---|---|---|---|---|

> 这是最终最关键的一张表。每一行必须能让读者直接看懂：**什么异常/异常输入发生了、代码如何处理、为什么这是静默回退、会影响什么。**

---

## 6. 重点审计样例（基于当前预读，后续会写入正式报告）

以下是已经确认存在代表性回退模式的样例方向，正式报告中会展开：

1. **`core/models/_helpers.py`**
   - `get / parse_int / parse_float`：大量默认值回退，不抛异常
   - 典型特征：完全静默、低层基础函数、影响面广

2. **`core/services/common/enum_normalizers.py`**
   - 未知值回到 `active/internal/no/default` 或原样透传
   - 典型特征：输入标准化型回退，部分是业务约定，部分可能掩盖脏数据

3. **`core/algorithms/greedy/schedule_params.py`**
   - 非法策略/派工规则/自动分配开关回退默认值
   - 典型特征：弱可观测（warnings），会影响排产参数实际生效口径

4. **`core/algorithms/greedy/dispatch/sgs.py`**
   - 评分失败、资源缺失、工时非法、效率异常时大面积退化到保守 key / 默认值
   - 典型特征：高风险、业务结果敏感、回退点密集

5. **`core/infrastructure/database.py` / `backup.py`**
   - 大量 best-effort 清理/关闭/回滚/重试/默认路径回退
   - 典型特征：偏“保护系统存活”的降级，需与业务层静默回退区分

6. **`core/plugins/manager.py`**
   - 插件路径异常、commit 失败、注册失败、logger 再失败均可能吞并
   - 典型特征：插件可用性降级 + 局部观测压制

7. **`core/services/scheduler/resource_pool_builder.py`**
   - 资源池构建失败 -> 自动分配关闭
   - 停机区间加载失败 -> 忽略停机约束
   - 典型特征：显式可观测降级，但对排产结果可能有实际影响

8. **`core/services/scheduler/freeze_window.py` / `gantt_tasks.py`**
   - 冻结窗口失败 -> 不冻结
   - 甘特图日历构建失败 -> 空数组
   - 典型特征：功能可用性优先，正确性或展示完整性次之

9. **`core/services/process/route_parser.py` / `part_service.py`**
   - 未知工种默认外部、默认周期 1 天
   - 自动解析失败不阻断零件创建
   - 典型特征：业务默认值会改变后续排产语义，需重点标红

---

## 7. 完成标准（验收口径）

正式报告完成时，至少要满足以下标准：

1. **有总数**
   - `core/` 中静默回退方法数、实现点数、目录级分布都明确给出
2. **有定义**
   - 报告开头明确“什么被算入、什么被排除”
3. **有证据**
   - 每条高风险记录必须带文件、方法、行号、证据片段
4. **有分层**
   - 至少按 algorithms / infrastructure / models+common / services / plugins 分层
5. **有风险判断**
   - 每条记录要标风险等级，且给出简要原因
6. **有可观测性判断**
   - 区分完全静默、弱可观测、显式可观测降级
7. **有可行动建议**
   - 对高风险热点给出治理建议，例如：改为显式告警、缩小 except 范围、补 telemetry、改为 fail-fast、补单测等

---

## 8. 本次计划的边界

- **本计划阶段不修改业务代码**
- **本计划阶段只为后续生成正式审计 MD 做准备**
- 正式执行后，输出物将是详细审计文档，而不是代码修复 PR

---

## 9. 推荐后续执行顺序

建议获批后按以下顺序真正落地：

1. 先出“汇总统计 + 热点文件 TOP 表”
2. 再补“方法级明细表”
3. 最后补“实现点级核心大表”与治理建议

这样即使中途需要分批交付，也能先给用户看到全局数量，再逐步下钻到每个方法和实现点。

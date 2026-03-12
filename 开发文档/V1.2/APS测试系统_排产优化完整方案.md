# APS测试系统 - 排产优化完整方案

## 文档信息
- **版本**: v1.3.0（修订拆分准备版）
- **日期**: 2026-03-12
- **适用范围**: APS测试系统 v2.0+
- **目标环境**: Windows 7 SP1 x64 + Python 3.8.10（单机无网）

### 版本跟踪策略

本文档为总览，同时承担索引角色。以下 8 个专题文档与本文共享统一版本号：

| 专题文档 | 来源章节 | 说明 |
|----------|---------|------|
| [排产优化_现状与问题诊断.md](排产优化_现状与问题诊断.md) | 第 2 章 | v1.x 现状诊断 |
| [排产优化_目标与验收标准.md](排产优化_目标与验收标准.md) | 第 3 章 | 分层目标与验收 |
| [排产优化_技术架构.md](排产优化_技术架构.md) | 第 4 章 | 引擎架构与约束边界 |
| [排产优化_数据模型与实例构建.md](排产优化_数据模型与实例构建.md) | 第 5 章 | 数据模型与实例 |
| [排产优化_核心算法.md](排产优化_核心算法.md) | 第 6 章 | 解码器与搜索算法 |
| [排产优化_Win7交付与部署.md](排产优化_Win7交付与部署.md) | 第 7+11 章 | Win7 交付与运维 |
| [排产优化_测试验证方案.md](排产优化_测试验证方案.md) | 第 9 章 | 测试策略与断言 |
| [排产优化_风险与降级.md](排产优化_风险与降级.md) | 第 10 章 | 风险与降级策略 |

- **统一版本号**：任一专题有实质性修改，统一递增主版本号并在本文 12.4 版本历史中记录。
- **每个专题文档头部**标注"归属版本"和"最后修改日期"，不独立维护版本历史。

### 交叉引用规则

- **引用格式**：`详见 [排产优化_核心算法](排产优化_核心算法.md#6-1-双解码器)`，使用相对路径 + 锚点。
- **引用方向**：专题之间允许平级引用，但鼓励通过本总览跳转以降低耦合。
- **引用到根目录文档**：`参见 [系统速查表](../系统速查表.md#db-字段)`。
- **引用检查**：每次修改后搜索确认指向该章节的引用未断裂。

---

## 目录

1. [项目概述](#1-项目概述)
2. [专题导航](#2-专题导航)
3. [实施路线图](#3-实施路线图)
4. [附录](#4-附录)

---

## 1. 项目概述

### 1.1 项目背景

APS测试系统是一款面向中小型制造企业的单机版排产软件，运行在Windows 7环境下。系统需要处理双资源约束（设备+人员）的作业车间调度问题，支持内外部工序混合、紧急插单等复杂场景。

### 1.2 当前系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      APS测试系统 v1.0                        │
├─────────────────────────────────────────────────────────────┤
│  第一层: 多策略排序（优先级/交期/权重/FIFO）                  │
│  第二层: 双资源约束贪心算法（Serial SGS）                     │
│  第三层: 简单局部搜索（improve模式）                          │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 核心挑战

| 挑战 | 描述 | 影响 |
|------|------|------|
| 双资源约束 | 设备和工人双重约束，互相锁死 | 解空间爆炸 |
| Win7限制 | 无法使用现代C++库（OR-Tools） | 算法选择受限 |
| 单机稳态 | 目标机以单机运行为主，默认单线程可复现 | 必须先保证单线程稳定，再评估可控并行 |
| 实时响应 | 车间操作员不能等待 | 算法必须在秒内完成 |
| 插单扰动 | 紧急订单导致全局重排 | 调度神经质 |

### 1.4 现状实现边界（v1.x）与 v2.0 规划状态（本版冻结）

为避免评审把"设计目标"误读为"已上线能力"，本版先冻结现状与规划边界：

| 主题 | v1.x 现状（已实现，可验收） | v2.0 规划（未落地） | 证据锚点 |
|------|------------------------------|----------------------|----------|
| 算法内核 | `GreedyScheduler`（含 `batch_order/sgs` 派工与 `improve` 模式） | `IG + TS + FastDecode/AccurateDecode` 双解码框架 | `core/algorithms/greedy/scheduler.py` |
| 运行形态 | Flask Web（路由 + 模板） | Flask Web（保留） + Numba JIT | `requirements.txt` |
| 甘特图能力 | Web 甘特图（设备/人员双视图、关键链高亮、依赖箭头模式、筛选与图例、URL 状态持久化） | Web 甘特图持续增强（复用同一数据契约） | `web/routes/scheduler_gantt.py`、`templates/scheduler/gantt.html`、`static/js/gantt.js`、`core/services/scheduler/gantt_contract.py` |
| 打包接入 | 当前仓库尚无 `.spec` 打包基线文件 | 后续补齐 spec、缓存回退与预热降级钩子 | 仓库根目录 `*.spec` 检索为空（需补证据文件） |
| 验证证据 | 已有 Web/排产冒烟与全量自测报告 | v2.0 目标能力需后续补充专项验收 | `evidence/Phase7/smoke_phase7_report.md`、`evidence/Phase10/smoke_phase10_report.md`、`evidence/FullSelfTest/full_selftest_report.md` |

> 状态口径冻结：专题文档以 v2.0 目标态设计为主；其中甘特图相关章节额外补充"v1.x 可执行基线"，用于指导当前仓库持续迭代，不作为 v2.0 已落地声明。

### 1.5 能力边界与本期范围

本方案的 v2.0 优化范围严格限定如下。任何超出此范围的需求必须作为独立里程碑立项，不得在 v2.0 实施过程中"顺手加入"。

**本期纳入**：

- 双资源约束（设备 + 人员）的 JSSP 排产优化。
- 分层目标体系 L0（可行性）+ L1（交付/加权拖期）为核心实现优先级；L2（稳定性）在两版本可比后启用；L3（切换成本）和 L4（效率）按数据就绪度触发。
- 冻结期支持（hard frozen 入可行域，soft frozen 作偏好成本）。
- 序列相关换模时间（SDST）按 family 建模。
- Win7 SP1 x64 单机部署。
- Web 甘特图持续迭代（契约统一、关键链、URL 持久化）。

**本期不纳入**：

- 材料齐套联合优化：系统已有 `ready_status/ready_date` 门禁，但算法主线不将材料约束纳入 L0 可行域做联合优化。
- 技能影响工时：维持 `pair_rank` 排序语义，不改变加工时长。
- 插件化加载算法：`core/plugins/` 保留现有结构，不作为 v2.0 必选交付。
- 多机多线程并行求解：默认单线程可复现，多线程评估作为独立实验。
- `OperatorSkill` 速度系数：schema 已存在该表，但本期不引入"技能影响工时"计算。

---

## 2. 专题导航

### 2.1 现状与问题诊断

诊断 v1.x 排产引擎的性能瓶颈（面向对象性能灾难、日历引擎无缓存）、建模局限（缺 SDST/冻结期/分层目标）和可维护性问题，为 v2.0 优化目标提供事实依据。

→ 详见 [排产优化_现状与问题诊断.md](排产优化_现状与问题诊断.md)

### 2.2 目标与验收标准

定义分层目标体系 L0（可行性）→ L1（交付）→ L2（稳定性）→ L3（切换成本）→ L4（效率均衡），以及各层的验收指标、实现优先级约束（L0+L1 先行）、拖期口径统一为 `weighted_tardiness_hours`、`ready_weight` 暂不生效声明。

→ 详见 [排产优化_目标与验收标准.md](排产优化_目标与验收标准.md)

### 2.3 技术架构

引擎分层架构、约束边界划分（SDST/冻结期/材料/外协/优先级）、数据转换层（InstanceBuilder）设计、物料齐套门禁语义（对齐现有实现）、Web 异步执行模型（待设计占位）、ext_group_id 快照策略（待设计占位）、GreedyScheduler v1.x 可执行基线。

→ 详见 [排产优化_技术架构.md](排产优化_技术架构.md)

### 2.4 数据模型与实例构建

`DRCJSSPInstance` 全量字段定义与冻结边界、日历口径与不可用区间生成、Top-K 预计算策略、编码与评估结构（`DualLayerEncoding`/`EvalResult`/`FullSchedule`）、efficiency 在整数时间轴中的表达（待设计占位）。

→ 详见 [排产优化_数据模型与实例构建.md](排产优化_数据模型与实例构建.md)

### 2.5 核心算法

双解码器设计（FastDecode 筛选 / AccurateDecode 发布，含职责边界表）、SGS 派工逻辑、IG 搜索框架（含可复现性约束 `random_seed`）、TS 搜索框架、鲁棒调度与冻结期处理、正在进行工序的剩余时长定义。

→ 详见 [排产优化_核心算法.md](排产优化_核心算法.md)

### 2.6 Win7 交付与部署

Win7 兼容差距矩阵、旧技术栈（Python 3.8/Numba 0.53.1/NumPy 1.20.3/PyInstaller 4.10）生命周期与替代路径、PyInstaller + Numba 打包策略、离线 Chrome109 集成、系统启停流程、留痕与审计（含 `result_summary` 512KB 体积约束）、版本回退 SOP。

→ 详见 [排产优化_Win7交付与部署.md](排产优化_Win7交付与部署.md)

### 2.7 测试验证方案

单元测试基线、集成测试策略、性能基准测试、分层验收断言（与 L0~L4 对应）、v1.x 甘特图可执行基线验收、关键口径一致性门禁。

→ 详见 [排产优化_测试验证方案.md](排产优化_测试验证方案.md)

### 2.8 风险与降级

技术风险矩阵、业务风险矩阵、分级降级策略（运行→内核→算法→优化→资源→业务，六级优先级链）、多重降级同时触发时的用户反馈要求、v2→v1 回退质量标准。

→ 详见 [排产优化_风险与降级.md](排产优化_风险与降级.md)

---

## 3. 实施路线图

> 状态：目标态实施计划，未落地（用于排期与里程碑管理）。

> 排期口径修订：v1.2.6 将核心开发周期从约 6 周调整为约 8.5 周，为 Numba nopython 调试、性能回归和参数调优预留必要缓冲。

### 3.1 Phase 1: 数据与解码内核（2.5周）

| 天数 | 任务 | 交付物 |
|------|------|--------|
| 1-3 | 搭建Win7测试环境，验证依赖兼容性 | 环境验证报告 |
| 4-6 | 实现family级SDST、`base_setup_time`闭环与`job_to_family`映射 | models.py |
| 7-9 | 实现双层编码`DualLayerEncoding`与合法性校验 | encoding.py, validator.py |
| 10-12 | 实现FastDecode与Top-K候选预计算（nopython契约） | fast_decoder.py |
| 13-15 | 实现AccurateDecode（空隙插入）+ setup规则分流 + 优先级双集合 unavail 取数 | accurate_decoder.py |
| 16-18 | 单元测试与基线性能测试（含nopython门禁） | 测试报告 |

**退出条件**: 所有单元测试通过；`machine_only`与`machine_and_worker`结果均可行；hard frozen工序保持不变；Numba nopython 编译通过；Win7环境运行无异常。

### 3.2 Phase 2: 搜索与鲁棒调度（2周）

| 天数 | 任务 | 交付物 |
|------|------|--------|
| 1-4 | 实现IG+TS框架（排序邻域+资源偏好邻域） | optimizer.py |
| 5-6 | 实现关键路径限频精算与近似关键工序评分 | critical_ops.py |
| 7-10 | 集成冻结期策略（hard入可行域，soft入偏好成本） | robust_scheduler.py |
| 11-12 | 实现无可行解诊断（冲突来源+建议动作） | infeasible_diag.py |
| 13-14 | 集成测试、性能回归与首轮参数调优 | 集成测试报告、性能报告 |

**退出条件**: L0约束违规为0；L1交付指标不劣于基线；200工序场景P90<8s；Win7冒烟通过。

### 3.3 Phase 3: Web UI集成（1.5周）

| 天数 | 任务 | 交付物 |
|------|------|--------|
| 1-3 | Web 甘特交互闭环与可中断流程提示 | gantt.js、gantt.html |
| 4-6 | 展示分层目标结果与失败诊断信息 | templates/scheduler/* |
| 7-8 | 打包配置与预热策略接入 | build.py, runtime_hook.py |
| 9-10 | 打包测试（含预热失败重试/降级） | 打包测试报告 |

### 3.4 Phase 4: 现场验证（2周）

| 天数 | 任务 | 交付物 |
|------|------|--------|
| 1-3 | 车间实地测试 | 现场测试报告 |
| 4-6 | 插单与冻结冲突场景验证 | 场景验证报告 |
| 7-10 | 性能压力测试 | 性能测试报告 |
| 11-14 | 操作员培训与参数固化 | 培训记录、反馈 |

### 3.5 Phase 5: 甘特图收口（1~2周，部分并行）

| 周次 | 任务 | 交付物 |
|------|------|--------|
| W1 | 固化甘特契约字段与 `contract_version`；关键链解释落地 | gantt_contract.py |
| W2 | 前端交互语义收口（状态优先后端、URL持久化、视图切换） | UI 对齐清单 |
| W3（可选） | 性能门禁与证据固化 | 增补报告 |

**退出条件**: 3类场景稳定可用；甘特契约回归全绿；一致性验证通过。

---

## 4. 附录

### 4.1 参考文献

1. Nowicki, E., & Smutnicki, C. (1996). A fast tabu search algorithm for the job shop problem. *Management Science*, 42(6), 797-813.
2. Ruiz, R., & Stützle, T. (2007). A simple and effective iterated greedy algorithm for the permutation flowshop scheduling problem. *European Journal of Operational Research*, 177(3), 2033-2049.
3. Taillard, É. (1994). Parallel taboo search techniques for the job shop scheduling problem. *ORSA Journal on Computing*, 6(2), 108-117.
4. Zheng, X. L., & Wang, L. (2016). A knowledge-guided fruit fly optimization algorithm for dual resource constrained flexible job-shop scheduling problem. *International Journal of Production Research*, 54(18), 5554-5566.
5. Allahverdi, A., Ng, C. T., Cheng, T. C. E., & Kovalyov, M. Y. (2008). A survey of scheduling problems with setup times or costs. *European Journal of Operational Research*, 187(3), 985-1032.

### 4.2 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 作业车间调度 | Job Shop Scheduling | 每个工件有特定的工艺路线 |
| 双资源约束 | Dual Resource Constrained | 设备和工人双重约束 |
| 关键路径 | Critical Path | 决定总工期的最长路径 |
| 关键块 | Critical Block | 同一机器上连续的关键路径工序 |
| 冻结期 | Frozen Window | 不可移动的时间窗口 |
| SDST | Sequence-Dependent Setup Time | 序列相关换模时间 |
| IG | Iterated Greedy | 迭代贪心算法 |
| 双层编码 | Dual-Layer Encoding | 排序基因(js) + 资源偏好基因(machine_pref/worker_pref) |
| 分层目标 | Lexicographic Objective | 按L0→L4逐层比较，高层级优先 |
| 快评/精评 | FastDecode / AccurateDecode | 尾插快评用于搜索迭代，空隙插入精评用于下发 |
| 产品族 | Product Family | SDST按族而非按件建模，降低矩阵规模 |
| 预分配slot | Pre-allocated Slot Array | Numba兼容的定长二维数组+计数器，替代动态列表 |

### 4.3 证据锚点

#### 4.3.1 内部证据（仓库内）

- 现状算法实现：`core/algorithms/greedy/scheduler.py`（`GreedyScheduler`）。
- 现状依赖口径：`requirements.txt`（Flask/openpyxl）。
- 现状打包口径：仓库根目录当前未检索到 `.spec` 文件；需在接入打包链路时补齐并补证据锚点。
- 日历默认与归一化：`core/services/scheduler/calendar_engine.py`、`web/routes/scheduler_utils.py`。
- schema 现状锚点：`schema.sql`（含 `SchemaVersion`、`ScheduleConfig`、`OperatorSkill`、`Materials`、`BatchMaterials`）。
- 插件系统现状锚点：`core/plugins/manager.py`、`core/plugins/registry.py`。
- 现状能力验证：
  - `evidence/FullSelfTest/full_selftest_report.md`
  - `evidence/Phase7/smoke_phase7_report.md`
  - `evidence/Phase10/smoke_phase10_report.md`

#### 4.3.2 外部证据（公开来源）

- pip 24.3.1 元数据（`requires_python >=3.8`）：https://pypi.org/pypi/pip/24.3.1/json
- Numba 与 NumPy 1.21 兼容问题与跟踪：https://github.com/numba/numba/issues/7175
- PyInstaller 官方支持语义（Win8+ 官方支持，Win7 非官方兼容）：https://raw.githubusercontent.com/pyinstaller/pyinstaller/develop/README.rst

### 4.4 版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| v1.3.0 | 2026-03-12 | 修订拆分版：拆分为"总览 + 8 个专题文档"结构；新增 1.5 能力边界与本期范围；新增 3.4 L0+L1 优先实现与 L3/L4 触发条件；新增 4.5.3~4.5.5（物料齐套门禁、Web 异步执行占位、ext_group_id 快照占位）；新增 DRCJSSPInstance 字段冻结边界与 efficiency 占位节；新增 FastDecode/AccurateDecode 职责边界表；新增可复现性约束；新增 6.4.1 正在进行工序剩余时长定义；新增旧技术栈生命周期；新增 10.4.2 多重降级优先级与用户反馈；新增 result_summary 体积约束；拖期指标口径统一为 weighted_tardiness_hours；ready_weight 标注暂不生效；审计意见文件归档。 |
| v1.2.9 | 2026-02-26 | 一致性收敛：统一优先级门禁数据契约为 `*_unavail_by_priority` 并消除"双轨判定"；补 setup 闭环（`base_setup_time + family_sdst`）及 L3 口径；重写 Top-K 预计算为 nopython 友好伪代码并补 `pair_compatible` 过滤；统一 `CriticalView` 返回契约；修正 IG destroy/rebuild 的 js token 语义；将 `accurate_eval_timeout_ms` 默认值收敛到 250ms；新增 v2->v1 回退适配契约与最小回归集；补 due_date 质量门禁并去重 9.6 重复断言。 |
| v1.2.8 | 2026-02-26 | 复审补强：修正打包证据锚点；补 L1 双口径与交期半开区间定义；新增复审映射清单；移除 `deap` 目标依赖；补 OperatorSkill/ScheduleConfig/Materials 与插件系统边界说明。 |
| v1.2.7 | 2026-02-26 | 评审收口：统一优先级门禁为双集合；补 L2/L3 边界门禁与对齐失败回退；统一 SDST 重建预算毫秒公式；新增 9.6 关键口径一致性门禁。 |
| v1.2.6 | 2026-02-26 | 审查修订：技能模型收敛为 `pair_rank` 排序；IG 重建改随机贪心插入降复杂度；补 SDST 闭环预算与超时降级；实施周期调整为约 8.5 周。 |
| v1.2.5 | 2026-02-24 | 新增甘特图实施基线（4.6、8.5、9.5）。 |
| v1.2.4 | 2026-02-24 | 口径修订：新增"现状实现边界"状态表；明确第3~9章为目标态设计稿。 |
| v1.2.3 | 2026-02-23 | 四审修正：numpy降级1.20.3；AccurateDecode SDST修正；InstanceBuilder迁移路径。 |
| v1.2.2 | 2026-02-23 | 三审查漏：补 get_family_setup 定义；空隙插入接入日历不可用区间。 |
| v1.2.1 | 2026-02-23 | 二审修订：Numba数组化设计；EvalResult热路径复用；SA分层delta。 |
| v1.2 | 2026-02-23 | 算法-数据-业务一致性修订：双层编码、Fast/Accurate双解码、分层目标。 |
| v1.0 | 2025年（具体日期待补） | 初始版本。 |

---

### 与现有开发文档体系的联动

拆分后的同步检查清单：

- 专题文档正式定义新字段/新表/新 `ScheduleConfig` 键 → 同步 [系统速查表.md](../系统速查表.md)。
- 专题文档确定新页面/路由/交互反馈/用户可见提示 → 同步 [面板与接口清单.md](../面板与接口清单.md)。
- 专题文档固化新模型边界/Repository 事实来源/输入输出结构 → 同步 [开发文档.md](../开发文档.md)。
- 关键技术选型定案（Win7 兼容策略、异步执行架构） → 追加 ADR 到 `开发文档/ADR/`。

---

**本文档为APS测试系统排产优化项目的总览与索引。详细内容请访问对应专题文档。**

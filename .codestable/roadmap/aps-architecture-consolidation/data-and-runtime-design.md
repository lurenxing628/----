---
doc_type: architecture-proposal
slug: aps-data-and-runtime-consolidation
status: approved
created: 2026-11-09
updated: 2026-11-09
scope: 业务域所有权、SQLite事务、显式事实作用域、7条命令回执查询统一、运行宿主单入口化与Win7交付
summary: 持久化存储格式0变更；消除实例私有属性偷渡与全库冗余构造，统一7条回执查询链路与单入口运行宿主。
related_roadmap: aps-architecture-consolidation
---

# 数据、业务事务与运行宿主设计

本文是[总设计](aps-architecture-consolidation-roadmap.md)的数据与运行时定稿详设。以下目标结构已由主代理与审查通道对齐定稿，当前源码证据单独标出。

## 1. 设计结论与持久化存储 0 变更边界

保留离线单体应用、SQLite、领域服务和显式事务，以及实际使用的受控计算和导出子进程。单体表示统一部署与业务边界，不表示强制只有一个操作系统进程；连接、`capture` 和运行态不跨进程传递。领域之间通过有业务含义的函数与只读事实协作；每次写入由一个用例拥有最外层事务，每类持久事实有明确的唯一写入者。

全部目标代码、内部合同、前端和构建产物作为一次切换集合交付。工作可以内部拆分实现和检查，但上线时只留下目标入口与目标实现，不发布新旧业务接口并存版本，不保留旧解析器、兼容重导出或双写链。

**持久化存储格式 0 变更裁决**：
- 当前 `CURRENT_SCHEMA_VERSION=45`（[`core/infrastructure/migration_state.py:55`](../../../core/infrastructure/migration_state.py#L55)）、业务表、归档 JSON、持久读模型、外部维护日志以及 `WorkbenchCommandReceipts` 表（[`data/repositories/workbench_command_repo.py:65`](../../../data/repositories/workbench_command_repo.py#L65)，落盘正文只有 `result/data/warnings`）在本次架构收敛中 **保持原编码 0 变更**；浏览器本机 `pending` 存储编码同样保持不变。
- **不建设一次性离线数据格式转换工具，不引入离线 `reconcile_frozen_intent` 接口**。内部类型、事实作用域与模块调整不触碰落盘格式；命令回执的查询包装（`state / may_be_in_flight / resolution`）统一在读取出口生成，不写回原 `receipt` 表。
- 服务切换前后，未决命令与在途任务的恢复统一通过现有的启动恢复（[`web/bootstrap/workbench_run_runtime.py:104`](../../../web/bootstrap/workbench_run_runtime.py#L104)、[`web/bootstrap/workbench_system_restore_recovery.py:23`](../../../web/bootstrap/workbench_system_restore_recovery.py#L23)）与统一后的在线回执查询接口按原 `request_key` 完成。

## 2. 业务域所有权

“拥有”表示决定合法变更、组织事务并解释该域事实；其他域可以读取公开投影，不能自行重写该域表或复制规则。下表为目标职责，现有目录可承载这些边界，不要求为每一行新增包或接口类。

| 业务域 | 唯一拥有的业务事实/动作 | 向其他域提供 | 禁止承担的职责 |
|---|---|---|---|
| 基础资料与工艺 | 零件、工序模板、工种、工艺确认与模板谱系 | 已确认路线、工时标准、永久引用 | 改写已保存候选的历史工艺 |
| 批次 | 批次数量、交期、批次工序生成/同步、合法拆批 | 排产范围与工序需求 | 在列表读取时隐式生成或同步工艺 |
| 资源与日历 | 设备、人员、供应商静态档案、资格、班次、停机和工作时段 | 同一有效日历/资格口径与供应商身份 | 根据某个页面自行解释另一套班次 |
| 物料 | 用料、到料、分阶段齐套与核对事实 | 批次/工序级可释放条件 | 决定搜索策略或补写排产结果 |
| 外协 | 外协业务能力约束、交接与到货事实 | 外协周期、能力和实际状态 | 将未确认交接伪装成已完成加工；另写供应商静态身份 |
| 现场执行 | 实际区间、数量、报工、撤销和剩余量确认 | 执行账本、实际甘特、排产保护事实 | 回写候选，使历史计算看似使用最新报工 |
| 排产运行 | 受理范围、持久任务、计算来源、候选发布 | 候选、搜索过程与结果状态 | 分配正式采用版本或修改现场实际 |
| 正式计划/采用 | 采用事务、正式版本、安排身份与采用来源 | 当前正式计划及历史版本 | 重新计算候选或绕过执行约束 |
| 试调 | 草稿、编辑版本、保存方案与试调验证 | 可供正式采用的确定方案 | 保存草稿时隐式更新正式计划 |
| 工时校准 | 样本选择、建议、模板定额采用证据 | 将来模板使用的定额 | 改写既有批次、历史工时和实际记录 |
| 报表/值班台/决策查询 | 查询范围、筛选、排序、展示投影、导出 | 业务读模型 | 形成第二套交付、工时或资源判断规则 |
| 系统维护 | 备份文件、恢复日志、运行宿主维护过程 | 可查询维护结果与重启要求 | 借普通DB回执证明数据库替换成功 |

当前已存在的合理复用必须延续：候选采用与试调采用共用 `AdoptionCommandHost`，但各自提供领域验证和持久化；校准采用明确为 `future_template_use_only`。[候选采用 `candidate_adoption.py:37`](../../../core/services/workbench/run/candidate_adoption.py#L37)、[试调采用 `adoption.py:43`](../../../core/services/workbench/trial/adoption.py#L43)、[校准采用 `adoption.py:65`](../../../core/services/workbench/calibration/adoption.py#L65)。

跨域动作由明确的用例协调。例如正式采用调用执行约束和资源事实读取，再一次写入计划与回执；报表只消费这些事实。无需新增事件总线、通用聚合框架或跨域仓储总门面。

## 3. 数据表示、领域规则收口与无用往返清理

### 3.1 四种数据表示与准入边界

目标区分四种数据，名称和类型表达用途，而不是都称作 model 或 context。

| 表示 | 创建位置 | 生命周期 | 校验与消费规则 |
|---|---|---|---|
| 输入合同 | HTTP/文件进入领域用例的准入处 | 一次用户意图 | 解析类型、范围、允许字段一次；内部传递规范结果 |
| 存储行 | Repository | 当前连接/事务 | SQL返回真实数据；领域准入解释其业务含义，不静默补缺 |
| 已准备事实 | 事实作用域（Fact Scope）/归档受理入口 | 一个事务快照或一个不可变归档对象 | 同源共享，不在每个下游重新校验/解码整份内容 |
| 对外DTO | 查询/命令发布出口 | 一次响应或持久读模型 | 只做对外合同要求的格式与字段映射 |

Repository 可直接持有连接并返回行或具名数据，不强制继承 `BaseRepository` 或统一经包根重导出。`WorkbenchRunRepository` 现已这样工作。[`workbench_run_repo.py:31`](../../../data/repositories/workbench_run_repo.py#L31)。

输入校验属于纯合同，业务决策属于用例；不能为了满足“Model只含from_row/to_dict”把纯准入塞进事务协调。需要更新的现行指导见 [架构不变量:29](../../../.limcode/rules/architecture-invariants.mdc#L29)，而不是给当前代码补空壳继承。

### 3.2 领域规则收口与无用往返清理（消除母题 J / M）

- **实体 `capabilities / blocked_reasons` 统一收口到领域层**：将路由层（[`web/routes/workbench/materials.py`](../../../web/routes/workbench/materials.py)、[`web/routes/workbench/resources.py`](../../../web/routes/workbench/resources.py)、[`web/routes/workbench/batches.py`](../../../web/routes/workbench/batches.py)）手写的实体可执行能力与阻断原因计算统一收口到对应领域服务层，以同一口径同时服务单行详情、批量（bulk）操作和文件导入。
- **删除无用类型往返与序列化往返**：
  - 删除 [`core/services/workbench/material/queries.py:45-49`](../../../core/services/workbench/material/queries.py#L45-L49) 构造 `WorkbenchEntityIdentity` 后立即 `asdict()`、到了 [`core/services/workbench/material/service.py:48`](../../../core/services/workbench/material/service.py#L48) 又转回 dataclass 的往返；保留 [`web/routes/workbench/materials.py:53`](../../../web/routes/workbench/materials.py#L53) 写指纹边界上的可序列化字典表示（因 `content_text / packed` 不直接序列化 dataclass）。
  - 删除 [`data/repositories/workbench_command_repo.py:45-50`](../../../data/repositories/workbench_command_repo.py#L45-L50) 刚执行 `canonical_json` 立刻 `json.loads` 的无用往返。

## 4. 事务、连接与显式事实作用域

### 4.1 三种操作路径

| 路径 | 事务拥有者 | 内部动作 | 发布时点 |
|---|---|---|---|
| 普通查询 | 查询用例 / 事实作用域 | 一份只读快照内先验轻量修订指纹，再按需捕获/投影；需要文件时在作用域内取完数据，退出读事务后再生成文件 | 数据已完整构造后返回 |
| 普通数据库命令 | `WorkbenchCommandService.execute` | 重放检查、取得写锁、当前事实guard、业务写入、同连接重读（如需）、回执写入 | 最外层提交成功后 |
| 长排产 | 运行用例/worker | 短事务受理；隔离副本计算；短事务复核事实、保存候选与终态 | 各持久阶段实际提交后 |

嵌套领域调用使用同一连接，不独立 commit。网络调用、文件保存、长计算不塞入数据库命令的写事务。Repository 不自行打开第二连接或另开事务来规避用例的原子性。

现有共同命令服务在写锁内第二次检查重放，防止两连接同时受理同一意图；这不是可删的重复校验。[`commands.py:45`](../../../core/services/workbench/commands.py#L45)。worker 在计算副本读取、保存事务内再次核对来源，属于跨时点复核。[`worker.py:93`](../../../core/services/workbench/run/worker.py#L93)、[`worker.py:111`](../../../core/services/workbench/run/worker.py#L111)。

### 4.2 目标内部调用合同

继续复用现有命令原语；它承担真实的事务所有权，无需另建命令执行框架。Python 3.8 接口草图：

```python
def execute(*, request_key: str, action: str, context_ref: str,
            normalized_input: object, guard, mutate) -> dict:
    # guard() 在已取得的写事务内产生本次已核对事实。
    # mutate(checked) 只操作同一DB连接，返回 WorkbenchCommandOutcome。
    # 业务变更与回执一次提交；提交前不得返回“已保存”。
    ...
```

这里保留 `guard/mutate` 回调有明确用途：多个领域共享同一种事务/重放协议。它与“只有一个生产调用者却层层传回调”的计算编排不同。领域负责 `guard` 内的业务决定，命令服务不按 action 字符串分派所有业务。

### 4.3 消除实例临时私有属性偷渡与字典子类魔法（母题 I）

当前工作台多个领域服务通过改写 `self` 私有属性或字典子类魔法隐式传递快照状态：
- **资源域**：[`core/services/workbench/resource/queries.py:61-84`](../../../core/services/workbench/resource/queries.py#L61-L84) 的 `read_snapshot` 在 `self` 上备份并还原 11 个私有属性，且 `ResourceTableFacts`（[`core/services/workbench/resource/table_facts.py:139`](../../../core/services/workbench/resource/table_facts.py#L139)）反向调用 `self.metrics._load`。
- **工艺域**：[`core/services/workbench/process/queries.py:47-72`](../../../core/services/workbench/process/queries.py#L47-L72)、[`303-339`](../../../core/services/workbench/process/queries.py#L303-L339) 的 `_RawProcessFacts(dict)` 覆写 `__getitem__` 在键访问时偷偷跑 SQL 改写自身，另有 [`core/services/workbench/process/route_facts.py:38`](../../../core/services/workbench/process/route_facts.py#L38) 的第二层目录懒加载。
- **物料与批次域**：[`core/services/workbench/material/queries.py:60-78`](../../../core/services/workbench/material/queries.py#L60-L78) 与 [`core/services/workbench/batch/facts.py:26-34`](../../../core/services/workbench/batch/facts.py#L26-L34) 在服务实例上临时挂载快照与查找表，退出时 `finally` 还原。
- **执行账本与报表跨层穿透**：[`core/services/execution/ledger_reader.py:172`](../../../core/services/execution/ledger_reader.py#L172) 维护实例级缓存，以及 [`core/services/workbench/report/facts.py:39`](../../../core/services/workbench/report/facts.py#L39) 穿透访问 [`core/services/workbench/plan/queries.py:64`](../../../core/services/workbench/plan/queries.py#L64) 的私有上下文。

**目标模式**：
1. 让显式的**事实作用域（Fact Scope）**成为唯一读取所有者；指标、表格投影、写入准备单向接收并消费该作用域对象，不在上层服务实例上暂存或恢复私有属性，也不覆写 `dict.__getitem__` 触发隐式查询。
2. 直接公开 `PlanReadContext` 与执行账本读作用域供报表与计划查询显式消费，消除跨模块私有方法穿透。
3. 同步将 [`tests/workbench/test_material_snapshot_facts.py:75`](../../../tests/workbench/test_material_snapshot_facts.py#L75)（断言内部 `_snapshot` 属性）与 [`tests/workbench/test_batch_actions.py:146`](../../../tests/workbench/test_batch_actions.py#L146)（断言内部 `_facts / _stamp / _lookups` 属性）迁移为公开行为与返回值契约断言。
4. **严格保留三种真实事务/快照生命周期**：
   - **工艺域**：加入调用方已持有的事务，不额外开启嵌套 `SAVEPOINT`（由 [`tests/workbench/test_process_file_api_transactions.py:273`](../../../tests/workbench/test_process_file_api_transactions.py#L273) 锁定）；
   - **批次域 detached snapshot**：[`core/services/workbench/batch/facts.py:75`](../../../core/services/workbench/batch/facts.py#L75) 在捕获完所需关系数据后立即释放自己拥有的读事务，再在事务外完成内存投影；
   - **写命令作用域**：在同一数据库连接完成写入后基于该连接重新读取最新状态；同一物料事实作用域内判断日（`today`）固定（跨午夜不漂移），资源导出在作用域内取完数据、退出读事务后再生成文件。

## 5. 事实快照、按需闭包读取与读模型

### 5.1 四种身份各司其职

| 身份 | 用途 | 不可替代 |
|---|---|---|
| 永久业务引用 | 标识具体批次、工序、方案等对象；保留删除与重建的区别 | 数据版本、写权限 |
| 来源修订集合 | 判断某项业务依赖的事实是否变化 | 历史事实正文、排产结果 |
| `snapshot_ref` | 将查询范围、事实值及首次观察时间绑定，约束连续分页/导出 | 写凭证、跨恢复有效的数据库身份 |
| `write_token` / `request_key` / `data_context_ref` | 分别表达确认过的写入条件、一次用户意图、数据库来源上下文 | 三者彼此不可替代 |

当前读绑定复用最初的 `as_of`，复查查询范围和事实值后继续使用同一token；失配报 `snapshot_stale`。[`read_context.py:76`](../../../web/routes/workbench/read_context.py#L76)。目标继续如此，不把每次翻页变成“自动刷新成另一份数据”。

### 5.2 先验轻量修订指纹，再按用途取完整关系闭包（消除母题 E / G）

`ProductionFactsCapture` 只属于一份事务快照；`GenerationFacts` 只解释一份已保存归档（[`candidate_facts.py:121`](../../../core/services/workbench/facts/candidate_facts.py#L121)）。修订集合按消费者真实依赖定义（[`source_revisions.py:18`](../../../core/services/workbench/facts/source_revisions.py#L18)）。在此基础上，工作台各域查询与预检统一遵循“先验轻量修订指纹、再按用途取完整关系闭包”：

1. **读/预检入口前置核验轻量修订指纹**：进入读事务或预检入口的第一步先核验轻量修订指纹与快照令牌，失配立即拒绝 `snapshot_stale`，杜绝先做重型计算再验过期的“先算后扔”（如修复 [`web/routes/workbench/preflight.py:54`](../../../web/routes/workbench/preflight.py#L54) 先完整重算预检结果再验 `snapshot_ref` 过期的倒置顺序）。
2. **已完成的按需读取保持稳定**：[`core/services/workbench/material/queries.py:222`](../../../core/services/workbench/material/queries.py#L222)、[`core/services/workbench/resource/queries.py:218`](../../../core/services/workbench/resource/queries.py#L218) 及 [`core/services/workbench/batch/service.py:51`](../../../core/services/workbench/batch/service.py#L51)（备注/交期修改）已完成按需与分页读取，直接保持，不再重复派发改造。
3. **批次（`batch`）读取精准瘦身与闭包边界**：
   - **按需构造 `workflow_snapshot`**：[`core/services/workbench/batch/facts.py:59`](../../../core/services/workbench/batch/facts.py#L59) 当前无条件构造全库 `workflow_snapshot`，但只有模板状态校验（[`core/services/workbench/batch/template_validation.py:49`](../../../core/services/workbench/batch/template_validation.py#L49)）消费它。调整后，批次列表（`page`）、`summaries`、选择（`selection`）、筛选项（`choices`）与普通导出直接跳过 `workflow_snapshot` 构造；单批次详情（[`core/services/workbench/batch/queries.py:70`](../../../core/services/workbench/batch/queries.py#L70)）与工艺同步则只按目标批次所属零件及关联外协组按需加载 `workflow_snapshot`、模板事实与跨零件外协组成员闭包，完整保留详情页的跨零件引用诊断（[`tests/workbench/test_batch_actions.py:407`](../../../tests/workbench/test_batch_actions.py#L407)），不再构造全库所有零件的 `workflow_snapshot`。
   - **单批次操作加载目标批次完整关系闭包**：单批次详情、删除、改量与重建工序继续保留 `BATCH_SOURCE_KEYS` 修订指纹（[`core/services/workbench/batch/facts.py:83`](../../../core/services/workbench/batch/facts.py#L83)、[`web/routes/workbench/read_context.py:76`](../../../web/routes/workbench/read_context.py#L76)），但不再全表加载所有批次，而是只按目标批次加载其**完整关系闭包**——包括目标批次全部工序、所有版本计划引用、有效及作废报工投影、外协收发、物料需求、拆分来源与子批关系（[`core/services/workbench/batch/facts.py:177`](../../../core/services/workbench/batch/facts.py#L177)），以及详情/工艺同步所需的目标零件模板与相关外协组跨零件成员（[`core/services/workbench/batch/template_validation.py:14`](../../../core/services/workbench/batch/template_validation.py#L14)）。
   - **列表轻筛选下推与同集合契约**：批次列表先下推编号、零件、标签等轻筛选条件，同时严格保留派生 `status / ready_status` 过滤以及 `selection / facets / filtered export` 看到同一匹配集合的契约（[`core/services/workbench/batch/queries.py:30`](../../../core/services/workbench/batch/queries.py#L30)、[`tests/workbench/test_batch_list_summary.py:82`](../../../tests/workbench/test_batch_list_summary.py#L82)）。

### 5.3 持久读模型与存储契约稳定

持久读模型是某次受理/完成时点的查询产物，由该事务一次生成并保存；普通 GET 不修复 Schema、不回写缺字段、不重排。相同来源的页面、导出、甘特通过同一领域投影取得口径一致的数据。

由于本次架构收敛保持数据库 Schema（版本 45）、归档 JSON 与持久读模型落盘格式 **0 变更**，现有历史候选归档、正式计划版本、执行账本与回执记录无需离线转换，直接由整理后的唯一领域入口按原存储契约读取与验证。

## 6. 幂等命令与 7 条回执查询链路统一收口

### 6.1 普通数据库命令

相同 `request_key + action + context_ref + normalized_input` 重放同一已提交回执；同键不同意图报 `request_key_conflict`。已提交结果的重放早于过期编辑token检查，避免“上次已成功、这次却被当新操作拒绝”。当前行为有直接实现与测试。[`commands.py:88`](../../../core/services/workbench/commands.py#L88)、[`test_commands.py:40`](../../../tests/workbench/test_commands.py#L40)。

对外仍区分三类事实：确定未提交的拒绝、确定提交的回执、暂时无法确认的结果。普通命令成功结果保持 `committed / unchanged / partial` 的业务区别；`partial` 必须是该用例明确支持的结果，不允许将意外异常后剩余数据称作部分成功。[`workbench_command.py:24`](../../../core/models/workbench_command.py#L24)、[`workbench_command.py:44`](../../../core/models/workbench_command.py#L44)。`WorkbenchCommandReceipts` 表的落盘结构（[`data/repositories/workbench_command_repo.py:65`](../../../data/repositories/workbench_command_repo.py#L65)，仅存储 `result / data / warnings`）保持 0 变更。

### 6.2 全仓 7 条命令回执查询（lookup）链路统一收口

当前全仓共有 7 条命令/任务/维护结果查询链路，在返回字段命名（`recorded` vs `committed` vs 裸返 `receipt`）、未观察到回执时的 HTTP 状态码（200 `not_observed` vs 404 `receipt_not_found`）以及上下文校验上各自为政。目标是将普通与领域命令回执查询统一到同一读取出口包装原语，全部 7 条现存查询链路的目标动作如下：

1. **通用普通命令查询 `GET /api/workbench/v1/commands/<request_key>`**：
   - 将当前混放在 [`web/routes/workbench/materials.py:103-121`](../../../web/routes/workbench/materials.py#L103-L121) 的路由抽离到独立的命令路由模块。
   - 统一返回标准信封与 `{state: "recorded" | "not_observed", receipt, may_be_in_flight, resolution}`（包装字段在读取出口动态生成，不写回 `WorkbenchCommandReceipts` 表）。
   - 普通 CRUD 与导入命令**仅凭 `request_key` 查询，不新增 `data_context_ref` 参数**（试调编辑本机仅存 key [`frontend/workbench/app/TrialAPI.js:7`](../../../frontend/workbench/app/TrialAPI.js#L7)，资源导入本机不存 `preview_ref` [`frontend/workbench/app/resource-api.js:74`](../../../frontend/workbench/app/resource-api.js#L74)）。
2. **候选采用回执查询 `GET /api/workbench/v1/scheduling/candidates/<candidate_ref>/adoption-commands/<request_key>`**（[`web/routes/workbench/run_candidate_adoption.py:48-54`](../../../web/routes/workbench/run_candidate_adoption.py#L48-L54)）：
   - 保留领域路由入口与 `run_ref / data_context_ref` 绑定校验。
   - 修复当前路由层丢弃服务层 `state: "recorded"`、直接裸返 `receipt` 的协议分裂，接入共同回执查询包装原语，返回统一的 `{state, receipt, may_be_in_flight, resolution, data_context_ref}`。
3. **试调采用回执查询 `GET /api/workbench/v1/trial/scenarios/<scenario_ref>/adoption-commands/<request_key>`**（[`web/routes/workbench/trial_adoption.py:50-54`](../../../web/routes/workbench/trial_adoption.py#L50-L54)）：
   - 保留领域路由入口与 `scenario_ref / data_context_ref` 绑定校验。
   - 将已提交状态名从 `committed` 统一改为 `recorded`，接入共同回执查询包装原语。
4. **校准采用回执查询 `GET /api/workbench/v1/calibration/<suggestion_ref>/adopt/receipts/<request_key>`**（[`web/routes/workbench/calibration_adoption.py:48-55`](../../../web/routes/workbench/calibration_adoption.py#L48-L55)）：
   - 保留领域路由的 `action / template_operation_ref` 绑定校验，接入共同回执查询包装原语。
   - **彻底删除未命中时抛 HTTP 404 `receipt_not_found` 的特判**（同步删除前端 [`frontend/workbench/app/transport.js:153`](../../../frontend/workbench/app/transport.js#L153) 的 404 兜底转换），未命中统一返回 HTTP 200 `{state: "not_observed", receipt: null, may_be_in_flight: true, resolution: "unresolved"}`。
   - 同步修正 [`web/routes/workbench/calibration_adoption.py:42`](../../../web/routes/workbench/calibration_adoption.py#L42)（显式设置 `g.workbench_result_target` 为专用回执查询路径）与 [`frontend/workbench/app/CalibrationAdoptionAPI.js:69`](../../../frontend/workbench/app/CalibrationAdoptionAPI.js#L69)（提交时 `expect` 地址），使后端 POST 失败信封的 `result_target`、前端 `expect` 与实际回执查询地址三者完全一致。
5. **试调草稿/方案编辑回执查询 `GET /api/workbench/v1/trial/commands/<request_key>`**（[`web/routes/workbench/trial.py:120-132`](../../../web/routes/workbench/trial.py#L120-L132)、[`core/services/workbench/trial/service.py:256-265`](../../../core/services/workbench/trial/service.py#L256-L265)）：
   - 保留 trial action 范围校验，接入共同回执查询包装原语，统一返回 `{state: "recorded" | "not_observed", receipt, may_be_in_flight, resolution}`。
6. **排产任务受理查询 `GET /api/workbench/v1/scheduling/requests/<request_key>`**（[`web/routes/workbench/scheduling_jobs.py:106-118`](../../../web/routes/workbench/scheduling_jobs.py#L106-L118)）：
   - 保留 `{found, run, resolution, data_context_ref}` 的任务生命周期语义，明确区分“排产请求已受理持久化”与“worker 后台计算完成”。
   - 严格保持 [`core/services/workbench/facts/run_data_context.py:33`](../../../core/services/workbench/facts/run_data_context.py#L33) 的判定边界：只有存在已验证的系统恢复记录时才判 `resolution = "context_replaced"`。
7. **系统维护结果查询 `GET /api/workbench/v1/system/results/<request_key>`**（[`web/routes/workbench/system_routes.py:20`](../../../web/routes/workbench/system_routes.py#L20)、[`web/routes/workbench/system_actions.py:36-50`](../../../web/routes/workbench/system_actions.py#L36-L50)）：
   - 系统配置保存回执复用共同数据库回执查询机制。
   - 文件级备份与恢复操作继续由数据库外部维护日志 `SystemMaintenanceJournal` 证明并返回结果（因恢复期间 [`web/bootstrap/workbench_system_restore_status.py:45`](../../../web/bootstrap/workbench_system_restore_status.py#L45) 可能只启动 journal-only host、不打开业务数据库）。

**结果语义与前端协同**：
- `recorded` 必须返回原回执，`may_be_in_flight=false`，表示该命令已提交的终态。同键与 `action / context` 不符直接报 `request_key_conflict`。
- `not_observed + unresolved` 保留 `may_be_in_flight=true`，不证明失败，也不授权生成新 key 重做。携带 `data_context_ref` 的采用/排产链路在确认数据库来源已因恢复替换后返回 `context_replaced` 且 `may_be_in_flight=false`，仅允许结束旧来源的本机待确认记录；对新库执行操作必须重新预检并形成用户新意图。
- 服务器回执是结果权威；浏览器本地存储只是未完成意图的恢复媒介。本机存储清理失败后，当前会话也不能把已观察到的终态降回 `pending`，详见[前端设计](frontend-design.md)。

### 6.3 三种持久对象不能合并

| 对象 | 权威存储 | 恢复方式 |
|---|---|---|
| 普通/领域数据库命令 | 与业务变更同事务的 `WorkbenchCommandReceipts` 表 | 按原 `request_key` 查询/重放 |
| 长排产任务 | 运行记录、执行者身份、已保存阶段与结果 | 启动恢复（[`workbench_run_runtime.py:104`](../../../web/bootstrap/workbench_run_runtime.py#L104)）与 worker 生命周期核对所有权和可恢复状态 |
| 备份/恢复文件动作 | 数据库外部维护日志 `SystemMaintenanceJournal` | 启动恢复（[`workbench_system_restore_recovery.py:23`](../../../web/bootstrap/workbench_system_restore_recovery.py#L23)）与按日志读取原结果，必要时停止服务并要求进程重启 |

恢复会替换业务数据库，因此其完成证据不能只存在于被替换库中；文件操作也不能假装受 SQLite 事务回滚。这三条路径共享错误表达和身份核对，但各自保留真实的持久化机制。

## 7. 运行宿主单入口化、启动连接复用与恢复

### 7.1 退役 `app_new_ui.py` / `ui_mode` 与消除 `app.py` 顶层导入副作用

1. **完整退役 `app_new_ui.py`、`start_new_ui.bat` 与 `ui_mode` / `APP_UI_MODE`（母题 A / B / C）**：
   - 删除 [`app_new_ui.py`](../../../app_new_ui.py)、[`start_new_ui.bat`](../../../start_new_ui.bat) 及相关内部参数与配置。
   - 删除 [`web/routes/workbench/system_runtime.py:25`](../../../web/routes/workbench/system_runtime.py#L25)（`/system/health` 中的 `ui_mode` 字段）、[`web/bootstrap/launcher_contracts.py:86`](../../../web/bootstrap/launcher_contracts.py#L86) 及 [`validate_dist_exe.py:262`](../../../validate_dist_exe.py#L262) 中的 `ui_mode == "default"` 检查，不留 `"default"` 僵尸常量。
   - 修复 [`tools/wufenchang_demo/builder.py:33`](../../../tools/wufenchang_demo/builder.py#L33) 向 `create_app_core` 传递 3 个已删 `enable_*` 参数导致的现存 `TypeError`。
   - 将 [`tests/app_runtime/test_app_new_ui_create_app_smoke.py:69`](../../../tests/app_runtime/test_app_new_ui_create_app_smoke.py#L69) 中冷启动不急切加载计算/Excel、排产锁共用、合法缓存配置 `0` 等有效断言完整迁入 [`app.py`](../../../app.py) 对应测试后，删除 `test_app_new_ui_create_app_smoke.py`。
2. **删除 [`app.py:52-57`](../../../app.py#L52-L57) 模块 import 顶层急切执行 `app = create_app()` 的副作用**：
   - 仅导入 `app` 模块不再隐式触发应用装配与数据库初始化；测试统一改为显式调用 `create_app()` 工厂函数。
   - 完整保留健康探针不连库、本机关停鉴权与启动失败退出码 `14` 的运行边界。

### 7.2 启动顺序、连接复用边界与停机

启动入口拥有资源获取顺序：确认维护日志可进入 → 获取实例/数据库范围锁 → 验证数据库合同 → 装配请求与 worker 生命周期 → 实际绑定监听 → 发布实际地址和运行身份 → 接收业务请求。各步骤的逆向释放只由同一宿主负责（[`runtime_server.py:61`](../../../web/bootstrap/runtime_server.py#L61)、[`launcher_runtime_lock.py:286`](../../../web/bootstrap/launcher_runtime_lock.py#L286)、[`workbench_request_lifecycle.py`](../../../web/bootstrap/workbench_request_lifecycle.py)）。

**启动与恢复的连接复用边界**：
- [`core/infrastructure/schema_structure.py:111`](../../../core/infrastructure/schema_structure.py#L111) 已完成声明表结构缓存，直接保持，无需再重复派发。
- 恢复启动检查（[`web/bootstrap/workbench_system_restore_recovery.py:23`](../../../web/bootstrap/workbench_system_restore_recovery.py#L23)）必须在打开任何业务数据库连接之前执行。
- 提取接收已打开数据库连接的核心 Schema/启动校验原语，供常规启动（[`web/bootstrap/factory.py:247-262`](../../../web/bootstrap/factory.py#L247-L262)）与系统恢复校验（[`core/services/system/backup_restore.py:66`](../../../core/services/system/backup_restore.py#L66)）各自管理连接生命周期并在同一连接内复用。
- 插件动态导入不进入 Schema 写锁，且严格保留 [`tests/app_runtime/test_plugins.py:58`](../../../tests/app_runtime/test_plugins.py#L58) 的 `telemetry_persisted` 提交语义。

监听端口以实际服务器返回地址为事实源，不先探测再假定绑定成功；普通停机先停止接收新工作，再等待 HTTP 与 worker 退出，最后关闭资源并释放自己拥有的锁。

### 7.3 恢复流程

恢复拥有者协调 `ready → draining → restoring → restart-required` 的业务阶段。进入恢复后阻止新业务，结束在途请求/运行，关闭连接，再执行文件替换与外部日志提交。

接受过恢复后必须重启进程，重新加载连接、永久引用、页面 token 和 worker 身份。恢复后的结果查询只读外部日志，不允许借查询重新受理业务。当前宿主已明确这套责任。[`workbench_system_restore.py:1`](../../../web/bootstrap/workbench_system_restore.py#L1)。

运行身份不明、维护日志 pending/不可读、停止屏障未完成时，留在明确的不可写状态并给可操作原因。这里的保护对应“错误进程/旧连接继续写库”的实际风险，应保留；不再由下层服务逐处猜测宿主是否已经停好。

## 8. 当前到目标的迁移清单

| 当前落点 | 目标动作 | 完成后退出的旧路径 | 主要消费者 |
|---|---|---|---|
| `resource / process / material / batch` 实例私有属性快照与 `_RawProcessFacts` | 显式事实作用域（Fact Scope）成为唯一读取所有者；公开 `PlanReadContext` 与账本读作用域 | `self` 11 属性备份还原、`__getitem__` 隐式跑 SQL、穿透私有 `_context`、测试断言私有 `_snapshot / _facts` | 资源、工艺、物料、批次、计划、报表及对应测试 |
| `preflight.py` 与 `batch/facts.py` 读取路径 | 读/预检事务最前先验轻量修订指纹；批次列表/详情/普通导出跳过全库 `workflow_snapshot`，单批操作只取目标批次完整关系闭包 | 先重算再验 `snapshot_stale`、非模板校验路径无条件构造全库 `workflow_snapshot` | 预检、批次列表/详情/导出/删除/改量/工艺同步 |
| `materials / resources / batches` 路由层手写 `capabilities / blocked_reasons` 及无用往返 | 领域层统一计算实体能力与阻断原因；删除 `WorkbenchEntityIdentity` `asdict()` 往返与 `workbench_command_repo` `canonical_json + json.loads` 往返 | 路由层分散手写规则、内部无用类型与 JSON 往返 | 物料、资源、批次单行/bulk/导入与命令仓储 |
| 全仓 7 条命令/任务/维护回执查询链路 | 抽离独立 `commands` 查询路由；普通/采用/校准/试调查询统一接入 `{state: "recorded" \| "not_observed", receipt, may_be_in_flight, resolution}` 包装原语 | `materials.py` 寄居路由、候选裸返 `receipt`、试调 `committed` 状态名、校准未命中 HTTP 404 `receipt_not_found` 特判及 `expect` 错址 | 前端全部命令会话、采用流程、校准、试调、排产与系统维护 |
| `app_new_ui.py`、`start_new_ui.bat`、`ui_mode` 与 `app.py` 顶层 `create_app()` | 退役双入口与 `ui_mode` 字段/检查；删除 `app.py` 顶层急切实例化；修复 `wufenchang_demo/builder.py` 失效参数；提取接收连接的启动校验原语 | `app_new_ui.py`、`start_new_ui.bat`、`ui_mode == "default"` 僵尸常量、顶层 import 副作用、`test_app_new_ui_create_app_smoke.py` | 启动器、健康检查、打包校验、五分厂构建脚本、运行时测试 |
| `core/models/workbench_*` 与 `architecture-invariants.mdc` | 明确输入合同与存储记录归属，实施完成时按目标职责同步更新规则文档 | 旧重导出别名、强制空继承/包根导出等过时要求 | routes、领域用例、测试与后续开发 |

## 9. 在线切换步骤与数据保全（0 格式转换）

由于数据库 Schema（版本 45）、业务表、归档 JSON、持久读模型、外部维护日志与 `WorkbenchCommandReceipts` 表均保持 **0 格式变更**，本次切换无需离线数据转换器，按以下在线停写切换流程执行：

1. **确定源集合与备份基线**：登记当前数据库路径、外部维护日志目录及配套文件，确认未误指测试副本；在停写窗口获取一致的数据库与维护日志备份副本作为恢复基点。
2. **停止旧进程与完成在途收敛**：停止接收新请求，等待在途 HTTP 请求退出，关闭旧进程并确认运行锁与数据库连接释放。浏览器本机 `pending` 记录保留原样（编码不变），严禁以清空浏览器存储或删除维护日志作为切换步骤。
3. **部署目标版本并启动单入口宿主**：安装目标代码与离线前端静态资产，从唯一入口启动目标进程。启动序列在打开数据库连接前先完成外部维护日志恢复检查（[`workbench_system_restore_recovery.py:23`](../../../web/bootstrap/workbench_system_restore_recovery.py#L23)），随后校验 Schema 45 合同并执行排产运行状态启动恢复（[`workbench_run_runtime.py:104`](../../../web/bootstrap/workbench_run_runtime.py#L104)）。
4. **未决命令按原 `request_key` 在线恢复结算**：浏览器加载新前端资产后，既有本机 `pending` 记录直接通过统一后的 7 条在线查询接口按原 `request_key` 查询结算：
   - 已提交的命令直接命中原 `WorkbenchCommandReceipts` 表记录，由读取出口包装返回 `state: "recorded"` 与原 `receipt` 完成本机结算；
   - 排产任务与系统维护操作分别通过 `GET /api/workbench/v1/scheduling/requests/<request_key>` 与 `GET /api/workbench/v1/system/results/<request_key>`（含 `SystemMaintenanceJournal`）按既有权威记录恢复终态。
5. **回退分界**：开放新业务写入前，若验收异常可直接切回原程序与备份基线；开放新写入后，原备份已缺少新业务事实，禁止直接拿旧库覆盖当前库，优先前向修复代码。

## 10. 验收矩阵与交付退出条件

| 应证明的行为 | 优先复用的现有测试/证据 | 本次迁移关注点 |
|---|---|---|
| 同意图重放、同键异意图拒绝、回执失败整事务回滚与 7 条查询链路统一 | `tests/workbench/test_commands.py`、各采用/试调/校准/排产/系统查询测试 | 7 条 lookup 链路统一返回结构与原 `request_key` 保留；校准未命中返回 200 `not_observed`；落盘回执格式 0 变更 |
| 显式事实作用域与三种事务生命周期 | `test_process_file_api_transactions.py`、`test_material_snapshot_facts.py`、`test_batch_actions.py`、`test_batch_list_summary.py` | 无实例私有属性偷渡与 `__getitem__` 隐式 SQL；前置验轻量修订指纹；批次按需跳过 `workflow_snapshot` 并加载目标批次完整关系闭包 |
| 候选/试调正式采用原子性 | `test_run_candidate_adoption_atomic.py`、`test_trial_adoption_atomic.py` | 正式版本/任务/回执同事务；执行事实变化拒绝采用 |
| 排产受理和终态一致 | `test_run_jobs_atomic.py` | 单意图不重复运行，保存前源事实复核，异常不会发布半份候选 |
| 归档与快照准入 | `test_stored_snapshot_validation.py` | 原归档与读模型 0 格式变更直接读取；损坏不补空值 |
| 恢复日志、启动连接复用与单入口宿主 | `test_system_maintenance_restore.py`、`test_plugins.py`、`app.py` 运行时测试 | `app_new_ui.py` 与 `ui_mode` 清零；`app.py` 无顶层实例化副作用；恢复检查早于连库；插件动态导入不进 Schema 写锁 |
| 前端持久化失败后的完整会话 | `storage_write_contract.cjs` 及真实界面操作 | 终态不退回 `pending`，重查/finish/刷新遵循同一来源 |
| Win7 启动、换端口、锁与停止 | `test_launcher_startup.py`、`test_runtime_server_binding.py`、`test_runtime_db_scope_lock.py` | 原生执行与目标包现场验收；新包不依赖开发机工具 |

目前登记的 **15个Windows启动器节点、5个Windows独占监听节点** 仍是目标环境待验，开发重载另有用例；实施不能把平台skip当通过。[台账:1920—1923](../../../开发文档/技术债务治理台账.md#L1920)。

本专题完成的信号是：持久存储保持 0 格式变更；各域通过显式事实作用域与按需关系闭包读取数据，彻底消除实例属性偷渡和全库无条件重型构造；全仓 7 条回执与结果查询链路口径统一；`app_new_ui.py`、`ui_mode` 与 `app.py` 顶层实例化副作用全部退出。

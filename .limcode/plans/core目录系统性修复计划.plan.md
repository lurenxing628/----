<!-- LIMCODE_SOURCE_ARTIFACT_START -->
{"type":"review","path":".limcode/review/阶段7_综合总结与交叉审查.md","contentHash":"sha256:6b7c4d61d9f6baa7736028cfc1a906a93a1ae20bedc8625651abed67eb573f1f"}
<!-- LIMCODE_SOURCE_ARTIFACT_END -->

## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [ ] 建立字段语义矩阵与处理边界（写入必填/写入可空/兼容读取/内部合同）  `#s0-1`
- [ ] 新建 `strict_parse.py` 严格解析层，旧 `parse_finite_*` 改为兼容门面  `#s0-2`
- [ ] 新建统一退化事件模型、收集器与兼容读取封装  `#s0-3`
- [ ] 为读侧构建器引入轻量结果封套 `BuildOutcome`，禁止新增裸元组退化返回  `#s0-4`
- [ ] 第零段配套回归测试  `#s0-test`
- [ ] 修复 `parse_finite_float/int` 空白语义并核查 `allow_none=False` 调用点  `#s1-1`
- [ ] 禁止供应商默认周期静默写 `1.0`  `#s1-2`
- [ ] 禁止外协周期编辑静默写 `1.0`  `#s1-3`
- [ ] 恢复空行动保险丝：在主链真实计算 `has_actionable_schedule`  `#s1-4`
- [ ] 批次更新禁止改图号但不重建工序  `#s1-5`
- [ ] 展示层坏时间过滤改为 `BuildOutcome` 并透出统一退化事件  `#s1-6`
- [ ] 资源排班导出复用统一退化事件与计数  `#s1-7`
- [ ] 第一段配套回归测试  `#s1-test`
- [ ] 迁移配置快照、优化器、算法参数、输入构建中的重复数值解析实现到公共入口  `#s2-1`
- [ ] 排产输入构建按字段语义矩阵贯穿严格语义  `#s2-2`
- [ ] 冻结窗口修正为失败关闭，摘要不再误报已生效硬约束  `#s2-3`
- [ ] 模板/外部组缺失进入结构化退化事件，严格模式下阻断  `#s2-4`
- [ ] `active_preset` 与真实配置同步  `#s2-5`
- [ ] 第二段配套回归测试  `#s2-test`
- [ ] 算法层坏交期与未排批次显式计入指标  `#s3-1`
- [ ] 外协周期默认 `1.0` 仅保留为历史兼容读取并计数留痕  `#s3-2`
- [ ] 甘特日历失败通过统一退化事件透传  `#s3-3`
- [ ] 恢复链 `RestoreResult.code` 改为“已复制待校验”语义  `#s3-4`
- [ ] 系统配置脏值标记：`SystemConfigSnapshot` 增加 `dirty_fields`  `#s3-5`
- [ ] 预热失败与插件启动留痕失败纳入统一退化外显  `#s3-6`
- [ ] 第三段配套回归测试  `#s3-test`
- [ ] 建批模板补建纳入同一事务  `#s4-1`
- [ ] 全局日历确认链收口到公共执行器  `#s4-2`
- [ ] `schedule_service.py` 主链拆分并保留现有对外接口  `#s4-3`
- [ ] 归一化矩阵统一（收敛 common/route/service 重复实现）  `#s4-4`
- [ ] 插件层配置读取改为注入接口，移除对服务/仓储的反向依赖  `#s4-5`
- [ ] 第四段配套回归测试  `#s4-test`
<!-- LIMCODE_TODO_LIST_END -->

## 修订目标
本次修订不是把原有问题清单简单扩容，而是把本 plan 升级为一份“共享合同先行、逐段落地、避免一次性推倒重来”的根治方案。目标有四个：

1. **新写路径不再制造脏语义**：用户输入、导入确认、服务写入中的坏值不再被静默改写成业务默认值。
2. **旧脏数据只允许通过显式退化通道读取**：兼容读取可以保留，但必须留痕、计数、对外可见。
3. **同类问题只修一次**：数值解析、归一化、退化透传、构建结果返回方式各自统一，不再每层重复造轮子。
4. **不做破坏性重建**：保留 `ScheduleService`、现有主要路由、主要页面契约，对外接口优先采用“新增字段、保留旧名、内部渐进迁移”的方式演进。

---

## 治理原则
1. **写入严格，读取兼容但必须显式退化**：新写入一律不允许静默补业务值；仅历史存量脏数据读取可走兼容路径。
2. **解析与退化留痕分离**：解析函数只负责“返回合法值或抛错”；兼容读取层才负责默认值、计数、告警和摘要透传。
3. **内部合同违约视为 BUG**：进入算法层、编排层、持久化层的中间值，默认已被上游校验；若仍坏，优先暴露问题，不再层层再兜底。
4. **退化必须跨两条通道可见**：任一退化至少同时进入“日志+摘要 / 摘要+页面 / 页面+导出”中的两条，不允许只记日志。
5. **小步收口，保留门面**：允许为旧函数保留一层薄门面，但门面内部必须委托到统一实现，不能长期双轨演进。

---

## 根治性补强：先统一共享合同，再修各条链路

### 一、字段语义矩阵：先定义“什么该报错，什么可退化”
原 plan 的方向是对的，但“报错还是告警”在若干位置仍偏模糊。根治的关键不是多写几个判断，而是先把字段按语义分层：

| 类别 | 典型来源 | 空白/缺失 | 非法/非有限 | 是否允许默认化 | 处理原则 |
| --- | --- | --- | --- | --- | --- |
| 写入必填 | 页面表单、导入确认、编辑接口中的业务必填字段 | 直接报错 | 直接报错 | 不允许 | 失败即失败 |
| 写入可空 | 备注、可选说明、明确允许留空的业务字段 | 返回 `None` | 报错 | 不允许偷偷补业务值 | 只表达“未填写” |
| 兼容读取 | 历史配置、旧排程、旧模板、展示读侧 | 可回退为 `default` 或 `None` | 可回退，但必须记退化事件 | 仅限读侧 | 退化必须可见 |
| 内部合同 | 进入算法、编排、持久化前的中间值 | 视为 BUG | 视为 BUG | 不允许 | 直接暴露或边界阻断 |

**首批纳入矩阵的关键字段**：
- `default_days`
- 外协工序 `ext_days`
- `setup_hours` / `unit_hours`
- `priority_weight` / `due_weight` / `ready_weight`
- `freeze_window_days`
- `due_date`
- 展示层 `start_time` / `end_time`

该矩阵将落地为公共配置，而不是只写在文档里。所有调用方先引用矩阵，再决定“报错/返回 `None`/兼容回退”，不再各自临场发挥。

### 二、统一退化事件合同：不再让每个模块自己发明一套告警格式
新增公共模块：`core/services/common/degradation.py`

建议最小模型：
```python
@dataclass(frozen=True)
class DegradationEvent:
    code: str
    scope: str
    field: str | None
    message: str
    count: int = 1
    sample: str | None = None
```

配套新增：
- `DegradationCollector`：统一收集、去重、计数、合并；
- 原因码约定：如 `blank_required`、`invalid_number`、`bad_time_row_skipped`、`calendar_load_failed`、`legacy_external_days_defaulted`、`freeze_seed_unavailable`；
- 摘要映射器：把退化事件汇入排产摘要；
- 页面映射器：把退化事件转为前端可展示提示；
- 导出映射器：把退化事件转为导出摘要键值对。

**硬性要求**：
- 以后不允许新增“只在日志里拼一句中文”的退化处理；
- 以后不允许新增“只返回一个字符串错误消息”的临时接口；
- 退化事实必须经过 `DegradationCollector` 统一汇总。

### 三、统一结果封套：不再新增裸元组退化返回
原 plan 中 `build_tasks() -> (items, skipped_count)` 这一思路是止血有效的，但长期看仍会形成新的多套返回协议。更优雅的做法是：

新增轻量封套：`BuildOutcome[T]`
```python
@dataclass
class BuildOutcome(Generic[T]):
    value: T
    events: list[DegradationEvent] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)

    @property
    def degraded(self) -> bool:
        return bool(self.events or self.counters)
```

**使用范围**：
- 首批只用于“读侧构建器”和“展示构建器”，包括：
  - `core/services/scheduler/gantt_tasks.py`
  - `core/services/scheduler/gantt_week_plan.py`
  - `core/services/scheduler/resource_dispatch_rows.py`
  - `build_calendar_days()`
- 对已有明确领域对象，不强制一刀切改成 `BuildOutcome`，但其退化信息必须统一用 `DegradationEvent` 表达。
- 这样既统一了退化合同，又避免大规模破坏性重写。

### 四、渐进迁移策略：不做大拆大建，但必须有统一落点
1. **先建公共合同**：字段矩阵、严格解析、兼容读取、退化事件、结果封套先落地。
2. **再改高风险链路**：供应商、外协周期、排产输入、冻结窗口、展示过滤、恢复链、配置脏值。
3. **最后收口结构**：`schedule_service.py` 拆分、日历确认链收口、插件层反向依赖移除、归一化矩阵统一。
4. **保持外部接口稳定**：
   - 服务类对外方法名尽量不改；
   - 路由响应优先新增可选字段，不重命名既有字段；
   - 旧解析函数保留一层兼容门面，但门面内部必须转调新实现。

---

## 第零段：治理底座先行（轻量公共合同，不改大结构）

### 0.1 建字段语义矩阵
**文件**：新建 `core/services/common/value_policies.py`

**修复方案**：
- 定义字段策略枚举，例如：`required_write`、`optional_write`、`compat_read`、`internal_contract`。
- 为关键字段建立首批映射表，至少覆盖排产主链、供应商配置、系统配置、展示时间字段。
- 所有公共解析入口都必须接收或推导字段策略，不再由调用方各自决定“遇到空白时返回 0、1、None 还是报错”。

### 0.2 建严格解析层
**文件**：新建 `core/services/common/strict_parse.py`

**修复方案**：
- 定义严格解析函数，只负责“返回合法值或抛 `ValidationError`”，不做默认化、不做日志、不做计数。
- 首批提供：
  - `parse_required_float()`
  - `parse_optional_float()`
  - `parse_required_int()`
  - `parse_optional_int()`
- `core/services/common/number_utils.py` 中的 `parse_finite_float/int` 暂时保留，但内部改为委托新入口，作为兼容门面。

### 0.3 建兼容读取层与统一退化事件收集器
**文件**：新建 `core/services/common/compat_parse.py`、`core/services/common/degradation.py`

**修复方案**：
- 兼容读取层只用于读历史数据、旧配置、旧模板、展示层脏记录。
- 在兼容读取层中：
  - 捕获严格解析抛出的异常；
  - 按字段矩阵回退为 `default` 或 `None`；
  - 同时向 `DegradationCollector` 记录统一退化事件。
- 禁止在服务层、算法层、路由层继续散落 `_safe_float()`、`_cfg_float()`、`_get_float()` 之类的局部实现。

### 0.4 为读侧构建器引入轻量结果封套
**文件**：新建 `core/services/common/build_outcome.py`

**修复方案**：
- 提供 `BuildOutcome[T]`，用于“主结果 + 退化事件 + 计数”的统一返回。
- 首批接入甘特、周计划、资源排班、日历加载四条高风险读链。
- 明确禁止新增 `(items, skipped_count)`、`(data, error_message)` 这类裸元组返回。

---

## 第一段：立即止血（先阻断继续制造错误语义）

### 1.1 修复 `parse_finite_float/int` 空白返回 `0/0.0` 的语义
**文件**：`core/services/common/number_utils.py`

**修复方案**：
- `allow_none=False` 时，空白/`None` 直接抛 `ValidationError`；
- `allow_none=True` 时才允许返回 `None`；
- 所有 `allow_none=False` 调用点逐一核查，并按字段语义矩阵归类；
- 不允许通过临时 `or 0`、`or 1`、`or "1"` 再补回旧行为。

### 1.2 禁止供应商默认周期静默写 `1.0`
**文件**：`core/services/process/supplier_service.py`、`web/routes/process_suppliers.py`

**修复方案**：
- 删除路由层 `or "1"` 兜底；
- `default_days` 在写入路径上按“写入必填”处理：空白直接报错；
- 非法值直接报错，不再回退到 `1.0`；
- 删除不再有意义的“默认值回退日志”分支；
- 若需要兼容读取历史脏值，统一放到读侧兼容层，不留在写入链。

### 1.3 禁止外协周期编辑静默写 `1.0`
**文件**：`core/services/scheduler/operation_edit_service.py`

**修复方案**：
- 外协工序编辑中，用户清空 `ext_days` 时直接报错；
- 删除 `dv = 1.0` 兜底；
- 外协与非外协工序分别按字段矩阵处理，避免继续混用“可空”语义。

### 1.4 恢复空行动保险丝的真实计算
**文件**：`core/services/scheduler/schedule_service.py`

**修复方案**：
- 在调用 `persist_schedule()` 前真实计算是否存在可落库的有效排程行；
- 不再硬编码 `has_actionable_schedule=True`；
- 把“无可重排工序”“全冻结”“优化器返回但无有效排程行”三种场景区分编码，避免混成同一类失败。

### 1.5 批次更新禁止“改图号但不重建工序”
**文件**：`core/services/scheduler/batch_excel_import.py`

**修复方案**：
- 更新已有批次时，如果 `part_no` 变化且 `auto_generate_ops=False`，直接报错；
- 错误消息明确提示“启用自动生成工序后重试”；
- 先止血拒绝，后续在第四段再把模板补建与重建纳入统一事务。

### 1.6 展示层坏时间行过滤改为统一结果封套
**文件**：
- `core/services/scheduler/gantt_tasks.py`
- `core/services/scheduler/gantt_week_plan.py`
- `core/services/scheduler/resource_dispatch_rows.py`

**修复方案**：
- 不再返回裸列表，也不再返回裸元组；
- 统一返回 `BuildOutcome[...]`；
- 坏时间行被过滤时，写入统一退化事件 `bad_time_row_skipped`，并记录计数；
- 若全部结果都被过滤，必须返回“退化空结果”，不能继续伪装成普通空状态。

### 1.7 资源排班导出复用统一退化事件
**文件**：`core/services/scheduler/resource_dispatch_excel.py`

**修复方案**：
- 导出摘要不再自行维护另一套键值逻辑；
- 直接消费 `BuildOutcome` / `DegradationCollector` 中的退化事件与计数；
- 与页面保持同一口径，至少覆盖：坏时间过滤、超期标记退化、推断日历使用中。

---

## 第二段：严格合同贯通与硬约束纠偏

### 2.1 迁移重复数值解析实现到公共入口
**文件**：
- `core/services/common/number_utils.py`
- `core/services/scheduler/config_snapshot.py`
- `core/services/scheduler/schedule_optimizer.py`
- `core/algorithms/greedy/schedule_params.py`
- `core/services/scheduler/schedule_input_builder.py`

**修复方案**：
- 删除本地 `_safe_float()`、`_cfg_float()`、`_get_float()` 等重复实现；
- 统一改为调用 `strict_parse.py` 与 `compat_parse.py`；
- 解析函数不再直接记日志或拼摘要，退化留痕全部通过 `DegradationCollector`。

### 2.2 排产输入构建按字段矩阵贯穿严格语义
**文件**：`core/services/scheduler/schedule_input_builder.py`

**修复方案**：
- `build_algo_operations()` 显式接收严格模式开关；
- 每个字段先映射到字段策略矩阵，再决定是报错、返回 `None`，还是兼容读取；
- 重点规则：
  - `setup_hours`、`unit_hours`：新写路径必须合法；兼容读取时可回退，但必须留事件；
  - 外协工序 `ext_days`：外协时为业务必填，非外协时才允许无值；
  - 模板缺失、外部组缺失不再静默清空组合并信息。
- 返回值改为带退化信息的结果对象，而不是“列表 + 局部字符串告警”。

### 2.3 冻结窗口改为“失败关闭”，摘要据实反映
**文件**：`core/services/scheduler/freeze_window.py`、`core/services/scheduler/schedule_summary.py`

**修复方案**：
- 冻结种子加载失败、时间无效、前缀缺失时，统一产生 `freeze_seed_unavailable` 退化事件；
- 严格模式下直接阻断排产；
- 非严格模式下允许继续，但摘要不得再把冻结窗口列为已生效硬约束；
- 页面、历史、摘要至少两处可见“冻结未生效”。

### 2.4 模板 / 外部组缺失进入结构化退化事件
**文件**：`core/services/scheduler/schedule_input_builder.py`、`core/services/scheduler/schedule_template_lookup.py`

**修复方案**：
- 模板缺失、`ext_group_id` 失配时，不再只是把相关字段置空；
- 统一记录 `template_missing`、`external_group_missing` 事件；
- 严格模式下直接失败；
- 非严格模式下继续，但摘要与页面必须能看到“组合并信息已退化”。

### 2.5 `active_preset` 与真实配置同步
**文件**：`core/services/scheduler/config_service.py`

**修复方案**：
- 所有 `set_*` 写接口执行时，统一把 `active_preset` 切换为 `custom`；
- 若应用预设时发生退化或校正，不得继续保留原预设名；
- 必要时补充“当前为自定义配置”的原因说明，避免元数据继续漂移。

---

## 第三段：退化可见性贯通（把读侧兼容从“吞掉”改成“留痕”）

### 3.1 算法层坏交期与未排批次显式计入指标
**文件**：`core/algorithms/greedy/date_parsers.py`、`core/algorithms/evaluation.py`

**修复方案**：
- 在评估层新增：
  - `invalid_due_count`
  - `unscheduled_batch_count`
- 坏交期不再仅仅等价为“无交期”；
- 未完工批次不再从指标中完全消失；
- 这些统计自动流入摘要与历史。

### 3.2 外协周期默认 `1.0` 仅保留为历史兼容读取
**文件**：
- `core/algorithms/greedy/external_groups.py`
- `core/algorithms/greedy/dispatch/sgs.py`

**修复方案**：
- 新写路径已在第一段彻底禁止再制造该状态；
- 算法层若因历史脏数据仍读到空白外协周期，可暂时回退为 `1.0`，但必须记录 `legacy_external_days_defaulted` 事件与计数；
- 严格模式下不允许继续走该兼容分支；
- 后续以数据清理和读侧退化提示逐步消除这条兼容链。

### 3.3 甘特日历失败通过统一退化事件透传
**文件**：`core/services/scheduler/gantt_tasks.py`

**修复方案**：
- `build_calendar_days()` 不再返回裸数组或裸字符串；
- 改为返回带退化事件的结果对象；
- 失败时记录 `calendar_load_failed`，并由前端显示“正在使用推断日历”；
- 不再让“后端空数组 + 前端默认周末规则”继续伪装成正常业务语义。

### 3.4 恢复链返回“已复制待校验”语义
**文件**：`core/infrastructure/backup.py`

**修复方案**：
- `RestoreResult.code` 区分：
  - `copied_pending_verify`
  - `verified`
- `restore()` 在仅完成复制时不得宣称完全成功；
- 保留路由层 `ensure_schema()` 的位置，但语义必须与返回码一致。

### 3.5 系统配置脏值标记
**文件**：`core/services/system/system_config_service.py`

**修复方案**：
- `SystemConfigSnapshot` 增加 `dirty_fields`；
- 数值回退、钳制、格式纠正时，把字段名记录进 `dirty_fields`；
- 页面渲染对这些字段加显式提示；
- 读侧兼容不再伪装成“本来就合法”。

### 3.6 预热失败与插件启动留痕失败纳入统一外显
**文件**：
- `core/services/scheduler/schedule_optimizer_steps.py`
- `web/bootstrap/plugins.py`
- `core/plugins/manager.py`

**修复方案**：
- 预热失败不再只写日志，必须进入统一退化事件管道；
- 插件启动留痕失败不得被吞掉，至少在系统页面或操作日志中可见；
- 这两条链与页面、摘要、导出统一使用同一套退化原因码与映射方式。

---

## 第四段：中期结构收口（不推倒重来，但消除重复规则与边界泄漏）

### 4.1 建批模板补建纳入同一事务
**文件**：`core/services/scheduler/batch_service.py`

**修复方案**：
- 将 `_load_template_ops_with_fallback()` 拆为“检查”与“写入”两步；
- 事务外只做只读检查；
- 如需自动补建模板，必须与批次创建、工序重建处于同一事务中；
- 彻底收住“模板先被改写、批次却创建失败”的副作用泄漏。

### 4.2 全局日历确认链收口到公共执行器
**文件**：`web/routes/scheduler_excel_calendar.py`

**修复方案**：
- 实现适配层，让全局日历确认链也走 `execute_preview_rows_transactional()`；
- 删除本地自维护事务、计数、循环写入逻辑；
- 让日历确认链自动继承公共执行器的结果合同与错误语义。

### 4.3 `schedule_service.py` 主链拆分，但保持对外接口不变
**目标文件**：
- 新建 `schedule_input_collector.py`
- 新建 `schedule_orchestrator.py`
- 复用现有 `schedule_persistence.py`
- 复用现有 `schedule_summary.py`

**修复方案**：
- 维持 `ScheduleService` 的外部入口不变；
- 内部拆成“输入收集 / 编排 / 落库 / 摘要”四块；
- 退化事件在内部统一沿用 `DegradationCollector` 透传，不再让每个阶段各自拼摘要。

### 4.4 归一化矩阵统一
**文件**：
- `core/services/common/excel_validators.py`
- `web/routes/normalizers.py`
- `core/services/scheduler/calendar_admin.py`
- `core/services/personnel/operator_machine_normalizers.py`

**修复方案**：
- 在 `core/services/common/` 下新建 `normalization_matrix.py`；
- 统一维护文本归一化、枚举映射、空白处理规则；
- 各消费方只引用矩阵，不再复制实现。

### 4.5 插件层配置读取改为注入接口，移除对服务 / 仓储的反向依赖
**文件**：`core/plugins/manager.py`、`web/bootstrap/plugins.py`

**修复方案**：
- 通过注入接口向插件层提供只读配置能力；
- 插件层不再直接依赖服务层和仓储层；
- 保持现有插件装载流程不大改，但消除底座层被上层污染的问题。

---

## 第五段：回归测试补充

### 第零段配套测试
| 测试文件 | 覆盖场景 |
| --- | --- |
| `test_value_policy_matrix.py` | 字段矩阵对关键字段的策略归类固定 |
| `test_strict_parse_contract.py` | 严格解析对空白、非法、非有限值的统一行为 |
| `test_compat_parse_degradation_contract.py` | 兼容读取回退时产生统一退化事件 |
| `test_build_outcome_contract.py` | `BuildOutcome` 的事件、计数、退化判定合同 |

### 第一段配套测试
| 测试文件 | 覆盖场景 |
| --- | --- |
| `test_number_utils_empty_strict.py` | `parse_finite_float("", allow_none=False)` 必须报错 |
| `test_supplier_no_silent_default_days.py` | 创建/更新供应商时空白默认周期必须报错 |
| `test_operation_edit_no_silent_ext_days.py` | 外协工序编辑空白周期必须报错 |
| `test_persist_actionable_fuse_real.py` | `has_actionable_schedule` 真实计算 |
| `test_batch_import_part_no_change_guard.py` | 改图号但不重建工序必须报错 |
| `test_display_build_outcome_bad_time.py` | 坏时间行过滤后通过 `BuildOutcome` 返回退化信息 |
| `test_dispatch_export_degradation_info.py` | 导出文件与页面共享同一退化口径 |

### 第二段配套测试
| 测试文件 | 覆盖场景 |
| --- | --- |
| `test_duplicate_numeric_parsers_converged.py` | 各处重复数值解析已收敛到公共入口 |
| `test_input_builder_policy_matrix.py` | 输入构建按字段矩阵处理空白/非法值 |
| `test_freeze_window_fail_close.py` | 冻结加载失败 + 严格模式 → 阻断排产 |
| `test_freeze_summary_no_misreport.py` | 冻结降级时摘要不列为已生效硬约束 |
| `test_template_missing_degradation_event.py` | 模板/外部组缺失时产生结构化退化事件 |
| `test_active_preset_sync.py` | 手工修改配置后 `active_preset` 变为 `custom` |

### 第三段配套测试
| 测试文件 | 覆盖场景 |
| --- | --- |
| `test_metrics_invalid_due_count.py` | 坏交期批次被统计为 `invalid_due_count` |
| `test_metrics_unscheduled_batch_count.py` | 未排批次被统计为 `unscheduled_batch_count` |
| `test_external_days_default_counter.py` | 历史脏数据触发外协周期兼容回退时计数递增 |
| `test_calendar_days_error_passthrough.py` | 日历加载失败产生统一退化事件 |
| `test_restore_code_pending_verify.py` | 恢复返回 `copied_pending_verify` |
| `test_system_config_dirty_fields.py` | 脏值钳制后 `dirty_fields` 非空 |
| `test_warmstart_plugin_degradation_visibility.py` | 预热失败与插件留痕失败进入统一外显通道 |

### 第四段配套测试
| 测试文件 | 覆盖场景 |
| --- | --- |
| `test_batch_template_autoparse_transactional.py` | 模板补建与建批处于同一事务 |
| `test_calendar_confirm_uses_executor.py` | 全局日历确认链复用公共执行器 |
| `test_schedule_service_split_contract.py` | `ScheduleService` 对外接口保持不变 |
| `test_normalization_matrix_contract.py` | 归一化矩阵被多处调用方共享 |
| `test_plugin_manager_injected_config_reader.py` | 插件层通过注入接口读取配置 |

---

## 实施顺序与依赖关系

```text
第零段（共享合同）
  ├─ 0.1 字段语义矩阵
  ├─ 0.2 严格解析层
  ├─ 0.3 兼容读取 + 退化事件收集
  └─ 0.4 结果封套
          ↓
第一段（立即止血）
  ├─ 1.1 parse_finite_* 空白语义
  ├─ 1.2 供应商默认周期
  ├─ 1.3 外协周期编辑
  ├─ 1.4 空行动保险丝
  ├─ 1.5 改图号保护
  ├─ 1.6 展示层坏时间过滤
  └─ 1.7 导出退化口径统一
          ↓
第二段（严格合同贯通）
  ├─ 2.1 重复解析实现收口
  ├─ 2.2 输入构建按字段矩阵处理
  ├─ 2.3 冻结窗口失败关闭
  ├─ 2.4 模板/外部组缺失退化可见
  └─ 2.5 active_preset 同步
          ↓
第三段（退化可见性贯通）
  ├─ 3.1 坏交期/未排批次指标
  ├─ 3.2 外协周期历史兼容计数
  ├─ 3.3 甘特日历退化透传
  ├─ 3.4 恢复链语义修正
  ├─ 3.5 系统配置脏值标记
  └─ 3.6 预热/插件退化外显
          ↓
第四段（结构收口）
  ├─ 4.1 建批事务边界
  ├─ 4.2 日历执行器收口
  ├─ 4.3 schedule_service 拆分
  ├─ 4.4 归一化矩阵统一
  └─ 4.5 插件层去反向依赖
```

**关键依赖**：
- 1.1、2.1、2.2 都依赖第零段的严格解析与字段矩阵先落地；
- 1.6、1.7、3.3、3.6 都依赖统一退化事件合同；
- 4.3 的拆分必须放在前三段语义稳定之后；
- 4.5 不要求重写插件框架，只做依赖方向纠偏。

---

## 风险控制
1. **不一次性替换全仓解析函数**：旧函数保留薄门面一轮，但必须转调新实现，防止双轨逻辑长期共存。
2. **对外接口优先增量兼容**：页面与接口优先新增退化字段，不立即改名删字段，降低联动风险。
3. **退化原因码稳定、异常细节受控**：对外展示使用稳定原因码与用户可理解提示，不直接泄漏底层异常全文。
4. **写入严格与读取兼容的边界必须由测试锁死**：尤其是 `default_days`、`ext_days`、`setup_hours`、`unit_hours`、`due_date`。
5. **读侧退化不替代数据治理**：第三段保留的兼容路径只服务历史存量，不得被新写路径复用。
6. **结构拆分先保接口、后换内部**：`ScheduleService`、日历确认链、插件装载链均通过“门面不变、内部替换”推进，不做大规模破坏性重建。

---

## 验收标准
1. 新写路径中不再出现把空白业务值静默改写成 `0`、`0.0`、`1.0`、`"1"` 的行为。
2. 兼容读取产生的退化事实，至少能在两条通道中看到。
3. 严格模式的含义被收口为“拒绝坏值”，而不是“部分字段严格、其余字段继续默认化”。
4. 展示层与导出层对同一批退化事实使用同一口径，不再出现页面知道、导出不知道的情况。
5. 主链和插件层不再新增局部 `_safe_*`、`except Exception: return []`、裸字符串告警等防御性分支。
6. `ScheduleService` 等主要外部入口保持兼容，重构工作集中在内部实现与共享合同上。

---

## 预期收益
- 对用户：坏值不再被包装成“看起来正常”的业务结果，页面与导出能明确提示退化。
- 对开发：同类解析、退化、归一化逻辑不再多处复制，后续修改只改一处。
- 对运维：恢复、预热、插件启动、冻结窗口等关键链路的成功与退化边界更清晰。
- 对后续重构：先把合同收稳，再拆大文件，能明显降低重构期回归风险。

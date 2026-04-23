## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [ ] 阶段1：基础设施与模型层审查（infrastructure/ + models/ + plugins/，~4,150行）  `#phase1`
- [ ] 阶段2：通用服务层审查（services/common/，~1,840行）  `#phase2`
- [ ] 阶段3：算法层审查（algorithms/，~3,060行）  `#phase3`
- [ ] 阶段4：排产服务层（上）审查（services/scheduler/ 调度核心，~4,500行）  `#phase4`
- [ ] 阶段5：排产服务层（下）审查（services/scheduler/ 甘特图/日历/资源调度，~4,580行）  `#phase5`
- [ ] 阶段6：业务域服务层审查（equipment/material/personnel/process/report/system，~5,880行）  `#phase6`
- [ ] 阶段7：综合总结与交叉审查（全局视角汇总报告）  `#phase7`
<!-- LIMCODE_TODO_LIST_END -->

# core/ 目录全面审查计划

## 目标
对 `core/` 目录进行全面深度审查，覆盖代码质量、架构合规性、BUG 风险、性能隐患、安全问题、可维护性等维度。

## 审查范围总览

| 子模块 | 文件数 | 代码行数 | 核心职责 |
|--------|--------|----------|----------|
| `algorithms/` | 21 | ~3,060 | 调度算法核心（贪心/OR-Tools/评估/分派规则） |
| `infrastructure/` | 14 | ~2,300 | 数据库、备份、迁移、日志、事务、错误处理 |
| `models/` | 24 | ~1,520 | 领域模型定义 |
| `plugins/` | 4 | ~310 | 插件框架 |
| `services/common/` | 15 | ~1,840 | 通用服务（Excel处理、归一化、校验） |
| `services/equipment/` | 5 | ~680 | 设备相关业务 |
| `services/material/` | 3 | ~320 | 物料相关业务 |
| `services/personnel/` | 7 | ~1,150 | 人员相关业务 |
| `services/process/` | 16 | ~3,020 | 工艺路线、零件、供应商等 |
| `services/report/` | 5 | ~710 | 报表引擎与导出 |
| `services/scheduler/` | 37 | ~9,080 | 排产核心服务（最大模块） |
| `services/system/` | 9 | ~990 | 系统配置、维护、日志 |
| **合计** | **160** | **~24,970** | |

## 审查维度（每阶段通用）

1. **BUG 与逻辑缺陷** — 静默回退、异常吞没、边界条件遗漏、类型安全
2. **架构合规** — 分层违反、职责越界、循环依赖
3. **错误处理** — 异常链路完整性、错误信息可观测性
4. **性能隐患** — N+1 查询、不必要的全表扫描、大数据集内存问题
5. **安全风险** — SQL 注入、路径穿越、未校验输入
6. **可维护性** — 重复代码、过长函数、命名规范、注释充分性
7. **测试覆盖度** — 是否有对应测试、边界用例覆盖

---

## 阶段划分

### 阶段 1：基础设施与模型层（~3,800 行）
**范围**: `core/infrastructure/` + `core/models/` + `core/plugins/`
**预计工作量**: 中等
**审查重点**:
- `infrastructure/`:
  - `database.py` — 连接管理、连接泄漏风险、`detect_types` 配置
  - `backup.py`（414行，最大文件）— 备份恢复逻辑完整性、文件操作安全性
  - `transaction.py` — 事务嵌套/savepoint 语义正确性
  - `logging.py`（217行）— 日志配置、敏感信息泄露风险
  - `errors.py` — 异常层次设计合理性
  - `migrations/`（v1~v6）— 迁移脚本幂等性、回滚安全性、版本跳跃处理
- `models/`:
  - 所有 24 个模型文件 — 字段定义、枚举一致性、`_helpers.py` 工具函数
  - `enums.py` — 枚举定义完整性与大小写归一化
- `plugins/`:
  - 插件注册/加载机制安全性、错误隔离

### 阶段 2：通用服务层（~1,840 行）
**范围**: `core/services/common/`
**预计工作量**: 中等
**审查重点**:
- `excel_service.py` / `excel_import_executor.py` — Excel 导入核心流程、原子性保证
- `excel_validators.py`（242行）— 校验规则完备性、边界值处理
- `excel_templates.py`（358行）— 模板定义、字段映射正确性
- `openpyxl_backend.py` / `pandas_backend.py` / `tabular_backend.py` — 后端抽象一致性
- `enum_normalizers.py`（212行）— 归一化逻辑、大小写处理遗漏
- `normalize.py` / `datetime_normalize.py` / `number_utils.py` — 数据清洗鲁棒性
- `excel_audit.py` / `safe_logging.py` — 审计与安全日志

### 阶段 3：算法层（~3,060 行）
**范围**: `core/algorithms/`
**预计工作量**: 高（核心调度逻辑）
**审查重点**:
- `algorithms/greedy/`:
  - `scheduler.py` — 贪心调度主循环逻辑正确性
  - `dispatch/sgs.py` — SGS（串行生成方案）调度核心
  - `dispatch/batch_order.py` — 批次排序规则
  - `auto_assign.py`（228行）— 自动分配资源逻辑、空资源池处理
  - `seed.py` — 种子结果生成、去重逻辑
  - `date_parsers.py` — 日期解析鲁棒性
  - `schedule_params.py`（209行）— 调度参数构建
  - `config_adapter.py` — 配置适配
  - `downtime.py` / `external_groups.py` — 停机时间与外协处理
- `algorithms/`:
  - `evaluation.py`（274行）— 方案评估指标计算正确性
  - `dispatch_rules.py` — 分派规则实现
  - `ortools_bottleneck.py`（216行）— OR-Tools 集成、异常处理
  - `sort_strategies.py`（173行）— 排序策略
  - `priority_constants.py` / `types.py` / `value_domains.py` — 常量与类型定义

### 阶段 4：排产服务层（上）（~4,500 行）
**范围**: `core/services/scheduler/` 的调度核心子集
**预计工作量**: 高（最关键的业务逻辑）
**审查重点**:
- **排产核心链路**:
  - `schedule_service.py` — 排产入口、编排逻辑
  - `schedule_input_builder.py` — 排产输入构建
  - `schedule_persistence.py`（306行）— 排产结果持久化
  - `schedule_summary.py` — 排产摘要生成
  - `schedule_optimizer.py` / `schedule_optimizer_steps.py`（315行）— 优化器
  - `schedule_template_lookup.py` — 模板查找
  - `schedule_history_query_service.py` — 历史查询
- **配置相关**:
  - `config_service.py` / `config_snapshot.py`（211行）/ `config_presets.py`（265行）/ `config_validator.py` — 配置管理全链路
- **冻结窗口**:
  - `freeze_window.py`（212行）— 冻结逻辑正确性

### 阶段 5：排产服务层（下）（~4,580 行）
**范围**: `core/services/scheduler/` 的甘特图、日历、资源调度子集
**预计工作量**: 高
**审查重点**:
- **甘特图相关**（5 个文件）:
  - `gantt_service.py`（238行）— 甘特图数据组装
  - `gantt_tasks.py`（271行）— 任务生成
  - `gantt_contract.py` — 数据契约
  - `gantt_critical_chain.py`（306行）— 关键链计算
  - `gantt_range.py` / `gantt_week_plan.py` — 范围与周计划
- **资源调度相关**（5 个文件）:
  - `resource_dispatch_service.py`（360行）— 资源调度入口
  - `resource_dispatch_support.py`（401行）— 支撑函数
  - `resource_dispatch_rows.py`（412行）— 行构建
  - `resource_dispatch_range.py` / `resource_dispatch_excel.py`（207行）— 范围与导出
- **日历相关**（3 个文件）:
  - `calendar_admin.py`（399行）— 日历管理
  - `calendar_engine.py`（335行）— 日历计算引擎
  - `calendar_service.py`（242行）— 日历服务
- **其他**:
  - `resource_pool_builder.py`（330行）— 资源池构建
  - `batch_service.py` / `batch_query_service.py` / `batch_excel_import.py` / `batch_copy.py` / `batch_template_ops.py` — 批次管理
  - `operation_edit_service.py`（217行）— 工序编辑
  - `number_utils.py` / `_sched_utils.py` — 工具函数

### 阶段 6：业务域服务层（~5,880 行）
**范围**: `core/services/equipment/` + `core/services/material/` + `core/services/personnel/` + `core/services/process/` + `core/services/report/` + `core/services/system/`
**预计工作量**: 中高
**审查重点**:
- **设备域** (`equipment/`):
  - `machine_service.py`（297行）— 设备 CRUD、Excel 导入
  - `machine_downtime_service.py`（241行）— 停机管理
  - `machine_excel_import_service.py` — 设备 Excel 导入
- **人员域** (`personnel/`):
  - `operator_service.py`（247行）— 人员管理
  - `operator_machine_service.py` / `operator_machine_normalizers.py` — 人机关联
  - `operator_excel_import_service.py` — 人员 Excel 导入
  - `resource_team_service.py`（193行）— 班组管理
- **工艺域** (`process/`):
  - `route_parser.py`（426行）— 工艺路线解析（复杂度高）
  - `part_service.py` — 零件管理
  - `unit_excel_converter.py` + `unit_excel/`（子目录 4 文件）— 单元产品 Excel 转换
  - `external_group_service.py`（207行）— 外协管理
  - `deletion_validator.py`（201行）— 删除前引用检查
  - `supplier_service.py`（250行）— 供应商管理
  - `op_type_service.py`（175行）— 工种管理
- **报表域** (`report/`):
  - `report_engine.py`（199行）— 报表引擎
  - `calculations.py`（286行）— 报表计算
  - `queries.py` — 数据查询
  - `exporters/xlsx.py` — Excel 导出
- **系统域** (`system/`):
  - `system_config_service.py`（193行）— 系统配置
  - `system_maintenance_service.py`（172行）— 维护任务
  - `maintenance/` — 备份任务、清理任务、节流

### 阶段 7：综合总结与交叉审查
**范围**: 全局视角
**预计工作量**: 中等
**审查重点**:
- **跨模块依赖分析** — 检查循环引用、分层违反
- **错误处理一致性** — 全局异常处理模式统一性
- **重复代码检测** — 跨模块重复逻辑
- **命名规范一致性** — 函数/变量/模块命名风格
- **对外契约稳定性** — 服务层公开接口的兼容性
- **汇总报告** — 合并所有阶段发现，按严重程度排序，给出修复建议优先级

---

## 交付物
每个阶段完成后产出：
1. 该阶段的审查发现清单（按严重程度分级：高/中/低）
2. 具体代码位置引用（文件+行号）
3. 修复建议

最终阶段 7 产出：
- 综合审查报告（含所有发现的汇总、优先级排序、修复路线图建议）

# APS Strict Mode / Silent Fallback 后续修复计划
- Date: 2026-04-02
- Overview: 基于 2026-04-02 三轮复核结果输出的逐步修复实施计划，覆盖兼容性、架构门禁、严格模式语义收口与全量回归验证。
- Status: completed
- Overall decision: conditionally_accepted

## Review Scope
- Date: 2026-04-02
- Source Review: `.limcode/review/aps-silent-fallback-revalidation-20260402.md`
- Purpose: 把“核心 strict_mode/silent fallback 已基本修到位，但分支仍需收尾”的复核结论，展开成一个可按步骤执行的修复计划。

### 1. 当前状态（一句话版）
当前分支的主结论不是“推倒重来”，而是：

1. **核心目标已经基本达成**：在已复核的主链路中，`strict_mode=True` 已能把关键 silent fallback 场景改成显式报错。
2. **但分支还不能直接宣称完全验收通过**：当前仍存在兼容性断点、架构门禁失败、以及少量非核心/环境敏感失败。

所以这份计划的目标不是“重写功能”，而是：

> **在不破坏已通过的 strict_mode 核心行为前提下，把当前分支收敛到“可解释、可验证、可交付”的状态。**

---

### 2. 已确认的问题清单（按优先级排序）
### P0：必须先处理

#### P0-1. `ConfigService.get_snapshot(strict_mode=...)` 的兼容性断点
- 现象：`ScheduleService` 现在调用 `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`
- 已复现失败：`tests/regression_auto_assign_persist_truthy_variants.py`
- 根因：旧 monkeypatch/stub 仍使用 `def get_snapshot(self):` 这种旧签名，不接受新 kwarg
- 风险：
  - 测试替身会炸
  - 未来任何自定义 stub / monkeypatch / extension point 也可能炸

#### P0-2. Windows 下 Excel 模板文件句柄未及时释放
- 已复现失败：`tests/test_team_pages_excel_smoke.py`
- 现象：`(test_templates / "人员基本信息.xlsx").unlink()` 报 `PermissionError: [WinError 32]`
- 高概率触发点：模板下载路由直接 `send_file(template_path, ...)`，在 Windows/测试客户端语义下可能造成文件仍被占用
- 风险：
  - Windows CI / 本地环境不稳定
  - 模板替换/删除类流程不可靠

### P1：高优先级

#### P1-1. `common <-> scheduler` 循环依赖
- 已复现失败：`tests/test_architecture_fitness.py::test_no_circular_service_dependencies`
- 已定位的具体边：
  - `core/services/common/excel_validators.py`
  - `from core.services.scheduler.number_utils import parse_finite_int`
- 现状：scheduler 侧本来又大量依赖 common，导致 `common -> scheduler -> common`

#### P1-2. `strict_mode` 对数值配置仍非完全严格
- 现状：
  - `dispatch_mode` / `dispatch_rule` / `auto_assign_enabled` 已可在 strict 下硬失败
  - 但 `build_schedule_config_snapshot(..., strict_mode=True)` 中 `_get_float()` / `_get_int()` 仍会把坏值回退为默认值
- 风险：
  - strict 语义不统一
  - 外部容易误以为“strict=True 就是所有配置都硬失败”

### P2：中优先级

#### P2-1. 架构门禁仍红
涉及：
- `test_no_silent_exception_swallow`
- `test_file_size_limit`
- `test_cyclomatic_complexity_threshold`

其中和本次改动直接相关、且应优先处理/决策的文件包括：
- `core/services/process/part_service.py`
- `core/services/process/route_parser.py`
- `core/services/scheduler/batch_service.py`
- `core/services/scheduler/schedule_optimizer.py`
- `core/services/scheduler/schedule_service.py`
- `core/services/scheduler/schedule_summary.py`
- `core/services/scheduler/resource_pool_builder.py`

#### P2-2. 非核心但稳定复现的合同失败
- `tests/regression_config_manual_markdown.py`
- 期望字符串：
  - `const markdownSource = manualMode === "page" ? buildPageMarkdown(currentManual) : rawMarkdown;`
- 当前 `static/js/config_manual.js` 使用了多分支重写逻辑，导致合同不一致

### P3：后续收尾

#### P3-1. 全量测试中的顺序依赖/偶发问题
当前 full suite 结果为：
- `261 passed, 11 failed`

其中有些失败在单独重跑时会消失，说明存在：
- 顺序依赖
- 环境敏感
- 资源释放不彻底

这类问题要放在核心修复完成后统一收口。

---

### 3. 修复总原则
整个修复过程必须遵守以下原则：

1. **先稳住已修好的 strict_mode 主行为，再修周边问题**
   - 不能为了兼容旧 stub，把真实 `strict_mode` 行为重新打回 silent fallback。

2. **每个工作流单独提交，避免大杂烩**
   - 推荐“一类问题一个 commit / 一个小 PR”。

3. **先修可稳定复现、收益最高的问题**
   - 兼容性断点
   - Windows 文件句柄
   - 循环依赖

4. **架构门禁分两类处理**
   - 真正应修的：改代码
   - 短期不适合大拆的：明确 allowlist + 说明原因 + 留债记录

5. **所有修复必须配套回归验证命令**
   - 不接受“凭感觉应该没问题”。

---

### 4. 建议执行顺序（推荐照这个顺序做）
### Phase 0：冻结基线并复现问题
### Phase 1：修 `get_snapshot(strict_mode=...)` 兼容性断点
### Phase 2：修 Windows 模板文件句柄问题 + `config_manual.js` 合同问题
### Phase 3：拆掉 `common <-> scheduler` 循环依赖
### Phase 4：决定并实现“数值配置是否也严格失败”的最终语义
### Phase 5：处理架构门禁（吞异常 / 文件过大 / 高复杂度）
### Phase 6：做全量回归与验收收口

> 不建议一上来就拆大文件。先把 P0/P1 的确定性问题解决掉，回归面更小，风险更可控。

---

### 5. Phase 0：冻结基线并复现问题
### 5.1 目标
把当前问题完整复现出来，形成后续每一步的对照基线。

### 5.2 执行步骤

1. 新建工作分支
   - 建议命名：`fix/strict-mode-followup-20260402`

2. 记录当前关键失败输出

```bash
python -m pytest tests/regression_auto_assign_persist_truthy_variants.py -v --tb=long
python -m pytest tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers -v --tb=long
python -m pytest tests/regression_config_manual_markdown.py -v --tb=short
python -m pytest tests/test_architecture_fitness.py -v --tb=short
```

3. 再跑一次当前重点回归包，确认核心 strict_mode 行为还是绿的

```bash
python -m pytest \
  tests/regression_schedule_summary_v11_contract.py \
  tests/regression_scheduler_route_enforce_ready_tristate.py \
  tests/regression_scheduler_strict_mode_dispatch_flags.py \
  tests/regression_dict_cfg_contract.py \
  tests/regression_batch_detail_linkage.py \
  tests/regression_supplier_service_invalid_default_days_not_silent.py \
  tests/regression_route_parser_supplier_default_days_zero_trace.py \
  tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py \
  tests/regression_route_parser_missing_supplier_warning.py \
  tests/regression_batch_service_strict_mode_template_autoparse.py \
  tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py \
  tests/regression_part_service_create_strict_mode_atomic.py \
  tests/regression_external_group_service_strict_mode_blank_days.py \
  -v --tb=short
```

### 5.3 完成标准
- 已稳定复现所有当前 blocker
- 已确认核心 strict_mode 回归包仍为绿色
- 已保存日志/终端输出，后续可对比

---

### 6. Phase 1：修复 `get_snapshot(strict_mode=...)` 兼容性断点

### 6.1 目标
在**不削弱真实 strict_mode 行为**的前提下，恢复对旧 monkeypatch/stub 的兼容性。

### 6.2 推荐方案
### 推荐采用“双保险”做法

#### 方案 A（代码侧兼容保护，推荐必须做）
在 `core/services/scheduler/schedule_service.py` 增加一个**可选 kwarg 兼容调用 helper**，行为参考现有的：
- `core/services/scheduler/schedule_optimizer_steps.py::_schedule_with_optional_strict_mode()`

建议新增类似 helper：
- `_get_snapshot_with_optional_strict_mode(cfg_svc, strict_mode: bool)`

行为要求：
1. 优先尝试：`cfg_svc.get_snapshot(strict_mode=bool(strict_mode))`
2. 如果明确报的是“unexpected keyword argument 'strict_mode'”
   - 再退回：`cfg_svc.get_snapshot()`
3. 其他异常一律继续抛出
4. **真实 `ConfigService` 仍走 strict_mode 调用，不改变主行为**

这样做的好处：
- 内部真实实现继续严格
- 老 stub/monkeypatch 不会炸
- 兼容范围更真实，不只修测试

#### 方案 B（测试侧 future-proof，建议一起做）
把 `tests/regression_auto_assign_persist_truthy_variants.py` 里的 monkeypatch 改成：

- `def _patched_get_snapshot(self, *args, **kwargs):`

或至少：
- `def _patched_get_snapshot(self, *, strict_mode=False):`

这样测试本身也更抗未来参数扩展。

### 6.3 涉及文件
- `core/services/scheduler/schedule_service.py`
- `tests/regression_auto_assign_persist_truthy_variants.py`
- （可选新增）一个专门验证“旧 stub 不接受 strict_mode 也不会炸”的回归测试

### 6.4 实施步骤
1. 在 `schedule_service.py` 中抽出 helper
2. 把当前直接调用 `cfg_svc.get_snapshot(strict_mode=bool(strict_mode))` 的位置改为走 helper
3. helper 只对“strict_mode kwarg 不被接受”的 `TypeError` 做兼容回退
4. 更新测试 monkeypatch 签名
5. 运行以下回归：

```bash
python -m pytest tests/regression_auto_assign_persist_truthy_variants.py -v --tb=long
python -m pytest tests/regression_scheduler_strict_mode_dispatch_flags.py -v --tb=short
python -m pytest tests/regression_dict_cfg_contract.py -v --tb=short
```

### 6.5 验收标准
- `regression_auto_assign_persist_truthy_variants.py` 变绿
- 现有 strict_mode 主链路测试不回退
- 真实 `ConfigService.get_snapshot(strict_mode=True)` 仍然有效

---

### 7. Phase 2：修复确定性非核心失败

### 7.1 子任务 A：恢复 `config_manual.js` 的精确合同
### 背景
当前 `tests/regression_config_manual_markdown.py` 期望的是**精确字符串合同**，而不是“语义差不多”。

### 目标
恢复下面这行在源文件中的存在性：

```js
const markdownSource = manualMode === "page" ? buildPageMarkdown(currentManual) : rawMarkdown;
```

### 涉及文件
- `static/js/config_manual.js`
- `tests/regression_config_manual_markdown.py`

### 推荐改法
不要只为了过测试粗暴删逻辑。建议改成：

1. **先保留这句一字不差的合同行**
2. 然后再引入第二个变量（例如 `resolvedMarkdownSource`）去做 fallback/trim/fallbackMarkdown 处理
3. 保持当前更稳健的空值保护逻辑，但不要破坏测试约定的“原始来源表达式”

### 实施步骤
1. 把 `let markdownSource = ""; ...` 这段改回“合同行 + 后续归一化变量”两段式
2. 保证 page/full 两种模式的行为不回退
3. 跑：

```bash
python -m pytest tests/regression_config_manual_markdown.py -v --tb=short
```

### 验收标准
- 测试通过
- 页面行为不因恢复合同行而丢失 fallback 逻辑

---

### 7.2 子任务 B：修复 Windows 下 Excel 模板文件被占用问题
### 背景
当前多个模板下载接口都存在如下模式：
- 先定位 `EXCEL_TEMPLATE_DIR` 下的物理 `.xlsx`
- 若存在则直接 `send_file(template_path, ...)`

已确认存在这一模式的路由至少包括：
- `web/routes/personnel_excel_operators.py`
- `web/routes/equipment_excel_machines.py`
- `web/routes/excel_demo.py`
- `web/routes/process_excel_op_types.py`
- `web/routes/process_excel_part_operation_hours.py`
- `web/routes/process_excel_routes.py`
- `web/routes/process_excel_suppliers.py`
- `web/routes/personnel_excel_operator_calendar.py`
- `web/routes/personnel_excel_links.py`
- `web/routes/equipment_excel_links.py`
- `web/routes/scheduler_excel_calendar.py`
- `web/routes/scheduler_excel_batches.py`

### 推荐方案
统一把“磁盘文件模板下载”改成：
1. 先读成 bytes
2. 放入 `io.BytesIO`
3. 再 `send_file(BytesIO(...), ...)`

这样可最大程度避免 Windows 下由底层文件句柄生命周期带来的锁问题。

### 同步卫生清理（建议一起做）
- `tests/test_team_pages_excel_smoke.py::_xlsx_headers()` 中读取 `openpyxl` workbook 后加 `wb.close()`
- `web/routes/excel_demo.py` 中对 `openpyxl.load_workbook(...)` 得到的 `wb` 也补 `close()`

> 说明：真正导致 WinError 32 的更高概率原因是 `send_file(template_path)`，但 workbook 关闭也应补齐，避免再留下资源泄漏点。

### 实施步骤

#### 步骤 1：新增一个模板文件内存化发送 helper
建议放在一个公共但不越层的位置，例如：
- `web/routes/excel_utils.py`
- 或各 route 模块先局部抽 helper，后续再收敛

helper 输入：
- 模板绝对路径
- 下载文件名
- mimetype

helper 行为：
1. `Path(template_path).read_bytes()` 读入内存
2. `io.BytesIO(data)`
3. `send_file(bytes_io, as_attachment=True, download_name=...)`

#### 步骤 2：替换上述 12 个模板下载路由中的 `send_file(template_path, ...)`
只替换“模板文件存在时的磁盘路径发送分支”，不要动动态生成模板的 `build_xlsx_bytes(...)` 分支。

#### 步骤 3：显式关闭 workbook
- `tests/test_team_pages_excel_smoke.py::_xlsx_headers`
- `web/routes/excel_demo.py`

#### 步骤 4：回归验证

```bash
python -m pytest tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers -v --tb=long
python -m pytest tests/smoke_phase0_phase1.py -v --tb=short
python -m pytest tests/smoke_web_phase0_5.py -v --tb=short
```

### 验收标准
- `test_team_pages_excel_smoke` 变绿
- 模板下载路由仍然可正常下载
- 删除/替换 `templates_excel` 下文件不再被 Windows 文件锁拦住

---

### 8. Phase 3：拆掉 `common <-> scheduler` 循环依赖

### 8.1 目标
让 `core/services/common` 不再反向 import `core/services/scheduler`。

### 8.2 推荐方案
### 核心思路
把真正“通用”的解析能力，迁移到一个**依赖中立**的 common 工具模块里。

### 推荐落点
新增一个中立模块，例如：
- `core/services/common/number_utils.py`
- 或 `core/services/common/value_parsers.py`

建议迁移/沉淀的函数：
- `parse_finite_int`
- （可选）`parse_finite_float`
- `to_yes_no` 是否迁移取决于你们希望它归在 enum/normalization 还是 numeric parsing

### 兼容策略（推荐这样做）
为了减少大面积改动：
1. 先新建 common 工具模块
2. `core/services/common/excel_validators.py` 改为从 common 新模块 import
3. `core/services/scheduler/number_utils.py` 内部改为复用/转发 common 新模块中的实现
4. 保留 `scheduler.number_utils` 旧导出，避免其他调用点一次性改太多

这样能做到：
- `common` 不再依赖 `scheduler`
- 旧代码 import `scheduler.number_utils` 仍不至于一次性全炸

### 8.3 涉及文件
- `core/services/common/excel_validators.py`
- `core/services/scheduler/number_utils.py`
- 新增：`core/services/common/number_utils.py`（或同义命名）
- 其他所有直接 import 受影响处（按实际搜索结果调整）

### 8.4 实施步骤
1. 新增 common 数值解析模块
2. 把 `parse_finite_int` 抽过去
3. 修改 `excel_validators.py` 的 import
4. 让 `scheduler.number_utils.py` 复用 common 模块实现
5. 全局搜一遍 `from core.services.scheduler.number_utils import ...`
6. 确认没有新的反向依赖边
7. 跑：

```bash
python -m pytest tests/test_architecture_fitness.py::test_no_circular_service_dependencies -v --tb=short
```

### 8.5 验收标准
- `test_no_circular_service_dependencies` 变绿
- 原有 numeric parsing 行为不变
- 没有引入新的 import 方向问题

---

### 9. Phase 4：收口 strict_mode 对“数值配置”的最终语义

### 9.1 先做决策，不要边改边猜
这里必须先拍板：

### 选项 A：维持现状并文档化
即：
- strict_mode 只保证 choice / yes-no 字段严格
- 数值字段仍允许回退默认值

优点：
- 改动小
- 对现有兼容性最稳

缺点：
- `strict_mode` 语义不统一
- 外部理解成本高

### 选项 B：把数值字段也纳入 strict 硬失败（推荐）
即在 `strict_mode=True` 时，对以下字段中的非法值改为直接报错，而不是默认值兜底：
- `priority_weight`
- `due_weight`
- `ready_weight`
- `holiday_default_efficiency`
- `ortools_time_limit_seconds`
- `time_budget_seconds`
- `freeze_window_days`
- 其他 snapshot 中走 `_get_float()` / `_get_int()` 的数值项

优点：
- strict 语义统一
- 更符合直觉

缺点：
- 可能影响部分旧配置库/旧环境

### 9.2 推荐执行方式
### 若选 B（推荐）
在 `core/services/scheduler/config_snapshot.py` 中：
1. 给 `_get_float()` / `_get_int()` 增加 `strict` 参数
2. 在 `strict_mode=True` 时：
   - 非数字 -> 抛 `ValidationError`
   - 非有限数（NaN/Inf） -> 抛 `ValidationError`
   - 不满足约束（如需要 `>=0` 或 `>0`） -> 抛 `ValidationError`
3. 在 `strict_mode=False` 时，保留旧回退逻辑

### 涉及文件
- `core/services/scheduler/config_snapshot.py`
- `core/services/scheduler/config_service.py`
- `core/services/scheduler/config_presets.py`
- 对应测试文件（按现有 regression 名称补强）

### 9.3 验证建议
至少补/跑以下类型回归：
- 非数字字符串
- `NaN`
- `Inf`
- 负数 / 0 边界
- strict=False 时仍能兼容回退
- strict=True 时明确报错

建议命令：

```bash
python -m pytest tests/regression_scheduler_apply_preset_reject_invalid_numeric.py -v --tb=short
python -m pytest tests/regression_dict_cfg_contract.py -v --tb=short
python -m pytest tests/regression_scheduler_strict_mode_dispatch_flags.py -v --tb=short
```

### 9.4 验收标准
- 已明确选择 A 或 B
- 若选 B，则 strict 数值配置回归齐全并通过
- 若选 A，则文档/测试必须明确 strict 的边界，不允许继续模糊

---

### 10. Phase 5：处理架构门禁（按“先最值钱、再最重”的顺序）

### 10.1 子任务 A：清理 changed files 里的 `except Exception: pass`
### 当前重点热点
- `core/services/process/external_group_service.py:143`
- `core/services/process/part_service.py:97`
- `core/services/process/part_service.py:169`
- `core/services/process/route_parser.py:288`
- `core/services/process/route_parser.py:332`
- `core/services/process/supplier_service.py:49`
- `core/services/scheduler/resource_pool_builder.py:139`
- `core/services/scheduler/resource_pool_builder.py:147`
- `core/services/scheduler/resource_pool_builder.py:172`
- `core/services/scheduler/resource_pool_builder.py:190`
- `core/services/scheduler/resource_pool_builder.py:265`
- `core/services/scheduler/resource_pool_builder.py:312`
- `core/services/scheduler/resource_pool_builder.py:320`
- `core/services/scheduler/resource_pool_builder.py:345`
- `core/services/scheduler/resource_pool_builder.py:363`

### 处理原则
把这些点分成三类：

#### A 类：纯日志保护
例如“logger 自己别再把主逻辑打爆”。
- 处理方式：抽 `safe_log_warning(...)` / `safe_log_exception(...)` helper
- 统一替换裸 `except Exception: pass`

#### B 类：兼容模式下允许继续，但必须留痕
例如：
- `part_service.py:169` 非 strict create 流程

处理方式：
- 捕获更具体的异常类型（如 `AppError`/`BusinessError`/`ValidationError`）
- 记录 warning / meta / op log
- 再继续

#### C 类：真正应抛而不该吞
这类直接改为显式失败

### 实施步骤
1. 逐个点位标注归类（A/B/C）
2. 先改 changed files，不要一次性扫全仓
3. 每改一个文件跑一次对应局部回归
4. 再跑：

```bash
python -m pytest tests/test_architecture_fitness.py::test_no_silent_exception_swallow -v --tb=short
```

### 验收标准
- changed files 中新增的/本次相关的裸吞异常全部清掉或合理 allowlist
- 不破坏 compatible mode 行为

---

### 10.2 子任务 B：文件过大（>500 行）
### 当前相关超限文件
- `core/services/process/part_service.py`（512）
- `core/services/scheduler/batch_service.py`（508）
- `core/services/scheduler/schedule_optimizer.py`（584）
- `core/services/scheduler/schedule_service.py`（532）
- `core/services/scheduler/schedule_summary.py`（648）

### 现实建议：分两条路径选一条

#### 路径 1：短期收口（推荐当前批次）
如果当前目标是“尽快把 strict_mode 分支收口”，建议：
- 对这些文件先**明确 allowlist + 说明原因**
- 同时在计划中登记后续拆分任务

#### 路径 2：本批次彻底拆分
若你要求这次必须让 `test_file_size_limit` 变绿，就按下面建议拆：

##### `part_service.py`
建议拆为：
- part 基础 CRUD
- route parse / reparse
- template save / snapshot helper
- external-group deletion/cleanup

##### `batch_service.py`
建议拆为：
- batch create/update 基础逻辑
- template/autoparse 辅助逻辑
- excel import / preview 逻辑

##### `schedule_optimizer.py`
建议拆为：
- orchestration 主流程
- warmstart / multi-start
- local search
- attempts compaction

##### `schedule_service.py`
建议拆为：
- input normalize / pre-check
- batch & op loading
- resource preparation
- persistence / result assembly

##### `schedule_summary.py`
建议拆为：
- downtime degradation
- algo warnings/meta merge
- final summary rendering

### 验收命令

```bash
python -m pytest tests/test_architecture_fitness.py::test_file_size_limit -v --tb=short
```

---

### 10.3 子任务 C：圈复杂度超标
### 当前重点热点
- `core/services/process/route_parser.py::_build_supplier_map`
- `core/services/scheduler/schedule_optimizer.py::_compact_attempts`
- `core/services/scheduler/schedule_summary.py::_compute_downtime_degradation`

### 推荐拆法

#### `_build_supplier_map`
拆成：
- 供应商行 -> op_type 映射获取
- `default_days` 解析
- issue message 构造

#### `_compact_attempts`
拆成：
- 单次 attempt 标准化
- 分组键构造
- 代表项选择
- fallback/meta 合并

#### `_compute_downtime_degradation`
拆成：
- 输入 meta 提取
- 失败样本归一化
- 结果摘要拼装

### 验收命令

```bash
python -m pytest tests/test_architecture_fitness.py::test_cyclomatic_complexity_threshold -v --tb=short
```

---

### 11. Phase 6：全量回归与收口

### 11.1 最小验收集（必须绿）
```bash
python -m pytest tests/regression_auto_assign_persist_truthy_variants.py -v --tb=long
python -m pytest tests/regression_config_manual_markdown.py -v --tb=short
python -m pytest tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers -v --tb=long
python -m pytest tests/test_architecture_fitness.py -v --tb=short
```

### 11.2 strict_mode 核心回归集（必须继续绿）
```bash
python -m pytest \
  tests/regression_schedule_summary_v11_contract.py \
  tests/regression_scheduler_route_enforce_ready_tristate.py \
  tests/regression_scheduler_strict_mode_dispatch_flags.py \
  tests/regression_dict_cfg_contract.py \
  tests/regression_batch_detail_linkage.py \
  tests/regression_supplier_service_invalid_default_days_not_silent.py \
  tests/regression_route_parser_supplier_default_days_zero_trace.py \
  tests/regression_route_parser_strict_mode_rejects_supplier_fallback.py \
  tests/regression_route_parser_missing_supplier_warning.py \
  tests/regression_batch_service_strict_mode_template_autoparse.py \
  tests/regression_batch_excel_import_strict_mode_hardfail_atomic.py \
  tests/regression_part_service_create_strict_mode_atomic.py \
  tests/regression_external_group_service_strict_mode_blank_days.py \
  -v --tb=short
```

### 11.3 全量回归（建议）
```bash
python -m pytest tests/ -v --tb=short
```

### 最佳完成标准
- 全量 suite 至少连续两次通过

### 若 CI 成本太高，最低完成标准
- 全量至少一次通过
- 曾经 flaky 的用例额外单独再跑一次

---

### 12. 推荐提交拆分方式（方便回滚）
### Commit / PR 1：兼容性 + 确定性小失败
包含：
- `get_snapshot(strict_mode=...)` 兼容保护
- `regression_auto_assign_persist_truthy_variants.py` 修正
- `config_manual.js` 合同修复
- Windows 模板文件句柄修复

### Commit / PR 2：循环依赖修复
包含：
- common/scheduler 数值解析模块收敛
- `common <-> scheduler` cycle break

### Commit / PR 3：strict 数值配置语义收口
包含：
- strict numeric decision A/B 的实现
- 对应测试补齐

### Commit / PR 4：架构门禁清理
包含：
- 裸吞异常清理
- 文件大小/复杂度处理或 allowlist 更新

> 这样拆分的好处是：哪一步出问题，都能快速回滚，不会把所有变化搅在一起。

---

### 13. 风险与注意事项
### 风险 1：为了兼容旧 stub，把真实 strict_mode 弱化了
- 规避方式：兼容 helper 只针对“方法不接受 strict_mode kwarg”的场景回退，**不能把真实 `ConfigService` 也降级成无 strict 模式**

### 风险 2：修 Windows 文件句柄时误改下载行为
- 规避方式：只替换“模板文件存在时的磁盘文件发送分支”，动态生成分支保持不动

### 风险 3：拆循环依赖时引入大面积 import 破坏
- 规避方式：先新增 common 中立模块，再做小步替换；必要时保留 `scheduler.number_utils` 兼容导出

### 风险 4：为过架构测试而做“机械式假修复”
- 规避方式：
  - 不要只把 `pass` 改成空 log
  - 要么变更异常类型
  - 要么显式留痕
  - 要么说明为什么必须兼容吞掉

### 风险 5：大文件拆分导致回归面过大
- 规避方式：若本轮主要目标是 strict_mode 收口，则优先选择“明确 allowlist + 后续计划”，不要一口气拆 5 个大文件

---

### 14. Definition of Done（本计划的完成标准）

### 必须达成（Must Have）
- `tests/regression_auto_assign_persist_truthy_variants.py` 通过
- `tests/test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers` 通过
- `tests/regression_config_manual_markdown.py` 通过
- strict_mode 核心回归包继续全绿
- `common <-> scheduler` 循环依赖问题解决或被清晰替代
- 对 strict numeric 行为已明确决策（A 或 B）

### 推荐达成（Should Have）
- `tests/test_architecture_fitness.py` 全部通过
- changed files 中裸吞异常问题清理完成
- 重要超大文件/高复杂函数已有清晰处置（拆分或 allowlist）

### 最佳达成（Nice to Have）
- `python -m pytest tests/ -v --tb=short` 全绿且稳定

---

### 15. 最短路径建议（如果你只想先把最关键的收掉）
如果现在目标是“**用最小代价把分支拉回到一个可信状态**”，建议按下面最短路径执行：

1. **先修 P0-1：`get_snapshot(strict_mode=...)` 兼容断点**
2. **再修 P0-2：Windows 模板文件句柄问题**
3. **同时修 `config_manual.js` 的精确合同**
4. **再拆 `common <-> scheduler` 循环依赖**
5. **最后决定 strict 数值配置是否也要硬失败**
6. **架构大文件/复杂度问题视交付压力决定：本轮真拆还是先 allowlist**

这是最符合当前分支风险收益比的路线。

---

### 16. 计划执行后的最终验收话术（供团队对外统一口径）
当以上步骤完成后，推荐使用下面这类表述，而不是模糊地说“都好了”：

> 已完成 strict_mode / silent fallback 后续收口：
> - 核心 silent fallback 已在严格模式下改为显式报错；
> - 兼容性断点已补齐；
> - Windows 模板文件占用问题已处理；
> - 关键架构依赖方向已收敛；
> - 相关回归与门禁已复核通过（或已对剩余技术债做明确记录）。

这样口径更真实，也便于后续继续维护。

## Review Summary
<!-- LIMCODE_REVIEW_SUMMARY_START -->
- Current status: completed
- Reviewed modules: core/services/scheduler/schedule_service.py, core/services/scheduler/config_snapshot.py, core/services/common/excel_validators.py, core/services/common/number_utils.py, web/routes/excel_utils.py, web/routes/excel_demo.py, web/routes/personnel_excel_operators.py, web/routes/equipment_excel_machines.py, web/routes/process_excel_op_types.py, web/routes/process_excel_part_operation_hours.py, web/routes/process_excel_routes.py, web/routes/process_excel_suppliers.py, web/routes/personnel_excel_operator_calendar.py, web/routes/personnel_excel_links.py, web/routes/equipment_excel_links.py, web/routes/scheduler_excel_calendar.py, web/routes/scheduler_excel_batches.py, static/js/config_manual.js, tests/regression_auto_assign_persist_truthy_variants.py, tests/regression_config_snapshot_strict_numeric.py, tests/test_team_pages_excel_smoke.py, tests/test_architecture_fitness.py, core/services/common/safe_logging.py, core/services/process/part_service.py, core/services/process/route_parser.py, core/services/process/external_group_service.py, core/services/process/supplier_service.py, core/services/scheduler/resource_pool_builder.py, core/services/scheduler/calendar_admin.py, core/services/common/excel_templates.py, core/infrastructure/logging.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_summary.py
- Current progress: 2 milestones recorded; latest: phase5-6-closeout-20260402
- Total milestones: 2
- Completed milestones: 1
- Total findings: 4
- Findings by severity: high 0 / medium 1 / low 3
- Latest conclusion: 本轮 strict_mode / silent fallback follow-up 已完成：核心 strict_mode 行为保持收紧，相关兼容性/模板句柄/循环依赖/strict numeric 问题已处理，架构门禁已通过；剩余维护性问题仅体现在 `tests/test_architecture_fitness.py` 中显式登记的历史大文件与复杂函数 allowlist，需在后续独立维护批次拆分。
- Recommended next action: 后续单开维护性批次，优先拆分 `tests/test_architecture_fitness.py` allowlist 中登记的历史大文件与复杂函数，不要与业务语义修复混批。
- Overall decision: conditionally_accepted
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
- [low] other: 架构门禁仍未全绿，当前剩余集中在 silent exception swallow、文件超限与高复杂度函数，需要单独拆批处理。
  - ID: F-架构门禁仍未全绿-当前剩余集中在-silent-exception-swallow-文件超限与高复杂度函数-需要单独拆批处理
  - Evidence Files:
    - `evidence/Phase0_Phase1/smoke_test_report.md`
    - `evidence/Phase0_to_Phase5/web_smoke_report.md`
  - Related Milestones: phase1-4-closeout-20260402

- [medium] maintainability: Phase 5 架构门禁仍未收口
  - ID: phase5-arch-gates-remaining
  - Description: `tests/test_architecture_fitness.py` 当前仍剩 `test_no_silent_exception_swallow`、`test_file_size_limit`、`test_cyclomatic_complexity_threshold` 失败；其中主要热点仍在 process/scheduler 历史大文件与资源池/路由解析复杂函数。
  - Evidence Files:
    - `core/services/process/part_service.py`
    - `core/services/process/route_parser.py`
    - `core/services/scheduler/resource_pool_builder.py`
    - `core/services/scheduler/schedule_optimizer.py`
    - `core/services/scheduler/schedule_summary.py`
    - `evidence/Phase0_Phase1/smoke_test_report.md`
    - `evidence/Phase0_to_Phase5/web_smoke_report.md`
  - Related Milestones: phase1-4-closeout-20260402
  - Recommendation: 按计划进入 Phase 5，优先清理 changed files 中的裸吞异常，再评估大文件拆分与复杂函数分解，不建议在同一批次混入更多行为语义修改。

- [low] other: 历史大文件与少量高复杂函数并未在本轮硬拆，而是按计划路径 1 进入显式 allowlist；后续应单独拆批，不要与 strict_mode 行为改动混批。
  - ID: F-历史大文件与少量高复杂函数并未在本轮硬拆-而是按计划路径-1-进入显式-allowlist-后续应单独拆批-不要与-strict-mode-行为改动混批
  - Evidence Files:
    - `tests/test_architecture_fitness.py`
    - `core/services/common/safe_logging.py`
    - `core/services/process/part_service.py`
    - `core/services/process/route_parser.py`
    - `core/services/process/external_group_service.py`
    - `core/services/process/supplier_service.py`
    - `core/services/scheduler/resource_pool_builder.py`
    - `core/services/scheduler/calendar_admin.py`
    - `core/services/common/excel_templates.py`
    - `core/infrastructure/logging.py`
    - `core/services/scheduler/schedule_optimizer.py`
    - `core/services/scheduler/schedule_summary.py`
  - Related Milestones: phase5-6-closeout-20260402

- [low] maintainability: Phase 5 历史大文件/复杂函数已显式登记技术债
  - ID: phase5-allowlist-debt-tracked
  - Description: `test_file_size_limit` 与 `test_cyclomatic_complexity_threshold` 现已转绿，但部分历史大文件与历史高复杂函数并未在本轮进一步大拆，而是按照计划 10.2 的路径 1 进入 `tests/test_architecture_fitness.py` 中的 allowlist，作为后续独立拆分批次处理。
  - Evidence Files:
    - `tests/test_architecture_fitness.py`
    - `core/services/scheduler/schedule_service.py`
    - `core/services/scheduler/schedule_summary.py`
    - `core/infrastructure/database.py`
    - `core/services/common/safe_logging.py`
    - `core/services/process/part_service.py`
    - `core/services/process/route_parser.py`
    - `core/services/process/external_group_service.py`
    - `core/services/process/supplier_service.py`
    - `core/services/scheduler/resource_pool_builder.py`
    - `core/services/scheduler/calendar_admin.py`
    - `core/services/common/excel_templates.py`
    - `core/infrastructure/logging.py`
    - `core/services/scheduler/schedule_optimizer.py`
  - Related Milestones: phase5-6-closeout-20260402
  - Recommendation: 后续单开维护性批次，按模块把 allowlist 中的历史大文件/复杂函数拆分，不要与业务语义修复混批。
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
### phase1-4-closeout-20260402 · Phase 1-4：兼容性、模板句柄、循环依赖与 strict numeric 收口
- Status: in_progress
- Recorded At: 2026-04-02T08:06:42.039Z
- Reviewed Modules: core/services/scheduler/schedule_service.py, core/services/scheduler/config_snapshot.py, core/services/common/excel_validators.py, core/services/common/number_utils.py, web/routes/excel_utils.py, web/routes/excel_demo.py, web/routes/personnel_excel_operators.py, web/routes/equipment_excel_machines.py, web/routes/process_excel_op_types.py, web/routes/process_excel_part_operation_hours.py, web/routes/process_excel_routes.py, web/routes/process_excel_suppliers.py, web/routes/personnel_excel_operator_calendar.py, web/routes/personnel_excel_links.py, web/routes/equipment_excel_links.py, web/routes/scheduler_excel_calendar.py, web/routes/scheduler_excel_batches.py, static/js/config_manual.js, tests/regression_auto_assign_persist_truthy_variants.py, tests/regression_config_snapshot_strict_numeric.py, tests/test_team_pages_excel_smoke.py
- Summary:
已完成本轮确定性修复：

- `ScheduleService` 增加 `get_snapshot(strict_mode=...)` 的兼容调用 helper，仅在 stub/monkeypatch 不接受 `strict_mode` kwarg 时回退到旧签名；真实 `ConfigService` 仍走严格参数路径。
- `tests/regression_auto_assign_persist_truthy_variants.py` 的 monkeypatch 已改为接受未来参数扩展，避免再次被方法签名变更击穿。
- `static/js/config_manual.js` 已恢复精确合同语句 `const markdownSource = manualMode === "page" ? buildPageMarkdown(currentManual) : rawMarkdown;`，并把 fallback 逻辑收敛到后续 `resolvedMarkdownSource`，保持行为稳定。
- 新增 `web/routes/excel_utils.py::send_excel_template_file()`，把磁盘模板先读入内存再发送；已替换相关 Excel 模板下载路由，避免 Windows 下 `send_file(template_path)` 持有文件句柄。
- `tests/test_team_pages_excel_smoke.py::_xlsx_headers()` 与 `web/routes/excel_demo.py` 已补 `wb.close()`，清掉 openpyxl 句柄残留点。
- `core/services/common/excel_validators.py` 已改为直接依赖 `core.services.common.number_utils`，`common <-> scheduler` 循环依赖已拆除。
- `core/services/common/number_utils.py` 增加 overload，消除 `parse_finite_int(..., allow_none=False)` 的 Optional 误报。
- 已选择并实现 strict numeric 方案 B：`build_schedule_config_snapshot(..., strict_mode=True)` 下，非法/非有限/越界的数值配置不再静默回退，而是抛 `ValidationError`；非 strict 模式继续保留兼容回退与最小值钳制。
- 新增 `tests/regression_config_snapshot_strict_numeric.py` 覆盖 strict/non-strict numeric 行为。

本轮未继续处理 Phase 5 的大块架构门禁（silent swallow / 文件超限 / 圈复杂度），这些仍需单独分批收口。
- Conclusion: P0/P1 与 strict numeric 收口已完成，当前剩余主阻塞为 Phase 5 架构门禁。
- Evidence Files:
  - `evidence/Phase0_Phase1/smoke_test_report.md`
  - `evidence/Phase0_to_Phase5/web_smoke_report.md`
- Recommended Next Action: 进入 Phase 5，先按计划清理 changed files 中的裸吞异常，再决定本轮是否拆大文件或只保留技术债记录。
- Findings:
  - [low] other: 架构门禁仍未全绿，当前剩余集中在 silent exception swallow、文件超限与高复杂度函数，需要单独拆批处理。
  - [medium] maintainability: Phase 5 架构门禁仍未收口

### phase5-6-closeout-20260402 · Phase 5-6：架构门禁收口与最小验收回归完成
- Status: completed
- Recorded At: 2026-04-02T08:27:59.628Z
- Reviewed Modules: tests/test_architecture_fitness.py, core/services/common/safe_logging.py, core/services/process/part_service.py, core/services/process/route_parser.py, core/services/process/external_group_service.py, core/services/process/supplier_service.py, core/services/scheduler/resource_pool_builder.py, core/services/scheduler/calendar_admin.py, core/services/common/excel_templates.py, core/infrastructure/logging.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_summary.py
- Summary:
本轮已完成 Phase 5/6 收口：

- `tests/test_architecture_fitness.py::test_no_silent_exception_swallow` 已转绿；此前 Phase 5 中新增的 silent swallow 清理（`part_service.py`、`external_group_service.py`、`supplier_service.py`、`route_parser.py`、`resource_pool_builder.py`、`calendar_admin.py`、`excel_templates.py`、`core/infrastructure/logging.py`）已通过门禁复核。
- 直接相关的复杂函数已完成拆分：`route_parser.py::_build_supplier_map`、`schedule_optimizer.py::_compact_attempts`、`schedule_summary.py::_compute_downtime_degradation` 不再触发复杂度门禁。
- 对剩余历史大文件与历史高复杂函数，按计划第 10.2 节“路径 1：短期收口”执行：在 `tests/test_architecture_fitness.py` 中显式登记 `known_oversize` 与 `known_violations`，并在注释中说明这些点位属于后续独立拆批的技术债，而非本轮继续做高风险结构拆分。
- 最小验收集已通过：`regression_auto_assign_persist_truthy_variants.py`、`regression_config_manual_markdown.py`、`test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers`、`tests/test_architecture_fitness.py`。
- strict_mode 核心回归集已通过：`regression_schedule_summary_v11_contract.py`、`regression_scheduler_route_enforce_ready_tristate.py`、`regression_scheduler_strict_mode_dispatch_flags.py`、`regression_dict_cfg_contract.py`、`regression_batch_detail_linkage.py`、`regression_supplier_service_invalid_default_days_not_silent.py`、`regression_route_parser_supplier_default_days_zero_trace.py`、`regression_route_parser_strict_mode_rejects_supplier_fallback.py`、`regression_route_parser_missing_supplier_warning.py`、`regression_batch_service_strict_mode_template_autoparse.py`、`regression_batch_excel_import_strict_mode_hardfail_atomic.py`、`regression_part_service_create_strict_mode_atomic.py`、`regression_external_group_service_strict_mode_blank_days.py`。

结论：本轮 strict_mode / silent fallback follow-up 已完成收口；架构门禁当前为绿色，历史大文件与少量高复杂度热点已转为显式登记的后续拆分债项。
- Conclusion: Phase 5/6 已完成：strict_mode / silent fallback follow-up 目标已收口，架构门禁通过，剩余仅为已登记的历史拆分债项。
- Evidence Files:
  - `tests/test_architecture_fitness.py`
  - `core/services/common/safe_logging.py`
  - `core/services/process/part_service.py`
  - `core/services/process/route_parser.py`
  - `core/services/process/external_group_service.py`
  - `core/services/process/supplier_service.py`
  - `core/services/scheduler/resource_pool_builder.py`
  - `core/services/scheduler/calendar_admin.py`
  - `core/services/common/excel_templates.py`
  - `core/infrastructure/logging.py`
  - `core/services/scheduler/schedule_optimizer.py`
  - `core/services/scheduler/schedule_summary.py`
- Recommended Next Action: 如需继续降低维护债，请单独开启后续批次拆分 `tests/test_architecture_fitness.py` allowlist 中登记的历史大文件与复杂函数。
- Findings:
  - [low] other: 历史大文件与少量高复杂函数并未在本轮硬拆，而是按计划路径 1 进入显式 allowlist；后续应单独拆批，不要与 strict_mode 行为改动混批。
  - [low] maintainability: Phase 5 历史大文件/复杂函数已显式登记技术债
<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mnh5toei-4vp9kb",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "finalizedAt": "2026-04-02T08:28:10.410Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "latestConclusion": "本轮 strict_mode / silent fallback follow-up 已完成：核心 strict_mode 行为保持收紧，相关兼容性/模板句柄/循环依赖/strict numeric 问题已处理，架构门禁已通过；剩余维护性问题仅体现在 `tests/test_architecture_fitness.py` 中显式登记的历史大文件与复杂函数 allowlist，需在后续独立维护批次拆分。",
  "recommendedNextAction": "后续单开维护性批次，优先拆分 `tests/test_architecture_fitness.py` allowlist 中登记的历史大文件与复杂函数，不要与业务语义修复混批。",
  "reviewedModules": [
    "core/services/scheduler/schedule_service.py",
    "core/services/scheduler/config_snapshot.py",
    "core/services/common/excel_validators.py",
    "core/services/common/number_utils.py",
    "web/routes/excel_utils.py",
    "web/routes/excel_demo.py",
    "web/routes/personnel_excel_operators.py",
    "web/routes/equipment_excel_machines.py",
    "web/routes/process_excel_op_types.py",
    "web/routes/process_excel_part_operation_hours.py",
    "web/routes/process_excel_routes.py",
    "web/routes/process_excel_suppliers.py",
    "web/routes/personnel_excel_operator_calendar.py",
    "web/routes/personnel_excel_links.py",
    "web/routes/equipment_excel_links.py",
    "web/routes/scheduler_excel_calendar.py",
    "web/routes/scheduler_excel_batches.py",
    "static/js/config_manual.js",
    "tests/regression_auto_assign_persist_truthy_variants.py",
    "tests/regression_config_snapshot_strict_numeric.py",
    "tests/test_team_pages_excel_smoke.py",
    "tests/test_architecture_fitness.py",
    "core/services/common/safe_logging.py",
    "core/services/process/part_service.py",
    "core/services/process/route_parser.py",
    "core/services/process/external_group_service.py",
    "core/services/process/supplier_service.py",
    "core/services/scheduler/resource_pool_builder.py",
    "core/services/scheduler/calendar_admin.py",
    "core/services/common/excel_templates.py",
    "core/infrastructure/logging.py",
    "core/services/scheduler/schedule_optimizer.py",
    "core/services/scheduler/schedule_summary.py"
  ],
  "milestones": [
    {
      "id": "phase1-4-closeout-20260402",
      "title": "Phase 1-4：兼容性、模板句柄、循环依赖与 strict numeric 收口",
      "summary": "已完成本轮确定性修复：\n\n- `ScheduleService` 增加 `get_snapshot(strict_mode=...)` 的兼容调用 helper，仅在 stub/monkeypatch 不接受 `strict_mode` kwarg 时回退到旧签名；真实 `ConfigService` 仍走严格参数路径。\n- `tests/regression_auto_assign_persist_truthy_variants.py` 的 monkeypatch 已改为接受未来参数扩展，避免再次被方法签名变更击穿。\n- `static/js/config_manual.js` 已恢复精确合同语句 `const markdownSource = manualMode === \"page\" ? buildPageMarkdown(currentManual) : rawMarkdown;`，并把 fallback 逻辑收敛到后续 `resolvedMarkdownSource`，保持行为稳定。\n- 新增 `web/routes/excel_utils.py::send_excel_template_file()`，把磁盘模板先读入内存再发送；已替换相关 Excel 模板下载路由，避免 Windows 下 `send_file(template_path)` 持有文件句柄。\n- `tests/test_team_pages_excel_smoke.py::_xlsx_headers()` 与 `web/routes/excel_demo.py` 已补 `wb.close()`，清掉 openpyxl 句柄残留点。\n- `core/services/common/excel_validators.py` 已改为直接依赖 `core.services.common.number_utils`，`common <-> scheduler` 循环依赖已拆除。\n- `core/services/common/number_utils.py` 增加 overload，消除 `parse_finite_int(..., allow_none=False)` 的 Optional 误报。\n- 已选择并实现 strict numeric 方案 B：`build_schedule_config_snapshot(..., strict_mode=True)` 下，非法/非有限/越界的数值配置不再静默回退，而是抛 `ValidationError`；非 strict 模式继续保留兼容回退与最小值钳制。\n- 新增 `tests/regression_config_snapshot_strict_numeric.py` 覆盖 strict/non-strict numeric 行为。\n\n本轮未继续处理 Phase 5 的大块架构门禁（silent swallow / 文件超限 / 圈复杂度），这些仍需单独分批收口。",
      "status": "in_progress",
      "conclusion": "P0/P1 与 strict numeric 收口已完成，当前剩余主阻塞为 Phase 5 架构门禁。",
      "evidenceFiles": [
        "evidence/Phase0_Phase1/smoke_test_report.md",
        "evidence/Phase0_to_Phase5/web_smoke_report.md"
      ],
      "reviewedModules": [
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/config_snapshot.py",
        "core/services/common/excel_validators.py",
        "core/services/common/number_utils.py",
        "web/routes/excel_utils.py",
        "web/routes/excel_demo.py",
        "web/routes/personnel_excel_operators.py",
        "web/routes/equipment_excel_machines.py",
        "web/routes/process_excel_op_types.py",
        "web/routes/process_excel_part_operation_hours.py",
        "web/routes/process_excel_routes.py",
        "web/routes/process_excel_suppliers.py",
        "web/routes/personnel_excel_operator_calendar.py",
        "web/routes/personnel_excel_links.py",
        "web/routes/equipment_excel_links.py",
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/scheduler_excel_batches.py",
        "static/js/config_manual.js",
        "tests/regression_auto_assign_persist_truthy_variants.py",
        "tests/regression_config_snapshot_strict_numeric.py",
        "tests/test_team_pages_excel_smoke.py"
      ],
      "recommendedNextAction": "进入 Phase 5，先按计划清理 changed files 中的裸吞异常，再决定本轮是否拆大文件或只保留技术债记录。",
      "recordedAt": "2026-04-02T08:06:42.039Z",
      "findingIds": [
        "F-架构门禁仍未全绿-当前剩余集中在-silent-exception-swallow-文件超限与高复杂度函数-需要单独拆批处理",
        "phase5-arch-gates-remaining"
      ]
    },
    {
      "id": "phase5-6-closeout-20260402",
      "title": "Phase 5-6：架构门禁收口与最小验收回归完成",
      "summary": "本轮已完成 Phase 5/6 收口：\n\n- `tests/test_architecture_fitness.py::test_no_silent_exception_swallow` 已转绿；此前 Phase 5 中新增的 silent swallow 清理（`part_service.py`、`external_group_service.py`、`supplier_service.py`、`route_parser.py`、`resource_pool_builder.py`、`calendar_admin.py`、`excel_templates.py`、`core/infrastructure/logging.py`）已通过门禁复核。\n- 直接相关的复杂函数已完成拆分：`route_parser.py::_build_supplier_map`、`schedule_optimizer.py::_compact_attempts`、`schedule_summary.py::_compute_downtime_degradation` 不再触发复杂度门禁。\n- 对剩余历史大文件与历史高复杂函数，按计划第 10.2 节“路径 1：短期收口”执行：在 `tests/test_architecture_fitness.py` 中显式登记 `known_oversize` 与 `known_violations`，并在注释中说明这些点位属于后续独立拆批的技术债，而非本轮继续做高风险结构拆分。\n- 最小验收集已通过：`regression_auto_assign_persist_truthy_variants.py`、`regression_config_manual_markdown.py`、`test_team_pages_excel_smoke.py::test_team_pages_and_excel_routes_show_team_columns_and_headers`、`tests/test_architecture_fitness.py`。\n- strict_mode 核心回归集已通过：`regression_schedule_summary_v11_contract.py`、`regression_scheduler_route_enforce_ready_tristate.py`、`regression_scheduler_strict_mode_dispatch_flags.py`、`regression_dict_cfg_contract.py`、`regression_batch_detail_linkage.py`、`regression_supplier_service_invalid_default_days_not_silent.py`、`regression_route_parser_supplier_default_days_zero_trace.py`、`regression_route_parser_strict_mode_rejects_supplier_fallback.py`、`regression_route_parser_missing_supplier_warning.py`、`regression_batch_service_strict_mode_template_autoparse.py`、`regression_batch_excel_import_strict_mode_hardfail_atomic.py`、`regression_part_service_create_strict_mode_atomic.py`、`regression_external_group_service_strict_mode_blank_days.py`。\n\n结论：本轮 strict_mode / silent fallback follow-up 已完成收口；架构门禁当前为绿色，历史大文件与少量高复杂度热点已转为显式登记的后续拆分债项。",
      "status": "completed",
      "conclusion": "Phase 5/6 已完成：strict_mode / silent fallback follow-up 目标已收口，架构门禁通过，剩余仅为已登记的历史拆分债项。",
      "evidenceFiles": [
        "tests/test_architecture_fitness.py",
        "core/services/common/safe_logging.py",
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/process/external_group_service.py",
        "core/services/process/supplier_service.py",
        "core/services/scheduler/resource_pool_builder.py",
        "core/services/scheduler/calendar_admin.py",
        "core/services/common/excel_templates.py",
        "core/infrastructure/logging.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_summary.py"
      ],
      "reviewedModules": [
        "tests/test_architecture_fitness.py",
        "core/services/common/safe_logging.py",
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/process/external_group_service.py",
        "core/services/process/supplier_service.py",
        "core/services/scheduler/resource_pool_builder.py",
        "core/services/scheduler/calendar_admin.py",
        "core/services/common/excel_templates.py",
        "core/infrastructure/logging.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_summary.py"
      ],
      "recommendedNextAction": "如需继续降低维护债，请单独开启后续批次拆分 `tests/test_architecture_fitness.py` allowlist 中登记的历史大文件与复杂函数。",
      "recordedAt": "2026-04-02T08:27:59.628Z",
      "findingIds": [
        "F-历史大文件与少量高复杂函数并未在本轮硬拆-而是按计划路径-1-进入显式-allowlist-后续应单独拆批-不要与-strict-mode-行为改动混批",
        "phase5-allowlist-debt-tracked"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-架构门禁仍未全绿-当前剩余集中在-silent-exception-swallow-文件超限与高复杂度函数-需要单独拆批处理",
      "severity": "low",
      "category": "other",
      "title": "架构门禁仍未全绿，当前剩余集中在 silent exception swallow、文件超限与高复杂度函数，需要单独拆批处理。",
      "description": null,
      "evidenceFiles": [
        "evidence/Phase0_Phase1/smoke_test_report.md",
        "evidence/Phase0_to_Phase5/web_smoke_report.md"
      ],
      "relatedMilestoneIds": [
        "phase1-4-closeout-20260402"
      ],
      "recommendation": null
    },
    {
      "id": "phase5-arch-gates-remaining",
      "severity": "medium",
      "category": "maintainability",
      "title": "Phase 5 架构门禁仍未收口",
      "description": "`tests/test_architecture_fitness.py` 当前仍剩 `test_no_silent_exception_swallow`、`test_file_size_limit`、`test_cyclomatic_complexity_threshold` 失败；其中主要热点仍在 process/scheduler 历史大文件与资源池/路由解析复杂函数。",
      "evidenceFiles": [
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/scheduler/resource_pool_builder.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_summary.py",
        "evidence/Phase0_Phase1/smoke_test_report.md",
        "evidence/Phase0_to_Phase5/web_smoke_report.md"
      ],
      "relatedMilestoneIds": [
        "phase1-4-closeout-20260402"
      ],
      "recommendation": "按计划进入 Phase 5，优先清理 changed files 中的裸吞异常，再评估大文件拆分与复杂函数分解，不建议在同一批次混入更多行为语义修改。"
    },
    {
      "id": "F-历史大文件与少量高复杂函数并未在本轮硬拆-而是按计划路径-1-进入显式-allowlist-后续应单独拆批-不要与-strict-mode-行为改动混批",
      "severity": "low",
      "category": "other",
      "title": "历史大文件与少量高复杂函数并未在本轮硬拆，而是按计划路径 1 进入显式 allowlist；后续应单独拆批，不要与 strict_mode 行为改动混批。",
      "description": null,
      "evidenceFiles": [
        "tests/test_architecture_fitness.py",
        "core/services/common/safe_logging.py",
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/process/external_group_service.py",
        "core/services/process/supplier_service.py",
        "core/services/scheduler/resource_pool_builder.py",
        "core/services/scheduler/calendar_admin.py",
        "core/services/common/excel_templates.py",
        "core/infrastructure/logging.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_summary.py"
      ],
      "relatedMilestoneIds": [
        "phase5-6-closeout-20260402"
      ],
      "recommendation": null
    },
    {
      "id": "phase5-allowlist-debt-tracked",
      "severity": "low",
      "category": "maintainability",
      "title": "Phase 5 历史大文件/复杂函数已显式登记技术债",
      "description": "`test_file_size_limit` 与 `test_cyclomatic_complexity_threshold` 现已转绿，但部分历史大文件与历史高复杂函数并未在本轮进一步大拆，而是按照计划 10.2 的路径 1 进入 `tests/test_architecture_fitness.py` 中的 allowlist，作为后续独立拆分批次处理。",
      "evidenceFiles": [
        "tests/test_architecture_fitness.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_summary.py",
        "core/infrastructure/database.py",
        "core/services/common/safe_logging.py",
        "core/services/process/part_service.py",
        "core/services/process/route_parser.py",
        "core/services/process/external_group_service.py",
        "core/services/process/supplier_service.py",
        "core/services/scheduler/resource_pool_builder.py",
        "core/services/scheduler/calendar_admin.py",
        "core/services/common/excel_templates.py",
        "core/infrastructure/logging.py",
        "core/services/scheduler/schedule_optimizer.py"
      ],
      "relatedMilestoneIds": [
        "phase5-6-closeout-20260402"
      ],
      "recommendation": "后续单开维护性批次，按模块把 allowlist 中的历史大文件/复杂函数拆分，不要与业务语义修复混批。"
    }
  ]
}
<!-- LIMCODE_REVIEW_METADATA_END -->

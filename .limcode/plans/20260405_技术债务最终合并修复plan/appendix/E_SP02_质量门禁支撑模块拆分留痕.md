# E：SP02 质量门禁支撑模块拆分留痕

- 记录时间：2026-04-10
- 关联子 plan：`./../subplans/SP02_质量门禁与治理台账.md`
- 目的：记录 `tools/quality_gate_support.py` 拆分后的稳定入口、模块边界、回归口径与后续改动注意事项，避免后续执行“最终合并修复 plan”时因为误改导入路径、模板或样本坐标造成二次断裂。

## 一、拆分背景

原 `tools/quality_gate_support.py` 已膨胀到 1500+ 行，同时承担：

1. 常量与路径工具；
2. 治理台账读写与结构校验；
3. 静默回退 / 复杂度 / 超长文件扫描；
4. 三类主条目构造与自动字段刷新；
5. 迁移、基线冻结、架构门禁读取口径。

这会让后续执行者在修改任一处时，很难快速判断“该改哪一层、会不会波及其它逻辑”。因此本次只做**按职责拆分**，不改对外导入入口，不改门禁语义，不改台账事实源，不改脚本入口命令。

## 二、拆分结果

### 1. 稳定对外入口

后续外部调用**继续只认**：

- `tools/quality_gate_support.py`

该文件现在是稳定外观层，只负责转发导出；**不要**让脚本、测试、文档直接改为导入内部拆分模块，否则后续再拆会重新放大改动面。

### 2. 新模块边界

| 文件 | 当前行数 | 职责 |
|---|---:|---|
| `tools/quality_gate_support.py` | 92 | 稳定外观层，保留既有导入路径 |
| `tools/quality_gate_shared.py` | 263 | 常量、路径工具、结构块解析与启动链样本定义 |
| `tools/quality_gate_ledger.py` | 388 | 治理台账读写、排序、结构校验、结构块渲染 |
| `tools/quality_gate_scan.py` | 483 | 静默回退 / 复杂度 / 超长文件扫描与样本点验真 |
| `tools/quality_gate_entries.py` | 133 | 三类主条目构造、默认说明、自动字段刷新 |
| `tools/quality_gate_operations.py` | 375 | 迁移、基线刷新、自动字段回刷、架构门禁读取口径 |

### 3. 调用边界

- `scripts/run_quality_gate.py`、`scripts/sync_debt_ledger.py`、`tests/test_architecture_fitness.py` 继续导入 `tools.quality_gate_support`。
- 内部模块之间按职责互调，不允许把脚本层直接绑到 `quality_gate_scan.py`、`quality_gate_operations.py` 等实现细节上。

## 三、这次拆分顺手修掉的隐藏问题

1. `render_ledger_markdown()` 模板已同步纳入当前文档真实口径：
   - `status` 合法值说明；
   - 静默回退门禁边界说明。  
   若未来只改 `开发文档/技术债务治理台账.md` 正文、不改模板，下次 `save_ledger()` 会把文案覆盖回旧版本。
2. 启动链样本 `launcher.py:stop_runtime_from_dir` 的坐标已随前序文档字符串改动同步刷新。
3. 拆分后引用链追踪证据仍维持原入口不变，并且当前追踪器已补纳入：
   - `web/bootstrap/`
   - `web/viewmodels/`
   - `scripts/`
   - `tools/`

## 四、后续执行时必须遵守的约束

### 1. 外部导入约束

后续如果只是调用现有能力：

- **只从** `tools.quality_gate_support` 导入。

只有当你在做“再次内部重构”时，才允许改内部模块之间的导入关系。

### 2. 台账模板约束

凡是改了以下任一内容：

- `开发文档/技术债务治理台账.md` 的固定说明文字；
- `status` 合法值集合；
- 静默回退门禁边界说明；

必须同步检查：

- `tools/quality_gate_ledger.py` 里的 `render_ledger_markdown()`；
- `tools/quality_gate_shared.py` 里的常量；
- `scripts/sync_debt_ledger.py` 的命令行参数约束。

### 3. 启动链样本约束

凡是改了以下文件的行号分布：

- `web/bootstrap/factory.py`
- `web/bootstrap/runtime_probe.py`
- `web/bootstrap/plugins.py`
- `web/bootstrap/launcher.py`
- `web/ui_mode.py`

都要同步检查：

- `tools/quality_gate_shared.py` 中 `STARTUP_SAMPLE_EXPECTATIONS` 的坐标；
- `python -m pytest -q tests/test_architecture_fitness.py`

否则很容易出现“逻辑没坏，但样本点失配导致门禁红”的假失败。

### 4. 静默回退口径约束

不要在 `quality_gate_scan.py` 里单独改分类口径后就停下；任何这类改动都必须同步核对：

- `quality_gate_operations.py` 中 `architecture_silent_scan_entries()` 的门禁边界；
- `开发文档/README.md` 与 `开发文档/技术债务治理台账.md` 的边界说明；
- 已落账条目的 `handler_fingerprint` 与样本点是否需要刷新。

### 5. 证据追踪约束

引用链证据现在依赖 `.limcode/skills/aps-deep-review/scripts/reference_tracer.py` 的搜索目录。若未来再迁路径，至少同步检查：

- `grep_callers()` 的搜索目录；
- `_classify_layer()` 的层级映射；
- `evidence/DeepReview/reference_trace.md` 是否需要重生。

## 五、已完成验证

本次拆分后已实际执行：

```powershell
python -m ruff check tools/quality_gate_shared.py tools/quality_gate_ledger.py tools/quality_gate_scan.py tools/quality_gate_entries.py tools/quality_gate_operations.py tools/quality_gate_support.py scripts/run_quality_gate.py scripts/sync_debt_ledger.py tests/test_architecture_fitness.py tests/test_sync_debt_ledger.py tests/test_run_quality_gate.py
python -m pytest -q tests/test_architecture_fitness.py tests/test_sync_debt_ledger.py tests/test_run_quality_gate.py
python scripts/run_quality_gate.py
python .limcode/skills/aps-deep-review/scripts/reference_tracer.py --file tools/quality_gate_support.py --file tools/quality_gate_shared.py --file tools/quality_gate_ledger.py --file tools/quality_gate_scan.py --file tools/quality_gate_entries.py --file tools/quality_gate_operations.py --file scripts/run_quality_gate.py --file scripts/sync_debt_ledger.py --file web/bootstrap/launcher.py
```

验证结果：

- 代码风格检查通过；
- 定向回归通过；
- 统一质量门禁通过；
- `evidence/DeepReview/reference_trace.md` 已重生成，当前汇总为 109 处调用关系、0 项跨层边界风险。

## 六、2026-04-10 补充收尾修正

拆分完成后又补了一轮收尾治理，避免内部模块边界和运行态提示继续积灰：

1. `quality_gate_entries.py`、`quality_gate_ledger.py`、`quality_gate_scan.py` 中跨模块复用的助手函数已统一改成共享命名：`build_default_note`、`find_existing_by_id`、`remove_entries_by_predicate`、`entry_sort_key`、`complexity_scan_map`；不再依赖 `__all__` 导出带前导下划线的名称来表达共享边界。
2. `tools/`、`scripts/` 已补包标记文件，确保脚本与测试在不同导入上下文下都能稳定按包解析。
3. `scripts/run_quality_gate.py` 的运行态不确定原因已补上“缺少运行时契约，无法做健康探测”的明确提示，避免只看到 `pid_state=unknown` 却不知道为什么没有健康检查结果。
4. `_run_command()` 的返回码判定已收敛为直接比较 `completed.returncode != 0`，不再保留冗余的整型兜底写法。
5. 运行态清理提示所用路径已通过 `launcher.resolve_runtime_state_paths()` 统一向启动器取值，避免 `scripts/run_quality_gate.py` 自己硬编码 `logs/aps_runtime.json`、`logs/aps_runtime.lock` 这类路径知识。
6. 统一质量门禁现在会显式执行 `python scripts/sync_debt_ledger.py check`，把治理台账 `current_value` 漂移一并纳入阻断，而不是只依赖架构门禁里的“新增/陈旧”断言。
7. 因 `launcher.py` 新增公共路径助手导致启动链行号与文件行数变化，已同步刷新 `STARTUP_SAMPLE_EXPECTATIONS` 与治理台账启动链基线；否则门禁会因 `stop_runtime_from_dir` 样本坐标失配和 `oversize:web-bootstrap-launcher` 的 `current_value` 漂移直接失败。
8. 引用链证据已重生成；当前 `reference_trace.md` 汇总为 124 处调用关系、5 条启发式风险。新增风险均来自 `find_existing_by_id()` 返回 `Optional` 后直接透传给接受 `existing: Optional[...]` 的构造函数，属于追踪器静态误报，不代表真实边界断裂。
9. README 的统一门禁步骤已补上 `python scripts/sync_debt_ledger.py check`，避免根文档再落后于 `run_quality_gate.py` 的实际顺序。
10. `resolve_runtime_state_paths()` 现已同时返回 `runtime_dir` 与 `state_dir`，便于调用方在传入仓库根、运行根或 `logs/` 目录时都能拿到一致的诊断上下文。
11. `tests/test_architecture_fitness.py` 里来自 `tools.quality_gate_support` 的双导入已合并，减少同源导入分裂造成的阅读噪音。

这批改动不改变对外稳定入口，也不改变统一门禁语义，属于拆分后的边界澄清与可维护性收口。

## 七、给后续执行者的最短提示

如果你后面在 SP02 / SP03 继续改门禁：

1. 对外导入别动，继续走 `tools.quality_gate_support`；
2. 文档模板、状态集合、样本坐标、证据追踪目录这四处最容易漏；
3. 若内部模块需要跨文件复用助手函数，优先直接使用共享命名，不要再制造“看起来私有、实际上跨模块依赖”的半隐藏名称；
4. 改完至少跑：
   - `python -m pytest -q tests/test_architecture_fitness.py`
   - `python scripts/sync_debt_ledger.py check`
   - `python scripts/run_quality_gate.py`

做到这几点，后续再接“最终合并修复 plan”时就不容易在门禁基础设施层面再次踩坑。

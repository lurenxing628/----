---
doc_type: architecture-proposal
status: approved
created: 2026-11-09
updated: 2026-11-10
scope: 门禁检查定义、执行回执、结果复用、完整证明与现行规则收口
parent: aps-architecture-consolidation-roadmap.md
implementation: completed
---

# 门禁工具链原地瘦身与规则收口设计

## 1. 目标与核心原则转变（原地做源头减法，不拆 4 个新文件）

本页属于[架构收敛总规划](aps-architecture-consolidation-roadmap.md)，描述已对齐定稿并已在 `A4`（`tooling-definition`）完成落地的目标设计。
核心目标是：**让新增或修改一个门禁检查只改一处 `GateCheckSpec` 声明；原地斩断反向导入与死代码孤岛；消除单步重复子进程与绑定历史 commit 的临时扫描器**。

**拒绝拆文件搬家，原地做源头减法**：
- [tools/quality_gate_shared.py](../../../tools/quality_gate_shared.py) 中有 600+ 行是全仓 22 个技术债务台账与扫描脚本共用的真实底座（台账标记块解析、公共路径归一化、回执读写原语等）。
- 本设计**保留 `quality_gate_shared.py`**，不拆出 4 个新文件，不为搬家而改动 22 个扫描脚本的导入路径。
- 验收标准是**单一 `GateCheckSpec` 声明源、单向模块依赖、删除 0 生产调用死代码孤岛、消除重复子进程与过时临时扫描器**，而不是按文件数或行数指标搬运代码。

用户已明确不要求历史缓存与旧格式兼容：实施时一次迁移全部消费者，整体切换；旧 manifest、proof、receipt、cache 不转换、不参与新版本核销，历史证据文件原位保留供人工追溯；新版本结果由实际运行重新生成，不设置兼容开关或双写阶段。

## 2. 现状病灶与保留价值

| 当前证据 | 核心病灶 | 原地瘦身动作 |
|---|---|---|
| [quality_gate_shared.py:706](../../../tools/quality_gate_shared.py#L706) 仅声明命令字符串，[long_gate_manifest.py:91](../../../tools/long_gate_manifest.py#L91) 与 [:208](../../../tools/long_gate_manifest.py#L208) 按 display/argv 反猜类别并维护 scopes 大分支 | 改一个检查要同步改命令表、manifest 分类器和 scopes 分支 | 在现有声明层原地定义 `GateCheckSpec`，彻底删除 `classify_quality_gate_command` 与重复 scopes 分支 |
| [run_quality_gate.py:1028](../../../scripts/run_quality_gate.py#L1028) 按 `display` 字符串分派处理器 | runner 内部维护了第二套字符串分类逻辑 | 改为直接消费 `GateCheckSpec` 的显式字段 |
| [quality_gate_shared.py:1312](../../../tools/quality_gate_shared.py#L1312) 反向导入 `long_gate_cache / fingerprint / manifest / schema` | `_reusable_quality_gate_results` 与 `verify_quality_gate_manifest`（及 manifest/replay 验证闭包 `:529-551`、`:579-673`、`:986-999`、`:1068-1095`、`:1126-1457`）在 `core/web/data/scripts/tools` 主链中 0 调用，仅被 `aps-full-selftest` 技能脚本与测试引用并造成双向循环依赖 | `aps-full-selftest` 同步迁入直接调用共同 runner（`scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache --no-resume`）并锁步纳入 `QUALITY_GATE_TOOL_PATHS` / `pyrightconfig.tools.json`；按符号调用闭包删除上述 manifest/replay 死代码孤岛及其专属测试断言（完整保留 `:1460-1502` 活函数底座与 `:458` 使用的回执/resume 原语）；将 [long_gate_schema.py:208](../../../tools/long_gate_schema.py#L208) 的 `repo_identity` 下沉到 schema 层 |
| [run_quality_gate.py:955-987](../../../scripts/run_quality_gate.py#L955-L987) `_assert_pyright_tools_coverage` 及 [:994](../../../scripts/run_quality_gate.py#L994) 调用 | 单步跑完一次 `pyright` 后，非缓存分支又起第二个 `pyright --outputjson` 子进程数文件数 | 删除 `_assert_pyright_tools_coverage` 第二次 `pyright` 子进程及 `:994` 调用，统一保留 [:940](../../../scripts/run_quality_gate.py#L940) 配置文件 `include == list(QUALITY_GATE_TOOL_PATHS)` 校验与单次执行 |
| [scan_anti_regression_gate.py](../../../tools/scan_anti_regression_gate.py) 与 [scan_aps_three_gap_py38_scope.py](../../../tools/scan_aps_three_gap_py38_scope.py) | 绑定历史 `d4589d77` diff、重复收集测试、检查形式主义 docstring、拆分两套 Py3.8 语法扫描 | 退役两个临时扫描器；生产文件范围覆盖并入 `test_registry`，Py3.8 扫描合并到 `scan_py38plus_syntax.py --fail-on-hit` |

现有“原内容、真实命令、环境、日志、输出与实际结果一致才复用”的机制有实际价值，完整保留：
- 保留[成功缓存两段写入](../../../tools/long_gate_cache.py#L1109)：先准备，汇总成功落盘后才提交缓存。
- 保留[实际失败复用](../../../tools/long_gate_cache.py#L812)的失败性质：复用失败证据不能把本次状态改成通过。
- 保留 [scripts/run_quality_gate.py:458](../../../scripts/run_quality_gate.py#L458) 实际调用的 receipt/resume 校验原语。

## 3. 五项具体源头瘦身动作

### 3.1 动作 1：单一 `GateCheckSpec` 消除两处字符串分类旁路

在现有门禁声明层（[quality_gate_shared.py:706](../../../tools/quality_gate_shared.py#L706)）直接用 Python 3.8 `dataclass(frozen=True)` 定义 `GateCheckSpec`，使命令与证据合同合一：

| 字段 | 类型与含义 | 规则 |
|---|---|---|
| `check_id` | `str`（如 `import_cycles_production`） | 稳定唯一身份，与列表序号、显示文案分离 |
| `entry_type` | `str`（如 `import_cycles`、`full_test_debt`） | 显式指明证据处理类别，彻底废除从 display/argv 反猜 |
| `command` | `GateCommand` | 实际 argv、display、capture_output、output_policy、env_overlay |
| `scopes` | `GateCheckScopes` | 内聚 `input_scopes`、`config_scopes`、`tool_scopes`、`dependency_scopes`、`env_keys` |
| `output_files` | `Tuple[str, ...]` | 命令应产出的证明文件，由回执绑定实际内容 |
| `reuse_policy` | `str`（`none` / `success` / `success_or_failure`） | 显式表达允许的缓存复用策略 |
| `proof_kind` | `str`（`ordinary` / `collect` / `full_test_debt` / `required`） | 显式驱动 runner 处理器与 fingerprint 特殊输入捕获 |

**配套清理与契约同步**：
1. 彻底删除 [tools/long_gate_manifest.py:91](../../../tools/long_gate_manifest.py#L91) 的 `classify_quality_gate_command` 及第 [208](../../../tools/long_gate_manifest.py#L208) 行的重复 scopes 大分支；manifest 直接序列化 `GateCheckSpec`。
2. 同步改造 [scripts/run_quality_gate.py:1028](../../../scripts/run_quality_gate.py#L1028)（runner 内部按 `display` 字符串分派处理器的第二套分类逻辑），改为直接按 `GateCheckSpec.check_id / proof_kind` 分派。
3. 同步更新 [quality_gate_shared.py:382](../../../tools/quality_gate_shared.py#L382)（确保命令规范化保留完整 `GateCheckSpec` 描述字段，不丢弃元数据）、缓存索引键以及 [run_quality_gate.py:2165](../../../scripts/run_quality_gate.py#L2165) 的 `--long-gate-force-rerun ENTRY_ID` CLI 契约（直接匹配 `spec.check_id`）。

### 3.2 动作 2：按符号调用闭包删除 `quality_gate_shared.py` 中的 manifest/replay 0 调用死代码孤岛，斩断反向导入

源码与引用闭包核查确认：
- [quality_gate_shared.py:1312](../../../tools/quality_gate_shared.py#L1312) 的 `_reusable_quality_gate_results` 与第 [1405](../../../tools/quality_gate_shared.py#L1405) 行的 `verify_quality_gate_manifest`（及其专属下层调用链：`collect_current_pytest_nodeids` [:529-543](../../../tools/quality_gate_shared.py#L529-L543)、`_resolve_quality_gate_command_args` [:546-551](../../../tools/quality_gate_shared.py#L546-L551)、`replay_quality_gate_command_plan` [:579-673](../../../tools/quality_gate_shared.py#L579-L673)、`_verify_quality_gate_collection_proof` [:986-999](../../../tools/quality_gate_shared.py#L986-L999)、`_verify_receipt_output_content` 与 `_is_default_collect_command` [:1068-1095](../../../tools/quality_gate_shared.py#L1068-L1095)、以及 `_verify_quality_gate_receipt_payload` 至 `git_status_short_lines` [:1126-1457](../../../tools/quality_gate_shared.py#L1126-L1457)）在 `core/web/data/scripts/tools` 主链中 0 调用，仅被 `.limcode/skills/aps-full-selftest/scripts/run_full_selftest.py` 与 [tools/host_tests/test_quality_gate_shared.py](../../../tools/host_tests/test_quality_gate_shared.py) 引用；将 `aps-full-selftest` 同步迁入直接委托共同门禁入口 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache --no-resume`（并锁步纳入 `QUALITY_GATE_TOOL_PATHS` 与 `pyrightconfig.tools.json`）后，该重放闭包彻底降为 0 生产调用孤岛。
- 正是 `_reusable_quality_gate_results` 在函数体内反向 import 了 `long_gate_cache`、`long_gate_fingerprint`、`long_gate_manifest` 与 `long_gate_schema`。
- 与之相对，[scripts/run_quality_gate.py:458-490](../../../scripts/run_quality_gate.py#L458-L490) 实际调用的 `--resume-from` 回执校验原语（`_load_verified_quality_gate_receipt` [:1002-1033](../../../tools/quality_gate_shared.py#L1002-L1033)、`_verify_receipt_header` [:1036-1051](../../../tools/quality_gate_shared.py#L1036-L1051)、`_verify_receipt_command_fields` [:1054-1065](../../../tools/quality_gate_shared.py#L1054-L1065)、`_verify_receipt_execution_fields` [:1098-1123](../../../tools/quality_gate_shared.py#L1098-L1123)、`_command_output_policy` [:554-556](../../../tools/quality_gate_shared.py#L554-L556)、`_normalize_command_output_for_policy` [:559-576](../../../tools/quality_gate_shared.py#L559-L576)），以及文件尾部的 [quality_gate_shared.py:1460-1502](../../../tools/quality_gate_shared.py#L1460-L1502)（`collect_quality_rule_files`、`is_startup_scope_path`、`ensure_single_marker`、`extract_marked_block`、`extract_json_code_block`、`render_marked_json_block`，被 `quality_gate_operations.py`、`quality_gate_scan.py`、`quality_gate_ledger.py` 生产调用）均为活代码底座，**必须完整保留**。

**收口措施**：
1. 连根删除上述 0 生产调用的 manifest/replay 验证死代码闭包（`:529-551`、`:579-673`、`:986-999`、`:1068-1095`、`:1126-1457`），并同步删除 [test_quality_gate_shared.py](../../../tools/host_tests/test_quality_gate_shared.py) 中仅测试该死代码闭包的断言与用例（`:52-53`、`:68`、`:95-101`、`:107`、`:121-125`、`:135-140`、`:146-148`、`:153-159`、`:238-346`）；完整保留 [quality_gate_shared.py:1460-1502](../../../tools/quality_gate_shared.py#L1460-L1502) 活函数底座与 [scripts/run_quality_gate.py:458](../../../scripts/run_quality_gate.py#L458) 使用的回执/resume 校验原语。
2. 将 [tools/long_gate_schema.py:208](../../../tools/long_gate_schema.py#L208) 反向从 `quality_gate_shared` 导入的 `repo_identity` 下沉到底层 `long_gate_schema.py`，并统一失败语义：Git 身份查询失败时直接显式报错，绝不把猜测的 `root / ".git"` 路径包装成有效仓库身份。

收口后的模块单向依赖关系：
```text
CLI / Git hooks
  → scripts/run_quality_gate.py / scripts/run_daily_quality_gate.py
  → tools/long_gate_cache.py → tools/long_gate_fingerprint.py → tools/long_gate_manifest.py
  → tools/quality_gate_shared.py → tools/long_gate_schema.py
```

### 3.3 动作 3：修正 `FingerprintFileSnapshot` 生命周期（单次缓存评估作用域）

**严禁跨整次门禁全程共享同一个文件快照**：
- 后序的 `required_regressions` 检查必须读取前序 `full_test_debt` 刚刚在磁盘上生成的阶段证明文件（见 [long_gate_manifest.py:435](../../../tools/long_gate_manifest.py#L435)）。
- 如果在门禁启动时创建一个全局 `FingerprintFileSnapshot` 并贯穿全程复用，前序命令新产出的证明文件在快照中将是旧态或缺失，导致后序依赖检查误判。
- **生命周期规定**：`FingerprintFileSnapshot` 只属于**单次缓存评估阶段**（[long_gate_fingerprint.py:237](../../../tools/long_gate_fingerprint.py#L237)）。任何门禁命令实际执行并产出新文件后，下一次指纹计算与证据核验必须重新捕获最新文件状态。

### 3.4 动作 4：删除 `scripts/run_quality_gate.py:955-995` 单步内第二次重复的 `pyright` 子进程

当前 `_handle_pyright_tools_quality_gate_command`（[run_quality_gate.py:989-995](../../../scripts/run_quality_gate.py#L989-L995)）在执行完一次 `pyright` 返回 0 之后，非缓存命中分支（[:994](../../../scripts/run_quality_gate.py#L994)）又调用 `_assert_pyright_tools_coverage`（[run_quality_gate.py:955-987](../../../scripts/run_quality_gate.py#L955-L987)）额外启动第二个 `pyright --outputjson` 子进程，只为了统计 `filesAnalyzed >= len(QUALITY_GATE_TOOL_PATHS)`。

**收口措施**：
- 直接删除 `_assert_pyright_tools_coverage`（[run_quality_gate.py:955-987](../../../scripts/run_quality_gate.py#L955-L987)）及其在 [:994](../../../scripts/run_quality_gate.py#L994) 的调用。
- 在普通执行与 `reused_success_cache` 路径下，统一保留调用 [run_quality_gate.py:940](../../../scripts/run_quality_gate.py#L940) 的 `_assert_pyright_tools_config_matches_tool_paths()`（校验 `pyrightconfig.tools.json` 中 `include == list(QUALITY_GATE_TOOL_PATHS)`）以及单步内唯一一次实际 `pyright` 执行。

### 3.5 动作 5：退役绑定历史 `d4589d77` 与旧路线图的临时扫描器

1. **退役 [tools/scan_anti_regression_gate.py](../../../tools/scan_anti_regression_gate.py) 及其独立门禁步骤（[quality_gate_shared.py:792](../../../tools/quality_gate_shared.py#L792)）**：
   - 该脚本硬编码了历史 `DEFAULT_BASE_REF = "d4589d77"`。
   - 将其唯一有实质价值的规则——**“当前全部生产源文件必须落在 `test_registry` 的 required 回归组 `*_file_scopes` 覆盖范围内”**——直接并入 `test_registry` 核验逻辑，按当前工作树完整生产文件集检查，彻底摆脱对 `d4589d77` 增量 diff 的依赖。
   - 测试收集统一复用 `pytest` 既有机制，取消仅要求测试文件包含模块 docstring 的形式主义检查。

2. **退役 [tools/scan_aps_three_gap_py38_scope.py](../../../tools/scan_aps_three_gap_py38_scope.py)（[quality_gate_shared.py:810](../../../tools/quality_gate_shared.py#L810)）**：
   - 将 [quality_gate_shared.py:769](../../../tools/quality_gate_shared.py#L769) 与 [:810](../../../tools/quality_gate_shared.py#L810) 两处 Py3.8+ 语法扫描合并为统一调用 [tools/scan_py38plus_syntax.py](../../../tools/scan_py38plus_syntax.py)。
   - 保留宿主专属目录排除、annotation 与 runtime 语法检查，且**必须显式传入 `--fail-on-hit`**（见 [scan_py38plus_syntax.py:663](../../../tools/scan_py38plus_syntax.py#L663)，该脚本默认不传 `--fail-on-hit` 时命中也返回 `0`）。

3. **更新路线图校验目标**：
   - 将 [quality_gate_shared.py:751](../../../tools/quality_gate_shared.py#L751) 校验旧路线图 YAML 的参数更新为校验当前路线图。

## 4. 失败、跳过与有效复用语义

| 情况 | 处理结果 |
|---|---|
| 当前格式、相同实际命令/输入/环境/工具，日志及输出完整，原结果通过 | 允许按 `GateCheckSpec` 复用通过结果，并写本次复用回执（`execution_source=reused`） |
| 原结果失败，且该检查 `reuse_policy` 允许失败复用 | 保留原非零退出码及原日志，本次仍失败；`--long-gate-force-rerun ENTRY_ID` 时强制重跑 |
| 缺日志、输出改动、源码改动、节点集合变化、工具或环境变化 | 对应检查重新执行，不凭 HEAD 或缓存文件存在跳过 |
| 中断、超时、部分写入或 summary 落盘失败 | 不提交预备成功缓存，不标记通过 |
| 旧版本 manifest/proof/receipt/cache | 不读取为本次证据，不转换；新运行重新生成当前版本 |
| Windows/PowerShell/Win7 原生节点 skipped | 保持未执行（见[台账监听验收项](../../../开发文档/技术债务治理台账.md#L1915)），绝不把平台跳过算作通过 |

## 5. 日常、完整与最终验收

沿用[当前质量治理入口](../../../开发文档/README.md#L53)：
- 日常影响选择仍由 `test_registry` 与 `DailyGateScope` 决定，消费同一份 `GateCheckSpec` 定义。
- 普通完整门禁允许显式 dirty 诊断，但不出 clean proof；最终验收要求最终 HEAD、起止干净工作区及完整结果一致。
- `--long-gate-cache`、`--no-long-gate-cache`、`--no-resume`、`--long-gate-force-rerun` 保持清晰的用户语义。

## 6. 既有验证与完成条件

优先复用并更新现有 host tests，删除仅为已退役死代码孤岛续命的用例：

| 验证内容 | 当前用例入口 |
|---|---|
| 输入、命令、环境、日志与输出改变导致失效；失败复用仍失败 | [test_long_gate_content.py:193](../../../tools/host_tests/test_long_gate_content.py#L193)、[:225](../../../tools/host_tests/test_long_gate_content.py#L225) |
| 实际节点、required 覆盖与阶段报告保真（含前序产出后刷新文件观察） | [test_long_gate_content.py:423](../../../tools/host_tests/test_long_gate_content.py#L423) |
| 回执身份、真实输出与源码证明契约（删除 manifest/replay 0 调用死代码闭包断言） | [test_quality_gate_shared.py:46](../../../tools/host_tests/test_quality_gate_shared.py#L46)、[:71](../../../tools/host_tests/test_quality_gate_shared.py#L71)、[:132](../../../tools/host_tests/test_quality_gate_shared.py#L132) |
| summary 失败不能提交成功缓存 | [test_gate_runner_and_hooks_content.py:971](../../../tools/host_tests/test_gate_runner_and_hooks_content.py#L971) |
| 日常边界扫描、非 ASCII 路径、pre-push 目标与缓存 | [test_gate_runner_and_hooks_content.py:199](../../../tools/host_tests/test_gate_runner_and_hooks_content.py#L199)、[:370](../../../tools/host_tests/test_gate_runner_and_hooks_content.py#L370)、[:754](../../../tools/host_tests/test_gate_runner_and_hooks_content.py#L754) |
| 语义债务身份不受单纯行号变化影响 | [test_import_cycle_baseline.py:30](../../../tools/host_tests/test_import_cycle_baseline.py#L30) |

## 7. 规则与文档同步清单

| 文件/计划 | 实施时处理方式 |
|---|---|
| [architecture-invariants.mdc:24](../../../.limcode/rules/architecture-invariants.mdc#L24) | 分别说明存储模型、纯输入合同、业务事实与 SQL 仓储；修正一律 `from_row`、强制 `BaseRepository`/统一导出的过窄表述 |
| [interface-patterns.mdc](../../../.limcode/rules/interface-patterns.mdc) | 模板同步采用真实公开边界，不引导新增兼容壳、重导出或第二套装配 |
| [开发文档/README.md:105](../../../开发文档/README.md#L105) 与根 README/交付说明 | 同步更新 schema 版本、检查 ID、复用与平台延期口径；保留日常/完整入口区别 |
| [foundation-boundary-governance](../foundation-boundary-governance/foundation-boundary-governance-roadmap.md) 与 [11 月 2 日专项](../../refactors/2026-11-02-first-principles-cleanup/first-principles-cleanup-apply-notes.md#L40) | 保持已完成状态与原内容证明、两段提交语义，不重复立项 |
| [11 月 7 日残余审计](../../audits/2026-11-07-first-principles-residuals/index.md#L147) | F22 构建加载随前端构建职责收敛处理；F23 radon 扫描上下文仍为独立低收益项，不作为本工作包前置条件 |

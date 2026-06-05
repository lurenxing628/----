# P0 配置层提速 —— 实测结果（2026-06-05）

> 分支 `cleanup/p0-config-speedup`。性质：纯配置改，**零删除、零业务语义改动、零测试增删**（collect-only 仍 4073）。
> 复测 oracle：`tools/scope_probe.py`（对 789 个受门禁影响的源文件逐个算 `_build_impact_plan`，绕开分支 diff 隔离单文件）。

## 做了什么

| 子步 | 文件 | 改动 |
|---|---|---|
| **P0.1** | `scripts/run_daily_quality_gate.py` | `FOCUSED_PYTEST_NODEIDS` 8→3：移除 4 个 `test_long_gate_*_cache` + 1 个 `test_architecture_fitness`（门禁自指，已在各自 group target_paths + CI 全量覆盖），保留 3 个真业务冒烟 |
| **P0.2** | `tools/test_registry_groups_misc.py` | 把 3 个原「不属任何组」的 web/ 顶层文件（`web/__init__.py`/`navigation_context.py`/`request_resource_context.py`）登记进 `request_services` 组，消除它们触发的升全量 |
| **P0.3** | `tools/test_registry_groups_scheduler.py` + `_misc.py` | 8 组里 6 个非-owner 组的宽 glob 收窄到各自页面/逻辑子域 |

### P0.3 收窄策略：owner 安全网（保证零新增升全量）
匹配引擎 `_path_matches_pattern` 用 `fnmatch`（`*` 跨 `/`）；收窄某组的宽 glob 后，**只要该域仍有 ≥1 个 owner 组保留宽 glob 覆盖全域，就不会有文件落到「outside known scopes → 升全量」**。owner 指派：

| 域 | owner 组（保留宽 glob） | 备注 |
|---|---|---|
| `core/**`、`data/**` | `scheduler_run_core` | 任一 core/data 文件至少命中本组 |
| `templates/**`、`static/**`、`web_new_test/**` | `ui_layout_presenters_system` | 任一前端文件至少命中本组 |
| `web/viewmodels/**` | `scheduler_analysis...` | 被契约 `:184` PIN，天然 owner |
| `web/routes/**` | `request_services...` | 被契约 `:171` PIN |
| `templates_excel/**` | `frontend_manual_excel` | — |
| `plugins/**` | `request_services...` | — |

非-owner 组改用页面级窄 glob（如 `templates/scheduler/config*.html`、`static/js/gantt*.js`、`web/viewmodels/scheduler_config*.py`、`core/services/process/**`）保留**本组真关心的页面/逻辑**的 push 覆盖；收过窄只会漏跑（CI 全量兜底），绝不会升全量或破门禁。

## 实测对比（oracle，789 文件）

| 指标 | 收窄前 | 收窄后 |
|---|---|---|
| **升全量文件数** | 4 | **1**（仅 `plugins/.gitkeep` 占位） |
| 命中 1 组 | 65 | **177** |
| 命中 2 组 | 56 | **358** |
| 命中 3 组 | 44 | 212 |
| 命中 4 组 | 161 | 32 |
| 命中 5–7 组 | 459 | 5（其中 4 个是 app.py/config.py/schema.sql/app_new_ui.py 中心文件，应当广跑） |
| **impact 目标测试数 median** | 179 | **80**（计划目标 40–90 ✓） |
| impact 目标测试数 mean | 141 | 89 |

代表文件（命中组/目标测试数）：
- `templates/scheduler/gantt.html`：7组/209 → **2组/99**
- `templates/equipment/equipment.html`：7组/209 → **2组/21**
- `static/css/ui_contract.css`：7组/209 → **1组/9**
- `web/viewmodels/scheduler_resource_dispatch.py`：5组/179 → **1组/90**
- `core/services/scheduler/schedule_service.py`：6组/199 → 3组/164（调度核心确属 run_core+analysis+batches 三组，正确）

## 验证

- `pytest regression_quality_gate_registry_split_scope_contract.py + regression_quality_gate_scan_contract.py + test_run_daily_quality_gate.py` → **68 passed**（所有契约 PIN 完好）。
- `pytest --collect-only tests` → **4073**（与基线一致，零掉）。
- ruff 三文件 → All checks passed。
- **B-9 护栏**：B 锚点 SOURCE 改动仍能拉起对应 B 锚点回归测试（R54/R57 已验证在 impact 集）；5 个 B 锚点 TEST 文件（含 HOLD_FOR_R51/R43 的 main-style）仍正常全量收集。`regression_schedule_result_view_context.py` 收窄前后都不在 impact（只在全量收集），非回归。

## 验收修正（全量门禁 + 红队两轮抓出，已并入本阶段）

1. **第三个 scope 契约（全量门禁抓出，必修已修）**：`test_long_gate_required_regression_cache.py:155`
   有一份硬编码「必须存在于 scope 并集」的 pattern 清单。首版收窄误删了 `docs/**/*.md` 与
   `web_new_test/static/docs/**/*.md` 两个**文档** pattern → 该测试红。修法：group 7 还原这两个 + `static/docs/**/*.md`
   共三项文档 scope（文档改动本就 skip 门禁，收窄它们零提速收益，纯属多余）。修后该测试 + 全部 long_gate/契约共
   **598 passed**。教训：scope 契约不止 `registry_split_scope_contract`，还有 `test_long_gate_required_regression_cache`。
2. **红队 item8（push 盲点，已精确修）**：首版把整树 `web/viewmodels/**` 从 ui_layout 组移除，导致只改
   system 页面 viewmodel（影响整页渲染）时 push 不再拉起 ui_layout 的整页渲染契约组。修法：ui_layout 加回它
   **真正测的** `web/viewmodels/system_*.py` + `web/viewmodels/ui_presenters.py` 两条窄 glob（恢复 system/presenter
   viewmodel 的 push 覆盖，又不重新拉回全 viewmodel 的慢浏览器几何测试）。
3. **FOCUSED 措辞校正**：被移除的 3 个 `test_long_gate_*_cache` 并不在任何 group 的 target_paths 里（这点
   commit message 表述不精确）——它们由**全量门禁**（full gate 对整棵 tests/ 归一化）覆盖，且改它们真正测的
   `tools/long_gate_*.py` 会升全量、改 `run_daily_quality_gate.py` 会拉 quality_gate 组 → 代码真变时仍触发。
   `test_architecture_fitness` 则确在 ui_layout 的 target_paths（改 viewmodel/template/static 仍拉它）。

4. **已知盲点：architecture_fitness 不再随 core/viewmodel 改动在 push 触发（计划认可，CI 兜底）**。
   P0.1 把 `test_architecture_fitness`（viewmodel 越层守卫）移出 FOCUSED + P0.3 把 `core/**`、`web/viewmodels/**`
   从 ui_layout 的 input_file_scopes 移除，叠加后：改 core/普通 viewmodel 文件时 push 不再跑分层守卫
   （改 templates/static/system 路由/system viewmodel 仍会跑；CI 全量门禁始终跑，已实测 21 passed）。
   这是 **PLAN P0.1 明确认可的取舍**（原文「移除 test_long_gate_*/test_architecture_fitness，CI 全量仍跑」），
   红队第二轮亦认定 CI 必兜底、不会漏过 merge，属「快速反馈被削弱」而非「门禁被破坏」。
   **曾尝试**把 architecture_fitness 加进 run_core/analysis 的 target_paths 补回 push 覆盖，但它会扰动
   long_gate required-regressions 的 manifest/proof 缓存系统（`test_required_success_writes_parent_proof_and_reuses_next_run` 红），
   属碰测试系统的 scope creep，已回退——遵「P0 纯配置、不改测试逻辑」原则，按计划接受此盲点。

## 尚未做 / 交接

- **quality_gate 组的 18 个慢自测**（`test_run_quality_gate` 2970 行等）只在改门禁文件时命中（非 always-on，已澄清「always-on」是分支 diff 假象）；它们的慢是 **P2** 的瘦身对象。
- 真实 push 墙钟时间待 P0 提交后实测回填 `BASELINE.md`。

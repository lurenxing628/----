---
doc_type: issue-fix-note
status: completed
date: 2026-09-10
scope: R1-L
---

# 第一轮 import resolver 定点收尾

## 结论与冻结范围

- 已完成指定 3 条动态导入的可靠静态解析；没有修改对应原测试、baseline、扫描 roots 或忽略项。
- 冻结源码下 Python 3.8.10 定点测试 75 passed；pyright 1.1.406 检查 5 个文件，0 errors / 0 warnings。
- 本轮只有 dirty-worktree targeted proof。仓库并行变化，未 stage / commit；不是全仓 clean proof。
- 未执行全站验收、5000 压测、Win7 发布、旧 UI 下线、全局 build、预览服务操作或生产 DB 操作。
- 无新增 tool 文件。新增测试文件 `tests/gate_meta/test_round1_import_resolver.py`，49 个用例；registry 未改，交主线/K 聚合。

## 根因和最小修正

- 原 `tools/import_cycle_analysis.py:visit_Call` 仅接受实参本身是字符串 AST Constant；固定字符串绑定也被报告 unresolved。
- 原 `spec_from_file_location` 一律 unresolved。它的加载名称不是源模块名，不能直接拿名称造边。
- `tools/import_cycle_graph.py:95` 检查词法绑定：参数、赋值/删除、import 别名、类/函数声明、global/nonlocal、星号 import 等冲突均保守处理。
- `tools/import_cycle_graph.py:121` 只允许作用域直接语句里的唯一赋值；`tools/import_cycle_analysis.py:238` 按访问顺序激活常量。条件赋值、使用前未赋值、遮蔽或重绑定不猜测。
- `tools/import_cycle_graph.py:136` 静态求值只覆盖字符串、可信 Name、可信 pathlib.Path、绝对路径 resolve、parent/常量 parents 下标及 Path/字符串路径连接；不 eval 源码，不执行被扫描模块。
- `tools/import_cycle_graph.py:185` 要求绝对路径、实际存在且位于本次文件索引，才映射到真实源模块。动态/相对/缺失路径及定制 loader 保留 unresolved。
- `tools/import_cycle_analysis.py:369` 记录文件来源；`tools/scan_import_cycles.py:256` 不给文件 spec 虚构父包初始化边。
- 原分析文件已有 585 行、`_dynamic_loader_aliases` CC=25。绑定收集与原样 Tarjan 图算法移入现有 graph 文件，分析文件降到 454 行；没有新模块或业务重构。
- 原 scanner 两处预期按新合同更新为“固定绑定产生实际边”，保留真正动态输入检查。专属回归补齐正向边、反向边及 3 个真实源文件只读 AST 检查。

## 三条实际结果

| 调用位置 | 静态证据 | 解析到的实际模块 |
|---|---|---|
| `tests/gate_meta/test_frozen_bundle_contract.py:198` | `:45` 的 `_ANCHOR_MODULE` 唯一字符串赋值 | `core.services.scheduler._frozen_import_anchor` |
| `tests/workbench/test_pending_build_sources.py:22` | `:10` 的 `TOOLS = Path(__file__).resolve().parents[2] / "scripts/workbench"`，再连接 `build.py` | `scripts.workbench.build` |
| `tests/workbench/test_process_readiness.py:133` | `:24` 的 `MODULE` 唯一字符串赋值 | `core.services.workbench.resource_readiness` |

三条均为 lazy。文件 spec 未误映射到临时加载名 `workbench_pending_build`。原测试不执行，仅解析 AST 和核对模块边；测试代码见 `tests/gate_meta/test_round1_import_resolver.py:163`。

## 实际扫描计数与并行边界

- 修改前：2565 modules，parse_errors=0，unresolved=49，相对 baseline 新增 5 条。
- 指定 3 条全部存在。另 2 条来自并行新增 `test_round1_execution_dependency_contract.py:28/29` 字符串拼接，不属于 R1-L。
- 修改后冻结扫描：2569 modules，parse_errors=0，unresolved=43，新增 unresolved=0。
- 49 到 43 不能全部归功于本修复：通用规则解析指定 3 条及已有 baseline 内 `core/services/scheduler/schedule_orchestrator.py:13` 的常量；另外 2 条由 D 改成显式 imports，已与主线消息核对。
- 含测试正式扫描 RC=1，剩余目录 SCC：`tests/gantt|tests/operation_execution|tests/web_pages|tests/workbench`。新增文件 SCC=0、新增目录圈内边=0、新增文件圈内边=0；此 SCC 交回主线，不在 R1-L 重做。
- 主线消息确认产品范围 scanner RC=0；本记录的独立实测是 include-tests，不能混称产品/全仓验收。
- 完整前后扫描为各约 5 MB 的只读输出，保存在 `/tmp/r1-l-import-resolver-ZJdf0U/scan-before.json` 和 `/tmp/r1-l-import-resolver-ZJdf0U/scan-final.json`，SHA-256 见同目录 evidence.json。

## 验证命令与结果

在仓库根目录执行，T=`/tmp/r1-l-import-resolver-ZJdf0U`，所有测试临时目录和 APS 路径均指向 T：

```bash
env PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 APS_ENV=testing APS_DB_PATH=$T/private.db APS_LOG_DIR=$T/logs APS_BACKUP_DIR=$T/backups APS_EXCEL_TEMPLATE_DIR=$T/templates .venv/bin/python -m pytest tests/gate_meta/test_import_cycle_scanner.py tests/gate_meta/test_round1_import_resolver.py tests/gate_meta/test_import_cycle_baseline.py -q -p no:cacheprovider --basetemp=$T/pytest-final
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pyright -p pyrightconfig.tools.json tools/import_cycle_analysis.py tools/import_cycle_graph.py tools/scan_import_cycles.py tests/gate_meta/test_import_cycle_scanner.py tests/gate_meta/test_round1_import_resolver.py --outputjson
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --json
git diff --check -- tools/import_cycle_analysis.py tools/import_cycle_graph.py tools/scan_import_cycles.py tests/gate_meta/test_import_cycle_scanner.py
```

- pytest：75 passed in 0.73s，RC=0；原 scanner 14 + 专属回归 49 + 未修改 baseline 回归 12。
- pyright：5 files，0 errors / 0 warnings，RC=0。最终用本机已有 1.1.406，不升级依赖。
- 质量工具 `scan_oversize_entries` / `scan_complexity_entries` 对上述 5 文件定点检查：无 >500 行文件、无新增 CC>15。既有未改 `tools/scan_import_cycles.py:431 main` CC=20 仍存在，不能写成“整个 complexity 全绿”。
- symbol_locator 在私有 `CHECKUP_CALLGRAPH=$T/callgraph` 查询 `dyn_imports`：定义原 :450，调用方 `_collect_module_edges`；locator 无更多 confident callee，已用 rg 和源码核对。不刷新共享调用图。
- 未修改全局测试/类型配置，没有新增 ignore、cast Any 或 baseline 豁免。

## 源码及数据保留

- 5 个修改/新增源码文件的最终 SHA-256、原测试和 baseline SHA-256、扫描输出摘要及原始输出 hash 均在 `evidence.json`。
- 指定 3 个原测试 hash 与起点一致。`test_frozen_bundle_contract.py` 仍是唯一 staged 文件，index blob 始终为 `3a75549413489ac9de33181b6f490cbe3cd49730`，文件 SHA-256 为 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`。
- 两份 import baseline 与 HEAD 无 diff，含测试 baseline SHA-256 与起点一致。没有改原业务测试为本工具消警。
- 未提交清单：3 个既有工具文件、原 scanner 测试、新增专属测试、本 issue 记录与证据。其他 dirty 全部保留。
- R1-L 到此停止，不接手其他 SCC，不启动全局门禁或后续发布。

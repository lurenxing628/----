# H 懒导出类型声明修复交接

- 状态：已授权的两文件产品修复完成，产品类型检查 0 errors / 0 warnings，定向联合回归 216 passed。
- 仍不是 full gate 或 clean-worktree proof；工作区有既有 dirty，Main 尚未归档到最终 HEAD。H 未 Git 写。
- 本轮产品写集严格限于 `core/services/scheduler/__init__.py`、`core/services/scheduler/schedule_orchestrator.py`。没有修改配置、忽略项、阈值、baseline、算法、DTO、factory/host 或其它产品。

## 修改内容

| 文件 | 本轮变更 |
| --- | --- |
| `core/services/scheduler/__init__.py:59` | 增加 `TYPE_CHECKING` 及 13 个真实类导入声明；静态声明在文件末尾，不移动原 `_EXPORTS`、`__getattr__` 或 `__all__` |
| `core/services/scheduler/schedule_orchestrator.py:4` | 类型导入补 `TYPE_CHECKING`；21 行起补真实 `ScheduleOrchestrationOutcome`、`orchestrate_schedule_run` 声明，旧转口运行逻辑不动 |
| `tests/gate_meta/test_scheduler_lazy_exports_final.py:1` | 新增 35 个用例：2 项静态声明完整性、2 个独立新进程被动加载/未知名拒绝、15 个真实导出 x 2 种新进程导入顺序、1 项 required owner |
| `tools/test_registry_data.py`、`tools/test_registry_groups_scheduler.py` | 新测试只登记一次，实际 required owner 为 `scheduler_run_core`；此组既有 `core/**/*.py` 输入范围覆盖真实目标及两个 root |
| `tests/gate_meta/test_workbench_round1_registry_contract.py` | 历史 R1 集合显式排除本次单独验收的新 H guard；原 582 项、33 组、原哈希与旧 schema 末尾断言仍保留，未把历史基线改成 583，也未删除原断言 |

普通 Python 3.8 下 `TYPE_CHECKING=False`，13+2 个目标导入只作为静态类型声明。末尾放置让原动态导入位置不移动，不需要刷新按行号记录的动态导入 baseline。

修改前后对 `_EXPORTS`、`_TARGET_MODULE`、`__getattr__`、`__dir__`、`__all__` 的 AST 做逐项相等比较，两个产品文件均为 true。新进程测试同时核对真实模块文件路径、`from ... import Name`、重复 getattr 与目标模块对象 `is` 相等；包的缓存与旧转口不缓存行为均锁定。不是仅比较对象名字，也不是在已有导入缓存上假测 cold import。

## 真实验证

测试命令：

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache \
  CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph \
  TMPDIR=/tmp/aps-task-h-01a08b02 \
  APS_ENV=development APS_DB_PATH=/tmp/aps-task-h-lazy-final/runtime/unused.db \
  APS_LOG_DIR=/tmp/aps-task-h-lazy-final/runtime/logs \
  APS_BACKUP_DIR=/tmp/aps-task-h-lazy-final/runtime/backups \
  APS_SYSTEM_JOURNAL_DIR=/tmp/aps-task-h-lazy-final/runtime/journal \
  .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  --basetemp=/tmp/aps-task-h-lazy-final-pytest-v1 \
  --junitxml=/tmp/aps-task-h-lazy-final-v1.xml \
  tests/gate_meta/test_scheduler_lazy_exports_final.py \
  tests/gate_meta/test_sp05_path_topology_contract.py \
  tests/schedule/service/test_schedule_orchestrator_contract.py \
  tests/gate_meta/test_frozen_bundle_contract.py \
  tests/gate_meta/test_workbench_round1_registry_contract.py
```

结果：**216 passed / 0 failed / 0 errors / 0 skipped，27.79 秒，exit 0**。文件分解为新 guard 35、SP05 12、编排合同 2、原冻结合同 6、R1 登记合同 161。本轮没有改原冻结测试文件。

以下命令均通过既有 `.venv/bin/python -B -m` 运行，`PYTHONDONTWRITEBYTECODE=1`，Pyright/XDG/bytecode 使用 `/tmp/aps-task-h-01a08b02/` 私有路径：

| 命令 | 实际结果 |
| --- | --- |
| `pyright -p pyrightconfig.gate.json --outputjson` | 1164 files，0 errors / 0 warnings，14.972 秒，exit 0 |
| `pyright -p pyrightconfig.tools.json --outputjson` | 62 files，0 errors / 0 warnings，4.732 秒，exit 0 |
| `pyright tests/gate_meta/test_scheduler_lazy_exports_final.py --outputjson` | 仅新测试 1 file，0 errors / 0 warnings，0.707 秒，exit 0 |
| `ruff check --no-cache` 加本次 6 个源码/测试/登记路径 | `All checks passed!`，exit 0 |

没有执行无路径的默认 Pyright，不扩大 2011 条历史 tests 类型债务。产品配置 SHA-256 仍为 `8c7e7f40351235c9e0ca919bdc90f6afbb697e2c1a428fee028c5b437a85b8c1`。

## 导入扫描与独立阻断

修改前、修改后均真实执行（同样 `.venv/bin/python -B` 和私有环境）：

```bash
python -B -m tools.scan_import_cycles --json --fail-on-new-cycle
python -B -m tools.scan_import_cycles --json --fail-on-new-cycle --include-tests
```

| 范围 | 修改前 | 修改后 | 严格结论 |
| --- | --- | --- | --- |
| production | exit 0；1 目录环 / 8 文件环 / 5 动态位置 | exit 0，同样计数 | 无新增环、圈内边、动态未解析；parse errors 0 |
| production-and-tests | exit 1；2 目录环 / 8 文件环 / 43 动态位置 | exit 1，同样计数 | 仍有同一个修改前已有的新目录环；不能标全通过 |

含 tests 的比较前后均仅 `new_dir=["scripts/workbench|tests/workbench"]`，`new_file/new_dir_edges/new_file_edges/new_unresolved_dynamic_imports` 全空。两个 baseline 文件的前后哈希相同。

根因证据与给 Main/B 的具体处理：

- `scripts/workbench/verify_final_capacity.py:11` 在模块顶层导入 `tests.workbench.final_capacity_probe.run_managed`，构成 scripts/workbench -> tests/workbench 硬边。
- `tests/workbench/test_asset_script_scopes.py:9`、`test_foundation_dependency_scope.py:12`、`test_asset_browser_globals.py:11` 顶层导入 `scripts.workbench.asset_sources`，构成反向目录聚合硬边。
- 建议 Main/B 把容量 CLI 对 `run_managed` 的导入移入其 `main()`（入口仍调用原函数、原参数，不更改真实容量结果或断言），再跑 CLI 定点与含 tests 导入扫描。H 本轮没有改该入口，也不刷新 baseline 抹掉这个失败。
- 这是确定的当前门禁阻断，不是单凭目录环认定运行时 ImportError，更不是本次 TYPE_CHECKING 改动新引入的产品 bug。

所有扫描真实命令、返回码、输出 SHA、比较对象与原始动态位置，在 `H-lazy-exports-evidence-20260910.json` 中保留。采集器成功解析不改变内部扫描 exit 1 的失败含义。

## 源码哈希

| 修改文件 | SHA-256 |
| --- | --- |
| `core/services/scheduler/__init__.py` | `c1d8d09a7dfd03b796add0745f2da29de541b54393faf6a39b8333ac01a32693` |
| `core/services/scheduler/schedule_orchestrator.py` | `71091b9b3942edfeb89332acfbf059c8925b65113398615c9c1974891053b14a` |
| `tests/gate_meta/test_scheduler_lazy_exports_final.py` | `9e1360be84d4f7ca75ad0ea5d00b7a6b37b528533cec83df1f74e701e2099153` |
| `tools/test_registry_data.py` | `37f6a0c7848726cbd51af707d2262c4279aca980c13ddd66f72a613fd7a891b8` |
| `tools/test_registry_groups_scheduler.py` | `5701746cdf0720ed8e3134d4026baa8f6657820704971867a8ed1c6eb490fa74` |
| `tests/gate_meta/test_workbench_round1_registry_contract.py` | `ed3d5fb3361346cdb5e1946ee62b9a5383ad453472f808ab2dfa77f04b292550` |

测试 XML `/tmp/aps-task-h-lazy-final-v1.xml` SHA-256 为 `7e0daa4472b41fb4b6fdde87f06edee15f43218934dc525753f4d4b35846e0b9`。登记现在观察到 583 required / 33 required groups，missing/duplicates/unknown 均为空；这是状态记录，不是新增浮动总数断言。

## 保留与后续

- H 无 Git 写，未 stage/commit，原 dirty 与已有未跟踪内容保留。仅 Main 负责分组归档与最终 HEAD。
- 没有操作原预览、两个源码归档、生产库、共享调用图或共享缓存。所有测试进程均正常结束。
- 本轮未重测 5000 容量；正式容量结论仍由 Main/B 原证据承担。H 只提供本次静态声明与运行时行为不变的限定证据，不把旧容量证明重新绑定到新文件哈希。
- 含 tests 的 CLI 目录环需 Main/B 收口；最终 full gate 等 Main 新 HEAD 通知，不在当前 dirty 仓库或早期 `c0097278` 全跑。

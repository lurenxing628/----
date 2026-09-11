# H 稳定容量 Helper 登记增量

- 状态：本轮局部实施与定点验证完成；不是完整 gate，不新增最终 test target。
- Main 通知正式容量独占窗口关闭、容量 PASS 后，H 恢复。5000 x 4 = 20000 rows、admission_to_terminal 122.728285375 秒、runtime 121.342296 秒及 1472 输入一致为 Main 已确认结果，H 没有重新测量或更改其证据。
- 本增量只写 `tools/test_registry_groups_workbench.py` 和已有 `tests/gate_meta/test_workbench_registry_contract.py`，外加本目录记录。没有产品、Git、阈值、baseline 或全局配置写入。

## 修改与范围

- `tools/test_registry_groups_workbench.py:861` 新增固定 `_FINAL_CAPACITY_INPUT_SCOPES`，只由两个现有 supplemental 容量组引用：`workbench_run_compute_capacity`、`workbench_run_jobs_capacity`（948、958 行）。
- 稳定链包括 B 的 6 个 `final_capacity_*.py` helper、正式命令入口 `scripts/workbench/verify_final_capacity.py`，以及实际引用的 `live_environment.py`、`run_live_server.py`、`run_live_server_support.py`。
- 修改前两个组各有 8 个路径不命中 input scope；`final_capacity_support.py` 和 `run_live_server_support.py` 已被既有通配规则覆盖。此次是固定依赖的预接入，不把尚未登记的 `test_final_capacity_*` 说成已由这些组执行。
- `tests/gate_meta/test_workbench_registry_contract.py:1341` 起补 22 个参数化用例：10 路径全部是 input 而非 target，并逐路径验证内容变化会改变两个组的文件指纹。测试所在文件已有唯一 required owner `workbench_registry`，没有新增测试文件或改变 target 分母。
- required 与 supplemental 所有 `(group_id, target_paths)` 在修改前后逐项相同，哈希均为 `27c0fe270396e5c6b087de736a02be5426b8af41b2d2876d709c0690bd772444`。没有把当下总数写成新断言。
- C/D/E/F 仍有在途构建、选择器、下载和场景链补漏，本轮不根据中间文件状态登记它们；Main foundation 的真实最终路径、当前 fullbuild 与最终 test target 仍等冻结 handoff。

## 定位与验证

- 已用私有 `CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph` 执行 symbol_locator `whereis _group --at tools/test_registry_groups_workbench.py:125` 和 `callers _group`。结果定位到 125 行；静态图未提供 confident callers，不能把模块顶层 `_group(...)` 数据构造当作无调用。实际影响通过两处显式引用和 registry 输入匹配核对。
- `callers` 不支持 `--at` 的尝试返回 exit 2 后已按真实接口重跑成功，没有修改工具或依赖来绕过。

实际测试命令：

```bash
env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache \
  CHECKUP_CALLGRAPH=/tmp/aps-task-h-01a08b02/callgraph \
  APS_ENV=development APS_DB_PATH=/tmp/aps-task-h-r2-helpers/runtime/unused.db \
  APS_LOG_DIR=/tmp/aps-task-h-r2-helpers/runtime/logs \
  APS_BACKUP_DIR=/tmp/aps-task-h-r2-helpers/runtime/backups \
  APS_SYSTEM_JOURNAL_DIR=/tmp/aps-task-h-r2-helpers/runtime/journal \
  .venv/bin/python -B -m pytest -q -p no:cacheprovider \
  --basetemp=/tmp/aps-task-h-r2-helpers-pytest-v1 \
  --junitxml=/tmp/aps-task-h-r2-helpers-v1.xml \
  tests/gate_meta/test_workbench_registry_contract.py -k stable_final_capacity
```

结果：**22 passed / 764 deselected，3.07 秒，exit 0**。这是明确选择的定点集合，不把 deselected 项计为通过；测试只操作私有文件指纹，不启动 capacity worker、浏览器、build 或真实业务库。

- 两个修改文件实际执行 `env PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/aps-task-h-01a08b02/pycache .venv/bin/python -B -m ruff check --no-cache tools/test_registry_groups_workbench.py tests/gate_meta/test_workbench_registry_contract.py`，exit 0 / `All checks passed!`。
- 同样私有 Pyright/XDG 缓存前缀，`.venv/bin/python -B -m pyright -p pyrightconfig.tools.json --outputjson`：62 files，0 errors / 0 warnings，3.793 秒，exit 0。没有运行默认含 tests 的全局类型检查。
- 原始 target 前后值、10 个依赖哈希、两个修改源哈希、XML 哈希与命令结果见 `H-stable-helpers-evidence-20260910.json`；该记录不冒充 clean-worktree proof。

## 剩余交接

- 15 warnings 的具体 TYPE_CHECKING 提案在 `H-warning-typechecking-proposal-20260910.md`；仅两个 root 文件，未实施产品变更。
- 正式 full gate 等 Main 的新最终 HEAD 与执行通知；不在早期 `c0097278` 上提前全跑。
- Main 决定分批本地提交；H 未 Git 写。原无关 dirty 和既有未跟踪文件保留，未操作原预览、归档、生产库或共享调用图。

# H 完整门禁首跑交接

- 日期：2026-09-10；状态：准备已交接，完整门禁尚未执行。
- 范围：任务 H，只读核查 tools/scripts/config 与旧证据，写本目录准备材料；不改产品、基线、阈值、全局配置，不创建代理，不执行 Git 写操作。
- Main 已获授权按归属分批本地提交、不 push；由 Main 建立对应最终 HEAD 的独立干净工作区后交 H 执行。原有 308 个 required 未跟踪文件是待入库检查项，不是永久阻断。
- 原目录 `/Users/lurenxing/GitHub/----` 不运行 full gate。旧预览 53144 / PID 73298 / `aps-workbench-live-l0tgvgp8`、生产库、两个源码备份及原 staged 冻结测试均不操作。

## 首跑前条件

1. Main 提供私有隔离工作区绝对路径、最终完整 HEAD、允许开始的重任务窗口。该工作区的源码、测试、工具、静态资产、schema、必要文档须与目标快照一致，不能只是把 dirty 目录复制过去。
2. `git status --short --untracked-files=all` 为空；`git diff --cached --exit-code`、`git diff --exit-code` 均 exit 0。登记的 required 文件及其实际 owner 随对应代码入库；不能以删除登记来解决缺文件。需要的 ignored 本地工具/依赖须检查存在与源哈希，不把 ignored payload 自动等同 HEAD。
3. `.venv/bin/python` 必须实际为 Python 3.8.10。可使用现有依赖，但不升级、不安装依赖、不调用坏 shebang；ruff/pyright 都使用 `-m`。
4. 本轮只读元数据核验：pytest 8.3.5、pytest-cov 5.0.0、pytest-xdist 3.6.1、Flask 2.3.3、openpyxl 3.0.10、networkx 3.1、ruff 0.15.11、pyright 1.1.406、radon 6.0.1。仅证明包元数据存在，不冒充完整 import 或测试成功。
5. `d4589d77^{commit}` 可解析为 `d4589d77d9b642fe3b16a891fe4f40f9aede1f93`；隔离工作区必须保留这段 Git 历史，不能 shallow 丢失 anti-regression 的比较对象。
6. Node、已有 playwright 模块、仓库内固定 standalone Babel 7.29.0、Chromium 109 可用；只读版本与模块解析后再启动测试，不自动下载替换。实际编译器为 `scripts/workbench/compile.cjs:25`，不是 esbuild/@babel/core。`tests/workbench/test_live_browser.py:16` 支持 `WORKBENCH_NODE`、`WORKBENCH_BROWSER`、`NODE_PATH`；部分旧测试仍硬编码 `/tmp/aps-chromium109-assessment/runtime/chrome-mac/Chromium.app/Contents/MacOS/Chromium`，执行前必须核对该路径。
7. 不与 Main 的正式 5000 同资源性能测量重叠。full gate 自身包括重性能/浏览器测试，三分片是既有合同，不改分片数或删 perf。接到暂停，完成当前测试后不开始新的重任务。

## 私有路径与真实命令

`WT` 与 `RUN` 均由 Main 指定的独立私有绝对路径替换，以下是执行模板，尚未运行；目录须预先准备好。不得把 `WT` 设为原仓库。

```bash
cd "$WT"
git rev-parse HEAD
git status --short --untracked-files=all
.venv/bin/python -B -c 'import sys; assert sys.version_info[:3] == (3, 8, 10); print(sys.executable, sys.version)'
git rev-parse --verify 'd4589d77^{commit}'

env PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPYCACHEPREFIX="$RUN/pycache" \
  CHECKUP_CALLGRAPH="$RUN/callgraph" \
  TMPDIR="$RUN/tmp" TMP="$RUN/tmp" TEMP="$RUN/tmp" \
  RUFF_CACHE_DIR="$RUN/ruff-cache" XDG_CACHE_HOME="$RUN/cache" \
  PYRIGHT_PYTHON_CACHE_DIR="$RUN/pyright-cache" \
  APS_ENV=development APS_SHARED_DATA_ROOT="$RUN/runtime" \
  APS_DB_PATH="$RUN/runtime/db/gate.db" APS_LOG_DIR="$RUN/runtime/logs" \
  APS_BACKUP_DIR="$RUN/runtime/backups" \
  APS_EXCEL_TEMPLATE_DIR="$RUN/runtime/templates_excel" \
  APS_SYSTEM_JOURNAL_DIR="$RUN/runtime/system-journal" \
  WORKBENCH_NODE="$NODE" WORKBENCH_BROWSER="$CHROME109" APS_CHROME_PATH="$CHROME109" \
  NODE_PATH="$NODE_MODULES" \
  PYTHONUTF8=1 PYTHONIOENCODING=utf-8 \
  .venv/bin/python -B scripts/run_quality_gate.py \
  --require-clean-worktree --no-long-gate-cache --no-resume
```

- 正式执行前检查继承环境：不得带选择/跳过测试的 `PYTEST_ADDOPTS`、强制改变 Pyright 版本或忽略诊断的变量，以及指向旧预览/生产目录的路径变量。`PYTHONPATH` 不得把源码导向原 dirty repo。不得设置 `CI` 让本地浏览器测试跳过；`tests/app_runtime/test_ui_browser_geometry_smoke.py:25` 的 CI skip 不因 `APS_BROWSER_SMOKE_REQUIRED=1` 自动取消。不通过设置过滤器来过门禁。
- `--no-long-gate-cache` 禁用长门禁复用；不需要再加在此模式下不生效的 `--long-gate-force-rerun-all`。不清任何共享缓存，不伪称所有内部扫描缓存均禁用。
- `TMPDIR` 让每个测试自行创建唯一目录。不要给多进程分片共享一个 `--basetemp`，避免 pytest 清理彼此的目录。临时 DB、备份、日志、锁仍由夹具在私有目录中创建。
- 不覆盖 `HOME`，不改全局 PATH/配置。Node 可沿已有 PATH 解析，专用测试用上面的进程级变量。
- 门禁所有固定产物保留在 `$WT/evidence/QualityGate/`，以及该私有工作区里的其它 ignored 测试产物。没有统一 `--output-root`。`tools/long_gate_paths.py:29` 会拒绝越出 repo realpath 的缓存路径，因此也不能用指向外部目录的 symlink 假装隔离。
- `scripts/run_quality_gate.py:3116` 写 manifest，3122 起清理旧回执/日志，3142 才拒绝 dirty。隔离目录中只运行新证据，不在原目录试跑来检查这个行为。运行时探针读取隔离 repo 的运行状态，见 1514 行；不得清理原目录状态或停止旧预览。
- stdout/stderr 由执行宿主保存到 `$RUN`，保留真实退出码；不能让 `tee` 的退出码覆盖 gate 退出码。门禁自身逐命令生成 logs 与 receipts。文件手写修改只用 `apply_patch`，正式 runner 生成的产物保留原样。

## 19 步严格覆盖

本轮实际只读调用 `tools.quality_gate_shared.build_quality_gate_command_plan()` 得到 19 项，`hash_quality_gate_commands(plan)` 为 `a9ef9378c8dc982a3f7e83a0122937ff193d3c80ed59bce36145789762cff35e`。全部原始 args、capture/output policy、env overlay、实际只读查询命令保存在同目录 `H-readonly-evidence-20260910.json`，不是手工猜测或删节后的 plan。以下 `python` 是 plan 的显示名，runner 实际替换为自身 `sys.executable`，见 `scripts/run_quality_gate.py:2262`。

| 序号 | plan 的实际命令/参数 | 证明边界 |
| --- | --- | --- |
| 1 | `python -m ruff --version` | 真实工具版本 |
| 2 | `python -m pyright --version` | 门禁要求 1.1.406 |
| 3 | `python -c "import radon"` | 实际可导入 |
| 4 | `python -m ruff check` | 既有 pyproject 范围；不自动 fix |
| 5 | `python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean` | 生产基线无新增，不代表零历史环 |
| 6 | `python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --quiet-when-clean` | 含 tests 的独立冻结基线 |
| 7 | `python -m pytest --collect-only -q tests` | 当前默认发现集合；不是实际执行通过 |
| 8 | `python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-three-gap-directions/aps-three-gap-directions-items.yaml --yaml-only --require roadmap --require created --require items` | 仅该 roadmap YAML，不代表所有迁移文档均验证 |
| 9 | `python tools/scan_py38plus_syntax.py --fail-on-hit` 加 `tools/quality_gate_shared.py:805` 的 10 个显式路径 | 局部语法合同，不代表 Win7 真机 |
| 10 | `python tests/gate_meta/check_quickref_vs_routes.py` | 当前速查表/路由合同 |
| 11 | `python tools/scan_anti_regression_gate.py --base-ref d4589d77` | 固定历史比较基准，不改基准 |
| 12 | `python -m pyright -p pyrightconfig.gate.json` | 产品 include 为 app.py、app_new_ui.py、config.py、core、data、web；不是默认含 tests 检查 |
| 13 | `python -m pyright -p pyrightconfig.tools.json` | 配置中显式工具/少量测试路径，不是全部 tools/tests |
| 14 | `python tools/scan_aps_three_gap_py38_scope.py --base-ref d4589d77` | 既有三差距专项变更语法范围 |
| 15 | `python -m pytest -q tests/gate_meta/test_architecture_fitness.py` | 架构、大小、复杂度等当前合同 |
| 16 | `python scripts/sync_debt_ledger.py check` | 当前账本与实际扫描一致，不是 sync 写回 |
| 17 | `python -m pytest -q` 加登记表 17 个 startup 文件 | 启动/停止/锁/配置/异常可见性，文件列表由 registry 提供 |
| 18 | `python tools/check_full_test_debt.py --sharded --shard-count 3` | collector 实际全量 `tests -q --tb=short -ra -p no:cacheprovider`，含 serial 与 3 分片，不删 perf |
| 19 | `python tools/verify_required_regressions_from_full_test_debt.py` | 以真实 full-test node 结果逐项验证 required，不仅查 collect |

第 18、19 步 plan 强制 `APS_BROWSER_SMOKE_REQUIRED=1`、`PYTHONDONTWRITEBYTECODE=1`、`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`。这些不自动启用各专题 `*_RUN_BROWSER=1` 的 opt-in supplemental，也不能替代 Main 的逐动作 B/K/V/P、截图人工审视、刷新重启和 5000 容量验收。

门禁声明是 `required_registry_bound_to_clean_worktree`，明确不声明 `risk_coverage_complete`，见 `tools/quality_gate_shared.py:108`。full-test-debt 的历史 xfail 必须按现有台账校验并如实报告，不能把 gate exit 0 翻译为“所有测试普通通过”。

默认 pytest 文件模式是 `test_*.py`、`*_test.py`、`regression_*.py`（`pyproject.toml:7`）。这 19 步不单独调用 `.limcode/skills/aps-full-selftest/scripts/run_full_selftest.py`，也不保证运行 `tests/_scripts_e2e/` 下每个独立 smoke/main 脚本；只有默认收集或被实际测试显式调用的部分进入运行。不能把“全 tests”扩写成“所有独立脚本/所有 opt-in/全站人工验收”。

## 执行后验收

- 读取 manifest、19 个命令及回执、stdout/stderr、collect nodeids、full-test-debt summary/current、required proof、两类导入扫描结果；逐项核对实际执行/复用/失败、普通通过/skip/xfail 数，不缩分母。
- 前后 HEAD 相同、前后工作区干净、所需 required tracked/source hash 一致，且完整命令成功并绑定，才可称该 HEAD 的 clean-worktree proof。`--allow-dirty-worktree` 即使执行完成也只是 `passed_but_unbound`/exit 2，不使用。
- 有失败就保留首次失败与命令回执，按 tools/meta 或产品 owner 分派。产品修复先交 Main；修复提交后重建或刷新由 Main 负责，再验证新 HEAD。不得在跑着的 worktree 上改文件。
- Win7 打包、Win7 真机、最终发布排除；完整源码门禁不等于这三项通过。历史 planning206 与原型 passed 不改写。

## 本轮只读快照

- HEAD（核查时）：`de96cd3f681bf4f3b1ca9183f347c56f3de8e73a`，不是本轮最终提交。
- `git diff --cached --raw` 仍只有 `A tests/gate_meta/test_frozen_bundle_contract.py`；staged binary patch SHA-256 `952a9e734f0c0d73d6c780090ac53a2854134b3523f0a552d3fe362f4f908b7d`；文件 SHA-256 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`。
- 实际查询的完整命令在 `H-readonly-evidence-20260910.json` 的 `executed_observation_command`，Python 子进程 exit 0；没有导入或运行 gate main，没有开始重测试。另完成 62 路径工具范围 Pyright 0 errors/0 warnings、Ruff 通过，见 `H-preparation-20260910.md`。

| 源文件 | SHA-256 |
| --- | --- |
| scripts/run_quality_gate.py | a3c9322f4fdace5b9e4ea5d79159b3a233bcc5a40091d9ea247cba18ca555dfe |
| tools/quality_gate_shared.py | 866f195d8842e02b031d8a42afa358b44df83424182b5269b2b6bd107f17b596 |
| tools/test_registry.py | 90d84b6bc266f1f8a9be7c432d4276482a7dd2a7d9b90abb1ba84741cf5c7377 |
| tools/test_registry_data.py | c3e7a0ac0c814d51a3a183db6f9ba707128e54a7032392518f237267129d13e9 |
| tools/test_registry_groups_misc.py | d9e97e9ff32b57dd2c38ac018ce03983ce4181087b303ef60c5be677f84c0a5b |
| tools/test_registry_groups_scheduler.py | 94260495a4507513ff39a69f34e9451b9cbc0ecdeb84c5d190a14a74b2c79c32 |
| tools/test_registry_groups_workbench.py | 143f58be0a06294a55297bd0fa50e1fdb068fbcfea6b7e9c4ab4855cea8e241d |
| pyrightconfig.gate.json | 8c7e7f40351235c9e0ca919bdc90f6afbb697e2c1a428fee028c5b437a85b8c1 |
| pyrightconfig.tools.json | 513df0a4052bd648c6f6c86438802e65f746a97cc18bcec6314c740e2840b446 |

## 首批提交后补充

- Main 首批提交 `c00972784ccc129957f650836dd2a423792f7049` 后，H 只读确认当前 index 为空，62 个工具源哈希与上述工具检查后快照全部一致；没有因短暂 stash 窗口报告产品 bug。
- 原冻结测试在该提交和原工作区中的内容均为 SHA-256 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`。最初的 staged 状态是历史采样，不再声称现在仍暂存；H 没有参与 Git 写操作。
- Main 通知首批隔离目录为 `/tmp/aps-workbench-r2-gate-PFwbOz/checkout`，detached `c0097278`，前后 status 空，Python 3.8.10 下冻结测试 6 passed / 0.67 秒。这是 Main 提供的首批 clean 定点结果，H 未复跑，不是 full gate，也不是最终 HEAD。
- 按 Main 最新指令，H 暂不在上述早期 HEAD 全跑。后续等冻结清单、最终当前 build 与正式执行窗口；主线提交前协调暂停，避免 tracked unstaged 的临时 stash 污染测试。

# 智能排产系统（APS）

## 项目定位

本项目是面向 Win7 x64 离线单机与共享数据场景的本地 APS 智能排产系统。它的目标是在目标机不安装 Python、不依赖外网的前提下，完成基础资料维护、Excel 导入导出、批次排产、结果查看、报表导出、备份/恢复以及现场交付。

当前开发与打包基线保持在 Python 3.8，并继续服从 Win7 兼容边界。正式交付时，目标机通过安装包和本地浏览器运行时访问 APS 页面。

## 主要能力

- **基础资料维护**：人员、班组、设备、停机计划、工艺路线、工种、供应商、物料与批次物料。
- **Excel 导入导出**：内置 `templates_excel/` 模板，支持上传预览、确认入库、导出、操作留痕；预览存在错误时整批拒绝导入，Excel 文件本体上限为 16MB。
- **排产调度**：批次管理、批次工序补充、正式排产、模拟排产、齐套约束、工作日历、排产策略与常用方案。
- **结果查看**：资源排班中心、甘特图、周计划、排产优化分析、排产历史。
- **报表中心**：逾期、资源利用率、停机影响等报表，并支持导出。
- **系统管理**：健康检查、备份/恢复、操作日志、排产历史、界面模式切换、插件开关。
- **可选增强**：`plugins/` 中提供 pandas Excel 后端与 OR-Tools 探测插件，默认关闭；OR-Tools 不是 Win7 交付必选依赖。

## 快速启动

### 源码开发启动

先在仓库根目录创建项目自己的 `.venv`，再用这个 `.venv` 安装运行依赖、开发依赖并启用本地钩子。不要用系统 Python 混着装，否则本地能启动、推送前门禁却找不到依赖：

```powershell
py -3.8 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pre_commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
```

常用启动入口：

- `.venv\Scripts\python app.py`：默认界面程序入口；只有已经激活 `.venv` 后，才可以简写成 `python app.py`。
- `.venv\Scripts\python app_new_ui.py`：现代界面程序入口；只有已经激活 `.venv` 后，才可以简写成 `python app_new_ui.py`。
- `start.bat` / `start_new_ui.bat`：仅适合已经确认当前命令行的 `python` 指向项目 `.venv` 时使用；否则请用上面两条 `.venv\Scripts\python ...` 命令。

实际访问地址不要写死端口，以启动后生成的 `logs/aps_host.txt` 与 `logs/aps_port.txt` 为准。

### 界面模式

系统保留经典界面与现代界面。界面模式可在系统内切换，并通过 Cookie 与 `SystemConfig.ui_mode` 保存。未迁移的页面会继续复用经典模板，已迁移页面会优先使用 `web_new_test/templates/` 下的覆盖模板。

### 正式交付与直拷交付

- 正式交付优先使用双包：`APS_Main_Setup.exe` 与 `APS_Chrome109_Runtime.exe`。
- 双包口径是管理员统一安装、共享同一套数据、仅允许单活用户。
- Chrome109 运行时只保证打开 APS 本地页面，不承诺完整桌面 Chrome 能力。
- 最小直拷与 legacy 应急交付说明见 `DELIVERY_WIN7.md`。
- 安装包构建、安装、卸载、强制清理和启动排障说明见 `installer/README_WIN7_INSTALLER.md`。

## 开发与质量门禁

### 日常开发快门禁

日常提交和推送前，先跑这条快门禁：

```powershell
.venv\Scripts\python scripts/run_daily_quality_gate.py
```

它会先看本次到底改了哪些文件：只改 README、开发文档或 CodeStable 记录时，不跑 required pytest，只做本地运行产物拦截、pytest 收集检查和一小组重点冒烟测试；改了 Python 文件时，只对这些还存在的 Python 文件跑 `ruff check`；改了公共配置、门禁工具配置，或脚本判断不出改动范围时，才退回全仓 `ruff check` 和更保守的 required pytest。

请注意：这条命令只用来尽快挡住明显问题，**不是最终 clean proof**。它不声明 full-test-debt proof，也不声明干净工作区证明。`.pre-commit-config.yaml` 的 pre-push hook 现在默认调用这条快门禁，所以日常推送不会每次都被完整 full-test-debt 执行拖住。

### 最终 clean proof

统一完整质量门禁入口：

```powershell
.venv\Scripts\python scripts/run_quality_gate.py
```

这只是普通完整门禁入口，不强制检查工作区是否干净，不能当最终 clean proof。

最终收口或托管环境使用：

```powershell
.venv\Scripts\python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache
```

如果已经激活 `.venv`，也可以把上面的 `.venv\Scripts\python` 简写成 `python`。这个入口会统一串联测试收集、full-test-debt proof、`ruff`、`pyright`、架构适应度、治理台账、启动链专项回归和速查表一致性检查。本地与托管环境都以这条入口为准。维护者想完全不复用 long gate cache 手动重跑时，可以去掉 `--long-gate-cache`，或显式加 `--no-long-gate-cache`。

full-test-debt proof 的意思是：当前没有未登记的 full pytest 失败，已登记的 full pytest 测试债务被台账管住，并且数量只能减少。它不是说历史 5 条测试债务已经全部修完。

常用定向命令：

```powershell
.venv\Scripts\python -m pytest --collect-only tests -q
.venv\Scripts\python -m pytest tests/regression -q
.venv\Scripts\python -m pytest tests -q
.venv\Scripts\python scripts\run_quality_gate.py --fast-precheck
.venv\Scripts\python -m pyright --version
.venv\Scripts\python -m pyright -p pyrightconfig.gate.json
.venv\Scripts\python -m pyright -p pyrightconfig.tools.json
.venv\Scripts\python -m pyright -p pyrightconfig.json
```

补充说明：

- `.venv\Scripts\python -m pytest --collect-only tests -q` 只列出测试，不执行 full pytest。
- `.venv\Scripts\python -m pytest tests/regression -q` 用于专项回归；`.venv\Scripts\python -m pytest tests -q` 是直接执行全量测试。
- `.venv\Scripts\python scripts\run_quality_gate.py --fast-precheck` 只对本次改动相关的 Python 文件跑局部 ruff，用来提前提醒明显问题。它不是 `ruff_check_full`，也不是 `pyright_gate_full` / `pyright_tools_full`，不能当成完整质量门禁、clean proof 或 long gate proof。
- 上面这些常用定向命令只适合定位问题，不能当成最终 clean proof。最终 clean proof 需要在干净工作区跑完整质量门禁，并且门禁结束后工作区仍然干净。
- 质量门禁里的 full pytest 收口检查由 `.venv\Scripts\python tools/check_full_test_debt.py` 完成，它会对照治理台账确认没有新的未登记失败。
- 单独运行 `.venv\Scripts\python tools/check_full_test_debt.py` 只会生成本次 full-test-debt 的 current/summary 证明，不会写 long gate success cache。也就是说，它能帮你定位 full-test-debt 本身是否通过，但不会让下一次完整门禁自动复用 long gate 缓存。
- 长耗时门禁缓存需要显式传 `.venv\Scripts\python scripts/run_quality_gate.py --long-gate-cache` 才会尝试复用。当前 enabled long gate entry 是 `pytest_collect_all`、`full_test_debt`、`ruff_check_full`、`pyright_gate_full`、`pyright_tools_full`、`required_regressions`、`debt_ledger_sync`、`startup_runtime_regressions` 和 `quickref_vs_routes`；当前仍 planned 的 long gate entry 只有 `architecture_fitness`。
- 要预热最终完整门禁会用到的 long gate 缓存，请跑完整门禁链：`.venv\Scripts\python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。这条命令成功后，才会留下 long gate success cache。
- CI 里也会复用 long gate cache：GitHub Actions 在完整门禁前恢复缓存，完整门禁成功后再保存缓存。缓存 key 的前缀会带上系统、Python 3.8、`requirements.txt` / `requirements-dev.txt` 依赖 hash，以及 workflow、门禁脚本、`tools/**/*.py`、pyright 配置等 tooling hash；保存 key 还会带上本次 `github.sha`，避免不同提交写到同一个精确 key。保存范围只包含已被忽略、下次复用会用到的 `evidence/QualityGate/` 运行产物，例如 `evidence/QualityGate/long_gate/` 和几份 long gate proof JSON，不包含已跟踪的 `evidence/Conformance/quickref_vs_routes.md`。来自 fork 的 pull request 只允许读取已有缓存，不会把自己的运行产物保存回主仓库缓存。
- long gate cache 不是跳过正式门禁。命中前会校验 command、fingerprint、stdout/stderr 日志、输出 proof、schema、runner/tooling hash 和 repo identity；证据缺失、损坏或 hash 不一致都会自动重跑。未登记的新失败仍然必须失败，已登记测试债务仍然必须被台账管住。
- `--long-gate-cache-explain` 只打印“会不会复用”的判断，不执行门禁，也不能当作通过证明。summary counts 只告诉你本轮执行、复用、失败、planned、disabled 各有多少条，也不是通过证明。CI 日志里看到 cache hit，也只能说明旧运行产物被拿回来参与校验，不能当成这次门禁已经通过。
- CI 和最终 clean gate 的要求不降低。最终 clean proof 仍要在干净工作区跑 `.venv\Scripts\python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`，并且门禁结束后 `git status --short` 仍然没有输出。
- 去掉 `--long-gate-cache` 或加 `--no-long-gate-cache` 只适合维护者强制全量重跑或排查缓存问题；对外收口、PR 和 CI 的最终证明仍按 `--require-clean-worktree --long-gate-cache` 或 `tools\git_hook_checks.py run-final-quality-gate` 口径写。
- `requirements.txt` 是程序运行依赖，`requirements-dev.txt` 是本地检查和托管门禁依赖；新环境两份都要装。
- `ruff` 版本口径为 `>=0.15,<0.16`。
- `pyright` 版本固定为 `==1.1.406`。
- `.pre-commit-config.yaml` 安装后会管三件事：提交前跑 `ruff` 和本地临时文件拦截，提交说明阶段拦截过于含糊的标题，推送前 hook 会通过项目 `.venv` Python 运行 `scripts/run_daily_quality_gate.py`。如果要在本地手动跑最终完整门禁，可以用 `.venv\Scripts\python tools\git_hook_checks.py run-final-quality-gate`，它仍会调用 `scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache`。
- 如果只想手动提前检查当前改动的 Python 文件，可以用 `.venv\Scripts\python tools\git_hook_checks.py run-fast-static-precheck`。它不会替代 pre-push daily gate，也不会写 long gate success cache。
- 推送前快门禁必须使用项目 `.venv` 里的 Python；如果项目 `.venv` 不存在，会直接失败，不会偷偷换成系统 Python，并且会强制使用 UTF-8 环境。本地 hook 不是可选检查，正常提交流程不要绕过它。CI/托管环境会重跑完整质量门禁，不过提交标题检查和“暂存区有没有混入本地运行产物”主要靠本地 hook，绕过后不能当作已经通过本地提交检查。
- `pyright` 不在提交前单独快跑，它由 `scripts/run_quality_gate.py` 与 CI 作为硬门禁运行。
- `pyrightconfig.gate.json` 覆盖主链：`app.py`、`app_new_ui.py`、`config.py`、`core/`、`data/`、`web/`。
- `pyrightconfig.tools.json` 覆盖门禁和维护脚本；`pyright_tools_full` 使用这个文件，不能用 `pyrightconfig.json` 的全仓债务盘点口径替代。
- `pyrightconfig.json` 保留为全仓类型债务盘点入口，包含 `tests/` 等更宽范围，不直接作为本轮硬门禁。
- 本地 hook 会拦截已登记的不该提交的运行产物，例如 `.DS_Store`、`.iris/`、`.playwright-mcp/`、`.limcode_*`、`launcher.log`、任意子目录里的 `launcher.log`、`logs/aps_host.txt`、`logs/aps_port.txt`、`logs/aps_db_path.txt`、`logs/aps_runtime.json`、`logs/aps_runtime.lock`、`logs/aps_secret_key.txt`、`evidence/QualityGate/quality_gate_manifest.json`、`evidence/QualityGate/current_full_test_debt.json`、`evidence/QualityGate/full_test_debt_summary.json`、`evidence/QualityGate/full_test_debt_node_cache.json`、`evidence/QualityGate/architecture_scan_cache.json`、`evidence/QualityGate/startup_runtime_regressions.json`、`evidence/QualityGate/required_regressions.json`、`evidence/QualityGate/debt_ledger_sync.json`、`evidence/QualityGate/ruff_check_full.json`、`evidence/QualityGate/pyright_gate_full.json`、`evidence/QualityGate/pyright_tools_full.json`、`evidence/QualityGate/receipts/`、`evidence/QualityGate/logs/`、`evidence/QualityGate/long_gate/`、`evidence/QualityGate/collect_nodeids.json`、`evidence/Conformance/quickref_vs_routes.md`、`evidence/FullSelfTest/pytest_tests_output.txt` 和 `aps_test.db*`。如果门禁生成了新的 `evidence/QualityGate/` 运行产物，也不要把它混进提交。

治理台账、测试目录命名契约与门禁细节统一维护在 `开发文档/README.md`。

## 关键目录

- `core/`：核心领域、算法、基础设施、服务与插件运行框架。
- `data/`：数据访问层。
- `web/`：Flask 启动、路由、页面装配、界面模式与 viewmodel。
- `templates/`、`static/`：经典页面模板与本地静态资源。
- `web_new_test/templates/`：现代界面模板覆盖层。
- `templates_excel/`：交付 Excel 模板。
- `plugins/`：自研插件目录，当前插件默认关闭。
- `tests/`：自动化测试；新增 `main()` 风格专项回归优先落到 `tests/regression/`。
- `开发文档/`：开发说明、系统速查表、页面与接口清单、设计资料。
- `codestable/`：CodeStable 工作流事实源，记录需求、架构、问题修复、规划和知识沉淀；默认入口见 `codestable/reference/system-overview.md`。
- `AGENTS.md`：AI 协作约定、CodeStable 分流规则和 APS 硬约束。
- `installer/`：Win7 双包安装器说明与脚本。
- `audit/`：审计与健康检查归档。
- `evidence/`：门禁、验收和排查证据归档。

## 文档导航

| 文档 | 用途 |
| --- | --- |
| `开发文档/README.md` | 开发文档总入口、开发基线、质量治理入口、测试命名契约 |
| `AGENTS.md` | AI 协作约定、CodeStable 默认分流规则、Win7 / Python 3.8 硬约束 |
| `codestable/reference/system-overview.md` | CodeStable 工作流总览和各类任务入口说明 |
| `开发文档/系统速查表.md` | 术语、枚举、接口、数据库字段、Excel 模板、打包交付关键点 |
| `开发文档/面板与接口清单.md` | 页面、路由、参数、按钮、提示文案与用户可见入口 |
| `installer/README_WIN7_INSTALLER.md` | Win7 双包构建、安装、卸载、强制清理与启动排障 |
| `DELIVERY_WIN7.md` | Win7 离线交付、直拷目录与 legacy 应急交付说明 |
| `ORTOOLS_WIN7_SPIKE.md` | OR-Tools 在 Win7 / Python 3.8 离线环境下的可行性结论 |
| `plugins/README.md` | 自研插件约定与当前插件清单 |
| `audit/README.md` | 审计归档入口 |

## Win7 / Python 3.8 兼容边界

- 当前目标仍是 Win7 x64 离线场景，因此依赖升级、语法升级与打包方案都要优先服从 Python 3.8 与 Win7 兼容性。
- 目标机不要求安装 Python；源码开发与打包机仍使用 Python 3.8。
- 页面不依赖外部脚本或样式，静态资源应随应用本地交付。
- OR-Tools 只作为可选增强和现场探测能力；缺失时不影响主流程。

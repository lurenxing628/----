# 开发文档总入口

本页只承担两件事：一是把当前仓库中真实存在的开发文档入口串起来；二是把后续子 plan 可以直接复用的开发基线、测试落点与命名契约写清楚。

## 文档导航

建议按下面顺序阅读：

1. 总体开发说明：`./开发文档.md`
2. 系统速查表：`./系统速查表.md`
3. 面板与接口清单：`./面板与接口清单.md`
4. AI 协作约定与默认工作流：`../AGENTS.md`
5. CodeStable 工作流总览：`../codestable/reference/system-overview.md`
6. 决策记录目录：`./ADR/`
7. V1.2 方案目录：`./V1.2/`

## 开发基线

在仓库根目录先创建项目自己的 `.venv`，再安装运行依赖、开发依赖并启用本地钩子。依赖安装、hook 安装、推送前门禁都要使用同一个项目 `.venv` Python，避免系统 Python 和项目 Python 不一致：

```powershell
py -3.8 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pre_commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push
```

说明：

- `requirements.txt` 是程序运行依赖，`requirements-dev.txt` 是本地检查和托管门禁依赖；新环境两份都要装。
- `PyYAML` 是 CodeStable YAML 工具的开发期依赖；缺失时工具只支持极简 Markdown frontmatter，不能校验 checklist / manifest 这类纯 YAML 文件。
- `ruff` 版本口径固定为 `>=0.15,<0.16`。
- 若未先在项目 `.venv` 中安装 `requirements.txt` 和 `requirements-dev.txt`，`.pre-commit-config.yaml` 中的 `ruff`、提交说明检查、推送前质量门禁以及本地启动都可能无法正常运行。
- 推送前质量门禁必须使用项目 `.venv` 里的 Python；如果项目 `.venv` 不存在，会直接失败，不会偷偷换成系统 Python，并且会强制使用 UTF-8 环境。本地 hook 不是可选检查，正常提交流程不要绕过它。CI/托管环境会重跑质量门禁，不过提交标题检查和“暂存区有没有混入本地运行产物”主要靠本地 hook，绕过后不能当作已经通过本地提交检查。

## 质量治理入口

### 统一门禁入口

```powershell
.venv\Scripts\python scripts/run_quality_gate.py
```

干净工作区或托管环境使用：

```powershell
.venv\Scripts\python scripts/run_quality_gate.py --require-clean-worktree
```

如果已经激活 `.venv`，也可以把上面的 `.venv\Scripts\python` 简写成 `python`。

用途：统一串联下面这些检查，本地与托管只认这一条入口：

1. 收集测试清单，确认测试能被 pytest 发现。
2. 运行 `.venv\Scripts\python tools/check_full_test_debt.py`，确认 full-test-debt 没有新增未登记失败。
3. 检查 `ruff` 和 `pyright` 版本是不是仓库要求的版本。
4. 跑 `radon` 导入检查、`ruff check`、主链 `pyright` 和工具脚本 `pyright`。
5. 跑架构适应度、必需回归、治理台账检查、启动链专项回归与系统速查表一致性检查。

full-test-debt proof 证明当前没有未登记的 full pytest 失败，并且已登记测试债务仍受台账约束；它不代表历史测试债务已经全部修完。

### 治理台账写入口

```powershell
.venv\Scripts\python scripts/sync_debt_ledger.py check
.venv\Scripts\python scripts/sync_debt_ledger.py refresh --mode migrate-inline-facts
.venv\Scripts\python scripts/sync_debt_ledger.py refresh --mode scan-startup-baseline
.venv\Scripts\python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields
.venv\Scripts\python scripts/sync_debt_ledger.py mark-test-debt-fixed --debt-id <debt-id>
```

说明：

- 治理数据唯一事实源：`./技术债务治理台账.md` 的受控 `json` 结构块，当前包含超长文件、高复杂度、静默回退、测试债务和接受风险。
- `scripts/run_quality_gate.py` 只读不写台账。
- `scripts/sync_debt_ledger.py` 是唯一台账写入口；人工治理字段必须通过 `set-entry-fields` 更新，接受风险必须通过 `upsert-risk` / `delete-risk` 维护。
- `set-entry-fields --status` 当前只接受 `open`、`in_progress`、`blocked`、`fixed`。
- 已登记 full pytest 测试债务修好后，不手删结构块；先运行 `mark-test-debt-fixed --debt-id ...` 标成 `fixed`，再由 full-test-debt proof 确认该测试已普通通过且不再带 xfail 标记。
- `test_debt.ratchet.max_registered_xfail` 必须等于当前 active xfail 数；修掉一条并标成 fixed 后，这个数字要随剩余 active xfail 数下降。
- 静默回退门禁当前分两段运行：启动链按四类分类全量冻结；非启动链仅续管历史 `silent_swallow` 遗留项，不把其余分类扩展为全仓新增门禁。

## 测试目录与命名契约

### 可直接复用的测试落点

- `tests/regression/`：后续新增 `main()` 风格专项回归的默认落点；这类回归由 pytest 收集后通过子进程执行，避免脚本里的全局改动污染后续测试。
- `tests/regression/regression_collection_contract.py`：最小收集探针，只提供无副作用 `main()` 并返回 `0`，用于证明子目录下的 `regression_*.py` 仍会被当前收集器识别。

### 命名契约

- `regression_*.py`：用于 `main()` 风格专项回归。
- `test_*.py`：用于标准 `pytest` 用例。
- 禁止在 `regression_*.py` 中同时声明 `main()` 与 `test_` 用例；若需要标准 `pytest` 用例，必须改为 `test_*.py` 命名，避免收集遗漏。
- 辅助 runner 不要命名成 `regression_*.py`，否则会被当成 main-style 回归再次收集；当前统一 runner 是 `tests/main_style_regression_runner.py`。
- 上述契约依赖当前 `tests/conftest.py` 的收集适配保持不变；`SP01` 只补目录、探针与契约，不修改该实现。
- `SP10` 完成前不迁移旧根层测试；后续新增专项回归优先落到 `tests/regression/`，避免继续把新文件堆回 `tests/` 根层。

## 对 SP02 的承接边界

以下内容已经准备好，并已由 `SP02` 实际接入：

- 可稳定链接的根入口、开发文档入口与审计入口。
- 本地开发与托管检查共用的开发依赖声明。
- 可直接承接新增专项回归的 `tests/regression/` 目录。
- 已明确写清的命名契约，以及它对当前 `tests/conftest.py` 收集适配前提的依赖。
- 统一质量门禁入口 `.venv\Scripts\python scripts/run_quality_gate.py`；只有已经激活 `.venv` 后，才可以简写成 `python scripts/run_quality_gate.py`。
- 唯一台账写入口 `.venv\Scripts\python scripts/sync_debt_ledger.py`；只有已经激活 `.venv` 后，才可以简写成 `python scripts/sync_debt_ledger.py`。
- 治理数据唯一事实源 `./技术债务治理台账.md`。

向 `SP03` 的直接交接点：

- 启动链基线已冻结到治理台账，后续优先做真实治理，不再重复搭基础设施。
- `web/ui_mode.py` 已按 `startup_guard` / `render_bridge` 分 scope 落账；其中 `render_bridge` 条目继续留给 `SP09`。
- 文档一致性检查已具备阻断语义，后续只需保持实现与速查表同步。

## Pyright 门禁补充

```powershell
.venv\Scripts\python -m pyright --version
.venv\Scripts\python -m pyright -p pyrightconfig.gate.json
.venv\Scripts\python -m pyright -p pyrightconfig.json
```

- `pyright` 版本口径固定为 `==1.1.406`，以 `requirements-dev.txt` 为准。
- `.pre-commit-config.yaml` 安装后会管三件事：提交前跑 `ruff` 和本地临时文件拦截，提交说明阶段拦截过于含糊的标题，推送前跑 `scripts/run_quality_gate.py --require-clean-worktree`。
- 推送前质量门禁必须使用项目 `.venv` 里的 Python；如果项目 `.venv` 不存在，会直接失败，不会偷偷换成系统 Python，并且会强制使用 UTF-8 环境。本地 hook 不是可选检查，正常提交流程不要绕过它，绕过后不能当作已经通过本地提交检查。
- `pyright` 不在提交前单独快跑，它由 `scripts/run_quality_gate.py` 和 CI 阻断。
- `scripts/run_quality_gate.py` 固定顺序已包含：测试收集、`python tools/check_full_test_debt.py`、`ruff` 版本检查、`pyright` 版本检查、`radon` 导入检查、`ruff check`、主链 `pyright`、工具脚本 `pyright`、架构适应度、必需回归、治理台账检查、启动链专项回归与速查表核对。
- `pyrightconfig.gate.json` 只覆盖 `app.py`、`app_new_ui.py`、`config.py`、`core/`、`data/`、`web/` 主链，是主链 gate 的类型检查口径。
- `pyrightconfig.json` 保留为全仓类型债务盘点入口，包含 `tests/` 等更宽范围，不直接作为本轮硬门禁。
- 上面这些 Pyright 命令只适合定位问题，不能当成最终 clean proof。最终 clean proof 需要在干净工作区跑完整质量门禁，并且门禁结束后工作区仍然干净。
- 本地 hook 会拦截不该提交的运行产物，例如 `.DS_Store`、`.iris/`、`.playwright-mcp/`、`.limcode_*`、`launcher.log`、任意子目录里的 `launcher.log`、`logs/aps_host.txt`、`logs/aps_port.txt`、`logs/aps_db_path.txt`、`logs/aps_runtime.json`、`logs/aps_runtime.lock`、`logs/aps_secret_key.txt`、`evidence/QualityGate/quality_gate_manifest.json`、`evidence/QualityGate/current_full_test_debt.json`、`evidence/QualityGate/receipts/`、`evidence/QualityGate/logs/`、`evidence/QualityGate/long_gate/`、`evidence/QualityGate/collect_nodeids.json`、`evidence/FullSelfTest/pytest_tests_output.txt` 和 `aps_test.db*`。

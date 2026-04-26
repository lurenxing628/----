# 开发文档总入口

本页只承担两件事：一是把当前仓库中真实存在的开发文档入口串起来；二是把后续子 plan 可以直接复用的开发基线、测试落点与命名契约写清楚。

## 文档导航

建议按下面顺序阅读：

1. 总体开发说明：`./开发文档.md`
2. 系统速查表：`./系统速查表.md`
3. 面板与接口清单：`./面板与接口清单.md`
4. 决策记录目录：`./ADR/`
5. V1.2 方案目录：`./V1.2/`

## 开发基线

在仓库根目录先安装开发依赖，再启用本地钩子：

```powershell
python -m pip install -r requirements-dev.txt
python -m pre_commit install
```

说明：

- `requirements-dev.txt` 已统一声明本地开发与托管检查共用的依赖口径。
- `ruff` 版本口径固定为 `>=0.15,<0.16`。
- 若未先安装 `requirements-dev.txt`，`.pre-commit-config.yaml` 中的 `python -m ruff` 钩子不会生效。

## 质量治理入口

### 统一门禁入口

```powershell
python scripts/run_quality_gate.py
```

用途：统一串联 `ruff`、架构门禁、启动链专项回归与系统速查表一致性检查。本地与托管只认这一条入口。

### 治理台账写入口

```powershell
python scripts/sync_debt_ledger.py check
python scripts/sync_debt_ledger.py refresh --mode migrate-inline-facts
python scripts/sync_debt_ledger.py refresh --mode scan-startup-baseline
python scripts/sync_debt_ledger.py refresh --mode refresh-auto-fields
```

说明：

- 三类治理数据唯一事实源：`./技术债务治理台账.md` 的受控 `json` 结构块。
- `scripts/run_quality_gate.py` 只读不写台账。
- `scripts/sync_debt_ledger.py` 是唯一台账写入口；人工治理字段必须通过 `set-entry-fields` 更新，接受风险必须通过 `upsert-risk` / `delete-risk` 维护。
- `set-entry-fields --status` 当前只接受 `open`、`in_progress`、`blocked`、`fixed`。
- 静默回退门禁当前分两段运行：启动链按四类分类全量冻结；非启动链仅续管历史 `silent_swallow` 遗留项，不把其余分类扩展为全仓新增门禁。

## 测试目录与命名契约

### 可直接复用的测试落点

- `tests/regression/`：后续新增 `main()` 风格专项回归的默认落点。
- `tests/regression/regression_collection_contract.py`：最小收集探针，只提供无副作用 `main()` 并返回 `0`，用于证明子目录下的 `regression_*.py` 仍会被当前收集器识别。

### 命名契约

- `regression_*.py`：用于 `main()` 风格专项回归。
- `test_*.py`：用于标准 `pytest` 用例。
- 禁止在 `regression_*.py` 中同时声明 `main()` 与 `test_` 用例；若需要标准 `pytest` 用例，必须改为 `test_*.py` 命名，避免收集遗漏。
- 上述契约依赖当前 `tests/conftest.py` 的收集适配保持不变；`SP01` 只补目录、探针与契约，不修改该实现。
- `SP10` 完成前不迁移旧根层测试；后续新增专项回归优先落到 `tests/regression/`，避免继续把新文件堆回 `tests/` 根层。

## 对 SP02 的承接边界

以下内容已经准备好，并已由 `SP02` 实际接入：

- 可稳定链接的根入口、开发文档入口与审计入口。
- 本地开发与托管检查共用的开发依赖声明。
- 可直接承接新增专项回归的 `tests/regression/` 目录。
- 已明确写清的命名契约，以及它对当前 `tests/conftest.py` 收集适配前提的依赖。
- 统一质量门禁入口 `python scripts/run_quality_gate.py`。
- 唯一台账写入口 `python scripts/sync_debt_ledger.py`。
- 三类治理数据唯一事实源 `./技术债务治理台账.md`。

向 `SP03` 的直接交接点：

- 启动链基线已冻结到治理台账，后续优先做真实治理，不再重复搭基础设施。
- `web/ui_mode.py` 已按 `startup_guard` / `render_bridge` 分 scope 落账；其中 `render_bridge` 条目继续留给 `SP09`。
- 文档一致性检查已具备阻断语义，后续只需保持实现与速查表同步。

## Pyright 门禁补充

```powershell
python -m pyright --version
python -m pyright -p pyrightconfig.gate.json
python -m pyright -p pyrightconfig.json
```

- `pyright` 版本口径固定为 `==1.1.406`，以 `requirements-dev.txt` 为准。
- `.pre-commit-config.yaml` 当前只执行 `ruff` 快速反馈；`pyright` 由 `scripts/run_quality_gate.py` 和 CI 阻断。
- `scripts/run_quality_gate.py` 固定顺序已包含：测试收集、`ruff` 版本检查、`pyright` 版本检查、`radon` 导入检查、`ruff check`、主链 `pyright`、工具脚本 `pyright`、架构适应度、必需回归、治理台账检查、启动链专项回归与速查表核对。
- `pyrightconfig.gate.json` 只覆盖 `app.py`、`app_new_ui.py`、`config.py`、`core/`、`data/`、`web/` 主链，是主链 gate 的类型检查口径。
- `pyrightconfig.json` 保留为全仓类型债务盘点入口，包含 `tests/` 等更宽范围，不直接作为本轮硬门禁。

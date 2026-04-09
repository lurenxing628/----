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

以下内容已经准备好，可直接被后续子 plan 复用：

- 可稳定链接的根入口、开发文档入口与审计入口。
- 本地开发与托管检查共用的开发依赖声明。
- 可直接承接新增专项回归的 `tests/regression/` 目录。
- 已明确写清的命名契约，以及它对当前 `tests/conftest.py` 收集适配前提的依赖。

以下内容仍留给 `SP02` 继续处理，不在 `SP01` 预支实现：

- 统一门禁
- 治理台账
- 专项回归扩展
- 审计留痕

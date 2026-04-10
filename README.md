# APS 测试系统

## 项目定位

本项目是面向 Win7 单机离线场景的 APS 排产测试系统，围绕批次、工艺、资源、排产、甘特图与报表链路提供本地运行、验证与交付支撑。当前开发与打包基线保持在 Python 3.8，并继续服从 Win7 兼容边界。

## 启动方式

- `start.bat`
  - 角色：默认界面的推荐开发入口。
  - 场景：日常本地开发、调试默认页面。
  - 行为：设置开发环境变量后调用 `python app.py`。
- `app.py`
  - 角色：默认界面程序入口。
  - 场景：命令行直接启动，或由其他脚本显式调用 `main()`。
- `start_new_ui.bat`
  - 角色：新界面测试入口。
  - 场景：验证新界面模板、样式与交互。
  - 行为：设置开发环境变量后调用 `python app_new_ui.py`。
- `app_new_ui.py`
  - 角色：新界面程序入口。
  - 场景：命令行直接启动新界面模式。
- 实际访问地址以 `logs/aps_host.txt` 与 `logs/aps_port.txt` 为准。
- 安装包与交付目录的浏览器启动链说明见 `./installer/README_WIN7_INSTALLER.md`。

## 开发依赖安装

在仓库根目录执行：

```powershell
python -m pip install -r requirements-dev.txt
python -m pre_commit install
```

若未先安装 `requirements-dev.txt`，本地 `python -m ruff` 钩子不会生效。

## 测试方式

### 统一质量门禁入口

在仓库根目录执行：

```powershell
python scripts/run_quality_gate.py
```

统一门禁固定按以下顺序执行：

- 仓库根活动 APS 实例前置检查
- `python -m ruff --version` 与版本断言（`>=0.15,<0.16`）
- `python -c "import radon"`
- `python -m ruff check`
- `python -m pytest -q tests/test_architecture_fitness.py`
- `python scripts/sync_debt_ledger.py check`
- 启动链专项回归统一 `pytest` 命令
- `python tests/check_quickref_vs_routes.py`

### 其他常用命令

```powershell
python -m pytest --collect-only tests -q
python -m pytest tests/regression -q
python -m pytest tests -q
```

专项回归目录、命名契约、治理台账入口与台账写入口说明统一维护在 `./开发文档/README.md`。

## 关键目录

- `core/`：核心领域、基础设施与服务
- `data/`：数据访问层
- `web/`：页面路由与装配
- `templates/`、`static/`：页面模板与静态资源
- `tests/`：自动化测试；新增 `main()` 风格专项回归优先落到 `tests/regression/`
- `开发文档/`：开发说明、速查表与设计资料
- `audit/`：审计与健康检查归档
- `installer/`：Win7 双包交付说明与脚本

## 文档导航

- 开发文档总入口：`./开发文档/README.md`
- 系统速查表：`./开发文档/系统速查表.md`
- Win7 安装包说明：`./installer/README_WIN7_INSTALLER.md`
- 审计归档入口：`./audit/README.md`

## Win7 / Python 3.8 接受风险说明

- 当前交付目标仍是 Win7 单机离线环境，因此开发与打包继续锁定 Python 3.8。
- 这意味着依赖升级、语法升级与运行环境能力都要优先服从 Win7 / Python 3.8 兼容边界，而不是追求新版本特性。
- 双包交付、共享数据目录与单活约束的详细说明见 `./installer/README_WIN7_INSTALLER.md`。

## 后续子 plan 承接

根入口现已提供统一质量门禁命令；治理台账结构、台账写入口、专项回归扩展与交接说明统一维护在 `./开发文档/README.md`。

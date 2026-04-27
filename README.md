# 回转壳体单元智能排产系统（APS）

## 项目定位

本项目是面向 Win7 x64 离线单机与共享数据场景的本地 APS 智能排产系统。它的目标是在目标机不安装 Python、不依赖外网的前提下，完成基础资料维护、Excel 导入导出、批次排产、结果查看、报表导出、备份恢复和现场交付。

当前开发与打包基线保持在 Python 3.8，并继续服从 Win7 兼容边界。正式交付时，目标机通过安装包和本地浏览器运行时访问 APS 页面。

## 主要能力

- **基础资料维护**：人员、班组、设备、停机计划、工艺路线、工种、供应商、物料与批次物料。
- **Excel 导入导出**：内置 `templates_excel/` 模板，支持上传预览、确认入库、导出、操作留痕；预览存在错误时整批拒绝导入，Excel 文件本体上限为 16MB。
- **排产调度**：批次管理、批次工序补充、正式排产、模拟排产、齐套约束、工作日历、排产策略与常用方案。
- **结果查看**：资源排班中心、甘特图、周计划、排产优化分析、排产历史。
- **报表中心**：逾期、资源利用率、停机影响等报表，并支持导出。
- **系统管理**：健康检查、备份恢复、日志、历史、界面模式切换、插件开关。
- **可选增强**：`plugins/` 中提供 pandas Excel 后端与 OR-Tools 探测插件，默认关闭；OR-Tools 不是 Win7 交付必选依赖。

## 快速启动

### 源码开发启动

先在仓库根目录安装开发依赖并启用本地钩子：

```powershell
python -m pip install -r requirements-dev.txt
python -m pre_commit install
```

常用启动入口：

- `start.bat`：默认开发入口，设置开发环境变量后调用 `python app.py`。
- `python app.py`：默认界面程序入口。
- `start_new_ui.bat`：现代界面测试入口，设置开发环境变量后调用 `python app_new_ui.py`。
- `python app_new_ui.py`：现代界面程序入口。

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

统一质量门禁入口：

```powershell
python scripts/run_quality_gate.py
```

干净工作区或托管环境使用：

```powershell
python scripts/run_quality_gate.py --require-clean-worktree
```

这个入口会统一串联测试收集、full-test-debt proof、`ruff`、`pyright`、架构适应度、治理台账、启动链专项回归和速查表一致性检查。本地与托管环境都以这条入口为准。

full-test-debt proof 的意思是：当前没有未登记的 full pytest 失败，已登记的 full pytest 测试债务被台账管住，并且数量只能减少。它不是说历史 5 条测试债务已经全部修完。

常用定向命令：

```powershell
python -m pytest --collect-only tests -q
python -m pytest tests/regression -q
python -m pytest tests -q
python -m pyright --version
python -m pyright -p pyrightconfig.gate.json
python -m pyright -p pyrightconfig.json
```

补充说明：

- `python -m pytest --collect-only tests -q` 只列出测试，不执行 full pytest。
- `python -m pytest tests/regression -q` 用于专项回归；`python -m pytest tests -q` 是直接执行全量测试。
- 质量门禁里的 full pytest 收口检查由 `python tools/check_full_test_debt.py` 完成，它会对照治理台账确认没有新的未登记失败。
- `requirements-dev.txt` 固定声明本地开发与托管检查共用的依赖口径。
- `ruff` 版本口径为 `>=0.15,<0.16`。
- `pyright` 版本固定为 `==1.1.406`。
- `.pre-commit-config.yaml` 当前只执行 `ruff` 快速反馈；`pyright` 由 `scripts/run_quality_gate.py` 与 CI 作为硬门禁运行。
- `pyrightconfig.gate.json` 覆盖主链：`app.py`、`app_new_ui.py`、`config.py`、`core/`、`data/`、`web/`。
- `pyrightconfig.json` 保留为全仓类型债务盘点入口，包含 `tests/` 等更宽范围，不直接作为本轮硬门禁。

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
- `installer/`：Win7 双包安装器说明与脚本。
- `audit/`：审计与健康检查归档。
- `evidence/`：门禁、验收和排查证据归档。

## 文档导航

| 文档 | 用途 |
| --- | --- |
| `开发文档/README.md` | 开发文档总入口、开发基线、质量治理入口、测试命名契约 |
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

# Win7 打包验收脚本与当前交付契约不一致

> 历史记录归档（2026-09-27）：本文保留初始调查、验收失败及当时的判断；正文中的“未修复”“未提交”“尚未安装”等描述均为记录时的状态。后续修复已提交于 `0b9a682f` 至 `d1307cb8`，原 Win7 的安装、复验和交付结果以[最终验收记录](2026-09-26-win7-fixes-acceptance.md)为准。打包验收脚本及两份专测已包含在 `0b9a682f` 中。本文原存于 `codestable/`，现归档至 `.codestable/`；引用的本机日志、数据库和截图不随 Git 上传。

日期：2026-09-26。状态：打包验收脚本已修复，并通过真实 Win7 冻结程序验证。
基线提交：`4df78c5330f8c0cb819ecf5a8678dc46b1340e58`。

## 原始问题

1. Win7 原始 onedir 构建成功后，校验要求磁盘存在 `networkx/__init__.py`，误报缺包。锁定的 PyInstaller 4.10 实际将纯 Python 模块放入 EXE 内的 PYZ；源码文件不是必要载荷。
2. 放行合法 PYZ 后，原始页面冒烟仍要求 `/personnel/` 等旧入口返回 200，而当前工作台契约要求这些无条件旧入口返回明确的 410 退役页，因此再次误报页面不可用。

## 最小修正

代码范围仅为以下三文件，生产运行逻辑、依赖版本和已构建 EXE 均未改动，未提交或推送：

- [validate_dist_exe.py](../../validate_dist_exe.py)：读取目标 EXE 的真实 CArchive/PYZ，逐项解码 8 个 NetworkX 关键模块；缺失、损坏、错误类型、伪造源码目录或相邻 EXE 均不能代替有效载荷。页面检查转为当前 15 个工作台视图、试调入口、唯一挂载节点、引导 JSON 和本地 CSS/主题脚本/主脚本，并保留旧 5 个入口的 410 及退役说明检查。
- [NetworkX 专测](../../tests/app_runtime/test_validate_dist_networkx_payload.py)：真实归档格式的正负用例。
- [工作台入口专测](../../tests/app_runtime/test_validate_dist_workbench_entry.py)：当前真实路由及错误状态、错误页面、缺失资源等负例。

修正后校验脚本 SHA-256：`279f34b210b00fcbdb65bb34f7991c940a63e393b1dba8617d363e190465f876`。

## 验证证据

| 环境与范围 | 结果 | 证据 |
| --- | --- | --- |
| 宿主 Python 3.8 相关回归 | 42 通过，14.35 秒；Ruff、diff 检查通过 | [宿主回归日志](../../evidence/Win7Acceptance/20260926/package/execution-evidence/validator-host-42-tests.log) |
| 真实 Win7、锁定 PyInstaller 4.10 | NetworkX 专测 7 通过，0.195 秒 | [Win7 专测日志](../../evidence/Win7Acceptance/20260926/package/execution-evidence/validator-networkx-win7-tests.log) |
| 真实 Win7 冻结 EXE | 冷启动、便携目录数据库、健康接口、当前入口、旧入口退役、静态载荷均通过 | [最终冷启动验证](../../evidence/Win7Acceptance/20260926/package/execution-evidence/03-original-exe-cold-start-validation.log) |
| 兼容打包编排 | 原始工具链检查、便携准备、修正后冷启动校验、真实 Chrome 冒烟、ZIP 归档五步均通过 | [兼容打包报告](../../evidence/Win7Acceptance/20260926/package/compatible-build-report.json) |

复用的原始 EXE SHA-256：`6d8eb24ee47679c084f675c3ad5edc15e718f89760be35a004bcd6227f79f5f5`。

## 结论边界

实际使用外部 Python 3.8＋PowerShell 2.0 兼容编排，报告中的 `official_powershell_51_pipeline_passed` 为 `false`；不能称官方 PowerShell 5.1 完整管线通过。构建副本仅对 `.bat/.cmd` 做了可核对的 LF→CRLF 暂存转换，以解决 Win7 命令解析失败，仓库 `.gitattributes` 未改。

此次通过的是修正后的打包载荷和入口验收，不能称原始校验脚本通过，也不能代替后续全面业务、界面及压力验收。HTML 引导检查不执行 JavaScript。

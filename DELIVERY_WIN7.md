# Win7 绿色便携版交付

默认交付 `APS_Portable_Win7_x64.zip`：完整解压后，双击 `启动_排产系统_Chrome.bat` 即可使用。主程序、Python 运行时和 APS 专用 Chrome109 都在包内，目标机不需要安装这些组件，也不需要管理员安装或区分本地账户与域账户。

需要单文件小于 80 MB 时，可使用已核验的分包交付：把编号 ZIP 放在同一目录，解压第一包并运行随包 `Install.cmd`，它会使用内置工具读取后续包、核对全部文件并部署到新目录，再运行 `Application/Start.cmd`。分包部署入口已在 Win7 自带 PowerShell 2.0 上验证；下文 PowerShell 5.1 要求仍适用于原构建流水线。详见 [2026-09-28 用户交付记录](.codestable/audits/2026-09-28-win7-user-delivery.md)。

## 使用与数据位置

解压到当前账户可读写的本机目录，例如 `D:\APS`。不要在 ZIP 内直接启动，也不要放到当前账户不可写的 `Program Files`。Windows 文件夹权限仍然生效；同一目录供其他账户使用时，也须允许其读写。

也可以直接把打包机上构建完成的整个 `dist/排产系统/` 文件夹复制到目标机，保留全部文件和便携标记。

如果解压后的中文文件名异常，可在 ZIP 所在目录打开 Windows PowerShell 5.1，解压到一个新的可写目录：

```powershell
Expand-Archive -LiteralPath '.\APS_Portable_Win7_x64.zip' -DestinationPath 'D:\APS_new'
```

本包采用 ZIP 标准的 UTF-8 文件名；PowerShell 5.1 的解压接口支持该编码。微软曾记录 Win7 自带解压组件的文件名乱码问题，因此不能把旧系统解压器的行为当作已验收。[Expand-Archive 5.1](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.archive/expand-archive?view=powershell-5.1) · [Win7 解压组件问题](https://support.microsoft.com/en-us/topic/japanese-characters-in-file-names-are-displayed-as-garbled-text-after-you-decompress-a-zip-file-in-windows-7-or-in-windows-server-2008-r2-a8dab642-4dc7-0872-4ee7-86cfd430a929)

```text
APS_Portable/
  启动_排产系统_Chrome.bat    日常启动入口
  aps-launcher.ps1           启动控制脚本，与 BAT 一起保留
  排产系统.exe              后台服务
  aps-portable.txt           便携标记，必须保留
  README_PORTABLE.txt        随包使用说明
  WIN7_ACCEPTANCE.txt        实机逐项验收及结果记录表
  tools/chrome109/           专用浏览器
  static/、templates/…      程序资源
  user-data/                首次启动自动生成
    db/aps.db               业务数据库
    backups/                备份
    logs/                   日志、密钥和运行状态
    templates_excel/        运行时的 Excel 目录（随包不带示例，模板由工作台现生成）
    chrome109_profile/      APS 浏览器配置
```

程序检测到 `aps-portable.txt` 后，数据库、日志、备份、模板和浏览器配置固定随目录走。旧安装注册表、`ProgramData`、`LOCALAPPDATA` 及 `APS_*` 数据路径覆盖不会把便携版引向其他目录；启动器只使用包内浏览器。路径不可写时明确失败，不换地方建库。

同一份数据一次只允许一个实例使用；重复启动和另一账户占用时仍执行现有的运行锁保护。使用系统页面退出功能，等待程序正常退出后再复制、移动、升级或拔出存储设备。专用浏览器只用于本机 APS 页面。

启动 BAT 只调用一次 Windows PowerShell；日志、实例身份核对和健康轮询都在该进程内完成。就绪等待按实际经过时间限制为 45 秒，`launcher.log` 中的 `elapsed_ms` 可用于区分服务就绪与浏览器打开阶段。更新启动器时必须同时替换 BAT 和 `aps-launcher.ps1`，不能只拷贝其中一个。日志仍为 UTF-8，运行目录可含中文、空格和 `!`。

## 构建

打包机基线：**Win7 SP1 x64、Python 3.8.x x64、PyInstaller 4.10、Windows PowerShell 5.1**。目标机按本次确认的 Windows PowerShell 5.1 环境使用，不依赖 PowerShell 7。

### 联网准备机

先用 Python 3.8 或以上版本执行 `python scripts/prepare_win7_offline.py download`，再执行 `python scripts/prepare_win7_offline.py verify`。支持在 Windows / macOS / Linux 准备材料，下载不会安装或执行第三方程序。

文件保存到 `offline/win7/`，包括 Python 3.8.10 x64 离线安装器、22 个运行及打包 wheel、ungoogled-chromium 109.0.5414.120-1.1 x64 ZIP。下载器通过 HTTPS 获取，逐文件核对大小及 SHA-256；缺失或损坏就停止，不静默覆盖已有错误文件。完整来源和哈希见 [`packaging/win7/offline-manifest.json`](packaging/win7/offline-manifest.json)。

来源：[Python 官方发行页](https://www.python.org/downloads/release/python-3810/)、[PyInstaller 4.10 / PyPI](https://pypi.org/project/pyinstaller/4.10/)、[Chromium 发布仓库](https://github.com/ungoogled-software/ungoogled-chromium-windows/releases/tag/109.0.5414.120-1.1)及其[校验清单](https://raw.githubusercontent.com/ungoogled-software/ungoogled-chromium-binaries/master/config/platforms/windows/64bit/109.0.5414.120-1.ini)。运行依赖沿用当前项目版本，完整构建依赖固定在 `requirements-win7-build.txt`，仍须经 Win7 冷启动验收。

将源码和整个 `offline/win7/` 一起带到现场，保持目录关系。大型第三方文件不进 Git；只拿 GitHub 源码不能离线打包。**这些是构建材料，不是已经完成的便携 EXE。**

### Win7 打包机

先确认 Win7 SP1 x64 和 PowerShell 5.1 已就绪。没有 Python 时，用 `offline\win7\installers\python-3.8.10-amd64.exe` 安装到打包机，确保新命令窗口的 `python` 指向 3.8 x64。脚本不会代装系统更新或修改全局安全策略。

```bat
setup_win7_build.bat
```

该命令核验全部材料，创建 `.venv-win7-build`，按哈希离线安装依赖，执行 `pip check`，把已核验浏览器 ZIP 放到 `tools/`。绿色构建入口会自动激活此环境。不要往这里安装 `requirements-dev.txt`；开发检查继续使用原有 `.venv`。

手工维护时的安装命令：`python -m pip install --no-index --find-links offline\win7\wheels --require-hashes -r requirements-win7-build.txt`。

- 浏览器源目录：`tools\Chrome.109.0.5414.120.x64\chrome.exe`，或离线 `tools\ungoogled-chromium_109*.zip`。
- 默认图分析需要 `networkx==3.1`；`build_win7_onedir.bat` 会从 `vendor/wheels` 离线安装并核对版本。
- 不需要 Inno Setup、注册表写入或安装器权限配置。
- 构建预检核对 Win7 SP1、Python 3.8 x64 和全部锁定依赖，不符合时在清理 `build/dist` 前停止。
- 静态资源已经提交，打包不要求 Node.js。已有浏览器源目录优先于 ZIP；验证固定材料时请使用新的源码目录。

仓库根目录执行：

```bat
build_win7_portable.bat
```

激活 `.venv-win7-build` 后的等价命令：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .limcode/skills/aps-package-win7/scripts/package_win7.ps1
```

流程会核对工具链和浏览器源，重新生成 `build/`、`dist/` 中的构建产物，复制裁剪后的 Chrome109、启动器、使用说明和便携标记，执行主程序冷启动及浏览器最小冒烟，然后清理**本次新构建的测试数据**，最后生成 ZIP 并检查完整性。不要把生产数据保存在仓库的构建目录里。

输出：`dist/APS_Portable_Win7_x64.zip` 和 `dist/APS_Portable_Win7_x64.zip.sha256`。压缩包必须包含一个完整的 `APS_Portable/` 目录。打包器发现数据库、日志、备份或浏览器用户数据混入时会拒绝出包，不会静默删掉这些数据。

单独执行 `build_win7_onedir.bat` 只生成开发用主程序目录，尚未组成便携交付包。

## PowerShell 5.1 与中文路径

微软说明：Windows PowerShell 可能把无 BOM 的非 ASCII 脚本按旧 ANSI 代码页解析；5.1 的文件编码默认值也不统一。[字符编码文档](https://learn.microsoft.com/zh-cn/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-7.5)

- 打包 `.ps1` 保持纯 ASCII，并使用 `#Requires -Version 5.1`。不使用 `utf8NoBOM` 编码参数、PowerShell 7 语法或要求升级到 7 的回退方案。
- 控制台、PowerShell 原生命令管道与 Python 输出显式设置 UTF-8；设置作用于本次进程，不改机器或账户的全局配置。
- 启动 `.bat` 保持 ASCII 内容与 CRLF，关闭延迟展开；`aps-launcher.ps1` 保持 ASCII 源码并兼容 Windows PowerShell 2.0，中文路径与 UTF-8 日志在同一 PowerShell 进程内处理。中文使用说明在出包时写成 UTF-8 带 BOM，供 Win7 记事本读取。
- `.gitattributes` 为启动和构建 BAT 固定 `text eol=crlf`，为打包 PS1 固定 `text eol=lf`，避免 Windows 的 `core.autocrlf` 改变各自的换行约定；不更改用户全局 Git 设置。[Git 换行属性文档](https://git-scm.com/docs/gitattributes)
- 浏览器验收对路径参数显式加双引号，并在含中文、空格的临时目录里执行。微软说明 `Start-Process` 会把参数数组拼为字符串，外层字符串引号不会自动传给子进程。[Start-Process 5.1 文档](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/start-process?view=powershell-5.1)

5.1 是本次现场基线，不能仅凭“Win7”推断版本；微软将其作为 WMF 5.1 更新提供给 Win7。[微软 WMF 5.1 发布说明](https://devblogs.microsoft.com/powershell/windows-management-framework-wmf-5-1-released/)

## 升级、搬迁与旧安装数据

- **升级**：新 ZIP 解压到新的空目录；正常退出旧程序后，把旧 `user-data/` 完整复制到新目录，再从新目录启动。保留旧目录作为副本，避免边运行边覆盖程序文件。
- **换目录或电脑**：正常退出后，复制整个 `APS_Portable/` 目录。
- **安装版转便携版**：先在旧系统导出备份，再进入新便携版的系统维护页面恢复。新包首次启动为空库，不自动读取、迁移或清理旧安装数据。
- **移除便携版**：正常退出并确认业务数据已备份后，删除其整个目录即可。

## 验收与排障

- `validate_dist_exe.py` 核对实际数据库路径、运行时身份、HTTP 页面与静态载荷；绿色版应生成 `user-data/logs/` 和 `user-data/db/aps.db`。
- 浏览器最小冒烟只证明 APS 专用浏览器可以拉起并短时存活；不能代替目标机完整使用验收。
- Win7 / PowerShell 5.1 现场还须验证：中文＋空格目录解压、双击启动、再次启动、正常退出、备份恢复、关闭后整目录搬迁、存在旧安装记录及切换账户后的路径隔离。
- 启动失败先看 `user-data/logs/launcher.log`，再看同目录 `aps_launch_error.txt`；不要通过删除运行锁来强行开启第二个实例。
- macOS 上的路径、打包合同、静态编码测试不等于 Windows EXE 或 PowerShell 5.1 真机通过。

现场按随包 [`WIN7_ACCEPTANCE.txt`](assets/WIN7_ACCEPTANCE.txt) 填写，覆盖离线启动、资料导入导出、排产和采用、甘特图、报工、报表打印、备份恢复、搬迁及账户占用。用 `TEST-W7` 前缀的样例，只操作测试目录，未测项如实保留。

若同一台 Win7 先安装 Python 用于打包，再运行成品，只能据此记录该环境的功能结果；“目标机无需安装 Python”须另在未安装 Python 的 Win7 环境验收，并在记录表中注明。

打包人员提供源码提交号、ZIP SHA-256 和打包日志。在 PowerShell 5.1 中运行 `Get-FileHash -Algorithm SHA256 .\APS_Portable_Win7_x64.zip`，与同名 `.sha256` 比较，不一致就停止。源码版本用 `git rev-parse HEAD` 记录；源码归档使用提供方附带的提交号。

失败时保留时间、截图、复现步骤、脱敏输入及错误日志片段。不要将整个 `user-data`、业务备份或含密钥的日志目录提交到公开 GitHub。

原双安装包仅保留为维护入口：`package_win7.ps1 -Installer`；`-MainOnly`、`-ChromeOnly`、`-Legacy` 继续显式可用，详见 [历史安装版说明](installer/README_WIN7_INSTALLER.md)。

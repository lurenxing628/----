# Win7 绿色便携版交付

默认交付 `APS_Portable_Win7_x64.zip`：完整解压后，双击 `启动_排产系统_Chrome.bat` 即可使用。主程序、Python 运行时和 APS 专用 Chrome109 都在包内，目标机不需要安装这些组件，也不需要管理员安装或区分本地账户与域账户。

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
  排产系统.exe              后台服务
  aps-portable.txt           便携标记，必须保留
  README_PORTABLE.txt        随包使用说明
  tools/chrome109/           专用浏览器
  static/、templates/…      程序资源
  user-data/                首次启动自动生成
    db/aps.db               业务数据库
    backups/                备份
    logs/                   日志、密钥和运行状态
    templates_excel/        Excel 模板
    chrome109_profile/      APS 浏览器配置
```

程序检测到 `aps-portable.txt` 后，数据库、日志、备份、模板和浏览器配置固定随目录走。旧安装注册表、`ProgramData`、`LOCALAPPDATA` 及 `APS_*` 数据路径覆盖不会把便携版引向其他目录；启动器只使用包内浏览器。路径不可写时明确失败，不换地方建库。

同一份数据一次只允许一个实例使用；重复启动和另一账户占用时仍执行现有的运行锁保护。使用系统页面退出功能，等待程序正常退出后再复制、移动、升级或拔出存储设备。专用浏览器只用于本机 APS 页面。

## 构建

打包机基线：**Win7 SP1 x64、Python 3.8.x x64、PyInstaller 4.10、Windows PowerShell 5.1**。目标机按本次确认的 Windows PowerShell 5.1 环境使用，不依赖 PowerShell 7。

先离线安装三份依赖，并准备 Chrome109：

```bat
python -m pip install --no-index --find-links C:\wheelhouse -r requirements.txt -r requirements-dev.txt -r requirements-optimizer-lite-win7.txt
```

- 浏览器源目录：`tools\Chrome.109.0.5414.120.x64\chrome.exe`，或离线 `tools\ungoogled-chromium_109*.zip`。
- 默认图分析需要 `networkx==3.1`；`build_win7_onedir.bat` 会从 `vendor/wheels` 离线安装并核对版本。
- 不需要 Inno Setup、注册表写入或安装器权限配置。

仓库根目录执行：

```bat
build_win7_portable.bat
```

等价命令：

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
- 启动 `.bat` 保持项目既有 UTF-8 无 BOM、LF 与第二行 `chcp 65001` 合同；中文使用说明在出包时写成 UTF-8 带 BOM，供 Win7 记事本读取。
- `.gitattributes` 为这些启动文件固定 `text eol=lf`，避免 Windows 的 `core.autocrlf` 改变既有换行合同；不更改用户全局 Git 设置。[Git 换行属性文档](https://git-scm.com/docs/gitattributes)
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

原双安装包仅保留为维护入口：`package_win7.ps1 -Installer`；`-MainOnly`、`-ChromeOnly`、`-Legacy` 继续显式可用，详见 [历史安装版说明](installer/README_WIN7_INSTALLER.md)。

# Win7 安装包构建说明（双包）

> 目标：在 **Win7 x64 离线打包机** 上，生成两个正式交付安装包：
> 1. `APS_Main_Setup.exe`（主程序包）
> 2. `APS_Chrome109_Runtime.exe`（浏览器运行时包）

> 当前交付边界（v1.3.x）：**管理员统一安装 + 共享同一套 APS 数据 + 仅允许单活用户**。
> 也就是说，不同域账户可以轮流使用同一套数据，但不能并发进入。

## 前置条件（离线打包机）

- **Windows 7 x64（建议 SP1）**
- **Python 3.8.x x64**
- **PyInstaller 4.10**（必须 4.x）
- **Inno Setup 6.x（Unicode）**：需要 `ISCC.exe`
- 浏览器运行时包 / legacy 全量包额外需要以下之一：
  - `tools\Chrome.109.0.5414.120.x64\chrome.exe`
  - `tools\ungoogled-chromium_109*.zip`

## 目录约定

- PyInstaller onedir 输出：`dist\排产系统\`
- 运行时临时 payload：`build\chrome109_runtime_payload\`
- 主程序安装脚本：`installer\aps_win7.iss`
- 浏览器运行时安装脚本：`installer\aps_win7_chrome.iss`
- legacy 全量包脚本（内部应急）：`installer\aps_win7_legacy.iss`
- 启动器模板：`assets\启动_排产系统_Chrome.bat`
- 输出目录：`installer\output\`

## 正式交付物

- `installer\output\APS_Main_Setup.exe`
- `installer\output\APS_Chrome109_Runtime.exe`

仅内部应急时才使用：

- `installer\output\APS_Legacy_Full_Setup.exe`

## 一键构建（推荐）

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/aps-package-win7/scripts/package_win7.ps1
```

默认会：

1. 构建主程序 `onedir`
2. 复制启动器到 `dist`（仅用于直拷目录辅助启动）
3. 执行 `validate_dist_exe.py`
4. 清理 `validate_dist_exe.py` 生成的运行时痕迹（`db` / `logs` / `backups` / runtime 契约）
5. 生成 `APS_Main_Setup.exe`
6. 生成 APS 专用裁剪运行时 payload（保留 `zh-CN` / `en-US`，裁掉 PWA / 通知 / 更新修复辅助程序）
7. 生成 `APS_Chrome109_Runtime.exe`

内部应急回退：

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/aps-package-win7/scripts/package_win7.ps1 -Legacy
```

### 找不到 ISCC.exe 怎么办

你可以二选一：

- 安装 Inno Setup 6.x 后重试（常见路径会自动识别）
- 或手工设置环境变量再运行：

```bat
set INNO_HOME=C:\Program Files (x86)\Inno Setup 6
```

## 手工构建（需要排查问题时）

### 方案 A：只构建主程序包

```bat
build_win7_installer.bat
python validate_dist_exe.py "dist\排产系统\排产系统.exe"
```

产物：

- `installer\output\APS_Main_Setup.exe`

### 方案 B：只构建浏览器运行时包

先确保离线 Chrome109 已整理到标准目录，或存在 `ungoogled-chromium_109*.zip`。

官方口径请使用打包脚本，它会先生成裁剪后的 APS 运行时 payload，再调用 Inno Setup：

```powershell
powershell -ExecutionPolicy Bypass -File .cursor/skills/aps-package-win7/scripts/package_win7.ps1 -ChromeOnly
```

产物：

- `installer\output\APS_Chrome109_Runtime.exe`

临时 payload 目录：

- `build\chrome109_runtime_payload\`

### 方案 C：内部应急 legacy 全量包

```bat
build_win7_onedir.bat
stage_chrome109_to_dist.bat
ISCC.exe installer\aps_win7_legacy.iss
```

产物：

- `installer\output\APS_Legacy_Full_Setup.exe`

## 浏览器运行时包（APS 专用保守裁剪）

- `APS_Chrome109_Runtime.exe` 面向本项目的启动链路：`chrome.exe --app=http://127.0.0.1:{port}/`
- 仅保留语言资源：`locales\zh-CN.pak`、`locales\en-US.pak`
- 从正式运行时包中移除：
  - `chrome_proxy.exe`
  - `chrome_pwa_launcher.exe`
  - `notification_helper.exe`
  - `elevation_service.exe`
- 继续保留：
  - `chrome_wer.dll`
  - `First Run`
- 这意味着正式运行时包**不承诺**完整桌面 Chrome / PWA 能力；当前仅保证 APS 打开本地页面所需功能

## 目标机安装顺序

推荐顺序：

1. 先安装 `APS_Chrome109_Runtime.exe`
2. 再安装 `APS_Main_Setup.exe`
3. 使用开始菜单或桌面快捷方式 **“排产系统”** 启动

也支持先装主程序包、后装浏览器运行时包；但首波双包口径下，主程序包安装完成后不会自动启动。

### 共享安装目录与共享数据目录

- 主程序默认安装到：`C:\Program Files\APS\SchedulerApp`
- Chrome109 运行时默认安装到：`C:\Program Files\APS\Chrome109`
- 共享数据目录默认位于：`C:\ProgramData\APS\shared-data`
- 共享数据目录下固定包含：
  - `db\`
  - `logs\`
  - `backups\`
  - `templates_excel\`

说明：

- 安装器会为 `shared-data` 及其子目录授予普通用户写权限。
- 启动器会把 `APS_DB_PATH` / `APS_LOG_DIR` / `APS_BACKUP_DIR` / `APS_EXCEL_TEMPLATE_DIR` 注入到当前进程，确保主程序写共享数据目录，而不是写 `Program Files`。
- 旧版 per-user 数据若存在，只会尝试复制**当前安装账户**下的旧目录到共享数据目录；源目录会保留，便于回退。
- 如果本次安装前选择了“强制清理”，安装器会删除当前安装账户的 legacy 目录，并显式跳过本次 legacy 数据迁移回填。

### 安装前强制清理（主程序包 / legacy 包）

- 当 `APS_Main_Setup.exe` 或 `APS_Legacy_Full_Setup.exe` 检测到本机存在 APS 运行实例、旧主程序安装目录、`shared-data` 或当前安装账户的 legacy 目录时，会在真正复制文件前弹出一次确认框。
- 你确认后，安装器会先解析可用停机 helper（优先运行时锁/契约中的 `exe_path`，其次注册表 `HKLM\SOFTWARE\APS\MainAppDir`，最后当前 `{app}`），再用 `--runtime-stop` 尝试关闭 APS。
- 若当前目标删除范围涉及 APS 专用 Chrome，安装器会一并请求关闭 APS Chrome 进程。
- 强制清理会删除：
  - 旧主程序安装目录
  - `C:\ProgramData\APS\shared-data`
  - 当前安装账户 `%LOCALAPPDATA%\APS\排产系统`
- 强制清理不会删除：
  - `%LOCALAPPDATA%\APS\Chrome109Profile`
  - 独立 Chrome109 运行时目录（`APS_Chrome109_Runtime.exe` 安装的 `ChromeDir`）
- 如果你在确认后安装后续失败，现场会处于“已清空、需重新安装”的状态。

## 环境变量与启动器

- 主程序包会把共享数据根写入机器级注册表：`HKLM\SOFTWARE\APS\SharedDataRoot`
- 浏览器运行时包会把 Chrome 目录写入机器级注册表：`HKLM\SOFTWARE\APS\ChromeDir`
- 启动器查找顺序固定为：
  1. `APS_CHROME_EXE`
  2. 当前进程 `APS_CHROME_DIR\chrome.exe`
  3. 当前进程 `APS_CHROME_DIR\App\chrome.exe`
  4. 机器级注册表 `HKLM\SOFTWARE\APS\ChromeDir\chrome.exe`
  5. 机器级注册表 `HKLM\SOFTWARE\APS\ChromeDir\App\chrome.exe`
  6. 兼容旧版注册表 `HKCU\Environment\APS_CHROME_DIR\chrome.exe`
  7. 兼容旧版注册表 `HKCU\Environment\APS_CHROME_DIR\App\chrome.exe`
  8. 默认目录 `C:\Program Files\APS\Chrome109\chrome.exe`
  9. 默认目录 `C:\Program Files (x86)\APS\Chrome109\chrome.exe`
  10. 默认目录 `%LOCALAPPDATA%\APS\Chrome109\chrome.exe`
  11. 默认目录 `%LOCALAPPDATA%\APS\Chrome109\App\chrome.exe`
  12. 当前安装目录 `tools\chrome109\chrome.exe`
  13. 当前安装目录 `tools\chrome109\App\chrome.exe`
- 启动器会优先读取共享日志目录中的 `aps_host.txt` 与 `aps_port.txt`，因此打开的 URL **不一定是** `http://127.0.0.1:5000/`
- 浏览器会固定使用用户数据目录：`%LOCALAPPDATA%\APS\Chrome109Profile`
- 启动器会读取共享日志目录中的 `aps_runtime.lock`；若检测到别的账户正在使用，第二个账户会被明确阻止，而不是静默复用。

## 启动排障（Win7 双包）

- `排产系统.exe` 只负责在后台启动本地服务；双击它时如果没有弹出窗口，不代表启动失败。
- 正常入口是开始菜单或桌面快捷方式 **“排产系统”**，其实际执行的是安装目录根下的 `启动_排产系统_Chrome.bat`。
- 若快捷方式只闪一下且未打开 Chrome，请先查看：**共享数据目录**下的 `logs\launcher.log`。
  - 默认安装时通常是：`C:\ProgramData\APS\shared-data\logs\launcher.log`
  - 如果安装时自定义了共享数据目录，应到该共享目录下查看 `logs\launcher.log`
- `launcher.log` 会记录：
  - `env_APS_CHROME_DIR`
  - `reg_HKLM_ChromeDir`
  - `reg_HKCU_APS_CHROME_DIR`
  - `chrome_source`
  - `chrome_exe`
  - `chrome_run_dir`
  - `chrome_cmd`
- 若提示“正在被其他账户使用”，说明共享数据目录里已有有效运行时锁。此时应让当前使用者先退出程序，再由下一位账户启动。
- 若现场仍异常，可把 `launcher.log` 里的 `chrome_cmd` 整行复制到 `cmd` 中执行，用于区分“bat 启动方式问题”和“Chrome 本体问题”。
- 当前 launcher 会显式以 Chrome 安装目录作为 working directory 启动 Chrome，避免 Win7 下 `start` 默认工作目录不一致导致的异常。

## 直拷目录与安装包的关系

- `dist\排产系统\` 是最小直拷交付目录，允许直接运行 `排产系统.exe`
- 最小直拷目录 **不承诺自带浏览器运行时**
- 如果需要在直拷目录中使用启动器，可额外复制 `assets\启动_排产系统_Chrome.bat` 到 `dist`
- 若需要 self-contained 的直拷目录，只能走 legacy 路线（内部/应急）

## 卸载说明

- “添加或删除程序”中会出现两个独立条目：
  - `排产系统`
  - `APS Chrome109 运行时`
- 卸载主程序包时，会先解析可用停机 helper，并对 `shared-data`、当前安装账户 legacy 目录、安装目录轮询执行 `--runtime-stop`；如果关闭失败，会提示用户是否继续卸载
- 卸载主程序包时会弹出二次确认：
  - 选择“是”：同时彻底清空共享数据目录下的 `db`、`logs`、`backups`、`templates_excel`
  - 选择“否”：仅卸载程序文件，保留共享数据
- 卸载 legacy 全量包时，会按同一套 helper 解析逻辑执行 `--runtime-stop ... --stop-aps-chrome`，同时关闭后端与 legacy 内置浏览器
- 卸载主程序包 **不会** 顺带卸载 `APS Chrome109 运行时`；浏览器运行时仍需单独卸载
- 卸载浏览器运行时包会先尝试关闭 APS 专用浏览器进程，再删除机器级 Chrome109 目录并清理 `HKLM\SOFTWARE\APS\ChromeDir`
- 为避免管理员卸载时误删错误账户的用户目录，浏览器运行时卸载器**不会自动删除任何账户的** `%LOCALAPPDATA%\APS\Chrome109Profile`；如需清理，请登录对应账户手动删除

## 验收建议

至少完成以下检查：

1. 在打包机执行 `python validate_dist_exe.py "dist\排产系统\排产系统.exe"`
2. 在目标机上以管理员身份安装 `APS_Chrome109_Runtime.exe` 与 `APS_Main_Setup.exe`
3. 切换到域账户后，确认开始菜单或桌面可见 **“排产系统”**，点击后能打开系统首页
4. 检查共享数据目录 `C:\ProgramData\APS\shared-data\` 下的 `db/ logs/ backups/ templates_excel/` 已建立并可写
5. 检查 `launcher.log` 中的 `chrome_source` / `chrome_exe` / `chrome_cmd` 是否与实际命中路径一致
6. 在已有一个账户运行时，再用第二个账户点击快捷方式，必须收到“正在被其他账户使用”的明确提示
7. 检查关键页面：人员 / 设备 / 工艺 / 排产 / 系统管理
8. 至少在一台实际 Win7 机器上完成一次端到端冒烟

> 注意：`validate_dist_exe.py` 只覆盖主程序 `exe` 冷启动与 HTTP 页面可访问性，不覆盖快捷方式、批处理脚本、环境变量刷新时序或 Chrome 启动链路。

## 备注

- **Chrome 109 已停止安全更新**：建议仅用于离线/内网访问本机系统页面
- **术语说明**：离线浏览器运行时可能来自 `ungoogled-chromium_109*.zip`，但交付口径统一称为“Chrome109 运行时”
- **能力边界**：正式运行时包不覆盖 PWA 文件关联、PWA 快捷方式代理、Windows 原生通知激活、Chrome 更新修复等桌面集成功能
- **合规提醒**：把浏览器二进制打进安装包可能受分发条款约束；若对外/商用分发，请先做内部合规确认


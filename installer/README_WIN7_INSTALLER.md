# Win7 安装包构建说明（双包）

> 目标：在 **Win7 x64 离线打包机** 上，生成两个正式交付安装包：
> 1. `APS_Main_Setup.exe`（主程序包）
> 2. `APS_Chrome109_Runtime.exe`（浏览器运行时包）

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
4. 生成 `APS_Main_Setup.exe`
5. 生成 APS 专用裁剪运行时 payload（保留 `zh-CN` / `en-US`，裁掉 PWA / 通知 / 更新修复辅助程序）
6. 生成 `APS_Chrome109_Runtime.exe`

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

## 环境变量与启动器

- 浏览器运行时包会写入用户级环境变量：`APS_CHROME_DIR={app}`
- 启动器查找顺序固定为：
  1. `APS_CHROME_EXE`
  2. `APS_CHROME_DIR\chrome.exe`
  3. `APS_CHROME_DIR\App\chrome.exe`
  4. 当前安装目录 `tools\chrome109\chrome.exe`
  5. 当前安装目录 `tools\chrome109\App\chrome.exe`
- 启动器会优先读取 `logs\aps_host.txt` 与 `logs\aps_port.txt`，因此打开的 URL **不一定是** `http://127.0.0.1:5000/`
- 浏览器会固定使用用户数据目录：`%LOCALAPPDATA%\APS\Chrome109Profile`

## 启动排障（Win7 双包）

- `排产系统.exe` 只负责在后台启动本地服务；双击它时如果没有弹出窗口，不代表启动失败。
- 正常入口是开始菜单或桌面快捷方式 **“排产系统”**，其实际执行的是安装目录根下的 `启动_排产系统_Chrome.bat`。
- 若快捷方式只闪一下且未打开 Chrome，请先查看：`%LOCALAPPDATA%\APS\排产系统\logs\launcher.log`
- `launcher.log` 会记录：
  - `chrome_exe`
  - `chrome_run_dir`
  - `chrome_cmd`
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
- 卸载主程序包会删除安装目录下的程序文件与本地数据（包括 `db`、`logs`、`backups`、`templates_excel`）
- 卸载浏览器运行时包会删除浏览器运行时目录并清理 `APS_CHROME_DIR`
- 卸载浏览器运行时包 **不会** 删除 `%LOCALAPPDATA%\APS\Chrome109Profile`

## 验收建议

至少完成以下检查：

1. 在打包机执行 `python validate_dist_exe.py "dist\排产系统\排产系统.exe"`
2. 在目标机安装双包后，点击 **“排产系统”** 能打开系统首页
3. 检查关键页面：人员 / 设备 / 工艺 / 排产 / 系统管理
4. 至少在一台实际 Win7 机器上完成一次端到端冒烟

## 备注

- **Chrome 109 已停止安全更新**：建议仅用于离线/内网访问本机系统页面
- **术语说明**：离线浏览器运行时可能来自 `ungoogled-chromium_109*.zip`，但交付口径统一称为“Chrome109 运行时”
- **能力边界**：正式运行时包不覆盖 PWA 文件关联、PWA 快捷方式代理、Windows 原生通知激活、Chrome 更新修复等桌面集成功能
- **合规提醒**：把浏览器二进制打进安装包可能受分发条款约束；若对外/商用分发，请先做内部合规确认


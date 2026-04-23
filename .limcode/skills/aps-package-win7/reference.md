# 关键经验（双包口径）

## 1) 主程序包与浏览器运行时包的职责已经拆开

- `APS_Main_Setup.exe`：只包含主程序 onedir 与启动器，不再内置浏览器运行时
- `APS_Chrome109_Runtime.exe`：只包含浏览器运行时，并写入机器级注册表 `HKLM\SOFTWARE\APS\ChromeDir`
- `APS_Legacy_Full_Setup.exe`：仅内部应急回退，不作为常规交付物
- 当前交付边界：**管理员统一安装 + 共享同一套业务数据 + 仅允许单活用户**

## 2) 启动器的浏览器查找顺序是固定契约

- `APS_CHROME_EXE`
- 当前进程 `APS_CHROME_DIR\chrome.exe`
- 当前进程 `APS_CHROME_DIR\App\chrome.exe`
- 注册表 `HKLM\SOFTWARE\APS\ChromeDir\chrome.exe`
- 注册表 `HKLM\SOFTWARE\APS\ChromeDir\App\chrome.exe`
- 兼容旧版注册表 `HKCU\Environment\APS_CHROME_DIR\chrome.exe`
- 兼容旧版注册表 `HKCU\Environment\APS_CHROME_DIR\App\chrome.exe`
- 默认 `C:\Program Files\APS\Chrome109\chrome.exe`
- 默认 `C:\Program Files (x86)\APS\Chrome109\chrome.exe`
- 默认 `%LOCALAPPDATA%\APS\Chrome109\chrome.exe`
- 默认 `%LOCALAPPDATA%\APS\Chrome109\App\chrome.exe`
- 当前目录兼容路径 `tools\chrome109\chrome.exe`
- 当前目录兼容路径 `tools\chrome109\App\chrome.exe`

如果 `APS_CHROME_EXE` 已设置但路径失效，启动器会直接报错，不会静默回退。
如果机器级 ChromeDir 已存在，启动器会优先命中机器级路径；旧版 `HKCU\Environment\APS_CHROME_DIR` 仅作为兼容回退。

## 3) 浏览器运行时目录不再要求用户可写

- 启动器会固定 `--user-data-dir=%LOCALAPPDATA%\APS\Chrome109Profile`
- Chrome109 本体可安装在机器级目录（默认 `C:\Program Files\APS\Chrome109`）
- 浏览器真正需要写入的是每用户 `Chrome109Profile`，不是 Chrome 安装目录本身
- 因此共享安装场景下，Chrome 本体与用户数据必须分离

## 4) 离线 Chrome109 只对运行时包 / legacy 全量包是硬依赖

- 主程序包构建不再依赖离线 Chrome109
- 浏览器运行时包与 legacy 全量包仍要求以下之一可用：
  - `tools/Chrome.109.0.5414.120.x64/chrome.exe`
  - `tools/ungoogled-chromium_109*.zip`
- 若使用 zip，`scripts/package_win7.ps1` 会自动整理为标准目录

## 5) 更换浏览器来源时，要核对目录结构

- 当前兼容两种结构：
  - 根目录 `chrome.exe`
  - `App\chrome.exe`
- 如果离线包换了来源，先核对解压目录是否仍满足上述契约，再交付

## 6) 直拷交付现在分三种口径

- 最小直拷：仅 `build_win7_onedir.bat` 产物，不承诺自带浏览器运行时
- 直拷辅助启动：可额外把 `assets/启动_排产系统_Chrome.bat` 复制到 `dist`
- legacy 自包含直拷：仅内部应急场景，需先 `stage_chrome109_to_dist.bat`

## 7) 冷启动验收仍然是强制步骤

- `validate_dist_exe.py` 只验证主程序，不依赖浏览器进程
- 这一步仍能兜底“能启动 + 关键页面 200”
- 浏览器定位 / 快捷方式 / 批处理链路需额外通过共享日志目录 `C:\ProgramData\APS\shared-data\logs\launcher.log` 和安装后启动冒烟验证
- 共享安装验收必须额外覆盖“第二个账户被阻止进入”的单活用户场景

## 8) PowerShell 5.1 编码注意

- 现象：运行 `scripts/package_win7.ps1` 报 `ParserError`
- 原因：Windows PowerShell 5.1 对 UTF-8 无 BOM + 非 ASCII 脚本兼容性差
- 规避建议（择一即可）：
  - 最稳：保持 `package_win7.ps1` **ASCII-only**
  - 若必须写中文：用 **UTF-8 with BOM** 保存该 `.ps1`
  - 或用 PowerShell 7 执行（`pwsh`）

---

# 一次性打包脚本（推荐）

见：`scripts/package_win7.ps1`

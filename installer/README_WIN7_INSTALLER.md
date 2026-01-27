# Win7 安装包构建说明（含 Chrome 109）

> 目标：在 **Win7 x64 离线打包机** 上，把 PyInstaller 的 onedir 产物 + 已准备好的 Chrome109 便携目录，一起做成一个可安装的 `setup.exe`（Inno Setup）。

## 前置条件（离线打包机）

- **Windows 7 x64（建议 SP1）**
- **Python 3.8.x x64**
- **PyInstaller 4.10**（必须 4.x）
- **Inno Setup 6.x（Unicode）**：需要 `ISCC.exe`
- 已准备好的离线 Chrome109 目录：
  - `tools\Chrome.109.0.5414.120.x64\chrome.exe`

## 目录约定

- PyInstaller onedir 输出：`dist\排产系统\`
- Chrome 注入目标：`dist\排产系统\tools\chrome109\`
- 启动器模板：`assets\启动_排产系统_Chrome.bat`
- Inno 脚本：`installer\aps_win7.iss`
- Inno 输出：`installer\output\APS_Win7_Setup.exe`

## 一键构建（推荐）

在仓库根目录运行：

```bat
build_win7_installer.bat
```

它会顺序执行：
- `build_win7_onedir.bat`（生成 `dist\排产系统\`）
- `stage_chrome109_to_dist.bat`（把 `tools\Chrome.109.0.5414.120.x64\` 复制到 `dist\排产系统\tools\chrome109\`）
- 调用 `ISCC.exe installer\aps_win7.iss`（输出 `installer\output\APS_Win7_Setup.exe`）

### 找不到 ISCC.exe 怎么办

你可以二选一：

- 安装 Inno Setup 6.x 后重试（常见路径会自动识别）  
- 或手工设置环境变量再运行：

```bat
set INNO_HOME=C:\Program Files (x86)\Inno Setup 6
build_win7_installer.bat
```

## 分步构建（需要排查问题时）

```bat
build_win7_onedir.bat
python validate_dist_exe.py "dist\排产系统\排产系统.exe"
stage_chrome109_to_dist.bat

REM 下面二选一：
ISCC.exe installer\aps_win7.iss
REM 或：
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\aps_win7.iss
```

## 目标机安装/验收

1. 拷贝并运行：`installer\output\APS_Win7_Setup.exe`
2. 安装完成后，使用开始菜单/桌面快捷方式 **“排产系统 (Chrome)”** 启动  
   - 启动器会先拉起 `排产系统.exe`，再用 `tools\chrome109\chrome.exe` 打开 `http://127.0.0.1:5000/`
3. 若打不开页面，优先查看：`{app}\logs\aps_error.log`

## 备注

- **Chrome 109 已停止安全更新**：建议仅用于离线/内网访问本机 `127.0.0.1` 的系统页面。
- **合规提醒**：把 Chrome 二进制打进安装包可能受 Google 条款约束；若对外/商用分发，请先做内部合规确认。


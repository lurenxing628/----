---
name: aps-package-win7
description: 对 APS 项目进行 Win7 双包打包：生成 APS_Main_Setup.exe 与 APS_Chrome109_Runtime.exe，保留 legacy 全量包回退并执行 validate_dist_exe.py 冷启动验收。适用于用户提到 打包/出包/Win7 安装包/PyInstaller/dist/onedir/Inno Setup/ISCC/Chrome109/冷启动验收 等场景。
---

# APS 打包（Win7 双包 + 冷启动验收）

## Quick start

- 一键打包（PowerShell）：`powershell -ExecutionPolicy Bypass -File .windsurf/skills/aps-package-win7/scripts/package_win7.ps1`
- 默认产物：
  - `installer/output/APS_Main_Setup.exe`
  - `installer/output/APS_Chrome109_Runtime.exe`
- 内部 legacy 回退：`powershell -ExecutionPolicy Bypass -File .windsurf/skills/aps-package-win7/scripts/package_win7.ps1 -Legacy`
  - 产物：`installer/output/APS_Legacy_Full_Setup.exe`

## 适用场景（触发词）

- 打包 / 出包 / PyInstaller / dist / onedir
- Win7 / 安装包 / Inno Setup / ISCC
- Chrome109 / 浏览器运行时 / 冷启动验收 / validate_dist_exe.py

## 硬性前置条件（必须检查）

- 主程序包前置：
  - 已安装 Inno Setup 6（可用 `ISCC.exe`），或设置环境变量 `ISCC_EXE` / `INNO_HOME`
  - 本机 Python 可运行（用于 `validate_dist_exe.py`）
- 浏览器运行时包 / legacy 全量包前置：
  - 优先：`tools/Chrome.109.0.5414.120.x64/chrome.exe` 已存在
  - 或：`tools/ungoogled-chromium_109*.zip` 已存在（`scripts/package_win7.ps1` 会自动解压并整理到上述路径）
- Windows PowerShell 5.1 编码注意：若你修改 `scripts/package_win7.ps1`，建议保持 **ASCII-only**；如必须写中文，请用 **UTF-8 with BOM** 保存或改用 PowerShell 7（否则可能出现 `ParserError`）

## 工作流（给 Agent 的执行指引）

### 0) 端口与环境变量

- 默认优先用 5000；如出现 `WinError 10013` 或现场端口冲突，改用其它端口
- 通过环境变量覆盖：`APS_HOST` / `APS_PORT`

### 1) 生成主程序包

- 构建 `onedir`
- 复制启动器到 `dist`（仅用于直拷目录辅助启动）
- 运行 `validate_dist_exe.py`
- 生成：`installer/output/APS_Main_Setup.exe`

### 2) 生成浏览器运行时包

- 准备离线 Chrome109 / `ungoogled-chromium` 109 目录
- 生成：`installer/output/APS_Chrome109_Runtime.exe`

### 3) 交付口径

- 对外正式交付：`APS_Main_Setup.exe` + `APS_Chrome109_Runtime.exe`
- 最小直拷交付：仅 `build_win7_onedir.bat` 产物，不承诺内置浏览器运行时
- legacy 自包含直拷 / 全量包：仅内部应急使用，依赖 `stage_chrome109_to_dist.bat`

### 4) 冷启动验收（强制）

- 运行：`python validate_dist_exe.py "<dist 下主 exe 路径>"`
- 目标：能启动 + 关键页面 200
- 备注：该验收只验证主程序，不依赖浏览器进程

## 额外资料

- 详细踩坑点与故障排查见：[reference.md](reference.md)

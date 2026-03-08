---
name: aps-package-win7
description: 对 APS 项目进行 Win7 打包：PyInstaller onedir 构建、注入离线 Chrome109、生成 Inno Setup 安装包，并执行 validate_dist_exe.py 冷启动验收。适用于用户提到 打包/出包/Win7 安装包/PyInstaller/dist/onedir/Inno Setup/ISCC/Chrome109/stage_chrome109_to_dist/冷启动验收 等场景。
---

# APS 打包（Win7 onedir + Chrome109 + 安装包 + 冷启动验收）

## Quick start

- 一键打包（PowerShell）：`powershell -ExecutionPolicy Bypass -File .windsurf/skills/aps-package-win7/scripts/package_win7.ps1`
- 最终产物：`installer/output/APS_Win7_Setup.exe`

## 适用场景（触发词）

- 打包 / 出包 / PyInstaller / dist / onedir
- Win7 / 安装包 / Inno Setup / ISCC
- Chrome109 / stage_chrome109_to_dist / 冷启动验收 / validate_dist_exe.py

## 硬性前置条件（必须检查）

- 离线 Chrome109 必须可用（否则注入 Chrome 必失败）：
  - 优先：`tools/Chrome.109.0.5414.120.x64/chrome.exe` 已存在
  - 或：`tools/ungoogled-chromium_109*.zip` 已存在（`scripts/package_win7.ps1` 会自动解压并整理到上述路径）
- 已安装 Inno Setup 6（可用 `ISCC.exe`），或设置环境变量 `ISCC_EXE` / `INNO_HOME`
- 本机 Python 可运行（用于 `validate_dist_exe.py`）
- Windows PowerShell 5.1 编码注意：若你修改 `scripts/package_win7.ps1`，建议保持 **ASCII-only**；如必须写中文，请用 **UTF-8 with BOM** 保存或改用 PowerShell 7（否则可能出现 `ParserError`）

## 工作流（给 Agent 的执行指引）

### 0) 端口与环境变量

- 默认优先用 5000；如出现 `WinError 10013` 或现场端口冲突，改用其它端口
- 通过环境变量覆盖：`APS_HOST` / `APS_PORT`

### 1) 重打前清理（避免 dist 被 Chrome 锁）

- 先 `taskkill /IM chrome.exe /F /T`
- 删除 `build/` 与 `dist/`

### 2) 构建 onedir

- 运行：`cmd /c build_win7_onedir.bat`

### 3) 注入 Chrome109

- 运行：`cmd /c stage_chrome109_to_dist.bat`

### 4) 生成安装包（Inno Setup）

- 运行：`ISCC.exe installer/aps_win7.iss`
- 产物：`installer/output/APS_Win7_Setup.exe`

### 5) 冷启动验收（强制）

- 运行：`python validate_dist_exe.py "<dist 下主 exe 路径>"`
- 目标：能启动 + 关键页面 200（比到 Win7 现场再排查省时）

## 额外资料

- 详细踩坑点与故障排查见：[reference.md](reference.md)

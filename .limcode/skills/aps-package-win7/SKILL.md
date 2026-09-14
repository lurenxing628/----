---
name: aps-package-win7
description: 构建 Win7 x64 绿色便携 ZIP，内含主程序与专用 Chrome109，执行冷启动、浏览器冒烟和 ZIP 完整性验收；原安装包仅通过显式参数生成。
---

# APS 打包（Win7 绿色便携版 + 冷启动验收）

## Quick start

- 一键打包：`build_win7_portable.bat`，或 `powershell -NoProfile -ExecutionPolicy Bypass -File .limcode/skills/aps-package-win7/scripts/package_win7.ps1`
- 默认产物：
  - `dist/APS_Portable_Win7_x64.zip`
  - `dist/APS_Portable_Win7_x64.zip.sha256`
- 维护原双安装包时显式传 `-Installer`；`-MainOnly` / `-ChromeOnly` 继续可用。
- 内部 legacy 回退：`powershell -ExecutionPolicy Bypass -File .limcode/skills/aps-package-win7/scripts/package_win7.ps1 -Legacy`
  - 产物：`installer/output/APS_Legacy_Full_Setup.exe`

## 适用场景（触发词）

- 打包 / 出包 / PyInstaller / dist / onedir
- Win7 / 安装包 / Inno Setup / ISCC
- Chrome109 / 浏览器运行时 / 冷启动验收 / validate_dist_exe.py

## 硬性前置条件（必须检查）

- 主程序前置：Win7 x64、Python 3.8 x64、PyInstaller 4.10、Windows PowerShell 5.1 和三份 requirements 的离线依赖。
- 默认便携版无需 Inno Setup；仅显式安装版模式需要 Inno Setup 6（`ISCC.exe`）或环境变量 `ISCC_EXE` / `INNO_HOME`。
- 便携版 / 浏览器运行时包 / legacy 全量包前置：
  - 优先：`tools/Chrome.109.0.5414.120.x64/chrome.exe` 已存在
  - 或：`tools/ungoogled-chromium_109*.zip` 已存在（`scripts/package_win7.ps1` 会自动解压并整理到上述路径）
- Windows PowerShell 5.1 编码：`scripts/package_win7.ps1` 保持 **ASCII-only**；控制台和原生命令输出明确指定 UTF-8，含空格参数显式带引号。禁止用升级 PowerShell 7 解决本项目兼容问题。

## 工作流（给 Agent 的执行指引）

### 0) 端口与环境变量

- 默认优先用 5000；如出现 `WinError 10013` 或现场端口冲突，改用其它端口
- 通过环境变量覆盖：`APS_HOST` / `APS_PORT`

### 1) 默认生成绿色便携版

- 构建 `onedir`
- 在 `dist` 中加入启动器、裁剪后的 Chrome109、`aps-portable.txt` 和带 BOM 的中文使用说明。
- 运行 `validate_dist_exe.py`，确认数据库和日志都在当前便携目录的 `user-data/`。
- 在含中文、空格路径的临时目录执行浏览器最小冒烟。
- 仅清理本次新构建的测试数据，调用 `scripts/portable_release.py archive` 生成 ZIP，检查完整性并计算 SHA-256；拒绝夹带业务库、日志、备份或浏览器配置。
- 没有 Windows 真机证据时，只能报告实际完成的静态或局部验证，不能写 EXE / PowerShell 5.1 已通过。

### 2) 维护历史安装包（显式模式）

- `-Installer` 生成原双包：`APS_Main_Setup.exe` + `APS_Chrome109_Runtime.exe`。

- 准备离线 Chrome109 / `ungoogled-chromium` 109 目录
- 生成：`installer/output/APS_Chrome109_Runtime.exe`

### 3) 交付口径

- 对外正式交付：`APS_Portable_Win7_x64.zip` + `.sha256`；解压到可写本机目录后双击启动，无需管理员安装或账户/域配置。
- 便携标记必须保留；全部持久数据位于 `user-data/`，旧安装注册表及环境变量不得改写便携数据位置。旧数据通过备份/恢复导入，不自动迁移或清理。
- 最小直拷交付：仅 `build_win7_onedir.bat` 产物，不承诺内置浏览器运行时
- legacy 全量安装包：仅历史内部应急使用，依赖 `stage_chrome109_to_dist.bat`

### 4) 冷启动验收（强制）

- 运行：`python validate_dist_exe.py "<dist 下主 exe 路径>"`
- 目标：能启动 + 关键页面 200
- 备注：该验收只验证主程序，不依赖浏览器进程

## 额外资料

- 当前便携交付、编码文档来源和真机验收见仓库根目录 `DELIVERY_WIN7.md`；历史安装版经验见：[reference.md](reference.md)

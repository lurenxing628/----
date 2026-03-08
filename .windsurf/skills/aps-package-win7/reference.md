# 关键经验（踩坑点）

## 1) Chrome109 必须提前准备好（硬依赖）

- `stage_chrome109_to_dist.bat` **硬依赖**：`tools/Chrome.109.0.5414.120.x64/chrome.exe`
- 若仓库 `tools/` 里只有 `ungoogled-chromium_109*.zip`：
  - 推荐：直接运行 `scripts/package_win7.ps1`，会自动解压并整理到 `tools/Chrome.109.0.5414.120.x64/`
  - 或手工：解压 zip 后，把**包含 `chrome.exe` 的目录**内容拷贝/整理到 `tools/Chrome.109.0.5414.120.x64/`（确保 `chrome.exe` 在该目录根）
- 若 `tools/` 里既没有上述目录也没有 zip：一键打包必失败，需要先准备离线 Chrome109

## 2) 重打前先关/杀掉 Chrome（否则 dist 清理可能 PermissionError）

- Chrome 可能会在 `dist/.../tools/chrome109/Data/...` 写入并锁文件，导致 PyInstaller 清理 `dist/` 报 `PermissionError`
- 重打前建议固定步骤：
  - `taskkill /IM chrome.exe /F /T`
  - 删除 `dist/`、`build/`

## 3) 端口 5000 在部分环境会被策略拦截（WinError 10013）

- 现象：启动时出现 `WinError 10013`（绑定被拒绝）
- 解决：用环境变量覆盖端口
  - `APS_HOST=127.0.0.1`
  - `APS_PORT=<可用端口>`
- 备注：启动器 bat 与 `validate_dist_exe.py` 已跟随支持（现场冲突/受限环境可直接换端口）

## 4) 打完一定做一次冷启动验收（强制）

- `validate_dist_exe.py` 能快速兜底“能启动 + 关键页面 200”
- 比到 Win7 现场再排查更省时间

## 5) PowerShell 5.1 + UTF-8 无 BOM 脚本可能触发 ParserError

- 现象：运行 `scripts/package_win7.ps1` 报 `ParserError`；中文字符串变乱码；报错位置可能指向类似 `$chrome = "tools\\..."` 的正常代码行
- 原因：Windows PowerShell 5.1 读取脚本文件时可能按系统 ANSI 代码页解析；当脚本为“UTF-8 无 BOM”且包含非 ASCII 字符时，可能导致解析失败
- 规避建议（择一即可）：
  - 最稳：保持 `package_win7.ps1` **ASCII-only**（推荐）
  - 若必须写中文：用 **UTF-8 with BOM** 保存该 `.ps1`
  - 或用 PowerShell 7 执行（`pwsh`）

---

# 一次性打包脚本（推荐）

见：`scripts/package_win7.ps1`

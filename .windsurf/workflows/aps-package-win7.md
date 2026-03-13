---
description: APS Win7 双包打包流程：生成 APS_Main_Setup.exe 与 APS_Chrome109_Runtime.exe，并执行主程序冷启动验收
---
当用户提到“打包 / 出包 / Win7 安装包 / PyInstaller / dist / onedir / Inno Setup / 冷启动验收”时，使用本 workflow。

1. 先检查前置条件。
   - 默认优先用端口 5000；若出现 `WinError 10013` 或端口冲突，改用其它端口。
   - 需要时通过环境变量覆盖：`APS_HOST`、`APS_PORT`。
   - 主程序包需要 Inno Setup 与 Python。
   - 浏览器运行时包额外需要离线 Chrome109 或 `ungoogled-chromium` 109 zip。

2. 生成主程序包。
   - 执行：`cmd /c build_win7_onedir.bat`
   - 复制启动器到 `dist`（仅用于直拷目录辅助启动）
   - 再调用：`ISCC.exe installer/aps_win7.iss`
   - 目标产物：`installer/output/APS_Main_Setup.exe`

3. 生成浏览器运行时包。
   - 确认 `tools/Chrome.109.0.5414.120.x64/` 已就绪，或能从 `tools/ungoogled-chromium_109*.zip` 自动整理
   - 调用：`ISCC.exe installer/aps_win7_chrome.iss`
   - 目标产物：`installer/output/APS_Chrome109_Runtime.exe`

4. 做冷启动验收，这是强制步骤。
   - 运行：`python validate_dist_exe.py "<dist 下主 exe 路径>"`
   - 验收目标：程序能启动、关键页面能正常返回
   - 备注：该验收不依赖浏览器运行时

5. 仅在内部应急场景下，才走 legacy 自包含全量包。
   - 需要先执行：`cmd /c stage_chrome109_to_dist.bat`
   - 目标产物：`installer/output/APS_Legacy_Full_Setup.exe`

6. 向用户回报时至少包含。
   - 主程序包是否生成成功
   - 浏览器运行时包是否生成成功
   - 冷启动验收结果
   - 若失败，指出失败发生在构建、运行时包准备、打包还是验收阶段

7. 使用边界。
   - 本 workflow 会修改构建产物与安装包目录，只在用户明确要求打包时使用
   - 对外正式交付只使用双包；legacy 全量包仅内部应急使用

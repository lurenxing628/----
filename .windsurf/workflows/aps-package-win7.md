---
description: APS Win7 打包流程：onedir 构建、注入 Chrome109、生成安装包并执行冷启动验收
---
当用户提到“打包 / 出包 / Win7 安装包 / PyInstaller / dist / onedir / Inno Setup / 冷启动验收”时，使用本 workflow。

1. 先检查前置条件。
   - 默认优先用端口 5000；若出现 `WinError 10013` 或端口冲突，改用其它端口。
   - 需要时通过环境变量覆盖：`APS_HOST`、`APS_PORT`。

2. 重打前清理，避免旧进程锁文件。
   - 先关闭可能占用 `dist/` 的 Chrome 进程。
   - 再清理 `build/` 与 `dist/`。

3. 构建 onedir。
   - 执行：`cmd /c build_win7_onedir.bat`

4. 注入 Chrome109。
   - 执行：`cmd /c stage_chrome109_to_dist.bat`

5. 生成安装包。
   - 执行：`ISCC.exe installer/aps_win7.iss`
   - 目标产物：`installer/output/APS_Win7_Setup.exe`

6. 做冷启动验收，这是强制步骤。
   - 运行：`python validate_dist_exe.py "<dist 下主 exe 路径>"`
   - 验收目标：程序能启动、关键页面能正常返回。

7. 向用户回报时至少包含。
   - onedir 是否构建成功。
   - 安装包是否生成成功。
   - 冷启动验收结果。
   - 若失败，指出失败发生在构建、注入、打包还是验收阶段。

8. 使用边界。
   - 本 workflow 会修改构建产物与安装包目录，只在用户明确要求打包时使用。

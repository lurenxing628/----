APS 排产系统 · Win7 x64 绿色便携版

1. 将整个 ZIP 解压到当前账户可读写的本机目录，例如 D:\APS。
2. 双击“启动_排产系统_Chrome.bat”。首次启动会自动建立 user-data。
3. 无需安装主程序、Python 或浏览器，无需管理员安装或选择本地/域账户。

使用数据均位于本文件旁边的 user-data：
  db\aps.db             业务数据库
  backups\              系统备份
  logs\                 日志和运行状态
  templates_excel\      Excel 模板
  chrome109_profile\    APS 专用浏览器配置

正常退出：使用系统页面中的退出功能，等待程序退出后再移动或复制目录。
迁移电脑：正常退出后，把整个 APS_Portable 文件夹复制过去。
升级程序：把新 ZIP 解压到新的空目录，关闭旧程序后，将旧 user-data 整个复制到新目录。
已有安装版数据：先从旧系统导出备份，再在便携版的系统维护页面恢复。
新便携版首次启动为空库，不会自动读取、删除或迁移旧安装的数据。

如果解压后的中文文件名异常，可在 ZIP 所在目录用 Windows PowerShell 5.1 执行：
  Expand-Archive -LiteralPath '.\APS_Portable_Win7_x64.zip' -DestinationPath 'D:\APS_new'
目标请选择新的可写目录。也可以直接从打包机复制构建完成的完整便携文件夹。

请保留 aps-portable.txt，以及完整的 tools\chrome109 和所有程序文件。
不要直接在压缩包内启动，不要把程序放在 Program Files 等当前账户不可写的目录。
同一份数据一次只允许一个实例使用；另一账户正在使用时，需等其正常退出。
便携版不修改机器级 APS 注册表或创建系统安装记录；Windows 目录权限仍须允许当前账户写入。
专用浏览器仅用于本机 APS 页面。

启动失败时，查看 user-data\logs\launcher.log 和 aps_launch_error.txt。
排产系统.exe 是后台服务；日常启动请使用上述 bat 文件。

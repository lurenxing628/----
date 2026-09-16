# 手动验收环境收口

- 时间：2026-09-15 23:01（Asia/Shanghai）。
- 保留真实主服务：[5000 工作台](http://127.0.0.1:5000/workbench)，PID `19236`，exec session `6442`。本阶段没有停止或重启它。
- 保留验收结果实例：[5005 工作台](http://127.0.0.1:5005/workbench)，新 PID `30081`，exec session `36919`，23:01:34 启动。两处只读 HTML 请求均为 200，`Cache-Control: no-store`。

## 已停止的隔离服务

对每个端口先用 `lsof` 获取实际监听 PID，再核对 Python 3.8 命令中的 `manual_app.py`、对应 `aps-manual-...` 目录、运行时契约和数据库路径。只向核验过的 PID 发送 SIGINT，随后确认四个端口不再监听。

| 端口 | 已停止 PID | 保留的隔离目录 |
| --- | --- | --- |
| 5001 | 18857 | `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-manual-remediation-20260915-m5q25mau` |
| 5002 | 91606 | `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-manual-outsourcing-20260915-1lytmyfn` |
| 5003 | 91706 | `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-manual-resources-20260915-494scls2` |
| 5004 | 91786 | `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-manual-process-batches-vizr_h36` |

所有目录、`db/aps.db`、`manual_app.py`、备份和证据文件均保留。四个 launcher 与关闭前的 SHA-256 一致；原有备份仍在且字节数一致。收口 JSON 记录全部数据库及备份的 SHA-256，可按保留的 launcher 和对应端口恢复实例。本阶段没有删除任何文件。

## 5005 结果与重启保留证据

验收实例保留在 `/private/var/folders/cz/6c_ysj195sbcytsy44zttdbc0000gn/T/aps-manual-reports-5005-mas98q0a`。旧 PID `13155` 经同样精确核验后正常退出，以 `APS_ENV=production`、该目录作为 `APS_SHARED_DATA_ROOT`、`APS_HOST=127.0.0.1`、`APS_PORT=5005` 和原 launcher 启动，加载最新后端。

重启前后使用 SQLite URI `mode=ro`、`query_only=ON`、只读事务采集全部行，逐列 SQLite 类型参与哈希，按行多重集合比较：

- 79 张表中 77 张完全一致；所有业务旧行、类型和全部 DDL 保留，schema32 不变。
- 仅 `OperationLogs` 新增 1 条插件启动日志（13,401 → 13,402 行），对应 `sqlite_sequence` 增加 1。没有业务新增、删除或改写。
- 27 个批次、74 道批次工序、正式计划 v15 的 74 道任务、5 次报工全部保留。
- 校准采用记录保留：模板版本 1 → 2，单件工时 0.05 → 0.09 小时，样本数 5；采用编号 `b70aa43ec55331a4abf737bd25715d8ff28b54044258be42`。
- 完整性检查 `ok`，外键检查无问题。

证据：`isolated-env-before-closeout.json`、`isolated5005-before-restart.json`、`isolated5005-after-restart.json`、`isolated-env-closeout.json`。5005 服务继续运行供用户打开查看。

未修改产品文件、运行门禁、测试或 build，也未执行 SQL/HTTP 业务写入或提交。

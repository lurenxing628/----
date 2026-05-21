---
doc_type: audit-finding
audit: 2026-05-21-networkx-full-browser-stress
finding_id: runtime-port-file-mismatch
nature: bug
severity: P1
confidence: high
status: open
suggested_action: cs-issue
last_deep_trace: 2026-05-21
---

# Finding 01：运行端口文件写成 5000，但实际服务在 61661

## 现象

本轮临时服务实际打开地址是 `http://127.0.0.1:61661/`，浏览器能正常访问。但运行信息文件仍写着 5000。

## 操作步骤

1. 用临时环境启动 APS，指定 `APS_PORT=61661`。
2. 浏览器访问 `http://127.0.0.1:61661/`，页面可用。
3. 查看 `/tmp/aps-networkx-full-browser-stress.h88s1vh4/logs/aps_port.txt`。
4. 查看 `/tmp/aps-networkx-full-browser-stress.h88s1vh4/logs/aps_runtime.json`。
5. 分别访问 61661 和 5000 的健康检查。

## 实际表现

- `aps_port.txt` 内容是 `5000`。
- `aps_runtime.json` 里的 `port` 是 `5000`。
- `http://127.0.0.1:61661/system/health` 返回 `status=ok`。
- `http://127.0.0.1:5000/system/health` 连接失败。

## 期望表现

运行信息文件应该写真实可访问端口 `61661`，否则维护人员或启动器按文件打开会走到错误地址。

## 问题类型

配置/启动信息错误。

## 严重程度

明显影响使用。服务本身能用，但运行提示文件会误导用户和维护工具。

## 证据

```text
aps_port.txt=5000
aps_runtime.json -> "port": 5000
61661 health -> {"app":"aps","status":"ok",...}
5000 health -> Failed to connect
```

## 追加根因追踪（2026-05-21）

根因不是压测脚本把端口文件写错，而是开发模式重载子进程重新挑了一次端口。

调用链：

- [app.py](/Users/lurenxing/Documents/GitHub/----/app.py:58) 的 `main()` 进入 `entrypoint.app_main()`。
- [web/bootstrap/entrypoint.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/entrypoint.py:225) 读取 `DEBUG`，默认开发配置会开启重载。
- [config.py](/Users/lurenxing/Documents/GitHub/----/config.py:60) 里 `DevelopmentConfig.DEBUG = True`，默认配置也是开发配置。
- [web/bootstrap/entrypoint.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/entrypoint.py:232) 读取 `APS_PORT`，默认候选端口在 [web/bootstrap/entrypoint.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/entrypoint.py:233) 是 `5000`。
- [web/bootstrap/entrypoint.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/entrypoint.py:243) 调 `pick_port()`。
- [web/bootstrap/launcher_network.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/launcher_network.py:128) 的候选端口顺序包含 `preferred`、`5000`、`5705`。
- [web/bootstrap/entrypoint.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/entrypoint.py:271) 把选出来的端口传给运行契约写入。
- [web/bootstrap/launcher_contracts.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/launcher_contracts.py:82) 写 `aps_port.txt`；[web/bootstrap/launcher_contracts.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/launcher_contracts.py:348) 写 `aps_runtime.json`。

关键变量：

- 默认端口：`preferred_port = 5000`。
- 指定端口：`APS_PORT=61661`。
- 实际监听端口：`61661`。
- 写入运行文件的端口：`5000`。
- 触发条件：`WERKZEUG_RUN_MAIN=true` 且已有 `WERKZEUG_SERVER_FD` 时，子进程复用父进程打开的 `61661` socket，但应用代码又重新 `pick_port()`，看到 `61661` 已被占用后误选 `5000` 写文件。

## 建议修复方向

最小修复点应放在 [web/bootstrap/entrypoint.py](/Users/lurenxing/Documents/GitHub/----/web/bootstrap/entrypoint.py:232) 附近：当处于 Werkzeug reloader 子进程并已有 `WERKZEUG_SERVER_FD` 时，不要重新探测端口，应沿用父进程传下来的 `APS_PORT` 写运行契约。`launcher_contracts.py` 只是写入传入端口，不是根因位置。

需要补回归：模拟 `WERKZEUG_RUN_MAIN=true`、`WERKZEUG_SERVER_FD=5`、`APS_PORT=61661`，即使 `pick_port()` 会返回 `5000`，也应断言写入运行文件的端口仍是 `61661`。另补真实启动级回归：非默认端口启动后，`aps_port.txt`、`aps_runtime.json`、健康检查地址三者一致。

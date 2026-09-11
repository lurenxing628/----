---
doc_type: acceptance-evidence
status: failed-preserved
date: 2026-09-10
scope: B owned copy of F13-source9, b7b4 build, ea5f test snapshot
---

# 首轮 Canonical / Boot 收尾

## 结论

- 完整执行 252 项，结果保留为 **216/252，通过不足，complete=false**。canonical 为 176/212，focused boot 为 40/40；不缩小分母，不覆盖历史 64b6 的 92/92。
- 36 个失败分两类：32 个是 ea5f 探针错误要求试调首次 URL 读取后已写 history；4 个是四种屏幕/主题组合下，报表原页跨宿主 PID 重启后真实 GET 返回 `409 snapshot_stale`。
- B 已只修探针空 history 假设，V2 测试集合为 `06ad141125f5bd09672ea60dcebb6d19b9c292d6f8296989127bacb73266be61`，24 个定点与 Ruff/Pyright/CJS syntax 通过，**尚未进行 V2 live 重跑**。不能把旧 32 项追记成通过。
- Main 已确认报表恢复根因并协调 E 修复。保持后端 snapshot 合同和运行中 409，不由 B 修改产品；等待 E 修复与新的完整 source/build，再 fresh copy 跑完整 252，不在已知缺口的旧快照盲跑。正式 5000 不在本轮执行。

## 绑定身份

| 项目 | 实际值 |
|---|---|
| F 原 source | `/private/tmp/aps-final-operations-F.TQejHX/F13-source9` |
| F 原 build | `/private/tmp/aps-final-operations-F.TQejHX/F13-copy-build7` |
| F source aggregate | `5dd296f23cda9993c3560cf8b1d11d1baf5ae8bb6fe84b138fdbedc7424e6be1` |
| B owned package | `/private/tmp/aps-final-foundation-B.xYPahs/F13-source9-copy-jNxcdz` |
| B source | 上述 package 的 `source` |
| B prebuilt | 上述 package 的 `prebuilt/static/workbench` |
| build_id | `b7b4f7c2241d948af6ae121f9940aaccba477ae26b8341b6393cee139e4491cb` |
| manifest SHA256 | `db6535e80339d7dec33c802696327aae3fad2e64ec288da85409830cf0e13b4b` |
| 本轮 12 tests SHA256 | `ea5f795e8b58ac16dcf21435b2858f1115ec872b2416aa1995290ac548884b16` |
| 运行 root | `/private/tmp/aps-final-foundation-B.xYPahs/F13-source9-copy-jNxcdz/fixtures/aps-workbench-live-if1sqobh` |
| 浏览器 | macOS Chromium 109.0.5414.46 |

启动命令与所有参数保存在 B package 的 `provenance/launch-canonical-boot.sh`，实际由 `/bin/sh` 执行。没有重 build，没有向 F 原 source 或 asset root 写入 overlay。

3632 个源码文件与 223 个资产文件（222 个 manifest 资产加 manifest 自身）逐 SHA/mode 相等；314 个 build 输入对应 B 源校验通过。12 项 tests-only 机械覆盖前后字节相同，依然独立分账。第一次模式受 umask 缩窄的 `F13-source9-copy-ODpZW6` 副本没有启动宿主，原样保留；jNxcdz 是重新复制并逐文件恢复 F mode 后验证的 fresh 副本。

## 409 最小证据

- 实际请求：`GET /api/workbench/v1/analytics`，body 为 null。query 含原 plan/batch/日期、`query=CAT-B`、topic/page/size/sort/direction 与 `snapshot_ref`；不含 `write_token`、`request_key` 或 command 字段。
- 响应：HTTP 409，`error.code=snapshot_stale`，`retryable=false`。原因原文：`读取范围已失效，请重新刷新；未自动切换到新数据。`
- 这是 **只读 snapshot_ref 失效，不是命令票据失效**。报表 GET 在 `web/routes/workbench/reports.py:25` 解析 `workbench-read-v1` 引用；`:36` 转为本次错误，`:128` 路由仅允许 GET。
- 原页 `history.state.workbench.view=reports`。`context.snapshot_ref` 和 `context.table.snapshot_ref` 是同一个旧只读引用；`context.scope` 中原 plan/batch/日期/query 保留，table 另有 topic/page/size/sort/direction。票据原值不在本交接回显。
- `frontend/workbench/app/ReportWorkspace.jsx:9` 把初始 history 的 snapshot 带入读取，`:27` 保存 response 与 table 的 snapshot；`web/public_token_registry.py:47` 使用进程内 `current_app.extensions` 登记，`:134` 解析引用。上述行号均对应本轮 B 冻结 source，不冒充后续 E 修改后的行号。

四组合 page_id 依次为 10、72、134、196；原始响应在运行 root 的 `foundation-responses/78791.json`、`80117.json`、`81443.json`、`82769.json`。完整字段名、原始响应 SHA 和冻结源码 SHA 在 `canonical-boot-ea5f-report409.json`。Main 已将证据转给 E。

没有清 history、删 snapshot_ref、改 URL、换新页面或使用假 API 响应来绕过失败。这里保留首次恢复失败，不把后续尚未执行的用户重读推定为已通过。

## 重启与保留

- 原宿主 PID 22346 正常停止，新宿主 PID 25308 在同一 `http://127.0.0.1:63894` 启动；browser PID 22380 和 24 个原 page/context 保活，原页面分别执行新 PID 恢复检查。
- 两个宿主均 return 0、runtime closed、pending=[]，运行锁与 DB 锁释放。Python 源守护分别记录 1101、1052 个项目模块，违规为 0；Node 源守护同样通过。所有 B 宿主/浏览器进程均已结束。
- 两进程内业务行前后完全一致；跨启动 75 张表不变，原行保留，只追加 1 条 `plugins/load` 正常启动审计及对应 `sqlite_sequence`。单个真实 trial 草稿在业务基线前由真实服务创建，request/receipt/前后行证据独立保留。
- F/B 两份源码与两份资产在运行后再次逐 SHA/mode 核对一致。772 个 raw API 文件、408 张截图散列核对通过；51448 条正常浏览器资产响应均有实际 bytes SHA，与 manifest 相等。
- 正常阶段错误为 4 次上述 HTTP409 和 4 条对应 console 错误，外部请求为 0。正常 production response 为 468；这不把边界故障测试算成业务成功。

## 文件与边界

- `canonical-boot-ea5f-evidence.json`：固定分母、全部失败索引、copy/build/test 身份、PID/page 身份、模板与数据保留证据。
- `canonical-boot-ea5f-post-verification.json`：运行后源/资产 mode+SHA、raw API/截图散列与锁释放复核。
- `canonical-boot-ea5f-report409.json`：不回显票据的 4 个只读失败请求、history 字段与源码位置。
- `executable-groups-trial-history-v2.json`：仅探针修正的新测试快照与 24 项单位验证，不是 live PASS。
- 原始 `foundation-result.json` 的 SHA256 为 `083214ff60bf21d65cd9bbbef0f0ef325aab35bc231e9b07d2ef8e5e4d732f8e`，`foundation-browser.json` 为 `d13e22fabf989f88eb1a7e2cb5ef6e86b76172520ad40f3de41726d9fda43214`，未覆写其失败状态。

本轮是 `unchanged_snapshot_not_final_HEAD`，`source_changes=[]`，不是最终 HEAD、clean-worktree proof 或原生 Win7 验收。没有整仓 full gate、提交或全局 freeze；当前 B 测试及本目录交接文件未提交，保留其他人的工作区改动。408 张图均有自动非空像素检查，B 人工抽看了报表失败与真实草稿两张，不代签全量视觉终审。旧 53144 和原生产数据未操作。

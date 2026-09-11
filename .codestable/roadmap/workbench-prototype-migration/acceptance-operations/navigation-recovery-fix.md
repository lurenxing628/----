# F：导航确认与跨进程只读状态恢复

## 结论与范围

- 本次是已授权的 `cs-issue-fix` 定向收尾：R14 两个原范围缺口、Dashboard 跨进程快照恢复、System 跨进程记录选择。与原 13 项补全分别记账，分母仍为 33 族 / 228 动作。
- 仅改四个 F 前端文件及对应测试。没有修改 backend token 生命周期、日志 key、恢复/删除执行协议、共享导航、全局构建注册或已固定归档。
- 最终固定完整源 source18 的 21 项全部通过，其中 19 个真实主入口场景、2 个源码合同补充；不是模拟接口页面，也不是 21 个组件测试。所有运行根均在 `/private/tmp/aps-final-operations-F.TQejHX/`，不涉及生产库或旧预览。

## 已复现根因

| 根因 | 真实失败证据 | 最小修复 |
| --- | --- | --- |
| DashboardSession 严格解析后仍保留 `q.snapshot_ref`，Workspace 又把它存入 page-context；新 PID 无法解析旧读快照 | `F13-restart-red2-results.xml`：同 page/context、端口 61798，PID 33659 → 33707，material/open/F-R2/desc/10/第二页，实际 GET 返回 `409 snapshot_stale` | `DashboardWorkspace.jsx:4` 只保留持久筛选；`:5` 同条件第一页绑定新快照再读原第二页，第一页不渲染；`:40` 与 `:141` 同时处理新保存和旧恢复，未知字段/错误字段类型仍拒绝 |
| 不可定位原对象时 Detail 禁用按钮，navigate 对 enabled=false 直接返回，缺少原型要求的确认分支 | 旧禁用证据与补全前状态仍留在历史 handoff/control mappings；当前后端真实 formal v2 不含原 B1，原 v1 的 26 条处置历史仍在 | `DashboardPanels.jsx:5` 校验已知目标与回调，`:89` 使用现有 Modal；`DashboardWorkspace.jsx:43` 确认只传安全概览和原返回上下文，不带原计划/批次/工序引用 |
| System records 持久化进程内 snapshot；备份选择还绑定旧 backup_ref | `F13-system-red1-results.xml`：备份同端口 54944，PID 36577 → 36599；日志同端口 55457，PID 36779 → 36804。两者原页新 PID 均实际 409 | `SystemMaintenanceAPI.js:149` 持久化只保留稳定 key/类型，`:159` 保留原页和筛选并剥离旧读令牌；`SystemMaintenanceRecords.jsx:56` 新进程直接读取原页的新快照，`:63` 仅唯一同 key/类型匹配，`:70` 保存当前进程新文件引用 |

System 和 Dashboard 的后端分页合同不同：System 允许不带旧 snapshot 的指定页读取并绑定新快照；Dashboard 第二页必须带快照，因此先做同 scope 的第一读取。两者都不把过期请求自动改成其他范围，也不静默回到第一页。

现有备份 key 的来源是 `core/services/workbench/system_reads.py:14` 的 size/mtime_ns/inode/device 与 `:34` 的文件名签名散列，不是进程 token。无需增加后端字段或逐文件全量内容散列。日志原 key 保持原定义和原值；缺少可信文件 key 的旧历史只提示，不用旧 backup_ref、同名文件或首行伪匹配。

## 验证

| 场景 | 当前结果 |
| --- | --- |
| Dashboard 原浏览器跨 PID，原筛选/清单第二页/选中条目/历史第二页 | 1392/1920 × 浅/深，共 4 PASS；每次原页 reload 的真实两次读取为同 scope 的 page1 + page2，原 item_ref 和 history_page=2 保持 |
| R14 确认、四种关闭、安全概览、原条目返回 | 四组合 4 PASS；取消/X/遮罩/Esc 均无导航写入，明确确认只进空概览，无当前计划 caption、无替代对象高亮；原生后退仍是原 B1 与跟进中筛选，F5 只清确认框；有效批次引用仍直达 |
| System 备份/日志原页跨 PID | 两种活动页各四组合，共 8 PASS；两个页签各自原筛选、page=2、稳定 key 保留；文件 backup_ref 变成新进程值，持久 context 不含 snapshot_ref/backup_ref/write_token |
| 同名备份替换 | 1 PASS；仅私有夹具在停机时用真实新备份替换选中文件，保留原文件名和时间但 inode/内容不同；新页仍有同名文件，新 key 不同，原选择保持未解决，无详情和文件确认动作自动弹出 |
| 旧历史只含 backup_ref、没有稳定 key | 1 PASS；明确标注为负向旧 history 夹具，仍使用完整 main 与真实 API；恢复原页/筛选，明确提示缺 key，不制造 key、不选其他记录 |
| 未核实配置请求跨 PID | 1 PASS；真实保存 interval=73，仅丢弃响应 ACK；重启后只 GET 原 request/receipt，保留待核实请求与新数据，浏览器 POST 总数仍为 1，没有自动重放 |
| 旧活动令牌仍拒绝 | 上述三项各实测旧 snapshot GET 409、旧 backup download 409、旧 delete/restore POST 409；均未改变数据库/备份/journal，维护请求协议未放宽 |
| 合同和旧相关回归 | 2 个源码合同测试在 source18 通过；原树另有 records/download/System widget 23 PASS。widget 仅为补充组件验证，不冒充 main 证据 |

最终命令（在 `/private/tmp/aps-final-operations-F.TQejHX/F13-source18` 执行）：

```bash
env -u PYTHONPATH -u PYTHONHOME \
  FINAL_OPERATIONS_SOURCE_MANIFEST=/private/tmp/aps-final-operations-F.TQejHX/F13-source18-manifest.json \
  FINAL_OPERATIONS_BUILD=/private/tmp/aps-final-operations-F.TQejHX/F13-copy-build16 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/aps-final-operations-F.TQejHX/pycache \
  /Users/lurenxing/GitHub/----/.venv/bin/python -m pytest \
  tests/workbench/test_final_operations_system_recovery.py \
  tests/workbench/test_final_operations_navigation.py \
  tests/workbench/test_final_operations_system_restart.py \
  tests/workbench/test_final_operations_context_contract.py \
  tests/workbench/test_final_operations_download_contract.py \
  -q -x -p no:cacheprovider \
  --basetemp=/private/tmp/aps-final-operations-F.TQejHX/F13-final-delta1-pytest \
  --junitxml=/private/tmp/aps-final-operations-F.TQejHX/F13-final-delta1-results.xml
```

该命令是实际历史命令；重跑应使用新的私有 basetemp/XML 路径，不覆盖旧证据。

## 数据与来源

- `F13-final-delta1-source-proof.json`：3672 个完整源文件 SHA/bytes/mode 重检零变化，38 个宿主进程的 repo-owned loaded-module 全在固定源中，violations 为空；原 venv 仅提供 Python 3.8 和第三方依赖。
- 15 次原 page/context 同端口跨 PID 场景，全部表保留，仅允许正常启动新增一条 `plugins/load` INFO 审计和其序号。备份与 journal 的跨启动哈希也逐项复核；仅“同名替换”测试事先声明的那个私有夹具文件允许变化。查 `runtime-evidence.json#restart_non_database_file_checks`。
- 旧失败没有删除：初次 Dashboard 测试夹具未提供 detail 读快照、R14 重复文本定位、配置 ACK 观察时序等测试错误均各自保留；实际产品 409 红证据单独列出，没有把它们混为产品根因或把失败整命令改称通过。
- Main 旧 28 张图片已通过独立可见布局检查，逐 SHA 原样引用 `../round2-main-v-F-matrix4.json`。新 delta 55 张图片尚待 Main 独立 V，F 不宣称全 228 动作 V。

## 交接

- 机器可读索引：`navigation-recovery-evidence.json`、`runtime-evidence.json`、`source-hashes.json`、`b-shared-source.json`。源与构建均只读复制到接收方自己的私有根，不覆盖 F 原证据。
- 没有新增产品叶文件，不需要新构建注册。Dashboard build-order 所有权已经交还 Main；F 不执行 B252、不改 H 全局 registry/门禁。
- 工作区仍有多方未提交内容。当前结论是绑定完整源码副本的新 delta 与注明的局部回归；统一最终 HEAD、容量门禁、Win7 实机与 clean-worktree proof 由 Main/H 后续统一给出。

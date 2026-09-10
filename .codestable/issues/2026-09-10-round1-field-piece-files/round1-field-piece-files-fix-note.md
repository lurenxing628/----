---
doc_type: fix-note
status: fixed
date: 2026-09-10
scope: R1-B
---

# R1-B 现场分件文件与 CSV 兼容补漏

## 授权与边界

- 仅完成第一轮已知补漏，以及主线追加授权的 `actual_gantt_scope.py` 三函数和 `field_workspace.py` 的 `cohort` 职责拆分。
- 保留已有 dirty，不 stage/commit；未修改 `execution_ledger*`、`production_report_*`、共享控件、全局配置或测试登记表。
- 未操作生产数据库、预览服务、全局 build；未进行全站验收、5000 压测、Win7 发布或旧 UI 下线。
- 原文件副本和本轮私有验证在 `/tmp/aps-r1-b.c3LzAl/`；没有删除共享缓存。
- 唯一 staged 仍为 `tests/gate_meta/test_frozen_bundle_contract.py`，Git blob `3a755494`，文件 SHA-256 `c7a02daca9a8bfd7c9f57dcb7374a1031534c8e067f8809a9902dbc650487b2b`，未触碰。

## XLSX 契约

- 原十列顺序不变：报工编号、批次号、工序、本次完成数量、实际开工、本次实际完工、有效加工工时(h)、实际设备、实际人员、备注。
- 下载模板和下载报工记录在末尾追加：任务编号、工序范围、单件编号。严格识别十列或十三列的完整表头集合，允许整体列重排，不接受缺列、错名、混合版本、重复列或额外物理列。
- `field_report_files_codec.py:20` 定义十三列表头；`:82` 识别格式；`field_report_files_xml.py:53` 核对原始 XML 的行号、列号、合并单元格和物理边界。不依赖 worksheet dimension 截断原内容。
- `field_report_files_identity.py:6` 从当前原读取范围预填永久 task_ref，界面称“任务编号”，不用手抄 48 位引用。填写说明及 `FieldFiles.jsx:29` 明确预填身份不可修改。
- `field_report_files_identity.py:20`：十三列按当前原范围 task_ref 唯一定位，同时核对批次、工序、工序范围、piece_id。单件必须有一致的单件编号；共同工序单件编号为空。伪造、范围外、过期编号或身份错配均拒绝，不退回名称猜匹配。
- 原十列只在批次号和工序唯一时可用；同批同序同名分件仍拒绝。只凭名称不能猜件。
- 数量和工时的未知保持空值/null，0 保持已知零；字符串单件编号 `0` 不当作空值。完整 0 报工也不自动完成工序，单件完成不带动兄弟件或共同工序。
- 原生产链路未替换：预检保留原 bytes、SHA-256、读取 snapshot、业务 snapshot；确认按原 preview_ref/request_key 原子执行；已提交请求在 context/token 过期后仍按原回执重放，不能累计第二次。
- 导出后跨计划重导保留原 report_ref/report_no/operation_ref/recorded_against_plan_ref/recorded_against_task_ref 和更正历史。已知字段冲突仍拒绝，不能用文件导入充当无原因更正。
- 没有新增路由、请求字段或模板参数。内部 codec 保留 `format_version=1` 默认值供原十列调用，正式下载显式使用版本 2。

## CSV 契约与消费者证据

- `actual_gantt_export.py:11` 恢复第十列旧 header `目标数量`，位置和值均不变，仍为 `execution.target_quantity`。
- 原前 42 列 header 不变；尾部 5 列继续为单件编号、计划应做数量、计划批次数量、计划数量依据、计划数量缺失原因，来自计划任务的五个原字段。未知不会用当前批次数量冒充计划历史证据。
- `field_report_files_codec.py:133` 填写说明明确 CSV 的目标数量是执行口径，计划数量另列。没有再次新增/改名 CSV 格式。
- 实际生产导出入口为 `web/routes/workbench/actual_gantt.py:44`。定向 `rg` 搜索 `actual_gantt_csv`、`field_report_files`、`目标数量`、`执行目标数量`，找到服务、路由、下载和测试引用；未找到 repo 内按这些列头解析实际甘特 CSV 的生产消费者。
- 这不证明外部脚本全部兼容。存量证据仅限当前 repo 回归与原列位置/值契约。
- `test_round1_field_piece_files_contract.py:20` 锁原 42 列 prefix、尾部五列准确值、第十列执行数量、原录入引用、null/0 和快照/筛选证据；同时验证跨计划重导和更正前后值留存。

## 职责拆分

| 原函数 | 原复杂度 | 当前复杂度 | 说明 |
| --- | ---: | ---: | --- |
| `ActualGanttScope.__post_init__` | 16 | 2 | 日期、资源、批次各自校验，错误语义不变 |
| `cohort_match` | 20 | 8 | 资源匹配及未知旧资源拒绝独立；point 半开区间不变 |
| `view_items` | 16 | 10 | 参数校验与本地视图筛选拆开 |
| `FieldWorkspaceService.cohort` | 17 | 9 | 单任务投影放到 `_task`，五数量字段及 point 字段原样透传 |

初始证据为 `output/workbench-migration/verification/round1-20260910/architecture-before.log:137` 和 `:145`。精确原类型诊断 `output/workbench-migration/verification/point-main-20260910/stage-pyright.json` 对本轮七个产品文件未列诊断；未据此声称整仓类型通过。

## 验证

全部后续 Python 命令带：

```text
PYTHONPYCACHEPREFIX=/tmp/aps-r1-b.c3LzAl/pycache
PYTHONDONTWRITEBYTECODE=1
```

- 起步十列 API/codec：10 passed，排除原 5000 行容量用例；在上述 pycache 隔离参数下重跑同为 10 passed。
- 新文件契约及存量文件 API/codec：41 passed，1 deselected；增加第二行写入故障回滚、单件真实完成后联合回归为 99 passed，2 deselected (73.47s)。`/tmp/aps-r1-b.c3LzAl/final-api.xml` 保留逐项结果。
- 联合 API 范围：`test_round1_field_piece_files.py`、`test_round1_field_piece_files_codec.py`、`test_round1_field_piece_files_contract.py`、`test_field_files_api.py`、`test_field_files_codec.py`、`test_field_workspace_api.py`、`test_piece_downstream_api.py`、`test_actual_gantt_api.py`、`test_point_downstream_api.py`。排除 `capacity_exact` 和 `10000_operations`，没有压测。
- 故障注入仅在私有库建临时 trigger，让第二条 revision INSERT 失败；整批 reports/revisions/clock/receipt 均回滚，删除该测试 trigger 后同 request_key 可重试成功并只重放一次。
- Chrome `109.0.5414.46`，1920x1080/1392x924，light/dark：4 passed (38.41s)。测试入口 `test_round1_field_piece_files_browser.py`，只编译该域组件到私有 HTTP 进程内存，`global_build=false`。
- 四视口每次均走真实下载模板、原文件填报同批同序的两个单件及共同工序、真实预检/确认/刷新/导出、重复导入。最终各 3 条 report/revision，0 报工不完成，兄弟件不变；无 pageerror。截图已逐一视觉核对，没有越界/遮挡。
- 初次浏览器证据为 `/tmp/aps-r1-b.c3LzAl/browser/test_real_file_browser_{light_10,light_11,dark_190,dark_130}/round1-field-browser.json` 及 `template/preview/refreshed/duplicate.png`。JSON 含 45 份依赖源 SHA-256。
- 七个产品文件的定点 Pyright 1.1.406：0 error / 0 warning。扩到新增测试后发现 Optional worksheet 未收窄，已改为明确非空断言和枚举表头列号；未加 ignore/cast/Any 或改配置，最终 13 文件为 0 error / 0 warning。
- 最终源码及测试修正后合并 API + 四视口浏览器：**103 passed, 2 deselected in 126.52s**。逐项 JUnit 为 `/tmp/aps-r1-b.c3LzAl/final.xml`，最终四视口浏览器 JSON/下载 XLSX/截图在 `/tmp/aps-r1-b.c3LzAl/final/test_real_file_browser_*/`。所有测试进程及私有 HTTP 服务已正常结束。
- 本轮所有产品函数 Radon complexity <= 13，Python 3.8 grammar 检查通过；没有新增运行依赖。
- `.venv/bin/pyright` 脚本 shebang 指向失效旧路径，改用 `.venv/bin/python -m pyright` 执行现有环境，未改 launcher 或共享缓存。

最终实际命令（在仓库根执行）：

```bash
env PYTHONPYCACHEPREFIX=/tmp/aps-r1-b.c3LzAl/pycache PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest \
  tests/workbench/test_round1_field_piece_files.py \
  tests/workbench/test_round1_field_piece_files_codec.py \
  tests/workbench/test_round1_field_piece_files_contract.py \
  tests/workbench/test_round1_field_piece_files_browser.py \
  tests/workbench/test_field_files_api.py tests/workbench/test_field_files_codec.py \
  tests/workbench/test_field_workspace_api.py tests/workbench/test_piece_downstream_api.py \
  tests/workbench/test_actual_gantt_api.py tests/workbench/test_point_downstream_api.py \
  -k 'not capacity_exact and not 10000_operations' \
  --basetemp=/tmp/aps-r1-b.c3LzAl/final -o cache_dir=/tmp/aps-r1-b.c3LzAl/cache \
  --junitxml=/tmp/aps-r1-b.c3LzAl/final.xml -q
```

类型命令为同一隔离环境下 `.venv/bin/python -m pyright`，显式指定下面产品 hash 表中的七个 Python 文件及新增的六个 `test_round1_field_piece_files*.py` 文件，带 `--outputjson`，输出 `filesAnalyzed=13,errorCount=0,warningCount=0`。

## 当前产品源 SHA-256

| 文件 | SHA-256 |
| --- | --- |
| `field_report_files.py` | `19b46f51bf5e19479957fdbaefca0ece77de3570b14c0d1b029ac250e801c95f` |
| `field_report_files_codec.py` | `8720ab7be13c71ad4f2ef8e906509f88eb80c984875472f2b6bcc8ab9b2f418c` |
| `field_report_files_xml.py` | `e769ab37952d49ae77ccd02fd08e850faa92aaadd347e79e3882b78a7df6d86a` |
| `field_report_files_identity.py` | `73d12dbef5484473904df269009a18d803b7f17ac8f66dfde04a11a090b6caa2` |
| `actual_gantt_export.py` | `9646e949997ab9ef16f6e168e11100d6e05ac98d56a03ac903ac94f57f209c4b` |
| `actual_gantt_scope.py` | `dc4e4839aed247ca0769f0d6fa2c77859a5e159963fd574a81feefff88054bd6` |
| `field_workspace.py` | `a9ee2bfa9b1db0266fe81a0e45816dbf3e8bb39e251bf31c2f587bc584d270cd` |
| `frontend/workbench/app/FieldFiles.jsx` | `31dec4e2c03001e096fe13fa74da15d98197ad6ab6f55f8dcb861232cc8fac79` |

## 主线交接与未完成

- 已分三次交接文件契约、职责拆分及 Chrome 定点闭环，每次附路径、源 hash、命令、结果和未完成边界。
- 新增专属测试/探针采用 `tests/workbench/test_round1_field_piece_files*` 前缀；未扩大写集修改全局测试 registry，主线可按其整体门禁安排登记。
- 最终新增测试类型校验及合并回归已完成。授权 R1-B 范围内无未完成实施；完成交接后停止本轮，不进入下一轮或整站门禁。
- 所有验证均为已有大量 dirty 上的局部 proof，不是 clean-worktree/full-gate/全站验收证明。

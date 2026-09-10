---
doc_type: issue-fix-note
status: fixed
date: 2026-09-10
scope: R1-G first-round analytics and process typing
---

# R1-G 第一轮补漏记录

## 结论与范围

- 已消除原始 `stage-pyright.json` 指定的报表 10 项、工艺命令 1 项类型错误。
- `catalog_workspace` 按职责拆开，复杂度从 27 降至 14，未增加 allowlist。
- 经本轮追加授权，修复工作台五专题 XLSX 元数据标识被前置单引号的问题；只改 `report_exports.py`，未改共享导出 helper、随机令牌或原测试断言。
- 全部结论是当前 dirty 工作区的局部证据，不是 clean-worktree proof，不代表全仓类型检查或全站验收通过。

## 根因和修改

- `core/models/workbench_report.py:27`：分离成对日期验证，明确收窄起止日期后再解析；缺项、非法日期、逆序仍拒绝，未修改共享 `reject` helper。
- `core/services/workbench/report_catalog.py:36`：按真实分支建立 batch/resource collections，避免对 `None` 取资源集合；正式计划、identity、fingerprint 原合同不变。
- `core/services/workbench/report_catalog.py:68,79,95`：分别负责超期行、资源行转换、筛选分页和摘要装配，原始导出行按原身份映射保留；未排程、交期异常、计划时间异常和未知利用率没有被删除或补零。
- `core/services/workbench/review_legacy.py:16,27,47`：声明精确结果字段，按任务累计有效暂停区间，最新异常只比较已验证时间。非法时间、缺失事实、开放暂停保持未知，不修改或删除源事实，不重算完成率。
- `web/routes/workbench/reports.py:54`：仅当 `sort` 参数不存在时采用默认字段；显式空值或未知字段仍拒绝。
- `core/models/workbench_process_commands.py:79`：字典值域允许 `str/float/None`，保留 exact dict、字段、ref、有限数、no-bool 数值及零工时明确确认校验。
- `core/services/workbench/report_exports.py:51,84`：根因是共享安全转义会给 `-` 开头的真实 snapshot 加单引号。本地 XLSX 元数据仅对“计划引用/范围快照”使用 `WriteOnlyCell` 并明确 `data_type="s"`，保持原值且不生成公式；其他元数据、正文及 CSV 继续原转义。旧目录/正式复盘 XLSX 的领域 exporter 及其 prefix 合同未改。

## 测试证据

证据根目录：`/tmp/aps-r1g-9Ykwy3/`。测试使用 `.venv/bin/python`，实测为 macOS Python **3.8.10**。

- 初始复现：`pyright-before.json`，5 文件、11 errors、0 warnings。
- 工艺闭环：`process-tests.log`，138 passed、10 deselected，4.05s；工艺源和新测试 pyright 0 errors。
- 原报告/复盘/导出/point 首次回归：`report-tests.log`，87 passed、1 failed，34.92s。失败保留在 `test_report_export.py:28`，未以重跑或修改断言掩盖。
- 固定 `-`、`+`、`=`、`@`、中文标识，修前 `export-before-tests.log` 为 8 failed、7 passed；修后新用例与原报告/台账导出用例 `export-after-tests.log` 为 35 passed，14.91s。
- 固定标识用例分别覆盖 direct/stream 模式，读回 XLSX 值与 `data_type=s`，解包实际 worksheet XML 验证 `inlineStr` 及不存在公式节点。每个用例的 `identities.xlsx` 和 `metadata-sheet.xml` 在 `export-after-pytest/test_xlsx_identity_bytes_and_d*/`。
- 新独立分析合同覆盖参数、非法时间、未知暂停、原始行保留、真实 cohort/图表分母及实际 CSV/XLSX 内容。原报告、复盘、台账来源/更正历史和下游 point 用例均纳入最终回归。
- ReportAPI 源合同、point 公共合同及原工艺 stage API：`adapter-tests.log`，145 passed，130.43s；无浏览器，该原 API 文件含既有 2000/10000 边界用例，不是全仓长测或 5000 专项压测。
- 最终合并定向回归：`final-tests.log`，**287 passed、10 deselected，91.36s**；排除工艺命令文件中的 10000 规模用例。
- 最终类型检查：`final-pyright.json`，6 产品文件 + 3 新测试，**9 文件、0 errors、0 warnings**。
- `final-ruff.log`：全部检查通过。`final-quality.json`：9 文件 Python 3.8 AST 解析通过，6 产品文件按现有复杂度阈值 15 和行数门禁扫描，无命中；`catalog_workspace=14`。
- `final-sources.sha256`：最终源码指纹，回归结束后逐项 `shasum -a 256 -c` 均为 OK。

### 复现命令

以下环境前缀应用于每条 Python 验证命令：

```bash
env PYTHONPYCACHEPREFIX=/tmp/aps-r1g-9Ykwy3/pycache PYTHONDONTWRITEBYTECODE=1 \
  APS_DB_PATH=/tmp/aps-r1g-9Ykwy3/unused.db APS_LOG_DIR=/tmp/aps-r1g-9Ykwy3/logs \
  APS_BACKUP_DIR=/tmp/aps-r1g-9Ykwy3/backups APS_ENV=development \
  .venv/bin/python -m pytest \
  tests/workbench/test_round1_process_contract.py tests/workbench/test_process_stage_commands.py \
  tests/workbench/test_round1_analytics_contract.py tests/workbench/test_round1_report_export_contract.py \
  tests/workbench/test_report_read.py tests/workbench/test_report_boundaries.py \
  tests/workbench/test_report_export.py tests/workbench/test_report_execution_ledger_read.py \
  tests/workbench/test_report_execution_ledger_boundaries.py tests/workbench/test_report_execution_ledger_identity.py \
  tests/workbench/test_report_execution_ledger_export.py tests/workbench/test_point_downstream_api.py \
  tests/workbench/test_report_widgets.py::test_report_api -k 'not 10000' \
  --basetemp=/tmp/aps-r1g-9Ykwy3/final-pytest -o cache_dir=/tmp/aps-r1g-9Ykwy3/pytest-cache -q
```

类型检查用 `-m pyright --outputjson` 指定下面 9 个文件；ruff 用 `-m ruff check --no-cache` 指定相同文件。局部门禁通过现有 `tools.quality_gate_support.scan_complexity_entries/scan_oversize_entries` 传入 6 个产品文件，未改配置、阈值或登记表。原 `.venv/bin/pyright` 的 shebang 指向已失效的 `Documents/GitHub` 路径，故使用 `-m pyright`，没有修环境或清共享缓存。

## 最终源码 SHA-256

```text
e3d6713b74e562a031720f9cb832447c363b15f2f250b1b35f479d8ddff1289d  core/models/workbench_report.py
ac16b67a5052d89087775093c9bbf23a0a98ef874b082772298f10673be0912c  core/services/workbench/report_catalog.py
66947a8ec34fe7cecddfe58fbe7bfa34e99785ed76a56c96a1ee6ef0d83ce031  core/services/workbench/review_legacy.py
5a193ec2078190be5cf2bf82b2e62c225f5cda9c2ef14c678a8e9caa5ec28013  core/services/workbench/report_exports.py
bd004ceb272f1a9f8c441ca1725993a00a4cfb7b7e776f311952247e450b1e0c  web/routes/workbench/reports.py
0203990c09ea5fee2a4d182ac39fcd705e4af7f321c60eef6aca77a03d282e31  core/models/workbench_process_commands.py
73bc6db65690419f46c67f0869af32ca7f8829d4887065538e0a11c77ecbcad5  tests/workbench/test_round1_analytics_contract.py
1351f1c43c2d80b5e24741d0fafa8f37d8656b678b459502be4680d0bddceb53  tests/workbench/test_round1_process_contract.py
84eddcd4b3c6c5cbc3ba2b2ef0cd0c87149b6aa908225280f385acdd8c9103e9  tests/workbench/test_round1_report_export_contract.py
```

## 保留事项与停止边界

- 本轮修改前已保存六个产品文件的私有入场副本，原本均是已有 untracked 内容，未覆盖其他 dirty 改动。新增三个独立测试文件和本记录，全部未暂存、未提交。
- 入场及结束时 `git diff --cached --raw` 均只有 `tests/gate_meta/test_frozen_bundle_contract.py`，blob 前缀 `3a755494`；未操作该文件或暂存区。
- 未创建其他代理，未改 R1-D 的 execution adapter 或其他所有权文件；只在独立 `/tmp` callgraph 目录做定位。
- 未运行全仓质量门禁、全站验收、5000 专项压测、Win7 发布、旧 UI 下线、全局 build；未操作预览服务或生产数据库。
- R1-G 授权范围内无已知未完成项。整仓剩余问题和后续验收归主线；本轮到此停止。

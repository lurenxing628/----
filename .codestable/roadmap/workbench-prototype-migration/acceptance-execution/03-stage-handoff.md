# E 阶段交接：域接入已写入，全站验收未完成

## 结论与分母

- 分母固定为 69 个 WBP：execution 32、analytics 31、calibration 6；每条内部多操作仍须分别验证。当前不能写成 69 项通过。
- 产品额外授权的 caption 和只读 history snapshot 已接入 5 个域 Workspace；未修改公共 schema/DTO、factory、Main 主入口或共享 build-order。
- 最新完整构建仍被其他域的加载顺序阻断，10 个全站测试均停在 setup，尚未运行完整主入口 K/V。这是阶段交接，不是任务完成。

## 变更定位

- `frontend/workbench/app/FieldWorkspace.jsx:16` / `:22`：同真实 plan 的 caption；scope/page/size/已选 task/operation refs/原来源恢复。第 29/31 行修正显式刷新和保存后分页重读，写表单不进 history。
- `frontend/workbench/app/ActualGanttWorkspace.jsx:7` / `:78` / `:83`：校验并恢复只读视图、缩放和位置；caption 来自返回的计划，候选不冒充正式。
- `frontend/workbench/app/ReportWorkspace.jsx:21` / `:26`：报表和复盘共用一次真实身份发布，保存 scope/topic/table/selected/charts/catalog/scroll/returnTo。
- `frontend/workbench/app/ReviewWorkspace.jsx:3`：说明由共用 ReportWorkspace 发布，避免第二个 hook 覆盖。
- `frontend/workbench/app/CalibrationWorkspace.jsx:19` / `:83`：只读模板/样本选择恢复；没有计划身份，caption 传 null。
- 9 个既有域组件 probe 仅补两个共享 hook 文件的加载，完整列表见 `02-extra-changes.md`；没有删除断言。
- 新增 `final_execution_*` 私有构建、宿主、SQLite 原始行/HTTP/下载字节记录、浏览器动作驱动和 4 个 `test_final_execution_*.py` 测试入口。
- 30 个本分支新增/修改源码文件的当前 SHA-256 见 `stage-source-sha256.json`。该文件明确是运行后磁盘 hash，不冒充 clean HEAD proof。

## 已实际运行

统一环境：`.venv/bin/python` 3.8.10，`PYTHONDONTWRITEBYTECODE=1`，`PYTHONPYCACHEPREFIX` 和 pytest basetemp 均为本分支 `/tmp/aps-final-e-*`，`-m pyright`；没有升级依赖。

| 范围 | 实际命令/结果 | 原始证据 |
|---|---|---|
| 8 个原后端文件的新鲜定点回归 | `.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/workbench/test_round1_field_piece_files.py tests/workbench/test_field_files_api.py tests/workbench/test_field_files_codec.py tests/workbench/test_field_workspace_api.py tests/workbench/test_execution_ledger_commands.py tests/workbench/test_calibration_method.py tests/workbench/test_calibration_adoption_transactions.py tests/workbench/test_calibration_adoption_drift.py`，**113 passed / 18.88s** | `/tmp/aps-final-e-current-ui.AmcHM6/domain-01.xml` |
| 新 hook 无 Provider 的组件兼容 | `.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/workbench/test_round1_field_piece_files_browser.py`，**4 passed / 18.67s**，真实 Chrome 109、SQLite 和下载；只是独立组件兼容，不是全站验收 | `/tmp/aps-final-e-caption.1Z9dDb/component-01.xml` |
| 新真实 factory 组最近可执行运行 | `test_final_execution_backend.py` + `test_final_execution_calibration.py`，**6 passed / 1 failed / 33.84s**。包括严格写表、整道完成、原事实/回执、真实重启、离群值中位数、采纳锁、暂停/异常/来源撤回资格。失败为模板内另一个既有待补行被预填资源补齐；新测试现改为从真实下载文件只保留两个指定分件行，尚待重跑 | `/tmp/aps-final-e-resume.o4u6zI/backend-02.xml`，各 `aps-workbench-live-*/` 的 `server-final.json` 和业务前后快照 |
| 新测试类型检查 | `.venv/bin/python -B -m pyright tests/workbench/final_execution*.py tests/workbench/test_final_execution*.py`，**0 errors / 0 warnings** | 当前工具实际输出 |
| 新测试风格检查 | `.venv/bin/python -B -m ruff check tests/workbench/final_execution*.py tests/workbench/test_final_execution*.py`，**All checks passed** | 当前工具实际输出 |
| 新浏览器脚本语法 | `node --check` 分别检查 `final_execution_field.cjs`、`final_execution_actual.cjs`、`final_execution_calibration.cjs`、`final_execution_reports.cjs`，四次均 RC 0 | 当前工具实际输出 |

重启前后严格检查没有把日志表整体排除：允许且要求只新增 1 条 `plugins/load` 审计和对应 sqlite_sequence 增量，所有旧行与业务/计划/报工/修订/来源表保持不变。会过期的 `write_context` 与不可变报工事实分开，回执数据仍逐字段比对。

## 当前阻断与未完成

1. 最新完整构建错误为 `Script dependency must load earlier: workbench/app/ResourceWorkspace.js -> workbench/app/ProcessWorkspace.js`。实际源码调用在 `frontend/workbench/app/ResourceWorkspace.jsx:60`；当前共享 build-order 的 ResourceWorkspace 在第 19 行，ProcessWorkspace 在第 26 行。此处归 Main 协调，本分支未越域修改。
2. 完整命令 `.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/workbench/test_final_execution_backend.py tests/workbench/test_final_execution_calibration.py tests/workbench/test_final_execution_reports.py tests/workbench/test_final_execution_browser.py` 最近结果为 **10 setup errors / 19.81s**；原始 `full-01.xml`、`build-command.json` 在 `/tmp/aps-final-e-current-ui.AmcHM6/`。错误保持可见，未绕过构建检查。
3. 较早 `scrollX/scrollY` 构建错误已由 Main 修复；再后一个 `RunCandidateControls` 的 `M` 错误也已观察到其源码补了绑定。原失败文件未覆盖删除，不把提交钩子短暂 stash 的读源漂移判成产品故障。
4. 共享 freeze 后需重新建立新私有完整构建，执行全部新测试、真实侧栏/F5/后退、56 个五专题及四目录下载字节/SQL 核对、现场与校准写入/重启闭环；1920/1392 深浅完整主入口截图仍待产生并交 Main V。
5. 原型动作中现场 5 指标、草稿、甘特关联线/自动刻度、校准图号跳统一零件详情/表头筛选列宽等，有待实际浏览器核查的实现差额；目前只作风险线索，不把静态扫描当 K，不把未覆盖项改 N/A 或移出 69 分母。新脚本会记录差额并保持验收失败，未获 Main 额外授权前不改这些产品行为。
6. `test_final_execution_backend.py` / `calibration.py` / `reports.py` / `browser.py` 的统一门禁登记交 Main；不自行修改 test_registry 或把本地通过数当整仓门禁。

## 保留与进程

- 工作区 prior dirty 和本轮新增文件均保留；本分支无 `git add/commit/reset/checkout`、无清缓存、无删文件操作。最近只读检查 staged 为空；此前唯一 staged 的处理来自 Main 的 `c0097278` 提交，不是 E 操作。
- `source-RauBC6`、pre-retirement 完整归档、生产库、原 53144 / PID 73298 / `aps-workbench-live-l0tgvgp8` 均未由本分支操作。
- 本分支所有已启动进程已正常退出；最后 `pgrep` 未发现 `final_execution_host`、本域浏览器或对应 pytest 进程。现无持有的 heavy/host/browser，可在 Main 修复共享加载顺序后恢复同一任务。

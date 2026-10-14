---
doc_type: feature-quality-note
feature: decision-integration-acceptance
status: completed
created: 2026-10-14
summary: A非延期范围主验收通过，Gate09原失败保留，Windows及性能按用户决定后续收口
tags: [aps, quality-gate, content-comparison, win7]
---

## 最新验收范围

A第0—8非延期范围已通过主对话验收，最终正常同库实页原件为`evidence/decision-stage-acceptance/stage-08/final-cold-runtime/parent-review.json`。Gate09前16步通过，实际758收集／722通过／36跳过／0失败；第17步15条Windows启动器setup skip未核销，原manifest保持failed。Windows全按用户决定大改后统一测；性能4／6／8候选20k summary3.6246／4.6823／5.2835秒未达2秒，按用户明确选择交C收口，原范围与目标保留。源码和测试冻结，后续只整理交接与提交归属；Git由主对话执行。

以下保留已执行的共同合同、历次失败和修复事实；当前结论见本节及[交接](implementation-handoff.md)。

## 实施结果与共同契约

- 门禁、long gate、hooks、测试登记及治理扫描的实际 SHA 计算已移除；本地分卷交付移除额外 CRC32 清单。Git 已有 HEAD、tree、remote ref 和旧历史 SHA 值保留原值。
- `tools/long_gate_schema.py` 的 `canonical_content` 保存完整规范 JSON，`content_equal` 严格比较原内容，区分布尔、整数和浮点。`read_file_content` 对原字节作可逆 Base64 编码；完整字节参与比较，文件路径、成员、类型和存在状态继续绑定来源。
- shared proof/receipt 为 schema 4，完整 receipt JSON 作为 manifest index 的 `content`，以原 `run_id`、`command_index` 和路径绑定。输出保留既有 raw/normalized policy；raw 日志按原 CRLF 读取，normalized 输出继续执行原规范化规则。receipt 文件名使用既有命令序号及 slug。
- 长门禁缓存、fingerprint 和 collect 为版本 2，保存实际命令、源内容、公开环境和完整日志/输出；required 核销保留真实 nodeids、reports、组覆盖和失败/xfail 判断。runner 的共同 receipt 写入者把原 path/run/index 同时传给成功与失败缓存。
- 新 shared current/topic/manifest/log/receipt 输出进入 `evidence/QualityGate/v4/`；long gate 的 `.v2.success/.v2.failure`、`.v2` 日志与 summary、`collect_nodeids.v2.json` 另写。既有旧原件和第7阶段证据保持原路径与内容。旧只有摘要、缺原内容的缓存首次明确 miss；旧 proof 可读取历史，新增验证由新运行绑定。
- 敏感环境值在日志/receipt 落盘前脱敏；非空敏感 command env overlay 明确拒绝，只报告键名。源码包含当前敏感环境原值或已知运行令牌文件时，原内容缓存报告缺项；不保存失真的脱敏源码。`SECRET_KEY` 只记录存在状态，存在时相关跨进程成功/失败缓存均不复用，force 路径同样不写该缓存。

## 文件归属

- runner、daily 与交付：`scripts/run_quality_gate.py`、`scripts/run_daily_quality_gate.py`、`scripts/portable_delivery.py`。
- 共同协议、缓存与登记：`tools/quality_gate_shared.py`、`tools/quality_gate_support.py`、`tools/long_gate_schema.py`、`tools/long_gate_fingerprint.py`、`tools/long_gate_cache.py`、`tools/long_gate_collect.py`、`tools/long_gate_manifest.py`、`tools/long_gate_summary.py`、`tools/git_hook_cache.py`、`tools/test_registry.py`、`tools/test_debt_registry.py`、`tools/verify_required_regressions_from_full_test_debt.py`、`tools/architecture_scan_cache.py`。
- 治理扫描：`tools/quality_gate_scan.py`、`tools/quality_gate_operations.py`、`tools/quality_gate_ledger.py`、`tools/quality_gate_entries.py`。
- 针对性验证：`tools/host_tests/` 下4个文件共16个测试函数（原15项及本次1项真实CLI回归），无参数矩阵；现有 `tests/app_runtime/test_portable_delivery.py` 随撤销职责删除1个 CRC-only 测试，Path/Bytes 与恢复要求进入原真实交付用例。`test_registry_data.py` 和用户 README 改动由原 owner 保持。

## 当前台账的原文迁移

扫描新记录保存完整 `handler_signature` 与 `handler_context` AST 原文，新编号用 path/symbol/except ordinal。旧 ID、人工字段、两项历史 SHA、历史 realignment 字段和 accepted risk 引用保留；原文缺失或真实 handler 内容变化均阻止自动刷新和当前扫描验证。

显式 `scan-startup-baseline` 已改为按业务定位保旧 ID 与人工/历史字段。实施层已保存原台账副本并执行既有命令，当前原文基线共76条：75条旧记录、4条风险、9个风险引用完整保留；新增1条 `_run_idle_maintenance` 可观测降级。迁移前原件、命令输出及逐字段保留核对放在 `evidence/decision-integration-acceptance/2026-10-14/ledger-*`：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/sync_debt_ledger.py refresh --mode scan-startup-baseline
```

基线迁移保存当前真实原文，既有风险退出条件继续执行。

## 剩余脚本、CI与测试helper

按主对话`remaining-content-cleanup-instructions.md`，两个离线准备脚本、workflow和6份既有测试helper的主动密码哈希已移除并冻结。脚本继续核对固定来源、路径、尺寸、包身份及上游元数据原值；测试继续使用原冻结SQL和迁移前后业务/DDL原件，源码和非回执状态直接比较规范原内容。CI restore/save统一采用已有ref/commit/run身份，仓库内缓存有效性仍由现有shared v4/long v2比较完整原内容。

该组本地微型文件和替代网络入口验证通过，另2个既有甘特/外协节点通过。原工艺profile暴露单零件快照遗漏真实revision，查询在同一身份JOIN补齐后，原stage-scale(1)的14阶段、noop(1)的8阶段均通过。冻结SQL差异为0；真实工具下载、vendor重导入、新迁移矩阵和新增测试节点均为0。

主对话第6节追加Jev缓存裁定已实施并冻结：该宿主客户端由两份历史审计脚本调用，保留现有接口，按完整原请求JSON在`cache_dir/responses.sqlite`等值读写。旧摘要命名文件留原件；相同请求、不同状态/模型/问题、跨实例复用、用量、失败不写缓存及锁/事务边界的替代HTTP本地验证通过。真实API、凭证读取和历史审计执行均为0。

第7节原19份宿主脚本与5份必要直接消费者已完成并冻结，共24份。来源按原bytes及mode比较；快照按原类型化行JSON计数，7行/6组/重复2次的小样保留类型、浮点精度及列序；AST直接按既有规范原文分组；语料以完整nodeid/longrepr去重，沿用旧ID，新序号继续既有最大值。现有2项source_guard用例及临时内容行为检查通过，Python3.8/Node语法通过。build_corpus原有7项UP031保持原状态。24份均为ignored/untracked，Git提交需主对话按明确pathspec处理；未操作Git/index、历史main、旧输出或数据库。完整清单和残余调用核对在`source-regressions/archived-host-content-freeze.json`，主动密码学调用为0。

## 实际验证与证据边界

- 最新第九轮前16步通过，完整pytest为758收集／722通过／36跳过／0失败。第17步required核销因15条启动器setup:skipped未完成，原manifest保持failed。用户随后明确全部Windows相关验证延期至本轮大改完成后统一执行；临时PowerShell安装、12条宿主脚本补验、Windows原生补测和白名单／门槛变化均为0，旧失败与skip原件保持。
- 最终第6次同库冷启实际完成：58240／PID3143／session21032、Python3.8.10、Schema40、原正式Schedule15行，公开／合同身份完全一致，旧58549/PID18726正常shutdown202／exit0。3次受影响真实GET全部200：候选原永久身份及48道工序完整、受理正式基准available且真实4候选、历史原15条及选中run身份保持。原响应及核对在`operator-ui/final-runtime-reading/`；新增fixture／计算／采用／导出为0。3次GET后附带的未用运行表计数探针遇到不存在的WorkbenchRunRequests，保留此宿主错误；随后仅读实际SchemaVersion与Schedule及原响应保存 metadata，业务GET重跑0。
- 实际Chrome帮助URL为58240的`/scheduler/config/manual?page=analysis#排产记录`，当前记录顺序／原值圆点／实线和淡虚线／缺项／当次规模／完整记录键盘与对照职责全部可读，console为空。DOM、正文和截图在`operator-ui/final-help/`；Root亲读原文并目视锚点截图通过。大规模4／6／8候选summary的3.6246／4.6823／5.2835秒仍分别高于2秒目标，最终小库读取属于接线核对。

- 宿主15项集成用例已执行通过；覆盖原源码变化、严格类型判等、receipt/run/index/path/日志绑定、raw CRLF、SECRET_KEY 非复用、旧缓存原件保留、真实 required 核销及台账原文/永久 ID。
- 主属8个源码 targeted Pyright 为0 errors/warnings；Ruff通过；Python 3.8 AST + compile通过。两个子域另外完成其定向类型、语法和差异检查。
- 现有本地交付两个文件的9项用例第一次运行在 `tests/conftest.py` 的 factory setup 阶段遇到并行产品接线：`run_data_context.py` 仍导入已撤的 `system_journal.file_fingerprint`。该结果为9 errors、1平台 skip；宿主15项仍通过。产品 owner 完成接线并冻结后，用原命令重验 `tests/app_runtime/test_portable_delivery.py` 与 `tests/app_runtime/test_ready_portable_delivery.py`，最终9 passed、1 skipped，耗时0.32秒；skip 对应 Windows installer 平台项。
- 完整dirty Gate已执行三轮：attempt01在第4步Ruff的9处I001失败；仅导入排序修复后，attempt02在第5步检出两个未批准的硬目录环；按主对话`import-cycle-repair-instructions.md`迁移共同职责后，attempt03的Ruff、两次循环、Python3.8检查通过，第10步发现速查表漏列历史查询／导出及方案summary三条实际接口。三轮尚未进入产品全量pytest，失败原件分别保存于本feature的`full-gate/attempt01-v4/`、`attempt02-v4/`、`attempt03-v4/`。仅补齐三条接口文档后，attempt04的接口及防回归检查通过，第12步Pyright报告123错误／29路径，失败原件在attempt04-v4；产品全量pytest仍未执行，已按主对话type-contract-repair-instructions完成共同类型、HTTP参数、归档格式和精确整数算术修复；2个真实缺陷验证节点通过0.65秒，失败Pyright配置收敛为0 errors／0 warnings。第五次产品Pyright通过、第13步工具Pyright报同一组件字典读取的6项；按母新增第10节局部收窄后tools配置0错误／0警告，attempt05-v4失败原件保留。随后第六次在第15步发现既有台账行号漂移：按第11节只同步预览同一37个自动字段，12旧记录及其余内容保持，check通过，attempt06-v4保留。第七次前15步通过，第16步实际全量为758收集／716通过／36跳过／6失败（2个required＋4个候选债务分类），第17步尚未执行，attempt07-v4完整保留，当前仅读取失败根因。第三次到第10步终止，未执行Pyright。Git/index操作、实际产品打包及产品数据库写入均为0。

## Dirty 与 clean 的实际来源边界

第七轮6项失败随后按主对话 `full-test-fixture-repair-instructions.md` 精确修正4份原测试夹具，41个函数／178条断言与参数范围保持；原6节点定点6 passed／2.57秒。第八轮前15步通过，第16步完整全量为758收集／721通过／36跳过／1个required失败，原6项均普通通过。新失败发生于校准测试修正一条已退出当前正式计划的报工，`require_current` 返回 `plan_not_writable`；最近20条的同时间永久身份排序与夹具来源正在只读核对。第17步未执行，manifest为failed／tracked_drift_detected=false，完整原件保存 `full-gate/attempt08-v4/`；源修复和新测试执行等待主对话具体施工稿。全部8次原件保留，债务、基线与门槛变更为0。

主对话亲读后按新增第6节核定校准夹具修复：原单测试导入MAX_SAMPLES，使当前正式版拥有21条样本，只从当前版extra_reports选择未入最近20条的报工。原5个函数／28条断言／2个异常断言／装饰器保持；限定Ruff及实际Python3.8 AST通过，主代理独立原文差异核对仅3处。原单失败节点1 passed／0.73秒，产品／共享fixture／排序／随机生成／静态包均未改。随后接续原完整dirty Gate第九轮；原六项验证与全部失败原件保持。

第九轮实际前16步全部通过，全量758收集／722通过／36跳过／0失败，未登记失败和xfail为0；原7条已修复节点均普通通过。第17步核销实际returncode1：启动器12项因缺PowerShell运行时、3项因Windows原生进程/CMD未执行，当前nodeid＋posix白名单未登记这15项。manifest为failed／tracked_drift_detected=false，完整原件在 `full-gate/attempt09-v4/`。原文与根因在 `full-gate/type-repair/required-attempt09-runtime-diagnosis.json`；该结果说明完整全量通过及required运行条件缺口；Windows核销按用户决定延期，当前A验收覆盖其余已通过范围。五份测试改前原文AST独立核对206条断言／10条异常断言完全一致。当前没有修改平台规则、required登记或跳过名单。

新 v2 source 的只读核对覆盖当时137个 required 文件：137个完整原字节 rows，109 tracked、28 untracked，缺文件与原字节差异均为0。主层随后登记1份 ImportSource 契约，当前来源核对覆盖138个 required 文件及138个完整原字节 rows，109 tracked、29 untracked，缺文件与原字节差异仍为0。来源类别仅说明 Git/Filesystem 归属，不改变内容覆盖。

主层裁定后，dirty 预检只要求实际 required 文件存在；实际 collect 还必须出现每个 required 路径，缺任一个就失败。完整 pytest 的每个 required nodeid/reports、passed/已列的平台 skip、无 xfail 和组覆盖继续由原核销器检查。dirty 前后原内容、命令、receipt、输出和执行状态保持绑定。clean 预检默认仍要求 tracked/index，当前 HEAD 和结束干净状态继续执行；dirty 结果与成功缓存均不声明 clean/bound。

该职责边界复用原2项 runner/hook 宿主测试补充验证：untracked 文件可进入 dirty、clean 默认拒绝，文件缺失始终拒绝；实际 collect 缺路径失败、全部覆盖才进入核销。补充后2项通过，未新增函数或参数矩阵。

主层在整体源冻结后运行完整 dirty Gate：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --no-resume --no-long-gate-cache
```

现行完整dirty步骤全部成功时的定义为`exit 2`／`passed_but_unbound`／`full_command_plan_unbound`；本轮Gate09实际因Windows核销保持failed。当前A验收覆盖用户决定的非延期范围，Git提交与后续平台验证分别记录。

旧全量 pytest payload 可沿 `tools/check_full_test_debt.py:run_check_from_existing_payload` 重新核销实际 reports，required verifier 继续逐 nodeid 核销；当前源码、命令、环境与完整门禁绑定由新运行提供。已有第0—7阶段专项证据按其未变化的真实职责复用，实际产品对应源改变时重验受影响范围。


## 实际提交钩子入口修复

主对话真实commit在pre-commit阶段暴露`python tools/git_hook_checks.py`的导入路径错误：旧fallback先加载顶层git_hook_cache，新增的tools.long_gate_schema导入缺仓库根目录，Ruff和blocked hook均在导入时失败。原日志`evidence/decision-stage-acceptance/stage-08/a-git-preparation/commit.log`保留；此前产品与门禁结果按原职责复用。

已按type-contract-repair-instructions第12节修复宿主入口：标准库导入之后、项目导入之前建立唯一REPO_ROOT并加入sys.path，统一tools包导入，删除旧ImportError fallback及_daily_gate_module重复路径设置；其余函数AST保持。原host测试文件追加1条真实CLI回归，从临时cwd移除PYTHONPATH后以实际sys.executable及绝对路径调用--help，检查原两个子命令。原两项测试AST不变，新测试文件0。该host文件实际3 passed／0.15秒，两份源Ruff All checks passed。pre-commit配置、产品源码、全量／构建／冷启／Windows执行均无改动，Root未操作index。

结果与原工具输出在`evidence/decision-integration-acceptance/2026-10-14/commit-handoff/hook-entry-repair/`。主对话仅更新`tools/git_hook_checks.py`、原host测试、本quality note与交接四条明确路径，随后重试真实commit；本修复的定点通过与实际commit／push结果分别记录。

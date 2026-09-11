# 2026-07-19 全库 14 维度缺陷扫描终稿（full-defect-sweep-ultra）

## 背景与方法

- 与 debt-recheck-ultra（同日，语义债向）互补：本轮专扫此前未覆盖的缺陷维度——Windows 编码、日期时间边界、数值边界、SQL/事务、并发、资源泄漏、web 入参、Excel I/O、可变状态、日志卫生、性能热点、测试质量、常量漂移、启动链，共 14 维度。
- Workflow `full-defect-sweep-ultra`（runId wf_9e059127-195）：14 个维度专职探子（硬预算 grep-first）→ 按 file+行桶去重 → 每候选 2 名独立对抗核实（镜头A 危害链怀疑者 / 镜头B 裁决登记核对者）→ 分歧仲裁。61 agents / 68.8 分钟 / 0 失败。已裁决 90 条账本债与全部 by-design 裁决内嵌排除。
- 完整性批评家首跑返回空，已单独补跑，结论见文末补记。

## 终局结论

**确认 17 条（0 high / 4 med / 13 low），驳回 4 条，未核实 0。** 各维度产出（找到/确认）：encoding-io 2/2、datetime-edges 2/1、numeric-edges 1/0、sql-tx 0/0、concurrency 1/1、resource-leak 0/0、web-input 1/1、excel-io 4/4、mutable-state 1/1、logging-hygiene 3/2、perf-hotspots 1/1、test-quality 2/1、config-drift 1/0、plugin-app 3/3。sql-tx 与 resource-leak 零产出（批评家复核见补记）。

## 确认清单（按严重度排序）

### D01 [med] [datetime-edges] core/algorithm_contracts/date_parsers.py:46-50

**due_exclusive 对交期 9999-12-31 做 +1 天溢出:整个排产评估/逾期报表 OverflowError 崩溃**

- 危害链：工厂 ERP 导出里常用 9999-12-31 当"无交期"哨兵值。用户 Excel 导入或 Web 编辑批次交期填 9999-12-31 → 校验全部放行入库 → 下一次排产跑到 evaluation._record_tardiness_if_overdue 或逾期报表跑到 compute_overdue_bucket_groups 时,due_exclusive 抛 OverflowError('date value out of range') → 整次排产评估/逾期看板/延误诊断整体崩溃,而且报错信息完全不指向那一行交期数据,用户无法自查。注意:这不是账本已锁的 None→datetime.max 契约语义,而是真实日期 +timedelta 溢出的新路径(账本明示该类新路径可报)。两份实现(date_parsers.py 与 overdue_calculations.py)同病,修一处不够。
- 证据：core/algorithm_contracts/date_parsers.py:46-50:
def due_exclusive(d: Optional[date]) -> datetime:
    if not d:
        return datetime.max
    return datetime(d.year, d.month, d.day, 0, 0, 0) + timedelta(days=1)
同型第二份实现 core/services/common/overdue_calculations.py:21-28 同样 `datetime(due_date.year, ..., due_date.day) + timedelta(days=1)`。当 d == date(9999,12,31) 时 datetime.max 再 +1 天直接 OverflowError。上游放行链已核实:Excel 导入 _normalize_batch_cell(core/services/common/excel_validators.py:76-84)用 r'^(\d{4})[/-]...' 接受任意 4 位年份,datetime(9999,12,31) 构造合法即通过;Web 编辑 batch_service._normalize_date(core/services
- 核实结论（双镜头）：A:维持成立,severity=med 恰当。全链实证:(1) 代码事实准确——date_parsers.py:46-49 与 overdue_calculations.py:21-28 两份 due_exclusive 均为 datetime(y,m,d)+timedelta(days=1),实跑对 9999-12-31 均抛 OverflowError('date value out of range')。(2) 上游无守卫——实跑 excel_validators._normalize_batch_date_cell('9999-12-31')返回 error=None 放行;batch_service.py:91 strptime 同样放行;全仓 grep 无年份上限或 9999 哨兵处理。(3) 下游无兜底——evaluation.py 三处 except OverflowError(:69/:313/:331)只包 float()转换且 re-raise,不覆盖此路径。(4) 爆炸半径比候选还宽:symbol_locator 确认 due_exclusive 共 6 个调用方,除候选列的 evaluation.py:253、ortools_bottleneck.py:137、overdue_calculations.py:104(→逾期看板/延误诊断)外,还有 dispatch_rules.py:53 build_dispatch_key(经 sgs_scoring.py:34-59 parse_date 解析后传入真 date)和 optimizer_neighborhood_move_support.py:61/:90——即 SGS 派工打分环节排产本体直接崩,不只事后评估。(5) 不升 high 的理由:触发值精确到唯一一天 9999-12-31(9999-01-01/2999-12-31 均不溢出),fail-loud 崩溃无静默错排,数据修正后可恢复;但该值是 ERP 常见'无交期'哨兵、报错完全不指向问题批次、单机离线用户无法自查,故 med 不

### D02 [med] [encoding-io] web/bootstrap/launcher_processes.py:114-119

**PowerShell 查询进程路径按 UTF-8+errors=ignore 解码,Win7 PS2.0 下中文安装路径会被静默吞字导致运行时身份误判**

- 危害链：输入/状态:APS 安装在含中文的路径(如 D:\排产系统\)且运行在交付目标 Win7 自带 PowerShell 2.0/.NET 3.5 上——脚本内改 [Console]::OutputEncoding 让 powershell 自身管道输出转 UTF-8 是 PS3+/.NET4.5 时代的技巧,PS2.0 上不可靠;若实际按 OEM cp936 输出,GBK 字节被按 UTF-8 解码且 errors="ignore" 把中文段静默丢掉→normcase/abspath 比较必然不等→pid_match=False。错误结果:(a) launcher_contracts.py:156 把本方仍在运行的锁判为非活跃→破锁重启,第二个运行时实例对着同一个 SQLite 库写;(b) launcher_stop.py:376 停止流程报 pid_mismatch 拒绝强杀,用户停不掉服务。全程 errors="ignore" 无任何留痕,违反项目'不吞错要留可查原因'原则。纯 ASCII 安装路径不受影响,PS2.0 具体行为未在真机验证,故定 med 而非 high。
- 证据：launcher_processes.py:114-119 `subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, encoding="utf-8", errors="ignore", ...)`;其唯一输出非 ASCII 内容的调用方是 _query_process_executable_path(143-161),脚本靠 158 行 `[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;` 再 `Write-Output $path` 输出 exe 完整路径。对比同文件 launcher_chrome.py 的 PID 查询只输出纯数字天然免疫,这里输出的是路径本身。消费端:launcher_contracts.py:155-157 `pid_match = _pid_matches_contract(pid, exe_path); if pid_match is False: return False`(把锁判为非活跃);launcher_stop.py:369 强杀门要求 `pid_match is True`,:376-377 `if status.get("pid_mat
- 核实结论（双镜头）：A:核实成立,维持 med。代码事实全部准确:launcher_processes.py:114-122 确为 encoding="utf-8"+errors="ignore";158-159 行靠 [Console]::OutputEncoding=UTF8 后 Write-Output 输出 exe 路径;消费端 launcher_contracts.py:155-157(False→锁判非活跃)、launcher_stop.py:369/376-377(强杀门/pid_mismatch)行号无误。危害链无上游护栏:acquire_runtime_lock(launcher_contracts.py:239-254)判非活跃后直接 _remove_stale_runtime_lock 破锁,第二实例写同一 SQLite;锁文件 expected 侧是 Python UTF-8 无损往返(launcher_contracts.py:180-183),actual 侧是唯一有损通道,误判必然发生;全 bootstrap 无 ASCII 路径校验、无 PS 版本门,rc==0 时零日志零留痕,违反项目 fail-loud 原则;且脚本 147-155 行 Get-WmiObject 回退证明 PS2.0 是有意支持目标。唯一弱环是 PS2.0 具体行为未真机验证:若赋值抛 IOException(PS2.0 重定向下已知可能)则 rc=1→pid_match=None 落安全侧(但 Win7 上强杀门 :369 永久无法满足,连纯 ASCII 路径也丧失强杀能力,属附带可用性缺陷);若赋值静默无效则 cp936 按 UTF-8+ignore 吞中文,双实例危害成立。Win7 是 AGENTS.md 明文交付硬约束+中文安装路径对中文产品现实,故不降 low;决定性一环未实证且可能落安全失败模式,故不升 high。 | B:逐项核实后确认这是未登记、未裁决的新问题。(1) 账本核对:docs/_panorama_data/debt_status_2026-07-19.jso

### D03 [med] [mutable-state] core/services/scheduler/gantt_critical_chain_provider.py:32-34

**GanttCriticalChainProvider 类级缓存无任何生产侧失效路径,数据回滚/同版本行变更后长驻进程持续返回旧关键链**

- 危害链：版本号由 ScheduleHistory max(version)+1 分配(schedule_service.py:242、schedule_orchestrator.py:402/413)。长驻 web 进程内:用户先查看过 version N 的甘特关键链(缓存写入 available=True 的结果)→ 之后通过备份恢复(core/infrastructure/backup.py)把数据库回滚到更早状态并重新排产,新计划复用同一 version N(max+1 在回滚后回退)且 db 文件路径不变 → 再打开甘特关键链时缓存 key 完全相同,直接命中并返回恢复前旧计划的关键链(ids/edges 全是旧行),页面展示的关键链与当前采纳计划的工序不一致,且 cache_hit=True 会一直命中直到 LRU 挤出或进程重启。candidate/scenario 行若存在同 id 重写路径同样命中此陷阱。备注:若备份恢复流程强制重启进程则危害不成立,需核实员确认恢复是否在进程内完成;账本 90 条债未逐条比对,请把关是否已立案。
- 证据：L32-34: `_CRITICAL_CHAIN_CACHE: OrderedDictType[Tuple[Any, ...], Dict[str, Any]] = OrderedDict()` 定义在类上(跨实例、跨连接共享,进程生命周期存活);L51-55 提供 `clear_cache()`,但 grep 全 core/ 与 web/ 仅 gantt_service.py:12/79/81 引用该类,`clear_cache` 无任何生产调用方。缓存 key(L97-105)只含 (db文件路径, version, role, source_table, candidate_id, scenario_id),不含任何数据版本指纹;L129-136 命中即直接返回 `cache_hit=True` 的副本。且 `_database_scope()`(L67-77)在 PRAGMA 失败或 :memory: 时回退 `str(id(self.conn))`,id 可被 GC 复用。
- 核实结论（双镜头）：A:维持成立(镜头A未能驳倒)。代码事实全部核实:类级缓存(gantt_critical_chain_provider.py:32-34)、clear_cache 仅测试调用零生产调用方、key(L97-105)无数据指纹、命中即返 cache_hit=True(L129-136)。危害链逐环可达:(a) 恢复是进程内完成——web/routes/system_backup.py:319-374 只关 g.db、restore 同一 DATABASE_PATH、ensure_schema 后 redirect,无重启、无任何缓存失效;(b) 生产路径确认——request_services.py:172 每请求建 GanttService,gantt_service.py:353 默认甘特视图走该 provider,类级缓存跨请求存活;(c) 版本复用一环需修正但结论不变:实际用 allocate_next_version(schedule_history_repo.py:56-100, ScheduleVersionSeq AUTOINCREMENT,注释明言'保证不会复用'),但该序列表在同一 db 文件内,文件级 restore 连同序列回滚,回滚后重排必复用 version N——恢复静默击穿了文档化的不复用保证,反而加重问题(候选引 schedule_service.py:242 的 max+1 只是过时 docstring)。触发是现实操作序列(看关键链→应用内一键恢复→重排→再看关键链),非纯理论;衰减因素仅为需进程不重启且未被 LRU 64 挤出。severity 维持 med:危害限于展示层关键链与当前计划错位并持续命中,可误导排产关注点、违背可复现可追溯,但不污染落库数据,重启即消。次要修正:id(self.conn) GC 复用一点纯理论(生产 sqlite 连接 PRAGMA 必返回路径),不构成主链。 | B:代码事实全部属实:类级缓存(gantt_critical_chain_provider.py:32-34)无数据版本指纹,clear_c

### D04 [med] [plugin-app] web/bootstrap/entrypoint.py:218-249

**单实例运行时锁在 create_app 全量 DB 副作用之后才获取：双开时会在运行实例底下执行 schema 迁移**

- 危害链：实例 A（旧版本）正在运行时，用户双击启动新版本 exe（升级后未先退出旧实例的常见操作）→ 实例 B 在锁检查之前就对共享 aps.db 执行 ensure_schema 迁移（ALTER TABLE/数据清洗），随后才因锁被占返回 13 退出 → A 继续用旧代码在已迁移的新 schema 上读写：轻则 SQL OperationalError 让排产/录入功能当场报错，重则旧代码按旧语义写入新结构，把语义错误的行写进正式业务库且无审计告警。同版本双开时 B 也会绕过单实例约束向共享库写 plugins load 操作日志。
- 证据：entrypoint.py app_main 顺序：218-224 先 `app = deps.create_app()`（内部 factory.py:329-334 `ensure_schema(...)` 会走 migrate_with_backup 做 ALTER/数据清洗，factory.py:336-340 `bootstrap_plugins(...)` 向共享库写操作日志），234-249 之后才调 `_own_runtime_resources` → entrypoint.py:308-319 `deps.acquire_runtime_lock(...)` 失败 return 13。而锁所需的 lock_scope_target/lock_scope_log_dir/runtime_owner 在 200-207 行、create_app 之前就已全部就绪，锁并非必须后置。
- 核实结论（双镜头）：A:成立，维持 med。核实结果：(1) 行号与事实全部准确——entrypoint.py:218-224 先 create_app，锁在 entrypoint.py:308-319（经 234-249 的 _own_runtime_resources）才获取，而锁所需输入在 200-207 已就绪；factory.py:329-334 的 ensure_schema 在 database.py:232-250 会对共享 aps.db 执行 _migrate_with_backup，且迁移确实含破坏性操作：ALTER TABLE ADD COLUMN（migrations/v14.py:21）、数据清洗 UPDATE（v1.py:83-163、v5.py、v8.py）、整表重建 RENAME+DROP（v18.py:35-38）；factory.py:336-340 的 bootstrap_plugins 在 plugins.py:252-261 向共享库写操作日志行。(2) 危害链无上游拦截——app.py:64 与 app_new_ui.py:17 直达 app_main，启动路径无任何实例探测（probe_runtime_health 只用于 stop 路径）；唯一版本守卫 _ensure_schema_version_not_newer（database.py:206/215）只挡降级方向，升级方向（新 exe 在旧实例运行中迁移库）无守卫。(3) 触发条件现实——单机桌面场景双击双开是锁存在的设计动机本身，升级未先退旧实例是常见操作；且加重项：锁失败文案（launcher_contracts.py:210-214）"请直接使用现有窗口"会主动引导用户继续用旧实例 A 在已迁移 schema 上操作。(4) severity 不虚高但也不升 high：_migrate_with_backup 迁移前有备份可回滚、多数迁移是加列型、需要"版本升级+旧实例在跑"复合条件，单机单用户爆炸半径有限；但 v18 式整表重建+数据清洗可让旧代码静默写出语义错误行且无审计告警

### D05 [low] [concurrency] web/bootstrap/static_versioning.py:83-87

**静态资源版本缓存跨两个 dict 的 check-then-act 竞态，threaded=True 下可返回空/陈旧版本号**

- 危害链：危害链:线程A首次(或文件更新后)解析某静态文件版本，执行完 86 行、尚未执行 87 行时，线程B进入:83 行 mtime_cache 已命中新 mtime → 84 行读 version_cache——首个填充窗口读到 ""(该页面所有静态 URL 不带 ?v=)，热更新窗口读到旧版本串(?v=旧mtime)。配合长 max-age 缓存策略，用户浏览器在这次响应里会继续用升级前缓存的旧 JS/CSS，页面表现为脚本与后端接口不匹配(样式错乱/前端报错)，直到下一次刷新才自愈。修法:把 87 行写到 86 行之前，或加一把小锁/单 dict 存 (mtime, ver) 元组。
- 证据：build_versioned_url_for 闭包里的两个共享 dict(57-58 行 mtime_cache/version_cache)被所有请求线程无锁共用；_mtime_version 内:
83:        if mtime_cache.get(cache_key) == mtime:
84:            return version_cache.get(cache_key, "")
85:        ver = str(mtime)
86:        mtime_cache[cache_key] = mtime
87:        version_cache[cache_key] = ver
先写 mtime_cache 再写 version_cache，两写之间无锁；服务器为 make_server(..., threaded=True)(web/bootstrap/factory.py:178)，该闭包经 install_versioned_url_for 装进 jinja 全局 url_for(static_versioning.py:103-110)，每个页面渲染都会并发进来。
- 核实结论（双镜头）：A:代码事实全部核实无误:static_versioning.py:57-58 双共享 dict、83-87 先写 mtime_cache 后写 version_cache 且无锁,factory.py:178 threaded=True,factory.py:300 max-age=43200s,生产未配 fixed_version 故 mtime 路径生效。竞态本身真实存在。但危害链两条分支一实一断:(A)首次填充窗口读到 "" 可达,但 "" 是本模块设计内降级值(OSError 路径 80-82 行返回同值,91-96 行对 "" 即发原始 URL),裸 URL 内容正确、用户无感;(B)候选主危害"热更新后发旧 ?v= 导致浏览器用旧 JS/CSS"要求静态文件 mtime 在服务运行期变化——全仓无运行时写 static 目录的代码,离线打包交付模型下升级=替换+重启(内存缓存随进程清空),生产不可达;仅剩开发者手改文件的 dev 场景,窗口为两条字节码之间的微秒级、下次渲染自愈,且叠加在 mtime 方案固有 HTTP 级 TOCTOU 之上(边际危害趋近零)。维持 low 且属 low 的下限:值得修(交换 86/87 行或存 (mtime,ver) 元组,一行修复),但无生产用户可见危害。 | B:未命中任何裁决或登记:账本 debt_status_2026-07-19.json 无 static_versioning/并发相关条目;.codestable/audits/2026-06-09-backend-redundant-work/REPORT.md:639 的 finding #58 虽在同一函数但立案的是重复 stat I/O(相邻形态,不算命中);tests/web_pages/test_static_versioning.py 三个用例只锁 warn-once/注入失败不崩/fail-loud,未锁两 dict 写序;源文件无 by-design 护栏注释;不属于 P4/P5/P6 已扫专项(concurrency 维度)。代码事实属实:

### D06 [low] [encoding-io] web/routes/system_runtime_logs.py:152

**诊断包失败兜底 arcname 用中文文件名,Win7 资源管理器解压显示乱码,'包内明示缺失'的设计意图在目标平台失效**

- 危害链：输入/状态:Win7 用户导出诊断包后用系统自带资源管理器/压缩文件夹打开(Win7 Explorer 不识别 zip EFS UTF-8 标志,按本地 cp936 解码条目名)。错误结果:UTF-8 字节 '读取失败' 被按 GBK 解读,文件名显示为 '操作日志_璇诲彇澶辫触.txt' 一类乱码;这个文件名恰恰是设计上唯一向用户明示'操作日志缺失'的信号(注释 143-144 行:缺失必须在包内明示),乱码后信号失效,用户/售后误以为包损坏或看不出缺了什么。文件内容本身仍可解出,故 low。
- 证据：system_runtime_logs.py:149-153 操作日志读取失败时返回 arcname `"operation_logs_读取失败.txt"`(成功路径是纯 ASCII "operation_logs.txt");core/services/system/runtime_log_reader.py:238 `zf.writestr(operation_logs_arcname, operation_logs_text)`——Python zipfile 对非 ASCII 条目名按 UTF-8 编码并置 EFS 标志位。
- 核实结论（双镜头）：A:核实成立。代码事实全部准确：web/routes/system_runtime_logs.py:152 失败路径返回中文 arcname "operation_logs_读取失败.txt"（成功路径 :169 为纯 ASCII），core/services/system/runtime_log_reader.py:238 zf.writestr 直写该名；本机实测 zipfile.ZipInfo._encodeFilenameFlags 对非 ASCII 名走 UTF-8+EFS(0x800)，且 '读取失败'.encode('utf-8').decode('gbk') 正是候选所称的 '璇诲彇澶辫触'。危害链无上游拦截：arcname 是 :147 裸 except Exception 分支里的字面量，不经任何编码校验；Win7 zipfldr 不识别 EFS 标志按 cp936 解码是已知平台行为，而 AGENTS.md 硬约束目标平台恰为 Win7 x64，触发条件（操作日志读取失败+Win7 自带解压）现实可达且与排障场景强相关。severity 维持 low 不虚高：ASCII 前缀 operation_logs_ 乱码后仍存且与成功名可辨、说明文本内容可解出、:148 logger.error 把失败写入随包附带的应用日志形成冗余线索，信号是降级而非全灭。附注：该中文 arcname 被 tests/web_pages/test_diagnostic_package_security.py:141,144 锁为合同，修复（改纯 ASCII 名如 operation_logs_READ_FAILED.txt）需同步改测试。 | B:未登记未裁决的新问题:债账本(debt_status_2026-07-19.json)与 .codestable/audits|issues|refactors 对该 arcname 均零命中;system_runtime_logs.py:143-144 注释与 test_diagnostic_package_security.

### D07 [low] [excel-io] core/services/process/unit_excel/parser.py:63

**默认读 wb.active 而非第一个 Sheet，与脚本承诺不符，可静默解析错误工作表**

- 危害链：用户的产品数据.xlsx 含多个 sheet（如附带说明页/汇总页），上次保存时停留在非数据页 → 不带 --sheet 运行转换 → 解析到错误 sheet，station 表头识别为空、parts 为空或垃圾 → 输出的三份导入模板为空/残缺，但 CLI 报"转换完成" → 用户拿空模板去导入，主数据缺失且无任何报错留痕
- 证据：parser.py:63 `ws = wb[sheet_name] if sheet_name else wb.active`；而 scripts/convert_rotary_shell_unit_excel.py:93 的 --sheet 帮助文本承诺"默认读取第一个 Sheet"。openpyxl 的 wb.active 返回的是文件上次保存时的活动标签页（workbookView activeTab），不是第一个 sheet。下游 template_builder.build(parser.py 调用链 unit_excel_converter.py:27-28)对 parts/stations 为空无任何 raise 守卫（template_builder.py:55 起无空输入检查），脚本 111 行仍打印"转换完成。"
- 核实结论（双镜头）：A:成立但降级。代码事实全部核实无误：parser.py:63 确用 wb.active；脚本 convert_rotary_shell_unit_excel.py:93 帮助文本承诺"默认读取第一个 Sheet"与实现不符；openpyxl wb.active 返回保存时活动标签页已本机实测证实（多 sheet 文件停在说明页时读到说明页）。危害链前段真实可达：唯一生产调用方就是该 CLI 脚本（无 web 导入 strict 校验兜底），template_builder.py:55 build() 对空 parts/stations 无任何守卫，exporter.py:13-21 对 0 行照写表头文件，脚本 111 行 diag_total==0 时打印"转换完成。"——错 sheet 下 diagnostics 恰为空，假成功坐实；且 tests/excel_data_io/ 无任何多 sheet 用例锁定契约。但 severity 从 med 降为 low，因最后一环"主数据缺失且无任何报错留痕"高估：错误 sheet 需第 9 列起 4 列步进的设备表头才产出 station，说明页/汇总页几乎必然退化为全空产物，而空模板是自暴露的——APS 导入走预览确认流程（excel_service.py:251-253），空模板预览显示 0 变更，导入后系统无零件可用，缺失会快速显形而非静默腐蚀；"垃圾数据通过导入"变体需错误 sheet 恰具设备表头结构，属纯理论。修复价值仍在（违反本仓 fail-loud 原则）：改用 wb.worksheets[0] 并在 stations/parts 全空时 raise。 | B:未命中任何已裁决/已登记项：账本中 unit_excel 仅有 U02（parser.py:268-282 路线解析，已修复），与本候选 parser.py:63 sheet 选择是不同位置不同形态；2026-07-19 debt-recheck-ultra 审计的 U 系列与驳回清单均无 sheet 选择裁决；无护栏注释；tests 中 wb.a

### D08 [low] [excel-io] core/services/process/unit_excel/parser.py:253-256

**工序号单元格被 Excel 自动转成日期后，_parse_step_seq_detail 静默把年份前 3 位当工序号**

- 危害链：工序号"10-1"（正是该格式的规范写法 XX-X）在源 Excel 中被 Excel 自动转成日期 datetime(2026,10,1) → data_only 读回 datetime → 解析成 seq=202 且 has_step_code=False，无任何诊断 → 该工序被误判为外协（脚本口径：仅"有工步(XX-X)+有人员"判内部），工序号也从 10 变成 202 → 错误工序号和错误内外协分类写进零件工序工时.xlsx 转换输出，随导入进入正式排产主数据。同根问题：part_no 列(parser.py:95)若被 Excel 日期化/科学计数法化也会静默产出"2026-03-10 00:00:00"式垃圾零件号
- 证据：parser.py:328-333 `_to_text` 对 datetime 直接 str(v).strip() 无类型防护，得到"2026-10-01 00:00:00"；parser.py:240 `re.match(r"^(\d{1,3})-([0-9A-Za-z]+)", s)` 因年份 4 位无法匹配带工步分支；parser.py:253-256 `m2 = re.match(r"^(\d{1,3})", s)` 匹配到"202"成功返回 `int(m2.group(1)), False, None`——seq=202、has_step_code=False 且第三个返回值 None 即零诊断
- 核实结论（双镜头）：A:代码事实全部核实成立(parser.py:328-333 _to_text 对 datetime 无防护、parser.py:240 四位年份不匹配带工步分支、parser.py:253-256 截 "202" 返回 seq=202/has_step_code=False/None)，且上游无拦截(唯一入口 scripts/convert_rotary_shell_unit_excel.py:104-105 直接 convert，parse 前无任何校验)。但候选的危害链有两环夸大：(1)"零诊断"不实——builder_diagnostics.py:42-65 record_compatible_row_diagnostic 对 has_step_code=False 的记录必落一条 compatible_row 诊断，sample 含可见的 "2026-10-01 00:00:00" step_text，脚本会打印兼容行数与样本(仅措辞良性、样本限前3条，可视性弱但非零)；(2)"错误工序号202写进输出"不实——template_builder.py:168-170 _all_seqs 只取 route_map∪internal_seq_set，seq=202 两边都进不去，202 不会出现在任何输出表；真实危害窄于所述：原工序10的记录挂到202桶失联，工序10被误判外协且工时丢失。触发条件偏理论：真实源文件 templates_excel/回转壳体单元产品数据.xlsx 全部 1850 个工步单元格中 datetime 为 0、裸 "XX-X" 写法为 0，实际惯例是"10-1铣端面"式码+中文描述连写，中文存在使 Excel 不会日期化；需未来有人敲入纯"10-1"才可能触发。缺陷本身真实(datetime 无类型防护+截断式 fallback 正则是手编 Excel 摄入路径的真隐患)，但触发无实证、危害窄于所述、且有(弱)诊断通道，severity 从 med 下调为 low。 | B:未登记未裁决的新问题。账本仅有 U02(parser.py:26

### D09 [low] [excel-io] core/services/process/unit_excel/parser.py:166-179

**_build_station_columns 表头为空或识别失败时整台设备列块静默丢弃，无诊断留痕**

- 危害链：站位表头是合并单元格且锚点（top-left）不在 4 列块首格，或有人在站位区前插入了一列导致 idx=8 步长 4 的固定布局错位 → values_only 读到 None/错位文本 → 该设备（乃至其后所有设备）的整块工步+换型/单件/批次工时数据被静默丢弃 → 转换输出缺整台设备的工序工时，CLI 诊断汇总为 0、报"转换完成" → 缺失的工时进入导入链后排产产能凭空少一台设备。与已修的路线解析静默吃数据(#2)不同位置：那次只给 route 段加了诊断，站位列块丢弃仍零留痕
- 证据：parser.py:167-179 `raw_header = self._to_text(headers[idx]); if raw_header: ... if machine_id: stations.append(...)` —— raw_header 为空或 machine_id 为空时直接 idx += 4 跳过，函数无 diagnostics 参数，也没有"丢弃列块"计数；对比同文件路线解析(_parse_route_map:279-290)每个丢弃片段都有 route_segment_dropped 诊断
- 核实结论（双镜头）：A:核心缺陷成立但危害链两环被驳倒、severity 由 med 降为 low。成立部分：parser.py:163-180 确实在 raw_header/machine_id 为空时静默跳过整个 4 列站位块，无诊断参数、无丢弃计数，违反同文件 parser.py:52-53 明示的"丢弃必须留痕"约定；全链无守卫（parse() 无表头校验、unit_excel_converter.py:26-28 与 scripts/convert_rotary_shell_unit_excel.py:104-111 均无 stations 空检查、无测试锁该行为）。被驳倒的两环：(1) "CLI 诊断汇总为 0、报转换完成"不成立——被丢站位的 seq 仍在 route_map，经 template_builder.py:221-227 落为外协工序，必然触发 route_sheet_builder.py:92-127 的 default_filled 诊断（每个供应商行 2-3 条），CLI 实际打"转换完成（带退化成功）"且计数非零；真实问题是诊断不可归因（与正常外协默认补齐噪声无法区分），不是零留痕。(2) "乃至其后所有设备"不成立——idx+=4 无条件推进，空表头只丢当前块；插列错位场景实测会经 _extract_machine_id(parser.py:206-215) 兜底把'批次加工时间'等子表头造成垃圾站位并伴随大量 invalid_number 诊断，是吵闹垃圾而非静默丢弃。触发现实性收窄：实测仓内真实源文件表头行无合并单元格、7 个站位块首格均有效，当前文件解析正常且有输出合同测试；触发需未来手工维护漂移（块首表头留空但数据仍填）。危害形态修正：数据非纯缺失而是误分类为外协+伪造 1.0 天周期、设备/操作工从对应模板消失，导入链当合法配置接受；但这是受监督的一次性转换 CLI，下游有人工导入预览可见设备缺失。建议修复：给 _build_station_columns 加与 route_segment_dropped 同款的 station_column

### D10 [low] [excel-io] scripts/convert_rotary_shell_unit_excel.py:105

**--sheet 指定不存在的 sheet 名时抛裸 KeyError 英文 traceback，脚本无捕获**

- 危害链：操作员 --sheet 参数打错一个字（如中文 sheet 名少个字/多个空格）→ 直接倒出英文 traceback 而非"错误：Sheet 'X' 不存在，可用 Sheet：..."的中文提示 → 与同脚本对文件不存在的友好中文报错(101 行)不一致，现场操作员无法自助排错
- 证据：script:105 `converted = converter.convert(input_path=input_path, sheet_name=args.sheet_name)` 无 try/except（唯一的输入校验是 100-102 行的文件存在检查）；parser.py:63 `wb[sheet_name]` 对不存在的名字抛 openpyxl 的 KeyError('Worksheet ... does not exist.')
- 核实结论（双镜头）：A:维持成立。事实全部核实：script:105 无 try/except（唯一校验是 100-102 行文件存在检查，中文报错+return 2）；convert 链路 unit_excel_converter.py:26-28 → parser.py:63 `wb[sheet_name]` 全程无 sheet 名校验；实测 openpyxl 对不存在的名字抛 KeyError('Worksheet ... does not exist.')，__main__ 仅 raise SystemExit(main()) 无外层捕获，英文 traceback 直达操作员。危害链可达：--sheet 是自由文本 CLI 参数（script:89-94），无任何上游 strict_parse/schema 约束，中文 sheet 名打错是现实输入。severity=low 恰当不虚高：崩溃在 write_templates 之前发生，零输出零脏数据，KeyError 消息含打错的名字，属 fail-loud 非吞错；但同一入口对文件不存在给友好中文报错、对 sheet 不存在倒英文 traceback 的不一致是真缺陷（脚本全篇中文输出、开发文档/系统速查表.md:46 确认为面向现场的命令行转换入口），且触发面窄（仅显式传 --sheet 且打错时），影响仅限操作员无法自助排错。 | B:代码事实属实：scripts/convert_rotary_shell_unit_excel.py:105 调 converter.convert 无 try/except，链路 unit_excel_converter.py:26→unit_excel/parser.py:63 `wb[sheet_name]` 对不存在的 sheet 名直接抛 openpyxl 英文 KeyError traceback，与同脚本 100-102 行对文件不存在的中文友好报错(返回 2)风格不一致。核对结果：debt_status_2026-07-19.json 无该脚本任何条目(唯一 unit_excel

### D11 [low] [logging-hygiene] web/routes/domains/scheduler/scheduler_resource_dispatch_execution_routes.py:91

**现场记录/实际情况四个端点的 except 日志完全同文且不带 op_id/task_key**

- 危害链：车间现场提交某道工序的实际情况(POST /resource-dispatch/execution/<op_id>/actual)时触发未预期异常→接口500、实际数据未落库→日志只有"填写实际情况失败"+traceback,既分不清是 op_id 版端点还是 task_key 版端点,也不知道是哪道工序哪张任务卡;多人并发提交时多条同文日志交错,无法定位是哪条工序的现场反馈丢了,只能等现场发现数据缺失后重新口头核对,排障链条断裂。
- 证据：行91与行124两个不同端点(按op_id查询 vs 按task_key查询)写一模一样的 current_app.logger.exception("现场记录加载失败");行140与行156两个提交端点同样写一模一样的 current_app.logger.exception("填写实际情况失败")。四处均不带 op_id、task_key、查询参数或 payload 摘要。对比同仓库惯例(如 web/routes/material.py:159 "新增批次物料需求失败（batch_id=%s）"、equipment_pages.py:316 带 machine_id/status),此文件低于自身代码库标准。
- 核实结论（双镜头+仲裁）：成立但按镜头A收窄。代码事实四方一致：行91/124、140/156 同文 exception 日志且无 op_id/task_key（已亲读源文件确认）。镜头B引用的裁决文档属实（_newdebt_parse-except.md C4 逐字引用该日志文本裁定"loud边界兜底、不进清单"，_newdebt_guard.md:125 二次裁决"非新债"），但其裁决维度是"是否静默吞错/是否新增P4债"——裁定的是 except-Exception+logger.exception+500 这个模式不算静默吞错，并未裁决"日志缺标识符"这一 logging-hygiene 维度；同文档 C2 节明确示范此类改进应"另立条目"，故"已审过选择不立案"是对裁决范围的拉伸，isReal=false 不成立。镜头A的危害收窄全部核实：logging.py:113/129 formatter 含 [%(filename)s:%(lineno)d]，四调用点按行号唯一区分端点且 traceback 含视图函数名，"分不清端点"不成立；端点同步返回500，"静默丢数据后口头核对"不成立；ValidationError 属 AppError 子类，裸 except 触发面窄。残留真实缺口：持久化异常日志无 op_id/task_key/payload 摘要，数据依赖型 bug 无法定位到具体工序记录、复现成本升高，且低于本仓自身惯例（material.py:159 带 batch_id、equipment_pages.py:316 带 machine_id/status，均已核实）。属低价值但真实的 logging-hygiene 改进项，severity=low。

### D12 [low] [logging-hygiene] web/error_handlers.py:52

**全局 AppError 处理器的业务错误日志不带请求路径/端点**

- 危害链：两个不同页面(如批次编辑和周计划导出)抛出同文案的 AppError(如"参数不合法")→日志里出现多条完全相同的"业务错误：参数不合法"warning→排障时无法区分是哪个接口、哪种操作触发,只能靠时间戳与访问日志人工对齐;单机部署下若未开访问日志则完全无法回溯来源端点,用户反馈"某页面总报错"时无法用日志证实。
- 证据：行47-52 `@app.errorhandler(AppError)` 中 `app.logger.warning(f"业务错误：{e}")`(无 internal_details 分支),只记异常文本;不像行102的500分支有 traceback 可反推代码位置,warning 级没有 traceback 也没有 request.method/request.path,而全站所有端点的 AppError 都汇聚到这一个处理器。
- 核实结论（双镜头）：A:成立(证据需修正一处)。行号准确,但候选说"无 internal_details 分支"不实——web/error_handlers.py:49-50 有该分支;真正缺陷是两个分支都不记 request.path/method/endpoint,且 AppError.__str__ 只含 [code] message(core/errors.py:83-84),ValidationError 共享同一 code 无法区分端点。危害链实证可达:同文案多点抛出真实存在("工号不能为空"×14处、"缺少状态参数"×8处),web/routes/material.py:168 与 :189 两个不同端点抛相同 ValidationError("缺少批次号") 且无本地 catch,直落全局 handler,日志行完全相同。访问日志兜底不存在:生产走 werkzeug make_server(web/bootstrap/factory.py:176),werkzeug 访问日志只到 stderr,AppLogger(core/infrastructure/logging.py:38)仅把 APS logger 接文件,全仓无 werkzeug logger 捕获、无 before/after_request 访问日志,Win7 冻结部署 stderr 丢失后文件日志无法回溯端点。severity 维持 low 不虚高:web/routes 有 85 处本地 except AppError 用 flash 消化掉大部分业务错误,到达全局 handler 的多为用户输入错误且用户当场可见,不影响正确性/数据,仅是排障可观测性债;修复也简单(handler 在请求上下文内,补 request.method/request.path 即可)。 | B:代码事实属实：web/error_handlers.py:47-52 的 handle_app_error 两个日志分支（行50 internal_details 分支、行52 else 分支）均只记异常文本，不带 request.me

### D13 [low] [perf-hotspots] core/algorithms/greedy/dispatch/sgs_graph.py:259-265

**图模式环检测 _release_graph_successors 全表扫描,Kahn 拓扑检测退化为 O(V²),且每次候选评估重跑**

- 危害链：生产默认已是图 ready 模式(GraphReadyV2 默认开),待排工序 V 随周计划规模增长:V=2000 时单次环检测约 400 万次内层字典迭代+set 判断(数百毫秒纯 Python 循环),V=5000 时约 2500 万次(秒级);局部搜索/GRASP-IG 一次优化请求会做数十到数百次候选评估,每次都重跑 SGS→重跑这段 O(V²)——一次排产优化请求平白多出数十秒到分钟级 CPU,且随计划规模平方放大,在 Win7 x64 老目标机上更明显。排产结果本身不受影响,属排产主循环入口的纯性能坑;修法是用已有 successor_op_ids_by_op_id 映射按标准 Kahn 做 O(V+E) 释放(该映射在同一函数 sgs_graph.py:70-74 已校验可用)。
- 证据：sgs_graph.py:249-254 `while ready: current = ready.pop(); ... _release_graph_successors(current, remaining=remaining, ...)`;sgs_graph.py:259-265 `def _release_graph_successors(current, *, remaining, ready, visited): for op_id, predecessor_ids in remaining.items(): if current not in predecessor_ids: continue; predecessor_ids.discard(current); ...`——每弹出一个节点就遍历整个 remaining 字典(全部 V 道待排工序),而不是用同函数上游 sgs_graph.py:70-74 已校验、已放进 graph_state 的 successor_op_ids_by_op_id 后继映射做 O(V+E) 释放。该环检测在 _prepare_graph_ready_state(sgs_graph.py:75)里执行,而 _run_sgs_loop(sgs.py:200)每次 SGS 排产都调用 _prepare_graph_ready_state
- 核实结论（双镜头）：A:代码事实全部核实成立:sgs_graph.py:259-265 _release_graph_successors 每弹出一个节点全表扫描 remaining(实测确认 O(V²):V=2000→42ms、V=5000→260ms,V 翻倍耗时约 4 倍),而同函数 sgs_graph.py:70-74/97 已校验的 successor_map 未被环检测使用,O(V+E) 修法数据就在手边;每候选重跑链路也成立(optimizer_local_search_round.py:243-266 → candidate_eval.py:36-53 → sgs.py:200 → _prepare_graph_ready_state,无缓存),且图模式确为生产默认(config_snapshot.py:44 graph_analysis_mode="on",schedule_orchestrator.py:172 传入)。但危害量级两处虚高:(1) 实测耗时比声称低约 5 倍——V=2000 实测 42ms 而非"数百毫秒",V=5000 实测 260ms 而非"秒级"(Win7 老机 3-5 倍慢后才接近声称值);(2) "一次优化请求平白多出数十秒到分钟级 CPU"不成立——局部搜索受墙钟 deadline 硬截止(optimizer_local_search.py:62-66,预设 30s/120s,config_presets.py:71,79),O(V²) 浪费只是吃掉预算内少数几个百分点的候选评估机会,不叠加请求耗时;deadline 外的固定次数阶段(5 个图权重 profile、GRASP≤6/IG≤4)最多多出十几次运行、V=5000 最坏也就秒级。且每次候选评估本身要完整重跑 SGS(V 道工序的打分/派机/日历计算,纯 Python 下 V=2000 量级为秒级),环检测占比约低个位数百分点;项目已示范的典型规模约数百工序(SMTWT 250 实例),V≤1000 时单次 ≤10ms 可忽略。结论:真实的冗余 O(V²) 性能瑕疵,修复简单(改用已有

### D14 [low] [plugin-app] core/plugins/manager.py:206-236

**插件 register() 中途失败无回滚：已注册能力残留全局 registry，与 loaded=no 状态自相矛盾**

- 危害链：用户在 plugins/ 投放一个 register() 里先 `registry.register("excel_backend.pandas", ...)`、后做依赖/版本校验并抛错的插件（框架 docstring manager.py:111 建议重依赖放 register 内 import，这种写法很自然）→ 插件状态页显示该插件 loaded=no、capabilities=[]（报错文案：插件加载失败），但残留的 provider 仍在 registry 里 → get_excel_backend(auto/pandas) 继续把所有 Excel 导入导出路由到这个半初始化插件的后端（构造成功但依赖未过校验时可能产出错误文件，或每次请求构造失败反复降级刷 warning）；同时 first_loaded_wins 冲突策略会让残留 key 挡住后续同名健康插件注册。运维按状态页排查永远对不上实际行为。
- 证据：manager.py:211-215 `registry.bind_plugin(plugin_id); try: mod.register(registry) finally: registry.clear_bound_plugin()`；成功路径 216-217 才计算 `cap_keys = sorted(list(after - before))`；异常路径 225-228 只置 `loaded="no"; cap_keys` 保持 []，但 register() 抛错前已写入 `registry.capabilities` 的条目无任何回滚，283-293 `_STATE.update({... "registry": registry ...})` 把残留能力发布为进程全局。消费方 core/services/common/excel_backend_factory.py:40-48 `reg = get_plugin_registry(); provider = reg.get("excel_backend.pandas")` 直接按能力存在与否选 Excel 后端。
- 核实结论（双镜头）：A:代码事实全部核实为真：manager.py:206-236 异常路径确无回滚，registry.py:33-51 无任何事务/回滚 API，残留能力经 manager.py:283-293 发布为进程全局，excel_backend_factory.py:40-48 是唯一业务消费方，first_loaded_wins 挡后续同名注册也属实（registry.py:36-51）。"loaded=no 但能力仍生效"的不变量确实无守卫且无测试锁定，缺陷成立。但危害链第一环是假设性的：触发需要插件在 register() 内"先 registry.register 后抛错"，仓内两个插件（plugins/pandas_backend_plugin.py:33-50、plugins/ortools_probe_plugin.py:18-21）都是校验完最后一行才 register，框架 docstring 建议的"register 内 import 重依赖"模式失败点在注册之前——即候选声称"很自然"的危险写法恰与所有官方示例和文档引导相反。本项目是单机离线交付、无第三方插件生态。且即便触发，auto 模式下构造失败会降级 openpyxl 并留 warning（excel_backend_factory.py:49-57），"产出错误文件"需要假设插件构造成功但校验未过的二阶假设；残留 key 在 get_plugin_status 的 registry.capabilities 列表中可见（manager.py:61-72），"排查永远对不上"言过其实。维持成立但降级为 low：属插件框架加固项（建议 register 失败时按 before 快照回滚新增 key 并加测试），非现实可达的中危缺陷。 | B:核实为全新未登记问题。1) 账本 docs/_panorama_data/debt_status_2026-07-19.json 无任何 plugin/registry/register 条目；.codestable/audits/ 仅有 A5 循环依赖与 B04

### D15 [low] [plugin-app] web/bootstrap/factory.py:272-277

**atexit 退出备份在获取单实例锁之前注册：锁失败被拒的第二实例退出时仍对共享库做 exit 备份并占用维护窗**

- 危害链：auto_backup_enabled=yes 且实例 A 正在运行，用户误双击再启动一次 → 实例 B 拿锁失败 rc=13 退出 → B 的 atexit 仍执行 _run_exit_backup：对共享 aps.db 拿维护窗锁并整库备份 → 备份期间（大库可达数秒到数十秒）A 的全部页面/接口返回 503"系统正在维护中"，用户以为系统故障；同时产生一份与任何真实退出都不对应的 exit 备份混入轮换，keep_days 修剪时可能顶掉真正有价值的退出备份。
- 证据：factory.py:272-277 `_EXIT_BACKUP_MANAGER = backup_manager; if not _EXIT_BACKUP_REGISTERED and _should_register_exit_backup(...): atexit.register(_run_exit_backup)`（在 create_app_core 尾部 :491 无条件执行，仅按 debug/reloader 判断，不看是否真正拥有运行时资源）；entrypoint.py:308-319 锁获取在其后，失败 return 13 不撤销该 atexit。_run_exit_backup（factory.py:125-137）只查 auto_backup_enabled 就调 `bm.backup(suffix="exit")`，而 core/infrastructure/backup.py:348 附近 backup() 用 `with maintenance_window(self.db_path, ...)` 对共享 db 加维护锁；运行实例的 before_request（factory.py:364 `is_maintenance_window_active`）会因此对所有请求返回 503。
- 核实结论（双镜头）：A:危害链逐环核实成立：factory.py:272-277 在 create_app_core:491 尾部注册 atexit(_run_exit_backup)，仅按 debug/reloader 判定（factory.py:88-93，生产 frozen 恒 True），不看运行时归属；entrypoint.py:219 create_app 先于 :309 acquire_runtime_lock，失败 :315-319 return 13 且无任何撤销；SystemExit 正常退出必跑 atexit → _run_exit_backup(factory.py:125-144) 只查 auto_backup_enabled 即调 bm.backup(suffix="exit")(:137)；backup.py:348 对共享 db 取跨进程维护锁文件（backup.py:273-294，B 存活期间不会被 pid 自愈清理），运行实例 A 的 before_request(factory.py:361-393) 命中即全站 503。无上游校验可拦（配置读取是 SQLite 并发读，锁冲突是代码明确预期的双启动场景，launcher_contracts.py:210-214）。但 severity 虚高，降为 low：(1) auto_backup_enabled 默认 "no"（system_config_service.py:151/177），须用户显式开启；(2) 后果是瞬态自愈的数秒级 503（一次 sqlite backup+integrity_check 时长），无数据损坏；(3) "keep_days 修剪顶掉有价值退出备份"子危害被驳回——cleanup_old_backups(backup.py:512-514) 纯按天龄修剪不按数量轮换，多余的 exit 备份本身也是经 integrity_check 的一致有效备份。修复方向：把 atexit 注册移到 _own_runtime_resources 拿锁成功之后，或在 _run_exit_b

### D16 [low] [test-quality] tests/operation_execution/test_operation_execution_event_foundation.py:433-447

**执行事件 DB 约束守卫五处全用裸 pytest.raises(Exception)，不锁异常类型也不带 match**

- 危害链：该测试守护执行事件审计链的 DB 级 CHECK/唯一约束合同。裸 Exception 使每个分支只要求'抛任意异常'：若 `_event` 测试辅助或 insert_event 的单个具体参数名漂移(例如 quantity_done 改名导致 `_event(quantity_done=-1)` 抛 TypeError)，该分支被裸 Exception 吞掉、测试保持绿，对应约束(如负数完工数量拒绝)从此不再被真实覆盖；后续迁移若放松该 CHECK 约束将无守卫报警，负数量/非法状态的执行反馈行可进入正式执行数据而测试全绿。
- 证据：test_operation_execution_database_rejects_bad_values_and_duplicates 中连续五个 `with pytest.raises(Exception):` 分别包住 insert_event 的非法 event_type="running"、非法 reported_status="finished"、非法 source_table="candidate_rows"、quantity_done=-1、重复 revision 五个坏输入，均不指定 sqlite3.IntegrityError 或错误消息。
- 核实结论（双镜头）：A:成立(实证后比候选还糟一处),severity 维持 low。行号事实准确:tests/operation_execution/test_operation_execution_event_foundation.py:433/435/437/439/441 五处裸 pytest.raises(Exception)。实证运行五分支:全部抛 Python 层 ValueError,没有一个触发 DB CHECK/唯一约束——insert_event(data/repositories/operation_execution_event_repo.py:224-278)在 SQL 前有 normalize_operation_execution_event_values、validate_current_official_execution_scope、_validate_event_sequence_for_insert 三道 Python 校验,测试 docstring 声称的"DB 层 CHECK"实际未被行使。掩蔽危害已实际发生:第4支(quantity_done=-1)抛的是与第5支完全相同的 revision 不匹配 ValueError('10:0:0' vs '10:1:1'),因基础 _event 复用已消费的 revision,负数量校验今天就未被该分支覆盖,删 CHECK 该分支照样绿,裸 Exception 掩住了测错对象。但候选危害链两环写错,压低了 severity:(1) TypeError 机制不可能——_event 是 def _event(**overrides)(line 121),任意 kwargs 不会因参数名漂移抛 TypeError;(2) "放松 CHECK 无守卫报警"夸大——CHECK 子句由 core/infrastructure/migration_operation_execution_contract.py:176 schema 形状合同锁住,负数存量数据由 tests/migration_db/test_mig

### D17 [low] [web-input] web/routes/domains/scheduler/scheduler_batches.py:291

**批量复制批次:用户可触发的输入错误用裸 ValueError,被 except Exception 吞成'系统错误'并污染 ERROR 日志**

- 危害链：批次号是用户自由输入文本(如'急件A'、纯中文编号)。用户在批次管理页勾选这类末尾无数字的批次→点'批量复制'→_next_batch_id_like 抛裸 ValueError→落入 except Exception 分支→页面 flash 显示'急件A（系统错误）',用户看不到真实原因'批次号末尾必须包含数字才能自动+1',误判为软件内部故障且不知如何自助修正;同时一条完全可预期的输入错误以 logger.exception 完整堆栈写进运行日志(ERROR 级),污染 system/runtime-logs 的报错日志,干扰真正故障排查。本仓已有 ValidationError 体系且同文件其它路径均走 AppError→用户可读消息,此处该用而没用。
- 证据：行291(_next_batch_id_like 内): raise ValueError("批次号末尾必须包含数字，才能自动 +1（如：B001）");行299: raise ValueError("无法生成新批次号：尝试次数过多")。唯一调用方 bulk_copy_batches 行346 调用后,行350-356 只区分 AppError 与 Exception: except AppError 走 user_visible_app_error_message,except Exception 则 current_app.logger.exception("批量复制批次失败（batch_id=%s）", bid) 并 failed.append(f"{bid}（系统错误）")
- 核实结论（双镜头）：A:成立。逐环核实无一断裂:(1) 行号/代码事实准确——web/routes/domains/scheduler/scheduler_batches.py:291/:299 裸 ValueError,:346 唯一调用点,:350-356 仅分 AppError/Exception,ValueError 非 AppError 子类(core/errors.py:65,:99),必落 except Exception→logger.exception ERROR 堆栈+flash"系统错误"。(2) 上游无 fail-loud 拦截——批次号创建仅校验非空(core/services/scheduler/batch_write_rules.py:104-106),Excel 导入仅 strip(batch_excel_import.py:39),末尾无数字批次号可合法存在;UI 对所有批次行渲染 checkbox 无格式过滤(templates/scheduler/batches_manage.html:163),"复制所选"直达端点(:207);_next_batch_id_like 在存在性检查之前调用。(3) 触发现实:用户给批次起中文/字母名再点批量复制即触发,非理论路径。唯一轻微缓解是 batches_manage.html:207 confirm 弹窗预告了"末尾数字自动+1"规则,但失败消息仍误导且污染 ERROR 日志。(4) severity=low 恰当不虚高:失败发生在 copy_batch 之前,无数据破坏/崩溃/安全影响,属可用性+日志可诊断性缺陷;修法为两处 ValueError 改抛 ValidationError。 | B:代码事实属实:scheduler_batches.py:291/299 裸 ValueError,唯一调用方 bulk_copy_batches:346 的 except 结构(350-356)使其落入 except Exception→flash"系统错误"+logger.exception,行291那句写给用户的自

## 驳回清单

1. (datetime-edges) `core/services/scheduler/run/optimizer_neighborhood_move_support.py:148-152` — result_time_key 用 getattr 默认值防 None 是死代码:排序键 None 与 datetime 混排会 TypeError
   驳回理由：A:代码事实准确(getattr 默认值对 dataclass 字段永不生效,排序点 :139/:168 属实),但危害链断在生产者一环,坏输入不可构造。进入 first_changeover_pair/changeover_count 的 results 全部来自 schedule_fn 产出的候选(optimizer_local_search_round.py:202→optimizer_local_search_candidate_eval.py:36-58→schedule_optimizer.py:110 baseline)。全仓 ScheduleResult 构造点仅 5 处:(1) 唯一带 machine_id 的 internal 行由 _build_internal_result(core/algorithms/greedy/internal_operation.py:210-222)构造,只在 estimate 成功后调用且 :86-87 先用 estimate.start_time/end_time 调 occupy_resource,时间恒为计算出的 datet

2. (logging-hygiene) `core/services/scheduler/run/freeze_window.py:335` — 冻结窗口加载上一版本排程失败的日志不带版本号
   驳回理由：终审采信镜头A。代码事实属实(freeze_window.py:335 日志确无 prev_version)但危害链两环经亲验均断裂：(1)触发不可达——候选声称的"特定历史版本坏数据导致加载失败"到不了行332的except：逐行坏数据全被 _load_schedule_map 行184-200的 per-row try 消化进 invalid_row_count，走行344-354另一条降级路径(该路径消息还带invalid样本)；能进except的只有 data/repositories/schedule_repo.py:63-66 的时间格式 ValueError(入参来自 svc._format_dt 对真实 datetime 的格式化，freeze_window.py:306-307，实际不可达)和 fetchall 的 sqlite 运行级错误(DB锁/损坏，版本无关，版本号对排障无增益)；行327 int(prev_version) 亦不可达异常(collector 已保证 int)。(2)可诊断性无损——prev_version=get_latest_version(

3. (test-quality) `tests/gate_meta/test_sync_debt_ledger.py:2714-2726` — 重复 debt_id 拒绝守卫用宽泛 pytest.raises(Exception, match="debt_id")，异常类型不锁定
   驳回理由：代码事实属实(test_sync_debt_ledger.py:2720 确用宽泛 pytest.raises(Exception, match="debt_id"))，但候选的危害链两个支柱均经亲自核验证伪。其一，"唯一守卫"为假：tests/gate_meta/test_full_test_debt_registry_contract.py:1161-1164 已用类型锁定的 pytest.raises(QualityGateError, match="debt_id") 直接守住 tools/quality_gate_ledger.py:416-417 的重复 debt_id 校验，校验被删时该合同测试以 DID NOT RAISE 响亮失败。其二，"静默写入台账"运行时不可达：build_test_debt_ledger_from_baseline 返回前自调 validate_ledger(tools/test_debt_registry.py:547)，load_ledger(quality_gate_ledger.py:52→59)与 save_ledger(:181→:

4. (config-drift) `tools/quality_gate_shared.py:363-397` — STARTUP_SAMPLE_EXPECTATIONS 硬编码外部文件行号坐标，随被锚定文件编辑必然漂移导致门禁误报失败
   驳回理由：终审驳回，by-design。代码事实属实（tools/quality_gate_shared.py:363-400 硬编码行号锚点、tools/quality_gate_scan.py:479-489 区间重叠承重匹配、:531-532 fail-loud raise），但"行号漂移→门禁失败"正是设计好的强制同步触发器：SP03 专项计划（.limcode/plans/20260405_技术债务最终合并修复plan/subplans/SP03_启动链静默回退专项.md 实施前确认#14、阶段1.5）明文规定漂移时先更新样本区间、"禁止依赖旧窗口碰巧仍命中来跳过同步"、"不得把样本失配误判成业务回归失败"，并配套 scripts/sync_debt_ledger.py refresh --mode scan-startup-baseline（:166,:241 实证存在）；独立三轮审查（.limcode/review/sp03-...第二版.md 第5点）裁决区间重叠匹配是"有意的鲁棒设计"、漂移风险已审过接受；契约测试 tests/gate_meta/test_architectu

## 完整性批评家补记（首跑失败后单独补跑，9 次工具调用抽查）

### 零产出/零确认维度的复核结论

- **sql-tx 0/0：大概率真干净**。SQL 入口高度集中（全仓仅 database.py:94 与 backup.py:63 两处 connect，事务由 transaction.py 统一管），两处绕开封装的点（gantt_adjustment_publish_service.py:107-108 的 BEGIN IMMEDIATE、logging.py:159-168 的 in_transaction 双检）都有刻意防御。**残留一条无人认领的缝**：database.py:97 `check_same_thread=False`——哪条长驻线程跨线程用连接、有没有串行化，落在 sql-tx 与 concurrency 两个维度的切缝里，下一轮点名核查。
- **resource-leak 0/0：抽查处真干净，可信度较高**。裸 open 赋值全仓为空；read_only workbook 有 finally close（excel_utils.py:391-404）；句柄生命周期有"注释文化"。未覆盖：migration_runner.py:36 mkstemp 清理、scripts 两处 Popen（开发侧，风险低）。
- **numeric-edges 1/0：与代码现状一致**。isfinite 守卫已体系化（strict_parse.py:41/62、_helpers.py:46/94、evaluation.py 三处、ortools_bottleneck 三处等）。未覆盖：报表聚合类除零，可下一轮定向补扫。
- **config-drift 1/0：探子没找对地方，该维度不干净**。批评家 10 分钟探针命中 3 组，主代理已逐组 grep 坐实：
  1. `ROLE_ADOPTED = "adopted"` 独立字面定义 **5 处**（core/models/schedule_plan_role.py:5 canonical + web/navigation_context.py:25 + viewmodels 两处 + reports_plan_template_fields.py:9）——**核实定案：new_debt，med（D18）**。无裁决/护栏/概念守卫覆盖（概念卡 plan-role.md:24 只禁 services 下第二套模块，hypothesis 守卫只调 core/models；R23/R44/R54/R72 是相邻条目非本形态）；复制非规则所迫（viewmodel 门禁明文允许 core.models，且 navigation_context.py:9 与 reports_plan_template_fields.py:5 本文件已 import schedule_plan_role 却仍本地重定义）；全仓无任何测试断言 web 副本 == canonical，漂移不会被拦。加重项：reports_plan_template_fields.py:10 还复制了标签 `DEFAULT_PLAN_LABEL = "正式采用方案"`，直接违反概念卡:17"标签映射唯一来源 plan_role_label()"。
  2. `GRAPH_CONFIG_PENDING_NOTICE`（及 :113 ACTIVE_NOTICE 变体）整句中文文案逐字重复 2 处（config_constants.py:112-113 / scheduler_config_panel.py:9）——**核实定案：new_debt，low（D19）**，且"导入禁令逼出的投影"假说不成立：core 侧两个常量**全仓零消费者（孤儿死代码）**，实际用的只有 viewmodel 副本（scheduler_config_panel.py:149/:159）；无 parity 测试、账本未登记。修法极小：删 core 孤儿常量，或以 core 为源经 route 注入 + parity 测试。
  3. `MISSING_POLICY_ERROR`/`MISSING_POLICY_FALLBACK_WITH_DEGRADATION` 各 2 处（core/models/schedule_config_runtime_fields.py:8-9 / core/services/scheduler/config/config_field_spec.py:9-10）——**主代理初判命中 LB07 config 双栈锁步裁决**（schedule_config_runtime_fields.py 属 LB07 五文件组，config_field_spec.py 是 service 栈孪生），按已裁决处理，不立案。

### 定级异议（批评家意见，主代理采纳情况）

- **采纳：D 类合并升级**——entrypoint.py:218（锁在 DB 迁移后才拿）+ factory.py:272（atexit 备份在锁前注册）应**合并为一条 high 复合链**：第二实例抢锁失败的退出路径 = 锁外并发迁移可损坏 schema + atexit 对正被写入的库做备份。这是 17 条里唯一通向"数据损坏"的链。
- **采纳：sgs_graph.py:259 O(V²) 降为"待实测"**——perf 结论无 benchmark 支撑即确认，违背本仓"性能要实跑 ground-truth"的既有教训（memory: review-fixes-gate-groundtruth）；修前先微基准。
- **记录：parser.py:166（站位列块静默丢弃=数据消失难发现）按仓库不吞错原则应比 :253（数据变形可发现）更重**，两条同级记账偏轻，修复排序时 166 优先。
- static_versioning 竞态本就定 low，无需调整。

### 下一轮盲区维度（批评家提名 5 个）

1. **进程级互斥与跨进程文件竞争**（本轮 concurrency 只切线程轴）：entrypoint.py:203-206 注释自认不同实例会并发覆盖 runtime contract；backup.py:26 `_MAINT_MUTEX` 是 threading.RLock 跨进程无效；database.py:94-99 无 busy_timeout。
2. **备份/恢复/迁移的数据完整性**：atexit 备份对正被写入的库拷贝是否一致、迁移半途断电可否恢复——单机软件"备份是坏的"是最高级用户灾难，本轮切法无家可归。
3. **长驻进程内存增长/无界缓存**："跑一个月后"轴——已确认的关键链缓存即此族成员，同族还有 web/public_token_registry.py:30 等模块级注册表。
4. **桌面壳/子进程生命周期（退出路径）**：壳崩后 Flask 是否成孤儿、runtime_stop 幂等性、崩溃后锁文件残留能否再启动。
5. **frozen 打包一致性**：is_frozen 分叉（entrypoint.py:202-206）、runtime_base_dir 拼路径（factory.py:291-293），14 维度全在源码语义层，没人问冻结态等价性。

## 处置

- **终局账（含批评家修正与补核）：18 条 = 1 high（D04+D15 合并复合链，entrypoint 锁序 + factory atexit 备份）/ 4 med（launcher PS 解码吞字、due_exclusive 9999-12-31 溢出、关键链缓存失效、ROLE_ADOPTED 五处字面漂移 D18）/ 12 low（含 GRAPH_CONFIG 文案孤儿 D19）/ 1 待实测（sgs_graph O(V²)，先微基准）**。
- 用户拍板（2026-07-19）：**全修**，同时按批评家提名的盲区维度另开一轮扫描（结果见 `.codestable/audits/2026-07-19-blindspot-sweep/`）。
- 运行档案：journal 见会话目录 subagents/workflows/wf_9e059127-195/journal.jsonl。

## 处置结果（2026-07-19 当日，18 条全部修复）

组织方式：WP1 主代理修 high 复合链，WP2-WP7 六个并行修复代理各领一包；每包局部测试全绿后集成，最后跑 `.venv` 日常全量门禁。

| 条目 | 修法 | 测试锁定 |
|---|---|---|
| D04+D15 (high) | 锁前移：新增 `web/bootstrap/startup_config.py`（resolve_config_class/resolve_startup_debug_flag），app_main 在 create_app **之前**判定归属并 `_acquire_runtime_lock_before_app`（锁+atexit(release)，失败 rc=13 时 create_app 零调用、零 DB 副作用）；契约发布拆 `_publish_runtime_contract`；atexit 退出备份注册随 create_app 天然落在拿锁成功之后 | tests/app_runtime/test_runtime_lock_before_db_side_effects.py（锁失败→rc13+create_app 零调用+零 atexit；锁成功→acquire→atexit(release)→create_app 顺序） |
| D01 (med) | 两份 due_exclusive 对 9999-12-31（date.max 同日）显式返回 datetime.max，语义与 None→datetime.max 合同同向 | tests/algorithm/test_due_exclusive_guard_contract.py + test_due_exclusive_consistency.py |
| D02 (med) | launcher_processes 新增 `_run_powershell_bytes` 字节通道，路径查询走 base64 往返（PS2.0 兼容、编码不可知），删除 errors="ignore" | tests/app_runtime/test_launcher_process_path_encoding.py |
| D03 (med) | 关键链缓存键并入行集内容指纹（COUNT+MAX(id)+MAX(created_at) 单条聚合 SQL 走版本索引）；恢复/重排/行级重写后指纹必变强制 miss | tests/gantt/test_gantt_critical_chain_cache_fingerprint.py |
| D18 (med) | 四处 ROLE_ADOPTED 字面副本改 import canonical（core.models.schedule_plan_role），DEFAULT_PLAN_LABEL 改走 plan_role_label() | tests/web_pages/test_plan_role_adopted_single_source_contract.py（全仓单一来源合同） |
| D05 | 双 dict 合并为单 dict 存 (mtime, version) 元组，GIL 单赋值原子 | tests/web_pages/test_static_versioning.py 扩展 |
| D06 | 失败 arcname 改纯 ASCII operation_logs_READ_FAILED.txt + Win7 zipfldr 约束 docstring | tests/web_pages/test_diagnostic_package_security.py 同步 |
| D07 | 新增 _select_worksheet 默认 wb.worksheets[0]，active 非首个出诊断 | tests/excel_data_io/test_unit_excel_first_sheet_and_sheet_not_found.py |
| D08 | 新增 cell_parsing.py 统一单元格文本化，datetime 化单元格出显式诊断（step seq 与 part_no 两路） | tests/excel_data_io/test_unit_excel_date_coerced_cells_diagnosed.py |
| D09 | _build_station_columns 带 parse_diagnostics，丢弃列块逐块留痕（含列范围标签）；按批评家排序优先于 D08 修 | tests/excel_data_io/test_unit_excel_station_block_dropped_visible.py |
| D10 | 新增 SheetNotFoundError（携带可用 sheet 清单），CLI 捕获打中文提示 return 2 | 同 D07 测试文件覆盖 |
| D11 | 五处 exception 日志补 op_id/task_key/action 标识符 | tests/operation_execution/test_operation_execution_error_log_context.py |
| D12 | error_handlers 新增 _request_log_context()（method/path/endpoint），两个日志分支携带 | tests/web_pages/test_app_error_log_request_context.py |
| D13 | 先微基准坐实热点（V=2000 55ms / V=5000 345ms）后改标准 Kahn：用已校验 successor_map 做 O(V+E) 释放；修后 58-120x 提速，ratchet 基准零偏差 | tests/algorithm/test_sgs_graph_cycle_detect_equivalence.py |
| D14 | register 前对 registry 三可变面快照，异常整体回滚后 re-raise | tests/config/test_plugin_register_failure_rollback.py |
| D16 | 五处裸 pytest.raises(Exception) 改锁具体类型+match；修正原第 4 支（负数量）实际测错对象的问题（改 AppError+断言 cause 是 sqlite3.IntegrityError） | 本体即测试文件 |
| D17 | 两处裸 ValueError 改 ValidationError 走 AppError 分支 | tests/web_pages/test_bulk_copy_batch_no_trailing_digit_friendly_error.py |
| D19 | 删 core 侧孤儿常量 + 护栏注释指明唯一来源在 viewmodel | 死代码删除，护栏注释防再抄 |

集成阶段协调项（WP6 巡检发现，均按正路收口不绕门禁）：静默回退台账 24 条行号按扫描器真值批量对齐（sync_debt_ledger check 通过）+ entrypoint 两条目改名迁移；quality_gate_shared STARTUP_SAMPLE_EXPECTATIONS 的 factory _close_db 锚点更新；a3 边界测试模块计数 pin 782/1493（+3 生产模块 builder_diagnostics/cell_parsing/startup_config，+15 测试模块，附 bump 纪律注释）；runtime_log_reader docstring 同步；ruff 5 处（3 个 import 排序 + UP030/UP031 格式化）。

账本登记：18 条以 D01-D19 编号（D04+D15 合并记 D04 一条 high）、bucket=BD、状态 fixed 登入 `docs/_panorama_data/debt_status_2026-07-19.json`（账本终态 108 条 = 41 fixed / 3 in_progress / 63 planned / 1 n_a）；债务全景图/项目全景图已重生（108 卡）。

门禁：`.venv/bin/python scripts/run_daily_quality_gate.py` 于 18 条修复+账本登记+ruff 5 处收口后全量复跑，**`[daily-fast-gate] passed` 全绿**（2026-07-20 03:33，含 ruff check full、pyright、py38 语法扫描、架构适应度、静默回退台账对齐、a3 边界、301+5 focused pytest）；`sync_debt_ledger.py check` 通过（silent_fallback_count=69）。工作区仍有本批未提交改动，按约定不声称 clean-worktree proof。

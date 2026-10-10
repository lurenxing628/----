---
doc_type: audit
date: 2026-10-10
status: completed
---

# Win7 复杂样例、读取压力与交付验收

本检查点的核心验收已完成：相同100批次/5000工序/6条分次报工、600s发起窗口/16并发/60s socket timeout/无重试条件下，修后原生冻结程序 **279/279请求全部HTTP200，timeout/failed/non_200/invalid_content均0**；压后任务、四个采用数量字段、执行事实、报工、完整来源链与全列导出保持。样例停用和复用、独立合法试调及下载维护生命周期已有真实证据。[读取压力问题](../issues/2026-10-10-win7-native-read-pressure-timeout/issue.md) 已resolved。

本报告所列原生验收、强退役临时Python后的普通启动/停止、环境恢复及宿主桌面交付已完成。Git整合和远程读回另以root实际执行的同步收据核对，不以问题resolved代替其它步骤。本文按已保存原始文件核销，不改写任何原失败。

## 版本、环境与证据口径

| 版本 / 环境 | 事实与边界 |
| --- | --- |
| 本轮开始基线 | `b8cc53017d03aa6e5a511127fe8f3f6ca8a26782` |
| 修复前native v2 | `a4a6ad24452675305196c8889f18482c025447ad`；门禁`9d4faa56743f9f9ab4af3e3740fcf14ea5bd198a`仅多债务台账坐标/时间更新，运行内容相同 |
| 最终运行源码 / native v3 / 完整门禁 | **`4f850c75cfb4c2d4d975e7832958180cd6f82d54`**，archive时clean，2130个tracked源码文件；不是把宿主测试绑定到另一版原生程序 |
| 文案checkpoint | `404dc65f7f1613de2b0251bc3bf640fb0bae7585`，两份说明调整；compiled source仍4f，148非README文件不变 |
| Win7 | SP1 x64，6.1.7601，PowerShell2.0，4 logical processors，约8GiB物理内存 |
| 原生构建/独立源码夹具 | Python3.8.10 / PyInstaller4.10；临时构建与测试运行时不是目标用户必装依赖 |
| 真实页面 | 随包Chrome109；本地应用静态资源，独立profile和真实冻结后端 |
| 源证据 | [source-v3 manifest](../../output/win7-complex-20261010/exchange/source-v3-manifest.json)、[环境](../../output/win7-complex-20261010/exchange/native-environment.txt)、[v3进程审查](../../output/win7-complex-20261010/native-pressure-v3-process-readonly-audit.json) |

最终main和远程版本一致性由root实际执行后记录于[Git同步收据](../../output/win7-complex-20261010/final-git-sync.json)，不在此文填写自引用提交号。原生编译4f与说明404dc的血缘不随后续验收文档提交改变。

证据分为真实冻结程序HTTP/worker/业务库、Win7独立源码测试、真实浏览器组件DOM夹具、实际业务页面读取、独立延迟fixture。它们分别计数；factory/SQL/monkeypatch或合成响应不替代真实业务写入、压力或逐按钮验收。证据根目录为本机`output/win7-complex-20261010/`，原库/原始响应/截图不随用户包交付；文档不复制完整运行时契约、shutdown token或write_context。

## 最终完整质量门禁

正式入口 `scripts/run_quality_gate.py --require-clean-worktree --no-long-gate-cache --no-resume` 在4f真实执行17/17steps，开始北京时间08:18:52、结束08:31:03。每份receipt returncode=0、execution_mode=executed、reused_from空；无缓存、成功前缀续跑、超时或中断，计划与执行命令/日志/run_id匹配。

收集 **526唯一nodes / 1578reports**，setup/call/teardown分别526条普通passed、每node恰好三phase；无skip/xfail/collection error/failure/new debt。serial66、parallel-1 130、parallel-2 206、parallel-3 124；第16步663.0s，第17步核销105targets/323required nodes。本轮新CPU **112=22业务语义+72存储类型oracle+18 metadata**、来源复用9，共121新增；原94仅早期阶段，原405门禁不借用来覆盖后续CPU源码。

门禁前后工作树状态数组为空、tracked drift=false、resume=false/skip_count=0；167项source proof含166个存在文件摘要一致和1个预期缺失状态一致。runtime snapshot contract/lock/health/pid absent。整个`evidence/QualityGate`已固定归档为 **55files / 1,082,544B**，文件集合与每个原始字节都与live evidence相同；旧405及失败档案未覆盖。来源：[固定manifest](../../output/win7-complex-20261010/quality-gate-cpu-4f850c75-526-raw/quality_gate_manifest.json)、[固定526结果](../../output/win7-complex-20261010/quality-gate-cpu-4f850c75-526-raw/current_full_test_debt.json)、[完整日志](../../output/win7-complex-20261010/quality-gate-cpu-4f850c75.log)，同固定目录receipts/logs。

## 原生构建、普通安装与复杂样例

v3在Win7从4f source archive实际构建，149个干净便携文件、276,590,651B，内部ZIP134,199,230B/CRC通过；内部归档超过80MB，不能直接作为外发包。来源：[build log](../../output/win7-complex-20261010/exchange/build-v3-live.log)、[portable manifest](../../output/win7-complex-20261010/exchange/APS_Portable_Win7_x64_20261010_v3.manifest.json)。

| 实际普通入口 / 固定run | 完成事实 |
| --- | --- |
| cold `20261010T002717445-844` | UTC00:27:20.742完成，独立cold目录149文件/exit0/source dist untouched；冻结健康、工作台HTML、本地资源及退役入口通过 |
| install `20261010T003217223-508` | Win7自带Shell.Application提取首ZIP14文件，普通Install.cmd完成149文件/exit0，首次启动前无user-data、sample默认off；wrapper独立保留 |
| Start `20261010T003347482-232` | 正式production/系统PATH、2.958s入口及运行状态核对/exit0，正式空库PID3760/5957；单独入口进程2.715s不混作计算时间 |
| SampleOn `20261010T003511703-5104` | fresh独立context，418.377s/exit0；固定观测83及完整业务报告complete，内部410.064s、333steps、1323真实HTTP |

固定证据：[cold](../../output/win7-complex-20261010/exchange/native-cold-v3-20261010T002717445-844.json)、[install](../../output/win7-complex-20261010/exchange/native-install-v3-20261010T003217223-508.json)、[Start](../../output/win7-complex-20261010/exchange/native-start-Start-20261010T003347482-232.json)、[SampleOn](../../output/win7-complex-20261010/exchange/native-start-SampleOn-20261010T003511703-5104.json)、[完整样例报告](../../output/win7-complex-20261010/exchange/native-sample-acceptance-20261010T004209791-5104.json)。不使用会被下一次运行覆盖的通用`*-state.json`替代固定run文件。

样例100批次×50工序=5000；4600自制、400外协、200合并连续外协周期；10套工艺、24设备、16人员、11工种、6设备组、2班次、3供应商、5物料。81工作日历日、20个人日历日、24停机记录。完整候选核对4900前后序、9160资源相邻区间无重叠、4600技能/设备授权、690物料释放条件；日历/效率/停机/执行仍由完整生产adopt-preview作权威复核，不靠近似第二套日历。

| 流程 | 真实结果及限制 |
| --- | --- |
| 第一轮排产 | 原算法5000 candidate completed/completeness=complete；计算14.321s、轮次18.970s，真实预检/正式采用/回读 |
| 已有正式计划下第二轮 | 原算法5000完整候选，计算14.337s、轮次20.982s，预检允许/候选重开；formally_adopted=false、原正式计划不改 |
| 其它优化候选 | 默认5s比较预算下两轮overall均partial，各5个比较候选skipped/task_count0；没有声称全部方案执行 |
| 导出与冲突试调 | 候选/正式CSV和XLSX各5000行、对应scope全部列/工序/原时段核对；独立冲突草稿保存、校验/采用预检拒绝，不改原正式计划 |
| 报工与再次排产 | 真实写令牌/命令产生6条partial。全100/5000与未报工94/4700两种范围均准确拒绝再次排产，无新job/receipt、计划/报工/目录不改 |

`complete`只表示现有可用流程及真实拒绝护栏验收完成。当前缺可信剩余安排时尚不支持报工后重排；自制连续组无现行业务写入入口。未补造完工/剩余安排、修改引擎保护或将正常未知评估改为零风险。

样例完成后独立[v3 baseline](../../output/win7-complex-20261010/native-v3-readonly/sample-baseline.json) 16GET全部200/no-store，6组检查passed，5000唯一task/6partial/342-node完整链及原scope snapshot重开一致；CSV2,864,017B、XLSX1,065,456B，各5000×32=160,000格按原单scope完整核对。最大guest桥接5.430543s包含HTTP与base64准备，host5.610s还含HGFS/串行排队，不能作并发吞吐。

## 真实压力：保留首失败，修后同参数通过

首v2 run `20261009T233236555-1212` 在相同规模/参数下含drain657.451s，254请求=94passed+160timeout，invalid0；health42和machine40全200，大分析6pass/76timeout、正式workspace6pass/84timeout。160timeout无HTTP状态，不能写成HTTP500/413。原[首压力最终结果](../../output/win7-complex-20261010/exchange/native-pressure/20261009T233236555-1212/http/result.json) 不覆盖。

后端564单核量级持续CPU/内存充足及独立cProfile共同支持CPU读取开销推断，不声称OOM或直接测量GIL。修复在既有只读evidence作用域复用相同audit的完整proof/已验证GenerationFacts、相同计划mapping及等价日期/primitive转换；不同baseline/ref、schema/manifest/receipt/canonical/64MiB/point保护全部保留。宿主诊断性能数字及版本历史详见issue，不外推成原生并发收益。

修后v3 run **`20261010T005347844-2572`**，真实HTTP窗口UTC00:53:57.643317开始；backend3088、actual client4300，launcher1916独立标识。直接来宾loopback真实GET，600s停止发新请求、16worker/60s socket操作timeout/no retries，原容量与预算不增。

| 指标 | v3终态 |
| --- | --- |
| 总耗时 / drain | 653.613s / 53.613s |
| 请求 / passed / failed / timed_out / non_200 / invalid | 279 / 279 / 0 / 0 / 0 / 0 |
| 四endpoint数量 | health45、machine43、full-analysis95、formal-scope96，全部HTTP200 |
| 实际最大I/O并发 / 完成worker | 16 / 16 |
| 最后发起 / 最后完成 | 596.642s / 653.363s |
| 最大HTTP wall / 对60s余量 | 58.266s / 1.734s |

279原JSONL、16worker精确序列、实际I/O区间/最大并发、真实client内容validator、234条业务响应no-store及失败数组独立核对；无600s后新请求、重试、失败删除或镜像失败。综合[16checks](../../output/win7-complex-20261010/native-pressure-v3-complete-readonly-audit.json)全true；原[HTTP终态](../../output/win7-complex-20261010/exchange/native-pressure/20261010T005347844-2572/http/result.json)、[原请求审查v2](../../output/win7-complex-20261010/exchange/native-pressure/20261010T005347844-2572/raw-audit-native_matrix_sources-v2.json)、[进程审查](../../output/win7-complex-20261010/native-pressure-v3-process-readonly-audit.json)独立保留。

37个backend WMI观测平均weighted约25.010%整机/1.0004单核量级，working-set峰值272,089,088B，可用内存最低5,808,340KiB；原capture时间与冷WMI格式化写出延迟分开。actual client仅核对后36条采样，首行缺失不回填。没有OOM/崩溃证据，也没有用37个观测证明任意长期运行无泄漏。60s是socket操作timeout，每次成功HTTP wall另实际核对小于60s，不假装它是所有trickle响应的绝对总截止。此次通过限于实际机器/规模/并发；最大余量1.734s如实保留。

## 压后完整性与真实界面

[压后16GET/导出](../../output/win7-complex-20261010/native-v3-readonly/postpressure-http-export.json) 全200/no-store，14原JSON+2原文件保存，7组业务checks passed；[独立压后16checks](../../output/win7-complex-20261010/native-pressure-v3-post-readonly-audit.json) 全true。与该v3压前基线比较，5000task核心字段/四数量字段/执行事实、6partial和342-node source chain一致；原snapshot/单scope重开，CSV/XLSX各5000×32全列原值核对无遗漏。独立审查又重读160,000格比较两个文件并验证plan/operation/batch/start/end五核心字段；完整32列原scope oracle由实际导出回读器另保存，不能把二者混写成独立审查重新推导所有风险列。

merged canonical8,240,061B、standalone7,399,514B在既有8MiB内；actual-gantt9,901,379B属于独立合同，不套用值班台预算。六条仍为partial，confirmed_finish/completion_basis/remaining_plan未知值保留。压后guest最大5.199520s（含base64）是串行桥接；279压力请求只保存client校验/时序/字节指标，不声称保存并重新解析每份原body。

实际v3 Chrome109 scan **`20261010T004839927-3336`** 覆盖16入口/15视图/33截图。原[result passed=true](../../output/win7-complex-20261010/exchange/app-ui-results/native-app-ui-scan-v3-20261010T004839927-3336/result.json)和[strict false](../../output/win7-complex-20261010/exchange/app-ui-results/native-app-ui-scan-v3-20261010T004839927-3336/strict-read-audit.json)均保留；唯一strict未核销项是把TrialCatalog打开draft_ref与保存scenario_ref错当同一实体ID。独立[96checks审查v2](../../output/win7-complex-20261010/native-app-ui-v3-independent-audit-v2.json)根据原seed/真实GET/源码核对两个5000草稿打开正确，全部passed。

原网络唯一request_id169=168HTTP200+1bootstrap导航cancel无status；API27=26成功+1同cancel，不能写169/27全成功。runtime/console/static异常0；只读POST按真实query源码核销。实际4张关键截图另有人工作视查阅，完整原33截图保留；局部滚动/小甘特条及未知评估正常显示，不泛化为所有写入按钮通过。

压力期间只对既有值班台局部展示动作作探针：**842.9ms**，新增request/API/WebSocket均0，无刷新/导航/业务写入。[局部探针](../../output/win7-complex-20261010/exchange/app-ui-results/native-app-ui-local-v3-20261010T010035564-4264/result.json)不证明满载重新加载页面。[压后fresh可见PNG](../../output/win7-complex-20261010/environment/v3-postpressure-ui-fresh.png)另核对中文、正式v1/独立样例标签、100待排与6项执行未知/400外协来源缺口可读，无空白/加载占位。没有因此隐藏真实风险或把来源缺口当已评估。

## 六类原触发条件：按真实证据类型核销

早期[review matrix](../../output/win7-complex-20261010/review-matrix.md)是待执行设计，保留原pending；本表记录实际完成范围，不把矩阵中未执行的家族/阶梯/写压力迁为通过。

| 类别 | 已完成证据及明确范围 |
| --- | --- |
| R1 读取60s预算 | 实际大样例/页面及同参数压力；Win7 Chrome交付GET独立45s fixture，唯一请求45.2944s成功、signalAborted=false、真实冻结5957捕获5000载荷，由5967人工延迟回放。不是产品计算45s，也不是fixture替代压力 |
| R2 下载后原worker维护 | Win7源码2个生命周期用例；独立冻结v3真实batch模板GET200/9098B/客户端EOF/ZIP CRC/13 XLSX entries，到期原10s节流worker自动备份1,384,448B/integrity ok，普通stop/退出0。配置由正常源码服务预置新库；没有逐个下载家族都触发自动备份或用EOF证明内部回调精确时刻 |
| R3 最终完整canonical8MiB | Win7源码canonical5项覆盖同一fact、合并/独立分析完整清单预算及analysis/candidate-comparison非有限JSON拒绝；实际5000 merged/standalone bytes及压后完整值核对。超限/非有限浮点定点证明属源码夹具，不冒充自然业务冻结输入；未从这5项宣称分析DTO含bytes已独立注入验证 |
| R4 历史来源正规化与严格写入 | Win7独立历史SQL/source factory4项，存储原值/SQLite类型、读正规化及未知来源/写拒绝合同；真实正常5000业务源另核对。坏历史输入不是正常资料写入，也没清洗正式数据 |
| R5 stale/pending提醒归属 | Win7 Chrome109独立DOM fixture实际组件点击/disabled/正文归属等；属于合成响应/本地存储故障，不冒称双浏览器真实竞争保存与网络丢返回均已重跑 |
| R6 共用计划问题/模态存储错误 | 同DOM fixture验证共享/独立来源、物料、storage模态/保留open、外协/unknown-source等；实际页面正常来源缺口保留。不能把局部fixture核销解释为全部业务写流程通过 |

独立DOM原v2 **13scenarios/119checks true/24PNG**、runtime/static0：[原DOM结果](../../output/win7-complex-20261010/exchange/ui-dom-results/native-ui-dom-v2-20261009T230848832-624/result.json)。源码v2/v3归档的frontend/workbench及static/workbench **370个文件逐字节相同、无新增**；两个native portable ZIP的workbench静态 **11个文件原字节相同、无新增**。因此相同组件证据保留，但仍归属原v2运行，不伪造v3新DOM run。R1 [45s结果](../../output/win7-complex-20261010/exchange/app-ui-results/native-app-ui-delay-v2-20261009T232622482-5016/result.json)同样保留实际source/fixture边界。

## Win7独立源码、冻结正向流程与原文件归档

独立v3运行 **`20261010T004448338-564`** 结束UTC **00:46:16.8992452 / 北京时间08:46:16**；早期交接04:46UTC笔误不用作证据。[固定state](../../output/win7-complex-20261010/exchange/native-independent-v3-20261010T004448338-564-state.json) 三步均complete：

- Win7 SP1/Python3.8.10，132=canonical5+历史4+维护下载2+来源复用9+CPU112，failures/errors/skipped0。原目录[copy manifest](../../output/win7-complex-20261010/exchange/native-cpu-source-fixtures-v3-raw/copy-manifest.json)的16文件全部存在/字节数一致，加manifest共17；5XML直接解析5/4/2/9/112合计132，source2130 CRC/字节数passed，隔离pytest导入/提取/CRC日志保留。copy检查是存在性/大小，不虚称fixture DB/user-data/runtime契约也归档。
- 独立149文件冻结v3/小型2×8，真实worker→候选采用→新建/编辑/保存/重开→试调采用，500requests，16tasks改1道、15道/数量/历史保持，原5000 untouched，普通owned stop0，无浏览器。[positive-trial-v3](../../output/win7-complex-20261010/exchange/trial-positive-v3/positive-trial.json)内部test名称旧v2仅是helper标签，版本以backend/source元数据为准；不冒称5000-row合法试调采用或UI流程。
- 独立冻结空库模板EOF/自动备份/普通stop及进程退出如R2，[maintenance-download-v3](../../output/win7-complex-20261010/exchange/maintenance-download-v3/maintenance-download.json)。精确WSGI active-count/close次数属于源码夹具，不以客户端EOF反推出内部执行时刻。

## 样例停用与复用：数据保持

正式切换前以真实业务HTTP创建唯一synthetic材料控制身份`55a4c96df784a3561fb0c5be45a38efe882725e03acfc0a3`；控制记录含过期write_context，本文不展示完整字段。

SampleOff固定 **`20261010T011208682-2580`** complete/pass/exit0、4.736s回正式PID2516/5957。[sentinel-off](../../output/win7-complex-20261010/native-v3-readonly/sentinel-off.json)12GET全200，业务详情保持，只排除新write_context；正式root/db恢复，与样例不同，正式仅1material、batch/run/history/scenario0，没有复制样例库。来源：[固定Off](../../output/win7-complex-20261010/exchange/native-start-SampleOff-20261010T011208682-2580.json)。

SampleOn复用固定 **`20261010T011401854-2708`** complete/pass/exit0、7.171s，样例PID1556/5957。[sample-on-reuse](../../output/win7-complex-20261010/native-v3-readonly/sample-on-reuse.json)16GET200/no-store，5000/6/342、2runs/100batches/history1/scenario0、数量/资源/目录一致，只有资料汇总calendar.as_of允许时钟变化。原sample-acceptance-before与on-reuse文件原字节完全相同，无重新注入；不把所有新HTTP响应说成原字节相同。来源：[固定On](../../output/win7-complex-20261010/exchange/native-start-SampleOn-20261010T011401854-2708.json)。

## 用户交付包

文案派生候选[delivery-v3-docfix](../../output/win7-complex-20261010/exchange/release-v3-docfix/delivery.json) **149files/276,591,182B**；148非README文件不变，只改README_PORTABLE.txt 2235B/CRCa99721c5→2766B/CRCa633c09f，EXE7,697,690B/CRC8b83ccc6保持。compiled source=4f、docs404dc；新部署目录Version4只代表安装次数，不代表native v4编译。

实存01 ZIP **76,368,182B/CRC0312fe32**、02 ZIP **23,635,469B/CRCfdfa30b9** 已只读逐字节CRC32及大小核对，均严格小于80,000,000B；继续沿既有ZIP/7z CRC和文件清单，无新密码校验框架。用户候选不含业务DB、运行样例库、日志、备份或浏览器profile。原已部署v3两包和内部134MB归档保留；最终docfix目录由下面独立安装证据核销。

最终中文/空格新目录普通安装wrapper **`20261010T011909031-3312`**，真实install run **`20261010T011909098-3312`** 均complete/pass；首包builtin提取14、程序149、首次无user-data、sample默认off、Install.cmd exit0。安装metadata evidence_version4/actual release_version3/release-v3-docfix，compiled4f/docs404dc/148不变1README；已安装EXE尺寸7,697,690B与派生记录一致。本步骤没有再次计算EXE CRC，不声称做了一次新编译。来源：[docfix wrapper](../../output/win7-complex-20261010/exchange/native-docfix-install-20261010T011909031-3312.json)、[固定真实Install](../../output/win7-complex-20261010/exchange/native-install-v4-20261010T011909098-3312.json)。

最终普通冷启动与相对目录停止固定 **`20261010T012504835-2968`** complete/pass，总8.368s、Start入口2.624s/exit0。初始rootbackend0/无user-data/defaultoff；新backend2936/5957创建时间晚于真实CMD，证明没有复用旧后端。系统PATH启动，在APS_Portable cwd经真实 **START /WAIT** 执行`--runtime-stop . --stop-aps-chrome`，延迟展开捕获ERRORLEVEL0；原PID/创建实例退出、5957独占绑定成功、正式marker保持、最终rootbackend0，helper kill=false/runtime retries0。来源：[cold-dot结果](../../output/win7-complex-20261010/exchange/native-docfix-cold-dot-20261010T012504835-2968.json)、[固定最终状态](../../output/win7-complex-20261010/exchange/native-final-state-20261010T012512894-2968.json)。这一步仅证明普通新安装/全新启动/正常相对目录停止；不借其系统PATH条件替代下面独立强退役验证。

## 临时Python强退役、进程收尾与VM恢复

强退役固定 **`20261010T012833250-1832`** complete/pass，总7.692s。四个本任务owned临时Python/构建目录可恢复移到`retired-python-20261010T012833250-1832`，并由退役脚本核对源/目标路径；没有删除全机Python或动用户旧程序。退役后系统PATH/清理Python环境变量经普通Start启动 **1.451s/exit0**，实际新backend **2784/5957** 创建晚于CMD；随后正常`--runtime-stop`退出0，正式marker及defaultOff保持，未以源码服务或已运行旧后端替代。来源：[强退役原结果](../../output/win7-complex-20261010/exchange/native-retire-python-20261010T012833250-1832.json)。

完成helper退出后另作新鲜WMI采集 **`20261010T013527843-4548`**：[退出状态](../../output/win7-complex-20261010/exchange/native-final-state-20261010T013527843-4548.json) 仅保留采集自身helper4548，1832 absent、owned APS/Chrome/Python0、sample formalOff。四条role=temporary_task_python_directory的正确字段均为 **directory_exists=false**，与先前Directory.Move后source不存在/destination存在断言一致；目录条目不能误读普通文件字段exists。149个已安装程序尺寸无差异、owned markers已核，原runtime契约未复制、命令行秘密脱敏。独立[28checks只读审查](../../output/win7-complex-20261010/build-prep/final-retire-readonly-audit-20261010T014022510-73652.json)全passed，未执行VM/RPC/GUI/Git。这只收尾本任务四目录及进程，不声称停止其它用户应用或删除全机Python。

VM恢复固定 **`20261010T013707772-57380`** [state](../../output/win7-complex-20261010/build-prep/host-restoration-evidence/20261010T013707772-57380/state.json) complete/passed：移除仅本任务`APSComplex20261010`共享，九个原HGFS键值完全恢复、final_plan already_restored=true；原两个snapshot列表及VMSD恢复前后原始字节一致，original baseline也一致，snapshot未改、VMX未整体覆盖、旧程序/业务未动。真实VMCLI状态 **on→soft suspended**，power baseline differences空，当前运行checkpoint保留；恢复过程guest_commands_executed=false。原九键、before/after VMX/VMSD、snapshot/power/每次命令结果在同固定目录保留。

第一次Apply **`20261010T013627470-26976`** 因helper只接受PowerState=running、实际VMCLI返回on，在修改前拒绝；原[failed state](../../output/win7-complex-20261010/build-prep/host-restoration-evidence/20261010T013627470-26976/state.json) 保留。该次仅listSnapshots及Power query两条只读命令，零mutation；没有自动恢复/猜测状态。最小兼容已明确的on返回后，独立[29项离线self-check](../../output/win7-complex-20261010/build-prep/host-restoration-self-check-20261010T013657071-55168/proof.json) 全passed，vm_commands0/guest_access=false/原VM文件不改，然后才执行上面的真实恢复。29项是helper守卫测试，不能单独代替真实VM恢复成功。

宿主桌面 `C:\Users\lurenxing\Desktop\APS_Win7_交付_20261010` 已实际生成一份，精确包含五个客户文件：两ZIP、README.txt、delivery.json、验收记录.txt。两个ZIP仍分别76,368,182B/CRC0312fe32和23,635,469B/CRCfdfa30b9；说明4047B、delivery1210B、验收记录3637B。复制入口先从两ZIP完整重建149个文件并核对全部CRC和大小、148非README与原生v3一致，然后复制并逐文件核对，最后完整读取桌面ZIP，全部通过。实际[桌面复制收据](../../output/delivery-complex-20261010-v3-docfix/desktop-copy-proof.json)、[最终使用说明](../../output/delivery-complex-20261010-v3-docfix/customer-prep/README.txt)、[最终验收记录](../../output/delivery-complex-20261010-v3-docfix/customer-prep/验收记录.txt) 保留；内部134MB归档、测试工具、原始证据、业务及样例库没有复制到客户目录。

未新增全覆盖声明：全部业务按钮、所有Excel文件家族及异常矩阵、真实R5双页竞争、写并发/1-4-8-16阶梯1024次、所有下载家族自动维护、实际打印、域账户/组策略、任意更大数据与更慢机器不在本次已实测全集内。旧历史记录可参考，不能替代当前版本的新实机事实。当前通过的是真实执行并有对应证据的范围。

## 原失败与工具问题保留

- 首v2压力160timeout是真实产品失败，未删除、重试或改为通过；修后v3是独立同参数新run。
- PS2 prelaunch WMI/JavaScriptSerializer循环引用、v2launcher3412误采与实际client1316纠正、一次不可能842.9009%派生CPU值分别保留，不冒称OOM或后端真实占全部机器8倍CPU。
- UI只读POST误分写入、v3trial draft/scenario ID误断言是工具口径；原false与独立纠正报告都保留。
- v3首次raw auditor48条计时方法误报（47offset/1峰值）原文件保留，corrected v2按实际capture时间核销；原HTTP failure始终0。
- 原a4/中间CPU门禁失败及债务坐标漂移日志、9d405与最终4f526固定raw档案分别保留，未改变债务身份、删除白名单项或修改阈值伪造通过。

实施现状见[feature implementation](../features/2026-10-10-complex-win7-sample/implementation.md)；原生验收及用户交付按已完成证据核销，Git同步以root实际完成后的独立收据为准。

---
doc_type: feature-implementation
date: 2026-10-10
status: completed
---

# Win7 复杂样例与交付验收

本轮以 `b8cc53017d03aa6e5a511127fe8f3f6ca8a26782` 为修复后基线。用户已授权最新代码的真实 Win7 验收、修复现场发现的问题、完成原有离线便携交付，并在本对话直接授权与“验收期量测算 Win7 1.0.1”协调虚拟机窗口。原打包要求仍是每个 ZIP 小于 80 MB，桌面保留一份。

复杂样例默认关闭。外层 `Application/Start.cmd` 选择正式程序或独立 `sample-context/APS_Portable`。首次启用按交付静态文件清单复制程序，创建明确的样例标记，经原启动器启动，然后执行冻结程序的 `--sample-inject`。注入使用公开业务 HTTP 接口及现有写令牌、命令和导入契约，不直接写数据库，不伪造排产结果。关闭先正常退出样例，再启动原程序；正式 `user-data` 不复制、不清空，样例数据单独保留。

通过现有工作台实例标签显示“复杂样例 · 独立数据”。初次样例先从过去 14 天开始排产，跨 81 天窗口，让分次报工来自真实已采用计划中的过去时段。真实未来报工拒绝保留。验收在报工前完成第二次真实重排；报工后对全范围和未报工批次范围都核对准确拒绝及计划、记录不变。当前产品会保护没有可信剩余安排的正式执行范围；不得补造完工事实或解除保护来制造通过。

目标样例为 100 批次、50 道工序，共 5000 道，覆盖异质路线、替代设备组、多技能共享人员、换型、前后序、连续外协、轮班/节假日/停机/个人日历、物料分期齐套、优先级和交期。采用及报工必须由真实排产候选和现有写入口产生。当前未找到独立的自制连续组写契约，不将其冒充为已支持。可行场景和合法写入造成的冲突分别记录。

交付保留原有离线程序、Chrome109和内置解压工具，沿用既有分卷安装入口，移除本轮交付的密码哈希校验，使用归档 CRC、字节大小和文件清单核对。包内不带业务库、样例运行库、日志、备份和浏览器配置。原依赖锁定契约不改写。

宿主准备发现 `validate_dist_exe.py` 的样式锚点仍指向已删除的 prototype/styles.css；更新为现行 manifest 使用的 app/workbench.css，使冷启动验证检查当前实际资源。

## 原生验收及用户交付已完成

本轮最终运行源码及原生冻结v3为 **`4f850c75cfb4c2d4d975e7832958180cd6f82d54`**；文案checkpoint **`404dc65f7f1613de2b0251bc3bf640fb0bae7585`** 只改说明。8个生产文件及2个新增测试沿既有只读作用域复用同一audit完整proof和已验证GenerationFacts，旧baseline、schema/manifest/receipt/canonical/64MiB/point保护全部保留；最终primitive采用严格类型身份，未新增全局缓存、请求重试或更大预算。宿主24份before/after业务值、键/类型/wire等价，CPU中位数formal3003减37.45%、analysis约12.5%、merged约13.7%；这些仍是独立源码串行诊断，原生结论另以实际压力证明。

4f完整clean/no-cache/no-resume门禁 **17steps/526nodes/1578reports** 实际全部普通passed，无skip/xfail/error/new debt；CPU最终112=22业务+72类型oracle+18metadata，加来源复用9，共121新增。Win7 SP1/Python3.8.10独立源码实际132=旧11+9+112全部passed，5XML合计132、16原文件加copy manifest共17文件已真实归档，2130源码CRC/字节数核对通过。它与冻结HTTP、真实页面和DOM夹具分别核销。

fresh原生普通安装149文件/样例默认关/首次启动前无user-data，冷启动exit0；正常Start 2.958s且PATH仅系统目录。正常SampleOn **418.377s**，内部410.064s/333steps/1323HTTP，100批次×50工序、6条partial报工。两轮各完整5000原算法候选，计算14.321/14.337s；默认5s下两轮overall partial、各5个其它候选skipped。第一轮正式采用，第二轮候选/复核/重开但formally_adopted=false，原正式计划不改。报工后全范围及未报工范围重排准确拒绝；自制连续组仍无现行业务写入口，complete不表示这些能力已支持。

原v2首压力 **254请求/94通过/160timeout** 永久保留。修后同规模/参数600s、16worker、60s socket timeout、无重试的真实Win7读压力为 **279/279全部200，失败/超时/内容错误0**，含drain653.613s，最大HTTP58.266s；实际client4300/backend3088及16worker由原序列、WMI/父链和综合16checks独立核对。此问题已resolved，详见[问题及真实核销](../../issues/2026-10-10-win7-native-read-pressure-timeout/issue.md)。压后16GET/导出、5000task四数量字段/业务事实、6partial、342链节点保持；CSV/XLSX各5000×32=160,000格按原scope全列核对。

实际v3页面16入口/15视图/33截图，独立96checks passed；原strict误把试调draft_ref与保存scenario_ref混淆的false保留。压力期间既有值班台局部操作842.9ms且无新增request/API/WebSocket；压后fresh可见截图正常，这不声称压力下完整页面重新加载。原Win7 DOM13场景/119checks/24PNG仍明确为独立合成响应；source-v2/v3的370个前端/静态文件、两个冻结包的11个workbench静态文件已只读逐字节核对完全相同。

SampleOff固定run `20261010T011208682-2580` 4.736s回正式PID2516，12GET核对原控制实体及正式空业务目录保持；SampleOn复用固定run `20261010T011401854-2708` 7.171s回样例PID1556，16GET/数量/目录/历史一致，原样例报告原字节相同、没有新注入。独立小型16-task合法试调全生命周期、真实模板EOF/自动备份及普通停止退出也已完成；六类原触发条件的实际证据类型与限制见[完整原生审计](../../audits/2026-10-10-win7-complex-native-acceptance.md)。

文案派生用户候选149文件/276,591,182B，148非README不变；两ZIP **76,368,182B/CRC0312fe32**、**23,635,469B/CRCfdfa30b9** 均小于80,000,000B，实存大小和CRC已核。最终普通安装run `20261010T011909098-3312` 已complete/exit0、builtin首包14/程序149/首次nouserdata/defaultoff；安装证据4、实际release3。最终目录“Version4”仅表示再次安装，compiled source仍4f、docs404dc，不能冒称native v4编译。

最终新目录独立普通cold-dot run `20261010T012504835-2968` 已passed，总8.368s、正常Start2.624s；新backend2936 born-after-CMD、PATH仅系统目录，实际START /WAIT相对目录停止ERRORLEVEL0、原进程退出/rootbackend0/5957free/正式marker保持，无kill/重试。随后独立强退役run `20261010T012833250-1832` 四个临时Python/构建目录可恢复移动后普通Start1.451s、新PID2784/5957、系统PATH/标准stop0，证明不依赖本轮临时安装环境，不能仅以先前干净PATH代替此步。

新鲜退出采集 `20261010T013527843-4548` 仅自身helper4548、1832 absent、owned APS/Chrome/Python0、formalOff，四旧目录实际directory_exists均false，与退役Move断言相符；独立退役/恢复28checks通过。VM恢复run `20261010T013707772-57380` 已九共享键原值/两个原快照/VMSD字节保持/soft suspended，旧程序与业务不改；首Apply对on/running命名的前置拒绝零mutation，原失败和修后29offlinechecks/真实成功都保留。只核销本任务临时工具/进程和原状态，不声明全机其它Python或用户应用被关闭。

宿主桌面 `C:\Users\lurenxing\Desktop\APS_Win7_交付_20261010` 已实际复制完成，仅含两个ZIP、README.txt、delivery.json、验收记录.txt。再次从两ZIP重建149文件并核对全部CRC/大小，148非README文件与原生v3一致，桌面两ZIP完整读回通过。实际记录见[桌面复制收据](../../../output/delivery-complex-20261010-v3-docfix/desktop-copy-proof.json)。本feature所列原生验收和交付已完成；提交、main整合及远程读回另由root实际执行并记录[Git同步收据](../../../output/win7-complex-20261010/final-git-sync.json)，不在本文填写自引用提交号。

当前通过不等于全部按钮、全部文件家族、域策略/普通域账户、任意更大数据或更慢机器全面覆盖；失败、正常拒绝、fixture及尚未执行项在审计中分别保留。

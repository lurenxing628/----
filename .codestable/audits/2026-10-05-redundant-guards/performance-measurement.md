---
doc_type: audit
audit: 2026-10-05-redundant-guards
created: 2026-10-06
status: completed
scope: 清理前 HEAD 与当前实现的固定业务链及真实浏览器耗时
keywords: [性能测量, 整体提速, 同机对照, SGS, 浏览器]
---

# 清理前后整体性能测量

已测到稳定的净提速：常规代表流程总耗时缩短约 11%–15%，1,000 任务的固定 SGS 流程缩短约 9%；四段真实网页打开/查看流程合计缩短约 6%。主要收益来自启动、采用和试调读写，固定候选生成耗时相近。工艺列表存在约 0.4–0.7 ms 的小幅回退，不能把清理描述成所有操作都同幅度变快。

## 对照范围与方法

- 清理前基线：`b64c1a10903fc30b939e2f7f91284699740212a3`，通过 git archive 导出到独立临时目录。初始审计时工作区干净；后续清理尚未提交，因此该 HEAD 对应全部清理前版本。当前版本为测量时本会话已修复并 review 的 dirty 工作区，不用历史日志耗时充当基线。随后提交前 review 的补修不属于本次计时版本；本报告对应末尾保存的源码快照，没有对补修后最终HEAD重新计时。
- 同一台 Mac（macOS-27.0.1-arm64-arm-64bit）、Python 3.8.10、同一依赖环境；浏览器使用同一个 Chrome109，1440×900，headless。不是 Win7 真机或冻结安装包测量。
- 两版分别使用自己的 Schema、源码、static 与 templates；逻辑种子相同。中等规模 20 批次×5 工序=100 任务，大规模 100 批次×10 工序=1,000 任务；均为 50 设备/50 人员/31 零件/50 物料，数量3、单件工时0.04，明确08:00–16:00班次、固定2026-09-09..25窗口，机器/人员有合法授权。
- 完整服务链：factory 导入及启动 → 设备列表 → 工艺列表 → 排产预检 → 准入预览/接收 → 生成并保存4候选 → 读取候选 → 从候选预检/建立试调 → 保存/重开试调 → 采用预检/正式提交 → 正式计划报表。试调先保存再采用，避免正式计划变化引入额外陈旧判断。
- 常规 `algo_mode=greedy`，每版/每规模7轮；SGS同样greedy、`dispatch_mode=sgs`，每版/每规模5轮。每对交替before/after或after/before，所有计时串行。SGS每候选原生decoder_invocations与evaluated_candidates均8，4候选合计32次，iterations=0/stop_reason=completed；不是因少解码而更快。
- 每一对核对任务工序/资源/起止/来源安排完全相同，报表行数及汇总完全相同，4个候选全部完成。随机引用号、令牌、创建时刻不作为等同性条件，不生成额外哈希。
- 业务阶段使用真实服务、算法、SQLite事务及持久化；建库、造数和test-helper导入不计时，接口网络与JSON开销在浏览器测试中另测。后端启动包含factory导入及create_app_core，不含launcher/端口握手；后端为源码development工厂，浏览器为production工厂+真实managed runtime/请求生命周期。
- 网页计时从navigation performance起点到真实业务DOM出现后两帧，不用networkidle的固定500ms等待；每页新incognito context，无旧查看状态/HTTP缓存混入。两版本服务在浏览器测试后停止，锁文件0。
- 表中为各轮中位数；“耗时减少”=`1−新中位耗时/旧中位耗时`。整体数为定义链路各阶段相加后的中位数，不是局部百分比相加。95%区间为配对bootstrap5000次的样本波动参考。没有用户操作频率权重，不把该代表链路比例外推为整个软件所有使用方式。

## 完整代表流程

| 模式与规模 | 清理前 | 清理后 | 总耗时减少 | 配对95%区间 |
|---|---:|---:|---:|---:|
| 常规 / 100任务 | 1.413s | 1.203s | 14.9% | 9.4%–15.5% |
| 常规 / 1000任务 | 8.330s | 7.439s | 10.7% | 8.4%–12.4% |
| 固定SGS / 100任务 | 1.609s | 1.387s | 13.8% | 0.5%–14.9% |
| 固定SGS / 1000任务 | 12.157s | 11.090s | 8.8% | 7.0%–9.6% |

仅业务链、不含factory启动：常规100任务0.953→0.823s（13.6%），1,000任务7.843→7.065s（9.9%）；SGS1,000任务11.620→10.721s（7.7%）。

## 主要阶段（常规1,000任务）

| 阶段 | 清理前 | 清理后 | 耗时减少 |
|---|---:|---:|---:|
| 后端factory启动 | 473.62ms | 377.52ms | 20.3% |
| 设备列表 | 3.66ms | 2.43ms | 33.6% |
| 工艺列表 | 14.41ms | 14.78ms | -2.5% |
| 候选生成与保存 | 4657.57ms | 4657.27ms | 0.0% |
| 建立试调 | 709.66ms | 527.69ms | 25.6% |
| 保存试调 | 566.18ms | 458.27ms | 19.1% |
| 重开试调 | 109.06ms | 91.65ms | 16.0% |
| 采用预检 | 455.11ms | 237.83ms | 47.7% |
| 采用正式提交 | 573.02ms | 360.05ms | 37.2% |
| 报表读取 | 174.10ms | 168.62ms | 3.1% |

- 大规模采用预检少217 ms、正式提交少213 ms，建立试调少182 ms、保存少108 ms，是整体约0.89秒流程缩短的主要来源；其中业务链本身缩短约0.78秒，其余来自factory启动。
- 常规候选生成4.658→4.657秒，波动区间包含零；SGS候选生成8.536→8.338秒，耗时减少2.3%的区间为−1.3%至3.1%。本次数据不能支持排产核心计算已有稳定明显提速。
- 工艺列表14.41→14.78 ms，慢0.37 ms（2.5%）；中等规模14.39→15.11 ms，慢0.72 ms（5.0%）。该读取回退保留在结果里，不用其它提速掩盖。

## 真实浏览器（1,000任务数据）

| 流程 | 清理前 | 清理后 | 耗时减少 | 配对95%区间 |
|---|---:|---:|---:|---:|
| 打开物料列表 | 356.0ms | 308.3ms | 13.4% | -2.7%–36.0% |
| 打开指定正式计划甘特 | 847.2ms | 812.6ms | 4.1% | 2.0%–5.7% |
| 打开实际甘特，自动选择唯一当前计划 | 995.5ms | 949.2ms | 4.7% | 2.1%–5.3% |
| 打开排产记录并点候选详情 | 587.2ms | 558.8ms | 4.8% | 2.4%–11.6% |
| 以上四段流程合计 | 2778.9ms | 2612.6ms | 6.0% | 3.3%–11.2% |

正式甘特、实际甘特和候选查看的改善约4%–5%，物料页13.4%的估计波动较大，其区间包含零；四段合计改善约6%，区间3.3%–11.2%。每页新context，代表无缓存冷打开，不包含人工思考时间；候选按真实“排产记录→详情”按钮进入，未使用该页面不支持的候选URL定位。接口请求状态全部成功、无页面运行错误。

## 同规模新增记录占用

| 1,000任务、4候选、1试调、1正式计划 | 清理前 | 清理后 | 减少 |
|---|---:|---:|---:|
| SQLite已分配页总量 | 34.38MiB | 29.39MiB | 14.5% |
| 4候选artifact列合计 | 1.83MiB | 0.65MiB | 64.6% |
| 试调snapshot列 | 2.98MiB | 0.12MiB | 95.8% |

snapshot列的95.8%减少是正文转移到永久任务行后的列占用；不是全部试调占用减少95.8%。完整回执和ScenarioRows仍保留。SQLite页总量约14.5%的减少同时包含正文去重和三重复索引退役；不是对已有用户数据库执行VACUUM后测得。

## 交付与证据

- 没有修改产品代码、实际业务库或性能门禁基线，没有提交、推送、打包安装；本轮只增加测量脚本/原始输出及本报告。
- 没有运行完整full-test-debt/final clean gate；这些数据是性能对照结果，不是最终验收证明。没有测文件导入、维护恢复、校准、真实报工更正/撤销、长期滚动响应、墙钟预算improve搜索或Win7真机速度，不能对这些流程签发同一提速比例。
- [环境与方法](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/environment.json)；[结果汇总与区间](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/summary.json)。
- [常规原始轮次](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/backend-raw.json)、[SGS原始轮次](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/sgs-backend-raw.json)、[浏览器原始轮次](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/browser-raw.json)。各轮独立JSON保留安排与报表，stdout/stderr日志同目录。
- 当前被测产品源码增量已保存为 [可恢复快照](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/current-source-delta.tar.gz)，[覆盖/删除路径](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/current-source-delta.json) 用于在清理前 HEAD 底稿上恢复本次代码，避免未来工作区变化使结果无法复算；没有生成源码哈希清单。
- 复跑入口：[业务链脚本](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/measure_backend.py)、[交替编排](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/run_pairs.py)、[浏览器脚本](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/measure_browser.cjs)、[隔离服务编排](/Users/lurenxing/GitHub/----/evidence/2026-10-06-cleanup-performance/run_browser.py)。先从同HEAD导出baseline并生成environment.json中的临时目录，再运行run_pairs；设置APS_PERF_DISPATCH=sgs测固定SGS，最后run_browser。现有临时种子仍可复算，无需打开业务库。

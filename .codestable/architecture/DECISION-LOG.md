---
doc_type: architecture
slug: DECISION-LOG
scope: 项目决定备忘录 —— 从1月到今全程考古出的技术/产品决定，做决定前先查这份，防止跟过去的自己打架
summary: ~386条决定考古结论：脊梁10条从未动摇、166次自我推翻全在"皮"上、骨头一次没动
status: current
created: 2026-06-02
last_reviewed: 2026-06-02
watermark_commit: 65870e47
watermark_date: 2026-06-01
tags: [aps, architecture, decision, memo, archaeology]
depends_on: [ARCHITECTURE, BOUNDARY-CHARTER]
---

# APS 项目决定备忘录

> **这份文档的用途**：你做新决定前先翻一眼，看"这事我过去定过没有、定的是什么"，防止跟过去的自己打架。
> **怎么来的**：2026-06 用多 Agent 对全程 git 历史（含 commit diff）+ 早期 ADR/策划 + CS 期 roadmap 做考古，打捞出从未成文的决定。
> **水位线**：本次覆盖到 commit `65870e47`(2026-06-01)。下次体检从这里增量。
> **如何追加**：新做的决定往对应类别追加一条（最好做的当天记，别等考古）。历史部分不要改（历史不会变）。

---

## 0. 一句话结论（你最该记住的）

**全程 ~386 条决定、166 次自我推翻，但骨头一次没动，皮改了上百次。** 你不是在乱走——你有一套从第一天就没变过的判断标准（单机离线、能简化别上重家伙、不自欺），是它在指挥你不断修正表皮去贴合它。推翻得多不是没方向，是方向太稳。

---

## 1. 🦴 脊梁：从1月扛到现在、一次没动摇的核心决定（代码逐条核实仍成立）

这 10 条是项目的承重墙。**改动任何一条都是"动地基"级的大决定，必须极度谨慎、且回来改这份文档。**

1. **Win7 SP1 x64 离线单机交付**是最硬约束：Python 3.8 + Flask2.3.3/Werkzeug2.3.7/openpyxl3.0.10/dateutil2.8.2 + PyInstaller4.10。不引 CDN/外链/外部前端框架，不破坏 Py3.8/Win7/Chrome109。（requirements.txt 至今原样、无 pandas）
2. **四层分层架构**：web/routes→core/services→data/repositories→core/models + core/infrastructure，层间单向调用、超500行拆分。（六个分层目录原样存在，AST 全量 0 违规）
3. **openpyxl-only、对外只用 List[Dict]/普通 dict/标量**：不让 DataFrame/nx.Graph 等流到对外层。
4. **双重资源约束贪心排产**（设备+人员两条时间线）+ 可插拔算法/四种排序策略，是排产大脑，从未被替换。NetworkX 上线也死守"只做诊断体检、不当第二个排产大脑"。
5. **SchemaVersion 轻量迁移、不上 Alembic**：迁移脚本手写到了 v17，全是顺序递增轻量脚本。
6. **batch_id 作为核心业务标识**，跨页定位优先用批次/设备/人员/日期，而非内部技术 id。
7. **事务规范**（TransactionManager + @transactional）+ **统一错误码**（ErrorCode/AppError + {success,data/error,meta}）+ **OperationLogs/ScheduleHistory 留痕**。
8. **🌟"坏数据不准静默兜底、宁可暴露错误也不自欺"**——这是项目的灵魂暗线，从4月底立原则后只增不减，到6月连首页"读取失败返回空列表"都禁掉改成显式数据缺口卡。**这是越扎越深、从未回头的价值观主线，是这个项目真正的性格。**
9. **Excel 整批拒绝**：任一 ERROR 整批退回、中文精确到行号字段、预览→确认两步。
10. **Frappe Gantt 本地静态资源、不上 CDN、不替换**：只在外面加适配层。

---

## 2. 各类别核心决定（做相关功能前查对应类别）

> 完整 386 条原始记录在 `.codestable/audits/2026-06-01-foundation-maturity/codemap/all_decisions_merged.json`，这里是提炼。

### 错误处理（57条）—— 全项目最大的一类，核心是"不自欺"
- 消除静默回退全栈运动：服务层碰坏值不再静默 return 默认/pass，统一发 DegradationEvent + 脏字段/计数，路由 consume 后页面横幅显示给用户。
- strict_mode 严格模式贯穿工艺解析/排产/导入：开启后未配工种/找不到供应商/默认天数异常一律报错而非降级，用户可在 Excel 导入页勾选。
- 统一 parse_int/parse_float 安全解析（拒绝 int('1.0')/bool当int/NaN/Inf）。
- 统一"静默吞异常"治理：fallback_log/safe_log（logger坏了也能 print stderr），全面消除 except:pass。
- 排产与评估链路全面收敛 NaN/Inf（派工评分/效率重算/to_dict JSON 序列化/零时长工序）。
- 非法时间参数显式抛 ValidationError 不再静默回退；冻结窗口/停机日历加载异常输出可见 warnings + degraded 标记。

### 架构分层（55条）—— 见脊梁第2条，外加这些落地动作
- TransactionManager 分层事务：最外层自有事务用显式 BEGIN/COMMIT，仅嵌套层才用 SAVEPOINT。（注：此为推翻早期"全用SAVEPOINT"后的现状）
- 集中化枚举归一化：各处内联 → enum_normalizers → 最终收敛到 normalization_matrix 唯一源。
- 公共解析层下沉 core/shared（field_parse/strict_parse/compat_parse/degradation/number_utils）。
- 启动链抽到 web/bootstrap；RequestServices 服务管家（cached_property 懒加载、同请求复用）。
- SP05 目录拓扑重构：scheduler 拆 config/run/summary/batch/dispatch/gantt/calendar 子包，用契约测试钉死拓扑。

### UI产品（55条）
- 报表默认时间窗用所选排产版本的实际排程范围，弃用"最近7天"；导出未指定 version 默认 latest。
- 全站用户可见文案统一通俗中文、保留枚举/接口参数不变（"权重混合"对用户改"综合优先级和交期"）。
- 前端 JS 模块化拆分；静态资源 URL 自动版本参数（按 mtime/hash）。
- 页面级说明书体系（ViewModel 层 page_manuals_* 数据驱动）。
- **甘特图定为只读可信查看页，关掉假拖动**（见边界 S3）。

### 算法策略（53条）
- 优先级语义集中到 priority_constants：RANK/WEIGHT/SCORE 三套映射 + normalize_priority。
- auto_assign 去掉"全设备兜底"：缺工种映射宁可失败也不退化为所有可用设备（排错机比明确失败更危险）。
- enforce_ready 三态：未传=None(按默认回退)/勾选=True/关闭=False。
- OR-Tools warm-start 整体 try"失败即降级"，过滤 NaN/Inf，允许 due_min 为负保留逾期紧迫度。
- **齐套 readiness 默认关闭**（5月初重大产品转向，见自我推翻 #2）。

### 数据建模（44条）
- ScheduleVersionSeq 序列表原子分配版本号，弃用 MAX(version)+1（并发会复用版本号混写）。
- 裸字符串枚举收敛到两个源：业务层 enums.py、算法层 value_domains.py（算法层不 import core.services）。
- 启动自动补表补索引 ensure_all_tables_exist：对比 schema.sql 与实库缺啥补啥。
- 车间执行事件 OperationExecutionEvents 只追加事实表 + 状态聚合，计划行与现场事实分离（v15）。

### 部署交付（23条）
- **安装模型 per-user → 机器级共享数据**（程序装 Program Files、数据迁 ProgramData/APS/shared-data + 运行时单活锁）。这是早期"单机单用户"的修订。
- 运行环境按 sys.frozen 判定（打包=production关reloader、源码=development）。
- 端口策略 APS_PORT>5000 优先，绑定失败自动选端口写 portfile；APS_HOST 仅 IPv4。
- Win7 双包打包：APS_Main_Setup（主程序小包）+ APS_Chrome109_Runtime（仅首次）。
- SECRET_KEY 去弱默认，改运行时确保（环境变量>持久化文件>强随机）。

### 测试门禁（33条）
- 架构适应度门禁（AST 守不变量）：Route 禁直连SQL/禁import Repository、Service 禁import flask.request、禁循环依赖、禁assert。
- 技术债治理台账作为质量门禁单一事实源（FILE_SIZE_LIMIT=500/COMPLEXITY_THRESHOLD=15）。
- 一键质量门禁 scripts/run_quality_gate.py + GitHub Actions(windows + Py3.8)。
- conftest.py 让 main() 入口的 regression_*.py 被 pytest 自动发现。

### 依赖选型（11条）
- 10 份 ADR 固化早期长期约束（见脊梁）。
- 插件能力冲突 first_loaded_wins（先注册者胜）。⚠️注意：见第4节，这条的 commit message 当年写反了。

---

## 3. ⟲ 自我推翻索引：你跟过去的自己打过的架（166次，这是最关键的几次）

**重要认知：每次推翻都朝同一方向（更简单/更不自欺/更贴现场）修正，不是来回摇摆。** 推翻不是错误，是修正。

1. **[1月] 定稿即推翻自己更早草案**：pandas+DataFrame → openpyxl-only；整套 ResourceLock 并发表 → 删掉靠事务管理；布尔字段 → 字符串枚举；后台定时备份 → 退出时备份。（从一开始就有"能简化就简化"的判断标准）
2. **[5月初] 齐套从"默认硬门槛"翻成"默认关闭"**：现场实际是计调员只排齐套的，默认开会误卡。重大产品判断转向。
3. **[5月底] 车间反馈从"实时按钮+反馈人必填+取浏览器时间" → "填实际情况+Excel导入+反馈人可空+时间可手填"**：现场根本没接 MES/DNC。最大一次产品反转。
4. **[5月底] 甘特假拖动 → 真只读**：假拖动会骗调度员"以为改了计划"。
5. **[5月底] 多方案对比一度让所有图模式都跑 → 回滚为仅显式开关打开才跑**：门禁报了15个失败，机制替你拦住方向跑偏。
6. **[2-4月] 事务模型 全SAVEPOINT → 最外层显式BEGIN**：最外层SAVEPOINT在RELEASE后事务已提交、再失败来不及回滚。
7. **[6月] "抽独立现场记录页+新路由" → "同页内分层+只拆JS"**：6个对抗评审 Agent 认定范围过大、证据不足。
8. **[4月底] AI 协作入口 superpowers/.limcode → CodeStable**。

> 完整推翻清单见 `docs/项目演进时间线.html`（⟲自我推翻 标签）。

---

## 4. ⚠️ 仍与现状矛盾的决定（该顺手清的陈词，全是文档/配置层，不碰业务代码）

386 条里真正"还在和现状打架"的只有这几条：

1. **文档大重组决定已失效**：当年决定"删《实现计划表》《开发文档》《系统速查表》合并为单一1937行大文档"，但这三份现在都还在且在改，单一大文档不存在（后来又拆回 8 个 V1.2 子文档）。→ 该更新或删除这条决定记录。
2. **AGENTS.md 关于 .cursor 的描述过期**：写"`.cursor` 仅作旧宿主兼容层保留"，但 `.windsurf` 和 `.cursor` 两个目录现在都已不存在，只剩 `.codestable` + `.limcode`。→ 该删 AGENTS.md 那句。
3. **🐛 插件能力冲突策略 message 与代码长期对不上**：当年 commit message 写"冲突时选后注册的(last-wins)"，但代码实际是 `first_loaded_wins`（先注册者胜）。→ message 写反了，代码是对的，该确认代码意图并修正记录。
4. **边界总册条数口径需澄清**：BOUNDARY-CHARTER 自述"31条"，实为 D1-5+L1-10+S1-7+C1-10+R1-7 共约39条。→ 已知，澄清即可。

---

## 5. 变更日志
- 2026-06-02：首次建立。多 Agent 全程考古（早期ADR+策划/中段git diff/CS期roadmap/后期417提交），打捞 ~386 条决定、166 次推翻、10 条脊梁。水位线 commit 65870e47。

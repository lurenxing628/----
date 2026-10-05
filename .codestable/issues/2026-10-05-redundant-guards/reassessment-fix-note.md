---
doc_type: issue-fix-note
issue: 2026-10-05-redundant-guards
created: 2026-10-05
status: fixed
review: completed
verification: targeted-review-and-daily-stage-complement-passed
---

# 未修项复判后的修复与 review

用户授权：此前“留档，然后该修的修”，本轮“该修的修，该 review 的 review”。本记录对应 [38组复判](../../audits/2026-10-05-redundant-guards/unfixed-reassessment.md)，第一阶段结果仍保存在原 fix-note，不改写旧失败或历史验收。

## 落地结果

35组落实修复，3组经真实职责 review 保留；另修3项既有启动门禁问题及明确的 TRIM 清洗 bug。混合组只删除无用途部分，不把整组必要保护一并删除。

| 编号 | 当前实现及保留职责 |
|---|---|
| 1.2 | 看板单条绑定自身完整来源、身份、评估状态及处置修订；补齐原始需求/复核/未来到料、交付工序、停机无效/取消记录、报工全部历史。集合仍绑定全看板。 |
| 1.3 / 4.3 | 单工序绑定自身完整 reports/voids/legacy/unresolved、当前任务/计划及旧来源；其他工序报工不误失效，前道/资源/合并约束仍在写锁内检查。find/get 共用已有 header。 |
| 1.4 | 资源创建只绑定该种类的关系集合及 ref/revision/班次 pattern；物料及无关系创建不计算空状态摘要。作用域、动作、期限和锁内唯一性继续检查。两个列表入口同一机制。 |
| 1.5 / 7.6 / 7.3 | 坏采用历史只显示局部恢复，合法结果仍可见；同页偏好4读→2读，跨tab重读、合并、readback、失败重试保留；每请求根目录只resolve一次，逐目标逃逸/存在检查保留。 |
| 2.6 / 2.7 | trial存档一次lossless编码供应文本/持久摘要；change回读最新head/current/行数，复用同事务已经验证且trigger禁止修改的immutable档案；首create完整回读保留。双方hash仅为相等的入口使用canonical same，类型语义不变。 |
| 3.2 / 3.3 / 10.1 | 当前版本启动事务中检查一次；同次结构事实供子合同消费，独立入口仍现读，不跨DDL缓存；去重复plan身份/clock检查；schema解析缓存直接文本key、最多8项。 |
| 3.4 / 10.8 / TRIM bug | 新v38删除三个被完整PK/UNIQUE覆盖的索引，核对列、顺序、Collation和真实约束来源；schema由实际迁移链生成。修v4漏纯空格，并前向仅清合法小写枚举；未知值/NULL/停用说明保留。v37末尾FK与整体回滚保留，v8仅真变化写，v4无日志不取弃用样例。 |
| 4.13 / 4.10 / 10.5 | 删除无消费template probe；公开缺零件错误优先级和事务内当前模板核验保留。旧路线解析复用一次预处理和同一SQL快照工种索引；注入仓储失败诊断保留。字段严格解析失败只解析原值一次，policy/原因码/fallback合法性不变。 |
| 4.5 / 4.9 / 4.12 / 6.3 | 系统配置写后只省弃用摘要，仍新读保存值；工艺、日历、物料/资源HTTP及导入内部写入口复用写锁中已检查的完整事实。公开独立入口自核、业务写后签名及结果读、关联多行影响仍检查。 |
| 5.3 / 5.6 | 子需求真变化仍committed，父齐套真变化才UPDATE；ledger渲染同内容免写，所有现行写入口共用。 |
| 6.1 / 6.5 | 资源、物料、工艺、报工、批次、人员设备权限、日历范围共用原preview token/实际expiry。先取服务器原预览并核操作，再核确认引用；当前proposal/范围/写入stamp与receipt先行重放保留。报工首次BG-X摘要和解码仍执行，确认复用同一留存source。 |
| 8.6 / 8.8 | 新proof schema3取消6个自摘要及receipt完整命令自摘要，完整权威对象、实际receipt文件/日志/输出/缓存身份仍核。schema2原规则可读，不允许旧源码证明适用新状态。single-ref复用已准备scope，子进程仍刷新dirty范围。 |
| 9.3 / 9.5 | 删除无依据100文件下限，保留写目标前7za t、解压x、逐文件摘要/长度/实际数量、禁止userdata及唯一launcher。portable只消费onedir已投放launcher，不再有第二写入者。 |
| 10.2 / 10.3 / 10.4 / 10.7 | 不计算无consumer延期诊断指纹、stdout来源字段及vendor第二摘要；恢复终态不依赖诊断整库读取，nullable/历史值兼容。rollback同父目录隔离写一次、只读验证并关闭后原子替换；坏源不动目标、WAL隔离、链接拒绝及锁重试保留。 |
| 10.6 / 10.9 | 删除未定义Suppliers/ExternalGroups.updated_at的猜列分支；时间UDF只由五类真实使用仓储注册，派生及plainconn保持。设备新增不可达判空删，维护tuple2/4解包共用真实协议。 |

三项review保留：4.1没有当前web旧事件写caller，旧start/pause/resume语义不能强行转成新数量报工；4.2最终采用投影有新的datetime.now，影响未来旧事件合法性和state revision，不能用准备阶段投影直接跳过；9.2固定环境、来源冻结及实际import分别证明不同事实。

## review发现并收口

- preview token共用后，preview_ref成为可写凭证。前端pending只保存回执查询所需key/kind/action及实际恢复需要的永久实体/date引用；不落盘32字符预览引用，旧记录实际清理，清理失败仍lookup原key而不重发。未恢复双token。
- 报工文件有“锁外预取→等写锁”真实时间边界：共同预览在写锁guard再次核live期限，随后核确认引用；这一次内存登记检查有独立职责，不重新解析、计算SHA或重建proposal。故障注入确认原遗漏会过期后committed，新实现零写入拒绝；期限/replay/首次parse和锁外复用4节点通过。
- 人员设备公开入口曾在自己的事务前读取关联，再在写锁后复用，可能漏清另一连接新主操。现在读取、规范化、清其他主操及更新在同一事务内，真实两连接回归通过。
- 旧concrete RouteParser捕获工种和供应商改为真实读事务，同次调用不会被当成冻结事实；注入仓储原语义保留。
- v38零行UPDATE也会经编译的AUTOINCREMENT trigger初始化sqlite_sequence。前向清洗先确认目标行才写；该保护有已复现用途。索引未知替换/Collation差异仍拒绝清理。
- 新复杂度按实际职责拆分；启动共享candidate_ports公开，监听失败继续日志/退出16/finally清理并精确登记，未扩大复杂度/私有导入白名单。
- 静态类型问题用已有返回保证、NoReturn及真实callback/数值/日期类型表达，未加入运行时判空兜底或关闭检查。

## 验证

不同批次有交集，下表不相加冒充独立总量。单独的schema、raw-source和故障计数均使用隔离SQLite/内存材料。

| 范围 | 有效结果 |
|---|---|
| root共用预览/create scope | 224 passed；guarded CRUD及process collection80 passed，3个旧registry测试替身改为真实共用引用/操作/期限后相关8 passed。 |
| schema | 356 passed；最后坏schema/身份168 passed，v38新增语义/回滚及职责拆分定点通过；生成schema --check通过。 |
| dashboard | 10新增scope回归、65命令/历史/原子及26来源读取回归通过。 |
| execution / trial | execution115个不同用例覆盖，含前道fresh约束和错误preview引用；trial105 passed，archive编码/权威回读和类型比较通过。 |
| domain / legacy | 工艺/个人日历/维护161 passed，物料资源172有效passed，catalog61有效passed及人员设备最终13 passed；parser最后64+3通过。独立对照456数值、128路线样本无差异，五UDF职责及4派生plainconn核验通过。 |
| restore / gate / delivery | restore相关75 passed；工具269 passed及新旧schema2补验；portable/integrity21 passed/1 Windows PowerShell解析skip。bootstrap57 passed/5 Windows原生socketskip。token漏入口151有效passed+2定点补验。 |
| 前端/真实浏览器 | Chrome109：真实Flask/隔离SQLite history28行为/4变体；组件mock resource204cases/4变体、process52cases/4变体；transport641检查，pending清理失败/F5 lookup/零重发通过。最新build为chrome109/276files，最新5个static/transport/边界目标通过。 |
| 最终静态 | 最后architecture/CodeStable/boundary三文件37 passed；主链Pyright以Windows目标检查0errors，宿主tools Pyright0errors，最后报工期限接线scoped Pyright0errors。全仓Ruff与diff-check通过。主链使用产品目标Windows类型平台，宿主tools使用当前macOS平台；检查配置没有关闭规则。 |
| 统一daily | 642目标的parallel初跑11876 passed /14 failed /1 skipped，653.30s；14失败逐条定位修正后，根代理最终同批14 passed、12.43s。serial补齐984 passed、209.00s；focused初次5 passed/2 failed（测试假路径及文档债务已还未减清单），修正后最终7 passed、4.01s。原统一命令退出1记录保留，交付的是有效通过项复用+失败补验+剩余阶段补齐，没有再跑第二次完整daily命令。 |

根目录原始日志和已有浏览器输出保存于 `evidence/2026-10-05-redundant-guards/`，本轮以 `reassessment-*` 命名；浏览器JSON及代表截图留在 `reassessment-browser/`。不复制浏览器夹具数据库/启动凭据，不重生成历史指纹。

## 交付边界

已同步现行DB模型/数据库速查及延期诊断合同，第一阶段记录与历史验收原样保留。未提交、推送或发布；未迁移/恢复实际业务库，未执行Windows7原机安装和完整final clean gate。当前dirty工作区保留供审阅，不能声明clean proof。

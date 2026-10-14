---
doc_type: feature-contract
feature: decision-integration-acceptance
status: in_progress
created: 2026-10-14
summary: 原内容、永久来源及历史摘要的共同职责
---

## 原内容与身份

`core/models/content.py`统一可逆编码及严格比较。BLOB、非有限REAL、日期与普通字典分开，字面类型标记字典使用escape；True、1、1.0保留各自类型。SQLite事实仓储通过原存储类型读取，避免DATE转换器使同一事实在主连接与worker备份连接中表示不同。

| 职责 | 现行来源与比较 | 历史处理 |
| --- | --- | --- |
| 普通命令回放 | request_key、action、context_ref及完整input_json；原事务保存结果 | 原回执查询保持；已知run/trial/采用可从原归档精确恢复意图；原意图缺失返回command_original_input_missing，领域guard和mutation尚未执行 |
| run/trial事实 | 完整归档原文、永久工序身份、真实Schema及业务值 | v39/v40按各自DDL，仅投影已知技术变化；未知结构及真实变化保留；旧摘要原值不重算 |
| 采用与正式基准 | 不可变来源、run/baseline/version与scenario revision；确认事务重新核对实际事实、执行和覆盖 | 旧proof按实际来源恢复；原永久引用、回执、archive与行内容不改写 |
| 读取与写入上下文 | 私有完整scope与snapshot一次编码，随机opaque token、动作、对象、TTL及事务 | 公开token格式与授权职责保持；内容不替代授权令牌 |
| 执行与工艺 | 完整原状态、真实修订、来源、计划/任务身份及原确认内容 | 新摘要列写NULL；原确认记录缺原内容时重新明确确认，不猜造旧事实 |
| 导入与恢复 | 原文件bytes、解析行、一次source identity；恢复元数据、原bytes与SQLite完整性 | 旧文件、业务编号和journal原件保留；缺原意图或来源路径返回明确缺项 |
| 优化缓存与去重 | 原安排、配置、完整内容、来源版本和实际scope | 原计数、预算、cache边界与算法行为保持 |
| 门禁与交付 | shared v4、long v2保存完整来源、日志、receipt、命令及环境；ZIP完整性及实际离线启动 | 旧证据留原路径；缺完整内容的旧缓存miss；Git和第三方分发的原版本寻址保持 |

## 实际边界

历史候选执行投影按既有单块上限恢复后核对全集合，允许已保存的20,000工序历史读取；真实AJ读取与worker快照回放仍沿现有10,000上限。20,000来源的性能证据明确记录为受控合法保存来源，由实际评分、选优、保存及HTTP路由执行，算法搜索与生产受理未执行。

本项目的产品、宿主脚本、测试helper、Windows启动器和workflow统一移除主动密码哈希计算。离线材料按固定来源、文件路径、普通文件类型和尺寸核对；React依赖按固定包身份、版本、许可证及上游integrity原值核对，现有目标文件直接比较原bytes。Git既有对象ID、上游元数据和历史摘要字符串保留原值。CI使用已有commit/run身份定位候选缓存，仓库内缓存仍比较完整原内容和真实环境。

剩余脚本、CI及helper按`remaining-content-cleanup-instructions.md`第2—4节完成定点验证。第6节Jev宿主缓存已改用完整原请求JSON等值读写，替代HTTP本地验证通过；第7节原19份宿主脚本及5份直接消费者已完成原bytes、带类型行、AST原文和完整语料判等，24份现行源的主动密码学调用为0。旧语料编号、历史原件和冻结源码保持。行为回执与最终源码核对在`evidence/decision-integration-acceptance/2026-10-14/source-regressions/`；第8完整门禁待最终界面和性能源冻结。

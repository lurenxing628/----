# FrozenContract（core P0/P1 修复期）

- **TransactionManager.transaction()**：必须支持嵌套；内层失败仅回滚内层，外层仍可继续；外层失败回滚整体；禁止出现“内层 commit 使外层 rollback 失效”。
- **in_transaction_context(conn)**：在任意 `TransactionManager.transaction()` 上下文内必须返回 True（供 `OperationLogger` 禁止隐式 commit）。
- **parse_dispatch_rule(value)**：对字符串输入做大小写/空白容错（例如 `"CR"`, `" atc "`），解析失败才回退默认。
- **build_dispatch_key()**：key 越小越优先；`priority` 大小写不敏感；当 `proc_hours<=0` 时不得制造 ATC/CR 极端值（避免把不可估算候选排到最前）。
- **dispatch_sgs()**：对缺资源/不可估算候选必须惩罚排序（先按可估算性，再按派工 key），避免在 ATC/CR 下被优先选择；排序需稳定可复现。
- **v4 migration**：对枚举/状态类文本字段做 `TRIM+LOWER`，对 NULL/空串写默认值；幂等可重复执行；新增清洗项不得破坏既有回归用例语义。


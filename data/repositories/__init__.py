"""
数据访问层（Repositories）。

约束：
- V1 不引入 ORM；统一使用 sqlite3 + repository 封装
- 服务层（core/services）应只依赖 repo，不直接写 SQL
- 包根不重导出：调用方按模块导入，如 ``from data.repositories.machine_repo import MachineRepository``
"""

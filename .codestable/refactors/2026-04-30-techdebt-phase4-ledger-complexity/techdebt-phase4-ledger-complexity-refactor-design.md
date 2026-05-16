---
doc_type: refactor-design
refactor: 2026-04-30-techdebt-phase4-ledger-complexity
status: approved
scope: 阶段 4 技术债台账 open oversize / complexity 项。
summary: 按小闭环拆分超长文件和高复杂度函数，每批保持 public API、导入路径和业务行为不变。
tags: [techdebt, oversize, complexity, quality-gate]
---

# techdebt phase4 ledger complexity refactor design

## 1. 本次范围

- S1：scheduler summary 拆分。
- S2：scheduler config field spec 拆分。
- S3：基础设施事务、备份、迁移、数据库入口拆分。
- S4：报表、单元 Excel、工艺路线、零件服务拆分。
- S5：人员详情、排产日历 Excel、系统备份路由拆分。

## 2. 前置依赖

- 使用 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python`。
- 第一笔提交必须先记录 `audit/2026-05/phase4_phase5_baseline.txt`。
- 每批先跑当前相关测试；若测试在改代码前失败，先停线说明。
- 所有台账更新必须通过 `scripts/sync_debt_ledger.py`。

## 3. 执行顺序

- 步骤 1：拆 scheduler summary。
  - 方法：Facade + Extract Module。
  - 操作：先抽 size guard，再抽 runtime/warning state。
  - 退出信号：summary/config 相关测试、ruff、pyright、full-test-debt、台账检查通过。
  - 回滚：回退本步骤提交。
- 步骤 2：拆 config field spec。
  - 方法：Facade + Extract Module。
  - 操作：抽字段校验和兼容读取，不拆字段注册表。
  - 退出信号：配置字段合同、快照同步、配置服务组件测试通过。
  - 回滚：回退本步骤提交。
- 步骤 3：拆基础设施。
  - 方法：Characterization Test + Extract Helper + Facade。
  - 操作：按 transaction、backup、v4 sanitizer、database 顺序推进。
  - 退出信号：迁移、备份、事务测试通过。
  - 回滚：回退本步骤提交。
- 步骤 4：拆业务服务。
  - 方法：Extract Pure Function + Facade。
  - 操作：按 report、unit_excel、route_parser、part_service 推进。
  - 退出信号：报表、Excel、工艺路线、零件服务测试通过。
  - 回滚：回退本步骤提交。
- 步骤 5：拆具体路由。
  - 方法：Move ViewModel / Route Thin Controller。
  - 操作：只拆本阶段触达的人员、排产日历 Excel、系统备份路由。
  - 退出信号：路由合同、页面烟测和门禁通过。
  - 回滚：回退本步骤提交。
- 步骤 6：刷新台账并对抗审查。
  - 方法：Controlled Ledger Refresh + Subagent Review。
  - 操作：只关闭扫描证明已达标的条目。
  - 退出信号：对抗审查无阻断，clean quality gate 通过。

## 4. 风险与停止线

- public API、导入路径、返回字段或用户可见文案需要变化时，停止。
- 出现新的静默吞错、宽泛 fallback、无解释默认值时，停止。
- 台账 refresh 影响无关条目时，停止。
- `tools/check_full_test_debt.py` 结果异常时，停止。
- clean gate 后工作区变脏时，不能宣称 clean proof。

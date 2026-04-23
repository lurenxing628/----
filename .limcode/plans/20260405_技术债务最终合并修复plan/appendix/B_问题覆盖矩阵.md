# 附录 B：问题覆盖矩阵

> 本附录只做覆盖关系与交叉索引，不替代各子 plan 的完成判定。执行时请回到对应子 plan 正文查看范围、步骤与最小验证命令。

## 一、原总 plan 问题覆盖矩阵

| 问题 | 对应子 plan |
| --- | --- |
| `A1` | `SP05` |
| `A2` | `SP06` |
| `A3` | `SP08` |
| `A4` | `SP08` |
| `A5` | `SP04`、`SP07` |
| `A6` | `SP07` |
| `A7` | `SP07` |
| `B1` | `SP08` |
| `B2` | `SP08` |
| `B3` | `SP08` |
| `B4` | `SP08` |
| `C1` | `SP05` |
| `C2` | `SP09` |
| `C3` | `SP09` |
| `C4` | `SP09` |
| `C5` | `SP09` |
| `C6` | `SP04` |
| `C7` | `SP02`、`SP03` |
| `D1` | `SP10` |
| `D2` | `SP10` |
| `D3` | `SP01`、`SP10` |
| `D4` | `SP02` |
| `E1` | `SP01`、`SP10` |
| `E2` | `SP10` |
| `E3` | `SP10` |
| `E4` | `SP10` |
| `E5` | `SP10` |
| `E6` | `SP09` |
| `F1` | `SP01`、`SP09`、`SP10` |
| `F2` | `SP05` |
| `F3` | `SP08` |
| `F4` | `SP06` |
| `F5` | `SP08`、`SP09`、`SP10` |
| `F6` | `SP05` |
| `F7` | `SP07` |
| `F8` | `SP07` |
| `F9` | `SP03` |
| `post-task3-path-drift` | `SP05`、`SP06`、`SP07`、`SP08`、`SP09`、`SP10` |
| `silent-fallback-governance-gap` | `SP02`、`SP03`、`SP09` |
| `number-utils-root-ownership` | `SP05` |
| `persist-schedule-keyword-count` | `SP07` |
| `ruff-version-lock` | `SP01`、`SP02` |
| `tests-glob-verification` | `SP01`、`SP10` |
| `open-db-silent-fallback-detail` | `SP03` |
| `request-services-maintenance-order` | `SP04` |
| `config-service-cross-task-ordering` | `SP04`、`SP06` |
| `system-inline-noqa-gating` | `SP05` |
| `path-sensitive-test-drift` | `SP05`、`SP10` |
| `optimizer-outcome-bridge` | `SP07` |
| `best-none-ownership` | `SP07`、`SP08` |
| `task5-delayed-import-decision` | `SP07` |
| `batchforsort-boundary` | `SP08` |
| `template-missing-regression` | `SP07` |
| `nested-test-gate-ordering` | `SP01`、`SP09`、`SP10` |

## 二、后续 review 补充问题映射

| 问题 | 对应子 plan / 处理方式 |
| --- | --- |
| `bootstrap-silent-fallback-scope-gap` | `SP02`、`SP03` |
| `ruff-hook-version-drift` | `SP01`、`SP02` |
| `governance-ledger-schema-gap` | `SP02` |
| `batch1-structure-churn-too-heavy` | `SP05`、`SP08`、`SP09` |
| `review-f1-gantt-critical-chain-edge-naming` | `SP08` |
| `review-f2-schedule-optimizer-steps-cfg-value` | `SP06` |
| `review-f3-f401-dedup-strategy` | `SP05` |
| `review-f4-direct-assembly-search-scope` | `SP04` |
| `review-f5-excel-demo-root-retention` | `SP05`（接受风险） |
| `review-f6-greedy-schedule-line-count` | `SP08` |
| `review-f7-schedule-run-input-field-ownership` | `SP07` |
| `review-f8-static-asset-version-strategy` | `SP09` |
| `review-f9-close-db-whitelist-entry` | `SP03` |
| `review-f10-task2-task3-import-ordering` | `SP04`、`SP05` |
| `review-f11-silent-fallback-empty-collection-patterns` | `SP02`、`SP03`、`SP08`、`SP09` |
| `review-f12-tests-glob-recursive-coverage` | `SP01`、`SP10` |
| `review-f13-metrics-best-metrics-mapping` | `SP07` |
| `review-f14-root-facade-import-path` | `SP05` |
| `review-f15-radon-dev-dependency` | `SP01` |
| `F-ui-mode-py-直接装配未纳入任务-2-收口范围` | `SP04`、`SP09` |
| `F-f401-全局忽略移除需前置评估影响面` | `SP05` |
| `F-maintainability-4` | `SP03` |
| `F-maintainability-2` | `SP03`、`SP08` |
| `bootstrap-governance-scope-still-incomplete` | `SP02`、`SP03` |
| `config-sss-misses-summary-readers` | `SP06` |
| `gantt-service-fallback-whitelist-unassigned` | `SP08` |
| `excel-pageflow-pilot-validation-misses-route-tests` | `SP09` |
| `task9-misses-ui-contract-gates` | `SP10` |
| `doc-path-drift-lacks-automated-validation` | `SP10` |
| `架构门禁扫描范围不含 web/bootstrap` | `SP02` |
| `factory.py:_is_exit_backup_enabled / _run_exit_backup 台账遗漏` | `SP02`、`SP03` |
| `factory.py:_open_db / _close_db / _perf_headers 样本命中需实测验证` | `SP02`、`SP03` |
| `任务 2 缺少维护窗口场景下 g.services 不存在的守卫要求` | `SP04` |
| `任务 5 内部步骤顺序依赖未显式声明` | `SP07` |
| `_parse_date` 非严格模式替代策略缺失 | `SP08` |
| `_parse_datetime` 应复用 python-dateutil | `SP08` |
| `task1-bootstrap-regression-gap` | `SP02`、`SP03` |
| `task3-domain-facade-ordering-conflict` | `SP05`、`SP09` |
| `task4-config-ui-second-source` | `SP06` |
| `task8-dom-protocol-exit-gap` | `SP09` |
| `F-test-1` | `SP06` |
| `F-任务-3-与任务-7-8-延迟迁移之间存在导入路径中间态风险` | `SP05`、`SP08`、`SP09` |
| `F-test-4` | `SP04` |
| `F-maintainability-5` | `SP07` |
| `F-javascript-6` | `SP08`（BUG 修复） |
| `F-maintainability-7` | `SP07` |
| `F-performance-8` | `SP08` |
| `task2-schedule-service-blast-radius` | `SP04` |
| `task1-factory-sample-points-not-cleared` | `SP03` |
| `task4-cfg-choices-second-source` | `SP06` |
| `task7-8-arch-whitelist-path-drift` | `SP08`、`SP09`、`SP10` |
| `F-other-1` | `SP07` |
| `F-other-2` | `SP07` |
| `F-other-3` | `SP06` |
| `F-other-4` | `SP07` |
| `F-other-5` | `SP03` |
| `F-other-6` | `SP08` |
| `F-other-7` | `SP06` |
| `F-other-8` | `SP07` |
| `F-other-9` | `SP08` |
| `F-other-10` | `SP07` |
| `F-other-11` | `SP07` |
| `sp06-holiday-default-efficiency-full-chain` | `SP06` |
| `sp06-config-service-get-default-escape-hatch` | `SP06` |
| `sp06-page-metadata-shape-drift` | `SP06` |
| `sp06-objective-score-summary-label-drift` | `SP06` |
| `sp06-error-field-label-second-source` | `SP06` |
| `sp06-raw-cfg-fallback-contract` | `SP06` |
| `F-plan-文档体量已超-3-万字-缺少执行者快速定位索引` | 本次拆分后的索引版主 plan |

## 三、使用说明

1. 看到某个问题编号时，先在本附录找到主归属子 plan。
2. 真正执行时回到对应子 plan 正文，不要直接拿本附录当执行底稿。
3. 若问题跨多个子 plan，先以最靠前的依赖子 plan 为主，再看后续承接子 plan 的联动更新说明。

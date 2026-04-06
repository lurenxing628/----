# 排产性能画像报告

- 生成时间：2026-03-16 02:11:04
- 项目根目录：`D:/Github/APS Test`
- Profile 目录：`D:/Github/APS Test/audit/2026-03/20260316_perf_profile_artifacts`

## smoke_phase7

- 命令：`D:\py3.8\python.exe -m cProfile -o D:\Github\APS Test\audit\2026-03\20260316_perf_profile_artifacts\smoke_phase7.prof tests/smoke_phase7.py`
- 退出码：0
- 墙钟耗时：2.258s
- cProfile 总 self time：2.064991s

| 指标 | calls | self_s | cum_s |
|------|-------|--------|-------|
| dispatch_sgs | 24 | 0.002014 | 0.009774 |
| calendar_add_working_hours | 1341 | 0.003608 | 0.021385 |
| calendar_adjust_to_working_time | 2841 | 0.002920 | 0.021706 |
| auto_assign_internal_resources | 0 | 0.000000 | 0.000000 |
| build_dispatch_key | 144 | 0.000439 | 0.000967 |

Top 热点（按 cum_s）:
- `__init__.py:<module>:1`：calls=1 self=0.000025s cum=1.181200s
- `resource_dispatch_service.py:<module>:1`：calls=1 self=0.000044s cum=0.949009s
- `resource_dispatch_excel.py:<module>:1`：calls=1 self=0.000031s cum=0.917742s
- `schedule_service.py:run_schedule:173`：calls=5 self=0.000152s cum=0.404521s
- `schedule_service.py:_run_schedule_impl:198`：calls=5 self=0.000485s cum=0.404354s
- `transaction.py:transaction:56`：calls=68 self=0.000716s cum=0.294978s
- `schedule_optimizer.py:optimize_schedule:225`：calls=5 self=0.000236s cum=0.179487s
- `schedule_optimizer.py:_run_local_search:71`：calls=5 self=0.003215s cum=0.153285s
- `batch_service.py:<module>:1`：calls=1 self=0.000037s cum=0.130857s
- `schedule_persistence.py:persist_schedule:187`：calls=5 self=0.000189s cum=0.125262s
- `scheduler.py:schedule:53`：calls=435 self=0.014261s cum=0.116645s
- `base_repo.py:execute:37`：calls=303 self=0.000234s cum=0.068660s

stdout tail:
```text
OK
D:\Github\APS Test\evidence\Phase7\smoke_phase7_report.md
```

## smoke_phase10_sgs_auto_assign

- 命令：`D:\py3.8\python.exe -m cProfile -o D:\Github\APS Test\audit\2026-03\20260316_perf_profile_artifacts\smoke_phase10_sgs_auto_assign.prof tests/smoke_phase10_sgs_auto_assign.py`
- 退出码：0
- 墙钟耗时：2.302s
- cProfile 总 self time：2.090526s

| 指标 | calls | self_s | cum_s |
|------|-------|--------|-------|
| dispatch_sgs | 15 | 0.001943 | 0.014917 |
| calendar_add_working_hours | 644 | 0.002466 | 0.013898 |
| calendar_adjust_to_working_time | 1338 | 0.001821 | 0.023115 |
| auto_assign_internal_resources | 44 | 0.001093 | 0.016198 |
| build_dispatch_key | 120 | 0.000411 | 0.000858 |

Top 热点（按 cum_s）:
- `__init__.py:<module>:1`：calls=1 self=0.000029s cum=1.235286s
- `resource_dispatch_service.py:<module>:1`：calls=1 self=0.000034s cum=1.014769s
- `resource_dispatch_excel.py:<module>:1`：calls=1 self=0.000021s cum=0.981882s
- `schedule_service.py:run_schedule:173`：calls=6 self=0.000228s cum=0.453560s
- `schedule_service.py:_run_schedule_impl:198`：calls=6 self=0.000770s cum=0.453309s
- `transaction.py:transaction:56`：calls=54 self=0.000650s cum=0.253555s
- `schedule_optimizer.py:optimize_schedule:225`：calls=6 self=0.000337s cum=0.182705s
- `schedule_persistence.py:persist_schedule:187`：calls=6 self=0.000191s cum=0.139879s
- `schedule_optimizer.py:_run_local_search:71`：calls=6 self=0.002767s cum=0.138505s
- `batch_service.py:<module>:1`：calls=1 self=0.000035s cum=0.129418s
- `scheduler.py:schedule:53`：calls=223 self=0.012097s cum=0.104370s
- `base_repo.py:execute:37`：calls=321 self=0.000278s cum=0.076055s

stdout tail:
```text
[smoke_phase10] report: D:\Github\APS Test\evidence\Phase10\smoke_phase10_report.md
```

## run_synthetic_case improve

- 命令：`D:\py3.8\python.exe -m cProfile -o D:\Github\APS Test\audit\2026-03\20260316_perf_profile_artifacts\synthetic_improve.prof tests/run_synthetic_case.py --mode improve --objective min_weighted_tardiness --time-budget 10 --parts 16 --batches-min 2 --batches-max 4 --ops-per-part 6 --calendar-days 60`
- 退出码：0
- 墙钟耗时：11.568s
- cProfile 总 self time：11.22597s

| 指标 | calls | self_s | cum_s |
|------|-------|--------|-------|
| dispatch_sgs | 12 | 1.180082 | 7.853086 |
| calendar_add_working_hours | 151062 | 0.434220 | 2.656964 |
| calendar_adjust_to_working_time | 343487 | 0.359024 | 2.370618 |
| auto_assign_internal_resources | 0 | 0.000000 | 0.000000 |
| build_dispatch_key | 103236 | 0.296415 | 0.636046 |

Top 热点（按 cum_s）:
- `schedule_service.py:run_schedule:173`：calls=1 self=0.000171s cum=10.039855s
- `schedule_service.py:_run_schedule_impl:198`：calls=1 self=0.000213s cum=10.039683s
- `schedule_optimizer.py:optimize_schedule:225`：calls=1 self=0.000300s cum=10.015990s
- `scheduler.py:schedule:53`：calls=81 self=0.022401s cum=9.819029s
- `schedule_optimizer_steps.py:_run_multi_start:136`：calls=1 self=0.001878s cum=8.077353s
- `sgs.py:dispatch_sgs:32`：calls=12 self=1.180082s cum=7.853086s
- `calendar_service.py:add_working_hours:229`：calls=151062 self=0.064371s cum=2.721335s
- `calendar_engine.py:add_working_hours:257`：calls=151062 self=0.434220s cum=2.656964s
- `calendar_engine.py:adjust_to_working_time:224`：calls=343487 self=0.359024s cum=2.370618s
- `calendar_engine.py:_policy_for_datetime:190`：calls=720416 self=0.619286s cum=2.217357s
- `schedule_optimizer.py:_run_local_search:71`：calls=1 self=0.006828s cum=1.936366s
- `scheduler.py:_schedule_internal:396`：calls=21384 self=0.214311s cum=1.855639s

stdout tail:
```text
"machine": {
          "count_used": 18,
          "busy_hours_total": 2181.1083,
          "util_avg": 0.334175,
          "load_cv": 0.385551,
          "load_max_hours": 214.1606,
          "load_min_hours": 45.7542
        },
        "operator": {
          "count_used": 21,
          "busy_hours_total": 2181.1083,
          "util_avg": 0.286436,
          "load_cv": 0.486651,
          "load_max_hours": 215.7067,
          "load_min_hours": 15.5589
        }
      }
    }
  ]
}
```


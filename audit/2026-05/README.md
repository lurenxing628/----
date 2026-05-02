# 2026-05 审计入口

## 当前阶段

阶段六用于收敛：

1. `result_summary` 解析入口；
2. 版本解析旧入口；
3. scheduler 路由导入即注册兼容副作用；
4. evidence/current 与 audit 当前入口。

## 当前判断口径

完整通过只以干净工作区命令为准：

```bash
python scripts/run_quality_gate.py --require-clean-worktree
```

辅助证明：

```bash
python tools/check_full_test_debt.py
python scripts/sync_debt_ledger.py check
python -m pyright -p pyrightconfig.gate.json
```

## 本月已有材料

- `phase4_phase5_baseline.txt`
- `phase5_startup_fallback_baseline.json`
- `phase5_win7_startup_review.md`

这些阶段五材料保留为前序背景，不改写旧结论。

## 历史材料

2026-04-25 收口总账仍作为前序债务来源，但阶段六完成后的当前结论以本目录和 `evidence/current/README.md` 为准。

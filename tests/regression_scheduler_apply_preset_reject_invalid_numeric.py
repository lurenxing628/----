import json
import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _expect_validation_error(fn, title: str) -> None:
    from core.infrastructure.errors import ValidationError

    ok = False
    try:
        fn()
    except ValidationError:
        ok = True
    assert ok, f"{title}：应抛出 ValidationError"


def _save_preset_raw(cfg_svc, name: str, payload: dict) -> None:
    with cfg_svc.tx_manager.transaction():
        cfg_svc.repo.set(
            cfg_svc._preset_key(name),  # noqa: SLF001 - 回归脚本允许使用内部 key 约定
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            description="regression preset",
        )


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.services.scheduler import ConfigService

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_preset_numeric_")
    test_db = os.path.join(tmpdir, "aps_preset_numeric.db")
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)

    try:
        cfg_svc = ConfigService(conn, logger=None, op_logger=None)
        base = cfg_svc.get_snapshot().to_dict()

        # 1) 非数字字符串（应拒绝）
        p1 = dict(base)
        p1["priority_weight"] = "abc"
        _save_preset_raw(cfg_svc, "bad_non_number", p1)
        _expect_validation_error(lambda: cfg_svc.apply_preset("bad_non_number"), "priority_weight=abc")

        # 2) 非有限数字 NaN/Inf（应拒绝）
        p2 = dict(base)
        p2["due_weight"] = "NaN"
        _save_preset_raw(cfg_svc, "bad_nan", p2)
        _expect_validation_error(lambda: cfg_svc.apply_preset("bad_nan"), "due_weight=NaN")

        p3 = dict(base)
        p3["holiday_default_efficiency"] = "Inf"
        _save_preset_raw(cfg_svc, "bad_inf", p3)
        _expect_validation_error(lambda: cfg_svc.apply_preset("bad_inf"), "holiday_default_efficiency=Inf")

        # 3) 整数字段非法（应拒绝）
        p4 = dict(base)
        p4["ortools_time_limit_seconds"] = "1.5"
        _save_preset_raw(cfg_svc, "bad_int_float", p4)
        _expect_validation_error(lambda: cfg_svc.apply_preset("bad_int_float"), "ortools_time_limit_seconds=1.5")

        # 4) 缺省字段仍允许回退默认（应通过）
        p5 = dict(base)
        p5.pop("priority_weight", None)
        p5.pop("due_weight", None)
        p5.pop("holiday_default_efficiency", None)
        _save_preset_raw(cfg_svc, "missing_numeric_allowed", p5)
        applied = cfg_svc.apply_preset("missing_numeric_allowed")
        assert applied == "missing_numeric_allowed", f"缺省字段回退默认应可应用，实际={applied!r}"

        print("OK")
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _system_exit_code(code: object) -> int:
    if code in (None, 0):
        return 0
    if isinstance(code, int):
        return int(code)
    print(str(code), file=sys.stderr)
    return 1


def _run_main(script_path: Path) -> int:
    module_name = f"_aps_regression_{script_path.stem}_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(module_name, str(script_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法为 {script_path.name} 创建模块加载器")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        main = getattr(module, "main", None)
        if not callable(main):
            raise RuntimeError(f"{script_path.name} 缺少可调用的 main()")
        try:
            result = main()
        except SystemExit as exc:
            return _system_exit_code(exc.code)
        if isinstance(result, int) and not isinstance(result, bool) and result != 0:
            return int(result)
        return 0
    finally:
        sys.modules.pop(module_name, None)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        raise SystemExit("用法：main_style_regression_runner.py <regression-script-path>")
    script_path = Path(args[0]).resolve()
    return _run_main(script_path)


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

_PYTHON_STARTED_AT = time.perf_counter()

if TYPE_CHECKING:
    from flask import Flask


def _entrypoint_module() -> Any:
    from web.bootstrap.entrypoint_loader import load_entrypoint

    return load_entrypoint(__file__, _PYTHON_STARTED_AT)


def create_app() -> Flask:
    return _entrypoint_module().create_app_with_mode("new_ui")


if __name__ not in ("__main__", "__mp_main__"):
    app = create_app()



def main(argv=None, deps=None) -> int:
    return _entrypoint_module().app_main("new_ui", anchor_file=__file__, argv=argv, deps=deps)


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    raise SystemExit(main())

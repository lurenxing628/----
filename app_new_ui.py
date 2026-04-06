from __future__ import annotations

from flask import Flask

from web.bootstrap.entrypoint import app_main, create_app_with_mode


def create_app() -> Flask:
    return create_app_with_mode("new_ui")


if __name__ != "__main__":
    app = create_app()



def main(argv=None, deps=None) -> int:
    return app_main("new_ui", anchor_file=__file__, argv=argv, deps=deps)


if __name__ == "__main__":
    raise SystemExit(main())

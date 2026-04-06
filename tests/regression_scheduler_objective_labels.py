import os


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> None:
    repo_root = find_repo_root()

    files = [
        os.path.join(repo_root, "templates", "scheduler", "config.html"),
        os.path.join(repo_root, "templates", "scheduler", "analysis.html"),
        os.path.join(repo_root, "templates", "scheduler", "batches.html"),
        os.path.join(repo_root, "web_new_test", "templates", "scheduler", "config.html"),
        os.path.join(repo_root, "web_new_test", "templates", "scheduler", "batches.html"),
        os.path.join(repo_root, "tests", "run_synthetic_case.py"),
    ]

    for path in files:
        text = _read(path)
        if "min_weighted_tardiness" not in text:
            raise RuntimeError(f"文件未同步新 objective：{os.path.relpath(path, repo_root)}")

    print("OK")


if __name__ == "__main__":
    main()

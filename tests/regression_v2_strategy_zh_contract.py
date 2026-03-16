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
    expected = {
        "priority_first": "优先级优先",
        "due_date_first": "交期优先",
        "weighted": "综合优先级和交期",
        "fifo": "先进先出",
    }
    files = [
        os.path.join(repo_root, "web_new_test", "templates", "scheduler", "batches.html"),
        os.path.join(repo_root, "web_new_test", "templates", "scheduler", "gantt.html"),
    ]

    for path in files:
        text = _read(path)
        for key, label in expected.items():
            token = f"'{key}': '{label}'"
            if token not in text:
                raise RuntimeError(f"模板缺少 strategy_zh 映射：{os.path.relpath(path, repo_root)} -> {token}")

    print("OK")


if __name__ == "__main__":
    main()

import os
import re
import tempfile
import time
from pathlib import Path


def find_repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main():
    repo_root = find_repo_root()
    doc_path = Path(repo_root) / "开发文档" / "系统速查表.md"
    txt = doc_path.read_text(encoding="utf-8", errors="strict")

    # 提取格式：- `GET /path`：xxx
    pat = re.compile(r"^-\s+`(GET|POST)\s+([^`]+)`", re.M)
    doc_eps = [(m.group(1), m.group(2).strip()) for m in pat.finditer(txt)]

    # 启动 app 并读取 url_map（隔离目录，避免污染真实 db/logs/backups）
    root = tempfile.mkdtemp(prefix="aps_quickref_check_")
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(root) / "aps.db")
    os.environ["APS_LOG_DIR"] = str(Path(root) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(root) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(root) / "templates_excel")

    import importlib
    import sys

    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()

    rule_set = set()
    for r in app.url_map.iter_rules():
        if r.rule.startswith("/static"):
            continue
        methods = set(r.methods or [])
        for m in ("GET", "POST"):
            if m in methods:
                rule_set.add((m, str(r.rule)))

    doc_set = set(doc_eps)
    missing_in_code = sorted([ep for ep in doc_set if ep not in rule_set])
    undocumented_in_doc = sorted([ep for ep in rule_set if ep not in doc_set and ep[1].startswith(("/excel-demo", "/personnel", "/equipment", "/process", "/scheduler", "/system", "/"))])

    out = []
    out.append("# 系统速查表接口对比（文档 vs 实现）")
    out.append("")
    out.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"- 文档：`{doc_path}`")
    out.append(f"- 文档接口条目（GET/POST）：{len(doc_eps)}")
    out.append(f"- 实现接口条目（GET/POST，排除 /static）：{len(rule_set)}")
    out.append("")
    out.append("## 结论")
    out.append(f"- 文档列出但实现缺失：{len(missing_in_code)}")
    out.append(f"- 实现存在但文档未列出：{len(undocumented_in_doc)}")
    out.append("")

    out.append("## 文档列出但实现缺失（如有）")
    if not missing_in_code:
        out.append("- 无")
    else:
        for m, p in missing_in_code[:200]:
            out.append(f"- `{m} {p}`")
    out.append("")

    out.append("## 实现存在但文档未列出（抽样前 80 条）")
    if not undocumented_in_doc:
        out.append("- 无")
    else:
        for m, p in undocumented_in_doc[:80]:
            out.append(f"- `{m} {p}`")
    out.append("")

    out_path = Path(repo_root) / "evidence" / "Conformance" / "quickref_vs_routes.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("OK")
    print(str(out_path))


if __name__ == "__main__":
    main()


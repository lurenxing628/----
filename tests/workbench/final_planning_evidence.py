"""Build an action ledger from completed private full-entry acceptance artifacts."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DESTINATION = REPO / ".codestable/roadmap/workbench-prototype-migration/acceptance-planning"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_source(root, label):
    path = root / ("final_planning_source-" + label + ".json")
    if not path.exists():
        return None
    value = read(path)
    manifest_path = Path(value["manifest"])
    manifest = read(manifest_path)
    assert value["files_checked"] == len(manifest["files"]) > 0
    assert value["aggregate_sha256"] == manifest["aggregate_sha256"]
    source = Path(value["source"]).resolve(strict=True)
    assert value["loaded_modules"] and source != Path(manifest["origin_root"]).resolve()
    return {"source": str(source), "manifest": str(manifest_path), "manifest_sha256": digest(manifest_path),
            "aggregate_sha256": manifest["aggregate_sha256"], "files_checked": value["files_checked"],
            "loaded_module_count": len(value["loaded_modules"]), "proof": str(path), "proof_sha256": digest(path)}


def check_console_errors(report):
    expected = [dict(row, status_text="BAD REQUEST") for row in report.get("expected_rejected_documents", [])]
    for row in report.get("expected_rejected_api", []):
        assert row["status"] == 404
        assert any(item["method"] == "GET" and item["url"] == row["url"] for item in report["requests"])
        assert any(item["url"] == row["url"] and item["status"] == row["status"] and item["body"]["ok"] is False
                   for item in report["responses"])
        expected.append(row)
    assert len(report["console_events"]) <= len(expected)
    for event in report["console_events"]:
        assert any(event["location"]["url"] == row["url"] and event["text"] ==
                   "Failed to load resource: the server responded with a status of " + str(row["status"]) +
                   " (" + row["status_text"] + ")" for row in expected)


def collect(root):
    proof = read(root / "final_planning_result.json")
    assert proof["errors"] == [], str(root)
    reports = {mode: read(root / ("final_planning_" + mode + ".json")) for mode in ("actions", "restart")}
    sample = {"root": str(root), "width": reports["actions"]["width"], "theme": reports["actions"]["theme"],
              "build_id": proof["source_build"]["build_id"], "result_sha256": digest(root / "final_planning_result.json"),
              "table_count": proof["tables"], "official_versions": proof["official_versions"], "hosts": [], "screenshots": []}
    for mode, report in reports.items():
        assert "error" not in report, str(root)
        assert all(not report[key] for key in ("page_errors", "capture_errors", "external_requests", "findings"))
        check_console_errors(report)
        for capture in report["screenshots"]:
            sample["screenshots"].append(dict(capture, mode=mode,
                full_sha256=digest(Path(capture["full"])), viewport_sha256=digest(Path(capture["viewport"]))))
        host = read(root / ("final_planning_server-" + mode + ".json"))
        assert host["server_returncode"] == host["browser_returncode"] == 0
        assert host["isolation"]["stopped"] and host["isolation"]["assets_unchanged"]
        assert host["isolation"]["python_sources"]["changed"] == host["isolation"]["isolation_violations"] == []
        sample["hosts"].append({"mode": mode, "pid": host["ready"]["pid"], "session": host["ready"]["session"],
            "normal_shutdown": True, "loaded_python_sources_unchanged": True,
            "frozen_source": frozen_source(root, "restart" if mode == "restart" else "first")})
    assert len({host["pid"] for host in sample["hosts"]}) == 2
    return sample, reports


def observation(root, mode, report, action):
    start, end = action["request_start"], action["request_end"]
    value = {"report": str(root / ("final_planning_" + mode + ".json")), "mode": mode,
            "request_start": start, "request_end": end,
            "request_count": end - start, "method_counts": dict(Counter(row["method"] for row in report["requests"][start:end]))}
    if action["action_id"] == "WBP-PLAN-004.invalid-reference":
        value["rejected_documents"] = report["expected_rejected_documents"]
    if action["action_id"] == "WBP-TRIAL-011.print":
        value["native_print"] = {key: report["native_print"][key] for key in ("method", "path", "sha256")}
    if action["action_id"] == "WBP-GANTT-004.trial-link":
        value["original_task_navigation"] = report["task_origin"]
    if action["action_id"] == "WBP-TRIAL-001.load-failure":
        value["rejected_api_reads"] = report["expected_rejected_api"]
    return value


def collect_nonwriting(root, mode):
    result_path = root / ("final_planning_" + mode + "_result.json")
    proof, report = read(result_path), read(root / ("final_planning_" + mode + ".json"))
    assert proof["errors"] == [] and proof["tables_unchanged"] > 0 and "error" not in report
    assert all(not report[key] for key in ("page_errors", "capture_errors", "external_requests", "findings"))
    check_console_errors(report)
    host = read(root / ("final_planning_server-" + mode + ".json"))
    assert host["server_returncode"] == host["browser_returncode"] == 0 and "forced_kill" not in host
    assert host["isolation"]["stopped"] and host["isolation"]["assets_unchanged"]
    assert host["isolation"]["python_sources"]["changed"] == host["isolation"]["isolation_violations"] == []
    recheck = read(root / "final_planning_build_input_recheck.json")
    assert recheck["changed"] == [] and recheck["build_id"] == proof["source_build"]["build_id"]
    sample = {"root": str(root), "width": proof["width"], "theme": proof["theme"], "cohort": mode,
              "build_id": proof["source_build"]["build_id"], "result_sha256": digest(result_path),
              "table_count": proof["tables_unchanged"], "tables_unchanged": True,
              "hosts": [{"mode": mode, "pid": host["ready"]["pid"], "session": host["ready"]["session"],
                         "normal_shutdown": True, "loaded_python_sources_unchanged": True,
                         "frozen_source": frozen_source(root, "first")}], "screenshots": []}
    for capture in report["screenshots"]:
        sample["screenshots"].append(dict(capture, mode=mode,
            full_sha256=digest(Path(capture["full"])), viewport_sha256=digest(Path(capture["viewport"]))))
    return sample, {mode: report}


def product_sources(samples):
    values = {}
    for sample in samples:
        for host in sample["hosts"]:
            proof = read(Path(sample["root"]) / ("final_planning_server-" + host["mode"] + ".json"))
            binding = host["frozen_source"]
            source = Path(binding["source"]) if binding else REPO
            for path, value in proof["isolation"]["python_sources"]["after"].items():
                try:
                    relative = Path(path).relative_to(source).as_posix()
                except ValueError:
                    continue
                if relative.split("/")[0] not in {"core", "web", "data"}:
                    continue
                assert values.setdefault(relative, value) == value, "Product source differs across admitted samples: " + relative
    assert values
    encoded = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"files_observed": len(values), "sha256": hashlib.sha256(encoded).hexdigest(),
            "basis": "Union of loaded core/web/data Python sources; every shared path must have the same digest across all admitted hosts."}


def build(roots, readonly_roots=(), preflight_roots=()):
    inventory = read(DESTINATION / "action-inventory.json")
    entries = {action["action_id"]: {"action_id": action["action_id"], "capability_id": capability["capability_id"],
        "B": "not_run", "K": "not_run", "V": "not_run", "P": "not_run", "observations": []}
        for capability in inventory["capabilities"] for action in capability["actions"]}
    samples, completed = [], set()
    for cohort, paths in (("actions", roots), ("readonly", readonly_roots), ("preflight", preflight_roots)):
        if not paths:
            continue
        variants, sets = set(), []
        for root in paths:
            sample, reports = collect(root) if cohort == "actions" else collect_nonwriting(root, cohort)
            samples.append(sample)
            variants.add((sample["width"], sample["theme"]))
            current = set()
            for mode, report in reports.items():
                for action in report["actions"]:
                    assert action["status"] == "passed" and action["action_id"] in entries
                    entry = entries[action["action_id"]]
                    entry["observations"].append(observation(root, mode, report, action))
                    current.add(action["action_id"])
            sets.append(current)
        assert len(paths) == 4 and variants == {(1920, "light"), (1920, "dark"), (1392, "light"), (1392, "dark")}
        assert all(values == sets[0] for values in sets)
        completed.update(sets[0])
    assert len({row["build_id"] for row in samples}) == 1
    bindings = [host["frozen_source"] for sample in samples for host in sample["hosts"]]
    if any(bindings):
        assert all(bindings), "Frozen and unbound historical hosts cannot form one source cohort"
        assert len({row["aggregate_sha256"] for row in bindings}) == 1
    backend_sources = product_sources(samples)
    for entry in entries.values():
        if not entry["observations"]:
            entry["reason"] = "本账本未收录该原子动作的完整组合证据；不借用旧原型或单组件通过状态。"
            continue
        entry["K"] = "passed"
        entry["V"] = "pending_main_review"
        entry["B"] = "passed" if any(row["request_count"] or row.get("rejected_documents") for row in entry["observations"]) else "not_applicable"
        entry["B_basis"] = ("实际浏览器请求与真实 factory/worker、SQLite 写入保留证据相互核对；非采用请求不改正式计划。"
                            if entry["B"] == "passed" else "本动作仅操作已经载入的浏览器状态，没有新增后端请求；不据此宣称写合同通过。")
        if any(row["mode"] == "restart" for row in entry["observations"]) or entry["action_id"] in {
                "WBP-PLAN-004.reload", "WBP-TRIAL-012.reload", "WBP-PLAN-004.invalid-reference", "WBP-GANTT-004.trial-link"}:
            entry["P"] = "passed"
        else:
            entry["P_reason"] = "已有整链持久性核对，但此原子动作未单列独立刷新或新进程断言。"
    return {"schema_version": 1, "status": "partial_acceptance_not_all_capabilities_passed", "source_build": samples[0]["build_id"],
            "cohorts": [name for name, paths in (("actions", roots), ("readonly", readonly_roots), ("preflight", preflight_roots)) if paths],
            "observed_python_product_sources": backend_sources,
            "capability_denominator": inventory["capability_count"], "action_denominator": inventory["action_count"],
            "K_passed": len(completed), "K_not_run": len(entries) - len(completed),
            "capabilities_with_observed_actions": len({value.split(".")[0] for value in completed}),
            "status_counts": {key: dict(Counter(entry[key] for entry in entries.values())) for key in ("B", "K", "V", "P")},
            "visual_boundary": "截图索引附 full/viewport SHA；D 的抽查不替代 Main 逐项视觉终审。",
            "persistence_boundary": ("两次采用产生 v5/v6；原数据保留，新进程恢复正式计划和原场景；不代表每个局部 UI 控件的独立 P 均已覆盖。"
                                     if roots else "本账本只有预检或只读边界，所有业务表逐项保持；没有进行正式采用，不据此声明采用持久性。"),
            "samples": samples, "actions": list(entries.values())}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", nargs=4, type=Path)
    parser.add_argument("--readonly-roots", nargs=4, type=Path, default=[])
    parser.add_argument("--preflight-roots", nargs=4, type=Path, default=[])
    args = parser.parse_args()
    result = build([root.resolve(strict=True) for root in args.roots],
                   [root.resolve(strict=True) for root in args.readonly_roots],
                   [root.resolve(strict=True) for root in args.preflight_roots])
    target = DESTINATION / "evidence-matrix.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"target": str(target), "sha256": digest(target), "source_build": result["source_build"],
                      "K_passed": result["K_passed"], "K_not_run": result["K_not_run"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Accept only the observed pristine-store default bootstrap, never arbitrary config edits."""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def expected_defaults():
    from core.services.scheduler.config import config_presets
    from core.services.scheduler.config.active_preset_service import ActivePresetService
    from core.services.scheduler.config.config_bootstrap_service import ConfigBootstrapService
    from core.services.scheduler.config.config_constants import BUILTIN_PRESET_NAMES
    from core.services.scheduler.config.config_field_spec import list_config_fields

    fields = [(spec.key, str(spec.default), spec.description) for spec in list_config_fields()]
    presets = [(config_presets.preset_key(name), config_presets.dump_snapshot_payload(snapshot), "排产配置模板：" + description)
               for name, snapshot, description in config_presets.builtin_presets(ConfigBootstrapService.default_snapshot())]
    provenance = ActivePresetService.active_preset_updates(BUILTIN_PRESET_NAMES[0])
    assert (len(fields), len(presets), len(provenance)) == (27, 4, 3), "Re-audit changed default registry"
    result = {key: {"config_value": value, "description": description} for key, value, description in fields + presets + provenance}
    assert len(result) == 34
    return result


def rows_hash(rows):
    ordinary = [{key: value for key, value in row.items() if key != "__rowid__"} for row in rows]
    return hashlib.sha256(json.dumps(ordinary, sort_keys=True).encode()).hexdigest()


def validate_bootstrap(before, after, trace, commands):
    assert before == [], "An existing configuration store cannot use the bootstrap allowance"
    defaults = expected_defaults()
    assert len(after) == len(defaults)
    assert [row["id"] for row in after] == list(range(1, 35))
    assert [row["__rowid__"] for row in after] == list(range(1, 35))
    assert {row["config_key"] for row in after} == set(defaults)
    started = datetime.fromisoformat(trace["first"]["at"]).replace(microsecond=0)
    ended = datetime.fromisoformat(trace["finished"])
    for row in after:
        assert set(row) == {"__rowid__", "id", "config_key", "config_value", "description", "updated_at"}
        assert {key: row[key] for key in ("config_value", "description")} == defaults[row["config_key"]]
        updated = datetime.strptime(row["updated_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        assert started <= updated <= ended
    assert trace["completed"] and trace["attempted_writes"] == 34
    assert trace["before_requests"] == {"rows": 0, "sha256": rows_hash([])}
    assert trace["first"]["statement_kind"] == "INSERT"
    assert len(trace["requests"]) == 1
    observed = trace["requests"][0]
    request = observed["request"]
    assert request == trace["first"]["request"]
    assert request["method"] == "POST" and request["path"] == "/api/workbench/v1/calendar/upsert"
    assert observed["attempted_writes"] == 34 and observed["response_status"] == 200
    assert observed["committed_config"] == {"rows": 34, "sha256": rows_hash(after)}
    matched = [row for row in commands if row.get("request_key") == request["request_key"]]
    assert len(matched) == 1
    assert matched[0]["path"] == request["path"] and matched[0]["status"] == 200
    assert matched[0]["result"] == "committed" and matched[0]["receipt_ref"]
    required = {
        ("core/services/workbench/calendars.py", "apply"),
        ("core/services/scheduler/config/config_bootstrap_service.py", "ensure_defaults_if_pristine"),
        ("core/services/scheduler/config/config_bootstrap_service.py", "bootstrap_registered_defaults"),
        ("data/repositories/config_repo.py", "set_batch"),
    }
    assert all(any(row["path"].endswith(path) and row["function"] == function for row in trace["first"]["stack"])
               for path, function in required)
    return {"passed": True, "kind": "exact_pristine_default_bootstrap", "rows_added": 34,
            "registered_fields": 27, "built_in_presets": 4, "provenance_fields": 3,
            "request": request, "receipt_ref": matched[0]["receipt_ref"], "config_sha256": rows_hash(after),
            "keys": sorted(defaults), "policy": "Empty store only, exact registry values and descriptions, one observed committed calendar command"}


def config_preservation(before, after, root, commands, initial_pid=None):
    old, new = before["tables"]["ScheduleConfig"], after["tables"]["ScheduleConfig"]
    if old == new:
        return {"passed": True, "kind": "unchanged", "rows_added": 0, "original_rows_retained": len(old)}
    assert root is not None, "Configuration changes require an actual per-process trace"
    assert type(initial_pid) is int and initial_pid > 0, "Bind the original PID explicitly, not the latest restart marker"
    trace_path = root / ("final-master-schedule-config-trace-" + str(initial_pid) + ".json")
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["pid"] == initial_pid
    assert not [row for row in before["tables"]["sqlite_sequence"] if row["name"] == "ScheduleConfig"]
    sequences = [row for row in after["tables"]["sqlite_sequence"] if row["name"] == "ScheduleConfig"]
    assert len(sequences) == 1 and sequences[0]["seq"] == 34
    return {**validate_bootstrap(old, new, trace, commands), "trace_path": str(trace_path),
            "trace_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest()}


if __name__ == "__main__":
    from tests.workbench.final_operations_source_binding import source_binding

    folder = Path(sys.argv[1]).resolve()
    original = json.loads((folder / "final-master-db-before.json").read_text(encoding="utf-8"))
    saved = json.loads((folder / "final-master-db-after.json").read_text(encoding="utf-8"))
    probe = json.loads((folder / "resource-probe-results.json").read_text(encoding="utf-8"))
    initial = json.loads((folder / "final-master-result.json").read_text(encoding="utf-8"))
    result = config_preservation(original, saved, folder, probe["commands"], initial["ready"]["pid"])
    binding = source_binding()
    assert binding is not None and not binding["violations"]
    result["source_binding"] = {key: binding[key] for key in ("root", "aggregate_sha256", "manifest", "violations")}
    print(json.dumps(result, ensure_ascii=False))

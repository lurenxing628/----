"""Real old write -> old detail GET -> canonical host, using Main's flash consumer."""

import argparse
import json
import traceback
from html.parser import HTMLParser
from pathlib import Path

from factory_runtime import FactoryCase


class Boot(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active, self.parts = False, []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "workbench-boot":
            self.active = True

    def handle_data(self, value):
        if self.active:
            self.parts.append(value)

    def handle_endtag(self, tag):
        if tag == "script":
            self.active = False


def boot(response):
    parser = Boot()
    parser.feed(response.get_data(as_text=True))
    return json.loads("".join(parser.parts))


def run(case, mode):
    message = "设备信息已保存。"
    response = case.client.post("/equipment/M-BASE/update", data={"name": "真实确认后的设备", "op_type_id": "OT-IN", "status": "active"})
    case.save_response("real-post", response)
    assert response.status_code == 302 and response.headers["Location"] == "/equipment/M-BASE"
    with case.db() as conn:
        row = conn.execute("SELECT name FROM Machines WHERE machine_id='M-BASE'").fetchone()
        assert row[0] == "真实确认后的设备"
        ref = conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='machine' AND entity_key='M-BASE' AND active=1").fetchone()[0]
    old_get = case.client.get(response.headers["Location"])
    case.save_response("old-get", old_get)
    assert old_get.status_code == 302 and old_get.headers["Location"].startswith("/workbench?")
    target = old_get.headers["Location"]
    if mode == "invalid-navigation":
        target += "&version=3"
    elif mode == "missing-assets":
        missing = case.root / "missing-static"
        missing.mkdir()
        case.app.static_folder = str(missing)
    final = case.client.get(target)
    case.save_response("canonical-result", final)
    if mode == "normal":
        assert final.status_code == 200
        payload = boot(final)
        assert payload["messages"] == [{"category": "success", "message": message}]
        assert payload["navigation"]["context"] == {"source": "production", "kind": "machine", "entity_ref": ref}
    else:
        assert final.status_code == (400 if mode == "invalid-navigation" else 503)
        assert message in final.get_data(as_text=True)
        assert final.headers["Cache-Control"] == "no-store"
    with case.db() as conn:
        assert conn.execute("SELECT name FROM Machines WHERE machine_id='M-BASE'").fetchone()[0] == "真实确认后的设备"
    refreshed = case.client.get(target)
    case.save_response("refresh", refreshed)
    if mode == "normal":
        assert boot(refreshed)["messages"] == []
    else:
        assert message not in refreshed.get_data(as_text=True)
    return {"passed": True, "mode": mode, "source": "actual equipment.update_machine transaction; no inserted test flash",
            "committed_value_retained": True, "old_get_canonical_identity_same": True, "message_once": True,
            "browser_execution_verified": False, "missing_assets_injection": "runtime static_folder points to an actually empty private directory" if mode == "missing-assets" else None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("runtime", type=Path)
    parser.add_argument("mode", choices=("normal", "invalid-navigation", "missing-assets"))
    args = parser.parse_args()
    case = FactoryCase(args.source, args.runtime, candidate=True)
    try:
        result = run(case, args.mode)
    except Exception as exc:
        result = {"passed": False, "error": str(exc), "traceback": traceback.format_exc()}
    case.write_result(result)
    print(json.dumps({"mode": args.mode, "passed": result["passed"], "error": result.get("error")}, ensure_ascii=False), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

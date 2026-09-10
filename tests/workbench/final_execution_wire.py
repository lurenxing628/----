"""Capture actual responses and enforce read-only GETs in the private acceptance host."""

import hashlib
import json
import threading
import uuid

from flask import g, request


def attach_wire(app, directory):
    lock = threading.Lock()

    def append(name, value):
        with lock, (directory / name).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, ensure_ascii=False) + "\n")

    @app.before_request
    def read_only():
        if request.method == "GET" and request.path.startswith("/api/workbench/"):
            g.db.execute("PRAGMA query_only=ON")
        if request.path.startswith("/api/workbench/"):
            url = request.full_path
            g.db.set_trace_callback(lambda sql: append("sql.jsonl", {"url": url, "sql": sql}))

    @app.after_request
    def capture(response):
        if not request.path.startswith("/api/workbench/"):
            return response
        row = {"url": request.full_path, "method": request.method, "status": response.status_code,
               "headers": dict(response.headers)}
        if request.is_json:
            row["input"] = request.get_json()
        if response.is_json:
            row["payload"] = response.get_json()
        append("http.jsonl", row)
        if response.direct_passthrough:
            original = response.response
            target = directory / ("wire-" + uuid.uuid4().hex + ".bin")

            def chunks():
                digest, length = hashlib.sha256(), 0
                try:
                    with target.open("wb") as output:
                        for chunk in original:
                            output.write(chunk)
                            digest.update(chunk)
                            length += len(chunk)
                            yield chunk
                    append("streams.jsonl", {"url": row["url"], "path": str(target),
                                              "bytes": length, "sha256": digest.hexdigest()})
                finally:
                    if hasattr(original, "close"):
                        original.close()

            response.response = chunks()
        return response

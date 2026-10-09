"""Complex-sample client: the same HTTP reads and write receipts as the UI."""

import json
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "/api/workbench/v1"


class SampleAPIError(RuntimeError):
    def __init__(self, path, status, body):
        self.path, self.status, self.body = path, status, body
        super().__init__(f"{path} returned {status}: {body}")


class SampleClient:
    def __init__(self, base_url, timeout=120):
        self.base_url, self.timeout = base_url.rstrip("/"), timeout
        self.request_count = 0

    def document(self, path, value=None, status=200):
        data = None if value is None else json.dumps(value, ensure_ascii=False).encode("utf-8")
        request = Request(self.base_url + path, data=data,
                          headers={"Content-Type": "application/json"} if data is not None else {})
        self.request_count += 1
        try:
            response = urlopen(request, timeout=self.timeout)
        except HTTPError as exc:
            response = exc
        with response:
            content = response.read()
            actual = response.getcode()
        body = json.loads(content.decode("utf-8"))
        if actual != status or body.get("ok") is False:
            raise SampleAPIError(path, actual, body)
        return body

    def get(self, path):
        return self.document(path)["data"]

    def post(self, path, value, status=200):
        return self.document(path, value, status)

    def command(self, path, context, value):
        return self.post(path, {"request_key": "complex-sample-" + uuid.uuid4().hex,
                                "write_token": context["write_token"], "input": value})

    def create(self, kind, payload):
        path = BASE + "/entities/" + kind
        context = self.get(path)["create_context"]
        return self.command(path + "/create", context, payload)["data"]["entity_ref"]


class SampleProgress:
    def __init__(self, output, client):
        self.output = Path(output) if output is not None else None
        self.client, self.started = client, time.monotonic()
        self.report = {"sample": "complex-v1", "state": "injecting", "steps": [],
                       "base_url": client.base_url, "injection_http_timeout_seconds": client.timeout,
                       "unsupported": ["自制连续组：当前产品没有该业务写入入口。"]}
        self.save(create=True)

    def save(self, create=False):
        self.report.update(elapsed_seconds=round(time.monotonic() - self.started, 3),
                           request_count=self.client.request_count)
        if self.output is not None:
            self.output.parent.mkdir(parents=True, exist_ok=True)
            with self.output.open("x" if create else "w", encoding="utf-8") as stream:
                json.dump(self.report, stream, ensure_ascii=False, indent=2)

    def step(self, name, function):
        row = {"name": name, "state": "running"}
        self.report["steps"].append(row)
        self.save()
        started = time.monotonic()
        try:
            result = function()
            row.update(state="complete", result=result)
            return result
        except Exception as exc:
            row.update(state="failed", error=str(exc))
            if isinstance(exc, SampleAPIError):
                row.update(path=exc.path, status=exc.status, response=exc.body)
            self.report["state"] = "failed"
            raise
        finally:
            row["elapsed_seconds"] = round(time.monotonic() - started, 3)
            self.save()

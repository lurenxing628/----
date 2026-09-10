"""CQ cold-process probe against only a test-supplied temporary database."""

import json
import os
import sqlite3
import sys

from flask import Flask

from core.models.workbench_command import WorkbenchCommandRejected
from tests.workbench.trial_adoption_support import INTENT, service
from tests.workbench.trial_support import connect


class CrashBeforeCommit(sqlite3.Connection):
    crash = False

    def commit(self):
        if self.crash:
            os._exit(73)
        return super().commit()


def main():
    mode, path, ref, key = sys.argv[1:5]
    conn = connect(path, CrashBeforeCommit)
    try:
        with Flask("cq-cold-process").app_context():
            svc = service(conn)
            if mode == "crash":
                token = svc.preview(ref)["write_context"]["write_token"]
                assert token
                conn.crash = True
                svc.adopt(ref, token, key, INTENT)
                raise AssertionError("Expected process exit before COMMIT")
            if mode == "stale":
                try:
                    svc.adopt(ref, sys.argv[5], key, INTENT)
                except WorkbenchCommandRejected as exc:
                    result = {"code": exc.code}
                else:
                    raise AssertionError("Another process's write token must not be accepted")
            else:
                result = svc.lookup(ref, key)
            print(json.dumps({"result": result, "changes": conn.total_changes, "in_transaction": conn.in_transaction}))
    finally:
        conn.close()


if __name__ == "__main__":
    main()


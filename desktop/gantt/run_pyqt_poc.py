from __future__ import annotations

import os
import sys

from core.infrastructure.database import get_connection
from core.services.scheduler import GanttService
from desktop.gantt.contract_client import GanttDesktopDataProvider
from desktop.gantt.pyqt_poc import GanttPyQtUnavailableError, launch_gantt_poc


def main() -> int:
    db_path = os.environ.get("APS_DB_PATH", "").strip()
    if not db_path:
        print("APS_DB_PATH is required, e.g. set APS_DB_PATH=./db/aps.db")
        return 2

    conn = get_connection(db_path)
    try:
        svc = GanttService(conn)
        provider = GanttDesktopDataProvider(svc)
        return int(launch_gantt_poc(provider))
    except GanttPyQtUnavailableError as e:
        print(str(e))
        return 3
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())


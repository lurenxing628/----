"""Encode materialized decision downloads outside the HTTP process GIL."""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from core.models.workbench_command import WorkbenchCommandRejected


def _encode_xlsx(kind, data, snapshot, section):
    try:
        if kind == "run":
            from .run.decision_export import write_run_decision_export

            download = write_run_decision_export(data, snapshot, "xlsx", section)
        elif kind == "history":
            from .history.export import write_history_export

            download = write_history_export(data, snapshot, "xlsx", section)
        else:
            raise ValueError("Unsupported decision export kind: " + str(kind))
    except WorkbenchCommandRejected as exc:
        # The exception's constructor needs code and message, while its ordinary
        # exception args contain only the message. Preserve its public contract.
        return "rejected", exc.code, str(exc), exc.status, exc.operation_refs
    return "encoded", download


def write_decision_xlsx(kind, data, snapshot, section):
    with ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn")) as encoder:
        result = encoder.submit(_encode_xlsx, kind, data, snapshot, section).result()
    if result[0] == "rejected":
        raise WorkbenchCommandRejected(result[1], result[2], result[3], operation_refs=result[4])
    return result[1]

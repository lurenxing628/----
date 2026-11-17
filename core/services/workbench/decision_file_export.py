"""Encode materialized decision downloads outside the HTTP process GIL.

The route hands over its own module-level file writer; the spawned process imports it by
reference, so this boundary depends on no workbench cluster.
"""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from core.models.workbench_command import WorkbenchCommandRejected


def _encode_xlsx(writer, data, snapshot, section):
    try:
        download = writer(data, snapshot, "xlsx", section)
    except WorkbenchCommandRejected as exc:
        # The exception's constructor needs code and message, while its ordinary
        # exception args contain only the message. Preserve its public contract.
        return "rejected", exc.code, str(exc), exc.status, exc.fields
    return "encoded", download


def write_decision_xlsx(writer, data, snapshot, section):
    with ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn")) as encoder:
        result = encoder.submit(_encode_xlsx, writer, data, snapshot, section).result()
    if result[0] == "rejected":
        raise WorkbenchCommandRejected(result[1], result[2], result[3], fields=result[4])
    return result[1]

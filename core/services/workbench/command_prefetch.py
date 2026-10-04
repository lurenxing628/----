"""Facts a command computes in a read snapshot before taking the write lock.

Reused under the lock only while no connection has committed since: a long read
then never runs inside BEGIN IMMEDIATE unless the database actually changed.
"""

from core.infrastructure.connection_guards import data_version
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages


def write_stamp(conn):
    """(本连接累计写入行数, 其他连接提交计数)：两项都没变，库里的数据就和取标记时一模一样。

    必须在读出事实的同一个事务里取；锁内比对时也要在写事务里取。事务外取的标记可能比事实新，
    会把过期事实当成最新。PRAGMA data_version 只随其他连接的提交变化，本连接自己的写入靠 total_changes。
    """
    if not conn.in_transaction:
        raise RuntimeError("Write stamps must be taken inside the transaction that read the facts")
    version = data_version(conn)
    if version is None:
        raise RuntimeError("SQLite data_version unavailable")
    return conn.total_changes, version


class FactsChanged(WorkbenchCommandRejected):
    """A guard found its prefetched facts stale; its write transaction is still empty and rolls back."""

    def __init__(self):
        super().__init__("snapshot_stale", messages.STALE)


class Prefetched:
    def __init__(self, conn, value, stamp, final):
        self.conn, self.value, self.stamp, self.final = conn, value, stamp, final

    def current(self, recompute):
        """写锁里取值：库没变就沿用锁外的结果；变了先回到锁外重算，最后一次才在锁内重算。"""
        if write_stamp(self.conn) == self.stamp:
            return self.value
        if not self.final:
            raise FactsChanged()
        return recompute()


def run_prefetched(conn, prefetch, command, *, attempts=2):
    """prefetch() -> (value, stamp) runs outside any write lock; command(Prefetched) runs the write command.

    Only the last attempt recomputes under the lock, so other writers committing during
    every prefetch cannot starve the command; earlier attempts never hold the lock long.
    """
    attempt = 1
    while True:
        value, stamp = prefetch()
        try:
            return command(Prefetched(conn, value, stamp, attempt >= attempts))
        except FactsChanged:
            if attempt >= attempts:
                raise
            attempt += 1

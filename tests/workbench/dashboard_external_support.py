"""DO fixtures install helpers explicitly on temporary real host connections."""

import pytest

from core.infrastructure.database import get_connection
from core.infrastructure.workbench_outsourcing_schema import install
from core.infrastructure.workbench_outsourcing_source_schema import install as install_sources
from core.infrastructure.workbench_process_schema import install_process
from core.infrastructure.workbench_template_lineage_schema import install_template_lineage
from tests.workbench.dashboard_support import DashboardCase
from tests.workbench.outsourcing_support import OutsourcingCase, original_rows


def storage(conn):
    result = original_rows(conn)
    names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
             if row[0].startswith("WorkbenchOutsourcing") or row[0] == "WorkbenchCommandReceipts"]
    for name in names:
        result[name] = [tuple(row) for row in conn.execute('SELECT * FROM "' + name + '" ORDER BY rowid')]
    return result


class ExternalCase(DashboardCase):
    def register(self, index=1, **patch):
        payload = self.shipments.payload(**patch)
        if not patch.get("merged"):
            payload["target"]["operation_refs"] = [self.shipments.operation_ref("XO" + str(index))]
        return self.shipments.confirm(self.shipments.preview(payload))["data"]["outsourcing_ref"]

    def returned(self, ref):
        return self.shipments.confirm(self.shipments.preview({"outsourcing_ref": ref,
            "returned": "2026-09-10T10:00:00", "confirmedState": "returned",
            "declared_operator": "Receiving clerk", "reason": "Checked original receipt"}))


@pytest.fixture(name="external_case")
def external_case(dashboard_case):
    conn = get_connection(str(dashboard_case.path))
    conn.execute("BEGIN")
    install_process(conn)
    install_template_lineage(conn)
    install(conn)
    install_sources(conn)
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT1','Heat treatment','external')")
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES ('XS1','Supplier','XT1',2)")
    conn.execute("INSERT INTO Parts(part_no,part_name,remark) VALUES ('XP1','Part',?)", (b"original\x00\xff",))
    conn.execute("INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_date,ready_status) "
                 "VALUES ('XB1','XP1','Part',10,'2026-09-11','2026-09-01','yes')")
    for index in range(1, 4):
        conn.execute("INSERT INTO BatchOperations(op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days) "
                     "VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)", ("XO" + str(index), index))
    conn.commit()
    case = ExternalCase(dashboard_case.path, conn)
    case.op = dashboard_case.op
    case.shipments = OutsourcingCase(case.path, conn)
    yield case
    conn.close()

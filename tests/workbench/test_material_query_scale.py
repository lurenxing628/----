"""Bounded real entity reads with a large set of batch material references."""

import json
import statistics
import time

from flask import Flask

from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.material_queries import WorkbenchMaterialQueryService
from core.services.workbench.materials import WorkbenchMaterialService
from web.routes.workbench.materials import _entity_with_context


def test_ten_thousand_materials_and_thirty_thousand_requirements(schema_conn):
    conn = schema_conn
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('P-SCALE','Scale')")
    conn.execute("INSERT INTO Batches(batch_id,part_no,quantity) VALUES ('B-SCALE','P-SCALE',1)")
    conn.executemany("INSERT INTO Materials(material_id,name,stock_qty) VALUES (?,?,?)",
                     [(f"M-{number:05d}", "Scale", number) for number in range(10000)])
    conn.executemany("INSERT INTO BatchMaterials(batch_id,material_id,required_qty,available_qty) VALUES ('B-SCALE',?,1,0)",
                     [(f"M-{number % 10000:05d}",) for number in range(30000)])
    conn.commit()
    plan = " ".join(str(row[3]) for row in conn.execute(
        "EXPLAIN QUERY PLAN SELECT COUNT(*) FROM BatchMaterials WHERE material_id=?", ("M-00001",)))
    assert "idx_workbench_batch_materials_material" in plan
    reader, domain = WorkbenchMaterialQueryService(conn), WorkbenchMaterialService(conn)
    records = []
    before = conn.total_changes
    with Flask("material-scale").app_context():
        for page_size, page_number in ((20, 1), (20, 400), (200, 1)):
            durations, counts = [], []
            for _ in range(3):
                statements = []
                conn.set_trace_callback(statements.append)
                start = time.perf_counter()
                with reader.read_snapshot():
                    rows, page = reader.page(MaterialPageRequest(number=page_number, size=page_size))
                    entities = [_entity_with_context(row, domain) for row in rows]
                durations.append((time.perf_counter() - start) * 1000)
                counts.append(sum(sql.lstrip().upper().startswith("SELECT") for sql in statements))
                conn.set_trace_callback(None)
                assert page["total"] == 10000 and len(entities) == page_size
                assert all(item["relationships"]["batch_requirement_count"] == 3 for item in entities)
                assert all(item["write_context"]["capabilities"]["material.delete"] is False for item in entities)
                assert len({item["ref"] for item in entities}) == page_size
            records.append({"size": page_size, "page": page_number, "median_ms": round(statistics.median(durations), 2),
                            "select_count": counts, "samples_ms": [round(value, 2) for value in durations]})
    assert conn.total_changes == before
    print("MATERIAL_QUERY_SCALE " + json.dumps({"materials": 10000, "requirements": 30000, "pages": records}))

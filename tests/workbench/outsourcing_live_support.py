"""Nonempty current-schema external operations for full workbench browser checks."""


def seed_outsourcing_data(conn):
    conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('XT1','Heat treatment','external')")
    conn.execute("INSERT INTO Suppliers(supplier_id,name,op_type_id,default_days) VALUES ('XS1','Heat treatment supplier','XT1',2)")
    conn.execute("INSERT INTO Parts(part_no,part_name) VALUES ('XP1','External production part')")
    conn.execute("""INSERT INTO Batches(batch_id,part_no,part_name,quantity,due_date,ready_date)
        VALUES ('XB1','XP1','External production part',10,'2026-09-14','2026-09-01')""")
    for seq in (10, 20, 30):
        conn.execute("""INSERT INTO BatchOperations
            (op_code,batch_id,seq,op_type_id,op_type_name,source,supplier_id,ext_days)
            VALUES (?,'XB1',?,'XT1','Heat treatment','external','XS1',2)""", ("XB1-" + str(seq), seq))
    conn.commit()
    return {"batch_code": "XB1", "supplier_code": "XS1", "operation_codes": ["XB1-10", "XB1-20", "XB1-30"],
            "batch_ref": conn.execute("SELECT ref FROM WorkbenchEntityRefs WHERE kind='batch' AND entity_key='XB1' AND active=1").fetchone()[0]}

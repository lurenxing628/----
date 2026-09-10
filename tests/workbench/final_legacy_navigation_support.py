"""Private real-schema fixture; never opens the app factory or production DB."""

from pathlib import Path

from flask import Flask

from core.infrastructure.workbench_plan_identity_schema import install_plan_identity
from tests.workbench.plan_read_support import connect, seed_plans
from web.routes.workbench.legacy_page_contract import LegacyGetRequest


def prepare_database(path):
    conn = connect(path)
    try:
        conn.executescript((Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8"))
        install_plan_identity(conn)
        seed_plans(conn)
        conn.execute("INSERT INTO OpTypes(op_type_id,name,category) VALUES ('PRIVATE-T1','Type one','external')")
        conn.execute("INSERT INTO Suppliers(supplier_id,name) VALUES ('PRIVATE-S1','Supplier one')")
        conn.commit()
    finally:
        conn.close()


def legacy(endpoint="scheduler.gantt_page", args=None, path=None):
    pairs = tuple(args.items()) if isinstance(args, dict) else tuple(args or ())
    return LegacyGetRequest(endpoint, pairs, path or {})


def token_app():
    return Flask("private-legacy-navigation-tokens")

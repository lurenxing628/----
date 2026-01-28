from flask import Blueprint

from web.ui_mode import render_ui_template as render_template


bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    return render_template("dashboard.html", title="首页")


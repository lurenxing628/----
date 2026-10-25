"""Draft-only legacy page boundary; no registration occurs on import."""

from functools import wraps
from typing import Mapping
from urllib.parse import urlsplit

from flask import current_app, g, redirect, render_template, request
from werkzeug.exceptions import BadRequest

from web.routes.workbench.legacy_navigation import resolve_legacy_get
from web.routes.workbench.legacy_page_contract import PAGE_POLICIES, LegacyGetDecision, LegacyGetRequest
from web.routes.workbench.legacy_presentation import install_legacy_presentation


def _unique_query():
    pairs = tuple(request.args.items(multi=True))
    names = [name for name, _ in pairs]
    if len(names) != len(set(names)):
        raise BadRequest("页面地址里的条件有重复项，页面没有打开。请从侧栏重新进入。")
    return pairs


def _validate_decision(decision, policy):
    if not isinstance(decision, LegacyGetDecision):
        raise RuntimeError("Legacy converter must return a checked decision.")
    if policy == "retired" and decision.kind != "retired":
        raise RuntimeError("A retired-only page cannot silently become another workspace.")
    if decision.kind == "redirect":
        if not decision.view or not isinstance(decision.context, Mapping):
            raise RuntimeError("A redirect must carry its checked target and context.")
    elif decision.kind == "retired":
        if not decision.reason_code or not decision.message:
            raise RuntimeError("Retirement requires an explicit public reason.")
    else:
        raise RuntimeError("Unknown legacy navigation decision.")
    return decision


def _destination_response(decision):
    destination = decision.destination
    if not isinstance(destination, str):
        raise RuntimeError("The canonical navigation destination must be a string.")
    parts = urlsplit(destination)
    if (parts.scheme or parts.netloc or parts.fragment
            or parts.path not in ("/workbench", "/workbench/trial")):
        raise RuntimeError("Legacy navigation must stay on a canonical workbench entry.")
    return redirect(destination, code=302)


def _page_adapter(endpoint, original, policy, restyled_views):
    @wraps(original)
    def adapted(**path_values):
        # POST parsing, transactions and confirmation keep their original handler.
        if request.method not in ("GET", "HEAD"):
            return original(**path_values)
        query = _unique_query()
        if policy == "restyle":
            response = current_app.make_response(restyled_views[endpoint](**path_values))
        else:
            legacy = LegacyGetRequest(endpoint, query, dict(path_values))
            decision = _validate_decision(resolve_legacy_get(g.db, legacy), policy)
            if decision.kind == "redirect":
                response = _destination_response(decision)
            else:
                response = current_app.make_response(
                    render_template("workbench/retired.html", title="旧入口已退役", decision=decision))
                response.status_code = 410
        response.headers["Cache-Control"] = "no-store"
        return response
    return adapted


def install_legacy_page_adapters(app, *, restyled_views):
    """Main calls this once, before serving, only after all presentation gates."""
    if "workbench.legacy_pages" in app.extensions:
        raise RuntimeError("Legacy page adapters are already installed.")
    replacements = {}
    # Validate the whole registry first; an incomplete registry changes no handlers.
    for endpoint, policy in PAGE_POLICIES.items():
        if endpoint not in app.view_functions:
            raise RuntimeError("Missing legacy page endpoint: " + endpoint)
        rules = list(app.url_map.iter_rules(endpoint))
        if not rules or any("GET" not in rule.methods for rule in rules):
            raise RuntimeError("Legacy page policy must refer to GET routes: " + endpoint)
        if policy == "restyle" and not callable(restyled_views.get(endpoint)):
            raise RuntimeError("Missing new print/manual presentation: " + endpoint)
        replacements[endpoint] = _page_adapter(
            endpoint, app.view_functions[endpoint], policy, restyled_views)
    install_legacy_presentation(app)
    app.view_functions.update(replacements)
    app.extensions["workbench.legacy_pages"] = tuple(PAGE_POLICIES)


def install_legacy_retirement(app):
    """Explicit production registration, after applying the companion renderers.

    The print/manual handlers retain their original parsers and now render the
    new templates. There is no TESTING flag, request switch or legacy bypass.
    """
    restyled = {endpoint: app.view_functions.get(endpoint) for endpoint, policy in PAGE_POLICIES.items()
                if policy == "restyle"}
    install_legacy_page_adapters(app, restyled_views=restyled)

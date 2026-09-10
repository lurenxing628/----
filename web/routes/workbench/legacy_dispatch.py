"""Draft-only legacy page boundary; no registration occurs on import."""

from functools import wraps
from typing import Mapping
from urllib.parse import urlsplit

from flask import current_app, g, redirect, render_template, request
from werkzeug.exceptions import BadRequest

from web.routes.workbench.legacy_navigation import build_legacy_destination, resolve_legacy_get
from web.routes.workbench.legacy_page_contract import PAGE_POLICIES as PAGE_POLICIES
from web.routes.workbench.legacy_page_contract import LegacyGetDecision as LegacyGetDecision
from web.routes.workbench.legacy_page_contract import LegacyGetRequest as LegacyGetRequest
from web.routes.workbench.legacy_presentation import install_legacy_presentation


def _unique_query():
    pairs = tuple(request.args.items(multi=True))
    names = [name for name, _ in pairs]
    if len(names) != len(set(names)):
        raise BadRequest("页面查询条件重复，未忽略任何条件或切换范围。")
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


def _destination_response(decision, build_destination):
    destination = build_destination(decision)
    if not isinstance(destination, str):
        raise RuntimeError("The canonical navigation destination must be a string.")
    parts = urlsplit(destination)
    if (parts.scheme or parts.netloc or parts.fragment
            or parts.path not in ("/workbench", "/workbench/trial")):
        raise RuntimeError("Legacy navigation must stay on a canonical workbench entry.")
    return redirect(destination, code=302)


def _page_adapter(endpoint, original, policy, convert_get, build_destination,
                  render_retired, restyled_views):
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
            decision = convert_get(legacy)
            _validate_decision(decision, policy)
            if decision.kind == "redirect":
                response = _destination_response(decision, build_destination)
            else:
                response = current_app.make_response(render_retired(decision))
                response.status_code = 410
        response.headers["Cache-Control"] = "no-store"
        return response
    return adapted


def install_legacy_page_adapters(app, *, convert_get, build_destination,
                                 render_retired, restyled_views):
    """Main calls this once, before serving, only after all presentation gates."""
    if "workbench.legacy_pages" in app.extensions:
        raise RuntimeError("Legacy page adapters are already installed.")
    if not all(callable(value) for value in (convert_get, build_destination, render_retired)):
        raise TypeError("All legacy navigation boundaries must be explicit callables.")
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
            endpoint, app.view_functions[endpoint], policy, convert_get,
            build_destination, render_retired, restyled_views)
    install_legacy_presentation(app)
    app.view_functions.update(replacements)
    app.extensions["workbench.legacy_pages"] = tuple(PAGE_POLICIES)


def _convert_current_request(legacy):
    return resolve_legacy_get(g.db, legacy)


def _render_retired(decision):
    return render_template("workbench/retired.html", title="旧入口已退役", decision=decision)


def install_legacy_retirement(app):
    """Explicit production registration, after applying the companion renderers.

    The print/manual handlers retain their original parsers and now render the
    new templates. There is no TESTING flag, request switch or legacy bypass.
    """
    restyled = {endpoint: app.view_functions.get(endpoint) for endpoint, policy in PAGE_POLICIES.items()
                if policy == "restyle"}
    install_legacy_page_adapters(app, convert_get=_convert_current_request,
                                 build_destination=build_legacy_destination,
                                 render_retired=_render_retired, restyled_views=restyled)

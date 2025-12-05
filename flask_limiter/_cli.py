from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse

from flask import Flask, current_app
from limits.strategies import RateLimiter
from rich.console import Console
from rich.pretty import Pretty
from rich.theme import Theme
from rich.tree import Tree
from werkzeug.exceptions import MethodNotAllowed, NotFound
from werkzeug.routing import Rule

from flask_limiter import ExemptionScope, Limiter
from flask_limiter._limits import RuntimeLimit
from flask_limiter.util import get_qualified_name

limiter_theme = Theme(
    {
        "success": "bold green",
        "danger": "bold red",
        "error": "bold red",
        "blueprint": "bold red",
        "default": "magenta",
        "callable": "cyan",
        "entity": "magenta",
        "exempt": "bold red",
        "route": "yellow",
        "http": "bold green",
        "option": "bold yellow",
    }
)


def render_func(func: Any) -> str | Pretty:
    if callable(func):
        if func.__name__ == "<lambda>":
            return f"[callable]<lambda>({func.__module__})[/callable]"
        return f"[callable]{func.__module__}.{func.__name__}()[/callable]"
    return Pretty(func)


def render_storage(ext: Limiter) -> Tree:
    render = Tree(ext._storage_uri or "N/A")
    if ext.storage:
        render.add(f"[entity]{ext.storage.__class__.__name__}[/entity]")
        render.add(f"[entity]{ext.storage.storage}[/entity]")  # type: ignore
        render.add(Pretty(ext._storage_options or {}))
        health = ext.storage.check()
        if health:
            render.add("[success]OK[/success]")
        else:
            render.add("[error]Error[/error]")
    return render


def render_strategy(strategy: RateLimiter) -> str:
    return f"[entity]{strategy.__class__.__name__}[/entity]"


def render_limit_state(
    limiter: Limiter, endpoint: str, limit: RuntimeLimit, key: str, method: str
) -> str:
    args = [key, limit.scope_for(endpoint, method)]
    if not limiter.storage or (limiter.storage and not limiter.storage.check()):
        return ": [error]Storage not available[/error]"
    test = limiter.limiter.test(limit.limit, *args)
    stats = limiter.limiter.get_window_stats(limit.limit, *args)
    if not test:
        return f": [error]Fail[/error] ({stats[1]} out of {limit.limit.amount} remaining)"
    else:
        return f": [success]Pass[/success] ({stats[1]} out of {limit.limit.amount} remaining)"


def render_limit(limit: RuntimeLimit, simple: bool = True) -> str:
    render = str(limit.limit)
    if simple:
        return render
    options = []
    if limit.deduct_when:
        options.append(f"deduct_when: {render_func(limit.deduct_when)}")
    if limit.exempt_when:
        options.append(f"exempt_when: {render_func(limit.exempt_when)}")
    if options:
        render = f"{render} [option]{{{', '.join(options)}}}[/option]"
    return render


def render_limits(
    app: Flask,
    limiter: Limiter,
    limits: tuple[list[RuntimeLimit], ...],
    endpoint: str | None = None,
    blueprint: str | None = None,
    rule: Rule | None = None,
    exemption_scope: ExemptionScope = ExemptionScope.NONE,
    test: str | None = None,
    method: str = "GET",
    label: str | None = "",
) -> Tree:
    _label = None
    if rule and endpoint:
        _label = f"{endpoint}: {rule}"
    label = _label or label or ""

    renderable = Tree(label)
    entries = []

    for limit in limits[0] + limits[1]:
        if endpoint:
            view_func = app.view_functions.get(endpoint, None)
            source = (
                "blueprint"
                if blueprint and limit in limiter.limit_manager.blueprint_limits(app, blueprint)
                else (
                    "route"
                    if limit
                    in limiter.limit_manager.decorated_limits(
                        get_qualified_name(view_func) if view_func else ""
                    )
                    else "default"
                )
            )
        else:
            source = "default"
        if limit.per_method and rule and rule.methods:
            for method in rule.methods:
                rendered = render_limit(limit, False)
                entry = f"[{source}]{rendered} [http]({method})[/http][/{source}]"
                if test:
                    entry += render_limit_state(limiter, endpoint or "", limit, test, method)
                entries.append(entry)
        else:
            rendered = render_limit(limit, False)
            entry = f"[{source}]{rendered}[/{source}]"
            if test:
                entry += render_limit_state(limiter, endpoint or "", limit, test, method)
            entries.append(entry)
    if not entries and exemption_scope:
        renderable.add("[exempt]Exempt[/exempt]")
    else:
        [renderable.add(entry) for entry in entries]
    return renderable


def get_filtered_endpoint(
    app: Flask,
    console: Console,
    endpoint: str | None,
    path: str | None,
    method: str | None = None,
) -> str | None:
    if not (endpoint or path):
        return None
    if endpoint:
        if endpoint in current_app.view_functions:
            return endpoint
        else:
            console.print(f"[red]Error: {endpoint} not found")
    elif path:
        adapter = app.url_map.bind("dev.null")
        parsed = urlparse(path)
        try:
            filter_endpoint, _ = adapter.match(parsed.path, method=method, query_args=parsed.query)
            return cast(str, filter_endpoint)
        except NotFound:
            console.print(f"[error]Error: {path} could not be matched to an endpoint[/error]")
        except MethodNotAllowed:
            assert method
            console.print(
                f"[error]Error: {method.upper()}: {path}"
                " could not be matched to an endpoint[/error]"
            )
    raise SystemExit

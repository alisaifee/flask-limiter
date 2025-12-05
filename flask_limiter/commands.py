from __future__ import annotations

import itertools
import time
from functools import partial

import click
from click import ClickException
from flask import current_app
from flask.cli import with_appcontext

try:
    from rich.console import Console, group
    from rich.live import Live
    from rich.pretty import Pretty
    from rich.prompt import Confirm
    from rich.table import Table
    from rich.tree import Tree

    from ._cli import (
        get_filtered_endpoint,
        limiter_theme,
        render_func,
        render_limit,
        render_limits,
        render_storage,
        render_strategy,
    )

    CLI_DEPS_AVAILABLE = True
except ImportError:  # noqa
    CLI_DEPS_AVAILABLE = False
from typing_extensions import TypedDict
from werkzeug.routing import Rule

from ._extension import Limiter
from ._limits import RuntimeLimit
from ._typing import Callable, Generator
from .constants import ConfigVars, HeaderNames


@click.group(help="Flask-Limiter maintenance & utility commands")
def cli() -> None:
    if not CLI_DEPS_AVAILABLE:  # noqa
        raise ClickException(
            "Missing dependencies for flask-limiter cli. Please install the cli extra (pip install flask-limiter[cli])"
        )


@cli.command(help="View the extension configuration")
@with_appcontext
def config() -> None:
    with current_app.test_request_context():
        console = Console(theme=limiter_theme)
        limiters = list(current_app.extensions.get("limiter", set()))
        limiter = limiters and list(limiters)[0]
        if limiter:
            extension_details = Table(title="Flask-Limiter Config")
            extension_details.add_column("Notes")
            extension_details.add_column("Configuration")
            extension_details.add_column("Value")
            extension_details.add_row("Enabled", ConfigVars.ENABLED, Pretty(limiter.enabled))
            extension_details.add_row(
                "Key Function", ConfigVars.KEY_FUNC, render_func(limiter._key_func)
            )
            extension_details.add_row(
                "Key Prefix", ConfigVars.KEY_PREFIX, Pretty(limiter._key_prefix)
            )
            limiter_config = Tree(ConfigVars.STRATEGY)
            limiter_config_values = Tree(render_strategy(limiter.limiter))
            node = limiter_config.add(ConfigVars.STORAGE_URI)
            node.add("Instance")
            node.add("Backend")
            limiter_config.add(ConfigVars.STORAGE_OPTIONS)
            limiter_config.add("Status")
            limiter_config_values.add(render_storage(limiter))
            extension_details.add_row("Rate Limiting Config", limiter_config, limiter_config_values)
            if limiter.limit_manager.application_limits:
                extension_details.add_row(
                    "Application Limits",
                    ConfigVars.APPLICATION_LIMITS,
                    Pretty(
                        [render_limit(limit) for limit in limiter.limit_manager.application_limits]
                    ),
                )
                extension_details.add_row(
                    None,
                    ConfigVars.APPLICATION_LIMITS_PER_METHOD,
                    Pretty(limiter._application_limits_per_method),
                )
                extension_details.add_row(
                    None,
                    ConfigVars.APPLICATION_LIMITS_EXEMPT_WHEN,
                    render_func(limiter._application_limits_exempt_when),
                )
                extension_details.add_row(
                    None,
                    ConfigVars.APPLICATION_LIMITS_DEDUCT_WHEN,
                    render_func(limiter._application_limits_deduct_when),
                )
                extension_details.add_row(
                    None,
                    ConfigVars.APPLICATION_LIMITS_COST,
                    Pretty(limiter._application_limits_cost),
                )
            else:
                extension_details.add_row(
                    "ApplicationLimits Limits",
                    ConfigVars.APPLICATION_LIMITS,
                    Pretty([]),
                )
            if limiter.limit_manager.default_limits:
                extension_details.add_row(
                    "Default Limits",
                    ConfigVars.DEFAULT_LIMITS,
                    Pretty([render_limit(limit) for limit in limiter.limit_manager.default_limits]),
                )
                extension_details.add_row(
                    None,
                    ConfigVars.DEFAULT_LIMITS_PER_METHOD,
                    Pretty(limiter._default_limits_per_method),
                )
                extension_details.add_row(
                    None,
                    ConfigVars.DEFAULT_LIMITS_EXEMPT_WHEN,
                    render_func(limiter._default_limits_exempt_when),
                )
                extension_details.add_row(
                    None,
                    ConfigVars.DEFAULT_LIMITS_DEDUCT_WHEN,
                    render_func(limiter._default_limits_deduct_when),
                )
                extension_details.add_row(
                    None,
                    ConfigVars.DEFAULT_LIMITS_COST,
                    render_func(limiter._default_limits_cost),
                )
            else:
                extension_details.add_row("Default Limits", ConfigVars.DEFAULT_LIMITS, Pretty([]))

            if limiter._meta_limits:
                extension_details.add_row(
                    "Meta Limits",
                    ConfigVars.META_LIMITS,
                    Pretty(
                        [render_limit(limit) for limit in itertools.chain(*limiter._meta_limits)]
                    ),
                )
            if limiter._headers_enabled:
                header_configs = Tree(ConfigVars.HEADERS_ENABLED)
                header_configs.add(ConfigVars.HEADER_RESET)
                header_configs.add(ConfigVars.HEADER_REMAINING)
                header_configs.add(ConfigVars.HEADER_RETRY_AFTER)
                header_configs.add(ConfigVars.HEADER_RETRY_AFTER_VALUE)

                header_values = Tree(Pretty(limiter._headers_enabled))
                header_values.add(Pretty(limiter._header_mapping[HeaderNames.RESET]))
                header_values.add(Pretty(limiter._header_mapping[HeaderNames.REMAINING]))
                header_values.add(Pretty(limiter._header_mapping[HeaderNames.RETRY_AFTER]))
                header_values.add(Pretty(limiter._retry_after))
                extension_details.add_row(
                    "Header configuration",
                    header_configs,
                    header_values,
                )
            else:
                extension_details.add_row(
                    "Header configuration", ConfigVars.HEADERS_ENABLED, Pretty(False)
                )

            extension_details.add_row(
                "Fail on first breach",
                ConfigVars.FAIL_ON_FIRST_BREACH,
                Pretty(limiter._fail_on_first_breach),
            )
            extension_details.add_row(
                "On breach callback",
                ConfigVars.ON_BREACH,
                render_func(limiter._on_breach),
            )

            console.print(extension_details)
        else:
            console.print(
                f"No Flask-Limiter extension installed on {current_app}",
                style="bold red",
            )


@cli.command(help="Enumerate details about all routes with rate limits")
@click.option("--endpoint", default=None, help="Endpoint to filter by")
@click.option("--path", default=None, help="Path to filter by")
@click.option("--method", default=None, help="HTTP Method to filter by")
@click.option("--key", default=None, help="Test the limit")
@click.option("--watch/--no-watch", default=False, help="Create a live dashboard")
@with_appcontext
def limits(
    endpoint: str | None = None,
    path: str | None = None,
    method: str = "GET",
    key: str | None = None,
    watch: bool = False,
) -> None:
    with current_app.test_request_context():
        limiters: set[Limiter] = current_app.extensions.get("limiter", set())
        limiter: Limiter | None = list(limiters)[0] if limiters else None
        console = Console(theme=limiter_theme)
        if limiter:
            manager = limiter.limit_manager
            groups: dict[str, list[Callable[..., Tree]]] = {}

            filter_endpoint = get_filtered_endpoint(current_app, console, endpoint, path, method)
            for rule in sorted(
                current_app.url_map.iter_rules(filter_endpoint), key=lambda r: str(r)
            ):
                rule_endpoint = rule.endpoint
                if rule_endpoint == "static":
                    continue
                if len(rule_endpoint.split(".")) > 1:
                    bp_fullname = ".".join(rule_endpoint.split(".")[:-1])
                    groups.setdefault(bp_fullname, []).append(
                        partial(
                            render_limits,
                            current_app,
                            limiter,
                            manager.resolve_limits(current_app, rule_endpoint, bp_fullname),
                            rule_endpoint,
                            bp_fullname,
                            rule,
                            exemption_scope=manager.exemption_scope(
                                current_app, rule_endpoint, bp_fullname
                            ),
                            method=method,
                            test=key,
                        )
                    )
                else:
                    groups.setdefault("root", []).append(
                        partial(
                            render_limits,
                            current_app,
                            limiter,
                            manager.resolve_limits(current_app, rule_endpoint, ""),
                            rule_endpoint,
                            None,
                            rule,
                            exemption_scope=manager.exemption_scope(
                                current_app, rule_endpoint, None
                            ),
                            method=method,
                            test=key,
                        )
                    )

            @group()
            def console_renderable() -> Generator:  # type: ignore
                if limiter and limiter.limit_manager.application_limits and not (endpoint or path):
                    yield render_limits(
                        current_app,
                        limiter,
                        (list(itertools.chain(*limiter._meta_limits)), []),
                        test=key,
                        method=method,
                        label="[gold3]Meta Limits[/gold3]",
                    )
                    yield render_limits(
                        current_app,
                        limiter,
                        (limiter.limit_manager.application_limits, []),
                        test=key,
                        method=method,
                        label="[gold3]Application Limits[/gold3]",
                    )
                for name in groups:
                    if name == "root":
                        group_tree = Tree(f"[gold3]{current_app.name}[/gold3]")
                    else:
                        group_tree = Tree(f"[blue]{name}[/blue]")
                    [group_tree.add(renderable()) for renderable in groups[name]]
                    yield group_tree

            if not watch:
                console.print(console_renderable())
            else:  # noqa
                with Live(
                    console_renderable(),
                    console=console,
                    refresh_per_second=0.4,
                    screen=True,
                ) as live:
                    while True:
                        try:
                            live.update(console_renderable())
                            time.sleep(0.4)
                        except KeyboardInterrupt:
                            break
        else:
            console.print(
                f"No Flask-Limiter extension installed on {current_app}",
                style="bold red",
            )


@cli.command(help="Clear limits for a specific key")
@click.option("--endpoint", default=None, help="Endpoint to filter by")
@click.option("--path", default=None, help="Path to filter by")
@click.option("--method", default=None, help="HTTP Method to filter by")
@click.option("--key", default=None, required=True, help="Key to reset the limits for")
@click.option("-y", is_flag=True, help="Skip prompt for confirmation")
@with_appcontext
def clear(
    key: str,
    endpoint: str | None = None,
    path: str | None = None,
    method: str = "GET",
    y: bool = False,
) -> None:
    with current_app.test_request_context():
        limiters = list(current_app.extensions.get("limiter", set()))
        limiter: Limiter | None = limiters[0] if limiters else None
        console = Console(theme=limiter_theme)
        if limiter:
            manager = limiter.limit_manager
            filter_endpoint = get_filtered_endpoint(current_app, console, endpoint, path, method)

            class Details(TypedDict):
                rule: Rule
                limits: tuple[list[RuntimeLimit], ...]

            rule_limits: dict[str, Details] = {}
            for rule in sorted(
                current_app.url_map.iter_rules(filter_endpoint), key=lambda r: str(r)
            ):
                rule_endpoint = rule.endpoint
                if rule_endpoint == "static":
                    continue
                if len(rule_endpoint.split(".")) > 1:
                    bp_fullname = ".".join(rule_endpoint.split(".")[:-1])
                    rule_limits[rule_endpoint] = Details(
                        rule=rule,
                        limits=manager.resolve_limits(current_app, rule_endpoint, bp_fullname),
                    )
                else:
                    rule_limits[rule_endpoint] = Details(
                        rule=rule,
                        limits=manager.resolve_limits(current_app, rule_endpoint, ""),
                    )
            application_limits = None
            if not filter_endpoint:
                application_limits = limiter.limit_manager.application_limits

            if not y:  # noqa
                if application_limits:
                    console.print(
                        render_limits(
                            current_app,
                            limiter,
                            (application_limits, []),
                            label="Application Limits",
                            test=key,
                        )
                    )
                for endpoint, details in rule_limits.items():
                    if details["limits"]:
                        console.print(
                            render_limits(
                                current_app,
                                limiter,
                                details["limits"],
                                endpoint,
                                rule=details["rule"],
                                test=key,
                            )
                        )
            if y or Confirm.ask(f"Proceed with resetting limits for key: [danger]{key}[/danger]?"):
                if application_limits:
                    node = Tree("Application Limits")
                    for limit in application_limits:
                        limiter.limiter.clear(
                            limit.limit,
                            key,
                            limit.scope_for("", method),
                        )
                        node.add(f"{render_limit(limit)}: [success]Cleared[/success]")
                    console.print(node)
                for endpoint, details in rule_limits.items():
                    if details["limits"]:
                        node = Tree(endpoint)
                        default, decorated = details["limits"]
                        for limit in default + decorated:
                            if (
                                limit.per_method
                                and details["rule"]
                                and details["rule"].methods
                                and not method
                            ):
                                for rule_method in details["rule"].methods:
                                    limiter.limiter.clear(
                                        limit.limit,
                                        key,
                                        limit.scope_for(endpoint, rule_method),
                                    )
                            else:
                                limiter.limiter.clear(
                                    limit.limit,
                                    key,
                                    limit.scope_for(endpoint, method),
                                )
                            node.add(f"{render_limit(limit)}: [success]Cleared[/success]")
                        console.print(node)
        else:
            console.print(
                f"No Flask-Limiter extension installed on {current_app}",
                style="bold red",
            )


if __name__ == "__main__":  # noqa
    cli()

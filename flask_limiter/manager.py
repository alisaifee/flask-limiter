import itertools
import logging
from typing import Dict, Iterable, List, Tuple

from flask import Request, current_app

from .constants import ExemptionScope
from .wrappers import Limit, LimitGroup


class LimitManager:
    def __init__(
        self,
        application_limits: List[LimitGroup],
        default_limits: List[LimitGroup],
        static_route_limits: Dict[str, List[Limit]],
        dynamic_route_limits: Dict[str, List[LimitGroup]],
        static_blueprint_limits: Dict[str, List[Limit]],
        dynamic_blueprint_limits: Dict[str, List[LimitGroup]],
        route_exemptions: Dict[str, ExemptionScope],
        blueprint_exemptions: Dict[str, ExemptionScope],
    ):
        self._application_limits = application_limits
        self._default_limits = default_limits
        self._static_route_limits = static_route_limits
        self._runtime_route_limits = dynamic_route_limits
        self._static_blueprint_limits = static_blueprint_limits
        self._runtime_blueprint_limits = dynamic_blueprint_limits
        self._route_exemptions = route_exemptions
        self._blueprint_exemptions = blueprint_exemptions
        self._logger = logging.getLogger("flask-limiter")

    @property
    def application_limits(self) -> List[Limit]:
        return list(itertools.chain(*self._application_limits))

    @property
    def default_limits(self) -> List[Limit]:
        return list(itertools.chain(*self._default_limits))

    def set_application_limits(self, limits: List[LimitGroup]):
        self._application_limits = limits

    def set_default_limits(self, limits: List[LimitGroup]):
        self._default_limits = limits

    def add_runtime_route_limits(self, route: str, limit: LimitGroup):
        self._runtime_route_limits.setdefault(route, []).append(limit)

    def add_runtime_blueprint_limits(self, blueprint: str, limit: LimitGroup):
        self._runtime_blueprint_limits.setdefault(blueprint, []).append(limit)

    def add_static_route_limits(self, route: str, *limits: Limit):
        self._static_route_limits.setdefault(route, []).extend(limits)

    def add_static_blueprint_limits(self, blueprint: str, *limits: Limit):
        self._static_blueprint_limits.setdefault(blueprint, []).extend(limits)

    def add_route_exemption(self, route: str, scope: ExemptionScope):
        self._route_exemptions[route] = scope

    def add_blueprint_exemption(self, blueprint: str, scope: ExemptionScope):
        self._blueprint_exemptions[blueprint] = scope

    def exemption_scope(self, request) -> ExemptionScope:
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        name = f"{view_func.__module__}.{view_func.__name__}" if view_func else ""
        route_exemption_scope = self._route_exemptions[name]
        if not request.blueprint:
            return route_exemption_scope
        else:
            (
                blueprint_exemption_scope,
                ancestor_exemption_scopes,
            ) = self._blueprint_exemption_scope(request)
            if (
                blueprint_exemption_scope
                & ~(ExemptionScope.DEFAULT | ExemptionScope.APPLICATION)
                or ancestor_exemption_scopes
            ):
                for exemption in ancestor_exemption_scopes.values():
                    blueprint_exemption_scope |= exemption
            return route_exemption_scope | blueprint_exemption_scope

    def route_limits(self, request: Request) -> List[Limit]:
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        name = f"{view_func.__module__}.{view_func.__name__}" if view_func else ""

        limits = []
        if not self._route_exemptions[name]:
            for limit in self._static_route_limits.get(name, []):
                limits.append(limit)

            if name in self._runtime_route_limits:
                for group in self._runtime_route_limits[name]:
                    try:
                        for limit in group:
                            limits.append(limit)
                    except ValueError as e:
                        self._logger.error(
                            f"failed to load ratelimit for view function {name}: {e}",
                        )
        return limits

    def blueprint_limits(self, request) -> List[Limit]:
        limits: List[Limit] = []

        blueprint_name = (
            current_app.blueprints[request.blueprint].name
            if request.blueprint
            else None
        )
        if blueprint_name:
            blueprint_ancestory = set(
                request.blueprint.split(".") if request.blueprint else []
            )

            self_exemption, ancestor_exemptions = self._blueprint_exemption_scope(
                request
            )

            if not (
                self_exemption & ~(ExemptionScope.DEFAULT | ExemptionScope.APPLICATION)
                or ancestor_exemptions
            ):
                blueprint_self_dynamic_limits = self._runtime_blueprint_limits.get(
                    blueprint_name, []
                )
                blueprint_dynamic_limits: Iterable[LimitGroup] = (
                    itertools.chain(
                        *(
                            self._runtime_blueprint_limits.get(member, [])
                            for member in blueprint_ancestory.intersection(
                                self._runtime_blueprint_limits
                            )
                        )
                    )
                    if not (
                        blueprint_self_dynamic_limits
                        or all(
                            limit.override_defaults
                            for limit in blueprint_self_dynamic_limits
                        )
                    )
                    and not self._blueprint_exemptions[blueprint_name]
                    & ExemptionScope.ANCESTORS
                    else blueprint_self_dynamic_limits
                )
                if blueprint_dynamic_limits:
                    for limit_group in blueprint_dynamic_limits:
                        try:
                            limits.extend(
                                [
                                    Limit(
                                        limit.limit,
                                        limit.key_func,
                                        limit.scope,
                                        limit.per_method,
                                        limit.methods,
                                        limit.error_message,
                                        limit.exempt_when,
                                        limit.override_defaults,
                                        limit.deduct_when,
                                        limit.on_breach,
                                        limit.cost,
                                    )
                                    for limit in limit_group
                                ]
                            )
                        except ValueError as e:
                            self._logger.error(
                                f"failed to load ratelimit for blueprint {blueprint_name}: {e}",
                            )
            blueprint_self_limits = self._static_blueprint_limits.get(
                blueprint_name, []
            )
            if (
                not (
                    blueprint_self_limits
                    and all(limit.override_defaults for limit in blueprint_self_limits)
                )
                and not self._blueprint_exemptions[blueprint_name]
                & ExemptionScope.ANCESTORS
            ):
                for member in blueprint_ancestory.intersection(
                    self._static_blueprint_limits
                ).difference(ancestor_exemptions):
                    limits.extend(self._static_blueprint_limits[member])
            else:
                limits.extend(blueprint_self_limits)
        return limits

    def _blueprint_exemption_scope(
        self, request: Request
    ) -> Tuple[ExemptionScope, Dict[str, ExemptionScope]]:
        name = (
            current_app.blueprints[request.blueprint].name
            if request.blueprint
            else None
        )
        exemption = self._blueprint_exemptions[name] & ~(ExemptionScope.ANCESTORS)

        ancestory = set(request.blueprint.split(".") if request.blueprint else [])
        ancestor_exemption = {
            k
            for k, f in self._blueprint_exemptions.items()
            if f & ExemptionScope.DESCENDENTS
        }.intersection(ancestory)

        return exemption, {k: self._blueprint_exemptions[k] for k in ancestor_exemption}

"""
Deterministic network policy firewall.

Rules are evaluated in explicit priority order.
Default policy is DENY.

This is a policy engine, not a packet interception driver.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock


class FirewallAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class FirewallRule:
    rule_id: str
    priority: int
    action: FirewallAction
    source: str = "*"
    destination: str = "*"
    protocol: str = "*"
    port: int | None = None
    enabled: bool = True
    metadata: dict[str, str] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError(
                "rule_id cannot be empty"
            )

        if self.priority < 0:
            raise ValueError(
                "priority cannot be negative"
            )

        if not isinstance(
            self.action,
            FirewallAction,
        ):
            raise TypeError(
                "action must be FirewallAction"
            )

        if (
            self.port is not None
            and not 1 <= self.port <= 65535
        ):
            raise ValueError(
                "port must be between 1 and 65535"
            )


@dataclass(frozen=True, slots=True)
class FirewallDecision:
    action: FirewallAction
    rule_id: str | None
    matched: bool


class FirewallRuleSet:
    """
    Thread-safe firewall policy collection.

    The first matching enabled rule wins.
    """

    def __init__(self) -> None:
        self._rules: dict[
            str,
            FirewallRule,
        ] = {}

        self._lock = RLock()

    def add(
        self,
        rule: FirewallRule,
    ) -> None:

        if not isinstance(
            rule,
            FirewallRule,
        ):
            raise TypeError(
                "rule must be FirewallRule"
            )

        with self._lock:
            if rule.rule_id in self._rules:
                raise ValueError(
                    "firewall rule already exists: "
                    f"{rule.rule_id}"
                )

            self._rules[
                rule.rule_id
            ] = rule

    def remove(
        self,
        rule_id: str,
    ) -> bool:

        with self._lock:
            return (
                self._rules.pop(
                    rule_id.strip(),
                    None,
                )
                is not None
            )

    def evaluate(
        self,
        *,
        source: str,
        destination: str,
        protocol: str,
        port: int | None = None,
    ) -> FirewallDecision:

        source = source.strip()
        destination = destination.strip()
        protocol = protocol.strip().lower()

        if not source:
            raise ValueError(
                "source cannot be empty"
            )

        if not destination:
            raise ValueError(
                "destination cannot be empty"
            )

        if not protocol:
            raise ValueError(
                "protocol cannot be empty"
            )

        with self._lock:
            rules = tuple(
                sorted(
                    (
                        rule
                        for rule
                        in self._rules.values()
                        if rule.enabled
                    ),
                    key=lambda item: (
                        item.priority,
                        item.rule_id,
                    ),
                )
            )

        for rule in rules:
            if (
                rule.source != "*"
                and rule.source != source
            ):
                continue

            if (
                rule.destination != "*"
                and rule.destination
                != destination
            ):
                continue

            if (
                rule.protocol != "*"
                and rule.protocol.lower()
                != protocol
            ):
                continue

            if (
                rule.port is not None
                and rule.port != port
            ):
                continue

            return FirewallDecision(
                action=rule.action,
                rule_id=rule.rule_id,
                matched=True,
            )

        return FirewallDecision(
            action=FirewallAction.DENY,
            rule_id=None,
            matched=False,
        )

    def rules(
        self,
    ) -> tuple[FirewallRule, ...]:

        with self._lock:
            return tuple(
                sorted(
                    self._rules.values(),
                    key=lambda item: (
                        item.priority,
                        item.rule_id,
                    ),
                )
            )


__all__ = [
    "FirewallAction",
    "FirewallRule",
    "FirewallDecision",
    "FirewallRuleSet",
]

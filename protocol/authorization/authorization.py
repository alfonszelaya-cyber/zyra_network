from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Permission:
    resource: str
    action: str

    def __post_init__(self) -> None:
        if not self.resource.strip():
            raise ValueError("Permission resource cannot be empty")
        if not self.action.strip():
            raise ValueError("Permission action cannot be empty")


class AuthorizationPolicy:
    """Explicit allow-list authorization policy."""

    def __init__(self) -> None:
        self._permissions: dict[str, set[Permission]] = {}

    def grant(self, principal: str, permission: Permission) -> None:
        principal = principal.strip()

        if not principal:
            raise ValueError("Principal cannot be empty")

        self._permissions.setdefault(principal, set()).add(permission)

    def revoke(self, principal: str, permission: Permission) -> bool:
        permissions = self._permissions.get(principal.strip())

        if not permissions or permission not in permissions:
            return False

        permissions.remove(permission)

        if not permissions:
            self._permissions.pop(principal.strip(), None)

        return True

    def allowed(
        self,
        principal: str,
        resource: str,
        action: str,
    ) -> bool:
        permission = Permission(resource, action)
        return permission in self._permissions.get(
            principal.strip(),
            set(),
        )

    def permissions(self, principal: str) -> frozenset[Permission]:
        return frozenset(
            self._permissions.get(principal.strip(), set())
        )


__all__ = ["Permission", "AuthorizationPolicy"]

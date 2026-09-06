
from dataclasses import dataclass, field

@dataclass
class SecurityContext:
    subject_id: str
    roles: set[str] = field(default_factory=set)
    permissions: set[str] = field(default_factory=set)

    def has_permission(self, permission):
        return permission in self.permissions


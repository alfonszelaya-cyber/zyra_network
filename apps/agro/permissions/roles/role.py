
class Role:
    def __init__(self, name, permissions=None):
        self.name = name
        self.permissions = set(permissions or [])

    def can(self, permission):
        return permission in self.permissions



class RoleRegistry:
    _roles = {}

    @classmethod
    def register(cls, role):
        cls._roles[role.name] = role

    @classmethod
    def get(cls, name):
        return cls._roles.get(name)


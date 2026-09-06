
class PermissionScope:
    def __init__(self, name, resources=None):
        self.name = name
        self.resources = set(resources or [])

    def contains(self, resource):
        return resource in self.resources


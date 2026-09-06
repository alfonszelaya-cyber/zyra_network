
class PermissionRule:
    def __init__(self, permission):
        self.permission = permission

    def evaluate(self, permissions):
        return self.permission in permissions



class SecurityGateway:
    def authorize(self, context, permission):
        if not context.has_permission(permission):
            raise PermissionError(
                f"Permission denied: {permission}"
            )
        return True


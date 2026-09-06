
class SecurityControlService:
    def record(self, actor_id, action, resource):
        return {
            "actor_id": actor_id,
            "action": action,
            "resource": resource
        }


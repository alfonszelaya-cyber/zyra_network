
from datetime import datetime

class AgroAuditService:
    def record(self, actor_id, action, resource, resource_id):
        return {
            "actor_id": actor_id,
            "action": action,
            "resource": resource,
            "resource_id": resource_id,
            "timestamp": datetime.utcnow().isoformat()
        }


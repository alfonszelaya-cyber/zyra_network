
class OperationActivityService:
    def create(self, operation_id, name):
        return {
            "operation_id": operation_id,
            "name": name,
            "status": "pending"
        }


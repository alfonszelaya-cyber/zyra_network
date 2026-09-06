
class OperationResults:
    def summarize(self, operations):
        completed = sum(
            1 for item in operations
            if item.get("status") == "completed"
        )

        return {
            "total": len(operations),
            "completed": completed
        }


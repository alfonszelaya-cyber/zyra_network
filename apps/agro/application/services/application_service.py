
class ApplicationService:
    def execute(self, operation, *args, **kwargs):
        if not callable(operation):
            raise TypeError("operation must be callable")
        return operation(*args, **kwargs)


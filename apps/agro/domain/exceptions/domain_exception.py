
class AgroDomainError(Exception):
    pass

class ValidationError(AgroDomainError):
    pass

class NotFoundError(AgroDomainError):
    pass


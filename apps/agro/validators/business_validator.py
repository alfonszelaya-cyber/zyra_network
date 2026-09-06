
class BusinessValidator:
    def validate_registration(self, registration_id):
        if not registration_id:
            raise ValueError("Registration ID is required")
        return True


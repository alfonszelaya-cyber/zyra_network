
class ProducerProgramService:
    def enroll(self, producer_id, program_id):
        return {
            "producer_id": producer_id,
            "program_id": program_id,
            "status": "enrolled"
        }


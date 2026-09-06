
class ProducerDocumentService:
    def register(self, producer_id, document):
        return {
            "producer_id": producer_id,
            "document": document,
            "status": "registered"
        }


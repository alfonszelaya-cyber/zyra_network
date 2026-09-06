
class ProducerHistory:
    def __init__(self):
        self.records = {}

    def add(self, producer_id, record):
        self.records.setdefault(producer_id, []).append(record)
        return record

    def get(self, producer_id):
        return list(self.records.get(producer_id, []))


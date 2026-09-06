
class CommunicationService:
    def send(self, recipient_id, message, channel="app"):
        return {
            "recipient_id": recipient_id,
            "message": message,
            "channel": channel,
            "status": "queued"
        }


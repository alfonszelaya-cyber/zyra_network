
class CustomerAssistanceService:
    def answer(self, request, response):
        return {
            "request": request,
            "response": response,
            "source": "ai"
        }


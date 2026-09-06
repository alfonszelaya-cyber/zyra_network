
class OpportunityService:
    def rank(self, opportunities):
        return sorted(
            opportunities,
            key=lambda item: item.get("price", 0),
            reverse=True
        )


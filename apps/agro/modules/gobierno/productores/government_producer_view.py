
class GovernmentProducerView:
    def summarize(self, producers):
        return {
            "total": len(producers),
            "verified": sum(
                1 for p in producers
                if p.get("verified")
            )
        }


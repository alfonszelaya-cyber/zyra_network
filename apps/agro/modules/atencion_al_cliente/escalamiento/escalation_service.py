
class EscalationService:
    def escalate(self, case, reason):
        case = dict(case)
        case["status"] = "escalated"
        case["escalation_reason"] = reason
        case["destination"] = "human_support"
        return case


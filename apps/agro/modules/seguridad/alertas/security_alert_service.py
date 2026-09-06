
class SecurityAlertService:
    def create(self, alert_type, severity, subject):
        return {
            "alert_type": alert_type,
            "severity": severity,
            "subject": subject
        }


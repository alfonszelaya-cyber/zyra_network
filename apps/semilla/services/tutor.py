"""IA-Tutor SEMILLA: the learning companion.

Rules of the tutor (recorded in the ecosystem):
- Stimulates thinking, never answers exams.
- Emotion detection: positive moods get reward
  emojis; negative/critical moods raise alerts
  (professor, and via AXIS: family/hospital).
- Scholarship engine: average >= 8.0 AND
  attendance >= 0.85 -> eligible.
"""
from __future__ import annotations

STIMULUS = {
    "feliz": "🌟 ¡Excelente actitud, sigue asi!",
    "motivado": "🚀 ¡Vamos con todo!",
    "neutro": "📚 Un paso a la vez.",
    "triste": "💙 Estamos contigo. Tu profesor"
              " te acompaña.",
    "enojado": "🧘 Respiremos juntos. Todo"
               " va a estar bien.",
    "enfermo": "🏥 Aviso enviado a tu familia"
               " y al profesor.",
}

CRITICAL_MOODS = ("enfermo",)
ALERT_MOODS = ("triste", "enojado", "enfermo")


class Tutor:
    """Rule-based tutor with provenance-ready
    outputs (the AI engine records provenance in
    a later integration)."""

    def stimulus(self, *, mood: str) -> dict:
        message = STIMULUS.get(
            mood,
            "📚 Un paso a la vez.",
        )
        alert = mood in ALERT_MOODS
        critical = mood in CRITICAL_MOODS
        return {
            "mood": mood,
            "message": message,
            "alert": alert,
            "critical": critical,
            "notify": (
                ["profesor"]
                if alert
                else []
            )
            + (
                [
                    "familia",
                    "hospital",
                    "seguridad",
                ]
                if critical
                else []
            ),
        }

    def scholarship_eligibility(
        self,
        *,
        average: float | None,
        attendance: float | None,
    ) -> dict:
        if average is None or (
            attendance is None
        ):
            return {
                "eligible": False,
                "reason": (
                    "faltan datos"
                    " (notas o"
                    " asistencia)"
                ),
            }
        if (
            average >= 8.0
            and attendance >= 0.85
        ):
            return {
                "eligible": True,
                "reason": (
                    "promedio"
                    f" {average:.1f} y"
                    " asistencia"
                    f" {attendance:.0%}"
                ),
            }
        return {
            "eligible": False,
            "reason": (
                "promedio"
                f" {average:.1f} /"
                " asistencia"
                f" {attendance:.0%}"
                " (requiere 8.0 y 85%)"
            ),
        }

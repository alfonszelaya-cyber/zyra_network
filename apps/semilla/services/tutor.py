"""IA-Tutor SEMILLA v2: adaptive companion."""
from __future__ import annotations

STIMULUS = {
    "feliz": "🌟 ¡Excelente actitud, sigue asi!",
    "motivado": "🚀 ¡Vamos con todo!",
    "neutro": "📚 Un paso a la vez.",
    "triste": "💙 Estamos contigo. Tu profesor te acompaña.",
    "enojado": "🧘 Respiremos juntos. Todo va a estar bien.",
    "enfermo": "🏥 Aviso enviado a tu familia y al profesor.",
}
CRITICAL_MOODS = ("enfermo",)
ALERT_MOODS = ("triste", "enojado", "enfermo")
TALENT_THRESHOLD = 9.0
TALENT_MIN_GRADES = 3
STRENGTH_THRESHOLD = 8.0
WEAKNESS_THRESHOLD = 6.0
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 3

CHALLENGE_BANK = {
    "matematicas": {
        1: {
            "question": "¿Cuanto es 7 + 5?",
            "options": ["11", "12", "13"],
            "answer": "12",
        },
        2: {
            "question": "¿Cuanto es 8 x 7?",
            "options": ["54", "56", "58"],
            "answer": "56",
        },
        3: {
            "question": "¿Raiz cuadrada de 81?",
            "options": ["8", "9", "10"],
            "answer": "9",
        },
    },
    "logica": {
        1: {
            "question": "Ana es mayor que Beto y Beto es mayor que Cara. ¿Quien es la mayor?",
            "options": ["Ana", "Beto", "Cara"],
            "answer": "Ana",
        },
        2: {
            "question": "Si todos los A son B y todos los B son C, entonces:",
            "options": ["Todos los A son C", "Algunos C no son A", "Ninguna de las anteriores"],
            "answer": "Todos los A son C",
        },
        3: {
            "question": "Secuencia: 2, 4, 8, 16. ¿Siguiente?",
            "options": ["20", "24", "32"],
            "answer": "32",
        },
    },
    "lectura": {
        1: {
            "question": "El sol es una...",
            "options": ["estrella", "planta", "roca"],
            "answer": "estrella",
        },
        2: {
            "question": "Sinonimo de 'alegre':",
            "options": ["contento", "triste", "rapido"],
            "answer": "contento",
        },
        3: {
            "question": "Lo contrario de 'efimero' es:",
            "options": ["duradero", "brillante", "pequeno"],
            "answer": "duradero",
        },
    },
}


class Tutor:
    """Rule-based tutor: stimulates, measures, adapts.
    Never answers exams."""

    def stimulus(self, *, mood: str) -> dict:
        message = STIMULUS.get(mood, "📚 Un paso a la vez.")
        alert = mood in ALERT_MOODS
        critical = mood in CRITICAL_MOODS
        return {
            "mood": mood,
            "message": message,
            "alert": alert,
            "critical": critical,
            "notify": (["profesor"] if alert else [])
            + (["familia", "hospital", "seguridad"] if critical else []),
        }

    def scholarship_eligibility(
        self, *, average: float | None, attendance: float | None,
    ) -> dict:
        if average is None or attendance is None:
            return {"eligible": False, "reason": "faltan datos (notas o asistencia)"}
        if average >= 8.0 and attendance >= 0.85:
            return {
                "eligible": True,
                "reason": f"promedio {average:.1f} y asistencia {attendance:.0%}",
            }
        return {
            "eligible": False,
            "reason": (
                f"promedio {average:.1f} / asistencia {attendance:.0%}"
                " (requiere 8.0 y 85%)"
            ),
        }

    def next_challenge(self, *, domain: str, difficulty: int) -> dict:
        bank = CHALLENGE_BANK.get(domain) or CHALLENGE_BANK["matematicas"]
        level = int(difficulty) if int(difficulty) in bank else MIN_DIFFICULTY
        item = bank[level]
        return {
            "domain": domain,
            "difficulty": level,
            "question": item["question"],
            "options": list(item["options"]),
        }

    def check_answer(
        self, *, domain: str, difficulty: int, submitted: str,
    ) -> bool:
        bank = CHALLENGE_BANK.get(domain) or CHALLENGE_BANK["matematicas"]
        item = bank.get(int(difficulty))
        if item is None:
            return False
        return str(submitted).strip() == item["answer"]

    def adapt_difficulty(self, *, difficulty: int, correct: bool) -> int:
        if correct:
            return min(MAX_DIFFICULTY, int(difficulty) + 1)
        return max(MIN_DIFFICULTY, int(difficulty) - 1)

    def detect_talents(self, *, grades) -> list[str]:
        by_subject: dict = {}
        for g in grades:
            by_subject.setdefault(str(g["subject"]), []).append(float(g["score"]))
        talents: list[str] = []
        for subject, scores in by_subject.items():
            if len(scores) >= TALENT_MIN_GRADES:
                if sum(scores) / len(scores) >= TALENT_THRESHOLD:
                    talents.append(subject)
        return talents

    def student_profile(self, *, grades, attendance: float | None) -> dict:
        by_subject: dict = {}
        for g in grades:
            by_subject.setdefault(str(g["subject"]), []).append(float(g["score"]))
        subjects = {}
        for subject, scores in by_subject.items():
            subjects[subject] = round(sum(scores) / len(scores), 2)
        strengths = [s for s, a in subjects.items() if a >= STRENGTH_THRESHOLD]
        weaknesses = [s for s, a in subjects.items() if a < WEAKNESS_THRESHOLD]
        all_scores = [float(g["score"]) for g in grades]
        level = (
            round(sum(all_scores) / len(all_scores), 2) if all_scores else None
        )
        return {
            "level": level,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "subjects": subjects,
            "attendance": attendance,
            "progress": len(grades),
        }

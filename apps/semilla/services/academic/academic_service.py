
"""Academic Service (S-12) - fachada UNICA del
ciclo escolar para wiring del server: construye
todos los engines del ciclo sobre una db/clock y
expone bootstrap canonico."""
from __future__ import annotations
from shared_engines.storage.database import (
    Database)
from apps.semilla.domain.student.student_registry_engine import (
    StudentRegistryEngine)
from apps.semilla.domain.classroom.classroom_engine import (
    ClassroomEngine)
from apps.semilla.domain.academic.enrollment_engine import (
    EnrollmentEngine)
from apps.semilla.domain.academic.academic_history_engine import (
    AcademicHistoryEngine)
from apps.semilla.domain.academic.school_cycle_engine import (
    SchoolCycleEngine)
from apps.semilla.domain.academic.exam_flow_engine import (
    ExamFlowEngine)
from apps.semilla.domain.attendance.linked_attendance_engine import (
    LinkedAttendanceEngine)
from apps.semilla.domain.notifications.alert_engine import (
    AlertEngine)
from apps.semilla.domain.evaluation.notes_flow_engine import (
    NotesFlowEngine)
from apps.semilla.domain.education_ai.tutor_link_engine import (
    TutorLinkEngine)
from apps.semilla.domain.learning.learning_path_engine import (
    LearningPathEngine)
from apps.semilla.domain.certification.certificate_engine import (
    CertificateEngine)
from apps.semilla.domain.admissions.admission_pipeline_engine import (
    AdmissionPipelineEngine)
from apps.semilla.domain.teacher.teacher_workload_engine import (
    TeacherWorkloadEngine)
from apps.semilla.domain.zyra_education_core.education_core_engine import (
    EducationCoreEngine)
from apps.semilla.migrations.database.canonical_migrations import (
    run_all)


class AcademicService:
    """Fachada del ciclo escolar (S-12)."""

    def __init__(self, db, clock):
        self.db = db
        self.clock = clock
        self.students = StudentRegistryEngine(
            db, clock)
        self.classrooms = ClassroomEngine(
            db, clock)
        self.enrollment = EnrollmentEngine(
            db, clock,
            classroom_engine=self.classrooms)
        self.history = AcademicHistoryEngine(
            db, clock)
        self.alerts = AlertEngine(db, clock)
        self.notes = NotesFlowEngine(
            db, clock,
            history_engine=self.history)
        self.attendance = LinkedAttendanceEngine(
            db, clock,
            alert_engine=self.alerts)
        self.exams = ExamFlowEngine(
            db, clock, calendar_engine=None,
            alert_engine=self.alerts,
            notes_flow=self.notes)
        self.cycle = SchoolCycleEngine(
            db, clock,
            student_registry=self.students,
            enrollment_engine=self.enrollment,
            history_engine=self.history)
        self.tutor = TutorLinkEngine(
            db, clock,
            student_registry=self.students)
        self.paths = LearningPathEngine(
            db, clock, tutor_link=self.tutor)
        self.certificates = CertificateEngine(
            db, clock)
        self.admissions = AdmissionPipelineEngine(
            db, clock,
            student_registry=self.students,
            classroom_engine=self.classrooms,
            enrollment_engine=self.enrollment)
        self.workload = TeacherWorkloadEngine(
            db, clock,
            classroom_engine=self.classrooms)
        self.core = EducationCoreEngine(
            db, clock,
            student_registry=self.students)

    def bootstrap_canonical(self) -> None:
        """S-12: garantiza tablas conocidas."""
        run_all(self.db, self.clock)

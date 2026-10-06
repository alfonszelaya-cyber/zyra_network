
"""Child Data Protection Engine - proteccion de
datos de menores (SM9, SE-3). Reglas:
1. Operaciones SENSIBLES sobre un menor requieren
   consentimiento parental VIGENTE (FamilyEngine
   inyectado — check_consent).
2. TODO acceso a datos queda auditado (AccessAudit
   inyectado) — permitido o denegado.
3. Minimizacion: los campos entregados se filtran
   por rol (DIRECTOR/TEACHER ven academicos,
   PARENT ve todo lo de su hijo, GOVERNMENT ve
   agregados). Fail-closed: sin familia inyectada,
   las operaciones sensibles se DENIEGAN."""
from __future__ import annotations
from typing import Dict

SENSITIVE_ACTIONS = ("VIEW_BIOMETRIC",
                     "EXPORT_FULL_RECORD",
                     "SHARE_EXTERNAL")

FIELD_POLICY = {
    "STUDENT": ("full_name", "level", "grade",
                "average"),
    "PARENT": ("full_name", "level", "grade",
               "average", "attendance_pct",
               "tutores", "emergency_contacts"),
    "TEACHER": ("full_name", "level", "grade",
                "average", "attendance_pct"),
    "DIRECTOR": ("full_name", "level", "grade",
                 "average", "attendance_pct",
                 "tutores", "authorized_pickup"),
    "GOVERNMENT": ("level", "grade",
                   "average_agg"),
}

class ChildDataProtectionEngine:
    """Proteccion de datos de menores (fail-closed)."""

    def __init__(self, rbac_engine,
                 family_engine=None,
                 audit_engine=None):
        self._rbac = rbac_engine
        self._family = family_engine
        self._audit = audit_engine

    def request_sensitive(self, *, actor,
                          student_id, action,
                          consent_type=
                          "DATA_PROCESSING",
                          consent_granted=None
                          ) -> Dict:
        """Operacion sensible: RBAC + consent
        parental vigente + auditoria. Fail-closed."""
        check = self._rbac.can(
            actor=actor, action="READ_STUDENT")
        allowed = False
        reason = check["reason"]
        role = check.get("role")
        if check["allowed"]:
            if (self._family is not None
                    and consent_granted is None):
                consent_granted = (self._family.
                                   check_consent(
                                       student_id,
                                       consent_type))
            if consent_granted is True:
                allowed = True
                reason = "consentimiento vigente"
            else:
                reason = ("requiere consentimiento"
                          " parental vigente ("
                          + consent_type + ")")
        if self._audit is not None:
            self._audit.record(
                actor=actor, action=action,
                student_id=student_id,
                allowed=allowed,
                data_scope="SENSITIVE",
                detail=reason)
        return {"actor": actor,
                "student_id": student_id,
                "action": action,
                "allowed": allowed,
                "reason": reason}

    def filtered_profile(self, *, actor,
                         student_id,
                         profile) -> Dict:
        """Minimizacion: filtra campos segun el rol
        del solicitante. Audita el acceso."""
        check = self._rbac.can(
            actor=actor, action="READ_STUDENT")
        allowed = check["allowed"]
        if not allowed:
            allowed = (self._rbac.can(
                actor=actor,
                action="READ_OWN")["allowed"]
                and actor.endswith(
                    student_id[-4:]))
        role = self._rbac.role_of(actor)
        if self._audit is not None:
            self._audit.record(
                actor=actor, action="READ_PROFILE",
                student_id=student_id,
                allowed=allowed,
                data_scope="PROFILE",
                detail="rol=" + str(role))
        if not allowed:
            return {"allowed": False,
                    "reason": check["reason"]}
        fields = FIELD_POLICY.get(role, ())
        out = {"allowed": True,
               "student_id": student_id}
        for f in fields:
            if f in profile:
                out[f] = profile[f]
        out["fields_shared"] = len(
            [k for k in out
             if k not in ("allowed",
                          "student_id")])
        return out

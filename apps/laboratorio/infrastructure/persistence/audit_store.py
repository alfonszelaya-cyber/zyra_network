"""Store SQL de auditoria: registro append-only de operaciones."""
from datetime import datetime

from apps.laboratorio.shared.helpers.json_helpers import a_json
from apps.laboratorio.shared.models.base import ahora_utc


class AuditStore:
    """Escritura y lectura de lab_audit."""

    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("AuditStore requiere conexion.")
        self._cx = conexion

    def registrar(self, actor_zid: str, accion: str, recurso: str, resultado: str, detalle: dict = None) -> int:
        """Registra un hecho de auditoria y devuelve su id."""
        if not actor_zid or not accion or not recurso or not resultado:
            raise ValueError("Auditoria exige actor, accion, recurso y resultado.")
        cursor = self._cx.ejecutar(
            "INSERT INTO lab_audit (momento, actor_zid, accion, recurso, resultado, detalle) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                ahora_utc().isoformat(),
                actor_zid,
                accion,
                recurso,
                resultado,
                a_json(dict(detalle or {})),
            ),
        )
        return int(cursor.lastrowid)

    def listar(self, limite: int = 50, offset: int = 0) -> list:
        """Lista de auditoria, la mas reciente primero."""
        filas = self._cx.consultar(
            "SELECT * FROM lab_audit ORDER BY id DESC LIMIT ? OFFSET ?",
            (int(limite), int(offset)),
        )
        return [
            {
                "id": int(f["id"]),
                "momento": f["momento"],
                "actor_zid": f["actor_zid"],
                "accion": f["accion"],
                "recurso": f["recurso"],
                "resultado": f["resultado"],
                "detalle": f["detalle"],
            }
            for f in filas
        ]

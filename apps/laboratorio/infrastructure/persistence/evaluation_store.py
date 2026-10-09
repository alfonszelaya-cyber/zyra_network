"""Store SQL de evaluaciones de escenarios."""
from apps.laboratorio.infrastructure.persistence.row_mappers import (
    evaluacion_a_fila,
    fila_a_evaluacion,
)


class EvaluationStore:
    """CRUD de lab_evaluations."""

    SQL_INSERT = (
        "INSERT INTO lab_evaluations (id, escenario_id, proyecto_id, metricas, "
        "nota, creado_en, actualizado_en) "
        "VALUES (:id, :escenario_id, :proyecto_id, :metricas, :nota, "
        ":creado_en, :actualizado_en)"
    )

    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("EvaluationStore requiere conexion.")
        self._cx = conexion

    def insertar(self, evaluacion) -> None:
        """Inserta la evaluacion (inmutable: no se actualiza)."""
        self._cx.ejecutar(self.SQL_INSERT, evaluacion_a_fila(evaluacion))

    def obtener(self, id_texto: str):
        """Devuelve la Evaluacion o None."""
        fila = self._cx.consultar_uno(
            "SELECT * FROM lab_evaluations WHERE id = ?", (id_texto,)
        )
        return fila_a_evaluacion(fila) if fila else None

    def listar_por_escenario(self, escenario_id: str, limite: int = 20, offset: int = 0) -> list:
        """Historial de evaluaciones del escenario."""
        filas = self._cx.consultar(
            "SELECT * FROM lab_evaluations WHERE escenario_id = ? "
            "ORDER BY creado_en DESC, id LIMIT ? OFFSET ?",
            (escenario_id, int(limite), int(offset)),
        )
        return [fila_a_evaluacion(f) for f in filas]

    def listar_por_proyecto(self, proyecto_id: str, limite: int = 20, offset: int = 0) -> list:
        """Historial de evaluaciones del proyecto."""
        filas = self._cx.consultar(
            "SELECT * FROM lab_evaluations WHERE proyecto_id = ? "
            "ORDER BY creado_en DESC, id LIMIT ? OFFSET ?",
            (proyecto_id, int(limite), int(offset)),
        )
        return [fila_a_evaluacion(f) for f in filas]

"""Store SQL de escenarios A/B/C."""
from apps.laboratorio.infrastructure.persistence.row_mappers import (
    escenario_a_fila,
    fila_a_escenario,
)


class ScenarioStore:
    """CRUD de lab_scenarios."""

    SQL_INSERT = (
        "INSERT INTO lab_scenarios (id, proyecto_id, tipo, titulo, descripcion, "
        "parametros, creado_en, actualizado_en) "
        "VALUES (:id, :proyecto_id, :tipo, :titulo, :descripcion, "
        ":parametros, :creado_en, :actualizado_en)"
    )
    SQL_UPDATE = (
        "UPDATE lab_scenarios SET tipo=:tipo, titulo=:titulo, "
        "descripcion=:descripcion, parametros=:parametros, "
        "actualizado_en=:actualizado_en WHERE id=:id"
    )

    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("ScenarioStore requiere conexion.")
        self._cx = conexion

    def insertar(self, escenario) -> None:
        """Inserta el escenario."""
        self._cx.ejecutar(self.SQL_INSERT, escenario_a_fila(escenario))

    def actualizar(self, escenario) -> bool:
        """Actualiza y devuelve True si la fila existia."""
        cursor = self._cx.ejecutar(self.SQL_UPDATE, escenario_a_fila(escenario))
        return cursor.rowcount > 0

    def obtener(self, id_texto: str):
        """Devuelve el Escenario o None."""
        fila = self._cx.consultar_uno(
            "SELECT * FROM lab_scenarios WHERE id = ?", (id_texto,)
        )
        return fila_a_escenario(fila) if fila else None

    def listar_por_proyecto(self, proyecto_id: str, limite: int = 20, offset: int = 0) -> list:
        """Lista escenarios del proyecto ordenados por tipo."""
        filas = self._cx.consultar(
            "SELECT * FROM lab_scenarios WHERE proyecto_id = ? "
            "ORDER BY tipo, creado_en LIMIT ? OFFSET ?",
            (proyecto_id, int(limite), int(offset)),
        )
        return [fila_a_escenario(f) for f in filas]

    def eliminar(self, id_texto: str) -> bool:
        """Elimina y devuelve True si existia."""
        cursor = self._cx.ejecutar(
            "DELETE FROM lab_scenarios WHERE id = ?", (id_texto,)
        )
        return cursor.rowcount > 0

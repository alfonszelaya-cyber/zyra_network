"""Store SQL del historial de proyectos (cadena de evidencia)."""
from apps.laboratorio.infrastructure.persistence.row_mappers import (
    fila_a_historial,
    historial_a_fila,
)


class HistoryStore:
    """Escritura y lectura de lab_history."""

    SQL_INSERT = (
        "INSERT INTO lab_history (id, proyecto_id, autor_zid, accion, detalle, "
        "creado_en, actualizado_en) "
        "VALUES (:id, :proyecto_id, :autor_zid, :accion, :detalle, "
        ":creado_en, :actualizado_en)"
    )

    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("HistoryStore requiere conexion.")
        self._cx = conexion

    def insertar(self, entrada) -> None:
        """Inserta la entrada de historial (append-only)."""
        self._cx.ejecutar(self.SQL_INSERT, historial_a_fila(entrada))

    def listar_por_proyecto(self, proyecto_id: str, limite: int = 50, offset: int = 0) -> list:
        """Historial ordenado cronologicamente."""
        filas = self._cx.consultar(
            "SELECT * FROM lab_history WHERE proyecto_id = ? "
            "ORDER BY creado_en, id LIMIT ? OFFSET ?",
            (proyecto_id, int(limite), int(offset)),
        )
        return [fila_a_historial(f) for f in filas]

    def contar_por_proyecto(self, proyecto_id: str) -> int:
        """Cantidad de entradas del proyecto."""
        fila = self._cx.consultar_uno(
            "SELECT COUNT(*) AS n FROM lab_history WHERE proyecto_id = ?",
            (proyecto_id,),
        )
        return int(fila["n"])

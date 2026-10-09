"""Store SQL de proyectos: solo persistencia, sin reglas de negocio."""
from apps.laboratorio.infrastructure.persistence.row_mappers import (
    fila_a_proyecto,
    proyecto_a_fila,
)


class ProyectoStore:
    """CRUD de lab_projects con parametros nombrados."""

    SQL_INSERT = (
        "INSERT INTO lab_projects (id, titulo, descripcion, tipo, etapa, estado, "
        "propietario_zid, etiquetas, creado_en, actualizado_en) "
        "VALUES (:id, :titulo, :descripcion, :tipo, :etapa, :estado, "
        ":propietario_zid, :etiquetas, :creado_en, :actualizado_en)"
    )
    SQL_UPDATE = (
        "UPDATE lab_projects SET titulo=:titulo, descripcion=:descripcion, "
        "tipo=:tipo, etapa=:etapa, estado=:estado, "
        "propietario_zid=:propietario_zid, etiquetas=:etiquetas, "
        "actualizado_en=:actualizado_en WHERE id=:id"
    )

    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("ProyectoStore requiere conexion.")
        self._cx = conexion

    def insertar(self, proyecto) -> None:
        """Inserta el proyecto; falla si el id ya existe."""
        self._cx.ejecutar(self.SQL_INSERT, proyecto_a_fila(proyecto))

    def actualizar(self, proyecto) -> bool:
        """Actualiza y devuelve True si la fila existia."""
        cursor = self._cx.ejecutar(self.SQL_UPDATE, proyecto_a_fila(proyecto))
        return cursor.rowcount > 0

    def obtener(self, id_texto: str):
        """Devuelve el Proyecto o None."""
        fila = self._cx.consultar_uno(
            "SELECT * FROM lab_projects WHERE id = ?", (id_texto,)
        )
        return fila_a_proyecto(fila) if fila else None

    def listar_por_propietario(self, zid: str, limite: int = 20, offset: int = 0) -> list:
        """Lista proyectos del propietario ordenados por creacion."""
        filas = self._cx.consultar(
            "SELECT * FROM lab_projects WHERE propietario_zid = ? "
            "ORDER BY creado_en, id LIMIT ? OFFSET ?",
            (zid, int(limite), int(offset)),
        )
        return [fila_a_proyecto(f) for f in filas]

    def contar(self, zid: str = None) -> int:
        """Cuenta proyectos totales o por propietario."""
        if zid:
            fila = self._cx.consultar_uno(
                "SELECT COUNT(*) AS n FROM lab_projects WHERE propietario_zid = ?",
                (zid,),
            )
        else:
            fila = self._cx.consultar_uno("SELECT COUNT(*) AS n FROM lab_projects")
        return int(fila["n"])

    def eliminar(self, id_texto: str) -> bool:
        """Elimina y devuelve True si existia."""
        cursor = self._cx.ejecutar(
            "DELETE FROM lab_projects WHERE id = ?", (id_texto,)
        )
        return cursor.rowcount > 0

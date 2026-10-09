"""Store SQL de artefactos generados."""
class ArtifactStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("ArtifactStore requiere conexion.")
        self._cx = conexion

    def insertar(self, artefacto) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_artifacts (id, proyecto_id, escena_id, nombre, formato, "
            "contenido, hash, tamano, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(artefacto.id), str(artefacto.proyecto_id), str(artefacto.escena_id),
             artefacto.nombre, artefacto.formato, artefacto.contenido,
             artefacto.hash_sha256, int(artefacto.tamano_bytes),
             artefacto.creado_en.isoformat(), artefacto.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_artifacts WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_artifacts WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.artifact import Artefacto
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        art = Artefacto(
            id=id_desde_texto("art", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            escena_id=id_desde_texto("scn", f["escena_id"]),
            nombre=f["nombre"], formato=f["formato"],
            contenido=f["contenido"], hash_sha256=f["hash"],
            tamano_bytes=int(f["tamano"]),
        )
        art.creado_en = datetime.fromisoformat(f["creado_en"])
        art.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return art

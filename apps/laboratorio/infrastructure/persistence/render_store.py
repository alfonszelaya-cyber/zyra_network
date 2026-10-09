"""Store SQL de trabajos de render (imagen y profundidad en BLOB)."""


class RenderStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("RenderStore requiere conexion.")
        self._cx = conexion

    def insertar(self, render) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_renders (id, proyecto_id, escena_id, calidad, formato, "
            "ancho, alto, imagen, profundidad, hash, duracion_ms, creado_en, "
            "actualizado_en) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(render.id), str(render.proyecto_id), str(render.escena_id),
             render.calidad.value, render.formato, int(render.ancho),
             int(render.alto), bytes(render.imagen),
             bytes(render.profundidad) if render.profundidad else None,
             render.hash_sha256, float(render.duracion_ms),
             render.creado_en.isoformat(), render.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_renders WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT id, proyecto_id, escena_id, calidad, formato, ancho, alto, "
            "hash, duracion_ms, creado_en, actualizado_en, "
            "LENGTH(imagen) AS tamano, profundidad IS NOT NULL AS con_profundidad "
            "FROM lab_renders WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [dict(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.render import TrabajoRender
        from apps.laboratorio.shared.enums.render_quality import RenderQuality
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        render = TrabajoRender(
            id=id_desde_texto("rnd", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            escena_id=id_desde_texto("scn", f["escena_id"]),
            calidad=RenderQuality(f["calidad"]),
            formato=f["formato"],
            ancho=int(f["ancho"]), alto=int(f["alto"]),
            imagen=bytes(f["imagen"]),
            profundidad=bytes(f["profundidad"]) if f["profundidad"] else b"",
            hash_sha256=f["hash"],
            duracion_ms=float(f["duracion_ms"]),
        )
        render.creado_en = datetime.fromisoformat(f["creado_en"])
        render.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return render

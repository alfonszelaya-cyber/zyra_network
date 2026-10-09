"""Store SQL de escenas 3D."""
import json


class SceneStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("SceneStore requiere conexion.")
        self._cx = conexion

    def insertar(self, escena) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_scenes (id, proyecto_id, nombre, ancho, alto, objetos, "
            "creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?)",
            (str(escena.id), str(escena.proyecto_id), escena.nombre,
             int(escena.ancho), int(escena.alto),
             json.dumps(escena.objetos, ensure_ascii=True),
             escena.creado_en.isoformat(), escena.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_scenes WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyecto(self, proyecto_id: str, limite: int = 50) -> list:
        filas = self._cx.consultar(
            "SELECT * FROM lab_scenes WHERE proyecto_id = ? ORDER BY creado_en DESC, id LIMIT ?",
            (proyecto_id, int(limite)),
        )
        return [self._fila_a_entidad(f) for f in filas]

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_scenes WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.scene import Escena3D
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        escena = Escena3D(
            id=id_desde_texto("scn", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            nombre=f["nombre"],
            ancho=int(f["ancho"]), alto=int(f["alto"]),
            objetos=json.loads(f["objetos"] or "[]"),
        )
        escena.creado_en = datetime.fromisoformat(f["creado_en"])
        escena.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return escena

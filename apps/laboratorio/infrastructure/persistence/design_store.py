"""Store SQL de blueprints de diseno."""
import json


class DesignStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("DesignStore requiere conexion.")
        self._cx = conexion

    def insertar(self, blueprint) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_designs (id, proyecto_id, nombre, tipo, componentes, "
            "creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?)",
            (str(blueprint.id), str(blueprint.proyecto_id), blueprint.nombre,
             blueprint.tipo_creacion.value,
             json.dumps(blueprint.componentes, ensure_ascii=True),
             blueprint.creado_en.isoformat(), blueprint.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_designs WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_designs WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.design import Blueprint
        from apps.laboratorio.shared.enums.creation_type import CreationType
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        bp = Blueprint(
            id=id_desde_texto("dsn", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            nombre=f["nombre"],
            tipo_creacion=CreationType(f["tipo"]),
            componentes=json.loads(f["componentes"] or "[]"),
        )
        bp.creado_en = datetime.fromisoformat(f["creado_en"])
        bp.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return bp

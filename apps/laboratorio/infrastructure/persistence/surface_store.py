"""Store SQL de superficies proyectables."""
import json


class SurfaceStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("SurfaceStore requiere conexion.")
        self._cx = conexion

    def insertar(self, superficie) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_surfaces (id, propietario_zid, nombre, tipo, corners, "
            "homografia, calibrada, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?)",
            (str(superficie.id), superficie.propietario_zid, superficie.nombre,
             superficie.tipo.value,
             json.dumps(superficie.corners, ensure_ascii=True),
             json.dumps(superficie.homografia, ensure_ascii=True),
             1 if superficie.calibrada else 0,
             superficie.creado_en.isoformat(), superficie.actualizado_en.isoformat()),
        )

    def actualizar_calibracion(self, superficie) -> bool:
        cursor = self._cx.ejecutar(
            "UPDATE lab_surfaces SET corners = ?, homografia = ?, calibrada = ?, "
            "actualizado_en = ? WHERE id = ?",
            (json.dumps(superficie.corners, ensure_ascii=True),
             json.dumps(superficie.homografia, ensure_ascii=True),
             1 if superficie.calibrada else 0,
             superficie.actualizado_en.isoformat(), str(superficie.id)),
        )
        return cursor.rowcount > 0

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_surfaces WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_propietario(self, zid: str, limite: int = 100) -> list:
        filas = self._cx.consultar(
            "SELECT * FROM lab_surfaces WHERE propietario_zid = ? "
            "ORDER BY creado_en DESC, id LIMIT ?",
            (zid, int(limite)),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.surface import Superficie
        from apps.laboratorio.shared.enums.surface_kind import SurfaceKind
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        sup = Superficie(
            id=id_desde_texto("sup", f["id"]),
            propietario_zid=f["propietario_zid"],
            nombre=f["nombre"],
            tipo=SurfaceKind(f["tipo"]),
            corners=json.loads(f["corners"] or "[]"),
            homografia=json.loads(f["homografia"] or "[]"),
            calibrada=bool(f["calibrada"]),
        )
        sup.creado_en = datetime.fromisoformat(f["creado_en"])
        sup.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return sup

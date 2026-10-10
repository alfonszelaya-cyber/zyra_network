"""Store SQL de destinos de salida."""
class DisplayStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("DisplayStore requiere conexion.")
        self._cx = conexion

    def insertar(self, destino) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_displays (id, propietario_zid, nombre, kind, "
            "creado_en, actualizado_en) VALUES (?,?,?,?,?,?)",
            (str(destino.id), destino.propietario_zid, destino.nombre,
             destino.kind.value,
             destino.creado_en.isoformat(), destino.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_displays WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_propietario(self, zid: str, limite: int = 100) -> list:
        filas = self._cx.consultar(
            "SELECT * FROM lab_displays WHERE propietario_zid = ? "
            "ORDER BY creado_en DESC, id LIMIT ?",
            (zid, int(limite)),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.display import DestinoSalida
        from apps.laboratorio.shared.enums.display_kind import DisplayKind
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        destino = DestinoSalida(
            id=id_desde_texto("dsp", f["id"]),
            propietario_zid=f["propietario_zid"],
            nombre=f["nombre"],
            kind=DisplayKind(f["kind"]),
        )
        destino.creado_en = datetime.fromisoformat(f["creado_en"])
        destino.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return destino

"""Store SQL de activos de biblioteca."""
import json


class AssetStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("AssetStore requiere conexion.")
        self._cx = conexion

    def insertar(self, activo) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_assets (id, propietario_zid, nombre, tipo, contenido, "
            "hash, tamano, etiquetas, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (str(activo.id), activo.propietario_zid, activo.nombre, activo.tipo,
             activo.contenido, activo.hash_sha256, int(activo.tamano_bytes),
             json.dumps(activo.etiquetas, ensure_ascii=True),
             activo.creado_en.isoformat(), activo.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_assets WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_propietario(self, zid: str, limite: int = 100) -> list:
        filas = self._cx.consultar(
            "SELECT * FROM lab_assets WHERE propietario_zid = ? ORDER BY creado_en DESC, id LIMIT ?",
            (zid, int(limite)),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.asset import Activo
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        activo = Activo(
            id=id_desde_texto("ast", f["id"]),
            propietario_zid=f["propietario_zid"],
            nombre=f["nombre"], tipo=f["tipo"],
            contenido=f["contenido"], hash_sha256=f["hash"],
            tamano_bytes=int(f["tamano"]),
            etiquetas=json.loads(f["etiquetas"] or "[]"),
        )
        activo.creado_en = datetime.fromisoformat(f["creado_en"])
        activo.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return activo

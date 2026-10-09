"""Store SQL de exportaciones."""
import json


class ExportStore:
    def __init__(self, conexion):
        if conexion is None:
            raise ValueError("ExportStore requiere conexion.")
        self._cx = conexion

    def insertar(self, exportacion) -> None:
        self._cx.ejecutar(
            "INSERT INTO lab_exports (id, proyecto_id, tipo, destino, piezas, "
            "tamano_total, hash, creado_en, actualizado_en) VALUES (?,?,?,?,?,?,?,?,?)",
            (str(exportacion.id), str(exportacion.proyecto_id), exportacion.tipo,
             exportacion.destino,
             json.dumps(exportacion.piezas, ensure_ascii=True),
             int(exportacion.tamano_total), exportacion.hash_sha256,
             exportacion.creado_en.isoformat(), exportacion.actualizado_en.isoformat()),
        )

    def obtener(self, id_texto: str):
        fila = self._cx.consultar_uno("SELECT * FROM lab_exports WHERE id = ?", (id_texto,))
        return self._fila_a_entidad(fila) if fila else None

    def listar_por_proyectos(self, proyecto_ids: list, limite: int = 100) -> list:
        if not proyecto_ids:
            return []
        marcadores = ",".join("?" * len(proyecto_ids))
        filas = self._cx.consultar(
            "SELECT * FROM lab_exports WHERE proyecto_id IN (" + marcadores + ") "
            "ORDER BY creado_en DESC, id LIMIT ?",
            ([str(p) for p in proyecto_ids] + [int(limite)]),
        )
        return [self._fila_a_entidad(f) for f in filas]

    @staticmethod
    def _fila_a_entidad(f):
        from datetime import datetime
        from apps.laboratorio.domain.export_bundle import Exportacion
        from apps.laboratorio.shared.models.identifiers import id_desde_texto
        exp = Exportacion(
            id=id_desde_texto("exp", f["id"]),
            proyecto_id=id_desde_texto("proy", f["proyecto_id"]),
            tipo=f["tipo"],
            destino=f["destino"],
            piezas=json.loads(f["piezas"] or "[]"),
            tamano_total=int(f["tamano_total"]),
            hash_sha256=f["hash"],
        )
        exp.creado_en = datetime.fromisoformat(f["creado_en"])
        exp.actualizado_en = datetime.fromisoformat(f["actualizado_en"])
        return exp

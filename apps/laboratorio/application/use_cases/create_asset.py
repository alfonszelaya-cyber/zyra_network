"""Caso de uso: guardar activo en la biblioteca con sellado SHA-256."""
from apps.laboratorio.application.commands.creation_commands import ComandoCrearActivo
from apps.laboratorio.domain.asset import Activo
from apps.laboratorio.shared.helpers.hashing import sha256_texto
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoCrearActivo:
    def __init__(self, repo_activos, auditoria):
        self._activos = repo_activos
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoCrearActivo, identidad) -> dict:
        if not isinstance(comando, ComandoCrearActivo):
            raise ValueError("Se esperaba ComandoCrearActivo.")
        if not comando.contenido.strip():
            raise ValueError("El activo requiere contenido.")
        activo = Activo(
            id=nuevo_id("ast"),
            propietario_zid=identidad.zid,
            nombre=comando.nombre,
            tipo=comando.tipo,
            contenido=comando.contenido,
            hash_sha256=sha256_texto(comando.contenido),
            tamano_bytes=len(comando.contenido.encode("utf-8")),
            etiquetas=list(comando.etiquetas),
        )
        self._activos.agregar(activo)
        self._auditoria.registrar(
            identidad, "activo.crear", str(activo.id), "exito",
            {"tipo": activo.tipo, "tamano": activo.tamano_bytes},
        )
        return {"activo": self._a_dict(activo)}

    @staticmethod
    def _a_dict(activo) -> dict:
        return {
            "id": str(activo.id),
            "propietario_zid": activo.propietario_zid,
            "nombre": activo.nombre,
            "tipo": activo.tipo,
            "hash_sha256": activo.hash_sha256,
            "tamano_bytes": activo.tamano_bytes,
            "etiquetas": list(activo.etiquetas),
            "preview": activo.contenido[:80],
            "creado_en": activo.creado_en.isoformat(),
        }

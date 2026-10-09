"""Caso de uso: generar artefacto real desde una escena."""
from apps.laboratorio.application.commands.creation_commands import ComandoGenerarArtefacto
from apps.laboratorio.domain.artifact import FORMATOS_GENERACION, Artefacto
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.helpers.hashing import sha256_bytes
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoGenerarArtefacto:
    def __init__(self, repo_escenas, repo_artefactos, repo_proyectos, repo_historial, motor, auditoria):
        self._escenas = repo_escenas
        self._artefactos = repo_artefactos
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._motor = motor
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoGenerarArtefacto, identidad) -> dict:
        if not isinstance(comando, ComandoGenerarArtefacto):
            raise ValueError("Se esperaba ComandoGenerarArtefacto.")
        escena = self._escenas.obtener_exigir(comando.escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        if comando.formato not in FORMATOS_GENERACION:
            raise ValueError(
                "El formato '" + str(comando.formato)
                + "' no esta disponible. El video MP4 llega con el motor de secuencia (fase 6)."
            )
        bytes_generados = self._motor.generar(escena, comando.formato)
        artefacto = Artefacto(
            id=nuevo_id("art"), proyecto_id=proyecto.id, escena_id=escena.id,
            nombre=escena.nombre + " (" + comando.formato + ")",
            formato=comando.formato,
            contenido=bytes_generados.decode("utf-8"),
            hash_sha256=sha256_bytes(bytes_generados),
            tamano_bytes=len(bytes_generados),
        )
        self._artefactos.agregar(artefacto)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="artefacto.generado",
            detalle={"artefacto_id": str(artefacto.id),
                     "formato": comando.formato, "tamano": artefacto.tamano_bytes},
        ))
        self._auditoria.registrar(
            identidad, "artefacto.generar", str(artefacto.id), "exito",
            {"formato": comando.formato, "tamano": artefacto.tamano_bytes},
        )
        return {"artefacto": self._a_dict(artefacto)}

    @staticmethod
    def _a_dict(artefacto) -> dict:
        preview = artefacto.contenido[:120] if artefacto.formato != "imagen" else "[SVG]"
        return {
            "id": str(artefacto.id),
            "proyecto_id": str(artefacto.proyecto_id),
            "escena_id": str(artefacto.escena_id),
            "nombre": artefacto.nombre,
            "formato": artefacto.formato,
            "mime": artefacto.mime,
            "hash_sha256": artefacto.hash_sha256,
            "tamano_bytes": artefacto.tamano_bytes,
            "preview": preview,
            "creado_en": artefacto.creado_en.isoformat(),
        }

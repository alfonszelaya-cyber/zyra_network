"""Caso de uso: crear escena 3D con objetos validados."""
from apps.laboratorio.application.commands.creation_commands import ComandoCrearEscena
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.domain.scene import Escena3D
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoCrearEscena:
    def __init__(self, repo_escenas, repo_proyectos, repo_historial, auditoria):
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoCrearEscena, identidad) -> dict:
        if not isinstance(comando, ComandoCrearEscena):
            raise ValueError("Se esperaba ComandoCrearEscena.")
        proyecto = self._proyectos.obtener_exigir(comando.proyecto_id)
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        if not comando.objetos:
            raise ValueError("Una escena requiere al menos un objeto.")
        escena = Escena3D(
            id=nuevo_id("scn"), proyecto_id=proyecto.id,
            nombre=comando.nombre, ancho=comando.ancho, alto=comando.alto,
        )
        for obj in comando.objetos:
            escena.agregar_objeto(obj)
        self._escenas.agregar(escena)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="escena.creada",
            detalle={"escena_id": str(escena.id), "objetos": len(escena.objetos)},
        ))
        self._auditoria.registrar(
            identidad, "escena.crear", str(escena.id), "exito",
            {"objetos": len(escena.objetos)},
        )
        return {"escena": self._a_dict(escena)}

    @staticmethod
    def _a_dict(escena) -> dict:
        return {
            "id": str(escena.id),
            "proyecto_id": str(escena.proyecto_id),
            "nombre": escena.nombre,
            "ancho": escena.ancho,
            "alto": escena.alto,
            "objetos": list(escena.objetos),
            "total_objetos": len(escena.objetos),
            "creado_en": escena.creado_en.isoformat(),
        }

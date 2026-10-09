"""Manejador de creacion: escenas y generacion de artefactos."""
from apps.laboratorio.application.commands.creation_commands import (
    ComandoCrearEscena,
    ComandoGenerarArtefacto,
)
from apps.laboratorio.application.use_cases.create_scene import CasoCrearEscena
from apps.laboratorio.application.use_cases.generate_artifact import CasoGenerarArtefacto
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorCreacion:
    def __init__(self, caso_escena, caso_generar, repo_escenas, repo_artefactos, repo_proyectos, auditoria):
        self._caso_escena = caso_escena
        self._caso_generar = caso_generar
        self._escenas = repo_escenas
        self._artefactos = repo_artefactos
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def crear_escena(self, identidad, proyecto_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        nombre = str(datos.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("La escena requiere nombre.")
        objetos = datos.get("objetos", [])
        if not isinstance(objetos, list):
            raise ValueError("objetos debe ser una lista.")
        comando = ComandoCrearEscena(
            proyecto_id=proyecto_id, nombre=nombre[:200],
            ancho=int(datos.get("ancho", 800)), alto=int(datos.get("alto", 600)),
            objetos=tuple(objetos),
        )
        resultado = self._caso_escena.ejecutar(comando, identidad)
        return exito(resultado, 201)

    def listar_escenas(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        escenas = self._escenas.listar_por_proyecto(proyecto.id)
        return exito({
            "escenas": [CasoCrearEscena._a_dict(e) for e in escenas],
            "total": len(escenas),
        })

    def obtener_escena(self, identidad, escena_id: str) -> tuple:
        escena = self._escenas.obtener_exigir(escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        return exito({"escena": CasoCrearEscena._a_dict(escena)})

    def generar(self, identidad, escena_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict) or not str(datos.get("formato", "")).strip():
            raise ValueError("Falta el campo formato.")
        comando = ComandoGenerarArtefacto(
            escena_id=escena_id, formato=str(datos["formato"]).strip().lower(),
        )
        resultado = self._caso_generar.ejecutar(comando, identidad)
        return exito(resultado, 201)

    def listar_artefactos(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        artefactos = self._artefactos.listar_por_proyectos([proyecto.id])
        return exito({
            "artefactos": [CasoGenerarArtefacto._a_dict(a) for a in artefactos],
            "total": len(artefactos),
        })

    def descargar_artefacto(self, identidad, artefacto_id: str) -> tuple:
        artefacto = self._artefactos.obtener_exigir(artefacto_id)
        proyecto = self._proyectos.obtener_exigir(str(artefacto.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        if artefacto.mime.startswith("image"):
            extension = "svg"
        elif "html" in artefacto.mime:
            extension = "html"
        else:
            extension = "json"
        return 200, artefacto.contenido.encode("utf-8"), {
            "Content-Type": artefacto.mime,
            "Content-Disposition": "inline; filename=art_" + str(artefacto.id) + "." + extension,
        }

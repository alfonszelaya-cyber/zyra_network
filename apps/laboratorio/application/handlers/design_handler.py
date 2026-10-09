"""Manejador de blueprints de diseno."""
from apps.laboratorio.application.commands.input_commands import ComandoCrearBlueprint
from apps.laboratorio.application.use_cases.create_blueprint import CasoCrearBlueprint
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorDisenos:
    def __init__(self, caso, repo_disenos, repo_proyectos, auditoria):
        self._caso = caso
        self._disenos = repo_disenos
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def crear(self, identidad, proyecto_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        nombre = str(datos.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("El blueprint requiere nombre.")
        componentes = datos.get("componentes", [])
        if not isinstance(componentes, list):
            raise ValueError("componentes debe ser una lista.")
        comando = ComandoCrearBlueprint(
            proyecto_id=proyecto_id, nombre=nombre[:200],
            tipo=str(datos.get("tipo", "")),
            componentes=tuple(componentes),
        )
        resultado = self._caso.ejecutar(comando, identidad)
        return exito(resultado, 201)

    def listar(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        disenos = self._disenos.listar_por_proyectos([proyecto.id])
        return exito({
            "blueprints": [CasoCrearBlueprint._a_dict(b) for b in disenos],
            "total": len(disenos),
        })

    def obtener(self, identidad, design_id: str) -> tuple:
        bp = self._disenos.obtener_exigir(design_id)
        proyecto = self._proyectos.obtener_exigir(str(bp.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        return exito({"blueprint": CasoCrearBlueprint._a_dict(bp)})

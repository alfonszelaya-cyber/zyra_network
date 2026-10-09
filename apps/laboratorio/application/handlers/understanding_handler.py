"""Manejador de comprension de entradas."""
from apps.laboratorio.application.commands.input_commands import ComandoComprenderEntrada
from apps.laboratorio.application.use_cases.understand_input import CasoComprenderEntrada
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorComprension:
    def __init__(self, caso, repo_inputs, repo_comprensiones, repo_proyectos, auditoria):
        self._caso = caso
        self._inputs = repo_inputs
        self._comprensiones = repo_comprensiones
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def comprender(self, identidad, entrada_id: str) -> tuple:
        resultado = self._caso.ejecutar(ComandoComprenderEntrada(entrada_id), identidad)
        return exito(resultado)

    def obtener(self, identidad, entrada_id: str) -> tuple:
        entrada = self._inputs.obtener_exigir(entrada_id)
        proyecto = self._proyectos.obtener_exigir(str(entrada.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        comprension = self._comprensiones.obtener_por_entrada(entrada.id)
        if comprension is None:
            return exito({"comprension": None, "mensaje": "Entrada sin comprender todavia"})
        return exito({"comprension": CasoComprenderEntrada._a_dict(comprension)})

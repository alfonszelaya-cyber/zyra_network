"""Caso de uso: comprender una entrada con el motor real."""
from apps.laboratorio.application.commands.input_commands import ComandoComprenderEntrada
from apps.laboratorio.domain.history import EntradaHistorial
from apps.laboratorio.domain.understanding import Comprension
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.shared.models.identifiers import nuevo_id


class CasoComprenderEntrada:
    def __init__(self, repo_inputs, repo_comprensiones, repo_proyectos, repo_historial, motor, auditoria):
        self._inputs = repo_inputs
        self._comprensiones = repo_comprensiones
        self._proyectos = repo_proyectos
        self._historial = repo_historial
        self._motor = motor
        self._auditoria = auditoria

    def ejecutar(self, comando: ComandoComprenderEntrada, identidad) -> dict:
        if not isinstance(comando, ComandoComprenderEntrada):
            raise ValueError("Se esperaba ComandoComprenderEntrada.")
        entrada = self._inputs.obtener_exigir(comando.entrada_id)
        proyecto = self._proyectos.obtener_exigir(str(entrada.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        existente = self._comprensiones.obtener_por_entrada(entrada.id)
        if existente is not None:
            return {"comprension": self._a_dict(existente), "reutilizada": True}
        if entrada.tipo.value in ("foto", "escaneo"):
            raise ValueError(
                "La comprension visual de imagenes llega con el motor de vision (fase 3)."
            )
        resultado = self._motor.analizar(entrada.contenido)
        comprension = Comprension(
            id=nuevo_id("und"), entrada_id=entrada.id, proyecto_id=proyecto.id,
            resumen=resultado["resumen"], hallazgos=resultado["hallazgos"],
            entidades=resultado["entidades"], dominio=resultado["dominio"],
            confianza=resultado["confianza"],
        )
        self._comprensiones.agregar(comprension)
        self._historial.agregar(EntradaHistorial(
            id=nuevo_id("his"), proyecto_id=proyecto.id,
            autor_zid=identidad.zid, accion="entrada.comprendida",
            detalle={"entrada_id": str(entrada.id),
                     "hallazgos": comprension.total_hallazgos,
                     "dominio": comprension.dominio},
        ))
        self._auditoria.registrar(
            identidad, "entrada.comprender", str(entrada.id), "exito",
            {"hallazgos": comprension.total_hallazgos, "dominio": comprension.dominio},
        )
        return {"comprension": self._a_dict(comprension), "reutilizada": False}

    @staticmethod
    def _a_dict(comprension) -> dict:
        return {
            "id": str(comprension.id),
            "entrada_id": str(comprension.entrada_id),
            "proyecto_id": str(comprension.proyecto_id),
            "resumen": comprension.resumen,
            "hallazgos": list(comprension.hallazgos),
            "entidades": dict(comprension.entidades),
            "dominio": comprension.dominio,
            "confianza": comprension.confianza,
            "total_hallazgos": comprension.total_hallazgos,
            "creado_en": comprension.creado_en.isoformat(),
        }

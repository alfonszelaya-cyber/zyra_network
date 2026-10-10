"""Casos de uso de escaneo por foto y avatar desde foto."""
from apps.laboratorio.application.commands.creation_commands import ComandoCrearActivo
from apps.laboratorio.application.use_cases.create_asset import CasoCrearActivo
from apps.laboratorio.infrastructure.providers.avatar_engine import MotorAvatar
from apps.laboratorio.infrastructure.providers.scanner_photo import (
    MotorEscaneoFoto,
    foto_desde_entrada,
)
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto


class CasoEscanearFoto:
    def __init__(self, repo_inputs, repo_proyectos, motor_scanner, auditoria):
        self._inputs = repo_inputs
        self._proyectos = repo_proyectos
        self._motor = motor_scanner
        self._auditoria = auditoria

    def ejecutar(self, identidad, entrada_id: str) -> dict:
        entrada = self._inputs.obtener_exigir(entrada_id)
        proyecto = self._proyectos.obtener_exigir(str(entrada.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        if entrada.tipo.value not in ("foto", "escaneo"):
            raise ValueError(
                "Solo se escanean entradas de tipo foto o escaneo; esta es "
                + entrada.tipo.value + "."
            )
        datos_png = foto_desde_entrada(entrada.contenido)
        resultado = self._motor.escanear(datos_png)
        self._auditoria.registrar(
            identidad, "foto.escanear", str(entrada.id), "exito",
            {"bordes": resultado["total_bordes"],
             "esquinas": len(resultado["esquinas"])},
        )
        return {
            "entrada_id": str(entrada.id),
            "proyecto_id": str(proyecto.id),
            "escaneo": resultado,
            "hash_foto": entrada.hash_sha256,
        }


class CasoAvatarDesdeFoto:
    def __init__(self, repo_inputs, repo_proyectos, caso_crear_activo, motor_avatar, auditoria):
        self._inputs = repo_inputs
        self._proyectos = repo_proyectos
        self._caso_activo = caso_crear_activo
        self._motor = motor_avatar
        self._auditoria = auditoria

    def ejecutar(self, identidad, entrada_id: str) -> dict:
        entrada = self._inputs.obtener_exigir(entrada_id)
        proyecto = self._proyectos.obtener_exigir(str(entrada.proyecto_id))
        PoliticaProyecto.exigir_editar(proyecto, identidad)
        if entrada.tipo.value not in ("foto", "escaneo"):
            raise ValueError(
                "Solo se crean avatares desde entradas de tipo foto o escaneo; "
                "esta es " + entrada.tipo.value + "."
            )
        datos_png = foto_desde_entrada(entrada.contenido)
        svg_bytes = self._motor.generar(datos_png, entrada.titulo)
        comando = ComandoCrearActivo(
            nombre="Avatar de " + entrada.titulo[:160],
            tipo="svg",
            contenido=svg_bytes.decode("utf-8"),
            etiquetas=("avatar", entrada.tipo.value),
        )
        activo = self._caso_activo.ejecutar(comando, identidad)
        self._auditoria.registrar(
            identidad, "avatar.crear", str(entrada.id), "exito",
            {"activo_id": activo["activo"]["id"]},
        )
        return {
            "entrada_id": str(entrada.id),
            "avatar": activo["activo"],
            "preview": activo["activo"]["preview"],
        }

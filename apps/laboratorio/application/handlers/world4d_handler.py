"""Manejador del 4D: lineas de tiempo, luz e interacciones."""
from apps.laboratorio.application.commands.world4d_commands import (
    ComandoCrearInteraccion,
    ComandoCrearLineaTiempo,
    ComandoCrearProgramaLuz,
)
from apps.laboratorio.application.use_cases.world4d import (
    CasoCrearInteraccion,
    CasoCrearLineaTiempo,
    CasoCrearProgramaLuz,
)
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorCuatroD:
    def __init__(
        self, caso_timeline, caso_luz, caso_interaccion,
        repo_timelines, repo_luces, repo_interacciones,
        repo_escenas, repo_proyectos, auditoria,
    ):
        self._caso_timeline = caso_timeline
        self._caso_luz = caso_luz
        self._caso_interaccion = caso_interaccion
        self._timelines = repo_timelines
        self._luces = repo_luces
        self._interacciones = repo_interacciones
        self._escenas = repo_escenas
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def _escena_verificada(self, identidad, escena_id: str, editar: bool):
        escena = self._escenas.obtener_exigir(escena_id)
        proyecto = self._proyectos.obtener_exigir(str(escena.proyecto_id))
        if editar:
            PoliticaProyecto.exigir_editar(proyecto, identidad)
        else:
            PoliticaProyecto.exigir_ver(proyecto, identidad)
        return escena

    def crear_timeline(self, identidad, escena_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        pistas = datos.get("pistas", [])
        if not isinstance(pistas, list):
            raise ValueError("pistas debe ser una lista.")
        comando = ComandoCrearLineaTiempo(
            escena_id=escena_id,
            duracion_s=float(datos.get("duracion_s", 10.0)),
            fps=int(datos.get("fps", 30)),
            pistas=tuple(pistas),
        )
        resultado = self._caso_timeline.ejecutar(comando, identidad)
        return exito(resultado, 201)

    def obtener_timeline(self, identidad, escena_id: str) -> tuple:
        self._escena_verificada(identidad, escena_id, editar=False)
        linea = self._timelines.obtener_por_escena(escena_id)
        if linea is None:
            return exito({"timeline": None, "mensaje": "Escena sin linea de tiempo"})
        return exito({"timeline": CasoCrearLineaTiempo._a_dict(linea)})

    def crear_luz(self, identidad, escena_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        pasos = datos.get("pasos", [])
        if not isinstance(pasos, list):
            raise ValueError("pasos debe ser una lista.")
        comando = ComandoCrearProgramaLuz(
            escena_id=escena_id,
            pasos=tuple(pasos),
            ambientar_fondo=bool(datos.get("ambientar_fondo", False)),
        )
        resultado = self._caso_luz.ejecutar(comando, identidad)
        return exito(resultado, 201)

    def obtener_luz(self, identidad, escena_id: str) -> tuple:
        self._escena_verificada(identidad, escena_id, editar=False)
        programa = self._luces.obtener_por_escena(escena_id)
        if programa is None:
            return exito({"lighting": None, "mensaje": "Escena sin programa de luz"})
        return exito({"lighting": CasoCrearProgramaLuz._a_dict(programa)})

    def crear_interaccion(self, identidad, escena_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        titulo = str(datos.get("titulo", "")).strip()
        if not titulo:
            raise ValueError("La interaccion requiere titulo.")
        comando = ComandoCrearInteraccion(
            escena_id=escena_id,
            x=float(datos.get("x", 0)), y=float(datos.get("y", 0)),
            w=float(datos.get("w", 100)), h=float(datos.get("h", 100)),
            accion=str(datos.get("accion", "clic")),
            titulo=titulo[:200],
        )
        resultado = self._caso_interaccion.ejecutar(comando, identidad)
        return exito(resultado, 201)

    def listar_interacciones(self, identidad, escena_id: str) -> tuple:
        self._escena_verificada(identidad, escena_id, editar=False)
        zonas = self._interacciones.listar_por_escena(escena_id)
        return exito({
            "interacciones": [CasoCrearInteraccion._a_dict(z) for z in zonas],
            "total": len(zonas),
        })

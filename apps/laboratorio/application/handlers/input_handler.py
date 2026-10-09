"""Manejador de capturas y su consulta."""
from apps.laboratorio.application.commands.input_commands import ComandoCapturarEntrada
from apps.laboratorio.application.use_cases.capture_input import CasoCapturarEntrada
from apps.laboratorio.permissions.policies.project_policy import PoliticaProyecto
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorCapturas:
    def __init__(self, caso, repo_inputs, repo_proyectos, auditoria):
        self._caso = caso
        self._inputs = repo_inputs
        self._proyectos = repo_proyectos
        self._auditoria = auditoria

    def crear(self, identidad, proyecto_id: str, datos: dict) -> tuple:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        titulo = str(datos.get("titulo", "")).strip()
        if not titulo:
            raise ValueError("La entrada requiere titulo.")
        titulo = titulo[:200]
        comando = ComandoCapturarEntrada(
            proyecto_id=proyecto_id,
            tipo=str(datos.get("tipo", "texto")),
            titulo=titulo,
            contenido=str(datos.get("contenido", "")),
        )
        resultado = self._caso.ejecutar(comando, identidad)
        return exito(resultado, 201)

    def listar(self, identidad, proyecto_id: str) -> tuple:
        proyecto = self._proyectos.obtener_exigir(proyecto_id)
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        entradas = self._inputs.listar_por_proyecto(proyecto.id)
        return exito({
            "entradas": [CasoCapturarEntrada._a_dict(e) for e in entradas],
            "total": len(entradas),
        })

    def obtener(self, identidad, entrada_id: str) -> tuple:
        entrada = self._inputs.obtener_exigir(entrada_id)
        proyecto = self._proyectos.obtener_exigir(str(entrada.proyecto_id))
        PoliticaProyecto.exigir_ver(proyecto, identidad)
        return exito({"entrada": CasoCapturarEntrada._a_dict(entrada)})

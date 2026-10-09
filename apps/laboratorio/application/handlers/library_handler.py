"""Manejador de biblioteca: activos y busqueda."""
from apps.laboratorio.application.commands.creation_commands import ComandoCrearActivo
from apps.laboratorio.application.use_cases.create_asset import CasoCrearActivo
from apps.laboratorio.schemas.responses.envelopes import exito


class ManejadorBiblioteca:
    def __init__(self, caso, repo_activos, auditoria):
        self._caso = caso
        self._activos = repo_activos
        self._auditoria = auditoria

    def crear(self, identidad, datos: dict) -> tuple:
        if not isinstance(datos, dict):
            raise ValueError("Cuerpo invalido.")
        nombre = str(datos.get("nombre", "")).strip()
        if not nombre:
            raise ValueError("El activo requiere nombre.")
        tipo = str(datos.get("tipo", "")).strip().lower()
        etiquetas = datos.get("etiquetas", [])
        if not isinstance(etiquetas, list):
            raise ValueError("etiquetas debe ser una lista.")
        comando = ComandoCrearActivo(
            nombre=nombre[:200], tipo=tipo,
            contenido=str(datos.get("contenido", "")),
            etiquetas=tuple(str(e).strip() for e in etiquetas),
        )
        resultado = self._caso.ejecutar(comando, identidad)
        return exito(resultado, 201)

    def listar(self, identidad) -> tuple:
        activos = self._activos.listar_por_propietario(identidad.zid)
        return exito({
            "activos": [CasoCrearActivo._a_dict(a) for a in activos],
            "total": len(activos),
        })

    def buscar(self, identidad, etiqueta: str) -> tuple:
        if not str(etiqueta).strip():
            raise ValueError("La etiqueta de busqueda esta vacia.")
        hallados = self._activos.buscar_por_etiqueta(
            identidad.zid, str(etiqueta).strip()
        )
        return exito({
            "activos": [CasoCrearActivo._a_dict(a) for a in hallados],
            "etiqueta": str(etiqueta).strip().lower(),
            "total": len(hallados),
        })

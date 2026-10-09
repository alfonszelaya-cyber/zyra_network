"""Modulo vertical de COMPRENSION: aporta rutas de analisis real."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="understanding",
        nombre="Comprension",
        version="0.1.0",
        descripcion="Motor real de analisis: mediciones, montos, anos y dominio con certeza",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import inputs as r_inputs
    return (r_inputs,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

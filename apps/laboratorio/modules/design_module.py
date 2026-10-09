"""Modulo vertical de DISENO: blueprints con componentes."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="design",
        nombre="Diseno",
        version="0.1.0",
        descripcion="Blueprints estructurales con componentes y requisitos",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import designs as r_designs
    return (r_designs,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

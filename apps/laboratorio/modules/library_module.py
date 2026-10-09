"""Modulo vertical de BIBLIOTECA: activos sellados y busqueda."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="library",
        nombre="Biblioteca",
        version="0.1.0",
        descripcion="Activos reutilizables con hash SHA-256 y etiquetas",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import assets as r_assets
    return (r_assets,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

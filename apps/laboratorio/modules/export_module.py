"""Modulo vertical de EXPORT: bundle verificable y envio ZYRA."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="export",
        nombre="Exportar",
        version="0.1.0",
        descripcion="Bundle ZIP con manifiesto SHA-256 y envio a apps ZYRA via outbox",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import exports as r_exports
    return (r_exports,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

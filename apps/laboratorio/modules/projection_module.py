"""Modulo vertical de PROYECCION: superficies, WARP y frames."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="projection",
        nombre="Proyectar",
        version="0.1.0",
        descripcion="Superficies, calibracion con homografia real y frames warpeados",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import surfaces as r_surfaces
    return (r_surfaces,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

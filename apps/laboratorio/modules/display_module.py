"""Modulo vertical de SALIDAS: destinos con estado honesto."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="display",
        nombre="Salidas",
        version="0.1.0",
        descripcion="Pantalla y proyector disponibles; holo, light-field y AR/VR honestos",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import displays as r_displays
    return (r_displays,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

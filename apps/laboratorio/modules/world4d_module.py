"""Modulo vertical del 4D: TIEMPO + LUZ + INTERACCION + PROFUNDIDAD."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="world4d",
        nombre="4D",
        version="0.1.0",
        descripcion="Tiempo, luz, interaccion, profundidad y generadores naked3d, holograma y oligrama",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import world4d as r_world4d
    return (r_world4d,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

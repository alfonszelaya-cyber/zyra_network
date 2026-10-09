"""Modulo vertical de CREACION: escenas 3D y generacion real."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="creation",
        nombre="Creacion",
        version="0.1.0",
        descripcion="Escenas 3D e imagen, pagina, modelo y animacion reales",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import scenes as r_scenes
    return (r_scenes,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

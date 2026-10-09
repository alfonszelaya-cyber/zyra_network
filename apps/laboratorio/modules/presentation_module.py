"""Modulo vertical de PRESENTACION: pasos, slideshow y sello ZYRA."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="presentation",
        nombre="Presentar",
        version="0.1.0",
        descripcion="Presentaciones con pasos reales, slideshow SVG y sellado en ZYRA",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import presentations as r_presentations
    return (r_presentations,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

"""Modulo vertical de RENDER: escalera fotoreal y profundidad."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="render",
        nombre="Renderizar",
        version="0.1.0",
        descripcion="Escalera fotoreal: borrador SVG, PNG, 3D con perspectiva y fotorreal 4K con profundidad",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import renders as r_renders
    return (r_renders,)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

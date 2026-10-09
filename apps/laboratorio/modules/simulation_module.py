"""Modulo vertical de SIMULACION: escenarios, decision y optimizacion."""
from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="simulation",
        nombre="Simulacion",
        version="0.2.0",
        descripcion="Escenarios A/B/C, evolucion temporal, comparacion y optimizacion con informes",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import decisions as r_decisions
    from apps.laboratorio.routers.api import projects as r_projects
    from apps.laboratorio.routers.api import scenarios as r_scenarios
    return (r_projects, r_scenarios, r_decisions)


def conectar(app) -> None:
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

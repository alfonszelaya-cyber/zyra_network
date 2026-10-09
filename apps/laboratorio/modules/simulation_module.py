"""Modulo vertical de SIMULACION: manifiesto + routers que aporta."""

from apps.laboratorio.registry.modules.module_manifest import ManifiestoModulo


def manifiesto() -> ManifiestoModulo:
    return ManifiestoModulo(
        id="simulation",
        nombre="Simulacion",
        version="0.1.0",
        descripcion="Escenarios A/B/C, evaluacion LAB-CORE, sellado ZYRA y exportacion SVG",
    )


def routers() -> tuple:
    from apps.laboratorio.routers.api import projects as r_projects
    from apps.laboratorio.routers.api import scenarios as r_scenarios
    return (r_projects, r_scenarios)


def conectar(app) -> None:
    """Registra el modulo y conecta sus routers."""
    app.contenedor.obtener("registro_modulos").registrar(manifiesto())
    for router in routers():
        router.registrar_rutas(app)

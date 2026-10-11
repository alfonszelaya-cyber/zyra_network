"""Contenedor de servicios: unico punto que construye y conecta todo."""
import os
import secrets

from apps.laboratorio.application.handlers.project_handler import ManejadorProyectos
from apps.laboratorio.application.handlers.scenario_handler import ManejadorEscenarios
from apps.laboratorio.application.use_cases.create_project import CasoCrearProyecto
from apps.laboratorio.application.handlers.input_handler import ManejadorCapturas
from apps.laboratorio.application.handlers.understanding_handler import ManejadorComprension
from apps.laboratorio.application.handlers.scene_handler import ManejadorCreacion
from apps.laboratorio.application.handlers.presentation_handler import ManejadorPresentaciones
from apps.laboratorio.application.handlers.projection_handler import ManejadorProyeccion
from apps.laboratorio.application.handlers.display_handler import ManejadorSalidas
from apps.laboratorio.application.handlers.scan_handler import ManejadorEscaneo
from apps.laboratorio.application.use_cases.projection import (
    CasoRegistrarSuperficie,
    CasoCalibrarSuperficie,
    CasoProyectarEnVivo,
)
from apps.laboratorio.application.use_cases.displays import (
    CasoRegistrarSalida,
    CasoProbarSalida,
)
from apps.laboratorio.application.use_cases.scan_photo import (
    CasoAvatarDesdeFoto,
    CasoEscanearFoto,
)
from apps.laboratorio.infrastructure.providers.calibrator_manual import CalibradorManual
from apps.laboratorio.infrastructure.providers.scanner_photo import MotorEscaneoFoto
from apps.laboratorio.infrastructure.providers.avatar_engine import MotorAvatar
from apps.laboratorio.infrastructure.persistence.surface_store import SurfaceStore
from apps.laboratorio.infrastructure.persistence.display_store import DisplayStore
from apps.laboratorio.infrastructure.repositories.surface_repository import SurfaceRepository
from apps.laboratorio.infrastructure.repositories.display_repository import DisplayRepository
from apps.laboratorio.application.handlers.export_handler import ManejadorExportaciones
from apps.laboratorio.application.use_cases.build_presentation import (
    CasoCrearPresentacion,
    CasoReproducirPresentacion,
    CasoSellarPresentacion,
)
from apps.laboratorio.application.use_cases.export_deliverables import CasoExportarBundle
from apps.laboratorio.infrastructure.persistence.presentation_store import PresentationStore
from apps.laboratorio.infrastructure.persistence.export_store import ExportStore
from apps.laboratorio.infrastructure.repositories.presentation_repository import PresentationRepository
from apps.laboratorio.infrastructure.repositories.export_repository import ExportRepository
from apps.laboratorio.application.handlers.render_handler import ManejadorRenders
from apps.laboratorio.application.use_cases.render_world import CasoRenderizarEscena
from apps.laboratorio.application.workflows.photoreal_ladder import EscaleraFotoreal
from apps.laboratorio.infrastructure.persistence.render_store import RenderStore
from apps.laboratorio.infrastructure.repositories.render_repository import RenderRepository
from apps.laboratorio.application.handlers.decision_handler import ManejadorDecisiones
from apps.laboratorio.application.use_cases.decide import (
    CasoSimularEvolucion,
    CasoCompararEscenarios,
    CasoOptimizarEscenario,
    CasoAplicarOptimizacion,
)
from apps.laboratorio.infrastructure.providers.simulation_engine import MotorEvolucionReal
from apps.laboratorio.infrastructure.providers.comparison_engine import MotorComparacionReal
from apps.laboratorio.infrastructure.providers.optimization_engine import MotorOptimizacionReal
from apps.laboratorio.infrastructure.persistence.simulation_store import SimulationStore
from apps.laboratorio.infrastructure.persistence.comparison_store import ComparisonStore
from apps.laboratorio.infrastructure.persistence.optimization_store import OptimizationStore
from apps.laboratorio.infrastructure.repositories.simulation_repository import SimulationRepository
from apps.laboratorio.infrastructure.repositories.comparison_repository import ComparisonRepository
from apps.laboratorio.infrastructure.repositories.optimization_repository import OptimizationRepository
from apps.laboratorio.application.handlers.world4d_handler import ManejadorCuatroD
from apps.laboratorio.application.use_cases.world4d import (
    CasoCrearLineaTiempo,
    CasoCrearProgramaLuz,
    CasoCrearInteraccion,
)
from apps.laboratorio.infrastructure.providers.naked3d_engine import MotorNaked3D
from apps.laboratorio.infrastructure.providers.hologram_engine import MotorHolograma
from apps.laboratorio.infrastructure.providers.oligram_engine import MotorOligrama
from apps.laboratorio.infrastructure.persistence.timeline_store import TimelineStore
from apps.laboratorio.infrastructure.persistence.lighting_store import LightingStore
from apps.laboratorio.infrastructure.persistence.interaction_store import InteractionStore
from apps.laboratorio.infrastructure.repositories.timeline_repository import TimelineRepository
from apps.laboratorio.infrastructure.repositories.lighting_repository import LightingRepository
from apps.laboratorio.infrastructure.repositories.interaction_repository import InteractionRepository
from apps.laboratorio.application.handlers.library_handler import ManejadorBiblioteca
from apps.laboratorio.application.use_cases.create_scene import CasoCrearEscena
from apps.laboratorio.application.use_cases.generate_artifact import CasoGenerarArtefacto
from apps.laboratorio.application.use_cases.create_asset import CasoCrearActivo
from apps.laboratorio.infrastructure.providers.generation_engine import MotorGeneracionReal
from apps.laboratorio.infrastructure.persistence.scene_store import SceneStore
from apps.laboratorio.infrastructure.persistence.artifact_store import ArtifactStore
from apps.laboratorio.infrastructure.persistence.asset_store import AssetStore
from apps.laboratorio.infrastructure.repositories.scene_repository import SceneRepository
from apps.laboratorio.infrastructure.repositories.artifact_repository import ArtifactRepository
from apps.laboratorio.infrastructure.repositories.asset_repository import AssetRepository
from apps.laboratorio.application.handlers.design_handler import ManejadorDisenos
from apps.laboratorio.application.use_cases.capture_input import CasoCapturarEntrada
from apps.laboratorio.application.use_cases.understand_input import CasoComprenderEntrada
from apps.laboratorio.application.use_cases.create_blueprint import CasoCrearBlueprint
from apps.laboratorio.infrastructure.providers.understanding_engine import MotorComprensionTextual
from apps.laboratorio.infrastructure.persistence.input_store import InputStore
from apps.laboratorio.infrastructure.persistence.understanding_store import UnderstandingStore
from apps.laboratorio.infrastructure.persistence.design_store import DesignStore
from apps.laboratorio.infrastructure.repositories.input_repository import InputRepository
from apps.laboratorio.infrastructure.repositories.understanding_repository import UnderstandingRepository
from apps.laboratorio.infrastructure.repositories.design_repository import DesignRepository
from apps.laboratorio.application.handlers.document_handler import ManejadorDocumentos
from apps.laboratorio.application.use_cases.create_project_from_document import CasoCrearProyectoDesdeDocumento
from apps.laboratorio.application.use_cases.evaluate_scenario import CasoEvaluarEscenario
from apps.laboratorio.config.application.app_config import AppConfig
from apps.laboratorio.config.database.db_config import DbConfig
from apps.laboratorio.config.events.events_config import EventsConfig
from apps.laboratorio.config.network.network_config import NetworkConfig
from apps.laboratorio.config.permissions.permissions_config import PermissionsConfig
from apps.laboratorio.config.security.security_config import SecurityConfig
from apps.laboratorio.infrastructure.database.connection import ConexionBD
from apps.laboratorio.infrastructure.database.migrations import aplicar_migraciones
from apps.laboratorio.infrastructure.messaging.event_bus import BusEventos
from apps.laboratorio.infrastructure.messaging.outbox import Outbox
from apps.laboratorio.infrastructure.messaging.subscribers import SuscriptorZyra
from apps.laboratorio.infrastructure.network.health import EstadoSalud
from apps.laboratorio.infrastructure.network.zyra_client import ClienteZyra
from apps.laboratorio.infrastructure.persistence.audit_store import AuditStore
from apps.laboratorio.infrastructure.persistence.evaluation_store import EvaluationStore
from apps.laboratorio.infrastructure.persistence.history_store import HistoryStore
from apps.laboratorio.infrastructure.persistence.project_store import ProyectoStore
from apps.laboratorio.infrastructure.persistence.scenario_store import ScenarioStore
from apps.laboratorio.infrastructure.providers.display_holo3d import MotorHolo3D
from apps.laboratorio.infrastructure.providers.renderer_3d import MotorRender3D
from apps.laboratorio.infrastructure.providers.renderer_photoreal import MotorRenderFotoreal
from apps.laboratorio.infrastructure.providers.renderer_raster import MotorRenderRaster
from apps.laboratorio.infrastructure.providers.renderer_svg import MotorRenderSVG
from apps.laboratorio.infrastructure.repositories.audit_repository import AuditoriaRepository
from apps.laboratorio.infrastructure.repositories.evaluation_repository import EvaluationRepository
from apps.laboratorio.infrastructure.repositories.history_repository import HistorialRepository
from apps.laboratorio.infrastructure.repositories.project_repository import ProyectoRepository
from apps.laboratorio.infrastructure.repositories.scenario_repository import ScenarioRepository
from apps.laboratorio.infrastructure.security.audit_sink import AuditoriaSink
from apps.laboratorio.infrastructure.security.signing import Firmador
from apps.laboratorio.registry.engines.capabilities import (
    Capacidad,
    DisponibilidadCapacidades,
)
from apps.laboratorio.registry.engines.engine_registry import RegistroMotores
from apps.laboratorio.registry.modules.register import RegistroModulos
from apps.laboratorio.registry.templates.template_registry import RegistroPlantillas


class _EnvolturaMotor:
    """Adapta un motor existente al registro con estado honesto."""

    def __init__(self, nombre, motor, disponible, motivo="", tipo="motor"):
        self.nombre = str(nombre)
        self._motor = motor
        self._disponible = bool(disponible)
        self._motivo = "" if disponible else str(motivo)
        self._tipo = str(tipo)

    def capacidades(self) -> dict:
        if hasattr(self._motor, "capacidades"):
            return self._motor.capacidades()
        return {}

    def reporte(self) -> dict:
        return {
            "nombre": self.nombre,
            "tipo": self._tipo,
            "estado": "disponible" if self._disponible else "no_disponible",
            "version": "1.0.0",
            "capacidades": tuple(self.capacidades().keys()),
            "motivo": self._motivo,
        }


class Contenedor:
    def __init__(self):
        self._fabricas = {}
        self._instancias = {}

    def registrar(self, nombre, fabrica, unico=True):
        if not nombre or not callable(fabrica):
            raise ValueError("Servicio requiere nombre y fabrica callable.")
        if nombre in self._fabricas:
            raise ValueError("Servicio duplicado: " + nombre)
        self._fabricas[nombre] = (fabrica, bool(unico))

    def obtener(self, nombre):
        if nombre not in self._fabricas:
            raise ValueError("Servicio no registrado: " + nombre)
        fabrica, unico = self._fabricas[nombre]
        if unico and nombre in self._instancias:
            return self._instancias[nombre]
        instancia = fabrica(self)
        if unico:
            self._instancias[nombre] = instancia
        return instancia

    def contiene(self, nombre) -> bool:
        return nombre in self._fabricas

    def nombres(self) -> tuple:
        return tuple(sorted(self._fabricas))


def _capacidades_honestas() -> DisponibilidadCapacidades:
    capacidades = DisponibilidadCapacidades()
    capacidades.declarar(Capacidad.RENDER_SVG, True)
    capacidades.declarar(Capacidad.RENDER_RASTER, True)
    capacidades.declarar(Capacidad.RENDER_3D, True)
    capacidades.declarar(Capacidad.PROFUNDIDAD, True)
    capacidades.declarar(Capacidad.PROYECCION_WARP, True)
    capacidades.declarar(Capacidad.HOLO_3D, False, "hardware holografico volumetrico no conectado")
    capacidades.declarar(Capacidad.LIGHT_FIELD, False, "hardware light-field no conectado")
    capacidades.declarar(Capacidad.AR_VR, False, "hardware AR/VR no conectado")
    return capacidades


def construir_contenedor(ruta_bd: str = ":memory:") -> Contenedor:
    """Compone TODA la aplicacion en un unico lugar (composition root)."""
    c = Contenedor()
    cfg_app = AppConfig.cargar()
    cfg_ev = EventsConfig.cargar()
    cfg_red = NetworkConfig.cargar()
    cfg_seg = SecurityConfig.cargar()
    cfg_perm = PermissionsConfig.cargar()
    cfg_db = DbConfig(ruta_archivo=ruta_bd) if ruta_bd else DbConfig.cargar()
    c.registrar("config_app", lambda _c: cfg_app)
    c.registrar("config_permisos", lambda _c: cfg_perm)
    destino = ":memory:" if ruta_bd == ":memory:" else cfg_db.ruta_archivo
    conexion = ConexionBD(destino, cfg_db.timeout_segundos, cfg_db.journal_mode)
    aplicar_migraciones(conexion)
    c.registrar("conexion", lambda _c: conexion)
    c.registrar("proyecto_store", lambda _c: ProyectoStore(conexion))
    c.registrar("scenario_store", lambda _c: ScenarioStore(conexion))
    c.registrar("evaluation_store", lambda _c: EvaluationStore(conexion))
    c.registrar("history_store", lambda _c: HistoryStore(conexion))
    c.registrar("audit_store", lambda _c: AuditStore(conexion))
    c.registrar("repo_proyectos", lambda _c: ProyectoRepository(_c.obtener("proyecto_store")))
    c.registrar("repo_escenarios", lambda _c: ScenarioRepository(_c.obtener("scenario_store")))
    c.registrar("repo_evaluaciones", lambda _c: EvaluationRepository(_c.obtener("evaluation_store")))
    c.registrar("repo_historial", lambda _c: HistorialRepository(_c.obtener("history_store")))
    c.registrar("repo_auditoria", lambda _c: AuditoriaRepository(_c.obtener("audit_store")))
    c.registrar("bus", lambda _c: BusEventos())
    c.registrar("outbox", lambda _c: Outbox(conexion, cfg_ev.reintentos))

    def _suscriptor(_c):
        suscriptor = SuscriptorZyra(_c.obtener("bus"), _c.obtener("outbox"))
        suscriptor.conectar()
        return suscriptor

    c.registrar("suscriptor_zyra", _suscriptor)
    c.registrar("cliente_zyra", lambda _c: ClienteZyra(cfg_red))

    def _motores(_c):
        registro = RegistroMotores()
        registro.registrar("renderer_svg", MotorRenderSVG())
        registro.registrar("renderer_raster", _EnvolturaMotor("renderer_raster", MotorRenderRaster(), True, tipo="renderer"))
        registro.registrar("renderer_3d", MotorRender3D())
        registro.registrar("renderer_photoreal", MotorRenderFotoreal())
        registro.registrar("naked3d", _EnvolturaMotor("naked3d", MotorNaked3D(), True))
        registro.registrar("holograma", _EnvolturaMotor("holograma", MotorHolograma(), True))
        registro.registrar("oligrama", _EnvolturaMotor("oligrama", MotorOligrama(), True))
        registro.registrar("avatar", _EnvolturaMotor("avatar", MotorAvatar(), True))
        registro.registrar("escaneo_foto", _EnvolturaMotor("escaneo_foto", MotorEscaneoFoto(), True))
        registro.registrar("calibrador", _EnvolturaMotor("calibrador", CalibradorManual(), True))
        registro.registrar("comprension_textual", _EnvolturaMotor("comprension_textual", MotorComprensionTextual(), True))
        registro.registrar("generacion", _EnvolturaMotor("generacion", MotorGeneracionReal(), True))
        registro.registrar("evolucion", _EnvolturaMotor("evolucion", MotorEvolucionReal(), True))
        registro.registrar("comparacion", _EnvolturaMotor("comparacion", MotorComparacionReal(), True))
        registro.registrar("optimizacion", _EnvolturaMotor("optimizacion", MotorOptimizacionReal(), True))
        registro.registrar("display_holo3d", MotorHolo3D())
        return registro

    c.registrar("registro_motores", _motores)
    c.registrar("estado_salud", lambda _c: EstadoSalud(conexion, cfg_red, _c.obtener("registro_motores")))
    clave = os.environ.get("LAB_SIGNING_KEY") or secrets.token_hex(32)
    c.registrar("firmador", lambda _c: Firmador(clave))
    c.registrar("auditoria_sink", lambda _c: AuditoriaSink(_c.obtener("repo_auditoria")))
    c.registrar("registro_modulos", lambda _c: RegistroModulos())
    c.registrar("registro_plantillas", lambda _c: RegistroPlantillas())
    c.registrar("capacidades", lambda _c: _capacidades_honestas())
    c.registrar("caso_crear_proyecto", lambda _c: CasoCrearProyecto(
        _c.obtener("repo_proyectos"), _c.obtener("repo_historial"),
        _c.obtener("bus"), _c.obtener("auditoria_sink"),
    ))
    c.registrar("caso_evaluar_escenario", lambda _c: CasoEvaluarEscenario(
        _c.obtener("repo_escenarios"), _c.obtener("repo_evaluaciones"),
        _c.obtener("repo_proyectos"), _c.obtener("repo_historial"),
        _c.obtener("bus"), _c.obtener("outbox"),
        _c.obtener("cliente_zyra"), _c.obtener("auditoria_sink"),
    ))
    c.registrar("manejador_proyectos", lambda _c: ManejadorProyectos(
        _c.obtener("caso_crear_proyecto"), _c.obtener("repo_proyectos"),
        _c.obtener("auditoria_sink"),
    ))
    c.registrar("manejador_escenarios", lambda _c: ManejadorEscenarios(
        _c.obtener("repo_escenarios"), _c.obtener("repo_evaluaciones"),
        _c.obtener("repo_proyectos"), _c.obtener("caso_evaluar_escenario"),
        _c.obtener("auditoria_sink"),
    ))
    c.registrar("caso_crear_desde_documento", lambda _c: CasoCrearProyectoDesdeDocumento(_c.obtener("caso_crear_proyecto")))
    c.registrar("manejador_documentos", lambda _c: ManejadorDocumentos(_c.obtener("caso_crear_desde_documento"), _c.obtener("auditoria_sink")))
    c.registrar("input_store", lambda _c: InputStore(conexion))
    c.registrar("understanding_store", lambda _c: UnderstandingStore(conexion))
    c.registrar("design_store", lambda _c: DesignStore(conexion))
    c.registrar("repo_inputs", lambda _c: InputRepository(_c.obtener("input_store")))
    c.registrar("repo_comprensiones", lambda _c: UnderstandingRepository(_c.obtener("understanding_store")))
    c.registrar("repo_disenos", lambda _c: DesignRepository(_c.obtener("design_store")))
    c.registrar("motor_comprension", lambda _c: MotorComprensionTextual())
    c.registrar("caso_capturar", lambda _c: CasoCapturarEntrada(_c.obtener("repo_inputs"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_comprender", lambda _c: CasoComprenderEntrada(_c.obtener("repo_inputs"), _c.obtener("repo_comprensiones"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("motor_comprension"), _c.obtener("auditoria_sink")))
    c.registrar("caso_disenar", lambda _c: CasoCrearBlueprint(_c.obtener("repo_disenos"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_capturas", lambda _c: ManejadorCapturas(_c.obtener("caso_capturar"), _c.obtener("repo_inputs"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_comprension", lambda _c: ManejadorComprension(_c.obtener("caso_comprender"), _c.obtener("repo_inputs"), _c.obtener("repo_comprensiones"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_disenos", lambda _c: ManejadorDisenos(_c.obtener("caso_disenar"), _c.obtener("repo_disenos"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("scene_store", lambda _c: SceneStore(conexion))
    c.registrar("artifact_store", lambda _c: ArtifactStore(conexion))
    c.registrar("asset_store", lambda _c: AssetStore(conexion))
    c.registrar("repo_escenas", lambda _c: SceneRepository(_c.obtener("scene_store")))
    c.registrar("repo_artefactos", lambda _c: ArtifactRepository(_c.obtener("artifact_store")))
    c.registrar("repo_activos", lambda _c: AssetRepository(_c.obtener("asset_store")))
    c.registrar("motor_generacion", lambda _c: MotorGeneracionReal())
    c.registrar("caso_crear_escena", lambda _c: CasoCrearEscena(_c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_generar", lambda _c: CasoGenerarArtefacto(_c.obtener("repo_escenas"), _c.obtener("repo_artefactos"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("motor_generacion"), _c.obtener("auditoria_sink")))
    c.registrar("caso_crear_activo", lambda _c: CasoCrearActivo(_c.obtener("repo_activos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_creacion", lambda _c: ManejadorCreacion(_c.obtener("caso_crear_escena"), _c.obtener("caso_generar"), _c.obtener("repo_escenas"), _c.obtener("repo_artefactos"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_biblioteca", lambda _c: ManejadorBiblioteca(_c.obtener("caso_crear_activo"), _c.obtener("repo_activos"), _c.obtener("auditoria_sink")))
    c.registrar("timeline_store", lambda _c: TimelineStore(conexion))
    c.registrar("lighting_store", lambda _c: LightingStore(conexion))
    c.registrar("interaction_store", lambda _c: InteractionStore(conexion))
    c.registrar("repo_timelines", lambda _c: TimelineRepository(_c.obtener("timeline_store")))
    c.registrar("repo_luces", lambda _c: LightingRepository(_c.obtener("lighting_store")))
    c.registrar("repo_interacciones", lambda _c: InteractionRepository(_c.obtener("interaction_store")))
    c.registrar("motor_naked3d", lambda _c: MotorNaked3D())
    c.registrar("motor_holograma", lambda _c: MotorHolograma())
    c.registrar("motor_oligrama", lambda _c: MotorOligrama())
    c.registrar("caso_timeline", lambda _c: CasoCrearLineaTiempo(_c.obtener("repo_timelines"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_luz", lambda _c: CasoCrearProgramaLuz(_c.obtener("repo_luces"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_interaccion", lambda _c: CasoCrearInteraccion(_c.obtener("repo_interacciones"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_cuatro_d", lambda _c: ManejadorCuatroD(_c.obtener("caso_timeline"), _c.obtener("caso_luz"), _c.obtener("caso_interaccion"), _c.obtener("repo_timelines"), _c.obtener("repo_luces"), _c.obtener("repo_interacciones"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("simulation_store", lambda _c: SimulationStore(conexion))
    c.registrar("comparison_store", lambda _c: ComparisonStore(conexion))
    c.registrar("optimization_store", lambda _c: OptimizationStore(conexion))
    c.registrar("repo_simulaciones", lambda _c: SimulationRepository(_c.obtener("simulation_store")))
    c.registrar("repo_comparaciones", lambda _c: ComparisonRepository(_c.obtener("comparison_store")))
    c.registrar("repo_optimizaciones", lambda _c: OptimizationRepository(_c.obtener("optimization_store")))
    c.registrar("motor_evolucion", lambda _c: MotorEvolucionReal())
    c.registrar("motor_comparacion", lambda _c: MotorComparacionReal())
    c.registrar("motor_optimizacion", lambda _c: MotorOptimizacionReal())
    c.registrar("caso_simular", lambda _c: CasoSimularEvolucion(_c.obtener("repo_simulaciones"), _c.obtener("repo_escenarios"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("motor_evolucion"), _c.obtener("auditoria_sink")))
    c.registrar("caso_comparar", lambda _c: CasoCompararEscenarios(_c.obtener("repo_comparaciones"), _c.obtener("repo_escenarios"), _c.obtener("repo_evaluaciones"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("motor_comparacion"), _c.obtener("auditoria_sink")))
    c.registrar("caso_optimizar", lambda _c: CasoOptimizarEscenario(_c.obtener("repo_optimizaciones"), _c.obtener("repo_escenarios"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("motor_optimizacion"), _c.obtener("auditoria_sink")))
    c.registrar("caso_aplicar", lambda _c: CasoAplicarOptimizacion(_c.obtener("repo_optimizaciones"), _c.obtener("repo_escenarios"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_decisiones", lambda _c: ManejadorDecisiones(_c.obtener("caso_simular"), _c.obtener("caso_comparar"), _c.obtener("caso_optimizar"), _c.obtener("caso_aplicar"), _c.obtener("repo_simulaciones"), _c.obtener("repo_comparaciones"), _c.obtener("repo_optimizaciones"), _c.obtener("repo_proyectos"), _c.obtener("repo_escenarios"), _c.obtener("repo_evaluaciones"), _c.obtener("auditoria_sink")))
    c.registrar("render_store", lambda _c: RenderStore(conexion))
    c.registrar("repo_renders", lambda _c: RenderRepository(_c.obtener("render_store")))
    c.registrar("escalera_fotoreal", lambda _c: EscaleraFotoreal())
    c.registrar("caso_renderizar", lambda _c: CasoRenderizarEscena(_c.obtener("repo_renders"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("repo_luces"), _c.obtener("repo_historial"), _c.obtener("escalera_fotoreal"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_renders", lambda _c: ManejadorRenders(_c.obtener("caso_renderizar"), _c.obtener("repo_renders"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("presentation_store", lambda _c: PresentationStore(conexion))
    c.registrar("export_store", lambda _c: ExportStore(conexion))
    c.registrar("repo_presentaciones", lambda _c: PresentationRepository(_c.obtener("presentation_store")))
    c.registrar("repo_exportaciones", lambda _c: ExportRepository(_c.obtener("export_store")))
    c.registrar("caso_crear_presentacion", lambda _c: CasoCrearPresentacion(_c.obtener("repo_presentaciones"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("auditoria_sink")))
    c.registrar("caso_reproducir", lambda _c: CasoReproducirPresentacion(_c.obtener("repo_presentaciones"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("caso_sellar_presentacion", lambda _c: CasoSellarPresentacion(_c.obtener("repo_presentaciones"), _c.obtener("repo_proyectos"), _c.obtener("repo_historial"), _c.obtener("bus"), _c.obtener("outbox"), _c.obtener("cliente_zyra"), _c.obtener("auditoria_sink")))
    c.registrar("caso_exportar_bundle", lambda _c: CasoExportarBundle(_c.obtener("repo_exportaciones"), _c.obtener("repo_proyectos"), _c.obtener("repo_escenas"), _c.obtener("repo_artefactos"), _c.obtener("repo_evaluaciones"), _c.obtener("repo_presentaciones"), _c.obtener("repo_historial"), _c.obtener("outbox"), _c.obtener("cliente_zyra"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_presentaciones", lambda _c: ManejadorPresentaciones(_c.obtener("caso_crear_presentacion"), _c.obtener("caso_reproducir"), _c.obtener("caso_sellar_presentacion"), _c.obtener("repo_presentaciones"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_exportaciones", lambda _c: ManejadorExportaciones(_c.obtener("caso_exportar_bundle"), _c.obtener("repo_exportaciones"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("surface_store", lambda _c: SurfaceStore(conexion))
    c.registrar("display_store", lambda _c: DisplayStore(conexion))
    c.registrar("repo_superficies", lambda _c: SurfaceRepository(_c.obtener("surface_store")))
    c.registrar("repo_salidas", lambda _c: DisplayRepository(_c.obtener("display_store")))
    c.registrar("calibrador", lambda _c: CalibradorManual())
    c.registrar("motor_scanner", lambda _c: MotorEscaneoFoto())
    c.registrar("motor_avatar", lambda _c: MotorAvatar())
    c.registrar("caso_registrar_superficie", lambda _c: CasoRegistrarSuperficie(_c.obtener("repo_superficies"), _c.obtener("auditoria_sink")))
    c.registrar("caso_calibrar", lambda _c: CasoCalibrarSuperficie(_c.obtener("repo_superficies"), _c.obtener("calibrador"), _c.obtener("auditoria_sink")))
    c.registrar("caso_proyectar", lambda _c: CasoProyectarEnVivo(_c.obtener("repo_superficies"), _c.obtener("repo_escenas"), _c.obtener("repo_proyectos"), _c.obtener("auditoria_sink")))
    c.registrar("caso_registrar_salida", lambda _c: CasoRegistrarSalida(_c.obtener("repo_salidas"), _c.obtener("auditoria_sink")))
    c.registrar("caso_probar_salida", lambda _c: CasoProbarSalida(_c.obtener("repo_salidas"), _c.obtener("auditoria_sink")))
    c.registrar("caso_escanear_foto", lambda _c: CasoEscanearFoto(_c.obtener("repo_inputs"), _c.obtener("repo_proyectos"), _c.obtener("motor_scanner"), _c.obtener("auditoria_sink")))
    c.registrar("caso_avatar_foto", lambda _c: CasoAvatarDesdeFoto(_c.obtener("repo_inputs"), _c.obtener("repo_proyectos"), _c.obtener("caso_crear_activo"), _c.obtener("motor_avatar"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_escaneo", lambda _c: ManejadorEscaneo(_c.obtener("caso_escanear_foto"), _c.obtener("caso_avatar_foto")))
    c.registrar("manejador_proyeccion", lambda _c: ManejadorProyeccion(_c.obtener("caso_registrar_superficie"), _c.obtener("caso_calibrar"), _c.obtener("caso_proyectar"), _c.obtener("repo_superficies"), _c.obtener("auditoria_sink")))
    c.registrar("manejador_salidas", lambda _c: ManejadorSalidas(_c.obtener("caso_registrar_salida"), _c.obtener("caso_probar_salida"), _c.obtener("repo_salidas"), _c.obtener("auditoria_sink")))
    c.obtener("suscriptor_zyra")
    return c

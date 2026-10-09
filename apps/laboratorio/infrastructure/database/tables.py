"""Esquema oficial de LABORATORIO: v1 a v6 (nucleo a fase 6)."""
ESQUEMA_V1 = """
CREATE TABLE IF NOT EXISTS lab_schema_version (
    version INTEGER NOT NULL,
    aplicada_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_projects (
    id TEXT PRIMARY KEY,
    titulo TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL,
    etapa TEXT NOT NULL,
    estado TEXT NOT NULL,
    propietario_zid TEXT NOT NULL,
    etiquetas TEXT NOT NULL DEFAULT '[]',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_scenarios (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    descripcion TEXT NOT NULL DEFAULT '',
    parametros TEXT NOT NULL DEFAULT '{}',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_evaluations (
    id TEXT PRIMARY KEY,
    escenario_id TEXT NOT NULL REFERENCES lab_scenarios(id) ON DELETE CASCADE,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    metricas TEXT NOT NULL DEFAULT '{}',
    nota TEXT NOT NULL DEFAULT '',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_history (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    autor_zid TEXT NOT NULL,
    accion TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT '{}',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    momento TEXT NOT NULL,
    actor_zid TEXT NOT NULL,
    accion TEXT NOT NULL,
    recurso TEXT NOT NULL,
    resultado TEXT NOT NULL,
    detalle TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS lab_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evento TEXT NOT NULL,
    destino TEXT NOT NULL DEFAULT '',
    carga TEXT NOT NULL DEFAULT '{}',
    intentos INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'pendiente',
    ultimo_error TEXT NOT NULL DEFAULT '',
    creado_en TEXT NOT NULL,
    enviado_en TEXT
);
CREATE INDEX IF NOT EXISTS idx_projects_propietario ON lab_projects(propietario_zid);
CREATE INDEX IF NOT EXISTS idx_scenarios_proyecto ON lab_scenarios(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_escenario ON lab_evaluations(escenario_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_proyecto ON lab_evaluations(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_history_proyecto ON lab_history(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_audit_momento ON lab_audit(momento);
"""

ESQUEMA_V2 = """
CREATE TABLE IF NOT EXISTS lab_inputs (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    contenido TEXT NOT NULL DEFAULT '',
    hash TEXT NOT NULL DEFAULT '',
    tamano INTEGER NOT NULL DEFAULT 0,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_understandings (
    id TEXT PRIMARY KEY,
    entrada_id TEXT NOT NULL REFERENCES lab_inputs(id) ON DELETE CASCADE,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    resumen TEXT NOT NULL DEFAULT '',
    hallazgos TEXT NOT NULL DEFAULT '[]',
    entidades TEXT NOT NULL DEFAULT '{}',
    dominio TEXT NOT NULL DEFAULT '',
    confianza REAL NOT NULL DEFAULT 0.0,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_designs (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    componentes TEXT NOT NULL DEFAULT '[]',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_inputs_proyecto ON lab_inputs(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_understandings_entrada ON lab_understandings(entrada_id);
CREATE INDEX IF NOT EXISTS idx_designs_proyecto ON lab_designs(proyecto_id);
"""

ESQUEMA_V3 = """
CREATE TABLE IF NOT EXISTS lab_scenes (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    ancho INTEGER NOT NULL,
    alto INTEGER NOT NULL,
    objetos TEXT NOT NULL DEFAULT '[]',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_artifacts (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    escena_id TEXT NOT NULL REFERENCES lab_scenes(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    formato TEXT NOT NULL,
    contenido TEXT NOT NULL DEFAULT '',
    hash TEXT NOT NULL DEFAULT '',
    tamano INTEGER NOT NULL DEFAULT 0,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_assets (
    id TEXT PRIMARY KEY,
    propietario_zid TEXT NOT NULL,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    contenido TEXT NOT NULL DEFAULT '',
    hash TEXT NOT NULL DEFAULT '',
    tamano INTEGER NOT NULL DEFAULT 0,
    etiquetas TEXT NOT NULL DEFAULT '[]',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scenes_proyecto ON lab_scenes(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_proyecto ON lab_artifacts(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_escena ON lab_artifacts(escena_id);
CREATE INDEX IF NOT EXISTS idx_assets_propietario ON lab_assets(propietario_zid);
"""

ESQUEMA_V4 = """
CREATE TABLE IF NOT EXISTS lab_timelines (
    id TEXT PRIMARY KEY,
    escena_id TEXT NOT NULL UNIQUE REFERENCES lab_scenes(id) ON DELETE CASCADE,
    duracion REAL NOT NULL,
    fps INTEGER NOT NULL,
    pistas TEXT NOT NULL DEFAULT '[]',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_lightprograms (
    id TEXT PRIMARY KEY,
    escena_id TEXT NOT NULL UNIQUE REFERENCES lab_scenes(id) ON DELETE CASCADE,
    pasos TEXT NOT NULL DEFAULT '[]',
    ambientar INTEGER NOT NULL DEFAULT 0,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_interactions (
    id TEXT PRIMARY KEY,
    escena_id TEXT NOT NULL REFERENCES lab_scenes(id) ON DELETE CASCADE,
    x REAL NOT NULL,
    y REAL NOT NULL,
    w REAL NOT NULL,
    h REAL NOT NULL,
    accion TEXT NOT NULL,
    titulo TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interactions_escena ON lab_interactions(escena_id);
"""

ESQUEMA_V5 = """
CREATE TABLE IF NOT EXISTS lab_simulations (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    escenario_id TEXT NOT NULL REFERENCES lab_scenarios(id) ON DELETE CASCADE,
    horizonte INTEGER NOT NULL,
    crecimiento REAL NOT NULL,
    serie TEXT NOT NULL DEFAULT '[]',
    metricas TEXT NOT NULL DEFAULT '{}',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_comparisons (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    participantes TEXT NOT NULL DEFAULT '[]',
    ganador TEXT NOT NULL DEFAULT '',
    brecha REAL NOT NULL DEFAULT 0.0,
    detalle TEXT NOT NULL DEFAULT '{}',
    informe TEXT NOT NULL DEFAULT '',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_optimizations (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    escenario_id TEXT NOT NULL REFERENCES lab_scenarios(id) ON DELETE CASCADE,
    recomendaciones TEXT NOT NULL DEFAULT '[]',
    parametros_optimizados TEXT NOT NULL DEFAULT '{}',
    puntaje_actual REAL NOT NULL DEFAULT 0.0,
    puntaje_proyectado REAL NOT NULL DEFAULT 0.0,
    estado TEXT NOT NULL DEFAULT 'sugerida',
    aplicado_como TEXT NOT NULL DEFAULT '',
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_simulations_proyecto ON lab_simulations(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_proyecto ON lab_comparisons(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_optimizations_proyecto ON lab_optimizations(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_optimizations_escenario ON lab_optimizations(escenario_id);
"""

ESQUEMA_V6 = """
CREATE TABLE IF NOT EXISTS lab_renders (
    id TEXT PRIMARY KEY,
    proyecto_id TEXT NOT NULL REFERENCES lab_projects(id) ON DELETE CASCADE,
    escena_id TEXT NOT NULL REFERENCES lab_scenes(id) ON DELETE CASCADE,
    calidad TEXT NOT NULL,
    formato TEXT NOT NULL,
    ancho INTEGER NOT NULL,
    alto INTEGER NOT NULL,
    imagen BLOB NOT NULL,
    profundidad BLOB,
    hash TEXT NOT NULL DEFAULT '',
    duracion_ms REAL NOT NULL DEFAULT 0.0,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_renders_proyecto ON lab_renders(proyecto_id);
CREATE INDEX IF NOT EXISTS idx_renders_escena ON lab_renders(escena_id);
"""

MIGRACIONES_SQL = {1: ESQUEMA_V1, 2: ESQUEMA_V2, 3: ESQUEMA_V3, 4: ESQUEMA_V4, 5: ESQUEMA_V5, 6: ESQUEMA_V6}

TABLAS_ESPERADAS = (
    "lab_projects", "lab_scenarios", "lab_evaluations",
    "lab_history", "lab_audit", "lab_outbox", "lab_schema_version",
    "lab_inputs", "lab_understandings", "lab_designs",
    "lab_scenes", "lab_artifacts", "lab_assets",
    "lab_timelines", "lab_lightprograms", "lab_interactions",
    "lab_simulations", "lab_comparisons", "lab_optimizations",
    "lab_renders",
)


def tablas_existentes(conexion) -> tuple:
    filas = conexion.consultar(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'lab_%'"
    )
    return tuple(sorted(fila["name"] for fila in filas))

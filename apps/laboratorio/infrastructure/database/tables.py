"""Esquema oficial v1 de LABORATORIO: tablas e indices."""
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

TABLAS_ESPERADAS = (
    "lab_projects", "lab_scenarios", "lab_evaluations",
    "lab_history", "lab_audit", "lab_outbox", "lab_schema_version",
)


def tablas_existentes(conexion) -> tuple:
    """Nombres reales de tablas presentes en la base."""
    filas = conexion.consultar(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'lab_%'"
    )
    return tuple(sorted(fila["name"] for fila in filas))

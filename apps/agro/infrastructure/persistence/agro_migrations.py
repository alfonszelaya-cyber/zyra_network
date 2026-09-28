"""AGRO - migraciones versionadas (GPT-9).
Esquema completo agro_* en orden;
idempotente."""
from __future__ import annotations

MIGRATIONS = (
    (1, "perfil_y_historial", (
        "CREATE TABLE IF NOT EXISTS"
        " agro_producer_profiles ("
        " producer_id TEXT PRIMARY KEY,"
        " phone TEXT, location TEXT,"
        " notes TEXT, updated_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_profile_history ("
        " hid INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " producer_id TEXT NOT NULL,"
        " actor TEXT NOT NULL,"
        " changed TEXT NOT NULL,"
        " at TEXT NOT NULL)",
    )),
    (2, "unidades_y_planes", (
        "CREATE TABLE IF NOT EXISTS"
        " agro_units ("
        " unit_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " name TEXT NOT NULL,"
        " unit_type TEXT NOT NULL,"
        " land_id TEXT, created_at TEXT,"
        " closed_at TEXT, closed_by TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_plans ("
        " plan_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " unit_id TEXT NOT NULL,"
        " crop TEXT NOT NULL,"
        " target REAL NOT NULL,"
        " status TEXT NOT NULL,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_stage_log ("
        " log_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " plan_id TEXT NOT NULL,"
        " stage TEXT NOT NULL,"
        " detail TEXT, logged_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_plan_costs ("
        " cost_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " plan_id TEXT NOT NULL,"
        " concept TEXT NOT NULL,"
        " amount REAL NOT NULL,"
        " currency TEXT NOT NULL,"
        " actor TEXT NOT NULL,"
        " created_at TEXT)",
    )),
    (3, "seguridad_y_auditoria", (
        "CREATE TABLE IF NOT EXISTS"
        " agro_audit_chain ("
        " seq INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " ts TEXT NOT NULL,"
        " actor TEXT NOT NULL,"
        " role TEXT NOT NULL,"
        " operation TEXT NOT NULL,"
        " outcome TEXT NOT NULL,"
        " detail TEXT NOT NULL DEFAULT"
        " '',"
        " prev_hash TEXT NOT NULL,"
        " event_hash TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_blocked_actors ("
        " actor TEXT PRIMARY KEY,"
        " reason TEXT NOT NULL,"
        " at TEXT NOT NULL)",
    )),
    (4, "comercializacion", (
        "CREATE TABLE IF NOT EXISTS"
        " agro_sales_plus ("
        " sale_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " product TEXT NOT NULL,"
        " quantity REAL NOT NULL,"
        " remaining REAL NOT NULL,"
        " unit TEXT NOT NULL DEFAULT"
        " 'quintal',"
        " buyer TEXT,"
        " offer_price REAL,"
        " total REAL,"
        " currency TEXT NOT NULL DEFAULT"
        " 'USD',"
        " status TEXT NOT NULL,"
        " paid_at TEXT, delivered_at"
        " TEXT,"
        " closed_at TEXT, created_at"
        " TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_sale_offers ("
        " offer_id TEXT PRIMARY KEY,"
        " sale_id TEXT NOT NULL,"
        " buyer TEXT NOT NULL,"
        " amount REAL NOT NULL,"
        " currency TEXT NOT NULL DEFAULT"
        " 'USD',"
        " status TEXT NOT NULL,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_inventory_plus ("
        " inv_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " producer_id TEXT NOT NULL,"
        " product TEXT NOT NULL,"
        " quantity REAL NOT NULL,"
        " unit TEXT NOT NULL,"
        " updated_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_market_prices ("
        " price_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " product TEXT NOT NULL,"
        " price REAL NOT NULL,"
        " actor TEXT NOT NULL,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_exports ("
        " export_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " product TEXT NOT NULL,"
        " destination TEXT NOT NULL,"
        " quantity REAL NOT NULL,"
        " status TEXT NOT NULL,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_shipments ("
        " shipment_id TEXT PRIMARY KEY,"
        " sale_id TEXT NOT NULL,"
        " origin TEXT NOT NULL,"
        " destination TEXT NOT NULL,"
        " cargo TEXT NOT NULL,"
        " status TEXT NOT NULL,"
        " engine TEXT NOT NULL,"
        " created_at TEXT)",
    )),
    (5, "recursos_y_riesgo", (
        "CREATE TABLE IF NOT EXISTS"
        " agro_equipment ("
        " equipment_id TEXT PRIMARY"
        " KEY,"
        " producer_id TEXT NOT NULL,"
        " kind TEXT NOT NULL,"
        " identifier TEXT,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_infrastructure ("
        " infra_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " kind TEXT NOT NULL,"
        " location TEXT,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_valuations ("
        " valuation_id TEXT PRIMARY"
        " KEY,"
        " producer_id TEXT NOT NULL,"
        " asset_kind TEXT NOT NULL,"
        " asset_id TEXT NOT NULL,"
        " amount REAL NOT NULL,"
        " currency TEXT NOT NULL,"
        " actor TEXT NOT NULL,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_asset_log ("
        " log_id INTEGER PRIMARY KEY"
        " AUTOINCREMENT,"
        " producer_id TEXT NOT NULL,"
        " asset_kind TEXT NOT NULL,"
        " asset_id TEXT NOT NULL,"
        " action TEXT NOT NULL,"
        " detail TEXT NOT NULL DEFAULT"
        " '',"
        " actor TEXT NOT NULL,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_climate_events ("
        " event_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " event_type TEXT NOT NULL,"
        " severity TEXT NOT NULL,"
        " alert INTEGER NOT NULL,"
        " detail TEXT NOT NULL DEFAULT"
        " '',"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_alerts ("
        " alert_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " risk_type TEXT NOT NULL,"
        " severity TEXT NOT NULL,"
        " target TEXT NOT NULL,"
        " detail TEXT NOT NULL DEFAULT"
        " '',"
        " status TEXT NOT NULL,"
        " resolution TEXT,"
        " created_at TEXT,"
        " resolved_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_responses ("
        " response_id TEXT PRIMARY"
        " KEY,"
        " producer_id TEXT NOT NULL,"
        " risk_id TEXT NOT NULL,"
        " actions TEXT NOT NULL,"
        " status TEXT NOT NULL,"
        " created_at TEXT,"
        " updated_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_incidents_plus ("
        " incident_id TEXT PRIMARY"
        " KEY,"
        " producer_id TEXT NOT NULL,"
        " unit_id TEXT, kind TEXT NOT"
        " NULL,"
        " severity TEXT NOT NULL,"
        " detail TEXT, status TEXT NOT"
        " NULL,"
        " escalated INTEGER NOT NULL"
        " DEFAULT 0,"
        " action TEXT, resolved_at"
        " TEXT,"
        " created_at TEXT)",
        "CREATE TABLE IF NOT EXISTS"
        " agro_risk_evals ("
        " eval_id TEXT PRIMARY KEY,"
        " producer_id TEXT NOT NULL,"
        " kind TEXT NOT NULL,"
        " ratio REAL,"
        " level TEXT,"
        " created_at TEXT)",
    )),
    (6, "outbox_ecosistema", (
        "CREATE TABLE IF NOT EXISTS"
        " agro_event_outbox ("
        " event_key TEXT PRIMARY KEY,"
        " event_type TEXT NOT NULL,"
        " payload TEXT NOT NULL,"
        " zid TEXT,"
        " status TEXT NOT NULL,"
        " attempts INTEGER NOT NULL"
        " DEFAULT 0,"
        " last_error TEXT,"
        " created_at TEXT,"
        " updated_at TEXT)",
    )),
)


def run_agro_migrations(db):
    """Aplica migraciones en orden;
    idempotente."""
    db.execute(
        "CREATE TABLE IF NOT EXISTS"
        " agro_migrations_applied ("
        " version INTEGER PRIMARY KEY,"
        " name TEXT NOT NULL,"
        " applied_at TEXT)"
    )
    aplicadas = []
    for name in (
        "query_all", "query", "fetchall"
    ):
        fn = getattr(db, name, None)
        if callable(fn):
            try:
                got = fn(
                    "SELECT version FROM"
                    " agro_migrations_applied"
                    " ORDER BY version"
                )
            except Exception:
                got = None
            if got:
                for r in got:
                    try:
                        aplicadas.append(
                            int(r["version"])
                        )
                    except Exception:
                        try:
                            aplicadas.append(
                                int(r[0])
                            )
                        except Exception:
                            pass
                break
    import time as _t
    ts = _t.strftime(
        "%Y-%m-%dT%H:%M:%SZ", _t.gmtime()
    )
    nuevas = []
    for version, name, sqls in MIGRATIONS:
        if version in aplicadas:
            continue
        for sql in sqls:
            db.execute(sql)
        db.execute(
            "INSERT INTO"
            " agro_migrations_applied ("
            " version, name, applied_at)"
            " VALUES (?, ?, ?)",
            (version, name, ts),
        )
        nuevas.append(version)
    return {
        "applied_now": nuevas,
        "total_versions": len(
            MIGRATIONS
        ),
    }

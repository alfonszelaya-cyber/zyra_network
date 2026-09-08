# Zyra Network — Mapa de Contratos Canónicos

Documento vinculante: define la AUTORIDAD de cada capacidad
cuando existe en más de una capa. Basado en auditoría 2025.

## Regla de interpretación
- **Autoridad canónica**: la implementación de referencia.
- **Capa de ejecución**: usa/delega en la autoridad; no
  redefine semántica.
- Ambos pueden coexistir SI respetan esta tabla.

## Tabla de autoridad

| Capacidad | Autoridad canónica | Capa de ejecución / fachada | Regla |
|---|---|---|---|
| Result | `foundation/contracts/result.py` | `shared_engines/common/result.py` | Engines importan de common; common delega semántica a foundation |
| Serialización | `foundation/contracts/serialization.py` | `shared_engines/common/serialization.py` | Idem |
| Tipos semánticos | `foundation/types/` | `shared_engines/common/types.py` | Idem |
| Service discovery | `infrastructure/dns/` (mecanismo autoritativo) | `infrastructure/discovery/` = fachada alto nivel | Fachada delega en dns |
| Transport | `protocol/transport/` (contrato) | `network/transport/` (implementación) | network implementa el contrato de protocol |
| Cluster | `shared_engines/network/cluster.py` (motor con tests) | `network/cluster/` (capa raíz) | Capa raíz delega en el engine |
| Failover | `shared_engines/network/failover.py` (quorum demostrado) | `network/failover/` | Idem |
| Replication | `shared_engines/network/replication.py` (hash-verified) | `network/replication/` | Idem |
| Database | `infrastructure/database/` (infra operativa) | `shared_engines/storage/database.py` (contrato para motores) | Motores dependen SOLO del contrato |
| Migraciones | `shared_engines/storage/migrations.py` + `network_migrations.py` (motor) | `migrations/versions/` (historial operativo) | scripts/migrate.py ejecuta el motor |
| Verificación | `shared_engines/verification/` (emisión) | `shared_engines/verifier/` (verificación OFFLINE terceros) | verifier consume attestations; nunca emite |
| Observability | `shared_engines/observability/` (backend + health) | `observability/` raíz (colección/dashboards) | Capa raíz se integra vía MetricsBackend/HealthRegistry |
| Telemetry | `shared_engines/telemetry/` (engine) | `telemetry/` raíz (fachadas futuras) | Se activan en fases posteriores |
| Logs | `shared_engines/logs/structured.py` (engine) | `logs/` raíz (archivo/retención) | cleanup.py usa el engine |

## Regla de nuevos módulos
Antes de crear cualquier archivo, consultar esta tabla.
Si la capacidad no está aquí, añadirla a esta tabla EN EL
MISMO commit que el código.

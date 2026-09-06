# ZYRA Observability

Production observability boundary of ZYRA Network.

The subsystem provides stable contracts for:

- correlation and trace context
- structured events
- metrics
- health checks
- alert rules
- alert state
- incidents
- component registration
- bounded collection
- query
- snapshots
- status aggregation
- dashboards
- reports
- routing
- exporters
- lifecycle management
- durable observation storage

The implementation is intentionally isolated from `apps/`.

Runtime dependencies are Python standard-library based.
`pytest` is installed by CI only for validation.

# ZYRA Observability

Production observability subsystem.

Provides:

- events
- structured context
- correlation IDs
- trace IDs
- span IDs
- metrics
- counters
- gauges
- histograms
- timers
- bounded cardinality
- bounded storage
- retention
- collector backpressure
- health checks
- alert rules
- alert deduplication
- incident lifecycle
- component registry
- query
- snapshots
- dashboards
- reports
- routing
- exporter abstraction
- monitoring
- stable public API

The implementation uses the Python standard library and does not
couple the core to applications or a specific observability vendor.

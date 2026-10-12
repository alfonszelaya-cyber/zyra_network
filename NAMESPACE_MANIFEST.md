# NAMESPACE_MANIFEST — Etiquetado formal de namespaces

Etiquetas: BUILT (codigo construido en repo, inactivo hasta cumplir su condicion de activacion) - FUTURE (reservado por roadmap, sin implementacion) - APP-SCOPE (de una App).

## Namespaces en shared_engines/

| Namespace | Etiqueta | Condición de activación |
|---|---|---|
| ai/ | BUILT | Modelos de IA reales contratados |
| certification/ | BUILT | Proceso de certificación institucional (post ISO) |
| compliance/ | BUILT | Reglas por jurisdicción definidas |
| compression/ | BUILT | Necesidad demostrada |
| consensus/ | BUILT | Multi-nodo real en producción |
| encryption/ | BUILT | Capacidades adicionales sobre security/ |
| export/ | BUILT | Requisito de exportación por clientes |
| integrations/ | BUILT | Primer convenio externo (gob.sv, bancos) |
| integrity/ | BUILT | Verificaciones adicionales sobre audit/ |
| interoperability/ | BUILT | Interoperabilidad con otras redes |
| orchestration/ | FUTURE | Orquestación post multi-nodo |
| radar/ | **APP-SCOPE** | Pertenece a SUBASTAS (Radar VIP) |
| reputation/ | BUILT | Reputación cross-app definida |
| routing/ | BUILT | Routing sobre network/ |
| scalability/ | BUILT | Escalado demostrado necesario |
| search/ | BUILT | Búsqueda sobre volúmenes reales |
| supervisor/ | BUILT | Supervisión de engines en runtime |
| system_loader/ | BUILT | Carga dinámica si se requiere |
| workflow/ | BUILT | Flujos multi-paso entre motores |

## Regla de oro
Ningún namespace se llena artificialmente. Se activa cuando
su condición se cumple, con tests reales.

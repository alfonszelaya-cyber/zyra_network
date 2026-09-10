# ZYRA Network

**Red de confianza digital independiente y autónoma.**
Como el WiFi o la energía: todos la consumen, nadie necesita verla.

Una infraestructura de identidad, verificación, autoridad y
evidencia, consumible por aplicaciones propias y terceros
autorizados (bancos, gobiernos, empresas, personas).

---

## Qué resuelve

- **Un ID único de confianza (ZID)** por persona, empresa o
  dispositivo, creado una sola vez y reconocido por toda la red.
- **Registro una vez, reconocido en todas partes**: quien se
  registra en una app autorizada obtiene su ZID y su perfil viaja
  con él (con permisos y auditoría por campo).
- **Historial de por vida** tipo registro civil digital: partida de
  nacimiento, salud, educación, empleo — append-only y a prueba de
  manipulación (cadena de hashes por persona).
- **Verificación para terceros con evidencia, no promesas**:
  cualquier comprador, banco o institución puede verificar un
  documento o firma OFFLINE con matemáticas (Ed25519 + SHA-256),
  sin confiar en el emisor ni consultar la red.
- **Autoridad de certificación acreditada**: emisores registrados
  con scopes explícitos, certificados con vigencia y revocación en
  cascada.

## Arquitectura

    apps (NEXO, DoctorSV, Subastas, externas)
              |
              v
    HTTP surface (runtime/api.py + capabilities_api.py)
              |
              v
    ZyraKernel (identity, verification, tokens, currency)
    ZyraCapabilities (trust services composition)
              |
              v
    17 transverse engines (consensus, integrity, encryption,
    certification, search, reputation, compression,
    scalability, supervisor, workflow, routing, system_loader,
    compliance, integrations, export, interoperability, ai)
              |
              v
    Storage (SQLite durable, WAL, snapshots, self-heal)
    Events (transactional outbox, claim/lease/fencing)
    Audit (tamper-evident hash chain)

## Los 17 motores transversales

| Motor | Responsabilidad |
|---|---|
| consensus | membership, términos, votos, líder por quorum, leases con fencing |
| integrity | proofs durables de contenido, detección de manipulación |
| encryption | keyring durable con rotación, sobres AES-GCM (zyra.enc.v1) |
| certification | emisores acreditados, certificados firmados con vigencia y revocación |
| search | búsquedas globales autorizadas, auditadas y paginadas |
| reputation | score con evidencia inmutable y decay temporal |
| compression | gzip con guardas anti-bomba |
| scalability | capacidad, backpressure, particionado estable |
| supervisor | ciclo de vida con presupuesto de reinicios y cuarentena |
| workflow | corridas durables multi-paso con compensación (saga) |
| routing | tabla de rutas priorizada y determinística |
| system_loader | carga por manifiestos con política de compatibilidad |
| compliance | políticas por jurisdicción, decisiones auditadas |
| integrations | adaptadores externos con retry y health |
| export | paquetes de evidencia firmados, verificables offline |
| interoperability | schemas versionados y negociación mutua |
| ai | provenance de análisis: qué modelo, qué versión, qué hash |

## Superficie HTTP

Núcleo (runtime/api.py): identity, verification (media,
credentials, attestations), tokens, currency.

Confianza (runtime/capabilities_api.py): apps autorizadas,
perfil portable, onboarding a ACTIVE, historial de vida,
notaría de documentos, búsqueda, reputación, export.

## Calidad

- ~290 tests en verde (pytest, colección normal)
- mypy --strict sobre todo shared_engines
- flake8, compileall
- CI en GitHub Actions: cada fase committeó código probado

Ver CHANGELOG.md para el historial de construcción y
docs/ROOT_AUTHORITY_RUNBOOK.md para el procedimiento de
rotación de la autoridad raíz.

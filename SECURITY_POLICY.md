# Zyra Network — Política de Seguridad Criptográfica

Política vinculante para la Root Authority. Vigencia: permanente.

## 1. Jerarquía de claves

ZYRA_ROOT_KEY (master, entorno/KMS, NUNCA en código)
      ↓ deriva (SHA-256 + nonce)
root.key (firma Ed25519, cifrada AES-256-GCM en disco)
      ↓ firma
attestations / fx quotes / eventos de seguridad

## 2. Ciclo de vida

| Fase | Operación | Requisito |
|---|---|---|
| Creación | Primer arranque | Master 32 bytes CSPRNG |
| Carga | Arranques posteriores | Misma master; root.key verificado |
| Fail-closed | Master incorrecta | Rechazo de arranque — nunca segunda autoridad |
| Rotación | rotate() por operador autorizado | Nueva clave; huella archivada; auditada |
| Archivo | Automático | historical_fingerprints() consultable |
| Revocación | Documental (futuro CRL) | Huella excluida por verificadores |

## 3. Procedimiento de rotación (operador)

1. GET /health → healthy
2. python scripts/backup.py
3. PersistentRootAuthority.rotate(rotated_by=<operador>)
4. Verificar nueva huella en el log
5. Publicar nueva clave pública a verificadores
6. Confirmar attestations históricos verificables

## 4. Recuperación de desastre

- Master perdida → irrecuperable POR DISEÑO (nueva era
  documentada). La master vive en KMS con backup.
- root.key corrupto → rollback.py o re-derivación con
  la misma master.
- Compromiso → rotación inmediata + revocación + forense.

## 5. Tabla de firma

| Artefacto | Firmado con | Verificado con |
|---|---|---|
| Attestations | Root Authority (Ed25519) | Clave pública embebida |
| FX Quotes | Root Authority (Ed25519) | Idem, offline |
| API Keys | N/A (hash SHA-256) | Comparación constante |
| Audit chain | Hash-chain | Recomputo |

## 6. Futuro (KMS/HSM)

- ZYRA_ROOT_KEY → AWS/GCP KMS o HSM (adapter listo)
- Rotación programada con doble control
- Anclaje externo de audit checkpoints

## 7. API Keys operativas

- Una por cliente/app, 256-bit CSPRNG
- Solo hash SHA-256 almacenado
- Rotación/revocación individuales auditadas
- Rate limiting + brute-force lockout

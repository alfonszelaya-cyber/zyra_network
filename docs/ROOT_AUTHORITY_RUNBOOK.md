# Root Authority — Rotation Runbook

Operational procedure for rotating the Root Authority key
(shared_engines/authority/root.py). This document is the
operational contract; the code enforces the mechanics.

## Roles

- **Custodian**: holds the master key passphrase; never
  sees the private key in plaintext.
- **Authorizer**: approves the rotation (two-person rule
  recommended for production).
- **Operator**: executes the procedure and records evidence.

## Preconditions

1. Current authority loads and verifies:
   `RootAuthority(...).load_or_create()` returns an active
   signer and matching status record.
2. A fresh snapshot of the authority database exists
   (SnapshotManager.create, label `pre-rotation`).
3. The rotation is recorded in an incident/change ticket
   with authorizer approval.

## Procedure

1. **Backup** — snapshot as in precondition 2; verify its
   manifest hash.
2. **Rotate** — call
   `root.rotate(rotated_by="<operator-id>")`.
   The engine persists the new encrypted key, records the
   rotation timestamp, and appends the new fingerprint to
   the historical fingerprints chain.
3. **Verify** —
   - `load_or_create()` returns the NEW key with the NEW
     fingerprint.
   - `historical_fingerprints()` contains the old
     fingerprint followed by the new one (order preserved).
   - Signatures issued BEFORE rotation still verify against
     the OLD public key (keep old public keys published).
4. **Publish** — distribute the new public key to every
   consumer that verifies attestations offline.
5. **Record evidence** — attach to the ticket: snapshot
   label, rotation timestamp, old and new fingerprints.

## Recovery

- If rotation is interrupted mid-write, the engine's
  file-atomic writes leave either the old or the new state,
  never a mixed one; re-running `load_or_create()` shows
  which. Restore the `pre-rotation` snapshot only if the
  new state is unusable, then repeat from step 2.
- Historical fingerprints are append-only: NEVER edit them;
  to invalidate a mistaken rotation, rotate again.

## What is kept

- Every historical fingerprint (verification of documents
  signed under old keys remains possible forever).
- The encrypted previous private keys are retained by the
  storage layer for audit; their plaintext is never
  reconstructed outside `load_or_create`.

# ZYRA Ecosystem - App Consolidation Map

## ADR-004: single public entrance (super-app)

The PUBLIC sees ONE app: "ZYRA". Login by ZID, then
the menu is role-based (agricultor -> AGRO screens,
gobierno -> national dashboards, banco -> credit
reports, empresa -> NEXO/Subastas).

The 9 systems are the INTERNAL engines behind that
single entrance. Isolation rule: if one internal
system is down or in maintenance, the others keep
serving.

Commercial model: verification is free forever
(offline cryptography); writes and scale are paid
per client (API keys, future workflow).

## Competitive position (different, not copy)

Not competing with go.sv or the new national
education system: being DIFFERENT and BETTER -
offline cryptographic verification, immutable
evidence chains, portable ZID across apps,
private-by-scope data. Those are the barriers
incumbents cannot cross.

## The 9 internal systems

1. nexo - business/fiscal core (wave 1)
2. agro - verified aid, prices (wave 1)
3. semilla - education (wave 1)
4. axis - health + justice + security (wave 1)
5. subastas - marketplace + Radar VIP + stocks (wave 1)
6. mi_primer_empleo - job matching (wave 1)
7. ciclo_digital - archeology + recycling (wave 2)
8. laboratorio - policy simulation + 3D (wave 2)
9. futuro_os - robots + 3D lanes (wave 3)

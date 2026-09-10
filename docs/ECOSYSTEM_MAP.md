# ZYRA Ecosystem - App Consolidation Map

Decision recorded in W22. The ecosystem is 9 systems,
all living on ZYRA Network. Every app consumes the
Network over HTTP; if one is down, the others keep
working (document verification works offline).

## The 9 systems

1. nexo - business/fiscal core (wave 1)
2. agro - verified aid, planting records, prices (wave 1)
3. semilla - education pre-k to university (wave 1)
4. axis - health + justice + security (wave 1)
5. subastas - marketplace + Radar VIP + stocks (wave 1)
6. mi_primer_empleo - job matching (wave 1)
7. ciclo_digital - archeology + recycling to tokens (wave 2)
8. laboratorio - policy simulation + 3D decisions (wave 2)
9. futuro_os - robots rescue + 3D space lanes (wave 3)

## Absorbed folders

- security_command -> axis/modules/seguridad_comando
  (penal records, police, face/emotion detection; every
  consultation is audited by the Network)
- reciclaje_digital -> ciclo_digital
- decisiones_reales -> laboratorio
- controlador_espacios -> futuro_os
- governance_portal -> ZYRA admin surface
- rednew, shared_domain -> removed (empty)

## Legacy cleanup

- templatess/ typo directories removed at any depth.
- Stray non-directory artifacts in apps/ root removed.
- AGRO real code (208 files) kept as starting point
  for its build (N1).

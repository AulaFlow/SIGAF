# Bitácora de uso de IA — SIGAF

Lineamientos 5.3: solo usos que se integraron al proyecto o influyeron en una decisión.

| Fecha | Integrante | Herramienta | Propósito | Resultado | Verificación | Commit |
|---|---|---|---|---|---|---|
| 2026-11-22 | Angel Ricardo Figueroa Flores | Claude (chat) | Esquema relacional, índices, funciones, triggers y procedimiento (#4, #5) | Aceptado; situación académica cambiada a vista | 11 pruebas en `db/pruebas.sql` (PostgreSQL 16); revisión en PR #2 | 462b6da–5b2635c |
| 2026-11-22 | Angel Ricardo Figueroa Flores | Claude (chat) | Consultas frecuentes para el análisis de acceso | Aceptado: 10 consultas, 9 en un solo centro | Ejecutadas sin error con datos de prueba | 5c57a2d |
| 2026-11-22 | Angel Ricardo Figueroa Flores | Claude (chat) | Ajustar el esquema a las decisiones del equipo (la IA solo presentó alternativas) | Aceptado: fragmentación derivada y vertical, reparto A/B provisional | 13 pruebas pasan (P12 y P13 nuevas) | ver PR #2 |
| 2026-11-22 | Angel Ricardo Figueroa Flores | Claude (chat) | Generador de ~150 mil registros sintéticos (#10) | Aceptado; contraseña fuera del código, no llena el directorio A/B | Corre sin errores contra el esquema; ruff, bandit y pip-audit limpios | ver PR del #10 |
| 2026-11-23 | Angel Ricardo Figueroa Flores | Claude (chat) | Roles, cifrado, seudonimización y TLS (#6) según las decisiones de seguridad del equipo (la IA solo presentó alternativas) | Aceptado: roles admin/API/ETL, nombres cifrados con AES-256, matrícula con HMAC, TLS obligatorio para API, ETL y replicación | 9 pruebas de seguridad (`db/pruebas_seguridad.sql`) y `infra/postgres/probar_tls.sh` (7 casos) pasan en PostgreSQL 16 | ver PR del #6 |

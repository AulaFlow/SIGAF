# Prueba de caída del primario (issue #9)

## Qué se probó

Que si el primario de un fragmento se cae de golpe, la réplica toma su lugar
sola, **sin perder datos**, y que la API sigue usando la misma dirección.

## Cómo está armado (`db/docker-compose.yml`)

| Pieza | Para qué sirve |
|---|---|
| `etcd` | Lleva el registro de quién es el primario de cada fragmento. Patroni lo consulta. |
| `pg-a1`, `pg-a2` | Fragmento A (CCB, CCSH, CCA). PostgreSQL 16 + Patroni. Uno es primario y el otro réplica síncrona. |
| `pg-b1`, `pg-b2` | Fragmento B (CCEA, CCS, CCDC). Igual que A. |
| `haproxy` | Puerta fija. 5432 = primario A, 5433 = réplica A, 5434 = primario B, 5435 = réplica B. Pregunta a Patroni (puerto 8008) quién es quién. |
| `certificados` | Genera la CA y un certificado por nodo con `infra/postgres/generar_certificados.sh`. |

Seguridad (de `infra/postgres`, issue de roles y TLS): TLS obligatorio, también
en la replicación entre nodos (`pg_stat_replication` muestra `ssl = t`, TLSv1.3),
`pg_hba` de Ricardo, usuario `sigaf_replicador` y roles de `05_seguridad.sql` /
`06_credenciales.sql`. Conectarse sin TLS es rechazado.

## Decisiones del equipo que aplica

- **CAP: CP en lo académico.** `synchronous_mode: true`: cada escritura espera a
  que la réplica la confirme, así una calificación guardada no se pierde.
- **CP estricto** (decidido por alex el 24 nov 2026): `synchronous_mode_strict: true`.
  Si la réplica de un fragmento se cae, ese fragmento **no acepta escrituras**
  hasta que vuelva. Se prefiere no escribir a escribir algo que se pueda perder.

## Cómo correrla

```bash
cd db
cp .env.example .env          # y poner contraseñas reales (mínimo 12 caracteres)
docker compose up -d --build
MSYS_NO_PATHCONV=1 docker compose exec pg-a1 patronictl -c /etc/patroni.yml list   # quién es primario (en Git Bash)
bash patroni/prueba_caida.sh      # fragmento A
bash patroni/prueba_caida.sh b    # fragmento B
```

Tablero de HAProxy: http://localhost:7000 (verde = ese nodo atiende ese puerto).

## Resultado (24 nov 2026, en una máquina)

| Paso | Fragmento A | Fragmento B |
|---|---|---|
| Calificación guardada antes de la caída | 9.50, ya en la réplica | 9.50, ya en la réplica |
| Caída del primario (`docker kill`) | pg-a1 | pg-b1 |
| Tiempo hasta que la réplica es primario | **19 s** | **19 s** |
| ¿Sigue la calificación? | Sí, cero pérdida | Sí, cero pérdida |
| Escribir sin réplica | Se queda esperando (CP estricto) | Se queda esperando |
| Regresa el nodo caído | Entra como réplica síncrona | Igual |
| Escribir de nuevo | Funciona | Funciona |

Los ~19 s salen de `ttl: 20` en Patroni: es lo que espera antes de dar por
muerto al primario. Bajarlo hace el failover más rápido, pero aumenta el riesgo
de cambiar de primario por un corte de red de unos segundos.

## Pendiente para las 4 laptops

- Un nodo por laptop: pg-a1 y pg-b1 en dos laptops, pg-a2 y pg-b2 en otras dos,
  una de ellas remota por la VPN (10.8.0.0/24, ya contemplada en `pg_hba`).
- etcd con 3 miembros (uno solo es punto único de falla).
- Llenar `directorio_fragmento` con `haproxy:5432` (A) y `haproxy:5434` (B) para
  el enrutador de la API (issue #6).

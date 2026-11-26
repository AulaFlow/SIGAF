# Registro de decisiones — SIGAF

Decisiones de diseño que cambian cómo se comporta el sistema y por qué se tomaron.
Una fila por decisión; si una decisión se revierte, se agrega otra fila que lo diga
(no se borra la anterior).

Las decisiones las tomamos los integrantes del equipo (Angel Ricardo Figueroa Flores,
Álvaro Alexis Acosta Villalpando, Kevin Matthew Saldívar Morales y Salvador Olivares
Mauricio). La IA (Claude) solo presentó alternativas con pros y contras y ayudó a
redactar (Lineamientos 5.1 a 5.3); queda en `docs/bitacora_ia.md`.

## Resumen

| Fecha | Issue | Decisión | Por qué | Consecuencia | Quién |
|---|---|---|---|---|---|
| 2026-11-22 | #4 | **D1.** Shard key: `centro_academico_id`. | 9 de las 10 consultas frecuentes se resuelven dentro de un solo centro. | Un alumno o grupo vive en un solo fragmento. | Equipo |
| 2026-11-22 | #4 | **D2.** Fragmentación horizontal derivada: `inscripcion`, `calificacion`, `entrega` y `asistencia` van con el centro del grupo; catálogos y usuarios se replican. | Lo académico de un grupo queda junto y no hay consultas entre fragmentos. | `entrega` y `asistencia` heredan `centro_academico_id` por trigger. | Equipo |
| 2026-11-22 | #4 | **D3.** Fragmentación vertical de `alumno`: datos académicos por un lado y personales (nombre, apellidos) en otra tabla restringida. | Separar sirve para proteger los datos personales. | La API lee datos personales solo por `fn_datos_alumno` (D12). | Equipo |
| 2026-11-22 | — | **D4.** Postura CAP mixta: CP para lo académico, eventual para avisos, mensajes y MongoDB. | Una calificación no puede tener dos valores; un aviso puede llegar tarde. | Ver D5: se ajustó al implementar. | Equipo |
| 2026-11-24 | #9 | **D5.** Ajuste de D4: **CP estricto en todo PostgreSQL** (`synchronous_mode_strict`); eventual solo en MongoDB. | Patroni configura la replicación síncrona por clúster, no por tabla; separar avisos daba más trabajo que valor. | Si se cae la réplica de un fragmento, ese fragmento no acepta escrituras (tampoco avisos) hasta que vuelva. | Álvaro |
| 2026-11-23 | #4 | **D6.** Reparto definitivo: A = CCB, CCSH, CCA · B = CCEA, CCS, CCDC. | Es el reparto más parejo con el conteo real del generador. | Agregar un centro nuevo obliga a decidir su fragmento. | Equipo |
| 2026-11-22 | — | **D7.** Nodos: 4 laptops, 2 fragmentos con primario y réplica; una laptop remota por VPN. | Los lineamientos piden nodos locales y remotos. | Ver D8. | Equipo |
| 2026-11-26 | #27 | **D8.** Ajuste de D7: por ahora los 4 nodos corren como contenedores en una PC; el nodo remoto queda pendiente (#27). | Así se pudo desarrollar y probar el failover sin depender de 4 equipos. | Falta definir qué laptop es la remota y probar la conexión por VPN. | Equipo |
| 2026-11-24 | #9 | **D9.** Alta disponibilidad con Patroni + etcd + HAProxy (en lugar de promover a mano o CockroachDB). | Failover automático y una puerta fija para la API. | etcd es un solo contenedor: si cae, Patroni no puede elegir nuevo primario. | Álvaro |
| 2026-11-22 | #11 | **D10.** Controles principales: roles con mínimo privilegio y seudonimización + cifrado (matrícula con HMAC, nombre cifrado, bcrypt). TLS obligatorio entre nodos y desde la API. | Son los que atacan los riesgos principales (alterar calificaciones, fuga de datos). | La llave HMAC vive fuera de la base. | Equipo |
| 2026-11-25 | #7 | **D11.** El enrutador busca a un alumno o grupo **en ambos fragmentos** y usa el que responda. | No confía en un dato del cliente ni obliga a cambiar los ids. | Doble consulta; si un fragmento está caído no se sabe si el dato está ahí. | Equipo |
| 2026-11-25 | #7 | **D12.** `fn_datos_alumno`: función `SECURITY DEFINER`, `EXECUTE` solo a `sigaf_api_svc`, `search_path` fijo, sin `PUBLIC`. | La API nunca toca la tabla de datos personales. | Requiere `db/08` (Ricardo); sin él la ruta responde 500. | Equipo |
| 2026-11-25 | #26 | **D13.** Monitoreo con script + CSV + Matplotlib; respaldos `pg_dump` por fragmento desde la réplica, con TLS y usuario de solo lectura. | Pocos recursos y fácil de restaurar (ver `docs/monitoreo_respaldos.md`). | No hay alertas automáticas; el respaldo es lógico, no incremental. | Álvaro |
| 2026-11-26 | #28 | **D14.** La API en Docker valida el certificado de la base con `verify-ca` vía HAProxy y solo recibe `ca.crt`; escucha en `127.0.0.1:8000`. | HAProxy no está en el certificado (verify-full fallaría) y la API no necesita la llave de la CA. | Solo se entra desde la misma PC; el HTTPS de la API lo hacen Salva/Kevin. | Álvaro |
| 2026-11-21 | — | **D15.** Repositorio público en la organización AulaFlow. | GitHub Free solo protege `main` en repos públicos. | No se suben secretos ni datos reales (solo sintéticos, `.env` fuera). | Equipo |
| 2026-11-26 | #11 | Si el intento de inicio de sesión no se puede anotar en `bitacora_acceso`, **no hay sesión**: el error se propaga (500) y no se entrega token. | Los lineamientos piden la bitácora de accesos; es preferible que nadie entre a que alguien entre sin dejar rastro. | `db/09_bitacora_acceso.sql` debe estar cargado en la base **antes** de desplegar la API; sin la tabla ningún login funciona. | Salvador |
| 2026-11-26 | #11 | El token JWT **no se revisa contra la base** en cada petición (sin estado) y dura 60 minutos (`SIGAF_JWT_MINUTOS`, 5 a 1440). | Ninguna petición tiene que ir a la base solo para saber quién es la persona. | Si un administrador desactiva una cuenta, su token sigue sirviendo hasta que venza (máximo la vida del token). | Salvador |
| 2026-11-26 | #11 | El correo del login se pasa **a minúsculas** antes de buscarlo, y se busca por igualdad exacta. | El generador, `pruebas.sql` y la limpieza guardan siempre minúsculas (verificado); la igualdad exacta usa el índice UNIQUE de `usuario.correo`. | La base **no** obliga minúsculas (no se agregó un CHECK, a propósito): una carga futura debe guardarlas así o esa cuenta no podrá entrar. | Salvador |
| 2026-11-26 | #11 | Todos los fallos de login responden lo mismo (401 "Correo o contraseña incorrectos") y gastan el mismo trabajo de bcrypt; el motivo real solo va a la bitácora. | Que no se pueda saber qué correos existen, ni por el mensaje ni por el tiempo de respuesta. | Para depurar un login fallido hay que consultar `bitacora_acceso` (solo la lee `sigaf_admin`). | Salvador |

## Detalle (contexto, alternativas y justificación)

> **Borrador:** > Las justificaciones marcadas "(borrador)" las redactó la IA como punto de partida y las revisa el equipo en el PR.

### D1. Shard key
- **Contexto:** elegir el campo con el que se reparten los datos entre A y B.
- **Alternativas:** `carrera_id` (un profesor con grupos en varias carreras consultaría dos fragmentos); `periodo_id` (casi todo el tráfico cae en el periodo actual, un fragmento trabajaría y el otro no).
- **Justificación (borrador):** casi todo lo que hace un alumno o profesor pasa dentro de su centro, así que con el centro como llave casi nunca hay que ir a los dos fragmentos. Además el profesor sugirió centro o carrera.

### D2. Fragmentación horizontal derivada
- **Contexto:** el profesor pide al menos una tabla fragmentada.
- **Alternativas:** solo `calificacion` (separa calificación de inscripción y obliga a cruzar fragmentos); todo lo académico (más configuración para el tiempo que había).
- **Justificación (borrador):** inscripción, calificación, entrega y asistencia siempre se consultan juntas por grupo; si viven en el mismo fragmento, una boleta se arma con una sola consulta.

### D3. Fragmentación vertical de `alumno`
- **Contexto:** los lineamientos piden horizontal y/o vertical.
- **Alternativas:** solo horizontal (no protege datos personales); metadatos de entrega (solo demuestra el concepto).
- **Justificación (borrador):** separar nombre y apellidos deja que casi todo el sistema trabaje con la matrícula seudónima y que solo una función controlada vea los datos personales.

### D4 y D5. Postura CAP
- **Contexto:** ante una partición de red no se puede tener a la vez consistencia y disponibilidad.
- **Alternativas:** CP para todo (tampoco se leen avisos en una falla); AP para todo (dos calificaciones distintas para un alumno); mixta por tabla (lo planeado en D4).
- **Qué cambió:** al configurar Patroni (#9) la replicación síncrona aplica a todo el clúster. Se eligió `synchronous_mode_strict`: cada escritura espera a la réplica y, si no hay réplica, no se escribe.
- **Justificación :** en este caso nuestra decidion fue preservar el cp, en este caso patroni aplica sincronio en todo el cluster, preferimos perder el servico unos minutos que perder una calificacion

### D6. Reparto A/B
- **Contexto:** asignar los 6 centros a los 2 fragmentos.
- **Alternativas:** A = CCB, CCS, CCA (520 vs 480 alumnos, menos parejo); A = CCB, CCDC, CCA (450 vs 550).
- **Justificación (borrador):** es el reparto más parejo; se confirmó el 23 nov con los conteos del generador (#4) y lo verifica el script de reparto (#8).

### D7 y D8. Distribución de nodos
- **Contexto:** se piden nodos locales y remotos, replicación y prueba de caída.
- **Alternativas:** contenedores en 1–2 máquinas (dos configuraciones que mantener); primario + 2 réplicas (6 nodos, no alcanzan 4 laptops).
- **Qué cambió:** hoy los 4 nodos (`pg-a1`, `pg-a2`, `pg-b1`, `pg-b2`) son contenedores en una PC. El nodo remoto y la VPN están en #27.
- **Justificación ):** con el uso de contenedores se simulo un failover haciendo uso de 4 contenedores y hacer pruebas de respaldos sin usr los 4 equipos
- **Pendiente:** qué laptop es la remota y de quién es cada una.

### D9. Patroni + etcd + HAProxy
- **Contexto:** se pide alta disponibilidad y prueba de pérdida de nodo.
- **Alternativas:** promover la réplica a mano (lento y depende de una persona); CockroachDB (ya se practicó antes; el equipo prefirió PostgreSQL y ver la replicación por dentro).
- **Justificación :** patroni fue nuestra mejor opcion ya que es automatico y no requiere intervencion humana, despues de 20 segundos este promueve a otro lider 

### D10. Controles de seguridad principales
- **Contexto:** elegir en qué controles poner más peso al defender.
- **Alternativas con menor peso:** TLS (se implementa, lo piden los lineamientos); auditoría e IDS (bitácora de calificaciones ya existe; IDS en Seguridad).
- **Justificación (borrador):** los riesgos más graves son que alguien altere calificaciones o se filtren datos personales; roles separados limitan quién puede escribir y la seudonimización hace que una fuga no diga de quién son los datos.
- **Ajuste:** el responsable de la seguridad de la API es Salvador (#11), no Ricardo como decía el documento del 22 nov.

### D11. Enrutador pregunta en ambos fragmentos
- **Alternativas:** la app manda el centro (se puede falsear); deducirlo del id (cambiar el generador y un alumno no podría cambiar de centro); tabla replicada (otra tabla que sincronizar).
- **Justificación (borrador):** son solo dos fragmentos, así que preguntar a los dos cuesta poco y no depende de nada que mande el cliente.

### D12. `fn_datos_alumno` con `SECURITY DEFINER`
- **Alternativas:** `GRANT` directo a la API (podría leer toda la tabla); usuario aparte (dos credenciales en el mismo proceso, aísla menos de lo que parece).
- **Justificación (borrador):** la API solo puede pedir lo que la función devuelve; aunque roben su usuario no pueden leer la tabla completa.

### D13. Monitoreo y respaldos (#26)
- **Alternativas:** Prometheus + Grafana; solo `patronictl`; `pg_basebackup`; pgBackRest; script en Windows con superusuario.
- **Justificación (del equipo, Álvaro):** ver `docs/monitoreo_respaldos.md`, sección "Decisiones".

### D14. API en Docker (#28)
- **Alternativas:** `verify-full` (falla porque `haproxy` no está en el SAN del certificado; se podría agregar); montar todo el volumen de certificados (la API vería `ca.key`); publicar en `0.0.0.0:8000` (cualquiera en la red entraría sin HTTPS).
- - **Justificación:** usamos verify-ca porque la API entra por HAProxy y el certificado no dice "haproxy", así que verify-full fallaría; verify-ca igual revisa que el certificado esté firmado por nosotros. A la API solo le damos ca.crt, que sirve para revisar certificados, y no ca.key, que sirve para crearlos; si alguien entra al contenedor de la API, no puede fabricar certificados falsos. La dejamos en 127.0.0.1 porque aún no tiene HTTPS.
### D15. Repositorio público
- **Alternativas:** privado (GitHub Free no permite proteger `main` en privados de una organización).
- **Justificación (borrador):** queríamos que nadie pudiera subir a `main` sin PR y revisión; como todos los datos son sintéticos, que sea público no expone nada real.

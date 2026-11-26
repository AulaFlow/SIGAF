# Registro de decisiones — SIGAF

Decisiones de diseño que cambian cómo se comporta el sistema y por qué se tomaron.
Una fila por decisión; si una decisión se revierte, se agrega otra fila que lo diga
(no se borra la anterior).

| Fecha | Issue | Decisión | Por qué | Consecuencia | Quién |
|---|---|---|---|---|---|
| 2026-11-26 | #11 | Si el intento de inicio de sesión no se puede anotar en `bitacora_acceso`, **no hay sesión**: el error se propaga (500) y no se entrega token. | Los lineamientos piden la bitácora de accesos; es preferible que nadie entre a que alguien entre sin dejar rastro. | `db/08_bitacora_acceso.sql` debe estar cargado en la base **antes** de desplegar la API; sin la tabla ningún login funciona. | Salvador |
| 2026-11-26 | #11 | El token JWT **no se revisa contra la base** en cada petición (sin estado) y dura 60 minutos (`SIGAF_JWT_MINUTOS`, 5 a 1440). | Ninguna petición tiene que ir a la base solo para saber quién es la persona. | Si un administrador desactiva una cuenta, su token sigue sirviendo hasta que venza (máximo la vida del token). | Salvador |
| 2026-11-26 | #11 | El correo del login se pasa **a minúsculas** antes de buscarlo, y se busca por igualdad exacta. | El generador, `pruebas.sql` y la limpieza guardan siempre minúsculas (verificado); la igualdad exacta usa el índice UNIQUE de `usuario.correo`. | La base **no** obliga minúsculas (no se agregó un CHECK, a propósito): una carga futura debe guardarlas así o esa cuenta no podrá entrar. | Salvador |
| 2026-11-26 | #11 | Todos los fallos de login responden lo mismo (401 "Correo o contraseña incorrectos") y gastan el mismo trabajo de bcrypt; el motivo real solo va a la bitácora. | Que no se pueda saber qué correos existen, ni por el mensaje ni por el tiempo de respuesta. | Para depurar un login fallido hay que consultar `bitacora_acceso` (solo la lee `sigaf_admin`). | Salvador |

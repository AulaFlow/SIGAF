#!/bin/bash
# =====================================================================
# SIGAF · respaldo de los fragmentos A y B con pg_dump (issue #26)
# Corre DENTRO del contenedor "respaldos" (ver docker-compose.yml).
#
#   respaldar.sh          cada INTERVALO segundos, para siempre (lo que usa Docker)
#   respaldar.sh una      un solo respaldo y termina:
#                         docker compose exec respaldos respaldar.sh una
#
# - Se conecta a la RÉPLICA de cada fragmento (así no carga al primario);
#   si no hay réplica, usa el primario.
# - TLS obligatorio con verify-full: comprueba que el certificado del nodo
#   lo firmó la CA del proyecto y que es de ese nodo (decisión del equipo).
# - Usuario sigaf_respaldo: solo lectura (mínimo privilegio).
# - Archivo: /respaldos/sigaf_<a|b>_<AAAAMMDD_HHMMSS>.dump (formato custom
#   de pg_dump: comprimido y se puede restaurar por partes con pg_restore).
# - Guarda los últimos GUARDAR respaldos de cada fragmento y borra los viejos.
# =====================================================================
set -uo pipefail

DESTINO="${DESTINO:-/respaldos}"
INTERVALO="${INTERVALO:-86400}"   # 24 h
GUARDAR="${GUARDAR:-7}"
REINTENTO="${REINTENTO:-300}"  # si falla, reintenta en 5 min (no espera 24 h)
umask 077                         # los respaldos solo los lee el dueño: traen datos de alumnos
export PGUSER=sigaf_respaldo PGDATABASE=postgres PGPASSWORD="${SIGAF_PASS_RESPALDO:?falta}"
export PGSSLMODE=verify-full PGSSLROOTCERT=/certs/ca.crt PGCONNECT_TIMEOUT=5

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" | tee -a "$DESTINO/respaldos.log"; }

# Elige el nodo: la réplica (pg_is_in_recovery = t); si no hay, el primario.
elegir_nodo() {
    local f="$1" n en_recuperacion primario=""
    for n in "pg-${f}1" "pg-${f}2"; do
        en_recuperacion="$(psql -h "$n" -AtqX -c "SELECT pg_is_in_recovery()" 2>/dev/null)" || continue
        [ "$en_recuperacion" = "t" ] && { echo "$n"; return 0; }
        primario="$n"
    done
    [ -n "$primario" ] && { echo "$primario"; return 0; }
    return 1
}

respaldar_fragmento() {
    local f="$1" nodo archivo tmp
    if ! nodo="$(elegir_nodo "$f")"; then
        log "ERROR fragmento ${f^^}: ningún nodo responde"
        return 1
    fi
    archivo="$DESTINO/sigaf_${f}_$(date '+%Y%m%d_%H%M%S').dump"
    tmp="$archivo.parcial"           # si se corta a la mitad no queda un .dump roto
    if pg_dump -h "$nodo" -Fc -f "$tmp" 2>>"$DESTINO/respaldos.log"; then
        mv "$tmp" "$archivo"
        sha256sum "$archivo" | sed "s|$DESTINO/||" > "$archivo.sha256"
        log "OK fragmento ${f^^} desde $nodo -> $(basename "$archivo") ($(du -h "$archivo" | cut -f1))"
    else
        rm -f "$tmp"
        log "ERROR fragmento ${f^^}: pg_dump falló en $nodo (detalle arriba)"
        return 1
    fi
    # Rotación: deja los últimos $GUARDAR
    ls -1t "$DESTINO"/sigaf_"${f}"_*.dump 2>/dev/null | tail -n +"$((GUARDAR + 1))" | while read -r viejo; do
        rm -f "$viejo" "$viejo.sha256"
        log "borrado por rotación: $(basename "$viejo")"
    done
}

una_vez() {
    local errores=0
    respaldar_fragmento a || errores=1
    respaldar_fragmento b || errores=1
    return "$errores"
}

mkdir -p "$DESTINO"
if [ "${1:-}" = "una" ]; then
    una_vez
    exit $?
fi

log "servicio de respaldos iniciado: cada ${INTERVALO}s, guarda ${GUARDAR} por fragmento"
sleep 30   # da tiempo a que Patroni elija primarios al arrancar todo junto
while true; do
    if una_vez; then
        sleep "$INTERVALO"
    else
        log "hubo errores; se reintenta en ${REINTENTO}s"
        sleep "$REINTENTO"
    fi
done

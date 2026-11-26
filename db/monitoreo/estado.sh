#!/usr/bin/env bash
# =====================================================================
# SIGAF · monitoreo de la base distribuida (issue #26, Lineamientos IV.a.6)
#
#   cd db && bash monitoreo/estado.sh          (una foto del estado)
#   cd db && bash monitoreo/estado.sh 60       (una foto cada 60 s; Ctrl+C para parar)
#
# Por cada nodo muestra:
#   - rol y estado según Patroni (Leader / Sync Standby, running / streaming)
#   - atraso de la réplica en MB (lag)
#   - conexiones activas de clientes (pg_stat_activity)
#   - tamaño de la base (pg_database_size)
# y agrega una línea por nodo a monitoreo/historial.csv para ver el crecimiento
# con el tiempo (las gráficas salen con monitoreo/graficas.py).
#
# Entra a cada contenedor como postgres por socket local (regla
# "local all postgres peer"): es la excepción de "admin local" del equipo,
# no viaja nada por la red. Solo necesita Docker.
# =====================================================================
set -uo pipefail
export MSYS_NO_PATHCONV=1          # Git Bash en Windows: no tocar las rutas /...
cd "$(dirname "$0")/.."

CSV="monitoreo/historial.csv"
CADA="${1:-0}"

# Lista de Patroni de un fragmento; si el primer nodo no responde, usa el otro.
lista() {
    local f="$1" n
    for n in "pg-${f}1" "pg-${f}2"; do
        if docker compose exec -T "$n" patronictl -c /etc/patroni.yml list -f tsv </dev/null 2>/dev/null; then
            return 0
        fi
    done
    return 1
}

# Una consulta SQL en un nodo, como postgres por socket local.
sql() { docker compose exec -T -u postgres "$1" psql -d postgres -AtqX -c "$2" </dev/null 2>/dev/null; }

# Imprime un renglón de la tabla y lo agrega al CSV
renglon() {
    local f="$1" nodo="$2" rol="$3" estado="$4" lag="$5" conex="$6" tamano="$7" mb="-"
    [ -n "$tamano" ] && mb=$((tamano / 1024 / 1024))
    printf '%-4s %-6s %-13s %-11s %7s %6s %10s\n' "${f^^}" "$nodo" "$rol" "$estado" \
        "${lag:--}" "${conex:--}" "$mb"
    echo "$fecha,${f^^},$nodo,$rol,$estado,$lag,$conex,$tamano" >> "$CSV"
}

foto() {
    fecha="$(date '+%Y-%m-%d %H:%M:%S')"   # global: la usa renglon()
    local caidos=0
    [ -f "$CSV" ] || echo "fecha,fragmento,nodo,rol,estado,lag_mb,conexiones,tamano_bytes" > "$CSV"

    echo
    echo "== SIGAF · estado de la base · $fecha =="
    printf '%-4s %-6s %-13s %-11s %7s %6s %10s\n' FRAG NODO ROL ESTADO LAG_MB CONEX TAMANO_MB

    local f linea cluster nodo host rol estado tl lag datos conex tamano
    for f in a b; do
        if ! linea="$(lista "$f")"; then
            echo "${f^^}    ningún nodo responde (¿está arriba el Docker?)"
            caidos=1
            continue
        fi
        while IFS=$'\t' read -r cluster nodo host rol estado tl lag; do
            [ "$cluster" = "Cluster" ] && continue          # encabezado
            datos="$(sql "$nodo" "SELECT
                        (SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend'),
                        pg_database_size('postgres')")"
            if [ -n "$datos" ]; then
                conex="${datos%%|*}"; tamano="${datos##*|}"
            else
                # Patroni tarda hasta 20 s (ttl) en darse cuenta; si no contesta SQL, está caído
                conex=""; tamano=""; estado="no responde"
            fi
            [ "$estado" = "running" ] || [ "$estado" = "streaming" ] || caidos=1
            renglon "$f" "$nodo" "$rol" "$estado" "${lag:-}" "$conex" "$tamano"
        done <<< "$linea"
        # Patroni borra de la lista al nodo que lleva caído más de 20 s
        for nodo in "pg-${f}1" "pg-${f}2"; do
            if ! grep -q $'\t'"$nodo"$'\t' <<< "$linea"; then
                renglon "$f" "$nodo" "-" "ausente" "" "" ""
                caidos=1
            fi
        done
    done

    [ "$caidos" -eq 0 ] && echo "OK: todos los nodos arriba." || echo "ATENCIÓN: hay nodos caídos o sin réplica."
    echo "(guardado en db/$CSV)"
    return "$caidos"
}

if [ "$CADA" -gt 0 ] 2>/dev/null; then
    while true; do foto; sleep "$CADA"; done
else
    foto
fi

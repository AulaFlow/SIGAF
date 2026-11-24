#!/usr/bin/env bash
# =====================================================================
# SIGAF · prueba de caída del primario (issue #9)
#
#   cd db && bash patroni/prueba_caida.sh        (fragmento A)
#   cd db && bash patroni/prueba_caida.sh b      (fragmento B)
#
# 1. Guarda una calificación de prueba en el primario.
# 2. "Desconecta" el primario de golpe (docker kill = se fue la luz).
# 3. Mide cuánto tarda Patroni en promover la réplica.
# 4. Revisa que la calificación siga ahí (cero pérdida).
# 5. Muestra que, sin réplica, NO se puede escribir (CP estricto).
# 6. Regresa el nodo caído: entra como réplica y ya se puede escribir.
# Solo necesita Docker (no hace falta psql en tu compu).
# =====================================================================
set -euo pipefail
# En Git Bash (Windows) evita que /etc/... se convierta en C:/Program Files/Git/etc/...
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

F="${1:-a}"
NODOS=("pg-$F"1 "pg-$F"2)

lista() { docker compose exec -T "$1" patronictl -c /etc/patroni.yml list -f tsv 2>/dev/null; }
lider_desde() { lista "$1" | awk -F'\t' '$4=="Leader" && $5=="running" {print $2}'; }
sql() { docker compose exec -T -u postgres "$1" psql -U postgres -d postgres -Atq -v ON_ERROR_STOP=1 -c "$2"; }

PRIMARIO="$(lider_desde "${NODOS[0]}")"
[ -n "$PRIMARIO" ] || { echo "No hay primario en el fragmento ${F^^}. ¿Está arriba el Docker?"; exit 1; }
REPLICA="${NODOS[0]}"; [ "$PRIMARIO" = "${NODOS[0]}" ] && REPLICA="${NODOS[1]}"

echo "== Fragmento ${F^^}: primario = $PRIMARIO, réplica = $REPLICA"
lista "$PRIMARIO"

echo
echo "== 1. Guardo una calificación de prueba en el primario"
sql "$PRIMARIO" "CREATE TABLE IF NOT EXISTS public.prueba_caida (
                   id serial PRIMARY KEY, momento text, nota numeric(4,2),
                   guardada_en timestamptz DEFAULT now())"
sql "$PRIMARIO" "INSERT INTO public.prueba_caida (momento, nota) VALUES ('antes de la caída', 9.5)"
echo "   En la réplica ya está: $(sql "$REPLICA" "SELECT momento || ' = ' || nota FROM public.prueba_caida ORDER BY id DESC LIMIT 1")"

echo
echo "== 2. Se cae el primario ($PRIMARIO) de golpe"
docker compose kill "$PRIMARIO" >/dev/null 2>&1
INICIO=$(date +%s)

echo "== 3. Esperando a que Patroni promueva a $REPLICA..."
NUEVO=""
for _ in $(seq 1 90); do
    NUEVO="$(lider_desde "$REPLICA" || true)"
    [ "$NUEVO" = "$REPLICA" ] && break
    sleep 1
done
TARDO=$(( $(date +%s) - INICIO ))
[ "$NUEVO" = "$REPLICA" ] || { echo "   ERROR: no hubo failover en 90 s"; exit 1; }
echo "   ✔ $REPLICA es el nuevo primario. Tardó $TARDO segundos."
lista "$REPLICA"

echo
echo "== 4. ¿Se perdió la calificación?"
QUEDA="$(sql "$REPLICA" "SELECT count(*) FROM public.prueba_caida WHERE momento = 'antes de la caída'")"
if [ "$QUEDA" -ge 1 ]; then echo "   ✔ No: sigue ahí ($QUEDA fila/s). Cero pérdida de datos."
else echo "   ✘ Se perdió"; exit 1; fi

echo
echo "== 5. Sin réplica, ¿se puede escribir? (decisión del equipo: CP estricto)"
if timeout 8 docker compose exec -T -u postgres "$REPLICA" psql -U postgres -d postgres -Atq \
     -c "INSERT INTO public.prueba_caida (momento, nota) VALUES ('sin réplica', 7)" >/dev/null 2>&1; then
    echo "   (se escribió: el modo estricto no está activo)"
else
    echo "   ✔ La escritura se queda esperando: sin réplica no se confirma (se confirma cuando la réplica regrese)."
fi

echo
echo "== 6. Regresa $PRIMARIO (se reconecta como réplica)"
docker compose start "$PRIMARIO" >/dev/null 2>&1
for _ in $(seq 1 120); do
    lista "$REPLICA" | awk -F'\t' -v n="$PRIMARIO" '$2==n && $4=="Sync Standby" && $5=="streaming" {ok=1} END {exit !ok}' && break
    sleep 1
done
lista "$REPLICA"
sql "$REPLICA" "INSERT INTO public.prueba_caida (momento, nota) VALUES ('después de regresar', 10)"
echo "   ✔ Ya se puede escribir otra vez. Lo que quedó guardado:"
sql "$REPLICA" "SELECT '   ' || id || ') ' || momento || ' = ' || nota FROM public.prueba_caida ORDER BY id"
echo
echo "RESULTADO: failover en $TARDO s, sin pérdida de datos. Nuevo primario: $REPLICA."

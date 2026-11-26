#!/usr/bin/env bash
# =====================================================================
# SIGAF · prueba de recuperación (issue #26)
#
#   cd db && bash respaldos/probar_restauracion.sh        (fragmento A)
#   cd db && bash respaldos/probar_restauracion.sh b      (fragmento B)
#
# 1. Toma el respaldo más nuevo del fragmento y revisa su sha256
#    (que el archivo no se dañó).
# 2. Levanta un PostgreSQL 16 LIMPIO y desechable, sin red (--network none):
#    no puede tocar a los nodos reales.
# 3. Restaura el respaldo con pg_restore.
# 4. Cuenta las filas de cada tabla del esquema sigaf en la copia restaurada
#    y en el primario real, y las compara.
# 5. Borra el contenedor desechable.
# Si nadie escribió en la base después del respaldo, los conteos deben ser iguales.
# =====================================================================
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

F="${1:-a}"
LIMPIA="sigaf-restauracion"
VOLUMEN="sigaf_respaldos"         # proyecto "sigaf" + volumen "respaldos" del compose

# Cuenta filas de todas las tablas de sigaf (query_to_xml permite un count(*) por tabla en una sola consulta)
CONTEOS="SELECT table_name || '|' || (xpath('/row/c/text()',
           query_to_xml(format('SELECT count(*) AS c FROM %I.%I', table_schema, table_name),
                        false, true, '')))[1]::text
         FROM information_schema.tables
         WHERE table_schema = 'sigaf' AND table_type = 'BASE TABLE' ORDER BY 1"

# 1. Respaldo más nuevo + revisión de integridad
ARCHIVO="$(docker compose exec -T respaldos sh -c "ls -1t /respaldos/sigaf_${F}_*.dump 2>/dev/null | head -1" </dev/null)"
[ -n "$ARCHIVO" ] || { echo "No hay respaldos del fragmento ${F^^}. Corre: docker compose exec respaldos respaldar.sh una"; exit 1; }
echo "1. Respaldo: $ARCHIVO"
docker compose exec -T respaldos sh -c "cd /respaldos && sha256sum -c $(basename "$ARCHIVO").sha256" </dev/null

# 2. Base limpia y desechable
docker rm -f "$LIMPIA" >/dev/null 2>&1 || true
trap 'docker rm -f "$LIMPIA" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$LIMPIA" --network none -e POSTGRES_HOST_AUTH_METHOD=trust \
    -v "$VOLUMEN":/respaldos:ro postgres:16 >/dev/null
echo -n "2. Base limpia arrancando"
for _ in $(seq 1 30); do
    docker exec "$LIMPIA" pg_isready -U postgres -q 2>/dev/null && break
    echo -n "."; sleep 2
done
# pg_isready puede decir que sí durante el arranque inicial; esperamos a que acepte consultas
until docker exec "$LIMPIA" psql -U postgres -Atqc "SELECT 1" >/dev/null 2>&1; do sleep 1; done
echo " lista"

# 3. Restaurar (sin dueños ni permisos: en la base limpia no existen los roles de SIGAF)
TMP_R="$(mktemp)"; TMP_V="$(mktemp)"
INICIO=$SECONDS
docker exec "$LIMPIA" pg_restore -U postgres -d postgres --no-owner --no-privileges --exit-on-error "$ARCHIVO"
echo "3. Restaurado en $((SECONDS - INICIO)) s"

# 4. Comparar conteos con el primario real
LIDER="$(docker compose exec -T "pg-${F}1" patronictl -c /etc/patroni.yml list -f tsv </dev/null \
         | awk -F'\t' '$4=="Leader" {print $2}')"
docker exec "$LIMPIA" psql -U postgres -d postgres -AtqX -c "$CONTEOS" > "$TMP_R"
docker compose exec -T -u postgres "$LIDER" psql -d postgres -AtqX -c "$CONTEOS" </dev/null > "$TMP_V"

echo "4. Conteos (restaurado vs primario real $LIDER):"
printf '   %-28s %10s %10s\n' TABLA RESTAURADO REAL
diferencias=0
while IFS='|' read -r tabla real; do
    restaurado="$(awk -F'|' -v t="$tabla" '$1==t {print $2}' "$TMP_R")"
    marca=""; [ "$restaurado" = "$real" ] || { marca="  <-- distinto"; diferencias=1; }
    printf '   %-28s %10s %10s%s\n' "$tabla" "${restaurado:-falta}" "$real" "$marca"
done < "$TMP_V"
rm -f "$TMP_R" "$TMP_V"

if [ "$diferencias" -eq 0 ]; then
    echo "RESULTADO: OK, el respaldo del fragmento ${F^^} se restauró completo."
else
    echo "RESULTADO: hay diferencias (¿alguien escribió después del respaldo?)."
    exit 1
fi

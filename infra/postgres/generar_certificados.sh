#!/usr/bin/env bash
# =====================================================================
# SIGAF · infra/postgres/generar_certificados.sh  (issue #6)
# Crea una autoridad certificadora (CA) propia del proyecto y un
# certificado TLS para cada nodo de PostgreSQL.
#
#   ./generar_certificados.sh laptop1 laptop2 laptop3 laptop4
#
# Los nombres pueden ser hostnames o IPs (de la red local o de la VPN).
# Salida en ./certs/ (NO se sube a git: ver .gitignore):
#   ca.crt            -> se copia a TODOS los nodos y a la API (para verificar)
#   ca.key            -> se guarda fuera de los nodos; firma certificados
#   <nodo>.crt/.key   -> se copian solo a ese nodo
# =====================================================================
set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "Uso: $0 nodo1 [nodo2 ...]" >&2
    exit 1
fi

DIR="$(dirname "$0")/certs"
DIAS=365
mkdir -p "$DIR"
chmod 700 "$DIR"

if [ ! -f "$DIR/ca.key" ]; then
    openssl req -x509 -newkey rsa:4096 -nodes -days "$DIAS" \
        -keyout "$DIR/ca.key" -out "$DIR/ca.crt" \
        -subj "/O=SIGAF/CN=SIGAF CA" 2>/dev/null
    chmod 600 "$DIR/ca.key"
    echo "[ok] CA creada"
fi

for NODO in "$@"; do
    # SAN: el nombre del nodo, localhost y, si es IP, también como IP
    SAN="DNS:$NODO,DNS:localhost,IP:127.0.0.1"
    if [[ "$NODO" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        SAN="IP:$NODO,DNS:localhost,IP:127.0.0.1"
    fi
    openssl req -newkey rsa:2048 -nodes \
        -keyout "$DIR/$NODO.key" -out "$DIR/$NODO.csr" \
        -subj "/O=SIGAF/CN=$NODO" 2>/dev/null
    openssl x509 -req -in "$DIR/$NODO.csr" -days "$DIAS" \
        -CA "$DIR/ca.crt" -CAkey "$DIR/ca.key" -CAcreateserial \
        -extfile <(printf "subjectAltName=%s\nextendedKeyUsage=serverAuth" "$SAN") \
        -out "$DIR/$NODO.crt" 2>/dev/null
    rm -f "$DIR/$NODO.csr"
    chmod 600 "$DIR/$NODO.key"   # PostgreSQL rechaza llaves legibles por otros
    echo "[ok] certificado para $NODO ($SAN)"
done

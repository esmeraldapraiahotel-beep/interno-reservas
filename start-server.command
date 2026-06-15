#!/bin/bash
# Atalho pra iniciar o servidor de impressão no Mac.
# Salve em ~/Desktop ou abra com dois cliques.
cd "$(dirname "$0")"
echo "Iniciando servidor de impressão…"
python3 print-server.py

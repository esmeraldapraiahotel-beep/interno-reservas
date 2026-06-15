#!/bin/bash
# Esmeralda Praia Hotel — Vouchers Internos
# Bootstrap one-click pra macOS
# Baixa o projeto, extrai e roda o setup. Zero pré-requisitos.

set -e
cd "$(dirname "$0")"

clear
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Vouchers Internos — Instalador (macOS)"
echo "  Esmeralda Praia Hotel"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "Vou:"
echo "  1. Baixar o projeto do GitHub"
echo "  2. Extrair em ~/Projetos/interno-reservas"
echo "  3. Rodar o setup automático"
echo ""
read -p "Pressione ENTER pra continuar (Ctrl+C pra cancelar)…"

DEST="$HOME/Projetos/interno-reservas"
ZIP="/tmp/interno-reservas.zip"
URL="https://github.com/esmeraldapraiahotel-beep/interno-reservas/archive/refs/heads/main.zip"

echo ""
echo "[1/3] Baixando projeto…"
curl -sL -o "$ZIP" "$URL"

echo "[2/3] Extraindo…"
mkdir -p "$HOME/Projetos"
rm -rf "$DEST" /tmp/interno-reservas-extract
unzip -q "$ZIP" -d /tmp/interno-reservas-extract
mv /tmp/interno-reservas-extract/interno-reservas-main "$DEST"
rm -rf "$ZIP" /tmp/interno-reservas-extract

echo "[3/3] Rodando setup automático…"
chmod +x "$DEST/setup.command"
cd "$DEST"
bash setup.command

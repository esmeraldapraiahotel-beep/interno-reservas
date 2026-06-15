#!/bin/bash
# Esmeralda Praia Hotel — Vouchers Internos
# Instalador one-click pra configurar a impressora POS80 (GoldenSky)
# Duplo-clique pra rodar.
set -e

cd "$(dirname "$0")"
clear

echo "╔════════════════════════════════════════════╗"
echo "║  Vouchers Internos — Setup automático      ║"
echo "║  Esmeralda Praia Hotel                     ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# ─── 1. Python + dependências ─────────────────────────────
echo "▸ Verificando Python e dependências…"
if ! command -v python3 >/dev/null 2>&1; then
  echo "  ✕ Python 3 não encontrado. Instale o Xcode Command Line Tools:"
  echo "      xcode-select --install"
  read -p "Pressione ENTER para sair"
  exit 1
fi
python3 -c "import PIL, qrcode" 2>/dev/null || {
  echo "  Instalando bibliotecas (Pillow, qrcode)…"
  pip3 install --user --quiet pillow qrcode 2>&1 | tail -3
}
echo "  ✓ Python OK"
echo ""

# ─── 2. Driver POS-80 (PPD + filter pos) ──────────────────
echo "▸ Verificando driver da impressora…"
if [ ! -f /usr/libexec/cups/filter/pos ] || [ ! -f /Library/Printers/POS/PPDs/POS-80.ppd ]; then
  echo "  Driver POS-80 não instalado."
  if [ -f ~/Downloads/POS_Printer_Driver.pkg ]; then
    echo "  Pacote achado em ~/Downloads/POS_Printer_Driver.pkg"
    xattr -d com.apple.quarantine ~/Downloads/POS_Printer_Driver.pkg 2>/dev/null || true
    echo "  Abrindo instalador — siga os passos (vai pedir senha)…"
    open -W ~/Downloads/POS_Printer_Driver.pkg
  else
    echo "  ✕ Coloque POS_Printer_Driver.pkg na pasta Downloads e rode de novo."
    read -p "Pressione ENTER para sair"
    exit 1
  fi
fi
echo "  ✓ Driver OK"
echo ""

# ─── 3. Detecta impressora USB ─────────────────────────────
echo "▸ Procurando impressora térmica conectada…"
PRINTER_NAME=""
PRINTER_URI=""

# Procura primeiro por POS80 já configurada
if lpstat -p POS80 >/dev/null 2>&1; then
  PRINTER_NAME="POS80"
  PRINTER_URI=$(lpoptions -p POS80 | tr ' ' '\n' | grep '^device-uri=' | cut -d= -f2-)
fi

# Senão, busca qualquer USB com nome POS/GoldenSky
if [ -z "$PRINTER_NAME" ]; then
  USB_URI=$(/usr/libexec/cups/backend/usb 2>/dev/null | grep -iE 'POS|GoldenSky' | awk '{print $2}' | head -1)
  if [ -n "$USB_URI" ]; then
    PRINTER_URI="$USB_URI"
    PRINTER_NAME="POS80"
    echo "  Configurando POS80 ($USB_URI)…"
    lpadmin -p POS80 -E -v "$USB_URI" -P /Library/Printers/POS/PPDs/POS-80.ppd \
      -o PageCutType=2FullCutPage -o DocCutType=2FullCutDoc \
      -o FeedCutAfterJobEnd=0None 2>&1 || true
  fi
fi

if [ -z "$PRINTER_NAME" ]; then
  echo "  ⚠ Nenhuma impressora térmica achada. Conecte via USB e rode de novo."
  read -p "Pressione ENTER para sair"
  exit 1
fi
echo "  ✓ Impressora: $PRINTER_NAME"
echo ""

# ─── 4. LaunchAgent (auto-start) ──────────────────────────
echo "▸ Configurando auto-start no boot…"
LAUNCHAGENT_DIR="$HOME/Library/LaunchAgents"
LAUNCHAGENT_FILE="$LAUNCHAGENT_DIR/com.esmeralda.vouchers.plist"
mkdir -p "$LAUNCHAGENT_DIR"
SCRIPT_PATH="$(pwd)/print-server.py"

cat > "$LAUNCHAGENT_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.esmeralda.vouchers</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$SCRIPT_PATH</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$(pwd)</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>VOUCHER_PRINTER_NAME</key><string>$PRINTER_NAME</string>
  </dict>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/voucher-server.log</string>
  <key>StandardErrorPath</key><string>/tmp/voucher-server.err</string>
</dict>
</plist>
EOF

launchctl unload "$LAUNCHAGENT_FILE" 2>/dev/null || true
launchctl load "$LAUNCHAGENT_FILE"
sleep 3
echo "  ✓ Auto-start configurado"
echo ""

# ─── 5. Teste final ───────────────────────────────────────
echo "▸ Testando servidor local…"
sleep 1
if curl -s --max-time 5 http://localhost:9876/health | grep -q '"ok": true'; then
  echo "  ✓ Servidor respondendo em http://localhost:9876"
else
  echo "  ⚠ Servidor não respondeu. Veja log em /tmp/voucher-server.err"
fi
echo ""

# ─── 6. Página de testes ──────────────────────────────────
echo "╔════════════════════════════════════════════╗"
echo "║  Tudo pronto! 🎉                            ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Abra o app em:"
echo "  https://internoreservas.esmeraldapraiahotel.com.br"
echo ""
echo "Pra imprimir um voucher de teste:"
read -p "Pressione ENTER pra abrir o app no navegador (ou Ctrl-C pra sair)"
open "https://internoreservas.esmeraldapraiahotel.com.br"

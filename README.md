# Vouchers Internos — Esmeralda Praia Hotel

App pra impressão de vouchers internos na recepção / balcão de Reservas. Hospedado em
`internoreservas.esmeraldapraiahotel.com.br`, imprime na impressora térmica
POS80 (GoldenSky) conectada via USB ao PC.

## Setup em um PC novo (1-clique)

### 🍎 macOS

1. **Conecte a impressora** POS80 via USB.
2. Coloque o **driver `POS_Printer_Driver.pkg`** em `~/Downloads`.
3. Clone o projeto:
   ```bash
   git clone https://github.com/esmeraldapraiahotel-beep/interno-reservas.git ~/Projetos/interno-reservas
   cd ~/Projetos/interno-reservas
   ```
4. **Duplo-clique em `setup.command`**.

### 🪟 Windows

1. **Conecte a impressora** POS80 via USB.
2. Clone o projeto (Git for Windows ou baixe o ZIP):
   ```powershell
   git clone https://github.com/esmeraldapraiahotel-beep/interno-reservas.git C:\interno-reservas
   cd C:\interno-reservas
   ```
3. **Duplo-clique em `setup.bat`** (rode como administrador).

> O instalador do driver `POS80Setup.exe` já vem no projeto e roda automaticamente. O SumatraPDF (usado pra imprimir silenciosamente) é baixado pelo próprio script.

### O que cada script faz

- ✅ Verifica/instala dependências (Python, Pillow, qrcode)
- ✅ Instala o driver da impressora (POS_Printer_Driver.pkg no Mac / POS80Setup.exe no Windows)
- ✅ Detecta a impressora térmica automaticamente
- ✅ Configura a fila de impressão (CUPS / Get-Printer)
- ✅ Cria auto-start (LaunchAgent no Mac / Startup folder no Windows)
- ✅ Inicia o servidor local e abre o app no navegador

## Estrutura do projeto

```
interno-reservas/
├── index.html           # App principal (emissão de voucher)
├── dashboard.html       # Dashboard de emissões
├── print-server.py      # Servidor local de impressão (porta 9876, cross-platform)
├── logo-esmeralda.png   # Logo do hotel impressa no voucher
├── logo.svg             # Logo Alavantú (uso futuro)
├── setup.command        # ⭐ Instalador one-click (macOS)
├── setup.ps1            # Script PowerShell de setup (Windows)
├── setup.bat            # ⭐ Wrapper one-click (Windows)
├── POS80Setup.exe       # Driver da impressora pra Windows
└── README.md
```

## Como funciona

```
┌──────────────────────────┐         ┌──────────────────────┐
│ Browser do balcão        │ POST →  │ Print server (Python)│
│ internoreservas...com.br │         │ http://localhost:9876│
└──────────────────────────┘         └──────────┬───────────┘
                                                │ lp -d POS80
                                                ▼
                                        Impressora térmica
                                        (POS80 / GoldenSky)
```

- O **frontend** é estático no VPS (HTML + JS).
- O **print server** roda no PC do balcão na porta 9876.
- O HTML é renderizado em PDF via Chrome headless, e o CUPS+filter oficial do
  POS-80 converte pra ESC/POS automaticamente.

## Operação dia-a-dia

- O servidor sobe sozinho ao ligar o Mac (via LaunchAgent).
- A barra verde no topo do app indica que tá conectado.
- Se cair, basta rodar `bash setup.command` de novo.

### Reinício manual

**macOS:**
```bash
launchctl unload ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
launchctl load   ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
```

**Windows:** Task Manager → encerra o `python.exe` que tá rodando → executa `setup.bat` de novo (ou só roda o atalho da pasta Startup).

### Logs

- **macOS:** `/tmp/voucher-server.log` (saída) e `/tmp/voucher-server.err` (erros)
- **Windows:** janela do Python no Tray do Windows

### Parar de iniciar automaticamente

**macOS:**
```bash
launchctl unload ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
rm ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
```

**Windows:** apague o atalho `VouchersInternos.lnk` da pasta Startup:
```powershell
Remove-Item "$([Environment]::GetFolderPath('Startup'))\VouchersInternos.lnk"
```

## Tipos de voucher disponíveis

- Welcome Drink (sem dados do hóspede)
- Gelato Liberado / Drink Liberado (diário, 1 por pessoa, exclui criança no drink)
- City Tour / Passeio Pipa / Passeio Litoral Norte (campo "Data do passeio" em branco)
- Vila CVC · 15% OFF
- Hóspede Raiz (checkboxes Gelato/Drink + regulamento)
- Hóspede Romântico (campo "Data do jantar" em branco)

## Deploy do frontend (VPS)

```bash
rsync -az -e "ssh -i ~/.ssh/hostinger_eph" \
  index.html dashboard.html logo-esmeralda.png \
  root@187.127.26.180:/var/www/internoreservas-esmeralda/
```

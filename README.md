# Vouchers Internos — Esmeralda Praia Hotel

App pra impressão de vouchers internos na recepção / balcão de Reservas. Hospedado em
`internoreservas.esmeraldapraiahotel.com.br`, imprime na impressora térmica
POS80 (GoldenSky) conectada via USB ao PC.

## Setup em um PC novo (1-clique)

1. **Conecte a impressora** POS80 via USB no Mac.
2. Coloque o **driver `POS_Printer_Driver.pkg`** em `~/Downloads`.
3. **Clone o repo** e abra:
   ```bash
   git clone https://github.com/esmeraldapraiahotel-beep/interno-reservas.git ~/Projetos/interno-reservas
   cd ~/Projetos/interno-reservas
   ```
4. **Duplo-clique em `setup.command`** (ou rode `bash setup.command`).

O script faz tudo:
- ✅ Instala dependências Python (Pillow, qrcode)
- ✅ Abre o instalador do driver POS-80 se ainda não estiver
- ✅ Detecta a impressora térmica conectada via USB
- ✅ Configura a fila CUPS com o PPD oficial
- ✅ Cria LaunchAgent pra iniciar o servidor automaticamente no boot
- ✅ Verifica health e abre o app no navegador

## Estrutura do projeto

```
interno-reservas/
├── index.html           # App principal (emissão de voucher)
├── dashboard.html       # Dashboard de emissões
├── print-server.py      # Servidor local de impressão (porta 9876)
├── logo-esmeralda.png   # Logo do hotel impressa no voucher
├── logo.svg             # Logo Alavantú (uso futuro)
├── setup.command        # ⭐ Instalador one-click
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

```bash
launchctl unload ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
launchctl load   ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
```

### Logs

- `/tmp/voucher-server.log` — saída padrão
- `/tmp/voucher-server.err` — erros

### Parar de iniciar automaticamente

```bash
launchctl unload ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
rm ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
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

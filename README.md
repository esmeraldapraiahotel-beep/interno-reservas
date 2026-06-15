# Vouchers Internos — Esmeralda Praia Hotel

App pra impressão de vouchers internos no balcão de Reservas. Hospedado em
`internoreservas.esmeraldapraiahotel.com.br`, imprime na impressora térmica
GoldenSky (POS80) conectada ao PC.

## Como funciona

```
┌──────────────────────────┐         ┌──────────────────────┐
│ Browser do balcão        │         │ Print server (Python)│
│ internoreservas...com.br │ POST → │ http://localhost:9876│
└──────────────────────────┘         └──────────┬───────────┘
                                                │ lp -d POS80 -o raw
                                                ▼
                                        Impressora térmica
                                            (GoldenSky)
```

- O **frontend** (HTML + JS) é estático, servido pelo VPS.
- O **print server** roda no PC do balcão na porta 9876.
- Toda chamada de impressão vai em `POST http://localhost:9876/print` com JSON
  do voucher → server renderiza HTML → screenshot via Chrome → bitmap ESC/POS →
  manda pra POS80.
- Quando o user esquece de iniciar o servidor, o app mostra um banner vermelho
  embaixo: "Servidor local não respondendo".

## Tipos de voucher disponíveis

- Welcome Drink (sem dados do hóspede)
- Gelato Liberado
- Drink Liberado
- City Tour
- Passeio Pipa
- Passeio Litoral Norte
- Vila CVC · 15% OFF
- Hóspede Raiz
- Hóspede Romântico

Cada tipo tem título, descrição e validade padrão configurados no JS.

## Setup no PC do balcão (uma vez)

```bash
# Instala dependências
pip3 install pillow qrcode

# (opcional) Adiciona um atalho no Desktop
cp start-server.command ~/Desktop/
chmod +x ~/Desktop/start-server.command
```

Depois, duplo-clique em `start-server.command` no Desktop pra iniciar o
servidor toda vez que ligar o computador.

## Setup recorrente (automático ao ligar — macOS)

Crie um `LaunchAgent` em `~/Library/LaunchAgents/com.esmeralda.vouchers.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.esmeralda.vouchers</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/marketingesmeralda/Projetos/interno-reservas/print-server.py</string>
  </array>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/tmp/vouchers-server.log</string>
  <key>StandardErrorPath</key><string>/tmp/vouchers-server.err</string>
</dict>
</plist>
```

Ative com:

```bash
launchctl load ~/Library/LaunchAgents/com.esmeralda.vouchers.plist
```

## Deploy do frontend no VPS

```bash
rsync -az -e "ssh -i ~/.ssh/hostinger_eph" \
  index.html logo.svg \
  root@187.127.26.180:/var/www/internoreservas-esmeralda/
```

E configuração nginx (em `/etc/nginx/sites-enabled/internoreservas`):

```nginx
server {
    server_name internoreservas.esmeraldapraiahotel.com.br;
    root /var/www/internoreservas-esmeralda;
    index index.html;

    location / { try_files $uri /index.html; }

    listen 443 ssl;
    ssl_certificate     /etc/letsencrypt/live/internoreservas.esmeraldapraiahotel.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/internoreservas.esmeraldapraiahotel.com.br/privkey.pem;
}

server {
    listen 80;
    server_name internoreservas.esmeraldapraiahotel.com.br;
    return 301 https://$host$request_uri;
}
```

## Estrutura do projeto

```
interno-reservas/
├── index.html        Frontend single-page
├── print-server.py   Servidor local de impressão
├── logo.svg          Logo Esmeralda Praia Hotel
├── start-server.command   Atalho macOS pra iniciar
└── README.md
```

## Próximos passos

- [ ] Habilitar upload de planilha (.xlsx/.csv) com cabeçalho `nome,quarto,reserva,tipo` → loop de impressão
- [ ] Persistir log de vouchers emitidos no Supabase pra auditoria
- [ ] Adicionar nicho de "Cancelar voucher" (invalidar QR)
- [ ] Modo offline: cache dos últimos 100 vouchers emitidos

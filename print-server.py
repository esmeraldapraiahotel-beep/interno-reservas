#!/usr/bin/env python3
"""
Servidor local de impressão pra app Vouchers Internos (Esmeralda Praia Hotel).

Roda na porta 9876 do PC do hotel. Recebe POST /print com JSON do voucher e
imprime na POS80 (GoldenSky) via CUPS lp.

O app em internoreservas.esmeraldapraiahotel.com.br chama esse servidor via
http://localhost:9876/print pra disparar a impressão local.

Como rodar:
    python3 print-server.py

Dependências (pip):
    pip3 install pillow qrcode flask flask-cors
"""
import os
import sys
import json
import base64
import subprocess
from datetime import datetime
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from PIL import Image
    import qrcode
except ImportError as e:
    print(f"Dependência faltando: {e}. Rode: pip3 install pillow qrcode", file=sys.stderr)
    sys.exit(1)

# ─── Config ──────────────────────────────────────────────────
PORT = int(os.environ.get("VOUCHER_PRINTER_PORT", 9876))
PRINTER = os.environ.get("VOUCHER_PRINTER_NAME", "POS80")
PRINTER_WIDTH = 576  # 80mm @ 8 dots/mm

# Supabase pra logar cada voucher emitido (dashboard usa esses dados)
SUPABASE_URL = "https://lafiidrevxommwtvxcws.supabase.co"
SUPABASE_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxhZmlpZHJldnhvbW13dHZ4Y3dzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwNTAzNzUsImV4cCI6MjA5MjYyNjM3NX0.FFAT4-Dz4zFsvsCL0rC1AAY2DvEC4ohH9xWJfzLXffk"
import urllib.request as _urlreq
import threading as _thread


def log_to_supabase(payload: dict, code: str):
    """Loga voucher emitido no Supabase (fire-and-forget)."""
    def _send():
        try:
            body = json.dumps({
                "code": code,
                "type": payload.get("type", ""),
                "title": payload.get("title", ""),
                "guest_name": payload.get("name") or None,
                "guest_room": payload.get("room") or None,
                "reserva": payload.get("reserva") or None,
                "validade": payload.get("validade") or None,
                "emitted_by": "reservas",
            }).encode("utf-8")
            req = _urlreq.Request(
                f"{SUPABASE_URL}/rest/v1/interno_voucher_log",
                data=body,
                headers={
                    "apikey": SUPABASE_ANON,
                    "Authorization": f"Bearer {SUPABASE_ANON}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                method="POST",
            )
            _urlreq.urlopen(req, timeout=8).read()
        except Exception as e:
            print(f"[log] falhou: {e}")
    _thread.Thread(target=_send, daemon=True).start()

ESC_INIT = b"\x1b\x40"
ESC_CENTER = b"\x1b\x61\x01"
ESC_LEFT = b"\x1b\x61\x00"
ESC_BOLD_ON = b"\x1b\x45\x01"
ESC_BOLD_OFF = b"\x1b\x45\x00"
LF = b"\x0a"
ESC_CUT = b"\x1d\x56\x42\x03"

# ─── Voucher templates ───────────────────────────────────────
SVG_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.svg")


def b64_logo():
    if not os.path.exists(SVG_LOGO_PATH):
        return None
    with open(SVG_LOGO_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def make_qr_b64(text: str) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10, border=2,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


ICONS_BY_TYPE = {
    "gelato": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><circle cx='50' cy='35' r='22' fill='none' stroke='#000' stroke-width='3'/><circle cx='42' cy='32' r='3' fill='#000'/><circle cx='58' cy='32' r='3' fill='#000'/><circle cx='50' cy='40' r='3' fill='#000'/><path d='M30 58 L50 90 L70 58' fill='none' stroke='#000' stroke-width='3' stroke-linejoin='miter'/><path d='M35 62 L65 62 M37 68 L63 68 M40 75 L60 75' stroke='#000' stroke-width='1.5'/></svg>",
    "drink_liberado": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><path d='M25 30 L75 30 L55 55 L55 85 L65 85 M55 85 L45 85 M45 85 L45 55 L25 30' fill='none' stroke='#000' stroke-width='3' stroke-linejoin='round'/><circle cx='50' cy='22' r='3' fill='#000'/></svg>",
    "welcome_drink": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><path d='M25 30 L75 30 L55 55 L55 85 L65 85 M55 85 L45 85 M45 85 L45 55 L25 30' fill='none' stroke='#000' stroke-width='3' stroke-linejoin='round'/><circle cx='50' cy='22' r='3' fill='#000'/></svg>",
    "city_tour": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><circle cx='50' cy='50' r='38' fill='none' stroke='#000' stroke-width='3'/><path d='M12 50 L88 50 M50 12 Q30 50 50 88 Q70 50 50 12' fill='none' stroke='#000' stroke-width='2'/></svg>",
    "passeio_pipa": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><path d='M50 15 L75 50 L50 70 L25 50 Z' fill='none' stroke='#000' stroke-width='3'/><path d='M50 15 L50 70 M25 50 L75 50' stroke='#000' stroke-width='2'/><path d='M50 70 Q45 78 50 85 Q55 78 50 70' fill='none' stroke='#000' stroke-width='2'/></svg>",
    "passeio_litoral_norte": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><path d='M10 65 Q25 55 40 65 Q55 75 70 65 Q85 55 95 65' fill='none' stroke='#000' stroke-width='3' stroke-linecap='round'/><path d='M10 80 Q25 70 40 80 Q55 90 70 80 Q85 70 95 80' fill='none' stroke='#000' stroke-width='3' stroke-linecap='round'/><circle cx='75' cy='25' r='10' fill='none' stroke='#000' stroke-width='3'/></svg>",
    "vila_cvc": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><path d='M20 80 L20 45 L50 22 L80 45 L80 80 Z' fill='none' stroke='#000' stroke-width='3' stroke-linejoin='round'/><path d='M42 80 L42 55 L58 55 L58 80' fill='none' stroke='#000' stroke-width='2'/></svg>",
    "hospede_raiz": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><circle cx='50' cy='35' r='15' fill='none' stroke='#000' stroke-width='3'/><path d='M25 80 Q25 55 50 55 Q75 55 75 80' fill='none' stroke='#000' stroke-width='3'/></svg>",
    "hospede_romantico": "<svg viewBox='0 0 100 100' style='width:80px;height:80px'><path d='M50 85 C30 70 15 55 15 38 C15 25 25 18 35 18 C42 18 47 22 50 28 C53 22 58 18 65 18 C75 18 85 25 85 38 C85 55 70 70 50 85 Z' fill='none' stroke='#000' stroke-width='3' stroke-linejoin='round'/></svg>",
}


FOOTER_BY_TYPE = {
    "gelato": "ESMERALDA PRAIA HOTEL  ·  Gelato Beach",
    "drink_liberado": "ESMERALDA PRAIA HOTEL  ·  Bar",
    "welcome_drink": "ESMERALDA PRAIA HOTEL  ·  Welcome",
    "city_tour": "ESMERALDA PRAIA HOTEL  ·  Recepção",
    "passeio_pipa": "ESMERALDA PRAIA HOTEL  ·  Recepção",
    "passeio_litoral_norte": "ESMERALDA PRAIA HOTEL  ·  Recepção",
    "vila_cvc": "ESMERALDA PRAIA HOTEL  ·  Parceiro CVC",
    "hospede_raiz": "ESMERALDA PRAIA HOTEL",
    "hospede_romantico": "ESMERALDA PRAIA HOTEL",
}


def build_voucher_html(payload: dict) -> str:
    """Gera HTML do voucher no formato landscape, estilo cartão clássico."""
    vtype = payload.get("type", "")
    code = payload.get("code", "—")
    title = payload.get("title", "Voucher")
    # Quebra a descrição em até 2 linhas — split em qualquer fim de frase
    # (. ! ?) seguido de espaço. Permite mensagens longas com 2 sentenças.
    import re as _re
    _desc_raw = payload.get("description") or ""
    _parts = _re.split(r"(?<=[.!?])\s+", _desc_raw, maxsplit=1)
    desc_line_1 = _parts[0]
    desc_line_2 = _parts[1] if len(_parts) > 1 else ""
    # Campos vazios viram linha pra preencher à caneta no balcão.
    # Underscore HTML não renderiza linha contínua, então uso uma borda CSS.
    BLANK_LINE = '<span class="blank"></span>'
    def _v(x):
        return x if (x and str(x).strip()) else BLANK_LINE
    name = _v(payload.get("name"))
    room = _v(payload.get("room"))
    reserva = _v(payload.get("reserva"))
    validade = _v(payload.get("validade"))

    icon_svg = ICONS_BY_TYPE.get(vtype, ICONS_BY_TYPE.get("gelato"))
    footer = FOOTER_BY_TYPE.get(vtype, "ESMERALDA PRAIA HOTEL")

    # Linha de info: 2 colunas. Welcome drink não tem dados de hóspede.
    # extra_label define o rótulo da última linha — pode ser "Validade",
    # "Data do passeio" (city/pipa/litoral) ou "Data do jantar" (romântico).
    extra_label = payload.get("extra_label") or "Válido até"
    info_block = ""
    if vtype != "welcome_drink":
        info_block = f"""
        <div class="info">
          <div class="info-col">
            <div><span class='lbl'>Hóspede:</span> {name}</div>
            <div><span class='lbl'>Reserva:</span> {reserva}</div>
          </div>
          <div class="info-col">
            <div><span class='lbl'>Quarto:</span> {room}</div>
            <div><span class='lbl'>{extra_label}:</span> {validade}</div>
          </div>
        </div>
        <div class="hr"></div>
        """

    # Welcome drink: sem dados pessoais, descrição mais longa
    is_welcome = vtype == "welcome_drink"
    welcome_extra = ""
    if is_welcome:
        welcome_extra = """
        <div class="welcome-desc">
            Prezado Hóspede, seja muito bem-vindo ao Esmeralda Praia Hotel!<br>
            Te oferecemos um delicioso drink de boas-vindas para brindar à sua chegada.
        </div>
        """

    # Hóspede Raiz: troca a descrição por 2 caixas de seleção (atendente
    # marca à caneta qual opção o hóspede escolheu) + mini regulamento.
    is_raiz = vtype == "hospede_raiz"
    raiz_extra = ""
    if is_raiz:
        raiz_extra = """
        <div class="choice-row">
          <div class="choice"><span class="checkbox"></span> Gelato</div>
          <div class="choice"><span class="checkbox"></span> Drink</div>
        </div>
        <div class="rules">
          Vale um drink: Soda Italiana (todos os sabores) ou Vodka Spritz (todos os sabores) ou um vale Gelato tamanho P. 1 por pessoa do apartamento por dia durante o período da sua hospedagem. Este voucher é intransferível e de uso único.
        </div>
        """

    # Orientação: 'horizontal' (default, 132×72mm) ou 'vertical' (72×95mm,
    # economiza ~28% de papel). User escolhe na UI por tipo de voucher.
    orientation = payload.get("orientation", "horizontal")
    if orientation == "vertical":
        page_w, page_h = "72mm", "95mm"
    else:
        page_w, page_h = "132mm", "72mm"

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: {page_w} {page_h}; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ width: {page_w}; height: {page_h}; margin:0; padding:0; background:#fff; color:#000;
                font-family: Georgia, "Times New Roman", serif; overflow: hidden; }}
  .frame {{
    width: {page_w}; height: {page_h};
    padding: 2mm;
    background: #fff;
    overflow: hidden;
    page-break-after: avoid;
    page-break-inside: avoid;
  }}
  .border-outer {{
    width: 100%; height: 100%;
    border: 0.6mm solid #000;
    border-radius: 4mm;
    padding: 1mm;
  }}
  .border-inner {{
    width: 100%; height: 100%;
    border: 0.3mm solid #000;
    border-radius: 2.5mm;
    padding: 3mm 6mm;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}
  /* Layout horizontal otimizado: título topo, depois 2 colunas (texto + código),
     e info do hóspede no rodapé em 2 colunas.
     Vertical: empilha tudo (single column). */
  .top-row {{
    display: flex;
    gap: {("3mm" if orientation == "vertical" else "5mm")};
    align-items: center;
    flex: 1;
    min-height: 0;
    flex-direction: {("column" if orientation == "vertical" else "row")};
  }}
  .top-row .text-side {{ flex: {("0 0 auto" if orientation == "vertical" else "1.4")}; display: flex; flex-direction: column; justify-content: center; width: 100%; }}
  .top-row .code-side {{
    flex: {("0 0 auto" if orientation == "vertical" else "1")};
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    border: 0.4mm solid #000;
    border-radius: 2mm;
    padding: 2mm 2mm;
    {("min-width: 60mm;" if orientation == "vertical" else "min-width: 38mm;")}
  }}
  .top-row .code-side .lbl-code {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 2.1mm;
    text-transform: uppercase;
    letter-spacing: 0.3mm;
    font-weight: 700;
    color: #444;
    margin-bottom: 0.5mm;
  }}
  /* Vertical: info-col em coluna única (Hóspede / Quarto / Reserva / Validade) */
  {(
    ".info { flex-direction: column; gap: 0.5mm; } .info-col:last-child { padding-left: 0; }"
    if orientation == "vertical" else ""
  )}
  .icon {{ display: flex; justify-content: center; margin-bottom: 0.5mm; }}
  .icon svg {{ width: 9mm; height: 9mm; }}
  .title {{
    text-align: center;
    font-family: "Brush Script MT", "Lucida Handwriting", "Apple Chancery", cursive;
    font-style: italic;
    font-size: 8mm;
    line-height: 1;
    margin: 0 0 1mm;
    flex-shrink: 0;
  }}
  .desc {{
    text-align: center;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 2.6mm;
    line-height: 1.32;
    margin: 0;
  }}
  .welcome-desc {{
    text-align: center;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 3mm;
    line-height: 1.35;
    margin: 0;
  }}
  .choice-row {{
    display: flex;
    justify-content: center;
    gap: 6mm;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 3.5mm;
    font-weight: 900;
    margin: 0 0 1.5mm;
  }}
  .choice {{ display: flex; align-items: center; gap: 1.5mm; }}
  .checkbox {{
    display: inline-block;
    width: 4mm; height: 4mm;
    border: 0.5mm solid #000;
    border-radius: 0.6mm;
  }}
  .rules {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 2.1mm;
    line-height: 1.3;
    text-align: center;
    margin: 0;
    color: #000;
  }}
  .hr {{ border-top: 0.3mm solid #000; margin: 1.5mm 0; }}
  .info {{
    display: flex;
    justify-content: space-between;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 2.7mm;
    line-height: 1.4;
    overflow: hidden;
    flex-shrink: 0;
  }}
  .info-col {{ flex: 1; min-width: 0; }}
  .info-col div {{ white-space: nowrap; overflow: visible; }}
  .info-col:last-child {{ text-align: left; padding-left: 3mm; }}
  .lbl {{ font-weight: 900; }}
  .blank {{
    display: inline-block;
    width: 22mm;
    border-bottom: 0.4mm solid #000;
    height: 3.2mm;
    vertical-align: middle;
    margin-left: 1mm;
  }}
  .code {{
    text-align: center;
    font-family: Arial, Helvetica, sans-serif;
    font-weight: 900;
    font-size: 7.5mm;
    letter-spacing: 0.5mm;
    line-height: 1;
    margin: 0;
  }}
  .footer {{
    text-align: center;
    font-family: Arial, Helvetica, sans-serif;
    font-weight: 900;
    font-size: 2.5mm;
    letter-spacing: 0.1mm;
    margin-top: auto;
    padding-top: 1mm;
  }}
</style>
</head><body>
<div class="frame">
  <div class="border-outer">
    <div class="border-inner">
      <div class="title">{title}</div>
      <div class="hr"></div>
      <div class="top-row">
        <div class="text-side">
          {raiz_extra if is_raiz else (welcome_extra if is_welcome else f'<div class="desc">{desc_line_1}{("<br>" + desc_line_2) if desc_line_2 else ""}</div>')}
        </div>
        <div class="code-side">
          <div class="lbl-code">Código</div>
          <div class="code">{code}</div>
        </div>
      </div>
      {('<div class="hr"></div>' + info_block) if info_block else ''}
    </div>
  </div>
</div>
</body></html>
"""


def html_to_pdf(html: str, pdf_path: str) -> bool:
    """Renderiza HTML em PDF via Chrome headless. CUPS usa o filter oficial
    `pos` (do driver POS-80) pra converter o PDF em comandos ESC/POS corretos."""
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    chrome = next((p for p in chrome_paths if os.path.exists(p)), None)
    if not chrome:
        return False
    html_path = pdf_path.replace(".pdf", ".html")
    with open(html_path, "w") as f:
        f.write(html)
    cmd = [
        chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path}",
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        return os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0
    except subprocess.TimeoutExpired:
        return False


def send_pdf_to_printer(pdf_path: str) -> tuple[bool, str]:
    """Manda PDF pra POS80 via lp (CUPS usa filter `pos` oficial).

    Opções importantes:
    - PageCutType=1PartialCutPage: corta após o voucher (sem avançar 30cm)
    - DocCutType=2FullCutPage: corte total ao final do documento
    - media=Custom.132x72mm: força papel custom (sem padding extra)
    """
    try:
        r = subprocess.run(
            ["lp", "-d", PRINTER,
             "-o", "media=Custom.132x72mm",
             "-o", "PageCutType=1PartialCutPage",
             "-o", "DocCutType=2FullCutPage",
             "-o", "fit-to-page",
             pdf_path],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return False, f"lp falhou: {r.stderr.strip()}"
        return True, r.stdout.strip()
    except Exception as e:
        return False, str(e)


def html_to_png(html: str, png_path: str) -> bool:
    """Renderiza HTML em PNG via Chrome headless. Layout landscape 989x576."""
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    chrome = next((p for p in chrome_paths if os.path.exists(p)), None)
    if not chrome:
        return False
    html_path = png_path.replace(".png", ".html")
    with open(html_path, "w") as f:
        f.write(html)
    cmd = [
        chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
        "--window-size=989,576",   # landscape
        f"--screenshot={png_path}",
        f"file://{html_path}",
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        return os.path.exists(png_path) and os.path.getsize(png_path) > 0
    except subprocess.TimeoutExpired:
        return False


def png_to_escpos(png_path: str) -> bytes:
    """Converte PNG landscape em bytes ESC/POS, rotacionando 90° pra caber
    na largura de 576 dots da impressora térmica.

    Layout original: 989 (largura) × 576 (altura)
    Após rotação 90° CCW: 576 (largura) × 989 (altura) → cabe na impressora.
    """
    img = Image.open(png_path).convert("L")
    # Cropa margens brancas do screenshot
    inv = Image.eval(img, lambda p: 255 - p)
    bbox = inv.getbbox()
    if bbox:
        img = img.crop(bbox)

    # Rotaciona 90° anti-horário: o lado mais comprido vira o "comprimento" do papel
    img = img.rotate(90, expand=True, fillcolor=255)

    w, h = img.size
    # Centraliza horizontalmente padando com branco
    if w > PRINTER_WIDTH:
        new_h = int(h * PRINTER_WIDTH / w)
        img = img.resize((PRINTER_WIDTH, new_h), Image.LANCZOS)
    elif w < PRINTER_WIDTH:
        canvas = Image.new("L", (PRINTER_WIDTH, h), 255)
        canvas.paste(img, ((PRINTER_WIDTH - w) // 2, 0))
        img = canvas
    w, h = img.size
    # Threshold simples (sem dithering) — preserva nitidez do QR/texto/bordas.
    # Floyd-Steinberg adicionava ruído de pixels que confundia a impressora térmica.
    img = img.point(lambda p: 0 if p < 160 else 255, mode="1")
    pixels = img.load()

    out = bytearray()
    out += ESC_INIT
    out += ESC_CENTER
    bytes_per_row = PRINTER_WIDTH // 8
    row = 0
    while row < h:
        block_h = min(32, h - row)
        xL = bytes_per_row & 0xFF
        xH = (bytes_per_row >> 8) & 0xFF
        yL = block_h & 0xFF
        yH = (block_h >> 8) & 0xFF
        out += b"\x1d\x76\x30\x00" + bytes([xL, xH, yL, yH])
        for y in range(row, row + block_h):
            for byte_idx in range(bytes_per_row):
                b = 0
                for bit in range(8):
                    x = byte_idx * 8 + bit
                    if pixels[x, y] == 0:
                        b |= (0x80 >> bit)
                out.append(b)
        row += block_h
    out += LF + LF
    out += ESC_CUT
    return bytes(out)


def send_to_printer(escpos_bytes: bytes) -> tuple[bool, str]:
    """Manda bytes pra POS80 via lp -o raw."""
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".escpos") as f:
        f.write(escpos_bytes)
        tmpfile = f.name
    try:
        r = subprocess.run(
            ["lp", "-d", PRINTER, "-o", "raw", tmpfile],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return False, f"lp falhou: {r.stderr.strip()}"
        return True, r.stdout.strip()
    finally:
        try: os.unlink(tmpfile)
        except: pass


def is_printer_available() -> bool:
    try:
        r = subprocess.run(["lpstat", "-p", PRINTER], capture_output=True, text=True, timeout=5)
        return "ociosa" in r.stdout or "idle" in r.stdout.lower() or "imprimindo" in r.stdout
    except: return False


# ─── HTTP Handler ────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {self.client_address[0]} - {fmt % args}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def _json(self, code, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            ok = is_printer_available()
            return self._json(200, {"ok": ok, "printer": PRINTER, "available": ok})
        return self._json(404, {"ok": False, "error": "not_found"})

    def do_POST(self):
        if self.path != "/print":
            return self._json(404, {"ok": False, "error": "not_found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            payload = json.loads(body)
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"invalid_body: {e}"})

        # Pipeline NOVO: HTML → PDF (Chrome headless) → lp (CUPS usa filter `pos`)
        # Antes: gerávamos bitmap ESC/POS manualmente e mandávamos `-o raw`.
        # Agora o driver oficial POS-80 (instalado via .pkg) tem filter próprio
        # que converte raster→ESC/POS — basta mandar o PDF normal.
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            pdf_path = f.name
        try:
            html = build_voucher_html(payload)
            ok = html_to_pdf(html, pdf_path)
            if not ok:
                return self._json(500, {"ok": False, "error": "html_to_pdf_failed"})
            ok, msg = send_pdf_to_printer(pdf_path)
            if not ok:
                return self._json(500, {"ok": False, "error": msg})
            # Log no Supabase (não bloqueia resposta)
            log_to_supabase(payload, payload.get("code", "—"))
            return self._json(200, {"ok": True, "code": payload.get("code"), "msg": msg})
        except Exception as e:
            return self._json(500, {"ok": False, "error": str(e)})
        finally:
            try: os.unlink(pdf_path)
            except: pass
            html_path = pdf_path.replace(".pdf", ".html")
            try: os.unlink(html_path)
            except: pass


def main():
    print(f"╔════════════════════════════════════════════╗")
    print(f"║  Voucher Print Server — Esmeralda          ║")
    print(f"║  Porta: {PORT:<5}   Impressora: {PRINTER:<10}    ║")
    print(f"╚════════════════════════════════════════════╝")
    print(f"Abra: http://internoreservas.esmeraldapraiahotel.com.br")
    print(f"(ou aponte o app pra http://localhost:{PORT}/print)")
    print()

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando…")
        server.shutdown()


if __name__ == "__main__":
    main()

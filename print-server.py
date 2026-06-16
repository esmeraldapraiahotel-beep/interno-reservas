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
import platform
from datetime import datetime
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

try:
    from PIL import Image
    import qrcode
except ImportError as e:
    print(f"Dependência faltando: {e}. Rode: pip3 install pillow qrcode", file=sys.stderr)
    sys.exit(1)

# ─── Config ──────────────────────────────────────────────────
PORT = int(os.environ.get("VOUCHER_PRINTER_PORT", 9876))


def _autodetect_printer() -> str:
    """Acha a primeira impressora com nome ou modelo POS/GoldenSky/thermal.
    Funciona em macOS (lpstat) e Windows (wmic/powershell)."""
    try:
        if IS_WINDOWS:
            r = subprocess.run(
                ["powershell", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"],
                capture_output=True, text=True, timeout=8,
            )
            for line in r.stdout.splitlines():
                name = line.strip()
                if not name:
                    continue
                if "POS" in name.upper() or "GOLDEN" in name.upper() or "THERMAL" in name.upper() or "80" in name:
                    return name
        else:
            r = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                # linha tipo: "impressora POS80 está ociosa..."
                parts = line.split()
                if len(parts) >= 2 and parts[0].lower() in ("impressora", "printer"):
                    name = parts[1]
                    if "POS" in name.upper() or "GOLDEN" in name.upper() or "THERMAL" in name.upper():
                        return name
    except Exception:
        pass
    return "POS80"  # fallback


PRINTER = os.environ.get("VOUCHER_PRINTER_NAME") or _autodetect_printer()
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
    # Quebra a descrição em ate N linhas. Se a descricao tiver \n
    # explicito, respeita. Se nao, faz split em fim de frase (. ! ?) +
    # espaco — ate 2 linhas (legado).
    import re as _re
    _desc_raw = payload.get("description") or ""
    if "\n" in _desc_raw:
        _lines = [l.strip() for l in _desc_raw.split("\n") if l.strip()]
        desc_html = "<br>".join(_lines)
    else:
        _parts = _re.split(r"(?<=[.!?])\s+", _desc_raw, maxsplit=1)
        desc_html = _parts[0] + (("<br>" + _parts[1]) if len(_parts) > 1 else "")
    desc_line_1 = desc_html  # legado (template usa desc_line_1)
    desc_line_2 = ""
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

    # Linha de info CENTRALIZADA: 2 colunas que ficam juntas no centro.
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
        """

    # Welcome drink: sem dados pessoais, descrição mais longa
    is_welcome = vtype == "welcome_drink"
    welcome_extra = ""
    if is_welcome:
        welcome_extra = """
        <div class="welcome-desc">
            Prezado Hóspede, seja muito bem-vindo ao Esmeralda Praia Hotel!<br>
            Te oferecemos um delicioso drink de boas-vindas para brindar à sua chegada.<br><br>
            <b>Horário para retirada dos drinks: 17h30 às 19h30.</b>
        </div>
        """

    # Hóspede Raiz: checkboxes (Gelato/Drink) ANTES do código (atendente marca
    # à caneta) e regulamento DEPOIS, no rodapé. Separados em 2 blocos.
    is_raiz = vtype == "hospede_raiz"
    raiz_choices = ""
    raiz_extra = ""
    if is_raiz:
        raiz_choices = """
        <div class="choice-row">
          <div class="choice"><span class="checkbox"></span> Gelato</div>
          <div class="choice"><span class="checkbox"></span> Drink</div>
        </div>
        """
        raiz_extra = """
        <div class="rules">
          Vale um drink: Soda Italiana (todos os sabores) ou Vodka Spritz (todos os sabores) ou um vale Gelato tamanho P. 1 por pessoa do apartamento por dia durante o período da sua hospedagem. Este voucher é intransferível e de uso único.<br><br>
          <b>Horário para retirada dos drinks: 17h30 às 19h30.</b>
        </div>
        """

    # Orientação: 'horizontal' (default, 132×72mm) ou 'vertical' (72×120mm,
    # economiza ~9% de papel mas usa formato com aspect ratio compatível
    # com o filter POS-80 (evita lixo de raster nas bordas).
    orientation = payload.get("orientation", "vertical")
    is_raiz_check = payload.get("type") == "hospede_raiz"
    if orientation == "vertical":
        # Hóspede Raiz tem mais conteúdo e o topo cortava — mais margem nele.
        page_w, page_h = "72mm", ("235mm" if is_raiz_check else "170mm")
    else:
        page_w, page_h = "132mm", "72mm"

    # Padding do frame (vertical) — Raiz ganha 38mm de topo, comum 28mm.
    if orientation == "vertical":
        frame_pad = "80mm 2mm 12mm 2mm" if is_raiz_check else "28mm 2mm 12mm 2mm"
    else:
        frame_pad = "2mm"

    # Borda em todos (vertical e horizontal) — testado e funcionando.
    show_border = True
    carimbo_h = "30mm" if orientation == "vertical" else "18mm"
    # Vertical é estreito (72mm) — título precisa ser menor pra caber sem cortar.
    title_size = "7.5mm" if orientation == "vertical" else "9mm"

    # Logo Esmeralda (PNG) — base64 inline pra Chrome renderizar
    LOGO_PNG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo-esmeralda.png")
    logo_esmeralda_b64 = ""
    if os.path.exists(LOGO_PNG_PATH):
        with open(LOGO_PNG_PATH, "rb") as f:
            logo_esmeralda_b64 = base64.b64encode(f.read()).decode("ascii")

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: {page_w} {page_h}; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ width: {page_w}; height: {page_h}; margin:0; padding:0; background:#fff; color:#000;
                font-family: Georgia, "Times New Roman", serif; overflow: hidden; }}
  .frame {{
    width: {page_w}; height: {page_h};
    padding: {frame_pad};
    background: #fff;
    overflow: hidden;
    page-break-after: avoid;
    page-break-inside: avoid;
    display: flex;
    flex-direction: column;
  }}
  .border-outer {{
    width: 100%;
    flex: 1;
    min-height: 0;
    {("border: 0.6mm solid #000; border-radius: 3.5mm;" if show_border else "")}
    padding: 3mm 6mm;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}
  /* border-inner removida — a borda dupla causava artefatos de raster
     (lixo de bytes interpretados como texto) na borda direita.
     Mantemos só a externa. */
  .border-inner {{
    width: 100%; height: 100%;
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
  .code-side {{
    display: inline-flex; flex-direction: column;
    align-items: center; justify-content: center;
    border: 0.4mm solid #000;
    border-radius: 2mm;
    padding: 2mm 6mm;
    margin: 0 auto;
  }}
  .code-wrap {{ text-align: center; }}
  .lbl-code {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 2.1mm;
    text-transform: uppercase;
    letter-spacing: 0.3mm;
    font-weight: 700;
    color: #444;
    margin-bottom: 0.5mm;
  }}
  /* Info já é coluna única em ambos os modos (acima) */
  /* Espaço pro carimbo físico do atendente (vertical: 30mm, horizontal: 18mm) */
  .carimbo-area {{
    height: {carimbo_h};
    border: 0.2mm dashed #aaa;
    border-radius: 1.5mm;
    margin: 2.5mm 4mm;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .carimbo-hint {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 2mm;
    color: #999;
    letter-spacing: 0.2mm;
  }}
  /* Logo Esmeralda APÓS a moldura — assinatura do hotel */
  .logo-hotel {{
    text-align: center;
    margin-top: 2mm;
    padding-top: 1mm;
  }}
  .logo-hotel img {{
    width: 12mm;
    height: auto;
    display: block;
    margin: 0 auto 0.5mm;
  }}
  .logo-hotel .hotel-name {{
    font-family: Georgia, "Times New Roman", serif;
    font-size: 3mm;
    font-weight: 700;
    letter-spacing: 0.4mm;
    color: #000;
  }}
  .icon {{ display: flex; justify-content: center; margin-bottom: 0.5mm; }}
  .icon svg {{ width: 9mm; height: 9mm; }}
  .title {{
    text-align: center;
    font-family: "Brush Script MT", "Lucida Handwriting", "Apple Chancery", cursive;
    font-style: italic;
    font-size: {title_size};
    line-height: 1.8;       /* leading bem generoso pra não cortar topo dos glifos */
    padding-top: 6mm;        /* respiro extra acima */
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
    flex-direction: column;
    align-items: center;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 2.7mm;
    line-height: 1.5;
    overflow: hidden;
    flex-shrink: 0;
    text-align: center;
    margin-top: 4mm;
  }}
  .info-col {{ min-width: 0; }}
  .info-col div {{ white-space: nowrap; overflow: visible; }}
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
      {raiz_choices}
      <div class="code-wrap">
        <div class="code-side">
          <div class="lbl-code">Código</div>
          <div class="code">{code}</div>
        </div>
      </div>
      {info_block}
      <div class="carimbo-area">
        <span class="carimbo-hint">Espaço para carimbo</span>
      </div>
      <div class="hr" style="margin-top:auto"></div>
      <div class="text-side">
        {raiz_extra if is_raiz else (welcome_extra if is_welcome else f'<div class="desc">{desc_line_1}{("<br>" + desc_line_2) if desc_line_2 else ""}</div>')}
      </div>
    </div>
  </div>
  <div class="logo-hotel">
    {f'<img src="data:image/png;base64,{logo_esmeralda_b64}" alt="">' if logo_esmeralda_b64 else ""}
  </div>
</div>
</body></html>
"""


def _find_chrome() -> "str | None":
    """Acha Chrome/Edge/Brave em macOS ou Windows."""
    if IS_WINDOWS:
        env = os.environ
        candidates = [
            (env.get("PROGRAMFILES") or "C:\\Program Files") + r"\Google\Chrome\Application\chrome.exe",
            (env.get("PROGRAMFILES(X86)") or "C:\\Program Files (x86)") + r"\Google\Chrome\Application\chrome.exe",
            (env.get("LOCALAPPDATA") or "") + r"\Google\Chrome\Application\chrome.exe",
            (env.get("PROGRAMFILES") or "C:\\Program Files") + r"\Microsoft\Edge\Application\msedge.exe",
            (env.get("PROGRAMFILES(X86)") or "C:\\Program Files (x86)") + r"\Microsoft\Edge\Application\msedge.exe",
        ]
    else:
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    return next((p for p in candidates if p and os.path.exists(p)), None)


def _find_sumatra() -> "str | None":
    """Acha SumatraPDF no Windows (preferencial pra imprimir PDF silenciosamente)."""
    if not IS_WINDOWS:
        return None
    env = os.environ
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "SumatraPDF.exe"),
        (env.get("PROGRAMFILES") or "C:\\Program Files") + r"\SumatraPDF\SumatraPDF.exe",
        (env.get("LOCALAPPDATA") or "") + r"\SumatraPDF\SumatraPDF.exe",
    ]
    return next((p for p in candidates if p and os.path.exists(p)), None)


def html_to_pdf(html: str, pdf_path: str) -> tuple[bool, str]:
    """Renderiza HTML em PDF via Chrome headless. Cross-platform.
    Retorna (ok, msg). msg contem o erro do Chrome quando falha.
    """
    chrome = _find_chrome()
    if not chrome:
        return False, "Chrome/Edge nao encontrado no PC"
    html_path = pdf_path.replace(".pdf", ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    file_url = "file:///" + html_path.replace("\\", "/") if IS_WINDOWS else "file://" + html_path

    # Tenta primeiro --headless=new (Chrome 109+), depois cai pro antigo.
    # Em Windows com Chrome moderno, --headless antigo pode dar exit code 21
    # ou falha silenciosa.
    common = [
        "--disable-gpu",
        "--no-sandbox",
        "--disable-extensions",
        "--no-pdf-header-footer",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}",
    ]
    if IS_WINDOWS:
        # user-data-dir limpa evita problemas de profile/lock
        import tempfile as _tf
        tmp_profile = _tf.mkdtemp(prefix="chrome-voucher-")
        common.append(f"--user-data-dir={tmp_profile}")

    last_err = ""
    for mode in ("--headless=new", "--headless"):
        # remove PDF anterior pra teste limpo
        if os.path.exists(pdf_path):
            try: os.remove(pdf_path)
            except: pass
        cmd = [chrome, mode] + common + [file_url]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            last_err = "timeout (30s) renderizando o PDF"
            continue
        except Exception as e:
            last_err = f"erro ao chamar Chrome: {e}"
            continue
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            return True, f"ok ({mode})"
        # falhou
        err = (r.stderr or "").strip() or (r.stdout or "").strip() or f"exit code {r.returncode}"
        last_err = f"{mode}: {err[:300]}"

    return False, last_err or "Chrome rodou mas nao gerou PDF"


def send_pdf_to_printer(pdf_path: str) -> tuple[bool, str]:
    """Manda PDF pra impressora.
    macOS: lp (CUPS + filter POS-80 oficial)
    Windows: SumatraPDF (silencioso) ou PowerShell Start-Process Print
    """
    if IS_WINDOWS:
        sumatra = _find_sumatra()
        if sumatra:
            try:
                r = subprocess.run(
                    [sumatra, "-print-to", PRINTER, "-print-settings", "fit", "-silent", pdf_path],
                    capture_output=True, text=True, timeout=20,
                )
                if r.returncode == 0:
                    return True, "ok (SumatraPDF)"
                return False, f"SumatraPDF falhou: {r.stderr.strip() or r.stdout.strip()}"
            except Exception as e:
                return False, str(e)
        # Fallback PowerShell — depende do reader default do Windows
        try:
            ps = (
                f"$pdf = '{pdf_path}'; "
                f"Start-Process -FilePath $pdf -Verb PrintTo -ArgumentList '\"{PRINTER}\"' -WindowStyle Hidden -Wait"
            )
            r = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True, timeout=20)
            if r.returncode == 0:
                return True, "ok (PowerShell)"
            return False, f"PowerShell falhou: {r.stderr.strip()}"
        except Exception as e:
            return False, str(e)
    # macOS / Linux — CUPS lp
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
        if IS_WINDOWS:
            r = subprocess.run(
                ["powershell", "-Command", f"(Get-Printer -Name '{PRINTER}').PrinterStatus"],
                capture_output=True, text=True, timeout=5,
            )
            out = r.stdout.strip().lower()
            return bool(out) and "error" not in out and "offline" not in out
        r = subprocess.run(["lpstat", "-p", PRINTER], capture_output=True, text=True, timeout=5)
        return "ociosa" in r.stdout or "idle" in r.stdout.lower() or "imprimindo" in r.stdout
    except Exception:
        return False


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
            ok, pdf_msg = html_to_pdf(html, pdf_path)
            if not ok:
                return self._json(500, {"ok": False, "error": f"html_to_pdf_failed: {pdf_msg}"})
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

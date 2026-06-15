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


def build_voucher_html(payload: dict) -> str:
    """Gera HTML do voucher pronto pra renderizar em PNG."""
    code = payload.get("code", "—")
    title = payload.get("title", "Voucher")
    subtitle = payload.get("subtitle", "")
    description = payload.get("description", "")
    name = payload.get("name") or ""
    room = payload.get("room") or ""
    reserva = payload.get("reserva") or ""
    validade = payload.get("validade") or ""
    obs = payload.get("obs") or ""
    issued = datetime.now().strftime("%d/%m/%Y %H:%M")

    logo_b64 = b64_logo()
    logo_html = ""
    if logo_b64:
        logo_html = f'<div style="display:flex;justify-content:center;margin-bottom:4px"><img src="data:image/svg+xml;base64,{logo_b64}" style="width:34mm;height:auto" alt=""></div>'

    qr_b64 = make_qr_b64(code)

    info_rows = []
    if name:
        info_rows.append(f"<div><strong>Hóspede:</strong> {name}</div>")
    if room:
        info_rows.append(f"<div><strong>Quarto:</strong> {room}</div>")
    if reserva:
        info_rows.append(f"<div><strong>Reserva:</strong> {reserva}</div>")
    if validade:
        info_rows.append(f"<div><strong>Validade:</strong> {validade}</div>")
    info_block = "\n".join(info_rows) if info_rows else ""

    obs_block = f'<div class="obs">Obs.: {obs}</div>' if obs else ""

    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  @page {{ size: 80mm auto; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ width:80mm; margin:0; padding:0; background:#fff; color:#000; font-family: Helvetica, Arial, sans-serif; }}
  .voucher {{
    width: 78mm; max-width:78mm; margin: 0 auto;
    padding: 4mm 1mm 5mm;
    text-align: center;
    font-size: 11pt; line-height: 1.3;
  }}
  .divider {{ border-top: 1.5px dashed #000; margin: 3px 0; }}
  .brand {{ font-weight:900; font-size:15pt; letter-spacing:1.5px; margin-bottom: 2px; line-height:1.1; }}
  .brand-sub {{ font-size:9pt; font-weight:700; letter-spacing:1px; margin-bottom:6px; }}
  .voucher-label {{ font-weight:900; font-size:13pt; letter-spacing:1.5px; margin: 5px 0 3px; }}
  .title {{ margin: 8px 0 2px; font-size:16pt; font-weight:900; line-height:1.15; font-family: Georgia, serif; }}
  .subtitle {{ font-size:10pt; font-weight:600; opacity:0.85; margin-bottom: 4px; }}
  .desc {{ font-size:10pt; margin: 4px 6mm 8px; line-height:1.4; }}
  .qr-wrap {{ display:flex; justify-content:center; margin: 4px 0 6px; }}
  .qr-wrap img {{ width: 38mm; height: 38mm; }}
  .code-box {{
    font-family: Menlo, "Courier New", monospace;
    font-size: 17pt; font-weight:900; letter-spacing: 2px;
    margin: 4px auto 8px; padding: 5px 4px;
    border: 2px solid #000; border-radius: 4px;
    display: inline-block; min-width: 58mm;
  }}
  .info {{ text-align:center; padding: 0 2mm; font-size:10pt; margin-bottom: 6px; }}
  .info div {{ margin: 1px 0; }}
  .obs {{ font-size:9pt; margin: 4px 6mm; font-style: italic; opacity: 0.8; }}
  .footer {{ font-size:9pt; opacity:0.7; margin-top:4px; }}
  .stamp {{ font-size: 8pt; margin-top: 6px; opacity:0.6; }}
</style>
</head><body>
<div class="voucher">
  {logo_html}
  <div class="brand">ESMERALDA PRAIA HOTEL</div>
  <div class="brand-sub">Reservas · Voucher Interno</div>
  <div class="divider"></div>
  <div class="title">{title}</div>
  <div class="subtitle">{subtitle}</div>
  <div class="desc">{description}</div>
  <div class="qr-wrap"><img src="data:image/png;base64,{qr_b64}" alt="QR"></div>
  <div class="code-box">{code}</div>
  <div class="info">
    {info_block}
  </div>
  {obs_block}
  <div class="divider"></div>
  <div class="footer">Apresente este voucher no atendimento</div>
  <div class="stamp">Emitido em {issued}</div>
</div>
</body></html>
"""


def html_to_png(html: str, png_path: str) -> bool:
    """Renderiza HTML em PNG via Chrome headless."""
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
        "--window-size=576,3000",
        f"--screenshot={png_path}",
        f"file://{html_path}",
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30)
        return os.path.exists(png_path) and os.path.getsize(png_path) > 0
    except subprocess.TimeoutExpired:
        return False


def png_to_escpos(png_path: str) -> bytes:
    """Converte PNG em bytes ESC/POS (GS v 0 com blocos de 32 rows)."""
    img = Image.open(png_path).convert("L")
    # Cropa margem branca
    inv = Image.eval(img, lambda p: 255 - p)
    bbox = inv.getbbox()
    if bbox:
        img = img.crop(bbox)
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
    img = img.convert("1", dither=Image.FLOYDSTEINBERG)
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

        # Pipeline: HTML → PNG → ESC/POS → lp
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            png_path = f.name
        try:
            html = build_voucher_html(payload)
            ok = html_to_png(html, png_path)
            if not ok:
                return self._json(500, {"ok": False, "error": "html_to_png_failed"})
            escpos = png_to_escpos(png_path)
            ok, msg = send_to_printer(escpos)
            if not ok:
                return self._json(500, {"ok": False, "error": msg})
            return self._json(200, {"ok": True, "code": payload.get("code"), "msg": msg})
        except Exception as e:
            return self._json(500, {"ok": False, "error": str(e)})
        finally:
            try: os.unlink(png_path)
            except: pass
            html_path = png_path.replace(".png", ".html")
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

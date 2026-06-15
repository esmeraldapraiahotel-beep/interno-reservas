# Esmeralda Praia Hotel — Vouchers Internos
# Instalador one-click pra Windows
# Rodar: clique direito no setup.bat → "Executar como administrador"
#         (ou abra PowerShell e rode: .\setup.ps1)
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ProjectDir

Write-Host ""
Write-Host "======================================================="
Write-Host "  Vouchers Internos — Setup automático (Windows)"
Write-Host "  Esmeralda Praia Hotel"
Write-Host "======================================================="
Write-Host ""

# ─── 1. Python ────────────────────────────────────────────
Write-Host "▸ Verificando Python..."
$python = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command python3 -ErrorAction SilentlyContinue)
if (-not $python) {
    Write-Host "  ✕ Python nao encontrado." -ForegroundColor Red
    Write-Host "  Baixe e instale em: https://www.python.org/downloads/"
    Write-Host "  Marque 'Add Python to PATH' durante a instalacao."
    Read-Host "Pressione ENTER para sair"
    exit 1
}
Write-Host "  ✓ Python: $($python.Source)"

# ─── 2. Dependencias Python ───────────────────────────────
Write-Host "▸ Instalando bibliotecas Python (Pillow, qrcode)..."
& $python.Source -m pip install --user --quiet pillow qrcode 2>&1 | Out-Null
Write-Host "  ✓ Dependencias instaladas"

# ─── 3. SumatraPDF (impressao silenciosa de PDF) ──────────
Write-Host "▸ Baixando SumatraPDF (necessario pra imprimir PDF sem abrir janela)..."
$SumatraPath = Join-Path $ProjectDir "SumatraPDF.exe"
if (-not (Test-Path $SumatraPath)) {
    $url = "https://www.sumatrapdfreader.org/dl/rel/3.5.2/SumatraPDF-3.5.2-64.exe"
    try {
        Invoke-WebRequest -Uri $url -OutFile $SumatraPath -UseBasicParsing
        Write-Host "  ✓ SumatraPDF baixado"
    } catch {
        Write-Host "  ⚠ Nao consegui baixar SumatraPDF. Baixe manualmente:" -ForegroundColor Yellow
        Write-Host "    $url" -ForegroundColor Yellow
        Write-Host "    e salve como SumatraPDF.exe nesta pasta."
    }
} else {
    Write-Host "  ✓ SumatraPDF ja existe"
}

# ─── 4. Driver da POS80 + detecta impressora ──────────────
Write-Host "▸ Procurando impressora termica..."
$printers = Get-Printer | Where-Object {
    $_.Name -match "POS|GoldenSky|Thermal|80"
}

if (-not $printers) {
    # Driver nao instalado — instala do instalador que vem com o projeto
    $InstallerInRepo = Join-Path $ProjectDir "POS80Setup.exe"
    $InstallerInDownloads = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads\POS80Setup_20190329.exe"

    $installer = $null
    if (Test-Path $InstallerInRepo)      { $installer = $InstallerInRepo }
    elseif (Test-Path $InstallerInDownloads) { $installer = $InstallerInDownloads }

    if ($installer) {
        Write-Host "  Driver nao detectado — abrindo instalador..." -ForegroundColor Yellow
        Write-Host "  Siga os passos do instalador (vai pedir confirmacao de administrador)."
        Start-Process -FilePath $installer -Verb RunAs -Wait
        Write-Host "  ✓ Instalador fechado. Verificando..."
        Start-Sleep -Seconds 2
        $printers = Get-Printer | Where-Object { $_.Name -match "POS|GoldenSky|Thermal|80" }
    } else {
        Write-Host "  ✕ Instalador da impressora nao achado." -ForegroundColor Red
        Write-Host "  Coloque POS80Setup_20190329.exe em ~/Downloads ou na pasta do projeto."
        Read-Host "Pressione ENTER para sair"
        exit 1
    }
}

if (-not $printers) {
    Write-Host "  ⚠ Ainda nao achei a impressora apos o driver." -ForegroundColor Yellow
    Write-Host "  Conecte a POS80 via USB e rode setup.bat de novo."
    Read-Host "Pressione ENTER para sair"
    exit 1
}
$printer = $printers[0].Name
Write-Host "  ✓ Impressora: $printer"

# ─── 5. Atalho na pasta Startup (auto-start no boot) ─────
Write-Host "▸ Configurando auto-start no boot..."
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "VouchersInternos.lnk"
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $python.Source
$Shortcut.Arguments = "`"$ProjectDir\print-server.py`""
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.WindowStyle = 7  # minimizado
$Shortcut.Save()
Write-Host "  ✓ Atalho criado em $StartupDir"

# ─── 6. Setar variavel de ambiente com o nome da impressora ─
[Environment]::SetEnvironmentVariable("VOUCHER_PRINTER_NAME", $printer, "User")

# ─── 7. Inicia o servidor agora ───────────────────────────
Write-Host "▸ Iniciando servidor..."
Start-Process -FilePath $python.Source `
    -ArgumentList "`"$ProjectDir\print-server.py`"" `
    -WorkingDirectory $ProjectDir `
    -WindowStyle Minimized
Start-Sleep -Seconds 3

# ─── 8. Health check ──────────────────────────────────────
Write-Host "▸ Testando..."
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:9876/health" -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -eq 200) {
        Write-Host "  ✓ Servidor respondendo em http://localhost:9876"
    }
} catch {
    Write-Host "  ⚠ Servidor nao respondeu ainda. Tente em alguns segundos." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "======================================================="
Write-Host "  Tudo pronto!"
Write-Host "======================================================="
Write-Host ""
Write-Host "Abrindo o app no navegador..."
Start-Process "https://internoreservas.esmeraldapraiahotel.com.br"
Write-Host ""
Read-Host "Pressione ENTER para fechar"

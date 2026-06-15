# Esmeralda Praia Hotel - Vouchers Internos
# Instalador one-click pra Windows (PowerShell 5.1+ compativel)
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ProjectDir

Write-Host ""
Write-Host "======================================================="
Write-Host "  Vouchers Internos - Setup automatico (Windows)"
Write-Host "  Esmeralda Praia Hotel"
Write-Host "======================================================="
Write-Host ""

# --- 1. Python ----------------------------------------------------
Write-Host "[1/8] Verificando Python..."
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $python) {
    Write-Host "  ERRO: Python nao encontrado." -ForegroundColor Red
    Write-Host "  Baixe e instale em: https://www.python.org/downloads/"
    Write-Host "  IMPORTANTE: marque 'Add Python to PATH' durante a instalacao."
    Read-Host "Pressione ENTER para sair"
    exit 1
}
Write-Host "  OK Python: $($python.Source)"

# --- 2. Dependencias Python --------------------------------------
Write-Host "[2/8] Instalando bibliotecas Python (Pillow, qrcode)..."
& $python.Source -m pip install --user --quiet pillow qrcode 2>&1 | Out-Null
Write-Host "  OK Dependencias instaladas"

# --- 3. SumatraPDF ------------------------------------------------
Write-Host "[3/8] Verificando SumatraPDF..."
$SumatraPath = Join-Path $ProjectDir "SumatraPDF.exe"
if (-not (Test-Path $SumatraPath)) {
    Write-Host "  Baixando SumatraPDF..."
    $url = "https://www.sumatrapdfreader.org/dl/rel/3.5.2/SumatraPDF-3.5.2-64.exe"
    try {
        $ProgressPreference = "SilentlyContinue"
        Invoke-WebRequest -Uri $url -OutFile $SumatraPath -UseBasicParsing
        Write-Host "  OK SumatraPDF baixado"
    } catch {
        Write-Host "  AVISO: nao consegui baixar SumatraPDF. Baixe manualmente:" -ForegroundColor Yellow
        Write-Host "    $url" -ForegroundColor Yellow
        Write-Host "    e salve como SumatraPDF.exe nesta pasta."
    }
} else {
    Write-Host "  OK SumatraPDF ja existe"
}

# --- 4. Procura impressora ---------------------------------------
Write-Host "[4/8] Procurando impressora termica..."
$printers = Get-Printer | Where-Object { $_.Name -match "POS|GoldenSky|Thermal|80" }

if (-not $printers) {
    $InstallerInRepo = Join-Path $ProjectDir "POS80Setup.exe"
    $InstallerInDownloads = Join-Path ([Environment]::GetFolderPath("UserProfile")) "Downloads\POS80Setup_20190329.exe"

    $installer = $null
    if (Test-Path $InstallerInRepo) {
        $installer = $InstallerInRepo
    } elseif (Test-Path $InstallerInDownloads) {
        $installer = $InstallerInDownloads
    }

    if ($installer) {
        Write-Host "  Driver nao detectado - abrindo instalador..." -ForegroundColor Yellow
        Write-Host "  Siga os passos do instalador (vai pedir confirmacao de administrador)."
        Start-Process -FilePath $installer -Verb RunAs -Wait
        Write-Host "  Instalador fechado. Verificando..."
        Start-Sleep -Seconds 2
        $printers = Get-Printer | Where-Object { $_.Name -match "POS|GoldenSky|Thermal|80" }
    } else {
        Write-Host "  ERRO: instalador da impressora nao achado." -ForegroundColor Red
        Write-Host "  Esperava POS80Setup.exe nesta pasta ou POS80Setup_20190329.exe em Downloads."
        Read-Host "Pressione ENTER para sair"
        exit 1
    }
}

if (-not $printers) {
    Write-Host "  AVISO: ainda nao achei a impressora apos instalar o driver." -ForegroundColor Yellow
    Write-Host "  Conecte a POS80 via USB e rode setup.bat de novo."
    Read-Host "Pressione ENTER para sair"
    exit 1
}
$printer = $printers[0].Name
Write-Host "  OK Impressora: $printer"

# --- 5. Variavel de ambiente -------------------------------------
Write-Host "[5/8] Configurando nome da impressora..."
[Environment]::SetEnvironmentVariable("VOUCHER_PRINTER_NAME", $printer, "User")
$env:VOUCHER_PRINTER_NAME = $printer
Write-Host "  OK VOUCHER_PRINTER_NAME = $printer"

# --- 6. Atalho na pasta Startup ----------------------------------
Write-Host "[6/8] Configurando auto-start no boot..."
$StartupDir = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupDir "VouchersInternos.lnk"
$WScriptShell = New-Object -ComObject WScript.Shell
$Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $python.Source
$Shortcut.Arguments = '"' + (Join-Path $ProjectDir "print-server.py") + '"'
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.WindowStyle = 7
$Shortcut.Save()
Write-Host "  OK Atalho criado em $StartupDir"

# --- 7. Inicia o servidor ----------------------------------------
Write-Host "[7/8] Iniciando servidor..."
$ScriptPath = Join-Path $ProjectDir "print-server.py"
Start-Process -FilePath $python.Source `
    -ArgumentList ('"' + $ScriptPath + '"') `
    -WorkingDirectory $ProjectDir `
    -WindowStyle Minimized
Start-Sleep -Seconds 3

# --- 8. Health check ---------------------------------------------
Write-Host "[8/8] Testando..."
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:9876/health" -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -eq 200) {
        Write-Host "  OK Servidor respondendo em http://localhost:9876"
    }
} catch {
    Write-Host "  AVISO: servidor nao respondeu ainda. Tente em alguns segundos." -ForegroundColor Yellow
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

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

function Find-RealPython {
    $candidates = @()
    $cmd1 = Get-Command python  -ErrorAction SilentlyContinue
    $cmd2 = Get-Command python3 -ErrorAction SilentlyContinue
    $cmd3 = Get-Command py      -ErrorAction SilentlyContinue
    if ($cmd1) { $candidates += $cmd1.Source }
    if ($cmd2) { $candidates += $cmd2.Source }
    if ($cmd3) { $candidates += $cmd3.Source }
    # Tambem checa instalacoes padrao
    $candidates += "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    $candidates += "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    $candidates += "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe"
    $candidates += "C:\Python312\python.exe"
    $candidates += "C:\Python311\python.exe"
    $candidates += "C:\Python310\python.exe"

    foreach ($p in $candidates) {
        if (-not $p) { continue }
        # Pula o stub falso do Windows Store
        if ($p -like "*WindowsApps*") { continue }
        if (-not (Test-Path $p)) { continue }
        # Testa se realmente roda
        try {
            $v = & $p --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $v -match "Python") {
                return $p
            }
        } catch { }
    }
    return $null
}

$pythonExe = Find-RealPython

if (-not $pythonExe) {
    Write-Host "  Python nao encontrado. Tentando instalar via winget..." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        try {
            & winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements --silent
            Write-Host "  Python instalado. Atualizando PATH..."
            # Recarrega o PATH da sessao
            $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
            Start-Sleep -Seconds 3
            $pythonExe = Find-RealPython
        } catch {
            Write-Host "  Falha ao instalar via winget." -ForegroundColor Red
        }
    }
}

if (-not $pythonExe) {
    Write-Host "  ERRO: Python nao encontrado e nao consegui instalar automatico." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Solucao manual:"
    Write-Host "  1. Abra: https://www.python.org/downloads/"
    Write-Host "  2. Baixe a versao mais recente"
    Write-Host "  3. IMPORTANTE: marque 'Add Python to PATH' na primeira tela"
    Write-Host "  4. Apos instalar, rode este setup novamente"
    Start-Process "https://www.python.org/downloads/"
    Read-Host "Pressione ENTER para sair"
    exit 1
}

$python = [PSCustomObject]@{ Source = $pythonExe }
Write-Host "  OK Python: $pythonExe"

# --- 2. Dependencias Python --------------------------------------
Write-Host "[2/8] Instalando bibliotecas Python (Pillow, qrcode)..."
# pip joga warnings benignos no stderr; isolamos pra nao matar o script
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $pipOutput = & $python.Source -m pip install --quiet --disable-pip-version-check --no-warn-script-location pillow qrcode 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  AVISO: pip retornou codigo $LASTEXITCODE. Tentando com --user..." -ForegroundColor Yellow
        $pipOutput = & $python.Source -m pip install --user --quiet --disable-pip-version-check --no-warn-script-location pillow qrcode 2>&1
    }
} catch {
    Write-Host "  AVISO no pip (continuando): $_" -ForegroundColor Yellow
}
$ErrorActionPreference = $prev

# Valida que pillow e qrcode foram realmente instalados
$check = & $python.Source -c "import PIL, qrcode; print('OK')" 2>&1
if ($check -match "OK") {
    Write-Host "  OK Dependencias instaladas"
} else {
    Write-Host "  ERRO: nao consegui importar Pillow/qrcode." -ForegroundColor Red
    Write-Host "  Saida do pip: $pipOutput"
    Write-Host "  Saida do teste: $check"
    Read-Host "Pressione ENTER para sair"
    exit 1
}

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

@echo off
REM Esmeralda Praia Hotel - Vouchers Internos
REM Atualiza so o print-server.py sem reinstalar nada.
REM Duplo-clique pra rodar.

cd /d "%~dp0"
echo.
echo =====================================================
echo   Atualizar Vouchers Internos (rapido)
echo   Esmeralda Praia Hotel
echo =====================================================
echo.

set "PROJECT_DIR=C:\interno-reservas"
set "FILE=print-server.py"
set "URL=https://raw.githubusercontent.com/esmeraldapraiahotel-beep/interno-reservas/main/print-server.py"

REM 1) Para o servidor antigo
echo [1/4] Parando servidor antigo...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *print-server*" >nul 2>&1
powershell -NoProfile -Command ^
    "Get-NetTCPConnection -LocalPort 9876 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"

REM 2) Backup do arquivo atual (caso precise reverter)
echo [2/4] Fazendo backup...
if exist "%PROJECT_DIR%\%FILE%" copy /Y "%PROJECT_DIR%\%FILE%" "%PROJECT_DIR%\%FILE%.bak" >nul

REM 3) Baixa a versao nova
echo [3/4] Baixando versao nova do GitHub...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile '%PROJECT_DIR%\%FILE%' -UseBasicParsing"
if errorlevel 1 (
    echo   X Falha ao baixar. Restaurando backup...
    if exist "%PROJECT_DIR%\%FILE%.bak" copy /Y "%PROJECT_DIR%\%FILE%.bak" "%PROJECT_DIR%\%FILE%" >nul
    pause
    exit /b 1
)
echo   OK arquivo atualizado

REM 4) Sobe o servidor novamente
echo [4/4] Subindo servidor...
for /f "delims=" %%P in ('powershell -NoProfile -Command "(Get-Command python -ErrorAction SilentlyContinue).Source"') do set "PYTHON=%%P"
if not defined PYTHON (
    echo   AVISO: python nao achado no PATH. Tentando local.
    set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
)
start "" /MIN "%PYTHON%" "%PROJECT_DIR%\%FILE%"
echo   OK servidor iniciando...

REM Aguarda 3 segundos e testa health
timeout /t 3 /nobreak >nul
echo.
echo Testando servidor...
powershell -NoProfile -Command ^
    "try { $r = Invoke-WebRequest -Uri 'http://localhost:9876/health' -UseBasicParsing -TimeoutSec 5; if ($r.StatusCode -eq 200) { Write-Host '  OK servidor respondendo!' -ForegroundColor Green } } catch { Write-Host '  AVISO: servidor nao respondeu ainda, aguarde mais alguns segundos.' -ForegroundColor Yellow }"

echo.
echo =====================================================
echo   Pronto! Recarregue a pagina dos vouchers (F5).
echo =====================================================
echo.
pause

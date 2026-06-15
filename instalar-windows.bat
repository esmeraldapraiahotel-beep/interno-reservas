@echo off
REM Esmeralda Praia Hotel - Vouchers Internos
REM Bootstrap one-click pra Windows
REM Auto-eleva pra administrador (driver da impressora precisa)

setlocal enabledelayedexpansion

REM -- Auto-eleva pra admin: pede senha UMA vez no comeco --
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo Este instalador precisa de privilegios de administrador
    echo para instalar o driver da impressora POS80.
    echo.
    echo Vai aparecer uma janela pedindo confirmacao.
    echo Se sua conta nao for admin, peca a senha do admin do hotel.
    echo.
    timeout /t 3 >nul
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

echo.
echo =====================================================
echo   Vouchers Internos - Instalador (Windows)
echo   Esmeralda Praia Hotel
echo   [rodando como administrador]
echo =====================================================
echo.
echo Este script vai:
echo   1. Baixar o projeto do GitHub
echo   2. Extrair em C:\interno-reservas
echo   3. Rodar o setup automatico (driver + impressora)
echo.

set "DEST=C:\interno-reservas"
set "ZIP=%TEMP%\interno-reservas.zip"
set "URL=https://github.com/esmeraldapraiahotel-beep/interno-reservas/archive/refs/heads/main.zip"

echo [1/4] Baixando projeto...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' -UseBasicParsing"
if errorlevel 1 (
    echo   X Falha ao baixar. Verifique sua conexao.
    pause
    exit /b 1
)

echo [2/4] Extraindo...
if exist "%DEST%" rmdir /s /q "%DEST%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -Path '%ZIP%' -DestinationPath '%TEMP%\interno-reservas-extract' -Force; Move-Item -Path '%TEMP%\interno-reservas-extract\interno-reservas-main' -Destination '%DEST%' -Force; Remove-Item -Path '%TEMP%\interno-reservas-extract' -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -Path '%ZIP%' -Force"

echo [3/4] Verificando dependencias...
echo   (o setup vai instalar Python automaticamente se precisar)

echo [4/4] Rodando setup automatico...
cd /d "%DEST%"
call setup.bat

endlocal

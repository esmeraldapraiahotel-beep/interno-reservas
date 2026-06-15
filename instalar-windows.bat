@echo off
REM Esmeralda Praia Hotel - Vouchers Internos
REM Bootstrap one-click pra Windows
REM Baixa o projeto, extrai e roda o setup. Zero pre-requisitos.

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo =====================================================
echo   Vouchers Internos - Instalador (Windows)
echo   Esmeralda Praia Hotel
echo =====================================================
echo.
echo Este script vai:
echo   1. Baixar o projeto do GitHub
echo   2. Extrair em C:\interno-reservas
echo   3. Rodar o setup automatico (driver + impressora)
echo.
pause

set "DEST=C:\interno-reservas"
set "ZIP=%TEMP%\interno-reservas.zip"
set "URL=https://github.com/esmeraldapraiahotel-beep/interno-reservas/archive/refs/heads/main.zip"

echo.
echo [1/4] Baixando projeto...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri '%URL%' -OutFile '%ZIP%' -UseBasicParsing"
if errorlevel 1 (
    echo   X Falha ao baixar. Verifique sua conexao.
    pause
    exit /b 1
)

echo [2/4] Extraindo...
if exist "%DEST%" rmdir /s /q "%DEST%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Expand-Archive -Path '%ZIP%' -DestinationPath '%TEMP%\interno-reservas-extract' -Force; Move-Item -Path '%TEMP%\interno-reservas-extract\interno-reservas-main' -Destination '%DEST%' -Force; Remove-Item -Path '%TEMP%\interno-reservas-extract' -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item -Path '%ZIP%' -Force"

echo [3/4] Verificando Python...
where python >nul 2>nul
if errorlevel 1 (
    echo   X Python nao instalado.
    echo   Abrindo download do Python...
    echo   IMPORTANTE: marque "Add Python to PATH" durante a instalacao.
    start https://www.python.org/downloads/
    echo.
    echo   Apos instalar o Python, rode este instalador de novo.
    pause
    exit /b 1
)

echo [4/4] Rodando setup automatico...
cd /d "%DEST%"
call setup.bat

endlocal

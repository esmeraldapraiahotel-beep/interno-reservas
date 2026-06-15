@echo off
REM Esmeralda Praia Hotel - Vouchers Internos
REM Instalador one-click pra Windows
REM Duplo-clique pra rodar.

cd /d "%~dp0"
echo.
echo ====================================================
echo   Vouchers Internos - Setup automatico (Windows)
echo   Esmeralda Praia Hotel
echo ====================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
pause

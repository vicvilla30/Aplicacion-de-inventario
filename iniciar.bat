@echo off
title Inventario LSI - Servidor
color 0A
cls

echo ============================================
echo    SISTEMA DE INVENTARIO LSI
echo    Iniciando servidor...
echo ============================================
echo.

REM Cambiar al directorio del script
cd /d "%~dp0"

REM Activar entorno virtual si existe
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Entorno virtual activado
) else (
    echo [AVISO] Usando Python global
)

echo.
echo ============================================
echo    SERVIDOR INICIADO
echo ============================================
echo.
echo    Accede desde cualquier PC en la red:
echo    http://%COMPUTERNAME%:5000
echo.
echo    O desde la IP local:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    echo    http:%%a:5000
)
echo.
echo ============================================
echo    Presiona Ctrl+C para detener
echo ============================================
echo.

REM Iniciar aplicación
python app.py --production

pause
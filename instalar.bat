@echo off
title Instalador - Inventario LSI
color 0B
cls

echo ============================================
echo    INSTALADOR - INVENTARIO LSI v1.0
echo ============================================
echo.
pause

echo [1/4] Verificando Python...
python --version
if errorlevel 1 (
    echo.
    echo ERROR: Python NO esta instalado
    echo Descargalo desde: https://www.python.org/downloads/
    echo.
    pause
    exit /b
)
echo [OK] Python instalado
echo.

echo [2/4] Creando entorno virtual...
if exist "venv\" (
    echo [OK] Entorno virtual ya existe
) else (
    python -m venv venv
    echo [OK] Entorno virtual creado
)
echo.

echo [3/4] Instalando dependencias...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo [OK] Dependencias instaladas
echo.

echo [4/4] Configurando firewall...
netsh advfirewall firewall add rule name="Inventario LSI" dir=in action=allow protocol=TCP localport=5000
echo [OK] Firewall configurado
echo.

cls
echo ============================================
echo    INSTALACION COMPLETADA
echo ============================================
echo.
echo Ahora ejecuta: iniciar.bat
echo.
pause
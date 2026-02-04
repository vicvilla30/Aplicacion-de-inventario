@echo off
echo Creando archivos necesarios...

REM Crear requirements.txt
(
echo Flask==3.0.0
echo pandas==2.1.4
echo openpyxl==3.1.2
echo Werkzeug==3.0.1
) > requirements.txt

REM Crear iniciar.bat
(
echo @echo off
echo title Inventario LSI - Servidor
echo color 0A
echo cls
echo.
echo ============================================
echo    SISTEMA DE INVENTARIO LSI
echo    Iniciando servidor...
echo ============================================
echo.
echo Activando entorno virtual...
echo.
echo cd /d "%%~dp0"
echo if exist "venv\Scripts\activate.bat" ^(
echo     call venv\Scripts\activate.bat
echo ^)
echo.
echo python app.py
echo pause
) > iniciar.bat

REM Crear instalar.bat
(
echo @echo off
echo title Instalador Inventario LSI
echo echo ============================================
echo echo    INSTALADOR - INVENTARIO LSI
echo echo ============================================
echo echo.
echo echo [1/4] Verificando Python...
echo python --version
echo if errorlevel 1 ^(
echo     echo ERROR: Python no instalado
echo     pause
echo     exit /b
echo ^)
echo echo.
echo echo [2/4] Creando entorno virtual...
echo python -m venv venv
echo echo.
echo echo [3/4] Instalando dependencias...
echo call venv\Scripts\activate.bat
echo pip install -r requirements.txt
echo echo.
echo echo [4/4] Configurando firewall...
echo netsh advfirewall firewall add rule name="Inventario LSI" dir=in action=allow protocol=TCP localport=5000
echo echo.
echo echo ============================================
echo echo    INSTALACION COMPLETA
echo echo ============================================
echo pause
) > instalar.bat

REM Crear ver_ip.bat
(
echo @echo off
echo echo ============================================
echo echo    DIRECCION IP DEL SERVIDOR
echo echo ============================================
echo echo.
echo hostname
echo ipconfig ^| findstr /c:"IPv4"
echo echo.
echo echo Accede desde: http://ESTA-IP:5000
echo echo.
echo pause
) > ver_ip.bat

echo.
echo ============================================
echo    ARCHIVOS CREADOS CORRECTAMENTE
echo ============================================
echo.
echo Se crearon los siguientes archivos:
echo   - requirements.txt
echo   - iniciar.bat
echo   - instalar.bat
echo   - ver_ip.bat
echo.
echo Ahora ejecuta: instalar.bat
echo.
pause
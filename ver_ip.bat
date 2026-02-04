@echo off
cls
echo ============================================
echo    DIRECCION IP DEL SERVIDOR
echo ============================================
echo.
echo Nombre del servidor:
hostname
echo.
echo Direccion IP:
ipconfig | findstr /c:"IPv4"
echo.
echo ============================================
echo Accede desde: http://IP-DE-ARRIBA:5000
echo ============================================
echo.
pause